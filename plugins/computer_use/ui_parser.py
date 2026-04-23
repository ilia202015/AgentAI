"""
Модуль для парсинга пользовательского интерфейса (UI) на основе скриншотов.
Обеспечивает трансформацию изображения в структурированный текстовый формат.

Стек:
1. RapidOCR (ONNX) - Быстрая детекция рамок текста.
2. EasyOCR (PyTorch) - Точное распознавание текста (кириллицы) в найденных рамках.
3. OpenCV (Canny) - Изоляция интерактивных элементов UI через маскирование текста.
4. MobileCLIP (Apple FastViT) - Сверхбыстрая Zero-Shot классификация иконок.
"""

import os
import base64
from collections import defaultdict
import urllib.request

import cv2
import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F

import easyocr
from rapidocr_onnxruntime import RapidOCR
import mobileclip

# Глобальные переменные для ленивой загрузки моделей (Singleton Pattern)
# Это предотвращает повторную инициализацию тяжелых моделей при каждом вызове.
_RAPID_ENGINE = None
_EASY_READER = None
_MC_MODEL = None
_MC_PREPROCESS = None
_MC_TOKENIZER = None
_TEXT_FEATURES = None

# Расширенный словарь визуальных описаний UI-элементов для MobileCLIP
_CANDIDATE_LABELS = [
    "google chrome browser logo", "file explorer yellow folder", 
    "windows 11 start button blue window", "telegram paper plane app icon", 
    "yandex browser red letter Y icon", "vscode code editor blue ribbon icon",
    "terminal command prompt black window icon", "green square menu button with three horizontal lines",
    "radio button empty circle", "radio button selected circle with dot", 
    "browser tab shape", "settings gear with letter Z inside",
    "settings cogwheel icon", "magnifying glass search icon", 
    "arrow pointing left back button", "green checkmark inside square",
    "white letter H inside black square logo", "purple ghost alien icon",
    "pink human brain icon", "blue paper plane send message button",
    "monitor display screen icon", "magic wand with sparkles icon",
    "pink pencil edit draw icon", "globe internet web icon",
    "refresh circular arrow icon", "shield security padlock icon",
    "plus add blue cross button", "stopwatch timer clock icon",
    "github cat octopus logo icon", "robot face bot icon", "red ABP adblock icon",
    "square button with number inside", "menu button with three dots", "bookmark flag icon"
]

def _init_models():
    """
    Инициализирует модели ИИ при первом вызове функции.
    Загружает веса MobileCLIP с серверов Apple, если они отсутствуют локально.
    """
    global _RAPID_ENGINE, _EASY_READER, _MC_MODEL, _MC_PREPROCESS, _MC_TOKENIZER, _TEXT_FEATURES
    if _RAPID_ENGINE is None:
        # Инициализация OCR движков
        _RAPID_ENGINE = RapidOCR()
        _EASY_READER = easyocr.Reader(['ru', 'en'], gpu=False, verbose=False)
        
        # Загрузка весов MobileCLIP (фоллбэк, так как библиотека Apple не качает их автоматически корректно)
        ckpt_path = os.path.join(os.path.dirname(__file__), "mobileclip_s0.pt")
        if not os.path.exists(ckpt_path):
            url = "https://docs-assets.developer.apple.com/ml-research/datasets/mobileclip/mobileclip_s0.pt"
            urllib.request.urlretrieve(url, ckpt_path)
            
        # Инициализация VLM
        _MC_MODEL, _, _MC_PREPROCESS = mobileclip.create_model_and_transforms('mobileclip_s0', pretrained=ckpt_path)
        _MC_TOKENIZER = mobileclip.get_tokenizer('mobileclip_s0')
        _MC_MODEL.eval()
        
        # Предвычисление текстовых признаков (Text Features) для ускорения классификации
        with torch.no_grad():
            _TEXT_FEATURES = _MC_MODEL.encode_text(_MC_TOKENIZER(_CANDIDATE_LABELS))
            _TEXT_FEATURES = F.normalize(_TEXT_FEATURES, dim=-1)

def get_iou(boxA, boxB):
    """Вычисляет Intersection over Union (IoU) для фильтрации пересекающихся рамок."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    if boxAArea == 0: return 0
    return interArea / float(boxAArea)

def contains(box_outer, box_inner):
    """Проверяет, находится ли box_inner внутри box_outer (с небольшим допуском)."""
    return (box_inner[0] >= box_outer[0] - 2 and 
            box_inner[1] >= box_outer[1] - 2 and 
            box_inner[2] <= box_outer[2] + 2 and 
            box_inner[3] <= box_outer[3] + 2)

def ui_parser(base64_image: str) -> str:
    """
    Главная функция парсинга интерфейса.
    
    Args:
        base64_image (str): Изображение скриншота, закодированное в Base64.
        
    Returns:
        str: Структурированный текстовый отчет (TSV/CSV-like).
             Формат:
             текст
             <x1>;<y1>;<x2>;<y2>;<содержимое_текста>
             <имя_класса_ui>
             <x1>;<y1>;<x2>;<y2>
             неопознано
             <x1>;<y1>;<x2>;<y2>
    """
    # 1. Декодируем base64
    if base64_image.startswith("data:image"):
        base64_image = base64_image.split(",")[1]
        
    try:
        img_data = base64.b64decode(base64_image)
        nparr = np.frombuffer(img_data, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            return "Ошибка: не удалось декодировать изображение."
    except Exception as e:
        return f"Ошибка обработки base64: {e}"
        
    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    height, width = img_gray.shape
    
    # 2. Инициализируем модели (выполняется 1 раз за время жизни процесса)
    _init_models()
    
    # === ЭТАП 1: OCR (Поиск текста) ===
    rapid_res, _ = _RAPID_ENGINE(img_bgr)
    text_results = []
    text_mask_boxes = []
    
    if rapid_res:
        for item in rapid_res:
            box_pts = item[0]
            xs = [pt[0] for pt in box_pts]
            ys = [pt[1] for pt in box_pts]
            x1, y1 = int(min(xs)), int(min(ys))
            x2, y2 = int(max(xs)), int(max(ys))
            
            # Немного расширяем рамку для лучшего захвата букв в EasyOCR
            pad = 4
            cx1, cy1 = max(0, x1-pad), max(0, y1-pad)
            cx2, cy2 = min(width, x2+pad), min(height, y2+pad)
            
            crop = img_gray[cy1:cy2, cx1:cx2]
            if crop.size > 0:
                # EasyOCR читает кириллицу внутри найденной рамки
                easy_res = _EASY_READER.readtext(crop, detail=0)
                if easy_res:
                    txt = " ".join(easy_res).strip()
                    if txt:
                        text_results.append((x1, y1, x2, y2, txt))
                        text_mask_boxes.append((x1, y1, x2, y2))
                        
    # === ЭТАП 2: Детекция интерфейса (OpenCV) ===
    edges = cv2.Canny(img_gray, 20, 60)
    
    # Выжигаем текст черным цветом, чтобы он не определялся как элементы UI
    for (x1, y1, x2, y2) in text_mask_boxes:
        cv2.rectangle(edges, (x1, y1), (x2, y2), 0, -1)
        
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    
    # Ищем все замкнутые контуры (включая вложенные элементы)
    contours, _ = cv2.findContours(closed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    raw_ui_boxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # Отбраковываем мусор (мелкие точки) и гигантские рамки (контейнеры окон)
        if 10 < w < 120 and 10 < h < 120:
            raw_ui_boxes.append((x, y, x+w, y+h))
            
    # Non-Maximum Suppression (NMS) для удаления дубликатов и вложенных рамок
    final_ui_boxes = []
    raw_ui_boxes.sort(key=lambda b: (b[2]-b[0])*(b[3]-b[1]), reverse=True)
    for b in raw_ui_boxes:
        is_inside = False
        for pb in final_ui_boxes:
            if contains(pb, b):
                is_inside = True
                break
        if not is_inside:
            overlap = False
            for kb in final_ui_boxes:
                if get_iou(b, kb) > 0.6: # Допуск для пересекающихся кнопок
                    overlap = True
                    break
            if not overlap:
                final_ui_boxes.append(b)
                
    # === ЭТАП 3: Классификация иконок (MobileCLIP Zero-Shot) ===
    ui_results = defaultdict(list)
    
    with torch.no_grad():
        for (x1, y1, x2, y2) in final_ui_boxes:
            pad = 8
            cx1, cy1 = max(0, x1-pad), max(0, y1-pad)
            cx2, cy2 = min(width, x2+pad), min(height, y2+pad)
            crop = img_bgr[cy1:cy2, cx1:cx2]
            if crop.size == 0: continue
            
            crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(crop_rgb)
            
            # Подготовка тензора картинки
            image_tensor = _MC_PREPROCESS(img_pil).unsqueeze(0)
            image_features = _MC_MODEL.encode_image(image_tensor)
            image_features = F.normalize(image_features, dim=-1)
            
            # Вычисление косинусного сходства со словарем (Cosine Similarity)
            similarity = (100.0 * image_features @ _TEXT_FEATURES.T).softmax(dim=-1)
            best_idx = similarity.argmax().item()
            conf = similarity[0, best_idx].item() * 100
            
            # Порог уверенности 70% для защиты от галлюцинаций
            if conf >= 70.0:
                label = _CANDIDATE_LABELS[best_idx]
            else:
                label = "неопознано"
                
            ui_results[label].append((x1, y1, x2, y2))
            
    # === ЭТАП 4: Форматирование результата (Строка TSV-формата) ===
    output_lines = ["текст"]
    for (x1, y1, x2, y2, txt) in text_results:
        output_lines.append(f"{x1};{y1};{x2};{y2};{txt}")
        
    for label in sorted(ui_results.keys()):
        if label == "неопознано": continue
        output_lines.append(label)
        for (x1, y1, x2, y2) in ui_results[label]:
            output_lines.append(f"{x1};{y1};{x2};{y2}")
            
    # Класс "неопознано" всегда идет в самом конце
    if "неопознано" in ui_results:
        output_lines.append("неопознано")
        for (x1, y1, x2, y2) in ui_results["неопознано"]:
            output_lines.append(f"{x1};{y1};{x2};{y2}")
            
    return "\n".join(output_lines)

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
from PIL import Image, ImageDraw, ImageFont
import torch
import torch.nn.functional as F

import easyocr
from rapidocr_onnxruntime import RapidOCR
import mobileclip


# Контейнер для моделей с поддержкой корректного пиклинга (для Autosave)
class UIModelContainer:
    def __init__(self):
        self.rapid = None
        self.easy = None
        self.mc_model = None
        self.mc_preprocess = None
        self.mc_tokenizer = None
        self.text_features = None

    def __getstate__(self):
        # При попытке сохранить состояние (pickle/dill), мы возвращаем пустой словарь.
        # Это заставляет пиклер игнорировать тяжелые и непиклируемые объекты (ONNX/Torch).
        return {}

    def __setstate__(self, state):
        # При восстановлении из сейва обнуляем ссылки, чтобы они переинициализировались лениво.
        self.__init__()

_MODELS = UIModelContainer()


# Флаг для отладки: сохранение размеченного скриншота в логах
DEBUG_SAVE_PARSED_IMAGE = True

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
    global _MODELS
    if _MODELS.rapid is None:
        # Инициализация OCR движков
        _MODELS.rapid = RapidOCR()
        _MODELS.easy = easyocr.Reader(['ru', 'en'], gpu=False, verbose=False)
        
        # Загрузка весов MobileCLIP
        ckpt_path = os.path.join(os.path.dirname(__file__), "mobileclip_s0.pt")
        if not os.path.exists(ckpt_path):
            url = "https://docs-assets.developer.apple.com/ml-research/datasets/mobileclip/mobileclip_s0.pt"
            urllib.request.urlretrieve(url, ckpt_path)
            
        # Инициализация VLM
        _MODELS.mc_model, _, _MODELS.mc_preprocess = mobileclip.create_model_and_transforms('mobileclip_s0', pretrained=ckpt_path)
        _MODELS.mc_tokenizer = mobileclip.get_tokenizer('mobileclip_s0')
        _MODELS.mc_model.eval()
        
        # Предвычисление текстовых признаков
        with torch.no_grad():
            _MODELS.text_features = _MODELS.mc_model.encode_text(_MODELS.mc_tokenizer(_CANDIDATE_LABELS))
            _MODELS.text_features = F.normalize(_MODELS.text_features, dim=-1)


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
    
    _init_models()
    
    # === ЭТАП 1: OCR Детектор (RapidOCR) ===
    rapid_res, _ = _MODELS.rapid(img_bgr)
    raw_text_boxes = []
    
    if rapid_res:
        for item in rapid_res:
            box_pts = item[0]
            xs = [pt[0] for pt in box_pts]
            ys = [pt[1] for pt in box_pts]
            raw_text_boxes.append([int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))])
            
    # === ЭТАП 2: Умная склейка текста (ТОЛЬКО для результатов OCR) ===
    raw_text_boxes.sort(key=lambda b: (b[1], b[0]))
    
    merged_boxes = []
    for box in raw_text_boxes:
        x1, y1, x2, y2 = box
        h = y2 - y1
        placed = False
        for m_box in merged_boxes:
            mx1, my1, mx2, my2 = m_box
            mh = my2 - my1
            y_overlap = max(0, min(y2, my2) - max(y1, my1))
            min_h = min(h, mh)
            if min_h > 0 and (y_overlap / min_h) > 0.4:
                threshold = max(h, mh) * 2.5
                if (x1 <= mx2 + threshold) and (x2 >= mx1 - threshold):
                    m_box[0] = min(mx1, x1)
                    m_box[1] = min(my1, y1)
                    m_box[2] = max(mx2, x2)
                    m_box[3] = max(my2, y2)
                    placed = True
                    break
        if not placed:
            merged_boxes.append([x1, y1, x2, y2])
            
    final_merged = []
    for box in merged_boxes:
        x1, y1, x2, y2 = box
        h = y2 - y1
        placed = False
        for m_box in final_merged:
            mx1, my1, mx2, my2 = m_box
            mh = my2 - my1
            y_overlap = max(0, min(y2, my2) - max(y1, my1))
            min_h = min(h, mh)
            if min_h > 0 and (y_overlap / min_h) > 0.4:
                threshold = max(h, mh) * 2.5
                if (x1 <= mx2 + threshold) and (x2 >= mx1 - threshold):
                    m_box[0] = min(mx1, x1)
                    m_box[1] = min(my1, y1)
                    m_box[2] = max(mx2, x2)
                    m_box[3] = max(my2, y2)
                    placed = True
                    break
        if not placed:
            final_merged.append(box)

    # === ЭТАП 3: Распознавание склеенного текста (EasyOCR) ===
    text_results = []
    valid_text_boxes = []
    for box in final_merged:
        x1, y1, x2, y2 = box
        pad = 6
        cx1, cy1 = max(0, x1-pad), max(0, y1-pad)
        cx2, cy2 = min(width, x2+pad), min(height, y2+pad)
        crop = img_gray[cy1:cy2, cx1:cx2]
        if crop.size > 0:
            easy_res = _MODELS.easy.readtext(crop, detail=0, paragraph=True)
            if easy_res:
                txt = " ".join(easy_res).strip()
                if txt:
                    text_results.append((x1, y1, x2, y2, txt))
                    valid_text_boxes.append(box)

    # === ЭТАП 4: OpenCV Детекция иконок ===
    edges = cv2.Canny(img_gray, 20, 60)
    
    # Маскируем только подтвержденный текст
    for (x1, y1, x2, y2) in valid_text_boxes:
        cv2.rectangle(edges, (x1, y1), (x2, y2), 0, -1)
        
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(closed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    raw_ui_boxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if 10 < w < 120 and 10 < h < 120:
            raw_ui_boxes.append([x, y, x+w, y+h])
            
    icons_boxes = []
    raw_ui_boxes.sort(key=lambda b: (b[2]-b[0])*(b[3]-b[1]), reverse=True)
    for b in raw_ui_boxes:
        is_inside = False
        for pb in icons_boxes:
            if contains(pb, b):
                is_inside = True
                break
        if not is_inside:
            overlap = False
            for kb in icons_boxes:
                if get_iou(b, kb) > 0.6:
                    overlap = True
                    break
            if not overlap:
                icons_boxes.append(b)

    # === ЭТАП 5: Классификация иконок (MobileCLIP) ===
    ui_results = defaultdict(list)
    with torch.no_grad():
        for (x1, y1, x2, y2) in icons_boxes:
            pad = 8
            cx1, cy1 = max(0, x1-pad), max(0, y1-pad)
            cx2, cy2 = min(width, x2+pad), min(height, y2+pad)
            crop = img_bgr[cy1:cy2, cx1:cx2]
            if crop.size == 0: continue
            
            crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(crop_rgb)
            
            image_tensor = _MODELS.mc_preprocess(img_pil).unsqueeze(0)
            image_features = _MODELS.mc_model.encode_image(image_tensor)
            image_features = F.normalize(image_features, dim=-1)
            
            similarity = (100.0 * image_features @ _MODELS.text_features.T).softmax(dim=-1)
            best_idx = similarity.argmax().item()
            conf = similarity[0, best_idx].item() * 100
            
            if conf >= 70.0:
                label = _CANDIDATE_LABELS[best_idx]
            else:
                label = "неопознано"
                
            ui_results[label].append((x1, y1, x2, y2))

    # === ЭТАП 6: Форматирование результата ===
    output_lines = ["текст"]
    for (x1, y1, x2, y2, txt) in text_results:
        output_lines.append(f"{x1};{y1};{x2};{y2};{txt}")
        
    for label in sorted(ui_results.keys()):
        if label == "неопознано": continue
        output_lines.append(label)
        for (x1, y1, x2, y2) in ui_results[label]:
            output_lines.append(f"{x1};{y1};{x2};{y2}")
            
    if "неопознано" in ui_results:
        output_lines.append("неопознано")
        for (x1, y1, x2, y2) in ui_results["неопознано"]:
            output_lines.append(f"{x1};{y1};{x2};{y2}")

    # === ЭТАП 7: Отладка (Сохранение картинки) ===
    if DEBUG_SAVE_PARSED_IMAGE:
        try:
            import datetime
            from PIL import ImageDraw, ImageFont
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            draw = ImageDraw.Draw(pil_img)
            
            try:
                font_paths = [
                    "C:/Windows/Fonts/arial.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/System/Library/Fonts/Cache/Arial.ttf"
                ]
                font = None
                for p in font_paths:
                    if os.path.exists(p):
                        font = ImageFont.truetype(p, 14)
                        break
                if not font:
                    font = ImageFont.load_default()
            except:
                font = ImageFont.load_default()

            for (x1, y1, x2, y2, txt) in text_results:
                draw.rectangle([x1, y1, x2, y2], outline=(0, 255, 0), width=2)
                draw.text((x1, y1 - 18), txt[:20], fill=(0, 255, 0), font=font)
                
            for label, boxes in ui_results.items():
                color = (0, 0, 255) if label != "неопознано" else (255, 0, 0)
                for (x1, y1, x2, y2) in boxes:
                    draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
                    if label != "неопознано":
                        short_label = label.split()[-1]
                        draw.text((x1, y2 + 5), short_label, fill=color, font=font)

            logs_dir = os.path.join(os.path.dirname(__file__), "logs")
            os.makedirs(logs_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filepath = os.path.join(logs_dir, f"parsed_{timestamp}.png")
            pil_img.save(filepath)
        except Exception as e:
            print(f"Ошибка при сохранении отладочного изображения: {e}")

    return "\n".join(output_lines)

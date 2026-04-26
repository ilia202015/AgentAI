"""
Модуль для парсинга пользовательского интерфейса (UI) на основе скриншотов.
Обеспечивает трансформацию изображения в структурированный текстовый формат.

Стек:
1. RapidOCR (ONNX) - Быстрая детекция рамок текста.
2. EasyOCR (PyTorch) - Точное распознавание скрытого текста в найденных рамках.
3. OpenCV (Canny) - Изоляция интерактивных элементов UI через маскирование текста.
4. MobileCLIP (Apple FastViT) - Сверхбыстрая Zero-Shot классификация иконок.
"""

import os
import base64
from collections import defaultdict
import urllib.request
import time

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
        return {}

    def __setstate__(self, state):
        self.__init__()

_MODELS = UIModelContainer()

# Флаг для отладки: сохранение размеченного скриншота в логах
DEBUG_SAVE_PARSED_IMAGE = True

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
    """Инициализирует модели ИИ при первом вызове функции."""
    global _MODELS
    if _MODELS.rapid is None:
        _MODELS.rapid = RapidOCR()
        _MODELS.easy = easyocr.Reader(['ru', 'en'], gpu=False, verbose=False)
        
        ckpt_path = os.path.join(os.path.dirname(__file__), "mobileclip_s0.pt")
        if not os.path.exists(ckpt_path):
            url = "https://docs-assets.developer.apple.com/ml-research/datasets/mobileclip/mobileclip_s0.pt"
            urllib.request.urlretrieve(url, ckpt_path)
            
        _MODELS.mc_model, _, _MODELS.mc_preprocess = mobileclip.create_model_and_transforms('mobileclip_s0', pretrained=ckpt_path)
        _MODELS.mc_tokenizer = mobileclip.get_tokenizer('mobileclip_s0')
        _MODELS.mc_model.eval()
        
        with torch.no_grad():
            _MODELS.text_features = _MODELS.mc_model.encode_text(_MODELS.mc_tokenizer(_CANDIDATE_LABELS))
            _MODELS.text_features = F.normalize(_MODELS.text_features, dim=-1)

def get_iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    if boxAArea == 0: return 0
    return interArea / float(boxAArea)

def contains(box_outer, box_inner):
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
    
    # === 1. RapidOCR ===
    rapid_res, _ = _MODELS.rapid(img_bgr)
    rapid_boxes_with_text = []
    if rapid_res:
        for item in rapid_res:
            xs, ys = [pt[0] for pt in item[0]], [pt[1] for pt in item[0]]
            txt = item[1]
            rapid_boxes_with_text.append([[int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))], txt])
            
    # Склейка RapidOCR
    rapid_boxes_with_text.sort(key=lambda b: (b[0][1], b[0][0]))
    merged_rapid = []
    for box, txt in rapid_boxes_with_text:
        x1, y1, x2, y2 = box
        placed = False
        for m in merged_rapid:
            m_box, m_txt = m[0], m[1]
            mx1, my1, mx2, my2 = m_box
            min_h = min(y2 - y1, my2 - my1)
            y_overlap = max(0, min(y2, my2) - max(y1, my1))
            if min_h > 0 and (y_overlap / min_h) > 0.4:
                thresh = max(y2 - y1, my2 - my1) * 3.0 
                if (x1 <= mx2 + thresh) and (x1 >= mx1):
                    m[0][0], m[0][1] = min(mx1, x1), min(my1, y1)
                    m[0][2], m[0][3] = max(mx2, x2), max(my2, y2)
                    m[1] = m_txt + " " + txt
                    placed = True; break
                elif (x2 >= mx1 - thresh) and (x2 <= mx2):
                    m[0][0], m[0][1] = min(mx1, x1), min(my1, y1)
                    m[0][2], m[0][3] = max(mx2, x2), max(my2, y2)
                    m[1] = txt + " " + m_txt
                    placed = True; break
        if not placed: merged_rapid.append([[x1, y1, x2, y2], txt])

    # Фильтр вложенностей RapidOCR
    final_rapid = []
    for i, m1 in enumerate(merged_rapid):
        is_inside = False
        for j, m2 in enumerate(merged_rapid):
            if i != j and contains(m2[0], m1[0]):
                is_inside = True; break
        if not is_inside: final_rapid.append(m1)
    merged_rapid = final_rapid

    # === 2. OpenCV (НЕ АГРЕССИВНЫЙ) ===
    edges = cv2.Canny(img_gray, 20, 60)
    for m in merged_rapid: 
        x1, y1, x2, y2 = m[0]
        cv2.rectangle(edges, (max(0, x1-2), max(0, y1-2)), (min(width, x2+2), min(height, y2+2)), 0, -1)
        
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    contours, _ = cv2.findContours(closed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    raw_ui_boxes = [cv2.boundingRect(c) for c in contours]
    raw_ui_boxes = [[x, y, x+w, y+h] for x, y, w, h in raw_ui_boxes if 8 < w < 250 and 8 < h < 250]
            
    valid_ui_boxes = []
    for b in raw_ui_boxes:
        if not any(contains(b, tb[0]) for tb in merged_rapid):
            valid_ui_boxes.append(b)

    valid_ui_boxes.sort(key=lambda b: (b[2]-b[0])*(b[3]-b[1]))
    icons_boxes = []
    for b in valid_ui_boxes:
        is_container = any(contains(b, accepted) for accepted in icons_boxes)
        is_inside = any(contains(accepted, b) for accepted in icons_boxes)
        high_iou = any(get_iou(b, accepted) > 0.5 for accepted in icons_boxes)
        if not is_container and not is_inside and not high_iou:
            icons_boxes.append(b)

    # === 3. Классификация EasyOCR / CLIP ===
    yellow_boxes_with_text = []
    pure_icons = []
    
    _MODELS.easy.text_threshold = 0.7 
    _MODELS.easy.low_text = 0.4
    
    for box in icons_boxes:
        x1, y1, x2, y2 = box
        crop = img_gray[max(0, y1-6):min(height, y2+6), max(0, x1-6):min(width, x2+6)]
        if crop.size == 0: continue
        txt = " ".join(_MODELS.easy.readtext(crop, detail=0, paragraph=True)).strip()
        if txt and sum(c.isalnum() for c in txt) >= 1 and len(txt) > 1:
            yellow_boxes_with_text.append([list(box), txt])
        else:
            pure_icons.append(list(box))

    # Склейка иконок
    merged_icons = []
    while pure_icons:
        base = pure_icons.pop(0)
        changed = True
        while changed:
            changed = False
            for i in range(len(pure_icons) - 1, -1, -1):
                b2 = pure_icons[i]
                dx = max(0, max(base[0], b2[0]) - min(base[2], b2[2]))
                dy = max(0, max(base[1], b2[1]) - min(base[3], b2[3]))
                if dx <= 6 and dy <= 6:
                    base[0] = min(base[0], b2[0])
                    base[1] = min(base[1], b2[1])
                    base[2] = max(base[2], b2[2])
                    base[3] = max(base[3], b2[3])
                    pure_icons.pop(i)
                    changed = True
        merged_icons.append(base)
    pure_icons = merged_icons

    # Склейка желтых
    yellow_boxes_with_text.sort(key=lambda b: (b[0][1], b[0][0]))
    merged_yellow = []
    for box, txt in yellow_boxes_with_text:
        x1, y1, x2, y2 = box
        placed = False
        for m in merged_yellow:
            m_box, m_txt = m[0], m[1]
            mx1, my1, mx2, my2 = m_box
            min_h = min(y2 - y1, my2 - my1)
            y_overlap = max(0, min(y2, my2) - max(y1, my1))
            if min_h > 0 and (y_overlap / min_h) > 0.4:
                thresh = max(y2 - y1, my2 - my1) * 3.5
                if (x1 <= mx2 + thresh) and (x1 >= mx1):
                    m[0][0], m[0][1] = min(mx1, x1), min(my1, y1)
                    m[0][2], m[0][3] = max(mx2, x2), max(my2, y2)
                    m[1] = m_txt + " " + txt
                    placed = True; break
                elif (x2 >= mx1 - thresh) and (x2 <= mx2):
                    m[0][0], m[0][1] = min(mx1, x1), min(my1, y1)
                    m[0][2], m[0][3] = max(mx2, x2), max(my2, y2)
                    m[1] = txt + " " + m_txt
                    placed = True; break
        if not placed: merged_yellow.append([[x1, y1, x2, y2], txt])

    # Склейка желтых с зелеными
    final_text_results = []
    for y_m in merged_yellow:
        y_box, y_txt = y_m[0], y_m[1]
        yx1, yy1, yx2, yy2 = y_box
        placed = False
        for r_m in merged_rapid:
            r_box, r_txt = r_m[0], r_m[1]
            rx1, ry1, rx2, ry2 = r_box
            min_h = min(yy2 - yy1, ry2 - ry1)
            y_overlap = max(0, min(yy2, ry2) - max(yy1, ry1))
            if min_h > 0 and (y_overlap / min_h) > 0.4:
                thresh = max(yy2 - yy1, ry2 - ry1) * 3.5
                if (yx1 <= rx2 + thresh) and (yx1 >= rx1 - min_h):
                    r_m[0][0], r_m[0][1] = min(rx1, yx1), min(ry1, yy1)
                    r_m[0][2], r_m[0][3] = max(rx2, yx2), max(ry2, yy2)
                    r_m[1] = r_txt + " " + y_txt
                    placed = True; break
                elif (yx2 >= rx1 - thresh) and (yx2 <= rx2 + min_h):
                    r_m[0][0], r_m[0][1] = min(rx1, yx1), min(ry1, yy1)
                    r_m[0][2], r_m[0][3] = max(rx2, yx2), max(ry2, yy2)
                    r_m[1] = y_txt + " " + r_txt
                    placed = True; break
        if not placed:
            final_text_results.append((y_box[0], y_box[1], y_box[2], y_box[3], y_txt, "opencv"))

    for r_m in merged_rapid:
        r_box, r_txt = r_m[0], r_m[1]
        final_text_results.append((r_box[0], r_box[1], r_box[2], r_box[3], r_txt, "rapid"))

    ui_results = defaultdict(list)
    with torch.no_grad():
        for box in pure_icons:
            x1, y1, x2, y2 = box
            cy1, cy2 = max(0, y1-6), min(height, y2+6)
            cx1, cx2 = max(0, x1-6), min(width, x2+6)
            img_pil = Image.fromarray(cv2.cvtColor(img_bgr[cy1:cy2, cx1:cx2], cv2.COLOR_BGR2RGB))
            sim = (100.0 * F.normalize(_MODELS.mc_model.encode_image(_MODELS.mc_preprocess(img_pil).unsqueeze(0)), dim=-1) @ _MODELS.text_features.T).softmax(dim=-1)
            best_idx = sim.argmax().item()
            label = _CANDIDATE_LABELS[best_idx] if sim[0, best_idx].item() * 100 >= 70.0 else "неопознано"
            ui_results[label].append((x1, y1, x2, y2))
                
    # === 4. Форматирование результата ===
    output_lines = ["текст"]
    for (x1, y1, x2, y2, txt, src) in final_text_results:
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

    # === 5. Отладка (Сохранение картинки) ===
    if DEBUG_SAVE_PARSED_IMAGE:
        try:
            import datetime
            pil_img = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(pil_img)
            
            try: font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 14)
            except: font = ImageFont.load_default()

            for (x1, y1, x2, y2, txt, src) in final_text_results:
                c = (0, 255, 0) if src == "rapid" else (255, 255, 0)
                draw.rectangle([x1, y1, x2, y2], outline=c, width=2)
                draw.text((x1, max(0, y1 - 18)), txt[:40], fill=c, font=font)
                
            for label, boxes in ui_results.items():
                c = (255, 0, 0) if label != "неопознано" else (255, 100, 100)
                for (x1, y1, x2, y2) in boxes:
                    draw.rectangle([x1, y1, x2, y2], outline=c, width=2)
                    if label != "неопознано":
                        lbl = label.split()[-1]
                        draw.text((x1, y2 + 2), lbl, fill=c, font=font)

            logs_dir = os.path.join(os.path.dirname(__file__), "logs")
            os.makedirs(logs_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filepath = os.path.join(logs_dir, f"parsed_{timestamp}.png")
            pil_img.save(filepath)
        except Exception as e:
            print(f"Ошибка при сохранении отладочного изображения: {e}")

    return "\n".join(output_lines)

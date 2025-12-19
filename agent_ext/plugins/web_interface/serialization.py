import json
from google.genai import types

def serialize_message(msg):
    # Если это уже dict (старый формат или ошибка), возвращаем как есть
    if isinstance(msg, dict):
        return msg
        
    try:
        # Используем Pydantic метод model_dump
        # Он АВТОМАТИЧЕСКИ сохраняет 'thought': True и 'thought_signature' внутри parts
        data = msg.model_dump(mode='json', exclude_none=True)
    except Exception:
        # Fallback
        try:
             data = msg.to_json_dict()
        except:
             data = {"role": msg.role, "parts": [{"text": p.text} for p in msg.parts]}

    # Добавляем кастомные поля Web Interface (дублируем мысли для удобства UI)
    if hasattr(msg, "_web_thoughts"):
        data["thoughts"] = msg._web_thoughts
    if hasattr(msg, "_web_tools"):
        data["tools"] = msg._web_tools
        
    return data

def deserialize_message(data):
    if not isinstance(data, dict):
        return data

    # Извлекаем кастомные поля UI
    thoughts = data.get("thoughts", None)
    tools = data.get("tools", None)
    
    # Очищаем данные от лишних полей перед валидацией
    clean_data = {k: v for k, v in data.items() if k not in ["thoughts", "tools"]}
    
    try:
        # 1. Пробуем загрузить как нативный объект Gemini (с parts и signatures)
        msg = types.Content.model_validate(clean_data)
    except Exception:
        # 2. Fallback: Legacy format (обычный content="...", без parts)
        parts = []
        
        # Если есть 'parts' (но валидация не прошла по другой причине)
        if "parts" in clean_data:
            for p in clean_data["parts"]:
                if "text" in p:
                    # Если это мысль без сигнатуры (старый формат), загружаем как текст, 
                    # чтобы не сломать API требованием сигнатуры.
                    is_thought = p.get("thought", False)
                    signature = p.get("thought_signature", None)
                    
                    if is_thought and not signature:
                        # Превращаем в обычный текст, скрывая флаг мысли от API, 
                        # так как без сигнатуры API вернет ошибку.
                        parts.append(types.Part(text=p["text"]))
                    else:
                        # Пытаемся восстановить как есть
                        parts.append(types.Part(**p))
                        
        # Если старый формат 'content'
        elif "content" in clean_data:
            parts.append(types.Part(text=str(clean_data["content"])))
            
        msg = types.Content(role=clean_data.get("role", "user"), parts=parts)

    # Восстанавливаем атрибуты для UI
    if thoughts:
        msg._web_thoughts = thoughts
    if tools:
        msg._web_tools = tools
        
    return msg

def serialize_history(messages):
    return [serialize_message(msg) for msg in messages]

def deserialize_history(data_list):
    return [deserialize_message(item) for item in data_list]

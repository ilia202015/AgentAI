import json
from google.genai import types

def serialize_message(msg):
    # Если это уже словарь, просто копируем
    if isinstance(msg, dict):
        return msg.copy()

    # 1. Базовая подготовка данных
    data = {"role": getattr(msg, "role", "user")}
    
    # 2. Обработка parts с разделением на Content и Thoughts
    parts_data = []
    thoughts_list = []
    
    if hasattr(msg, "parts"):
        for part in msg.parts:
            # Проверяем, является ли часть "мыслью"
            # В SDK Gemini это атрибут .thought (bool)
            is_thought = getattr(part, "thought", False)
            
            # Извлекаем текст
            text = getattr(part, "text", "")
            if not text:
                continue

            if is_thought:
                thoughts_list.append(text)
            else:
                # Это обычный контент
                # Проверяем, не является ли это вызовом функции (они тоже могут быть в parts)
                if getattr(part, "function_call", None):
                    parts_data.append(part.model_dump(mode='json', exclude_none=True))
                elif getattr(part, "function_response", None):
                    parts_data.append(part.model_dump(mode='json', exclude_none=True))
                else:
                    parts_data.append({"text": text})

    data["parts"] = parts_data

    # 3. Обработка метаданных плагина (перекрывают или дополняют мысли из SDK)
    # Если мы стримили мысли через плагин, они сохранены в _web_thoughts
    web_thoughts = getattr(msg, "_web_thoughts", None)
    
    if web_thoughts:
        data["thoughts"] = web_thoughts
    elif thoughts_list:
        # Если плагин не перехватил, берем то, что нашли в parts
        data["thoughts"] = "\n".join(thoughts_list)
    else:
        data["thoughts"] = ""

    # 4. Обработка инструментов
    if hasattr(msg, "_web_tools"):
        data["tools"] = msg._web_tools
    else:
        data["tools"] = []

    return data

def deserialize_message(data):
    if not isinstance(data, dict):
        return data

    # Извлекаем спец. поля
    thoughts = data.get("thoughts", None)
    tools = data.get("tools", None)
    
    # Очищаем данные для валидации моделью
    clean_data = {k: v for k, v in data.items() if k not in ["thoughts", "tools", "content", "tool_calls"]}
    
    try:
        # Пытаемся восстановить через SDK
        msg = types.Content.model_validate(clean_data)
    except Exception:
        # Ручное восстановление
        parts = []
        if "parts" in clean_data:
            for p in clean_data["parts"]:
                if "text" in p:
                    parts.append(types.Part(text=p["text"]))
                elif "function_call" in p:
                    try: parts.append(types.Part(function_call=types.FunctionCall(**p["function_call"])))
                    except: pass
                elif "function_response" in p:
                    try: parts.append(types.Part(function_response=types.FunctionResponse(**p["function_response"])))
                    except: pass
        
        msg = types.Content(role=clean_data.get("role", "user"), parts=parts)

    # Восстанавливаем атрибуты
    if thoughts: msg._web_thoughts = thoughts
    if tools: msg._web_tools = tools
    
    return msg

def serialize_history(messages):
    return [serialize_message(msg) for msg in messages]

def deserialize_history(data_list):
    return [deserialize_message(item) for item in data_list]

import json
from google.genai import types

def serialize_message(msg):
    if isinstance(msg, dict):
        data = msg.copy()
    else:
        try:
            data = msg.model_dump(mode='json', exclude_none=True)
        except Exception:
            try:
                data = msg.to_json_dict()
            except:
                data = {"role": getattr(msg, "role", "user"), "parts": []}
                if hasattr(msg, "parts"):
                    data["parts"] = [{"text": p.text} for p in msg.parts if hasattr(p, "text")]

    # Извлекаем сохраненные метаданные
    if hasattr(msg, "_web_thoughts"):
        data["thoughts"] = msg._web_thoughts
    if hasattr(msg, "_web_tools"):
        data["tools"] = msg._web_tools
        
    return data

def deserialize_message(data):
    if not isinstance(data, dict):
        return data

    thoughts = data.get("thoughts", None)
    tools = data.get("tools", None)
    
    clean_data = {k: v for k, v in data.items() if k not in ["thoughts", "tools", "content", "tool_calls"]}
    
    try:
        msg = types.Content.model_validate(clean_data)
    except Exception:
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
        
        if not parts and "content" in data:
             parts.append(types.Part(text=str(data["content"])))

        msg = types.Content(role=clean_data.get("role", "user"), parts=parts)

    if thoughts: msg._web_thoughts = thoughts
    if tools: msg._web_tools = tools
    
    return msg

def serialize_history(messages):
    return [serialize_message(msg) for msg in messages]

def deserialize_history(data_list):
    return [deserialize_message(item) for item in data_list]

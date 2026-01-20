import json
import os
import hashlib
import base64
from google.genai import types

def _save_image(chat_id, data_bytes, mime_type):
    if not chat_id:
        return None
        
    base_dir = "agent_ext/chats"
    chat_dir = os.path.join(base_dir, str(chat_id), "images")
    os.makedirs(chat_dir, exist_ok=True)
    
    file_hash = hashlib.md5(data_bytes).hexdigest()
    ext = "bin"
    if "jpeg" in mime_type or "jpg" in mime_type: ext = "jpg"
    elif "png" in mime_type: ext = "png"
    elif "webp" in mime_type: ext = "webp"
    
    filename = f"{file_hash}.{ext}"
    file_path = os.path.join(chat_dir, filename)
    
    if not os.path.exists(file_path):
        with open(file_path, "wb") as f:
            f.write(data_bytes)
            
    return f"chats/{chat_id}/images/{filename}"

def _load_image(path):
    full_path = os.path.join("agent_ext", path)
    if os.path.exists(full_path):
        with open(full_path, "rb") as f:
            return f.read()
    return None

def serialize_message(msg, chat_id=None):
    if isinstance(msg, dict): return msg.copy()
    data = {"role": getattr(msg, "role", "user")}
    parts_data = []
    thoughts_list = []
    
    if hasattr(msg, "parts"):
        for part in msg.parts:
            is_thought = getattr(part, "thought", False)
            text = getattr(part, "text", "")
            inline_data = getattr(part, "inline_data", None)
            
            if inline_data:
                mime_type = getattr(inline_data, "mime_type", "image/jpeg")
                img_bytes = getattr(inline_data, "data", None)
                if img_bytes:
                    image_path = _save_image(chat_id, img_bytes, mime_type)
                    if image_path:
                        parts_data.append({"local_image_path": image_path, "mime_type": mime_type})
            elif text:
                if is_thought: thoughts_list.append(text)
                else: parts_data.append({"text": text})
            elif getattr(part, "function_call", None):
                parts_data.append(part.model_dump(mode='json', exclude_none=True))
            elif getattr(part, "function_response", None):
                parts_data.append(part.model_dump(mode='json', exclude_none=True))

    data["parts"] = parts_data
    web_thoughts = getattr(msg, "_web_thoughts", None)
    if web_thoughts: data["thoughts"] = web_thoughts
    elif thoughts_list: data["thoughts"] = "\n".join(thoughts_list)
    else: data["thoughts"] = ""
    data["tools"] = getattr(msg, "_web_tools", []) if hasattr(msg, "_web_tools") else []
    return data

def serialize_history_for_web(messages, chat_id=None):
    history = []
    for msg in messages:
        data = {"role": getattr(msg, "role", "user")}
        parts_data = []
        thoughts_list = []
        
        if hasattr(msg, "parts"):
            for part in msg.parts:
                is_thought = getattr(part, "thought", False)
                text = getattr(part, "text", "")
                inline_data = getattr(part, "inline_data", None)
                
                if inline_data:
                    mime = getattr(inline_data, "mime_type", "image/jpeg")
                    local_name = getattr(part, "_local_filename", None)
                    
                    if local_name and chat_id:
                        # Return URL
                        url = f"/chat_images?chat_id={chat_id}&file={local_name}"
                        parts_data.append({"image_url": url, "mime_type": mime})
                    else:
                        # Return Base64
                        if inline_data.data:
                            b64 = base64.b64encode(inline_data.data).decode('utf-8')
                            parts_data.append({"image_url": f"data:{mime};base64,{b64}", "mime_type": mime})
                
                elif text:
                    if is_thought: thoughts_list.append(text)
                    else: parts_data.append({"text": text})
                
                elif getattr(part, "function_call", None):
                    parts_data.append(part.model_dump(mode='json', exclude_none=True))
                elif getattr(part, "function_response", None):
                    parts_data.append(part.model_dump(mode='json', exclude_none=True))
        
        data["parts"] = parts_data
        
        web_thoughts = getattr(msg, "_web_thoughts", None)
        if web_thoughts: data["thoughts"] = web_thoughts
        elif thoughts_list: data["thoughts"] = "\n".join(thoughts_list)
        else: data["thoughts"] = ""
        
        data["tools"] = getattr(msg, "_web_tools", []) if hasattr(msg, "_web_tools") else []
        history.append(data)
    return history

def deserialize_message(data):
    if not isinstance(data, dict): return data
    thoughts = data.get("thoughts", None)
    tools = data.get("tools", None)
    parts = []
    if "parts" in data:
        for p in data["parts"]:
            if "text" in p:
                parts.append(types.Part(text=p["text"]))
            elif "local_image_path" in p:
                img_data = _load_image(p["local_image_path"])
                if img_data:
                    part = types.Part.from_bytes(data=img_data, mime_type=p.get("mime_type", "image/jpeg"))
                    part._local_filename = os.path.basename(p["local_image_path"])
                    parts.append(part)
            elif "function_call" in p:
                try: parts.append(types.Part(function_call=types.FunctionCall(**p["function_call"])))
                except: pass
            elif "function_response" in p:
                try: parts.append(types.Part(function_response=types.FunctionResponse(**p["function_response"])))
                except: pass
    
    msg = types.Content(role=data.get("role", "user"), parts=parts)
    if thoughts: msg._web_thoughts = thoughts
    if tools: msg._web_tools = tools
    return msg

def serialize_history(messages, chat_id=None):
    return [serialize_message(msg, chat_id) for msg in messages]

def deserialize_history(data_list):
    return [deserialize_message(item) for item in data_list]

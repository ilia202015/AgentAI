import os
import json
import uuid
import datetime
import pickle
import copy
import sys
import types
import marshal

CHATS_DIR = "agent_ext/chats"
CONFIG_PATH = "agent_ext/plugin_config.json"

EXCLUDED_ATTRS = {
    'client', 'web_queue', 'web_emit', 'lock', '_lock', 
    'server_thread', 'chats', 'messages', 'base_messages',
    'send', 'print', 'print_thought', 'print_code', 
    '_handle_stream_response'
}

def ensure_chats_dir():
    if not os.path.exists(CHATS_DIR):
        os.makedirs(CHATS_DIR)

def get_current_config():
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error reading config: {e}")
    return {}

def list_chats():
    ensure_chats_dir()
    chats = []
    for filename in os.listdir(CHATS_DIR):
        if filename.endswith(".pkl"):
            try:
                filepath = os.path.join(CHATS_DIR, filename)
                if os.path.getsize(filepath) == 0:
                    continue
                    
                with open(filepath, 'rb') as f:
                    data = pickle.load(f)
                    chats.append({
                        "id": data.get("id"),
                        "name": data.get("name", "Unnamed Chat"),
                        "updated_at": data.get("updated_at", ""),
                        "preview": _get_preview(data.get("messages", []))
                    })
            except Exception as e:
                pass
    
    chats.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return chats

def _get_preview(messages):
    for msg in reversed(messages):
        if msg.get("role") in ["user", "assistant"] and msg.get("content"):
            content = str(msg["content"])
            return (content[:50] + '...') if len(content) > 50 else content
    return "Empty chat"

def load_chat_state(chat_id):
    ensure_chats_dir()
    filepath = os.path.join(CHATS_DIR, f"{chat_id}.pkl")
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        return None, None
    
    try:
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
            
        # Восстановление динамических функций в local_env
        instance_state = data.get("instance_state", {})
        if 'local_env' in instance_state:
            env = instance_state['local_env']
            for k, v in env.items():
                if isinstance(v, dict) and v.get('__type') == 'dynamic_function':
                    try:
                        code = marshal.loads(v['code'])
                        # Используем globals() текущего модуля. 
                        # Функции будут привязаны к этому контексту, но работать будут.
                        new_func = types.FunctionType(code, globals(), v['name'], v['defaults'])
                        new_func.__doc__ = v['doc']
                        env[k] = new_func
                    except Exception as e:
                        print(f"⚠️ Failed to restore function {k}: {e}")

    except (EOFError, pickle.UnpicklingError):
        return None, "Corrupted chat file"
        
    saved_config = data.get("plugin_config", {})
    current_config = get_current_config()
    
    warning = None
    if saved_config != current_config:
        warning = "⚠️ **Warning:** The plugin configuration has changed since this chat was saved."
        
    return data, warning

def save_chat_state(chat_instance, chat_id=None, name=None):
    ensure_chats_dir()
    
    if not chat_id:
        chat_id = str(uuid.uuid4())
    
    instance_state = {}
    
    # Собираем данные: атрибуты экземпляра
    attributes_to_save = chat_instance.__dict__.copy()
    
    # Явно добавляем local_env, если он есть (даже если он классовый, getattr его достанет)
    if hasattr(chat_instance, 'local_env'):
        attributes_to_save['local_env'] = getattr(chat_instance, 'local_env')
    
    for key, value in attributes_to_save.items():
        if key in EXCLUDED_ATTRS or key.startswith('__'):
            continue
            
        if callable(value):
            continue
            
        if isinstance(value, types.ModuleType):
            continue
        
        # Специальная обработка для local_env
        if key == 'local_env' and isinstance(value, dict):
            safe_env = {}
            for k_env, v_env in value.items():
                if k_env == 'self': continue
                if isinstance(v_env, types.ModuleType): continue
                try:
                    pickle.dumps(v_env)
                    safe_env[k_env] = v_env
                except:
                    # Пытаемся сохранить динамическую функцию
                    if isinstance(v_env, types.FunctionType):
                         try:
                             code_dump = marshal.dumps(v_env.__code__)
                             safe_env[k_env] = {
                                 '__type': 'dynamic_function',
                                 'name': v_env.__name__,
                                 'code': code_dump,
                                 'defaults': v_env.__defaults__,
                                 'doc': v_env.__doc__
                             }
                         except Exception as e:
                             # print(f"⚠️ Failed to marshal function {k_env}: {e}")
                             pass
            instance_state[key] = safe_env
            continue
            
        try:
            pickle.dumps(value)
            instance_state[key] = value
        except (TypeError, pickle.PicklingError) as e:
            pass

    data = {
        "id": chat_id,
        "updated_at": datetime.datetime.now().isoformat(),
        "messages": chat_instance.messages,
        "instance_state": instance_state,
        "plugin_config": get_current_config()
    }

    filepath = os.path.join(CHATS_DIR, f"{chat_id}.pkl")
    
    if name:
        data["name"] = name
    elif os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        try:
            with open(filepath, 'rb') as f:
                old_data = pickle.load(f)
                data["name"] = old_data.get("name", "New Chat")
        except:
             data["name"] = "New Chat"
    else:
        data["name"] = "New Chat"
        for msg in chat_instance.messages:
            if msg["role"] == "user":
                content = str(msg.get("content", ""))
                clean = content.replace('\n', ' ').strip()
                data["name"] = (clean[:30] + "...") if len(clean) > 30 else clean
                break

    temp_path = filepath + ".tmp"
    try:
        with open(temp_path, 'wb') as f:
            pickle.dump(data, f)
        
        if os.path.exists(filepath):
            os.remove(filepath)
        os.rename(temp_path, filepath)
        
    except Exception as e:
        print(f"❌ Critical save error: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e
    
    return data

def create_chat_state(base_messages=None):
    chat_id = str(uuid.uuid4())
    data = {
        "id": chat_id,
        "name": "New Chat",
        "updated_at": datetime.datetime.now().isoformat(),
        "messages": base_messages if base_messages else [],
        "instance_state": {},
        "plugin_config": get_current_config()
    }
    
    filepath = os.path.join(CHATS_DIR, f"{chat_id}.pkl")
    with open(filepath, 'wb') as f:
        pickle.dump(data, f)
        
    return data

def delete_chat(chat_id):
    filepath = os.path.join(CHATS_DIR, f"{chat_id}.pkl")
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False

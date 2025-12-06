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
    chat_ids = set()
    for filename in os.listdir(CHATS_DIR):
        if filename.endswith(".pkl") or filename.endswith(".json"):
            chat_ids.add(filename.rsplit('.', 1)[0])
            
    for chat_id in chat_ids:
        pkl_path = os.path.join(CHATS_DIR, f"{chat_id}.pkl")
        json_path = os.path.join(CHATS_DIR, f"{chat_id}.json")
        
        data = None
        try:
            # Приоритет PKL
            if os.path.exists(pkl_path) and os.path.getsize(pkl_path) > 0:
                with open(pkl_path, 'rb') as f:
                    data = pickle.load(f)
            # Фолбэк на JSON
            elif os.path.exists(json_path) and os.path.getsize(json_path) > 0:
                 with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            if data:
                chats.append({
                    "id": data.get("id"),
                    "name": data.get("name", "Unnamed Chat"),
                    "updated_at": data.get("updated_at", ""),
                    "preview": _get_preview(data.get("messages", []))
                })
        except Exception:
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
    pkl_path = os.path.join(CHATS_DIR, f"{chat_id}.pkl")
    json_path = os.path.join(CHATS_DIR, f"{chat_id}.json")
    
    data = None
    loaded_source = None
    
    # 1. Пытаемся загрузить PKL
    if os.path.exists(pkl_path) and os.path.getsize(pkl_path) > 0:
        try:
            with open(pkl_path, 'rb') as f:
                data = pickle.load(f)
                loaded_source = "pickle"
                
                # Восстановление динамических функций
                instance_state = data.get("instance_state", {})
                if 'local_env' in instance_state:
                    env = instance_state['local_env']
                    for k, v in env.items():
                        if isinstance(v, dict) and v.get('__type') == 'dynamic_function':
                            try:
                                code = marshal.loads(v['code'])
                                new_func = types.FunctionType(code, globals(), v['name'], v['defaults'])
                                new_func.__doc__ = v['doc']
                                env[k] = new_func
                            except Exception as e:
                                print(f"⚠️ Failed to restore function {k}: {e}")

        except (EOFError, pickle.UnpicklingError, AttributeError, ImportError) as e:
            print(f"⚠️ Failed to load PKL for {chat_id}: {e}. Trying JSON...")
    
    # 2. Если PKL не удалось, пробуем JSON
    if not data and os.path.exists(json_path) and os.path.getsize(json_path) > 0:
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                loaded_source = "json"
                print(f"✅ Recovered chat {chat_id} from JSON backup.")
        except Exception as e:
             print(f"❌ Failed to load JSON for {chat_id}: {e}")

    if not data:
        return None, "Chat not found or corrupted"
        
    saved_config = data.get("plugin_config", {})
    current_config = get_current_config()
    
    warning = None
    if saved_config != current_config:
        warning = "⚠️ **Warning:** The plugin configuration has changed."
    
    if loaded_source == "json":
        warning = (warning or "") + "\n\n⚠️ **Restored from JSON backup.** Python variables and execution context were lost."

    return data, warning

def save_chat_state(chat_instance, chat_id=None, name=None):
    ensure_chats_dir()
    
    if not chat_id:
        chat_id = str(uuid.uuid4())
    
    instance_state = {}
    
    # Собираем данные: атрибуты экземпляра
    attributes_to_save = chat_instance.__dict__.copy()
    
    if hasattr(chat_instance, 'local_env'):
        attributes_to_save['local_env'] = getattr(chat_instance, 'local_env')
    
    for key, value in attributes_to_save.items():
        if key in EXCLUDED_ATTRS or key.startswith('__'): continue
        if callable(value): continue
        if isinstance(value, types.ModuleType): continue
        
        if key == 'local_env' and isinstance(value, dict):
            safe_env = {}
            for k_env, v_env in value.items():
                if k_env == 'self': continue
                if isinstance(v_env, types.ModuleType): continue
                try:
                    pickle.dumps(v_env)
                    safe_env[k_env] = v_env
                except:
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
                         except: pass
            instance_state[key] = safe_env
            continue
            
        try:
            pickle.dumps(value)
            instance_state[key] = value
        except: pass

    base_data = {
        "id": chat_id,
        "updated_at": datetime.datetime.now().isoformat(),
        "messages": chat_instance.messages,
        "plugin_config": get_current_config()
    }

    if name:
        base_data["name"] = name
    else:
        # Если имя не передано явно, пытаемся сохранить старое имя
        # Или генерируем новое, если это новый чат
        old_name = "New Chat"
        json_path = os.path.join(CHATS_DIR, f"{chat_id}.json")
        if os.path.exists(json_path):
             try:
                 with open(json_path, 'r', encoding='utf-8') as f:
                     old_name = json.load(f).get("name", "New Chat")
             except: pass
        
        if old_name == "New Chat":
             # Генерируем из первого сообщения
             for msg in chat_instance.messages:
                if msg["role"] == "user":
                    content = str(msg.get("content", ""))
                    clean = content.replace('\n', ' ').strip()
                    old_name = (clean[:30] + "...") if len(clean) > 30 else clean
                    break
        
        base_data["name"] = old_name

    # 1. Save JSON
    json_data = base_data.copy()
    json_data["instance_state"] = {}
    
    json_path = os.path.join(CHATS_DIR, f"{chat_id}.json")
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        print(f"❌ Error saving JSON backup: {e}")

    # 2. Save Pickle
    pkl_data = base_data.copy()
    pkl_data["instance_state"] = instance_state
    
    pkl_path = os.path.join(CHATS_DIR, f"{chat_id}.pkl")
    try:
        with open(pkl_path, 'wb') as f:
            pickle.dump(pkl_data, f)
    except Exception as e:
        print(f"❌ Error saving Pickle: {e}")
    
    return pkl_data

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
    
    json_path = os.path.join(CHATS_DIR, f"{chat_id}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    pkl_path = os.path.join(CHATS_DIR, f"{chat_id}.pkl")
    with open(pkl_path, 'wb') as f:
        pickle.dump(data, f)
        
    return data

def delete_chat(chat_id):
    deleted = False
    pkl_path = os.path.join(CHATS_DIR, f"{chat_id}.pkl")
    if os.path.exists(pkl_path):
        os.remove(pkl_path)
        deleted = True
        
    json_path = os.path.join(CHATS_DIR, f"{chat_id}.json")
    if os.path.exists(json_path):
        os.remove(json_path)
        deleted = True
        
    return deleted

def rename_chat(chat_id, new_name):
    data, _ = load_chat_state(chat_id)
    if not data: return False
    
    data["name"] = new_name
    
    # Save JSON
    json_path = os.path.join(CHATS_DIR, f"{chat_id}.json")
    try:
        json_data = data.copy()
        json_data["instance_state"] = {}
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
    except: pass

    # Save Pickle
    pkl_path = os.path.join(CHATS_DIR, f"{chat_id}.pkl")
    try:
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
    except: return False
    
    return True

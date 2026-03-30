import shutil
import os
import json
import uuid
import datetime
import dill
import copy
import sys
import types
import queue
import traceback
import re
import threading

PROMPTS_CONFIG_PATH = "final_prompts.json"
WEB_PROMPT_MARKER_START = "### FINAL_PRO" + "MPT_START ###"
WEB_PROMPT_MARKER_END = "### FINAL_PRO" + "MPT_END ###"

# Import serialization utils
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)
try:
    import serialization
except ImportError:
    print("Warning: serialization module not found in storage")
    serialization = None

is_print_debug = True
CHATS_DIR = "chats"
INDEX_PATH = os.path.join(CHATS_DIR, "index.json")
index_lock = threading.Lock()

def ensure_chats_dir():
    if not os.path.exists(CHATS_DIR):
        os.makedirs(CHATS_DIR)

def get_current_config():
    try:
        if os.path.exists("plugin_config.json"):
            with open("plugin_config.json", 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error reading config: {e}")
    return {}

# --- INDEXING LOGIC ---

def _load_index_raw():
    if os.path.exists(INDEX_PATH):
        try:
            with open(INDEX_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            # Если файл битый (например, оборванная запись), возвращаем None,
            # чтобы спровоцировать пересборку индекса.
            return None
    return None # Если файла нет

def _save_index_raw(index_data):
    try:
        tmp_path = INDEX_PATH + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, INDEX_PATH)
    except Exception as e:
        print(f"Error saving index: {e}")

def _rebuild_index():
    if is_print_debug: print("🛠 Rebuilding chats index...")
    ensure_chats_dir()
    chats = []
    try:
        files = [f for f in os.listdir(CHATS_DIR) if f.endswith(".json") and f != "index.json"]
    except OSError:
        return []

    for filename in files:
        chat_id = filename[:-5]
        json_path = os.path.join(CHATS_DIR, filename)
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            chats.append({
                "id": chat_id,
                "name": data.get("name", "New Chat"),
                "updated_at": data.get("updated_at", ""),
                "preview": _get_preview(data.get("messages", []))
            })
        except: continue
    
    with index_lock:
        _save_index_raw(chats)
    return chats

def _update_index_entry(chat_id, name, updated_at, preview):
    with index_lock:
        index = _load_index_raw()
        if index is None: # Если индекса нет или он поврежден, пересоберем всё
            _rebuild_index()
            return
            
        # Ищем существующий
        found = False
        for i, item in enumerate(index):
            if item.get("id") == chat_id:
                index[i] = {"id": chat_id, "name": name, "updated_at": updated_at, "preview": preview}
                found = True
                break
        
        if not found:
            index.append({"id": chat_id, "name": name, "updated_at": updated_at, "preview": preview})
            
        _save_index_raw(index)

def _remove_from_index(chat_id):
    with index_lock:
        index = _load_index_raw()
        if index:
            new_index = [item for item in index if item.get("id") != chat_id]
            if len(new_index) != len(index):
                _save_index_raw(new_index)

# --- PUBLIC API ---

def list_chats(get_chat=None):
    with index_lock: # Блокируем чтение для безопасности
        index = _load_index_raw()
        
    if index is None:
        return _rebuild_index()
    
    # Сортировка по дате обновления (новые сверху)
    index.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return index

def _get_preview(messages):
    for msg in reversed(messages):
        role = getattr(msg, "role", msg.get("role") if isinstance(msg, dict) else None)
        if role in ["user", "assistant", "model"]:
            content = ""
            if hasattr(msg, "parts"):
                for p in msg.parts:
                    if hasattr(p, "text") and p.text: content += p.text + " "
            elif isinstance(msg, dict) and "parts" in msg:
                 for p in msg["parts"]:
                     if "text" in p: content += p["text"] + " "
            elif isinstance(msg, dict) and "content" in msg:
                content = str(msg["content"])
                
            content = content.strip()
            if content:
                return (content[:70] + '...') if len(content) > 70 else content
    return "Empty chat"

def load_chat_state(id, get_chat):
    if is_print_debug:
        print(f"load_chat_state({id})")
    ensure_chats_dir()
    pkl_path = os.path.join(CHATS_DIR, f"{id}.pkl")
    json_path = os.path.join(CHATS_DIR, f"{id}.json")
    
    if os.path.exists(pkl_path) and os.path.getsize(pkl_path) > 0:
        try:
            with open(pkl_path, 'rb') as f:
                if is_print_debug:
                    print(f"dill...")
                chat = dill.load(f)
                if is_print_debug:
                    print(f"end")
                if not getattr(chat, "name", False): chat.name = "New chat"
                if not getattr(chat, "id", False): chat.id = id
                if not getattr(chat, "active_preset_id", False): chat.active_preset_id = 'default'
                if not hasattr(chat, "web_queue") or chat.web_queue is None: chat.web_queue = queue.Queue()
                chat.busy_depth = 0
                return chat, None
        except: pass

    if os.path.exists(json_path) and os.path.getsize(json_path) > 0:
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            chat = get_chat()
            for key, value in data.items():
                if key == "messages" and serialization:
                    chat.messages = serialization.deserialize_history(value)
                else: setattr(chat, key, value)
            chat.id = id
            chat.busy_depth = 0
            return chat, "⚠️ Restored from JSON backup."
        except: pass

    return None, "Chat not found"

def save_chat_state(chat):
    ensure_chats_dir()
    if not getattr(chat, 'id', None): chat.id = str(uuid.uuid4())
    chat.updated_at = datetime.datetime.now().isoformat()
    
    # Очистка системного промпта
    if hasattr(chat, 'system_prompt') and chat.system_prompt:
        pattern = re.escape(WEB_PROMPT_MARKER_START) + r".*?" + re.escape(WEB_PROMPT_MARKER_END)
        chat.system_prompt = re.sub(pattern, "", chat.system_prompt, flags=re.DOTALL).strip()

    messages_json = serialization.serialize_history(chat.messages, chat_id=chat.id) if serialization else chat.messages
    
    # Определение имени и превью
    preview = _get_preview(chat.messages)
    current_name = getattr(chat, 'name', 'New Chat')
    if current_name == 'New Chat' and preview != 'Empty chat':
        current_name = preview[:30]
    chat.name = current_name

    base_data = {
        'id': chat.id,
        'name': chat.name,
        'updated_at': chat.updated_at,
        'messages': messages_json,
        'active_preset_id': getattr(chat, 'active_preset_id', 'default'),
        'plugin_config': get_current_config()
    }

    # Сохранение JSON
    json_path = os.path.join(CHATS_DIR, f'{chat.id}.json')
    tmp_json = json_path + ".tmp"
    with open(tmp_json, 'w', encoding='utf-8') as f:
        json.dump(base_data, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp_json, json_path)

    # Сохранение PKL
    pkl_path = os.path.join(CHATS_DIR, f'{chat.id}.pkl')
    tmp_pkl = pkl_path + ".tmp"
    with open(tmp_pkl, 'wb') as f:
        dill.dump(chat, f)
    os.replace(tmp_pkl, pkl_path)
    
    # Обновление индекса
    _update_index_entry(chat.id, chat.name, chat.updated_at, preview)
    
    return chat

def delete_chat(id):
    ensure_chats_dir()
    deleted = False
    for ext in [".pkl", ".json"]:
        p = os.path.join(CHATS_DIR, f"{id}{ext}")
        if os.path.exists(p):
            os.remove(p)
            deleted = True
    
    img_dir = os.path.join(CHATS_DIR, str(id))
    if os.path.exists(img_dir):
        shutil.rmtree(img_dir)
        deleted = True
        
    if deleted:
        _remove_from_index(id)
    return deleted

def rename_chat(id, new_name, get_chat):
    chat, _ = load_chat_state(id, get_chat)
    if not chat: return False
    chat.name = new_name
    save_chat_state(chat)
    return True

def clear_chat_context(id):
    pkl_path = os.path.join(CHATS_DIR, f"{id}.pkl")
    if os.path.exists(pkl_path):
        os.remove(pkl_path)
        _rebuild_index() # Проще всего пересобрать превью
        return True
    return False

def get_final_prompts_config():
    if not os.path.exists(PROMPTS_CONFIG_PATH):
        return {'active_id': 'default', 'active_parameters': [], 'prompts': {}}
    try:
        with open(PROMPTS_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {'active_id': None, 'active_parameters': [], 'prompts': {}}

def save_final_prompts_config(config):
    with open(PROMPTS_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def get_presets_config():
    config = {"default_preset_id": "default", "presets": {"default": {"name": "Стандартный", "prompt_ids": ["default"], "modes": [], "commands": [], "blocked": [], "settings": {}}}}
    if os.path.exists("presets.json"):
        try:
            with open("presets.json", 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    if "presets" in loaded: config["presets"].update(loaded["presets"])
                    if "default_preset_id" in loaded: config["default_preset_id"] = loaded["default_preset_id"]
        except: pass
    return config

def save_presets_config(config):
    with open("presets.json", 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

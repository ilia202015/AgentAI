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
PROMPTS_CONFIG_PATH = "final_prompts.json"
WEB_PROMPT_MARKER_START = "### FINAL_PROMPT_START ###"
WEB_PROMPT_MARKER_END = "### FINAL_PROMPT_END ###"


# Import serialization utils
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)
try:
    import serialization
except ImportError:
    # Fallback/Error handling if serialization not found
    print("Warning: serialization module not found in storage")
    serialization = None

is_print_debug = False

CHATS_DIR = "chats"
CONFIG_PATH = "plugin_config.json"

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

def list_chats(get_chat=None):
    """
    Reads chat list directly from JSON files.
    get_chat argument is kept for compatibility but ignored.
    """
    ensure_chats_dir()
    chats = []
    
    # We rely on .json files for listing because they are faster to read and stable.
    try:
        files = [f for f in os.listdir(CHATS_DIR) if f.endswith(".json")]
    except OSError:
        return []

    for filename in files:
        chat_id = filename[:-5]
        json_path = os.path.join(CHATS_DIR, filename)
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, dict):
                continue
                
            name = data.get("name", "New Chat")
            updated_at = data.get("updated_at", "")
            # Если даты нет, берем время модификации файла
            if not updated_at:
                try:
                    mtime = os.path.getmtime(json_path)
                    updated_at = datetime.datetime.fromtimestamp(mtime).isoformat()
                except: pass

            messages = data.get("messages", [])
            preview = _get_preview(messages)
            
            chats.append({
                "id": chat_id,
                "name": name,
                "updated_at": updated_at,
                "preview": preview
            })
        except Exception as e:
            # Не ломаем весь список из-за одного битого файла
            print(f"Error listing chat {chat_id}: {e}")

    # Сортировка по дате обновления (новые сверху)
    chats.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return chats

def _get_preview(messages):
    for msg in reversed(messages):
        # Handle both dict and Object
        role = getattr(msg, "role", msg.get("role") if isinstance(msg, dict) else None)
        
        if role in ["user", "assistant", "model"]:
            content = ""
            # Handle Object
            if hasattr(msg, "parts"):
                for p in msg.parts:
                    if hasattr(p, "text") and p.text:
                        content += p.text + " "
            # Handle Dict
            elif isinstance(msg, dict) and "parts" in msg:
                 for p in msg["parts"]:
                     if "text" in p:
                         content += p["text"] + " "
            # Handle Dict Legacy
            elif isinstance(msg, dict) and "content" in msg:
                content = str(msg["content"])
                
            content = content.strip()
            if content:
                return (content[:50] + '...') if len(content) > 50 else content
    return "Empty chat"

def load_chat_state(id, get_chat):
    if is_print_debug:
        print(f"load_chat_state({id}, {get_chat})")

    ensure_chats_dir()
    pkl_path = os.path.join(CHATS_DIR, f"{id}.pkl")
    json_path = os.path.join(CHATS_DIR, f"{id}.json")
    
    # 1. Пытаемся загрузить PKL
    if os.path.exists(pkl_path) and os.path.getsize(pkl_path) > 0:
        try:
            with open(pkl_path, 'rb') as f:
                chat = dill.load(f)
                
                # Basic fixups
                if not getattr(chat, "name", False): chat.name = "New chat"
                if not getattr(chat, "id", False): chat.id = id
                if not getattr(chat, "web_queue", False): chat.web_queue = queue.Queue()
                chat.busy_depth = 0
                
                # Check config
                warning = None
                if getattr(chat, "plugin_config", None) != get_current_config():
                    warning = "⚠️ **Warning:** The plugin configuration has changed."
                return chat, warning

        except (EOFError, dill.UnpicklingError, AttributeError, ImportError) as e:
            print(f"⚠️ Failed to load PKL for {id}: {traceback.format_exc()}.")
    
    print(f"Trying JSON...")

    data = None
    loaded_source = None
    
    # 2. Если PKL не удалось, пробуем JSON
    if os.path.exists(json_path) and os.path.getsize(json_path) > 0:
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                loaded_source = "json"
                print(f"✅ Recovered chat {id} from JSON backup.")
        except Exception as e:
             print(f"❌ Failed to load JSON for {id}: {e}")

    if not data:
        return None, "Chat not found or corrupted"
    
    chat = get_chat()
    
    # Restore fields
    for key, value in data.items():
        if key == "messages" and serialization:
            chat.messages = serialization.deserialize_history(value)
        else:
            setattr(chat, key, value)

    if not getattr(chat, "name", False): chat.name = "New chat"
    if not getattr(chat, "id", False): chat.id = id
                
    saved_config = data.get("plugin_config", {})
    current_config = get_current_config()
    
    warning = None
    if saved_config != current_config:
        warning = "⚠️ **Warning:** The plugin configuration has changed."
    
    if loaded_source == "json":
        warning = (warning or "") + "\n\n⚠️ **Restored from JSON backup.** Python variables and execution context were lost."

    return chat, warning

def save_chat_state(chat):
    ensure_chats_dir()
    
    if not getattr(chat, 'id', None):
        chat.id = str(uuid.uuid4())

    chat.updated_at = datetime.datetime.now().isoformat()
    chat.plugin_config = get_current_config()
    
    # Очищаем системный промпт от внедрений веб-интерфейса перед сохранением
    # чтобы избежать дублирования при следующей загрузке
    if hasattr(chat, 'system_prompt') and chat.system_prompt:
        pattern = re.escape(WEB_PROMPT_MARKER_START) + r".*?" + re.escape(WEB_PROMPT_MARKER_END)
        chat.system_prompt = re.sub(pattern, "", chat.system_prompt, flags=re.DOTALL).strip()

    # Подготовка данных для JSON
    messages_json = chat.messages
    if serialization:
        messages_json = serialization.serialize_history(chat.messages, chat_id=chat.id)
    
    base_data = {
        'id': chat.id,
        'updated_at': chat.updated_at,
        'messages': messages_json,
        'plugin_config': chat.plugin_config
    }

    # Определение имени чата
    current_name = getattr(chat, 'name', 'New Chat')
    json_path = os.path.join(CHATS_DIR, f'{chat.id}.json')
    
    if current_name == 'New Chat' and os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                current_name = json.load(f).get('name', 'New Chat')
        except: pass
            
    if current_name == 'New Chat':
        preview = _get_preview(chat.messages)
        if preview != 'Empty chat':
            current_name = preview[:30]
            
    base_data['name'] = current_name
    chat.name = base_data['name']

    # 1. Сохранение JSON (Бэкап и метаданные)
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(base_data, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        print(f"❌ Error saving JSON backup: {e}")

    # 2. Сохранение Dill (Полное состояние объекта)
    # Логика очистки непиклируемых полей теперь в Chat.__getstate__ (web_getstate)
    pkl_path = os.path.join(CHATS_DIR, f'{chat.id}.pkl')
    try:
        with open(pkl_path, 'wb') as f:            
            dill.dump(chat, f)
    except Exception as e:
        print(f"❌ Error saving dill: {e}")
    
    return chat

def delete_chat(id):
    deleted = False
    pkl_path = os.path.join(CHATS_DIR, f"{id}.pkl")
    if os.path.exists(pkl_path):
        os.remove(pkl_path)
        deleted = True
        
    json_path = os.path.join(CHATS_DIR, f"{id}.json")
    if os.path.exists(json_path):
        os.remove(json_path)
        deleted = True
        
    # NEW: Delete images folder
    images_dir = os.path.join(CHATS_DIR, f"{id}")
    if os.path.exists(images_dir):
        try:
            shutil.rmtree(images_dir)
            deleted = True
        except Exception as e:
            print(f"Error removing chat dir {id}: {e}")
        
    return deleted

def rename_chat(id, new_name, get_chat):
    chat, _ = load_chat_state(id, get_chat)
    if not chat: return False
    
    chat.name = new_name
    
    try:
        save_chat_state(chat)
    except Exception as e: 
        print("storage.rename_chat error:", e)
        return False
    
    return True

def clear_chat_context(id):
    pkl_path = os.path.join(CHATS_DIR, f"{id}.pkl")
    if os.path.exists(pkl_path):
        os.remove(pkl_path)
        return True
    return False

def get_final_prompts_config():
    if not os.path.exists(PROMPTS_CONFIG_PATH):
        default_path = os.path.join(os.path.dirname(__file__), 'default_prompts.json')
        if os.path.exists(default_path):
            shutil.copy(default_path, PROMPTS_CONFIG_PATH)
        else:
            # Fallback if even default is missing
            config = {'active_id': 'default', 'active_parameters': [], 'prompts': {'default': {'name': 'Стандартный', 'text': '...', 'type': 'system'}}}
            save_final_prompts_config(config)
            return config
    try:
        with open(PROMPTS_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {'active_id': None, 'active_parameters': [], 'prompts': {}}

def save_final_prompts_config(config):
    with open(PROMPTS_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def get_active_final_prompt_text():
    config = get_final_prompts_config()
    text = ''
    # 1. System Prompt
    active_id = config.get('active_id')
    if active_id and active_id in config.get('prompts', {}):
        text += config['prompts'][active_id].get('text', '') + '\n\n'
    # 2. Active Parameters
    active_params = config.get('active_parameters', [])
    for p_id in active_params:
        if p_id in config.get('prompts', {}):
            text += config['prompts'][p_id].get('text', '') + '\n\n'
    return text.strip()

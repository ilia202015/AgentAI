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

CHATS_DIR = "agent_ext/chats"
CONFIG_PATH = "agent_ext/plugin_config.json"

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
    
    if not getattr(chat, "id", None):
        chat.id = str(uuid.uuid4())

    if is_print_debug:
        print(f"save_chat_state({chat.id})")

    chat.updated_at = datetime.datetime.now().isoformat()
    chat.plugin_config = get_current_config()
    
    # Serialize messages for JSON
    messages_json = chat.messages
    if serialization:
        messages_json = serialization.serialize_history(chat.messages, chat_id=chat.id)
    
    base_data = {
        "id": chat.id,
        "updated_at": datetime.datetime.now().isoformat(),
        "messages": messages_json,
        "plugin_config": get_current_config()
    }

    if getattr(chat, "name", None):
        base_data["name"] = chat.name
    else:
        # Generate Name Logic
        old_name = "New Chat"
        json_path = os.path.join(CHATS_DIR, f"{chat.id}.json")
        if os.path.exists(json_path):
             try:
                 with open(json_path, 'r', encoding='utf-8') as f:
                     old_name = json.load(f).get("name", "New Chat")
             except: pass
        
        if old_name == "New Chat":
             # Try to generate from messages
             preview = _get_preview(chat.messages)
             if preview != "Empty chat":
                 old_name = preview[:30]
        
        base_data["name"] = old_name

    chat.name = base_data["name"]

    # 1. Save JSON
    json_path = os.path.join(CHATS_DIR, f"{chat.id}.json")
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(base_data, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        print(f"❌ Error saving JSON backup: {e}")

    # 2. Save dill
    pkl_path = os.path.join(CHATS_DIR, f"{chat.id}.pkl")
    try:
        with open(pkl_path, 'wb') as f:            
            # Safe attribute access
            client = getattr(chat, 'client', None)
            chat.client = None
            
            busy_depth = getattr(chat, 'busy_depth', 0)
            chat.busy_depth = 0

            dill.dump(chat, f)

            chat.busy_depth = busy_depth
            if client:
                chat.client = client
    except Exception as e:
        print(f"❌ Error saving dill: {e}")
        # Restore attributes in case of error
        chat.busy_depth = getattr(chat, 'busy_depth', 0) # Should be original value roughly
        if client: chat.client = client
    
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

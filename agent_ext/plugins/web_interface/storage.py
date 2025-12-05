import os
import json
import uuid
import datetime
import shutil

CHATS_DIR = "agent_ext/chats"

def ensure_chats_dir():
    if not os.path.exists(CHATS_DIR):
        os.makedirs(CHATS_DIR)

def list_chats():
    ensure_chats_dir()
    chats = []
    for filename in os.listdir(CHATS_DIR):
        if filename.endswith(".json"):
            try:
                filepath = os.path.join(CHATS_DIR, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Базовая валидация
                    if "id" in data and "messages" in data:
                        chats.append({
                            "id": data["id"],
                            "name": data.get("name", "New Chat"),
                            "updated_at": data.get("updated_at", ""),
                            "preview": _get_preview(data["messages"])
                        })
            except Exception as e:
                print(f"Error reading chat {filename}: {e}")
    
    # Сортировка по дате обновления (новые сверху)
    chats.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return chats

def _get_preview(messages):
    # Ищем последнее сообщение пользователя или ассистента
    for msg in reversed(messages):
        if msg.get("role") in ["user", "assistant"] and msg.get("content"):
            content = msg["content"]
            return (content[:50] + '...') if len(content) > 50 else content
    return "Empty chat"

def load_chat(chat_id):
    filepath = os.path.join(CHATS_DIR, f"{chat_id}.json")
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_chat(chat_id, messages, name=None):
    ensure_chats_dir()
    filepath = os.path.join(CHATS_DIR, f"{chat_id}.json")
    
    data = {
        "id": chat_id,
        "updated_at": datetime.datetime.now().isoformat(),
        "messages": messages
    }
    
    # Если имя не передано, пробуем сохранить старое или генерируем
    if name:
        data["name"] = name
    elif os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
                data["name"] = old_data.get("name", "New Chat")
        except:
             data["name"] = "New Chat"
    else:
        # Генерируем имя из первого сообщения пользователя
        data["name"] = "New Chat"
        for msg in messages:
            if msg["role"] == "user":
                data["name"] = (msg["content"][:30] + "...") if len(msg["content"]) > 30 else msg["content"]
                break

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return data

def create_chat():
    chat_id = str(uuid.uuid4())
    messages = []
    # Можно добавить системный промпт по умолчанию, если нужно, 
    # но обычно агент сам его добавляет при инициализации. 
    # В данном случае мы сохраняем чистый лист, агент добавит system prompt сам при загрузке контекста.
    
    return save_chat(chat_id, messages, "New Chat")

def delete_chat(chat_id):
    filepath = os.path.join(CHATS_DIR, f"{chat_id}.json")
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False

def rename_chat(chat_id, new_name):
    chat_data = load_chat(chat_id)
    if chat_data:
        save_chat(chat_id, chat_data["messages"], new_name)
        return True
    return False

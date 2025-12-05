import sys
import os
import threading
import importlib.util
import types

# Добавляем путь к текущей директории плагина в sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    import server
    import storage
except ImportError:
    try:
        from . import server
        from . import storage
    except ImportError:
        # Fallback
        spec = importlib.util.spec_from_file_location("server", os.path.join(current_dir, "server.py"))
        server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server)
        
        spec_st = importlib.util.spec_from_file_location("storage", os.path.join(current_dir, "storage.py"))
        storage = importlib.util.module_from_spec(spec_st)
        spec_st.loader.exec_module(storage)

def main(chat, settings):
    print("🚀 Запуск Web Interface...")
    
    # 1. Сохраняем "базовое" состояние сообщений (System prompt)
    if not hasattr(chat, "base_messages"):
        chat.base_messages = list(chat.messages)
        print(f"📦 Base chat state saved ({len(chat.base_messages)} messages)")

    # 2. Инициализация ID чата
    if not hasattr(chat, "current_chat_id"):
        chat.current_chat_id = None # Нет активного чата при старте

    # 3. Декорируем chat.send для автосохранения
    original_send = chat.send
    
    def send_with_autosave(self, message):
        # Вызываем оригинальный send
        result = original_send(message)
        
        # После выполнения сохраняем текущий чат, если он выбран
        if self.current_chat_id:
            try:
                storage.save_chat(self.current_chat_id, self.messages)
                # print(f"💾 Chat {self.current_chat_id} autosaved.") 
            except Exception as e:
                print(f"⚠️ Autosave failed: {e}")
        
        return result

    chat.send = types.MethodType(send_with_autosave, chat)

    # 4. Запуск сервера
    server_thread = threading.Thread(target=server.run_server, args=(chat,), daemon=True)
    server_thread.start()
    
    print("✅ Web Server thread started.")
    
    return chat

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
        spec = importlib.util.spec_from_file_location("server", os.path.join(current_dir, "server.py"))
        server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server)
        
        spec_st = importlib.util.spec_from_file_location("storage", os.path.join(current_dir, "storage.py"))
        storage = importlib.util.module_from_spec(spec_st)
        spec_st.loader.exec_module(storage)

def main(chat, settings):
    print("🚀 Запуск Web Interface...")
    
    if not hasattr(chat, "base_messages"):
        chat.base_messages = list(chat.messages)
        print(f"📦 Base chat state saved ({len(chat.base_messages)} messages)")

    if not hasattr(chat, "current_chat_id"):
        chat.current_chat_id = None 

    original_send = chat.send
    
    def send_with_autosave(self, message):
        result = original_send(message)
        
        if self.current_chat_id:
            try:
                # Используем save_chat_state, передавая ВЕСЬ инстанс
                storage.save_chat_state(self, self.current_chat_id)
            except Exception as e:
                print(f"⚠️ Autosave failed: {e}")
        
        return result

    chat.send = types.MethodType(send_with_autosave, chat)

    server_thread = threading.Thread(target=server.run_server, args=(chat,), daemon=True)
    server_thread.start()
    
    print("✅ Web Server thread started.")
    
    return chat

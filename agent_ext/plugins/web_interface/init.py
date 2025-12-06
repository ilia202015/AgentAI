import sys
import os
import threading
import importlib.util
import types

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

    if not hasattr(chat, "current_chat_id"):
        chat.current_chat_id = None 
        
    chat.stop_requested = False
    
    # 1. Autosave patch
    original_send = chat.send
    def send_with_autosave(self, message):
        result = original_send(message)
        if self.current_chat_id:
            try:
                storage.save_chat_state(self, self.current_chat_id)
            except Exception as e:
                print(f"⚠️ Autosave failed: {e}")
        return result
    chat.send = types.MethodType(send_with_autosave, chat)

    # 2. Stop generation patch (Simplified)
    original_handle_stream = chat._handle_stream
    
    def handle_stream_with_stop(self, stream):
        def interruptible_generator(gen):
            try:
                for chunk in gen:
                    if getattr(self, 'stop_requested', False):
                        self.print("\n🛑 Force stopped.")
                        break
                    yield chunk
            except Exception as e:
                print(f"Stream error: {e}")
            self.stop_requested = False

        return original_handle_stream(interruptible_generator(stream))

    chat._handle_stream = types.MethodType(handle_stream_with_stop, chat)

    # Start Server
    server_thread = threading.Thread(target=server.run_server, args=(chat,), daemon=True)
    server_thread.start()
    
    print("✅ Web Server thread started.")
    
    return chat

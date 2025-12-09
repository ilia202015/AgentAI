import sys
import os
import threading
import importlib.util
import types
import queue
import copy

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    import server
except ImportError:
    try:
        from . import server
    except ImportError:
        spec = importlib.util.spec_from_file_location("server", os.path.join(current_dir, "server.py"))
        server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server)

def main(root_chat, settings):
    print("🚀 Запуск Web Interface (Parallel Mode)...")

    server_thread = threading.Thread(target=server.run_server, args=(root_chat,), daemon=True)
    server_thread.start()
    print("✅ Web Server thread started.")
    return root_chat

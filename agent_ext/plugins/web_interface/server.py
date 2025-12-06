import http.server
import socketserver
import json
import os
import queue
import time
import threading
import sys
import traceback
from urllib.parse import urlparse, parse_qs
import mimetypes
import importlib.util
import socket

# Импорт локальных модулей
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    import storage
except ImportError:
    try:
        from . import storage
    except ImportError:
        spec = importlib.util.spec_from_file_location("storage", os.path.join(current_dir, "storage.py"))
        storage = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(storage)

HOST = "127.0.0.1"
START_PORT = 8080
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

mimetypes.init()
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('text/html', '.html')

class WebRequestHandler(http.server.BaseHTTPRequestHandler):
    chat_instance = None
    
    def log_message(self, format, *args):
        pass 

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)

            if path == "/" or path == "":
                self.serve_static("index.html")
            elif path == "/stream":
                self.handle_stream()
            elif path.startswith("/api/"):
                self.handle_api_get(path, query)
            else:
                self.serve_static(path.lstrip("/"))
        except Exception as e:
            print(f"❌ Error in do_GET: {e}")
            self.send_error(500)

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8')) if post_data else {}
            
            path = self.path.split('?')[0]
            
            if path == "/api/send":
                self.api_send(data)
            elif path == "/api/stop":
                self.api_stop()
            elif path == "/api/chats":
                self.api_create_chat()
            elif path.endswith("/load"):
                self.api_load_chat(path)
            elif path.endswith("/save"):
                self.api_save_chat(path)
            else:
                self.send_error(404)
        except Exception as e:
            print(f"❌ Error in POST: {e}")
            self.send_error(500, str(e))

    def do_DELETE(self):
         path = self.path.split('?')[0]
         if path.startswith("/api/chats/"):
            chat_id = path.split("/")[-1]
            if storage.delete_chat(chat_id):
                if self.chat_instance and self.chat_instance.current_chat_id == chat_id:
                    self.chat_instance.current_chat_id = None
                self.send_json({"status": "deleted"})
            else:
                self.send_error(404)

    # --- API Handlers ---

    def api_send(self, data):
        msg = data.get("message")
        if msg and self.chat_instance:
            if not self.chat_instance.current_chat_id:
                    base = getattr(self.chat_instance, "base_messages", [])
                    new_chat = storage.create_chat_state(base)
                    self.chat_instance.current_chat_id = new_chat["id"]
            
            # Сброс флага стопа перед новым сообщением
            self.chat_instance.stop_requested = False
            
            threading.Thread(target=self.chat_instance.send, args=({"role": "user", "content": msg},)).start()
            self.send_json({"status": "processing"})
        else:
            self.send_error(400)

    def api_stop(self):
        if self.chat_instance:
            self.chat_instance.stop_requested = True
            print("🛑 Stop signal received from Web UI")
        self.send_json({"status": "ok"})

    def api_create_chat(self):
        base = getattr(self.chat_instance, "base_messages", [])
        new_chat = storage.create_chat_state(base)
        self.send_json(new_chat)

    def api_load_chat(self, path):
        chat_id = path.split("/")[-2]
        chat_data, warning = storage.load_chat_state(chat_id)
        
        if chat_data and self.chat_instance:
            instance_state = chat_data.get("instance_state", {})
            for k, v in instance_state.items():
                if not callable(v):
                        setattr(self.chat_instance, k, v)
            
            self.chat_instance.messages = chat_data["messages"]
            self.chat_instance.current_chat_id = chat_id
            
            if hasattr(self.chat_instance, "base_messages") and not any(m["role"] == "system" for m in self.chat_instance.messages):
                self.chat_instance.messages = list(self.chat_instance.base_messages) + self.chat_instance.messages

            if warning:
                self.chat_instance.web_emit("text", f"\n\n> {warning}\n")

            self.send_json({"status": "loaded", "chat": chat_data})
        else:
            self.send_error(404)

    def api_save_chat(self, path):
        chat_id = path.split("/")[-2]
        if self.chat_instance:
            storage.save_chat_state(self.chat_instance, chat_id)
            self.send_json({"status": "saved"})

    def handle_api_get(self, path, query):
        if path == "/api/chats":
            self.send_json(storage.list_chats())
        elif path == "/api/current":
             if self.chat_instance and self.chat_instance.current_chat_id:
                 data, _ = storage.load_chat_state(self.chat_instance.current_chat_id)
                 if data:
                     self.send_json(data)
                     return
             self.send_json({"id": None})
        elif path.startswith("/api/chats/"):
            chat_id = path.split("/")[-1]
            data, _ = storage.load_chat_state(chat_id)
            self.send_json(data if data else {})

    # --- Static & Utils ---

    def serve_static(self, path):
        full_path = os.path.abspath(os.path.join(STATIC_DIR, path))
        if not full_path.startswith(STATIC_DIR):
            self.send_error(403)
            return

        if os.path.exists(full_path) and os.path.isfile(full_path):
            self.send_response(200)
            mime, _ = mimetypes.guess_type(full_path)
            if not mime and full_path.endswith(".js"): mime = "application/javascript"
            self.send_header("Content-Type", mime or "application/octet-stream")
            with open(full_path, 'rb') as f:
                content = f.read()
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404)

    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE, PATCH")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def handle_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._send_cors_headers()
        self.end_headers()
        
        q = self.chat_instance.web_queue if self.chat_instance else None
        if not q: return
        
        self.wfile.write(b": keep-alive\n\n")
        self.wfile.flush()
        
        while True:
            try:
                event = q.get(timeout=1)
                
                if isinstance(event, dict):
                    payload = json.dumps(event, ensure_ascii=False)
                    self.wfile.write(f"data: {payload}\n\n".encode())
                else:
                    payload = json.dumps({"type": "text", "data": str(event)}, ensure_ascii=False)
                    self.wfile.write(f"data: {payload}\n\n".encode())
                
                self.wfile.flush()
            except queue.Empty:
                self.wfile.write(b": keep-alive\n\n")
                self.wfile.flush()
            except Exception:
                break

def get_free_port(start_port):
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((HOST, port))
                return port
            except OSError:
                port += 1
    return start_port

def run_server(chat):
    WebRequestHandler.chat_instance = chat
    if not os.path.exists(STATIC_DIR): os.makedirs(STATIC_DIR)
    
    port = get_free_port(START_PORT)
    
    try:
        server = socketserver.ThreadingTCPServer((HOST, port), WebRequestHandler)
        server.allow_reuse_address = True
        server.daemon_threads = True
        print(f"🌍 Web Interface running at http://{HOST}:{port}")
        server.serve_forever()
    except Exception as e:
        print(f"❌ Server crashed: {e}")

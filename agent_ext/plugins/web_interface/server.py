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

PORT = 8085
HOST = "127.0.0.1"
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

mimetypes.init()
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('text/html', '.html')

class WebRequestHandler(http.server.BaseHTTPRequestHandler):
    chat_instance = None
    
    def log_message(self, format, *args):
        # Mute logs slightly
        pass 
        # print(f"🌐 [{self.address_string()}] {format%args}")

    def do_GET(self):
        try:
            if self.path == "/" or self.path == "":
                self.path = "/index.html"
                
            if self.path.startswith("/api/"):
                parsed = urlparse(self.path)
                self.handle_api_get(parsed.path, parse_qs(parsed.query))
            elif self.path == "/stream":
                self.handle_stream()
            else:
                self.serve_static_manual()
        except Exception as e:
            print(f"❌ Error in do_GET: {e}")
            traceback.print_exc()

    def serve_static_manual(self):
        path = self.path.split('?')[0]
        path = path.lstrip("/")
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

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8')) if post_data else {}
            
            if self.path == "/api/send":
                msg = data.get("message")
                if msg and self.chat_instance:
                    # Если чат не выбран, создаем новый
                    if not self.chat_instance.current_chat_id:
                         new_chat = storage.create_chat()
                         self.chat_instance.current_chat_id = new_chat["id"]
                         # Применяем базовый шаблон, если есть
                         if hasattr(self.chat_instance, "base_messages"):
                             self.chat_instance.messages = list(self.chat_instance.base_messages)
                         else:
                             # Если базы нет, оставляем как есть (скорее всего там уже что-то есть)
                             pass
                    
                    threading.Thread(target=self.chat_instance.send, args=({"role": "user", "content": msg},)).start()
                    self.send_json({"status": "processing"})
                else:
                    self.send_error(400)

            elif self.path.endswith("/load"):
                chat_id = self.path.split("/")[-2]
                chat_data = storage.load_chat(chat_id)
                
                if chat_data and self.chat_instance:
                    # 1. Загружаем сообщения в агента
                    self.chat_instance.messages = chat_data["messages"]
                    self.chat_instance.current_chat_id = chat_id
                    
                    # 2. Важно: Если в загруженном чате нет системного промпта (старый формат?),
                    # добавляем его из base_messages
                    if hasattr(self.chat_instance, "base_messages") and not any(m["role"] == "system" for m in self.chat_instance.messages):
                        self.chat_instance.messages = list(self.chat_instance.base_messages) + self.chat_instance.messages

                    self.send_json({"status": "loaded", "chat": chat_data})
                else:
                    self.send_error(404)

            elif self.path == "/api/chats":
                # Создание нового чата
                new_chat = storage.create_chat()
                # При создании нового чата мы НЕ переключаемся сразу в агенте, 
                # пока пользователь не выберет его (или фронт не вызовет load)
                # Но фронт обычно сразу вызывает load после создания.
                self.send_json(new_chat)
            
            elif self.path.startswith("/api/chats/") and self.path.endswith("/save"):
                 # Force save
                 chat_id = self.path.split("/")[-2]
                 if self.chat_instance:
                     storage.save_chat(chat_id, self.chat_instance.messages)
                     self.send_json({"status": "saved"})

            else:
                self.send_error(404)
        except Exception as e:
            print(f"❌ Error in POST: {e}")
            traceback.print_exc()

    def do_DELETE(self):
         if self.path.startswith("/api/chats/"):
            chat_id = self.path.split("/")[-1]
            if storage.delete_chat(chat_id):
                # Если удалили текущий чат, сбрасываем ID
                if self.chat_instance and self.chat_instance.current_chat_id == chat_id:
                    self.chat_instance.current_chat_id = None
                self.send_json({"status": "deleted"})
            else:
                self.send_error(404)

    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def handle_api_get(self, path, query):
        if path == "/api/chats":
            self.send_json(storage.list_chats())
        elif path.startswith("/api/chats/"):
            chat_id = path.split("/")[-1]
            chat = storage.load_chat(chat_id)
            self.send_json(chat if chat else {})

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
        
        while True:
            try:
                msg = q.get(timeout=1)
                data = json.dumps({"text": msg}, ensure_ascii=False)
                self.wfile.write(f"data: {data}\n\n".encode())
                self.wfile.flush()
            except queue.Empty:
                self.wfile.write(b": keep-alive\n\n")
                self.wfile.flush()
            except:
                break

def run_server(chat):
    WebRequestHandler.chat_instance = chat
    if not os.path.exists(STATIC_DIR): os.makedirs(STATIC_DIR)
    
    server = socketserver.ThreadingTCPServer((HOST, PORT), WebRequestHandler)
    server.allow_reuse_address = True
    server.daemon_threads = True
    print(f"🌍 Web Interface running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except Exception as e:
        print(f"❌ Server crashed: {e}")

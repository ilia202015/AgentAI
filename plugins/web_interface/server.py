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
import copy
import types
import re

is_print_debug = True

# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__)) 
plugins_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(plugins_dir)

if current_dir not in sys.path: sys.path.append(current_dir)
if root_dir not in sys.path: sys.path.append(root_dir)

# LOGGING
LOG_FILE = os.path.join(root_dir, "server_debug.log")
def log_debug(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} - {msg}\n")
    except: pass

log_debug("--- Server Module Loaded ---")

try:
    import storage
except Exception as e:
    log_debug(f"Storage import failed: {e}")

try:
    import serialization
except ImportError:
    log_debug(f"Serialization import failed")
    serialization = None

HOST = "127.0.0.1"
#HOST = "192.168.123.10"
START_PORT = 8080
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

mimetypes.init()
mimetypes.add_type('application/javascript', '.js')

class WebRequestHandler(http.server.BaseHTTPRequestHandler):
    root_chat = None
    ai_client = None
    active_chats = {}
    
    def log_message(self, format, *args): 
        pass

    def send_json_error(self, code, message):
        log_debug(f"Sending Error {code}: {message}")
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"error": message, "code": code}).encode())
        except Exception as e:
            log_debug(f"Failed to send error: {e}")

    # --- TRUE CLONING LOGIC ---
    def clone_root_chat(self):
        if is_print_debug:
            print(f"clone_root_chat()")

        # 1. Create instance WITHOUT calling __init__
        new_agent = copy.deepcopy(self.root_chat)
        new_agent.client = self.ai_client

        # 3. Initialize fresh components
        new_agent.print_to_console = False 
        new_agent.web_queue = queue.Queue()
        
        return new_agent
    def get_agent_for_chat(self, id):
        if is_print_debug:
            print(f"get_agent_for_chat({id})")

        if not id: 
            return None
        if id in self.active_chats: 
            return self.active_chats[id]
        
        log_debug(f"Creating agent for {id}")
        try:
            if id == 'temp':
                # 1. Clone from Root (Clean copy without patches)
                new_agent = self.clone_root_chat()
                
                # 2. Setup ID
                new_agent.id = id
                # Inject active final prompt
                final_text = storage.get_active_final_prompt_text()
                if final_text and hasattr(new_agent, 'system_prompt'):
                    final_prompt_base_instructions = "Инструкции далее самые важные, они нужны чтобы систематизировать все предыдущие и ты понимал, на чём нужно сделать акцент, их написал пользователь, они могут меняться в процессе чата, всегда сдедуй им, даже если они противоречат твоим редыдущим действиям:"
                    new_agent.system_prompt += f"\n\n{storage.WEB_PROMPT_MARKER_START}\n{final_prompt_base_instructions}\n{final_text}\n{storage.WEB_PROMPT_MARKER_END}"

                self.active_chats[id] = new_agent
                return new_agent
            else:
                chat, warning = storage.load_chat_state(id, self.clone_root_chat)
                if not chat:
                    return None
                    
                chat.client = self.ai_client
                # Ensure web queue exists
                if not hasattr(chat, 'web_queue') or chat.web_queue is None:
                    chat.web_queue = queue.Queue()
                    
                if warning:
                    print(warning)
                
                # Inject active final prompt
                final_text = storage.get_active_final_prompt_text()
                if final_text and hasattr(chat, 'system_prompt'):
                    final_prompt_base_instructions = "Инструкции далее самые важные, они нужны чтобы систематизировать все предыдущие и ты понимал, на чём нужно сделать акцент, их написал пользователь, они могут меняться в процессе чата, всегда сдедуй им, даже если они противоречат твоим редыдущим действиям:"
                    chat.system_prompt += f"\n\n{storage.WEB_PROMPT_MARKER_START}\n{final_prompt_base_instructions}\n{final_text}\n{storage.WEB_PROMPT_MARKER_END}"

                self.active_chats[id] = chat
                return chat

        except Exception as e:
            log_debug(f"Agent creation failed: {e}\n{traceback.format_exc()}")
            return None

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            
            if path == "/" or path == "": 
                self.serve_static("index.html")
            elif path == "/stream": 
                self.handle_stream()
            elif path.startswith("/api/"): 
                query = parse_qs(parsed.query)
                self.handle_api_get(path, query)
            elif path.startswith("/chat_images"):
                query = parse_qs(parsed.query)
                self.serve_chat_image(query)
            else: 
                self.serve_static(path.lstrip("/"))
        except Exception as e:
            self.send_json_error(500, str(e))

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length).decode('utf-8')) if length else {}
            path = self.path.split('?')[0]
            
            if path == "/api/send": self.api_send(data)
            elif path == "/api/final-prompts":
                config = storage.get_final_prompts_config()
                p_id = data.get("id") or str(time.time())
                config["prompts"][p_id] = {
                    "name": data.get("name", "New Prompt"), 
                    "text": data.get("text", ""),
                    "type": data.get("type", "system"),
                    "icon": data.get("icon", "ph-app-window")
                }
                if data.get("make_active"): config["active_id"] = p_id
                storage.save_final_prompts_config(config)
                self._refresh_active_agents_prompts()
                self.send_json({"status": "ok", "id": p_id})
            elif path == "/api/final-prompts/toggle-parameter":
                config = storage.get_final_prompts_config()
                p_id = data.get("id")
                active_params = config.get("active_parameters", [])
                if p_id in active_params: active_params.remove(p_id)
                else: active_params.append(p_id)
                config["active_parameters"] = active_params
                storage.save_final_prompts_config(config)
                self._refresh_active_agents_prompts()
                self.send_json({"status": "ok", "active_parameters": active_params})
            elif path == "/api/final-prompts/select":
                config = storage.get_final_prompts_config()
                p_id = data.get("id")
                if p_id in config["prompts"]:
                    config["active_id"] = p_id
                    storage.save_final_prompts_config(config)
                    self._refresh_active_agents_prompts()
                    self.send_json({"status": "ok"})
                else: self.send_json_error(404, "Not found")
            elif path == "/api/stop": self.api_stop(data)
            elif path == "/api/chats": self.api_create_chat()
            elif path == "/api/temp": self.api_start_temp()
            elif path.endswith("/load"): self.api_load_chat(path)
            elif path.endswith("/save"): self.api_save_chat(path)
            elif path.endswith("/edit"): self.api_edit_message(path, data)
            elif path.endswith("/clear-context"): self.api_clear_context(path)
            elif path.endswith("/model"): self.api_change_model(path, data)
            else: self.send_json_error(404, "Endpoint not found")
        except Exception as e:
            self.send_json_error(500, str(e))
    def do_PATCH(self):
         try:
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length).decode('utf-8')) if length else {}
            path = self.path.split('?')[0]
            if path.endswith("/rename"):
                 cid = path.split("/")[-2]
                 agent = self.active_chats.get(cid)
                 if agent and getattr(agent, "busy_depth", 0) > 0:
                     return self.send_json_error(409, "Agent is busy")
                 if storage.rename_chat(cid, data.get("name"), self.clone_root_chat):
                     if cid in self.active_chats:
                         self.active_chats[cid].name = data.get("name")
                     self.send_json({"status": "ok"})
                 else: self.send_json_error(400, "Fail")
            else: self.send_json_error(404, "Not found")
         except Exception as e: self.send_json_error(500, str(e))

    def do_DELETE(self):
         try:
             path = self.path.split('?')[0]
             if path.startswith("/api/final-prompts/"):
                p_id = path.split("/")[-1]
                config = storage.get_final_prompts_config()
                if p_id in config["prompts"]:
                    del config["prompts"][p_id]
                    if config["active_id"] == p_id: config["active_id"] = next(iter(config["prompts"]), None)
                    storage.save_final_prompts_config(config)
                    self.send_json({"status": "deleted"})
                else: self.send_json_error(404, "Not found")
             else:
                cid = path.split("/")[-1]
                if storage.delete_chat(cid):
                   if cid in self.active_chats: del self.active_chats[cid]
                   self.send_json({"status": "deleted"})
                else: self.send_json_error(404, "Not found")
         except Exception as e: self.send_json_error(500, str(e))

        # Handlers
    def api_send(self, data):
        if is_print_debug:
            print(f"api_send(chatId={data.get('chatId')}, msg_len={len(data.get('message', ''))}, images={len(data.get('images', []))})")

        cid = data.get("chatId")
        if not cid: 
            return self.send_json_error(400, "No chatId")
        
        agent = self.get_agent_for_chat(cid)
        if not agent: 
            return self.send_json_error(500, "Agent init failed")
        
        if getattr(agent, "busy_depth", False): 
            return self.send_json_error(409, "Busy")
        
        agent.stop_requested = False

        msg_payload = {
            "role": "user", 
            "content": data.get("message", ""),
            "images": data.get("images", [])
        }

        def run_and_save():
            try:
                agent.send(msg_payload)
            finally:
                if cid != 'temp':
                    try:
                        if cid != 'temp': storage.save_chat_state(agent)
                    except Exception as e:
                        print(f"Auto-save failed for {cid}: {e}")

        threading.Thread(target=run_and_save).start()
        self.send_json({"status": "processing"})
        
    def api_create_chat(self):
        if is_print_debug:
            print(f"api_create_chat()")
        
        new_chat = storage.save_chat_state(self.clone_root_chat())
        
        resp = new_chat.__dict__.copy()
        if 'client' in resp: del resp['client']
        if 'web_queue' in resp: del resp['web_queue']
        
        if serialization:
            resp['messages'] = serialization.serialize_history_for_web(new_chat.messages, chat_id=getattr(new_chat, 'id', None))
            
        log_debug(f"DEBUG RESP: {resp.keys()}")
        self.send_json(resp)

    def api_start_temp(self):
        if is_print_debug:
            print(f"api_start_temp()")
        
        agent = self.get_agent_for_chat('temp')
        if not agent: 
            return self.send_json_error(500, "Failed")
        if getattr(agent, "is_busy", False): 
            return self.send_json_error(409, "Busy")
        
        self.send_json({"status": "ok", "id": "temp"})

    def api_load_chat(self, path):
        cid = path.split("/")[-2]
        try:
            chat, warning = storage.load_chat_state(cid, self.clone_root_chat)
            if chat: 
                resp = chat.__dict__.copy()
                if "client" in resp: del resp["client"]
                if "web_queue" in resp: del resp["web_queue"]
                
                if serialization:
                    resp["messages"] = serialization.serialize_history_for_web(chat.messages, chat_id=cid)
                
                chat.client = self.ai_client
                self.active_chats[cid] = chat
                
                self.send_json({"status": "loaded", "chat": resp, "warning": warning})
            else: 
                self.send_json_error(404, f"Chat {cid} not found or corrupted")
        except Exception as e:
            self.send_json_error(500, f"Error loading chat: {str(e)}")
    def api_save_chat(self, path):
        if is_print_debug:
            print(f"api_save_chat({path})")
        
        cid = path.split("/")[-2]
        if cid in self.active_chats:
            storage.save_chat_state(self.active_chats[cid])
        self.send_json({"status": "saved"})

    def api_edit_message(self, path, data): 
        cid = data.get("chatId")
        agent = self.get_agent_for_chat(cid)
        if agent and getattr(agent, "busy_depth", 0) > 0:
            return self.send_json_error(409, "Agent is busy")

        self.send_json_error(501, "Not impl in debug")
    
    def api_stop(self, data):
        if is_print_debug:
            print(f"api_stop({data})")
        
        cid = data.get("chatId")
        if cid and cid in self.active_chats:
             self.active_chats[cid].stop_requested = True
        self.send_json({"status": "ok"})


    def api_clear_context(self, path):
        cid = path.split("/")[-2]
        if storage.clear_chat_context(cid):
            if cid in self.active_chats:
                # Пересоздаем агент из JSON
                new_agent, _ = storage.load_chat_state(cid, self.clone_root_chat)
                if new_agent:
                    new_agent.client = self.ai_client
                    self.active_chats[cid] = new_agent
            self.send_json({"status": "context_cleared"})
        else:
            self.send_json_error(404, "PKL not found")

    def api_change_model(self, path, data):
        cid = path.split("/")[-2]
        agent = self.active_chats.get(cid)
        if agent and getattr(agent, "busy_depth", 0) > 0:
            return self.send_json_error(409, "Agent is busy")
        model_name = data.get("model")
        if not model_name: return self.send_json_error(400, "No model")
        
        agent = self.get_agent_for_chat(cid)
        if agent:
            # Находим RPM для модели
            rpm = 25
            for m, r in agent.models:
                if m == model_name: rpm = r
            agent.model = model_name
            agent.model_rpm = rpm
            if cid != 'temp': storage.save_chat_state(agent)
            self.send_json({"status": "model_changed", "model": model_name})
        else:
            self.send_json_error(404, "Chat not found")

    def handle_api_get(self, path, query):
        if is_print_debug:
            print(f"handle_api_get({path}, {query})")

        if path == "/api/chats": 
            self.send_json(storage.list_chats())
        elif path == "/api/final-prompts":
            self.send_json(storage.get_final_prompts_config())
        elif path == "/api/models":
            self.send_json(self.root_chat.models)
        else: 
            self.send_json({})

    def serve_chat_image(self, query):
        try:
            chat_id = query.get("chat_id", [None])[0]
            filename = query.get("file", [None])[0]
            
            if not chat_id or not filename:
                return self.send_json_error(400, "Missing params")
                
            # Security check for both chat_id and filename to prevent traversal
            if any(p and (".." in p or "/" in p or "\\" in p) for p in [chat_id, filename]):
                return self.send_json_error(403, "Invalid path component")
                
            file_path = os.path.join("chats", chat_id, "images", filename)
            
            if os.path.exists(file_path):
                self.send_response(200)
                mime, _ = mimetypes.guess_type(file_path)
                self.send_header("Content-Type", mime or "application/octet-stream")
                self._send_cors_headers()
                
                with open(file_path, 'rb') as f:
                    content = f.read()
                    
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_json_error(404, "Image not found")
        except Exception as e:
            self.send_json_error(500, str(e))

    def serve_static(self, path):
        full = os.path.abspath(os.path.join(STATIC_DIR, path))
        if not full.startswith(STATIC_DIR): 
            return self.send_json_error(403, "Denied")
        if os.path.exists(full) and os.path.isfile(full):
            try:
                self.send_response(200)
                mime, _ = mimetypes.guess_type(full)
                self.send_header("Content-Type", mime or "application/octet-stream")
                with open(full, 'rb') as f: 
                    content = f.read()
                self.send_header("Content-Length", str(len(content)))
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                log_debug(f"Static serve error: {e}")
        else: self.send_json_error(404, "File not found")

    def send_json(self, data):
        try:
            #print(f"send_json({data})")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(data, default=str).encode())
        except Exception as e: log_debug(f"Send JSON error: {e}")

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE, PATCH")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def _refresh_active_agents_prompts(self):
        final_text = storage.get_active_final_prompt_text()
        marker_start = storage.WEB_PROMPT_MARKER_START
        marker_end = storage.WEB_PROMPT_MARKER_END
        base_instr = "Инструкции далее самые важные, они нужны чтобы систематизировать все предыдущие и ты понимал, на чём нужно сделать акцент, их написал пользователь, они могут меняться в процессе чата, всегда сдедуй им, даже если они противоречат твоим редыдущим действиям:"
        for agent in self.active_chats.values():
            if hasattr(agent, 'system_prompt'):
                pattern = re.escape(marker_start) + r".*?" + re.escape(marker_end)
                agent.system_prompt = re.sub(pattern, "", agent.system_prompt, flags=re.DOTALL).strip()
                if final_text:
                    agent.system_prompt += f"\n\n{marker_start}\n{base_instr}\n{final_text}\n{marker_end}"
    def handle_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._send_cors_headers()
        self.end_headers()
        
        self.wfile.write(b": keep-alive\n\n")
        self.wfile.flush()
        
        while True:
            # Snapshot of active chats to avoid runtime errors if dict changes
            current_chats = list(self.active_chats.values())
            
            if not current_chats:
                try:
                    time.sleep(1)
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                except Exception:
                    break
                continue

            got_event = False
            for chat in current_chats:
                try:
                    # Use a small timeout to poll all chats
                    if not hasattr(chat, 'web_queue') or chat.web_queue is None:
                        continue
                        
                    event = chat.web_queue.get(timeout=0.05)
                    payload = json.dumps(event, ensure_ascii=False)
                    self.wfile.write(f"data: {payload}\n\n".encode())
                    self.wfile.flush()
                    got_event = True
                except queue.Empty:
                    pass
                except Exception as e:
                    log_debug(f"SSE Connection error: {e}")
                    # Stop all agents if the user closed the connection
                    for c in current_chats:
                        if hasattr(c, "stop_requested"):
                            c.stop_requested = True
                    return

            if not got_event:
                 try:
                    time.sleep(0.5)
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                 except Exception:
                    for c in current_chats:
                        if hasattr(c, "stop_requested"): c.stop_requested = True
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
    WebRequestHandler.ai_client = chat.client
    chat.client = None
    chat.web_queue = None
    WebRequestHandler.root_chat = chat
    print(f"WebRequestHandler настроен")

    if not os.path.exists(STATIC_DIR): 
        print(f"Папки {STATIC_DIR} не существует, создаю...")
        os.makedirs(STATIC_DIR)
    print(f"Поиск порта...")
    port = get_free_port(START_PORT)
    log_debug(f"Server starting on {port}")
    print(f"Порт получен: {port}")
    try:
        server = socketserver.ThreadingTCPServer((HOST, port), WebRequestHandler)
        server.allow_reuse_address = True
        server.daemon_threads = True
        print(f"🌍 Web Interface running at http://{HOST}:{port}")
        server.serve_forever()
    except Exception as e:
        log_debug(f"Server crash: {e}")
        print(f"❌ Server crashed: {e}")

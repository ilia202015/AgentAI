
import http.server
import socketserver
import threading
import json
import logging
import queue
import time
import uuid

# Потокобезопасные структуры
command_queue = queue.Queue()
# Теперь ответы хранятся в словаре с привязкой к message_id
response_dict = {}
response_condition = threading.Condition()

class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Позволяет обрабатывать GET и POST запросы параллельно, решая проблему Deadlock."""
    daemon_threads = True
    allow_reuse_address = True

class BrowserBridgeHandler(http.server.SimpleHTTPRequestHandler):
    
    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "X-Requested-With, Content-type")
        self.end_headers()

    def do_GET(self):
        # Эндпоинт для расширения: получить следующую команду
        try:
            command = command_queue.get(timeout=2)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "command", "data": command}).encode('utf-8'))
        except queue.Empty:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "waiting"}).encode('utf-8'))

    def do_POST(self):
        # Эндпоинт для расширения: отправить результат выполнения команды
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                raise ValueError("Empty body")
                
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            # Сохраняем ответ с уникальным ID и уведомляем ожидающий поток
            msg_id = data.get("message_id")
            if msg_id:
                with response_condition:
                    response_dict[msg_id] = data
                    response_condition.notify_all()
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "received"}).encode('utf-8'))
        except Exception as e:
            logging.error(f"Ошибка при обработке POST: {e}")
            self.send_response(400)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

    def log_message(self, format, *args):
        pass

class BrowserBridgeServer:
    def __init__(self, port=8085):
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        self.server = ThreadedHTTPServer(("", self.port), BrowserBridgeHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        logging.info(f"Сервер (Threaded) запущен на порту {self.port}")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            logging.info("Сервер остановлен")

# Глобальный экземпляр сервера
bridge_server = BrowserBridgeServer()

def init_bridge():
    # Перед запуском проверяем, не работает ли уже сервер, чтобы избежать ошибки занятого порта
    stop_bridge()
    bridge_server.start()

def stop_bridge():
    bridge_server.stop()
    
def send_command(command, timeout=30):
    """Отправляет команду в браузер и ждет результат, используя уникальные ID."""
    msg_id = str(uuid.uuid4())
    command["message_id"] = msg_id
    
    command_queue.put(command)
    
    start_time = time.time()
    with response_condition:
        while time.time() - start_time < timeout:
            if msg_id in response_dict:
                return response_dict.pop(msg_id)
            # Ждем уведомления с таймаутом
            response_condition.wait(timeout=1.0)
            
    return {"status": "error", "message": f"Таймаут ожидания ответа от браузера ({timeout}с)"}

import time
import json
import queue
import threading
import logging
import os

# Настройка логирования
logger = logging.getLogger("browser_bridge")

_bridge_instance = None
_bridge_lock = threading.Lock()

class BrowserBridge:
    """
    Мост для взаимодействия между ИИ-агентом и браузерным расширением.
    Реализует механизм Long Polling для передачи команд и получения ответов.
    """
    def __new__(cls):
        global _bridge_instance
        with _bridge_lock:
            if _bridge_instance is None:
                _bridge_instance = super(BrowserBridge, cls).__new__(cls)
                _bridge_instance._initialized = False
        return _bridge_instance

    def __init__(self):
        if getattr(self, '_initialized', False):
            return
        self._command_queue = queue.Queue(maxsize=100)
        self._responses = {}
        self._response_ttl = 300 
        self._is_registered = False
        self._last_poll = 0
        self._initialized = True
        print("🌐 [BrowserBridge] Инициализирован")

    def __reduce__(self):
        return (BrowserBridge, ())

    def _cleanup_responses(self):
        now = time.time()
        expired = [rid for rid, res in self._responses.items() 
                   if now - res.get("_timestamp", 0) > self._response_ttl]
        for rid in expired:
            del self._responses[rid]

    def register(self):
        self._is_registered = True
        self._last_poll = time.time()
        print("🌐 [BrowserBridge] Расширение зарегистрировано")
        return {"status": "ok"}

    def poll(self):
        self._last_poll = time.time()
        self._cleanup_responses()
        try:
            cmd = self._command_queue.get(timeout=15)
            print(f"🌐 [BrowserBridge] Команда отправлена: {cmd.get('type')}")
            return cmd
        except queue.Empty:
            return {"type": "noop"}

    def respond(self, data):
        request_id = data.get("request_id")
        if request_id:
            data["_timestamp"] = time.time()
            self._responses[request_id] = data
            return {"status": "accepted"}
        return {"status": "error", "message": "no request_id"}

    def execute(self, command_type, params=None, timeout=30):
        """
        Отправка команды в браузер и ожидание результата.
        """
        # Исправлена проверка таймаута соединения
        if time.time() - self._last_poll > 60:
            self._is_registered = False

        if not self._is_registered:
            return {"error": "Browser extension not registered or lost connection"}
        
        request_id = f"{command_type}_{time.time()}"
        
        # Поддержка команды batch
        actual_type = command_type
        if command_type == "execute_batch":
            actual_type = "batch"

        cmd = {
            "request_id": request_id,
            "type": actual_type,
            "params": params or {}
        }
        
        try:
            self._command_queue.put(cmd, block=False)
        except queue.Full:
            return {"error": "Command queue is full"}
        
        start_wait = time.time()
        
        # Специальная логика для open_url: ожидание статуса до 30 секунд
        if actual_type == "open_url":
            while time.time() - start_wait < 30:
                if request_id in self._responses:
                    resp = self._responses.get(request_id)
                    status = resp.get("status")
                    if status in ["success", "complete", "timeout"]:
                        return self._responses.pop(request_id)
                    return self._responses.pop(request_id)
                time.sleep(0.2)
        else:
            # Стандартное ожидание для остальных команд
            while time.time() - start_wait < timeout:
                if request_id in self._responses:
                    return self._responses.pop(request_id)
                time.sleep(0.1)
            
        return {"error": "timeout"}

bridge = BrowserBridge()

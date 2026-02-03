import time
import json
import queue
import threading

class BrowserBridge:
    """
    Мост для взаимодействия между ИИ-агентом и браузерным расширением.
    Реализует механизм Long Polling для передачи команд и получения ответов.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(BrowserBridge, cls).__new__(cls)
                # Очередь команд для расширения (лимит для защиты памяти)
                cls._instance._command_queue = queue.Queue(maxsize=100)
                # Хранилище ответов от расширения
                cls._instance._responses = {}
                # Время жизни ответа в секундах
                cls._instance._response_ttl = 300 
                # Статус регистрации расширения
                cls._instance._is_registered = False
                # Время последнего запроса от расширения
                cls._instance._last_poll = 0
                print("🌐 [BrowserBridge] Инициализирован")
        return cls._instance

    def _cleanup_responses(self):
        """Очистка устаревших ответов по TTL."""
        now = time.time()
        expired = [rid for rid, res in self._responses.items() 
                   if now - res.get("_timestamp", 0) > self._response_ttl]
        for rid in expired:
            del self._responses[rid]
            print(f"🌐 [BrowserBridge] Ответ {rid} удален по TTL")

    def register(self):
        """Регистрация браузерного расширения в системе."""
        self._is_registered = True
        self._last_poll = time.time()
        print("🌐 [BrowserBridge] Расширение зарегистрировано")
        return {"status": "ok"}

    def poll(self):
        """
        Метод для расширения (Long Polling). 
        Возвращает следующую команду из очереди или 'noop' по таймауту.
        """
        self._last_poll = time.time()
        self._cleanup_responses()
        try:
            # Ожидание команды до 25 секунд
            cmd = self._command_queue.get(timeout=25)
            print(f"🌐 [BrowserBridge] Команда отправлена в расширение: {cmd.get('type')}")
            return cmd
        except queue.Empty:
            return {"type": "noop"}

    def respond(self, data):
        """Прием ответа от браузерного расширения."""
        request_id = data.get("request_id")
        if request_id:
            data["_timestamp"] = time.time()
            self._responses[request_id] = data
            print(f"🌐 [BrowserBridge] Получен ответ на {request_id}")
            return {"status": "accepted"}
        return {"status": "error", "message": "no request_id"}

    def execute(self, command_type, params=None, timeout=30):
        """
        Отправка команды в браузер и ожидание результата.
        
        Args:
            command_type (str): Тип команды (например, 'click', 'navigate').
            params (dict): Параметры команды.
            timeout (int): Время ожидания ответа в секундах.
        """
        if not self._is_registered:
            # Проверка на потерю связи (более 1 минуты без поллинга)
            if time.time() - self._last_poll > 60:
                self._is_registered = False
            return {"error": "Browser extension not registered or lost connection"}
        
        request_id = f"{command_type}_{time.time()}"
        cmd = {
            "request_id": request_id,
            "type": command_type,
            "params": params or {}
        }
        
        try:
            self._command_queue.put(cmd, block=False)
        except queue.Full:
            return {"error": "Command queue is full"}
        
        start_wait = time.time()
        while time.time() - start_wait < timeout:
            if request_id in self._responses:
                return self._responses.pop(request_id)
            time.sleep(0.1)
            
        return {"error": "timeout"}

# Синглтон для использования во всем приложении
bridge = BrowserBridge()
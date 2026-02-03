import json
import importlib.util
import types
import os
import sys

# Динамическая загрузка bridge.py для избежания ModuleNotFoundError
current_dir = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("browser_bridge", os.path.join(current_dir, "bridge.py"))
bridge_module = importlib.util.module_from_spec(spec)
# Регистрируем модуль в sys.modules, чтобы dill мог его найти при сериализации чата
sys.modules["browser_bridge"] = bridge_module
spec.loader.exec_module(bridge_module)
bridge = bridge_module.bridge

# --- Реализация инструментов ---

def browser_open_tool(self, url):
    """Открыть URL в браузере."""
    return bridge.execute("open_url", {"url": url})

def browser_actions_tool(self, commands):
    """
    Выполнить пакет команд (click, type, wait, scroll, get_state, get_html, js_exec) за один вызов.
    Используй этот инструмент для большинства задач.
    """
    return bridge.execute("execute_batch", {"commands": commands})

def browser_get_raw_html_tool(self, selector=None):
    """Получить полный HTML код страницы или элемента для глубокого анализа."""
    return bridge.execute("get_raw_html", {"selector": selector})

# --- Инициализация ---

def main(chat, settings):
    """
    Инициализация плагина browser_use.
    Регистрирует инструменты в объекте chat и настраивает API эндпоинты.
    """
    print("🔌 [browser_use] Инициализация инструментов и API...")
    
    chat.browser_open_tool = types.MethodType(browser_open_tool, chat)
    chat.browser_actions_tool = types.MethodType(browser_actions_tool, chat)
    chat.browser_get_raw_html_tool = types.MethodType(browser_get_raw_html_tool, chat)
    
    browser_tools = [
        {
            "function": {
                "name": "browser_open",
                "description": "Открыть указанный URL в новой или текущей вкладке браузера.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL для перехода (обязательно с http/https)"}
                    },
                    "required": ["url"]
                }
            }
        },
        {
            "function": {
                "name": "browser_actions",
                "description": "Выполнить пакет команд (click, type, wait, scroll, get_state, get_html, js_exec) за один вызов. Это основной инструмент для навигации и взаимодействия.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "commands": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {
                                        "type": "string", 
                                        "enum": ["click", "type", "scroll", "wait", "get_state", "get_html", "js_exec"]
                                    },
                                    "id": {"type": "integer", "description": "ID элемента (Label ID) из состояния страницы"},
                                    "text": {"type": "string", "description": "Текст для ввода или JS код"},
                                    "enter": {"type": "boolean", "description": "Нажать Enter после ввода текста"},
                                    "ms": {"type": "integer", "description": "Миллисекунды ожидания"},
                                    "direction": {"type": "string", "enum": ["up", "down"], "description": "Направление скролла"}
                                },
                                "required": ["type"]
                            }
                        }
                    },
                    "required": ["commands"]
                }
            }
        },
        {
            "function": {
                "name": "browser_get_raw_html",
                "description": "Получить полный, нефильтрованный HTML код всей страницы или конкретного элемента по CSS-селектору.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string", "description": "CSS селектор (например, '#main-content'). Если не указан, вернет всю страницу."}
                    },
                    "required": []
                }
            }
        }
    ]

    for tool in browser_tools:
        if not any(t.get("function", {}).get("name") == tool["function"]["name"] for t in chat.tools):
            chat.tools.append(tool)

    try:
        # Прямой доступ к WebRequestHandler через sys.modules (если загружен)
        server_mod = sys.modules.get('server')
        WebRequestHandler = server_mod.WebRequestHandler
        
        _old_do_POST = WebRequestHandler.do_POST
        _old_do_GET = WebRequestHandler.do_GET

        
        def new_do_POST(self):
            import logging
            logger = logging.getLogger('browser_bridge')
            try:
                if self.path == '/api/browser/register':
                    logger.info("Registering browser extension")
                    content_length = int(self.headers.get('Content-Length', 0))
                    if content_length > 0:
                        self.rfile.read(content_length)
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps(bridge.register()).encode())
                elif self.path == '/api/browser/respond':
                    content_length = int(self.headers.get('Content-Length', 0))
                    if content_length > 0:
                        post_data = json.loads(self.rfile.read(content_length))
                        logger.info(f"Received response for ID: {post_data.get('request_id')}")
                        res = bridge.respond(post_data)
                    else:
                        res = {"status": "error", "message": "no data"}
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps(res).encode())
                else:
                    _old_do_POST(self)
            except Exception as e:
                logger.error(f"Error in browser_use POST: {e}", exc_info=True)
                if not self.wfile.closed:
                    try:
                        # Если мы еще не отправили заголовки, пробуем 500
                        # Но проще просто передать управление старому обработчику или закрыть
                        _old_do_POST(self)
                    except: pass


        def new_do_GET(self):
            import logging
            logger = logging.getLogger('browser_bridge')
            logger.debug(f'GET request: {self.path}')
            if self.path == '/api/browser/poll':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(bridge.poll()).encode())
            else:
                _old_do_GET(self)

        WebRequestHandler.do_POST = new_do_POST
        WebRequestHandler.do_GET = new_do_GET
        print("✅ [browser_use] API эндпоинты интегрированы в WebRequestHandler")
        return chat
    except Exception as e:
        print(f"⚠️ [browser_use] Ошибка интеграции в веб-интерфейс: {e}")
        return chat

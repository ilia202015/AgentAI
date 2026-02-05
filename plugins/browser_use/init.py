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
    """Открыть указанный URL. Ждет полной загрузки до 10 сек (состояние complete). Если страница не загружена полностью за это время, возвращает ответ о таймауте, но не прерывает работу."""
    return bridge.execute("open_url", {"url": url})

def browser_actions_tool(self, commands):
    """Выполнить пакет команд. Типы: click, type, scroll, wait, get_state, hover, js_exec, get_text. Вкладки: list_tabs, switch_tab, close_tab. ВНИМАНИЕ: get_state НЕ возвращает список вкладок."""
    return bridge.execute("execute_batch", {"commands": commands})

def browser_get_raw_html_tool(self, selector=None):
    """Получить полный HTML код страницы или элемента. Параметр selector опционален."""
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
                "description": chat.prompts.get('browser_open', 'Открыть указанный URL в новой или текущей вкладке браузера.'),
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
                "description": chat.prompts.get('browser_actions', 'Выполнить пакет команд взаимодействия.'),
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
                                        "enum": ["click", "type", "scroll", "wait", "get_state", "hover", "js_exec", "get_text", "list_tabs", "switch_tab", "close_tab"]
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
                "description": chat.prompts.get('browser_get_raw_html', 'Получить полный HTML код страницы.'),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string", "description": "CSS селектор. Если не указан, вернет всю страницу."}
                    },
                    "required": []
                }
            }
        }
    ]

    for tool in browser_tools:
        # Обновляем или добавляем инструменты
        existing = next((t for t in chat.tools if t.get("function", {}).get("name") == tool["function"]["name"]), None)
        if existing:
            existing["function"]["description"] = tool["function"]["description"]
            existing["function"]["parameters"] = tool["function"]["parameters"]
        else:
            chat.tools.append(tool)

    try:
        # Прямой доступ к WebRequestHandler через sys.modules (если загружен)
        server_mod = sys.modules.get('server')
        if not server_mod:
             print("⚠️ [browser_use] Модуль server не найден в sys.modules")
             return chat
             
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


import types
import json
import os
import sys
import importlib.util
import time

def get_bridge():
    if "bridge_mod" in sys.modules:
        return sys.modules["bridge_mod"]
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    bridge_path = os.path.join(current_dir, "bridge.py")
    spec = importlib.util.spec_from_file_location("bridge_mod", bridge_path)
    bridge = importlib.util.module_from_spec(spec)
    sys.modules["bridge_mod"] = bridge
    spec.loader.exec_module(bridge)
    return bridge

def browser_open_tool(self, url):
    bridge = get_bridge()
    res = bridge.send_command({"action": "navigate", "url": url}, timeout=15)
    return json.dumps(res, ensure_ascii=False)

def browser_actions_tool(self, actions):
    bridge = get_bridge()
    try:
        if isinstance(actions, str):
            actions_list = json.loads(actions)
        else:
            actions_list = actions
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Invalid actions format: {e}"})
        
    res = bridge.send_command({"action": "execute_actions", "actions": actions_list}, timeout=30)
    return json.dumps(res, ensure_ascii=False)


def browser_get_dom_tool(self, delay=0):
    if float(delay) > 0:
        time.sleep(float(delay))
    bridge = get_bridge()
    res = bridge.send_command({"action": "get_dom"}, timeout=15)
    return json.dumps(res, ensure_ascii=False)


def browser_get_raw_html_tool(self, delay=0):
    if float(delay) > 0:
        time.sleep(float(delay))
    bridge = get_bridge()
    res = bridge.send_command({"action": "get_raw_html"}, timeout=15)
    return json.dumps(res, ensure_ascii=False)

def browser_execute_js_tool(self, script):
    bridge = get_bridge()
    res = bridge.send_command({"action": "execute_script", "script": script}, timeout=20)
    return json.dumps(res, ensure_ascii=False)

def main(chat, settings):
    bridge = get_bridge()
    bridge.init_bridge()
    
    chat.browser_open_tool = types.MethodType(browser_open_tool, chat)
    chat.browser_actions_tool = types.MethodType(browser_actions_tool, chat)
    chat.browser_get_dom_tool = types.MethodType(browser_get_dom_tool, chat)
    chat.browser_get_raw_html_tool = types.MethodType(browser_get_raw_html_tool, chat)
    chat.browser_execute_js_tool = types.MethodType(browser_execute_js_tool, chat)

    
    
    # Описания берутся из chat.prompts (загружены start.py из папки prompts/)
    browser_open_schema = {
        "function": {
            "name": "browser_open",
            "description": chat.prompts.get("browser_open", "Открывает URL"),
            "parameters": {
                "type": "OBJECT",
                "properties": { "url": { "type": "STRING" } },
                "required": ["url"]
            }
        }
    }
    
    browser_actions_schema = {
        "function": {
            "name": "browser_actions",
            "description": chat.prompts.get("browser_actions", "Действия в браузере"),
            "parameters": {
                "type": "OBJECT",
                "properties": { "actions": { "type": "STRING", "description": 'JSON массив действий. Пример: [{"action": "click", "selector": "#id"}, {"action": "read", "selector": ".class"}, {"action": "search", "query": "div.answer"}]' } },
                "required": ["actions"]
            }
        }
    }
    
    browser_get_dom_schema = {
        "function": {
            "name": "browser_get_dom",
            "description": chat.prompts.get("browser_get_dom", "Получить DOM"),
            "parameters": { "type": "OBJECT", "properties": {"delay": {"type": "NUMBER", "description": "Задержка в секундах перед выполнением запроса (по умолчанию 0)"}}, "required": [] }
        }
    }
    
    browser_get_raw_html_schema = {
        "function": {
            "name": "browser_get_raw_html",
            "description": chat.prompts.get("browser_get_raw_html", "Получить RAW HTML"),
            "parameters": { "type": "OBJECT", "properties": {"delay": {"type": "NUMBER", "description": "Задержка в секундах перед выполнением запроса (по умолчанию 0)"}}, "required": [] }
        }
    }
    
    browser_execute_js_schema = {
        "function": {
            "name": "browser_execute_js",
            "description": chat.prompts.get("browser_execute_js", "Выполнить JS"),
            "parameters": {
                "type": "OBJECT",
                "properties": { "script": { "type": "STRING", "description": "JS код для выполнения" } },
                "required": ["script"]
            }
        }
    }

    # Удаляем старые версии инструментов если они были (для чистоты при перезагрузках)
    chat.tools = [t for t in chat.tools if t["function"]["name"] not in ["browser_open", "browser_actions", "browser_get_dom", "browser_get_raw_html", "browser_execute_js"]]
    
    chat.tools.extend([
        browser_open_schema, 
        browser_actions_schema, 
        browser_get_dom_schema, 
        browser_get_raw_html_schema, 
        browser_execute_js_schema
    ])

    return chat

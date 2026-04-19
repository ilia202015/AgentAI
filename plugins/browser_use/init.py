
import types
import json
import os
import sys
import importlib.util

def get_bridge():
    # Пытаемся найти уже загруженный модуль или загружаем заново
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

def main(chat, settings):
    bridge = get_bridge()
    bridge.init_bridge()
    
    chat.browser_open_tool = types.MethodType(browser_open_tool, chat)
    chat.browser_actions_tool = types.MethodType(browser_actions_tool, chat)
    
    browser_open_schema = {
        "function": {
            "name": "browser_open",
            "description": "Открывает указанный URL в браузере и возвращает актуальный DOM или статус.",
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
            "description": "Выполняет действия в браузере через CDP.",
            "parameters": {
                "type": "OBJECT",
                "properties": { "actions": { "type": "STRING" } },
                "required": ["actions"]
            }
        }
    }
    
    chat.tools = [t for t in chat.tools if t["function"]["name"] not in ["browser_open", "browser_actions"]]
    chat.tools.append(browser_open_schema)
    chat.tools.append(browser_actions_schema)
        
    print("[browser_use] Инициализирован безопасный бэкенд (Threaded Server, порт 8085)")
    return chat

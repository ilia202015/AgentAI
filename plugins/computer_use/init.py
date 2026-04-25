import os
import sys
import types
import json
import base64
import traceback
import io
from PIL import Image

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

import tools
import ui_parser
import pyautogui

def computer_actions_tool(self, actions):
    try:
        tools.monitor.update_last_pos() # Сброс монитора перед началом
        acts = json.loads(actions)
        results = []
        sw, sh = pyautogui.size()
        
        for act in acts:
            action_name = act.pop("action")
            if "x" in act: act["x"] = (act["x"] / sw) * 1000
            if "y" in act: act["y"] = (act["y"] / sh) * 1000
            if "destination_x" in act: act["destination_x"] = (act["destination_x"] / sw) * 1000
            if "destination_y" in act: act["destination_y"] = (act["destination_y"] / sh) * 1000
                
            res = tools.execute_action(action_name, act)
            results.append(res)
            
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка выполнения действий: {e}\n{traceback.format_exc()}"

def computer_screenshot_tool(self):
    try:
        img_bytes = tools.take_screenshot()
        b64_img = base64.b64encode(img_bytes).decode('utf-8')
        sw, sh = pyautogui.size()
        return {
            "result": f"Скриншот сделан. Разрешение: {sw}x{sh}", 
            "images": [f"data:image/png;base64,{b64_img}"]
        }
    except Exception as e:
        return f"Ошибка при создании скриншота: {e}"

def computer_analyze_region_tool(self, x1, y1, x2, y2):
    try:
        import mss
        sw, sh = pyautogui.size()
        
        x1, y1 = max(0, int(x1)), max(0, int(y1))
        x2, y2 = min(sw, int(x2)), min(sh, int(y2))
        w = x2 - x1
        h = y2 - y1
        
        if w <= 0 or h <= 0: 
            return "Ошибка: Недопустимые размеры региона (ширина и высота должны быть > 0)."
        
        with mss.mss() as sct:
            monitor_info = sct.monitors[1]
            bbox = {"left": monitor_info["left"] + x1, "top": monitor_info["top"] + y1, "width": w, "height": h}
            sct_img = sct.grab(bbox)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            
            output = io.BytesIO()
            img.save(output, format="PNG")
            b64_img = base64.b64encode(output.getvalue()).decode('utf-8')
            
            raw_result = ui_parser.ui_parser(b64_img)
            
            if raw_result.startswith("Ошибка"):
                return raw_result
                
            adjusted_lines = []
            for line in raw_result.splitlines():
                parts = line.split(";")
                if len(parts) >= 4 and parts[0].isdigit():
                    try:
                        parts[0] = str(int(parts[0]) + x1)
                        parts[1] = str(int(parts[1]) + y1)
                        parts[2] = str(int(parts[2]) + x1)
                        parts[3] = str(int(parts[3]) + y1)
                        adjusted_lines.append(";".join(parts))
                    except:
                        adjusted_lines.append(line)
                else:
                    adjusted_lines.append(line)
                    
            return "Анализ региона:\n" + "\n".join(adjusted_lines)
    except Exception as e:
        return f"Ошибка при анализе: {e}\n{traceback.format_exc()}"


def main(chat, settings):
    chat.tools = [t for t in getattr(chat, 'tools', []) if t['function']['name'] != 'start_computer_session']
    
    p_actions = chat.prompts.get('computer_actions', 'Выполняет действия на компьютере.')
    p_screenshot = chat.prompts.get('computer_screenshot', 'Снимок экрана.')
    p_analyze = chat.prompts.get('computer_analyze_region', 'Анализ региона экрана.')
    
    tool_actions = {
        "function": {
            "name": "computer_actions",
            "description": p_actions,
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "actions": {
                        "type": "STRING",
                        "description": "JSON массив действий."
                    }
                },
                "required": ["actions"]
            }
        }
    }
    
    tool_screenshot = {
        "function": {
            "name": "computer_screenshot",
            "description": p_screenshot,
            "parameters": {
                "type": "OBJECT",
                "properties": {},
                "required": []
            }
        }
    }
    
    tool_analyze = {
        "function": {
            "name": "computer_analyze_region",
            "description": p_analyze,
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "x1": {"type": "INTEGER", "description": "X левого верхнего угла"},
                    "y1": {"type": "INTEGER", "description": "Y левого верхнего угла"},
                    "x2": {"type": "INTEGER", "description": "X правого нижнего угла"},
                    "y2": {"type": "INTEGER", "description": "Y правого нижнего угла"}
                },
                "required": ["x1", "y1", "x2", "y2"]
            }
        }
    }
    
    # Привязываем методы
    chat.computer_actions_tool = types.MethodType(computer_actions_tool, chat)
    chat.computer_screenshot_tool = types.MethodType(computer_screenshot_tool, chat)
    chat.computer_analyze_region_tool = types.MethodType(computer_analyze_region_tool, chat)
    
    tool_names = [t["function"]["name"] for t in chat.tools]
    if "computer_actions" not in tool_names: chat.tools.append(tool_actions)
    if "computer_screenshot" not in tool_names: chat.tools.append(tool_screenshot)
    if "computer_analyze_region" not in tool_names: chat.tools.append(tool_analyze)
    
    return chat

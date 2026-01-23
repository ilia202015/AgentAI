import pyautogui
import mss
import mss.tools
from PIL import Image
import io
import time
import platform
import json
import pyperclip
import webbrowser
import os
import sys

# Добавляем путь к библиотекам UFO
current_dir = os.path.dirname(os.path.abspath(__file__))
libs_path = os.path.join(current_dir, "libs")
if libs_path not in sys.path:
    sys.path.append(libs_path)

try:
    import ufo_utils
except ImportError:
    ufo_utils = None

# Настройка pyautogui
pyautogui.FAILSAFE = True 
pyautogui.PAUSE = 0.3 

def get_screen_size():
    return pyautogui.size()

def take_screenshot():
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        output = io.BytesIO()
        img.save(output, format="PNG")
        return output.getvalue()

def denormalize(x, y):
    if x is None or y is None: return 0, 0
    w, h = pyautogui.size()
    return int(float(x) / 1000 * w), int(float(y) / 1000 * h)

def execute_action(action_name, args):
    screen_width, screen_height = get_screen_size()
    
    if action_name == "open_web_browser":
        url = args.get("url", "https://google.com")
        webbrowser.open(url)
        time.sleep(2)
        return {"output": f"Browser opened: {url}"}

    elif action_name == "click_at":
        x, y = denormalize(args.get("x"), args.get("y"))
        if ufo_utils and ufo_utils.smart_click(x, y):
            return {"output": f"System click performed at {x}, {y}"}
        pyautogui.click(x, y)
        return {"output": f"Clicked at {x}, {y}"}

    elif action_name == "hover_at":
        x, y = denormalize(args.get("x"), args.get("y"))
        pyautogui.moveTo(x, y, duration=0.2)
        return {"output": f"Hovered at {x}, {y}"}

    elif action_name == "drag_and_drop":
        x, y = denormalize(args.get("x"), args.get("y"))
        dx, dy = denormalize(args.get("destination_x"), args.get("destination_y"))
        pyautogui.moveTo(x, y)
        time.sleep(0.2)
        pyautogui.dragTo(dx, dy, button='left', duration=0.5)
        return {"output": f"Dragged from {x},{y} to {dx},{dy}"}

    elif action_name == "type_text_at":
        x, y = denormalize(args.get("x"), args.get("y"))
        text = args.get("text", "")
        press_enter = args.get("press_enter", True)
        clear = args.get("clear_before_typing", True)
        
        pyautogui.click(x, y)
        time.sleep(0.5)
        
        if ufo_utils:
            ufo_utils.smart_type(x, y, text, clear=clear)
        
        if clear:
            mod = 'command' if platform.system() == 'Darwin' else 'ctrl'
            pyautogui.hotkey(mod, 'a')
            pyautogui.press('backspace')
            time.sleep(0.2)

        if text:
            try:
                pyperclip.copy(text)
                mod = 'command' if platform.system() == 'Darwin' else 'ctrl'
                pyautogui.hotkey(mod, 'v')
            except:
                pyautogui.write(text, interval=0.02)
        
        if press_enter:
            time.sleep(0.2)
            pyautogui.press('enter')
        return {"output": f"Typed text at {x}, {y}"}

    elif action_name == "key_combination":
        keys_str = args.get("keys", "")
        if not keys_str: return {"error": "No keys provided"}
        keys = [k.strip().lower() for k in keys_str.split('+')]
        mapped = []
        for k in keys:
            if k == 'control': mapped.append('ctrl')
            elif k in ['command', 'meta']: mapped.append('win')
            else: mapped.append(k)
        pyautogui.hotkey(*mapped)
        return {"output": f"Pressed keys: {keys_str}"}

    elif action_name == "scroll_document":
        direction = args.get("direction", "down")
        if direction == "down": pyautogui.press('pagedown')
        elif direction == "up": pyautogui.press('pageup')
        elif direction == "left": pyautogui.press('left')
        elif direction == "right": pyautogui.press('right')
        return {"output": f"Scrolled document {direction}"}

    elif action_name == "scroll_at":
        x, y = denormalize(args.get("x"), args.get("y"))
        direction = args.get("direction", "down")
        magnitude = args.get("magnitude", 500)
        pyautogui.moveTo(x, y)
        amount = magnitude if direction == "up" else -magnitude
        pyautogui.scroll(amount)
        return {"output": f"Scrolled {direction} at {x}, {y}"}

    elif action_name == "wait_5_seconds":
        time.sleep(5)
        return {"output": "Waited 5 seconds"}

    elif action_name == "go_back":
        pyautogui.hotkey('alt', 'left')
        return {"output": "Navigated back"}

    elif action_name == "go_forward":
        pyautogui.hotkey('alt', 'right')
        return {"output": "Navigated forward"}

    elif action_name == "search":
        webbrowser.open("https://www.google.com")
        return {"output": "Search engine opened"}

    elif action_name == "navigate":
        url = args.get("url")
        if url:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            webbrowser.open(url)
            return {"output": f"Navigated to {url}"}
        return {"error": "URL is missing"}

    return {"error": f"Unknown action: {action_name}"}

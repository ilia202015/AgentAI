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
import ctypes

# Настройка pyautogui
pyautogui.FAILSAFE = True 
pyautogui.PAUSE = 0.3 

# VK коды для Windows (раскладка-независимые)
VK_CODES = {
    'ctrl': 0x11,
    'alt': 0x12,
    'shift': 0x10,
    'win': 0x5B,
    'a': 0x41,
    'c': 0x43,
    'v': 0x56,
    'x': 0x58,
    'z': 0x5A,
    'backspace': 0x08,
    'enter': 0x0D,
    'delete': 0x2E
}

def win_hotkey(*keys):
    """Выполняет нажатие горячих клавиш через WinAPI (игнорирует текущую раскладку)."""
    if platform.system() != "Windows":
        pyautogui.hotkey(*keys)
        return

    codes = [VK_CODES.get(k.lower(), None) for k in keys]
    if None in codes:
        pyautogui.hotkey(*keys)
        return

    for code in codes:
        ctypes.windll.user32.keybd_event(code, 0, 0, 0)
    for code in reversed(codes):
        ctypes.windll.user32.keybd_event(code, 0, 2, 0)

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
        
        if clear:
            mod = 'ctrl'
            if platform.system() == 'Darwin': mod = 'command'
            win_hotkey(mod, 'a')
            pyautogui.press('backspace')
            time.sleep(0.2)

        if text:
            try:
                pyperclip.copy(text)
                mod = 'ctrl'
                if platform.system() == 'Darwin': mod = 'command'
                win_hotkey(mod, 'v')
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
        mod_map = {'control': 'ctrl', 'command': 'win', 'meta': 'win'}
        clean_keys = [mod_map.get(k, k) for k in keys]
        win_hotkey(*clean_keys)
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

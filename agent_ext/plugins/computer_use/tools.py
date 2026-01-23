
import pyautogui
import mss
import mss.tools
from PIL import Image
import io
import time
import platform
import json
import pyperclip

# Настройка pyautogui
pyautogui.FAILSAFE = True 
pyautogui.PAUSE = 0.5 

def get_screen_size():
    return pyautogui.size()

def take_screenshot():
    with mss.mss() as sct:
        # Берем первый монитор (основной)
        # sct.monitors[0] - это объединение всех мониторов
        # sct.monitors[1] - первый монитор
        monitor = sct.monitors[1]
        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        output = io.BytesIO()
        img.save(output, format="PNG")
        return output.getvalue()

def denormalize_coords(x, y, width, height):
    return int(x / 1000 * width), int(y / 1000 * height)

def execute_action(action_name, args):
    screen_width, screen_height = get_screen_size()
    
    if action_name == "open_web_browser":
        import webbrowser
        url = args.get("url", "https://google.com")
        webbrowser.open(url)
        return {"output": f"Browser opened with {url}"}

    elif action_name == "click_at":
        x = args.get("x")
        y = args.get("y")
        if x is None or y is None: raise ValueError("Missing x or y")
        real_x, real_y = denormalize_coords(x, y, screen_width, screen_height)
        pyautogui.click(real_x, real_y)
        return {"output": "Clicked"}

    elif action_name == "hover_at":
        x = args.get("x")
        y = args.get("y")
        if x is None or y is None: raise ValueError("Missing x or y")
        real_x, real_y = denormalize_coords(x, y, screen_width, screen_height)
        pyautogui.moveTo(real_x, real_y)
        return {"output": "Hovered"}

    elif action_name == "drag_and_drop":
        x = args.get("x")
        y = args.get("y")
        dest_x = args.get("destination_x")
        dest_y = args.get("destination_y")
        
        if any(v is None for v in [x, y, dest_x, dest_y]):
            raise ValueError("Missing coordinates for drag_and_drop")
            
        real_x, real_y = denormalize_coords(x, y, screen_width, screen_height)
        real_dest_x, real_dest_y = denormalize_coords(dest_x, dest_y, screen_width, screen_height)
        
        pyautogui.moveTo(real_x, real_y)
        # Задержка перед перетаскиванием часто помогает
        time.sleep(0.2)
        pyautogui.dragTo(real_dest_x, real_dest_y, button='left', duration=1.0)
        return {"output": "Dragged and dropped"}

    elif action_name == "type_text_at":
        x = args.get("x")
        y = args.get("y")
        text = args.get("text")
        press_enter = args.get("press_enter", True)
        
        if x is not None and y is not None:
            real_x, real_y = denormalize_coords(x, y, screen_width, screen_height)
            pyautogui.click(real_x, real_y)
            time.sleep(0.5) 
        
        modifier = 'command' if platform.system() == 'Darwin' else 'ctrl'
        
        # Очистка
        pyautogui.hotkey(modifier, 'a')
        time.sleep(0.1)
        pyautogui.press('backspace')
        time.sleep(0.1)

        if text:
            try:
                pyperclip.copy(text)
                time.sleep(0.3) 
                pyautogui.hotkey(modifier, 'v')
                time.sleep(0.3) 
            except Exception as e:
                print(f"Clipboard paste failed: {e}")
                pyautogui.write(text, interval=0.05)
        
        if press_enter:
            time.sleep(0.3)
            pyautogui.press('enter')
            
        return {"output": "Typed text"}
        
    elif action_name == "key_combination":
        keys_str = args.get("keys")
        if not keys_str: raise ValueError("Missing keys")
        keys = keys_str.lower().split('+')
        mapped_keys = []
        for k in keys:
            if k == 'control': mapped_keys.append('ctrl')
            elif k == 'meta': mapped_keys.append('win' if platform.system() == 'Windows' else 'command')
            else: mapped_keys.append(k)
        pyautogui.hotkey(*mapped_keys)
        return {"output": f"Pressed {keys_str}"}

    elif action_name == "scroll_document":
        direction = args.get("direction", "down")
        amount = 500 
        if direction == "down": pyautogui.scroll(-amount)
        elif direction == "up": pyautogui.scroll(amount)
        elif direction == "left": pyautogui.hscroll(-amount)
        elif direction == "right": pyautogui.hscroll(amount)
        return {"output": f"Scrolled {direction}"}
        
    elif action_name == "wait_5_seconds":
        time.sleep(5)
        return {"output": "Waited"}

    else:
        # Для неизвестных действий (например, navigate, search) 
        # возвращаем заглушку, чтобы агент не падал, а мог попробовать альтернативу
        return {"output": f"Action {action_name} executed (simulated/fallback)"}

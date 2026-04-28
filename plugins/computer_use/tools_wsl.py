
import os
import subprocess
import json
import base64
import time

# Конфигурация WSL
DISPLAY = ":99"

# НЕТ ИНДИКАЦИИ В WSL
class DummyOverlay:
    def start(self): pass
    def stop(self): pass

overlay = DummyOverlay()

def run_wsl_command(command, decode=True):
    """Выполняет bash-команду внутри WSL с заданным дисплеем."""
    full_cmd = f'wsl -e bash -c "DISPLAY={DISPLAY} {command}"'
    try:
        result = subprocess.run(full_cmd, shell=True, capture_output=True, text=decode, check=False)
        return result.stdout.strip() if decode else result.stdout
    except Exception as e:
        print(f"WSL Error: {e}")
        return None

def take_screenshot():
    """Делает скриншот через scrot (Linux) и возвращает байты."""
    temp_file = "/tmp/agent_screenshot.png"
    # scrot заменяет файл, если он существует
    run_wsl_command(f"scrot {temp_file}")
    
    # Читаем файл из Windows (обращаемся к файловой системе WSL)
    wsl_temp_path = r"\\wsl$\Ubuntu\tmp\agent_screenshot.png"
    # Если дистрибутив называется иначе, лучше читать содержимое через stdout
    
    # Надежный способ: прочитать файл в base64 внутри WSL и декодировать в Windows
    b64_output = run_wsl_command(f"base64 -w 0 {temp_file}")
    if b64_output:
        return base64.b64decode(b64_output)
    else:
        raise RuntimeError("Не удалось сделать скриншот в WSL. Убедитесь, что Xvfb запущен и scrot установлен.")

def get_screen_size():
    """Получает разрешение экрана через xdpyinfo."""
    output = run_wsl_command("xdpyinfo | awk '/dimensions:/ {print $2}'")
    if output and "x" in output:
        w, h = output.split("x")
        return int(w), int(h)
    return 1920, 1080 # Fallback

def denormalize(x, y):
    if x is None or y is None: return 0, 0
    w, h = get_screen_size()
    return int(float(x) / 1000 * w), int(float(y) / 1000 * h)

def execute_action(action_name, args):
    if action_name == "click_at":
        x, y = denormalize(args.get("x"), args.get("y"))
        run_wsl_command(f"xdotool mousemove {x} {y} click 1")
        return {"output": f"Clicked at {x}, {y}"}

    elif action_name == "hover_at":
        x, y = denormalize(args.get("x"), args.get("y"))
        run_wsl_command(f"xdotool mousemove {x} {y}")
        return {"output": f"Hovered at {x}, {y}"}

    elif action_name == "drag_and_drop":
        x, y = denormalize(args.get("x"), args.get("y"))
        dx, dy = denormalize(args.get("destination_x"), args.get("destination_y"))
        run_wsl_command(f"xdotool mousemove {x} {y} mousedown 1 mousemove {dx} {dy} mouseup 1")
        return {"output": f"Dragged from {x},{y} to {dx},{dy}"}

    elif action_name == "type_text_at":
        x, y = denormalize(args.get("x"), args.get("y"))
        text = args.get("text", "")
        press_enter = args.get("press_enter", True)
        clear = args.get("clear_before_typing", True)
        
        # Клик для фокуса
        run_wsl_command(f"xdotool mousemove {x} {y} click 1")
        time.sleep(0.2)
        
        if clear:
            run_wsl_command("xdotool key ctrl+a BackSpace")
            time.sleep(0.1)
            
        if text:
            # xdotool type иногда работает нестабильно с русским языком. 
            # Лучше использовать буфер обмена (xclip), но пока оставим базовый type
            run_wsl_command(f"xdotool type '{text}'")
            
        if press_enter:
            time.sleep(0.1)
            run_wsl_command("xdotool key Return")
            
        return {"output": f"Typed text at {x}, {y}"}

    elif action_name == "key_combination":
        keys_str = args.get("keys", "")
        if not keys_str: return {"error": "No keys provided"}
        
        # Адаптация клавиш под xdotool
        keys = keys_str.lower().replace("ctrl", "ctrl").replace("win", "super").replace("+", "+")
        run_wsl_command(f"xdotool key {keys}")
        return {"output": f"Pressed keys: {keys_str}"}

    elif action_name == "scroll_document":
        direction = args.get("direction", "down")
        if direction == "down": run_wsl_command("xdotool key Page_Down")
        elif direction == "up": run_wsl_command("xdotool key Page_Up")
        return {"output": f"Scrolled document {direction}"}

    elif action_name == "scroll_at":
        x, y = denormalize(args.get("x"), args.get("y"))
        direction = args.get("direction", "down")
        run_wsl_command(f"xdotool mousemove {x} {y}")
        # xdotool click 4 - вверх, 5 - вниз
        btn = 5 if direction == "down" else 4
        run_wsl_command(f"xdotool click {btn}")
        return {"output": f"Scrolled {direction} at {x}, {y}"}

    elif action_name == "wait":
        seconds = args.get("seconds", 1)
        time.sleep(float(seconds))
        return {"output": f"Waited {seconds} seconds"}

    elif action_name == "search":
        run_wsl_command("chromium-browser --no-sandbox https://www.google.com &")
        return {"output": "Search engine opened"}

    elif action_name == "navigate":
        url = args.get("url")
        if url:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            # Пытаемся открыть новую вкладку, если браузер запущен
            run_wsl_command(f"chromium-browser --no-sandbox {url} &")
            return {"output": f"Navigated to {url}"}
        return {"error": "URL is missing"}

    return {"error": f"Unknown action: {action_name}"}

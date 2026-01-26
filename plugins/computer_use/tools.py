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
import threading
import tkinter as tk

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

# --- НОВЫЙ ФУНКЦИОНАЛ: ИНДИКАЦИЯ И МОНИТОРИНГ ---

class StatusOverlay:
    """Виджет индикации работы агента, скрытый от захвата экрана."""
    def __init__(self):
        self.root = None
        self.thread = None
        self._stop_event = threading.Event()

    def __getstate__(self):
        """Исключаем непиклируемые объекты (tkinter, thread) из состояния."""
        state = self.__dict__.copy()
        state['root'] = None
        state['thread'] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.root = None
        self.thread = None

    def _create_window(self):
        try:
            self.root = tk.Tk()
            self.root.title("Agent Status")
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            
            sw = self.root.winfo_screenwidth()
            w = 400
            h = 40
            x = (sw - w) // 2
            y = 10
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            
            label = tk.Label(self.root, text="🤖 Агент управляет компьютером...", 
                             fg="white", bg="#2563eb", font=("Arial", 11, "bold"))
            label.pack(expand=True, fill="both")
            
            if platform.system() == "Windows":
                try:
                    self.root.update()
                    hwnd = self.root.winfo_id()
                    ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
                except Exception as e:
                    print(f"Ошибка скрытия окна: {e}")

            def check_stop():
                if self._stop_event.is_set():
                    self.root.destroy()
                    self.root = None
                else:
                    self.root.after(500, check_stop)

            self.root.after(500, check_stop)
            self.root.mainloop()
        except Exception as e:
            print(f"Ошибка StatusOverlay: {e}")

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._create_window, daemon=True)
        self.thread.start()

    def stop(self):
        self._stop_event.set()

class ActivityMonitor:
    """Мониторинг вмешательства пользователя."""
    def __init__(self):
        self.last_pos = pyautogui.position()
        self.is_interrupted = False

    def __getstate__(self):
        state = self.__dict__.copy()
        # Point объект из pyautogui обычно пиклится, но на всякий случай переведем в кортеж
        state['last_pos'] = (self.last_pos.x, self.last_pos.y) if hasattr(self.last_pos, 'x') else self.last_pos
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        # Восстанавливаем как Point если нужно, или оставляем кортежем

    def check(self):
        current_pos = pyautogui.position()
        lx, ly = (self.last_pos[0], self.last_pos[1]) if isinstance(self.last_pos, (list, tuple)) else (self.last_pos.x, self.last_pos.y)
        if abs(current_pos.x - lx) > 15 or abs(current_pos.y - ly) > 15:
            return True
        return False

    def update_last_pos(self):
        time.sleep(0.1)
        self.last_pos = pyautogui.position()

def show_completion_notification(title="Задача выполнена", message="Агент завершил работу. Нажмите, чтобы вернуться."):
    if platform.system() != "Windows":
        return
    
    ps_script = f'\n    [void] [System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms")\n    $notification = New-Object System.Windows.Forms.NotifyIcon\n    $notification.Icon = [System.Drawing.SystemIcons]::Information\n    $notification.BalloonTipTitle = "{title}"\n    $notification.BalloonTipText = "{message}"\n    $notification.Visible = $true\n    $notification.ShowBalloonTip(5000)\n\n    $code = @"\n    using System;\n    using System.Runtime.InteropServices;\n    public class WindowUtils {{ \n        [DllImport(\"user32.dll\")]\n        public static extern bool SetForegroundWindow(IntPtr hWnd);\n        [DllImport(\"user32.dll\")]\n        public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);\n    }} \n"@\n    Add-Type -TypeDefinition $code\n    \n    Start-Sleep -Seconds 2\n    $hwnd = [WindowUtils]::FindWindow($null, "Agent AI")\n    if ($hwnd -eq [IntPtr]::Zero) {{ \n        $hwnd = [WindowUtils]::FindWindow($null, "Рабочая среда")\n    }} \n    if ($hwnd -ne [IntPtr]::Zero) {{ \n        [WindowUtils]::SetForegroundWindow($hwnd)\n    }} \n    '
    
    try:
        import subprocess
        subprocess.Popen(["powershell", "-Command", ps_script], creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception as e:
        print(f"Ошибка уведомления: {e}")

# Глобальные объекты
overlay = StatusOverlay()
monitor = ActivityMonitor()

# --- КОНЕЦ НОВОГО ФУНКЦИОНАЛА ---

def win_hotkey(*keys):
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
        monitor_info = sct.monitors[1]
        sct_img = sct.grab(monitor_info)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        output = io.BytesIO()
        img.save(output, format="PNG")
        return output.getvalue()

def denormalize(x, y):
    if x is None or y is None: return 0, 0
    w, h = pyautogui.size()
    return int(float(x) / 1000 * w), int(float(y) / 1000 * h)

def execute_action(action_name, args):
    if action_name == "open_web_browser": #EXCLUDED
        url = args.get("url", "https://google.com")
        webbrowser.open(url)
        time.sleep(2)
        monitor.update_last_pos()
        return {"output": f"Browser opened: {url}"}

    elif action_name == "click_at":
        x, y = denormalize(args.get("x"), args.get("y"))
        pyautogui.click(x, y)
        monitor.update_last_pos()
        return {"output": f"Clicked at {x}, {y}"}

    elif action_name == "hover_at":
        x, y = denormalize(args.get("x"), args.get("y"))
        pyautogui.moveTo(x, y, duration=0.2)
        monitor.update_last_pos()
        return {"output": f"Hovered at {x}, {y}"}

    elif action_name == "drag_and_drop":
        x, y = denormalize(args.get("x"), args.get("y"))
        dx, dy = denormalize(args.get("destination_x"), args.get("destination_y"))
        pyautogui.moveTo(x, y)
        time.sleep(0.2)
        pyautogui.dragTo(dx, dy, button='left', duration=0.5)
        monitor.update_last_pos()
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
        monitor.update_last_pos()
        return {"output": f"Typed text at {x}, {y}"}

    elif action_name == "key_combination":
        keys_str = args.get("keys", "")
        if not keys_str: return {"error": "No keys provided"}
        keys = [k.strip().lower() for k in keys_str.split('+')]
        mod_map = {'control': 'ctrl', 'command': 'win', 'meta': 'win'}
        clean_keys = [mod_map.get(k, k) for k in keys]
        win_hotkey(*clean_keys)
        monitor.update_last_pos()
        return {"output": f"Pressed keys: {keys_str}"}

    elif action_name == "scroll_document":
        direction = args.get("direction", "down")
        if direction == "down": pyautogui.press('pagedown')
        elif direction == "up": pyautogui.press('pageup')
        elif direction == "left": pyautogui.press('left')
        elif direction == "right": pyautogui.press('right')
        monitor.update_last_pos()
        return {"output": f"Scrolled document {direction}"}

    elif action_name == "scroll_at":
        x, y = denormalize(args.get("x"), args.get("y"))
        direction = args.get("direction", "down")
        magnitude = args.get("magnitude", 500)
        pyautogui.moveTo(x, y)
        amount = magnitude if direction == "up" else -magnitude
        pyautogui.scroll(amount)
        monitor.update_last_pos()
        return {"output": f"Scrolled {direction} at {x}, {y}"}

    elif action_name == "wait_5_seconds":
        time.sleep(5)
        monitor.update_last_pos()
        return {"output": "Waited 5 seconds"}

    elif action_name == "go_back":
        pyautogui.hotkey('alt', 'left')
        monitor.update_last_pos()
        return {"output": "Navigated back"}

    elif action_name == "go_forward":
        pyautogui.hotkey('alt', 'right')
        monitor.update_last_pos()
        return {"output": "Navigated forward"}

    elif action_name == "search":
        webbrowser.open("https://www.google.com")
        monitor.update_last_pos()
        return {"output": "Search engine opened"}

    elif action_name == "navigate":
        url = args.get("url")
        if url:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            webbrowser.open(url)
            monitor.update_last_pos()
            return {"output": f"Navigated to {url}"}
        return {"error": "URL is missing"}

    return {"error": f"Unknown action: {action_name}"}

import sys
import os
import threading
import importlib.util
import types
import queue
import time
import copy
import json
from google.genai import types as genai_types

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    import server
except ImportError:
    try:
        from . import server
    except ImportError:
        spec = importlib.util.spec_from_file_location("server", os.path.join(current_dir, "server.py"))
        server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server)

try:
    import storage
except ImportError:
    try:
        from . import storage
    except ImportError:
        spec = importlib.util.spec_from_file_location("storage", os.path.join(current_dir, "storage.py"))
        storage = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(storage)


# === WEB INTERFACE METHODS ===

def web_emit(self, msg_type, payload):
    """Отправляет событие в веб-интерфейс через очередь."""
    if not hasattr(self, 'web_queue') or self.web_queue is None:
        self.web_queue = queue.Queue(maxsize=2000)
        
    cid = getattr(self, "id", "unknown")
    event = { "type": msg_type, "chatId": cid, "data": payload }
    try: 
        self.web_queue.put_nowait(event)
    except queue.Full:
        try: 
            self.web_queue.get_nowait()
            self.web_queue.put_nowait(event)
        except queue.Empty: 
            pass

def web_print(self, message, count_tab=-1, **kwargs):
    """Переопределенный print: выводит в консоль и отправляет в веб."""
    end = kwargs.get('end', '\n')
    msg_str = str(message)
    
    # Console Output (вызываем оригинальный метод или логику)
    # Так как мы не можем вызвать super() легко при манки-патчинге, реализуем логику вывода
    print(f"[{getattr(self, 'id', '?')}]: ", end='')
    if count_tab == -1: count_tab = self.count_tab
    if msg_str != '':
        try:
            console_msg = '\t' * count_tab + msg_str.replace('\n', '\n' + '\t' * count_tab)
            print(console_msg, **kwargs)
        except:
            print(msg_str, **kwargs)
    elif end != '':
        print('\t' * count_tab, **kwargs)
    
    # Web Output
    self.web_emit("text", str(message) + str(end))

def web_print_thought(self, message, count_tab=-1, **kwargs):
    end = kwargs.get('end', '\n')
    msg_str = str(message)
    
    # Buffer logic (Stack Top)
    if not hasattr(self, '_web_thought_stack'):
        self._web_thought_stack = []
        
    if self._web_thought_stack:
        self._web_thought_stack[-1] += msg_str + (end if end != '\n' else '\n')

    # Console
    print(f"[{getattr(self, 'id', '?')}] (thought): ", end='')
    if count_tab == -1: count_tab = self.count_tab
    if msg_str != '':
        try:
            console_msg = '\t' * count_tab + msg_str.replace('\n', '\n' + '\t' * count_tab)
            print(console_msg, **kwargs)
        except:
            print(msg_str, **kwargs)
    elif end != '':
        print('\t' * count_tab, **kwargs)
    
    # Web
    self.web_emit("thought", str(message) + str(end))

def web_print_code(self, language, code, count_tab=-1, max_code_display_lines=6):
    tool_data = {"title": str(language), "content": str(code)}
    
    # Direct attach to last message
    if self.messages:
        last_msg = self.messages[-1]
        if getattr(last_msg, 'role', '') == 'model':
            if not hasattr(last_msg, '_web_tools'):
                last_msg._web_tools = []
            last_msg._web_tools.append(tool_data)
    
    self.web_emit("tool", tool_data)

    # Console Output (Logic from agent.py)
    if count_tab == -1:
        count_tab = self.count_tab
    displayed_code = ""
    if code != '':
        lines = code.split('\n')
        while len(lines) and lines[0] == '':
            lines = lines[1:]
        if len(lines):
            while lines[-1] == '':
                lines.pop()
            if len(lines) > max_code_display_lines:
                half_lines = max_code_display_lines // 2
                displayed_code = '\n'.join(lines[:half_lines]) + '\n\t...\n' + '\n'.join(lines[-half_lines:])
            else:
                displayed_code = code
            if len(displayed_code) > 500:
                displayed_code = code[:250] + '\n\t...\n' + code[-250:]
    
    def raw_print(msg, tabs):
        try:
            print('\t' * tabs + msg.replace('\n', '\n' + '\t' * tabs))
        except:
            print(msg)

    print("") 
    raw_print(f"[{getattr(self, 'id', '?')}] Code ({language}):", count_tab)
    raw_print(displayed_code + '\n', count_tab + 1)

def web_send(self, messages):
    # self.busy_depth и stop_requested должны быть инициализированы
    if not hasattr(self, 'busy_depth'): self.busy_depth = 0
    if not hasattr(self, 'stop_requested'): self.stop_requested = False

    self.busy_depth += 1
    try:
        # Вызываем ОРИГИНАЛЬНЫЙ метод, сохраненный в классе
        # Обращаемся к классу через type(self) или напрямую через сохраненный атрибут
        original_send = getattr(self.__class__, '_original_send', None)
        if original_send:
            result = original_send(self, messages)
        else:
            # Fallback если что-то пошло не так (рекурсия?)
            print("ERROR: _original_send not found!")
            return "Error: Internal agent error (send loop)"
        
        cid = getattr(self, "id", None)
        if self.busy_depth == 1 and cid and cid != 'temp':
            try:
                storage.save_chat_state(self)
            except Exception as e: 
                print(f"⚠️ Autosave failed: {e}")
        return result
    finally:
        self.busy_depth -= 1
        if self.busy_depth == 0:
            self.web_emit("finish", "done")

def web_handle_stream(self, stream):
    # Push new thought buffer
    if not hasattr(self, '_web_thought_stack'): self._web_thought_stack = []
    self._web_thought_stack.append("")
    
    target_msg_index = len(self.messages)
    
    def parsing_generator(gen):
        for chunk in gen:
            if getattr(self, 'stop_requested', False):
                self.print("\n🛑 Force stopped.")
                break
            yield chunk

    try:
        original_handle = getattr(self.__class__, '_original_handle_stream', None)
        if original_handle:
            result = original_handle(self, parsing_generator(stream))
        else:
             return "Error: _original_handle_stream missing"
        
        # Attach thoughts
        if len(self.messages) > target_msg_index:
             msg = self.messages[target_msg_index]
             if getattr(msg, 'role', '') == 'model':
                 thoughts = self._web_thought_stack[-1]
                 if thoughts:
                     msg._web_thoughts = thoughts

    finally:
        cid = getattr(self, "id", None)
        if cid and cid != 'temp':
            try: storage.save_chat_state(self)
            except: pass
            
        if self._web_thought_stack:
            self._web_thought_stack.pop()
            
    return result

# === PICKLE SUPPORT ===

def web_getstate(self):
    orig = getattr(self.__class__, '_original_getstate', None)
    if orig:
        state = orig(self)
    else:
        state = self.__dict__.copy()

    # Удаляем непиклируемые или временные объекты
    for attr in ['client', 'web_queue', '_web_thought_stack']:
        if attr in state:
            del state[attr]
            
    # Сбрасываем состояние занятости для сохраненной копии
    state['busy_depth'] = 0
        
    return state

def web_setstate(self, state):
    orig = getattr(self.__class__, '_original_setstate', None)
    if orig:
        orig(self, state)
    else:
        self.__dict__.update(state)
    
    # Восстанавливаем (инициализируем) очередь
    if not hasattr(self, 'web_queue') or self.web_queue is None:
        self.web_queue = queue.Queue()
        
    if not hasattr(self, '_web_thought_stack'):
        self._web_thought_stack = []


def patch_chat_class(root_chat):
    ChatClass = root_chat.__class__
    
    if hasattr(ChatClass, '_web_interface_patched'):
        return

    print("🔌 Patching Chat class for Web Interface...")

    # 1. Сохраняем оригинальные методы
    ChatClass._original_print = ChatClass.print
    ChatClass._original_print_thought = ChatClass.print_thought
    ChatClass._original_print_code = ChatClass.print_code
    ChatClass._original_send = ChatClass.send
    ChatClass._original_handle_stream = ChatClass._handle_stream
    ChatClass._original_getstate = getattr(ChatClass, '__getstate__', None)
    ChatClass._original_setstate = getattr(ChatClass, '__setstate__', None)

    # 2. Заменяем методы на новые (функции модуля init)
    ChatClass.print = web_print
    ChatClass.print_thought = web_print_thought
    ChatClass.print_code = web_print_code
    ChatClass.send = web_send
    ChatClass._handle_stream = web_handle_stream
    
    # 3. Добавляем новые методы
    ChatClass.web_emit = web_emit
    
    # 4. Патчим pickle
    ChatClass.__getstate__ = web_getstate
    ChatClass.__setstate__ = web_setstate

    ChatClass._web_interface_patched = True
    print("✅ Chat class patched successfully.")


def main(root_chat, settings):
    print("🚀 Запуск Web Interface (Parallel Mode)...")

    # Патчим класс (применяется ко всем чатам)
    patch_chat_class(root_chat)

    server_thread = threading.Thread(target=server.run_server, args=(root_chat,), daemon=True)
    server_thread.start()
    print("✅ Web Server thread started.")
    time.sleep(10) # Костыль чтобы при запуске внутри песочницы сервер успел загрузиться
    return root_chat

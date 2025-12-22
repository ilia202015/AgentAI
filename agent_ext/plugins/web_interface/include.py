import queue
import types
import json
import threading
import os
import sys
import importlib.util
import copy
from google.genai import types as genai_types

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

web_interface_dir = os.path.dirname(os.path.abspath(__file__)) + "/plugins/web_interface"
if web_interface_dir not in sys.path:
    sys.path.append(web_interface_dir)

import storage

# --- Queue & Emitter ---
if not hasattr(self, 'web_queue'):
    self.web_queue = queue.Queue(maxsize=2000)

def web_emit(self, msg_type, payload):
    import queue
    if hasattr(self, 'web_queue'):
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

self.web_emit = types.MethodType(web_emit, self)

# --- Buffer Stack for Thoughts (Only) ---
if not hasattr(self, '_web_thought_stack'):
    self._web_thought_stack = []

def web_print(self, message, count_tab=-1, **kwargs):
    end = kwargs.get('end', '\n')
    msg_str = str(message)
    
    # Console
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
    
    # Web
    self.web_emit("text", str(message) + str(end))

def web_print_thought(self, message, count_tab=-1, **kwargs):
    end = kwargs.get('end', '\n')
    msg_str = str(message)
    
    # Buffer logic (Stack Top)
    if hasattr(self, '_web_thought_stack') and self._web_thought_stack:
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
    
    # Direct attach to last message (if it's a model message)
    # Because tools run AFTER model message is appended to history.
    if self.messages:
        last_msg = self.messages[-1]
        # Check if it looks like a model message (role 'model' or 'assistant')
        if getattr(last_msg, 'role', '') == 'model':
            if not hasattr(last_msg, '_web_tools'):
                last_msg._web_tools = []
            
            # Avoid duplicates if print_code called multiple times for same thing?
            # No, print_code is imperative. Just append.
            last_msg._web_tools.append(tool_data)
    
    self.web_emit("tool", tool_data)

    # Console Output
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

self.print = types.MethodType(web_print, self)
self.print_thought = types.MethodType(web_print_thought, self)
self.print_code = types.MethodType(web_print_code, self)

self.busy_depth = 0
self.stop_requested = False


self.__original_send = self.send
def send_with_autosave(self, message):
    import storage

    self.busy_depth += 1
    try:
        result = self.__original_send(message)
        
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

self.send = types.MethodType(send_with_autosave, self)

self.__original_handle_stream = self._handle_stream

def handle_stream_with_parsing(self, stream):
    import storage
    
    # Push new thought buffer
    if not hasattr(self, '_web_thought_stack'): self._web_thought_stack = []
    self._web_thought_stack.append("")
    
    # Fix for recursive calls (Tool Use):
    # Capture the index where the new message will be stored.
    target_msg_index = len(self.messages)
    
    def parsing_generator(gen):
        for chunk in gen:
            if getattr(self, 'stop_requested', False):
                self.print("\n🛑 Force stopped.")
                break
            yield chunk

    try:
        result = self.__original_handle_stream(parsing_generator(stream))
        
        # Attach collected thoughts to the SPECIFIC message generated by THIS stream layer
        if len(self.messages) > target_msg_index:
             msg = self.messages[target_msg_index]
             if getattr(msg, 'role', '') == 'model':
                 thoughts = self._web_thought_stack[-1]
                 if thoughts:
                     msg._web_thoughts = thoughts

    finally:
        # Autosave logic
        cid = getattr(self, "id", None)
        if cid and cid != 'temp':
            try: storage.save_chat_state(self)
            except: pass
            
        # Pop buffer
        if self._web_thought_stack:
            self._web_thought_stack.pop()
            
    return result

self._handle_stream = types.MethodType(handle_stream_with_parsing, self)


def getstate(self):
    state = self.__dict__.copy()
    state['web_queue'] = state["client"] = None
    return state

def setstate(self, state):
    self.__dict__.update(state)
    self.web_queue = queue.Queue()

self.__getstate__ = types.MethodType(getstate, self)
self.__setstate__ = types.MethodType(setstate, self)

print("✅ Web Interface: Hooks installed (Direct Attachment Mode).")

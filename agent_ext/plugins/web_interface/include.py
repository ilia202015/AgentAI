import queue
import types
import json
import threading
import os
import sys
import importlib.util
import copy

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

web_interface_dir = os.path.dirname(os.path.abspath(__file__)) + "/plugins/web_interface"
if web_interface_dir not in sys.path:
    sys.path.append(web_interface_dir)

import storage

# Limit queue size to prevent OOM, but large enough for bursts
if not hasattr(self, 'web_queue'):
    self.web_queue = queue.Queue(maxsize=2000)

def web_emit(self, msg_type, payload):
    import queue
    
    if hasattr(self, 'web_queue'):
        cid = getattr(self, "id", "unknown")
        # print(f"DEBUG: Emitting {msg_type} for {cid}") # DEBUG PRINT
        if cid == "unknown":
            print("web_emit: cid = unknown")
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
    
    self.messages[-1]["thoughts"] = self.messages[-1].get("thoughts", "") + msg_str

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
    self.web_emit("text", str(message) + str(end))

def web_print_code(self, language, code, count_tab=-1, max_code_display_lines=6):
    tool_data = {"title": str(language), "content": str(code)}
    
    if self.messages and self.messages[-1]["role"] == "assistant":
        if "tools" not in self.messages[-1]: 
            self.messages[-1]["tools"] = []
        self.messages[-1]["tools"].append(tool_data)
    self.web_emit("tool", tool_data)

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
        if self.busy_depth < 0:
            print("self.busy_depth < 0")
        if self.busy_depth == 0:
            self.web_emit("finish", "done")

self.send = types.MethodType(send_with_autosave, self)

self.__original_handle_stream = self._handle_stream

def handle_stream_with_parsing(self, stream):
    import storage

    thoughts_buffer = []
    is_thought_mode = False
    text_buffer = "" 
    
    def parsing_generator(gen):
        nonlocal is_thought_mode, text_buffer
        for chunk in gen:
            if getattr(self, 'stop_requested', False):
                self.print("\n🛑 Force stopped.")
                break
            
            yield chunk

    result = self.__original_handle_stream(parsing_generator(stream))
    
    if thoughts_buffer and self.messages and self.messages[-1]["role"] == "assistant":
        cid = getattr(self, "id", None)
        if cid and cid != 'temp':
            try: 
                storage.save_chat_state(self)
            except: 
                pass
    return result

self._handle_stream = types.MethodType(handle_stream_with_parsing, self)


def getstate(self):
    #print("getstate")
    state = self.__dict__.copy()
    #for key, value in self.__dict__.items():
        #state[key] = value
    state['web_queue'] = state["client"] = None
    return state

def setstate(self, state):
    #print("setstate")
    self.__dict__.update(state)
    self.web_queue = queue.Queue()


self.__getstate__ = types.MethodType(getstate, self)
self.__setstate__ = types.MethodType(setstate, self)

print("✅ Web Interface: Hooks installed (Queue Limited, Thread-Safe).")

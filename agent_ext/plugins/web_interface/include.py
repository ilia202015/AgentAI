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
        class FakeDelta:
            def __init__(self, content):
                self.content = content
                self.tool_calls = None
                self.role = "assistant"
                self.model_extra = {}
            def __contains__(self, item): 
                return item == 'model_extra' or hasattr(self, item)
            def __getitem__(self, item): 
                if item == 'model_extra': 
                    return self.model_extra
                return getattr(self, item, None)

        class FakeChoice:
            def __init__(self, content): 
                self.delta = FakeDelta(content)

        class FakeChunk:
            def __init__(self, content, original_chunk):
                self.choices = [FakeChoice(content)]
                self.id = getattr(original_chunk, 'id', 'fake_id')
                self.created = getattr(original_chunk, 'created', 0)
                self.model = getattr(original_chunk, 'model', 'fake_model')
                self.object = getattr(original_chunk, 'object', 'chat.completion.chunk')
                if hasattr(original_chunk, 'model_extra'): 
                    self.model_extra = original_chunk.model_extra
                else: 
                    self.model_extra = None


        nonlocal is_thought_mode, text_buffer
        for chunk in gen:
            if getattr(self, 'stop_requested', False):
                self.busy_depth = 0
                self.print("\n🛑 Force stopped.")
                break
            
            if chunk.choices and chunk.choices[0].delta.tool_calls:
                yield chunk
                continue

            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                text_buffer += content
                while True:
                    if is_thought_mode:
                        if "</thought>" in text_buffer:
                            end_idx = text_buffer.find("</thought>")
                            thoughts_buffer.append(text_buffer[:end_idx])
                            text_buffer = text_buffer[end_idx + len("</thought>"):]
                            is_thought_mode = False
                        elif "</" in text_buffer or "<" in text_buffer and len(text_buffer) < 20: 
                            break
                        else:
                            thoughts_buffer.append(text_buffer)
                            text_buffer = ""
                            break
                    else:
                        if "<thought>" in text_buffer:
                            start_idx = text_buffer.find("<thought>")
                            if start_idx > 0: 
                                yield FakeChunk(text_buffer[:start_idx], chunk)
                            text_buffer = text_buffer[start_idx + len("<thought>"):]
                            is_thought_mode = True
                        elif "<" in text_buffer and len(text_buffer) < 20: 
                            break
                        else:
                            yield FakeChunk(text_buffer, chunk)
                            text_buffer = ""
                            break
            else:
                yield chunk
        
        if text_buffer: 
            yield FakeChunk(text_buffer, chunk)

    result = self.__original_handle_stream(parsing_generator(stream))
    
    if thoughts_buffer and self.messages and self.messages[-1]["role"] == "assistant":
        full_thoughts = "".join(thoughts_buffer)
        self.messages[-1]["thoughts"] = self.messages[-1].get("thoughts", "") + full_thoughts
        
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

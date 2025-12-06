import queue
import types
import json

if not hasattr(self, 'web_queue'):
    self.web_queue = queue.Queue()

def web_emit(self, msg_type, payload):
    if hasattr(self, 'web_queue'):
        event = {"type": msg_type, "data": payload}
        self.web_queue.put(event)

self.web_emit = types.MethodType(web_emit, self)

def web_print(self, message, count_tab=-1, **kwargs):
    end = kwargs.get('end', '\n')
    msg_str = str(message)
    
    # Console
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
    # Только трансляция. Сохранение делает init.py через парсинг стрима.
    self.web_emit("thought", str(message))

def web_print_code(self, language, code, count_tab=-1, max_code_display_lines=6):
    code_str = str(code)
    tool_data = {"title": str(language), "content": code_str}

    # 1. Прямая запись в историю (Last Assistant Message)
    if self.messages:
        target_msg = None
        if self.messages[-1]["role"] == "assistant":
            target_msg = self.messages[-1]
        
        if target_msg:
            if "tools" not in target_msg:
                target_msg["tools"] = []
            target_msg["tools"].append(tool_data)

    # 2. Console
    if count_tab == -1: count_tab = self.count_tab
    print("\n\n" + '\t' * count_tab + str(language) + ":\n")
    lines = code_str.split('\n')
    if len(lines) > 20:
         print('\t' * (count_tab + 1) + f"... {len(lines)} lines ...\n")
    else:
         print('\t' * (count_tab + 1) + code_str.replace('\n', '\n' + '\t' * (count_tab + 1)) + '\n')

    # 3. Web
    self.web_emit("tool", tool_data)

self.print = types.MethodType(web_print, self)
self.print_thought = types.MethodType(web_print_thought, self)
self.print_code = types.MethodType(web_print_code, self)

print("✅ Web Interface: Hooks installed (Direct Tools, Stream Thoughts).")

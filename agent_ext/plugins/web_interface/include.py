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
    
    # Console
    if count_tab == -1: count_tab = self.count_tab
    # Приводим к строке для безопасности консоли
    msg_str = str(message)
    if msg_str != '':
        console_msg = '\t' * count_tab + msg_str.replace('\n', '\n' + '\t' * count_tab)
        print(console_msg, **kwargs)
    elif end != '':
        print('\t' * count_tab, **kwargs)
    
    # Web
    # Принудительно приводим к строке, чтобы избежать [object Object] в JS
    self.web_emit("text", str(message) + str(end))

def web_print_thought(self, message, count_tab=-1, **kwargs):
    if count_tab == -1: count_tab = self.count_tab
    self.web_emit("thought", str(message))

def web_print_code(self, language, code, count_tab=-1, max_code_display_lines=6):
    if count_tab == -1: count_tab = self.count_tab

    displayed_code = ""
    code_str = str(code) # Safety cast
    if code_str != '':
        lines = code_str.split('\n')
        while len(lines) and lines[0] == '': lines = lines[1:]
        if len(lines):
            while lines[-1] == '': lines.pop()
            if len(lines) > max_code_display_lines:
                half_lines = max_code_display_lines // 2
                displayed_code = '\n'.join(lines[:half_lines]) + '\n\t...\n' + '\n'.join(lines[-half_lines:])
            else:
                displayed_code = code_str
            if len(displayed_code) > 500:
                displayed_code = code_str[:250] + '\n\t...\n' + code_str[-250:]

    print("\n\n" + '\t' * count_tab + str(language) + ":\n")
    print('\t' * (count_tab + 1) + displayed_code.replace('\n', '\n' + '\t' * (count_tab + 1)) + '\n')

    self.web_emit("tool", {"title": str(language), "content": code_str})

self.print = types.MethodType(web_print, self)
self.print_thought = types.MethodType(web_print_thought, self)
self.print_code = types.MethodType(web_print_code, self)

print("✅ Web Interface: Enhanced hooks installed (Text/Thought/Tool).")

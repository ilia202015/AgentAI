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
    msg_str = str(message)
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
    msg_str = str(message)
    
    # 1. Update history directly
    if self.messages and self.messages[-1]["role"] == "assistant":
        last_msg = self.messages[-1]
        last_msg["thoughts"] = (last_msg.get("thoughts", "") + msg_str)

    # 2. Web emit
    if count_tab == -1: count_tab = self.count_tab
    self.web_emit("thought", msg_str)

def web_print_code(self, language, code, count_tab=-1, max_code_display_lines=6):
    code_str = str(code)
    tool_data = {"title": str(language), "content": code_str}

    # 1. Update history directly
    # Мы прикрепляем код (инструмент или результат) к последнему сообщению ассистента
    # Даже если это результат выполнения, который происходит позже, логически он относится к этому шагу.
    if self.messages:
        # Ищем последнее сообщение ассистента (идем с конца)
        # Обычно это messages[-1], но если агент уже добавил message tool, то -2.
        # Но agent.py добавляет tool message ПОСЛЕ выполнения. А print_code вызывается ВО ВРЕМЯ выполнения.
        # Так что messages[-1] должно быть assistant (с tool_calls).
        
        target_msg = None
        if self.messages[-1]["role"] == "assistant":
            target_msg = self.messages[-1]
        elif len(self.messages) > 1 and self.messages[-1]["role"] == "tool" and self.messages[-2]["role"] == "assistant":
             target_msg = self.messages[-2]
             
        if target_msg:
            if "tools" not in target_msg:
                target_msg["tools"] = []
            target_msg["tools"].append(tool_data)

    # 2. Console output
    if count_tab == -1: count_tab = self.count_tab
    print("\n\n" + '\t' * count_tab + str(language) + ":\n")
    lines = code_str.split('\n')
    if len(lines) > 20:
         print('\t' * (count_tab + 1) + f"... {len(lines)} lines ...\n")
    else:
         print('\t' * (count_tab + 1) + code_str.replace('\n', '\n' + '\t' * (count_tab + 1)) + '\n')

    # 3. Web emit
    self.web_emit("tool", tool_data)

self.print = types.MethodType(web_print, self)
self.print_thought = types.MethodType(web_print_thought, self)
self.print_code = types.MethodType(web_print_code, self)

print("✅ Web Interface: Hooks installed (Direct History Update).")

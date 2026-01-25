import types
import json
import os
import importlib.util
import sys

# Импорт computer_chat
current_dir = os.path.dirname(os.path.abspath(__file__))

# ВАЖНО: Добавляем текущую директорию в sys.path, чтобы pickle мог найти модуль
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    # Сначала пробуем импортировать через sys.path
    import computer_chat
except ImportError:
    # Фолбэк на ручную загрузку
    spec = importlib.util.spec_from_file_location("computer_chat", os.path.join(current_dir, "computer_chat.py"))
    computer_chat = importlib.util.module_from_spec(spec)
    # Регистрируем модуль в sys.modules, чтобы pickle мог его найти по имени 'computer_chat'
    sys.modules["computer_chat"] = computer_chat 
    spec.loader.exec_module(computer_chat)

ComputerUseChat = computer_chat.ComputerUseChat

def main(chat, settings):
    # Добавляем инструмент computer_use_tool в основной чат
    
    tool_def = {
        "function": {
            "name": "start_computer_session",
            "description": chat.prompts["start_computer_session"],
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "task": {
                        "type": "STRING",
                        "description": "Подробное описание задачи, которую нужно выполнить на компьютере."
                    }
                },
                "required": ["task"]
            }
        }
    }
    
    if not hasattr(chat, 'tools'):
        chat.tools = []
    
    exists = False
    for t in chat.tools:
        if t['function']['name'] == 'start_computer_session':
            exists = True
            break
            
    if not exists:
        chat.tools.append(tool_def)
        print("🔌 Computer Use tool registered.")
    
    def start_computer_session_tool(self, task):
        # Создаем дочерний чат для Computer Use
        computer_agent = ComputerUseChat(print_to_console=True, count_tab=self.count_tab + 1)
        
        # Передаем web_emit для стриминга
        if hasattr(self, 'web_emit'):
            computer_agent.web_emit = self.web_emit
            
        result = computer_agent.run_task(task)
        return result

    chat.start_computer_session_tool = types.MethodType(start_computer_session_tool, chat)
    
    return chat

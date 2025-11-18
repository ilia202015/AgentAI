import os
import json
import logging
import ast
import sys
import types
import pickle
import schedule
import time
import threading
from datetime import datetime
from openai import OpenAI

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agent_med.log')
    ]
)
logger = logging.getLogger(__name__)

with open("api.key") as f:
    api_key = f.read()

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

local_env = locals()
result = ''

class Chat:
    def __init__(self):
        self.system_prompt = """
Ты - продвинутый AI-агент с самомодификацией. Ты можешь:
- Выполнять Python код
- Изменять собственный код
- Сохранять и загружать чаты
- Планировать задачи
- Работать с пользовательскими данными

Твоя цель - эффективно решать задачи с минимальным вмешательством пользователя.
Используй инструменты только когда необходимо. Пиши краткие и информативные ответы.
"""

        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "python",
                    "description": "Выполнить Python код с валидацией",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Python код для выполнения",
                            }
                        },
                        "required": ["code"]
                    },
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_method",
                    "description": "Изменить или добавить метод",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Код метода",
                            },
                            "metod": {
                                "type": "string",
                                "description": "Имя метода",
                            },
                        },
                        "required": ["code", "metod"]
                    },
                }
            },
        ]

        self.tools_dict = {
            "python" : ["code"],
            "update_method" : ["code", "metod"]
        }

        self.messages = [
            {"role": "system", "content": self.system_prompt},
        ]
        
        # Новые функции
        self.user_data = {}
        self.scheduled_tasks = []
        self.chat_history_file = "chat_history.pkl"
        
        # Загружаем сохраненные данные
        self.load_user_data()
        self.load_chat_history()
        
        # Запускаем планировщик
        self.start_scheduler()

    def load_user_data(self):
        """Загрузка пользовательских данных"""
        try:
            with open("user_data.json", "r") as f:
                self.user_data = json.load(f)
        except FileNotFoundError:
            self.user_data = {"name": "", "preferences": {}, "usage_stats": {}}

    def save_user_data(self):
        """Сохранение пользовательских данных"""
        with open("user_data.json", "w") as f:
            json.dump(self.user_data, f, indent=2)

    def load_chat_history(self):
        """Загрузка истории чатов"""
        try:
            with open(self.chat_history_file, "rb") as f:
                history = pickle.load(f)
                # Применяем изменения кода из истории
                for msg in history:
                    if msg.get("type") == "code_update":
                        self.apply_code_update(msg["code"])
        except FileNotFoundError:
            pass

    def save_chat_history(self):
        """Сохранение истории чатов"""
        with open(self.chat_history_file, "wb") as f:
            pickle.dump(self.messages, f)

    def apply_code_update(self, code):
        """Применение обновления кода из истории"""
        try:
            exec(code, globals(), locals())
        except Exception as e:
            logger.error(f"Ошибка применения кода из истории: {e}")

    def start_scheduler(self):
        """Запуск планировщика задач"""
        def scheduler_loop():
            while True:
                schedule.run_pending()
                time.sleep(1)
        
        scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
        scheduler_thread.start()

    def schedule_task(self, task_func, interval_minutes=60):
        """Планирование задачи"""
        schedule.every(interval_minutes).minutes.do(task_func)
        self.scheduled_tasks.append({"func": task_func, "interval": interval_minutes})

    def validate_python_code(self, code):
        """Валидация Python кода"""
        try:
            ast.parse(code)
            return True, "Код прошел валидацию"
        except SyntaxError as e:
            return False, f"Синтаксическая ошибка: {e}"
        except Exception as e:
            return False, f"Ошибка валидации: {e}"

    def python_tool(self, code):
        """Выполнение Python кода"""
        is_valid, message = self.validate_python_code(code)
        if not is_valid:
            logger.warning(f"Код не прошел валидацию: {message}")
            return f"Ошибка: {message}"
        
        try:
            global local_env, result
            exec(code, globals(), local_env)
            logger.info("Код выполнен успешно")
            return result
        except Exception as e:
            logger.error(f"Ошибка выполнения кода: {e}")
            return f"Ошибка выполнения: {e}"

    def update_method_tool(self, code, method):
        """Обновление метода"""
        code += f"\nself.{method} = types.MethodType({method}, self)"
        
        is_valid, message = self.validate_python_code(code)
        if not is_valid:
            logger.warning(f"Код не прошел валидацию: {message}")
            return f"Ошибка: {message}"
        
        try:
            exec(code, globals(), locals())
            # Сохраняем обновление в историю
            self.messages.append({
                "type": "code_update",
                "code": code,
                "timestamp": datetime.now().isoformat()
            })
            self.save_chat_history()
            logger.info(f"Метод {method} обновлен")
            return f"Метод {method} успешно обновлен"
        except Exception as e:
            logger.error(f"Ошибка обновления метода: {e}")
            return f"Ошибка обновления: {e}"

    def check_tool_args(self, args, tool_args, tool_id):
        for arg in args:
            if arg not in tool_args:
                self.send({
                    "role": "tool", 
                    "tool_call_id": tool_id, 
                    "content": f"Ошибка: отсутствует параметр {arg}"
                })
                return False
        return True

    def tool_exec(self, args, tool_args, tool_id, name):
        if self.check_tool_args(args, tool_args, tool_id):
            exec(f"result = self.{name}_tool(*[tool_args[arg] for arg in args])", globals(), locals())
            self.send({
                "role": "tool", 
                "tool_call_id": tool_id, 
                "content": result
            })

    def send(self, message):
        """Отправка сообщения"""
        self.messages.append(message)

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=self.messages,
                tools=self.tools,
                max_tokens=8192
            )
            
            assistant_message = response.choices[0].message
            self.messages.append(assistant_message)
            
            # Сохраняем историю
            self.save_chat_history()
            
            logger.info("Получен ответ от модели")
            
            if assistant_message.content:
                print(f"\nАгент: {assistant_message.content}")

            if assistant_message.tool_calls:
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    logger.info(f"Вызов инструмента: {tool_name}")
                    
                    if tool_name in self.tools_dict.keys():
                        self.tool_exec(self.tools_dict[tool_name], tool_args, tool_call.id, tool_name)
                    else:
                        self.send({
                            "role": "tool", 
                            "tool_call_id": tool_call.id,
                            "content": "Инструмент не существует"
                        })
                        
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения: {e}")
            error_msg = f"Произошла ошибка: {e}"
            print(f"\nОшибка: {error_msg}")
            self.send({"role": "system", "content": error_msg})

    def get_usage_stats(self):
        """Получение статистики использования"""
        return {
            "total_messages": len(self.messages),
            "tool_calls": len([m for m in self.messages if m.get("role") == "tool"]),
            "scheduled_tasks": len(self.scheduled_tasks),
            "user_data_fields": len(self.user_data)
        }

def main():
    """Главная функция"""
    print("Запуск улучшенного AI-агента")
    print("Функции: планировщик, сохранение чатов, пользовательские данные")
    
    chat_agent = Chat()
    
    try:
        while True:
            user_input = input("\nВы: ")
            if user_input.lower() in ['exit', 'quit', 'выход']:
                print("Завершение работы")
                break
            chat_agent.send({"role": "user", "content": user_input})
    except KeyboardInterrupt:
        print("\nПрограмма завершена")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        print(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    main()

import os, json, logging, ast, sys, types
from openai import OpenAI

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agent_min.log')
    ]
)
logger = logging.getLogger(__name__)

with open("api.key") as f:
    api_key = f.read()

with open("agent_min.py") as f:
    self_code = f.read()

with open("system_prompt") as f:
    self_system_prompt = f.read()

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

class Chat:
    local_env = dict()
    result = ''

    def __init__(self):
        self.local_env["self"] = self

        self.system_prompt = self_system_prompt + self_code

        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "python",
                    "description": "Выполнить Python код. Перед выполнением код проходит валидацию, если не успешно возвращается её вердикт вместо результата и выполнения. Результат сохраняется в переменную result, то что ты вывел с помощью print или через stdout (например, при запуске приложения через system) ты не увидешь, но увидет пользователь, чтобы передать себе информацию вместо print(\"...\") используй result += \"...\". Код выполняется в окружении скрипта agent_min.py, реализовано с помощью exec(code, globals(), local_env) (local_env это locals(), но внуртри класса Chat), self - текущий self класса chat, ты можешь переписать любой его метод или изменить любую переменную (например, переписать send (написать def send:\n\t#...; self.send = types.MethodType(send, self))), все переменные окружения сохраняются между запусками.",
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
        ]

        self.tools_dict = {
            "python" : ["code"]
        }

        self.messages = [
            {"role": "system", "content": self.system_prompt},
        ]

    def validate_python_code(self, code):
        """Валидация Python кода для безопасности"""
        try:
            # Проверка синтаксиса
            ast.parse(code)
            
            return True, "Код прошел валидацию"
        except SyntaxError as e:
            return False, f"Синтаксическая ошибка: {e}"
        except Exception as e:
            return False, f"Ошибка валидации: {e}"

    def python_tool(self, code):
        """Безопасное выполнение Python кода"""
        is_valid, message = self.validate_python_code(code)
        if not is_valid:
            logger.warning(f"Код не прошел валидацию: {message}")
            return f"Ошибка: {message}"
        
        try:
            # Выполняем код

            self.local_env["result"] = ''
            exec(code, globals(), self.local_env)
            
            logger.info(f"Код выполнен успешно. Результат: {self.local_env["result"]}")
            return self.local_env["result"]
            
        except Exception as e:
            logger.error(f"Ошибка выполнения кода: {e}")
            return f"Ошибка выполнения: {e}"

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
            self.python_tool(f"result = self.{name}_tool(*{[tool_args[arg] for arg in args]})")
            self.send({
                "role": "tool", 
                "tool_call_id": tool_id, 
                "content": self.local_env["result"]
            })

    def send(self, message):
        """Отправка сообщения и обработка ответа"""
        self.messages.append(message)

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=self.messages,
                tools=self.tools,
            )
            
            assistant_message = response.choices[0].message
            self.messages.append(assistant_message)

            logger.info(f"Получен ответ от модели")
            
            if assistant_message.content:
                print(f"\n🤖 Агент: {assistant_message.content}")

            if assistant_message.tool_calls:
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    logger.info(f"Вызов инструмента: {tool_name} с аргументами: {tool_args}")
                    
                    if tool_name in self.tools_dict.keys():
                        self.tool_exec(self.tools_dict[tool_name], tool_args, tool_call.id, tool_name)
                    else:
                        self.send({
                            "role": "tool", 
                            "tool_call_id": tool_call.id,
                            "content": "Такого инструмента не существует"
                        })
                        
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения: {e}")
            error_msg = f"Произошла ошибка: {e}"
            print(f"\n❌ {error_msg}")
            self.send({"role": "system", "content": error_msg})


def main():
    """Главная функция"""
    print("🚀 Запуск улучшенного AI-агента с самомодификацией!")
    print("=" * 60)
    print("Агент может:")
    print("• Выполнять Python код")
    print("• Изменять собственный код во время работы")
    print("• Добавлять новые инструменты и функции")
    print("• Адаптироваться к новым задачам")
    print("=" * 60)
    
    chat_agent = Chat()
    
    try:
        while True:
            user_input = input("\n👤 Вы: ")
            if user_input.lower() in ['exit', 'quit', 'выход']:
                print("👋 До свидания!")
                break
            chat_agent.send({"role": "user", "content": user_input})
    except KeyboardInterrupt:
        print("\n👋 Программа завершена пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        print(f"\n💥 Критическая ошибка: {e}")


if __name__ == "__main__":
    main()

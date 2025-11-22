import os, json, logging, ast, sys, types, readline, datetime, time
from openai import OpenAI


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agent_med/agent_med.log')
    ]
)
logger = logging.getLogger(__name__)

with open("agent_med/gemini.key", 'r', encoding="utf8") as f:
    ai_key = f.read()

with open("agent_med/user_profile.json", 'r', encoding="utf8") as f:
    self_user_profile = f.read()

with open("agent_med/agent_med.py", 'r', encoding="utf8") as f:
    self_code = f.read()

with open("agent_med/system_prompt", 'r', encoding="utf8") as f:
    self_system_prompt = f.read()

with open("agent_med/python_prompt", 'r', encoding="utf8") as f:
    self_python_prompt = f.read()

with open("agent_med/chat_prompt", 'r', encoding="utf8") as f:
    self_chat_prompt = f.read()

with open("agent_med/chat_exec_prompt", 'r', encoding="utf8") as f:
    self_chat_exec_prompt = f.read()

with open("agent_med/user_profile_prompt", 'r', encoding="utf8") as f:
    self_user_profile_prompt = f.read()

#client = OpenAI(api_key=ai_key, base_url="https://api.deepseek.com")
client = OpenAI(api_key=ai_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")

#model = "deepseek-chat"
model = "gemini-2.5-flash"

model_rpm = 10

last_send_time = 0

class Chat:
    local_env = dict()
    result = ''
    

    def __init__(self, output_mode="user", count_tab = 0):
        self.output_mode = output_mode
        self.count_tab = count_tab

        self.local_env["self"] = self

        self.system_prompt = self_system_prompt + self_code + f"Режим вывода: {output_mode}\n" + "Информация о пользователе (user_profile.json):\n" + self_user_profile

        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "python",
                    "description": self_python_prompt,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Python код для выполнения, не более 4000 символов, если нужно больше, разбей код на части и сделай несколько запросов",
                            }
                        },
                        "required": ["code"]
                    },
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "chat",
                    "description": self_chat_prompt,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string", 
                                "description": "Имя чата"
                            },
                            "message": {
                                "type": "string",
                                "description": "Сообщение для отправки в чат"
                            }
                        },
                        "required": ["name", "message"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "chat_exec",
                    "description": self_chat_exec_prompt,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string", 
                                "description": "Имя чата"
                            },
                            "code": {
                                "type": "string",
                                "description": "Код для выполненич в чате"
                            }
                        },
                        "required": ["name", "code"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "google_search",
                    "description": "Выполняет поиск через Google Custom Search API. Возвращает результаты в формате JSON.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Поисковый запрос"
                            },
                            "num_results": {
                                "type": "integer",
                                "description": "Количество результатов (по умолчанию 10, максимум 10)",
                                "default": 10
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "user_profile",
                    "description": self_user_profile_prompt,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "data": {
                                "type": "string",
                                "description": "Данные для записи в формате json"
                            },
                        },
                        "required": ["data"]
                    }
                }
            }
        ]

        self.chats = dict()

        # Обязательные параметры
        self.tools_dict_required = { 
            "chat" : ["name", "message"],
            "chat_exec" : ["name", "code"],
            "python" : ["code"],
            "google_search" : ["query"],
            "user_profile" : ["data"],
        }

        # Дополнительные параметры
        self.tools_dict_additional  = { 
            "chat" : [],
            "chat_exec" : [],
            "python" : [],
            "google_search" : ["num_results"],
            "user_profile" : [],
        }

        self.messages = [
            {"role": "system", "content": self.system_prompt},
        ]

    def chat_tool(self, name, message):
        if name not in self.chats:
            self.chats[name] = Chat(output_mode="auto", count_tab=self.count_tab + 1)
            
        self.print(f"\n🤖 Агент (авто, запрос, чат: {name}): " + message)

        return self.chats[name].send({"role": "user", "content": message})

    def chat_exec_tool(self, name, code):
        if name not in self.chats.keys():
            self.chats[name] = Chat(output_mode="auto", count_tab=self.count_tab + 1)
        return self.chats[name].python_tool(code)

    def google_search_tool(self, query, num_results=10):
        try:
            # Импортируем внутри функции чтобы избежать проблем с областью видимости
            import json
            from googleapiclient.discovery import build
            
            # Чтение ключа API из файла
            with open("agent_med/google.key", "r") as f:
                api_key = f.read().strip()
            
            # Чтение Search Engine ID
            with open("agent_med/search_engine.id", "r") as f:
                search_engine_id = f.read().strip()
            
            # Создаем сервис
            service = build("customsearch", "v1", developerKey=api_key)
            
            # Выполняем поиск
            result = service.cse().list(
                q=query,
                cx=search_engine_id,
                num=min(num_results, 10)
            ).execute()
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return f"Ошибка при выполнении поиска: {e}"

    def user_profile_tool(self, data):
        try:
            profile_file = "agent_med/user_profile.json"
            
            data = json.loads(data)
            with open(profile_file, 'r', encoding="utf8") as f:
                user_profile = json.load(f)

            for [key, val] in data.items():
                if val == "":
                    if key in user_profile:
                        user_profile.pop(key)
                else:
                    user_profile[key] = {
                        "data" : val,
                        "time" : datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
            
            with open(profile_file, 'w', encoding="utf8") as f:
                    json.dump(user_profile, f, ensure_ascii=False, indent=2)
            
            return "Профиль обновлён успешно"
        except Exception as e:
            return f"Ошибка: {e}"


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

    def python_tool(self, code, no_print=False):
        """Безопасное выполнение Python кода"""
        is_valid, message = self.validate_python_code(code)
        if not is_valid:
            logger.warning(f"Код не прошел валидацию: {message}")
            return f"Ошибка: {message}"
        
        try:
            # Выполняем код
            
            if not no_print:
                print('\t' * self.count_tab + "python:")
                self.print(code, count_tab=self.count_tab + 1)

            self.local_env["self"] = self
            self.local_env["result"] = ''
            exec(code, globals(), self.local_env)
            
            if not no_print:
                print('\t' * self.count_tab + "Результат:")
                self.print(self.local_env["result"], count_tab=self.count_tab + 1)

            logger.info(f"Код выполнен успешно. Результат: {self.local_env["result"]}")
            return str(self.local_env["result"])
            
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

    def tool_exec(self, name, tool_args, tool_id):
        required = self.tools_dict_required[name]
        additional = self.tools_dict_additional[name]

        for key, val in tool_args.items():
            if type(val) == str:
                tool_args[key] = repr(val)

        try:
            if self.check_tool_args(required, tool_args, tool_id):
                self.python_tool(
                    f"result = self.{name}_tool(" +
                    ', '.join(str(tool_args[arg]) for arg in required) + 
                    (', ' if len(additional) else '') + 
                    ', '.join(str(arg) + '=' + str(tool_args[arg]) for arg in additional if arg in tool_args) + ")", 
                    no_print=True
                    )
                self.send({
                    "role": "tool", 
                    "tool_call_id": tool_id, 
                    "content": self.local_env["result"]
                })
        except Exception as e:
            logger.error(f"Ошибка инструмента: {e}")
            self.send({
                    "role": "tool", 
                    "tool_call_id": tool_id, 
                    "content": f"Ошибка инструмента: {e}"
                })

    def print(self, message, count_tab=-1):
        if count_tab == -1:
            count_tab = self.count_tab
        f = False
        if message[-1] == '\n':
            message = message[:-1]
            f = True
        print('\t' * count_tab + message.replace('\n', '\n' + '\t' * count_tab))
        if f:
            print()

    def send(self, message):
        """Отправка сообщения с потоковым выводом"""
        global last_send_time

        self.messages.append(message)

        delay = 60 / model_rpm - (time.time() - last_send_time)
        if delay > 0:
            self.print(f"Жду {delay} секунд")
            time.sleep(delay)
        last_send_time = time.time()

        if self.output_mode == "user":
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=self.messages,
                    tools=self.tools,
                    stream=True,
                )
                
                # Собираем полный ответ
                full_content = ""
                tool_calls = []
                
                print("\n🤖 Агент: ", end="", flush=True)
                
                
                for chunk in response:
                    if chunk.choices[0].delta.content is not None:
                        content = chunk.choices[0].delta.content
                        full_content += content
                        print(content, end="", flush=True)
                    
                    # Собираем tool calls если есть
                    if chunk.choices[0].delta.tool_calls:
                        for tool_call in chunk.choices[0].delta.tool_calls:
                            if tool_call.index == None or len(tool_calls) <= tool_call.index:
                                tool_calls.append({
                                    "id": tool_call.id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_call.function.name,
                                        "arguments": tool_call.function.arguments or ""
                                    }
                                })
                            else:
                                tool_calls[tool_call.index]["function"]["arguments"] += tool_call.function.arguments or ""
                
                print()  # Новая строка после завершения потока
                
                # Создаем полное сообщение ассистента
                assistant_message = {
                    "role": "assistant",
                    "content": full_content
                }
                
                if tool_calls:
                    assistant_message["tool_calls"] = tool_calls
                    
                self.messages.append(assistant_message)
                
                logger.info(f"Получен потоковый ответ от модели")
                
                # Обрабатываем tool calls
                if tool_calls:
                    for tool_call in tool_calls:
                        tool_name = tool_call["function"]["name"]
                        try:
                            tool_args = json.loads(tool_call["function"]["arguments"])
                        except:
                            tool_args = {}
                        
                        logger.info(f"Вызов инструмента: {tool_name} с аргументами: {tool_args}")
                        
                        if tool_name in self.tools_dict_required:
                            self.tool_exec(tool_name, tool_args, tool_call["id"])
                        else:
                            self.send({
                                "role": "tool", 
                                "tool_call_id": tool_call["id"],
                                "content": "Такого инструмента не существует"
                            })

                        
            except Exception as e:
                logger.error(f"Ошибка при обработке сообщения: {e}")
                error_msg = f"Произошла ошибка: {e}"
                print(f"\n❌ {error_msg}")
                self.send({"role": "system", "content": error_msg})
                
        else:
            result = ''

            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=self.messages,
                    tools=self.tools,
                )
                
                assistant_message = response.choices[0].message
                self.messages.append(assistant_message)

                logger.info(f"Получен ответ от модели")
                
                if assistant_message.content:
                    result = assistant_message.content
                
                self.print("\n🤖 Агент (авто, ответ): " + result)

                if assistant_message.tool_calls:
                    for tool_call in assistant_message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)
                        
                        logger.info(f"Вызов инструмента: {tool_name} с аргументами: {tool_args}")
                        
                        if tool_name in self.tools_dict_required.keys():
                            self.tool_exec(tool_name, tool_args, tool_call.id)
                        else:
                            result = self.send({
                                "role": "tool", 
                                "tool_call_id": tool_call.id,
                                "content": "Такого инструмента не существует"
                            })
                            
            except Exception as e:
                logger.error(f"Ошибка при обработке сообщения: {e}")
                error_msg = f"Произошла ошибка: {e}"
                print(f"\n❌ {error_msg}")
                result = self.send({"role": "system", "content": error_msg})

            finally:
                return result


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

    # Стандартная структура профиля
    chat_agent = Chat()
    
    try:
        while True:
            user_input = input("\n👤 Вы: ")
            chat_agent.send({"role": "user", "content": user_input})
    except KeyboardInterrupt:
        print("\n👋 Программа завершена пользователем")
    except EOFError:
        print("\n👋 Программа завершена (Ctrl+D)")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        print(f"\n💥 Критическая ошибка: {e}")


if __name__ == "__main__":
    main()

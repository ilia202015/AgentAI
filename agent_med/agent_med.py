import os, json, logging, ast, sys, types, readline, datetime, time, subprocess, traceback
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

gemini_keys = []
i = 0
while True:
    key_path = f"agent_med/gemini{i}.key"
    if os.path.exists(key_path):
        with open(key_path, 'r', encoding="utf8") as f:
            gemini_keys.append(f.read().strip())
        i += 1
    else:
        break

if not gemini_keys:
    raise ValueError("Не найдены файлы с ключами API Gemini (например, agent_med/gemini0.key)")

ai_key = gemini_keys[0]
current_key_index = 0

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

client = OpenAI(api_key=ai_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")

model = "gemini-2.5-pro"

model_rpm = 2

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
                    "description": "Выполняет поиск через Google Custom Search API. Возвращает результаты в формате JSON. Всегда использовать при необходимости (не обязательно чтобы пользователь попросил)",
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
                    "name": "shell",
                    "description": "Выполняет команду в системной оболочке (shell) и возвращает stdout, stderr и код возврата в формате JSON.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "Команда для выполнения."
                            },
                            "timeout": {
                                "type": "integer",
                                "description": "Максимальное время выполнения команды в секундах. По умолчанию 120.",
                                "default": 120
                            }
                        },
                        "required": ["command"]
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
            },
            {
                "type": "function",
                "function": {
                    "name": "http",
                    "description": "Загружает HTML-страницу по заданному URL, удаляет все HTML-теги (скрипты, стили, разметку) и возвращает чистый текст страницы.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "URL-адрес веб-страницы для загрузки и очистки."
                            }
                        },
                        "required": ["url"]
                    }
                }
            }
        ]

        self.chats = dict()

        self.tools_dict_required = { 
            "chat" : ["name", "message"],
            "chat_exec" : ["name", "code"],
            "python" : ["code"],
            "google_search" : ["query"],
            "shell" : ["command"],
            "user_profile" : ["data"],
            "http" : ["url"],
        }

        self.tools_dict_additional  = { 
            "chat" : [],
            "chat_exec" : [],
            "python" : [],
            "google_search" : ["num_results"],
            "shell" : ["timeout"],
            "user_profile" : [],
            "http" : [],
        }

        self.messages = [
            {"role": "system", "content": self.system_prompt},
        ]

    def chat_tool(self, name, message):
        if name not in self.chats:
            self.chats[name] = Chat(output_mode="auto", count_tab=self.count_tab + 1)
            
        self.print(f"\n⚙️ Агент (авто, запрос, чат: {name}): " + message)

        return self.chats[name].send({"role": "user", "content": message})

    def chat_exec_tool(self, name, code):
        if name not in self.chats.keys():
            self.chats[name] = Chat(output_mode="auto", count_tab=self.count_tab + 1)
        return self.chats[name].python_tool(code)

    def google_search_tool(self, query, num_results=10):
        try:
            import json
            from googleapiclient.discovery import build
            
            with open("agent_med/google.key", "r") as f:
                api_key = f.read().strip()
            
            with open("agent_med/search_engine.id", "r") as f:
                search_engine_id = f.read().strip()
            
            service = build("customsearch", "v1", developerKey=api_key)
            
            result = service.cse().list(
                q=query,
                cx=search_engine_id,
                num=min(num_results, 10)
            ).execute()

            if 'items' not in result:
                return json.dumps([], ensure_ascii=False, indent=2)

            simplified_results = []
            for item in result['items']:
                simplified_results.append({
                    'title': item.get('title'),
                    'link': item.get('link'),
                    'snippet': item.get('snippet')
                })
            
            return json.dumps(simplified_results, ensure_ascii=False, indent=2)
            
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


    def shell_tool(self, command, timeout=120):
        """
        Выполняет команду в системной оболочке и возвращает stdout, stderr и код возврата.
        """
        try:
            # Используем subprocess.run для выполнения команды
            process = subprocess.run(
                command,
                shell=True,         # Позволяет выполнять сложные команды как в терминале
                capture_output=True,# Захватывает stdout и stderr
                text=True,          # Декодирует stdout/stderr в текст
                timeout=timeout         # Таймаут в секундах для предотвращения зависаний
            )
            # Возвращаем результат в виде JSON-строки для удобства парсинга
            return json.dumps({
                "returncode": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr
            }, ensure_ascii=False, indent=2)
        except subprocess.TimeoutExpired:
            return json.dumps({
                "returncode": -1,
                "stdout": "",
                "stderr": f"Ошибка: Команда выполнялась дольше {timeout} секунд и была прервана."
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({
                "returncode": -1,
                "stdout": "",
                "stderr": f"Критическая ошибка при выполнении команды: {str(e)}"
            }, ensure_ascii=False, indent=2)

    def http_tool(self, url):
        """
        Загружает HTML-страницу по URL, очищает от лишних тегов и возвращает основной текст.
        """
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            return "Ошибка: для работы этого инструмента необходимы библиотеки requests и beautifulsoup4. Установите их с помощью: pip install requests beautifulsoup4"

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Проверка на ошибки HTTP (4xx или 5xx)
            
            soup = BeautifulSoup(response.text, 'html.parser')

            # Удаляем ненужные теги (скрипты, стили, навигацию, футеры и т.д.)
            for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                element.decompose()

            # Получаем текст и очищаем его от лишних пробелов и пустых строк
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            cleaned_text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return cleaned_text

        except requests.exceptions.RequestException as e:
            return f"Ошибка сети при запросе к {url}: {e}"
        except Exception as e:
            return f"Ошибка при обработке URL {url}: {e}"

    def validate_python_code(self, code):
        try:
            ast.parse(code)
            
            return True, "Код прошел валидацию"
        except SyntaxError as e:
            return False, f"Синтаксическая ошибка: {e}"
        except Exception as e:
            return False, f"Ошибка валидации: {e}"

    def python_tool(self, code, no_print=False):
        is_valid, message = self.validate_python_code(code)
        if not is_valid:
            logger.warning(f"Код не прошел валидацию: {message}")
            return f"Ошибка: {message}"
        
        try:
            
            self.local_env["self"] = self
            self.local_env["result"] = ''
            exec(code, globals(), self.local_env)
            
            logger.info(f"Код выполнен успешно. Результат: {self.local_env['result']}")
            return str(self.local_env["result"])
            
        except Exception as e:
            logger.error(f"Ошибка выполнения кода: {e}")
            # Форматируем полный стектрейс для детального отчета
            error_traceback = traceback.format_exc()
            return f"Ошибка выполнения:\n{error_traceback}"

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

        if name == 'python' and 'code' in tool_args:
            self.print_code(f"Запрос {name}", tool_args['code'])
        else:
            try:
                args_for_print = json.dumps(tool_args, ensure_ascii=False, indent=2)
                self.print_code(f"Запрос {name}", args_for_print)
            except Exception:
                self.print_code(f"Запрос {name}", str(tool_args))

        args_for_exec = tool_args.copy()
        for key, val in args_for_exec.items():
            if isinstance(val, str):
                args_for_exec[key] = repr(val)
        
        try:
            if self.check_tool_args(required, tool_args, tool_id):
                if name == 'python':
                    tool_result = self.python_tool(tool_args['code'])
                else:
                    required_args_str = ', '.join(str(args_for_exec[arg]) for arg in required)
                    additional_args_str = ', '.join(f"{arg}={args_for_exec[arg]}" for arg in additional if arg in args_for_exec)
                    all_args = []
                    if required_args_str: all_args.append(required_args_str)
                    if additional_args_str: all_args.append(additional_args_str)
                    call_string = f"result = self.{name}_tool({', '.join(all_args)})"
                    self.python_tool(call_string, no_print=True)
                    tool_result = self.local_env.get("result")

                self.print_code(f"Результат {name}", str(tool_result))
                
                self.send({
                    "role": "tool", 
                    "tool_call_id": tool_id, 
                    "content": str(tool_result)
                })

        except Exception as e:
            logger.error(f"Ошибка при выполнении инструмента {name}: {e}")
            error_message = f"Ошибка инструмента: {e}"
            self.print_code(f"Ошибка {name}", error_message)
            self.send({
                "role": "tool", 
                "tool_call_id": tool_id, 
                "content": error_message
            })

    def print(self, message, count_tab=-1):
        if count_tab == -1:
            count_tab = self.count_tab
        if message != '':
            if message[-1] == '\n':
                message = message[:-1]
            print('\t' * count_tab + message.replace('\n', '\n' + '\t' * count_tab))
        print()

    def print_code(self, language, code, count_tab=-1, max_code_display_lines=6):
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
                        displayed_code = '\n'.join(lines[:half_lines]) + \
                                        '\n\t...\n' + \
                                        '\n'.join(lines[-half_lines:])
                    else:
                        displayed_code = code
                    if len(displayed_code) > 100:
                        displayed_code = code[:50] + '\n\t...\n' + code[-50:]

            self.print(language + ":", count_tab=count_tab)
            self.print(displayed_code, count_tab=count_tab + 1)

    def send(self, message):
        global last_send_time, client, current_key_index

        self.messages.append(message)

        delay = 60 / model_rpm - (time.time() - last_send_time)
        if delay > 0:
            self.print(f"Жду {delay} секунд")
            time.sleep(delay)
        last_send_time = time.time()

        if self.output_mode == "user":
            while True:
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=self.messages,
                        tools=self.tools,
                        stream=True,
                    )
                    
                    full_content = ""
                    tool_calls = []
                    
                    print("\n🤖 Агент: ", end="", flush=True)
                    
                    
                    for chunk in response:
                        if chunk.choices[0].delta.content is not None:
                            content = chunk.choices[0].delta.content
                            full_content += content
                            print(content, end="", flush=True)
                        
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
                    
                    print()
                    
                    assistant_message = {
                        "role": "assistant",
                        "content": full_content
                    }
                    
                    if tool_calls:
                        assistant_message["tool_calls"] = tool_calls
                        
                    self.messages.append(assistant_message)
                    
                    logger.info(f"Получен потоковый ответ от модели")
                    
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
                    break

                        
                except Exception as e:
                    logger.error(f"Ошибка при обработке сообщения: {e}")
                    error_msg = f"Произошла ошибка: {e}"
                    print(f"\n❌ {error_msg}")
                    
                    if "Error code: 429" in str(e):
                        if "'quotaValue': '50'" in str(e):
                            last_send_time -= 60

                            current_key_index += 1
                            current_key_index %= len(gemini_keys)

                            ai_key = gemini_keys[current_key_index]
                            client = OpenAI(api_key=ai_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
                            print(f"\n🔑 Превышен лимит запросов. Переключаюсь на следующий ключ ({current_key_index + 1}/{len(gemini_keys)}).")

                        self.messages.pop()
                        self.send(message)
                    else:
                        self.send({"role": "system", "content": error_msg})
                    break
                
        else:
            result = ''
            while True:
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
                    
                    self.print("\n⚙️ Агент (авто, ответ): " + result)

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
                    break
                                
                except Exception as e:
                    logger.error(f"Ошибка при обработке сообщения: {e}")
                    
                    error_msg = f"Произошла ошибка: {e}"
                    print(f"\n❌ {error_msg}")

                    if "Error code: 429" in str(e):
                        if "'quotaValue': '50'" in str(e):
                            last_send_time -= 60
                            current_key_index += 1
                            current_key_index %= len(gemini_keys)

                            ai_key = gemini_keys[current_key_index]
                            client = OpenAI(api_key=ai_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
                            print(f"\n🔑 Превышен лимит запросов. Переключаюсь на следующий ключ ({current_key_index + 1}/{len(gemini_keys)}).")

                        self.messages.pop()
                        result = self.send(message)
                    else:
                        result = self.send({"role": "system", "content": error_msg})
                    break

                finally:
                    return result


def main():
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

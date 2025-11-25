import os, json, logging, ast, sys, types, readline, datetime, time, subprocess, traceback
from openai import OpenAI


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agent_ext/agent_ext.log')
    ]
)
logger = logging.getLogger(__name__)


class Chat:
    local_env = dict()
    result = ''
    
    def __init__(self, output_mode="user", count_tab=0):
        self.agent_dir = "agent_ext"
        self.output_mode = output_mode
        self.count_tab = count_tab
        self.chats = {}
        self.last_send_time = 0
        self.model = "gemini-2.5-pro"
        self.model_rpm = 2

        self._load_config()
        self.client = OpenAI(api_key=self.ai_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
        
        system_prompt_parts = [
            self.prompts['system'], "Код файла agent.py:", self.self_code,
            "saved_code_changes.py (дополнительные изменения):", self.saved_code,
            f"Режим вывода: {self.output_mode}", "Информация о пользователе (user_profile.json):", self.user_profile
        ]
        self.system_prompt = "\n".join(system_prompt_parts)
        self.messages = [{"role": "system", "content": self.system_prompt}]

        self._initialize_tools()
        self._apply_saved_changes()

    def _load_config(self):
        self.gemini_keys = []
        i = 0
        while True:
            key_path = f"{self.agent_dir}/keys/gemini{i}.key"
            if os.path.exists(key_path):
                with open(key_path, 'r', encoding="utf8") as f: 
                    self.gemini_keys.append(f.read().strip())
                i += 1
            else: break
        if not self.gemini_keys: raise ValueError(f"Не найдены файлы с ключами API Gemini.")

        key_num_path = f"{self.agent_dir}/keys/gemini.key_num"
        if not os.path.exists(key_num_path):
            with open(key_num_path, 'w', encoding="utf8") as f: 
                f.write('0')
        with open(key_num_path, 'r', encoding="utf8") as f: 
            self.current_key_index = int(f.read())
        self.ai_key = self.gemini_keys[self.current_key_index]

        self.prompts = {}
        prompt_names = ["system", "python", "chat", "chat_exec", "user_profile", "save_code_changes", "http", "shell", "google_search"]
        for name in prompt_names:
            try:
                with open(f"{self.agent_dir}/prompts/{name}", 'r', encoding="utf8") as f: 
                    self.prompts[name] = f.read()
            except FileNotFoundError: self.prompts[name] = f"Prompt '{name}' not found."

        with open(f"{self.agent_dir}/user_profile.json", 'r', encoding="utf8") as f: 
            self.user_profile = f.read()
        with open(__file__, 'r', encoding="utf8") as f: 
            self.self_code = f.read()
        
        saved_changes_path = f"{self.agent_dir}/saved_code_changes.py"
        if not os.path.exists(saved_changes_path):
            with open(saved_changes_path, 'w', encoding="utf8") as f: 
                f.write('# Этот файл хранит сохраненные изменения кода агента.\n\n')
        with open(saved_changes_path, 'r', encoding="utf8") as f: 
            self.saved_code = f.read()

        with open("agent_ext/keys/google.key", "r") as f:
            self.google_search_key = f.read().strip()
        
        with open("agent_ext/keys/search_engine.id", "r") as f:
            self.search_engine_id = f.read().strip()
            

    def _initialize_tools(self):
        with open(f"{self.agent_dir}/tools.json", 'r', encoding="utf8") as f: 
            self.tools = json.load(f)["tools"]
        
        for tool_num in range(len(self.tools)):
            self.tools[tool_num]["function"]["description"] = self.prompts[self.tools[tool_num]["function"]["name"]]

        self.tools_dict_required = { "chat": ["name", "message"], "chat_exec": ["name", "code"], "python": ["code"], "google_search": ["query"], "shell": ["command"], "user_profile": ["data"], "http": ["url"], "save_code_changes": ["code"]}
        self.tools_dict_additional = { "google_search": ["num_results"], "shell": ["timeout"]}

    def _apply_saved_changes(self):
        try:
            if self.saved_code.strip():
                print("⚙️ Обнаружены сохраненные изменения. Применяю...")
                result = self.python_tool(self.saved_code, no_print=True)
                if result and "Ошибка" in str(result): print(f"❌ Ошибка: {result}")
                else: print("✅ Изменения успешно применены.")
        except Exception as e:
            print(f"❌ Критическая ошибка при загрузке изменений: {e}")

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
            
            service = build("customsearch", "v1", developerKey=self.google_search_key)
            
            result = service.cse().list(
                q=query,
                cx=self.search_engine_id,
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
            profile_file = "agent_ext/user_profile.json"
            
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
            return f"Ошибка выполнения:\n\n{error_traceback}"
        
    def save_code_changes_tool(self, code):
        """
        Сохраняет протестированные изменения собственного кода в файл для их применения при следующем запуске.
        Используй только для изменений, которые могут пригодиться позже или если пользователь попросил сохранить.
        """
        try:
            is_valid, message = self.validate_python_code(code)
            if not is_valid:
                return f"Ошибка валидации: {message}. Изменения не сохранены."

            file_path = "agent_ext/saved_code_changes.py"
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n# Saved on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(code)
                f.write("\n" + "#" * 80 + "\n")

            return "Изменения в коде успешно сохранены. Они будут автоматически применены при следующем запуске агента."
        except Exception as e:
            return f"Критическая ошибка при сохранении изменений: {e}"
    
    def check_tool_args(self, args, tool_args, tool_id):
        for arg in args:
            if arg not in tool_args:
                self.messages.append({
                    "role": "tool", 
                    "tool_call_id": tool_id, 
                    "content": f"Ошибка: отсутствует параметр {arg}"
                })
                return False
        return True

    def tool_exec(self, name, tool_args, tool_id):
        required = self.tools_dict_required[name] if name in self.tools_dict_required else []
        additional = self.tools_dict_additional[name] if name in self.tools_dict_additional else []

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
                
                return {
                    "role": "tool", 
                    "tool_call_id": tool_id, 
                    "content": str(tool_result)
                }

        except Exception as e:
            logger.error(f"Ошибка при выполнении инструмента {name}: {e}")
            error_message = f"Ошибка инструмента: {e}"
            self.print_code(f"Ошибка {name}", error_message)
            return {
                "role": "tool", 
                "tool_call_id": tool_id, 
                "content": error_message
            }

    def print(self, message, count_tab=-1, **kwargs):
        if count_tab == -1:
            count_tab = self.count_tab
        if message != '':
            print('\t' * count_tab + message.replace('\n', '\n' + '\t' * count_tab), **kwargs)

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
                    
                    if len(displayed_code) > 500:
                        displayed_code = code[:250] + '\n\t...\n' + code[-250:]

            self.print("\n\n" + language + ":\n", count_tab=count_tab)
            self.print(displayed_code + '\n', count_tab=count_tab + 1)

    
    def send(self, message):
        if isinstance(message, dict):
            self.messages.append(message)
        else:
            self.messages.extend(message)

        return self._process_request()

    def _process_request(self):
        """Основной цикл обработки запроса к AI.
        Обрабатывает ошибки сети и лимитов API, автоматически переключая ключи."""
        while True:
            try:
                delay = 60 / self.model_rpm - (time.time() - self.last_send_time)
                if delay > 0:
                    self.print(f"Жду {delay:.2f} секунд")
                    time.sleep(delay)
                self.last_send_time = time.time()

                stream = self.output_mode == "user"
                response_generator = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    tools=self.tools,
                    stream=stream,
                )
                return self._handle_response(response_generator, stream)

            except Exception as e:
                logger.error(f"Ошибка при обработке сообщения: {e}")
                error_msg = f"Произошла ошибка: {e}\n\n{traceback.format_exc()}"
                self.print(f"\n❌ {error_msg}")

                if "Error code: 429" in str(e):
                    if "'quotaValue': '50'" in str(e):
                        self.last_send_time -= 60  # Даем шанс на быстрый повторный запрос
                        self._switch_api_key()
                        self.messages.pop() # Убираем сообщение, вызвавшее ошибку, чтобы попробовать снова
                    continue # Повторяем запрос с новым ключом
                else:
                    # Для других ошибок добавляем системное сообщение и выходим
                    if self.output_mode != "user":
                        self.send({"role": "system", "content": error_msg})
                    return f"Критическая ошибка: {error_msg}" # Возвращаем ошибку в режиме auto

    def _switch_api_key(self):
        """Переключает на следующий доступный API ключ Gemini."""
        self.current_key_index = (self.current_key_index + 1) % len(self.gemini_keys)
        with open(f"{self.agent_dir}/keys/gemini.key_num", 'w', encoding="utf8") as f:
            f.write(str(self.current_key_index))
        
        self.ai_key = self.gemini_keys[self.current_key_index]
        self.client = OpenAI(api_key=self.ai_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
        self.print(f"🔑 Превышен лимит запросов. Переключаюсь на следующий ключ ({self.current_key_index + 1}/{len(self.gemini_keys)}).")

    def _handle_response(self, response, stream):
        """Определяет, как обрабатывать ответ в зависимости от режима (stream/auto)."""
        if stream:
            return self._handle_stream_response(response)
        else:
            return self._handle_auto_mode_response(response)
            
    def _handle_stream_response(self, response_stream):
        """Обрабатывает потоковый ответ от модели для режима 'user'."""
        full_content = ""
        tool_calls = []
        
        self.print("🤖 Агент: ", end="", flush=True)

        for chunk in response_stream:
            content_delta = chunk.choices[0].delta.content
            tool_calls_delta = chunk.choices[0].delta.tool_calls

            if content_delta:
                full_content += content_delta
                self.print(content_delta, end="", flush=True, count_tab=0) # Выводим без отступов
            
            if tool_calls_delta:
                for tool_call in tool_calls_delta:
                    # Если новый tool_call, добавляем его в список
                    if tool_call.index is None or tool_call.index >= len(tool_calls):
                         tool_calls.append({
                             "id": tool_call.id,
                             "type": "function",
                             "function": {"name": tool_call.function.name, "arguments": tool_call.function.arguments or ""}
                         })
                    # Если продолжение существующего, дописываем аргументы
                    else:
                        tool_calls[tool_call.index]["function"]["arguments"] += tool_call.function.arguments or ""
        
        self.print("") # Перевод строки после ответа
        
        assistant_message = {"role": "assistant", "content": full_content}
        if tool_calls:
            assistant_message["tool_calls"] = tool_calls
        
        self.messages.append(assistant_message)
        logger.info("Получен потоковый ответ от модели.")
        
        if tool_calls:
            self._execute_tool_calls(tool_calls)
        
        return "Обработка завершена."

    def _handle_auto_mode_response(self, response):
        """Обрабатывает стандартный ответ от модели для режима 'auto'."""
        assistant_message = response.choices[0].message
        self.messages.append(assistant_message)
        logger.info("Получен ответ от модели в режиме auto.")

        result = assistant_message.content or ""
        self.print("⚙️ Агент (авто, ответ): " + result)

        if assistant_message.tool_calls:
            tool_calls = []
            for tool in assistant_message.tool_calls:
                tool_calls.append({
                    "function" : {
                        "name" : tool.function.name,
                        "arguments" : tool.function.arguments
                    },
                    "id" : tool.id
                    })
            self._execute_tool_calls(tool_calls)

        return result

    def _execute_tool_calls(self, tool_calls):
        """Выполняет вызовы инструментов, полученные от модели, и отправляет результаты обратно в модель."""
        tool_responses = []
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            
            try:
                tool_args_str = tool_call["function"]["arguments"]
                tool_args = json.loads(tool_args_str)
            except json.JSONDecodeError:
                tool_args = {}
            
            logger.info(f"Вызов инструмента: {tool_name} с аргументами: {tool_args}")
            
            tool_call_id = tool_call["id"]
            
            if tool_name in self.tools_dict_required:
                response = self.tool_exec(tool_name, tool_args, tool_call_id)
                tool_responses.append(response)
            else:
                tool_responses.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": "Такого инструмента не существует"
                })

        if tool_responses:
             self.send(tool_responses)

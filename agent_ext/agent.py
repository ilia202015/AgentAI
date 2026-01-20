import os, json, base64, ast, sys, types, datetime, time, subprocess, traceback, platform
from google import genai
from google.genai import types

class Chat:
    local_env = dict()
    result = ''

    @staticmethod
    def _get_full_console_info():
        report = []
        try:
            sys_name = platform.system()
            sys_release = platform.release()
            if sys_name == 'Darwin':
                sys_name = 'macOS (Darwin)'
            report.append(f"Операционная система: {sys_name} {sys_release}")
        except Exception as e:
            report.append(f"Операционная система: Не удалось определить ({e})")

        try:
            shell_info = "Неизвестно"
            env = os.environ
            if platform.system() == "Windows":
                if "PSModulePath" in env:
                    shell_info = "PowerShell"
                else:
                    shell_info = env.get("COMSPEC", "cmd.exe")
            else:
                shell_path = env.get("SHELL", None)
                if shell_path:
                    shell_info = os.path.basename(shell_path)
                else:
                    shell_info = "Не задана переменная $SHELL"
            report.append(f"Оболочка (Shell): {shell_info}")
        except Exception as e:
            report.append(f"Оболочка (Shell): Ошибка при определении ({e})")

        try:
            term_env = "Стандартный терминал"
            env = os.environ
            if "PYCHARM_HOSTED" in env or "XPC_SERVICE_NAME" in env and "pycharm" in env["XPC_SERVICE_NAME"].lower():
                term_env = "PyCharm Console"
            elif env.get("TERM_PROGRAM") == "vscode":
                term_env = "VS Code Terminal"
            elif "WT_SESSION" in env:
                term_env = "Windows Terminal"
            elif env.get("TERM_PROGRAM") == "Apple_Terminal":
                term_env = "macOS Terminal"
            elif env.get("TERM_PROGRAM") == "iTerm.app":
                term_env = "iTerm2"
            elif "TMUX" in env:
                term_env = "Tmux Session"
            report.append(f"Среда запуска (IDE/Terminal): {term_env}")
        except Exception as e:
            report.append(f"Среда запуска: Ошибка при проверке ({e})")
        return "\n".join(report)

    def __init__(self, output_mode="user", count_tab=0, print_to_console=False):
        self.agent_dir = "agent_ext"
        self.output_mode = output_mode
        self.count_tab = count_tab
        self.print_to_console = print_to_console
        self.chats = {}
        self.last_send_time = 0
        
        # free
        #self.model, self.model_rpm = "gemini-2.5-pro", 2
        #self.model, self.model_rpm = "gemini-2.5-flash", 10

        # tier 1
        self.model, self.model_rpm = "gemini-3-pro-preview", 25
        #self.model, self.model_rpm = "gemini-3-flash-preview", 1000
        #self.model, self.model_rpm = "gemini-2.5-pro", 150

        self._load_config()
        self.client = genai.Client(api_key=self.ai_key)
        
        system_prompt_parts = [
            self.prompts['system'], 
            "Код файла agent.py:", self.self_code,
            "saved_code_changes.py (дополнительные изменения):", self.saved_code,
            f"Режим вывода: {self.output_mode}", 
            "Информация о пользователе (user_profile.json):", self.user_profile,
            "Информация о окружении:", self._get_full_console_info(),
            f"Ты работаешь на базе модели {self.model}, если ты о ней не знаешь, это не опечатка, просто информации о неё небыло в твоей обучающей выборке"
        ]
        self.system_prompt = "\n".join(system_prompt_parts)
        
        # История сообщений (Native Gemini Format: types.Content)
        self.messages = [] 

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
            else:
                break
        if not self.gemini_keys:
            raise ValueError(f"Не найдены файлы с ключами API Gemini.")

        key_num_path = f"{self.agent_dir}/keys/gemini.key_num"
        if not os.path.exists(key_num_path):
            with open(key_num_path, 'w', encoding="utf8") as f:
                f.write('0')
        with open(key_num_path, 'r', encoding="utf8") as f: 
            self.current_key_index = int(f.read())
        self.ai_key = self.gemini_keys[self.current_key_index]

        self.prompts = {}
        prompt_names = ["system", "python", "chat", "chat_exec", "user_profile", "save_code_changes", "http", "shell", "google_search", "python_str"]
        for name in prompt_names:
            try:
                with open(f"{self.agent_dir}/prompts/{name}", 'r', encoding="utf8") as f:
                    self.prompts[name] = f.read()
            except FileNotFoundError:
                self.prompts[name] = f"Prompt '{name}' not found."

        with open(f"{self.agent_dir}/user_profile.json", 'r', encoding="utf8") as f:
            self.user_profile = f.read()
        
        self_code_path = "agent_ext/agent.py" if os.path.exists("agent_ext/agent.py") else __file__
        with open(self_code_path, 'r', encoding="utf8") as f:
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

    def _get_tools_dicts(self):
        tools_dict_required = {}
        tools_dict_additional = {}
        for tool in self.tools:
            tools_dict_required[tool["function"]["name"]] = tool["function"]["parameters"]["required"]
            for parameter in tool["function"]["parameters"].keys():
                if parameter not in tool["function"]["parameters"]["required"]:
                    if tool["function"]["name"] not in tools_dict_additional:
                        tools_dict_additional[tool["function"]["name"]] = []
                    tools_dict_additional[tool["function"]["name"]].append(parameter)
        return tools_dict_required, tools_dict_additional

    def _initialize_tools(self):
        with open(f"{self.agent_dir}/tools.json", 'r', encoding="utf8") as f: 
            self.tools = json.load(f)["tools"]
        for tool in self.tools:
            tool["function"]["description"] = self.prompts.get(tool["function"]["name"], tool["function"]["description"])

    def _apply_saved_changes(self):
        try:
            if self.saved_code.strip():
                print("⚙️ Обнаружены сохраненные изменения. Применяю...")
                result = self.python_tool(self.saved_code, no_print=True)
                if result and "Ошибка" in str(result):
                    print(f"❌ Ошибка: {result}")
                else:
                    print("✅ Изменения успешно применены.")
        except Exception as e:
            print(f"❌ Критическая ошибка при загрузке изменений: {e}")

    # === TOOLS IMPLEMENTATION ===

    def chat_tool(self, name, message):
        if name not in self.chats:
            self.chats[name] = Chat(output_mode="auto", count_tab=self.count_tab + 1)
        self.print(f"\n⚙️ Агент (авто, запрос, чат: {name}): " + message)
        # Отправляем сообщение как user
        return self.chats[name].send(types.Content(role="user", parts=[types.Part(text=message)]))

    def chat_exec_tool(self, name, code):
        if name not in self.chats.keys():
            self.chats[name] = Chat(output_mode="auto", count_tab=self.count_tab + 1)
        return self.chats[name].python_tool(code)

    def google_search_tool(self, query, num_results=10):
        try:
            import json
            from googleapiclient.discovery import build
            service = build("customsearch", "v1", developerKey=self.google_search_key)
            result = service.cse().list(q=query, cx=self.search_engine_id, num=min(num_results, 10)).execute()
            if 'items' not in result:
                return json.dumps([], ensure_ascii=False, indent=2)
            simplified_results = []
            for item in result['items']:
                simplified_results.append({'title': item.get('title'), 'link': item.get('link'), 'snippet': item.get('snippet')})
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
                    user_profile[key] = {"data" : val, "time" : datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            with open(profile_file, 'w', encoding="utf8") as f:
                json.dump(user_profile, f, ensure_ascii=False, indent=2)
            return "Профиль обновлён успешно"
        except Exception as e:
            return f"Ошибка: {e}"

    def shell_tool(self, command, timeout=120):
        try:
            process = subprocess.run(command, encoding='utf-8', shell=True, capture_output=True, text=True, timeout=timeout)
            return json.dumps({"returncode": process.returncode, "stdout": process.stdout, "stderr": process.stderr}, ensure_ascii=False, indent=2)
        except subprocess.TimeoutExpired:
            return json.dumps({"returncode": -1, "stdout": "", "stderr": f"Ошибка: Команда выполнялась дольше {timeout} секунд и была прервана."}, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"returncode": -1, "stdout": "", "stderr": f"Критическая ошибка при выполнении команды: {str(e)}"}, ensure_ascii=False, indent=2)

    def http_tool(self, url):
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            return "Ошибка: для работы этого инструмента необходимы библиотеки requests и beautifulsoup4."
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                element.decompose()
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            return '\n'.join(chunk for chunk in chunks if chunk)
        except Exception as e:
            return f"Ошибка при обработке URL {url}: {e}"

    def python_str_tool(self, text):
        return repr(text)

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
            return f"Ошибка: {message}"
        try:
            self.local_env["self"] = self
            self.local_env["result"] = ''
            exec(code, globals(), self.local_env)
            return str(self.local_env["result"])
        except Exception as e:
            return f"Ошибка выполнения:\n\n{traceback.format_exc()}"
        
    def save_code_changes_tool(self, code):
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
    
    def check_tool_args(self, args, tool_args):
        for arg in args:
            if arg not in tool_args:
                return False
        return True

    def tool_exec(self, name, tool_args):
        tools_dict_required, tools_dict_additional = self._get_tools_dicts()
        required = tools_dict_required.get(name, [])
        additional = tools_dict_additional.get(name, [])

        # Логирование
        if name == 'python' and 'code' in tool_args:
            self.print_code(f"Запрос {name}", tool_args['code'])
        else:
            try:
                self.print_code(f"Запрос {name}", json.dumps(tool_args, ensure_ascii=False, indent=2))
            except:
                self.print_code(f"Запрос {name}", str(tool_args))

        args_for_exec = tool_args.copy()
        for key, val in args_for_exec.items():
            if isinstance(val, str):
                args_for_exec[key] = repr(val)
        
        try:
            if self.check_tool_args(required, tool_args):
                if name == 'python':
                    tool_result = self.python_tool(tool_args['code'])
                else:
                    required_args_str = ', '.join(str(args_for_exec[arg]) for arg in required)
                    additional_args_str = ', '.join(f"{arg}={args_for_exec[arg]}" for arg in additional if arg in args_for_exec)
                    all_args = [arg for arg in [required_args_str, additional_args_str] if arg]
                    call_string = f"result = self.{name}_tool({', '.join(all_args)})"
                    self.python_tool(call_string, no_print=True)
                    tool_result = self.local_env.get("result")

                self.print_code(f"Результат {name}", str(tool_result))
                return tool_result 

        except Exception as e:
            error_message = f"Ошибка инструмента: {e}"
            self.print_code(f"Ошибка {name}", error_message)
            return error_message
            
        return "Ошибка: неверные аргументы или инструмент не найден"

    # === OUTPUT & LOGGING ===

    def print(self, message, count_tab=-1, **kwargs):
        if count_tab == -1:
            count_tab = self.count_tab
        if message != '':
            print('\t' * count_tab + message.replace('\n', '\n' + '\t' * count_tab), **kwargs)

    print_thought = print

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
                        displayed_code = '\n'.join(lines[:half_lines]) + '\n\t...\n' + '\n'.join(lines[-half_lines:])
                    else:
                        displayed_code = code
                    if len(displayed_code) > 500:
                        displayed_code = code[:250] + '\n\t...\n' + code[-250:]
            self.print("\n\n" + language + ":\n", count_tab=count_tab)
            self.print(displayed_code + '\n', count_tab=count_tab + 1)

    # === CORE LOGIC ===

    def send(self, messages):
        # В Native режиме принимаем типы types.Content или список parts
        if not isinstance(messages, list):
            messages = [messages]

        for msg in messages:
            # Если это словарь или простой текст, пробуем преобразовать в types.Content
            if isinstance(msg, dict):
                parts = []
                # Текст
                if "content" in msg and msg["content"]:
                    parts.append(types.Part(text=msg["content"]))
                
                # Картинки
                if "images" in msg and isinstance(msg["images"], list):
                    for img_data in msg["images"]:
                        try:
                            # Ожидаем format: "data:image/png;base64,..."
                            if "base64," in img_data:
                                header, b64_str = img_data.split("base64,", 1)
                                mime_type = header.split(":")[1].split(";")[0]
                            else:
                                b64_str = img_data
                                mime_type = "image/jpeg"
                            
                            parts.append(types.Part.from_bytes(data=base64.b64decode(b64_str), mime_type=mime_type))
                        except Exception as e:
                            print(f"Ошибка декодирования изображения: {e}")
                
                # Если части созданы - добавляем
                if parts:
                    self.messages.append(types.Content(role=msg["role"], parts=parts))
            
            elif isinstance(msg, str):
                 self.messages.append(types.Content(role="user", parts=[types.Part(text=msg)]))
            else:
                 # Предполагаем types.Content
                 self.messages.append(msg)
        
        return self._process_request()

    def _process_request(self):
        while True:
            try:
                # Rate limiter
                delay = 60 / self.model_rpm - (time.time() - self.last_send_time)
                if delay > 0:
                    self.print(f"Жду {delay:.2f} секунд")
                    time.sleep(delay)
                self.last_send_time = time.time()

                if self.print_to_console:
                    prefix = "🤖 Агент: " if self.output_mode == "user" else "⚙️ Агент (авто, ответ): "
                    self.print(prefix, end="", flush=True)

                tools_gemini = []
                for tool in self.tools:
                    tools_gemini.append(types.Tool(function_declarations=[tool["function"]]))

                config = types.GenerateContentConfig(
                    tools=tools_gemini,
                    system_instruction=self.system_prompt,
                    thinking_config=types.ThinkingConfig(include_thoughts=True),
                )

                stream = self.client.models.generate_content_stream(
                    model=self.model,
                    contents=self.messages,
                    config=config,
                )

                return self._handle_stream(stream)

            except Exception as e:
                error_msg = f"Произошла ошибка API: {e}\n\n{traceback.format_exc()}"
                self.print(f"\n❌ {error_msg}")

                if "429" in str(e) or "Resource has been exhausted" in str(e):
                    self.last_send_time -= 60
                    self._switch_api_key()
                    continue
                else:
                    return f"Критическая ошибка: {error_msg}"

    def _handle_stream(self, stream):
        response_parts = []
        tool_calls_buffer = []
        
        try:
            for chunk in stream:
                if not chunk.candidates or not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
                    continue
                
                for part in chunk.candidates[0].content.parts:
                    response_parts.append(part)
                    
                    if part.text:
                        # FIX: Безопасный доступ к thought
                        is_thought = getattr(part, 'thought', False)
                        if is_thought:
                            if self.print_to_console:
                                self.print("Мысль:", end='\t\t\t')
                            self.print_thought(part.text, flush=True, end='')
                        else:
                            self.print(part.text, flush=True, end='')
                    
                    if part.function_call:
                        tool_calls_buffer.append(part.function_call)

            self.print("")
            
            self.messages.append(types.Content(role="model", parts=response_parts))

            if tool_calls_buffer:
                return self._execute_tool_calls(tool_calls_buffer)

            return "" 

        except Exception as e:
            e_trace = traceback.format_exc()
            self.print(f"Ошибка обработки стрима: {e}\n{e_trace}")
            return f"Ошибка обработки стрима: {e}"

    def _execute_tool_calls(self, tool_calls):
        # Gemini Protocol: Model -> User (FunctionResponse) -> Model
        
        response_parts = []
        
        for fc in tool_calls:
            name = fc.name
            args = fc.args
            
            # Приводим аргументы к dict
            if not isinstance(args, dict):
                 try:
                     args = json.loads(args)
                 except:
                     args = {}

            # Выполнение
            result_str = self.tool_exec(name, args)

            # Формируем ответ
            response_parts.append(types.Part(
                function_response=types.FunctionResponse(
                    name=name,
                    response={"result": result_str} 
                )
            ))
        
        # Добавляем ответы инструментов в историю (от имени user)
        self.messages.append(types.Content(role="user", parts=response_parts))

        # Продолжаем диалог
        return self._process_request()

    def _switch_api_key(self):
        self.current_key_index = (self.current_key_index + 1) % len(self.gemini_keys)
        with open(f"{self.agent_dir}/keys/gemini.key_num", 'w', encoding="utf8") as f:
            f.write(str(self.current_key_index))
        self.ai_key = self.gemini_keys[self.current_key_index]
        self.client = genai.Client(api_key=self.ai_key)
        self.print(f"🔑 Превышен лимит запросов. Переключаюсь на следующий ключ ({self.current_key_index + 1}/{len(self.gemini_keys)}).")


def main():
    print("🚀 AI-агент запущен (Gemini Native Mode). Введите ваш запрос.")
    chat_agent = Chat(print_to_console=True)
    try:
        while True:
            user_input = input("\n👤 Вы: ")
            chat_agent.send(user_input)
    except KeyboardInterrupt:
        print("\n👋 Программа завершена пользователем")
    except EOFError:
        print("\n👋 Программа завершена (Ctrl+D)")
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")

if __name__ == "__main__":
    main()

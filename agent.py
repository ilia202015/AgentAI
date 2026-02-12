import os, re, json, base64, ast, sys, types, datetime, time, subprocess, traceback, platform
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
        self.agent_dir = "."
        self.output_mode = output_mode
        self.count_tab = count_tab
        self.print_to_console = print_to_console
        self.chats = {}
        self.last_send_time = 0
        self.active_preset_id = "default"
        self.final_prompt = ""
        self.blocked_tools = []
        self.settings_tools = {}
        
        self.models = [ #(name, rpm)
            ("gemini-3-pro-preview", 25),
            ("gemini-3-flash-preview", 1000)
        ]
        self.model, self.model_rpm = self.models[1]

        self._load_config()
        self.client = genai.Client(api_key=self.ai_key)
        
        system_prompt_parts = [
            "Код файла agent.py:", self.self_code,
            f"Режим вывода: {self.output_mode}", 
            "Информация о пользователе (user_profile.json):", self.user_profile,
            "Информация о окружении:", self._get_full_console_info(),
            f"Ты работаешь на базе модели {self.model}, если ты о ней не знаешь, это не опечатка, просто информации о ней небыло в твоей обучающей выборке",
            "\n\n\nЭто были исходники проэкта и системная информация, далее будут инструкции\n",
            self.prompts['system'], 
        ]
        self.system_prompt = "\n".join(system_prompt_parts)
        
        # История сообщений (Native Gemini Format: types.Content)
        self.messages = [] 

        self._initialize_tools()

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
        prompt_names = ["system", "python", "chat", "user_profile", "http", "shell", "google_search", "python_str"]
        for name in prompt_names:
            try:
                with open(f"{self.agent_dir}/prompts/{name}", 'r', encoding="utf8") as f:
                    self.prompts[name] = f.read()
            except FileNotFoundError:
                self.prompts[name] = f"Prompt '{name}' not found."

                
        profile_path = f"{self.agent_dir}/user_profile.json"
        if not os.path.exists(profile_path):
            with open(profile_path, 'w', encoding="utf-8") as f:
                json.dump({}, f)
        with open(profile_path, 'r', encoding="utf8") as f:
            self.user_profile = f.read()
        self_code_path = "agent.py" if os.path.exists("agent.py") else __file__
        with open(self_code_path, 'r', encoding="utf8") as f:
            self.self_code = f.read()

        with open("keys/google.key", "r") as f:
            self.google_search_key = f.read().strip()
        with open("keys/search_engine.id", "r") as f:
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

    def __getstate__(self):
        state = self.__dict__.copy()
        # Удаляем несериализуемые объекты
        # client: содержит локи и сетевые соединения
        if 'client' in state:
            del state['client']
        
        # local_env оставляем (по требованию), 
        # но ответственность за его содержимое лежит на пользователе.
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        try:
            from google import genai
            if hasattr(self, 'ai_key') and self.ai_key:
                 self.client = genai.Client(api_key=self.ai_key)
            elif hasattr(self, '_load_config'):
                 self._load_config()
                 if hasattr(self, 'ai_key'):
                    self.client = genai.Client(api_key=self.ai_key)
        except Exception as e:
            print(f"Error restoring Chat client: {e}")

    # === TOOLS IMPLEMENTATION ===

    def chat_tool(self, name, message):
        if name not in self.chats:
            self.chats[name] = Chat(output_mode="auto", count_tab=self.count_tab + 1)
        self.print(f"\n⚙️ Агент (авто, запрос, чат: {name}): " + message)
        # Отправляем сообщение как user
        return self.chats[name].send(types.Content(role="user", parts=[types.Part(text=message)]))

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
            profile_file = "user_profile.json"
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
            import subprocess, json, os
            cf = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            process = subprocess.Popen(
                command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=cf
            )
            
            def decode_bytes(data):
                if not data: return ""
                for enc in ['utf-8', 'cp866', 'cp1251']:
                    try:
                        return data.decode(enc)
                    except (UnicodeDecodeError, AttributeError):
                        continue
                return data.decode('utf-8', errors='replace')

            try:
                stdout_bytes, stderr_bytes = process.communicate(timeout=timeout)
                stdout = decode_bytes(stdout_bytes)
                stderr = decode_bytes(stderr_bytes)
                return json.dumps({"returncode": process.returncode, "stdout": stdout, "stderr": stderr}, ensure_ascii=False, indent=2)
            except subprocess.TimeoutExpired:
                if os.name == 'nt':
                    subprocess.run(f'taskkill /F /T /PID {process.pid}', capture_output=True, shell=True)
                else:
                    import signal
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except:
                        process.kill()
                return json.dumps({"returncode": -1, "stdout": "", "stderr": f"Ошибка: Команда выполнялась дольше {timeout} секунд и была ПРИНУДИТЕЛЬНО прервана."}, ensure_ascii=False, indent=2)
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

    def sandbox_tool(self, action):
        import os, subprocess, sys, shutil, socket, re, json, fnmatch, time
        
        sandbox_dir = "sandbox"
        log_file = "sandbox_agent.log"
        full_log_path = os.path.join(sandbox_dir, log_file)
        
        if 'sandbox_state' not in self.local_env:
            self.local_env['sandbox_state'] = {'process': None, 'port': None, 'pid': None}
        
        state = self.local_env['sandbox_state']
        
        if action == "create":
            if state['process'] and state['process'].poll() is None:
                state['process'].terminate()
                state['process'].wait()
            
            if os.path.exists(sandbox_dir):
                try: shutil.rmtree(sandbox_dir)
                except: subprocess.run(f"powershell -Command \"Remove-Item -Path '{sandbox_dir}' -Recurse -Force\"", shell=True)
            
            os.makedirs(sandbox_dir, exist_ok=True)
            
            exclude_patterns = {
                'temp', 'chats', 'venv', '.venv', 'env', 
                '__pycache__', '.pytest_cache', '.git', 
                '*.log', 'final_prompts.json', 'user_profile.json',
                'sandbox'
            }
            
            if os.path.exists(".gitignore"):
                try:
                    with open(".gitignore", "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                pattern = line.rstrip('/').replace("\\", "/")
                                exclude_patterns.add(pattern)
                except: pass
                
            must_include_patterns = {
                'plugin_config.json', 
                'gemini*.key', 'google.key', 'search_engine.id',
                'keys/gemini*.key', 'keys/google.key', 'keys/search_engine.id',
                'keys/gemini.key_num'
            }

            def should_exclude(name, rel_path):
                for p in must_include_patterns:
                    if fnmatch.fnmatch(name, p) or fnmatch.fnmatch(rel_path, p):
                        return False
                for p in exclude_patterns:
                    if fnmatch.fnmatch(name, p) or fnmatch.fnmatch(rel_path, p):
                        return True
                    if p.endswith('/') and (fnmatch.fnmatch(name + '/', p) or fnmatch.fnmatch(rel_path + '/', p)):
                        return True
                return False

            def copy_recursive(src_root, dst_root, current_rel=""):
                for item in os.listdir(src_root):
                    item_rel = os.path.join(current_rel, item).replace("\\", "/")
                    if should_exclude(item, item_rel):
                        continue
                    
                    src_item = os.path.join(src_root, item)
                    dst_item = os.path.join(dst_root, item)
                    
                    if os.path.isdir(src_item):
                        os.makedirs(dst_item, exist_ok=True)
                        copy_recursive(src_item, dst_item, item_rel)
                    else:
                        shutil.copy2(src_item, dst_item)

            try:
                copy_recursive(".", sandbox_dir)
                prompts_path = os.path.join(sandbox_dir, "final_prompts.json")
                if not os.path.exists(prompts_path):
                    default_p = "plugins/web_interface/default_prompts.json"
                    if os.path.exists(default_p):
                        shutil.copy2(default_p, prompts_path)
                return "Песочница создана успешно."
            except Exception as e:
                return f"Ошибка при создании: {str(e)}"

        elif action == "start":
            if not os.path.exists(sandbox_dir): self.sandbox_tool("create")
            if state['process'] and state['process'].poll() is None: 
                self.sandbox_tool("stop")
            port_to_try = 8080
            found_port = None
            while port_to_try < 8095:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    if s.connect_ex(('127.0.0.1', port_to_try)) != 0:
                        found_port = port_to_try
                        break
                port_to_try += 1
            if not found_port: 
                return "Нет свободных портов."
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            proc = subprocess.Popen([sys.executable, 'start.py'], cwd=sandbox_dir, stdout=open(os.path.join(sandbox_dir, log_file), 'w', encoding='utf-8'), stderr=subprocess.STDOUT, env=env)
            state['process'] = proc
            state['pid'] = proc.pid
            actual_port = "Неизвестен"
            start_time = time.time()
            while time.time() - start_time < 20:
                if os.path.exists(full_log_path):
                    with open(full_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        match = re.search(r"http://127.0.0.1:(\d+)", content)
                        if match:
                            actual_port = match.group(1)
                            break
                time.sleep(1)
            return self.sandbox_tool("info")

        elif action == "info":
            status = "Остановлен"
            pid = state.get('pid')
            if state['process']:
                poll = state['process'].poll()
                if poll is None: status = "Работает"
                else: status = f"Завершен ({poll})"
            actual_port = "Неизвестен"
            logs = ""
            if os.path.exists(full_log_path):
                with open(full_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    logs_list = content.splitlines()
                    logs = "\n".join(logs_list[-7:])
                    match = re.search(r"http://127.0.0.1:(\d+)", content)
                    if match: actual_port = match.group(1)
            return json.dumps({"status": status, "pid": pid, "port": actual_port, "logs": logs}, ensure_ascii=False)

        elif action == "stop":
            if state['process'] and state['process'].poll() is None:
                state['process'].terminate()
                return "Остановлена."
            return "Не запущена."

        elif action == "delete":
            if state['process'] and state['process'].poll() is None:
                state['process'].terminate()
                state['process'].wait()
            if os.path.exists(sandbox_dir):
                try: shutil.rmtree(sandbox_dir)
                except: subprocess.run(f"powershell -Command \"Remove-Item -Path '{sandbox_dir}' -Recurse -Force\"", shell=True)
                return "Удалена."
            return "Не найдена."
        return "Неверная команда"

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
        

    def check_tool_args(self, args, tool_args):
        for arg in args:
            if arg not in tool_args:
                return False
        return True

    def tool_exec(self, name, tool_args):
        import json
        import copy
        
        tools_dict_required, tools_dict_additional = self._get_tools_dicts()
        required = tools_dict_required.get(name, [])
        additional = tools_dict_additional.get(name, [])

        # Логирование запроса
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

                # Логирование результата (с очисткой от тяжелых данных)
                print_result = tool_result
                if isinstance(tool_result, dict):
                    clean_result = copy.deepcopy(tool_result)
                    if "images" in clean_result:
                        count = len(clean_result["images"]) if isinstance(clean_result["images"], list) else 1
                        clean_result["images"] = f"< {count} images omitted from logs >"
                    print_result = json.dumps(clean_result, ensure_ascii=False, indent=2)
                
                self.print_code(f"Результат {name}", print_result)
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


    def get_generate_config(self):
        # 1. Сборка промпта
        full_instruction = self.system_prompt + getattr(self, "final_prompt", "")
        
        # 2. Фильтрация инструментов
        blocked = getattr(self, "blocked_tools", [])
        allowed_tools_defs = [
            t for t in self.tools 
            if t["function"]["name"] not in blocked
        ]
        
        tools_gemini = []
        for tool in allowed_tools_defs:
            tools_gemini.append(types.Tool(function_declarations=[tool["function"]]))

        return types.GenerateContentConfig(
            tools=tools_gemini,
            system_instruction=full_instruction,
            thinking_config=types.ThinkingConfig(include_thoughts=True),
        )

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

                config = self.get_generate_config()

                stream = self.client.models.generate_content_stream(
                    model=self.model,
                    contents=self.messages,
                    config=config,
                )

                res = self._handle_stream(stream)
                if res:
                    return res

            except Exception as e:
                error_msg = f"Произошла ошибка API: {e}\n\n{traceback.format_exc()}"
                self.print(f"\n❌ {error_msg}")

    def _handle_stream(self, stream):
        response_parts = []
        tool_calls_buffer = []
        full_response_text = ""
        
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
                        full_response_text += part.text
                    
                    if part.function_call:
                        tool_calls_buffer.append(part.function_call)

            self.print("")
            
            self.messages.append(types.Content(role="model", parts=response_parts))

            if tool_calls_buffer:
                return self._execute_tool_calls(tool_calls_buffer)

            return full_response_text 

        except Exception as e:
            e_trace = traceback.format_exc()

            if "429" in str(e) or "Resource has been exhausted" in str(e):
                wait_time = -1
                try:
                    # Поиск "Please retry in ...s" (самый точный способ из сообщения об ошибке)
                    match = re.search(r"Please retry in (\d+\.?\d*)s", str(e))
                    if match:
                        wait_time = float(match.group(1))
                    else:
                        # Поиск в JSON-структуре 'retryDelay': '29s'
                        match = re.search(r"retryDelay': '(\d+)s'", str(e))
                        if match:
                            wait_time = int(match.group(1))
                except Exception as e:
                    self.print(f"Ошибка обработки стрима: {e}\n{e_trace}")
                    return f"Ошибка обработки стрима: {e}"
                
                if wait_time == -1:
                    self.print(f"Ошибка обработки стрима: {e}\n{e_trace}")
                    return f"Ошибка обработки стрима: {e}"

                self.print(f"⚠️ Лимит исчерпан (429). Ожидание {wait_time:.1f}с...")
                time.sleep(wait_time + 1)
                return None
            else:
                self.print(f"Ошибка обработки стрима: {e}\n{e_trace}")
                return f"Ошибка обработки стрима: {e}"

    def _execute_tool_calls(self, tool_calls):
        import json
        import base64
        from google.genai import types
        
        response_parts = []
        
        for fc in tool_calls:
            name = fc.name
            args = fc.args
            
            if not isinstance(args, dict):
                try:
                    args = json.loads(args)
                except:
                    args = {}

            # Выполнение инструмента
            # Guard: Blocked tools
            if name in getattr(self, "blocked_tools", []):
                result = f"Ошибка: Инструмент {name} заблокирован пресетом."
            else:
                # Overrides: Settings tools
                overrides = getattr(self, "settings_tools", {}).get(name, {})
                if overrides:
                    original_args = args.copy() if isinstance(args, dict) else {}
                    conflicts = [k for k in overrides if k in original_args and original_args[k] != overrides[k]]
                    
                    if isinstance(args, dict):
                        args.update(overrides)
                    
                    result = self.tool_exec(name, args)
                    
                    if conflicts:
                        notes = ", ".join(conflicts)
                        if isinstance(result, str):
                            result += f"\n[Внимание: Аргументы ({notes}) были переопределены настройками пресета]"
                else:
                    result = self.tool_exec(name, args)
            
            # Подготовка данных для FunctionResponse
            res_payload = {"result": result}
            fr_parts = []
            
            # Если инструмент вернул словарь, проверяем наличие изображений
            if isinstance(result, dict):
                res_payload = result.copy()
                # Извлекаем изображения, если они есть
                images = res_payload.pop("images", [])
                if not isinstance(images, list):
                    images = [images]
                
                for img in images:
                    try:
                        if isinstance(img, str):
                            if "base64," in img:
                                header, b64_str = img.split("base64,", 1)
                                mime = header.split(":")[1].split(";")[0]
                                data = base64.b64decode(b64_str)
                            else:
                                data = base64.b64decode(img)
                                mime = "image/jpeg"
                        elif isinstance(img, bytes):
                            data = img
                            mime = "image/jpeg"
                        else:
                            continue
                            
                        # Используем структуру для мультимодальных ответов инструментов
                        fr_parts.append(types.FunctionResponsePart(
                            inline_data=types.FunctionResponseBlob(
                                mime_type=mime,
                                data=data
                            )
                        ))
                    except Exception as e:
                        self.print(f"Ошибка обработки изображения в ответе инструмента: {e}")
            
            # Создаем Part с ответом функции
            response_parts.append(types.Part(
                function_response=types.FunctionResponse(
                    name=name,
                    response=res_payload,
                    parts=fr_parts if fr_parts else None
                )
            ))
        
        # Добавляем ответы инструментов в историю (от имени user по протоколу Gemini)
        self.messages.append(types.Content(role="user", parts=response_parts))

        # Продолжаем диалог с новыми данными
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

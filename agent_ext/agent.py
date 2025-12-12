import os, json, ast, sys, types, datetime, time, subprocess, traceback
from google import genai
from google.genai import types

class Chat:
    local_env = dict()
    result = ''
    
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
        #self.model, self.model_rpm = "gemini-2.5-pro", 150

        self._load_config()
        self.client = genai.Client(api_key=self.ai_key)
        
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
        prompt_names = ["system", "python", "chat", "chat_exec", "user_profile", "save_code_changes", "http", "shell", "google_search", "python_str"]
        for name in prompt_names:
            try:
                with open(f"{self.agent_dir}/prompts/{name}", 'r', encoding="utf8") as f: 
                    self.prompts[name] = f.read()
            except FileNotFoundError: self.prompts[name] = f"Prompt '{name}' not found."

        with open(f"{self.agent_dir}/user_profile.json", 'r', encoding="utf8") as f: 
            self.user_profile = f.read()
        
        # Читаем agent.py для контекста
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

    def _initialize_tools(self):
        with open(f"{self.agent_dir}/tools.json", 'r', encoding="utf8") as f: 
            self.tools_config = json.load(f)["tools"]
        
        for tool in self.tools_config:
            tool["function"]["description"] = self.prompts.get(tool["function"]["name"], tool["function"]["description"])

        # Конвертация в формат Google GenAI
        function_declarations = []
        for tool in self.tools_config:
            func = tool["function"]
            params = func.get("parameters", {})
            # Fix for GenAI: properties required
            if "properties" not in params:
                params["properties"] = {}
                params["type"] = "OBJECT"
            
            function_declarations.append(
                types.FunctionDeclaration(
                    name=func["name"],
                    description=func["description"],
                    parameters=params
                )
            )
        
        if function_declarations:
            self.genai_tools = [types.Tool(function_declarations=function_declarations)]
        else:
            self.genai_tools = []

        self.tools_dict_required = { 
            "chat": ["name", "message"], 
            "chat_exec": ["name", "code"], 
            "python": ["code"], 
            "google_search": ["query"], 
            "shell": ["command"], 
            "user_profile": ["data"], 
            "http": ["url"], 
            "save_code_changes": ["code"],
            "python_str" : ["text"]
        }
        self.tools_dict_additional = { 
            "google_search": ["num_results"], 
            "shell": ["timeout"]
        }

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
            process = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            return json.dumps({"returncode": process.returncode, "stdout": process.stdout, "stderr": process.stderr}, ensure_ascii=False, indent=2)
        except subprocess.TimeoutExpired:
            return json.dumps({"returncode": -1, "stdout": "", "stderr": f"Ошибка: Команда выполнялась дольше {timeout} секунд и была прервана."}, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"returncode": -1, "stdout": "", "stderr": f"Критическая ошибка при выполнении команды: {str(e)}"}, ensure_ascii=False, indent=2)

    def http_tool(self, url):
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError: return "Ошибка: для работы этого инструмента необходимы библиотеки requests и beautifulsoup4."
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
    
    def check_tool_args(self, args, tool_args, tool_id):
        for arg in args:
            if arg not in tool_args:
                self.messages.append({"role": "tool", "tool_call_id": tool_id, "content": f"Ошибка: отсутствует параметр {arg}"})
                return False
        return True

    def tool_exec(self, name, tool_args, tool_id):
        required = self.tools_dict_required.get(name, [])
        additional = self.tools_dict_additional.get(name, [])

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
            if self.check_tool_args(required, tool_args, tool_id):
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
                return {"role": "tool", "tool_call_id": tool_id, "content": str(tool_result)}

        except Exception as e:
            error_message = f"Ошибка инструмента: {e}"
            self.print_code(f"Ошибка {name}", error_message)
            return {"role": "tool", "tool_call_id": tool_id, "content": error_message}

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

    def send(self, message):
        if isinstance(message, dict):
            self.messages.append(message)
        else:
            self.messages.extend(message)
        return self._process_request()

    def _convert_to_genai_history(self):
        """Конвертирует историю OpenAI (self.messages) в формат Google GenAI (contents)."""
        contents = []
        system_instruction = None
        
        i = 0
        while i < len(self.messages):
            msg = self.messages[i]
            role = msg["role"]
            content_text = msg.get("content", "")
            
            if role == "system":
                if system_instruction is None:
                    system_instruction = content_text
                else:
                    system_instruction += "\n" + content_text
                i += 1
                continue
                
            if role == "user":
                contents.append(types.Content(role="user", parts=[types.Part(text=content_text)]))
                i += 1
                
            elif role == "assistant":
                parts = []
                if content_text:
                    parts.append(types.Part(text=content_text))
                
                if "tool_calls" in msg and msg["tool_calls"]:
                    for tc in msg["tool_calls"]:
                        fn = tc["function"]
                        try:
                            args = json.loads(fn["arguments"])
                        except:
                            args = {}
                        parts.append(types.Part(
                            function_call=types.FunctionCall(
                                name=fn["name"],
                                args=args
                            )
                        ))
                
                if parts:
                    contents.append(types.Content(role="model", parts=parts))
                i += 1
            
            elif role == "tool":
                function_responses = []
                while i < len(self.messages) and self.messages[i]["role"] == "tool":
                    tool_msg = self.messages[i]
                    call_id = tool_msg.get("tool_call_id")
                    
                    # Ищем имя функции по ID
                    func_name = "unknown"
                    for hist_msg in reversed(self.messages[:i]):
                        if hist_msg["role"] == "assistant" and "tool_calls" in hist_msg:
                            for tc in hist_msg["tool_calls"]:
                                if tc["id"] == call_id:
                                    func_name = tc["function"]["name"]
                                    break
                            if func_name != "unknown": break
                    
                    response_content = tool_msg["content"]
                    try:
                        response_data = json.loads(response_content)
                    except:
                        response_data = {"result": response_content}

                    function_responses.append(types.Part(
                        function_response=types.FunctionResponse(
                            name=func_name,
                            response=response_data
                        )
                    ))
                    i += 1
                
                if function_responses:
                    contents.append(types.Content(role="user", parts=function_responses))
            
            else:
                i += 1

        return contents, system_instruction

    def _process_request(self):
        while True:
            try:
                delay = 60 / self.model_rpm - (time.time() - self.last_send_time)
                if delay > 0:
                    self.print(f"Жду {delay:.2f} секунд")
                    time.sleep(delay)
                self.last_send_time = time.time()

                if self.print_to_console:
                    prefix = "🤖 Агент: " if self.output_mode == "user" else "⚙️ Агент (авто, ответ): "
                    self.print(prefix, end="", flush=True)

                contents, system_inst = self._convert_to_genai_history()
                
                config = types.GenerateContentConfig(
                    tools=self.genai_tools,
                    system_instruction=system_inst,
                )

                stream = self.client.models.generate_content_stream(
                    model=self.model,
                    contents=contents,
                    config=config
                )
                
                return self._handle_stream(stream)

            except Exception as e:
                error_msg = f"Произошла ошибка: {e}\n\n{traceback.format_exc()}"
                self.print(f"\n❌ {error_msg}")

                if "429" in str(e) or "Resource has been exhausted" in str(e):
                    self.last_send_time -= 60
                    self._switch_api_key()
                    continue
                else:
                    if self.output_mode != "user":
                        self.send({"role": "system", "content": error_msg})
                    return f"Критическая ошибка: {error_msg}"

    def _handle_stream(self, stream):
        full_content = ""
        tool_calls_buffer = []
        is_thought = False

        try:
            for chunk in stream:
                if chunk.text:
                    text_part = chunk.text
                    
                    if "<thought>" in text_part:
                        is_thought = True
                        display_text = text_part.replace("<thought>", '')
                        if self.print_to_console:
                            self.print('\nМысли:', flush=True)
                    elif "</thought>" in text_part:
                        is_thought = False
                        display_text = text_part.replace("</thought>", '')
                        if self.print_to_console: self.print('\nОтвет:', flush=True)
                    else:
                        display_text = text_part

                    if is_thought:
                        self.print_thought(display_text, count_tab=self.count_tab + 1, flush=True, end='')
                    else:
                        full_content += display_text
                        self.print(display_text, flush=True, end='')

                if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                    for part in chunk.candidates[0].content.parts:
                        if part.function_call:
                            # Generate an ID for OpenAI compatibility
                            call_id = f"call_{int(time.time())}_{part.function_call.name}"
                            args_str = json.dumps(part.function_call.args) 
                            
                            tc = {
                                "id": call_id,
                                "type": "function",
                                "function": {
                                    "name": part.function_call.name,
                                    "arguments": args_str
                                }
                            }
                            tool_calls_buffer.append(tc)

            self.print("") 

            assistant_message = {
                "role": "assistant",
                "content": full_content
            }
            if tool_calls_buffer:
                assistant_message["tool_calls"] = tool_calls_buffer

            self.messages.append(assistant_message)

            if "tool_calls" in assistant_message:
                self._execute_tool_calls(assistant_message["tool_calls"])

            return full_content

        except Exception as e:
            e_trace = traceback.format_exc()
            self.print(f"Ошибка обработки стрима GenAI: {e}\n{e_trace}")
            return f"Ошибка обработки стрима: {e}"

    def _switch_api_key(self):
        self.current_key_index = (self.current_key_index + 1) % len(self.gemini_keys)
        with open(f"{self.agent_dir}/keys/gemini.key_num", 'w', encoding="utf8") as f:
            f.write(str(self.current_key_index))
        self.ai_key = self.gemini_keys[self.current_key_index]
        self.client = genai.Client(api_key=self.ai_key)
        self.print(f"🔑 Превышен лимит запросов. Переключаюсь на следующий ключ ({self.current_key_index + 1}/{len(self.gemini_keys)}).")

    def _execute_tool_calls(self, tool_calls):
        tool_responses = []
        for tool_call in tool_calls:
            if "function" not in tool_call:
                continue
            tool_name = tool_call["function"]["name"]
            try:
                tool_args_str = tool_call["function"]["arguments"]
                tool_args = json.loads(tool_args_str)
            except json.JSONDecodeError:
                tool_args = {}
            tool_call_id = tool_call["id"]
            
            if tool_name in self.tools_dict_required:
                response = self.tool_exec(tool_name, tool_args, tool_call_id)
                tool_responses.append(response)
            else:
                tool_responses.append({"role": "tool", "tool_call_id": tool_call_id, "content": "Такого инструмента не существует"})

        if tool_responses:
            self.send(tool_responses)


def main():
    print("🚀 AI-агент запущен. Введите ваш запрос.")

    chat_agent = Chat(print_to_console=True)
    
    try:
        while True:
            user_input = input("\n👤 Вы: ")
            chat_agent.send({"role": "user", "content": user_input})
    except KeyboardInterrupt:
        print("\n👋 Программа завершена пользователем")
    except EOFError:
        print("\n👋 Программа завершена (Ctrl+D)")
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")


if __name__ == "__main__":
    main()

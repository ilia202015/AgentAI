
import sys
import os
import time
import base64
import json
import importlib.util
from google import genai
from google.genai import types

# Импорт базового класса Chat
current_dir = os.path.dirname(os.path.abspath(__file__))
agent_ext_path = os.path.dirname(os.path.dirname(current_dir))
if agent_ext_path not in sys.path:
    sys.path.append(agent_ext_path)

from agent import Chat

# Надежная загрузка tools
try:
    from . import tools
except ImportError:
    try:
        import tools
    except ImportError:
        spec = importlib.util.spec_from_file_location("tools", os.path.join(current_dir, "tools.py"))
        tools = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tools)

class ComputerUseChat(Chat):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Принудительно ставим модель Computer Use
        self.model = "gemini-2.5-computer-use-preview-10-2025" 
        self.output_mode = "auto"
        self.tools = [] 
        
        self.system_prompt = """Ты - агент, управляющий компьютером. 
Твоя цель - выполнить задачу пользователя, используя доступные инструменты (мышь, клавиатура).
1. Всегда анализируй скриншот перед действием.
2. Если элемент не найден, попробуй прокрутить страницу.
3. По завершении задачи просто ответь текстом с результатом.
"""
    
    def run_task(self, task_description):
        self.print(f"🖥️ Computer Use Agent начал работу: {task_description}")
        
        screenshot_bytes = tools.take_screenshot()
        
        if hasattr(self, 'web_emit'):
            b64_img = base64.b64encode(screenshot_bytes).decode('utf-8')
            self.web_emit("computer_view", {"image": f"data:image/png;base64,{b64_img}"})

        user_content = types.Content(
            role="user",
            parts=[
                types.Part(text=task_description),
                types.Part.from_bytes(data=screenshot_bytes, mime_type='image/png')
            ]
        )
        self.messages = [user_content]
        
        config = types.GenerateContentConfig(
            tools=[types.Tool(
                computer_use=types.ComputerUse(
                    environment=types.Environment.ENVIRONMENT_UNSPECIFIED
                )
            )],
            thinking_config=types.ThinkingConfig(include_thoughts=True),
            system_instruction=self.system_prompt
        )

        turn_limit = 15
        
        MAX_RECENT_TURN_WITH_SCREENSHOTS = 3
        
        for i in range(turn_limit):
            self.print(f"\n--- Ход {i+1} ---")
            
            # --- API CALL ---
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=self.messages,
                    config=config
                )
            except Exception as e:
                return f"Ошибка API: {e}"

            if not response.candidates:
                return "Ошибка: Пустой ответ от модели."

            candidate = response.candidates[0]
            
            text_parts = [p.text for p in candidate.content.parts if p.text]
            if text_parts:
                full_text = " ".join(text_parts)
                self.print(f"🤖 Мысль/Ответ: {full_text}")
                if hasattr(self, 'web_emit'):
                    self.web_emit("thought", full_text)

            self.messages.append(candidate.content)

            function_calls = [p.function_call for p in candidate.content.parts if p.function_call]
            
            if not function_calls:
                return " ".join(text_parts) if text_parts else "Задача завершена (без текста)."

            # --- EXECUTION ---
            self.print(f"⚡ Выполнение {len(function_calls)} действий...")
            
            results = []
            for fc in function_calls:
                fname = fc.name
                args = fc.args
                self.print(f"  -> {fname}({json.dumps(args, ensure_ascii=False)})")
                
                try:
                    res = tools.execute_action(fname, args)
                    results.append((fname, res))
                except Exception as e:
                    self.print(f"  ❌ Ошибка: {e}")
                    results.append((fname, {"error": str(e)}))

            # --- OBSERVATION (Screenshot) ---
            self.print("📸 Обновление состояния экрана...")
            time.sleep(2.0)
            new_screenshot = tools.take_screenshot()
            
            if hasattr(self, 'web_emit'):
                b64_img = base64.b64encode(new_screenshot).decode('utf-8')
                self.web_emit("computer_view", {"image": f"data:image/png;base64,{b64_img}"})

            fr_parts = []
            for fname, result_dict in results:
                if isinstance(result_dict, dict) and "url" not in result_dict:
                     result_dict["url"] = "https://desktop.local"

                fr_part = types.Part(
                    function_response=types.FunctionResponse(
                        name=fname,
                        response=result_dict,
                        parts=[
                            types.FunctionResponsePart(
                                inline_data=types.FunctionResponseBlob(
                                    mime_type="image/png",
                                    data=new_screenshot
                                )
                            )
                        ]
                    )
                )
                fr_parts.append(fr_part)

            self.messages.append(types.Content(role="user", parts=fr_parts))
            
            # --- CLEANUP HISTORY ---
            # Оставляем скриншоты только в последних N ответах инструментов
            # Ищем сообщения с ролью 'user' (ответы инструментов), содержащие function_response
            
            screenshot_turns = []
            for idx, msg in enumerate(self.messages):
                if msg.role == "user" and msg.parts:
                    has_screen = False
                    for p in msg.parts:
                         if p.function_response and p.function_response.parts:
                             # Проверяем наличие блоба (скриншота)
                             # Обычно он первый в parts
                             if any(sub.inline_data for sub in p.function_response.parts):
                                 has_screen = True
                                 break
                    if has_screen:
                        screenshot_turns.append(idx)
            
            if len(screenshot_turns) > MAX_RECENT_TURN_WITH_SCREENSHOTS:
                # Удаляем старые
                indices_to_clean = screenshot_turns[:-MAX_RECENT_TURN_WITH_SCREENSHOTS]
                for idx in indices_to_clean:
                    msg = self.messages[idx]
                    for p in msg.parts:
                        if p.function_response:
                             # Очищаем parts у function_response (где лежал скриншот)
                             p.function_response.parts = None
                
                self.print(f"🧹 Очищены скриншоты из {len(indices_to_clean)} старых ходов.")

        return "Превышен лимит ходов (15)."

import sys
import os
import time
import base64
import json
import importlib.util
import traceback
from google import genai
from google.genai import types

# Импорт базового класса Chat
current_dir = os.path.dirname(os.path.abspath(__file__))
agent_ext_path = os.path.dirname(os.path.dirname(current_dir))
if agent_ext_path not in sys.path:
    sys.path.append(agent_ext_path)

from agent import Chat

# Загрузка инструментов и библиотек
try:
    from . import tools
except ImportError:
    import tools

class ComputerUseChat(Chat):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model = "gemini-2.5-computer-use-preview-10-2025" 
        self.output_mode = "auto"
        self.tools = [] 
        
        self.system_prompt = """Ты - экспертный агент по управлению Windows.
Твоя задача: выполнять действия в ОС, используя 13 встроенных функций Computer Use.
ПРАВИЛА:
1. Координаты передавай в формате 0-1000. (0,0 - левый верхний угол, 1000,1000 - правый нижний).
2. Перед кликом или вводом текста ВСЕГДА проверяй скриншот.
3. Для ввода текста используй type_text_at, он автоматически очищает поле.
4. Если нужно подождать загрузки страницы или приложения, используй wait_5_seconds.
5. Если задача выполнена, заверши работу итоговым текстовым отчетом."""
    
    def run_task(self, task_description):
        self.print(f"🖥️ Computer Use Agent начал работу: {task_description}")
        
        # Запуск индикации и мониторинга
        if hasattr(tools, 'overlay'):
            tools.overlay.start()
        if hasattr(tools, 'monitor'):
            tools.monitor.update_last_pos()
        
        final_report = "Задача завершена."
        
        try:
            try:
                screenshot_bytes = tools.take_screenshot()
            except Exception as e:
                return f"Ошибка захвата экрана: {e}"
            
            if hasattr(self, 'web_emit'):
                b64_img = base64.b64encode(screenshot_bytes).decode('utf-8')
                self.web_emit("computer_view", {"image": f"data:image/png;base64,{b64_img}"} )

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

            turn_limit = 50
            MAX_RECENT_TURN_WITH_SCREENSHOTS = 3
            
            for i in range(turn_limit):
                self.print(f"\n--- Ход {i+1} ---")
                
                # Проверка вмешательства пользователя
                if hasattr(tools, 'monitor') and tools.monitor.check():
                    self.print("⚠️ Обнаружено вмешательство пользователя! Прерывание работы.")
                    final_report = "Работа прервана пользователем (движение мыши или ввод)."
                    break

                try:
                    response = self.client.models.generate_content(
                        model=self.model,
                        contents=self.messages,
                        config=config
                    )
                except Exception as e:
                    final_report = f"Ошибка API: {e}"
                    break

                if not response.candidates:
                    final_report = "Ошибка: Пустой ответ от модели."
                    break

                candidate = response.candidates[0]
                
                # Логирование мыслей
                if candidate.content.parts:
                    for part in candidate.content.parts:
                        if part.text:
                            self.print(f"🤖 {part.text}")
                            if hasattr(self, 'web_emit'):
                                self.web_emit("thought", part.text)

                self.messages.append(candidate.content)

                function_calls = [p.function_call for p in candidate.content.parts if p.function_call]
                
                if not function_calls:
                    final_report = "Задача завершена."
                    break

                # Исполнение
                results = []
                for fc in function_calls:
                    fname = fc.name
                    args = fc.args
                    
                    safety_ack = False
                    if args and 'safety_decision' in args:
                        self.print(f"🛡️ Обнаружено решение по безопасности: {args['safety_decision'].get('explanation', '')}.")
                        safety_ack = True
                    
                    self.print(f"⚡ Выполнение: {fname}({json.dumps(args, ensure_ascii=False)})")
                    
                    try:
                        res = tools.execute_action(fname, args)
                        if safety_ack:
                            res["safety_acknowledgement"] = "true"
                        results.append((fname, res))
                    except Exception as e:
                        self.print(f"  ❌ Ошибка: {e}")
                        error_res = {"error": str(e)}
                        if safety_ack:
                            error_res["safety_acknowledgement"] = "true"
                        results.append((fname, error_res))

                # Обновление состояния
                time.sleep(1.5)
                try:
                    new_screenshot = tools.take_screenshot()
                except:
                    new_screenshot = screenshot_bytes

                if hasattr(self, 'web_emit'):
                    b64_img = base64.b64encode(new_screenshot).decode('utf-8')
                    self.web_emit("computer_view", {"image": f"data:image/png;base64,{b64_img}"} )

                fr_parts = []
                for fname, result_dict in results:
                    if "url" not in result_dict:
                         result_dict["url"] = "https://desktop.local"

                    fr_parts.append(types.Part(
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
                    ))

                self.messages.append(types.Content(role="user", parts=fr_parts))
                
                # Очистка скриншотов
                screenshot_turns = []
                for idx, msg in enumerate(self.messages):
                    if msg.role == "user" and msg.parts:
                        if any(p.function_response and p.function_response.parts for p in msg.parts):
                            screenshot_turns.append(idx)
                
                if len(screenshot_turns) > MAX_RECENT_TURN_WITH_SCREENSHOTS:
                    indices_to_clean = screenshot_turns[:-MAX_RECENT_TURN_WITH_SCREENSHOTS]
                    for idx in indices_to_clean:
                        for p in self.messages[idx].parts:
                            if p.function_response:
                                 p.function_response.parts = None
            
            if i >= turn_limit - 1:
                final_report = "Превышен лимит ходов."
                
        finally:
            if hasattr(tools, 'overlay'):
                tools.overlay.stop()
            
            # Отправка браузерного уведомления
            if hasattr(self, 'web_emit'):
                self.web_emit("notification", {
                    "title": "Computer Use завершен",
                    "body": final_report
                })
            
            # Оставляем системное как запасной вариант (опционально)
            # if hasattr(tools, 'show_completion_notification'):
            #    tools.show_completion_notification(message=final_report)
            
        return final_report

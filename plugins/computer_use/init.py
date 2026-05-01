
import os
import sys
import types
import base64
import json
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    import tools
except ImportError:
    from . import tools

def main(chat, settings):
    # 1. Загрузка метаданных инструментов
    try:
        with open(os.path.join(current_dir, "tools_metadata.json"), "r", encoding="utf-8") as f:
            plugin_tools = json.load(f)
        for t in plugin_tools:
            name = t["function"]["name"]
            # Подхватываем промпт из chat.prompts
            if name in chat.prompts:
                desc = chat.prompts[name]
                if name == "computer_use_actions" and hasattr(tools, "TOOLS_PROMPT"):
                    desc += "\n\n" + tools.TOOLS_PROMPT
                t["function"]["description"] = desc
            
            # Удаляем старые версии инструмента, чтобы обновить
            chat.tools = [existing for existing in chat.tools if existing['function']['name'] != name]
            chat.tools.append(t)
            
        # Удаляем take_screenshot из инструментов, если он там остался
        chat.tools = [existing for existing in chat.tools if existing['function']['name'] != 'take_screenshot']
    except Exception as e:
        print(f"⚠️ Ошибка загрузки tools_metadata.json: {e}")

    # 2. Инструмент: computer_use_actions
    def computer_use_actions_tool(self, actions):
        if hasattr(tools, 'overlay'):
            tools.overlay.start()
        
        results = []
        images_b64 = [] # Массив для всех собранных скриншотов
        
        for act in actions:
            action_name = act.get("action")
            if not action_name:
                continue
                
            self.print(f"⚡ [Action] {action_name}({json.dumps(act, ensure_ascii=False)})")
            
            if action_name == "screenshot":
                try:
                    delay = float(act.get("seconds", 0))
                    if delay > 0:
                        self.print(f"📸 Ожидание {delay}с перед скрином...")
                        time.sleep(delay)
                        
                    img_bytes = tools.take_screenshot()
                    
                    if hasattr(self, 'web_emit'):
                        b64_img = base64.b64encode(img_bytes).decode('utf-8')
                        self.web_emit("computer_view", {"image": f"data:image/png;base64,{b64_img}"})
                    
                    b64 = base64.b64encode(img_bytes).decode('utf-8')
                    images_b64.append(b64)
                    results.append({"action": "screenshot", "status": "success", "image_index": len(images_b64) - 1})
                except Exception as e:
                    self.print(f"  ❌ Ошибка скриншота: {e}")
                    results.append({"action": "screenshot", "error": str(e)})
                continue

            # Выполнение других действий
            try:
                res = tools.execute_action(action_name, act)
                results.append({"action": action_name, "result": res})
            except Exception as e:
                self.print(f"  ❌ Ошибка: {e}")
                results.append({"action": action_name, "error": str(e)})

        if hasattr(tools, 'overlay'):
            tools.overlay.stop()
            
        final_response = {"status": "completed", "details": results}
        
        # Прикрепляем все собранные картинки. agent.py автоматически развернет их в FunctionResponsePart
        if images_b64:
            final_response["images"] = images_b64
            
        return final_response

    chat.computer_use_actions_tool = types.MethodType(computer_use_actions_tool, chat)

    print("✅ Custom Computer Use (Action: screenshot) интегрирован.")
    return chat

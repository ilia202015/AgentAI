
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
    try:
        with open(os.path.join(current_dir, "tools_metadata.json"), "r", encoding="utf-8") as f:
            plugin_tools = json.load(f)
        for t in plugin_tools:
            name = t["function"]["name"]
            if name in chat.prompts:
                t["function"]["description"] = chat.prompts[name]
            if not any(exist['function']['name'] == name for exist in chat.tools):
                chat.tools.append(t)
    except Exception as e:
        print(f"⚠️ Ошибка загрузки tools_metadata.json: {e}")

    def take_screenshot_tool(self):
        try:
            img_bytes = tools.take_screenshot()
            if hasattr(self, 'web_emit'):
                b64_img = base64.b64encode(img_bytes).decode('utf-8')
                self.web_emit("computer_view", {"image": f"data:image/png;base64,{b64_img}"})
            b64 = base64.b64encode(img_bytes).decode('utf-8')
            return {"status": "success", "images": [b64]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    chat.take_screenshot_tool = types.MethodType(take_screenshot_tool, chat)

    def computer_use_actions_tool(self, actions, delay_before_screenshot=1.0):
        if hasattr(tools, 'overlay'):
            tools.overlay.start()
        
        results = []
        for act in actions:
            action_name = act.get("action")
            if not action_name:
                continue
                
            self.print(f"⚡ [Action] {action_name}({json.dumps(act, ensure_ascii=False)})")
            try:
                res = tools.execute_action(action_name, act)
                results.append({"action": action_name, "result": res})
            except Exception as e:
                self.print(f"  ❌ Ошибка: {e}")
                results.append({"action": action_name, "error": str(e)})

        if hasattr(tools, 'overlay'):
            tools.overlay.stop()
            
        final_response = {"status": "completed", "details": results}
        
        # Обработка итогового скриншота
        try:
            delay = float(delay_before_screenshot)
            if delay >= 0:
                self.print(f"📸 Ожидание {delay}с перед скриншотом...")
                time.sleep(delay)
                img_bytes = tools.take_screenshot()
                
                if hasattr(self, 'web_emit'):
                    b64_img = base64.b64encode(img_bytes).decode('utf-8')
                    self.web_emit("computer_view", {"image": f"data:image/png;base64,{b64_img}"})
                
                b64 = base64.b64encode(img_bytes).decode('utf-8')
                final_response["images"] = [b64]
                final_response["screenshot_status"] = "attached"
        except Exception as e:
            self.print(f"⚠️ Ошибка создания скриншота: {e}")
            final_response["screenshot_status"] = f"error: {e}"
            
        return final_response

    chat.computer_use_actions_tool = types.MethodType(computer_use_actions_tool, chat)

    print("✅ Custom Computer Use (Batch Mode + Auto-Screenshot) интегрирован.")
    return chat

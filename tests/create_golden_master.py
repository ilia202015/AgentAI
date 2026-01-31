import os, sys
sys.path.insert(0, os.getcwd())
import os
import sys
import shutil
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import agent
import plugins.web_interface.storage as storage
from google.genai import types

def create_baseline():
    print("Creating Golden Master baseline...")
    
    # 1. Setup temporary workspace
    temp_dir = "tests/temp_baseline"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    
    storage.CHATS_DIR = temp_dir
    
    # 2. Mock Chat to avoid external dependencies
    def dummy_load(self):
        self.ai_key = "dummy"
        self.gemini_keys = ["dummy"]
        self.current_key_index = 0
        self.prompts = {"system": "sys", "python": "py", "user_profile": "{}"}
        self.user_profile = "{}"
        self.self_code = "pass"
        self.saved_code = ""

    with patch('agent.Chat._load_config', dummy_load), \
         patch('google.genai.Client', return_value=MagicMock()):
        
        chat = agent.Chat()
        chat.id = "v1"
        chat.name = "Baseline Chat v1"
        
        # 3. Add complex data
        # Message 1: User with image
        msg1 = types.Content(
            role="user",
            parts=[
                types.Part(text="Hello with image"),
                types.Part.from_bytes(data=b"fake_image_data_baseline", mime_type="image/png")
            ]
        )
        chat.messages.append(msg1)
        
        # Message 2: Model with thoughts and tool calls
        msg2 = types.Content(
            role="model",
            parts=[
                types.Part(text="Thinking...", thought=True),
                types.Part(text="I will call a tool"),
                types.Part(function_call=types.FunctionCall(name="python", args={"code": "print(123)"}))
            ]
        )
        # Custom attributes used by web_interface
        msg2._web_thoughts = "Baseline thoughts"
        msg2._web_tools = [{"title": "python", "content": "print(123)"}]
        chat.messages.append(msg2)
        
        # 4. Save
        storage.save_chat_state(chat)
        
        # 5. Move to data folder
        target_dir = "tests/data"
        os.makedirs(target_dir, exist_ok=True)
        
        shutil.copy(os.path.join(temp_dir, "v1.json"), os.path.join(target_dir, "v1.json"))
        shutil.copy(os.path.join(temp_dir, "v1.pkl"), os.path.join(target_dir, "v1.pkl"))
        
        # Also cleanup temp_dir
        shutil.rmtree(temp_dir)
        print(f"Baseline 'v1' created in {target_dir}")

if __name__ == "__main__":
    create_baseline()

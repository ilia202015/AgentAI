import pytest
import os
import sys
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import agent
import plugins.web_interface.storage as storage
from google.genai import types

@pytest.fixture
def mock_client():
    client = MagicMock()
    # Mock models.generate_content_stream if needed, but for storage tests 
    # we mostly need the client object to exist in the Chat instance.
    return client

@pytest.fixture
def mock_agent(mock_client, tmp_path, monkeypatch):
    # 1. Isolate Storage
    test_chats_dir = tmp_path / "chats"
    test_chats_dir.mkdir()
    monkeypatch.setattr(storage, "CHATS_DIR", str(test_chats_dir))
    
    # 2. Mock Config loading (don't read real keys/files)
    def dummy_load(self):
        self.ai_key = "dummy_key"
        self.gemini_keys = ["dummy_key"]
        self.current_key_index = 0
        self.prompts = {
            "system": "test", "python": "test", "chat": "test", "chat_exec": "test",
            "user_profile": "{}", "save_code_changes": "test", "http": "test",
            "shell": "test", "google_search": "test", "python_str": "test"
        }
        self.user_profile = "{}"
        self.self_code = "pass"
        self.saved_code = ""
        self.google_search_key = "dummy"
        self.search_engine_id = "dummy"

    monkeypatch.setattr(agent.Chat, "_load_config", dummy_load)
    
    # 3. Create Chat instance
    # We patch the Client class to return our mock_client
    with patch('google.genai.Client', return_value=mock_client):
        chat = agent.Chat()
        chat.client = mock_client
        return chat

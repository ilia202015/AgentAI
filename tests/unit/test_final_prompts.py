
import pytest
import os
import json
import re
import plugins.web_interface.storage as storage
from unittest.mock import patch, MagicMock

@pytest.fixture
def isolated_prompts(tmp_path, monkeypatch):
    test_config_path = tmp_path / "final_prompts_test.json"
    monkeypatch.setattr(storage, "PROMPTS_CONFIG_PATH", str(test_config_path))
    return test_config_path

def test_get_config_default_fallback(isolated_prompts):
    if os.path.exists(isolated_prompts):
        os.remove(isolated_prompts)
    with patch("os.path.join", side_effect=lambda *args: "non_existent_path" if "default_prompts.json" in args else os.path.join(*args)):
        config = storage.get_final_prompts_config()
        assert config['active_id'] == 'default'
        assert 'default' in config['prompts']
        assert os.path.exists(isolated_prompts)

def test_save_and_load_config(isolated_prompts):
    test_config = {
        'active_id': 'p1',
        'active_parameters': ['param1'],
        'prompts': {
            'p1': {'name': 'Prompt 1', 'text': 'System Text', 'type': 'system'},
            'param1': {'name': 'Param 1', 'text': 'Param Text', 'type': 'parameter'}
        }
    }
    storage.save_final_prompts_config(test_config)
    loaded_config = storage.get_final_prompts_config()
    assert loaded_config == test_config

def test_get_active_final_prompt_text(isolated_prompts):
    test_config = {
        'active_id': 'p1',
        'active_parameters': ['param1', 'param2'],
        'prompts': {
            'p1': {'name': 'Prompt 1', 'text': 'System Text', 'type': 'system'},
            'param1': {'name': 'Param 1', 'text': 'Param Text', 'type': 'parameter'},
            'param2': {'name': 'Param 2', 'text': 'Another Param', 'type': 'parameter'}
        }
    }
    storage.save_final_prompts_config(test_config)
    text = storage.get_active_final_prompt_text()
    assert "System Text" in text
    assert "Param Text" in text
    assert "Another Param" in text
    assert text.index("System Text") < text.index("Param Text")
    assert text.index("Param Text") < text.index("Another Param")

def test_get_active_final_prompt_text_missing_id(isolated_prompts):
    test_config = {'active_id': 'non_existent', 'active_parameters': [], 'prompts': {}}
    storage.save_final_prompts_config(test_config)
    text = storage.get_active_final_prompt_text()
    assert text == ""

def test_corruption_handling(isolated_prompts):
    with open(isolated_prompts, "w") as f:
        f.write("invalid json {")
    config = storage.get_final_prompts_config()
    assert config['prompts'] == {}
    assert config['active_id'] is None

def test_save_chat_state_cleanup(mock_agent, isolated_prompts):
    # Setup some final prompt markers in the system prompt
    marker_start = storage.WEB_PROMPT_MARKER_START
    marker_end = storage.WEB_PROMPT_MARKER_END
    original_prompt = "Base instructions."
    injected_prompt = f"\n\n{marker_start}\nSome Injected Instructions\n{marker_end}"
    
    chat = mock_agent
    chat.system_prompt = original_prompt + injected_prompt
    chat.id = "test_cleanup"
    chat.messages = []
    
    # Save the state
    with patch("plugins.web_interface.storage.serialization", None): # Simplify
        storage.save_chat_state(chat)
    
    # Check that the saved JSON does NOT contain the injected prompt in system_prompt
    # Wait, storage.save_chat_state modifies chat.system_prompt IN PLACE before saving
    assert marker_start not in chat.system_prompt
    assert "Injected" not in chat.system_prompt
    assert chat.system_prompt.strip() == original_prompt

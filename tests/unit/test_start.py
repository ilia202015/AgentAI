
import pytest
import os
import json
import start
from unittest.mock import MagicMock, patch

def test_system_prompt_assembly(mocker):
    # Mocking files
    mock_files = {
        "start.py": "print('start_code')",
        "plugin_config.json": json.dumps({"list": ["p1"], "settings": {}}),
        "agent.py": "class Chat: pass",
        "user_profile.json": "{}",
        "prompts/system": "Base"
    }
    
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("os.listdir", return_value=[]) # No files in prompts/ dir to avoid loop errors
    
    def mock_open_impl(file, mode='r', **kwargs):
        fname = os.path.basename(file)
        # Search in keys if paths contain dirs
        for k in mock_files:
            if k in file:
                return MagicMock(__enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value=mock_files[k]))))
        return MagicMock(__enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value="dummy"))))

    mocker.patch("builtins.open", side_effect=mock_open_impl)
    mocker.patch("os.walk", return_value=[(".", ["plugins"], ["start.py", "plugin_config.json"])])
    
    mock_chat = MagicMock()
    mock_chat.system_prompt = "BasePrompt"
    mock_chat.messages = []
    mock_chat.prompts = {}
    mocker.patch("start.Chat", return_value=mock_chat)
    
    start.load_plugins()
    
    assert "start_code" in mock_chat.system_prompt
    assert "plugin_config.json" in mock_chat.system_prompt
    assert "BasePrompt" in mock_chat.system_prompt

def test_plugin_init_call(mocker):
    mocker.patch("os.path.exists", return_value=True)
    # Mocking plugin folder structure
    def exists_side_effect(path):
        if "init.py" in path: return True
        if "prompts" in path: return False # Skip prompts for simplicity
        return True
    mocker.patch("os.path.exists", side_effect=exists_side_effect)
    
    mocker.patch("builtins.open", mocker.mock_open(read_data='{"list": ["p1"]}'))
    mocker.patch("os.walk", return_value=[(".", ["plugins"], []), ("./plugins/p1", [], ["init.py"])])
    
    mock_chat = MagicMock()
    mock_chat.system_prompt = ""
    mocker.patch("start.Chat", return_value=mock_chat)
    
    mock_module = MagicMock()
    mock_spec = MagicMock()
    mocker.patch("importlib.util.spec_from_file_location", return_value=mock_spec)
    mocker.patch("importlib.util.module_from_spec", return_value=mock_module)
    
    start.load_plugins()
    mock_module.main.assert_called_once()

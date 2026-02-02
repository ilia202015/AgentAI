
import pytest
import os
import json
import re
from unittest.mock import MagicMock, patch
import plugins.web_interface.server as server
import plugins.web_interface.storage as storage

@pytest.fixture
def mock_handler(mock_agent, tmp_path, monkeypatch):
    # Setup Storage isolation
    test_chats_dir = tmp_path / "chats"
    test_chats_dir.mkdir()
    test_config_path = tmp_path / "final_prompts_test.json"
    
    # Patch both possible module references
    monkeypatch.setattr(storage, "CHATS_DIR", str(test_chats_dir))
    monkeypatch.setattr(storage, "PROMPTS_CONFIG_PATH", str(test_config_path))
    
    if hasattr(server, 'storage'):
        monkeypatch.setattr(server.storage, "CHATS_DIR", str(test_chats_dir))
        monkeypatch.setattr(server.storage, "PROMPTS_CONFIG_PATH", str(test_config_path))
    
    # Initialize Handler state
    server.WebRequestHandler.root_chat = mock_agent
    server.WebRequestHandler.active_chats = {}
    
    # We want to use real logic from WebRequestHandler
    handler = MagicMock(spec=server.WebRequestHandler)
    handler.clone_root_chat = server.WebRequestHandler.clone_root_chat.__get__(handler, server.WebRequestHandler)
    handler.get_agent_for_chat = server.WebRequestHandler.get_agent_for_chat.__get__(handler, server.WebRequestHandler)
    handler._refresh_active_agents_prompts = server.WebRequestHandler._refresh_active_agents_prompts.__get__(handler, server.WebRequestHandler)
    
    handler.root_chat = mock_agent
    handler.active_chats = {}
    handler.ai_client = mock_agent.client
    
    return handler

def test_prompt_injection_on_load(mock_handler):
    config = {
        'active_id': 'p1',
        'active_parameters': [],
        'prompts': {'p1': {'name': 'P1', 'text': 'Final Instructions', 'type': 'system'}}
    }
    storage.save_final_prompts_config(config)
    
    agent = mock_handler.get_agent_for_chat("temp")
    
    assert storage.WEB_PROMPT_MARKER_START in agent.system_prompt
    assert "Final Instructions" in agent.system_prompt

def test_prompt_refresh_logic(mock_handler):
    storage.save_final_prompts_config({
        'active_id': 'a', 'active_parameters': [],
        'prompts': {'a': {'text': 'PROMPT_A'}}
    })
    
    agent = mock_handler.get_agent_for_chat("temp")
    assert "PROMPT_A" in agent.system_prompt
    
    storage.save_final_prompts_config({
        'active_id': 'b', 'active_parameters': [],
        'prompts': {'b': {'text': 'PROMPT_B'}}
    })
    
    mock_handler._refresh_active_agents_prompts()
    
    assert "PROMPT_A" not in agent.system_prompt
    assert "PROMPT_B" in agent.system_prompt
    assert agent.system_prompt.count(storage.WEB_PROMPT_MARKER_START) == 1

def test_prompt_parameters_refresh(mock_handler):
    storage.save_final_prompts_config({
        'active_id': 's', 'active_parameters': [],
        'prompts': {'s': {'text': 'SYSTEM_TEXT'}}
    })
    agent = mock_handler.get_agent_for_chat("temp")
    
    storage.save_final_prompts_config({
        'active_id': 's', 'active_parameters': ['p'],
        'prompts': {
            's': {'text': 'SYSTEM_TEXT'},
            'p': {'text': 'PARAM_TEXT'}
        }
    })
    mock_handler._refresh_active_agents_prompts()
    
    assert "SYSTEM_TEXT" in agent.system_prompt
    assert "PARAM_TEXT" in agent.system_prompt

def test_load_regular_chat_with_final_prompt_bug(mock_handler, mock_agent):
    # 1. Create a regular chat and save it
    mock_agent.id = "reg1"
    storage.save_chat_state(mock_agent)
    
    # 2. Setup final prompt
    storage.save_final_prompts_config({
        'active_id': 'p1', 'active_parameters': ['p2'],
        'prompts': {
            'p1' : {
                "name": "test",
                "text": "Final Instructions test",
                "type": "system",
                "icon": "ph-robot"
            },
            'p2' : {
                "name": "test2",
                "text": "Final test Instructions",
                "type": "parameter",
                "icon": "ph-robot"
            }
        }
    })
    
    # 3. Try to load it via server handler
    # This should trigger the bug: NameError: name 'new_agent' is not defined
    try:
        chat = mock_handler.get_agent_for_chat("reg1")
        assert "Final Instructions test" in chat.system_prompt and \
        "Final test Instructions" in chat.system_prompt and \
        storage.WEB_PROMPT_MARKER_START in chat.system_prompt and \
        storage.WEB_PROMPT_MARKER_END in chat.system_prompt

    except NameError as e:
        pytest.fail(f"Caught expected bug: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error: {type(e)} {e}")

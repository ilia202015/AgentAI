
import sys, os
sys.path.append(os.getcwd())
import pytest
import threading
import time
import requests
import socket
import json
from unittest.mock import MagicMock, patch
from agent import Chat
import plugins.web_interface.server as server_mod
from plugins.web_interface.server import WebRequestHandler
import plugins.browser_use.init as browser_init

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

@pytest.fixture(scope="module")
def mock_agent_env():
    with patch('agent.Chat.__init__', return_value=None):
        chat = Chat()
        chat.agent_dir = "."
        chat.output_mode = "user"
        chat.count_tab = 0
        chat.print_to_console = False
        chat.chats = {}
        chat.last_send_time = 0
        chat.models = [("gemini-3-flash-preview", 1000)]
        chat.model = "gemini-3-flash-preview"
        chat.model_rpm = 1000
        chat.client = MagicMock()
        chat.ai_key = "mock_key"
        chat.tools = []
        chat.prompts = {"system": "test"}
        chat.user_profile = "{}"
        chat.self_code = ""
        chat.system_prompt = "system"
        yield chat

@pytest.fixture(scope="module")
def server_thread(mock_agent_env):
    chat = mock_agent_env
    
    import sys as sys_lib
    sys_lib.modules['server'] = server_mod
    
    # Инициализируем плагин
    browser_init.main(chat, {})
    
    # Получаем bridge
    bridge = sys_lib.modules['browser_bridge'].bridge
    
    port = get_free_port()
    WebRequestHandler.ai_client = chat.client
    WebRequestHandler.root_chat = chat
    
    from http.server import HTTPServer
    server = HTTPServer(('127.0.0.1', port), WebRequestHandler)
    
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    
    yield f"http://127.0.0.1:{port}", bridge
    server.shutdown()
    server.server_close()

def test_browser_use_integration(server_thread, mock_agent_env):
    base_url, bridge = server_thread
    chat = mock_agent_env
    
    # Сброс
    bridge._is_registered = False
    while not bridge._command_queue.empty():
        try: bridge._command_queue.get_nowait()
        except: break

    # 1. Register
    resp = requests.post(f"{base_url}/api/browser/register", timeout=5)
    assert resp.status_code == 200
    assert bridge._is_registered is True

    # 2. Tool call
    command_result = []
    def call_tool():
        try:
            res = chat.browser_actions_tool(commands=[{"type": "get_state"}])
            command_result.append(res)
        except Exception as e:
            command_result.append({"error": str(e)})

    tool_thread = threading.Thread(target=call_tool)
    tool_thread.start()

    # 3. Poll
    time.sleep(1)
    poll_resp = requests.get(f"{base_url}/api/browser/poll", timeout=5)
    assert poll_resp.status_code == 200
    poll_data = poll_resp.json()
    assert poll_data["type"] == "execute_batch"
    request_id = poll_data["request_id"]

    # 4. Respond
    mock_browser_response = {
        "request_id": request_id,
        "status": "success",
        "state": {"url": "http://test.com", "title": "Verified Shared Bridge"}
    }
    respond_resp = requests.post(f"{base_url}/api/browser/respond", json=mock_browser_response, timeout=5)
    assert respond_resp.status_code == 200

    # 5. Final check
    tool_thread.join(timeout=10)
    assert len(command_result) == 1
    assert command_result[0].get("state", {}).get("title") == "Verified Shared Bridge"
    print("\n[TEST SUCCESS] Browser Use Integration Flow Verified!")

if __name__ == "__main__":
    pytest.main([__file__, "-s"])

import pytest
import requests
import threading
import time
import json
import os
import socket
import shutil
import sys
from unittest.mock import MagicMock, patch

import plugins.web_interface.server as server
import plugins.web_interface.storage as storage
import plugins.web_interface.serialization as serialization

# Фикстура для проверки окружения перед запуском любого теста в модуле
@pytest.fixture(scope="module", autouse=True)
def check_sandbox_env():
    cwd = os.getcwd()
    if not ('sandbox' in cwd.lower() or 'temp' in cwd.lower() or 'test' in cwd.lower()):
        pytest.exit("CRITICAL: Tests must run in an isolated environment (sandbox/temp/test)! Aborting.")

@pytest.fixture(scope='module')
def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

@pytest.fixture(scope='module')
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()

@pytest.fixture(scope='module')
def live_server(mock_agent, free_port, monkeypatch_module):
    test_chats_dir = os.path.join(os.getcwd(), 'tests', 'integration_chats')
    os.makedirs(test_chats_dir, exist_ok=True)
    monkeypatch_module.setattr(storage, 'CHATS_DIR', test_chats_dir)
    if 'storage' in sys.modules:
        monkeypatch_module.setattr(sys.modules['storage'], 'CHATS_DIR', test_chats_dir)
    server_instance = None
    def start_server():
        nonlocal server_instance
        monkeypatch_module.setattr(server, 'START_PORT', free_port)
        monkeypatch_module.setattr(server, 'HOST', '127.0.0.1')
        orig_threading_server = server.socketserver.ThreadingTCPServer
        class CapturingServer(orig_threading_server):
            def __init__(self, *args, **kwargs):
                nonlocal server_instance
                server_instance = self
                super().__init__(*args, **kwargs)
        with patch('plugins.web_interface.server.socketserver.ThreadingTCPServer', CapturingServer):
            server.run_server(mock_agent)
    thread = threading.Thread(target=start_server, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{free_port}'
    max_retries = 20
    for _ in range(max_retries):
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200: break
        except: time.sleep(0.2)
    else: pytest.fail('Server failed to start')
    yield url
    if server_instance: server_instance.shutdown(); server_instance.server_close()
    if os.path.exists(test_chats_dir): shutil.rmtree(test_chats_dir)

def test_chat_crud_lifecycle(live_server):
    resp = requests.post(f'{live_server}/api/chats')
    assert resp.status_code == 200
    chat_id = resp.json()['id']
    json_path = os.path.join(storage.CHATS_DIR, f'{chat_id}.json')
    assert os.path.exists(json_path)
    new_name = 'Integration Test Chat'
    resp = requests.patch(f'{live_server}/api/chats/{chat_id}/rename', json={'name': new_name})
    assert resp.status_code == 200
    with open(json_path, 'r', encoding='utf-8') as f: assert json.load(f)['name'] == new_name
    resp = requests.delete(f'{live_server}/api/chats/{chat_id}')
    assert resp.status_code == 200
    assert not os.path.exists(json_path)

def test_message_persistence(live_server, mock_agent):
    resp = requests.post(f'{live_server}/api/chats')
    chat_id = resp.json()['id']
    msg_text = 'Hello from integration test'
    resp = requests.post(f'{live_server}/api/send', json={'chatId': chat_id, 'message': msg_text})
    assert resp.status_code == 200
    time.sleep(1)
    json_path = os.path.join(storage.CHATS_DIR, f'{chat_id}.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        messages = json.load(f)['messages']
        assert any(msg_text in str(m) for m in messages)
    resp = requests.post(f'{live_server}/api/chats/{chat_id}/load')
    assert resp.status_code == 200
    assert len(resp.json()['chat']['messages']) >= 1

def test_static_and_security(live_server):
    resp = requests.get(f'{live_server}/index.html')
    assert resp.status_code == 200
    assert '<title>' in resp.text
    traversal_file = '../../keys/google.key'
    resp = requests.get(f'{live_server}/chat_images?chat_id=some_id&file={traversal_file}')
    assert resp.status_code == 403
    assert 'Invalid filename' in resp.text

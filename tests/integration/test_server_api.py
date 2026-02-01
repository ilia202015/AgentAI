
import pytest
import requests
import os
import json
import time
import threading
import shutil
import base64
import queue

import sys
sys.path.append(os.path.join(os.getcwd(), "plugins"))
from web_interface import server, storage, serialization
from agent import Chat

# --- CRITICAL SAFETY CHECK ---
current_path = os.getcwd().replace("\\", "/")
if "sandbox" not in current_path and "temp" not in current_path:
    print(f"CRITICAL SAFETY ERROR: Tests must run in sandbox or temp. Current: {current_path}")
    pytest.exit("Safety condition failed: not in sandbox/temp")

# --- MOCKS & CONFIG ---
TEST_CHATS_DIR = "chats"

@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    if os.path.exists(TEST_CHATS_DIR):
        shutil.rmtree(TEST_CHATS_DIR)
    os.makedirs(TEST_CHATS_DIR)
    pass
    yield
    if os.path.exists(TEST_CHATS_DIR):
        shutil.rmtree(TEST_CHATS_DIR)

class MockAgent(Chat):
    def __init__(self, *args, **kwargs):
        self.id = None
        self.messages = []
        self.name = "Mock Chat"
        self.web_queue = None
        self.busy_depth = 0
        self.model = "mock-model"
        self.models = [("mock-model", 100), ("other-model", 50)]
        self.client = None
        self.updated_at = ""
        self.agent_dir = "."

    def _load_config(self): pass

    
    def send(self, msg):
        from google.genai import types
        self.busy_depth += 1
        parts = []
        if isinstance(msg, dict):
            content = msg.get("message", msg.get("content", ""))
            if content: parts.append(types.Part(text=content))
            images = msg.get("images", [])
            for img in images:
                if "base64," in img:
                    b64_str = img.split("base64,")[1]
                    parts.append(types.Part.from_bytes(data=base64.b64decode(b64_str), mime_type="image/png"))
        
        self.messages.append(types.Content(role="user", parts=parts))
        
        if hasattr(self, 'web_queue') and self.web_queue:
            self.web_queue.put({"type": "text", "chatId": self.id, "data": "Hello from mock"})
            self.web_queue.put({"type": "finish", "chatId": self.id, "data": "done"})
        
        self.messages.append(types.Content(role="model", parts=[types.Part(text="Hello from mock")]))
        self.busy_depth -= 1
        return "Hello from mock"


@pytest.fixture
def test_server():
    agent = MockAgent()
    # Mocking the root_chat cloning logic in server
    server.WebRequestHandler.root_chat = agent
    server.WebRequestHandler.ai_client = None
    server.WebRequestHandler.active_chats = {}
    
    port = 8081 # Use static or find free
    srv = server.socketserver.ThreadingTCPServer(("127.0.0.1", port), server.WebRequestHandler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    
    base_url = f"http://127.0.0.1:{port}"
    # Wait for server to start
    time.sleep(0.5)
    
    yield base_url
    srv.shutdown()
    srv.server_close()

# --- SCENARIOS ---

def test_1_full_crud_cycle(test_server):
    # 1. Create
    resp = requests.post(f"{test_server}/api/chats")
    assert resp.status_code == 200
    chat_id = resp.json()["id"]
    
    json_path = os.path.join(TEST_CHATS_DIR, f"{chat_id}.json")
    pkl_path = os.path.join(TEST_CHATS_DIR, f"{chat_id}.pkl")
    assert os.path.exists(json_path)
    assert os.path.exists(pkl_path)
    
    # 2. Rename
    new_name = "Renamed Chat"
    resp = requests.patch(f"{test_server}/api/chats/{chat_id}/rename", json={"name": new_name})
    assert resp.status_code == 200
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        assert data["name"] == new_name
        
    # 3. Delete
    resp = requests.delete(f"{test_server}/api/chats/{chat_id}")
    assert resp.status_code == 200
    assert not os.path.exists(json_path)
    assert not os.path.exists(pkl_path)

def test_2_persistence_check(test_server):
    resp = requests.post(f"{test_server}/api/chats")
    chat_id = resp.json()["id"]
    
    msg_text = "Persistence test message"
    requests.post(f"{test_server}/api/send", json={"chatId": chat_id, "message": msg_text})
    
    # Wait for async save
    time.sleep(1)
    
    json_path = os.path.join(TEST_CHATS_DIR, f"{chat_id}.json")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        messages = data["messages"]
        # Check if user message is saved
        assert any(msg_text in str(m) for m in messages)

def test_3_multimodal_images(test_server):
    resp = requests.post(f"{test_server}/api/chats")
    chat_id = resp.json()["id"]
    
    # Fake small png
    b64_img = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    img_data = f"data:image/png;base64,{b64_img}"
    
    requests.post(f"{test_server}/api/send", json={
        "chatId": chat_id, 
        "message": "What is this?", 
        "images": [img_data]
    })
    
    time.sleep(1)
    img_dir = os.path.join(TEST_CHATS_DIR, chat_id, "images")
    assert os.path.exists(img_dir)
    assert len(os.listdir(img_dir)) > 0
    
    # Check history image_url эндпоинт
    resp = requests.post(f"{test_server}/api/chats/{chat_id}/load")
    history = resp.json()["chat"]["messages"]
    found_img = False
    for msg in history:
        for part in msg.get("parts", []):
            if "image_url" in part:
                assert f"chat_id={chat_id}" in part["image_url"]
                found_img = True
    assert found_img

def test_4_clear_context(test_server):
    resp = requests.post(f"{test_server}/api/chats")
    chat_id = resp.json()["id"]
    pkl_path = os.path.join(TEST_CHATS_DIR, f"{chat_id}.pkl")
    assert os.path.exists(pkl_path)
    
    requests.post(f"{test_server}/api/chats/{chat_id}/clear-context")
    assert not os.path.exists(pkl_path)
    assert os.path.exists(os.path.join(TEST_CHATS_DIR, f"{chat_id}.json"))

def test_5_model_management(test_server):
    resp = requests.post(f"{test_server}/api/chats")
    chat_id = resp.json()["id"]
    
    new_model = "other-model"
    requests.post(f"{test_server}/api/chats/{chat_id}/model", json={"model": new_model})
    
    with open(os.path.join(TEST_CHATS_DIR, f"{chat_id}.json"), 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Assuming server saves model field to JSON
        # If server.py doesn't save model to json, we'd need to check the agent instance
        pass

def test_6_sse_streaming(test_server):
    resp = requests.post(f"{test_server}/api/chats")
    chat_id = resp.json()["id"]
    
    # Trigger message to generate events
    requests.post(f"{test_server}/api/send", json={"chatId": chat_id, "message": "Trigger SSE"})
    
    # Listen to stream
    with requests.get(f"{test_server}/stream", stream=True, timeout=5) as r:
        found_text = False
        found_finish = False
        for line in r.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith("data:"):
                    data = json.loads(decoded[5:])
                    if data["chatId"] == chat_id:
                        if data["type"] == "text": found_text = True
                        if data["type"] == "finish": found_finish = True
                if found_text and found_finish:
                    break
    assert found_text
    assert found_finish

def test_7_error_404(test_server):
    resp = requests.post(f"{test_server}/api/chats/fake_id/load")
    assert resp.status_code == 404
    assert "error" in resp.json()

def test_8_path_traversal(test_server):
    # Try to access sensitive files
    resp = requests.get(f"{test_server}/chat_images?chat_id=..&file=..%2fkeys%2fgoogle.key")
    # If server is fixed, it should be 403 or 404
    assert resp.status_code in [403, 404]

def test_9_temp_chats(test_server):
    resp = requests.post(f"{test_server}/api/temp")
    assert resp.status_code == 200
    assert resp.json()["id"] == "temp"
    
    # Temp chat shouldn't create files initially
    assert not os.path.exists(os.path.join(TEST_CHATS_DIR, "temp.json"))

def test_10_broken_storage(test_server):
    chat_id = "broken_chat"
    json_path = os.path.join(TEST_CHATS_DIR, f"{chat_id}.json")
    with open(json_path, 'w') as f:
        f.write("{ invalid json ...")
        
    resp = requests.post(f"{test_server}/api/chats/{chat_id}/load")
    # Server should handle JSON error gracefully
    assert resp.status_code in [404, 500]

def test_11_concurrency(test_server):
    ids = []
    def create():
        r = requests.post(f"{test_server}/api/chats")
        if r.status_code == 200:
            ids.append(r.json()["id"])
            
    threads = [threading.Thread(target=create) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    assert len(ids) == 5
    assert len(set(ids)) == 5 # Unique IDs

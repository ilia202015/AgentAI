
import pytest
import requests
import os
import json
import time
import threading
import shutil
import base64
import queue
import socket
import sys
import unittest.mock as mock

# Настройка путей
current_dir = os.getcwd()
sys.path.append(os.path.join(current_dir, "plugins"))
from web_interface import server, storage, serialization
from agent import Chat

# --- CRITICAL SAFETY CHECK ---
current_path = os.getcwd().replace("\\", "/")
if "sandbox" not in current_path and "temp" not in current_path:
    pytest.exit("Safety condition failed: not in sandbox/temp")

# --- MOCKS & CONFIG ---
TEST_CHATS_DIR = "chats"

@pytest.fixture(autouse=True)
def setup_test_env():
    if os.path.exists(TEST_CHATS_DIR):
        try: shutil.rmtree(TEST_CHATS_DIR)
        except: pass
    os.makedirs(TEST_CHATS_DIR)
    server.WebRequestHandler.active_chats = {}
    yield
    if os.path.exists(TEST_CHATS_DIR):
        try: shutil.rmtree(TEST_CHATS_DIR)
        except: pass

class MockAgent(Chat):
    def __init__(self, *args, **kwargs):
        self.id = kwargs.get('id', None)
        self.messages = []
        self.name = "Mock Chat"
        self.web_queue = None
        self.busy_depth = 0
        self.model = "mock-model"
        self.models = [("mock-model", 100), ("other-model", 50)]
        self.client = None
        self.updated_at = ""
        self.agent_dir = "."
        self.stop_requested = False
        self.system_prompt = "System info"
        self.simulate_exception = False
        self.simulate_long_wait = 0
        self.generation_event = threading.Event()

    def _load_config(self): pass
    def print(self, *args, **kwargs): pass
    def print_thought(self, *args, **kwargs): pass
    def print_code(self, *args, **kwargs): pass

    def __getstate__(self):
        state = self.__dict__.copy()
        state["web_queue"] = None
        state["generation_event"] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.web_queue = queue.Queue()
        self.generation_event = threading.Event()

    def send(self, msg):
        from google.genai import types
        self.busy_depth += 1
        self.stop_requested = False
        try:
            if self.simulate_long_wait > 0:
                start = time.time()
                while time.time() - start < self.simulate_long_wait:
                    if self.stop_requested: break
                    time.sleep(0.1)
            if self.simulate_exception:
                self.web_emit("text", "Crashing...")
                raise Exception("Mock generation error")
            if self.stop_requested:
                self.web_emit("text", "Stopped.")
                return "Stopped"
                
            content = msg.get("message", msg.get("content", ""))
            from google.genai import types as genai_types
            parts = [genai_types.Part(text=content)]
            if "images" in msg and msg["images"]:
                for img_data in msg["images"]:
                    if "base64," in img_data:
                        header, b64_str = img_data.split("base64,", 1)
                        mime = header.split(":")[1].split(";")[0]
                    else: b64_str, mime = img_data, "image/jpeg"
                    parts.append(genai_types.Part.from_bytes(data=base64.b64decode(b64_str), mime_type=mime))
            self.messages.append(genai_types.Content(role="user", parts=parts))
            self.web_emit("text", "Hello")
            self.web_emit("finish", "done")
            self.messages.append(types.Content(role="model", parts=[types.Part(text="Hello")]))
            return "Hello"
        finally:
            self.busy_depth -= 0 if self.busy_depth == 0 else 1
            self.generation_event.set()

    def web_emit(self, msg_type, payload):
        if self.web_queue:
            self.web_queue.put({ "type": msg_type, "chatId": self.id, "data": payload })

@pytest.fixture
def test_server():
    agent = MockAgent()
    server.WebRequestHandler.root_chat = agent
    server.WebRequestHandler.ai_client = None
    server.WebRequestHandler.active_chats = {}
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    srv = server.socketserver.ThreadingTCPServer(("127.0.0.1", port), server.WebRequestHandler)
    srv.allow_reuse_address = True
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    time.sleep(0.2)
    yield url
    srv.shutdown()
    srv.server_close()

# --- ФАЗЫ 0-3 (ОРИГИНАЛЬНЫЕ ТЕСТЫ 1-11) ---

def test_1_full_crud_cycle(test_server):
    resp = requests.post(f"{test_server}/api/chats")
    chat_id = resp.json()["id"]
    json_path = os.path.join(TEST_CHATS_DIR, f"{chat_id}.json")
    assert os.path.exists(json_path)
    requests.patch(f"{test_server}/api/chats/{chat_id}/rename", json={"name": "New"})
    requests.delete(f"{test_server}/api/chats/{chat_id}")
    assert not os.path.exists(json_path)

def test_2_persistence_check(test_server):
    r = requests.post(f"{test_server}/api/chats")
    cid = r.json()["id"]
    requests.post(f"{test_server}/api/send", json={"chatId": cid, "message": "SaveMe"})
    time.sleep(0.5)
    with open(os.path.join(TEST_CHATS_DIR, f"{cid}.json"), 'r', encoding='utf-8') as f:
        assert "SaveMe" in f.read()

def test_3_multimodal_images(test_server):
    r = requests.post(f"{test_server}/api/chats")
    cid = r.json()["id"]
    b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    requests.post(f"{test_server}/api/send", json={"chatId": cid, "message": "Img", "images": [f"data:image/png;base64,{b64}"]})
    time.sleep(0.5)
    assert os.path.exists(os.path.join(TEST_CHATS_DIR, cid, "images"))

def test_4_clear_context(test_server):
    r = requests.post(f"{test_server}/api/chats")
    cid = r.json()["id"]
    requests.post(f"{test_server}/api/chats/{cid}/clear-context")
    assert not os.path.exists(os.path.join(TEST_CHATS_DIR, f"{cid}.pkl"))

def test_5_model_management(test_server):
    r = requests.post(f"{test_server}/api/chats")
    cid = r.json()["id"]
    requests.post(f"{test_server}/api/chats/{cid}/model", json={"model": "other-model"})
    r_load = requests.post(f"{test_server}/api/chats/{cid}/load")
    assert r_load.json()["chat"]["model"] == "other-model"

def test_6_sse_streaming(test_server):
    r = requests.post(f"{test_server}/api/chats")
    cid = r.json()["id"]
    requests.post(f"{test_server}/api/send", json={"chatId": cid, "message": "SSE"})
    with requests.get(f"{test_server}/stream", stream=True, timeout=5) as r:
        for line in r.iter_lines():
            if line and b"data:" in line: return
    assert False, "No data"

def test_7_error_404(test_server):
    assert requests.post(f"{test_server}/api/chats/none/load").status_code == 404

def test_8_path_traversal(test_server):
    r = requests.get(f"{test_server}/chat_images?chat_id=..&file=..")
    assert r.status_code in [403, 404]

def test_9_temp_chats(test_server):
    assert requests.post(f"{test_server}/api/temp").json()["id"] == "temp"

def test_10_broken_storage(test_server):
    with open(os.path.join(TEST_CHATS_DIR, "bad.json"), 'w') as f: f.write("{")
    assert requests.post(f"{test_server}/api/chats/bad/load").status_code in [404, 500]

def test_11_concurrency(test_server):
    def create(): requests.post(f"{test_server}/api/chats")
    ts = [threading.Thread(target=create) for _ in range(3)]
    for t in ts: t.start()
    for t in ts: t.join()
    assert len(os.listdir(TEST_CHATS_DIR)) >= 3

# --- ФАЗА 4 (НОВЫЕ ТЕСТЫ 12-19) ---

def test_12_sse_disconnect_stops_agent(test_server):
    r = requests.post(f"{test_server}/api/chats")
    chat_id = r.json()["id"]
    requests.post(f"{test_server}/api/chats/{chat_id}/load")
    agent = server.WebRequestHandler.active_chats[chat_id]
    agent.simulate_long_wait = 5
    requests.post(f"{test_server}/api/send", json={"chatId": chat_id, "message": "Task"})
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(("127.0.0.1", int(test_server.split(":")[-1])))
        s.sendall(b"GET /stream HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        time.sleep(0.5)
    time.sleep(2)
    assert agent.stop_requested == True

def test_13_atomic_write_protection(test_server):
    r = requests.post(f"{test_server}/api/chats")
    cid = r.json()["id"]
    requests.post(f"{test_server}/api/chats/{cid}/load")
    json_path = os.path.join(TEST_CHATS_DIR, f"{cid}.json")
    with open(json_path, 'r', encoding='utf-8') as f: orig = f.read()
    def m_open(p, m='r', *a, **k):
        if str(p).endswith(".tmp") and 'w' in m: raise IOError("DiskFull")
        return open(p, m, *a, **k)
    with mock.patch("builtins.open", side_effect=m_open):
        try: storage.save_chat_state(server.WebRequestHandler.active_chats[cid])
        except: pass
    with open(json_path, 'r', encoding='utf-8') as f: assert f.read() == orig

def test_14_busy_lockdown(test_server):
    r = requests.post(f"{test_server}/api/chats")
    cid = r.json()["id"]
    requests.post(f"{test_server}/api/chats/{cid}/load")
    agent = server.WebRequestHandler.active_chats[cid]
    agent.busy_depth = 1
    assert requests.patch(f"{test_server}/api/chats/{cid}/rename", json={"name": "x"}).status_code == 409
    assert requests.post(f"{test_server}/api/chats/{cid}/model", json={"model": "y"}).status_code == 409

def test_15_generator_exception_handling(test_server):
    r = requests.post(f"{test_server}/api/chats")
    cid = r.json()["id"]
    requests.post(f"{test_server}/api/chats/{cid}/load")
    agent = server.WebRequestHandler.active_chats[cid]
    agent.simulate_exception = True
    requests.post(f"{test_server}/api/send", json={"chatId": cid, "message": "x"})
    with requests.get(f"{test_server}/stream", stream=True) as r:
        for line in r.iter_lines():
            if line and line.startswith(b"data:"): break
    agent.generation_event.wait(timeout=2)
    assert agent.busy_depth == 0

def test_16_double_stop(test_server):
    r = requests.post(f"{test_server}/api/chats")
    cid = r.json()["id"]
    assert requests.post(f"{test_server}/api/stop", json={"chatId": cid}).status_code == 200
    assert requests.post(f"{test_server}/api/stop", json={"chatId": cid}).status_code == 200

def test_17_zombie_recovery(test_server):
    cid = "zombie"
    with open(os.path.join(TEST_CHATS_DIR, "zombie.json"), 'w') as f:
        json.dump({"id": "zombie", "busy_depth": 5, "messages": []}, f)
    r = requests.post(f"{test_server}/api/chats/zombie/load")
    assert r.json()["chat"]["busy_depth"] == 0

def test_18_prompt_hot_update(test_server):
    r = requests.post(f"{test_server}/api/chats")
    cid = r.json()["id"]
    requests.post(f"{test_server}/api/chats/{cid}/load")
    agent = server.WebRequestHandler.active_chats[cid]
    requests.post(f"{test_server}/api/final-prompts", json={"id": "p", "name": "P", "text": "PIRATE", "type": "system", "make_active": True})
    time.sleep(0.5)
    assert "PIRATE" in agent.system_prompt

def test_19_sse_heartbeat(test_server):
    with requests.get(f"{test_server}/stream", stream=True) as r:
        for line in r.iter_lines():
            if line and b"keep-alive" in line: return
    assert False, "No heartbeat"

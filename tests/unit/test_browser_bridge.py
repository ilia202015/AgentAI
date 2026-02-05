import os, sys, unittest
from unittest.mock import MagicMock, patch
import importlib.util
import time
import queue

builtins_print = print
def mock_print(*args, **kwargs):
    pass

bridge_path = os.path.abspath("sandbox/plugins/browser_use/bridge.py")
spec = importlib.util.spec_from_file_location("bridge", bridge_path)
bridge_module = importlib.util.module_from_spec(spec)
with patch('builtins.print', side_effect=mock_print):
    spec.loader.exec_module(bridge_module)

BrowserBridge = bridge_module.BrowserBridge

class TestBrowserBridge(unittest.TestCase):
    def setUp(self):
        bridge_module._bridge_instance = None
        self.print_patcher = patch('builtins.print', side_effect=mock_print)
        self.print_patcher.start()
        self.bridge = BrowserBridge()

    def tearDown(self):
        self.print_patcher.stop()

    def test_batch_command_structure(self):
        self.bridge.register()
        commands = [{"type": "click", "selector": "button"}]
        with patch.object(self.bridge, '_command_queue') as mock_queue:
            try:
                self.bridge.execute("execute_batch", {"commands": commands}, timeout=0.01)
            except:
                pass
            args, _ = mock_queue.put.call_args
            queued_cmd = args[0]
            self.assertEqual(queued_cmd["type"], "batch")
            self.assertEqual(queued_cmd["params"]["commands"], commands)

    def test_open_url_success(self):
        self.bridge.register()
        with patch('time.time', return_value=1000.0):
            request_id = "open_url_1000.0"
            def side_effect(*args, **kwargs):
                self.bridge._responses[request_id] = {"status": "complete", "result": "ok"}
            with patch.object(self.bridge._command_queue, 'put', side_effect=side_effect):
                result = self.bridge.execute("open_url", {"url": "http://example.com"})
                self.assertEqual(result.get("status"), "complete")

    def test_open_url_timeout(self):
        self.bridge.register()
        # Даем достаточное количество значений для time.time(), чтобы избежать StopIteration
        start_time = 1000.0
        # bridge.py вызывает time.time() в начале execute, затем в цикле while
        times = [start_time] * 10 + [start_time + 40] * 10
        with patch('time.time', side_effect=times):
            result = self.bridge.execute("open_url", {"url": "http://timeout.com"})
            self.assertEqual(result.get("error"), "timeout")

    def test_registration_loss(self):
        self.bridge.register()
        self.bridge._last_poll = time.time() - 100 
        result = self.bridge.execute("open_url", {"url": "http://lost.com"})
        self.assertIn("error", result)
        msg = result["error"].lower()
        self.assertTrue("registered" in msg or "lost" in msg)

if __name__ == "__main__":
    unittest.main()

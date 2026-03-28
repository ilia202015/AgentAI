import sys
import os
import time
import json
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent import ShellSession, Chat

def run_test_with_timeout(func, timeout_duration):
    result = []
    error = []
    
    def target():
        try:
            res = func()
            result.append(res)
        except Exception as e:
            error.append(e)

    t = threading.Thread(target=target)
    t.start()
    t.join(timeout_duration)
    
    if t.is_alive():
        print(f"TEST FAILED: Function {func.__name__} timed out after {timeout_duration}s")
        os._exit(1)
        
    if error:
        import traceback
        traceback.print_exception(type(error[0]), error[0], error[0].__traceback__)
        print(f"TEST FAILED: Exception in {func.__name__}: {error[0]}")
        sys.exit(1)
    
    return result[0] if result else None

def test_shell_session():
    # 1. Initialize
    session = ShellSession()
    time.sleep(1)
    session.read()
    
    if os.name == 'nt':
        cmd = "echo HELLO_TEST\n"
        persist_cmd1 = "set VAR123=ABC\n"
        persist_cmd2 = "echo %VAR123%\n"
    else:
        cmd = "echo HELLO_TEST\n"
        persist_cmd1 = "export VAR123=ABC\n"
        persist_cmd2 = "echo $VAR123\n"
        
    session.write(cmd)
    time.sleep(1)
    out = session.read()
    if 'HELLO_TEST' not in out['stdout']:
        print(f"TEST FAILED: Expected 'HELLO_TEST' in stdout, got {out}")
        sys.exit(1)
        
    session.write(persist_cmd1)
    time.sleep(0.5)
    session.read()
    session.write(persist_cmd2)
    time.sleep(1)
    out = session.read()
    if 'ABC' not in out['stdout']:
        print(f"TEST FAILED: Persistence failed. Expected 'ABC' in stdout, got {out}")
        sys.exit(1)
        
    if out['status'] is not None:
        print(f"TEST FAILED: Process exited unexpectedly, status: {out['status']}")
        sys.exit(1)
        
    if hasattr(session, 'close'):
        session.close()
    elif hasattr(session, 'process'):
        session.process.terminate()

def test_chat_shell_tool():
    chat = Chat()
    chat.print_to_console = False # Suppress logs
    
    # Run first command
    if os.name == 'nt':
        persist_cmd1 = "set VAR999=XYZ"
        persist_cmd2 = "echo %VAR999%"
    else:
        persist_cmd1 = "export VAR999=XYZ"
        persist_cmd2 = "echo $VAR999"
        
    res1 = chat.shell_tool(persist_cmd1)
    res1_dict = json.loads(res1)
    
    time.sleep(0.5)
    
    res2 = chat.shell_tool(persist_cmd2)
    res2_dict = json.loads(res2)
    
    if 'XYZ' not in res2_dict['stdout']:
        print(f"TEST FAILED: Chat shell_tool persistence failed. Expected 'XYZ', got {res2_dict}")
        sys.exit(1)

    # Clean up
    chat.shell_tool(action="interrupt")

    print("TEST PASSED")

if __name__ == '__main__':
    run_test_with_timeout(test_shell_session, 15)
    run_test_with_timeout(test_chat_shell_tool, 15)

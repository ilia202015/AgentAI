
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))
try:
    from agent import Chat
except ImportError:
    print("Cannot import Chat")
    sys.exit(1)

def test_get_shell_session():
    print("Starting session via chat...")
    try:
        chat = Chat()
        session = chat._get_shell_session()
    except Exception as e:
        print(f"Failed to create session: {e}")
        return False
    
    time.sleep(0.5)
    
    cmd1 = "echo TEST_VIA_CHAT"
    res1 = session.write(cmd1)
    time.sleep(0.5)
    out1 = session.read()
    
    if "TEST_VIA_CHAT" not in out1['stdout']:
        print(f"Failed to read cmd1 output: {out1}")
        return False
        
    return True

if __name__ == '__main__':
    if test_get_shell_session():
        sys.exit(0)
    else:
        sys.exit(1)

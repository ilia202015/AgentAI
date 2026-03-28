
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))
try:
    from agent import ShellSession
except ImportError:
    print("Cannot import ShellSession")
    sys.exit(1)

def test_shell_session():
    print("Starting session...")
    try:
        session = ShellSession()
    except Exception as e:
        print(f"Failed to create session: {e}")
        return False
    
    time.sleep(0.5)
    
    cmd1 = "echo START_TEST"
    print("Writing cmd1...")
    res1 = session.write(cmd1)
    if 'ОШИБКА' in res1 or 'Ошибка' in res1:
        print(f"Failed to write cmd1: {res1}")
        return False
    
    time.sleep(0.5)
    out1 = session.read()
    
    if "START_TEST" not in out1['stdout']:
        print(f"Failed to read cmd1 output: {out1}")
        return False
        
    cmd2 = "set TEST_VAR=12345" if os.name == 'nt' else "export TEST_VAR=12345"
    print("Writing cmd2...")
    session.write(cmd2)
    time.sleep(0.5)
    
    cmd3 = "echo %TEST_VAR%" if os.name == 'nt' else "echo $TEST_VAR"
    print("Writing cmd3...")
    session.write(cmd3)
    time.sleep(0.5)
    
    out3 = session.read()
    if "12345" not in out3['stdout']:
        print(f"Failed to read cmd3 output (persistence): {out3}")
        return False
        
    print("Closing session...")
    session.close()
    print("TEST PASSED")
    return True

if __name__ == '__main__':
    if test_shell_session():
        sys.exit(0)
    else:
        sys.exit(1)

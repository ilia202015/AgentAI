
import pytest
import json
import subprocess
from unittest.mock import MagicMock, patch

def test_validate_python_code(mock_agent):
    is_valid, msg = mock_agent.validate_python_code("print('hello')")
    assert is_valid is True
    is_valid, msg = mock_agent.validate_python_code("if True print('oops')")
    assert is_valid is False

def test_python_tool(mock_agent):
    res = mock_agent.python_tool("result = 10 + 5")
    assert res == "15"
    mock_agent.python_tool("x = 100")
    res = mock_agent.python_tool("result = x + 1")
    assert res == "101"
    res = mock_agent.python_tool("1 / 0")
    assert "ZeroDivisionError" in res

def test_tool_exec_python(mock_agent):
    res = mock_agent.tool_exec("python", {"code": "result = 'hello world'"})
    assert res == "hello world"

def test_tool_exec_dynamic_call(mock_agent, mocker):
    mock_agent.test_tool_tool = MagicMock(return_value="tool_result")
    mocker.patch.object(mock_agent, "_get_tools_dicts", return_value=(
        {"test_tool": ["arg1"]}, # required
        {"test_tool": ["arg2"]}  # additional
    ))
    res = mock_agent.tool_exec("test_tool", {"arg1": "val1", "arg2": "val2"})
    assert res == "tool_result"
    # Note: exec() interprets "'val1'" as the string 'val1'
    mock_agent.test_tool_tool.assert_called_once_with("val1", arg2="val2")

def test_shell_tool(mock_agent, mocker):
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stdout=b"success", stderr=b"")
    res = json.loads(mock_agent.shell_tool("echo 1"))
    assert res["returncode"] == 0
    assert res["stdout"].strip() == "success"
    
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="echo 1", timeout=120)
    res = json.loads(mock_agent.shell_tool("echo 1"))
    assert res["returncode"] == -1
    assert "была прервана" in res["stderr"]

def test_google_search_tool(mock_agent, mocker):
    mock_build = mocker.patch("googleapiclient.discovery.build")
    mock_service = mock_build.return_value
    mock_service.cse.return_value.list.return_value.execute.return_value = {
        "items": [{"title": "T", "link": "L", "snippet": "S"}]
    }
    res = json.loads(mock_agent.google_search_tool("q"))
    assert res[0]["title"] == "T"

def test_http_tool(mock_agent, mocker):
    mock_get = mocker.patch("requests.get")
    mock_response = MagicMock()
    mock_response.text = "<html><body><nav>M</nav><h1>T</h1><p>C</p></body></html>"
    mock_get.return_value = mock_response
    res = mock_agent.http_tool("u")
    assert "T" in res and "C" in res and "M" not in res

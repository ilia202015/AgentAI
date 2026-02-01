import pytest
import os
import html5lib

# Исправленные пути относительно корня проекта
FILES = [
    "plugins/web_interface/static/index.html"
]

def validate_html_strict(path):
    if not os.path.exists(path):
        pytest.fail(f"File {path} not found")
        
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    parser = html5lib.HTMLParser(strict=True)
    try:
        parser.parse(content)
    except Exception as e:
        raise SyntaxError(f"HTML Strict Validation Error in {path}:\n{str(e)}")

@pytest.mark.parametrize("file_path", FILES)
def test_html_syntax_strict(file_path):
    # Тест находится в tests/unit/, корень на 2 уровня выше
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    abs_path = os.path.join(root_dir, file_path)
    validate_html_strict(abs_path)

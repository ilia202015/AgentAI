
import os
import json
import subprocess
import pytest
import html.parser
import shutil

EXCLUDE_DIRS = {".git", "__pycache__", ".venv", "venv", "env", "node_modules", "libs", "chats", "sandbox", "temp"}
EXTENSIONS = {".py", ".json", ".html", ".js"}

def get_all_files():
    files_to_test = []
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    for root, dirs, files in os.walk(root_dir):
        # Filter directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in EXTENSIONS:
                full_path = os.path.join(root, file)
                # Store relative path for cleaner output
                rel_path = os.path.relpath(full_path, root_dir)
                files_to_test.append(rel_path)
    return files_to_test

FILES = get_all_files()

class SyntaxHTMLParser(html.parser.HTMLParser):
    def error(self, message):
        raise SyntaxError(message)

def validate_python(path):
    with open(path, 'r', encoding='utf-8') as f:
        source = f.read()
    compile(source, path, 'exec')

def validate_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        json.load(f)

def validate_html(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    parser = SyntaxHTMLParser()
    parser.feed(content)

def validate_js(path):
    if not shutil.which('node'):
        pytest.skip("Node.js not found in system, skipping JS validation")
    
    result = subprocess.run(['node', '-c', path], capture_output=True, text=True)
    if result.returncode != 0:
        raise SyntaxError(f"JS Syntax Error in {path}:\n{result.stderr}")

@pytest.mark.parametrize("file_path", FILES)
def test_file_syntax(file_path):
    # Ensure the path is absolute for validation functions
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    abs_path = os.path.join(root_dir, file_path)
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".py":
        validate_python(abs_path)
    elif ext == ".json":
        validate_json(abs_path)
    elif ext == ".html":
        validate_html(abs_path)
    elif ext == ".js":
        validate_js(abs_path)

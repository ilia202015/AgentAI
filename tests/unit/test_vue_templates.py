
import os
import re
import pytest

# Путь к компонентам
COMPONENTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../plugins/web_interface/static/js/components"))

def get_js_components():
    files = []
    if os.path.exists(COMPONENTS_DIR):
        for f in os.listdir(COMPONENTS_DIR):
            if f.endswith(".js"):
                files.append(os.path.join(COMPONENTS_DIR, f))
    return files

def extract_template(content):
    # Простой поиск template: `...`
    # Используем DOTALL, чтобы захватить многострочный шаблон
    match = re.search(r'template:\s*`([^`]+)`', content, re.DOTALL)
    return match.group(1) if match else None

@pytest.mark.parametrize("file_path", get_js_components())
def test_vue_template_interpolation(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    template = extract_template(content)
    if not template:
        # Если шаблона нет (или он не в backticks), пропускаем
        return

    # Ищем ${...}
    # Это грубая проверка, но для наших целей эффективная.
    # Если внутри шаблона есть ${var}, браузер попытается выполнить это как JS template string при загрузке файла.
    # В Vue шаблонах это НЕДОПУСТИМО (должно быть {{ var }}).
    
    # Исключение: внутри <script> тегов в шаблоне (если они есть), но в Vue components обычно их нет.
    
    matches = re.findall(r'(\$\{[^}]+\})', template)
    
    if matches:
        # Формируем сообщение об ошибке с контекстом
        errors = []
        for m in matches:
            # Находим строку с ошибкой для контекста
            lines = template.splitlines()
            for i, line in enumerate(lines):
                if m in line:
                    errors.append(f"Line {i+1}: {line.strip()}")
        
        if errors:
            pytest.fail(f"Found invalid JS interpolation ${{...}} in Vue template in {os.path.basename(file_path)}.\nUse {{{{...}}}} instead.\nErrors:\n" + "\n".join(errors))

if __name__ == "__main__":
    # Для ручного запуска
    files = get_js_components()
    for f in files:
        try:
            test_vue_template_interpolation(f)
            print(f"✅ {os.path.basename(f)} passed")
        except Exception as e:
            print(f"❌ {os.path.basename(f)} failed: {e}")

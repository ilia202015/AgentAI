import json
import os
import sys
import importlib.util
import traceback

# Добавляем текущую директорию в путь поиска модулей, чтобы найти agent.py
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from agent import Chat
except ImportError:
    # Если запускаем не из agent_ext, а из корня
    sys.path.append(os.path.join(current_dir, "."))
    from agent import Chat

# Список папок, которые мы всегда игнорируем (библиотеки, кэши, временные данные)
EXCLUDE_DIRS = {".git", "__pycache__", ".venv", "venv", "env", "node_modules", "libs", "chats", "sandbox"}

def load_plugins():
    config_path = os.path.join(current_dir, "plugin_config.json")
    if not os.path.exists(config_path):
        print(f"❌ Config not found: {config_path}")
        return

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return

    print("🤖 Инициализация главного чата...")
    chat = Chat()
    
    # === Внедрение системной информации (код start.py, конфиг, структура папок) ===
    print("📝 Сбор системной информации для промпта...")
    additional_info = "\n\n=== АВТОМАТИЧЕСКИ ДОБАВЛЕННАЯ ИНФОРМАЦИЯ ИЗ START.PY ===\n"

    # 1. Код самого start.py
    try:
        with open(__file__, 'r', encoding='utf-8') as f:
            additional_info += f"\nКод start.py:\n{f.read()}\n"
    except Exception as e:
        additional_info += f"\nОшибка чтения start.py: {e}\n"

    # 2. Содержимое plugin_config.json
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            additional_info += f"\nplugin_config.json:\n{f.read()}\n"
    except Exception as e:
        additional_info += f"\nОшибка чтения plugin_config.json: {e}\n"

    # 3. Структура папок и файлов
    additional_info += "\nСтруктура файлов (относительно корня):\n"
    try:
        for root, dirs, files in os.walk(current_dir):
            # Фильтрация папок (удаляем исключенные папки из списка обхода)
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            
            level = root.replace(current_dir, '').count(os.sep)
            indent = ' ' * 4 * level
            folder_name = os.path.basename(root)
            if folder_name:
                additional_info += f"{indent}{folder_name}/\n"
            else:
                 additional_info += f". (root)/\n"
                 
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                if not f.endswith(".pyc") and f != ".DS_Store": # Фильтр мусора
                    additional_info += f"{subindent}{f}\n"
    except Exception as e:
        additional_info += f"\nОшибка при сканировании структуры папок: {e}\n"

    # Применение изменений к промпту
    chat.system_prompt = additional_info + chat.system_prompt
    
    # Для совместимости, если вдруг messages уже заполнены
    if chat.messages and isinstance(chat.messages[0], dict) and chat.messages[0].get("role") == "system":
        chat.messages[0]["content"] = chat.system_prompt
        
    print("✅ Системный промпт обновлен (добавлены код загрузчика, конфиг и структура файлов).")
    # ==============================================================================

    plugins_dir = os.path.join(current_dir, "plugins")
    
    for plugin_name in config.get("list", []):
        plugin_path = os.path.join(plugins_dir, plugin_name)
        if not os.path.exists(plugin_path):
            print(f"⚠️ Plugin {plugin_name} not found at {plugin_path}")
            continue
            
        print(f"🔌 Загрузка плагина: {plugin_name}")
        
        try:
            init_path = os.path.join(plugin_path, "init.py")
            prompts_dir = os.path.join(plugin_path, "prompts")
            include_path = os.path.join(plugin_path, "include.py")
            
            # --- Сбор всех файлов плагина ---
            plugin_files_dump = ""
            for root, dirs, files in os.walk(plugin_path):
                # Фильтрация папок: исключаем библиотеки и папку prompts (т.к. она грузится отдельно)
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and d != "prompts"]
                
                for file in files:
                    if file.endswith(".pyc") or file == ".DS_Store": continue
                    
                    abs_path = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_path, plugin_path).replace("\\", "/")
                    
                    try:
                        with open(abs_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        chat.system_prompt = f"\n{plugin_name}/{rel_path}:\n{content}\n" + chat.system_prompt
                        plugin_files_dump += f"\n{plugin_name}/{rel_path}\n"
                    except Exception:
                        pass # Пропускаем бинарники и ошибки
            # --------------------------------

            # 1. Загрузка промптов (System Prompt Addition + Custom Prompts)
            system_prompt_addition = ""
            if os.path.exists(prompts_dir):
                for prompt_file in os.listdir(prompts_dir):
                    p_path = os.path.join(prompts_dir, prompt_file)
                    if os.path.isfile(p_path):
                        with open(p_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        if prompt_file == "system":
                            system_prompt_addition = content
                        else:
                            chat.prompts[prompt_file] = content
                            print(f"  - Промпт '{prompt_file}' загружен")

            # Формируем итоговую добавку в System Prompt для данного плагина
            full_plugin_info = f"\n\n=== Плагин {plugin_name} ===\n"
            if system_prompt_addition:
                full_plugin_info += f"[System Prompt из prompts/system]:\n{system_prompt_addition}\n"
            if plugin_files_dump:
                full_plugin_info += f"[Файлы плагина]:\n{plugin_files_dump}"
            
            chat.system_prompt += full_plugin_info
            
            # Обновляем системное сообщение если оно есть (обычно в Google GenAI messages пустые при старте, но на всякий случай)
            if chat.messages and isinstance(chat.messages[0], dict) and chat.messages[0].get("role") == "system":
                chat.messages[0]["content"] = chat.system_prompt
            
            print(f"  - Системный промпт обновлен (файлы плагина добавлены)")

            # 2. Выполнение include.py (функционал)
            if os.path.exists(include_path):
                with open(include_path, 'r', encoding='utf-8') as f:
                    include_code_exec = f.read()
                if include_code_exec:
                    print(f"include.py: result = {chat.python_tool(include_code_exec)}")
                    print(f"  - include.py выполнен")
                
            # 3. Инициализация через init.py
            if os.path.exists(init_path):
                spec = importlib.util.spec_from_file_location(f"plugins.{plugin_name}", init_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"plugins.{plugin_name}"] = module
                spec.loader.exec_module(module)
                
                if hasattr(module, 'main'):
                    settings = config.get("settings", {}).get(plugin_name, {})
                    print(f"  - Запуск main() плагина...")
                    chat = module.main(chat, settings)
                else:
                    print(f"  - Функция main() не найдена в init.py")

        except Exception as e:
            print(f"❌ Ошибка при загрузке плагина {plugin_name}: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    load_plugins()
    
    try:
        while True:
            input()
    except KeyboardInterrupt:
        print("\n👋 Программа завершена пользователем")
    except EOFError:
        print("\n👋 Программа завершена (Ctrl+D)")
    except Exception as e:
        print(f"\n💥 Критическая ошибка в плагине console_output: {e}")
        traceback.print_exc()

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
    sys.path.append(os.path.join(current_dir, "agent_ext"))
    from agent import Chat

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
    chat = Chat(print_to_console=True)
    
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

            with open(include_path, 'r', encoding='utf-8') as f:
                include_code = f.read()

            with open(init_path, 'r', encoding='utf-8') as f:
                init_code = f.read()

            # 1. Загрузка промптов
            if os.path.exists(prompts_dir):
                for prompt_file in os.listdir(prompts_dir):
                    p_path = os.path.join(prompts_dir, prompt_file)
                    if os.path.isfile(p_path):
                        with open(p_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        if prompt_file == "system":
                            chat.system_prompt += f"\n\nПлагин {plugin_name}:\n" + content + f"{plugin_name}/include.py:\n" + include_code + f"{plugin_name}/init.py:\n" + init_code
                            # Обновляем системное сообщение в истории сообщений (обычно это первое сообщение)
                            if chat.messages and chat.messages[0]["role"] == "system":
                                chat.messages[0]["content"] = chat.system_prompt
                            print(f"  - Системный промпт обновлен")
                        else:
                            chat.prompts[prompt_file] = content
                            print(f"  - Промпт '{prompt_file}' загружен")

            # 2. Выполнение include.py внутри чата
            if os.path.exists(include_path):
                chat.python_tool(include_code)
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

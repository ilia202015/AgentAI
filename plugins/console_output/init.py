import sys
import traceback

def main(chat, settings):
    print("🚀 AI-агент запущен (плагин console_output). Введите ваш запрос.")

    chat.print_to_console=True
    
    try:
        while True:
            try:
                user_input = input("\n👤 Вы: ")
            except UnicodeDecodeError:
                # Fallback для некоторых терминалов
                user_input = sys.stdin.readline().strip()
            
            if not user_input:
                continue
                
            chat.send({"role": "user", "content": user_input})
    except KeyboardInterrupt:
        print("\n👋 Программа завершена пользователем")
    except EOFError:
        print("\n👋 Программа завершена (Ctrl+D)")
    except Exception as e:
        print(f"\n💥 Критическая ошибка в плагине console_output: {e}")
        traceback.print_exc()
    
    return chat

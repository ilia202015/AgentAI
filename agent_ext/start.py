
import subprocess
import sys
import os

def check_streamlit():
    try:
        import streamlit
        return True
    except ImportError:
        return False

def main():
    if not check_streamlit():
        print("Ошибка: Streamlit не установлен.")
        print("Пожалуйста, установите его, выполнив команду:")
        print("pip install streamlit")
        sys.exit(1)

    script_path = os.path.join(os.path.dirname(__file__), 'streamlit', 'app.py')
    
    if not os.path.exists(script_path):
        print(f"Ошибка: Не найден файл приложения по пути: {script_path}")
        sys.exit(1)

    print("Запуск Streamlit приложения...")
    print(f"Чтобы остановить сервер, нажмите Ctrl+C в этом терминале.")
    
    try:
        subprocess.run(["streamlit", "run", script_path], check=True)
    except FileNotFoundError:
        print("Ошибка: Команда 'streamlit' не найдена.")
        print("Убедитесь, что Streamlit установлен и путь к его исполняемым файлам находится в системной переменной PATH.")
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при запуске Streamlit: {e}")
    except KeyboardInterrupt:
        print("\nСервер Streamlit остановлен.")

if __name__ == "__main__":
    main()

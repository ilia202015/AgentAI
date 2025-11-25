import logging
from agent import Chat # Импортируем класс из нового файла

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agent_ext/agent_ext.log')
    ]
)
logger = logging.getLogger(__name__)

def main():
    print("🚀 AI-агент запущен. Введите ваш запрос.")

    chat_agent = Chat()
    
    try:
        while True:
            user_input = input("\n👤 Вы: ")
            chat_agent.send({"role": "user", "content": user_input})
    except KeyboardInterrupt:
        print("\n👋 Программа завершена пользователем")
    except EOFError:
        print("\n👋 Программа завершена (Ctrl+D)")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        print(f"\n💥 Критическая ошибка: {e}")


if __name__ == "__main__":
    main()

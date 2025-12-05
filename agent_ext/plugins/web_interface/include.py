import queue
import types
import sys

# Создаем очередь для сообщений, если её нет
if not hasattr(self, 'web_queue'):
    self.web_queue = queue.Queue()

def web_print(self, message, count_tab=-1, **kwargs):
    # Получаем end (по умолчанию \n)
    end = kwargs.get('end', '\n')
    
    # Логика для консоли (сохраняем оригинальное поведение вывода)
    if count_tab == -1:
        count_tab = self.count_tab
    
    # Формируем сообщение для консоли с отступами
    if message != '':
        # Если message многострочный, добавляем табы
        console_msg = '\t' * count_tab + message.replace('\n', '\n' + '\t' * count_tab)
        # Вызываем встроенный print
        print(console_msg, **kwargs)
    elif end != '':
        # Если сообщение пустое, но есть end (например пустой print())
        print('\t' * count_tab, **kwargs)
    
    # Логика для веб-интерфейса
    if hasattr(self, 'web_queue'):
        # Отправляем полный текст с учетом end
        full_message = message + end
        self.web_queue.put(full_message)

# Подменяем методы
self.print = types.MethodType(web_print, self)
# print_thought тоже использует print, поэтому его трогать не обязательно, если он вызывает self.print
# Но в agent.py он определен как self.print_thought = print. 
# Лучше переопределить и его, чтобы он использовал наш новый self.print
self.print_thought = self.print

print("✅ Web Interface: Print methods hooked (with correct line endings).")

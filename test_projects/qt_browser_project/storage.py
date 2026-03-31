import os
import sqlite3
import datetime
import threading
import queue
from PyQt6.QtCore import QObject

class StorageManager(QObject):
    """
    Класс для управления хранением данных Lumina Browser.
    Обеспечивает асинхронную запись истории и кеширование закладок в памяти для мгновенного UI.
    """
    
    def __init__(self, db_path=None):
        super().__init__()
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, "userdata.db")
        
        self.db_path = db_path
        self._init_db()
        
        # Кеш закладок в памяти (Set) для мгновенной проверки is_bookmarked
        self._bookmarks_cache = set()
        self._load_bookmarks_to_cache()
        
        # Очередь для задач записи истории (тяжелые операции)
        self.task_queue = queue.Queue()
        self._stop_event = threading.Event()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        # Очистка старых данных
        self.clear_old_history()
        self._history_counter = 0  # Счетчик для периодической обрезки истории

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Инициализация БД и создание индексов."""
        try:
            with self._get_connection() as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT NOT NULL,
                        title TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS bookmarks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT NOT NULL UNIQUE,
                        title TEXT,
                        date_added DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_time ON history(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_url ON history(url)")
                conn.commit()
        except sqlite3.Error as e:
            print(f"Storage Error during initialization: {e}")

    def _load_bookmarks_to_cache(self):
        """Загружает все URL закладок в память при запуске."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT url FROM bookmarks")
                self._bookmarks_cache = {row[0] for row in cursor.fetchall()}
        except sqlite3.Error as e:
            print(f"Storage Error loading cache: {e}")

    def _worker_loop(self):
        """Фоновый цикл для обработки задач из очереди с переиспользованием соединения."""
        conn = self._get_connection()
        while not self._stop_event.is_set():
            try:
                task = self.task_queue.get(timeout=1.0)
                if task is None:
                    break
                
                try:
                    func, args, kwargs = task
                    func(conn, *args, **kwargs)
                except Exception as e:
                    print(f"DB Execution Error: {e}")
                finally:
                    self.task_queue.task_done() # Гарантированный вызов для предотвращения Queue Leak
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Async Storage Worker Loop Error: {e}")
        conn.close()

    def shutdown(self):
        """Graceful shutdown для воркера БД."""
        self._stop_event.set()
        self.task_queue.put(None)
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)

    def add_history_entry(self, url, title):
        """Асинхронная запись в историю."""
        if self._stop_event.is_set() or not url or url == "about:blank":
            return
        timestamp = datetime.datetime.now().isoformat()
        self.task_queue.put((self._db_add_history, (url, title, timestamp), {}))

    def _db_add_history(self, conn, url, title, timestamp):
        """
        Запись истории с защитой от дубликатов (History Flood) и ограничением на 5000 записей.
        """
        try:
            cursor = conn.cursor()
            
            # 1. Проверяем последнюю запись, чтобы не плодить дубликаты при переходах Назад/Вперед
            cursor.execute("SELECT id, url FROM history ORDER BY id DESC LIMIT 1")
            last_entry = cursor.fetchone()
            
            if last_entry and last_entry[1] == url:
                # Если URL совпадает с последним, просто обновляем время и заголовок
                cursor.execute("UPDATE history SET timestamp = ?, title = ? WHERE id = ?", 
                             (timestamp, title, last_entry[0]))
            else:
                # Иначе вставляем новую запись
                cursor.execute(
                    "INSERT INTO history (url, title, timestamp) VALUES (?, ?, ?)",
                    (url, title, timestamp)
                )
            
            # 2. Периодическая обрезка истории (раз в 50 записей) для экономии ресурсов
            self._history_counter += 1
            if self._history_counter >= 50:
                cursor.execute("""
                    DELETE FROM history 
                    WHERE id NOT IN (
                        SELECT id FROM history ORDER BY timestamp DESC LIMIT 5000
                    )
                """)
                self._history_counter = 0
            
            conn.commit()
        except sqlite3.Error as e:
            print(f"DB Error (History): {e}")

    def add_bookmark(self, url, title):
        """Добавление в кеш (синхронно) и в БД (асинхронно)."""
        if self._stop_event.is_set() or not url: return
        self._bookmarks_cache.add(url) # Мгновенное обновление для UI
        self.task_queue.put((self._db_add_bookmark, (url, title), {}))

    def _db_add_bookmark(self, conn, url, title):
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bookmarks (url, title) 
                VALUES (?, ?) 
                ON CONFLICT(url) DO UPDATE SET title=excluded.title
            """, (url, title))
            conn.commit()
        except sqlite3.Error as e:
            print(f"DB Error (Add Bookmark): {e}")

    def delete_bookmark(self, url):
        """Удаление из кеша (синхронно) и из БД (асинхронно)."""
        if self._stop_event.is_set() or not url: return
        self._bookmarks_cache.discard(url) # Мгновенное обновление для UI
        self.task_queue.put((self._db_delete_bookmark, (url,), {}))

    def _db_delete_bookmark(self, conn, url):
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM bookmarks WHERE url = ?", (url,))
            conn.commit()
        except sqlite3.Error as e:
            print(f"DB Error (Delete Bookmark): {e}")

    def is_bookmarked(self, url):
        """Мгновенная проверка статуса через кеш в памяти."""
        return url in self._bookmarks_cache

    def get_recent_history(self, limit=100):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT url, title, timestamp FROM history ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                )
                return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Storage Error (get_recent_history): {e}")
            return []

    def get_bookmarks(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT url, title FROM bookmarks ORDER BY date_added DESC")
                return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Storage Error (get_bookmarks): {e}")
            return []

    def clear_old_history(self, days=30):
        self.task_queue.put((self._db_clear_old_history, (days,), {}))

    def _db_clear_old_history(self, conn, days):
        try:
            date_limit = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM history WHERE timestamp < ?", (date_limit,))
            conn.commit()
        except sqlite3.Error as e:
            print(f"DB Error (Clear Old History): {e}")

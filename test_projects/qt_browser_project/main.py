import sys
import os
import time
import traceback

# 1. Базовые механизмы (QtCore) - Добавлен QUrlQuery
from PyQt6.QtCore import QUrl, QUrlQuery, Qt, QSize, pyqtSignal, pyqtSlot, QTimer

# 2. Графические ресурсы, действия и горячие клавиши (QtGui)
from PyQt6.QtGui import QAction, QShortcut, QKeySequence, QIcon, QPixmap

# 3. Виджеты интерфейса (QtWidgets)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QToolBar, QToolButton,
    QLineEdit, QProgressBar, QVBoxLayout, QWidget, QStyle,
    QMenu, QMessageBox, QSizePolicy, QStatusBar
)

# 4. Веб-движок (QtWebEngine)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings

# 5. Модуль базы данных (локальный)
try:
    from storage import StorageManager
except ImportError:
    # На случай, если структура папок изменится при запуске из корня
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from storage import StorageManager

class BrowserTab(QWebEngineView):
    """
    Индивидуальная вкладка браузера на базе QWebEngineView.
    Инкапсулирует логику отображения контента и обработки событий Chromium.
    """
    tab_title_changed = pyqtSignal(str)
    tab_url_changed = pyqtSignal(QUrl)
    tab_load_progress = pyqtSignal(int)
    tab_icon_changed = pyqtSignal(QIcon)
    tab_load_finished = pyqtSignal(bool)

    def __init__(self, profile=None):
        super().__init__()
        self.current_progress = 0
        
        # Настройка страницы с привязкой к профилю
        page = QWebEnginePage(profile if profile else QWebEngineProfile.defaultProfile(), self)
        self.setPage(page)
        
        # Проброс стандартных сигналов
        self.titleChanged.connect(self.tab_title_changed.emit)
        self.urlChanged.connect(self.tab_url_changed.emit)
        self.loadProgress.connect(self.tab_load_progress.emit)
        self.iconChanged.connect(self.tab_icon_changed.emit)
        self.loadFinished.connect(self.tab_load_finished.emit)
        
        # Обработка падения процесса рендеринга (Fix: Render Crash)
        self.renderProcessTerminated.connect(self.on_render_crash)
        
        # Обработка запросов на разрешения (камера, микрофон и т.д.)
        self.page().featurePermissionRequested.connect(self.on_feature_permission_requested)


    def createWindow(self, type):
        """Перенаправление всплывающих окон в новые вкладки."""
        # Находим главное окно через иерархию (или используем parent)
        main_window = self.window()
        if hasattr(main_window, 'add_new_tab'):
            return main_window.add_new_tab()
        return super().createWindow(type)

    def on_render_crash(self, termination_status, exit_code):
        """Обработка критической ошибки процесса рендеринга страницы."""
        status_map = {
            QWebEnginePage.RenderProcessTerminationStatus.NormalTerminationStatus: "Завершено нормально",
            QWebEnginePage.RenderProcessTerminationStatus.AbnormalTerminationStatus: "Аварийное завершение",
            QWebEnginePage.RenderProcessTerminationStatus.CrashedTerminationStatus: "Процесс упал (Crash)",
            QWebEnginePage.RenderProcessTerminationStatus.KilledTerminationStatus: "Процесс убит ОС"
        }
        status_text = status_map.get(termination_status, "Неизвестная ошибка")
        
        error_html = f"""
        <div style='text-align: center; padding-top: 50px; font-family: sans-serif;'>
            <h1>📉 Ой, вкладка упала!</h1>
            <p>Процесс отображения страницы завершился с ошибкой: <b>{status_text}</b> (Код: {exit_code})</p>
            <button onclick='window.location.reload()'>Обновить страницу</button>
        </div>
        """
        self.setHtml(error_html)

    def on_feature_permission_requested(self, url, feature):
        """Базовая политика безопасности для разрешений (по умолчанию запрещаем)."""
        # В будущем здесь можно реализовать диалоговое окно запроса
        self.page().setFeaturePermission(url, feature, QWebEnginePage.PermissionPolicy.PermissionDeniedByUser)

    def safe_close(self):
        """Безопасное высвобождение ресурсов перед удалением вкладки."""
        self.stop()
        # Отключаем все сигналы для предотвращения вызовов к удаляемому объекту
        try:
            self.titleChanged.disconnect()
            self.urlChanged.disconnect()
            self.loadProgress.disconnect()
            self.iconChanged.disconnect()
            self.loadFinished.disconnect()
            self.renderProcessTerminated.disconnect()
        except:
            pass
        
        # Удаляем страницу вручную для чистоты памяти
        old_page = self.page()
        self.setPage(QWebEnginePage(None))
        old_page.deleteLater()
        self.deleteLater()

class MainWindow(QMainWindow):
    """
    Главное окно браузера Lumina.
    Управляет набором вкладок и общей конфигурацией приложения.
    """
    APP_NAME = "Lumina Browser"
    SEARCH_ENGINE_BASE_URL = "https://www.google.com/search"
    

    def __init__(self):
        super().__init__()

        self.setWindowTitle(self.APP_NAME)
        self.resize(1200, 800)


        # Глобальный стиль приложения
        
        # Загрузка стилей из внешнего файла QSS
        qss_path = os.path.join(os.path.dirname(__file__), "style.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
    


        # Определение путей относительно скрипта
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.user_data_dir = os.path.join(self.base_dir, "userdata")
        os.makedirs(self.user_data_dir, exist_ok=True)
        self.storage = StorageManager(os.path.join(self.user_data_dir, "userdata.db"))

        
        self.setup_profile()

        # Навигационная панель (Navigation Bar)
        self.nav_bar = QToolBar("Navigation")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.nav_bar)
        self.nav_bar.setMovable(False)
        self.nav_bar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)

        # Кнопки навигации
        self.back_btn = QToolButton()
        self.back_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack))
        self.back_btn.setToolTip("Назад")
        self.back_btn.clicked.connect(lambda: self.current_browser().back() if self.current_browser() else None)
        self.nav_bar.addWidget(self.back_btn)

        self.forward_btn = QToolButton()
        self.forward_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward))
        self.forward_btn.setToolTip("Вперед")
        self.forward_btn.clicked.connect(lambda: self.current_browser().forward() if self.current_browser() else None)
        self.nav_bar.addWidget(self.forward_btn)

        self.reload_btn = QToolButton()
        self.reload_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.reload_btn.setToolTip("Обновить")
        self.reload_btn.clicked.connect(lambda: self.current_browser().reload() if self.current_browser() else None)
        self.nav_bar.addWidget(self.reload_btn)

        self.home_btn = QToolButton()
        self.home_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirHomeIcon))
        self.home_btn.setToolTip("Домой")
        self.home_btn.clicked.connect(self.navigate_home)
        self.nav_bar.addWidget(self.home_btn)

        self.nav_bar.addSeparator()

        # Адресная строка (Address Bar)
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Введите URL или запрос для поиска...")
        self.url_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.nav_bar.addWidget(self.url_bar)
        self.bookmark_btn = QToolButton()
        self.bookmark_btn.setCheckable(True)
        self.bookmark_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton))
        self.bookmark_btn.setToolTip("Добавить в закладки")
        self.bookmark_btn.clicked.connect(self.toggle_bookmark)
        self.nav_bar.addWidget(self.bookmark_btn)

        # Индикатор загрузки (Progress Bar)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(3)
        self.progress_bar.setTextVisible(False)

        self.progress_bar.hide()
        # self.statusBar().addPermanentWidget(self.progress_bar)

        # Настройка контейнера вкладок
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.current_tab_changed)
        
        # Кнопка быстрой вкладки
        self.add_button = QToolButton()
        self.add_button.setText("+")
        self.add_button.setToolTip("Открыть новую вкладку")
        self.add_button.clicked.connect(lambda: self.add_new_tab())
        self.tabs.setCornerWidget(self.add_button, Qt.Corner.TopRightCorner)

        
        # Компоновка центральной части (Progress Bar + Tabs)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.tabs)
        self.setCentralWidget(container)
        
        # Горячие клавиши (Shortcuts)
        QShortcut("Ctrl+L", self).activated.connect(self.url_bar.setFocus)
        QShortcut("Ctrl+T", self).activated.connect(lambda: self.add_new_tab())
        QShortcut("Ctrl+W", self).activated.connect(lambda: self.close_tab(self.tabs.currentIndex()))
        QShortcut("Ctrl+R", self).activated.connect(lambda: self.current_browser().reload() if self.current_browser() else None)
        
        # Начальная загрузка
        self.add_new_tab(QUrl("https://www.google.com"), "Google")

    def _connect_tab_signals(self, browser):
        """Централизованное связывание сигналов вкладки с логикой окна."""
        browser.tab_title_changed.connect(lambda t: self._sync_tab_metadata(browser, title=t))
        browser.tab_icon_changed.connect(lambda i: self._sync_tab_metadata(browser, icon=i))
        browser.tab_url_changed.connect(lambda u: self.on_url_changed(browser, u))
        browser.urlChanged.connect(lambda u: self.update_nav_buttons(browser))
        browser.tab_load_finished.connect(lambda ok: self.on_load_finished(browser, ok))
        browser.loadStarted.connect(lambda: self.on_load_started(browser))
        browser.tab_load_progress.connect(lambda p: self.on_progress_update(browser, p))

    def _sync_tab_metadata(self, browser, title=None, icon=None):
        """Обновление текста и иконки вкладки с синхронизацией заголовка окна."""
        index = self.tabs.indexOf(browser)
        if index == -1: return
        
        if title is not None:
            # Обрезка заголовка для вкладки
            display_title = title[:25] + "..." if len(title) > 25 else title
            self.tabs.setTabText(index, display_title or "New Tab")
            if self.tabs.currentIndex() == index:
                self.update_window_title(title)
        
        if icon is not None:
            self.tabs.setTabIcon(index, icon)

    def toggle_bookmark(self):
        browser = self.current_browser()
        if not browser: return
        url = browser.url().toString()
        title = browser.title()
        if self.storage.is_bookmarked(url):
            self.storage.delete_bookmark(url)
        else:
            self.storage.add_bookmark(url, title)
        self.update_bookmark_button(browser)
        status = "сохранена в закладки" if self.storage.is_bookmarked(url) else "удалена из закладок"
        self.statusBar().showMessage(f"Страница {status}", 3000)

    def update_bookmark_button(self, browser):
        if not browser or browser != self.current_browser(): return
        is_saved = self.storage.is_bookmarked(browser.url().toString())
        self.bookmark_btn.setChecked(is_saved)
        icon_type = QStyle.StandardPixmap.SP_DialogYesButton if is_saved else QStyle.StandardPixmap.SP_DialogNoButton
        self.bookmark_btn.setIcon(self.style().standardIcon(icon_type))
        self.bookmark_btn.setToolTip("Удалить из закладок" if is_saved else "Добавить в закладки")

    def navigate_to_url(self):
        """Интеллектуальный переход по адресу или поиск (Omnibox)."""
        text = self.url_bar.text().strip()
        if not text:
            return

        # Используем QUrl.fromUserInput для базовой обработки
        url = QUrl.fromUserInput(text)
        
        # Если в хосте нет точки и это не localhost - считаем это поисковым запросом
        is_search = not (url.host() and "." in url.host()) and "localhost" not in text.lower() and "://" not in text
        
        if is_search:
            # Используем QUrlQuery для безопасного кодирования параметров поиска
            url = QUrl(self.SEARCH_ENGINE_BASE_URL)
            query = QUrlQuery()
            query.addQueryItem("q", text)
            url.setQuery(query)
        
        browser = self.current_browser()
        if browser:
            browser.setUrl(url)

    def current_browser(self):
        """Возвращает текущий активный BrowserTab."""
        return self.tabs.currentWidget()

    def navigate_home(self):
        """Переход на домашнюю страницу (Google по умолчанию)."""
        browser = self.current_browser()
        if browser:
            browser.setUrl(QUrl("https://www.google.com"))

    def setup_profile(self):
        """Настройка изолированного профиля и параметров безопасности."""
        storage_path = os.path.join(self.user_data_dir, "storage")
        cache_path = os.path.join(self.user_data_dir, "cache")
        os.makedirs(storage_path, exist_ok=True)
        os.makedirs(cache_path, exist_ok=True)

        self.profile = QWebEngineProfile("LuminaMainProfile", self)
        self.profile.setPersistentStoragePath(storage_path)
        self.profile.setCachePath(cache_path)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)

        settings = self.profile.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.FocusOnNavigationEnabled, True)

    def add_new_tab(self, qurl=None, label="New Tab"):
        """Создание и регистрация новой вкладки."""
        if qurl is None or qurl.isEmpty():
            qurl = QUrl("about:blank")
        
        try:
            browser = BrowserTab(self.profile)
            browser.setUrl(qurl)
            
            index = self.tabs.addTab(browser, label)
            self.tabs.setCurrentIndex(index)
            self.url_bar.setFocus()
            self.url_bar.selectAll()
            
            self._connect_tab_signals(browser)
            return browser
        except Exception:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать вкладку:\n{traceback.format_exc()}")
            return None

    def update_nav_buttons(self, browser):
        """Обновление активности кнопок навигации."""
        if browser == self.current_browser():
            history = browser.page().history()
            self.back_btn.setEnabled(history.canGoBack())
            self.forward_btn.setEnabled(history.canGoForward())

    def on_url_changed(self, browser, url):
        """Синхронизация адресной строки и кнопки закладок."""
        self.update_bookmark_button(browser)
        if browser == self.current_browser():
            self.url_bar.setText(url.toString())
            self.url_bar.setCursorPosition(0)
            self.update_nav_buttons(browser)

    def on_load_started(self, browser):
        """Показать прогресс-бар при начале загрузки."""
        if browser == self.current_browser():
            browser.current_progress = 0
            self.progress_bar.setValue(0)
            self.progress_bar.show()

    def on_progress_update(self, browser, progress):
        """Обновить значение прогресс-бара."""
        browser.current_progress = progress
        if browser == self.current_browser():
            self.progress_bar.setValue(progress)
            if progress < 100:
                self.progress_bar.show()

    def on_load_finished(self, browser, success):
        """Завершение загрузки: сохранение истории и обновление UI."""
        if success:
            self.storage.add_history_entry(browser.url().toString(), browser.title())
        browser.current_progress = 100
        if browser == self.current_browser():
            self.progress_bar.hide()
            # Обновляем URL только если пользователь сейчас не вводит адрес вручную
            if not self.url_bar.hasFocus():
                self.url_bar.setText(browser.url().toString())
                self.url_bar.setCursorPosition(0)
            self.update_nav_buttons(browser)

    def current_tab_changed(self, index):
        """Синхронизация состояния при переключении вкладок."""
        if index == -1: return
        browser = self.tabs.widget(index)
        self.update_bookmark_button(browser)
        if isinstance(browser, BrowserTab):
            self.update_window_title(browser.title())
            self.url_bar.setText(browser.url().toString())
            self.url_bar.setCursorPosition(0)
            self.update_nav_buttons(browser)
            
            # Восстановление состояния прогресс-бара
            if browser.current_progress < 100:
                self.progress_bar.setValue(browser.current_progress)
                self.progress_bar.show()
            else:
                self.progress_bar.hide()
            
            browser.setFocus()

    def update_window_title(self, title):
        """Смена заголовка основного окна."""
        if title:
            self.setWindowTitle(f"{title} - {self.APP_NAME}")
        else:
            self.setWindowTitle(self.APP_NAME)

    def close_tab(self, index):
        """Закрытие вкладки."""
        if self.tabs.count() > 1:
            browser = self.tabs.widget(index)
            if isinstance(browser, BrowserTab):
                self.tabs.removeTab(index)
                browser.safe_close()
        else:
            browser = self.tabs.widget(index)
            if isinstance(browser, BrowserTab):
                browser.setUrl(QUrl("about:blank"))
                self.tabs.setTabText(index, "New Tab")
                self.tabs.setTabIcon(index, QIcon())
                self.update_window_title("")

    def closeEvent(self, event):
        """Graceful shutdown при закрытии приложения."""
        if hasattr(self, 'storage'):
            self.storage.shutdown()
        event.accept()

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("Lumina Browser")
        
        # Проверка совместимости
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            print("ОШИБКА: Модуль QtWebEngine не найден. Установите его: pip install PyQt6-WebEngine")
            sys.exit(1)

        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception:
        print(f"КРИТИЧЕСКИЙ СБОЙ ПРИ ЗАПУСКЕ:\n{traceback.format_exc()}")
        sys.exit(1)

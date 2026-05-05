
import os
import time
import threading
import http.server
import socketserver
import io
from PIL import Image
from playwright.sync_api import sync_playwright

PORT = 8081
DIRECTORY = "./"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    def log_message(self, format, *args):
        pass

def start_server():
    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"Сервер запущен на порту {PORT}")
            httpd.serve_forever()
    except OSError:
        pass # Порт уже занят, ничего страшного

def generate_pdf():
    print("Генерация PDF из скриншотов...")
    pdf_path = "Presentation_Crisp_Images.pdf"
    images = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Настраиваем контекст: viewport 1280x720, но device_scale_factor=2.0
        # В итоге скриншоты будут 1920x1080 (Full HD)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            device_scale_factor=3
        )
        page = context.new_page()

        page.goto(f"http://localhost:{PORT}/index.html", wait_until="load", timeout=60000)

        print("Ожидание отрисовки...")
        
        # Ждем загрузки слайдов (через переменную window.loadedSlidesCount)
        try:
            page.wait_for_function("window.loadedSlidesCount > 0", timeout=10000)
        except Exception:
            page.wait_for_timeout(5000)

        # Выключаем UI
        page.evaluate("if (document.getElementById('presentation-controls')) document.getElementById('presentation-controls').style.display = 'none';")
        
        # Отключаем режим презентации, чтобы все слайды отображались списком
        page.evaluate("document.body.classList.remove('presentation-mode');")
        page.wait_for_timeout(1000)

        # Находим все элементы .slide-page
        slide_elements = page.query_selector_all('.slide-page')
        loaded_count = len(slide_elements)
        print(f"Найдено слайдов: {loaded_count}")

        if loaded_count == 0:
            print("Слайды не найдены! Проверьте загрузку.")
            browser.close()
            return

        for i, slide in enumerate(slide_elements):
            print(f"Снятие скриншота слайда {i+1}...")
            # Снимаем растровый скриншот конкретно DOM-элемента слайда
            screenshot_bytes = slide.screenshot(type='png')
            img = Image.open(io.BytesIO(screenshot_bytes))
            img = img.convert('RGB')
            images.append(img)

        browser.close()

    if images:
        images[0].save(
            pdf_path,
            "PDF",
            resolution=100.0,
            save_all=True,
            append_images=images[1:]
        )
        print(f"Успешно сохранено в {pdf_path}")

if __name__ == "__main__":
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    time.sleep(1)
    
    try:
        generate_pdf()
    except Exception as e:
        print(f"Ошибка при генерации PDF: {e}")

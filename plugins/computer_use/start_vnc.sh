#!/bin/bash
export DISPLAY=:99

echo "Очистка окружения..."
killall Xvfb x11vnc websockify fluxbox google-chrome-stable chromium-browser 2>/dev/null
rm -f /tmp/.X99-lock

echo "Запуск Xvfb..."
Xvfb :99 -screen 0 1280x800x24 &
XVFB_PID=$!
sleep 2

if ! kill -0 $XVFB_PID 2>/dev/null; then
    echo "Ошибка: Xvfb не запустился"
    exit 1
fi

echo "Запуск Fluxbox..."
fluxbox &
sleep 1

echo "Запуск VNC и noVNC..."
env -u WAYLAND_DISPLAY x11vnc -display :99 -nopw -listen 0.0.0.0 -xkb -forever &
websockify --web /usr/share/novnc 6080 0.0.0.0:5900 &

echo "Запуск Google Chrome..."
google-chrome-stable --password-store=basic --no-sandbox --test-type --window-position=0,0 --window-size=1280,800 --start-maximized &

echo "Ожидание окна браузера для позиционирования..."
sleep 5
wmctrl -r "Google Chrome" -e 0,0,0,1280,800 2>/dev/null || true
wmctrl -r "Google Chrome" -b add,maximized_vert,maximized_horz 2>/dev/null || true

echo "Окружение успешно запущено!"
tail -f /dev/null

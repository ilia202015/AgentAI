import sys

# Выбор бэкенда для выполнения команд
BACKEND = "wsl" # варианты: "windows_base", "wsl", "browser_use"

if BACKEND == "windows_base":
    from .tools_windows_base import *
elif BACKEND == "wsl":
    from .tools_wsl import *
else:
    raise ValueError(f"Unknown computer_use BACKEND: {BACKEND}")

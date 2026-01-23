import uiautomation as auto
import ctypes
import time

def get_dpi_scaling():
    """Возвращает коэффициент масштабирования DPI для Windows."""
    try:
        # Для Windows 10+ корректный способ получить DPI
        shcore = ctypes.windll.shcore
        shcore.SetProcessDpiAwareness(1) 
        return 1.0 # По умолчанию, если не удастся высчитать
    except:
        return 1.0

def get_element_at(x, y):
    """Находит элемент управления UI Automation по указанным координатам."""
    try:
        auto.SetGlobalSearchTimeout(0.5)
        element = auto.ElementFromPoint(x, y)
        return element
    except:
        return None

def find_clickable_parent(element):
    """Ищет ближайшего кликабельного предка."""
    if not element: return None
    curr = element
    # Список типов, которые точно кликабельны
    clickable_types = ["ButtonControl", "MenuItemControl", "HyperlinkControl", "ListItemControl", "TabItemControl", "CheckBoxControl"]
    for _ in range(5):
        if curr.ControlTypeName in clickable_types or curr.IsPassword:
            return curr
        try:
            curr = curr.GetParentControl()
        except: break
        if not curr: break
    return element

def smart_type(x, y, text, press_enter=True, clear=True):
    """Пытается сфокусироваться и ввести текст системно."""
    el = get_element_at(x, y)
    if el:
        target = find_clickable_parent(el)
        try:
            target.SetFocus()
            if clear:
                # Системная очистка через ValuePattern если возможно
                if hasattr(target, "GetValuePattern"):
                    target.GetValuePattern().SetValue("")
            return False # Возвращаем False, чтобы PyAutoGUI допечатал текст (надежнее для раскладок)
        except:
            pass
    return False

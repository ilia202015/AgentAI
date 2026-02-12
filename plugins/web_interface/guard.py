import os
import sys
import re
from pathlib import Path
import contextvars
import traceback

# Флаги разрешений:
# r - read
# w - write
# x - execute (shell/subprocess)
# l - list (os.listdir)
# d - delete (unlink/rmdir)

# Контекст безопасности для текущего потока/задачи
security_context = contextvars.ContextVar('security_context', default=None)

class GuardViolation(RuntimeError):
    """Исключение при нарушении безопасности."""
    pass

def normalize_path(path):
    """Приводит путь к абсолютному каноническому виду относительно корня проекта."""
    try:
        p = Path(str(path))
        # Если путь относительный, считаем его от корня проекта
        if not p.is_absolute():
            p = (Path.cwd() / p)
        return p.resolve()
    except Exception:
        return Path(os.path.abspath(str(path)))

def get_permissions(path, config):
    """
    Реализует иерархический поиск разрешений (Bubble-up).
    """
    if not config:
        return ""
        
    target = normalize_path(path)
    root = Path.cwd().resolve()
    
    # Собираем список проверяемых путей: от самого длинного к корню
    check_paths = [target] + list(target.parents)
    
    paths_config = config.get('paths', {})
    
    for p in check_paths:
        try:
            rel_p = str(p.relative_to(root)).replace("\\", "/")
            if rel_p == ".": rel_p = ""
        except ValueError:
            rel_p = str(p).replace("\\", "/")

        if rel_p in paths_config:
            return paths_config[rel_p]
        if rel_p + "/" in paths_config:
            return paths_config[rel_p + "/"]

    return config.get('global', "")

def intersect_flags(s1, s2):
    """Возвращает пересечение флагов (только те, что есть в обоих строках)."""
    if s1 is None or s2 is None: return ""
    return "".join(c for c in s1 if c in s2)

def intersect_acl_configs(configs):
    """
    Реализует строгое пересечение списка конфигураций ACL.
    Итоговые права = Права(Config1) ∩ Права(Config2) ∩ ...
    """
    if not configs:
        return {"global": "", "paths": {}}
    
    # Фильтруем пустые конфиги (трактуем None как запрет всего)
    valid_configs = [c if c else {"global": "", "paths": {}} for c in configs]
    
    # 1. Пересечение Global
    res_global = valid_configs[0].get("global", "")
    for c in valid_configs[1:]:
        res_global = intersect_flags(res_global, c.get("global", ""))
        
    # 2. Пересечение путей
    all_path_keys = set()
    for c in valid_configs:
        all_path_keys.update(c.get("paths", {}).keys())
        
    res_paths = {}
    for path in all_path_keys:
        # Для каждого уникального пути вычисляем эффективные права в каждом конфиге
        # (с учетом наследования от родительских папок или global)
        effective_perms = [get_permissions(path, c) for c in valid_configs]
        
        # Пересекаем полученные права
        p_flags = effective_perms[0]
        for f in effective_perms[1:]:
            p_flags = intersect_flags(p_flags, f)
        
        # Сохраняем только если права отличаются от итогового global (для лаконичности)
        # или если это важный узел. Но для безопасности лучше сохранить все явно.
        res_paths[path] = p_flags
        
    return {"global": res_global, "paths": res_paths}

def check_access(path, required_mode):
    """Основная функция проверки доступа."""
    ctx = security_context.get()
    if ctx is None:
        return True
        
    perms = get_permissions(path, ctx)
    if required_mode.lower() in perms.lower():
        return True
        
    return False

def audit_hook(event, args):
    """Хук аудита Python."""
    if security_context.get() is None:
        return

    try:
        if event in ("open", "os.open"):
            path = args[0]
            mode = args[1] if len(args) > 1 else "r"
            req = 'w' if any(c in str(mode) for c in "wa+") else 'r'
            if not check_access(path, req):
                raise GuardViolation(f"[Security] Access Denied: '{req}' permission required for {path}")
        
        elif event == "os.listdir":
            if not check_access(args[0], 'l'):
                raise GuardViolation(f"[Security] Access Denied: 'l' permission required for {args[0]}")
        
        elif event in ("os.remove", "os.unlink", "os.rmdir", "shutil.rmtree"):
            if not check_access(args[0], 'd'):
                raise GuardViolation(f"[Security] Access Denied: 'd' permission required for {args[0]}")
                
        elif event in ("subprocess.Popen", "os.system", "os.spawn"):
            if not check_access(".", 'x'):
                raise GuardViolation(f"[Security] Access Denied: 'x' permission required to execute commands here")

    except GuardViolation as e:
        raise

if not hasattr(sys, '_guard_hook_registered'):
    sys.addaudithook(audit_hook)
    sys._guard_hook_registered = True

def set_context(config):
    return security_context.set(config)

def reset_context(token):
    security_context.reset(token)

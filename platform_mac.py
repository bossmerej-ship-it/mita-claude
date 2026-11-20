"""macOS-часть маскота: поиск окна Claude/ChatGPT через Quartz и прозрачное окно Tk.

Нужен бесплатный pyobjc:  pip3 install pyobjc-framework-Quartz pyobjc-framework-Cocoa
Имя программы-владельца окна macOS отдаёт без разрешения на запись экрана,
поэтому ищем окно по программе (Claude, ChatGPT, Codex), а не по заголовку.
Активное окно = самое переднее обычное окно в списке окон (так надёжнее, чем NSWorkspace).
Координаты Quartz и Tk на маке одинаковые: точки, начало в левом верхнем углу главного экрана.
"""

import os

import Quartz
from AppKit import NSApplication, NSRunningApplication, NSScreen

BG = "systemTransparent"
# На маке правая кнопка у Tk — это Button-2 (а у некоторых мышей Button-3), плюс Ctrl+клик.
RIGHT_BUTTONS = ("<Button-2>", "<Button-3>", "<Control-Button-1>")

_OWN_PID = os.getpid()
_ACTIVATE_IGNORING_OTHERS = 1 << 1


def setup_window(root):
    """Прозрачный фон и без значка в Dock. Возвращает свой pid как «своё окно»."""
    root.config(bg=BG)
    root.attributes("-transparent", True)
    try:
        NSApplication.sharedApplication().setActivationPolicy_(1)   # Accessory: без Dock и меню
    except Exception:
        pass
    return _OWN_PID


def _windows():
    opts = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    return Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID) or []


def _normal(w):
    """Обычное окно программы (не меню, не Dock), достаточно большое, и не наше."""
    if w.get(Quartz.kCGWindowLayer, 1) != 0 or w.get(Quartz.kCGWindowOwnerPID) == _OWN_PID:
        return None
    b = w.get(Quartz.kCGWindowBounds) or {}
    if b.get("Width", 0) < 200 or b.get("Height", 0) < 200:
        return None
    return {
        "pid": int(w.get(Quartz.kCGWindowOwnerPID)),
        "owner": str(w.get(Quartz.kCGWindowOwnerName) or ""),
        "bounds": (int(b["X"]), int(b["Y"]), int(b["X"] + b["Width"]), int(b["Y"] + b["Height"])),
    }


def _front():
    """Самое переднее обычное окно: список окон macOS идёт от переднего к заднему."""
    for w in _windows():
        win = _normal(w)
        if win:
            return win
    return None


def _main_window_of(pid):
    for w in _windows():
        win = _normal(w)
        if win and win["pid"] == pid:
            return win
    return None


def describe():
    """Для лога: какие программы с окнами сейчас на экране."""
    names = []
    for w in _windows():
        win = _normal(w)
        if win and win["owner"] not in names:
            names.append(win["owner"])
    return ", ".join(names)


def find_target(last, match):
    """Окно активной программы из списка; если впереди другая — последнее, где она была."""
    front = _front()
    if front:
        name = match(front["owner"])
        if name:
            return front, name
    if last and last[0]:
        win = _main_window_of(last[0]["pid"])
        if win:
            return win, last[1]
    return None, None


def is_minimized(win):
    return win is None      # свёрнутое окно не попадает в список видимых


def window_rect(win):
    return win["bounds"]


def work_bottom(win):
    """Нижняя граница экрана над Dock, в координатах «сверху вниз»."""
    l, t, r, b = win["bounds"]
    cx, cy = (l + r) / 2, (t + b) / 2
    screens = NSScreen.screens()
    main_h = screens[0].frame().size.height
    for s in screens:
        f = s.frame()
        top = main_h - (f.origin.y + f.size.height)
        if f.origin.x <= cx <= f.origin.x + f.size.width and top <= cy <= top + f.size.height:
            vf = s.visibleFrame()
            return int(main_h - vf.origin.y)
    return b


def is_foreground(win, own):
    front = _front()
    return front is not None and front["pid"] == win["pid"]


def refocus(win):
    """Клик по маскоту делает Python активным — возвращаем фокус Claude/ChatGPT."""
    try:
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(win["pid"])
        if app is not None:
            app.activateWithOptions_(_ACTIVATE_IGNORING_OTHERS)
    except Exception:
        pass

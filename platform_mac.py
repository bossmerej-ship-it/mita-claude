"""macOS-часть маскота: поиск окна Claude/ChatGPT через Quartz и прозрачное окно Tk.

Нужен бесплатный pyobjc:  pip3 install pyobjc-framework-Quartz pyobjc-framework-Cocoa
Имя программы-владельца окна macOS отдаёт без разрешения на запись экрана,
поэтому ищем окно по программе (Claude, ChatGPT, Codex), а не по заголовку.
Координаты Quartz и Tk на маке одинаковые: точки, начало в левом верхнем углу главного экрана.
"""

import os

import Quartz
from AppKit import NSApplication, NSRunningApplication, NSScreen, NSWorkspace

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


def _main_window_of(pid):
    """Самое верхнее обычное окно программы (окна идут от переднего к заднему)."""
    for w in _windows():
        if w.get("kCGWindowOwnerPID") != pid or w.get("kCGWindowLayer", 1) != 0:
            continue
        b = w.get("kCGWindowBounds") or {}
        if b.get("Width", 0) > 200 and b.get("Height", 0) > 200:
            return {
                "pid": pid,
                "bounds": (int(b["X"]), int(b["Y"]), int(b["X"] + b["Width"]), int(b["Y"] + b["Height"])),
            }
    return None


def find_target(last, match):
    """Окно активной программы из списка; если активна другая — последнее, где она была."""
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is not None:
        name = match(str(app.localizedName() or ""))
        if name:
            win = _main_window_of(app.processIdentifier())
            if win:
                return win, name
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
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    pid = app.processIdentifier() if app is not None else None
    return pid in (win["pid"], own)


def refocus(win):
    """Клик по маскоту делает Python активным — возвращаем фокус Claude/ChatGPT."""
    try:
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(win["pid"])
        if app is not None:
            app.activateWithOptions_(_ACTIVATE_IGNORING_OTHERS)
    except Exception:
        pass

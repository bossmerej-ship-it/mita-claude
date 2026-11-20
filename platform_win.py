"""Windows-часть маскота: поиск окна Claude/ChatGPT и прозрачное окно поверх всех (WinAPI через ctypes)."""

import ctypes
import ctypes.wintypes as wt

user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # координаты совпадают с экраном
except Exception:
    user32.SetProcessDPIAware()

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.restype = ctypes.c_long
user32.GetParent.restype = wt.HWND
user32.GetForegroundWindow.restype = wt.HWND
user32.MonitorFromWindow.restype = wt.HANDLE

KEY = "#ff00fe"                     # этот цвет становится прозрачным (в спрайтах его нет)
BG = KEY
RIGHT_BUTTONS = ("<Button-3>",)


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


def _title(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def setup_window(root):
    """Прозрачный фон, без кнопки на панели задач, не забирает фокус. Возвращает своё окно."""
    root.config(bg=KEY)
    root.attributes("-transparentcolor", KEY)
    root.update_idletasks()
    hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE) | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
    return hwnd


def find_target(last, match):
    """Активное окно из списка; если активно другое — последнее, где она была. -> (окно, имя)"""
    fg = user32.GetForegroundWindow()
    name = match(_title(fg)) if fg else None
    if name:
        return fg, name
    if last and user32.IsWindow(last[0]) and user32.IsWindowVisible(last[0]):
        return last
    return None, None


def describe():
    """Для лога: заголовок активного окна."""
    return _title(user32.GetForegroundWindow())


def is_minimized(win):
    return bool(user32.IsIconic(win))


def window_rect(win):
    r = wt.RECT()
    user32.GetWindowRect(win, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def work_bottom(win):
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    user32.GetMonitorInfoW(user32.MonitorFromWindow(win, 2), ctypes.byref(mi))
    return mi.rcWork.bottom


def is_foreground(win, own):
    return user32.GetForegroundWindow() in (win, own)


def refocus(win):
    """На Windows окно маскота и так не забирает фокус."""

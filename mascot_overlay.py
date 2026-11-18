"""Пиксельный маскот поверх Claude Desktop и приложения Codex, с физикой.

Прозрачное окно поверх всех окон. Клики по пустому месту проходят насквозь,
а саму девочку можно трогать мышкой:

  ЛКМ (зажать и тащить)   взять её на руки. Отпустишь, и она упадёт.
                          Если резко дёрнуть, она полетит, как брошенная.
  Ctrl + отпустить ЛКМ    «вот тут рамка поля ввода»: запоминает уступ, по которому она гуляет.
  ПКМ                     «сиди!»: она садится (на уступе свешивает ножки) и остаётся на месте,
                          даже если её перенести. Ещё раз ПКМ, и она снова живёт сама.
  Shift + ПКМ             закрыть маскота.

Мир девочки — активное окно Claude или Codex (у каждого свой уступ): пол (низ окна), уступ (рамка поля ввода) и крыша окна.
Она ходит, оглядывается, разворачивается, залезает на уступ по его краю и слезает,
иногда спрыгивает. Падает с ускорением, после сильного падения лежит и встаёт.
Всё считается относительно окна Claude, так что двигается вместе с ним.
Claude Desktop не меняется, поэтому всё переживает обновления.

Запуск:  python mascot_overlay.py   (или pythonw, чтобы не было консоли)
"""

import ctypes
import ctypes.wintypes as wt
import json
import random
import tkinter as tk
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPRITES = HERE / "sprites"
POS_FILE = HERE / "mascot_pos.json"

SCALE = 1             # только целое число: 1 = 41x86, 2 = 82x172. Дробь размоет пиксели.
# Окна, по которым она гуляет. Она живёт в том из них, что сейчас активно.
TARGETS = ("Claude", "Codex")
KEY = "#ff00fe"       # этот цвет становится прозрачным (в спрайтах его нет)
TICK_MS = 33          # ~30 кадров в секунду
SPEED = 1.2           # ходьба, пикселей за кадр
CLIMB = 1.0           # лазанье, пикселей за кадр
GRAVITY = 0.7         # ускорение падения
MAX_FALL = 26         # предельная скорость падения
HARD_LANDING = 13     # быстрее этого — падает плашмя и потом встаёт
LEDGE_HALF = 380      # полуширина уступа (рамки поля ввода)
LEG = 14 * SCALE      # насколько свешиваются ножки, когда сидит на уступе

# Уступ по умолчанию: dx — от центра окна, dy — от низа окна вверх. Для каждого окна свой.
DEFAULT_LEDGE = {"dx": 0, "dy": 128}
DEFAULT = {"ledges": {}, "sit": False, "sitpos": {}}

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
EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


def title_of(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def target_name(title):
    for t in TARGETS:
        if title == t or title.startswith(t + " "):
            return t
    return None


def find_target(last):
    """Активное окно Claude или Codex; если активно другое — последнее, где она была."""
    fg = user32.GetForegroundWindow()
    name = target_name(title_of(fg)) if fg else None
    if name:
        return fg, name
    if last and user32.IsWindow(last[0]) and user32.IsWindowVisible(last[0]):
        return last
    return None, None


def window_rect(hwnd):
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def work_bottom(hwnd):
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, 2), ctypes.byref(mi))
    return mi.rcWork.bottom


def load_state():
    st = json.loads(json.dumps(DEFAULT))
    try:
        saved = json.loads(POS_FILE.read_text(encoding="utf-8"))
        if "ledges" in saved:
            st.update(saved)
        elif "ledge" in saved:                      # файлы прошлых версий: это было окно Claude
            st["ledges"]["Claude"] = saved["ledge"]
        elif "home" in saved:
            st["ledges"]["Claude"] = {"dx": saved["home"][0], "dy": saved["home"][1]}
    except Exception:
        pass
    if not isinstance(st.get("sitpos"), dict):
        st["sitpos"] = {}
    return st


class Mascot:
    def __init__(self):
        self.st = load_state()
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.config(bg=KEY)
        self.root.attributes("-transparentcolor", KEY)

        self.img = {}
        for f in SPRITES.glob("*.png"):
            im = tk.PhotoImage(file=str(f))
            self.img[f.stem] = im.zoom(SCALE, SCALE) if SCALE > 1 else im
        self.cw = max(i.width() for i in self.img.values()) + 2
        self.base = max(i.height() for i in self.img.values()) + 6   # линия ног на холсте
        self.ch = self.base + LEG + 2
        self.canvas = tk.Canvas(self.root, width=self.cw, height=self.ch, bg=KEY,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.sprite = self.canvas.create_image(self.cw // 2, self.base, anchor="s", image=self.img["front"])
        self.root.geometry(f"{self.cw}x{self.ch}+0+0")
        self.root.update_idletasks()

        self.hwnd = user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
        ex = user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE) | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, ex)

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_right)

        # Положение ног в координатах окна Claude: X от левого края, Y от нижнего (вверх — минус).
        self.X, self.Y = 300.0, -200.0
        self.vx = self.vy = 0.0
        self.dir = random.choice((-1, 1))
        self.on = None            # на каком уступе стоит: "floor", "ledge", "roof" или None
        self.mode = "fall"
        self.timer = 0
        self.frame = 0
        self.edge_cooldown = 0
        self.held = False
        self.trail = []           # последние точки мышки, чтобы посчитать бросок
        self.world = None
        self.placed = False
        self.target = (None, None)   # (окно, "Claude"/"Codex")
        self.root.after(TICK_MS, self.tick)

    # ---------- мир ----------
    def platforms(self):
        l, t, r, b, wb = self.world
        w = r - l
        ledge = self.st["ledges"].get(self.target[1], DEFAULT_LEDGE)
        cx = w / 2 + ledge["dx"]
        floor_y = min(b, wb) - b
        return {
            "floor": (floor_y, 0, w),
            "ledge": (-ledge["dy"], max(0, cx - LEDGE_HALF), min(w, cx + LEDGE_HALF)),
            "roof": (t - b, 0, w),
        }

    # ---------- мышка ----------
    def pointer_world(self):
        l, t, r, b, wb = self.world
        return self.root.winfo_pointerx() - l, self.root.winfo_pointery() - b

    def on_press(self, e):
        if self.world is None:
            return
        self.held = True
        self.on = None
        self.mode = "held"
        self.grab = (e.x - self.cw // 2, e.y - self.base)
        self.trail = [self.pointer_world()]

    def on_drag(self, _e):
        if not self.held or self.world is None:
            return
        px, py = self.pointer_world()
        self.X, self.Y = px - self.grab[0], py - self.grab[1]
        self.trail = (self.trail + [(px, py)])[-4:]

    def on_release(self, e):
        if not self.held:
            return
        self.held = False
        if e.state & 0x0004:                         # Ctrl: здесь рамка поля ввода
            w = self.world[2] - self.world[0]
            self.st["ledges"][self.target[1]] = {"dx": round(self.X - w / 2), "dy": round(-self.Y)}
            self.land("ledge", 0)
            self.save()
            return
        if self.st["sit"]:                           # сказали сидеть — остаётся, где отпустили
            self.st["sitpos"][self.target[1]] = [self.X, self.Y]
            self.mode, self.on = "sit", self.platform_under_feet()
            self.save()
            return
        if len(self.trail) >= 2:                     # бросок: скорость последних движений мышки
            (x0, y0), (x1, y1) = self.trail[0], self.trail[-1]
            n = len(self.trail) - 1
            self.vx = max(-22, min(22, (x1 - x0) / n))
            self.vy = max(-22, min(22, (y1 - y0) / n))
        else:
            self.vx = self.vy = 0
        self.mode = "fall"

    def on_right(self, e):
        if e.state & 0x0001:                         # Shift + ПКМ = выход
            self.root.destroy()
            return
        self.st["sit"] = not self.st["sit"]
        if self.st["sit"]:
            self.st["sitpos"][self.target[1]] = [self.X, self.Y]
            self.mode = "sit"
        else:
            self.st["sitpos"] = {}
            if self.on:
                self.mode, self.timer = "idle", 20
            else:
                self.vx = self.vy = 0
                self.mode = "fall"
        self.save()

    def save(self):
        try:
            POS_FILE.write_text(json.dumps(self.st), encoding="utf-8")
        except Exception:
            pass

    def platform_under_feet(self):
        for name, (py, x1, x2) in self.platforms().items():
            if abs(self.Y - py) < 2 and x1 <= self.X <= x2:
                return name
        return None

    # ---------- поведение ----------
    def land(self, name, speed):
        self.on = name
        self.Y = self.platforms()[name][0]
        self.vx = self.vy = 0
        if speed > HARD_LANDING:
            self.mode, self.timer = "lying", 70      # шлёпнулась
        else:
            self.mode, self.timer = "land", 7        # присела от приземления

    def next_action(self):
        r = random.random()
        if r < 0.6:
            self.mode, self.timer = "walk", random.randint(60, 220)
            if random.random() < 0.3:
                self.start_turn()
        elif r < 0.85:
            self.mode, self.timer = "idle", random.randint(40, 130)
        else:
            self.mode, self.timer = "look", random.randint(30, 60)

    def start_turn(self):
        self.dir *= -1
        self.mode, self.timer = "turn", 12

    def at_edge(self, name, x1, x2):
        """Дошла до края уступа: развернуться, слезть или спрыгнуть."""
        plats = self.platforms()
        floor_y = plats["floor"][0]
        r = random.random()
        if name == "floor" or self.edge_cooldown > 0:
            self.X = min(max(self.X, x1 + 1), x2 - 1)
            self.start_turn()
        elif name == "ledge" and r < 0.3 and floor_y - plats["ledge"][0] > 20:
            self.mode = "climb_down"
            self.on = None
        elif r < 0.45:
            self.mode, self.on = "fall", None          # спрыгнула
            self.vx, self.vy = self.dir * 2.5, -5
        else:
            self.X = min(max(self.X, x1 + 1), x2 - 1)
            self.start_turn()
        self.edge_cooldown = 90

    def step(self):
        plats = self.platforms()
        if self.edge_cooldown > 0:
            self.edge_cooldown -= 1

        if self.mode in ("held", "sit"):
            return

        if self.mode == "fall":
            prev = self.Y
            self.vy = min(MAX_FALL, self.vy + GRAVITY)
            self.X += self.vx
            self.Y += self.vy
            w = self.world[2] - self.world[0]
            if self.X < 20 or self.X > w - 20:      # стены окна: отскок
                self.X = min(max(self.X, 20), w - 20)
                self.vx = -self.vx * 0.5
                self.dir = 1 if self.vx > 0 else -1
            if self.vy >= 0:
                hit = [(py, name) for name, (py, x1, x2) in plats.items()
                       if x1 <= self.X <= x2 and prev <= py <= self.Y]
                if hit:
                    py, name = min(hit)
                    self.land(name, self.vy)
            if self.Y > plats["floor"][0] + 400:    # улетела за низ — вернуть на пол
                self.Y = plats["floor"][0]
                self.land("floor", 0)
            return

        if self.mode == "climb_up":
            self.Y -= CLIMB
            if self.Y <= plats["ledge"][0]:
                self.on = "ledge"
                self.Y = plats["ledge"][0]
                self.X += 4 * self.dir
                self.mode, self.timer = "land", 6
            return

        if self.mode == "climb_down":
            self.Y += CLIMB
            if self.Y >= plats["floor"][0]:
                self.on = "floor"
                self.Y = plats["floor"][0]
                self.mode, self.timer = "land", 6
            return

        # стоит на уступе: держимся на нём, даже если окно поменяло размер
        if self.on is None:
            self.mode, self.vy, self.vx = "fall", 0, 0
            return
        py, x1, x2 = plats[self.on]
        self.Y = py

        self.timer -= 1
        if self.mode == "walk":
            self.X += SPEED * self.dir
            if self.X <= x1 or self.X >= x2:
                self.at_edge(self.on, x1, x2)
                return
            # на полу у края уступа: может залезть наверх
            if self.on == "floor" and self.edge_cooldown == 0:
                lp, lx1, lx2 = plats["ledge"]
                for edge in (lx1, lx2):
                    if abs(self.X - edge) < SPEED and py - lp > 20 and random.random() < 0.5:
                        self.X = edge
                        self.mode, self.on = "climb_up", None
                        self.dir = 1 if edge == lx1 else -1
                        self.edge_cooldown = 90
                        return
        if self.timer <= 0:
            if self.mode == "turn":
                self.mode, self.timer = "walk", random.randint(60, 200)
            elif self.mode == "lying":
                self.mode, self.timer = "getup", 18
            else:
                self.next_action()

    # ---------- картинка ----------
    def pick(self):
        f = self.frame
        left = "_left" if self.dir < 0 else ""
        m = self.mode
        if m == "held":
            moving = len(self.trail) >= 2 and abs(self.trail[-1][0] - self.trail[0][0]) > 3
            return ("front_step0" if (f // 3) % 2 else "front_step1") if moving else "held", 0
        if m == "sit":
            if self.on:                                  # сидит на краю, болтает ножками
                return ("sit0" if (f // 20) % 2 else "sit1"), LEG
            return "front", 0
        if m == "fall":
            side = "_left" if self.vx < -0.5 else ("" if self.vx > 0.5 else left)
            return ("front34_step0" if (f // 3) % 2 else "front34_step1") + side, 0
        if m == "land":
            return "squash", 0
        if m == "lying":
            return "lying" + left, 0
        if m == "getup":
            return ("squash" if self.timer > 9 else "front34" + left), 0
        if m in ("climb_up", "climb_down"):
            return ("back_step0" if (f // 8) % 2 else "back_step1"), 0
        if m == "walk":
            return {0: "side_step0", 1: "side", 2: "side_step1", 3: "side"}[(f // 6) % 4] + left, 0
        if m == "turn":
            return ("front34" + left) if self.timer > 6 else "front", 0
        if m == "look":
            return ("back34" + left) if self.timer > 8 else ("front34" + left), 0
        return "front", 0

    def tick(self):
        self.frame += 1
        claude, name = find_target(self.target if self.target[0] else None)
        if name != self.target[1] and claude is not None:
            self.target = (claude, name)            # перебралась в другое окно
            self.placed, self.held = False, False
        if claude is None or user32.IsIconic(claude):
            self.root.withdraw()
            self.root.after(TICK_MS, self.tick)
            return
        l, t, r, b = window_rect(claude)
        self.world = (l, t, r, b, work_bottom(claude))

        if not self.placed:                              # первый кадр: на уступ или туда, где сидела
            self.placed = True
            spot = self.st["sitpos"].get(self.target[1])
            if self.st["sit"] and spot:
                self.X, self.Y = spot
                self.mode, self.on = "sit", self.platform_under_feet()
            else:
                py, x1, x2 = self.platforms()["ledge"]
                self.X, self.Y = (x1 + x2) / 2, py - 120
                self.mode = "fall"

        self.step()
        name, drop = self.pick()
        self.canvas.itemconfig(self.sprite, image=self.img.get(name, self.img["front"]))
        self.canvas.coords(self.sprite, self.cw // 2, self.base + drop)
        bob = 1 if self.mode == "idle" and (self.frame // 25) % 2 else 0

        fg = user32.GetForegroundWindow()
        if self.held or self.mode == "fall" or fg in (claude, self.hwnd):
            wx = l + round(self.X) - self.cw // 2
            wy = b + round(self.Y) - self.base - bob
            self.root.geometry(f"+{wx}+{wy}")
            self.root.deiconify()
            self.root.attributes("-topmost", True)
        else:
            self.root.withdraw()
        self.root.after(TICK_MS, self.tick)


if __name__ == "__main__":
    try:
        Mascot().root.mainloop()
    except KeyboardInterrupt:
        pass

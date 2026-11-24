"""Пиксельный маскот поверх Claude Desktop и ChatGPT/Codex, с физикой. Windows и macOS.

Прозрачное окно поверх всех окон. Клики по пустому месту проходят насквозь,
а саму девочку можно трогать мышкой:

  ЛКМ (зажать и тащить)   взять её на руки. Отпустишь, и она упадёт.
                          Если резко дёрнуть, она полетит, как брошенная.
  Shift + отпустить ЛКМ   посадить на край поля ввода здесь и запомнить место.
                          На Windows также можно использовать Ctrl.
  ПКМ                     «сиди!»: она садится (на уступе свешивает ножки) и остаётся на месте,
                          даже если её перенести. Ещё раз ПКМ, и она снова живёт сама.
  Shift + ПКМ             закрыть маскота.

Мир девочки — активное окно Claude или Codex (у каждого свой уступ): пол (низ окна), уступ (рамка поля ввода) и крыша окна.
Она ходит, оглядывается, разворачивается, залезает на уступ по его краю и слезает,
иногда спрыгивает. Падает с ускорением, после сильного падения лежит и встаёт.
Всё считается относительно окна Claude, так что двигается вместе с ним.
Claude Desktop не меняется, поэтому всё переживает обновления.

Запуск:  Windows — python mascot_overlay.py (или pythonw, чтобы не было консоли)
         macOS   — python3 mascot_overlay.py (нужен pip3 install pyobjc-framework-Quartz pyobjc-framework-Cocoa)
"""

import json
import random
import sys
import traceback
import tkinter as tk
from pathlib import Path

if sys.platform == "darwin":
    import platform_mac as plat       # macOS: Quartz + pyobjc
else:
    import platform_win as plat       # Windows: WinAPI

HERE = Path(__file__).resolve().parent
SPRITES = HERE / "sprites"
POS_FILE = HERE / "mascot_pos.json"
LOG_FILE = HERE / "mita.log"


def log(text):
    """Ошибки пишем в mita.log рядом со скриптом, чтобы было что прислать."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(text.rstrip() + chr(10))
    except Exception:
        pass

SCALE = 1             # только целое число: 1 = 41x86, 2 = 82x172. Дробь размоет пиксели.
# Окна, по которым она гуляет. Она живёт в том из них, что сейчас активно.
TARGETS = ("Claude", "Codex", "ChatGPT")
TICK_MS = 33          # ~30 кадров в секунду
SPEED = 1.2           # ходьба, пикселей за кадр
CLIMB = 1.0           # лазанье, пикселей за кадр
GRAVITY = 0.7         # ускорение падения
MAX_FALL = 26         # предельная скорость падения
HARD_LANDING = 13     # быстрее этого — падает плашмя и потом встаёт
LEDGE_HALF = 380      # полуширина уступа (рамки поля ввода)
USE_LEDGE = False     # True — добавить уступ по умолчанию и крышу; заданный мышкой уступ работает всегда
LEG = 14 * SCALE      # насколько свешиваются ножки, когда сидит на уступе

# Сцена после сильного падения: (кадр, сколько тиков держать). "dazed" — лежит со звёздочками.
CRASH = [("crash_impact", 7), ("crash_tears", 10), ("dazed", 75), ("dazed3", 22), ("situp", 18),
         ("knees", 18), ("kneel", 12), ("dustoff", 28), ("recover", 20), ("shy", 24)]

# Уступ по умолчанию: dx — от центра окна, dy — от низа окна вверх. Для каждого окна свой.
DEFAULT_LEDGE = {"dx": 0, "dy": 128}
DEFAULT = {"ledges": {}, "sit": False, "sitpos": {}}

def target_name(title):
    for t in TARGETS:
        if title == t or title.startswith(t + " "):
            return t
    return None


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
    if not isinstance(st.get("ledges"), dict):
        st["ledges"] = {}
    if not isinstance(st.get("sitpos"), dict):
        st["sitpos"] = {}
    return st


class Mascot:
    def __init__(self):
        self.st = load_state()
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        self.img = {}
        try:
            self.drops = json.loads((SPRITES / "drops.json").read_text(encoding="utf-8"))
        except Exception:
            self.drops = {}
        for f in SPRITES.glob("*.png"):
            im = tk.PhotoImage(file=str(f))
            self.img[f.stem] = im.zoom(SCALE, SCALE) if SCALE > 1 else im
        self.cw = max(i.width() for i in self.img.values()) + 2
        self.base = max(i.height() for i in self.img.values()) + 6   # линия ног на холсте
        self.ch = self.base + LEG + 2
        self.canvas = tk.Canvas(self.root, width=self.cw, height=self.ch, bg=plat.BG,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.sprite = self.canvas.create_image(self.cw // 2, self.base, anchor="s", image=self.img["front"])
        self.root.geometry(f"{self.cw}x{self.ch}+0+0")
        self.own = plat.setup_window(self.root)   # прозрачность, без панели задач/Dock, без фокуса

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        for button in plat.RIGHT_BUTTONS:
            self.canvas.bind(button, self.on_right)

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
        self.prompt = None        # настоящий прямоугольник поля ввода (экранные координаты)
        self.auto_prompt_apps = set()
        self.placed = False
        self.target = (None, None)   # (окно, "Claude"/"Codex")
        self.shown = None            # видна ли сейчас (меняем только при изменении)
        self.root.after(TICK_MS, self.tick)

    # ---------- мир ----------
    def platforms(self):
        l, t, r, b, wb = self.world
        w = r - l
        floor_y = min(b, wb) - b
        plats = {"floor": (floor_y, 0, w)}
        prompt = self.prompt
        ledge = self.st["ledges"].get(self.target[1])
        if prompt is not None:
            pl, pt, pr, pb = prompt
            x1, x2 = max(0, pl - l), min(w, pr - l)
            if x2 > x1 and t <= pt < min(b, wb):
                plats["ledge"] = (pt - b, x1, x2)
        elif (ledge is not None or USE_LEDGE) and self.target[1] not in self.auto_prompt_apps:
            ledge = ledge if ledge is not None else DEFAULT_LEDGE
            cx = min(w, max(0, w / 2 + ledge["dx"]))
            # При уменьшении окна уступ остаётся между верхом окна и полом.
            y = min(floor_y - LEG, max(t - b, -ledge["dy"]))
            plats["ledge"] = (y, max(0, cx - LEDGE_HALF), min(w, cx + LEDGE_HALF))
        if USE_LEDGE:
            plats["roof"] = (t - b, 0, w)
        return plats

    def remember_sit(self):
        if self.on == "ledge":
            w = self.world[2] - self.world[0]
            self.st["sitpos"][self.target[1]] = {"dx": self.X - w / 2, "on": "ledge"}
        else:
            self.st["sitpos"][self.target[1]] = [self.X, self.Y]

    def sit_on_ledge(self):
        """Пользователь показывает край поля ввода: ноги свешиваются ниже этого края."""
        w = self.world[2] - self.world[0]
        self.st["ledges"][self.target[1]] = {"dx": round(self.X - w / 2), "dy": round(-self.Y)}
        self.auto_prompt_apps.discard(self.target[1])
        self.st["sit"] = True
        self.mode, self.on = "sit", "ledge"
        self.vx = self.vy = 0
        self.remember_sit()
        self.step()
        self.save()

    def refresh_prompt(self):
        self.prompt = plat.prompt_rect(self.target[0], self.world[:4])
        if self.prompt is not None:
            self.auto_prompt_apps.add(self.target[1])

    # ---------- мышка ----------
    def pointer_world(self):
        l, t, r, b, wb = self.world
        return self.root.winfo_pointerx() - l, self.root.winfo_pointery() - b

    def on_press(self, e):
        if self.world is None:
            return
        self.held = True
        # Подняли даже закреплённую Миту: после отпускания снова действует физика.
        if self.st["sit"]:
            self.st["sit"] = False
            self.st["sitpos"].pop(self.target[1], None)
            self.save()
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
        self.refresh_prompt()
        plat.refocus(self.target[0])                 # фокус остаётся у Claude/ChatGPT
        if e.state & 0x0001 or (sys.platform != "darwin" and e.state & 0x0004):
            self.sit_on_ledge()                     # Shift (или Ctrl на Windows): сесть на край
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
        plat.refocus(self.target[0])
        self.st["sit"] = not self.st["sit"]
        if self.st["sit"]:
            self.on = self.platform_under_feet()
            self.mode = "sit"
            self.remember_sit()
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
        if abs(self.vx) > 0.5:
            self.dir = 1 if self.vx > 0 else -1
        self.vx = self.vy = 0
        if speed > HARD_LANDING:
            self.mode, self.crash_i = "crash", 0     # шлёпнулась: дальше вся сцена CRASH
            self.timer = CRASH[0][1]
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

        if self.mode == "held":
            return
        if (self.on == "ledge" or self.mode in ("climb_up", "climb_down")) and "ledge" not in plats:
            self.mode, self.on, self.vx, self.vy = "fall", None, 0, 0
        if self.mode == "sit":
            w = self.world[2] - self.world[0]
            if self.on in plats:
                self.Y, x1, x2 = plats[self.on]
                spot = self.st["sitpos"].get(self.target[1])
                if self.on == "ledge" and isinstance(spot, dict):
                    self.X = w / 2 + spot["dx"]
            else:
                x1, x2 = 0, w
            margin = min(self.cw / 2, (x2 - x1) / 2)
            self.X = min(x2 - margin, max(x1 + margin, self.X))
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

        if self.on == "ledge":
            margin = min(self.cw / 2, (x2 - x1) / 2)
            x1, x2 = x1 + margin, x2 - margin
            self.X = min(x2, max(x1, self.X))

        self.timer -= 1
        if self.mode == "walk":
            self.X += SPEED * self.dir
            if self.X <= x1 or self.X >= x2:
                self.at_edge(self.on, x1, x2)
                return
            # на полу у края уступа: может залезть наверх
            if self.on == "floor" and self.edge_cooldown == 0 and "ledge" in plats:
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
            elif self.mode == "crash":
                self.crash_i += 1
                if self.crash_i < len(CRASH):
                    self.timer = CRASH[self.crash_i][1]
                else:
                    self.mode, self.timer = "idle", 40
            else:
                self.next_action()

    # ---------- картинка ----------
    def pick(self):
        f = self.frame
        left = "_left" if self.dir < 0 else ""
        m = self.mode
        if m == "held":
            moving = len(self.trail) >= 2 and abs(self.trail[-1][0] - self.trail[0][0]) > 3
            if moving:                                   # мотают — паникует
                return "fall_panic" + ("_left" if (f // 4) % 2 else ""), 0
            return "held", 0
        if m == "sit":
            if self.on == "ledge":                       # сидит на краю, болтает ножками
                return ("sit0" if (f // 20) % 2 else "sit1"), LEG
            return "front", 0
        if m == "fall":
            if abs(self.vx) > 3:                         # летит вбок — «рыбкой»
                return "fall_dive" + ("_left" if self.vx < 0 else ""), 0
            if self.vy > 4:                              # падает — машет руками
                return "fall_panic" + ("_left" if (f // 5) % 2 else ""), 0
            return "front34" + left, 0
        if m == "land":
            return "squash", 0
        if m == "crash":
            name = CRASH[self.crash_i][0]
            if name == "dazed":                          # звёздочки кружатся, иногда дёргается
                name = "dazed1" if (f // 7) % 3 else "dazed2"
            return name + left, self.drops.get(name, 0)
        if m in ("climb_up", "climb_down"):
            return ("back_step0" if (f // 8) % 2 else "back_step1"), 0
        if m == "walk":
            return {0: "side_step0", 1: "side", 2: "side_step1", 3: "side"}[(f // 6) % 4] + left, 0
        if m == "turn":
            return ("front34" + left) if self.timer > 6 else "front", 0
        if m == "look":
            return ("back34" + left) if self.timer > 8 else ("front34" + left), 0
        return "front", 0

    def set_shown(self, on):
        # Windows: поверх всех заново каждый кадр; мак: только когда меняется (иначе крадёт фокус)
        if on and (sys.platform != "darwin" or self.shown is not True):
            plat.show(self.root)
        elif not on and self.shown is not False:
            plat.hide(self.root)
        self.shown = on

    def tick(self):
        try:
            self._tick()
        except Exception:
            log(traceback.format_exc())
            self.root.after(500, self.tick)

    def _tick(self):
        self.frame += 1
        claude, name = plat.find_target(self.target if self.target[0] else None, target_name)
        if claude is not None:
            if name != self.target[1]:
                self.placed, self.held = False, False
                log(f"окно: {name} {plat.window_rect(claude)}")
            self.target = (claude, name)            # обновляем и при смене окна того же приложения
        if self.frame == 150 and self.target[1] is None:
            log(f"за 5 секунд не нашла окно из {TARGETS}. Сейчас на экране: {plat.describe()}")
            self.placed, self.held = False, False
        if claude is None or plat.is_minimized(claude):
            self.set_shown(False)
            self.root.after(TICK_MS, self.tick)
            return
        l, t, r, b = plat.window_rect(claude)
        self.world = (l, t, r, b, plat.work_bottom(claude))
        self.refresh_prompt()

        if not self.placed:                              # первый кадр: на уступ или туда, где сидела
            self.placed = True
            spot = self.st["sitpos"].get(self.target[1])
            if (self.st["sit"] and isinstance(spot, dict)
                    and spot.get("on") == "ledge" and "ledge" in self.platforms()):
                self.mode, self.on = "sit", "ledge"
                self.X = (r - l) / 2 + spot["dx"]
                self.Y = self.platforms()["ledge"][0]
            elif self.st["sit"] and isinstance(spot, list) and len(spot) == 2:
                self.X, self.Y = spot
                self.mode, self.on = "sit", self.platform_under_feet()
            else:
                plats = self.platforms()
                py, x1, x2 = plats.get("ledge", plats["floor"])
                self.X, self.Y = (x1 + x2) / 2, py - 120
                self.mode = "fall"

        self.step()
        name, drop = self.pick()
        self.canvas.itemconfig(self.sprite, image=self.img.get(name, self.img["front"]))
        shake = (1 if self.frame % 2 else -1) if self.mode == "crash" and self.crash_i == 0 else 0
        self.canvas.coords(self.sprite, self.cw // 2 + shake, self.base + drop)
        bob = 1 if self.mode == "idle" and (self.frame // 25) % 2 else 0

        if self.held or self.mode == "fall" or plat.is_foreground(claude, self.own):
            wx = l + round(self.X) - self.cw // 2
            wy = b + round(self.Y) - self.base - bob
            self.root.geometry(f"+{wx}+{wy}")
            self.set_shown(True)
        else:
            self.set_shown(False)
        self.root.after(TICK_MS, self.tick)


if __name__ == "__main__":
    log(f"--- старт: {sys.platform}, Python {sys.version.split()[0]}, Tk {tk.TkVersion}")
    try:
        Mascot().root.mainloop()
    except KeyboardInterrupt:
        pass
    except Exception:
        log(traceback.format_exc())
        raise

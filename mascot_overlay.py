"""Пиксельный маскот поверх Claude Desktop и ChatGPT/Codex, с физикой. Windows и macOS.

Прозрачное окно поверх всех окон. Клики по пустому месту проходят насквозь,
а саму девочку можно трогать мышкой:

  ЛКМ (зажать и тащить)   взять её на руки. Отпустишь, и она упадёт.
                          Если резко дёрнуть, она полетит, как брошенная.
                          Над полем ввода — приземлится на его край, посидит и пойдёт гулять.
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
import time
import traceback
import tkinter as tk
from collections import deque
from pathlib import Path

import activities
import fall_motion as motion
import rise_motion as rise
import walk_motion as walk

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
TICK_MS = 33          # базовый такт для скоростей и длительностей
TICK_SECONDS = TICK_MS / 1000
MOTION_FRAME_MS = 16  # интервал между кадрами движения, мс
SPEED = 1.2           # ходьба, пикселей за базовый такт
CLIMB = 1.0           # лазанье, пикселей за базовый такт
GRAVITY = 0.7         # ускорение падения
MAX_FALL = 26         # предельная скорость падения
HARD_LANDING = 13     # быстрее этого — падает плашмя и потом встаёт
LEDGE_HALF = 380      # полуширина уступа (рамки поля ввода)
USE_LEDGE = False     # True — добавить уступ по умолчанию и крышу; заданный мышкой уступ работает всегда
LEG = 14 * SCALE      # насколько свешиваются ножки, когда сидит на уступе

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
        self.img.update(motion.load_poses(self.root, SPRITES / "motion" / "fall.png", SCALE))
        self.img.update(motion.load_poses(self.root, SPRITES / "motion" / "walk.png", SCALE,
                                          cell=walk.CELL, rows=walk.POSE_ROWS))
        self.img.update(motion.load_poses(self.root, SPRITES / "motion" / "plant.png", SCALE,
                                          cell=walk.CELL, rows=walk.PLANT_ROWS))
        self.img.update(motion.load_poses(self.root, SPRITES / "motion" / "console.png", SCALE,
                                          cell=activities.CELL, rows=activities.GAME_ROWS))
        self.img.update(motion.load_poses(self.root, SPRITES / "motion" / "greeting.png", SCALE,
                                          cell=activities.CELL, rows=activities.GREET_ROWS))
        self.img.update(motion.load_poses(self.root, SPRITES / "motion" / "sleep.png", SCALE,
                                          cell=activities.CELL, rows=activities.REST_ROWS))
        self.img.update(motion.load_poses(self.root, SPRITES / "motion" / "get_up.png", SCALE,
                                          cell=rise.CELL, rows=rise.POSE_ROWS))
        self.cw = max(i.width() for i in self.img.values()) + 2
        self.base = max(i.height() for i in self.img.values()) + 6   # линия ног на холсте
        self.ch = self.base + LEG + 2
        self.canvas = tk.Canvas(self.root, width=self.cw, height=self.ch, bg=plat.BG,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.root.geometry(f"{self.cw}x{self.ch}+0+0")
        self.own, self.present = plat.setup_window(self.root, self.canvas, self.cw, self.ch)

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
        self.walk_pixels = 0
        self.walk_age = 0.0
        self.activities = activities.Activities()
        self.edge_cooldown = 0
        self.held = False
        self.trail = deque()      # время и координаты последних движений мыши
        self.air_pose = self.air_ticks = 0.0
        self.world = None
        self.prompt = None        # настоящий прямоугольник поля ввода (экранные координаты)
        self.auto_prompt_apps = set()
        self.placed = False
        self.target = (None, None)   # (окно, "Claude"/"Codex")
        self.shown = None            # видна ли сейчас (меняем только при изменении)
        self.last_tick = time.monotonic()
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

    def update_cursor(self, visible, dt):
        greeting = self.activities.greeting
        if (not visible or self.on is None or self.mode not in activities.GREET_MODES
                or self.mode == "perch" and self.timer <= rise.EDGE_TICKS
                or self.mode == "game" and not 19 < self.timer <= self.activities.game_length - activities.PLAY_START):
            greeting.cancel()
            return
        seated = self.on == "ledge" and self.mode in ("sit", "perch", "game")
        center = (self.X, self.Y - 43 * SCALE + (LEG if seated else 0))
        greeting.update(self.pointer_world(), center, self.dir, SCALE, dt)

    def on_press(self, e):
        if self.world is None:
            return
        self.held = True
        self.activities.held_rub = activities.RUB_TICKS if self.mode in activities.REST_MODES else 0
        self.activities.greeting.cancel()
        # Подняли даже закреплённую Миту: после отпускания снова действует физика.
        if self.st["sit"]:
            self.st["sit"] = False
            self.st["sitpos"].pop(self.target[1], None)
            self.save()
        self.on = None
        self.mode = "held"
        self.air_pose = self.air_ticks = 0.0
        self.grab = (e.x - self.cw // 2, e.y - self.base)
        self.trail.clear()
        motion.record_drag(self.trail, time.monotonic(), self.pointer_world())

    def on_drag(self, _e):
        if not self.held or self.world is None:
            return
        px, py = self.pointer_world()
        self.X, self.Y = px - self.grab[0], py - self.grab[1]
        motion.record_drag(self.trail, time.monotonic(), (px, py))

    def on_release(self, e):
        if not self.held:
            return
        now = time.monotonic()
        self.held = False
        self.refresh_prompt()
        plat.refocus(self.target[0])                 # фокус остаётся у Claude/ChatGPT
        if e.state & 0x0001 or (sys.platform != "darwin" and e.state & 0x0004):
            self.sit_on_ledge()                     # Shift (или Ctrl на Windows): сесть на край
            return
        self.last_tick = now
        self.start_fall(*motion.throw_velocity(self.trail, now, TICK_SECONDS), pose=self.air_pose)

    def on_right(self, e):
        if e.state & 0x0001:                         # Shift + ПКМ = выход
            self.root.destroy()
            return
        self.activities.greeting.cancel()
        plat.refocus(self.target[0])
        self.st["sit"] = not self.st["sit"]
        if self.st["sit"]:
            self.on = self.platform_under_feet()
            self.mode = "sit"
            self.remember_sit()
        else:
            self.st["sitpos"] = {}
            if self.on and self.mode in activities.REST_MODES:
                self.activities.rest_pinned = False
                if self.mode != "wake":
                    self.activities.rest_drop = self.pick()[1]
                    self.mode, self.timer = "wake", activities.REST_PHASES["wake"][-1][0]
            elif self.on == "ledge":
                self.start_edge_rise()
            elif self.on:
                self.mode, self.timer = "idle", 20
            else:
                self.start_fall()
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
    def start_fall(self, vx=0.0, vy=0.0, pose=0.0):
        self.activities.greeting.cancel()
        self.activities.held_rub = 0
        self.mode, self.on = "fall", None
        self.vx, self.vy = vx, vy
        self.air_pose, self.air_ticks = pose, 0.0
        if abs(vx) > 1:
            self.dir = 1 if vx > 0 else -1

    def horizontal_flight(self, ticks):
        width = self.world[2] - self.world[0]
        margin = min(20, width / 2)
        left, right = margin, width - margin
        x = min(right, max(left, self.X)) + self.vx * ticks
        if left <= x <= right:
            return x, self.vx
        wall = left if x < left else right
        return min(right, max(left, wall - .5 * (x - wall))), -.5 * self.vx

    def step_fall(self, plats, dt):
        # Одна траектория определяет и подготовку к касанию, и сам момент удара.
        # Проверяем X именно в момент пересечения верхней границы поля ввода.
        contact, when = None, 6.0
        for name, (surface_y, x1, x2) in plats.items():
            crossing = motion.crossing_time(surface_y - self.Y, self.vy, GRAVITY, MAX_FALL)
            if crossing <= when and x1 <= self.horizontal_flight(crossing)[0] <= x2:
                contact, when = name, crossing

        goal = 1 + min(1, max(0, (abs(self.vx) - 4) / 8))
        if contact is not None:
            impact = min(MAX_FALL, self.vy + GRAVITY * when)
            goal = 2.0 if impact > HARD_LANDING else 0.0
        travel = min(dt, when) if contact is not None else dt
        self.air_pose = motion.approach_pose(self.air_pose, goal, travel)
        self.air_ticks += travel
        self.X, self.vx = self.horizontal_flight(travel)
        distance, self.vy = motion.fall_travel(self.vy, travel, GRAVITY, MAX_FALL)
        self.Y += distance
        if contact is not None and when <= dt:
            self.land(contact, self.vy)
        elif self.Y > plats["floor"][0] + 400:
            self.land("floor", 0)

    def land(self, name, speed):
        self.on = name
        self.Y = self.platforms()[name][0]
        self.vx = self.vy = 0
        if speed > HARD_LANDING:
            self.mode = "tip" if self.air_pose < 1.95 else "crash"
            self.timer = motion.IMPACT_TICKS
        else:
            self.mode, self.timer = "land", 7        # присела от приземления

    def next_action(self):
        if self.on == "ledge" and self.activities.game_wait <= 0:
            self.start_walk(180)  # дойти до уголка, даже если обычная прогулка короче
            return
        if self.on == "ledge" and random.random() < 0.3:
            self.start_sitting(rest=random.randint(60, 140))
            return
        r = random.random()
        if r < 0.6:
            self.start_walk(random.randint(60, 220))
            if random.random() < 0.3:
                self.start_turn()
        elif r < 0.85:
            self.mode, self.timer = "idle", random.randint(40, 130)
        else:
            self.mode, self.timer = "look", random.randint(30, 60)

    def start_walk(self, duration):
        if self.mode != "walk":
            self.walk_pixels = 0
            self.walk_age = 0.0
        self.mode, self.timer = "walk", duration

    def start_turn(self):
        self.dir *= -1
        self.mode, self.timer = "turn", walk.TURN_TICKS

    def seat_swing(self):
        return 0 if (self.frame // 20) % 2 else 1

    def start_sitting(self, rest=60, overshoot=0):
        duration = walk.SEAT_TICKS if self.mode == "walk" else rise.LIFT_TICKS
        self.perch_ticks = rest
        self.mode, self.timer = "sit_back", duration + overshoot

    def start_edge_rise(self, remaining=rise.EDGE_TICKS, swing=None):
        self.rise_swing = self.seat_swing() if swing is None else swing
        self.mode, self.timer = "edge_rise", remaining

    def start_game(self, seated=False):
        if not seated:
            self.dir *= -1  # после игры пойдёт от края обратно
        self.mode, self.timer = "game", self.activities.begin_game(seated)

    def update_sleep(self, visible, now):
        act = self.activities
        resting = self.mode in activities.REST_MODES
        if (not visible or self.on is None or now < act.next_idle_check
                or self.mode == "wake" or not (resting or self.mode in activities.CAN_START_REST)):
            return
        act.next_idle_check = now + .5
        idle = plat.idle_seconds()
        if idle is None:
            return
        if resting and idle < activities.SLEEP_AFTER_SECONDS:
            phase = "wake"
        elif not resting and idle >= activities.SLEEP_AFTER_SECONDS:
            act.rest_pinned = self.mode == "sit"
            phase = "yawn"
        else:
            return
        act.rest_drop = self.pick()[1]
        act.greeting.cancel()
        self.mode, self.timer = phase, activities.REST_PHASES[phase][-1][0]

    def step_rest(self, dt):
        if self.mode == "sleep":
            self.timer += dt
            return
        self.timer -= dt
        if self.timer > 0:
            return
        if self.mode == "yawn":
            self.mode, self.timer = "doze", activities.REST_PHASES["doze"][-1][0] + self.timer
        elif self.mode == "doze":
            self.mode, self.timer = "sleep", -self.timer
        elif self.activities.rest_pinned:
            self.mode, self.timer = "sit", 0
        elif self.on == "ledge":
            self.start_edge_rise(rise.EDGE_TICKS + self.timer, swing=0)
        else:
            self.mode, self.timer = "idle", 20

    def at_edge(self, name):
        """Дошла до края уступа: развернуться, слезть или спрыгнуть."""
        if name == "ledge" and self.activities.game_wait <= 0:
            self.start_game()
            return
        plats = self.platforms()
        floor_y = plats["floor"][0]
        r = random.random()
        if name == "floor" or self.edge_cooldown > 0:
            self.start_turn()
        elif name == "ledge" and r < 0.3 and floor_y - plats["ledge"][0] > 20:
            self.mode = "climb_down"
            self.on = None
        elif r < 0.45:
            self.start_fall(self.dir * 2.5, -5)        # спрыгнула
        else:
            self.start_turn()
        self.edge_cooldown = 90

    def step(self, dt=1.0):
        plats = self.platforms()
        if self.edge_cooldown > 0:
            self.edge_cooldown = max(0, self.edge_cooldown - dt)

        if self.mode == "held":
            self.activities.held_rub = max(0, self.activities.held_rub - dt)
            vx, _ = motion.throw_velocity(self.trail, time.monotonic(), TICK_SECONDS)
            self.air_pose = motion.approach_pose(self.air_pose, .4 if abs(vx) > 4 else 0, dt)
            if abs(vx) > 4:
                self.dir = 1 if vx > 0 else -1
            return
        if (self.on == "ledge" or self.mode in ("climb_up", "climb_down")) and "ledge" not in plats:
            self.start_fall()
        resting = self.mode in activities.REST_MODES
        if self.mode == "sit" or resting and self.activities.rest_pinned:
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
            if resting:
                self.step_rest(dt)
            return

        if self.mode == "fall":
            self.step_fall(plats, dt)
            return

        if self.mode == "climb_up":
            self.Y -= CLIMB * dt
            if self.Y <= plats["ledge"][0]:
                self.on = "ledge"
                self.Y = plats["ledge"][0]
                self.X += 4 * self.dir
                self.mode, self.timer = "land", 6
            return

        if self.mode == "climb_down":
            self.Y += CLIMB * dt
            if self.Y >= plats["floor"][0]:
                self.on = "floor"
                self.Y = plats["floor"][0]
                self.mode, self.timer = "land", 6
            return

        # стоит на уступе: держимся на нём, даже если окно поменяло размер
        if self.on is None:
            self.start_fall()
            return
        py, x1, x2 = plats[self.on]
        self.Y = py

        if self.on == "ledge":
            margin = min(self.cw / 2, (x2 - x1) / 2)
            x1, x2 = x1 + margin, x2 - margin
        if self.on == "ledge" or self.mode in ("walk", "crash", "get_up") or resting:
            self.X = min(x2, max(x1, self.X))
        if resting:
            self.step_rest(dt)
            return
        if self.activities.greeting.remaining > 0:
            return  # стопы остаются на опоре, таймер игры продолжится после приветствия
        if self.on == "ledge" and self.mode in activities.FREE_MODES:
            self.activities.game_wait = max(0, self.activities.game_wait - dt)
        if (self.on == "ledge" and self.mode in ("walk", "perch", "edge_rise")
                and x2 - x1 < 2 + len(walk.FIRST_STEP) * SCALE):
            # После изменения ширины поля между краями может не поместиться даже первый шаг.
            if self.mode == "edge_rise" and self.timer < rise.EDGE_TICKS:
                self.timer = min(rise.EDGE_TICKS, self.timer + dt)
            elif self.activities.game_wait <= 0:
                self.start_game(seated=self.mode != "walk")
            elif self.mode == "walk":
                self.start_sitting()
            else:
                self.mode, self.timer = "perch", 60
            return

        if self.mode == "tip":
            self.air_pose = min(2.0, self.air_pose + .5 * dt)
            if self.air_pose == 2.0:
                self.mode = "crash"
            return

        self.timer -= dt
        if self.mode == "perch" and self.timer <= rise.EDGE_TICKS:
            self.start_edge_rise(self.timer)
        if self.mode == "walk":
            distance = walk.travel(self.walk_age, dt, SPEED)
            self.walk_age += dt
            # Считаем путь по тем же целым координатам, по которым перемещается окно Tk.
            previous_x = round(self.X)
            inset = min(1, (x2 - x1) / 2)
            limit = x2 - inset if self.dir > 0 else x1 + inset
            x = self.X + self.dir * distance
            self.X = min(x, limit) if self.dir > 0 else max(x, limit)
            self.walk_pixels += max(0, (round(self.X) - previous_x) * self.dir)
            if self.X == limit:
                self.at_edge(self.on)
                return
            # на полу у края уступа: может залезть наверх
            if self.on == "floor" and self.edge_cooldown == 0 and "ledge" in plats:
                lp, lx1, lx2 = plats["ledge"]
                for edge in (lx1, lx2):
                    if abs(self.X - edge) < distance and py - lp > 20 and random.random() < 0.5:
                        self.X = edge
                        self.mode, self.on = "climb_up", None
                        self.dir = 1 if edge == lx1 else -1
                        self.edge_cooldown = 90
                        return
        if self.timer <= 0:
            if self.mode == "game":
                self.start_edge_rise(rise.EDGE_TICKS + self.timer, swing=1)
            elif self.mode in ("turn", "edge_rise"):
                self.start_walk(random.randint(60, 200))
            elif self.mode == "land" and self.on == "ledge":
                self.start_sitting(overshoot=self.timer)
            elif self.mode == "crash":
                self.mode, self.timer = "get_up", rise.GROUND_TICKS + self.timer
            elif self.mode == "get_up":
                if self.on == "ledge":
                    self.start_sitting(overshoot=self.timer)
                else:
                    self.mode, self.timer = "idle", 40
            elif self.mode == "sit_back":
                self.mode, self.timer = "perch", self.perch_ticks + self.timer
            else:
                self.next_action()

    # ---------- картинка ----------
    def pick(self):
        f = self.frame
        left = "_left" if self.dir < 0 else ""
        m = self.mode
        if m in activities.REST_MODES:
            return activities.rest_pose(m, self.timer, self.dir, self.on == "ledge", self.activities.rest_drop, LEG)
        if m == "held" and self.activities.held_rub > 0:
            return activities.held_rub_pose(self.activities.held_rub, self.dir)
        if self.activities.greeting.remaining > 0:
            seated = self.on == "ledge" and m in ("sit", "perch", "game")
            return self.activities.greeting.pose(m, seated), LEG if seated else 0
        if m == "game":
            return self.activities.game_pose(self.timer, self.dir, self.walk_pixels, SCALE, LEG)
        if m in ("held", "fall", "tip"):
            return motion.air_sprite(self.air_pose, self.air_ticks) + left, 0
        if m == "edge_rise":
            return rise.edge_pose(self.timer, self.dir, self.rise_swing, SCALE)
        if m == "sit_back":
            return walk.sitting_pose(self.timer, self.dir, self.walk_pixels, SCALE)
        if m in ("sit", "perch"):
            if self.on == "ledge":                       # сидит на краю, болтает ножками
                return f"sit{self.seat_swing()}" + left, LEG
            return "front" + left, 0
        if m == "land":
            age = len(motion.CUSHION) - self.timer
            name = motion.CUSHION[min(len(motion.CUSHION) - 1, max(0, int(age)))]
            return name + left, 0
        if m == "crash":
            name = motion.impact_pose(self.timer)
            return name + left, SCALE * self.drops.get(name, 0)
        if m == "get_up":
            return rise.floor_pose(self.timer, self.dir)
        if m in ("climb_up", "climb_down"):
            return ("back_step0" if (f // 8) % 2 else "back_step1"), 0
        if m == "walk":
            return walk.sprite(self.walk_pixels, SCALE, self.dir), 0
        if m == "turn":
            return walk.turn_sprite(self.timer, self.dir, self.walk_pixels, SCALE), 0
        if m == "look":
            return ("back34" + left) if self.timer > 8 else ("front34" + left), 0
        return "front" + left, 0

    def set_shown(self, on):
        if self.shown == on:
            return
        if on:
            plat.show(self.root, self.own)
        else:
            plat.hide(self.root, self.own)
        self.shown = on

    def tick(self):
        try:
            self._tick()
        except Exception:
            log(traceback.format_exc())
            self.root.after(500, self.tick)

    def _tick(self):
        now = time.monotonic()
        # Не догоняем пропущенные секунды одним рывком при пробуждении компьютера.
        dt = min(2.0, (now - self.last_tick) / TICK_SECONDS)
        self.last_tick = now
        previous_frame = self.frame
        self.frame += dt
        claude, name = plat.find_target(self.target if self.target[0] else None, target_name)
        if claude is not None:
            if name != self.target[1]:
                self.placed, self.held = False, False
                self.activities.greeting.cancel()
                log(f"окно: {name} {plat.window_rect(claude)}")
            self.target = (claude, name)            # обновляем и при смене окна того же приложения
        if previous_frame < 150 <= self.frame and self.target[1] is None:
            log(f"за 5 секунд не нашла окно из {TARGETS}. Сейчас на экране: {plat.describe()}")
            self.placed, self.held = False, False
        if claude is None or plat.is_minimized(claude):
            self.activities.greeting.cancel()
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
                self.start_fall()

        self.step(dt)
        visible = self.held or self.mode == "fall" or plat.is_foreground(claude, self.own)
        self.update_sleep(visible, now)
        self.update_cursor(visible, dt)
        if visible:
            name, drop = self.pick()
            bob = 1 if self.mode == "idle" and self.activities.greeting.remaining <= 0 and (self.frame // 25) % 2 else 0
            wx = l + round(self.X) - self.cw // 2
            wy = b + round(self.Y) - self.base - bob
            self.present(self.img.get(name, self.img["front"]), self.base + drop, wx, wy)
            self.set_shown(True)
        else:
            self.set_shown(False)
        moving = self.mode in ("held", "fall", "land", "tip", "crash", "get_up", "edge_rise",
                               "sit_back", "wake", "walk", "turn", "climb_up", "climb_down")
        sitting_to_play = self.mode == "game" and self.timer > self.activities.game_length - walk.SEAT_TICKS
        period = MOTION_FRAME_MS if moving or sitting_to_play else TICK_MS
        spent_ms = (time.monotonic() - now) * 1000
        self.root.after(max(1, round(period - spent_ms)), self.tick)


if __name__ == "__main__":
    log(f"--- старт: {sys.platform}, Python {sys.version.split()[0]}, Tk {tk.TkVersion}")
    try:
        Mascot().root.mainloop()
    except KeyboardInterrupt:
        pass
    except Exception:
        log(traceback.format_exc())
        raise

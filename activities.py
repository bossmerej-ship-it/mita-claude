"""Добровольные занятия Миты и их позы. Один такт анимации равен 33 мс."""

import random

import fall_motion
import walk_motion


CELL = (61, 90)
UNPACK = ("game_reach", "game_pocket", "game_lift", "game_ready")
PLAY = tuple(f"game_play{i}" for i in range(4))
GAME_ROWS = (UNPACK, PLAY)
FREE_MODES = ("walk", "turn", "perch", "idle", "look")
GREET_MODES = ("walk", "perch", "idle", "look", "sit", "game")
GESTURES = ("notice", "raise", "wave_in", "wave_out")
GREET_ROWS = tuple(tuple(f"{posture}_{name}" for name in GESTURES)
                   for posture in ("stand", "seat", "pad"))


class CursorGreeting:
    def __init__(self):
        self.cooldown = 0.0
        self.direction = 1
        self.wave = False
        self.cancel()

    def cancel(self):
        self.anchor = None
        self.dwell = self.remaining = 0.0
        self.latched = False

    def update(self, point, center, direction, scale, dt):
        self.remaining = max(0, self.remaining - dt)
        self.cooldown = max(0, self.cooldown - dt)
        x, y = point
        dx, dy = x - center[0], y - center[1]
        if (dx / (56 * scale))**2 + (dy / (56 * scale))**2 > 1:
            self.anchor, self.dwell, self.latched = None, 0.0, False
            return
        if self.remaining > 0:
            if abs(dx) > 9 * scale:
                self.direction = 1 if dx > 0 else -1
            return
        if self.latched or self.cooldown > 0:
            return
        if self.anchor is None or max(abs(x-self.anchor[0]), abs(y-self.anchor[1])) > 8 * scale:
            self.anchor, self.dwell = point, 0.0
        self.dwell += dt
        if self.dwell >= 30:
            self.direction = direction if abs(dx) < 3 * scale else (1 if dx > 0 else -1)
            self.wave = random.random() < .45
            self.remaining = 50 if self.wave else 34
            self.cooldown, self.latched = 180, True

    def pose(self, mode, seated):
        posture = "pad" if mode == "game" else ("seat" if seated else "stand")
        gesture = "notice"
        if self.wave:
            age = 50 - self.remaining
            if 6 <= age < 40:
                sequence = ("raise", "wave_in", "wave_out", "wave_in", "wave_out", "raise")
                gesture = sequence[min(len(sequence)-1, int((age-6) / 6))]
        return f"{posture}_{gesture}" + ("_left" if self.direction < 0 else "")


class Activities:
    def __init__(self):
        self.game_wait = 150.0
        self.game_length = 0
        self.greeting = CursorGreeting()

    def begin_game(self, seated):
        self.game_length = random.randint(300, 440)
        self.game_wait = random.randint(900, 1500)
        return self.game_length - (16 if seated else 0)

    def game_pose(self, remaining, direction, walk_pixels, scale, leg):
        age = self.game_length - remaining
        left = "_left" if direction < 0 else ""
        if age < 3:
            return walk_motion.sprite(walk_pixels, scale, -direction), 0
        if age < 6:
            return ("front34_left" if direction < 0 else "front34"), 0
        if age < 9:
            return "front", 0
        if age < 16:
            return "sit1" + left, fall_motion.eased_drop((age - 9) / 7, leg)
        if age < 32:
            name = UNPACK[int((age - 16) / 4)]
        elif remaining <= 3:
            name = "sit1"
        elif remaining < 19:
            name = UNPACK[int((remaining - 3) / 4)]
        else:
            name = PLAY[int((age - 32) / 5) % len(PLAY)]
        return name + left, leg

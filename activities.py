"""Добровольные занятия Миты и их позы. Один такт анимации равен 33 мс."""

import random

import fall_motion
import walk_motion


CELL = (61, 90)
UNPACK = ("game_reach", "game_pocket", "game_lift", "game_ready")
PLAY = tuple(f"game_play{i}" for i in range(4))
GAME_ROWS = (UNPACK, PLAY)
FREE_MODES = ("walk", "turn", "perch", "idle", "look")


class Activities:
    def __init__(self):
        self.game_wait = 150.0
        self.game_length = 0

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

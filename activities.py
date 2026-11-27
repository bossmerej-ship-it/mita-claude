"""Добровольные занятия Миты и их позы. Один такт анимации равен 33 мс."""

import random
import math

import fall_motion
import rise_motion
import walk_motion


CELL = (61, 90)
UNPACK = ("game_reach", "game_pocket", "game_lift", "game_ready")
PLAY = tuple(f"game_play{i}" for i in range(4))
GAME_ROWS = (UNPACK, PLAY)
CONSOLE_LINK_ROWS = tuple(tuple(f"console_step{stage}_{i}" for i in range(3)) for stage in range(5))
UNPACK_SEQUENCE = tuple(name for keys, end in zip(CONSOLE_LINK_ROWS, (*UNPACK, PLAY[0]))
                        for name in (*keys, end))
UNPACK_TICKS = len(UNPACK_SEQUENCE)
PLAY_START = walk_motion.SEAT_TICKS + UNPACK_TICKS
PACK_TICKS = UNPACK_TICKS + 3
FREE_MODES = ("walk", "turn", "perch", "idle", "look")
GREET_MODES = ("walk", "perch", "idle", "look", "sit", "game")
ATTENTION = tuple(f"attention{i}" for i in range(4))
RAISE = (*(f"lift{i}" for i in range(4)), "raise")
UNFOLD = (*(f"unfold{i}" for i in range(4)), "wave_in")
SWEEP = (*(f"sweep{i}" for i in range(4)), "wave_out")
GREET_ROWS = tuple(tuple(f"{posture}_{side}{name}" for name in (*ATTENTION, "notice", *RAISE, *UNFOLD, *SWEEP))
                   for posture in ("stand", "seat", "pad") for side in ("", "far_"))
SLEEP_AFTER_SECONDS = 60
REST_GESTURES = ("drowsy", "lift", "yawning", "cover", "settle", "nod", "droop",
                 "breathe_in", "breathe_out", "rub_in", "rub_out", "blink")
HELD_RUB = ("held_rub_in", "held_rub_out", "held_blink")
REST_ROWS = tuple(tuple(f"{place}_{name}" for name in REST_GESTURES)
                  for place in ("edge", "floor")) + (HELD_RUB,)
REST_PHASES = {
    "yawn": ((7, "drowsy"), (13, "lift"), (24, "yawning"), (38, "cover"), (48, "settle")),
    "doze": ((17, "settle"), (30, "nod"), (40, "droop"), (49, "nod"), (59, "settle"),
             (66, "nod"), (72, "droop")),
    "wake": ((6, "rub_in"), (12, "rub_out"), (18, "rub_in"), (24, "rub_out"),
             (30, "blink"), (34, "drowsy")),
}
REST_MODES = (*REST_PHASES, "sleep")
CAN_START_REST = ("walk", "perch", "idle", "look", "sit")
RUB_TICKS = 28
REST_PAIRS = (("drowsy", "lift"), ("lift", "yawning"), ("yawning", "cover"), ("cover", "settle"),
              ("settle", "nod"), ("nod", "droop"), ("droop", "breathe_in"), ("breathe_in", "breathe_out"),
              ("rub_in", "rub_out"), ("rub_out", "blink"), ("blink", "drowsy"))
WAKE_FROM = ("drowsy", "lift", "yawning", "cover", "settle", "nod", "droop", "breathe_in", "breathe_out")
REST_LINKS = REST_PAIRS + tuple((name, "rub_in") for name in WAKE_FROM)
REST_LINK_ROWS = tuple(tuple(f"{place}_{a}_to_{b}_{i}" for i in range(3))
                       for place in ("floor", "edge") for a, b in REST_LINKS)


class PoseClip:
    """Short, interruptible sequences of (sprite, sole offset) in simulation time."""
    frame_ticks = .7

    def __init__(self):
        self.play(())

    def play(self, poses):
        self.frames = tuple(poses)
        self.remaining = len(self.frames) * self.frame_ticks

    def pose(self):
        i = len(self.frames) - math.ceil(self.remaining / self.frame_ticks - 1e-9)
        return self.frames[min(i, len(self.frames) - 1)]

    def advance(self, dt):
        used = min(dt, self.remaining)
        self.remaining -= used
        if self.remaining < 1e-9:
            self.remaining = 0
        return dt - used


def rest_between(name, next_name, until):
    if until > 3:
        return name
    i = min(2, max(0, int(3 - until)))
    if (name, next_name) in REST_PAIRS:
        return f"{name}_to_{next_name}_{i}"
    if (next_name, name) in REST_PAIRS:
        return f"{next_name}_to_{name}_{2-i}"
    return name


def rest_pose(mode, timer, direction, on_ledge, initial_drop, leg):
    if mode == "wake" and not on_ledge and timer <= rise_motion.WAKE_TICKS:
        return rise_motion.floor_pose(timer, direction, waking=True)
    if mode == "sleep":
        a, b = ("breathe_in", "breathe_out") if int(timer / 24) % 2 == 0 else ("breathe_out", "breathe_in")
        name = rest_between(a, b, 24 - timer % 24)
        drop = leg
    else:
        phases = REST_PHASES[mode]
        age = phases[-1][0] - timer
        i = next((i for i, (end, _) in enumerate(phases) if age < end), len(phases)-1)
        end, name = phases[i]
        after = phases[i+1][1] if i+1 < len(phases) else ("breathe_in" if mode == "doze" else name)
        if mode == "wake" and not on_ledge and end == 24:
            after = "rub_out"  # First cel of the standing-up sequence.
        name = rest_between(name, after, end - age)
        drop = leg if mode == "doze" else initial_drop + fall_motion.eased_drop(age / 10, leg - initial_drop)
    place = "edge" if on_ledge else "floor"
    return f"{place}_{name}" + ("_left" if direction < 0 else ""), drop if on_ledge else 0


def held_rub_pose(remaining, direction):
    age = RUB_TICKS - remaining
    name = HELD_RUB[2] if remaining <= 6 else HELD_RUB[int(age / 5) % 2]
    return name + ("_left" if direction < 0 else ""), 0


class CursorGreeting:
    def __init__(self):
        self.cooldown = 0.0
        self.direction = 1
        self.wave = False
        self.clip = PoseClip()
        self.cancel()

    def cancel(self):
        self.anchor = None
        self.dwell = 0.0
        self.clip.play(())
        self.latched = False

    @property
    def remaining(self):
        return self.clip.remaining

    def update(self, point, center, direction, scale, dt):
        self.clip.advance(dt)
        self.cooldown = max(0, self.cooldown - dt)
        x, y = point
        dx, dy = x - center[0], y - center[1]
        if (dx / (56 * scale))**2 + (dy / (56 * scale))**2 > 1:
            self.anchor, self.dwell, self.latched = None, 0.0, False
            return
        if self.remaining > 0 or self.latched or self.cooldown > 0:
            return
        if self.anchor is None or max(abs(x-self.anchor[0]), abs(y-self.anchor[1])) > 8 * scale:
            self.anchor, self.dwell = point, 0.0
        self.dwell += dt
        if self.dwell >= 30:
            self.direction = direction if abs(dx) < 3 * scale else (1 if dx > 0 else -1)
            self.wave = random.random() < .45
            self.cooldown, self.latched = 180, True
            return True

    def begin(self, entry, posture, body_direction, drop):
        side = "" if self.direction == body_direction else "far_"
        suffix = "_left" if body_direction < 0 else ""
        gestures = ["notice"] * (7 if self.wave else 32)
        if self.wave:
            gestures.extend((*RAISE, *UNFOLD, *SWEEP, *reversed(SWEEP[:-1]), "wave_in",
                             *SWEEP, *reversed(SWEEP[:-1]), *reversed(UNFOLD), *reversed(RAISE), "notice"))
        action = [(f"{posture}_{side}{key}{suffix}", drop) for key in (*ATTENTION, *gestures, *reversed(ATTENTION))]
        self.clip.play((*entry, *action, *reversed(entry)))


class Activities:
    def __init__(self):
        self.game_wait = 150.0
        self.game_length = 0
        self.greeting = CursorGreeting()
        self.bridge = PoseClip()
        self.next_idle_check = 0.0
        self.rest_drop = 0
        self.rest_pinned = False
        self.held_rub = 0.0
        self.seat_pause = 0.0

    def begin_game(self, seated, direction):
        self.game_direction = direction
        self.game_length = random.randint(300, 440)
        self.game_wait = random.randint(900, 1500)
        return self.game_length - (walk_motion.SEAT_TICKS if seated else 0)

    def game_pose(self, remaining, direction, walk_pixels, scale, leg):
        age = self.game_length - remaining
        left = "_left" if direction < 0 else ""
        if age < walk_motion.SEAT_TICKS:
            remaining_seat = walk_motion.SEAT_TICKS - age
            return walk_motion.sitting_pose(remaining_seat, direction, walk_pixels, scale)
        if age < PLAY_START:
            name = UNPACK_SEQUENCE[int(age - walk_motion.SEAT_TICKS)]
        elif remaining <= 3:
            name = "sit1"
        elif remaining < PACK_TICKS:
            name = UNPACK_SEQUENCE[int(remaining - 3)]
        else:
            name = PLAY[int((age - PLAY_START) / 5) % len(PLAY)]
        return name + left, leg

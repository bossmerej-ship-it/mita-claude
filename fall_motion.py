"""Позы и движение Миты между отпусканием мыши и приземлением."""

import math
import tkinter as tk
from bisect import bisect_right
from itertools import accumulate


# Ячейки атласа нарисованы в исходном разрешении, по центру нижней границы.
CELL = (79, 90)
POSE_ROWS = (
    ("release1", "release2", "release3", "release4"),
    ("lean1", "lean2", "lean3", "lean4"),
    ("flutter1", "flutter2", "contact1", "contact2"),
    ("cushion1", "cushion2", "cushion3"),
)
AIR = ("held", *POSE_ROWS[0], "fall_panic", *POSE_ROWS[1], "fall_dive")
FLUTTER = ("fall_panic", "flutter1", "flutter2", "flutter1")
CUSHION = ("cushion1", "cushion3", "squash", "cushion3", "cushion2", "cushion1", "front")
DRAG_WINDOW = 0.11  # секунды
IMPACT = (("contact1", 1), ("contact2", 1.5), ("crash_impact", 3), ("crash_tears", 9),
          ("dazed1", 12), ("dazed2", 7), ("dazed1", 12), ("dazed2", 7))
IMPACT_ENDS = tuple(accumulate(ticks for _, ticks in IMPACT))
IMPACT_TICKS = IMPACT_ENDS[-1]


def impact_pose(remaining):
    i = min(len(IMPACT) - 1, bisect_right(IMPACT_ENDS, IMPACT_TICKS - remaining))
    return IMPACT[i][0]


def load_poses(root, path, scale, *, cell=CELL, rows=POSE_ROWS):
    sheet = tk.PhotoImage(master=root, file=str(path))
    width, height = cell
    poses = {}
    for row, names in enumerate(rows):
        for column, name in enumerate(names):
            x, y = column * width, row * height
            image = tk.PhotoImage(master=root)
            root.tk.call(image, "copy", sheet, "-from", x, y, x + width, y + height,
                         "-zoom", scale, scale)
            poses[name] = image
            poses[name + "_left"] = image.subsample(-1, 1)
    return poses


def record_drag(samples, now, point):
    samples.append((now, *point))
    # Оставляем одну точку до границы интервала для интерполяции.
    while len(samples) > 2 and samples[1][0] <= now - DRAG_WINDOW:
        samples.popleft()


def throw_velocity(samples, now, tick_seconds):
    """Скорость в пикселях за обычный такт, независимо от частоты событий мыши."""
    if len(samples) < 2 or now - samples[-1][0] >= DRAG_WINDOW:
        return 0.0, 0.0
    start = max(samples[0][0], now - DRAG_WINDOW)
    t0, x0, y0 = samples[0]
    for t1, x1, y1 in samples:
        if t1 > start:
            fraction = (start - t0) / (t1 - t0)
            x0 += (x1 - x0) * fraction
            y0 += (y1 - y0) * fraction
            break
        t0, x0, y0 = t1, x1, y1
    _, x, y = samples[-1]
    factor = tick_seconds / max(now - start, .016)
    return max(-22, min(22, (x - x0) * factor)), max(-22, min(22, (y - y0) * factor))


def fall_travel(speed, ticks, gravity, terminal):
    """Точно интегрируем ускорение, в том числе при достижении предельной скорости."""
    speed = min(speed, terminal)
    accelerating = min(ticks, (terminal - speed) / gravity) if gravity > 0 else ticks
    end_speed = speed + gravity * accelerating
    distance = (speed + end_speed) * .5 * accelerating + end_speed * (ticks - accelerating)
    return distance, end_speed


def crossing_time(gap, speed, gravity, terminal):
    """Момент, когда ноги пересекут горизонталь сверху вниз (не на взлёте)."""
    speed = min(speed, terminal)
    if gravity <= 0:
        return gap / speed if gap >= 0 and speed > 0 else math.inf
    squared = speed * speed + 2 * gravity * gap
    if squared < 0:
        return math.inf
    impact = math.sqrt(squared)
    if impact <= terminal:
        ticks = (impact - speed) / gravity
    else:
        accelerating = (terminal - speed) / gravity
        ticks = accelerating + (gap - (speed + terminal) * .5 * accelerating) / terminal
    return ticks if ticks >= 0 else math.inf


def approach_pose(current, goal, ticks):
    # Переход от спокойной позы к раскрытым рукам занимает примерно 130 мс.
    change = .26 * ticks
    return current + max(-change, min(change, goal - current))


def air_sprite(pose, age):
    # 0 — отпустили, 1 — руки в стороны, 2 — наклон в направлении броска.
    name = AIR[round(pose * (len(AIR) - 1) / 2)]
    if name == "fall_panic":
        return FLUTTER[int(age / 3.5) % len(FLUTTER)]
    return name


def eased_drop(progress, leg):
    progress = max(0.0, min(1.0, progress))
    return round(leg * progress * progress * (3 - 2 * progress))

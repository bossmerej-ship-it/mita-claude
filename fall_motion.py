"""Позы и движение Миты между отпусканием мыши и приземлением."""

import tkinter as tk


# Ячейки атласа нарисованы в исходном разрешении, по центру нижней границы.
CELL = (79, 90)
POSE_ROWS = (
    ("release1", "release2", "release3", "release4"),
    ("lean1", "lean2", "lean3", "lean4"),
    ("flutter1", "flutter2", "contact1", "contact2"),
    ("cushion1", "cushion2", "cushion3"),
    ("lift1", "lift2"),
    ("situp1", "situp2"),
    ("rise1", "rise2", "rise3"),
    ("stand1", "stand2"),
)
AIR = ("held", *POSE_ROWS[0], "fall_panic", *POSE_ROWS[1], "fall_dive")
FLUTTER = ("fall_panic", "flutter1", "flutter2", "flutter1")
CUSHION = ("cushion1", "cushion3", "squash", "cushion3", "cushion2", "cushion1", "front")
DRAG_WINDOW = 0.11  # секунды


def load_poses(root, path, scale):
    sheet = tk.PhotoImage(master=root, file=str(path))
    width, height = CELL
    poses = {}
    for row, names in enumerate(POSE_ROWS):
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

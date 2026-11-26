"""Шаги в исходных пикселях спрайта и позы разворота на месте."""

import rise_motion as rise

CELL = (49, 88)
CYCLE = tuple(f"walk{i:02d}" for i in range(32))
FIRST_STEP = tuple(f"step_in{i}" for i in range(8))
POSE_ROWS = tuple(CYCLE[i:i + 8] for i in range(0, len(CYCLE), 8)) + (FIRST_STEP,)

START_TICKS = 4.0
PLANT_FRAMES = 4
PLANT_TICKS = 3.0
_PLANTS = tuple(f"plant_{stride}_{i}" for stride in CYCLE + FIRST_STEP for i in range(1, PLANT_FRAMES + 1))
PLANT_ROWS = tuple(_PLANTS[i:i + 8] for i in range(0, len(_PLANTS), 8))
PIVOT_FRAME_TICKS = .55
TURN_TICKS = PLANT_TICKS + 2 * len(rise.PIVOT) * PIVOT_FRAME_TICKS
SEAT_TICKS = PLANT_TICKS + rise.EDGE_TICKS


def travel(age, dt, speed):
    """Плавно набираем скорость в начале прогулки, в том числе между двумя кадрами."""
    ramp = min(dt, max(0.0, START_TICKS - age))
    return speed * (ramp * (age + ramp / 2) / START_TICKS + (dt - ramp))


def stride_name(pixels, scale):
    # Один исходный пиксель пути на позу. После первого шага дальняя нога уже впереди.
    distance = pixels // scale
    if distance < len(FIRST_STEP):
        return FIRST_STEP[distance]
    since_contact = distance - len(FIRST_STEP)
    return CYCLE[(len(CYCLE) // 2 + since_contact) % len(CYCLE)]


def sprite(pixels, scale, direction):
    return stride_name(pixels, scale) + ("_left" if direction < 0 else "")


def plant_sprite(age, direction, pixels, scale):
    stride = stride_name(pixels, scale)
    i = min(PLANT_FRAMES, max(0, int(age * (PLANT_FRAMES + 1) / PLANT_TICKS)))
    name = f"plant_{stride}_{i}" if i else stride
    return name + ("_left" if direction < 0 else "")


def turn_sprite(timer, direction, pixels, scale):
    age = TURN_TICKS - timer
    if age < PLANT_TICKS:
        return plant_sprite(age, -direction, pixels, scale)
    n = len(rise.PIVOT)
    i = min(2 * n - 1, int((age - PLANT_TICKS) / PIVOT_FRAME_TICKS))
    if i < n:
        return rise.PIVOT[n - 1 - i] + ("_left" if direction > 0 else "")
    return rise.PIVOT[i - n] + ("_left" if direction < 0 else "")


def sitting_pose(remaining, direction, pixels, scale):
    if remaining > rise.EDGE_TICKS:
        return plant_sprite(SEAT_TICKS - remaining, direction, pixels, scale), 0
    return rise.edge_pose(remaining, direction, 1, scale, sitting_down=True)

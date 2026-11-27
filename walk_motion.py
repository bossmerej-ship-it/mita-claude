"""Шаги в исходных пикселях спрайта и позы разворота на месте."""

import rise_motion as rise

CELL = (49, 88)
CYCLE = tuple(f"walk{i:02d}" for i in range(32))
FIRST_STEP = tuple(f"step_in{i}" for i in range(8))
POSE_ROWS = tuple(CYCLE[i:i + 8] for i in range(0, len(CYCLE), 8)) + (FIRST_STEP,)

START_TICKS = 4.0
PLANT_FRAMES = 7
PLANT_TICKS = 5.0
_PLANTS = tuple(f"plant_{stride}_{i}" for stride in CYCLE + FIRST_STEP for i in range(1, PLANT_FRAMES + 1))
PLANT_ROWS = tuple(_PLANTS[i:i + 8] for i in range(0, len(_PLANTS), 8))
PIVOT_FRAME_TICKS = .55
TURN_TICKS = PLANT_TICKS + 2 * len(rise.PIVOT) * PIVOT_FRAME_TICKS
SEAT_TICKS = PLANT_TICKS + rise.EDGE_TICKS
BREATH = ("idle_in1", "idle_in2", "idle_in3")


def idle_pose(age, direction):
    phase = age % 86
    if phase < 16 or phase >= 70:
        name = "front"
    else:
        index = min(2, int((phase - 16) / 8), int((70 - phase) / 8))
        name = BREATH[index]
    return name + ("_left" if direction < 0 else ""), 0


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


def face_front(pixels, direction, scale):
    stride = stride_name(pixels, scale)
    suffix = "_left" if direction < 0 else ""
    planted = (stride, *(f"plant_{stride}_{i}" for i in range(1, PLANT_FRAMES + 1)))
    return tuple((name + suffix, 0) for name in (*planted, *reversed(rise.PIVOT)))


def look_pose(age, remaining, direction):
    # Turn the head into three-quarter view, hold, then face front before the next action.
    index = min(8, max(0, int(min(age, remaining) / PIVOT_FRAME_TICKS)))
    return rise.PIVOT[index] + ("_left" if direction < 0 else ""), 0


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

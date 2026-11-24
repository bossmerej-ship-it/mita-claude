"""Шаги в исходных пикселях спрайта и позы разворота на месте."""

CELL = (49, 88)
CYCLE = tuple(f"walk{i:02d}" for i in range(32))
FIRST_STEP = tuple(f"step_in{i}" for i in range(8))
POSE_ROWS = tuple(CYCLE[i:i + 8] for i in range(0, len(CYCLE), 8)) + (FIRST_STEP,)

START_TICKS = 4.0
TURN_TICKS = 12
# Исходный front34 смотрит влево, исходный side — вправо.
TURN_RIGHT = ("front34", "front", "front34_left", FIRST_STEP[0])
TURN_LEFT = ("front34_left", "front", "front34", FIRST_STEP[0] + "_left")


def travel(age, dt, speed):
    """Плавно набираем скорость в начале прогулки, в том числе между двумя кадрами."""
    ramp = min(dt, max(0.0, START_TICKS - age))
    return speed * (ramp * (age + ramp / 2) / START_TICKS + (dt - ramp))


def sprite(pixels, scale, direction):
    # Один исходный пиксель пути на позу. После первого шага дальняя нога уже впереди.
    distance = pixels // scale
    if distance < len(FIRST_STEP):
        name = FIRST_STEP[distance]
    else:
        since_contact = distance - len(FIRST_STEP)
        name = CYCLE[(len(CYCLE) // 2 + since_contact) % len(CYCLE)]
    return name + ("_left" if direction < 0 else "")


def turn_sprite(timer, direction, pixels, scale):
    views = TURN_RIGHT if direction > 0 else TURN_LEFT
    index = min(len(views), int((TURN_TICKS - timer) * (len(views) + 1) / TURN_TICKS))
    if index <= 0:
        return sprite(pixels, scale, -direction)
    return views[index - 1]

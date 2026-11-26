"""Подъём с пола и с края поля. Кадры привязаны к опоре в исходных пикселях."""

import math

CELL = (79, 90)
FRAME_TICKS = .75


def frames(prefix, count):
    return tuple(f"{prefix}{i:02d}" for i in range(count))


GROUND = tuple(name for stage, count in (
    ("push_up", 16), ("tuck_knees", 12), ("brace", 8), ("plant_foot", 20),
    ("straighten", 14), ("brush_off", 10), ("lower_arms", 12), ("face_front", 8),
) for name in frames(stage, count))
GROUND_TICKS = len(GROUND) * FRAME_TICKS

# Первые кадры продолжают взмах той ноги, которая была поднята у сидящей Миты.
SWINGS = (frames("edge_left_foot", 12), frames("edge_right_foot", 12))
PLANT = frames("edge_stand", 12)
PIVOT = frames("edge_pivot", 17)
LIFT = tuple(swing + PLANT for swing in SWINGS)
EDGE = tuple(lift + PIVOT for lift in LIFT)
LIFT_TICKS = len(LIFT[0]) * FRAME_TICKS
EDGE_TICKS = len(EDGE[0]) * FRAME_TICKS
TOE_BELOW_EDGE = (14, 14, 14, 14, 14, 13, 12, 10, 9, 7, 5, 4, 2, 1)

WAKE = frames("wake_stand", 16)
WAKE_TICKS = 10
POSE_ROWS = (tuple(GROUND[i:i + 10] for i in range(0, len(GROUND), 10))
             + SWINGS + (PLANT, PIVOT[:9], PIVOT[9:], WAKE[:8], WAKE[8:]))


def frame_index(remaining, duration, count):
    return min(count - 1, max(0, int((duration - remaining) * count / duration)))


def floor_pose(remaining, direction, *, waking=False):
    poses, duration = (WAKE, WAKE_TICKS) if waking else (GROUND, GROUND_TICKS)
    i = frame_index(remaining, duration, len(poses))
    return poses[i] + ("_left" if direction < 0 else ""), 0


def edge_pose(remaining, direction, swing, scale, *, sitting_down=False):
    poses = EDGE[swing]
    if sitting_down:
        i = max(0, min(len(poses) - 1, math.ceil(remaining / FRAME_TICKS) - 1))
    else:
        i = frame_index(remaining, EDGE_TICKS, len(poses))
    offset = TOE_BELOW_EDGE[i] * scale if i < len(TOE_BELOW_EDGE) else 0
    return poses[i] + ("_left" if direction < 0 else ""), offset

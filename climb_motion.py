"""A side climb, measured from the actual rail and lip in native sprite pixels."""

import math

import rise_motion
import walk_motion

CELL = (61, 90)
PERIOD = 24
CREST_HEIGHT = 40
OUTSIDE = 11
INSIDE = 6
GRIP_FRAMES = 7
CREST_FRAMES = 33
FRAME_TICKS = .75
GRIPS = tuple(tuple(f"grip{phase:02}_{i}" for i in range(GRIP_FRAMES)) for phase in range(PERIOD))
RAIL = tuple(f"rail{i:02}" for i in range(PERIOD))
CREST = tuple(f"crest{i:02}" for i in range(CREST_FRAMES))
ROWS = GRIPS + tuple(frames[i:i+8] for frames in (RAIL, CREST) for i in range(0, len(frames), 8))


def ease(t):
    return t * t * (3 - 2 * t)


class Climb:
    def __init__(self, upward, inward, edge, width, top, bottom, start_x, stride, scale, speed):
        self.upward, self.inward = upward, inward
        self.edge, self.top, self.bottom, self.start_x = edge, top, bottom, start_x
        self.scale, self.speed = scale, speed * scale
        self.inset = min(INSIDE * scale, width / 2)
        self.outside = OUTSIDE * scale
        self.wall = max(0, bottom - top - CREST_HEIGHT * scale)
        # A shallow card starts partway through the pull over the lip.
        fraction = 1 - min(1, (bottom - top) / (CREST_HEIGHT * scale))
        self.crest_start = 0 if not fraction else .5 - math.sin(math.asin(1 - 2 * fraction) / 3)
        self.crest_ticks = (CREST_FRAMES - 1) * FRAME_TICKS
        self.grip_phase = round(-self.wall / scale) % PERIOD
        self.grip_ticks = (GRIP_FRAMES + 1) * FRAME_TICKS
        self.rail_end = self.grip_ticks + self.wall / self.speed
        self.travel_ticks = self.rail_end + (1 - self.crest_start) * self.crest_ticks
        direction = inward if upward else -inward
        approach = walk_motion.face_front(stride, direction, scale)
        self.suffix = "_left" if inward < 0 else ""
        if upward:
            self.entry = approach[:walk_motion.PLANT_FRAMES + 1]
        else:
            self.entry = approach + tuple((key + self.suffix, 0) for key in rise_motion.PIVOT)
        self.entry_ticks = len(self.entry) * FRAME_TICKS
        self.duration = self.entry_ticks + self.travel_ticks
        self.age = 0.0

    def attached(self, edge, top, card_bottom, reach):
        return (abs(edge - self.edge) <= 2 * self.scale and abs(top - self.top) <= 2 * self.scale
                and self.position()[1] <= card_bottom + reach + 1)

    def local_time(self):
        t = max(0, min(self.travel_ticks, self.age - self.entry_ticks))
        return t if self.upward else self.travel_ticks - t

    def crest_progress(self, t):
        return min(1.0, self.crest_start + max(0, t - self.rail_end) / self.crest_ticks)

    def lip_position(self, progress):
        weight = ease(progress)
        return (self.edge + self.inward * (-self.outside + (self.outside + self.inset) * weight),
                self.top + CREST_HEIGHT * self.scale * (1 - weight))

    def position(self):
        t = self.local_time()
        if t >= self.rail_end:
            x, y = self.lip_position(self.crest_progress(t))
        else:
            x = self.lip_position(self.crest_start)[0]
            y = self.bottom - max(0, t - self.grip_ticks) * self.speed
        if self.age < self.entry_ticks:
            x = self.start_x + (x - self.start_x) * ease(self.age / self.entry_ticks)
        return x, y

    def pose(self):
        if self.age < self.entry_ticks:
            return self.entry[int(self.age / FRAME_TICKS)]
        t = self.local_time()
        if t < self.grip_ticks:
            i = int(t / FRAME_TICKS)
            name = walk_motion.FIRST_STEP[0] if i == 0 else GRIPS[self.grip_phase][i-1]
        elif t < self.rail_end:
            phase = round((t - self.rail_end) * self.speed / self.scale) % PERIOD
            name = RAIL[phase]
        else:
            name = CREST[round(self.crest_progress(t) * (CREST_FRAMES-1))]
        return name + self.suffix, 0

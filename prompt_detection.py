"""Locate a composer using accessibility geometry, without reading its text."""

import math
import threading
import time


def rectangle(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    if not all(isinstance(n, (int, float)) and math.isfinite(n) for n in value):
        return None
    l, t, r, b = value
    return (l, t, r, b) if r > l and b > t else None


def composer_frame(edit, parents, window):
    l, t, r, b = edit
    wl, wt, wr, wb = window
    styled = fallback = None
    for parent in parents:
        hint = ""
        if isinstance(parent, dict):
            hint = str(parent.get("hint", "")).lower()
            parent = parent.get("rect")
        bounds = rectangle(parent)
        if bounds is None:
            continue
        pl, pt, pr, pb = bounds
        if not (wl <= pl <= l <= r <= pr <= wr and wt <= pt <= t <= b <= pb <= wb):
            continue
        if max(l - pl, pr - r) > max(80, (r - l) * .12) or pb - pt > (wb - wt) * .8:
            continue
        # The painted card can grow upwards by an entire attachment preview.
        # Its body wins even when the first ancestor fits only the editor text.
        if any(tag in hint for tag in ("composerlayoutbody", "composer-surface", "composer-card")):
            return bounds
        if styled is None and "rounded-" in hint and any(tag in hint for tag in ("bg-", "border", "ring-", "shadow")):
            styled = bounds
        if (bounds != edit and fallback is None and "contents" not in hint.split()
                and "footer" not in hint and t - pt <= 80 and pb - b <= 160
                and pb - pt <= b - t + 180):
            fallback = bounds
    return styled or fallback or edit


def choose_prompt(candidates, window):
    """Prefer a known composer, otherwise a large editor in the lower window."""
    window = rectangle(window)
    if window is None:
        return None
    wl, wt, wr, wb = window
    width, height = wr - wl, wb - wt
    choices = []
    for candidate in candidates:
        edit = rectangle(candidate.get("rect"))
        if edit is None:
            continue
        l, t, r, b = edit
        if l < wl or r > wr or t < wt or b > wb or r - l < 160 or b - t < 16:
            continue
        hint = str(candidate.get("hint", "")).lower()
        known = any(s in hint for s in ("prosemirror", "tiptap", "prompt", "composer", "lexical"))
        if not known and (t < wt + height * .5 or r - l < width * .35):
            continue
        if b - t > height * .65:
            continue
        surface = composer_frame(edit, candidate.get("parents", []), window)
        score = (int(known), b, r - l)
        choices.append((score, surface))
    return max(choices, default=(None, None), key=lambda item: item[0])[1]


class PromptDetector:
    """Poll off the Tk thread and expire stale surfaces when a composer closes."""

    def __init__(self, read, interval=.25, lifetime=1.5):
        self.read = read
        self.interval, self.lifetime = interval, lifetime
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.pending = None
        self.result = None
        self.last_key, self.last_size, self.last_request = None, None, -math.inf
        self.thread = None

    def has_sample(self, key):
        with self.lock:
            return self.result is not None and self.result[0] == key

    def get(self, key, target, window):
        now = time.monotonic()
        l, t, r, b = window
        size = (r - l, b - t)
        with self.lock:
            if key != self.last_key or size != self.last_size or now - self.last_request >= self.interval:
                self.pending = (key, target)
                self.last_key, self.last_size, self.last_request = key, size, now
                self.wake.set()
                if self.thread is None:
                    self.thread = threading.Thread(target=self._run, daemon=True)
                    self.thread.start()
            result = self.result
        if result is None or result[0] != key or now - result[2] > self.lifetime or result[1] is None:
            return None
        # Anchor to the center/bottom until the next scan, including while moving.
        dx1, dy1, dx2, dy2 = result[1]
        return ((l + r) / 2 + dx1, b + dy1, (l + r) / 2 + dx2, b + dy2)

    def _run(self):
        while True:
            self.wake.wait()
            with self.lock:
                job, self.pending = self.pending, None
                self.wake.clear()
            if job is None:
                continue
            key, target = job
            relative = None
            try:
                surface, window = self.read(target)
                if rectangle(surface) and rectangle(window):
                    l, t, r, b = window
                    x1, y1, x2, y2 = surface
                    relative = (x1 - (l+r)/2, y1 - b, x2 - (l+r)/2, y2 - b)
            except Exception:
                # Inaccessible or closing applications are not fatal to animation.
                pass
            with self.lock:
                self.result = (key, relative, time.monotonic())

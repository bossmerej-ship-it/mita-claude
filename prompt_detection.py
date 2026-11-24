"""Locate a composer using accessibility geometry, without reading its text."""

import math


def rectangle(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    if not all(isinstance(n, (int, float)) and math.isfinite(n) for n in value):
        return None
    l, t, r, b = value
    return (l, t, r, b) if r > l and b > t else None


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
        surface = edit
        # The editor's compact enclosing group includes its padding and toolbar.
        # Stop before a transcript, sidebar, or other large page container.
        for parent in candidate.get("parents", []):
            parent = rectangle(parent)
            if parent is None:
                continue
            pl, pt, pr, pb = parent
            if (pl < wl or pr > wr or pt < wt or pb > wb
                    or pl > l or pt > t or pr < r or pb < b
                    or l - pl > 80 or pr - r > 80 or t - pt > 80
                    or pb - b > 160 or pb - pt > min(height * .65, b - t + 180)):
                break
            surface = parent
        score = (int(known), b, r - l)
        choices.append((score, surface))
    return max(choices, default=(None, None), key=lambda item: item[0])[1]

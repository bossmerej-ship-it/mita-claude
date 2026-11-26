"""macOS Accessibility composer geometry (requires Accessibility permission)."""

import time

from prompt_detection import choose_prompt


def read_prompt(win):
    try:
        import ApplicationServices as ax
    except ImportError:
        return None, None
    if not ax.AXIsProcessTrusted():
        return None, None

    def attribute(element, name):
        error, value = ax.AXUIElementCopyAttributeValue(element, name, None)
        return value if error == 0 else None

    def bounds(element):
        pos, size = attribute(element, "AXPosition"), attribute(element, "AXSize")
        if pos is None or size is None:
            return None
        ok_pos, point = ax.AXValueGetValue(pos, ax.kAXValueTypeCGPoint, None)
        ok_size, dims = ax.AXValueGetValue(size, ax.kAXValueTypeCGSize, None)
        if not ok_pos or not ok_size:
            return None
        return (point[0], point[1], point[0] + dims[0], point[1] + dims[1])

    app = ax.AXUIElementCreateApplication(win["pid"])
    ax.AXUIElementSetMessagingTimeout(app, .15)
    # Chromium lazily exposes its editor to accessibility clients.
    ax.AXUIElementSetAttributeValue(app, "AXEnhancedUserInterface", True)
    windows = attribute(app, "AXWindows") or []
    selected, selected_bounds = None, None
    for window in windows:
        rect = bounds(window)
        if rect and max(abs(a-b) for a, b in zip(rect, win["bounds"])) < 8:
            selected, selected_bounds = window, rect
            break
    if selected is None:
        return None, None

    pending, candidates = [(selected, [], 0)], []
    deadline = time.monotonic() + .4
    visited = 0
    while pending and visited < 400 and time.monotonic() < deadline:
        element, parents, depth = pending.pop()
        visited += 1
        role = attribute(element, "AXRole")
        if role in ("AXTextArea", "AXTextField") and attribute(element, "AXEnabled") is not False:
            frames = []
            for ancestor, rect in parents:
                classes = attribute(ancestor, "AXDOMClassList") or []
                class_name = classes if isinstance(classes, str) else " ".join(classes)
                identifier = attribute(ancestor, "AXIdentifier") or ""
                frames.append({"rect": rect, "hint": f"{identifier} {class_name}"})
            candidates.append({"rect": bounds(element), "parents": frames,
                               "hint": attribute(element, "AXIdentifier") or ""})
        if depth < 20:
            rect = bounds(element)
            ancestors = ([(element, rect)] + parents)[:9] if rect else parents
            # Visit the bottom/end of the view first, before a long transcript.
            for child in attribute(element, "AXChildren") or []:
                pending.append((child, ancestors, depth + 1))
    return choose_prompt(candidates, selected_bounds), selected_bounds

"""A short, opaque-pixel in-between when the mouse interrupts an arbitrary pose."""

import struct
import tkinter as tk
import zlib


def _rows(image, scale):
    native = image.subsample(scale) if scale > 1 else image
    w, h = native.width(), native.height()
    length = w * h * 3
    black, white = (native.tk.call(native, "data", "-format", "ppm", "-background", matte)[-length:]
                    for matte in ("black", "white"))
    rows = []
    for y in range(h):
        pixels = []
        for x in range(w):
            k = 3 * (y * w + x)
            pixels.append(black[k:k+3] + b"\xff" if white[k] == black[k] else bytes(4))
        ink = [x for x, pixel in enumerate(pixels) if pixel[3]]
        rows.append((ink[0] - w//2, pixels[ink[0]:ink[-1]+1]) if ink else (0, []))
    while len(rows) > 1 and not rows[0][1]:
        rows.pop(0)
    return w, rows


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def _between(a, b, t, master, scale):
    # Interpolate scanline contours on the native pixel grid. The chosen ink retains
    # its original color and transparency, including gaps between arms and boots.
    aw, ar = a
    bw, br = b
    width = max(aw, bw)
    height = round(len(ar) + t * (len(br) - len(ar)))
    scan = bytearray((1 + width * 4) * height)
    for y in range(height):
        ax, ap = ar[min(len(ar)-1, int((y+.5) * len(ar) / height))]
        bx, bp = br[min(len(br)-1, int((y+.5) * len(br) / height))]
        if not ap or not bp:
            if not (ap if t < .5 else bp):
                continue
            if not ap:
                ax, ap = bx, bp
            else:
                bx, bp = ax, ap
        left = max(0, round(ax + t * (bx - ax)) + width//2)
        n = round(len(ap) + t * (len(bp) - len(ap)))
        n = min(n, width-left)
        ink = ap if t < .5 else bp
        offset = y * (width * 4 + 1) + 1
        for x in range(n):
            dst = offset + 4 * (left + x)
            scan[dst:dst+4] = ink[min(len(ink)-1, int((x+.5) * len(ink) / n))]
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(scan, 1)) + _chunk(b"IEND", b"")
    image = tk.PhotoImage(master=master, data=png)
    return image.zoom(scale) if scale > 1 else image


class SpriteHandoff:
    duration = .13

    def __init__(self):
        self.reset()

    def reset(self):
        self.last = self.source = None
        self.requested = False
        self.rows = {}
        self.last_key = None

    def frame(self, image, drop, now, scale):
        if self.requested:
            self.source, self.started = self.last, now
            self.rows.clear()
            self.last_key = None
            self.requested = False
        if self.source is not None:
            old, before = self.source
            phase = min(5, max(0, int(5 * (now - self.started) / self.duration)))
            if phase == 0:
                return self.source
            if phase < 5 and (image is not old or drop != before):
                key = (image, drop, phase)
                if self.last_key != key:
                    for sprite in (old, image):
                        if sprite not in self.rows:
                            self.rows[sprite] = _rows(sprite, scale)
                    t = phase / 5
                    cel = _between(self.rows[old], self.rows[image], t, image, scale)
                    self.last = (cel, round((before + t * (drop - before)) / scale) * scale)
                    self.last_key = key
                return self.last
            self.source = None
            self.rows.clear()
            self.last_key = None
        self.last = (image, drop)
        return self.last

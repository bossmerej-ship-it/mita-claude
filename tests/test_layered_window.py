import struct
import sys
import tkinter as tk
import unittest
import zlib
from unittest.mock import patch


@unittest.skipUnless(sys.platform == "win32", "uses a Win32 layered window")
class LayeredWindowTests(unittest.TestCase):
    def setUp(self):
        import platform_win
        self.platform = platform_win
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def test_transparent_pixels_ink_and_partial_alpha_are_distinct(self):
        from layered_window import sprite_pixels

        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

        header = struct.pack(">IIBBBBB", 3, 1, 8, 6, 0, 0, 0)
        scanline = bytes([0, 255, 0, 254, 255, 255, 99, 22, 0, 32, 128, 240, 128])
        png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
               + chunk(b"IDAT", zlib.compress(scanline)) + chunk(b"IEND", b""))
        img = tk.PhotoImage(master=self.root, data=png)
        width, height, pixels = sprite_pixels(img)
        self.assertEqual((width, height), (3, 1))
        self.assertEqual(pixels[:8], bytes([254, 0, 255, 255, 0, 0, 0, 0]))
        for actual, expected in zip(pixels[8:], (120, 64, 16, 128)):
            self.assertLessEqual(abs(actual - expected), 1)

    def test_frame_replaces_all_previous_pixels_and_moves_with_its_surface(self):
        import layered_window

        self.root.overrideredirect(True)
        self.root.geometry("9x9+0+0")
        canvas = tk.Canvas(self.root, width=9, height=9, highlightthickness=0)
        canvas.pack()
        hwnd, present = self.platform.setup_window(self.root, canvas, 9, 9)
        surface = present.__self__
        self.assertFalse(self.platform.user32.IsWindowVisible(hwnd))
        full = tk.PhotoImage(master=self.root, width=9, height=9)
        full.put("#ffffff", to=(0, 0, 9, 9))
        dot = tk.PhotoImage(master=self.root, width=1, height=1)
        dot.put("#ff00fe")
        with patch.object(layered_window.user, "UpdateLayeredWindow",
                          wraps=layered_window.user.UpdateLayeredWindow) as update:
            present(full, 9, 35, 40)
            present(dot, 3, -11, 23)
            self.assertEqual(self.platform.window_rect(hwnd), (-11, 23, -2, 32))
            pixels = bytearray(9 * 9 * 4)
            i = (2 * 9 + 4) * 4
            pixels[i:i + 4] = bytes([254, 0, 255, 255])
            self.assertEqual(bytes(surface.pixels), pixels)
            present(dot, 3, -11, 23)
            self.assertEqual(update.call_count, 2)
            present(dot, 3, -10, 23)
            self.assertEqual(update.call_count, 3)
            self.assertEqual(bytes(surface.pixels), pixels)

    def test_staying_visible_preserves_the_existing_window(self):
        import mascot_overlay as overlay
        mascot = overlay.Mascot.__new__(overlay.Mascot)
        mascot.root, mascot.own, mascot.shown = self.root, 123, None
        with patch.object(self.platform, "show") as show, patch.object(self.platform, "hide") as hide:
            for visible in (True, True, True, False, False, True):
                mascot.set_shown(visible)
        self.assertEqual(show.call_count, 2)
        hide.assert_called_once_with(self.root, 123)

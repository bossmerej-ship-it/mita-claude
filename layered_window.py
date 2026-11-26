"""Present a Tk sprite and its screen position together on a Win32 layered window."""

import ctypes as c
from ctypes import wintypes as w


class BitmapInfoHeader(c.Structure):
    _fields_ = [
        ("size", w.DWORD), ("width", w.LONG), ("height", w.LONG),
        ("planes", w.WORD), ("bit_count", w.WORD), ("compression", w.DWORD),
        ("image_size", w.DWORD), ("x_resolution", w.LONG), ("y_resolution", w.LONG),
        ("colors_used", w.DWORD), ("colors_important", w.DWORD),
    ]


class BlendFunction(c.Structure):
    _fields_ = [("operation", w.BYTE), ("flags", w.BYTE),
                ("opacity", w.BYTE), ("alpha_format", w.BYTE)]


gdi = c.WinDLL("gdi32", use_last_error=True)
user = c.WinDLL("user32", use_last_error=True)
gdi.CreateCompatibleDC.argtypes = [w.HDC]
gdi.CreateCompatibleDC.restype = w.HDC
gdi.CreateDIBSection.argtypes = [w.HDC, c.POINTER(BitmapInfoHeader), w.UINT,
                                 c.POINTER(c.c_void_p), w.HANDLE, w.DWORD]
gdi.CreateDIBSection.restype = w.HBITMAP
gdi.SelectObject.argtypes = [w.HDC, w.HANDLE]
gdi.SelectObject.restype = w.HANDLE
gdi.DeleteObject.argtypes = [w.HANDLE]
gdi.DeleteDC.argtypes = [w.HDC]
user.UpdateLayeredWindow.argtypes = [
    w.HWND, w.HDC, c.POINTER(w.POINT), c.POINTER(w.SIZE), w.HDC,
    c.POINTER(w.POINT), w.COLORREF, c.POINTER(BlendFunction), w.DWORD,
]


def sprite_pixels(image):
    """Tk composites onto each matte. Black gives premultiplied RGB, the difference gives alpha."""
    width, height = image.width(), image.height()
    byte_count = width * height * 3

    def matte(color):
        ppm = image.tk.call(image, "data", "-format", "ppm", "-background", color)
        return ppm[-byte_count:]

    black, white = matte("#000000"), matte("#ffffff")
    bgra = bytearray(width * height * 4)
    bgra[0::4], bgra[1::4], bgra[2::4] = black[2::3], black[1::3], black[0::3]
    bgra[3::4] = bytes(255 - (light - dark) for light, dark in zip(white[0::3], black[0::3]))
    return width, height, bgra


class LayeredWindow:
    def __init__(self, root, hwnd, width, height):
        self.hwnd = hwnd
        self.size = w.SIZE(width, height)
        self.origin = w.POINT(0, 0)
        self.blend = BlendFunction(0, 0, 255, 1)  # AC_SRC_OVER, AC_SRC_ALPHA
        self.frames = {}
        self.last_frame = self.last_position = None
        self.dc = gdi.CreateCompatibleDC(None)
        if not self.dc:
            raise c.WinError(c.get_last_error())
        self.bitmap = self.previous_bitmap = None
        try:
            info = BitmapInfoHeader(c.sizeof(BitmapInfoHeader), width, -height, 1, 32)
            bits = c.c_void_p()
            self.bitmap = gdi.CreateDIBSection(self.dc, c.byref(info), 0, c.byref(bits), None, 0)
            if not self.bitmap:
                raise c.WinError(c.get_last_error())
            self.previous_bitmap = gdi.SelectObject(self.dc, self.bitmap)
            if not self.previous_bitmap:
                raise c.WinError(c.get_last_error())
            self.pixels = memoryview((c.c_ubyte * (width * height * 4)).from_address(bits.value)).cast("B")
            self.empty = bytes(len(self.pixels))
            root.bind("<Destroy>", lambda e: self.close() if e.widget is root else None, add="+")
        except Exception:
            self.close()
            raise

    def close(self):
        if self.dc:
            if self.previous_bitmap:
                gdi.SelectObject(self.dc, self.previous_bitmap)
            if self.bitmap:
                gdi.DeleteObject(self.bitmap)
            gdi.DeleteDC(self.dc)
            self.dc = None

    def present(self, image, bottom, x, y):
        frame = (image, bottom)
        position = (x, y)
        if frame == self.last_frame and position == self.last_position:
            return
        if frame != self.last_frame:
            if image not in self.frames:
                self.frames[image] = sprite_pixels(image)
            width, height, data = self.frames[image]
            stride = self.size.cx * 4
            left = self.size.cx // 2 - width // 2
            top = bottom - height
            self.pixels[:] = self.empty
            # The window fits the widest sprite. Clip the vertical offset to the surface.
            for row in range(max(0, -top), min(height, self.size.cy - top)):
                dst = (top + row) * stride + left * 4
                self.pixels[dst:dst + width * 4] = data[row * width * 4:(row + 1) * width * 4]
        dest = w.POINT(x, y)
        if not user.UpdateLayeredWindow(self.hwnd, None, c.byref(dest), c.byref(self.size),
                                        self.dc, c.byref(self.origin), 0, c.byref(self.blend), 2):
            raise c.WinError(c.get_last_error())
        self.last_frame, self.last_position = frame, position

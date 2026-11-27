"""Keep the source sheets at native resolution and scale only the poses being displayed."""

from collections import OrderedDict
from collections.abc import Mapping
import tkinter as tk


def cut(sheet, bounds, scale, mirrored):
    image = tk.PhotoImage(master=sheet)
    sheet.tk.call(image, "copy", sheet, "-from", *bounds, "-subsample", -1 if mirrored else 1, 1,
                  "-zoom", scale, scale)
    return image


class SpriteLibrary(Mapping):
    def __init__(self, root, folder, scale):
        self.root, self.folder, self.scale = root, folder, scale
        self.sources = {}
        self.cache = OrderedDict()
        self.width = self.height = 0
        for path in folder.glob("*.png"):
            image = tk.PhotoImage(master=root, file=str(path))
            w, h = image.width(), image.height()
            self.sources[path.stem] = (image, (0, 0, w, h), False)
            self.width, self.height = max(self.width, w * scale), max(self.height, h * scale)

    def add_sheet(self, name, cell, rows):
        sheet = tk.PhotoImage(master=self.root, file=str(self.folder / "motion" / (name + ".png")))
        w, h = cell
        self.width, self.height = max(self.width, w * self.scale), max(self.height, h * self.scale)
        for j, row in enumerate(rows):
            for i, key in enumerate(row):
                bounds = (i*w, j*h, (i+1)*w, (j+1)*h)
                self.sources[key] = (sheet, bounds, False)
                self.sources[key + "_left"] = (sheet, bounds, True)

    def __getitem__(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        sheet, bounds, mirrored = self.sources[key]
        image = cut(sheet, bounds, self.scale, mirrored)
        self.cache[key] = image
        if len(self.cache) > 128:
            self.cache.popitem(last=False)
        return image

    def __iter__(self):
        return iter(self.sources)

    def __len__(self):
        return len(self.sources)

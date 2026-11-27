import tkinter as tk
import unittest

import mascot_overlay as overlay
from sprite_library import SpriteLibrary


class SpriteLibraryTests(unittest.TestCase):
    def test_cached_and_reloaded_poses_match_their_original_pixels_in_both_directions(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)

        def pixels(image):
            return root.tk.call(image, "data", "-format", "ppm", "-background", "#123456")

        for scale in (1, 2):
            bank = SpriteLibrary(root, overlay.SPRITES, scale)
            bank.add_sheet("walk", overlay.walk.CELL, overlay.walk.POSE_ROWS)
            bank.add_sheet("plant", overlay.walk.CELL, overlay.walk.PLANT_ROWS)
            originals = overlay.motion.load_poses(root, overlay.SPRITES / "motion" / "walk.png", scale,
                                                   cell=overlay.walk.CELL, rows=overlay.walk.POSE_ROWS)
            self.assertFalse(bank.cache)
            for name in ("walk03", "walk16_left", "step_in3_left"):
                self.assertEqual(pixels(bank[name]), pixels(originals[name]))
                self.assertIs(bank[name], bank[name])
            first = bank["walk03"]
            for key in tuple(key for row in overlay.walk.PLANT_ROWS for key in row)[:150]:
                bank[key]
            self.assertLessEqual(len(bank.cache),128)
            self.assertIsNot(first,bank["walk03"])
            self.assertEqual(pixels(first),pixels(bank["walk03"]))
            front = tk.PhotoImage(master=root,file=str(overlay.SPRITES / "front_left.png"))
            self.assertEqual(pixels(front.zoom(scale)), pixels(bank["front_left"]))

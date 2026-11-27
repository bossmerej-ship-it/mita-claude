import tkinter as tk
import unittest
from unittest.mock import patch

import climb_motion as climb
import mascot_overlay as overlay
from test_activities import mascot


def climbing_mita(up, inward, scale):
    m = mascot("floor" if up else "ledge", inward if up else -inward)
    m.cw = 79 * scale + 2
    top, left, right = m.platforms()["ledge"]
    x = left if inward > 0 else right
    m.X = x + inward * (-climb.OUTSIDE if up else climb.INSIDE) * scale
    m.walk_pixels = 18 * scale
    m.start_climb(up, inward, m.platforms())
    return m


class ClimbingTests(unittest.TestCase):
    def test_real_floor_walk_enters_the_grip_from_either_side(self):
        for inward in (-1, 1):
            m = mascot("floor", inward)
            m.X = (80 if inward > 0 else 420) - inward*(climb.OUTSIDE + 3)
            with patch.object(overlay.random, "random", return_value=0):
                for _ in range(16):
                    m.step(.5)
                    if m.mode == "climb_up":
                        break
            self.assertEqual((m.mode, m.on, m.climb.inward), ("climb_up", None, inward))
            self.assertEqual(m.pick(), (overlay.walk.sprite(m.walk_pixels, 1, inward), 0))

    def test_up_and_down_are_independent_of_the_global_clock_and_cadence(self):
        for scale in (1, 2):
            with patch.object(overlay, "SCALE", scale), patch.object(overlay, "HAND_REACH", 16*scale):
                for up in (True, False):
                    for inward in (1,-1):
                        a, b = (climbing_mita(up, inward, scale) for _ in range(2))
                        poses = set()
                        while a.mode.startswith("climb"):
                            for dt in (.25,)*8:
                                a.frame += 141
                                last_x, last_y = a.X, a.Y
                                a.step(dt)
                                self.assertLessEqual(abs(a.X-last_x), .7 * scale)
                                self.assertLessEqual(abs(a.Y-last_y), .8 * scale)
                                poses.add(a.pick()[0].removesuffix("_left"))
                            for dt in (1.7,.3):
                                b.frame += .001
                                b.step(dt)
                            self.assertAlmostEqual(a.X,b.X)
                            self.assertAlmostEqual(a.Y,b.Y)
                            self.assertEqual((a.mode, a.pick()), (b.mode, b.pick()))
                        self.assertTrue(any(n.startswith("grip") for n in poses))
                        self.assertTrue(set(climb.RAIL) <= poses)
                        self.assertTrue(set(climb.CREST[1:-1]) <= poses)
                        self.assertEqual(a.on, "ledge" if up else "floor")
                        self.assertEqual(a.mode, "walk" if up else "turn")

    def test_moving_or_removing_the_handhold_releases_both_directions(self):
        for up in (True, False):
            for event in (None, (120, 470, 460, 590), (80, 520, 420, 590)):
                m = climbing_mita(up, 1, 1)
                m.step(m.climb.entry_ticks + 25)
                x,y = m.X,m.Y
                m.prompt = event
                m.step(.5)
                self.assertEqual((m.mode, m.on, m.X), ("fall", None, x))
                self.assertLessEqual(abs(m.Y-y), 1)

    def test_shallow_and_narrow_cards_finish_inside_the_available_top(self):
        for width in (9, 27, 74):
            m = mascot("floor")
            m.prompt = (120, 571, 120+width, 593)
            m.X = 120 - climb.OUTSIDE
            m.start_climb(True,1,m.platforms())
            self.assertIn(m.climb.grip,climb.LOW_GRIPS)
            m.step(m.climb.duration)
            self.assertEqual((m.mode,m.on,m.Y), ("walk","ledge",-29))
            self.assertTrue(120 <= m.X <= 120+width)
            m.step(.5)
            self.assertIn(m.mode, ("sit_back","game"))

    def test_small_layout_changes_keep_the_hand_on_the_actual_corner(self):
        m = climbing_mita(True,1,1)
        m.step(m.climb.entry_ticks + m.climb.rail_end + 5)
        x,y,pose = m.X,m.Y,m.pick()
        m.prompt = (81,471,421,591)
        m.step(0)
        self.assertEqual((m.X,m.Y,m.pick()),(x+1,y+1,pose))

    def test_an_inked_hand_then_a_shoe_stay_on_the_same_lip_pixels_at_both_scales(self):
        root=tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        for scale in (1,2):
            images = overlay.motion.load_poses(root, overlay.SPRITES/"motion"/"climb.png",
                                               scale, cell=climb.CELL, rows=climb.ROWS)
            for inward in (-1,1):
                c = climb.Climb(True,inward,240,300,-140,0,240-inward*11*scale,15*scale,scale,1)
                for i in range(1,30):
                    t = i/(climb.CREST_FRAMES-1)
                    c.age = c.entry_ticks+c.rail_end+(t-c.crest_start)*c.crest_ticks
                    if c.age < c.entry_ticks+c.rail_end:
                        continue
                    x,y = c.position()
                    im = images[c.pose()[0]]
                    # Before weight transfer the glove holds the corner. Then the toe carries it.
                    if t < .45 or .52 < t < .85:
                        world_x = 240 + (inward*5*scale if t>.5 else 0)
                        px = world_x - round(x) + im.width()//2
                        py = -140 - round(y) + im.height()-scale
                        self.assertTrue(any(not im.transparency_get(px+dx,py+dy)
                                            for dx in range(-scale,scale+1) for dy in range(-1,1)
                                            if 0 <= px+dx < im.width() and 0 <= py+dy < im.height()),
                                        (scale,inward,i,px,py))

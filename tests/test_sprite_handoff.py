import gc
import tkinter as tk
import unittest
import weakref
from collections import deque
from types import SimpleNamespace
from unittest.mock import patch

import mascot_overlay as overlay
from sprite_handoff import SpriteHandoff
from test_activities import mascot


class InterruptionTests(unittest.TestCase):
    def test_picking_up_during_activity_cancels_it_and_an_immediate_release_obeys_physics(self):
        for activity in ("walk", "wave", "game", "wake", "climb"):
            m = mascot()
            m.base, m.trail = 96, deque()
            m.pointer_world = lambda: (m.X, m.Y-32)
            if activity == "game":
                m.start_game(seated=True)
            elif activity == "wake":
                m.mode,m.timer = "wake", 20
            elif activity == "wave":
                m.update_cursor(True,30)
            elif activity == "climb":
                m.start_climb(False,1,m.platforms())
            pick = SimpleNamespace(x=m.cw//2,y=m.base-32,state=0)
            m.on_press(pick)
            self.assertEqual((m.mode,m.held,m.on,m.climb), ("held",True,None,None))
            self.assertTrue(m.activities.handoff.requested)
            self.assertFalse(m.activities.greeting.remaining or m.activities.bridge.remaining)
            with patch.object(m, "refresh_prompt"), patch.object(overlay.plat, "refocus"):
                m.on_release(pick)
            self.assertEqual((m.mode,m.held,m.on), ("fall",False,None))
            self.assertTrue(m.activities.handoff.requested)

    def test_visible_pickup_and_release_retarget_the_last_drawn_pixel_cel_at_both_scales(self):
        root=tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        for scale in (1,2):
            handoff=SpriteHandoff()
            sit, held = [tk.PhotoImage(master=root,file=str(overlay.SPRITES/(name+".png"))).zoom(scale)
                         for name in ("sit1","held")]
            handoff.frame(sit,14*scale,0,scale)
            handoff.requested=True
            self.assertEqual(handoff.frame(held,0,2,scale),(sit,14*scale))
            midway=handoff.frame(held,0,2.065,scale)
            image, offset=midway
            self.assertNotIn(image,(held,sit))
            self.assertTrue(0 < offset < 14*scale and offset % scale == 0)
            native=image.subsample(scale)
            restored=native.zoom(scale)
            def matte(im):
                return root.tk.call(im,"data","-format","ppm","-background","#00ff00")
            self.assertEqual(matte(image), matte(restored))
            self.assertTrue(image.transparency_get(0,0))
            handoff.requested=True
            self.assertEqual(handoff.frame(held,0,2.067,scale),midway)
            self.assertEqual(handoff.frame(held,0,2.25,scale),(held,0))
            ref=weakref.ref(image)
            del image,midway
            gc.collect()
            self.assertIsNone(ref())

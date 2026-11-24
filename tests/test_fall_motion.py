import unittest
from collections import deque

import fall_motion as motion
import mascot_overlay as overlay


class FallMotionTests(unittest.TestCase):
    def test_same_gesture_gives_same_throw_at_different_mouse_rates(self):
        for rate in (30, 100, 500):
            with self.subTest(rate=rate):
                samples = deque()
                for i in range(rate + 1):
                    t = i / rate
                    motion.record_drag(samples, t, (420*t, -200*t))
                vx, vy = motion.throw_velocity(samples, 1.0, overlay.TICK_SECONDS)
                self.assertAlmostEqual(vx, 420 * overlay.TICK_SECONDS)
                self.assertAlmostEqual(vy, -200 * overlay.TICK_SECONDS)
                self.assertEqual(motion.throw_velocity(samples, 1.25, overlay.TICK_SECONDS), (0, 0))

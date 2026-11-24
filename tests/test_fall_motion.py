import unittest
from collections import deque

import fall_motion as motion
import mascot_overlay as overlay


def falling_mita(x=200, y=-450, vx=0, vy=0, prompt=None):
    m = overlay.Mascot.__new__(overlay.Mascot)
    m.world = (0, 0, 1200, 900, 900)
    m.target = (1, "Codex")
    m.prompt, m.auto_prompt_apps = prompt, set()
    m.st = {"ledges": {}, "sitpos": {}, "sit": False}
    m.X, m.Y, m.dir = x, y, 1
    m.frame, m.edge_cooldown, m.cw = 0, 0, 81
    m.drops = {}
    m.start_fall(vx, vy)
    return m


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

    def test_equal_elapsed_time_gives_same_arc_including_terminal_speed(self):
        a, b = (falling_mita(y=-1800, vx=4, vy=-3) for _ in range(2))
        for dt in [.5] * 100:
            a.step(dt)
        for dt in [1.8, .2, 1.0, .6, 1.4] * 10:
            b.step(dt)
        self.assertEqual((a.mode, b.mode), ("fall", "fall"))
        self.assertEqual(a.vy, overlay.MAX_FALL)
        for first, second in ((a.X, b.X), (a.Y, b.Y), (a.vy, b.vy)):
            self.assertAlmostEqual(first, second)

    def test_diagonal_throw_hits_edge_at_crossing_even_if_next_frame_is_beyond_it(self):
        for dt in (.25, 1.0, 2.0):
            with self.subTest(dt=dt):
                m = falling_mita(495, -210, 20, 20, prompt=(100, 700, 507, 800))
                while m.on is None:
                    m.step(dt)
                self.assertEqual((m.on, m.Y), ("ledge", -200))
                self.assertLess(m.X, 507)

    def test_hard_drop_keeps_facing_and_reaches_recovery_from_both_directions(self):
        for direction in (1, -1):
            m = falling_mita(x=600)
            m.dir = direction
            sequence = []
            for _ in range(600):
                m.step(.5)
                if m.mode == "idle":
                    break
                name, _ = m.pick()
                self.assertEqual(name.endswith("_left"), direction == -1)
                sequence.append(name[:-5] if name.endswith("_left") else name)
            self.assertEqual((m.mode, m.on, m.Y), ("idle", "floor", 0))
            for pose in ("release2", "fall_panic", "lean2", "fall_dive", "crash_impact", "kneel", "recover"):
                self.assertIn(pose, sequence)

    def test_fast_downward_flick_close_to_floor_folds_before_impact(self):
        m = falling_mita(y=-3, vx=-5, vy=22)
        poses = []
        for _ in range(24):
            m.step(.5)
            if m.mode == "crash":
                break
            self.assertEqual((m.on, m.Y), ("floor", 0))
            poses.append(m.pick()[0])
        self.assertGreater(len(set(poses)), 3)
        self.assertTrue(all(pose.endswith("_left") for pose in poses))
        self.assertEqual((m.mode, m.on, m.Y), ("crash", "floor", 0))

    def test_soft_ledge_landing_eases_into_sitting_with_feet_on_the_edge(self):
        m = falling_mita(x=400, y=-275, prompt=(100, 700, 800, 800))
        contact_poses, offsets = set(), []
        for _ in range(100):
            m.step(.5)
            if m.mode in ("land", "perch"):
                self.assertEqual((m.on, m.Y), ("ledge", -200))
                pose, drop = m.pick()
                contact_poses.add(pose)
                offsets.append(drop)
            if m.mode == "perch":
                break
        self.assertEqual(m.mode, "perch")
        self.assertTrue({"squash", "cushion1", "front"} <= contact_poses)
        self.assertEqual((offsets[0], offsets[-1]), (0, overlay.LEG))
        self.assertEqual(offsets, sorted(offsets))
        self.assertGreater(len(set(offsets)), 3)

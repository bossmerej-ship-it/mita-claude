import tkinter as tk
import unittest
from unittest.mock import patch

import mascot_overlay as overlay
import walk_motion as walk


def walking_mita(direction=1, surface="ledge"):
    m = overlay.Mascot.__new__(overlay.Mascot)
    m.world = (0, 0, 1000, 750, 750)
    m.st, m.target = {"ledges": {}}, (1, "Codex")
    m.prompt, m.auto_prompt_apps = (100, 620, 900, 725), set()
    m.mode, m.on, m.dir = "idle", surface, direction
    m.X, m.Y, m.cw = 500.25, m.platforms()[surface][0], 81
    m.frame, m.edge_cooldown = 0, 200
    m.start_walk(1000)
    return m


class WalkMotionTests(unittest.TestCase):
    def test_same_ground_distance_gives_same_pose_across_speeds_and_frame_rates(self):
        for direction in (-1, 1):
            poses = []
            for speed, steps, surface in ((.6, (.25,), "floor"), (1.2, (1.8, .7, .5), "ledge"),
                                          (2.4, (1,), "floor")):
                m = walking_mita(direction, surface)
                # За первые 4 такта средняя скорость вдвое ниже обычной.
                remaining = 2 + 36 / speed
                with patch.object(overlay, "SPEED", speed):
                    i = 0
                    while remaining > 1e-8:
                        dt = min(steps[i % len(steps)], remaining)
                        m.frame += 7 * dt  # часы других анимаций не задают темп шагов
                        m.step(dt)
                        remaining -= dt
                        i += 1
                self.assertAlmostEqual(m.X, 500.25 + direction * 36)
                self.assertEqual(m.Y, m.platforms()[surface][0])
                poses.append(m.pick())
            self.assertEqual(len(set(poses)), 1)

    def test_unchanged_screen_position_freezes_footwork_and_continued_walk_keeps_phase(self):
        m = walking_mita()
        for _ in range(20):
            m.step()
        pose = m.pick()
        m.start_walk(180)
        with patch.object(overlay, "SPEED", 0):
            for _ in range(12):
                m.frame += 1
                m.step()
                self.assertEqual(m.pick(), pose)
        m.prompt = (650, 615, 950, 720)
        m.step(0)
        self.assertGreater(m.X, 650)
        self.assertEqual(m.pick(), pose)

    def test_turn_keeps_position_and_passes_through_both_three_quarter_views(self):
        for incoming in (-1, 1):
            m = walking_mita(incoming)
            m.X = 145 if incoming < 0 else 855
            for _ in range(10):
                m.step()
                if m.mode == "turn":
                    break
            self.assertEqual(m.mode, "turn")
            x = m.X
            views = []
            for _ in range(30):
                name, drop = m.pick()
                self.assertEqual((m.X, drop), (x, 0))
                if not views or name != views[-1]:
                    views.append(name)
                m.step(.5)
                if m.mode != "turn":
                    break
            self.assertEqual(m.mode, "walk")
            angles = ["front34", "front", "front34_left"]
            self.assertEqual(views[1:-1], angles if incoming < 0 else angles[::-1])
            self.assertEqual(views[-1], m.pick()[0])
            m.step()
            self.assertGreater((m.X - x) * -incoming, 0)

    def test_ledge_too_narrow_for_a_step(self):
        m = walking_mita()
        m.prompt = (490, 615, 525, 720)
        for _ in range(120):
            m.step()
            self.assertEqual((m.mode, m.X, m.Y), ("perch", 507.5, -135))
        m.prompt = (400, 615, 650, 720)
        for _ in range(61):
            m.step()
        self.assertEqual(m.mode, "walk")
        self.assertGreater(m.X, 507.5)

    def test_leaving_seat_brings_feet_up_before_facing_the_first_step(self):
        for direction, angle in ((1, "front34_left"), (-1, "front34")):
            m = walking_mita(direction)
            m.mode, m.timer = "perch", 10
            poses = []
            for _ in range(10):
                poses.append(m.pick())
                m.step()
            drops = [drop for _, drop in poses]
            self.assertEqual(drops, sorted(drops, reverse=True))
            self.assertEqual((drops[0], drops[-1]), (overlay.LEG, 0))
            self.assertIn(("front", 0), poses)
            self.assertEqual(poses[-1], (angle, 0))
            self.assertEqual((m.mode, m.X), ("walk", 500.25))

if __name__ == "__main__":
    unittest.main()

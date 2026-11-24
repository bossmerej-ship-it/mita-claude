import unittest
from unittest.mock import patch

import activities
import mascot_overlay as overlay


def mascot(place="ledge", direction=1):
    m = overlay.Mascot.__new__(overlay.Mascot)
    m.world, m.target = (0, 0, 500, 600, 600), (1, "Codex")
    m.prompt, m.auto_prompt_apps = (80, 470, 420, 590), {"Codex"}
    m.st = {"ledges": {}, "sit": False, "sitpos": {}}
    m.activities = activities.Activities()
    m.on, m.mode, m.dir = place, "idle", direction
    m.frame, m.cw, m.edge_cooldown = 0, 81, 0
    m.X, m.Y = 250, m.platforms()[place][0]
    m.start_walk(300)
    return m


class ConsoleTests(unittest.TestCase):
    def test_walk_to_corner_unpack_play_pack_and_walk_back(self):
        for direction in (-1, 1):
            m = mascot(direction=direction)
            m.activities.game_wait = 1
            m.timer = 5
            for _ in range(200):
                m.step()
                if m.mode == "game":
                    break
            self.assertEqual((m.mode, m.dir), ("game", -direction))
            corner = m.X
            self.assertGreater((corner - 250) * direction, 100)
            poses = []
            for _ in range(500):
                if m.mode != "game":
                    break
                pose, drop = m.pick()
                poses.append(pose.removesuffix("_left"))
                if pose.startswith("game_"):
                    self.assertEqual(drop, overlay.LEG)
                self.assertEqual((m.X, m.Y), (corner, -130))
                m.step()
            distinct = [a for i, a in enumerate(poses) if i == 0 or a != poses[i-1]]
            start = distinct.index("game_reach")
            self.assertEqual(distinct[start:start+4], list(activities.UNPACK))
            self.assertTrue(set(activities.PLAY) <= set(poses))
            self.assertEqual(distinct[-5:], [*reversed(activities.UNPACK), "sit1"])
            for _ in range(9):
                m.step()
            self.assertEqual(m.mode, "walk")
            self.assertLess((m.X - corner) * direction, 0)

    def test_prompt_resizing_and_closing_during_a_game(self):
        m = mascot()
        m.start_game(seated=True)
        m.prompt = (320, 420, 450, 590)
        m.step()
        self.assertEqual((m.mode, m.Y), ("game", -180))
        self.assertGreaterEqual(m.X, 320+m.cw/2)
        m.prompt = None
        m.step()
        self.assertEqual((m.mode, m.on), ("fall", None))

    def test_manual_seat_keeps_its_place_even_when_a_game_is_due(self):
        m = mascot()
        m.mode, m.st["sit"], m.activities.game_wait = "sit", True, 0
        for _ in range(40):
            m.step()
        self.assertEqual((m.mode, m.X, m.pick()[1]), ("sit", 250, overlay.LEG))


class GreetingTests(unittest.TestCase):
    def test_dwell_pauses_and_resumes_the_same_game_without_repeating(self):
        m = mascot()
        m.start_game(seated=True)
        m.timer = m.activities.game_length - 50
        pointer = [m.X-24, m.Y-32]
        m.pointer_world = lambda: tuple(pointer)
        with patch.object(activities.random, "random", return_value=.1):
            for _ in range(29):
                m.update_cursor(True, 1)
            self.assertEqual(m.activities.greeting.remaining, 0)
            m.update_cursor(True, 1)
            before = m.timer
            poses = set()
            for _ in range(50):
                pose, drop = m.pick()
                self.assertEqual(drop, overlay.LEG)
                poses.add(pose)
                m.step()
                m.update_cursor(True, 1)
            self.assertTrue({"pad_notice_left", "pad_wave_in_left", "pad_wave_out_left"} <= poses)
            self.assertEqual(m.timer, before)
            m.step()
            self.assertLess(m.timer, before)
            for _ in range(210):
                m.update_cursor(True, 1)
            self.assertEqual(m.activities.greeting.remaining, 0)
            pointer[0] += 300
            m.update_cursor(True, 1)
            pointer[0] = m.X+24
            for _ in range(30):
                m.update_cursor(True, 1)
            self.assertEqual(m.pick()[0], "pad_notice")

    def test_flybys_hidden_windows_and_dragging_do_not_trigger_a_wave(self):
        m = mascot(place="floor")
        pointer = [m.X, m.Y-40]
        m.pointer_world = lambda: tuple(pointer)
        for i in range(100):
            pointer[0] = m.X + (20 if i % 2 else -20)
            m.update_cursor(True, 1)
        self.assertEqual(m.activities.greeting.remaining, 0)
        for _ in range(29):
            m.update_cursor(False, 1)
        with patch.object(activities.random, "random", return_value=.9):
            for _ in range(30):
                m.update_cursor(True, 1)
        self.assertFalse(m.activities.greeting.wave)
        self.assertEqual(m.pick(), ("stand_notice", 0))
        m.start_fall()
        m.update_cursor(True, 50)
        self.assertEqual(m.activities.greeting.remaining, 0)

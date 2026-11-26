import unittest
from collections import deque
from types import SimpleNamespace
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
            self.assertEqual(m.mode, "edge_rise")
            for _ in range(2 * int(overlay.rise.EDGE_TICKS) + 4):
                if m.mode == "walk":
                    break
                self.assertEqual((m.mode, m.X), ("edge_rise", corner))
                m.step(.5)
            self.assertEqual(m.mode, "walk")
            m.step()
            self.assertLess((m.X - corner) * direction, 0)

    def test_prompt_resizing_and_closing_during_a_game(self):
        m = mascot()
        m.start_game(seated=True)
        m.prompt = (220, 420, 450, 590)
        m.step()
        self.assertEqual((m.mode, m.Y), ("game", -180))
        self.assertEqual(m.X, 250)
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


class SleepTests(unittest.TestCase):
    def test_sleep_follows_session_inactivity_not_a_stationary_pointer(self):
        m = mascot(place="floor")
        with patch.object(overlay.plat, "idle_seconds", return_value=.2) as idle:
            for i in range(1500):
                m.update_sleep(True, i/20)
            self.assertEqual(m.mode, "walk")
            self.assertEqual(idle.call_count, 150)
            idle.return_value = activities.SLEEP_AFTER_SECONDS - .01
            m.update_sleep(True, 75)
            self.assertEqual(m.mode, "walk")
            idle.return_value = activities.SLEEP_AFTER_SECONDS
            m.update_sleep(True, 75.5)
        self.assertEqual((m.mode, m.pick()), ("yawn", ("floor_drowsy", 0)))
        modes, poses = [], set()
        for _ in range(230):
            if not modes or modes[-1] != m.mode:
                modes.append(m.mode)
            pose, drop = m.pick()
            poses.add(pose)
            self.assertEqual(drop, 0)
            m.step()
        self.assertEqual(modes, ["yawn", "doze", "sleep"])
        self.assertTrue({"floor_yawning", "floor_nod", "floor_droop",
                         "floor_breathe_in", "floor_breathe_out"} <= poses)
        with patch.object(overlay.plat, "idle_seconds", return_value=0):
            m.update_sleep(True, 87)
        self.assertEqual((m.mode, m.pick()[0]), ("wake", "floor_rub_in"))
        poses = set()
        for _ in range(68):
            poses.add(m.pick()[0])
            m.step(.5)
        self.assertTrue(set(overlay.rise.WAKE) <= poses)
        self.assertEqual((m.mode, m.on), ("idle", "floor"))

    def test_hidden_windows_active_games_and_missing_input_data(self):
        m = mascot()
        with patch.object(overlay.plat, "idle_seconds", return_value=None) as idle:
            m.update_sleep(False, 1)
            m.start_game(seated=True)
            m.update_sleep(True, 2)
            idle.assert_not_called()
            m.mode = "perch"
            m.update_sleep(True, 3)
            self.assertEqual(m.mode, "perch")
            idle.return_value = 100
            m.start_fall()
            m.update_sleep(True, 4)
            idle.assert_called_once()
            self.assertEqual(m.mode, "fall")

    def test_ledge_sleep_keeps_contact_and_remembers_a_pinned_seat(self):
        m = mascot(direction=-1)
        with patch.object(overlay.plat, "idle_seconds", return_value=90):
            m.update_sleep(True, 1)
        offsets = []
        for _ in range(12):
            offsets.append(m.pick()[1])
            m.step()
        self.assertEqual((offsets[0], offsets[-1]), (0, overlay.LEG))
        self.assertEqual(offsets, sorted(offsets))
        m.mode, m.st["sit"] = "sit", True
        m.remember_sit()
        with patch.object(overlay.plat, "idle_seconds", return_value=90):
            m.update_sleep(True, 2)
        self.assertEqual(m.pick(), ("edge_drowsy_left", overlay.LEG))
        m.world, m.prompt = (0, 0, 640, 650, 650), (160, 450, 550, 630)
        for _ in range(125):
            m.step()
        self.assertEqual((m.mode, m.X, m.Y), ("sleep", 320, -200))
        with patch.object(overlay.plat, "idle_seconds", return_value=0):
            m.update_sleep(True, 10)
        for _ in range(34):
            m.step()
        self.assertEqual((m.mode, m.X, m.st["sit"]), ("sit", 320, True))
        with patch.object(overlay.plat, "idle_seconds", return_value=100):
            m.update_sleep(True, 110)
        m.prompt = None
        m.step()
        self.assertEqual((m.mode, m.on), ("fall", None))

    def test_picking_up_a_sleeper_rubs_eyes_and_still_allows_an_immediate_drop(self):
        for hold_ticks in (0, 12, 32):
            with self.subTest(hold_ticks=hold_ticks):
                m = mascot(direction=-1)
                m.mode, m.timer, m.base = "sleep", 10, 100
                m.trail = deque()
                pointer = [m.X, m.Y-25]
                m.pointer_world = lambda: tuple(pointer)
                event = SimpleNamespace(x=m.cw//2, y=m.base-25, state=0)
                with patch.object(overlay.time, "monotonic", return_value=100):
                    m.on_press(event)
                self.assertEqual((m.mode, m.pick()[0]), ("held", "held_rub_in_left"))
                pointer[:] = [m.X+30, m.Y-75]
                with patch.object(overlay.time, "monotonic", return_value=100.1):
                    m.on_drag(event)
                    for _ in range(hold_ticks):
                        m.step()
                    self.assertEqual((m.X, m.Y), (280, -180))
                    self.assertEqual(m.pick()[0].startswith("held_rub"), hold_ticks < activities.RUB_TICKS)
                    with patch.object(m, "refresh_prompt"), patch.object(overlay.plat, "refocus"):
                        m.on_release(event)
                self.assertEqual((m.mode, m.on, m.activities.held_rub), ("fall", None, 0))
                self.assertGreater(m.vx, 0)
                self.assertLess(m.vy, 0)

import unittest
from collections import deque
from types import SimpleNamespace
from unittest.mock import patch

import activities
import mascot_overlay as overlay
import walk_motion as walk


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
            for _ in range(950):
                if m.mode != "game":
                    break
                pose, drop = m.pick()
                poses.append(pose.removesuffix("_left"))
                if pose.startswith("game_"):
                    self.assertEqual(drop, overlay.LEG)
                self.assertEqual((m.X, m.Y), (corner, -130))
                m.step(.5)
            distinct = [a for i, a in enumerate(poses) if i == 0 or a != poses[i-1]]
            start = distinct.index(activities.UNPACK_SEQUENCE[0])
            self.assertEqual(distinct[start:start+len(activities.UNPACK_SEQUENCE)], list(activities.UNPACK_SEQUENCE))
            self.assertTrue(set(activities.PLAY) <= set(poses))
            self.assertEqual(distinct[-len(activities.UNPACK_SEQUENCE)-1:], [*reversed(activities.UNPACK_SEQUENCE), "sit1"])
            self.assertEqual(m.pick(), (overlay.rise.SWINGS[1][0] + ("_left" if direction < 0 else ""), overlay.LEG))
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
    def test_mid_stride_wave_plants_the_feet_and_returns_to_the_interrupted_step(self):
        for direction in (-1, 1):
            m = mascot("floor", direction)
            m.walk_pixels, m.walk_age, m.timer = 34, 28, 91
            cursor = [m.X + direction*22, m.Y-40]
            m.pointer_world = lambda: tuple(cursor)
            first, x, y = m.pick(), m.X, m.Y
            with patch.object(activities.random, "random", return_value=0):
                m.update_cursor(True, 30)
            self.assertEqual(m.pick(), first)
            poses = []
            while m.activities.greeting.remaining:
                poses.append(m.pick())
                if "raise" in m.pick()[0]:
                    cursor[0] = x - direction*22
                dt = min(.35, m.activities.greeting.remaining)
                m.step(dt)
                m.update_cursor(True, dt)
                self.assertEqual((m.X, m.Y, m.timer, m.walk_pixels, m.walk_age), (x, y, 91, 34, 28))
            entry = walk.face_front(34, direction, 1)
            unique = [v for i,v in enumerate(poses) if i == 0 or v != poses[i-1]]
            self.assertEqual(unique[:len(entry)], list(entry))
            self.assertEqual(unique[-len(entry):], list(reversed(entry)))
            self.assertEqual(m.activities.greeting.direction, direction)
            self.assertEqual(m.pick(), first)
            m.step()
            self.assertGreater((m.X-x)*direction, 0)

    def test_timer_stop_from_walk26_plants_before_standing(self):
        for action, expected in ((.72, "idle"), (.94, "look")):
            m = mascot("floor")
            m.walk_pixels, m.timer = 18, 0
            with patch.object(overlay.random, "random", return_value=action):
                m.step(0)
            self.assertEqual((m.mode, m.pick()), (expected, ("walk26", 0)))
            self.assertEqual(m.activities.bridge.frames, walk.face_front(18, 1, 1))
            x, y, timer = m.X, m.Y, m.timer
            while m.activities.bridge.remaining:
                m.step(min(.5, m.activities.bridge.remaining))
                self.assertEqual((m.X, m.Y, m.timer), (x,y,timer))
            self.assertIn(m.pick()[0], ("front", overlay.rise.PIVOT[0]))

    def test_dwell_pauses_and_resumes_the_same_game_without_repeating(self):
        m = mascot()
        m.start_game(seated=True)
        m.timer = m.activities.game_length - activities.PLAY_START - 5
        pointer = [m.X-24, m.Y-32]
        m.pointer_world = lambda: tuple(pointer)
        with patch.object(activities.random, "random", return_value=.1):
            for _ in range(29):
                m.update_cursor(True, 1)
            self.assertEqual(m.activities.greeting.remaining, 0)
            m.update_cursor(True, 1)
            before = m.timer
            poses = set()
            original = m.pick()
            while m.activities.greeting.remaining:
                pose, drop = m.pick()
                self.assertEqual(drop, overlay.LEG)
                poses.add(pose)
                dt = min(.5, m.activities.greeting.remaining)
                m.step(dt)
                m.update_cursor(True, dt)
            self.assertTrue({"pad_far_notice", "pad_far_wave_in", "pad_far_wave_out"} <= poses)
            self.assertEqual(m.pick(), original)
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
            self.assertGreater(m.activities.greeting.remaining, 0)
            self.assertEqual(m.activities.greeting.direction, 1)

    def test_fractional_end_of_a_greeting_returns_unused_time_to_the_game(self):
        m = mascot()
        m.start_game(seated=True)
        m.timer = m.activities.game_length - activities.PLAY_START - 5
        m.pointer_world=lambda:(m.X+12,m.Y-32)
        m.update_cursor(True,30)
        timer=m.timer
        m.step(m.activities.greeting.remaining-.25)
        self.assertEqual(m.timer,timer)
        m.step(1.25)
        self.assertAlmostEqual(m.timer,timer-1)
        self.assertEqual(m.activities.greeting.remaining,0)

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
        self.assertEqual(m.pick(), ("step_in0", 0))
        self.assertIn(("stand_notice", 0), m.activities.greeting.clip.frames)
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
        self.assertEqual((m.mode, m.pick()), ("yawn", ("step_in0", 0)))
        m.step(m.activities.bridge.remaining)
        self.assertEqual(m.pick(), ("floor_drowsy", 0))
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
        self.assertEqual(m.mode, "wake")
        self.assertIn("breathe", m.pick()[0])
        m.step(m.activities.bridge.remaining)
        self.assertEqual(m.pick()[0], "floor_rub_in")
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
        while m.activities.bridge.remaining:
            offsets.append(m.pick()[1])
            m.step(.5)
        self.assertEqual((offsets[0], offsets[-1]), (0, overlay.LEG))
        self.assertEqual(offsets, sorted(offsets))
        m.mode, m.st["sit"] = "sit", True
        m.remember_sit()
        with patch.object(overlay.plat, "idle_seconds", return_value=90):
            m.update_sleep(True, 2)
        self.assertEqual(m.pick(), ("sit1_left", overlay.LEG))
        m.step(m.activities.bridge.remaining)
        self.assertEqual(m.pick(), ("edge_drowsy_left", overlay.LEG))
        m.world, m.prompt = (0, 0, 640, 650, 650), (160, 450, 550, 630)
        for _ in range(125):
            m.step()
        self.assertEqual((m.mode, m.X, m.Y), ("sleep", 320, -200))
        with patch.object(overlay.plat, "idle_seconds", return_value=0):
            m.update_sleep(True, 10)
        m.step(m.activities.bridge.remaining)
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

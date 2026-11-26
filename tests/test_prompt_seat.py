import copy
import json
import tempfile
import time
import unittest
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import mascot_overlay as overlay


class PromptSeatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state_file = Path(self.temp.name) / "position.json"
        state_patch = patch.object(overlay, "POS_FILE", self.state_file)
        state_patch.start()
        self.addCleanup(state_patch.stop)
        for patcher in (patch.object(overlay, "USE_LEDGE", False),
                        patch.object(overlay.plat, "refocus"),
                        patch.object(overlay.plat, "idle_seconds", return_value=0),
                        patch.object(overlay.plat, "prompt_rect", return_value=None),
                        patch.object(overlay, "log")):
            patcher.start()
            self.addCleanup(patcher.stop)

        self.m = overlay.Mascot.__new__(overlay.Mascot)
        self.m.st = copy.deepcopy(overlay.DEFAULT)
        self.m.world = (100, 100, 1100, 900, 900)
        self.m.prompt = None
        self.m.auto_prompt_apps = set()
        self.m.target = (101, "Codex")
        self.m.X, self.m.Y = 650, -150
        self.m.vx, self.m.vy = 12, 8
        self.m.cw, self.m.base = 70, 100
        self.m.mode, self.m.on = "held", None
        self.m.held, self.m.placed = True, True
        self.m.frame, self.m.edge_cooldown = 0, 0
        self.m.walk_pixels, self.m.walk_age = 0, 0.0
        self.m.activities = overlay.activities.Activities()
        self.m.dir = 1
        self.m.root, self.m.present = Mock(), Mock()
        self.m.root.winfo_pointerx.return_value = self.m.root.winfo_pointery.return_value = -10000
        self.m.img, self.m.own = {"front": Mock()}, 999
        self.m.trail = deque()
        self.m.air_pose = self.m.air_ticks = 0.0
        self.m.last_tick = time.monotonic()
        self.m.placement_deadline = self.m.last_tick

    def seat(self, modifier=0x0001):
        self.m.on_release(SimpleNamespace(state=modifier))

    def tick_in(self, name, handle=202, rect=(100, 100, 1100, 900)):
        with patch.object(overlay.plat, "find_target", return_value=(handle, name)), \
                patch.object(overlay.plat, "is_minimized", return_value=False), \
                patch.object(overlay.plat, "window_rect", return_value=rect), \
                patch.object(overlay.plat, "work_bottom", return_value=rect[3]), \
                patch.object(overlay.plat, "is_foreground", return_value=True), \
                patch.object(self.m, "set_shown"):
            self.m._tick()

    def test_shift_drop_seats_and_saves_without_experimental_setting(self):
        self.assertNotIn("ledge", self.m.platforms())
        self.seat()
        self.assertEqual((self.m.mode, self.m.on), ("sit", "ledge"))
        self.assertEqual((self.m.vx, self.m.vy), (0, 0))
        self.assertFalse(self.m.held)
        self.assertTrue(self.m.st["sit"])
        self.assertEqual(self.m.platforms()["ledge"], (-150, 270, 1000))
        self.assertNotIn("roof", self.m.platforms())
        saved = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["ledges"]["Codex"], {"dx": 150, "dy": 150})
        self.assertEqual(saved["sitpos"]["Codex"], {"dx": 150, "on": "ledge"})
        self.assertEqual(self.m.pick(), ("sit1", overlay.LEG))
        self.m.frame = 20
        self.assertEqual(self.m.pick(), ("sit0", overlay.LEG))

    def test_windows_ctrl_drop_also_seats(self):
        with patch.object(overlay.sys, "platform", "win32"):
            self.seat(0x0004)
        self.assertEqual(self.m.on, "ledge")

    def test_mac_shift_drop_seats(self):
        with patch.object(overlay.sys, "platform", "darwin"):
            self.seat()
        self.assertEqual(self.m.on, "ledge")

    def test_plain_drop_still_falls_without_creating_a_ledge(self):
        self.seat(0)
        self.assertEqual(self.m.mode, "fall")
        self.assertNotIn("ledge", self.m.platforms())

    def test_seat_follows_center_and_bottom_when_window_moves_and_resizes(self):
        self.seat()
        self.m.world = (300, 200, 1500, 1200, 1200)
        self.m.step()
        self.assertEqual((self.m.X, self.m.Y), (750, -150))

    def test_seat_is_clamped_but_recovers_after_window_widens(self):
        self.seat()
        self.m.world = (0, 0, 200, 300, 300)
        self.m.step()
        self.assertEqual(self.m.X, 200 - self.m.cw / 2)
        self.m.world = (0, 0, 1000, 800, 800)
        self.m.step()
        self.assertEqual(self.m.X, 650)

    def test_restart_restores_seated_pose_and_saved_edge(self):
        self.seat()
        self.m.st = overlay.load_state()
        self.m.mode, self.m.on = "fall", None
        self.m.X, self.m.Y, self.m.placed = 0, 0, False
        self.tick_in("Codex")
        self.assertEqual((self.m.X, self.m.Y), (650, -150))
        self.assertEqual((self.m.mode, self.m.on), ("sit", "ledge"))

    def test_switching_apps_restores_each_apps_own_seat(self):
        self.seat()
        self.m.target = (303, "Claude")
        self.m.X, self.m.Y, self.m.held = 300, -220, True
        self.seat()
        self.tick_in("Codex")
        self.assertEqual((self.m.X, self.m.Y), (650, -150))
        self.tick_in("Claude", handle=303)
        self.assertEqual((self.m.X, self.m.Y), (300, -220))

    def test_switching_windows_in_same_app_updates_native_handle(self):
        self.seat()
        self.tick_in("Codex", handle=202)
        self.assertEqual(self.m.target, (202, "Codex"))

    def test_right_click_resumes_walking_and_can_sit_on_edge_again(self):
        self.seat()
        self.m.on_right(SimpleNamespace(state=0))
        self.assertFalse(self.m.st["sit"])
        self.assertEqual((self.m.mode, self.m.pick()[1]), ("edge_rise", overlay.LEG))
        self.assertIn("ledge", self.m.platforms())
        self.m.on_right(SimpleNamespace(state=0))
        self.assertEqual((self.m.mode, self.m.on), ("sit", "ledge"))
        self.assertEqual(self.m.st["sitpos"]["Codex"]["on"], "ledge")

    def test_previous_position_file_still_loads(self):
        self.state_file.write_text(json.dumps({
            "ledges": {}, "sit": True, "sitpos": {"Codex": [240, 0]},
        }), encoding="utf-8")
        self.m.st = overlay.load_state()
        self.m.placed = False
        self.tick_in("Codex")
        self.assertEqual((self.m.mode, self.m.on), ("sit", "floor"))
        self.assertEqual((self.m.X, self.m.Y), (240, 0))

    def test_first_frame_waits_for_the_composer_then_starts_above_its_edge(self):
        self.m.placed, self.m.held = False, False
        self.m.target = (None, None)
        with patch.object(overlay.plat, "prompt_ready", return_value=False):
            self.tick_in("ChatGPT")
            self.assertFalse(self.m.placed)
            self.m.present.assert_not_called()
            overlay.plat.prompt_rect.return_value = (300, 640, 900, 860)
            self.tick_in("ChatGPT")
        self.assertTrue(self.m.placed)
        self.assertEqual(self.m.mode, "fall")
        self.assertLess(self.m.Y, self.m.platforms()["ledge"][0])

    def test_unavailable_composer_still_allows_starting_on_the_floor(self):
        self.m.placed, self.m.held = False, False
        self.m.placement_deadline = 0
        with patch.object(overlay.plat, "prompt_ready", return_value=False):
            self.tick_in("Codex")
        self.assertTrue(self.m.placed)
        self.assertEqual(self.m.mode, "fall")

    def test_fall_is_hidden_when_another_application_is_in_front(self):
        self.m.held = False
        self.m.start_fall()
        self.m.shown = True
        with patch.object(overlay.plat, "find_target", return_value=self.m.target), \
                patch.object(overlay.plat, "is_minimized", return_value=False), \
                patch.object(overlay.plat, "window_rect", return_value=self.m.world[:4]), \
                patch.object(overlay.plat, "work_bottom", return_value=self.m.world[4]), \
                patch.object(overlay.plat, "is_foreground", return_value=False), \
                patch.object(overlay.plat, "hide") as hide:
            self.m._tick()
        self.m.present.assert_not_called()
        hide.assert_called_once_with(self.m.root, self.m.own)

    def drop_above_prompt(self, x=650, y=-250):
        overlay.plat.prompt_rect.return_value = (300, 700, 900, 860)
        self.m.X, self.m.Y = x, y
        self.seat(0)

    def fall_until_landing(self):
        for _ in range(150):
            self.m.step()
            if self.m.on is not None:
                return
        self.fail("Mascot never landed")

    def test_plain_drop_lands_on_real_prompt_then_sits_and_walks(self):
        self.drop_above_prompt()
        self.assertEqual(self.m.mode, "fall")
        self.fall_until_landing()
        self.assertEqual((self.m.on, self.m.Y), ("ledge", -200))
        for _ in range(7):
            self.m.step()
        self.assertEqual((self.m.mode, self.m.pick()[1]), ("sit_back", 0))
        for _ in range(int(overlay.rise.LIFT_TICKS)):
            self.m.step()
        self.assertEqual(self.m.mode, "perch")
        self.assertEqual(self.m.pick()[1], overlay.LEG)
        self.assertFalse(self.m.st["sit"])
        self.assertEqual(self.m.st["ledges"], {})
        for _ in range(60):
            self.m.step()
        self.assertEqual(self.m.mode, "walk")
        x = self.m.X
        self.m.step()
        self.assertGreater(self.m.X, x)

    def test_drop_outside_prompt_width_reaches_floor(self):
        self.drop_above_prompt(x=100)
        self.fall_until_landing()
        self.assertEqual(self.m.on, "floor")

    def test_drop_below_prompt_does_not_teleport_onto_it(self):
        self.drop_above_prompt(y=-190)
        self.fall_until_landing()
        self.assertEqual(self.m.on, "floor")

    def test_high_speed_fall_cannot_pass_through_prompt(self):
        self.drop_above_prompt(y=-210)
        self.m.vy = overlay.MAX_FALL
        self.m.step()
        self.assertEqual((self.m.on, self.m.Y), ("ledge", -200))

    def test_prompt_disappearing_or_closing_returns_mascot_to_physics(self):
        self.drop_above_prompt()
        self.fall_until_landing()
        self.m.mode, self.m.prompt = "perch", None
        self.m.step()
        self.assertEqual((self.m.mode, self.m.on), ("fall", None))
        self.fall_until_landing()
        self.assertEqual(self.m.on, "floor")

    def test_prompt_disappearing_during_climb_does_not_crash(self):
        self.m.mode, self.m.on = "climb_up", None
        self.m.step()
        self.assertEqual(self.m.mode, "fall")

    def test_closed_auto_prompt_does_not_fall_back_to_old_manual_edge(self):
        self.m.st["ledges"]["Codex"] = {"dx": 0, "dy": 150}
        self.drop_above_prompt()
        self.fall_until_landing()
        overlay.plat.prompt_rect.return_value = None
        self.m.refresh_prompt()
        self.assertNotIn("ledge", self.m.platforms())
        self.m.step()
        self.assertEqual(self.m.mode, "fall")

    def test_sitting_tracks_prompt_height_and_width_changes(self):
        self.drop_above_prompt()
        self.fall_until_landing()
        self.m.mode, self.m.timer = "perch", 60
        overlay.plat.prompt_rect.return_value = (400, 600, 850, 860)
        self.tick_in("Codex")
        self.assertEqual(self.m.Y, -300)
        self.assertEqual((self.m.X, self.m.on), (650, "ledge"))

    def test_walking_turns_at_actual_prompt_edge(self):
        self.drop_above_prompt()
        self.fall_until_landing()
        self.m.mode, self.m.timer, self.m.X = "walk", 60, 800
        with patch.object(overlay.random, "random", return_value=.9):
            self.m.step()
        self.assertEqual(self.m.mode, "turn")
        self.assertEqual(self.m.X, 800)

    def test_automatic_rest_is_followed_by_walking(self):
        self.drop_above_prompt()
        self.fall_until_landing()
        with patch.object(overlay.random, "random", return_value=.1):
            self.m.next_action()
        self.assertEqual(self.m.mode, "sit_back")
        self.m.step(self.m.timer)
        self.assertEqual(self.m.mode, "perch")
        self.m.step(self.m.timer)
        self.assertEqual(self.m.mode, "walk")

    def test_picking_up_previously_pinned_mascot_enables_plain_drop(self):
        self.seat()
        with patch.object(self.m, "pointer_world", return_value=(650, -250)):
            self.m.on_press(SimpleNamespace(x=self.m.cw//2, y=self.m.base))
        self.assertFalse(self.m.st["sit"])
        self.drop_above_prompt()
        self.assertEqual(self.m.mode, "fall")


if __name__ == "__main__":
    unittest.main()

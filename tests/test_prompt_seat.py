import copy
import json
import tempfile
import unittest
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
                        patch.object(overlay, "log")):
            patcher.start()
            self.addCleanup(patcher.stop)

        self.m = overlay.Mascot.__new__(overlay.Mascot)
        self.m.st = copy.deepcopy(overlay.DEFAULT)
        self.m.world = (100, 100, 1100, 900, 900)
        self.m.target = (101, "Codex")
        self.m.X, self.m.Y = 650, -150
        self.m.vx, self.m.vy = 12, 8
        self.m.cw, self.m.base = 70, 100
        self.m.mode, self.m.on = "held", None
        self.m.held, self.m.placed = True, True
        self.m.frame, self.m.edge_cooldown = 0, 0
        self.m.dir = 1
        self.m.root, self.m.canvas = Mock(), Mock()
        self.m.img, self.m.sprite, self.m.own = {"front": Mock()}, 1, 999
        self.m.trail = []

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
        self.assertEqual(self.m.mode, "idle")
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


if __name__ == "__main__":
    unittest.main()

import unittest

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

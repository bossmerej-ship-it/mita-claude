import tkinter as tk
import unittest
from unittest.mock import patch

import mascot_overlay as overlay
import rise_motion as rise
import walk_motion as walk


def walking_mita(direction=1, surface="ledge"):
    m = overlay.Mascot.__new__(overlay.Mascot)
    m.world = (0, 0, 1000, 750, 750)
    m.st, m.target = {"ledges": {}}, (1, "Codex")
    m.prompt, m.auto_prompt_apps = (100, 620, 900, 725), set()
    m.mode, m.on, m.dir = "idle", surface, direction
    m.X, m.Y, m.cw = 500.25, m.platforms()[surface][0], 81
    m.frame, m.edge_cooldown = 0, 200
    m.activities = overlay.activities.Activities()
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
        x = m.X
        m.prompt = (round(x) - 5, 615, 950, 720)
        m.step(0)
        self.assertEqual(m.X, x)
        self.assertEqual(m.pick(), pose)

    def test_turn_plants_the_current_stride_then_rotates_through_both_profiles(self):
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
            stride = walk.stride_name(m.walk_pixels, overlay.SCALE)
            for _ in range(60):
                name, drop = m.pick()
                self.assertEqual((m.X, drop), (x, 0))
                if not views or name != views[-1]:
                    views.append(name)
                m.step(.5)
                if m.mode != "turn":
                    break
            self.assertEqual(m.mode, "walk")
            before, after = ("_left", "") if incoming < 0 else ("", "_left")
            expected = [stride + before]
            expected.extend(f"plant_{stride}_{i}" + before for i in range(1, walk.PLANT_FRAMES + 1))
            expected.extend(name + before for name in reversed(rise.PIVOT))
            expected.extend(name + after for name in rise.PIVOT)
            self.assertEqual(views, expected)
            self.assertEqual(m.pick(), (walk.FIRST_STEP[0] + after, 0))
            m.step()
            self.assertGreater((m.X - x) * -incoming, 0)

    def test_ledge_too_narrow_for_a_step(self):
        m = walking_mita()
        m.prompt = (490, 615, 525, 720)
        drops = []
        for _ in range(120):
            m.step()
            self.assertIn(m.mode, ("sit_back", "perch"))
            self.assertEqual((m.X, m.Y), (507.5, -135))
            drops.append(m.pick()[1])
        self.assertEqual((drops[0], drops[-1]), (0, overlay.LEG))
        self.assertEqual(drops, sorted(drops))
        self.assertEqual(m.mode, "perch")
        m.prompt = (400, 615, 650, 720)
        for _ in range(61):
            m.step()
        self.assertEqual(m.mode, "walk")
        self.assertGreater(m.X, 507.5)

    def test_retracted_and_sideways_composers_release_the_walking_feet(self):
        for prompt in ((100, 700, 900, 720), (650, 620, 950, 720)):
            m = walking_mita()
            x, y = m.X, m.Y
            m.prompt = prompt
            m.step(.5)
            self.assertEqual((m.mode, m.on, m.X), ("fall", None, x))
            self.assertGreater(m.Y, y)
            self.assertLess(m.Y, y + 1)

    def test_leaving_the_edge_finishes_the_stride_then_clears_the_card(self):
        for direction in (-1, 1):
            m = walking_mita(direction)
            m.edge_cooldown = 0
            m.X = 142 if direction < 0 else 858
            with patch.object(overlay.random, "random", return_value=.4):
                last_x = m.X
                for _ in range(100):
                    m.step(.5)
                    self.assertLessEqual(abs(m.X - last_x), overlay.SPEED * .5 + .001)
                    last_x = m.X
                    if m.mode == "fall":
                        break
            self.assertEqual(m.mode, "fall")
            for _ in range(100):
                m.step(.5)
                if m.on:
                    break
            self.assertEqual(m.on, "floor")

    def test_climbing_stops_where_the_side_of_the_card_ends(self):
        m = walking_mita()
        m.prompt = (100, 620, 900, 700)
        m.X = 894
        m.start_climb(False, -1, m.platforms())
        for _ in range(600):
            m.step(.5)
            if m.mode == "fall":
                break
        self.assertEqual((m.mode, m.on), ("fall", None))
        self.assertAlmostEqual(m.Y, -50 + overlay.HAND_REACH, delta=1)

    def test_every_stride_has_drawn_intermediates_that_converge_on_planted_feet(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        images = overlay.motion.load_poses(root, overlay.SPRITES / "motion" / "walk.png", 1,
                                          cell=walk.CELL, rows=walk.POSE_ROWS)
        images.update(overlay.motion.load_poses(root, overlay.SPRITES / "motion" / "plant.png", 1,
                                                cell=walk.CELL, rows=walk.PLANT_ROWS))

        def pixels(name):
            return root.tk.call(images[name], "data", "-background", "#00ff00", "-format", "ppm")

        neutral = pixels(walk.FIRST_STEP[0])
        self.assertEqual(pixels(f"plant_{walk.FIRST_STEP[0]}_1"), neutral)
        def soles(name):
            image = images[name]
            return {x for x in range(image.width()) if not image.transparency_get(x, image.height()-1)}

        for stride in walk.CYCLE + walk.FIRST_STEP:
            final = pixels(f"plant_{stride}_{walk.PLANT_FRAMES}")
            diff = sum(a != b for a, b in zip(final, neutral))
            self.assertLessEqual(diff, sum(a != b for a, b in zip(pixels(stride), neutral)), stride)
            landing = [soles(stride), *(soles(f"plant_{stride}_{i}") for i in range(1,8)), soles(walk.FIRST_STEP[0])]
            self.assertTrue(set.intersection(*landing[:5]), stride)
            self.assertTrue(set.intersection(*landing[4:]), stride)

    def test_background_shows_through_boots_and_ponytail_in_both_directions(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        for name, holes in (("front", [(20, 80)]), ("sit0", [(20, 80)]), ("held", [(19, 82)]),
                            ("front34_left", [(23, 80), (10, 51)]), ("back34", [(20, 80), (10, 50)])):
            reverse = name.removesuffix("_left") if name.endswith("_left") else name + "_left"
            for asset, mirror in ((name, False), (reverse, True)):
                image = tk.PhotoImage(master=root, file=str(overlay.SPRITES / (asset + ".png")))
                for x, y in holes:
                    x = image.width() - 1 - x if mirror else x
                    self.assertTrue(image.transparency_get(x, y), (asset, x, y))
                    # Both inked edges framing the gap survive.
                    self.assertTrue(any(not image.transparency_get(i, y) for i in range(x)))
                    self.assertTrue(any(not image.transparency_get(i, y) for i in range(x + 1, image.width())))

    def test_leaving_seat_brings_feet_up_before_facing_the_first_step(self):
        for direction, swing in ((1, 1), (-1, 0)):
            m = walking_mita(direction)
            m.frame = 0 if swing == 1 else 24
            m.mode, m.timer = "perch", rise.EDGE_TICKS + .5
            m.step(.5)
            poses = []
            for _ in range(len(rise.EDGE[swing]) * 2):
                if m.mode != "edge_rise":
                    break
                poses.append(m.pick())
                self.assertEqual((m.X, m.Y), (500.25, -130))
                m.frame += .5
                m.step(.5)
            drops = [drop for _, drop in poses]
            self.assertEqual(drops, sorted(drops, reverse=True))
            self.assertEqual((drops[0], drops[-1]), (overlay.LEG, 0))
            self.assertLessEqual(max(a - b for a, b in zip(drops, drops[1:])), 2)
            suffix = "_left" if direction < 0 else ""
            self.assertEqual(list(dict.fromkeys(name for name, _ in poses)),
                             [name + suffix for name in rise.EDGE[swing]])
            self.assertEqual((m.mode, round(m.X)), ("walk", round(500.25)))
            self.assertAlmostEqual(m.X, 500.25 + direction * walk.travel(0, .25, overlay.SPEED))

    def test_narrowing_ledge_reverses_the_rise_and_removing_it_releases_mita(self):
        m = walking_mita()
        m.start_edge_rise()
        for _ in range(7):
            m.step()
        m.prompt = (495, 590, 525, 713)
        drops = []
        for _ in range(12):
            m.step()
            drops.append(m.pick()[1])
        self.assertEqual((m.mode, m.X, m.Y), ("perch", 510, -160))
        self.assertEqual(drops, sorted(drops))
        m.prompt = (300, 590, 770, 730)
        for _ in range(31):
            m.step()
        self.assertEqual(m.mode, "edge_rise")
        m.prompt = None
        m.step(.5)
        self.assertEqual((m.mode, m.on), ("fall", None))

    def test_drawn_rise_matches_its_endpoints_and_keeps_the_supporting_shoe_planted(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        root.withdraw()
        self.addCleanup(root.destroy)

        def pixels(im):
            return root.tk.call(im, "data", "-background", "#00ff00", "-format", "ppm")

        def on_canvas(im, scale):
            w, h = (n * scale for n in rise.CELL)
            padded = tk.PhotoImage(master=root, width=w, height=h)
            root.tk.call(padded, "copy", im, "-to", (w - im.width()) // 2, h - im.height())
            return pixels(padded)

        for scale in (1, 2):
            images = overlay.motion.load_poses(root, overlay.SPRITES / "motion" / "get_up.png",
                                               scale, cell=rise.CELL, rows=rise.POSE_ROWS)
            walks = overlay.motion.load_poses(root, overlay.SPRITES / "motion" / "walk.png",
                                              scale, cell=walk.CELL, rows=walk.POSE_ROWS)
            for suffix in ("", "_left"):
                for swing in (0, 1):
                    seat = tk.PhotoImage(master=root, file=str(overlay.SPRITES / f"sit{swing}{suffix}.png"))
                    self.assertEqual(pixels(images[rise.EDGE[swing][0] + suffix]),
                                     on_canvas(seat.zoom(scale), scale))
                self.assertEqual(pixels(images[rise.PIVOT[-1] + suffix]),
                                 on_canvas(walks[walk.FIRST_STEP[0] + suffix], scale))
                front = tk.PhotoImage(master=root, file=str(overlay.SPRITES / f"front{suffix}.png"))
                for pose in (rise.GROUND[-1], rise.WAKE[-1]):
                    self.assertEqual(pixels(images[pose + suffix]), on_canvas(front.zoom(scale), scale))
                sole = None
                for name in rise.GROUND[rise.GROUND.index("straighten00"):]:
                    im = images[name + suffix]
                    y = im.height() - 1
                    contact = {x for x in range(im.width()) if not im.transparency_get(x, y)
                               and min(im.get(x, y)) < 110}
                    sole = contact if sole is None else sole & contact
                self.assertGreaterEqual(len(sole), 2 * scale)

    def test_planted_shoe_stays_on_same_screen_pixels_in_both_half_cycles(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        root.withdraw()
        self.addCleanup(root.destroy)
        for scale in (1, 2):
            images = overlay.motion.load_poses(root, overlay.SPRITES / "motion" / "walk.png",
                                               scale, cell=walk.CELL, rows=walk.POSE_ROWS)
            for direction in (-1, 1):
                with self.subTest(scale=scale, direction=direction), patch.object(overlay, "SCALE", scale):
                    m = walking_mita(direction)
                    start = round(m.X)
                    contacts = [[], []]
                    for _ in range(200):
                        m.step(.5)
                        x = round(m.X)
                        image = images[m.pick()[0]]
                        soles = {x + i - image.width() // 2 for i in range(image.width())
                                 if not image.transparency_get(i, image.height() - 1)}
                        self.assertTrue(soles, "Обе ноги оказались над поверхностью")
                        travelled = abs(x - start)
                        for i, (lo, hi) in enumerate(((12, 20), (28, 36))):
                            if lo * scale <= travelled <= hi * scale:
                                contacts[i].append(soles)
                        if travelled >= 37 * scale:
                            break
                    else:
                        self.fail("Мита не прошла полный цикл ходьбы")
                    planted = [set.intersection(*half) for half in contacts]
                    self.assertTrue(all(len(foot) >= 2 * scale for foot in planted))
                    self.assertGreater(direction * (min(planted[1]) - min(planted[0])), 10 * scale)


if __name__ == "__main__":
    unittest.main()

import threading
import time
import unittest

from prompt_detection import PromptDetector, choose_prompt


class PromptGeometryTests(unittest.TestCase):
    window = (0, 0, 1200, 900)

    def test_uses_composer_frame_instead_of_inner_text_area(self):
        result = choose_prompt([{
            "rect": (220, 750, 1000, 790), "hint": "ProseMirror",
            "parents": [(200, 730, 1020, 860), (0, 100, 1200, 900)],
        }], self.window)
        self.assertEqual(result, (200, 730, 1020, 860))

    def test_file_change_badge_above_codex_is_outside_the_walking_surface(self):
        window = (0, 0, 1920, 1080)
        card = (535, 936, 1456, 1059)
        edit = {"rect": (550, 954, 1441, 1004), "hint": "ProseMirror", "parents": [
            {"rect": card, "hint": "ComposerLayoutBody-uBBf1A"},
            {"rect": (535, 896, 1456, 1059), "hint": "contents"},
            {"rect": (515, 896, 1476, 1059), "hint": "relative px-5"},
        ]}
        self.assertEqual(choose_prompt([edit], window), card)

    def test_attachment_above_the_edit_is_inside_the_composer(self):
        window = (0, 0, 1920, 1080)
        card = (535, 750, 1456, 1059)
        edit = {"rect": (550, 950, 1441, 1004), "hint": "ProseMirror", "parents": [
            {"rect": (546, 942, 1445, 1008), "hint": "rounded-sm border"},
            {"rect": card, "hint": "ComposerLayoutBody-nextVersion"},
            {"rect": (535, 710, 1456, 1059), "hint": "contents"},
        ]}
        self.assertEqual(choose_prompt([edit], window), card)

    def test_ignores_search_at_top_and_prefers_known_composer(self):
        result = choose_prompt([
            {"rect": (20, 40, 400, 80)},
            {"rect": (500, 750, 1100, 790), "hint": "prompt-textarea"},
        ], self.window)
        self.assertEqual(result, (500, 750, 1100, 790))

    def test_known_composer_can_be_in_center_of_new_chat(self):
        self.assertEqual(choose_prompt([
            {"rect": (200, 350, 1000, 450), "hint": "ProseMirror"},
        ], self.window), (200, 350, 1000, 450))

    def test_rejects_empty_off_window_and_invalid_rectangles(self):
        self.assertIsNone(choose_prompt([
            {"rect": (0, 0, 0, 0)}, {"rect": (-500, 750, -100, 800)},
            {"rect": (0, float("nan"), 900, 800)},
        ], self.window))
        self.assertIsNone(choose_prompt([], self.window))

    def test_negative_monitor_coordinates_are_supported(self):
        self.assertEqual(choose_prompt([
            {"rect": (-1000, 700, -300, 800), "hint": "composer"},
        ], (-1200, 0, 0, 900)), (-1000, 700, -300, 800))

    def test_bottom_editor_without_known_css_class_is_supported(self):
        self.assertEqual(choose_prompt([
            {"rect": (200, 700, 1000, 800)},
        ], self.window), (200, 700, 1000, 800))

    def test_cached_surface_follows_window_and_expires(self):
        detector = PromptDetector(lambda _: (None, None))
        detector.last_key, detector.last_size, detector.last_request = 1, (1400, 1000), time.monotonic()
        detector.result = (1, (-400, -170, 400, -40), time.monotonic())
        self.assertEqual(detector.get(1, 1, (100, 100, 1500, 1100)), (400, 930, 1200, 1060))
        detector.result = (1, (-400, -170, 400, -40), time.monotonic()-2)
        self.assertIsNone(detector.get(1, 1, self.window))

    def test_window_reflow_starts_an_immediate_scan_while_translation_uses_cached_geometry(self):
        scanned = threading.Event()

        def read(_):
            scanned.set()
            return None, self.window

        detector = PromptDetector(read, interval=30)
        detector.last_key, detector.last_size, detector.last_request = 1, (1200, 900), time.monotonic()
        detector.get(1, 1, (200, 100, 1400, 1000))
        self.assertFalse(scanned.is_set())
        detector.get(1, 1, (200, 100, 1100, 1000))
        self.assertTrue(scanned.wait(timeout=1))

    def test_blocked_accessibility_does_not_block_animation(self):
        entered, release = threading.Event(), threading.Event()

        def read(_):
            entered.set()
            release.wait(timeout=1)
            return None, None

        detector = PromptDetector(read)
        try:
            start = time.monotonic()
            self.assertIsNone(detector.get(1, 1, self.window))
            self.assertLess(time.monotonic()-start, .2)
            self.assertTrue(entered.wait(timeout=1))
            self.assertIsNone(detector.get(2, 2, self.window))
        finally:
            release.set()


if __name__ == "__main__":
    unittest.main()

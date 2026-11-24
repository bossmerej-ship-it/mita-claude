import unittest

from prompt_detection import choose_prompt


class PromptGeometryTests(unittest.TestCase):
    window = (0, 0, 1200, 900)

    def test_uses_composer_frame_instead_of_inner_text_area(self):
        result = choose_prompt([{
            "rect": (220, 750, 1000, 790), "hint": "ProseMirror",
            "parents": [(200, 730, 1020, 860), (0, 100, 1200, 900)],
        }], self.window)
        self.assertEqual(result, (200, 730, 1020, 860))

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

if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import unittest

from extraction_paths import (
    build_by_label_destination,
    format_pig_size,
    normalize_pig_type,
    safe_path_component,
)


def parts(path: str):
    return path.split(os.sep)


class ExtractionPathTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_destination_distinguishes_type_size_and_label(self):
        destination = build_by_label_destination(
            self.temp_dir.name, "c-mfl", 18, 4, 1, "cmflb4s1"
        )

        self.assertEqual(
            parts(destination)[-4:],
            ["By_Label", "C-MFL", "18-inch", "CMFLB4S1"],
        )

    def test_unconfigured_size_uses_stable_unknown_bucket(self):
        destination = build_by_label_destination(
            self.temp_dir.name, "A-MFL", 0, 3, 2, "MFLB3S2"
        )

        self.assertEqual(
            parts(destination)[-4:],
            ["By_Label", "A-MFL", "Unknown-size", "MFLB3S2"],
        )

    def test_missing_label_uses_board_and_slot_fallback(self):
        destination = build_by_label_destination(
            self.temp_dir.name, "EGP", 24, 7, 5, ""
        )

        self.assertEqual(parts(destination)[-1], "UNLABELED_B7S5")

    def test_path_components_are_safe_for_windows(self):
        destination = build_by_label_destination(
            self.temp_dir.name, "unexpected/type", "bad", 1, 2, 'bad<label>:*?'
        )

        self.assertEqual(
            parts(destination)[-3:],
            ["Unknown-type", "Unknown-size", "BAD_LABEL____"],
        )

    def test_normalizers_accept_only_supported_values(self):
        self.assertEqual(normalize_pig_type(" egp "), "EGP")
        self.assertEqual(normalize_pig_type("other"), "Unknown-type")
        self.assertEqual(format_pig_size("20"), "20-inch")
        self.assertEqual(format_pig_size(-1), "Unknown-size")
        self.assertEqual(safe_path_component("name. ", "fallback"), "name")


if __name__ == "__main__":
    unittest.main()

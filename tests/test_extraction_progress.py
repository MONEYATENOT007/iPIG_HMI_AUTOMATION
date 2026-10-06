import unittest

from extraction_progress import estimate_eta_seconds, extraction_percent, format_eta


class ExtractionProgressTests(unittest.TestCase):
    def test_reports_byte_percentage(self):
        self.assertEqual(extraction_percent(250, 1000), 25)

    def test_active_copy_does_not_claim_verified_completion(self):
        self.assertEqual(extraction_percent(1000, 1000), 99)
        self.assertEqual(extraction_percent(1000, 1000, complete=True), 100)

    def test_values_are_clamped(self):
        self.assertEqual(extraction_percent(-10, 100), 0)
        self.assertEqual(extraction_percent(500, 100), 99)

    def test_invalid_or_empty_totals_are_zero(self):
        self.assertEqual(extraction_percent(20, 0), 0)
        self.assertEqual(extraction_percent("bad", 100), 0)

    def test_eta_uses_average_speed_for_whole_slot_copy(self):
        self.assertEqual(estimate_eta_seconds(250, 1000, 10.0, 20.0), 30)

    def test_eta_waits_for_enough_data(self):
        self.assertIsNone(estimate_eta_seconds(0, 1000, 10.0, 20.0))
        self.assertIsNone(estimate_eta_seconds(1000, 1000, 10.0, 20.0))
        self.assertIsNone(estimate_eta_seconds(100, 1000, 20.0, 10.0))

    def test_eta_format_is_compact(self):
        self.assertEqual(format_eta(5), "ETA 5s")
        self.assertEqual(format_eta(65), "ETA 1m 05s")
        self.assertEqual(format_eta(3660), "ETA 1h 01m")
        self.assertEqual(format_eta(None), "ETA calculating...")


if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import unittest
from unittest.mock import patch

import main


class ExpressExtractionTests(unittest.TestCase):
    def setUp(self):
        main.CANCEL_EVENT.clear()

    def test_offsets_are_frame_aligned_and_one_per_mib(self):
        size = (2 * 1024 * 1024) + 200
        offsets = main.express_sample_offsets(size, 112)
        self.assertEqual(3, len(offsets))
        self.assertTrue(all(offset % 112 == 0 for offset in offsets))
        self.assertTrue(all(offset + 112 <= size for offset in offsets))

    def test_small_file_has_one_sample(self):
        self.assertEqual([0], main.express_sample_offsets(64, 64))
        self.assertEqual([], main.express_sample_offsets(63, 64))

    def test_extraction_writes_packets_and_manifest(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as dest:
            payload = bytes(range(64)) * ((1024 * 1024 // 64) + 2)
            with open(os.path.join(source, "DATA.bin"), "wb") as output:
                output.write(payload)
            with patch.object(main, "get_board_type", return_value="A-MFL"):
                self.assertTrue(main.extract_express_report_samples(
                    source, dest, "MFLB1", 1, "MFLB1S1"))
            sampled = os.path.join(dest, "DATA.bin.express.bin")
            self.assertEqual(20 + (2 * (8 + 64)), os.path.getsize(sampled))
            self.assertTrue(os.path.isfile(os.path.join(dest, "express_manifest.json")))

    def test_data_log_summary_remains_available_by_itself(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as dest:
            source_file = os.path.join(source, "DATA.bin")
            with open(source_file, "wb") as output:
                output.write(b"sample data")

            self.assertTrue(main.log_sdcard_file_info(
                source, dest, "MFLB1", 1, "MFLB1S1"
            ))

            log_path = os.path.join(dest, "data_log.txt")
            self.assertTrue(os.path.isfile(log_path))
            with open(log_path, "r", encoding="utf-8") as summary:
                contents = summary.read()
            self.assertIn("DATA.bin | 11 bytes", contents)
            self.assertFalse(os.path.exists(os.path.join(dest, main.EXPRESS_REPORT_SUBFOLDER)))

    def test_express_package_uses_separate_summary_and_report_folders(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as dest:
            payload = bytes(range(64)) * ((1024 * 1024 // 64) + 2)
            with open(os.path.join(source, "DATA.bin"), "wb") as output:
                output.write(payload)

            with patch.object(main, "get_board_type", return_value="A-MFL"):
                self.assertTrue(main.extract_express_report_package(
                    source, dest, "MFLB1", 1, "MFLB1S1"
                ))

            summary_dir = os.path.join(dest, main.LOG_SUMMARY_SUBFOLDER)
            report_dir = os.path.join(dest, main.EXPRESS_REPORT_SUBFOLDER)
            self.assertTrue(os.path.isfile(os.path.join(summary_dir, "data_log.txt")))
            self.assertTrue(os.path.isfile(os.path.join(report_dir, "express_manifest.json")))
            self.assertTrue(os.path.isfile(os.path.join(report_dir, "DATA.bin.express.bin")))

    def test_log_and_express_are_separate_menu_modes(self):
        modes = dict(main.MainWindow.MODES)
        self.assertEqual("12. DATA EXTRACTION LOG", modes["DATA_LOG"])
        self.assertEqual("18. EXPRESS REPORT EXTRACTION", modes["EXPRESS_REPORT"])


if __name__ == "__main__":
    unittest.main()

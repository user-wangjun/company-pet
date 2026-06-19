#!/usr/bin/env python3

import unittest

import make_ikun_contact_sheet as contact_sheet


class ContactSheetLayoutTests(unittest.TestCase):
    def test_jump_row_draws_exactly_eight_columns(self) -> None:
        spec = {
            "frames": 8,
            "atlasFrames": 8,
        }

        self.assertEqual(contact_sheet.display_column_count(spec), 8)

    def test_throw_row_includes_the_independent_finish_frame(self) -> None:
        spec = {
            "frames": 9,
            "atlasFrames": 8,
        }

        self.assertEqual(contact_sheet.display_column_count(spec), 9)

    def test_frame_labels_are_one_based(self) -> None:
        self.assertEqual(contact_sheet.frame_label(0), "1")
        self.assertEqual(contact_sheet.frame_label(7), "8")
        self.assertEqual(contact_sheet.frame_label(8, independent_finish=True), "9 独立收尾")


if __name__ == "__main__":
    unittest.main()

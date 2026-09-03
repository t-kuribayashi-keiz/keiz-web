"""院マスタの見出し読み取り。実際のシート(2026-09-03のスクリーンショット)の形で試す。"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import clinic_master as cm  # noqa: E402


# 実物の形。結合セルは先頭の1セルにしか値が返らないので、平日/土日祝も前/後もそう書く。
ROWS = [
    [],
    ["", "", "平日", "", "", "", "土日祝"],
    ["", "", "前", "", "後", "", "前", "", "後"],
    ["", "", "開始", "終了", "開始", "終了", "開始", "終了", "開始", "終了",
     "定休", "電話番号", "短縮番号"],
    [],
    ["1", "本八幡駅前整骨院", "9:30", "12:30", "15:30", "21:00",
     "8:00", "12:00", "14:30", "17:00", "", "047-332-7767", "001"],
    ["28", "安倍川駅前総合治療院", "9:30", "12:30", "15:30", "20:30",
     "8:30", "12:30", "15:00", "17:30", "木", "054-204-1266", "049"],
]


class TestHeaderReading(unittest.TestCase):
    def test_finds_the_bottom_header_row(self):
        """開始/終了と定休が並ぶ段。行番号は決め打ちしない。"""
        self.assertEqual(cm.header_row_index(ROWS), 3)

    def test_a_sheet_without_those_headers_is_not_guessed_at(self):
        self.assertIsNone(cm.header_row_index([["院名", "住所"], ["A", "B"]]))

    def test_merged_labels_carry_to_the_right(self):
        """「平日」はC1だけに値が返る。持ち越さないと土日祝と区別できない。"""
        filled = cm.forward_fill(ROWS[1], 9)
        self.assertEqual(filled[2:6], ["平日"] * 4)
        self.assertEqual(filled[6:9], ["土日祝"] * 3)

    def test_the_four_time_bands_are_named_from_the_rows_above(self):
        columns = cm.hour_columns(ROWS, 3)
        self.assertEqual([label for label, _, _ in columns],
                         ["平日 前", "平日 後", "土日祝 前", "土日祝 後"])
        self.assertEqual([(s, e) for _, s, e in columns], [(2, 3), (4, 5), (6, 7), (8, 9)])

    def test_a_start_without_a_matching_end_is_skipped(self):
        rows = [
            ["", "", "平日"],
            ["", "", "前"],
            ["", "", "開始", "定休"],
            ["1", "どこか院", "9:30", ""],
        ]
        self.assertEqual(cm.hour_columns(rows, 2), [])

    def test_the_closed_column(self):
        self.assertEqual(cm.closed_column(ROWS, 3), 10)


class TestReadingAClinicRow(unittest.TestCase):
    COLUMNS = [("平日 前", 2, 3), ("平日 後", 4, 5), ("土日祝 前", 6, 7), ("土日祝 後", 8, 9)]

    def test_the_first_clinic_in_the_sheet(self):
        self.assertEqual(cm.read_hours(ROWS[5], self.COLUMNS), {
            "平日 前": "9:30-12:30",
            "平日 後": "15:30-21:00",
            "土日祝 前": "8:00-12:00",
            "土日祝 後": "14:30-17:00",
        })
        self.assertEqual(cm.cell_at(ROWS[5], 10), "")

    def test_the_one_row_with_a_closing_day(self):
        """安倍川はK列が「木」。実際のシートで唯一色が付いていた行。"""
        self.assertEqual(cm.cell_at(ROWS[6], 10), "木")

    def test_a_half_filled_band_is_dropped(self):
        """「9:30-」のような読めない値を入れるより、その区分を落とす。"""
        row = ["1", "どこか院", "9:30", "", "15:30", "21:00"]
        self.assertEqual(cm.read_hours(row, self.COLUMNS), {"平日 後": "15:30-21:00"})


class TestNameMatching(unittest.TestCase):
    def test_the_sheet_names_resolve_against_the_clinic_master(self):
        """院名の列には見出しが無いので、照合できることが唯一の裏取りになる。"""
        import json
        path = Path(__file__).resolve().parent.parent / "data" / "clinics.json"
        clinics = json.loads(path.read_text(encoding="utf-8"))["clinics"]
        keys = {cm.normalize_store_name(c["name"]) for c in clinics}
        for row in (ROWS[5], ROWS[6]):
            self.assertIn(cm.normalize_store_name(row[1]), keys, row[1])


if __name__ == "__main__":
    unittest.main()

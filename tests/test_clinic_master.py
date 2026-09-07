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


# 実物の直営院タブの形(2026-09-07、clinic-master.yml --inspect の実行で判明)。
# 「定休」は開始/終了の行ではなく、平日/土日祝と同じグループ見出し行(2つ上)にある。
# ROWS(既存のモック)は定休が開始/終了と同じ行にあり、これとは形が違う——
# 両方に対応できることをここで固定する。
ROWS_CLOSED_ON_A_HIGHER_ROW = [
    ["平日", "", "", "", "土日祝", "", "", "", "定休", "電話番号"],
    ["前", "", "後", "", "前", "", "後", "", "", ""],
    ["開始", "終了", "開始", "終了", "開始", "終了", "開始", "終了", "短縮番号", "携帯電話"],
    ["9:30", "12:30", "15:30", "21:00", "8:00", "12:00", "14:30", "17:00", "", "047-332-7767"],
]


class TestClosedColumnAboveTheHeaderRow(unittest.TestCase):
    def test_header_row_is_found_without_requiring_closed_on_it(self):
        self.assertEqual(cm.header_row_index(ROWS_CLOSED_ON_A_HIGHER_ROW), 2)

    def test_closed_column_is_found_on_the_group_row_above(self):
        self.assertEqual(cm.closed_column(ROWS_CLOSED_ON_A_HIGHER_ROW, 2), 8)


# 実物のミライ・サンズタブの形(2026-09-07、実データで判明)。サブ見出し行(前/後に
# 相当する行)は「平日」側にだけ「松原：全日」という注記が入り、「土日祝」側は空。
ROWS_LEAKING_SUB_HEADER = [
    ["", "", "平日", "", "", "", "土日祝", "", "", ""],
    ["", "", "松原：全日", "松原：全日", "松原：全日", "松原：全日", "", "", "", ""],
    ["", "", "", "", "", "", "", "", "", ""],
    ["", "院名", "開始", "終了", "開始", "終了", "開始", "終了", "開始", "終了"],
    ["1", "弁慶はりきゅう整骨院 西大津院", "10:00", "13:00", "15:30", "21:00",
     "9:00", "12:30", "15:00", "18:00"],
]


class TestSubHeaderDoesNotLeakAcrossGroups(unittest.TestCase):
    """平日側だけにある注記が、空の土日祝側にまで持ち越されると、
    4つの時間帯が同じラベルになって read_hours が後の時間帯で前の時間帯を上書きする。"""

    def test_forward_fill_resets_at_a_group_boundary(self):
        groups = cm.forward_fill(ROWS_LEAKING_SUB_HEADER[0], 10)
        subs = cm.forward_fill(ROWS_LEAKING_SUB_HEADER[1], 10, boundaries=groups)
        self.assertEqual(subs[2:6], ["松原：全日"] * 4)
        self.assertEqual(subs[6:10], ["", "", "", ""])

    def test_all_four_time_bands_survive_with_distinct_labels(self):
        columns = cm.hour_columns(ROWS_LEAKING_SUB_HEADER, 3)
        labels = [label for label, _, _ in columns]
        self.assertEqual(len(labels), 4)
        self.assertEqual(len(set(labels)), 4, labels)

    def test_no_time_band_is_silently_dropped(self):
        columns = cm.hour_columns(ROWS_LEAKING_SUB_HEADER, 3)
        hours = cm.read_hours(ROWS_LEAKING_SUB_HEADER[4], columns)
        self.assertEqual(len(hours), 4, hours)
        self.assertEqual(set(hours.values()),
                         {"10:00-13:00", "15:30-21:00", "9:00-12:30", "15:00-18:00"})


class TestAllowedTabs(unittest.TestCase):
    """『診療時間』にはバックアップ・旧版タブが多数同居する(2026-09-07、実データで判明)。
    栗林さんに確認して固定した現行タブの一覧を、決め打ちにせず設定ファイルから読む。"""

    def test_exactly_the_six_confirmed_brand_tabs(self):
        self.assertEqual(cm.allowed_tabs(), [
            "直営院",
            "ミライ・サンズ",
            "スマイルストーリー［20231113］",
            "心身堂［20260708］",
            "グッドフォーチュン［20240112］",
            "【整体】リラックス",
        ])

    def test_known_junk_tabs_are_not_in_the_list(self):
        junk = ("～20240930までbk", "経営計画書用", "（旧）太洋光井",
                "美容", "トップソルブ", "整体院", "閉院")
        allowed = cm.allowed_tabs()
        for title in junk:
            self.assertNotIn(title, allowed, title)


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

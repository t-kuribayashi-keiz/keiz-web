#!/usr/bin/env python3
"""集計スクリプトのうち、Sheets APIを使わずに検証できる部分のテスト。

ここで守りたいのは「間違ったまま静かに通ってしまう」経路を全部塞ぐこと。
店舗数や合計行を1つ取り違えても数字は自然に見えるので、誰も気づけない。
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import kpi_aggregate as kpi
from store_matcher import StoreMatcher


class TestColumnHelpers(unittest.TestCase):
    def test_round_trip(self):
        for letters, index in (("A", 1), ("N", 14), ("AU", 47), ("BB", 54), ("BL", 64), ("AO", 41)):
            self.assertEqual(kpi.col_to_index(letters), index, letters)
            self.assertEqual(kpi.index_to_col(index), letters, letters)

    def test_source_columns_are_the_ones_specified(self):
        """栗林さん指定(2026-09-03): HPはN/AU/BB/BL、HPBはN、EparkはM。"""
        sources = kpi.load_source_columns()
        self.assertEqual(
            sources["hp"]["columns"], {"hp": "N", "uu_seo": "AU", "uu_meo": "BB", "uu_ppc": "BL"}
        )
        self.assertEqual(sources["hpb"]["columns"], {"hpb": "N"})
        self.assertEqual(sources["epark"]["columns"], {"epark": "M"})

    def test_no_source_column_is_left_unresolved(self):
        for key, source in kpi.load_source_columns().items():
            for name, column in source["columns"].items():
                self.assertIsNotNone(column, f"{key}.{name}")


class TestFindTotalRow(unittest.TestCase):
    def _sheet(self, store_count: int):
        rows = [["店舗名", "", "", "", "", "", "", "", "", "", "", "", "", "集客数"]]
        for i in range(store_count):
            rows.append([f"店舗{i}"] + [""] * 12 + [str(10 + i)])
        rows.append(["合計"] + [""] * 12 + ["9999"])
        return rows

    def test_total_row_moves_with_store_count(self):
        """店舗が増減すると合計行がずれる。だから行番号を固定してはいけない。"""
        self.assertEqual(kpi.find_total_row(self._sheet(150), 14), 152)
        self.assertEqual(kpi.find_total_row(self._sheet(151), 14), 153)

    def test_missing_total_row_raises(self):
        rows = [["店舗名"], ["店舗A"] + [""] * 12 + ["10"]]
        with self.assertRaises(ValueError):
            kpi.find_total_row(rows, 14)

    def test_falls_back_to_the_sum_when_there_is_no_label(self):
        """「合計」というラベルが無いタブでも、値が上の行の合計と一致する行で特定できる。"""
        rows = [["店舗名"] + [""] * 12 + ["集客数"]]
        for i in range(5):
            rows.append([f"店舗{i}"] + [""] * 12 + [str(10 + i)])
        rows.append([""] * 13 + [str(sum(10 + i for i in range(5)))])
        self.assertEqual(kpi.find_total_row(rows, 14), 7)

    def test_multiple_total_rows_raise_instead_of_picking_one(self):
        rows = self._sheet(3)
        rows.append(["総計"] + [""] * 12 + ["8888"])
        with self.assertRaises(ValueError):
            kpi.find_total_row(rows, 14)


class TestFindMonthColumn(unittest.TestCase):
    HEADER = [["", "2026年7月", "2026年8月", "2026年9月"]]

    def test_finds_the_month(self):
        self.assertEqual(kpi.find_month_column(self.HEADER, "2026年8月"), 3)

    def test_accepts_slash_notation(self):
        self.assertEqual(kpi.find_month_column([["", "2026/7", "2026/8"]], "2026年8月"), 3)

    def test_missing_month_raises(self):
        with self.assertRaises(ValueError):
            kpi.find_month_column(self.HEADER, "2027年1月")

    def test_duplicate_month_raises_rather_than_reading_a_neighbour(self):
        rows = [["", "2026年8月", "2026年8月"]]
        with self.assertRaises(ValueError):
            kpi.find_month_column(rows, "2026年8月")


class TestAdSpendCounting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matcher = StoreMatcher()

    def _rows(self, body):
        return [["院名", "2026年7月", "2026年8月"]] + body

    def test_counts_by_group_and_tolerates_media_name_variants(self):
        rows = self._rows([
            ["本八幡駅前整骨院", "10000", "12000"],
            ["【肩こり・腰痛なら】わかば整体院", "8000", "9000"],      # 整骨院→整体院 + 冠文字
            ["たいよう鍼灸整骨院 枚方公園院", "5000", "5000"],          # サンズ
            ["弁慶はりきゅう整骨院 西大津院", "5000", "5000"],          # ミライ
            ["やまもと鍼灸接骨院 おおとり院", "3000", "3000"],          # スマイル(直営には数えない)
            ["都賀駅前整骨院", "7000", ""],                             # 8月は金額なし → 数えない
        ])
        counts, unmatched = kpi.count_ad_spend_stores(rows, "2026年8月", self.matcher)
        self.assertEqual(unmatched, [])
        self.assertEqual(counts.get("直営"), 2)
        self.assertEqual(counts.get("サンズ"), 1)
        self.assertEqual(counts.get("ミライ"), 1)
        self.assertEqual(counts.get("スマイル"), 1)

    def test_zero_amount_is_not_counted_as_listed(self):
        rows = self._rows([["本八幡駅前整骨院", "10000", "0"]])
        counts, _ = kpi.count_ad_spend_stores(rows, "2026年8月", self.matcher)
        self.assertEqual(counts, {})

    def test_summary_rows_are_skipped(self):
        rows = self._rows([
            ["プラチナ", "1", "1"],
            ["PPC(直営院)", "1", "1"],
            ["全合計", "1", "1"],
        ])
        counts, unmatched = kpi.count_ad_spend_stores(rows, "2026年8月", self.matcher)
        self.assertEqual(counts, {})
        self.assertEqual(unmatched, [])

    def test_unknown_store_is_reported_not_swallowed(self):
        rows = self._rows([["まだマスタに無い整骨院 どこか院", "1000", "1000"]])
        counts, unmatched = kpi.count_ad_spend_stores(rows, "2026年8月", self.matcher)
        self.assertEqual(counts, {})
        self.assertEqual(len(unmatched), 1)


class TestResolveTab(unittest.TestCase):
    TITLES = ["8月HP(速報値)", "8月HPB （速報値）", "8月Epark(速報値)", "7月HP(速報値)", "年間計画・目標"]

    def test_picks_the_right_month_and_medium(self):
        self.assertEqual(kpi.resolve_tab(self.TITLES, ["8月", "HP", "速報値"], "x"), "8月HP(速報値)")

    def test_full_width_parentheses_and_spaces_do_not_matter(self):
        self.assertEqual(kpi.resolve_tab(self.TITLES, ["8月", "HPB", "速報値"], "x"), "8月HPB （速報値）")

    def test_missing_tab_raises(self):
        with self.assertRaises(ValueError):
            kpi.resolve_tab(self.TITLES, ["9月", "HP", "速報値"], "x")

    def test_ambiguous_tab_raises_rather_than_reading_last_month(self):
        with self.assertRaises(ValueError):
            kpi.resolve_tab(self.TITLES, ["HP", "速報値"], "x")


class TestFindMonthRow(unittest.TestCase):
    ROWS = [["タイトル"], ["", "媒体名"], ["", "2026年7月"], ["", "2026年8月"]]

    def test_finds_the_row(self):
        self.assertEqual(kpi.find_month_row(self.ROWS, "B", "2026年8月"), 4)

    def test_missing_month_raises(self):
        with self.assertRaises(ValueError):
            kpi.find_month_row(self.ROWS, "B", "2026年9月")


class TestWriteWhitelist(unittest.TestCase):
    def test_store_count_l_is_left_manual(self):
        """L列(店舗数)は栗林さんの判断で当面手動(2026-09-03)。書き込まない。"""
        self.assertNotIn("stores_hp", kpi.WRITABLE_PLAN_KEYS)

    def test_formula_columns_are_never_writable(self):
        """I・K・P・T・U・AD は数式。上書きすると数式が消える。"""
        for key in ("seo_meo", "stores_hpb_total", "stores_epark_total", "uu_natural"):
            self.assertNotIn(key, kpi.WRITABLE_PLAN_KEYS, key)

    def test_manual_columns_are_never_writable(self):
        """③PPC/META は自動化保留、④紹介/オフライン合計/AI は転記方法が未確定。"""
        for key in ("ppc", "meta", "referral", "offline_total", "ai"):
            self.assertNotIn(key, kpi.WRITABLE_PLAN_KEYS, key)

    def test_every_writable_key_has_a_column(self):
        for key in kpi.WRITABLE_PLAN_KEYS:
            self.assertIn(key, kpi.PLAN_COLUMNS, key)


if __name__ == "__main__":
    unittest.main()

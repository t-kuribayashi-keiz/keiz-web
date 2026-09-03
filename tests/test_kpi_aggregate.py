#!/usr/bin/env python3
"""集計スクリプトのうち、Sheets APIを使わずに検証できる部分のテスト。

ここで守りたいのは「間違ったまま静かに通ってしまう」経路を全部塞ぐこと。
店舗数や合計行を1つ取り違えても数字は自然に見えるので、誰も気づけない。
"""

import os
import re
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
    """広告費シートのヘッダーは、年が1月の列にしか入っていない実際の形で試す。

        B1='2017年\n1月'  C1='\n２月' ... M1='\n１２月'  N1='2018年\n１月'

    「2026年7月」という文字列はシートのどこにも存在しない。
    """

    HEADER = [[""] + [f"{2017 + (i // 12)}年\n1月" if i % 12 == 0
                      else f"\n{'０１２３４５６７８９'[(i % 12) + 1] if (i % 12) < 9 else ''}"
                           f"{'１０１１１２'[((i % 12) - 9) * 2:((i % 12) - 9) * 2 + 2] if (i % 12) >= 9 else ''}月"
                      for i in range(12 * 10)]]

    def test_counts_from_the_january_column(self):
        # 2017年1月がB列(2)なので、2017年7月はH列(8)。
        self.assertEqual(kpi.find_month_column(self.HEADER, "2017年7月"), 8)
        # 2018年1月はN列(14)。2018年3月はP列(16)。
        self.assertEqual(kpi.find_month_column(self.HEADER, "2018年3月"), 16)

    def test_january_itself(self):
        self.assertEqual(kpi.find_month_column(self.HEADER, "2018年1月"), 14)

    def test_full_width_month_digits_match(self):
        rows = [["", "2026年\n1月", "\n２月", "\n３月"]]
        self.assertEqual(kpi.find_month_column(rows, "2026年3月"), 4)

    def test_direct_label_still_works(self):
        rows = [["", "2026年7月", "2026年8月"]]
        self.assertEqual(kpi.find_month_column(rows, "2026年8月"), 3)

    def test_missing_year_raises(self):
        with self.assertRaises(ValueError):
            kpi.find_month_column(self.HEADER, "2099年1月")

    def test_stops_when_the_counted_column_is_not_that_month(self):
        """年の列から数えた先の見出しが合わなければ止まる。1列ずれたら隣の月を数えてしまう。"""
        rows = [["", "2026年\n1月", "\n２月"]]   # 3月の列が無い
        with self.assertRaises(ValueError):
            kpi.find_month_column(rows, "2026年3月")

    def test_duplicate_month_raises_rather_than_reading_a_neighbour(self):
        rows = [["", "2026年8月", "2026年8月"]]
        with self.assertRaises(ValueError):
            kpi.find_month_column(rows, "2026年8月")


class TestFindMonthRowBlocks(unittest.TestCase):
    """「年間計画・目標」タブには同じ月の行が複数ある(全体数 / 1店舗当たり ほか)。"""

    ROWS = [
        ["タイトル"],
        ["", "媒体名"],
        ["全体数", "2026年7月", "2059"],
        ["", "2026年8月", "2250"],          # A列は結合セルなので空
        ["1店舗当たり", "2026年7月", "13.7"],
        ["", "2026年8月", "15.0"],
    ]

    def test_block_label_walks_up_through_merged_cells(self):
        self.assertEqual(kpi.block_label_at(self.ROWS, 4), "全体数")
        self.assertEqual(kpi.block_label_at(self.ROWS, 6), "1店舗当たり")

    def test_block_label_disambiguates(self):
        self.assertEqual(kpi.find_month_row(self.ROWS, "B", "2026年7月", "全体数"), 3)
        self.assertEqual(kpi.find_month_row(self.ROWS, "B", "2026年7月", "1店舗当たり"), 5)

    def test_without_a_block_it_refuses_to_guess(self):
        """全体数の行に1店舗当たりを書くと桁が2つ違う値が入る。推測させない。"""
        with self.assertRaises(ValueError):
            kpi.find_month_row(self.ROWS, "B", "2026年7月")


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


class TestDashboardValues(unittest.TestCase):
    """2026年8月の実データで、1店舗当たりの行→ダッシュボードの対応を確かめる。

    表示値は小数第1位までなので、全体数の行からの計算とはわずかにずれる。そのずれが
    許容幅に収まることと、**対応表が正しいこと**の両方をここで見る。
    分母がHPBとEPARKだけ違う(それぞれの掲載店舗数)のが罠で、全部をLで割っても
    桁は合うため目視では気づけない。
    """

    # 「年間計画・目標」タブから2026-09-03に読み取った実際の値。
    PER_STORE = {"C": "14.5", "D": "19.3", "E": "1.4", "F": "3.9", "H": "6.3", "J": "10.3",
                 "L": "8.2", "M": "4.4", "N": "2.4", "O": "4.0", "P": "2.2", "Q": "0.1",
                 "R": "151.2", "S": "151.2", "T": "40.8", "U": "191.9", "V": "307.0"}
    TOTAL = {"C": "2180", "D": "2607", "E": "200", "L": "150", "P": "135", "T": "147",
             "U": "1229", "V": "604", "W": "326", "X": "21", "AD": "28792", "AE": "46050"}

    def _rows(self, per_store=None, total=None):
        def build(mapping, label, month):
            width = max(kpi.col_to_index(c) for c in mapping) if mapping else 2
            row = [""] * max(width, 2)
            row[0] = label
            row[1] = month
            for column, value in mapping.items():
                row[kpi.col_to_index(column) - 1] = value
            return row

        return [
            ["タイトル"], ["", "媒体名"],
            build(total if total is not None else self.TOTAL, "全体数", "2026年8月"),
            build(per_store if per_store is not None else self.PER_STORE, "1店舗当たり", "2026年8月"),
        ]

    def test_row_lookup_uses_formatted_values_not_raw(self):
        """生値だと月のセルが文字列で返らない(日付として保持されている)ため、
        行の特定は表示値、値の読み取りは生値、と分けている。"""
        formatted = self._rows()
        raw = [list(row) for row in formatted]
        for row in raw[2:]:
            row[1] = 46235          # 生値では日付シリアル値になる
        values = kpi.build_dashboard_values(formatted, raw, "2026年8月")
        self.assertAlmostEqual(values["hp"], 14.5, places=6)

    def test_reproduces_the_dashboard_row(self):
        values = kpi.build_dashboard_values(self._rows(), self._rows(), "2026年8月")
        for key, expected in (
            ("web_total", 35.2), ("hp", 14.5), ("hpb", 19.3), ("epark", 1.4),
            ("seo", 8.3), ("meta", 2.2), ("ppc", 4.0), ("uu_seo", 191.9), ("uu_ppc", 307.0),
        ):
            self.assertAlmostEqual(values[key], expected, places=6, msg=key)

    def test_hpb_and_epark_use_their_own_store_counts(self):
        """分母をLに揃えると検算が合わなくなること = 罠が実際に検出できること。"""
        wrong = dict(self.PER_STORE, D=str(2607 / 150), E=str(200 / 150))
        with self.assertRaises(ValueError):
            kpi.build_dashboard_values(self._rows(per_store=wrong), self._rows(per_store=wrong), "2026年8月")

    def test_seo_includes_ai(self):
        """AK = SEO,MEO + AI。AI分(Q列)を落とすと検算に引っかかる。"""
        wrong = dict(self.PER_STORE, Q="0")
        with self.assertRaises(ValueError):
            kpi.build_dashboard_values(self._rows(per_store=wrong), self._rows(per_store=wrong), "2026年8月")

    def test_missing_ai_column_is_treated_as_zero(self):
        """X列(AI集客数)が未入力の月がある。そこで止まらないこと。"""
        total = dict(self.TOTAL, X="")
        per_store = dict(self.PER_STORE, Q="0")
        rows = self._rows(per_store=per_store, total=total)
        values = kpi.build_dashboard_values(rows, rows, "2026年8月")
        self.assertAlmostEqual(values["seo"], 8.2, places=6)


class TestValuesMatch(unittest.TestCase):
    """書き込み後の読み返しの照合。

    読み返しは表示用の値で有効数字10桁程度に丸められるため、完全一致は使えない。
    かといって緩めると、書き込み位置を間違えたときに気づけなくなる。
    """

    def test_rounding_from_the_read_back_is_accepted(self):
        # 実際に起きた値: 14.533333333333333 と書いて 14.53333333 が返る。
        self.assertTrue(kpi.values_match("14.53333333", 14.533333333333333))
        self.assertTrue(kpi.values_match("35.20498866", 35.20498866213152))
        self.assertTrue(kpi.values_match("1.360544218", 1.3605442176870748))

    def test_integers_still_compare_exactly_enough(self):
        self.assertTrue(kpi.values_match("2,180", 2180))
        self.assertFalse(kpi.values_match("2,181", 2180))

    def test_a_real_difference_is_still_caught(self):
        self.assertFalse(kpi.values_match("14.5", 14.533333333333333))
        self.assertFalse(kpi.values_match("191.9", 191.94666666666666))
        self.assertFalse(kpi.values_match("", 14.5))
        self.assertFalse(kpi.values_match("エラー", 14.5))


class TestBackupTabs(unittest.TestCase):
    """複製・バックアップのタブは実データと同じ形なので、読めてしまう。中身は古い。"""

    TITLES = [
        "2026年Web集客KPI管理ダッシュボード",
        "2026年Web集客KPI管理ダッシュボード のコピー",
        "2026年Web集客KPI管理ダッシュボード BK0604",
    ]

    def test_backups_are_excluded(self):
        self.assertEqual(
            kpi.resolve_tab(self.TITLES, ["ダッシュボード"], "x"),
            "2026年Web集客KPI管理ダッシュボード",
        )

    def test_is_backup_tab(self):
        self.assertFalse(kpi.is_backup_tab("年間計画・目標"))
        self.assertFalse(kpi.is_backup_tab("8月HP(速報値)"))
        for title in ("シート のコピー", "計画 BK0604", "旧データ", "backup_2025"):
            self.assertTrue(kpi.is_backup_tab(title), title)


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
    ROWS = [["タイトル"], ["", "媒体名"], ["全体数", "2026年7月"], ["", "2026年8月"]]

    def test_finds_the_row(self):
        self.assertEqual(kpi.find_month_row(self.ROWS, "B", "2026年8月", "全体数"), 4)

    def test_missing_month_raises(self):
        with self.assertRaises(ValueError):
            kpi.find_month_row(self.ROWS, "B", "2026年9月", "全体数")


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


class TestTrendsCsv(unittest.TestCase):
    """工程⑥。GoogleトレンドのCSVからAO3:AS26を書き換える。"""

    KEYWORDS = ["整骨院", "整体", "腰痛", "肩こり", "骨盤矯正"]
    CSV = (
        "カテゴリ: すべてのカテゴリ\n"
        "\n"
        "月,整骨院: (日本),整体: (日本),腰痛: (日本),肩こり: (日本),骨盤矯正: (日本)\n"
        "2025-01,90,89,35,82,9\n"
        "2025-02,90,89,35,77,7\n"
        "2026-07,89,100,32,67,7\n"
        "2026-08,87,97,28,68,7\n"
    )

    def test_parses_by_keyword_not_by_position(self):
        """並び順が変わっても正しい列に入ること。位置で取ると黙って別のキーワードが入る。"""
        shuffled = self.CSV.replace(
            "整骨院: (日本),整体: (日本)", "整体: (日本),整骨院: (日本)"
        )
        parsed = kpi.parse_trends_csv(shuffled, self.KEYWORDS)
        self.assertEqual(parsed[(2025, 1)]["整体"], 90)
        self.assertEqual(parsed[(2025, 1)]["整骨院"], 89)

    def test_reads_the_real_shape(self):
        parsed = kpi.parse_trends_csv(self.CSV, self.KEYWORDS)
        self.assertEqual(parsed[(2026, 8)],
                         {"整骨院": 87, "整体": 97, "腰痛": 28, "肩こり": 68, "骨盤矯正": 7})

    def test_less_than_one_becomes_zero(self):
        csv = self.CSV.replace("2025-01,90,89,35,82,9", "2025-01,90,89,35,82,<1")
        self.assertEqual(kpi.parse_trends_csv(csv, self.KEYWORDS)[(2025, 1)]["骨盤矯正"], 0)

    def test_weekly_csv_is_rejected(self):
        """期間が短いとGoogleトレンドは週次で返す。週を月に畳んでも月次は再現できない。"""
        weekly = self.CSV.replace("月,整骨院", "週,整骨院").replace(
            "2025-01,", "2025-01-05,").replace("2025-02,", "2025-01-12,")
        with self.assertRaises(ValueError) as caught:
            kpi.parse_trends_csv(weekly, self.KEYWORDS)
        self.assertIn("週次", str(caught.exception))

    def test_missing_keyword_stops(self):
        csv = self.CSV.replace("骨盤矯正: (日本)", "ぎっくり腰: (日本)")
        with self.assertRaises(ValueError):
            kpi.parse_trends_csv(csv, self.KEYWORDS)

    def test_separately_pulled_csv_is_rejected(self):
        """1キーワードずつ取ると5つそれぞれに100が出る。比較できないのに数字は自然に見える。"""
        separate = {
            (2025, 1): {k: 100 for k in self.KEYWORDS},
            (2025, 2): {k: 80 for k in self.KEYWORDS},
        }
        with self.assertRaises(ValueError):
            kpi.check_joint_normalization(separate)

    def test_jointly_pulled_csv_is_accepted(self):
        joint = kpi.parse_trends_csv(self.CSV, self.KEYWORDS)
        kpi.check_joint_normalization(joint)   # 整体 2026/7 だけが100

    def test_missing_hundred_stops(self):
        with self.assertRaises(ValueError):
            kpi.check_joint_normalization({(2025, 1): {k: 50 for k in self.KEYWORDS}})

    def test_writes_only_the_months_the_sheet_has(self):
        header = [""] * 45
        for column, keyword in zip(kpi.TRENDS_VALUE_COLUMNS, self.KEYWORDS):
            header[kpi.col_to_index(column) - 1] = keyword
        month_rows = []
        for label in ("2025/1", "2025/2", "2026/7", "2026/8", "2026/9"):
            row = [""] * 45
            row[kpi.col_to_index(kpi.TRENDS_MONTH_COLUMN) - 1] = label
            month_rows.append(row)

        parsed = kpi.parse_trends_csv(self.CSV, self.KEYWORDS)
        planned = kpi.build_trends_writes("年間計画・目標", header, month_rows, parsed)

        # 4か月 × 5キーワード。2026/9 はCSVに無いので空のまま残す。
        self.assertEqual(len(planned), 20)
        self.assertEqual(planned["trends_2025-01_整骨院"][1], "AO3")
        self.assertEqual(planned["trends_2026-08_骨盤矯正"][1], "AS6")
        self.assertNotIn("trends_2026-09_整骨院", planned)

    def test_the_formula_columns_are_never_written(self):
        """AT列と正規化ブロックは数式。定数で上書きすると壊れる。"""
        header = [""] * 45
        for column, keyword in zip(kpi.TRENDS_VALUE_COLUMNS, self.KEYWORDS):
            header[kpi.col_to_index(column) - 1] = keyword
        row = [""] * 45
        row[kpi.col_to_index(kpi.TRENDS_MONTH_COLUMN) - 1] = "2025/1"
        planned = kpi.build_trends_writes(
            "年間計画・目標", header, [row], kpi.parse_trends_csv(self.CSV, self.KEYWORDS)
        )
        for _, ref, _ in planned.values():
            column = re.match(r"[A-Z]+", ref).group(0)
            row_number = int(re.search(r"\d+", ref).group(0))
            self.assertIn(column, kpi.TRENDS_VALUE_COLUMNS)
            self.assertLessEqual(row_number, kpi.TRENDS_LAST_ROW)

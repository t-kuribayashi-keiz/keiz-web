#!/usr/bin/env python3
"""EPARK法人名の分類が、実シートの内訳を再現できるかを確かめる。

期待値の出どころ: 2026-09-03に「EPARK掲載店舗リスト」2026/8タブ(158行)を読み、
その内訳を数えたところ 直営131 / サンズ8 / ミライ8 / スマイル11 になった。この4つは
KPIシート「年間計画・目標」2026年8月行の Q=131 / R=8 / S=8 / T=147 と一致している。
つまりこの期待値は推測ではなく、別々の2つのシートが独立に裏付けている数字。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from kpi_aggregate import classify_epark_corporation, count_epark_stores, load_epark_groups

# 実シートに出現する契約法人名と、2026/8タブでの件数。
OBSERVED = {
    "株式会社クラシオン": ("chokuei", 22),
    "株式会社ケイズ": ("chokuei", 20),
    "株式会社エフアール": ("chokuei", 19),
    "株式会社フォース": ("chokuei", 19),
    "ドリームジャパン株式会社": ("chokuei", 19),
    "株式会社アポロ": ("chokuei", 16),
    "株式会社バーニング": ("chokuei", 14),
    "株式会社トラスト": ("chokuei", 2),
    "株式会社太洋メディカル": ("sans", 6),
    "株式会社サンズ": ("sans", 2),
    "株式会社光井JAPAN": ("mirai", 5),
    "株式会社ミライ": ("mirai", 3),
    "有限会社スマイルストーリー": ("excluded", 11),
}


class TestEparkClassifier(unittest.TestCase):
    def test_each_corporation_lands_in_the_expected_group(self):
        groups = load_epark_groups()
        for name, (expected, _) in OBSERVED.items():
            self.assertEqual(classify_epark_corporation(name, groups), expected, name)

    def test_spacing_variants_still_match(self):
        """『株式会社 エフアール』のように空白入りの行が実際にある。"""
        groups = load_epark_groups()
        self.assertEqual(classify_epark_corporation("株式会社 エフアール", groups), "chokuei")
        self.assertEqual(classify_epark_corporation("株式会社　ケイズ", groups), "chokuei")

    def test_unknown_corporation_stops_instead_of_counting_as_chokuei(self):
        groups = load_epark_groups()
        with self.assertRaises(ValueError):
            classify_epark_corporation("株式会社まだ知らない法人", groups)

    def test_counts_reproduce_the_sheet(self):
        """2026/8タブの内訳を再現し、KPIシートのQ/R/S/Tと突き合わせる。"""
        rows = [["gp", "契約法人名", "施設名"]]
        gp = 0
        for name, (_, count) in OBSERVED.items():
            for _ in range(count):
                gp += 1
                rows.append([str(gp), name, f"ダミー{gp}院"])

        counts = count_epark_stores(rows)
        self.assertEqual(counts["chokuei"], 131)   # Q列
        self.assertEqual(counts["sans"], 8)        # R列
        self.assertEqual(counts["mirai"], 8)       # S列
        self.assertEqual(counts["excluded"], 11)   # 対象外(スマイル)
        self.assertEqual(counts["chokuei"] + counts["sans"] + counts["mirai"], 147)  # T列
        self.assertEqual(sum(counts.values()), 158)  # シートの行数


if __name__ == "__main__":
    unittest.main()

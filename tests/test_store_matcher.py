#!/usr/bin/env python3
"""店舗名マッチングの検証。

守りたい性質は2つ:
  1. 媒体ごとの表記ゆれ(整骨院→整体院、冠文字、鍼灸/針灸)を吸収して同じ店舗に当てること
  2. **当てられないときに黙って直営に寄せないこと**。集計サマリー行や未知の店舗名が
     直営として1件数えられても、数字は自然に見えてしまい誰も気づかない
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from store_matcher import StoreMatcher, group_of, normalize_store_name


class TestNormalization(unittest.TestCase):
    def test_clinic_type_words_collapse_to_one_token(self):
        for name in ("本八幡駅前整骨院", "本八幡駅前整体院", "本八幡駅前接骨院"):
            self.assertEqual(normalize_store_name(name), "本八幡駅前〇", name)

    def test_seo_prefix_is_stripped(self):
        self.assertEqual(
            normalize_store_name("【肩こり・腰痛なら】本八幡駅前整体院"),
            normalize_store_name("本八幡駅前整骨院"),
        )

    def test_trailing_in_marker_is_ignored(self):
        self.assertEqual(
            normalize_store_name("たいよう鍼灸整骨院 枚方公園院"),
            normalize_store_name("たいよう鍼灸整骨院 枚方公園"),
        )

    def test_case_is_ignored(self):
        """広告費シートは『たいよう鍼灸整骨院BRANCH松井山手』、院マスタは『branch松井山手院』。"""
        self.assertEqual(
            normalize_store_name("たいよう鍼灸整骨院BRANCH松井山手"),
            normalize_store_name("たいよう鍼灸整骨院 branch松井山手院"),
        )

    def test_only_leading_brackets_are_dropped(self):
        """先頭の冠文字は装飾だが、途中・末尾の括弧は店舗を識別する情報。中身を消さない。"""
        self.assertEqual(normalize_store_name("おかだ鍼灸整骨院（御殿山）"), "おかだ〇御殿山")

    def test_brand_prefix_is_stripped(self):
        """広告費シートは『リフレッシュセンターリラックス梅ヶ丘店』、院マスタは『梅ヶ丘店』。"""
        self.assertEqual(
            normalize_store_name("リフレッシュセンターリラックス梅ヶ丘店"),
            normalize_store_name("梅ヶ丘店"),
        )

    def test_shin_kyu_spelling_variants_unify(self):
        self.assertEqual(
            normalize_store_name("すまいる針灸接骨院 六甲道院"),
            normalize_store_name("すまいる鍼灸接骨院 六甲道院"),
        )


class TestMatching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matcher = StoreMatcher()
        with open(os.path.join(ROOT, "data", "clinics.json"), encoding="utf-8") as handle:
            cls.clinics = json.load(handle)["clinics"]

    def test_no_two_clinics_normalize_into_different_groups(self):
        """正規化を強くしすぎて別グループの店舗が同一視されていないこと。"""
        collisions = {
            key: [c["name"] for c in group]
            for key, group in self.matcher.by_normalized.items()
            if len({group_of(c) for c in group}) > 1
        }
        self.assertEqual(collisions, {})

    def test_every_master_store_matches_itself_and_its_media_variants(self):
        misses = []
        for clinic in self.clinics:
            name = clinic["name"]
            variants = [
                name,
                "【肩こり・腰痛なら】" + name,
                "［骨盤矯正］" + name,
                name.replace("整骨院", "整体院").replace("接骨院", "整体院"),
                name.replace("鍼灸", "針灸"),
                name.replace(" ", "　"),
                name.upper(),
            ]
            if clinic["brand"] == "リラックス":
                variants.append("リフレッシュセンターリラックス" + name)
            for variant in variants:
                result = self.matcher.match(variant)
                if result["group"] != group_of(clinic):
                    misses.append((name, variant, result["how"], result["group"]))
        self.assertEqual(misses, [])

    def test_summary_rows_do_not_match_any_store(self):
        """広告費シートの集計サマリー行を店舗として数えないこと。"""
        for label in ("プラチナ", "ゴールド", "正会員", "アイワ", "レセワン",
                      "HPB(直営院)", "PPC(直営院)", "全合計", "院名", "Line"):
            result = self.matcher.match(label)
            self.assertIsNone(result["group"], f"{label} -> {result}")
            self.assertIn(result["how"], ("unmatched", "ambiguous"), label)

    def test_unknown_store_is_not_silently_counted_as_chokuei(self):
        result = self.matcher.match("まだマスタに無い整骨院 どこか院")
        self.assertIsNone(result["group"])

    def test_names_seen_in_the_ad_spend_sheet(self):
        """2026-07の実行で突き合わせられなかった実際の店舗名。全部当たること。"""
        expected = {
            "たいよう鍼灸整骨院BRANCH松井山手": "サンズ",
            "おかだ鍼灸整骨院（御殿山）": "サンズ",
            "薬園台駅東口接骨院": "直営",
            "高円寺店": "リラックス",
            "リフレッシュセンターリラックスたまプラーザ東急百貨店": "リラックス",
            "リフレッシュセンターリラックスFKDインターパーク店": "リラックス",
        }
        for name, group in expected.items():
            self.assertEqual(self.matcher.match(name)["group"], group, name)

    def test_group_of_folds_chokuei_corporations_together(self):
        """M列・Q列(直営)は法人を分けないので、直営配下は全部『直営』に畳む。"""
        groups = {group_of(c) for c in self.clinics if c["brand"] == "直営"}
        self.assertEqual(groups, {"直営"})

    def test_sansu_and_mirai_stay_separate(self):
        """N/O列・R/S列はサンズとミライを分けるので、畳んではいけない。"""
        groups = {group_of(c) for c in self.clinics if c["brand"] == "サンズミライ"}
        self.assertEqual(groups, {"サンズ", "ミライ"})


if __name__ == "__main__":
    unittest.main()

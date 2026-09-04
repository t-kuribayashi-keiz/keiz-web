"""GA4プロパティ名→店舗の突き合わせ。

プロパティ名の付け方は実物を見るまで分からないので、**ありそうな書き方を複数試して
どれでも通ること**を確かめる。ここで取り違えると、別店舗の数字が黙って入る。
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ga4_properties as ga4  # noqa: E402


class TestCleanPropertyName(unittest.TestCase):
    def test_decorations_are_dropped(self):
        for raw, want in (
            ("リラックス 阿佐ヶ谷店 - GA4", "リラックス 阿佐ヶ谷店"),
            ("GA4_浦和店", "浦和店"),
            ("梅ヶ丘店（GA4）", "梅ヶ丘店"),
            ("refresh-relax.com 笹塚店", "笹塚店"),
            ("笹塚店 Google Analytics 4", "笹塚店"),
        ):
            self.assertEqual(ga4.clean_property_name(raw), want, raw)

    def test_a_name_that_is_only_decoration_is_left_alone(self):
        """空にすると、どの店舗にも当たらないのではなく全店舗に当たってしまう。"""
        self.assertNotEqual(ga4.clean_property_name("GA4"), "")
        self.assertNotEqual(ga4.clean_property_name("refresh-relax.com"), "")

    def test_a_plain_store_name_is_untouched(self):
        self.assertEqual(ga4.clean_property_name("久我山店"), "久我山店")

    def test_decorated_names_still_reach_the_right_store(self):
        """見た目の整形より、正しい店舗に解決されることが本題。"""
        for raw in ("梅ヶ丘店（GA4）", "GA4_梅ヶ丘店", "refresh-relax.com 梅ヶ丘店",
                    "リフレッシュセンターリラックス梅ヶ丘店 - GA4"):
            result = ga4.resolve([raw], "リラックス")
            self.assertEqual(list(result["matched"]), ["梅ヶ丘店"], raw)


class TestPropertyNamesFrom(unittest.TestCase):
    def test_plain_lines(self):
        self.assertEqual(
            ga4.property_names_from(" 浦和店 \n\n笹塚店\n"), ["浦和店", "笹塚店"]
        )

    def test_admin_api_json(self):
        raw = json.dumps({"accountSummaries": [{"propertySummaries": [
            {"displayName": "浦和店", "property": "properties/111"},
            {"displayName": "笹塚店", "property": "properties/222"},
        ]}]})
        self.assertEqual(ga4.property_names_from(raw), ["浦和店", "笹塚店"])
        self.assertEqual(ga4.property_id_map(raw),
                         {"浦和店": "properties/111", "笹塚店": "properties/222"})

    def test_a_plain_list_has_no_ids(self):
        self.assertEqual(ga4.property_id_map("浦和店\n笹塚店"), {})


class TestResolve(unittest.TestCase):
    """実際の data/clinics.json のリラックス25店舗に対して突き合わせる。"""

    CLINICS = Path(__file__).resolve().parent.parent / "data" / "clinics.json"

    @classmethod
    def setUpClass(cls):
        clinics = json.loads(cls.CLINICS.read_text(encoding="utf-8"))["clinics"]
        cls.relax = [c["name"] for c in clinics if c["brand"] == "リラックス"]

    def test_the_store_list_is_what_we_expect(self):
        self.assertEqual(len(self.relax), 25)

    def test_exact_store_names_all_resolve(self):
        result = ga4.resolve(list(self.relax), "リラックス")
        self.assertEqual(len(result["matched"]), 25)
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["unmatched"], [])
        self.assertEqual(result["duplicated"], {})

    def test_names_carrying_the_brand_prefix_resolve(self):
        """広告費シートは『リフレッシュセンターリラックス梅ヶ丘店』と書く。同じ表記ゆれ。"""
        names = ["リフレッシュセンターリラックス" + name for name in self.relax]
        result = ga4.resolve(names, "リラックス")
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["unmatched"], [])

    def test_names_with_ga4_decoration_resolve(self):
        names = [f"{name} - GA4" for name in self.relax]
        result = ga4.resolve(names, "リラックス")
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["unmatched"], [])

    def test_two_properties_for_one_store_are_both_dropped(self):
        """どちらが正か決められないものを片方選ぶと、外れたほうの数字が消える。"""
        result = ga4.resolve(["浦和店", "浦和店 - GA4", "笹塚店"], "リラックス")
        self.assertNotIn("浦和店", result["matched"])
        self.assertIn("浦和店", result["duplicated"])
        self.assertIn("笹塚店", result["matched"])

    def test_an_unknown_property_is_reported_not_forced(self):
        result = ga4.resolve(["浦和店", "どこにも無い店"], "リラックス")
        self.assertEqual(len(result["unmatched"]), 1)
        self.assertEqual(result["unmatched"][0][0], "どこにも無い店")
        self.assertEqual(len(result["matched"]), 1)

    def test_a_property_for_another_brand_does_not_enter_this_table(self):
        """院マスタには204院いる。リラックス以外に当たったものを混ぜない。"""
        result = ga4.resolve(["浦和店", "本八幡駅前整骨院"], "リラックス")
        self.assertEqual(list(result["matched"]), ["浦和店"])
        self.assertEqual(len(result["other_brand"]), 1)

    def test_missing_stores_are_listed(self):
        result = ga4.resolve(["浦和店"], "リラックス")
        self.assertEqual(len(result["missing"]), 24)
        self.assertIn("笹塚店", result["missing"])

    def test_an_unknown_brand_stops(self):
        with self.assertRaises(ValueError):
            ga4.resolve(["浦和店"], "存在しないブランド")


class TestReportExitCode(unittest.TestCase):
    def test_unresolved_input_reports_failure(self):
        result = ga4.resolve(["浦和店"], "リラックス")
        self.assertEqual(ga4.report(result), 1, "24店舗欠けているのに成功で返してはいけない")

    def test_a_complete_mapping_reports_success(self):
        clinics = json.loads(
            TestResolve.CLINICS.read_text(encoding="utf-8")
        )["clinics"]
        names = [c["name"] for c in clinics if c["brand"] == "リラックス"]
        self.assertEqual(ga4.report(ga4.resolve(names, "リラックス")), 0)


if __name__ == "__main__":
    unittest.main()

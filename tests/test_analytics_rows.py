"""GA4・Search Consoleの応答を統合ログの行に落とす部分。

APIは叩かない。応答の形だけを与えて、行の作り方が正しいかを見る。
一番間違えやすいのは**ページURLをどの店舗に当てるか**で、ここを外すと
別店舗の数字が黙って積み上がる。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import analytics_rows as rows  # noqa: E402


class TestStorePaths(unittest.TestCase):
    def test_paths_come_from_the_clinic_master(self):
        paths = rows.store_paths("リラックス")
        self.assertEqual(paths["tama"], "たまプラーザ東急百貨店")
        self.assertEqual(paths["togoshiginza"], "戸越銀座店")
        self.assertEqual(len(paths), 25)  # 2026-09-07にURL登録され全25店舗ぶん揃った

    def test_another_brand_gets_its_own_paths(self):
        self.assertEqual(rows.store_paths("存在しないブランド"), {})


class TestStoreOfPage(unittest.TestCase):
    PATHS = {
        "tama": "たまプラーザ東急百貨店",
        "nakanoshinbashi": "中野新橋店",
        "nakanosakaue": "中野坂上店",
        "asagaya": "阿佐ヶ谷店",
    }

    def test_a_store_page(self):
        self.assertEqual(
            rows.store_of_page("https://refresh-relax.com/tama/", self.PATHS),
            "たまプラーザ東急百貨店",
        )

    def test_a_page_below_the_store(self):
        self.assertEqual(
            rows.store_of_page("https://refresh-relax.com/asagaya/price/", self.PATHS),
            "阿佐ヶ谷店",
        )

    def test_similar_prefixes_do_not_bleed(self):
        """中野新橋と中野坂上は接頭辞が重なる。短いほうから採ると取り違える。"""
        self.assertEqual(
            rows.store_of_page("https://refresh-relax.com/nakanosakaue/", self.PATHS),
            "中野坂上店",
        )
        self.assertEqual(
            rows.store_of_page("https://refresh-relax.com/nakanoshinbashi/", self.PATHS),
            "中野新橋店",
        )

    def test_a_path_that_merely_starts_with_a_store_path_is_not_that_store(self):
        """`/tama/` と `/tamagawa/` は別物。区切りまで見る。"""
        self.assertEqual(
            rows.store_of_page("https://refresh-relax.com/tamagawa/", self.PATHS),
            rows.OUTSIDE,
        )

    def test_the_top_page_is_not_dropped(self):
        """店舗外を捨てると、合計が合わないときに理由が分からなくなる。"""
        self.assertEqual(
            rows.store_of_page("https://refresh-relax.com/", self.PATHS), rows.OUTSIDE
        )


class TestGscRows(unittest.TestCase):
    PATHS = {"tama": "たまプラーザ東急百貨店", "asagaya": "阿佐ヶ谷店"}

    RESPONSE = {"rows": [
        {"keys": ["https://refresh-relax.com/tama/"],
         "clicks": 30, "impressions": 1000, "ctr": 0.03, "position": 5.0},
        {"keys": ["https://refresh-relax.com/tama/price/"],
         "clicks": 10, "impressions": 1000, "ctr": 0.01, "position": 15.0},
        {"keys": ["https://refresh-relax.com/"],
         "clicks": 5, "impressions": 100, "ctr": 0.05, "position": 2.0},
    ]}

    def rows_for(self, store):
        produced = rows.gsc_rows("2026-08", self.RESPONSE, self.PATHS)
        return {r["metric"]: r["value"] for r in produced if r["store"] == store}

    def test_pages_of_one_store_are_summed(self):
        tama = self.rows_for("たまプラーザ東急百貨店")
        self.assertEqual(tama["クリック"], 40)
        self.assertEqual(tama["表示回数"], 2000)

    def test_ctr_is_recomputed_not_averaged(self):
        """0.03と0.01の平均(0.02)ではなく、40/2000=0.02。この例では一致するが、
        表示回数が偏ると違う値になる。式として正しいほうを採る。"""
        tama = self.rows_for("たまプラーザ東急百貨店")
        self.assertAlmostEqual(tama["CTR"], 40 / 2000)

    def test_position_is_weighted_by_impressions(self):
        """単純平均なら10.0。表示回数が同じなのでここでは10.0で正しい。"""
        tama = self.rows_for("たまプラーザ東急百貨店")
        self.assertAlmostEqual(tama["平均掲載順位"], (5.0 * 1000 + 15.0 * 1000) / 2000)

    def test_position_weighting_actually_differs_from_a_plain_average(self):
        response = {"rows": [
            {"keys": ["https://refresh-relax.com/tama/"],
             "clicks": 0, "impressions": 1, "position": 100.0},
            {"keys": ["https://refresh-relax.com/tama/a/"],
             "clicks": 0, "impressions": 9999, "position": 2.0},
        ]}
        produced = {r["metric"]: r["value"]
                    for r in rows.gsc_rows("2026-08", response, self.PATHS)}
        self.assertLess(produced["平均掲載順位"], 3.0, "単純平均なら51になる")

    def test_the_top_page_lands_outside_not_in_a_store(self):
        outside = self.rows_for(rows.OUTSIDE)
        self.assertEqual(outside["クリック"], 5)

    def test_a_store_with_no_impressions_gets_no_rate_rows(self):
        """0で割らない。件数の行だけ出す。"""
        response = {"rows": [{"keys": ["https://refresh-relax.com/tama/"],
                              "clicks": 0, "impressions": 0, "position": 0}]}
        produced = [r["metric"] for r in rows.gsc_rows("2026-08", response, self.PATHS)]
        self.assertEqual(produced, ["クリック", "表示回数"])

    def test_an_empty_response(self):
        self.assertEqual(rows.gsc_rows("2026-08", {}, self.PATHS), [])


class TestGa4Rows(unittest.TestCase):
    RESPONSE = {
        "dimensionHeaders": [{"name": "sessionDefaultChannelGroup"}],
        "metricHeaders": [{"name": "sessions"}, {"name": "totalUsers"}],
        "rows": [
            {"dimensionValues": [{"value": "Organic Search"}],
             "metricValues": [{"value": "1200"}, {"value": "900"}]},
            {"dimensionValues": [{"value": "Paid Search"}],
             "metricValues": [{"value": "300"}, {"value": "250"}]},
        ],
    }

    def test_each_channel_and_metric_becomes_a_row(self):
        produced = rows.ga4_rows("2026-08", "たまプラーザ東急百貨店", self.RESPONSE)
        self.assertEqual(len(produced), 4)
        self.assertEqual(
            {(r["channel"], r["metric"], r["value"]) for r in produced},
            {("Organic Search", "sessions", 1200.0),
             ("Organic Search", "totalUsers", 900.0),
             ("Paid Search", "sessions", 300.0),
             ("Paid Search", "totalUsers", 250.0)},
        )

    def test_metric_names_come_from_the_response_not_from_us(self):
        """問い合わせ側の指定を写すと、問い合わせを変えたとき黙ってずれる。"""
        response = dict(self.RESPONSE, metricHeaders=[{"name": "keyEvents"},
                                                      {"name": "totalUsers"}])
        produced = rows.ga4_rows("2026-08", "店", response)
        self.assertIn("keyEvents", {r["metric"] for r in produced})

    def test_a_non_numeric_metric_is_dropped(self):
        response = {
            "dimensionHeaders": [{"name": "sessionDefaultChannelGroup"}],
            "metricHeaders": [{"name": "sessions"}],
            "rows": [{"dimensionValues": [{"value": "Direct"}],
                      "metricValues": [{"value": "(not set)"}]}],
        }
        self.assertEqual(rows.ga4_rows("2026-08", "店", response), [])

    def test_an_empty_response(self):
        self.assertEqual(rows.ga4_rows("2026-08", "店", {}), [])


class TestTsv(unittest.TestCase):
    def test_header_and_one_row(self):
        text = rows.to_tsv([{"month": "2026-08", "store": "浦和店",
                             "channel": "SEO", "metric": "クリック", "value": 40.0}])
        self.assertEqual(text.splitlines()[0], "年月\t店舗\tチャネル\t指標\t値")
        self.assertEqual(text.splitlines()[1], "2026-08\t浦和店\tSEO\tクリック\t40")


if __name__ == "__main__":
    unittest.main()

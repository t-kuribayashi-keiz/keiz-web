"""hpb_ribbon_extract / hpb_master_writer の純粋ロジックの回帰テスト。

ネットワーク・PDFライブラリ・サービスアカウントを一切使わない。PDFから取り出した
テキストのfixtureと、集客数タブを模した2次元配列だけで、抽出と結合の要所を固める。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import hpb_ribbon_extract as ext  # noqa: E402
import hpb_master_writer as wr  # noqa: E402


# 実PDFのP1「性別/年齢」ブロックの並びを模したもの。末尾2列が『当月号(進行中)』『翌月号』で、
# 完了月は末尾から2列目。開店直後は先頭が『- %』で入る。
PAGE1_LINES = (
    "女性率\n82%\n82%\n64%\n57%\n71%\n75%\n53%\n73%\n53%\n58%\n56%\n67%\n67%\n0%\n"
    "男性率\n18%\n18%\n36%\n43%\n29%\n25%\n47%\n27%\n47%\n42%\n44%\n33%\n33%\n0%\n"
    "年齢\n"
    "20代未満\n0%\n5%\n0%\n0%\n0%\n0%\n0%\n0%\n0%\n5%\n0%\n17%\n0%\n0%\n"
    "20代\n18%\n27%\n21%\n36%\n14%\n75%\n29%\n18%\n26%\n21%\n31%\n33%\n0%\n0%\n"
    "30代\n55%\n23%\n43%\n29%\n29%\n8%\n29%\n55%\n37%\n37%\n6%\n33%\n17%\n0%\n"
    "40代\n18%\n36%\n14%\n21%\n14%\n17%\n12%\n9%\n16%\n26%\n38%\n17%\n33%\n0%\n"
    "50代以上\n9%\n9%\n21%\n14%\n43%\n0%\n29%\n18%\n16%\n11%\n25%\n0%\n50%\n0%\n"
    "未設定\n"
).split("\n")

# 開店直後(早い月が『- %』)。完了月は末尾から2列目の 59%。
PAGE1_NEW_STORE = (
    "女性率\n- %\n- %\n- %\n- %\n- %\n- %\n- %\n- %\n- %\n- %\n- %\n57%\n59%\n0%\n"
    "男性率\n"
).split("\n")

SUMMARY_TEXT = (
    "自サロンTOP PV\n同エリア・同プラン・同ジャン\nル平均\n比較サロン平均\n"
    "432\n1,036\n1,119\n興味喚起\n対比較サロン平均\n100.2%\n"
    "自サロンCVR\n同エリア・同プラン・同ジャン\nル平均\n比較サロン平均\n"
    "62.5%\n55.1%\n62.4%\nアクション\n対比較サロン平均\n46.3%\n"
    "自サロンACR\n同エリア・同プラン・同ジャン\nル平均\n比較サロン平均\n"
    "3.0%\n7.6%\n6.4%\n"
    "予約数\n前月予約数\n6\n達成率：20.0%\n新規予約\nリピート予約\n5\n達成率：16.7%\n1\n"
)

SUMMARY_EMPTY = (
    "自サロンTOP PV\n同エリア・同プラン・同ジャン\nル平均\n比較サロン平均\n"
    "-\n-\n-\n興味喚起\n対比較サロン平均\n- %\n"
    "自サロンCVR\n同エリア・同プラン・同ジャン\nル平均\n比較サロン平均\n- %\n- %\n- %\n"
    "自サロンACR\n同エリア・同プラン・同ジャン\nル平均\n比較サロン平均\n- %\n- %\n- %\n"
)


class TestSeries(unittest.TestCase):
    def test_completed_month_is_second_to_last(self):
        val, n = ext.series_completed_value(PAGE1_LINES, "女性率")
        self.assertEqual(val, "67%")
        self.assertEqual(n, 14)

    def test_label_prefix_does_not_bleed(self):
        # 「20代未満」を探しても「20代」に化けない(完全一致行のみ)
        val, _ = ext.series_completed_value(PAGE1_LINES, "20代未満")
        self.assertEqual(val, "0%")
        val20, _ = ext.series_completed_value(PAGE1_LINES, "20代")
        self.assertEqual(val20, "0%")   # この店の完了月(末尾-2)の20代は0%

    def test_age_sums_to_100(self):
        ages = [ext.clean_number(ext.series_completed_value(PAGE1_LINES, lbl)[0])
                for lbl in ("20代未満", "20代", "30代", "40代", "50代以上")]
        self.assertAlmostEqual(sum(float(a) for a in ages), 100.0, delta=1.0)

    def test_dash_months_counted_as_columns(self):
        # 『- %』を欠損列として数えるので、完了月(末尾-2)=59% を正しく取る
        val, n = ext.series_completed_value(PAGE1_NEW_STORE, "女性率")
        self.assertEqual(val, "59%")   # 末尾-2(=完了月)。末尾0%は当月号(進行中)
        self.assertEqual(n, 14)


class TestSummary(unittest.TestCase):
    def test_parse(self):
        k = ext.parse_summary_kpis(SUMMARY_TEXT)
        self.assertEqual(k["自社PV"], "432")
        self.assertEqual(k["エリア平均PV"], "1036")
        self.assertEqual(k["自社CVR"], "62.5")
        self.assertEqual(k["エリア平均CVR"], "55.1")
        self.assertEqual(k["自社ACR"], "3.0")
        self.assertEqual(k["エリア平均ACR"], "7.6")
        self.assertEqual(k["新規予約数実績"], "5")
        self.assertEqual(k["集客数_ribbon_ALL"], "6")

    def test_empty_new_store(self):
        k = ext.parse_summary_kpis(SUMMARY_EMPTY)
        self.assertIsNone(k["自社PV"])
        self.assertIsNone(k["エリア平均CVR"])
        self.assertIsNone(k["新規予約数実績"])

    def test_filename(self):
        self.assertEqual(
            ext.store_name_from_filename("【腰痛】五井駅東口整体院_20260902_120814.pdf"),
            "【腰痛】五井駅東口整体院")


class TestResolveTab(unittest.TestCase):
    def test_hp_not_hpb(self):
        titles = ["8月HP(速報値)", "8月HPB (速報値)", "8月Epark（速報値)"]
        self.assertEqual(wr.resolve_tab(titles, ["8月", "HP", "速報値"]), "8月HP(速報値)")
        self.assertEqual(wr.resolve_tab(titles, ["8月", "HPB", "速報値"]), "8月HPB (速報値)")

    def test_ambiguous_raises(self):
        with self.assertRaises(ValueError):
            wr.resolve_tab(["A速報値", "B速報値"], ["速報値"])

    def test_month_keywords(self):
        self.assertEqual(wr.month_tab_keywords(["HPB", "速報値"], "2026年08月号"),
                         ["8月", "HPB", "速報値"])


class TestShukyakuJoin(unittest.TestCase):
    def test_build_map_stops_at_total(self):
        values = [
            ["エリア", "", "…院名", "当月", "前月"],
            ["関東", "", "佐倉ユーカリが丘接骨院", "8", "9"],
            ["関東", "", "市川げんき整骨院", "21", "16"],
            ["", "", "合計", "2607", ""],
            ["", "", "店舗数", "130", ""],
        ]
        m = wr.build_shukyaku_map(values)
        self.assertIn(wr.normalize_store_name("佐倉ユーカリが丘接骨院"), m)
        self.assertEqual(m[wr.normalize_store_name("市川げんき整骨院")][1], "21")
        # 合計以降は入らない
        self.assertNotIn(wr.normalize_store_name("店舗数"), m)

    def test_twin_listing_not_double_counted(self):
        # 集客数側は「八幡宿駅西口接骨院」1件。抽出側に接骨院と鍼灸接骨院の2行。
        shu = {wr.normalize_store_name("八幡宿駅西口接骨院"): ("八幡宿駅西口接骨院", "24")}
        rows = [
            {"店舗名": "八幡宿駅西口接骨院"},
            {"店舗名": "八幡宿駅西口鍼灸接骨院"},
        ]
        joined, notes = wr.join_shukyaku(rows, shu)
        by = {r["店舗名"]: r["集客数"] for r in joined}
        self.assertEqual(by["八幡宿駅西口接骨院"], "24")   # 本体に入る
        self.assertEqual(by["八幡宿駅西口鍼灸接骨院"], "")  # 併設側は空欄
        self.assertTrue(any(k == "併設按分" for k, _ in notes))

    def test_unmatched_left_blank(self):
        rows = [{"店舗名": "どこにも無い整骨院"}]
        joined, notes = wr.join_shukyaku(rows, {})
        self.assertEqual(joined[0]["集客数"], "")
        self.assertTrue(any(k == "未マッチ" for k, _ in notes))


class TestPositionalNo(unittest.TestCase):
    def test_step14(self):
        self.assertEqual(wr.positional_no(0), 1)
        self.assertEqual(wr.positional_no(1), 15)
        self.assertEqual(wr.positional_no(2), 29)


if __name__ == "__main__":
    unittest.main()

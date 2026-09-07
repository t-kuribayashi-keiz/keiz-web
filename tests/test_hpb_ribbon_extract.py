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

    def test_lone_acupuncture_listing_gets_value(self):
        # Masterにその拠点の鍼灸リスティングしか無い場合は、按分せずその行に値を入れる
        # (本体行がMasterに無いので二重計上の心配がない)。2026年8月号の郡山若葉町・豊四季北口。
        shu = {wr.normalize_store_name("郡山若葉町接骨院"): ("郡山若葉町接骨院", "15")}
        rows = [{"店舗名": "郡山若葉町鍼灸接骨院"}]
        joined, _ = wr.join_shukyaku(rows, shu)
        self.assertEqual(joined[0]["集客数"], "15")

    def test_branch_match_when_suffix_differs(self):
        # 「おかだ〇御殿山」(Master) と 「おかだ〇枚方御殿山」(集客数) を屋号+支店名で繋ぐ
        # (別名表に頼らず、御殿山 ⊂ 枚方御殿山 で一致)
        shu = {wr.normalize_store_name("おかだ鍼灸整骨院 枚方御殿山院"): ("おかだ鍼灸整骨院 枚方御殿山院", "9")}
        rows = [{"店舗名": "おかだ鍼灸整骨院（御殿山）"}]
        joined, notes = wr.join_shukyaku(rows, shu)
        self.assertEqual(joined[0]["集客数"], "9")
        self.assertFalse(any(k == "未マッチ" for k, _ in notes))

    def test_alias_bridges_name_difference(self):
        # 堺市美原区骨盤整体×salon(Master) と 堺市美原区整骨院(集客数) を別名表で繋ぐ
        self.assertEqual(
            wr.normalize_store_name("堺市美原区骨盤整体×salon"),
            wr.normalize_store_name("堺市美原区整骨院"))


class TestBrandProfiles(unittest.TestCase):
    """系列ごとの読み書き先。ここを取り違えると、別ブランドのシートを読む/書く。"""

    @classmethod
    def setUpClass(cls):
        import json, os
        cls.cfg = json.load(open(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "hpb-ribbon-config.json"), encoding="utf-8"))

    def test_chokuei_is_unchanged(self):
        """既定は従来どおり。プロファイル化で直営の挙動を変えていないこと。"""
        prof = wr.profile_config(self.cfg, "chokuei")
        self.assertEqual(prof["master_sheet"], self.cfg["master_sheet"])
        self.assertEqual(prof["shukyaku_sheet"], self.cfg["shukyaku_sheet"])
        self.assertEqual(prof["key_env"], "GCP_KPI_WRITER_KEY")

    def test_smile_good_reads_its_own_sheet_with_its_own_key(self):
        prof = wr.profile_config(self.cfg, "smile-good")
        self.assertNotEqual(prof["shukyaku_sheet"]["id"],
                            self.cfg["shukyaku_sheet"]["id"])
        self.assertEqual(prof["key_env"], "GCP_SMILE_GOOD_KEY")

    def test_smile_good_writes_to_its_own_master(self):
        """専用Masterに書く。直営の145店舗Masterと同じIDになっていたら事故。"""
        prof = wr.profile_config(self.cfg, "smile-good")
        self.assertIsNotNone(prof["master_sheet"])
        self.assertNotEqual(prof["master_sheet"]["id"], self.cfg["master_sheet"]["id"])

    def test_both_masters_share_the_same_column_layout(self):
        """列が食い違うと、同じ抽出CSVから作った行が別の意味の列に入る。"""
        prof = wr.profile_config(self.cfg, "smile-good")
        self.assertEqual(prof["master_sheet"]["columns"],
                         self.cfg["master_sheet"]["columns"])
        self.assertEqual(prof["master_sheet"]["master_ext_columns"],
                         self.cfg["master_sheet"]["master_ext_columns"])

    def test_smile_good_is_limited_to_its_own_brands(self):
        self.assertEqual(wr.profile_config(self.cfg, "smile-good").get("brands"),
                         ["スマイル", "グッド"])

    def test_chokuei_is_not_narrowed(self):
        """直営側は従来どおり絞らない。ここに絞りを入れると過去と挙動が変わる。"""
        self.assertIsNone(wr.profile_config(self.cfg, "chokuei").get("brands"))

    def test_an_unknown_profile_stops(self):
        with self.assertRaises(ValueError):
            wr.profile_config(self.cfg, "存在しない系列")

    def test_smile_good_tab_keywords_do_not_hit_the_hpb_tab_name(self):
        """このシートの月次タブは『◯月HP(速報値)』1枚。HPはHPBに当たってはいけない。"""
        prof = wr.profile_config(self.cfg, "smile-good")
        titles = ["6月HP(速報値)", "報告用", "集計用 （栗林）"]
        kw = wr.month_tab_keywords(prof["shukyaku_sheet"]["tab_keywords"], "2026年06月号")
        self.assertEqual(wr.resolve_tab(titles, kw), "6月HP(速報値)")


class TestSplitByBrand(unittest.TestCase):
    """リボンのZIPは全ブランドまとめて届く。転記先ごとに絞らないと別系列が混ざる。"""

    BRANDS = {
        wr.normalize_store_name("姿勢堂 段原整体院"): "グッド",
        wr.normalize_store_name("すまいる針灸接骨院 六甲道院"): "スマイル",
        wr.normalize_store_name("佐倉ユーカリが丘接骨院"): "直営",
    }

    ROWS = [
        {"店舗名": "姿勢堂　段原鍼灸接骨院"},
        {"店舗名": "すまいる針灸接骨院六甲道院"},
        {"店舗名": "佐倉ユーカリが丘接骨院"},
        {"店舗名": "まだ院マスタに無い整骨院"},
    ]

    def test_only_the_target_brands_are_kept(self):
        kept, dropped, _ = wr.split_by_brand(self.ROWS, ["スマイル", "グッド"], self.BRANDS)
        self.assertEqual([r["店舗名"] for r in kept],
                         ["姿勢堂　段原鍼灸接骨院", "すまいる針灸接骨院六甲道院"])
        self.assertEqual(dropped, [("佐倉ユーカリが丘接骨院", "直営")])

    def test_the_clinic_master_bridges_the_name_difference(self):
        """シートは『段原鍼灸接骨院』、院マスタは『段原整体院』。正規化で繋がること。"""
        kept, _, _ = wr.split_by_brand([self.ROWS[0]], ["グッド"], self.BRANDS)
        self.assertEqual(len(kept), 1)

    def test_an_unknown_store_is_reported_and_not_forced_in(self):
        """ブランドが判定できない店舗を混ぜると、別系列のMasterに紛れ込む。"""
        kept, _, unknown = wr.split_by_brand(self.ROWS, ["スマイル", "グッド"], self.BRANDS)
        self.assertEqual([r["店舗名"] for r in unknown], ["まだ院マスタに無い整骨院"])
        self.assertNotIn("まだ院マスタに無い整骨院", [r["店舗名"] for r in kept])

    def test_without_brands_nothing_is_dropped(self):
        """直営(絞り無し)は従来どおり全行そのまま。不明店も落とさない。"""
        kept, dropped, unknown = wr.split_by_brand(self.ROWS, None, self.BRANDS)
        self.assertEqual(len(kept), 4)
        self.assertEqual(dropped, [])
        self.assertEqual(len(unknown), 1)

    def test_the_real_clinic_master_covers_every_smile_and_good_store(self):
        """実データで、スマイル11院・グッド7院がブランド解決できること。"""
        brand_map = wr.brand_by_store()
        names = ["姿勢堂　段原鍼灸接骨院", "姿勢堂　西条鍼灸接骨院", "姿勢堂　寺家鍼灸接骨院",
                 "姿勢堂　府中鍼灸接骨院", "姿勢堂　祇園鍼灸接骨院", "姿勢堂　宮内鍼灸接骨院",
                 "ひなた鍼灸接骨院",
                 "やまもと鍼灸接骨院 なかもず院", "やまもと鍼灸接骨院 さかいし院",
                 "やまもと鍼灸接骨院 おおとり院", "すまいる鍼灸接骨院 ながよし院",
                 "すまいる鍼灸接骨院 泉が丘院", "金剛まるまる針灸接骨院",
                 "岸和田まるまる針灸接骨院", "すまいる針灸接骨院六甲道院",
                 "すまいる針灸接骨院春木院", "すまいる針灸接骨院甲南山手院",
                 "すまいる針灸接骨院きたのだ院"]
        rows = [{"店舗名": n} for n in names]
        kept, dropped, unknown = wr.split_by_brand(rows, ["スマイル", "グッド"], brand_map)
        self.assertEqual(len(kept), 18, f"未解決={[r['店舗名'] for r in unknown]}")
        self.assertEqual(dropped, [])
        self.assertEqual(unknown, [])


class TestBlockMarker(unittest.TestCase):
    """1タブに HP / HPB / meta / オフライン が縦に並ぶシート(グッド・スマイル月次報告)。"""

    VALUES = [
        ["", "", "", "", "", "", "", ""],
        ["No.", "担当", "エリア", "院名", "HP合計", "6月", "5月"],
        ["1", "グッド", "広島県", "姿勢堂 段原鍼灸接骨院", "30", "10", "9"],
        ["", "", "", "グッド・スマイル合計", "300", "", ""],
        [""],
        ["", "", "", "", "", "", "HPB"],
        ["", "担当", "エリア", "院名", "当月", "前月", "前月比較"],
        ["1", "グッド", "広島県", "姿勢堂 段原鍼灸接骨院", "14", "12", "2"],
        ["2", "スマイル", "堺市エリア", "やまもと鍼灸接骨院 なかもず院", "13", "5", "8"],
        ["", "", "", "グッド・スマイル合計", "108", "83", "25"],
        ["", "", "", "グッド1院当たり", "10.7", "", ""],
    ]

    def marker_map(self, values=None):
        return wr.build_shukyaku_map(
            values if values is not None else self.VALUES,
            block_marker="HPB", stop_contains=("合計", "平均", "店舗数", "1院当たり"))

    def test_the_hpb_block_is_read_not_the_hp_block_above_it(self):
        """見出しだけ探すと先頭のHPブロックに当たる。数字が黙って入れ替わる一番危ない罠。"""
        m = self.marker_map()
        self.assertEqual(m[wr.normalize_store_name("姿勢堂 段原鍼灸接骨院")][1], "14")

    def test_without_the_marker_the_blocks_are_silently_merged(self):
        """印なしだと何が起きるかを記録しておく。

        先頭のHPブロックの見出しから読み始め、打ち切りラベル(『グッド・スマイル合計』)も
        行頭一致では止まらないので、下のHPBブロックまで走って**同じ院名を上書きする**。
        エラーは出ない。だから印が要る。
        """
        m = wr.build_shukyaku_map(self.VALUES)
        danbara = m[wr.normalize_store_name("姿勢堂 段原鍼灸接骨院")][1]
        self.assertIn(danbara, ("10", "14"))
        self.assertIn(wr.normalize_store_name("グッド・スマイル合計"), m,
                      "合計行まで店舗として取り込まれてしまう")

    def test_totals_in_the_middle_of_the_label_stop_the_read(self):
        """『グッド・スマイル合計』は行頭一致では止まらない。部分一致で打ち切る。"""
        m = self.marker_map()
        self.assertNotIn(wr.normalize_store_name("グッド・スマイル合計"), m)
        self.assertNotIn(wr.normalize_store_name("グッド1院当たり"), m)
        self.assertEqual(len(m), 2)

    def test_two_blocks_with_the_same_marker_stop_instead_of_guessing(self):
        """同じ印のブロックが2つあるとき、片方を選ぶと外れたほうの数字が消える。"""
        doubled = self.VALUES + [[""], ["", "", "", "", "", "", "HPB"],
                                 ["", "担当", "エリア", "院名", "当月", "前月"],
                                 ["1", "グッド", "広島県", "姿勢堂 段原鍼灸接骨院", "10", "10"]]
        with self.assertRaises(ValueError):
            self.marker_map(doubled)

    def test_a_missing_marker_stops(self):
        with self.assertRaises(ValueError):
            wr.build_shukyaku_map(self.VALUES, block_marker="EPARK")

    def test_the_chokuei_sheet_still_reads_without_a_marker(self):
        values = [
            ["エリア", "", "…院名", "当月", "前月"],
            ["関東", "", "佐倉ユーカリが丘接骨院", "8", "9"],
            ["", "", "合計", "2607", ""],
        ]
        m = wr.build_shukyaku_map(values)
        self.assertEqual(m[wr.normalize_store_name("佐倉ユーカリが丘接骨院")][1], "8")


class TestPositionalNo(unittest.TestCase):
    def test_step14(self):
        self.assertEqual(wr.positional_no(0), 1)
        self.assertEqual(wr.positional_no(1), 15)
        self.assertEqual(wr.positional_no(2), 29)


class TestExtendedColumns(unittest.TestCase):
    def test_col_letter(self):
        self.assertEqual(wr.col_letter(1), "A")
        self.assertEqual(wr.col_letter(19), "S")
        self.assertEqual(wr.col_letter(20), "T")   # 拡張列の先頭
        self.assertEqual(wr.col_letter(47), "AU")  # 19 + 28 列目

    def test_extended_cols_match_config(self):
        import json, os
        cfg = json.load(open(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "hpb-ribbon-config.json"), encoding="utf-8"))
        self.assertEqual(ext.EXTENDED_COLS, cfg["master_sheet"]["master_ext_columns"])
        self.assertEqual(len(ext.EXTENDED_COLS), 28)

    def test_p3_dash_does_not_grab_competitor(self):
        # 自サロン行の設備数などが「-」でも、比較サロン一覧の先頭店(ミモザ 942)を拾わない
        p3 = ("自サロンの掲載状況\nサロン名\n設備数\n口コミ数\n口コミ評点\nブログ数\nクーポン数\n最寄駅\n"
              "本八幡南口鍼灸接骨院\n-\n0\n-\n0\n4\n本八幡\n"
              "自サロンと比較・検討されているサロン一覧\nサロン名\n設備数\n口コミ数\n口コミ評点\nブログ数\nクーポン数\n最寄駅\n"
              "ミモザ(mimosa)\n1\n942\n4.94\n26\n44\n本八幡\n")
        r = ext._extract_extended([p3], [], [], "", None, -2)
        self.assertEqual(r.get("口コミ数"), "0")     # 942 ではなく自店の 0
        self.assertEqual(r.get("クーポン数"), "4")
        self.assertIsNone(r.get("口コミ評点"))        # 「-」→ None


if __name__ == "__main__":
    unittest.main()

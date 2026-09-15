"""relax_shukyaku_pull.py の純粋関数(clean_number/month_column/parse_blocks)の回帰テスト。

APIは叩かない。フィクスチャは2026-09-07に実シート(『集客数(新ルール6月〜)』タブ)を
sheets-smoke-testで読んだ実物の行の形をそのまま使う。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import relax_shukyaku_pull as pull  # noqa: E402


HEADER_ROW = ["店舗名", "店舗名", "媒体", "25年最高", "25年平均",
              "2024/1", "2024/2", "2024/3", "2024/4", "2024/5", "2024/6", "2024/7",
              "2024/8", "2024/9", "2024/10", "2024/11", "2024/12/01",
              "2025/0101", "2025/02", "2025/03", "2025/04", "2025/05", "2025/06",
              "2025/07", "2025/08", "2025/09", "2025/10", "2025/11", "2025/12",
              "2026/01", "2026/02", "2026/03", "2026/04", "2026/05", "2026/06",
              "2026/07", "2026/08", "前月比"]

# 実物の西新宿店ブロック(2026-09-07にsheets-smoke-testで読んだ形)。
# 列は HEADER_ROW と対応。2026/08 は index 36。
NISHISHINJUKU_BLOCK = [
    ["西新宿店", "西新宿店120", "新患合計", "154", "107",
     "79", "67", "88", "101", "110", "120", "92", "94", "94", "81", "59",
     "76", "90", "86", "93", "91", "108", "126", "110", "154", "81", "122",
     "109", "114", "79", "73", "69", "78", "91", "100", "107", "88", "-19"],
    ["", "", "HPB", "1020", "706",
     "349", "336", "394", "431", "497", "718", "653", "754", "650", "709", "564",
     "623", "455", "420", "441", "602", "619", "762", "757", "1020", "688", "968",
     "856", "879", "716", "695", "560", "487", "529", "486", "543", "532", "-11"],
]

MEDIA_ONLY_ROW_WITH_SLASH_VALUE = [
    ["幡ヶ谷店", "幡ヶ谷店60", "新患合計", "80", "55",
     "42", "44", "47", "55", "52", "58", "56", "57", "39", "61", "44",
     "43", "25", "26", "33", "58", "56", "69", "80", "69", "46", "75",
     "76", "50", "53", "33", "40", "53", "64", "42", "47", "43", "-4"],
    # 2025/06(index22)が「22/27」の実物のセル(修正前後の併記と思われる)。
    ["", "", "HPB", "45", "24",
     "14", "14", "16", "22", "14", "33", "23", "23", "22/27", "22", "14",
     "24", "9", "9", "12", "29", "19", "29", "41", "28", "14", "35",
     "45", "23", "22", "14", "19", "27", "34", "18", "22", "18", "-4"],
]


class TestCleanNumber(unittest.TestCase):
    def test_plain_int(self):
        self.assertEqual(pull.clean_number("532"), 532)

    def test_trailing_space_is_stripped(self):
        self.assertEqual(pull.clean_number("107 "), 107)

    def test_dash_is_no_data(self):
        self.assertIsNone(pull.clean_number("-"))

    def test_blank_is_no_data(self):
        self.assertIsNone(pull.clean_number(""))
        self.assertIsNone(pull.clean_number(None))

    def test_slash_value_is_unreadable(self):
        """『22/27』(修正前後の併記と思われる実物のセル)は判読不能としてNoneにする。"""
        self.assertIsNone(pull.clean_number("22/27"))

    def test_formula_error_is_unreadable(self):
        self.assertIsNone(pull.clean_number("#VALUE!"))

    def test_comma_thousands_separator(self):
        self.assertEqual(pull.clean_number("1,728"), 1728)


class TestMonthColumn(unittest.TestCase):
    def test_resolves_2026_08(self):
        self.assertEqual(pull.month_column(HEADER_ROW, "2026年08月号"), 36)

    def test_missing_month_raises(self):
        with self.assertRaises(ValueError):
            pull.month_column(HEADER_ROW, "2027年01月号")


class TestParseBlocks(unittest.TestCase):
    def test_hpb_value_for_2026_08(self):
        col = pull.month_column(HEADER_ROW, "2026年08月号")
        blocks = pull.parse_blocks(NISHISHINJUKU_BLOCK, col)
        self.assertEqual(blocks["西新宿店"]["HPB"], 532)
        self.assertEqual(blocks["西新宿店"]["新患合計"], 88)

    def test_unreadable_cell_becomes_none_not_zero(self):
        """『22/27』を0と誤読しない(HPB店舗の実新患数が消える事故を防ぐ)。

        列は直接指定する(2024年の見出しは『2024/9』のようにゼロ埋め無しで、
        month_columnのゼロ埋め前提と食い違う実物の癖があるため、ここでは
        month_column自体は検証しない。対象月2026/08はゼロ埋りで一致することを
        test_resolves_2026_08で別に固定済み)。
        """
        col = HEADER_ROW.index("2024/9")
        blocks = pull.parse_blocks(MEDIA_ONLY_ROW_WITH_SLASH_VALUE, col)
        self.assertIsNone(blocks["幡ヶ谷店"]["HPB"])

    def test_rows_without_a_leading_store_name_join_the_current_block(self):
        col = pull.month_column(HEADER_ROW, "2026年08月号")
        blocks = pull.parse_blocks(NISHISHINJUKU_BLOCK, col)
        self.assertEqual(set(blocks.keys()), {"西新宿店"})
        self.assertEqual(set(blocks["西新宿店"].keys()), {"新患合計", "HPB"})


if __name__ == "__main__":
    unittest.main()

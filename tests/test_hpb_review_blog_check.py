#!/usr/bin/env python3
"""hpb_review_blog_check.pyのうち、ネットワーク/認証を使わずに検証できる部分のテスト。

2026-09-11、書き込み先を新スプレッドシートに切り替え、書き込み対象列をG〜IからB〜Fに
変更した際に追加。ensure_tab_existsのクリア範囲(B:F)と、apply_to_sheetの
「E列は前月タブのC列からコピー、無ければスクレイピング値にフォールバック」という
分岐を固定しておく(ここを間違えると、前月タブが無い月だけE列が静かに空欄になる)。
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import hpb_review_blog_check as m  # noqa: E402


class TestEnsureTabExists(unittest.TestCase):
    def test_existing_tab_returned_as_is(self):
        spreadsheet = MagicMock()
        target_ws = MagicMock()
        spreadsheet.worksheet.side_effect = lambda name: (
            target_ws if name == "2609月分" else (_ for _ in ()).throw(Exception("not found"))
        )
        result = m.ensure_tab_exists(spreadsheet, "2609月分", 2026, 9)
        self.assertIs(result, target_ws)

    def test_missing_tab_duplicates_previous_month_and_clears_b_to_f(self):
        spreadsheet = MagicMock()
        prev_ws = MagicMock()
        prev_ws.index = 3
        new_ws = MagicMock()
        prev_ws.duplicate.return_value = new_ws

        def worksheet_side_effect(name):
            if name == "2608月分":
                return prev_ws
            raise Exception("not found")

        spreadsheet.worksheet.side_effect = worksheet_side_effect
        result = m.ensure_tab_exists(spreadsheet, "2609月分", 2026, 9)

        self.assertIs(result, new_ws)
        prev_ws.duplicate.assert_called_once_with(insert_sheet_index=4, new_sheet_name="2609月分")
        new_ws.batch_clear.assert_called_once_with(["B3:F36", "B40:F170"])

    def test_year_rollover(self):
        spreadsheet = MagicMock()
        prev_ws = MagicMock()
        prev_ws.index = 5
        new_ws = MagicMock()
        prev_ws.duplicate.return_value = new_ws

        def worksheet_side_effect(name):
            if name == "2512月分":
                return prev_ws
            raise Exception("not found")

        spreadsheet.worksheet.side_effect = worksheet_side_effect
        result = m.ensure_tab_exists(spreadsheet, "2601月分", 2026, 1)
        self.assertIs(result, new_ws)


class TestApplyToSheetColumnMapping(unittest.TestCase):
    """apply_to_sheetはGCP_KPI_WRITER_KEY/gspreadに依存するbuild_spreadsheet()を呼ぶため、
    そこだけモンキーパッチして、以降の列マッピング・フォールバック分岐を検証する。"""

    def _make_worksheet(self, rows):
        ws = MagicMock()
        ws.get_all_values.return_value = rows
        return ws

    def test_writes_b_to_f_and_copies_prev_c_from_previous_tab(self):
        # 対象タブ(2609月分): A列に院名のみ入っている状態(新規タブ作成直後を想定)
        target_ws = self._make_worksheet([["院名"], ["わかば整骨院"], ["幕張南口整骨院"]])
        # 前月タブ(2608月分): C列(前月時点の「今月の口コミ投稿総数」)に値が入っている
        prev_ws = self._make_worksheet([["院名"], ["わかば整骨院"], ["幕張南口整骨院"]])
        prev_ws.get.return_value = [["C見出し"], ["14"], ["9"]]

        spreadsheet = MagicMock()

        def worksheet_side_effect(name):
            if name == "2609月分":
                return target_ws
            if name == "2608月分":
                return prev_ws
            raise Exception("not found")

        spreadsheet.worksheet.side_effect = worksheet_side_effect
        m.build_spreadsheet = lambda: spreadsheet  # type: ignore[assignment]

        results = [
            {
                "name": "わかば整骨院",
                "store_id": "H000475060",
                "review_total": 3,
                "review_5star": 2,
                "blog_total_raw": 5,
                "blog_photo_count": 4,
                "prev_review_total_scraped": 999,  # 前月タブから拾えるはずなので使われない
                "prev_review_reply": 6,
                "error": "",
            },
            {
                "name": "幕張南口整骨院",
                "store_id": "H000475110",
                "review_total": 1,
                "review_5star": 1,
                "blog_total_raw": 0,
                "blog_photo_count": 0,
                "prev_review_total_scraped": 888,
                "prev_review_reply": 2,
                "error": "",
            },
        ]

        m.apply_to_sheet(results, 2026, 9, tab_override="2609月分")

        target_ws.batch_update.assert_called_once()
        (updates,), _ = target_ws.batch_update.call_args
        by_range = {u["range"]: u["values"][0] for u in updates}
        # B:F = ブログ数, 口コミ総数, ★5数, 前月口コミ総数(前月タブC列から), 前月返信数(スクレイピング値)
        self.assertEqual(by_range["B2:F2"], [4, 3, 2, "14", 6])
        self.assertEqual(by_range["B3:F3"], [0, 1, 1, "9", 2])

    def test_falls_back_to_scraped_value_when_previous_tab_missing(self):
        target_ws = self._make_worksheet([["院名"], ["わかば整骨院"]])
        spreadsheet = MagicMock()

        def worksheet_side_effect(name):
            if name == "2609月分":
                return target_ws
            raise Exception("not found")  # 前月タブ(2608月分)が存在しない

        spreadsheet.worksheet.side_effect = worksheet_side_effect
        m.build_spreadsheet = lambda: spreadsheet  # type: ignore[assignment]

        results = [
            {
                "name": "わかば整骨院",
                "store_id": "H000475060",
                "review_total": 3,
                "review_5star": 2,
                "blog_total_raw": 5,
                "blog_photo_count": 4,
                "prev_review_total_scraped": 999,
                "prev_review_reply": 6,
                "error": "",
            }
        ]

        m.apply_to_sheet(results, 2026, 9, tab_override="2609月分")

        (updates,), _ = target_ws.batch_update.call_args
        self.assertEqual(updates[0]["range"], "B2:F2")
        # 前月タブが無いので、E列はスクレイピング値(999)にフォールバックする
        self.assertEqual(updates[0]["values"][0], [4, 3, 2, 999, 6])


if __name__ == "__main__":
    unittest.main()

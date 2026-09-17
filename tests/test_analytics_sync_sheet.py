"""analytics_sync_sheet.py のマージロジック。APIは叩かない。

一番大事なのは、同じ(年月・ブランド・店舗・ソース・チャネル・指標)の再送で
行が増えないこと(再実行のたびにログが太っていくと、長形式ログの意味がなくなる)。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import analytics_sync_sheet as sync  # noqa: E402


class TestMerge(unittest.TestCase):
    def test_a_rerun_of_the_same_key_replaces_not_duplicates(self):
        existing = [["2026年08月号", "スマイル", "浦和店", "GSC", "SEO", "クリック", "40",
                     "2026-09-01 10:00:00"]]
        new_rows = [{"年月": "2026年08月号", "店舗": "浦和店", "ソース": "GSC",
                     "チャネル": "SEO", "指標": "クリック", "値": "55"}]
        merged = sync.merge(existing, new_rows, "スマイル", "2026-09-17 12:00:00")
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0][6], "55")  # 値が更新されている
        self.assertEqual(merged[0][7], "2026-09-17 12:00:00")  # 取得日時も更新

    def test_unrelated_existing_rows_are_kept(self):
        """別の月・別のブランドの行は、今回のバッチに含まれなくても消えない。"""
        existing = [["2026年07月号", "グッド", "宮内整体院", "GA4", "Direct", "sessions", "10",
                     "2026-08-01 09:00:00"]]
        new_rows = [{"年月": "2026年08月号", "店舗": "浦和店", "ソース": "GSC",
                     "チャネル": "SEO", "指標": "クリック", "値": "1"}]
        merged = sync.merge(existing, new_rows, "スマイル", "2026-09-17 12:00:00")
        self.assertEqual(len(merged), 2)

    def test_two_stores_in_the_same_batch_both_land(self):
        new_rows = [
            {"年月": "2026年08月号", "店舗": "浦和店", "ソース": "GSC",
             "チャネル": "SEO", "指標": "クリック", "値": "1"},
            {"年月": "2026年08月号", "店舗": "大宮店", "ソース": "GSC",
             "チャネル": "SEO", "指標": "クリック", "値": "2"},
        ]
        merged = sync.merge([], new_rows, "スマイル", "2026-09-17 12:00:00")
        self.assertEqual({row[2] for row in merged}, {"浦和店", "大宮店"})

    def test_rows_are_sorted_for_a_stable_diff(self):
        new_rows = [
            {"年月": "2026年08月号", "店舗": "浦和店", "ソース": "GSC",
             "チャネル": "SEO", "指標": "表示回数", "値": "1"},
            {"年月": "2026年08月号", "店舗": "浦和店", "ソース": "GSC",
             "チャネル": "SEO", "指標": "クリック", "値": "1"},
        ]
        merged = sync.merge([], new_rows, "スマイル", "2026-09-17 12:00:00")
        self.assertEqual([row[5] for row in merged], ["クリック", "表示回数"])


class TestReadRowsTsv(unittest.TestCase):
    def test_parses_the_header_and_rows(self):
        path = Path(__file__).resolve().parent / "_tmp_analytics_rows.tsv"
        path.write_text(
            "年月\t店舗\tソース\tチャネル\t指標\t値\n"
            "2026年08月号\t浦和店\tGSC\tSEO\tクリック\t40\n",
            encoding="utf-8",
        )
        try:
            rows = sync.read_rows_tsv(str(path))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["店舗"], "浦和店")
            self.assertEqual(rows[0]["値"], "40")
        finally:
            path.unlink()

    def test_an_empty_file_yields_no_rows(self):
        path = Path(__file__).resolve().parent / "_tmp_analytics_rows_empty.tsv"
        path.write_text("", encoding="utf-8")
        try:
            self.assertEqual(sync.read_rows_tsv(str(path)), [])
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()

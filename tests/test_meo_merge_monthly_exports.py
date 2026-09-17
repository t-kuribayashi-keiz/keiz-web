"""MEOチェキCSVのstore_id変換。APIも実ファイルの対応表も使わない範囲だけを見る。

一番大事なのは、対応表に無い案件名を**捨てずに**、案件名のまま出力に残すこと
(黙って行が減ると、取り込み漏れなのか元々存在しない店舗なのか区別できなくなる)。
"""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import meo_merge_monthly_exports as merge  # noqa: E402


class TestLoadStoreIdMap(unittest.TestCase):
    def test_a_missing_file_yields_an_empty_map(self):
        self.assertEqual(merge.load_store_id_map(Path("/does/not/exist.json")), {})

    def test_the_matched_section_is_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.json"
            path.write_text(
                '{"matched": {"すまいる針灸接骨院 六甲道院": "smile-rokkomichi"}, '
                '"unresolved": {}}',
                encoding="utf-8",
            )
            result = merge.load_store_id_map(path)
            self.assertEqual(result, {"すまいる針灸接骨院 六甲道院": "smile-rokkomichi"})


class TestMainMerge(unittest.TestCase):
    def _run(self, rows, store_id_map=None, monkeypatch_map=True):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            csv_path = tmp_path / "2026-08.csv"
            with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["日付", "案件名", "検索キーワード", "順位", "検索住所"])
                writer.writeheader()
                writer.writerows(rows)

            out_dir = tmp_path / "out"
            original_load = merge.load_store_id_map
            if monkeypatch_map:
                merge.load_store_id_map = lambda *_args, **_kwargs: (store_id_map or {})
            try:
                sys.argv = ["meo_merge_monthly_exports.py", str(csv_path), "--out-dir", str(out_dir)]
                merge.main()
            finally:
                merge.load_store_id_map = original_load

            with (out_dir / "rank_checks_combined.csv").open(encoding="utf-8-sig") as f:
                return list(csv.DictReader(f))

    def test_a_mapped_store_name_becomes_the_clinic_id(self):
        rows = self._run(
            [{"日付": "2026-8-1", "案件名": "すまいる針灸接骨院 六甲道院",
              "検索キーワード": "整骨院 六甲道", "順位": "3", "検索住所": ""}],
            store_id_map={"すまいる針灸接骨院 六甲道院": "smile-rokkomichi"},
        )
        self.assertEqual(rows[0]["store_id"], "smile-rokkomichi")

    def test_an_unmapped_store_name_is_kept_as_is_not_dropped(self):
        rows = self._run(
            [{"日付": "2026-8-1", "案件名": "宇都宮オリオン通り整骨院",
              "検索キーワード": "整骨院 宇都宮", "順位": "5", "検索住所": ""}],
            store_id_map={},
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["store_id"], "宇都宮オリオン通り整骨院")

    def test_out_of_area_rank_becomes_not_found(self):
        rows = self._run(
            [{"日付": "2026-8-1", "案件名": "店A", "検索キーワード": "kw", "順位": "圏外", "検索住所": ""}],
            store_id_map={},
        )
        self.assertEqual(rows[0]["found"], "False")
        self.assertEqual(rows[0]["rank_absolute"], "")


if __name__ == "__main__":
    unittest.main()

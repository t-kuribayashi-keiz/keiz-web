#!/usr/bin/env python3
"""MEOチェキの「順位データ全案件ダウンロード」CSVを、BigQuery(meo_internal)の
rank_checks / keywords_master テーブル向けのNDJSONに変換する。

背景: functions/meo-internal/CLAUDE.md参照。2026-09-17にMEOチェキの管理画面
(app.ranktoolap.com)から取得した実データ(199店舗・1,856キーワード・31,454行)を
無料スクレイパー([scripts/meo_rank_check.py](meo_rank_check.py))の精度検証・
キーワード設定の初期投入に使う。

store_idはまだdata/clinics.jsonのidと突き合わせていない(MEOチェキの「案件名」を
そのままstore_idとして使っている)。突き合わせは別途対応。

使い方:
    python scripts/meo_import_rank_export.py <MEOチェキCSVパス> --out-dir .scratch/meo_export
    bq load --source_format=NEWLINE_DELIMITED_JSON meo-automation-490007:meo_internal.keywords_master .scratch/meo_export/keywords_master.ndjson
    bq load --source_format=NEWLINE_DELIMITED_JSON meo-automation-490007:meo_internal.rank_checks .scratch/meo_export/rank_checks.ndjson
"""
import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path


def convert(csv_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    seen_keywords = set()
    keywords_out = []
    rank_checks_out = []

    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            store_id = row["案件名"]
            keyword = row["検索キーワード"]
            rank_raw = row["順位"]
            check_date = row["日付"].replace("-", "")
            # 日付が '2026-9-1' のようにゼロ埋めされていないため、日付型に変換してISO表記にする
            y, m, d = row["日付"].split("-")
            check_date_iso = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

            key = (store_id, keyword)
            if key not in seen_keywords:
                seen_keywords.add(key)
                keywords_out.append(
                    {
                        "store_id": store_id,
                        "brand": None,
                        "keyword": keyword,
                        "active": True,
                        "added_date": date.today().isoformat(),
                    }
                )

            found = rank_raw != "圏外"
            rank_absolute = int(rank_raw) if found and rank_raw.isdigit() else None
            rank_checks_out.append(
                {
                    "check_date": check_date_iso,
                    "store_id": store_id,
                    "brand": None,
                    "keyword": keyword,
                    "location_coordinate": row.get("検索住所"),
                    "rank_absolute": rank_absolute,
                    "found": found,
                    "place_id": None,
                    "matched_name": None,
                    "total_listings_seen": None,
                    "source": "meochecki_csv_import_20260917",
                }
            )

    kw_path = out_dir / "keywords_master.ndjson"
    rc_path = out_dir / "rank_checks.ndjson"
    with kw_path.open("w", encoding="utf-8") as f:
        for row in keywords_out:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with rc_path.open("w", encoding="utf-8") as f:
        for row in rank_checks_out:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"keywords_master: {len(keywords_out)} rows -> {kw_path}")
    print(f"rank_checks: {len(rank_checks_out)} rows -> {rc_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path(".scratch/meo_export"))
    args = parser.parse_args()
    convert(args.csv_path, args.out_dir)
    sys.exit(0)

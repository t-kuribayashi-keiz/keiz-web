#!/usr/bin/env python3
"""複数月分のMEOチェキ「順位データ全案件ダウンロード」CSVを1本に統合する。

背景: functions/meo-internal/CLAUDE.md参照。BigQueryのサンドボックスモードは
パーティションに60日の自動有効期限があり、1〜8月分のデータが投入直後に消える
ことが判明したため、Google Sheetsへの保存に切り替える(2026-09-17)。

使い方:
    python scripts/meo_merge_monthly_exports.py <CSVファイル...> --out-dir .scratch/meo_export

出力:
    - rank_checks_combined.csv: 全月をまとめた順位ログ(日付,店舗,キーワード,順位,found)
    - keywords_master_combined.csv: 店舗×キーワードの一覧(初出日付・アクティブ)
"""
import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_paths", nargs="+", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path(".scratch/meo_export"))
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rank_rows = []
    keyword_first_seen = {}

    for csv_path in args.csv_paths:
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                store_id = row["案件名"]
                keyword = row["検索キーワード"]
                rank_raw = row["順位"]
                y, m, d = row["日付"].split("-")
                check_date = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
                found = rank_raw != "圏外"
                rank_absolute = int(rank_raw) if found and rank_raw.isdigit() else ""

                rank_rows.append(
                    {
                        "check_date": check_date,
                        "store_id": store_id,
                        "keyword": keyword,
                        "rank_absolute": rank_absolute,
                        "found": found,
                        "location_text": row.get("検索住所", ""),
                        "source": csv_path.name,
                    }
                )

                key = (store_id, keyword)
                if key not in keyword_first_seen or check_date < keyword_first_seen[key]:
                    keyword_first_seen[key] = check_date

    rank_rows.sort(key=lambda r: (r["check_date"], r["store_id"], r["keyword"]))

    rank_path = args.out_dir / "rank_checks_combined.csv"
    with rank_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["check_date", "store_id", "keyword", "rank_absolute", "found", "location_text", "source"],
        )
        writer.writeheader()
        writer.writerows(rank_rows)

    kw_path = args.out_dir / "keywords_master_combined.csv"
    with kw_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["store_id", "keyword", "first_seen_date", "active"])
        for (store_id, keyword), first_seen in sorted(keyword_first_seen.items()):
            writer.writerow([store_id, keyword, first_seen, True])

    print(f"rank_checks_combined: {len(rank_rows)} rows -> {rank_path}")
    print(f"keywords_master_combined: {len(keyword_first_seen)} rows -> {kw_path}")


if __name__ == "__main__":
    main()

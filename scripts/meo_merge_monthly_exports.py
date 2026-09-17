#!/usr/bin/env python3
"""複数月分のMEOチェキ「順位データ全案件ダウンロード」CSVを1本に統合する。

背景: functions/meo-internal/CLAUDE.md参照。BigQueryのサンドボックスモードは
パーティションに60日の自動有効期限があり、1〜8月分のデータが投入直後に消える
ことが判明したため、Google Sheetsへの保存に切り替える(2026-09-17)。

**store_idの変換(2026-09-17追加)**: MEOチェキの「案件名」は店舗の表示名であって
data/clinics.jsonのidではない。data/meo-store-id-map.json(scripts/store_matcher.pyで
事前に突き合わせ済み)を使って、可能な行はidに変換する。**対応表に無い案件名の行は
捨てずに残す**(store_idを案件名のまま出力し、末尾に警告を出す)——合計行数が
黙って減ると、取り込み漏れなのか元々存在しない店舗なのか区別できなくなるため。

使い方:
    python scripts/meo_merge_monthly_exports.py <CSVファイル...> --out-dir .scratch/meo_export

出力:
    - rank_checks_combined.csv: 全月をまとめた順位ログ(日付,店舗,キーワード,順位,found)
    - keywords_master_combined.csv: 店舗×キーワードの一覧(初出日付・アクティブ)
"""
import argparse
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STORE_ID_MAP_PATH = REPO / "data" / "meo-store-id-map.json"


def load_store_id_map(path: Path = STORE_ID_MAP_PATH) -> dict[str, str]:
    """MEOチェキの案件名 → data/clinics.json の id。無ければ空のマップを返す
    (対応表がまだ無い環境でもこのスクリプト自体は動く。ただしstore_idは案件名のまま)。"""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("matched", {})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_paths", nargs="+", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path(".scratch/meo_export"))
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    store_id_map = load_store_id_map()
    unmapped_names: set[str] = set()

    rank_rows = []
    keyword_first_seen = {}

    for csv_path in args.csv_paths:
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_name = row["案件名"]
                store_id = store_id_map.get(raw_name)
                if store_id is None:
                    store_id = raw_name
                    unmapped_names.add(raw_name)
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
    if unmapped_names:
        print(
            f"WARNING: store_id未変換のまま出力した案件名が{len(unmapped_names)}件あります"
            " (data/meo-store-id-map.jsonに無い): ",
            file=sys.stderr,
        )
        for name in sorted(unmapped_names):
            print(f"  {name}", file=sys.stderr)


if __name__ == "__main__":
    main()

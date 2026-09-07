#!/usr/bin/env python3
"""GA4 Data API と Search Console API から対象月の実データを取得する。

analytics_discover.py は「何が見えるか」を確認するだけで指標は取らない。こちらは
実際に GA4 の runReport / Search Console の searchAnalytics.query を叩き、
analytics_rows.py の変換関数に渡して統合ログの行にする。

**読み取り専用。** GA4にもSearch Consoleにも書き込まない。

    python3 scripts/analytics_pull.py --brand リラックス --key-env GCP_RELAX_KEY \
        --month 2026年08月号 --out /tmp/relax-2026-08.tsv
"""

from __future__ import annotations

import argparse
import calendar
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ga4_properties as ga4  # noqa: E402
import analytics_rows as rows_mod  # noqa: E402
from analytics_discover import (  # noqa: E402
    credentials, build, ga4_account_summaries, gsc_sites,
)


def month_range(month_label: str) -> tuple[str, str]:
    """『2026年08月号』『2026年08月』→ ('2026-08-01', '2026-08-31')。月末は暦で決める。"""
    m = re.search(r"(\d{4})年(\d{1,2})月", month_label)
    if not m:
        raise ValueError(f"年月号の形式が読めません: {month_label!r}")
    year, month = int(m.group(1)), int(m.group(2))
    last_day = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"


def ga4_property_ids(summaries: list[dict]) -> dict[str, str]:
    """プロパティのdisplayName → リソース名(properties/123456)。"""
    found = {}
    for summary in summaries:
        for prop in summary.get("propertySummaries", []):
            if prop.get("displayName") and prop.get("property"):
                found[prop["displayName"]] = prop["property"]
    return found


def pull_ga4(creds, brand: str, month_label: str) -> list[dict]:
    start, end = month_range(month_label)
    data_api = build("analyticsdata", "v1beta", creds)
    summaries = ga4_account_summaries(creds)
    names = [p["displayName"] for s in summaries for p in s.get("propertySummaries", [])
             if p.get("displayName")]
    id_map = ga4_property_ids(summaries)

    result = ga4.resolve(names, brand)
    if result["unmatched"] or result["duplicated"]:
        print(f"[GA4] 名寄せ未解決あり: unmatched={len(result['unmatched'])} "
              f"duplicated={len(result['duplicated'])}", file=sys.stderr)
    if result["missing"]:
        print(f"[GA4] プロパティが見つからない店舗: {result['missing']}", file=sys.stderr)

    all_rows: list[dict] = []
    for store, display_name in sorted(result["matched"].items()):
        property_id = id_map.get(display_name)
        if not property_id:
            print(f"  [プロパティID不明] {store} ({display_name!r})", file=sys.stderr)
            continue
        response = data_api.properties().runReport(
            property=property_id,
            body={
                "dateRanges": [{"startDate": start, "endDate": end}],
                "dimensions": [{"name": "sessionDefaultChannelGroup"}],
                "metrics": [{"name": "sessions"}, {"name": "conversions"}],
            },
        ).execute()
        all_rows.extend(rows_mod.ga4_rows(month_label, store, response))
    return all_rows


def pull_gsc(creds, brand: str, month_label: str) -> list[dict]:
    start, end = month_range(month_label)
    search_console = build("searchconsole", "v1", creds)
    sites = gsc_sites(creds)

    clinics = json.loads(rows_mod.CLINICS_PATH.read_text(encoding="utf-8"))["clinics"]
    by_url = {}
    for clinic in clinics:
        if clinic.get("brand") != brand:
            continue
        website = (clinic.get("website") or "").rstrip("/")
        if website:
            by_url[website] = clinic["name"]

    domain_sites = [s for s in sites if s.get("siteUrl", "").startswith("sc-domain:")]
    if domain_sites:
        print(f"[GSC] ドメインプロパティ({len(domain_sites)}件)は未対応。"
              "URLプレフィックス方式のみ実装済み。", file=sys.stderr)

    all_rows: list[dict] = []
    matched_urls = set()
    for site in sites:
        url = site.get("siteUrl", "").rstrip("/")
        store = by_url.get(url)
        if not store:
            continue
        matched_urls.add(url)
        response = search_console.searchanalytics().query(
            siteUrl=site["siteUrl"],
            body={"startDate": start, "endDate": end, "dimensions": ["page"],
                  "rowLimit": 1000},
        ).execute()
        path = urlparse(url).path.strip("/")
        all_rows.extend(rows_mod.gsc_rows(month_label, response, {path: store}))

    missing = sorted(set(by_url.values()) - {by_url[u] for u in matched_urls})
    if missing:
        print(f"[GSC] サイトが見つからない店舗: {missing}", file=sys.stderr)
    return all_rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brand", required=True, help="院マスタのブランド名(例: リラックス)")
    parser.add_argument("--key-env", default="GCP_RELAX_KEY")
    parser.add_argument("--month", required=True, help="対象年月号(例 2026年08月号)")
    parser.add_argument("--skip-ga4", action="store_true")
    parser.add_argument("--skip-gsc", action="store_true")
    parser.add_argument("--out", default="", help="TSVの出力先。省略時は標準出力")
    args = parser.parse_args(argv)

    creds = credentials(args.key_env)
    rows: list[dict] = []

    if not args.skip_ga4:
        try:
            rows.extend(pull_ga4(creds, args.brand, args.month))
        except Exception as error:  # noqa: BLE001
            print(f"GA4の取得に失敗しました: {error}", file=sys.stderr)
            return 1

    if not args.skip_gsc:
        try:
            rows.extend(pull_gsc(creds, args.brand, args.month))
        except Exception as error:  # noqa: BLE001
            print(f"Search Consoleの取得に失敗しました: {error}", file=sys.stderr)
            return 1

    text = rows_mod.to_tsv(rows)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"書き出し: {args.out}({len(rows)}行)", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

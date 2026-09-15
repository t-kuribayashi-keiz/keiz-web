#!/usr/bin/env python3
"""GA4 Data APIの properties.getMetadata で、実際に使える指標名(apiName)を確認する。

指標のAPI名を記憶や検索結果から推測しない — 同じブランドのプロパティ1件に対して
実際にメタデータを取得し、キーワードに一致する apiName/uiName/description をそのまま
表示する。「新規ユーザー数」「コンバージョンに至ったユーザー数」のような、UI上の呼び方と
API名が一致しない指標を安全に選ぶための道具。

    python3 scripts/ga4_metrics_probe.py --brand リラックス --grep user,conversion,key

**読み取り専用。** メタデータの取得のみ。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ga4_properties as ga4  # noqa: E402
from analytics_discover import credentials, build, ga4_account_summaries  # noqa: E402
from analytics_pull import ga4_property_ids  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brand", required=True)
    parser.add_argument("--key-env", default="GCP_RELAX_KEY")
    parser.add_argument("--grep", default="user,conversion,key",
                         help="カンマ区切りのキーワード(apiName/uiName/descriptionのいずれかに"
                              "部分一致すれば表示。大小文字は区別しない)")
    args = parser.parse_args()

    creds = credentials(args.key_env)
    summaries = ga4_account_summaries(creds)
    names = [p["displayName"] for s in summaries for p in s.get("propertySummaries", [])
              if p.get("displayName")]
    id_map = ga4_property_ids(summaries)
    result = ga4.resolve(names, args.brand)
    if not result["matched"]:
        print("ERROR: 一致する店舗が1件もありません", file=sys.stderr)
        return 1

    store, display_name = next(iter(sorted(result["matched"].items())))
    property_id = id_map[display_name]
    print(f"サンプルプロパティ: {store} ({property_id})\n")

    data_api = build("analyticsdata", "v1beta", creds)
    metadata = data_api.properties().getMetadata(name=f"{property_id}/metadata").execute()

    keywords = [k.strip().lower() for k in args.grep.split(",") if k.strip()]

    def matches(entry: dict) -> bool:
        text = " ".join([entry.get("apiName", ""), entry.get("uiName", ""),
                          entry.get("description", "")]).lower()
        return any(k in text for k in keywords)

    print("=" * 60)
    print("METRICS")
    print("=" * 60)
    for m in metadata.get("metrics", []):
        if matches(m):
            print(f"  {m.get('apiName'):<28} {m.get('uiName')!r}")
            print(f"      {m.get('description')}")

    print()
    print("=" * 60)
    print("DIMENSIONS")
    print("=" * 60)
    for d in metadata.get("dimensions", []):
        if matches(d):
            print(f"  {d.get('apiName'):<28} {d.get('uiName')!r}")
            print(f"      {d.get('description')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""GA4とSearch Consoleに何が見えているかを、サービスアカウントで確かめる。

分析の第一歩は「このサービスアカウントで何が読めるのか」を確定させること。プロパティIDや
サイトURLを人が手で書き写す必要はない — GA4は Admin API の `accountSummaries`、
Search Console は `sites.list` が、権限のあるものを全部返してくれる。

GA4のプロパティは、そのまま [`ga4_properties.py`](ga4_properties.py) で院マスタの店舗名に
突き合わせる。1対1に定まらないものは対応表に入れず、未解決として報告する。

ブランド非依存。ブランドごとに違うのは「どの鍼(環境変数)を使うか」と「院マスタの
ブランド名」だけなので、両方とも引数にしてある。

    python3 scripts/analytics_discover.py --brand リラックス --key-env GCP_RELAX_KEY

**読み取り専用。** GA4にもSearch Consoleにも一切書き込まない。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ga4_properties as ga4  # noqa: E402

# 読み取りだけ。書き込みスコープは要求しない(要求しても使わないが、
# 鍵が持つ権限は小さいほうがよい)。
SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def credentials(key_env: str):
    raw = os.environ.get(key_env, "").strip()
    if not raw:
        fail(
            f"{key_env} が未設定です。GitHub Actionsではリポジトリシークレットから渡ります。"
            "ワークフローのenvブロックとシークレット名を確認してください。"
        )
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        # 鍵の中身は絶対にログへ出さない。
        fail(f"{key_env} がJSONとして読めません(値の中身は表示しません)。")

    try:
        from google.oauth2 import service_account
    except ImportError:
        fail("google-auth が必要です")
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    print(f"サービスアカウント: {creds.service_account_email}\n")
    return creds


def build(service_name: str, version: str, creds):
    from googleapiclient.discovery import build as _build
    return _build(service_name, version, credentials=creds, cache_discovery=False)


def ga4_account_summaries(creds) -> list[dict]:
    """権限のあるGA4アカウントとプロパティを全部返す。ページングも辿る。"""
    admin = build("analyticsadmin", "v1beta", creds)
    summaries, page_token = [], None
    while True:
        response = admin.accountSummaries().list(
            pageSize=200, pageToken=page_token
        ).execute()
        summaries.extend(response.get("accountSummaries", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return summaries


def report_ga4(summaries: list[dict], brand: str) -> int:
    print("=" * 60)
    print("GA4")
    print("=" * 60)
    if not summaries:
        print("\n**プロパティが1件も返りませんでした。**")
        print("権限がアカウント単位ではなくプロパティ単位で付いている可能性が高いです。")
        print("GA4管理画面の左『アカウント』列 →『アカウントのアクセス管理』から、")
        print("サービスアカウントのメールアドレスに『閲覧者』を付け直してください。")
        return 1

    names = []
    print(f"アクセスできるアカウント: {len(summaries)}件\n")
    for summary in summaries:
        properties = summary.get("propertySummaries", [])
        print(f"  [{summary.get('displayName')}] ({summary.get('account')}) "
              f"— プロパティ {len(properties)}件")
        for prop in properties:
            print(f"      {prop.get('property'):<24} {prop.get('displayName')!r}")
            if prop.get("displayName"):
                names.append(prop["displayName"])
    print()

    result = ga4.resolve(names, brand)
    return ga4.report(result)


def gsc_sites(creds) -> list[dict]:
    search_console = build("searchconsole", "v1", creds)
    return search_console.sites().list().execute().get("siteEntry", [])


def report_gsc(sites: list[dict], store_paths: list[str]) -> int:
    print("\n" + "=" * 60)
    print("Search Console")
    print("=" * 60)
    if not sites:
        print("\n**サイトが1件も返りませんでした。**")
        print("Search Console にはGA4のようなアカウント単位の一括付与がありません。")
        print("対象プロパティごとに『設定 → ユーザーと権限 → ユーザーを追加』で、")
        print("サービスアカウントに『フル』を付ける必要があります。")
        return 1

    print(f"\nアクセスできるサイト: {len(sites)}件\n")
    for site in sites:
        url = site.get("siteUrl", "")
        kind = "ドメインプロパティ" if url.startswith("sc-domain:") else "URLプレフィックス"
        print(f"  {url:<45} {kind:<16} 権限={site.get('permissionLevel')}")

    # ドメインプロパティが1つあれば、店舗別はページのパスで切り出せる。
    # URLプレフィックスが店舗ごとに切られている場合は、そのまま店舗の単位になる。
    domain = [s for s in sites if s.get("siteUrl", "").startswith("sc-domain:")]
    prefix = [s for s in sites if not s.get("siteUrl", "").startswith("sc-domain:")]
    print()
    if domain:
        print(f"ドメインプロパティが {len(domain)}件 あります。"
              f"店舗別は pagePath の接頭辞({len(store_paths)}店舗ぶん)で切り出せます。")
    if prefix:
        print(f"URLプレフィックスが {len(prefix)}件 あります。"
              "店舗ごとに切られているなら、それがそのまま店舗の単位になります。")
    return 0


def store_paths_of(brand: str) -> list[str]:
    """院マスタから、そのブランドの店舗ページのパスを集める。"""
    from urllib.parse import urlparse
    clinics = json.loads(ga4.CLINICS_PATH.read_text(encoding="utf-8"))["clinics"]
    paths = []
    for clinic in clinics:
        if clinic.get("brand") != brand:
            continue
        path = urlparse(clinic.get("website", "")).path.strip("/")
        if path:
            paths.append(path)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brand", required=True, help="院マスタのブランド名(例: リラックス)")
    parser.add_argument("--key-env", default="GCP_RELAX_KEY",
                        help="鍵JSONが入っている環境変数名(既定: GCP_RELAX_KEY)")
    parser.add_argument("--skip-ga4", action="store_true")
    parser.add_argument("--skip-gsc", action="store_true")
    args = parser.parse_args()

    creds = credentials(args.key_env)
    status = 0

    if not args.skip_ga4:
        try:
            status |= report_ga4(ga4_account_summaries(creds), args.brand)
        except Exception as error:  # noqa: BLE001 — APIの失敗理由をそのまま見せたい
            print(f"GA4の取得に失敗しました: {error}", file=sys.stderr)
            status |= 1

    if not args.skip_gsc:
        try:
            status |= report_gsc(gsc_sites(creds), store_paths_of(args.brand))
        except Exception as error:  # noqa: BLE001
            print(f"Search Consoleの取得に失敗しました: {error}", file=sys.stderr)
            status |= 1

    print()
    if status:
        print("未解決があります。上の指摘を潰してから、数字の取り込みに進むこと。")
    else:
        print("GA4・Search Consoleとも読めています。")
    return status


if __name__ == "__main__":
    sys.exit(main())

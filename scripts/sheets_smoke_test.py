#!/usr/bin/env python3
"""任意のスプレッドシートに、指定のサービスアカウントで読めるかだけを確かめる。

新しいシートを共有してもらったとき、本格的な取り込みスクリプトを書く前に
「そもそも読めるか」を1回で確かめるための使い捨てチェック。ブランド非依存
(analytics_discover.pyと同じ設計: 鍼は環境変数名で切り替え、シート側の情報は引数)。

読み取り専用。書き込みは一切行わない。
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def credentials(key_env: str):
    raw = os.environ.get(key_env, "").strip()
    if not raw:
        fail(f"{key_env} が未設定です。")
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        fail(f"{key_env} がJSONとして読めません(値の中身は表示しません)。")
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    print(f"サービスアカウント: {creds.service_account_email}")
    return creds


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--key-env", required=True)
    ap.add_argument("--sheet-id", required=True)
    ap.add_argument("--tab", help="読むタブ名。省略するとタブ一覧だけ出す")
    ap.add_argument("--range", default="A1:E5", help="タブ指定時に読む範囲(既定 A1:E5)")
    args = ap.parse_args()

    creds = credentials(args.key_env)
    from googleapiclient.discovery import build
    svc = build("sheets", "v4", credentials=creds, cache_discovery=False)

    try:
        meta = svc.spreadsheets().get(spreadsheetId=args.sheet_id).execute()
    except Exception as error:  # noqa: BLE001
        print(f"開けませんでした: {error}", file=sys.stderr)
        return 1

    title = meta["properties"]["title"]
    tabs = [s["properties"]["title"] for s in meta["sheets"]]
    print(f"シート: {title!r}")
    print(f"タブ({len(tabs)}件): {tabs}")

    if not args.tab:
        print("\n--tab を指定すると、そのタブの先頭を読んで内容も確認します。")
        return 0

    if args.tab not in tabs:
        fail(f"タブ {args.tab!r} が見つかりません。上のタブ一覧から選んでください。")

    values = svc.spreadsheets().values().get(
        spreadsheetId=args.sheet_id, range=f"'{args.tab}'!{args.range}"
    ).execute().get("values", [])
    print(f"\n'{args.tab}'!{args.range} の内容({len(values)}行):")
    for row in values:
        print(" ", row)
    return 0


if __name__ == "__main__":
    sys.exit(main())

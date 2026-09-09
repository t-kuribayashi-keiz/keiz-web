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
    ap.add_argument("--gid", type=int,
                     help="--tabの代わりにgid(スプレッドシートURLの#gid=以降の数値)でタブを指定する。"
                          "--tabと同時指定時は--tabを優先")
    ap.add_argument("--range", default="A1:E5", help="タブ指定時に読む範囲(既定 A1:E5)")
    ap.add_argument("--out-csv", help="省略可。指定するとログ表示に加えて範囲の内容をCSVとして書き出す"
                                       "(get_job_logsの出力上限を超える大きな範囲を読むとき用。"
                                       "actions/upload-artifactで拾う想定。ただしArtifactのダウンロード先が"
                                       "blob.core.windows.netで、組織のプロキシ越しにそこへ到達できない"
                                       "実行環境もある。その場合は--grep-colと組み合わせてログに収まる"
                                       "行数まで絞り込むこと)")
    ap.add_argument("--grep-col", type=int,
                     help="省略可。0始まりの列番号を指定すると、その列が--grep-valuesのいずれかと"
                          "完全一致する行だけに絞ってログへ出す(--out-csv未指定時のみ有効)。"
                          "大きな範囲を、ログに収まる行数まで絞り込みたいときに使う")
    ap.add_argument("--grep-values", help="--grep-colとセットで使う。カンマ区切りの一致対象値")
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
    gid_by_title = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    print(f"シート: {title!r}")
    print(f"タブ({len(tabs)}件): {tabs}")
    print(f"gid対応: {gid_by_title}")

    tab = args.tab
    if not tab and args.gid is not None:
        title_by_gid = {v: k for k, v in gid_by_title.items()}
        tab = title_by_gid.get(args.gid)
        if tab is None:
            fail(f"gid={args.gid} が見つかりません。上のgid対応から選んでください。")
        print(f"gid={args.gid} -> タブ {tab!r}")

    if not tab:
        print("\n--tab か --gid を指定すると、そのタブの先頭を読んで内容も確認します。")
        return 0
    args.tab = tab

    if args.tab not in tabs:
        fail(f"タブ {args.tab!r} が見つかりません。上のタブ一覧から選んでください。")

    values = svc.spreadsheets().values().get(
        spreadsheetId=args.sheet_id, range=f"'{args.tab}'!{args.range}"
    ).execute().get("values", [])
    print(f"\n'{args.tab}'!{args.range} の内容({len(values)}行):")
    if args.out_csv:
        import csv
        with open(args.out_csv, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows(values)
        print(f"  -> {args.out_csv} に書き出し済み(ログには表示しない。行数が多いため)")
    elif args.grep_col is not None:
        wanted = set(v.strip() for v in (args.grep_values or "").split(","))
        matched = [row for row in values if len(row) > args.grep_col and row[args.grep_col] in wanted]
        print(f"  絞り込み: 列{args.grep_col}が{sorted(wanted)}のいずれかに一致する行のみ"
              f"({len(matched)}/{len(values)}行)")
        for row in matched:
            print(" ", row)
    else:
        for row in values:
            print(" ", row)
    return 0


if __name__ == "__main__":
    sys.exit(main())

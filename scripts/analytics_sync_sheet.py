#!/usr/bin/env python3
"""GA4/GSCの統合ログ(analytics_pull.pyの出力)を、Google Sheetsの長形式ログに書き込む。

analytics_discover.py・analytics_pull.py は読み取り専用(GA4/GSCにもリポジトリにも
書き込まない)。ここだけがGoogle Sheetsへの書き込みを担当する、明確に分離した別スクリプト
——「鍵が持つ権限は小さいほうがよい」という方針([analytics_discover.py]のコメント参照)を
崩さないため、Sheets書き込みスコープ(https://www.googleapis.com/auth/spreadsheets)は
このスクリプトだけが要求する。

**マージして書き戻す方式。** シートを全部読み、(年月・ブランド・店舗・ソース・チャネル・指標)
をキーに、渡された行で上書き(無ければ追加)してから、シート全体を書き戻す。同じ月を
再実行しても重複が増えない。件数がまだ小さいうち(MEOのように数十万行に達するまで)は
これで十分機能する——[MEOのSheets移行](../functions/meo-internal/CLAUDE.md)と同じ考え方。

    python3 scripts/analytics_pull.py --brand スマイル --key-env ANALYTICS_KEY \
        --month "2026年08月号" --out /tmp/smile.tsv
    python3 scripts/analytics_sync_sheet.py --brand スマイル --key-env ANALYTICS_KEY \
        --sheet-id <スプレッドシートID> --rows /tmp/smile.tsv
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

HEADER = ["年月", "ブランド", "店舗", "ソース", "チャネル", "指標", "値", "取得日時"]
KEY_COLUMNS = ["年月", "ブランド", "店舗", "ソース", "チャネル", "指標"]

DEFAULT_TAB = "ログ"


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

    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)


def build_sheets(creds):
    from googleapiclient.discovery import build

    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def read_rows_tsv(path: str) -> list[dict]:
    """analytics_pull.py が書き出したTSV(年月・店舗・ソース・チャネル・指標・値)を読む。"""
    text = Path(path).read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    header = lines[0].split("\t")
    expected = ["年月", "店舗", "ソース", "チャネル", "指標", "値"]
    if header != expected:
        fail(f"TSVの列が想定と違います。期待={expected} 実際={header}")
    rows = []
    for line in lines[1:]:
        cells = line.split("\t")
        rows.append(dict(zip(header, cells)))
    return rows


def existing_rows(sheets, sheet_id: str, tab: str) -> tuple[list[str], list[list[str]]]:
    """シートの現在の中身を読む。タブが無ければ(初回)ヘッダだけの空として扱う。"""
    meta = sheets.spreadsheets().get(spreadsheetId=sheet_id).execute()
    titles = [s["properties"]["title"] for s in meta.get("sheets", [])]
    if tab not in titles:
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": tab}}}]},
        ).execute()
        return HEADER, []

    response = sheets.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"'{tab}'!A1:H"
    ).execute()
    values = response.get("values", [])
    if not values:
        return HEADER, []
    header, body = values[0], values[1:]
    if header != HEADER:
        fail(
            f"シート'{tab}'の見出し行が想定と違います。期待={HEADER} 実際={header}\n"
            "手で列を足したり並べ替えたりしていないか確認してください。"
        )
    return header, body


def merge(existing: list[list[str]], new_rows: list[dict], brand: str,
          fetched_at: str) -> list[list[str]]:
    """既存の行を(キー)→行のdictにし、新しい行で上書き(無ければ追加)する。"""
    by_key: dict[tuple, list[str]] = {}
    for row in existing:
        padded = row + [""] * (len(HEADER) - len(row))
        key = tuple(padded[HEADER.index(col)] for col in KEY_COLUMNS)
        by_key[key] = padded

    for row in new_rows:
        record = {
            "年月": row["年月"], "ブランド": brand, "店舗": row["店舗"],
            "ソース": row["ソース"], "チャネル": row["チャネル"], "指標": row["指標"],
            "値": row["値"], "取得日時": fetched_at,
        }
        key = tuple(record[col] for col in KEY_COLUMNS)
        by_key[key] = [record[col] for col in HEADER]

    # 年月・ブランド・店舗・ソース・チャネル・指標の順で並べる。差分が目で追える。
    return sorted(by_key.values(), key=lambda r: tuple(r[:6]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brand", required=True, help="院マスタのブランド名(例: スマイル)")
    parser.add_argument("--key-env", required=True,
                        help="Sheets書き込みスコープ付きの鍵JSONが入っている環境変数名")
    parser.add_argument("--sheet-id", required=True, help="書き込み先スプレッドシートID")
    parser.add_argument("--tab", default=DEFAULT_TAB, help=f"タブ名(既定: {DEFAULT_TAB})")
    parser.add_argument("--rows", required=True,
                        help="analytics_pull.py --out で書き出したTSVのパス")
    args = parser.parse_args()

    new_rows = read_rows_tsv(args.rows)
    if not new_rows:
        print("書き込む行がありません(TSVが空)。何もせず終了します。")
        return 0

    creds = credentials(args.key_env)
    sheets = build_sheets(creds)

    _, existing = existing_rows(sheets, args.sheet_id, args.tab)
    fetched_at = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S")
    merged = merge(existing, new_rows, args.brand, fetched_at)

    sheets.spreadsheets().values().clear(
        spreadsheetId=args.sheet_id, range=f"'{args.tab}'!A1:H"
    ).execute()
    sheets.spreadsheets().values().update(
        spreadsheetId=args.sheet_id, range=f"'{args.tab}'!A1",
        valueInputOption="RAW",
        body={"values": [HEADER] + merged},
    ).execute()

    print(f"書き込み完了: '{args.tab}' タブ、{len(merged)}行(このブランド・このバッチで"
          f"{len(new_rows)}行を追加/更新)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

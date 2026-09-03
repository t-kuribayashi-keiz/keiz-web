#!/usr/bin/env python3
"""院マスタ(Googleスプレッドシート「診療時間」)から診療時間・定休日を取り込む。

data/clinics.json には院名・住所・電話・URL・メールしか入っていない。取り込み元の
スプレッドシートのファイル名が「診療時間」だったため取り込んだつもりになりやすいが、
**時間と定休日の列は入っていない**(2026-09-03に判明。別セッションの
salonboard-operator が「定休日がどこにも無い」と回答した原因)。

`--inspect` はタブ名と見出し行を出すだけ。`--apply` は data/clinics.json の各院に
`hours` と `closed_days` を足す。院名の照合は scripts/store_matcher.py の正規化を使う
(媒体側の表記ゆれ用に作ったもので、整骨院/接骨院の違いなどを吸収する)。

書き込むのはリポジトリのJSONだけで、スプレッドシートには一切書かない。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from store_matcher import normalize_store_name  # noqa: E402

# ファイル名が「診療時間」のスプレッドシート。data/clinics.json の notes と
# docs/org-review-log.md(2026-09-02)に出典として記録されている院マスタ本体。
CLINIC_MASTER_ID = "1Pd2S6P9sAVMTk8FBqPJHKwihhggPgmvQk6pEFkgwHl8"
CLINICS_PATH = Path(__file__).resolve().parent.parent / "data" / "clinics.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# 見出しの候補。実際の見出しは実機を見てから確定する(推測で列を決めない)。
HOURS_HEADERS = ("診療時間", "営業時間", "受付時間")
CLOSED_HEADERS = ("定休日", "休診日", "休業日")
NAME_HEADERS = ("院名", "店舗名", "医院名", "名称")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def build_service():
    raw = os.environ.get("GCP_KPI_WRITER_KEY", "").strip()
    if not raw:
        fail(
            "GCP_KPI_WRITER_KEY が未設定です。GitHub Actionsではリポジトリシークレットから"
            "渡ります。ワークフローのenvブロックとシークレット名を確認してください。"
        )
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        # 鍵の中身は絶対にログへ出さない。
        fail("GCP_KPI_WRITER_KEY がJSONとして読めません(値の中身は表示しません)。")

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        fail("google-auth / google-api-python-client が必要です")

    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def header_row_index(rows: list[list]) -> int | None:
    """見出し行を探す。院名らしい見出しがある最初の行。

    先頭行が見出しとは限らない(タイトル行や注記が上にあるシートが実在する)ので、
    行番号を決め打ちしない。
    """
    for index, row in enumerate(rows[:10]):
        texts = [str(cell).strip() for cell in row]
        if any(text in NAME_HEADERS for text in texts):
            return index
    return None


def columns_of(header: list, candidates: tuple[str, ...]) -> list[int]:
    """見出し名に候補のどれかを含む列の位置(0起点)。

    「診療時間①」「診療時間(平日)」のような枝番が付くことがあるので前方一致で拾い、
    **見つかった列を全部返す**。1つに絞れないときに勝手に選ぶと、平日の時間だけを
    その院の診療時間として記録してしまう。
    """
    found = []
    for index, cell in enumerate(header):
        text = str(cell).strip()
        if any(text.startswith(name) for name in candidates):
            found.append(index)
    return found


def inspect(service) -> int:
    """タブ名と見出し行を出すだけ。書き込みは一切しない。"""
    meta = service.spreadsheets().get(
        spreadsheetId=CLINIC_MASTER_ID,
        fields="properties.title,sheets.properties(sheetId,title,gridProperties)",
    ).execute()
    print(f"スプレッドシート名: {meta['properties']['title']}")
    sheets = meta.get("sheets", [])
    print(f"タブ数: {len(sheets)}")
    for sheet in sheets:
        props = sheet["properties"]
        grid = props.get("gridProperties", {})
        print(f"  gid={props['sheetId']:<12} {props['title']!r} "
              f"({grid.get('rowCount')}行×{grid.get('columnCount')}列)")

    for sheet in sheets:
        title = sheet["properties"]["title"]
        print(f"\n=== {title!r} ===")
        result = (
            service.spreadsheets().values()
            .get(spreadsheetId=CLINIC_MASTER_ID, range=f"'{title}'!A1:BZ8",
                 valueRenderOption="FORMATTED_VALUE")
            .execute()
        )
        rows = result.get("values", [])
        if not rows:
            print("  (空)")
            continue
        index = header_row_index(rows)
        if index is None:
            print(f"  見出し行が見つかりません(1行目: {rows[0][:12]})")
            continue
        header = rows[index]
        print(f"  見出し行 = {index + 1}行目")
        print("  " + " | ".join(
            f"{i + 1}:{str(cell).strip()}" for i, cell in enumerate(header) if str(cell).strip()
        ))
        hours = columns_of(header, HOURS_HEADERS)
        closed = columns_of(header, CLOSED_HEADERS)
        print(f"  診療時間らしい列: {[header[i] for i in hours] or 'なし'}")
        print(f"  定休日らしい列:   {[header[i] for i in closed] or 'なし'}")
        for row in rows[index + 1:index + 3]:
            shown = {str(header[i]).strip(): (row[i] if i < len(row) else "")
                     for i in hours + closed if i < len(header)}
            name = next((row[i] for i, cell in enumerate(header)
                         if str(cell).strip() in NAME_HEADERS and i < len(row)), "")
            print(f"    {name!r}: {shown}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inspect", action="store_true",
        help="院マスタのタブ名・見出し行・診療時間/定休日の列を出すだけ",
    )
    args = parser.parse_args()

    if args.inspect:
        return inspect(build_service())

    fail("いまは --inspect だけ実装しています。列が確定してから取り込みを書きます。")
    return 1


if __name__ == "__main__":
    sys.exit(main())

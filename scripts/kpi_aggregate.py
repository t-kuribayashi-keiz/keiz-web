#!/usr/bin/env python3
"""直営+サンズミライの月次KPIを「【2026年_月次報告】集客数」に転記する。

月の途中に入れた中間値(見込み)を、月が締まったあとの速報値に差し替えるのがこの処理。
詳細は functions/kpi-aggregation/CLAUDE.md。

**既定はドライラン。** 書き込むには --apply を明示する。本番の業務シートを触るため、
既定で書き込む設計にはしない。

安全策(すべて必須。省略しない):
  1. 書き込み前に対象セルの現在値を読んで記録する(巻き戻せるように)
  2. 書き込むセルはホワイトリストで固定し、範囲外には一切書かない
  3. 書き込み後に読み返して、意図した値と一致するか照合する。不一致なら異常終了
  4. 合計行は毎回探して検証する。ハードコードしない(店舗増減で行がずれるため)

認証: 環境変数 GCP_KPI_WRITER_KEY にサービスアカウントのJSON全文。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

SPREADSHEET_ID = "1Ali0uUUTnoWVv00GBYcp88-JfiPFP01Ttu5gqJ9D_Bg"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# 「年間計画・目標」タブの列。2026-09-02に確定(functions/kpi-aggregation/CLAUDE.md 参照)。
# 数式が入っている列(I, K, P, T, AD など)には**書き込まない**。上書きすると数式が消える。
PLAN_COLUMNS = {
    "month": "B",
    "hp": "C",
    "hpb": "D",
    "epark": "E",
    "referral": "F",          # ④
    "offline_total": "J",     # ④
    "stores_hp": "L",
    "stores_hpb_chokuei": "M",
    "stores_hpb_sans": "N",
    "stores_hpb_mirai": "O",
    "stores_epark_chokuei": "Q",
    "stores_epark_sans": "R",
    "stores_epark_mirai": "S",
    "seo_meo": "U",
    "ppc": "V",               # ③ 手入力のまま
    "meta": "W",              # ③ 手入力のまま
    "ai": "X",                # ④
    "uu_seo": "AB",
    "uu_meo": "AC",
    "uu_ppc": "AE",
}

# ダッシュボードのAG〜AO列。並びは栗林さんの指定とヘッダー解析が一致して確定。
DASHBOARD_COLUMNS = [
    ("web_total", "AG"),
    ("hp", "AH"),
    ("hpb", "AI"),
    ("epark", "AJ"),
    ("seo", "AK"),   # SEO + MEO + AI の合算
    ("meta", "AL"),
    ("ppc", "AM"),
    ("uu_seo", "AN"),
    ("uu_ppc", "AO"),
]

# ①②⑤で書き込んでよい列だけを列挙する。ここに無い列には絶対に書かない。
# ③(PPC/META)は自動化保留、④は転記方法が未確定なので、いまは対象外。
WRITABLE_PLAN_KEYS = {
    "hp", "hpb", "epark",
    "stores_hp",
    "stores_hpb_chokuei", "stores_hpb_sans", "stores_hpb_mirai",
    "stores_epark_chokuei", "stores_epark_sans", "stores_epark_mirai",
    "uu_seo", "uu_meo", "uu_ppc",
}

# 合計行を探すときに、その行が本当に合計行かを確かめるためのラベル。
TOTAL_LABELS = ("合計", "総計", "計")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def col_to_index(letters: str) -> int:
    """A -> 1, AA -> 27。"""
    index = 0
    for char in letters:
        index = index * 26 + (ord(char.upper()) - ord("A") + 1)
    return index


def index_to_col(index: int) -> str:
    letters = ""
    while index > 0:
        index, rem = divmod(index - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


def find_total_row(rows: list[list[str]], value_col_index: int) -> int:
    """合計行の行番号(1始まり)を返す。見つからない/怪しい場合は例外。

    行番号を固定で持たない理由: 店舗が増減すると合計行がずれる。ずれたまま読むと
    合計ではない1店舗分の値をKPIとして書き込んでしまい、しかもエラーが出ない。

    判定は2段構え:
      1. どこかのセルに「合計」等のラベルがある行を探す
      2. その行の対象列に数値が入っていることを確かめる
    候補が複数あるときは、どれを使うべきか機械的に決められないので失敗させる。
    """
    candidates = []
    for row_index, row in enumerate(rows, start=1):
        has_label = any(
            any(label in str(cell) for label in TOTAL_LABELS) for cell in row
        )
        if not has_label:
            continue
        value = row[value_col_index - 1] if len(row) >= value_col_index else ""
        if parse_number(value) is None:
            continue
        candidates.append(row_index)

    if not candidates:
        raise ValueError(
            "合計行が見つかりませんでした。シートの構造が変わった可能性があります。"
            "行番号を推測して書き込むのは危険なため、ここで停止します。"
        )
    if len(candidates) > 1:
        raise ValueError(
            f"合計行の候補が複数見つかりました(行: {candidates})。"
            "どれを使うか機械的に判断できないため停止します。"
        )
    return candidates[0]


def parse_number(value) -> float | None:
    """'1,234' や '1234' を数値に。数値でなければ None。"""
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("　", "")
    if text in ("", "-", "―"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def find_month_row(rows: list[list[str]], month_col: str, month_label: str) -> int:
    """「2026年8月」のような月ラベルから対象行を特定する。"""
    col_index = col_to_index(month_col)
    matches = [
        row_index
        for row_index, row in enumerate(rows, start=1)
        if len(row) >= col_index and str(row[col_index - 1]).strip() == month_label
    ]
    if not matches:
        raise ValueError(f"{month_label} の行が見つかりませんでした。")
    if len(matches) > 1:
        raise ValueError(f"{month_label} の行が複数あります(行: {matches})。")
    return matches[0]


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
        fail("google-auth / google-api-python-client が必要です: pip install google-auth google-api-python-client")

    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def read_range(service, sheet_range: str) -> list[list[str]]:
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=SPREADSHEET_ID, range=sheet_range, valueRenderOption="FORMATTED_VALUE")
        .execute()
    )
    return result.get("values", [])


def snapshot(service, cells: dict[str, str]) -> dict[str, str]:
    """書き込み前の現在値を読んで返す。巻き戻しの手掛かりとしてログに残す。"""
    current = {}
    for label, cell in cells.items():
        values = read_range(service, cell)
        current[label] = values[0][0] if values and values[0] else ""
    return current


def verify(service, planned: dict[str, tuple[str, object]]) -> list[str]:
    """書き込み後に読み返し、一致しないものを返す。"""
    mismatches = []
    for label, (cell, expected) in planned.items():
        values = read_range(service, cell)
        actual = values[0][0] if values and values[0] else ""
        if parse_number(actual) != parse_number(expected):
            mismatches.append(f"{label} ({cell}): 期待={expected} / 実際={actual}")
    return mismatches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", required=True, help="対象月ラベル(例: 2026年8月)")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="実際に書き込む。指定しなければドライラン(書き込む内容をログに出すだけ)",
    )
    args = parser.parse_args()

    print(f"対象月: {args.month}")
    print(f"モード: {'本番書き込み' if args.apply else 'ドライラン(書き込まない)'}")
    print()

    # 転記元の抽出はサービスアカウントで実シートを読んでから確定させる。
    # 未確定のまま推測で書くと、誤った数字が誰にも気づかれずKPIになるため、
    # ここは意図的に未実装のままにしてある(functions/kpi-aggregation/CLAUDE.md の未確定事項)。
    fail(
        "転記元の抽出ロジックが未実装です。\n"
        "  未確定: 速報値タブのどの列が集客数/SEO UU/MEO UU/PPC UUか、U列(SEO,MEO)の出どころ、\n"
        "  広告費・EPARKシートでの直営/サンズ/ミライの判別方法。\n"
        "  サービスアカウントで該当タブを読んでから実装する。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

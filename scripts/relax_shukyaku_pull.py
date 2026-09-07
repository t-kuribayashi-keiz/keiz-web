#!/usr/bin/env python3
"""「リラックス新規客経路集計」シートから、店舗×媒体×対象月の新患数を取得する。

タブ「集客数(新ルール6月〜)」は店舗ごとに可変行数のブロックが縦に並ぶ形をしている
(新患合計→紹介→チラシ(ポスト/街頭)→看板(通りすがり)→GoogleMap検索→インターネット検索→
HPB→SNS→その他→HP広告用→SNS広告用→GIFTLs用→Map＋WEB→Map＋WEB+HPB)。行数を決め打ちせず、
A列(店舗名)が埋まっている行でブロックの開始を判定し、C列(媒体)でチャネルの行を特定する。

**読み取り専用。** シートには一切書き込まない。

    python3 scripts/relax_shukyaku_pull.py --key-env GCP_RELAX_KEY --month 2026年08月号
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analytics_discover import credentials, build  # noqa: E402
from store_matcher import normalize_store_name  # noqa: E402

SHEET_ID = "1v6ruoGHKQ4Gny5lVO8fVIVAzlRDozQjo2I9K5oRjjxA"
TAB = "集客数(新ルール6月～)"  # ～は全角チルダ(U+FF5E)。波ダッシュ(〜 U+301C)ではない。
HEADER_ROW_INDEX = 2  # 0-based。1〜2行目はタイトル・目標値の行で、3行目が見出し。


def clean_number(raw) -> int | None:
    """『107 』『-』『22/27』『#VALUE!』のようなセルを数値かNoneにする。

    前後の空白付き数値はstrip()で読む。ダッシュ・空欄は「データなし」でNone。
    スラッシュ入り(修正前後の併記)やエラー値は判読不能としてNoneに落とし、
    呼び出し側の[要確認]で報告する(黙って0扱いにしない)。
    """
    s = str(raw or "").strip()
    if s in ("", "-", "#VALUE!"):
        return None
    if "/" in s:
        return None
    s = s.replace(",", "")
    try:
        return int(s)
    except ValueError:
        return None


def month_column(header_row: list, month_label: str) -> int:
    """『2026年08月号』→ 見出し行の『2026/08』の列index。"""
    m = re.search(r"(\d{4})年(\d{1,2})月", month_label)
    if not m:
        raise ValueError(f"年月号の形式が読めません: {month_label!r}")
    target = f"{int(m.group(1))}/{int(m.group(2)):02d}"
    for i, cell in enumerate(header_row):
        if str(cell or "").strip() == target:
            return i
    raise ValueError(f"見出しに列『{target}』が見つからない")


def parse_blocks(values: list[list], month_col: int) -> dict[str, dict[str, int | None]]:
    """行の並びを店舗ブロックに切り出し、店舗名 → {媒体: 値} を返す。

    A列が埋まっている行がブロックの先頭(店舗名)。それ以降、次のブロック先頭までの
    行を同じ店舗の媒体別行として扱う。C列(媒体)が空の行(タイトル・空行)は無視する。
    """
    result: dict[str, dict[str, int | None]] = {}
    current_store = None
    for row in values:
        name = str(row[0] if len(row) > 0 else "").strip()
        channel = str(row[2] if len(row) > 2 else "").strip()
        if name:
            current_store = name
            result.setdefault(current_store, {})
        if current_store is None or not channel:
            continue
        raw = row[month_col] if month_col < len(row) else ""
        result[current_store][channel] = clean_number(raw)
    return result


def pull(svc, month_label: str) -> dict[str, dict[str, int | None]]:
    values = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=f"'{TAB}'!A1:BZ2000",
        valueRenderOption="FORMATTED_VALUE",
    ).execute().get("values", [])
    if len(values) <= HEADER_ROW_INDEX:
        raise ValueError("シートの行数が想定より少ない(見出し行に届かない)")
    col = month_column(values[HEADER_ROW_INDEX], month_label)
    return parse_blocks(values[HEADER_ROW_INDEX + 1:], col)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-env", default="GCP_RELAX_KEY")
    parser.add_argument("--month", required=True, help="対象年月号(例 2026年08月号)")
    parser.add_argument("--brand", default="リラックス")
    args = parser.parse_args(argv)

    creds = credentials(args.key_env)
    svc = build("sheets", "v4", creds)
    blocks = pull(svc, args.month)

    import json
    clinics_path = Path(__file__).resolve().parent.parent / "data" / "clinics.json"
    clinics = json.loads(clinics_path.read_text(encoding="utf-8"))["clinics"]
    in_brand = {normalize_store_name(c["name"]): c["name"]
                for c in clinics if c.get("brand") == args.brand}

    matched = 0
    unmatched_stores = []
    print(f"年月\t店舗\tチャネル\t指標\t値")
    for store_raw, channels in blocks.items():
        key = normalize_store_name(store_raw)
        store = in_brand.get(key)
        if store is None:
            unmatched_stores.append(store_raw)
            continue
        matched += 1
        for channel, value in channels.items():
            if value is None:
                continue
            print(f"{args.month}\t{store}\t{channel}\t新患数\t{value}")

    print(f"[集計] ブロック={len(blocks)} / {args.brand}に一致={matched}", file=sys.stderr)
    if unmatched_stores:
        print(f"[未一致(他ブランド or 全体行)] {unmatched_stores}", file=sys.stderr)
    missing = sorted(set(in_brand.values()) - {
        in_brand[normalize_store_name(s)] for s in blocks
        if normalize_store_name(s) in in_brand
    })
    if missing:
        print(f"[シートに見つからない店舗] {missing}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

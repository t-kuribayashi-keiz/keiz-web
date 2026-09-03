#!/usr/bin/env python3
"""院マスタ(Googleスプレッドシート「診療時間」)から診療時間・定休日を取り込む。

`data/clinics.json` には院名・住所・電話・URL・メールしか入っていない。取り込み元の
スプレッドシートのファイル名が「診療時間」なので取り込んだつもりになりやすいが、
**時間と定休日の列は入っていない**(2026-09-03に判明。別セッションの
salonboard-operator が「定休日がどこにも無い」と回答した原因)。

シートの見出しは3段の入れ子になっている:

    平日                          土日祝                        定休  電話番号 …
    前         後                 前         後
    開始  終了  開始  終了        開始  終了  開始  終了

結合セルは先頭の1セルにしか値が返らないので、上2段は右へ持ち越して読む。
**行番号も列記号も決め打ちしない** — 見出しの文字から探して、見つからなければ止める。

`--inspect` は構造を出すだけ。`--apply` は data/clinics.json の各院に `hours` と
`closed_day` を足す。書き込むのはリポジトリのJSONだけで、スプレッドシートには
一切書かない。
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

CLOSED_HEADERS = ("定休", "定休日", "休診日", "休業日")
START_HEADERS = ("開始",)
END_HEADERS = ("終了",)
# 院名の列には見出しが無い(A列が連番、B列が院名)。見出しから引けないので、
# clinics.json の院名と実際に照合できるかで確かめる。
NAME_COLUMN_INDEX = 1
MIN_NAME_MATCH_RATE = 0.8


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


def text(cell) -> str:
    return str(cell).strip()


def forward_fill(row: list, width: int) -> list[str]:
    """結合セルの見出しを右へ持ち越す。

    「平日」がC1:F1の結合なら、APIはC列にしか値を返さない。D〜F列を空のまま扱うと
    土日祝の列と区別できなくなる。
    """
    filled, carried = [], ""
    for index in range(width):
        value = text(row[index]) if index < len(row) else ""
        if value:
            carried = value
        filled.append(carried)
    return filled


def header_row_index(rows: list[list]) -> int | None:
    """見出しの最下段(開始/終了・定休が並ぶ行)を探す。

    先頭行が見出しとは限らないので行番号を決め打ちしない。
    """
    for index, row in enumerate(rows[:10]):
        texts = {text(cell) for cell in row}
        if texts & set(CLOSED_HEADERS) and texts & set(START_HEADERS):
            return index
    return None


def hour_columns(rows: list[list], header_index: int) -> list[tuple[str, int, int]]:
    """(区分名, 開始列, 終了列) の一覧。区分名は上2段の見出しをつなげたもの。

    上2段が無い(header_index < 2)なら区分名は付けられないので空を返す。
    """
    header = rows[header_index]
    width = max(len(row) for row in rows[:header_index + 1])
    groups = forward_fill(rows[header_index - 2], width) if header_index >= 2 else [""] * width
    subs = forward_fill(rows[header_index - 1], width) if header_index >= 1 else [""] * width

    found = []
    for index, cell in enumerate(header):
        if text(cell) not in START_HEADERS:
            continue
        # 開始のすぐ右が終了。そうでなければ想定と違うので拾わない。
        if index + 1 >= len(header) or text(header[index + 1]) not in END_HEADERS:
            continue
        label = " ".join(part for part in (groups[index], subs[index]) if part)
        found.append((label or f"列{index + 1}", index, index + 1))
    return found


def closed_column(rows: list[list], header_index: int) -> int | None:
    for index, cell in enumerate(rows[header_index]):
        if text(cell) in CLOSED_HEADERS:
            return index
    return None


def cell_at(row: list, index: int) -> str:
    return text(row[index]) if index < len(row) else ""


def read_hours(row: list, columns: list[tuple[str, int, int]]) -> dict[str, str]:
    """1院ぶんの診療時間。開始と終了が両方入っている区分だけ返す。

    片方だけの区分を「9:30-」のように残さないのは、営業時間として読めない値を
    入れるくらいなら無いほうがましなため。
    """
    hours = {}
    for label, start_index, end_index in columns:
        start, end = cell_at(row, start_index), cell_at(row, end_index)
        if start and end:
            hours[label] = f"{start}-{end}"
    return hours


def read_sheet(service, title: str) -> list[list]:
    result = (
        service.spreadsheets().values()
        .get(spreadsheetId=CLINIC_MASTER_ID, range=f"'{title}'!A1:BZ400",
             valueRenderOption="FORMATTED_VALUE")
        .execute()
    )
    return result.get("values", [])


def sheet_titles(service) -> tuple[str, list[str]]:
    meta = service.spreadsheets().get(
        spreadsheetId=CLINIC_MASTER_ID,
        fields="properties.title,sheets.properties(sheetId,title,gridProperties)",
    ).execute()
    return meta["properties"]["title"], [s["properties"]["title"] for s in meta.get("sheets", [])]


def collect(service) -> dict[str, dict]:
    """院名(正規化後) → {hours, closed_day, tab} を全タブから集める。"""
    _, titles = sheet_titles(service)
    collected: dict[str, dict] = {}
    for title in titles:
        rows = read_sheet(service, title)
        if not rows:
            continue
        header_index = header_row_index(rows)
        if header_index is None:
            print(f"  {title!r}: 見出し行が見つからないので飛ばします")
            continue
        columns = hour_columns(rows, header_index)
        closed_index = closed_column(rows, header_index)
        if not columns:
            print(f"  {title!r}: 開始/終了の組が見つからないので飛ばします")
            continue

        count = 0
        for row in rows[header_index + 1:]:
            name = cell_at(row, NAME_COLUMN_INDEX)
            if not name:
                continue
            key = normalize_store_name(name)
            entry = {
                "hours": read_hours(row, columns),
                "closed_day": cell_at(row, closed_index) if closed_index is not None else "",
                "tab": title,
                "name": name,
            }
            if not entry["hours"] and not entry["closed_day"]:
                continue
            # 同じ院名が2タブに出たら、どちらが正しいか決められない。両方落とす。
            if key in collected and collected[key] != entry:
                collected[key] = {"conflict": True, **entry}
            else:
                collected[key] = entry
            count += 1
        print(f"  {title!r}: 見出し={header_index + 1}行目 / 区分={[c[0] for c in columns]} / "
              f"定休列={closed_index + 1 if closed_index is not None else 'なし'} / {count}院")
    return collected


def inspect(service) -> int:
    """構造と、clinics.json との照合率を出すだけ。書き込みはしない。"""
    file_title, titles = sheet_titles(service)
    print(f"スプレッドシート名: {file_title}")
    print(f"タブ: {titles}\n")

    collected = collect(service)
    print(f"\n読めた院: {len(collected)}件")

    clinics = json.loads(CLINICS_PATH.read_text(encoding="utf-8"))["clinics"]
    matched = [c for c in clinics if normalize_store_name(c["name"]) in collected]
    print(f"clinics.json {len(clinics)}院のうち、マスタと照合できたのは {len(matched)}院")
    for clinic in matched[:5]:
        entry = collected[normalize_store_name(clinic["name"])]
        print(f"  {clinic['name']}: hours={entry['hours']} closed_day={entry['closed_day']!r}")
    missing = [c["name"] for c in clinics if normalize_store_name(c["name"]) not in collected]
    if missing:
        print(f"照合できなかった院 {len(missing)}件: {missing[:15]}")
    return 0


def apply(service) -> int:
    """clinics.json に hours と closed_day を足す。スプレッドシートには書かない。"""
    collected = collect(service)
    data = json.loads(CLINICS_PATH.read_text(encoding="utf-8"))
    clinics = data["clinics"]

    matched = [c for c in clinics if normalize_store_name(c["name"]) in collected]
    rate = len(matched) / len(clinics) if clinics else 0
    if rate < MIN_NAME_MATCH_RATE:
        fail(
            f"照合できたのは {len(matched)}/{len(clinics)}院({rate:.0%})しかありません。"
            "院名の列が想定(B列)と違うか、シートの構造が変わった可能性があります。"
            "半端に入れると『定休日が無い院』と『取り込めていない院』が区別できなくなるため停止します。"
        )

    conflicts = [entry["name"] for entry in collected.values() if entry.get("conflict")]
    if conflicts:
        fail(f"同じ院名が複数タブで別の内容でした: {conflicts}。どちらが正か決められないため停止します。")

    changed = 0
    for clinic in clinics:
        entry = collected.get(normalize_store_name(clinic["name"]))
        if entry is None:
            continue
        clinic["hours"] = entry["hours"]
        clinic["closed_day"] = entry["closed_day"]
        changed += 1

    data["_comment"] = (
        "院マスタ。id は kpi-history/ や proposals/ から参照するキーとして使う。"
        "ブランド別の詳細コンテキストは brands/<ブランド名>/CLAUDE.md を参照。"
        "hours(診療時間)と closed_day(定休)は院マスタのスプレッドシート「診療時間」"
        "(ID: 1Pd2S6P9sAVMTk8FBqPJHKwihhggPgmvQk6pEFkgwHl8)から "
        "scripts/clinic_master.py --apply で取り込む。**closed_day が空文字なのは"
        "『マスタの定休列が空だった』という意味で、『定休日が無い』と確定したわけではない。**"
        "hours や closed_day のキー自体が無い院は、マスタと院名を照合できなかった院。"
    )
    CLINICS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n{changed}院に hours と closed_day を書き込みました: {CLINICS_PATH}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true",
                        help="構造とclinics.jsonとの照合率を出すだけ")
    parser.add_argument("--apply", action="store_true",
                        help="clinics.json に hours と closed_day を書き込む")
    args = parser.parse_args()

    if args.inspect:
        return inspect(build_service())
    if args.apply:
        return apply(build_service())
    fail("--inspect か --apply を指定してください。")
    return 1


if __name__ == "__main__":
    sys.exit(main())

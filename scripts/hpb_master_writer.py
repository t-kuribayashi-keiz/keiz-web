#!/usr/bin/env python3
"""抽出したHPBリボンKPIを「HPB_145店舗_KPI一括集計結果」のMasterへ転記する。

設計は functions/kpi-aggregation と同じ思想:
  - GAS ではなくサービスアカウント + Sheets API。Claudeが実行結果をAPIで読み返して検証できる
  - 行番号・タブ名・合計行はコードに直書きしない。毎回ラベルで動的に特定し、外れたら止める
  - 既定はドライラン。--apply のときだけ書き込み、書いた直後に読み返して一致を確認する
  - 書き込み前に、既に入っている過去の月号で --calibrate して抽出の妥当性を確かめる

集客数の出どころ:
  「【2026年_月次報告】集客数」の『◯月HPB (速報値)』タブの、院名(各行)×当月列。
  タブ全体の合計(kpi_aggregate が読むもの)ではなく、店舗別の当月値を使う。

鍼灸併設リスティングの扱い(重要):
  同一店舗がHPB上で『◯◯接骨院』と『◯◯鍼灸接骨院』の2リスティングを持つことがある。
  集客数シートには本体側(非鍼灸)に1つだけ計上される。正規化すると両者は同じキーになるため、
  素の名前が集客数側に近い方(本体)にだけ値を入れ、もう一方は空欄にする(二重計上を防ぐ)。

このファイルはネットワーク越しの読み書きを行う。純粋な結合ロジック(join_shukyaku,
resolve_tab, find_total_row 等)はシート非依存で、tests から検証できるよう関数に切り出す。
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from store_matcher import normalize_store_name  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(REPO_ROOT, "data", "hpb-ribbon-config.json")


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


# --- 純粋ロジック (Sheets非依存。テスト対象) -----------------------------------------------

def resolve_tab(titles, keywords):
    """タブ名の一覧から、keywordsを全部含むものを1つに絞る。

    `HP` は `HPB` の一部なので、英数字キーワードは前後の境界を見て取り違えを防ぐ
    (『8月HP(速報値)』を探すときに『8月HPB(速報値)』へ当たらないように)。
    0件でも複数でも例外。
    """
    def contains(title, kw):
        if re.fullmatch(r"[0-9A-Za-z]+", kw):
            return re.search(rf"(?<![0-9A-Za-z]){re.escape(kw)}(?![0-9A-Za-z])", title) is not None
        return kw in title

    hits = [t for t in titles if all(contains(t, kw) for kw in keywords)]
    if len(hits) != 1:
        raise ValueError(f"タブが一意に決まらない keywords={keywords} 候補={hits}")
    return hits[0]


def month_tab_keywords(base_keywords, month_label):
    """『2026年08月号』『2026年8月』→ 月キーワード『8月』を base に足す。"""
    m = re.search(r"(\d{1,2})月", month_label)
    if not m:
        return list(base_keywords)
    return [f"{int(m.group(1))}月"] + list(base_keywords)


def header_index(header_row, *, contains=None, exact=None):
    for i, cell in enumerate(header_row):
        c = (cell or "").strip()
        if exact is not None and c == exact:
            return i
        if contains is not None and contains in c:
            return i
    raise ValueError(f"見出し列が見つからない contains={contains} exact={exact}")


def build_shukyaku_map(values, name_contains="院名", count_exact="当月"):
    """『◯月HPB(速報値)』タブの2次元配列 → 院名(生, 正規化) → 当月 の辞書。

    合計行以降(合計/既存/店舗数 等のラベル)は店舗ではないので取り込まない。
    """
    # 見出し行を探す(院名 と 当月 が同じ行にある)
    hdr_i = None
    for i, row in enumerate(values[:20]):
        if any(name_contains in (c or "") for c in row) and any((c or "").strip() == count_exact for c in row):
            hdr_i = i
            break
    if hdr_i is None:
        raise ValueError("集客数タブの見出し行(院名/当月)が見つからない")
    header = values[hdr_i]
    ni = header_index(header, contains=name_contains)
    ci = header_index(header, exact=count_exact)

    raw = {}          # 正規化キー → (生の院名, 当月)
    STOP = ("合計", "既存", "昨年", "昨対", "店舗数", "1店舗", "目標")
    for row in values[hdr_i + 1:]:
        name = (row[ni] if ni < len(row) else "").strip()
        if not name:
            continue
        if any(name.startswith(s) for s in STOP):
            break
        count = (row[ci] if ci < len(row) else "").strip()
        raw[normalize_store_name(name)] = (name, count)
    return raw


def join_shukyaku(rows, shukyaku_map):
    """抽出行(店舗名=院名)に集客数を結合する。鍼灸併設の二重計上を避ける。

    rows: 各行 dict に少なくとも '店舗名'(=院名) を持つ。'集客数' を書き込んで返す。
    戻り値: (rows, notes)。notes は未マッチ・按分など人が見るべき事項。
    """
    # 正規化キーごとに、そのキーに落ちる抽出行を集める
    buckets = {}
    for r in rows:
        key = normalize_store_name(r.get("店舗名") or r.get("院名") or "")
        buckets.setdefault(key, []).append(r)

    notes = []
    for key, group in buckets.items():
        entry = shukyaku_map.get(key)
        if entry is None:
            for r in group:
                r["集客数"] = ""
            notes.append(("未マッチ", [r.get("店舗名") for r in group]))
            continue
        raw_name, count = entry
        if len(group) == 1:
            group[0]["集客数"] = count
            continue
        # 複数の抽出行が同じ集客数エントリに落ちる = 鍼灸併設等。
        # 生の名前が集客数側に一番近い1行(本体)に入れ、他は空欄。
        primary = max(group, key=lambda r: difflib.SequenceMatcher(
            None, (r.get("店舗名") or ""), raw_name).ratio())
        for r in group:
            r["集客数"] = count if r is primary else ""
        notes.append(("併設按分", {
            "集客数院名": raw_name, "本体": primary.get("店舗名"),
            "空欄": [r.get("店舗名") for r in group if r is not primary],
        }))
    return rows, notes


def positional_no(index):
    """各月ブロックの位置番号 1,15,29,… (= 1 + 14*i)。No.は集計に使われない飾り。"""
    return 1 + 14 * index


# --- Sheets I/O -----------------------------------------------------------------------------

def sheets_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    raw = os.environ.get("GCP_KPI_WRITER_KEY", "")
    if not raw:
        raise SystemExit("GCP_KPI_WRITER_KEY が未設定。鍵はSecrets経由でのみ渡す。")
    info = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def list_tab_titles(svc, sheet_id):
    meta = svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
    return [s["properties"]["title"] for s in meta["sheets"]]


def get_values(svc, sheet_id, a1):
    return svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=a1,
        valueRenderOption="UNFORMATTED_VALUE").execute().get("values", [])


def load_extract_csv(path):
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "HPB店舗名": r.get("HPB店舗名", ""),
                "店舗名": r.get("院名", ""),
                "年月号": r.get("年月号", ""),
                "自社PV": r.get("自社PV", ""), "エリア平均PV": r.get("エリア平均PV", ""),
                "自社CVR": r.get("自社CVR", ""), "エリア平均CVR": r.get("エリア平均CVR", ""),
                "自社ACR": r.get("自社ACR", ""), "エリア平均ACR": r.get("エリア平均ACR", ""),
                "新規予約数実績": r.get("新規予約数実績", ""), "女性率": r.get("女性率", ""),
                "20代未満比率": r.get("20代未満比率", ""), "20代比率": r.get("20代比率", ""),
                "30代比率": r.get("30代比率", ""), "40代比率": r.get("40代比率", ""),
                "50代以上比率": r.get("50代以上比率", ""),
                "集客数": "", "予約枠〇": "",
            })
    return rows


def build_master_matrix(rows, columns):
    out = []
    for i, r in enumerate(rows):
        r["No."] = positional_no(i)
        out.append([r.get(c, "") for c in columns])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="HPBリボンKPIをMasterへ転記")
    ap.add_argument("--extract-csv", required=True, help="hpb_ribbon_extract.py の出力CSV")
    ap.add_argument("--month", required=True, help="対象年月号(例 2026年08月号)")
    ap.add_argument("--mode", choices=["inspect", "calibrate", "dry-run", "apply"],
                    default="dry-run")
    args = ap.parse_args(argv)

    cfg = load_config()
    master_cfg, shu_cfg = cfg["master_sheet"], cfg["shukyaku_sheet"]
    columns = master_cfg["columns"]

    svc = sheets_service()

    # 1) 集客数タブ(◯月HPB速報値)を読む
    shu_titles = list_tab_titles(svc, shu_cfg["id"])
    shu_tab = resolve_tab(shu_titles, month_tab_keywords(shu_cfg["tab_keywords"], args.month))
    shu_values = get_values(svc, shu_cfg["id"], f"'{shu_tab}'!A1:BZ400")
    shukyaku_map = build_shukyaku_map(
        shu_values,
        name_contains=shu_cfg["columns"]["store_name_header_contains"],
        count_exact=shu_cfg["columns"]["count_header_exact"])
    print(f"集客数タブ='{shu_tab}' 店舗={len(shukyaku_map)}", file=sys.stderr)

    # 2) 抽出CSVを読み、集客数を結合
    rows = load_extract_csv(args.extract_csv)
    for r in rows:
        r["年月号"] = args.month
    rows, notes = join_shukyaku(rows, shukyaku_map)
    filled = sum(1 for r in rows if str(r["集客数"]).strip() != "")
    print(f"抽出={len(rows)}店舗 / 集客数入り={filled} / 空欄={len(rows)-filled}", file=sys.stderr)
    for kind, detail in notes:
        print(f"  [{kind}] {detail}", file=sys.stderr)

    if args.mode == "inspect":
        print("[inspect] Master列:", columns, file=sys.stderr)
        return 0

    # 3) Masterタブ
    m_titles = list_tab_titles(svc, master_cfg["id"])
    m_tab = resolve_tab(m_titles, [master_cfg["tab_keyword"]])
    m_values = get_values(svc, master_cfg["id"], f"'{m_tab}'!A1:S5000")
    ym_col = columns.index("年月号")
    existing_months = {(r[ym_col] if ym_col < len(r) else "") for r in m_values[2:]}
    last_data_row = len(m_values)  # 0-based長。次に書く行(1-based)は +1

    if args.mode == "calibrate":
        if args.month not in existing_months:
            print(f"[calibrate] {args.month} はMasterに未登録。過去の完了月を指定する。", file=sys.stderr)
            return 1
        # 既存行を店舗名→行 で引き、抽出と突き合わせ
        name_col = columns.index("店舗名")
        existing = {}
        for r in m_values[2:]:
            if (r[ym_col] if ym_col < len(r) else "") == args.month:
                existing[(r[name_col] if name_col < len(r) else "")] = r
        checked = mismatch = 0
        for r in rows:
            ex = existing.get(r["店舗名"])
            if not ex:
                continue
            for c in ("自社PV", "エリア平均PV", "自社CVR", "エリア平均CVR", "自社ACR", "エリア平均ACR"):
                ci = columns.index(c)
                exv = str(ex[ci]).strip() if ci < len(ex) else ""
                nv = str(r.get(c, "")).strip()
                if exv and nv and exv != nv:
                    mismatch += 1
                    print(f"  不一致 {r['店舗名']} {c}: シート={exv} 抽出={nv}", file=sys.stderr)
            checked += 1
        print(f"[calibrate] 照合{checked}店舗 / 不一致{mismatch}", file=sys.stderr)
        return 0 if mismatch == 0 else 2

    if args.month in existing_months:
        raise SystemExit(f"{args.month} は既にMasterにある。二重書き込みを防ぐため停止。")

    matrix = build_master_matrix(rows, columns)
    start_row = last_data_row + 1
    a1 = f"'{m_tab}'!A{start_row}"
    print(f"書き込み先: {a1}  {len(matrix)}行 x {len(columns)}列", file=sys.stderr)

    if args.mode == "dry-run":
        print("[dry-run] 先頭3行:", file=sys.stderr)
        for row in matrix[:3]:
            print("   ", row, file=sys.stderr)
        return 0

    # apply: 書き込み → 読み返して一致確認
    svc.spreadsheets().values().update(
        spreadsheetId=master_cfg["id"], range=a1,
        valueInputOption="USER_ENTERED", body={"values": matrix}).execute()
    end_row = start_row + len(matrix) - 1
    back = get_values(svc, master_cfg["id"], f"'{m_tab}'!A{start_row}:S{end_row}")
    ok = (len(back) == len(matrix))
    if ok:
        for w, g in zip(matrix, back):
            g = list(g) + [""] * (len(w) - len(g))
            if [str(x) for x in w] != [str(x) for x in g[:len(w)]]:
                ok = False
                break
    print(f"[apply] 書き込み{len(matrix)}行 / 読み返し一致={ok}", file=sys.stderr)
    return 0 if ok else 3


if __name__ == "__main__":
    raise SystemExit(main())

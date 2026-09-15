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

ブランド系列(--profile):
  読み書き先の組は data/hpb-ribbon-config.json の profiles に持つ。既定の chokuei が
  直営+サンズミライ+リラックス系で、従来と同じ挙動。スマイル・グッドは集客数シート自体が
  別物(『グッド・スマイル月次報告』)で、しかも1つの月次タブの中に HP / HPB / meta /
  オフライン のブロックが縦に並ぶため、block_marker で目的のブロックまで降りてから
  見出しを探す。降りずに見出しだけ探すと**HPの数字をHPBとして取り込む**。

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


def profile_config(cfg, name):
    """系列名(chokuei / smile-good …)→ そのプロファイルの読み書き先。

    直営系はトップレベルの master_sheet / shukyaku_sheet をそのまま使う。他系列は
    profiles 側の同名キーで**丸ごと差し替える**(部分マージにすると、書いていない
    キーが直営の値のまま残って別シートを読みに行く事故になる)。
    """
    profiles = cfg.get("profiles", {})
    if name not in profiles:
        known = [k for k in profiles if not k.startswith("_")]
        raise ValueError(f"未知のプロファイル {name!r}。定義済み: {known}")
    prof = profiles[name]
    resolved = {
        "key_env": prof.get("key_env", "GCP_KPI_WRITER_KEY"),
        "brands": prof.get("brands"),          # None = 絞らない(直営の従来挙動)
        "master_sheet": prof.get("master_sheet", cfg["master_sheet"]),
        "shukyaku_sheet": prof.get("shukyaku_sheet", cfg["shukyaku_sheet"]),
    }
    if resolved["master_sheet"] is None:
        # 転記先が未決のプロファイル。読むところまでは動かせるが書けない。
        resolved["master_sheet"] = None
    return resolved


def find_block_header(values, marker, name_contains, count_exact, lookahead=5):
    """『HPB』のようなブロック印の下にある見出し行(院名/当月)の行番号を返す。

    1タブに HP / HPB / meta / オフライン のブロックが縦に並ぶシート用。見出しだけを
    探すと先頭ブロック(HP)に当たり、**別チャネルの数字を黙って取り込む**。

    印の付いたブロックが1つに定まらなければ例外。片方を勝手に選ばない
    (2026-09-06時点、最新月のタブには『HPB』印のブロックが2つ見えている。
    どちらが集客数かはシート側で決着させること)。
    """
    hits = []
    for i, row in enumerate(values):
        if not any(str(c or "").strip() == marker for c in row):
            continue
        for j in range(i + 1, min(i + 1 + lookahead, len(values))):
            row_j = values[j]
            if (any(name_contains in str(c or "") for c in row_j)
                    and any(str(c or "").strip() == count_exact for c in row_j)):
                hits.append(j)
                break
    if len(hits) != 1:
        raise ValueError(
            f"『{marker}』ブロックが一意に決まらない(見出し行={hits})。"
            "シート側でブロック名を分けるか、どちらを使うかを決めること。")
    return hits[0]


def header_index(header_row, *, contains=None, exact=None):
    for i, cell in enumerate(header_row):
        c = str(cell or "").strip()
        if exact is not None and c == exact:
            return i
        if contains is not None and contains in c:
            return i
    raise ValueError(f"見出し列が見つからない contains={contains} exact={exact}")


DEFAULT_STOP_PREFIXES = ("合計", "既存", "昨年", "昨対", "店舗数", "1店舗", "目標")


def build_shukyaku_map(values, name_contains="院名", count_exact="当月",
                       block_marker=None, stop_prefixes=DEFAULT_STOP_PREFIXES,
                       stop_contains=()):
    """集客数タブの2次元配列 → 院名(生, 正規化) → 当月 の辞書。

    合計行以降(合計/既存/店舗数 等のラベル)は店舗ではないので取り込まない。直営の
    シートは行頭一致で足りるが、系列によっては『グッド・スマイル合計』のように
    ラベルが途中に来るので stop_contains も見る。

    block_marker を渡すと、その印の付いたブロックの見出しから読む(1タブに複数
    チャネルのブロックが縦に並ぶシート向け)。
    """
    if block_marker:
        hdr_i = find_block_header(values, block_marker, name_contains, count_exact)
    else:
        # 見出し行を探す(院名 と 当月 が同じ行にある)
        hdr_i = None
        for i, row in enumerate(values[:20]):
            if (any(name_contains in str(c or "") for c in row)
                    and any(str(c or "").strip() == count_exact for c in row)):
                hdr_i = i
                break
        if hdr_i is None:
            raise ValueError("集客数タブの見出し行(院名/当月)が見つからない")
    header = values[hdr_i]
    ni = header_index(header, contains=name_contains)
    ci = header_index(header, exact=count_exact)

    raw = {}          # 正規化キー → (生の院名, 当月)
    for row in values[hdr_i + 1:]:
        # UNFORMATTED_VALUE で取得しているため、数値セルは str ではなく int/float で返る。
        name = str(row[ni] if ni < len(row) else "").strip()
        if not name:
            continue
        if any(name.startswith(s) for s in stop_prefixes):
            break
        if any(s in name for s in stop_contains):
            break
        count = str(row[ci] if ci < len(row) else "").strip()
        raw[normalize_store_name(name)] = (name, count)
    return raw


_TYPE_TOKEN = "〇"
_BRANCH_TAIL_THRESHOLD = 0.6


def _split_head_tail(normalized):
    """「おかだ〇枚方御殿山」→ ("おかだ","枚方御殿山")。屋号(〇の前)と支店名に分ける。"""
    if _TYPE_TOKEN not in normalized:
        return None
    head, _, tail = normalized.partition(_TYPE_TOKEN)
    return (head, tail) if head else None


def _branch_match(key, shukyaku_map, used):
    """正規化の完全一致で当たらないとき、屋号+支店名で1つに絞る(store_matcherと同じ考え方)。

    支店名の書き方の差(「（御殿山）」と「枚方御殿山院」)で完全一致を割るケースを拾う。
    候補が1つに絞れなければ Noneを返す(黙って別店に寄せない)。
    """
    sp = _split_head_tail(key)
    if not sp:
        return None
    head, tail = sp
    cands = []
    for sk in shukyaku_map:
        if sk in used:
            continue
        osp = _split_head_tail(sk)
        if not osp or osp[0] != head:
            continue
        otail = osp[1]
        if tail and otail:
            contained = tail in otail or otail in tail
            ratio = difflib.SequenceMatcher(None, tail, otail).ratio()
            if not contained and ratio < _BRANCH_TAIL_THRESHOLD:
                continue
        cands.append(sk)
    return cands[0] if len(cands) == 1 else None


def join_shukyaku(rows, shukyaku_map):
    """抽出行(店舗名=院名)に集客数を結合する。鍼灸併設の二重計上を避ける。

    rows: 各行 dict に少なくとも '店舗名'(=院名) を持つ。'集客数' を書き込んで返す。
    戻り値: (rows, notes)。notes は未マッチ・按分など人が見るべき事項。

    結合は2段構え。(1)正規化の完全一致、(2)当たらなければ屋号+支店名の緩い一致
    (store_matcherと同じ)。集客数エントリは1回だけ使う(usedで消費済みを追う)。
    """
    # 正規化キーごとに、そのキーに落ちる抽出行を集める
    buckets = {}
    for r in rows:
        key = normalize_store_name(r.get("店舗名") or r.get("院名") or "")
        buckets.setdefault(key, []).append(r)

    used = set()
    resolved = {}   # bucket_key -> shukyaku_key
    for key in buckets:                       # (1) 完全一致を先に確定
        if key in shukyaku_map:
            resolved[key] = key
            used.add(key)
    for key in buckets:                       # (2) 残りを屋号+支店名で
        if key in resolved:
            continue
        sk = _branch_match(key, shukyaku_map, used)
        if sk is not None:
            resolved[key] = sk
            used.add(sk)

    notes = []
    for key, group in buckets.items():
        sk = resolved.get(key)
        if sk is None:
            for r in group:
                r["集客数"] = ""
            notes.append(("未マッチ", [r.get("店舗名") for r in group]))
            continue
        raw_name, count = shukyaku_map[sk]
        if len(group) == 1:
            group[0]["集客数"] = count
            continue
        # 複数の抽出行が同じ集客数エントリに落ちる = 鍼灸併設等。
        # 生の名前が集客数側に一番近い1行(本体)に入れ、他は空欄(二重計上を防ぐ)。
        primary = max(group, key=lambda r: difflib.SequenceMatcher(
            None, (r.get("店舗名") or ""), raw_name).ratio())
        for r in group:
            r["集客数"] = count if r is primary else ""
        notes.append(("併設按分", {
            "集客数院名": raw_name, "本体": primary.get("店舗名"),
            "空欄": [r.get("店舗名") for r in group if r is not primary],
        }))
    return rows, notes


CLINICS_PATH = os.path.join(REPO_ROOT, "data", "clinics.json")


def brand_by_store(clinics_path=CLINICS_PATH):
    """院マスタから 正規化した院名 → ブランド名 の辞書を作る。"""
    clinics = json.load(open(clinics_path, encoding="utf-8"))["clinics"]
    return {normalize_store_name(c["name"]): c.get("brand", "") for c in clinics}


def split_by_brand(rows, brands, brand_map):
    """抽出行を、対象ブランドのものとそれ以外に分ける。

    リボンのZIPは全ブランドの店舗PDFを1つにまとめて届くので、抽出CSVには直営もスマイルも
    グッドも一緒に入っている。**転記先のMasterごとに絞らないと、別系列の店舗が混ざる。**

    brands が None なら絞らない(従来の挙動)。院マスタに載っていない店舗は「不明」として
    返し、**捨てずに必ず報告する**(新店・名寄せ漏れの入口なので)。
    """
    kept, dropped, unknown = [], [], []
    for r in rows:
        brand = brand_map.get(normalize_store_name(r.get("店舗名") or ""))
        if brand is None:
            unknown.append(r)
            if brands is not None:
                continue
            kept.append(r)
            continue
        if brands is None or brand in brands:
            kept.append(r)
        else:
            dropped.append((r.get("店舗名"), brand))
    return kept, dropped, unknown


def positional_no(index):
    """各月ブロックの位置番号 1,15,29,… (= 1 + 14*i)。No.は集計に使われない飾り。"""
    return 1 + 14 * index


# --- Sheets I/O -----------------------------------------------------------------------------

def sheets_service(key_env="GCP_KPI_WRITER_KEY"):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    raw = os.environ.get(key_env, "")
    if not raw:
        raise SystemExit(f"{key_env} が未設定。鍵はSecrets経由でのみ渡す。")
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


def col_letter(n):
    """1-based 列番号 → A1記法の列文字(1→A, 20→T, 47→AU)。"""
    s = ""
    while n > 0:
        n, m = divmod(n - 1, 26)
        s = chr(65 + m) + s
    return s


def load_extract_csv(path, ext_columns=()):
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            d = {
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
            }
            for c in ext_columns:                 # Master右側(T列〜)の拡張項目
                d[c] = r.get(c, "")
            rows.append(d)
    return rows


def build_master_matrix(rows, columns):
    out = []
    for i, r in enumerate(rows):
        r["No."] = positional_no(i)
        out.append([r.get(c, "") for c in columns])
    return out


def init_master(svc, master_cfg, columns, ext_columns):
    """空のスプレッドシートをMasterに仕立てる(タブ名 + 1行目タイトル/拡張ヘッダー + 2行目ヘッダー)。

    直営のMasterと同じ形にそろえる。writerは3行目からをデータとして読むので、この2行が
    無いと1行目のデータをヘッダーとして読み飛ばす。**空のシートにしか実行しない。**
    """
    meta = svc.spreadsheets().get(spreadsheetId=master_cfg["id"]).execute()
    sheets = meta["sheets"]
    if len(sheets) != 1:
        raise SystemExit(f"タブが{len(sheets)}枚ある。init-master は新規の空シート専用。")
    props = sheets[0]["properties"]
    title, sheet_id = props["title"], props["sheetId"]

    existing = get_values(svc, master_cfg["id"], f"'{title}'!A1:C5")
    if existing:
        raise SystemExit(f"タブ'{title}'は空ではない。既存のMasterに init-master は使わない。")

    want_tab = master_cfg["tab_keyword"]
    if title != want_tab:
        svc.spreadsheets().batchUpdate(spreadsheetId=master_cfg["id"], body={"requests": [
            {"updateSheetProperties": {"properties": {"sheetId": sheet_id, "title": want_tab},
                                       "fields": "title"}}]}).execute()
        print(f"タブ名を '{title}' → '{want_tab}' に変更", file=sys.stderr)

    row1 = ([master_cfg.get("title", want_tab)] + [""] * (len(columns) - 1) + list(ext_columns))
    rows = [row1, list(columns)]
    svc.spreadsheets().values().update(
        spreadsheetId=master_cfg["id"], range=f"'{want_tab}'!A1",
        valueInputOption="USER_ENTERED", body={"values": rows}).execute()

    back = get_values(svc, master_cfg["id"],
                      f"'{want_tab}'!A1:{col_letter(len(columns) + len(ext_columns))}2")
    ok = len(back) == 2 and [str(x) for x in back[1][:len(columns)]] == list(columns)
    print(f"[init-master] ヘッダー2行を書き込み / 読み返し一致={ok}", file=sys.stderr)
    return 0 if ok else 3


def main(argv=None):
    ap = argparse.ArgumentParser(description="HPBリボンKPIをMasterへ転記")
    ap.add_argument("--extract-csv", required=True, help="hpb_ribbon_extract.py の出力CSV")
    ap.add_argument("--month", required=True, help="対象年月号(例 2026年08月号)")
    ap.add_argument("--mode",
                    choices=["inspect", "calibrate", "dry-run", "apply", "init-master"],
                    default="dry-run")
    ap.add_argument("--profile", default="chokuei",
                    help="ブランド系列(既定 chokuei = 直営+サンズミライ+リラックス系)")
    args = ap.parse_args(argv)

    cfg = load_config()
    prof = profile_config(cfg, args.profile)
    master_cfg, shu_cfg = prof["master_sheet"], prof["shukyaku_sheet"]
    if master_cfg is None and args.mode != "inspect":  # noqa: E501
        raise SystemExit(
            f"プロファイル {args.profile!r} は転記先(master_sheet)が未決定。"
            "data/hpb-ribbon-config.json に書き込み先を決めてから --mode を上げること。"
            "いまは --mode inspect(集客数の結合確認)だけ動かせる。")

    columns = master_cfg["columns"] if master_cfg else []          # 既存A〜S(19列)
    ext_columns = master_cfg.get("master_ext_columns", []) if master_cfg else []
    full_columns = columns + ext_columns
    last_col = col_letter(len(full_columns)) if full_columns else "A"

    svc = sheets_service(prof["key_env"])

    if args.mode == "init-master":
        # 新規Masterの下ごしらえ。集客数も抽出CSVも要らない。
        return init_master(svc, master_cfg, columns, ext_columns)

    # 1) 集客数タブ(◯月HPB速報値)を読む
    shu_titles = list_tab_titles(svc, shu_cfg["id"])
    shu_tab = resolve_tab(shu_titles, month_tab_keywords(shu_cfg["tab_keywords"], args.month))
    shu_values = get_values(svc, shu_cfg["id"], f"'{shu_tab}'!A1:BZ400")
    shukyaku_map = build_shukyaku_map(
        shu_values,
        name_contains=shu_cfg["columns"]["store_name_header_contains"],
        count_exact=shu_cfg["columns"]["count_header_exact"],
        block_marker=shu_cfg.get("block_marker"),
        stop_prefixes=tuple(shu_cfg.get("stop_prefixes", DEFAULT_STOP_PREFIXES)),
        stop_contains=tuple(shu_cfg.get("stop_contains", ())))
    print(f"集客数タブ='{shu_tab}' 店舗={len(shukyaku_map)}", file=sys.stderr)

    # 2) 抽出CSVを読み、集客数を結合
    rows = load_extract_csv(args.extract_csv, ext_columns)
    for r in rows:
        r["年月号"] = args.month

    # リボンのZIPは全ブランドまとめて届く。転記先のMasterに合わせて絞る。
    brands = prof.get("brands")
    rows, dropped, unknown = split_by_brand(rows, brands, brand_by_store())
    if brands is not None:
        print(f"対象ブランド={brands} / 採用={len(rows)} 他系列={len(dropped)}", file=sys.stderr)
        by_brand = {}
        for _, b in dropped:
            by_brand[b] = by_brand.get(b, 0) + 1
        if by_brand:
            print(f"  [他系列につき除外] {by_brand}", file=sys.stderr)
    if unknown:
        # 院マスタに無い店舗。新店か名寄せ漏れ。黙って通さない。
        names = [r.get("店舗名") for r in unknown]
        print(f"  [院マスタに無い] {len(names)}店舗: {names[:10]}"
              f"{' …' if len(names) > 10 else ''}", file=sys.stderr)
        if brands is not None:
            print("    → 対象ブランドか判定できないので、この実行では転記しない。"
                  "data/clinics.json か data/store-name-aliases.json に足すこと。",
                  file=sys.stderr)

    rows, notes = join_shukyaku(rows, shukyaku_map)
    filled = sum(1 for r in rows if str(r["集客数"]).strip() != "")
    print(f"抽出={len(rows)}店舗 / 集客数入り={filled} / 空欄={len(rows)-filled}", file=sys.stderr)
    for kind, detail in notes:
        print(f"  [{kind}] {detail}", file=sys.stderr)

    if args.mode == "inspect":
        print("[inspect] Master列:", columns or "(転記先未決定)", file=sys.stderr)
        return 0

    # 3) Masterタブ
    m_titles = list_tab_titles(svc, master_cfg["id"])
    m_tab = resolve_tab(m_titles, [master_cfg["tab_keyword"]])
    m_values = get_values(svc, master_cfg["id"], f"'{m_tab}'!A1:{last_col}5000")
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

    matrix = build_master_matrix(rows, full_columns)
    start_row = last_data_row + 1
    a1 = f"'{m_tab}'!A{start_row}"
    print(f"書き込み先: {a1}  {len(matrix)}行 x {len(full_columns)}列(A〜{last_col})", file=sys.stderr)

    # 拡張列のヘッダー(1行目 T列〜)が未設定なら入れる。既存A〜Sヘッダーには触れない。
    header_row = m_values[0] if m_values else []
    ext_start_idx = len(columns)  # 0-based。T列 = index 19
    ext_header_present = len(header_row) > ext_start_idx and any(
        str(header_row[i]).strip() for i in range(ext_start_idx, min(len(header_row), len(full_columns))))
    if args.mode == "dry-run":
        print("[dry-run] 先頭3行(先頭6列+拡張先頭3列):", file=sys.stderr)
        for row in matrix[:3]:
            print("   ", row[:6], "...", row[ext_start_idx:ext_start_idx + 3], file=sys.stderr)
        print(f"[dry-run] 拡張ヘッダー既存={ext_header_present}(未設定なら T1〜 に列名を書く)", file=sys.stderr)
        return 0

    # apply: (必要なら)拡張ヘッダー → データ本体 → 読み返して一致確認
    if not ext_header_present:
        ext_col_letter = col_letter(ext_start_idx + 1)  # T
        svc.spreadsheets().values().update(
            spreadsheetId=master_cfg["id"], range=f"'{m_tab}'!{ext_col_letter}1",
            valueInputOption="USER_ENTERED", body={"values": [ext_columns]}).execute()
        print(f"拡張ヘッダーを {ext_col_letter}1 に書き込み", file=sys.stderr)
    svc.spreadsheets().values().update(
        spreadsheetId=master_cfg["id"], range=a1,
        valueInputOption="USER_ENTERED", body={"values": matrix}).execute()
    end_row = start_row + len(matrix) - 1
    back = get_values(svc, master_cfg["id"], f"'{m_tab}'!A{start_row}:{last_col}{end_row}")
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

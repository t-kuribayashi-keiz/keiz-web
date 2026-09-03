#!/usr/bin/env python3
"""直営+サンズミライの月次KPIを「【2026年_月次報告】集客数」に転記する。

月の途中に入れた中間値(見込み)を、月が締まったあとの速報値に差し替えるのがこの処理。
工程①②⑤を担当する。詳細は functions/kpi-aggregation/CLAUDE.md。

**既定はドライラン。** 書き込むには --apply を明示する。本番の業務シートを触るため、
既定で書き込む設計にはしない。

安全策(すべて必須。省略しない):
  1. 書き込み前に対象セルの現在値を読んで記録する(巻き戻せるように)
  2. 書き込むセルはホワイトリストで固定し、範囲外には一切書かない
  3. 書き込み後に読み返して、意図した値と一致するか照合する。不一致なら異常終了
  4. 合計行は毎回探して検証する。ハードコードしない(店舗増減で行がずれるため)
  5. 判定できない行・未知の法人名・未知の店舗名が出たら、推測せずに停止する

検証の作法: **既に人が速報値まで入れ終えた過去の月**に対して --calibrate を走らせ、
その月の行を再現できるかを見る(例: `--month 2026年7月 --calibrate`)。
当月(まだ中間値が入っている月)は答え合わせに使えない。中間値と速報値は違う数字だから。

認証: 環境変数 GCP_KPI_WRITER_KEY にサービスアカウントのJSON全文。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from store_matcher import StoreMatcher, group_of  # noqa: E402

SPREADSHEET_ID = "1Ali0uUUTnoWVv00GBYcp88-JfiPFP01Ttu5gqJ9D_Bg"
EPARK_SPREADSHEET_ID = "1TNuyQL0Wi96jdVdpiT9ZDGjw9JlncT5eaKUeiVQ9KPs"
AD_SPEND_SPREADSHEET_ID = "1aH6L_cMz95PbZs9plKYHBKv7G0LG5dFSuO0ON1mCmnM"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPARK_CORPORATIONS_PATH = os.path.join(REPO_ROOT, "data", "epark-corporations.json")
SOURCE_COLUMNS_PATH = os.path.join(REPO_ROOT, "data", "kpi-source-columns.json")
AD_SPEND_IGNORE_PATH = os.path.join(REPO_ROOT, "data", "ad-spend-ignore-rows.json")

PLAN_TAB_KEYWORDS = ["年間計画"]
DASHBOARD_TAB_KEYWORDS = ["ダッシュボード"]
AD_SPEND_TAB_KEYWORDS = ["広告費各詳細"]

# 「年間計画・目標」タブの列。2026-09-02に確定(functions/kpi-aggregation/CLAUDE.md 参照)。
# 数式が入っている列(I, K, P, T, U, AD)には**書き込まない**。上書きすると数式が消える。
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
    "stores_hpb_total": "P",  # 数式
    "stores_epark_chokuei": "Q",
    "stores_epark_sans": "R",
    "stores_epark_mirai": "S",
    "stores_epark_total": "T",  # 数式
    "seo_meo": "U",           # 数式(C-V-W-X)
    "ppc": "V",               # ③ 手入力のまま
    "meta": "W",              # ③ 手入力のまま
    "ai": "X",                # ④
    "uu_seo": "AB",
    "uu_meo": "AC",
    "uu_natural": "AD",       # 数式(AB+AC)
    "uu_ppc": "AE",
}

# ①②で書き込んでよい列だけを列挙する。ここに無い列には絶対に書かない。
# ③(PPC/META)は自動化保留、④は転記方法が未確定なので、いまは対象外。
# L列(店舗数)は栗林さんの判断で当面手動運用(2026-09-03)。出どころが未確定なまま
# 書き込むより、人が入れた値をそのまま残すほうが安全なため、ここには入れない。
WRITABLE_PLAN_KEYS = {
    "hp", "hpb", "epark",
    "stores_hpb_chokuei", "stores_hpb_sans", "stores_hpb_mirai",
    "stores_epark_chokuei", "stores_epark_sans", "stores_epark_mirai",
    "uu_seo", "uu_meo", "uu_ppc",
}

# ⑤ ダッシュボードのAG〜AO列。2026年8月の実測値9項目すべてが下記の算出式と一致して確定。
# 値そのものは「年間計画・目標」タブの1店舗当たり行から転記するのが本筋で、この式は
# 転記結果が妥当かを機械的に確かめるための照合用。
DASHBOARD_COLUMNS = [
    ("web_total", "AG"),   # = hp + hpb + epark(いずれも1店舗当たり)
    ("hp", "AH"),          # = C / L
    ("hpb", "AI"),         # = D / P
    ("epark", "AJ"),       # = E / T
    ("seo", "AK"),         # = (U + X) / L   ← SEO,MEO + AI
    ("meta", "AL"),        # = W / L
    ("ppc", "AM"),         # = V / L
    ("uu_seo", "AN"),      # = AD / L        ← 自然検索UU(SEO UU + MEO UU)
    ("uu_ppc", "AO"),      # = AE / L
]

# 合計行を探すときに、その行が本当に合計行かを確かめるためのラベル。
TOTAL_LABELS = ("合計", "総計", "計")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def normalize(text) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(text)))


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


def parse_number(value) -> float | None:
    """'1,234' や '1234' を数値に。数値でなければ None。"""
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("　", "").replace("¥", "").replace("\\", "")
    if text in ("", "-", "―", "−"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def cell(row: list, column: str):
    index = col_to_index(column)
    return row[index - 1] if len(row) >= index else ""


def column_sum_above(rows: list[list[str]], column: str, row_index: int) -> float:
    """指定行より上にある数値の合計。合計行かどうかの裏取りに使う。"""
    total = 0.0
    for row in rows[: row_index - 1]:
        number = parse_number(cell(row, column))
        if number is not None:
            total += number
    return total


def find_total_row(rows: list[list[str]], value_col_index: int) -> int:
    """合計行の行番号(1始まり)を返す。見つからない/怪しい場合は例外。

    行番号を固定で持たない理由: 店舗が増減すると合計行がずれる。ずれたまま読むと
    合計ではない1店舗分の値をKPIとして書き込んでしまい、しかもエラーが出ない。
    栗林さんからも各タブのセル位置と併せて「店舗数が変わるとこの位置も変わる」と
    明示されている。

    判定は2段構え:
      1. どこかのセルに「合計」等のラベルがある行を探し、対象列が数値であることを確かめる
      2. ラベルで決まらなければ、対象列の値が「その行より上の数値の合計」と一致する行を探す
    どちらの段でも候補が1つに絞れなければ停止する。推測して読むと、合計ではない値が
    そのままKPIになる。
    """
    column = index_to_col(value_col_index)

    labelled = [
        row_index
        for row_index, row in enumerate(rows, start=1)
        if any(any(label in str(value) for label in TOTAL_LABELS) for value in row)
        and parse_number(cell(row, column)) is not None
    ]
    if len(labelled) == 1:
        return labelled[0]

    # ラベルで決まらなかったので、値そのもので合計行を探す。
    summed = []
    for row_index, row in enumerate(rows, start=1):
        value = parse_number(cell(row, column))
        if value is None or value == 0:
            continue
        if abs(value - column_sum_above(rows, column, row_index)) < 0.5:
            summed.append(row_index)

    if len(summed) == 1:
        return summed[0]
    if not labelled and not summed:
        raise ValueError(
            f"{column}列の合計行が見つかりませんでした。「合計」等のラベルも無く、"
            "上の行の合計と一致する行もありません。シートの構造が変わった可能性があります。"
            "行番号を推測して読むのは危険なため停止します。"
        )
    raise ValueError(
        f"{column}列の合計行を1つに絞れませんでした"
        f"(ラベル一致: {labelled} / 合計一致: {summed})。"
        "どれを使うか機械的に判断できないため停止します。"
    )


def find_month_row(rows: list[list[str]], month_col: str, month_label: str) -> int:
    """「2026年8月」のような月ラベルから対象行を特定する。"""
    wanted = normalize(month_label)
    matches = [
        row_index
        for row_index, row in enumerate(rows, start=1)
        if normalize(cell(row, month_col)) == wanted
    ]
    if not matches:
        raise ValueError(f"{month_label} の行が見つかりませんでした。")
    if len(matches) > 1:
        raise ValueError(f"{month_label} の行が複数あります(行: {matches})。")
    return matches[0]


# --------------------------------------------------------------------------
# EPARK: 契約法人名から 直営 / サンズ / ミライ を数える
# --------------------------------------------------------------------------

def load_epark_groups() -> dict:
    """EPARK法人名 → 直営/サンズ/ミライ の対応表を読む。

    法人名をコードに直書きしない理由: 法人が増減したときに、設定ファイル1行の変更で
    済ませたい(ルートCLAUDE.mdの「ブランド固有の情報はdata/に切り出す」方針)。
    """
    with open(EPARK_CORPORATIONS_PATH, encoding="utf-8") as handle:
        return json.load(handle)["groups"]


def classify_epark_corporation(name: str, groups: dict) -> str:
    """契約法人名から所属グループのキーを返す。判定できなければ ValueError。

    完全一致にしないのは「株式会社 エフアール」のように空白入りの表記ゆれがあるため。
    未知の法人名を直営に寄せない: 黙って直営が1件増えても誰も気づかず、店舗数がずれる。
    """
    text = normalize(name)
    matched = [
        key
        for key, group in groups.items()
        if any(normalize(needle) in text for needle in group["match"])
    ]
    if not matched:
        raise ValueError(
            f"EPARKの契約法人名『{name}』が data/epark-corporations.json のどのグループにも"
            "該当しません。直営として数えると店舗数が静かにずれるため停止します。"
            "法人が増えたのであれば対応表に追記してください。"
        )
    if len(matched) > 1:
        raise ValueError(
            f"EPARKの契約法人名『{name}』が複数のグループに該当しました({matched})。"
            "対応表のmatch文字列が重複しています。"
        )
    return matched[0]


def count_epark_stores(rows: list[list[str]]) -> dict[str, int]:
    """EPARK掲載店舗リストの1タブ分から、直営/サンズ/ミライの店舗数を数える。

    列は A=gp / B=契約法人名 / C=施設名。ヘッダー行(B列が『契約法人名』)は飛ばす。
    """
    groups = load_epark_groups()
    counts = {key: 0 for key in groups}
    for row in rows:
        if len(row) < 2:
            continue
        corporation = str(row[1]).strip()
        if not corporation or corporation == "契約法人名":
            continue
        counts[classify_epark_corporation(corporation, groups)] += 1
    return counts


# --------------------------------------------------------------------------
# 広告費シート: 店舗名から 直営 / サンズ / ミライ を数える
# --------------------------------------------------------------------------

def load_ad_spend_ignore() -> dict:
    with open(AD_SPEND_IGNORE_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def is_ignorable_ad_spend_row(label: str, ignore: dict) -> bool:
    """店舗ではない行(集計サマリー・見出し)かどうか。"""
    text = normalize(label)
    if not text:
        return True
    if text in {normalize(x) for x in ignore["ignore_exact"]}:
        return True
    return any(normalize(needle) in text for needle in ignore["ignore_contains"])


def find_month_column(rows: list[list[str]], month_label: str, search_rows: int = 12) -> int:
    """ヘッダー行から対象月の列番号(1始まり)を探す。

    「2026年8月」「2026/8」「2026-08」のいずれの書き方でも当たるようにする。
    候補が0件でも複数でも停止する — 隣の月の列を読むと丸ごと違う数字になるため。
    """
    match = re.match(r"(\d{4})年(\d{1,2})月", month_label)
    if not match:
        raise ValueError(f"月ラベル『{month_label}』を解釈できません(例: 2026年8月)。")
    year, month = int(match.group(1)), int(match.group(2))
    wanted = {
        normalize(f"{year}年{month}月"),
        normalize(f"{year}/{month}"),
        normalize(f"{year}/{month:02d}"),
        normalize(f"{year}-{month:02d}"),
    }

    hits = set()
    for row in rows[:search_rows]:
        for col_index, value in enumerate(row, start=1):
            if normalize(value) in wanted:
                hits.add(col_index)
    if not hits:
        raise ValueError(
            f"広告費シートに {month_label} の列が見つかりませんでした。"
            f"先頭{search_rows}行にヘッダーが無い可能性があります。"
        )
    if len(hits) > 1:
        raise ValueError(
            f"{month_label} の列が複数見つかりました(列: {sorted(hits)})。"
            "隣の月を読むと数字が丸ごと変わるため停止します。"
        )
    return hits.pop()


def count_ad_spend_stores(
    rows: list[list[str]],
    month_label: str,
    matcher: StoreMatcher,
    name_col: int = 1,
) -> tuple[dict[str, int], list[str]]:
    """広告費シートの1タブ分から、対象月に金額が入っている店舗を数える。

    栗林さんの指示(2026-09-03): 広告費シートには法人を判別する列が無いので、
    店舗名を院マスタと突き合わせて判別する。ただし媒体ごとに店舗名が違う
    (HPB掲載時に整骨院→整体院、SEO目的の【冠文字】)ため、完全一致では取りこぼす。
    判定は store_matcher に任せ、ここでは数えるだけにする。

    戻り値は (グループ別の件数, 判定できなかった行のラベル)。
    判定できなかった行は呼び出し側で必ず突きつける — 黙って捨てると店舗数が減る。
    """
    ignore = load_ad_spend_ignore()
    month_col = find_month_column(rows, month_label)

    counts: dict[str, int] = {}
    unmatched: list[str] = []
    for row in rows:
        label = str(cell(row, index_to_col(name_col))).strip()
        amount = parse_number(cell(row, index_to_col(month_col)))
        if amount is None or amount == 0:
            continue
        if is_ignorable_ad_spend_row(label, ignore):
            continue
        result = matcher.match(label)
        if result["group"] is None:
            unmatched.append(f"{label}({result['how']}, 候補={result['candidates'][:3]})")
            continue
        counts[result["group"]] = counts.get(result["group"], 0) + 1
    return counts, unmatched


# --------------------------------------------------------------------------
# Sheets API
# --------------------------------------------------------------------------

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


def list_tab_titles(service, spreadsheet_id: str) -> list[str]:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="sheets.properties.title").execute()
    return [sheet["properties"]["title"] for sheet in meta.get("sheets", [])]


def _keyword_matches(title: str, keyword: str) -> bool:
    """タブ名にキーワードが含まれるか。英数字のキーワードは前後の境界も見る。

    境界を見る理由: 「HP」は「HPB」の一部なので、単純な部分一致だと
    『8月HP(速報値)』を探したつもりで『8月HPB(速報値)』にも当たってしまう。
    形式が同じなので読めてしまい、HPの欄にHPBの数字が入る事故になる。
    """
    pattern = re.escape(keyword)
    if keyword[-1:].isascii() and keyword[-1:].isalnum():
        pattern += r"(?![0-9A-Za-z])"
    if keyword[:1].isascii() and keyword[:1].isalnum():
        pattern = r"(?<![0-9A-Za-z])" + pattern
    return re.search(pattern, title) is not None


def resolve_tab(titles: list[str], keywords: list[str], label: str) -> str:
    """キーワードをすべて含むタブ名を1つに決める。0件でも複数でも停止する。

    タブ名を直書きしない理由: 月ごとにタブが増え、表記も「8月HP(速報値)」のように
    括弧が半角/全角で揺れる。違うタブを読んでも形式は同じなのでエラーにならず、
    先月の数字を今月として書き込む事故になる。
    """
    hits = [
        title
        for title in titles
        if all(_keyword_matches(normalize(title), normalize(word)) for word in keywords)
    ]
    if not hits:
        raise ValueError(f"{label} のタブが見つかりません(キーワード: {keywords})。")
    if len(hits) > 1:
        raise ValueError(f"{label} のタブ候補が複数あります({hits})。どれを読むか決められないため停止します。")
    return hits[0]


def read_tab(service, spreadsheet_id: str, title: str) -> list[list[str]]:
    result = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=f"'{title}'",
            valueRenderOption="FORMATTED_VALUE",
        )
        .execute()
    )
    return result.get("values", [])


def read_cell(service, spreadsheet_id: str, title: str, ref: str) -> str:
    values = read_tab_range(service, spreadsheet_id, f"'{title}'!{ref}")
    return values[0][0] if values and values[0] else ""


def read_tab_range(service, spreadsheet_id: str, sheet_range: str) -> list[list[str]]:
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=sheet_range, valueRenderOption="FORMATTED_VALUE")
        .execute()
    )
    return result.get("values", [])


# --------------------------------------------------------------------------
# 抽出(工程①②)
# --------------------------------------------------------------------------

def month_tab_prefix(month_label: str) -> str:
    """「2026年8月」→「8月」。タブ名は年を含まず「8月HP(速報値)」のような形。"""
    match = re.match(r"\d{4}年(\d{1,2})月", month_label)
    if not match:
        raise ValueError(f"月ラベル『{month_label}』を解釈できません(例: 2026年8月)。")
    return f"{int(match.group(1))}月"


def load_source_columns() -> dict:
    with open(SOURCE_COLUMNS_PATH, encoding="utf-8") as handle:
        return json.load(handle)["sources"]


def extract_from_soku_tab(service, month_label: str, source_key: str) -> dict[str, float]:
    """速報値タブの合計行から値を読む。"""
    sources = load_source_columns()
    source = sources[source_key]
    columns = {key: col for key, col in source["columns"].items() if col}
    missing = [key for key, col in source["columns"].items() if not col]
    if missing:
        raise ValueError(
            f"速報値タブ『{source_key}』の列 {missing} が未確定です "
            f"(data/kpi-source-columns.json)。{source.get('_todo', '')}"
        )

    titles = list_tab_titles(service, SPREADSHEET_ID)
    keywords = [month_tab_prefix(month_label)] + source["tab_keywords"]
    title = resolve_tab(titles, keywords, f"{month_label} の{source_key}速報値")
    rows = read_tab(service, SPREADSHEET_ID, title)

    first_column = next(iter(columns.values()))
    total_row_index = find_total_row(rows, col_to_index(first_column))
    total_row = rows[total_row_index - 1]
    checksum = column_sum_above(rows, first_column, total_row_index)
    total_value = parse_number(cell(total_row, first_column))
    print(f"  {title}: 合計行 = {total_row_index}行目 "
          f"({first_column}={total_value} / 上の行の合計={checksum:g})")
    if total_value is not None and abs(total_value - checksum) >= 0.5:
        print("    ※ 合計行の値が上の行の合計と一致しません。合計行の判定を疑うこと。")

    values = {}
    for key, column in columns.items():
        number = parse_number(cell(total_row, column))
        if number is None:
            raise ValueError(
                f"{title} の {column}{total_row_index} が数値ではありません "
                f"(値: {cell(total_row, column)!r})。合計行の判定を誤っている可能性があります。"
            )
        values[key] = number
        print(f"    {key}: {column}{total_row_index} = {number:g}")
    return values


def extract_store_counts(service, month_label: str, matcher: StoreMatcher) -> dict[str, float]:
    """工程②。HPBは広告費シート、EPARKは専用シートから店舗数を数える。"""
    values: dict[str, float] = {}

    # --- HPB: 広告費シートで対象月に金額が入っている店舗 ---
    titles = list_tab_titles(service, AD_SPEND_SPREADSHEET_ID)
    title = resolve_tab(titles, AD_SPEND_TAB_KEYWORDS, "広告費各詳細")
    rows = read_tab(service, AD_SPEND_SPREADSHEET_ID, title)
    counts, unmatched = count_ad_spend_stores(rows, month_label, matcher)
    if unmatched:
        raise ValueError(
            "広告費シートで院マスタに突き合わせられなかった行があります。"
            "直営として数えると店舗数が静かにずれるため停止します。"
            "店舗名の表記ゆれなら data/clinics.json の名称を見直し、店舗でない行なら "
            "data/ad-spend-ignore-rows.json に追記してください。\n  - "
            + "\n  - ".join(unmatched)
        )
    print(f"  {title}: {month_label} に金額のある店舗 = {counts}")
    values["stores_hpb_chokuei"] = counts.get("直営", 0)
    values["stores_hpb_sans"] = counts.get("サンズ", 0)
    values["stores_hpb_mirai"] = counts.get("ミライ", 0)

    # --- EPARK: 対象月のタブの契約法人名 ---
    titles = list_tab_titles(service, EPARK_SPREADSHEET_ID)
    match = re.match(r"(\d{4})年(\d{1,2})月", month_label)
    year, month = int(match.group(1)), int(match.group(2))
    title = resolve_tab(titles, [f"{year}/{month}"], f"EPARK {month_label}")
    rows = read_tab(service, EPARK_SPREADSHEET_ID, title)
    epark = count_epark_stores(rows)
    print(f"  {title}: {epark}")
    values["stores_epark_chokuei"] = epark["chokuei"]
    values["stores_epark_sans"] = epark["sans"]
    values["stores_epark_mirai"] = epark["mirai"]
    return values


def extract(service, month_label: str) -> dict[str, float]:
    matcher = StoreMatcher()
    values: dict[str, float] = {}
    print("① 速報値タブから集客数・UU数を読む")
    values.update(extract_from_soku_tab(service, month_label, "hp"))
    values.update(extract_from_soku_tab(service, month_label, "hpb"))
    values.update(extract_from_soku_tab(service, month_label, "epark"))
    print("② 店舗数を数える")
    values.update(extract_store_counts(service, month_label, matcher))
    # L列(店舗数)はHP速報値タブの店舗行数。速報値タブの構造が未確認なので、
    # 確認できるまでは書き込み対象から外す(未確定のまま書くと誰も気づかずに狂う)。
    return values


# --------------------------------------------------------------------------
# 書き込みと検証
# --------------------------------------------------------------------------

def snapshot(service, cells: dict[str, str]) -> dict[str, str]:
    """書き込み前の現在値を読んで返す。巻き戻しの手掛かりとしてログに残す。"""
    return {
        label: read_cell(service, SPREADSHEET_ID, title, ref)
        for label, (title, ref) in cells.items()
    }


def verify(service, planned: dict[str, tuple[str, str, object]]) -> list[str]:
    """書き込み後に読み返し、一致しないものを返す。"""
    mismatches = []
    for label, (title, ref, expected) in planned.items():
        actual = read_cell(service, SPREADSHEET_ID, title, ref)
        if parse_number(actual) != parse_number(expected):
            mismatches.append(f"{label} ({title}!{ref}): 期待={expected} / 実際={actual}")
    return mismatches


def calibrate(service, month_label: str, extracted: dict[str, float]) -> int:
    """既に人が速報値を入れ終えた月の行と、抽出結果を突き合わせる。

    ここが全項目一致してはじめて、この自動化を本番で使ってよいとみなす。
    当月(まだ中間値が入っている月)を指定しても意味が無い — 中間値と速報値は違う数字。
    """
    titles = list_tab_titles(service, SPREADSHEET_ID)
    plan_title = resolve_tab(titles, PLAN_TAB_KEYWORDS, "年間計画・目標")
    rows = read_tab(service, SPREADSHEET_ID, plan_title)
    row_index = find_month_row(rows, PLAN_COLUMNS["month"], month_label)
    row = rows[row_index - 1]

    print(f"\n照合: {plan_title} の {row_index}行目({month_label})")
    mismatches = []
    for key in sorted(extracted):
        column = PLAN_COLUMNS.get(key)
        if column is None:
            continue
        current = parse_number(cell(row, column))
        got = extracted[key]
        mark = "OK " if current == got else "NG "
        if current != got:
            mismatches.append(f"{key} ({column}{row_index}): シート={current} / 抽出={got}")
        print(f"  {mark}{key:24s} {column}{row_index}  シート={current}  抽出={got}")

    if mismatches:
        print("\n一致しませんでした:")
        for line in mismatches:
            print(f"  - {line}")
        print("\n抽出ロジックかシートの構造のどちらかが想定と違います。本番書き込みはしないこと。")
        return 1
    print("\n全項目一致。この抽出ロジックは、人が入れた1か月分を再現できています。")
    return 0


# --------------------------------------------------------------------------
# 構造調査(読み取りのみ)
# --------------------------------------------------------------------------

def inspect(service, month_label: str) -> int:
    """シートの構造を出すだけのモード。書き込みは一切しない。

    推測でコードを直すより、実際の並びを1回見るほうが速くて確実。
    タブ名の表記ゆれ(「7月HPB (速報値) 」の末尾空白、「7月Epark（速報値)」の全角括弧など)は
    実物を見ないと分からない。
    """
    match = re.match(r"(\d{4})年(\d{1,2})月", month_label)
    year, month = int(match.group(1)), int(match.group(2))

    print("=== 広告費シート「広告費各詳細」の先頭15行 ===")
    titles = list_tab_titles(service, AD_SPEND_SPREADSHEET_ID)
    title = resolve_tab(titles, AD_SPEND_TAB_KEYWORDS, "広告費各詳細")
    rows = read_tab(service, AD_SPEND_SPREADSHEET_ID, title)
    print(f"タブ: {title!r} / 行数={len(rows)}")
    for row_index, row in enumerate(rows[:15], start=1):
        cells = [
            f"{index_to_col(i)}{row_index}={value!r}"
            for i, value in enumerate(row[:14], start=1)
            if str(value).strip()
        ]
        print(f"  [{row_index}行] " + (" | ".join(cells) if cells else "(空)"))

    print(f"\n=== 先頭15行のうち {year} を含むセル(最大30件) ===")
    hits = 0
    for row_index, row in enumerate(rows[:15], start=1):
        for col_index, value in enumerate(row, start=1):
            if str(year) in str(value) and hits < 30:
                print(f"  {index_to_col(col_index)}{row_index} = {value!r}")
                hits += 1
    if not hits:
        print("  (該当なし。年月ヘッダーが16行目以降にあるか、別の書き方をしている)")

    print(f"\n=== KPIシートの「{month}月」を含むタブ ===")
    for name in list_tab_titles(service, SPREADSHEET_ID):
        if f"{month}月" in normalize(name):
            print(f"  {name!r}")

    print(f"\n=== {month_label} の 速報値 / 確定値 の合計値の比較 ===")
    sources = load_source_columns()
    for source_key, source in sources.items():
        for kind in ("速報値", "確定値"):
            keywords = [month_tab_prefix(month_label)] + [
                kind if word == "速報値" else word for word in source["tab_keywords"]
            ]
            try:
                titles = list_tab_titles(service, SPREADSHEET_ID)
                tab = resolve_tab(titles, keywords, f"{source_key} {kind}")
                tab_rows = read_tab(service, SPREADSHEET_ID, tab)
                column = next(iter(source["columns"].values()))
                total_row = find_total_row(tab_rows, col_to_index(column))
                value = parse_number(cell(tab_rows[total_row - 1], column))
                print(f"  {source_key:6s} {kind}: {tab!r} {column}{total_row} = {value}")
            except ValueError as error:
                print(f"  {source_key:6s} {kind}: 読めず — {error}")

    print(f"\n=== 「年間計画・目標」の {month_label} の行 ===")
    titles = list_tab_titles(service, SPREADSHEET_ID)
    plan_title = resolve_tab(titles, PLAN_TAB_KEYWORDS, "年間計画・目標")
    plan_rows = read_tab(service, SPREADSHEET_ID, plan_title)
    row_index = find_month_row(plan_rows, PLAN_COLUMNS["month"], month_label)
    row = plan_rows[row_index - 1]
    print(f"タブ: {plan_title!r} / {row_index}行目")
    for key, column in PLAN_COLUMNS.items():
        print(f"  {key:22s} {column}{row_index} = {cell(row, column)!r}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", required=True, help="対象月ラベル(例: 2026年8月)")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="実際に書き込む。指定しなければドライラン(書き込む内容をログに出すだけ)",
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help=(
            "書き込まず、抽出結果を『既に人が速報値を入れ終えた月』の行と突き合わせる。"
            "全項目一致してはじめて本番で使ってよい"
        ),
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="書き込まず、シートの構造(タブ名・ヘッダー行・合計値)を出すだけ",
    )
    args = parser.parse_args()

    if args.inspect:
        return inspect(build_service(), args.month)

    if args.calibrate and args.apply:
        fail("--calibrate と --apply は同時に指定できません。答え合わせと書き込みは分ける。")

    print(f"対象月: {args.month}")
    print(f"モード: {'照合のみ' if args.calibrate else ('本番書き込み' if args.apply else 'ドライラン(書き込まない)')}")
    print()

    service = build_service()
    try:
        extracted = extract(service, args.month)
    except ValueError as error:
        fail(str(error))
        return 1

    if args.calibrate:
        return calibrate(service, args.month, extracted)

    titles = list_tab_titles(service, SPREADSHEET_ID)
    plan_title = resolve_tab(titles, PLAN_TAB_KEYWORDS, "年間計画・目標")
    rows = read_tab(service, SPREADSHEET_ID, plan_title)
    row_index = find_month_row(rows, PLAN_COLUMNS["month"], args.month)

    planned = {}
    for key, value in sorted(extracted.items()):
        if key not in WRITABLE_PLAN_KEYS:
            print(f"  skip {key}(書き込み対象外)")
            continue
        ref = f"{PLAN_COLUMNS[key]}{row_index}"
        planned[key] = (plan_title, ref, value)

    print(f"\n書き込み先: {plan_title} の {row_index}行目")
    before = snapshot(service, {key: (title, ref) for key, (title, ref, _) in planned.items()})
    for key, (title, ref, value) in sorted(planned.items()):
        print(f"  {key:24s} {ref}  現在={before[key]!r} → {value:g}")

    if not args.apply:
        print("\nドライランのため書き込みませんでした。--apply で実行します。")
        return 0

    service.spreadsheets().values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={
            "valueInputOption": "USER_ENTERED",
            "data": [
                {"range": f"'{title}'!{ref}", "values": [[value]]}
                for _, (title, ref, value) in sorted(planned.items())
            ],
        },
    ).execute()

    mismatches = verify(service, planned)
    if mismatches:
        print("\n書き込み後の読み返しが一致しませんでした:", file=sys.stderr)
        for line in mismatches:
            print(f"  - {line}", file=sys.stderr)
        print(f"\n書き込み前の値: {before}", file=sys.stderr)
        return 1

    print("\n書き込み後の読み返しも一致しました。")
    print(f"書き込み前の値(巻き戻し用): {before}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

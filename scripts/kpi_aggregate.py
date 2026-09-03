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

from store_matcher import StoreMatcher, group_of, normalize_store_name  # noqa: E402

SPREADSHEET_ID = "1Ali0uUUTnoWVv00GBYcp88-JfiPFP01Ttu5gqJ9D_Bg"
EPARK_SPREADSHEET_ID = "1TNuyQL0Wi96jdVdpiT9ZDGjw9JlncT5eaKUeiVQ9KPs"
AD_SPEND_SPREADSHEET_ID = "1aH6L_cMz95PbZs9plKYHBKv7G0LG5dFSuO0ON1mCmnM"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPARK_CORPORATIONS_PATH = os.path.join(REPO_ROOT, "data", "epark-corporations.json")
SOURCE_COLUMNS_PATH = os.path.join(REPO_ROOT, "data", "kpi-source-columns.json")
REFERRAL_SOURCES_PATH = os.path.join(REPO_ROOT, "data", "referral-sources.json")
AD_SPEND_IGNORE_PATH = os.path.join(REPO_ROOT, "data", "ad-spend-ignore-rows.json")

PLAN_TAB_KEYWORDS = ["年間計画"]
# 「年間計画・目標」タブには同じ月の行が複数ある(全体数 / 1店舗当たり ほか)。
# ①②が書き込むのは全体数のブロック。A列の結合セルに入っているブロック名で絞る。
PLAN_BLOCK_TOTAL = "全体数"
PLAN_BLOCK_PER_STORE = "1店舗当たり"
# ダッシュボードの年月はA列。
DASHBOARD_MONTH_COLUMN = "A"

# 工程⑥ Googleトレンド。「年間計画・目標」タブの右端にある2つのブロック。
# AN=年月 / AO〜AS=整骨院・整体・腰痛・肩こり・骨盤矯正 / AT=5キーワード平均。
# 下のブロックは「2025/1整骨院で正規化」したもので、上のブロックから機械的に導ける
# (2025/1と2026/7・8で検算済み)。どこまでが数式でどこからが手入力かは実物を見て決める。
TRENDS_COLUMNS = ["AN", "AO", "AP", "AQ", "AR", "AS", "AT"]
TRENDS_HEADER_ROW = 2          # AO2:AS2 にキーワード名が入っている
TRENDS_FIRST_ROW = 3           # 2025年1月
TRENDS_LAST_ROW = 26           # 2026年12月
TRENDS_MONTH_COLUMN = "AN"
TRENDS_VALUE_COLUMNS = ["AO", "AP", "AQ", "AR", "AS"]
# 2026-09-03に数式を読んで確認した、書き込んではいけない範囲:
#   AT3:AT26        = AVERAGE(AO{n}:AS{n})
#   AO30:AT53       = AO{n-27}/$AO$3*100  (2025/1整骨院で正規化したブロック)
# つまり実データが要るのは AO3:AS26 だけで、残りは自動で追随する。
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
    "referral", "offline_total", "ai",          # ④
    "stores_hpb_chokuei", "stores_hpb_sans", "stores_hpb_mirai",
    "stores_epark_chokuei", "stores_epark_sans", "stores_epark_mirai",
    "uu_seo", "uu_meo", "uu_ppc",
}

# ⑤ ダッシュボードのAG〜AO列。2026年8月の実測値9項目すべてが下記の算出式と一致して確定。
# 値そのものは「年間計画・目標」タブの1店舗当たり行から転記するのが本筋で、この式は
# 転記結果が妥当かを機械的に確かめるための照合用。
# 転記元は「年間計画・目標」タブの1店舗当たりブロックの行。ただしこのブロックは
# 全体数ブロックと列の意味が違う(店舗数の列を別の指標に使い回している)ので、
# 独自の対応表が要る。2026年8月の実データで1列ずつ確認した(2026-09-03)。
#   (ダッシュボードの列, 1店舗当たり行の列たち, 全体数の行から検算する式)
DASHBOARD_COLUMNS = [
    ("web_total", "AG", ["C", "D", "E"], lambda t: t["C"] / t["L"] + t["D"] / t["P"] + t["E"] / t["T"]),
    ("hp",        "AH", ["C"],           lambda t: t["C"] / t["L"]),
    ("hpb",       "AI", ["D"],           lambda t: t["D"] / t["P"]),
    ("epark",     "AJ", ["E"],           lambda t: t["E"] / t["T"]),
    ("seo",       "AK", ["L", "Q"],      lambda t: (t["U"] + t["X"]) / t["L"]),   # SEO,MEO + AI
    ("meta",      "AL", ["P"],           lambda t: t["W"] / t["L"]),
    ("ppc",       "AM", ["O"],           lambda t: t["V"] / t["L"]),
    ("uu_seo",    "AN", ["U"],           lambda t: t["AD"] / t["L"]),             # 自然検索UU
    ("uu_ppc",    "AO", ["V"],           lambda t: t["AE"] / t["L"]),
]

# 検算に使う全体数ブロックの列。X(AI集客数)だけは未入力の月があるので0として扱う。
CHECK_COLUMNS = ("C", "D", "E", "L", "P", "T", "U", "V", "W", "X", "AD", "AE")
CHECK_OPTIONAL = ("X",)
# 転記元と検算値のずれの許容幅。両者が別経路で同じ数字に行き着くことを確かめるのが目的で、
# 小数第1位までしか表示されない値も混ざるため、ぴったり一致は求めない。
DASHBOARD_TOLERANCE = 0.05

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


def block_label_at(rows: list[list[str]], row_index: int, label_col: str = "A") -> str:
    """その行が属するブロックの名前。

    「年間計画・目標」タブは同じ月が何度も出てくる(全体数 / 1店舗当たり / ほか)。
    ブロック名はA列の結合セルなので、値が入っているのは先頭行だけ。上に遡って探す。
    """
    for index in range(row_index, 0, -1):
        value = str(cell(rows[index - 1], label_col)).strip()
        if value:
            return value
    return ""


def find_month_row(
    rows: list[list[str]],
    month_col: str,
    month_label: str,
    block_label: str | None = None,
) -> int:
    """「2026年8月」のような月ラベルから対象行を特定する。

    同じ月の行が複数あるので、ブロック名(A列)でも絞る。絞っても1つに決まらなければ
    停止する — 1店舗当たりの行に全体数を書き込むと、桁が2つ違う値が入る。
    """
    wanted = normalize(month_label)
    matches = [
        row_index
        for row_index, row in enumerate(rows, start=1)
        if normalize(cell(row, month_col)) == wanted
    ]
    if block_label:
        matches = [
            row_index
            for row_index in matches
            if normalize(block_label) in normalize(block_label_at(rows, row_index))
        ]

    if not matches:
        raise ValueError(
            f"{month_label}"
            + (f"(ブロック「{block_label}」)" if block_label else "")
            + " の行が見つかりませんでした。"
        )
    if len(matches) > 1:
        labels = {row_index: block_label_at(rows, row_index) for row_index in matches}
        raise ValueError(
            f"{month_label} の行が複数あります({labels})。"
            "どの行に書くか機械的に決められないため停止します。"
        )
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


def find_month_column(rows: list[list[str]], month_label: str, search_rows: int = 15) -> int:
    """ヘッダー行から対象月の列番号(1始まり)を探す。

    広告費シートのヘッダーは「年は1月の列にしか入っていない」形:

        B1='2017年\n1月'  C1='\n２月'  D1='\n３月' ... N1='2018年\n１月'

    つまり「2026年7月」という文字列はシートのどこにも存在しない。年の列を見つけて、
    そこから(月-1)だけ右に数える。数えっぱなしにはせず、**その列の見出しが本当に
    「7月」かを確認してから**使う。1列ずれると隣の月の金額を数えることになり、
    店舗数が丸ごと変わる。しかも金額は入っているのでエラーにはならない。

    月は全角数字(「２月」「１０月」)で書かれているが、normalize()のNFKCで半角に揃う。
    """
    match = re.match(r"(\d{4})年(\d{1,2})月", month_label)
    if not match:
        raise ValueError(f"月ラベル『{month_label}』を解釈できません(例: 2026年8月)。")
    year, month = int(match.group(1)), int(match.group(2))

    january = normalize(f"{year}年1月")
    direct = normalize(f"{year}年{month}月")
    january_cols, direct_cols = set(), set()
    for row in rows[:search_rows]:
        for col_index, value in enumerate(row, start=1):
            text = normalize(value)
            if text == january:
                january_cols.add(col_index)
            elif text == direct:
                direct_cols.add(col_index)

    if direct_cols:
        candidates = direct_cols
    elif january_cols:
        candidates = {col + (month - 1) for col in january_cols}
    else:
        raise ValueError(
            f"広告費シートに {year}年 の見出しが見つかりませんでした"
            f"(先頭{search_rows}行を検索)。ヘッダーの位置か書き方が変わった可能性があります。"
        )

    if len(candidates) > 1:
        raise ValueError(
            f"{month_label} の列が複数見つかりました(列: {sorted(candidates)})。"
            "隣の月を読むと数字が丸ごと変わるため停止します。"
        )
    column = candidates.pop()

    # 数えた先が本当に対象月かを見出しで確認する。ずれていても金額は入っているので、
    # 確認しないと「隣の月の店舗数」が何食わぬ顔でKPIになる。
    wanted = {normalize(f"{month}月"), direct}
    seen = [
        normalize(cell(row, index_to_col(column)))
        for row in rows[:search_rows]
        if normalize(cell(row, index_to_col(column)))
    ]
    if not any(text in wanted for text in seen):
        raise ValueError(
            f"{month_label} の列として {index_to_col(column)}列 を割り出しましたが、"
            f"その列の見出しが「{month}月」ではありません(見えているのは {seen[:5]})。"
            "列の数え方が合っていないため停止します。"
        )
    return column


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


# バックアップ・複製のタブ。実データと同じ形なので読めてしまい、しかも中身は古い。
# 「2026年Web集客KPI管理ダッシュボード のコピー」「〜 BK0604」が実在する(2026-09-03)。
TAB_EXCLUDE_KEYWORDS = ("コピー", "copy", "バックアップ", "backup", "bk", "旧", "old", "退避")


def is_backup_tab(title: str) -> bool:
    text = normalize(title).casefold()
    return any(word in text for word in TAB_EXCLUDE_KEYWORDS)


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
        and not is_backup_tab(title)
    ]
    if not hits:
        raise ValueError(f"{label} のタブが見つかりません(キーワード: {keywords})。")
    if len(hits) > 1:
        raise ValueError(f"{label} のタブ候補が複数あります({hits})。どれを読むか決められないため停止します。")
    return hits[0]


def read_tab(service, spreadsheet_id: str, title: str, raw: bool = False) -> list[list[str]]:
    """タブ全体を読む。

    raw=True は書式を通さない生の値。ダッシュボードへの転記元は小数第1位までしか
    表示されないため、表示値をそのまま書くと精度が落ちる(14.533... が 14.5 になる)。
    """
    result = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=f"'{title}'",
            valueRenderOption="UNFORMATTED_VALUE" if raw else "FORMATTED_VALUE",
        )
        .execute()
    )
    return result.get("values", [])


def read_cell(service, spreadsheet_id: str, title: str, ref: str) -> str:
    values = read_tab_range(service, spreadsheet_id, f"'{title}'!{ref}")
    return values[0][0] if values and values[0] else ""


def read_tab_range(
    service,
    spreadsheet_id: str,
    sheet_range: str,
    render: str = "FORMATTED_VALUE",
) -> list[list[str]]:
    """範囲を読む。render="FORMULA" にすると、数式が入っているセルは数式そのものが返る。

    数式かどうかを見分けられないと、自動計算されるセルを定数で上書きして数式を壊す。
    """
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=sheet_range, valueRenderOption=render)
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
    print("④ 紹介・オフライン合計・AI を3ブランドから読む")
    values.update(extract_referral(service, month_label))
    # L列(店舗数)はHP速報値タブの店舗行数。速報値タブの構造が未確認なので、
    # 確認できるまでは書き込み対象から外す(未確定のまま書くと誰も気づかずに狂う)。
    return values


# --------------------------------------------------------------------------
# 書き込みと検証
# --------------------------------------------------------------------------

# Sheets APIの読み取りは「1分あたり60回」で頭打ちになる。⑥は100セルを触るので、
# 1セル1リクエストだと確実に超える(実際に429で止まった)。まとめて読む。
BATCH_READ_CHUNK = 50


def read_cells(service, refs: list[tuple[str, str]]) -> list[str]:
    """(タブ名, セル)のリストをまとめて読む。並び順は入力どおり。"""
    values: list[str] = []
    for start in range(0, len(refs), BATCH_READ_CHUNK):
        chunk = refs[start:start + BATCH_READ_CHUNK]
        result = (
            service.spreadsheets()
            .values()
            .batchGet(
                spreadsheetId=SPREADSHEET_ID,
                ranges=[f"'{title}'!{ref}" for title, ref in chunk],
                valueRenderOption="FORMATTED_VALUE",
            )
            .execute()
        )
        for value_range in result.get("valueRanges", []):
            rows = value_range.get("values", [])
            values.append(rows[0][0] if rows and rows[0] else "")
    return values


def snapshot(service, cells: dict[str, str]) -> dict[str, str]:
    """書き込み前の現在値を読んで返す。巻き戻しの手掛かりとしてログに残す。"""
    labels = list(cells)
    values = read_cells(service, [cells[label] for label in labels])
    return dict(zip(labels, values))


def values_match(actual, expected) -> bool:
    """読み返した値が、書いた値と同じとみなせるか。

    完全一致にできない理由: 読み返しは表示用の値で、有効数字10桁程度に丸められる
    (14.533333333333333 と書いて 14.53333333 が返る)。整数の転記では完全一致するが、
    ⑤の1店舗当たりの数字は割り算の結果なので必ずずれる。
    丸め以上のずれは見逃したくないので、許容幅は丸め幅ぎりぎりに絞る。
    """
    got, want = parse_number(actual), parse_number(expected)
    if got is None or want is None:
        return False
    return abs(got - want) <= max(1e-7, abs(want) * 1e-7)


def write_cells(service, planned: dict[str, tuple[str, str, object]]) -> None:
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


def verify(service, planned: dict[str, tuple[str, str, object]]) -> list[str]:
    """書き込み後に読み返し、一致しないものを返す。"""
    labels = list(planned)
    actuals = read_cells(service, [(planned[label][0], planned[label][1]) for label in labels])
    mismatches = []
    for label, actual in zip(labels, actuals):
        title, ref, expected = planned[label]
        if not values_match(actual, expected):
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
    row_index = find_month_row(rows, PLAN_COLUMNS["month"], month_label, PLAN_BLOCK_TOTAL)
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
        for kind in ("中間値", "速報値", "確定値"):
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
    wanted = normalize(month_label)
    candidates = [
        row_index
        for row_index, row in enumerate(plan_rows, start=1)
        if normalize(cell(row, PLAN_COLUMNS["month"])) == wanted
    ]
    print(f"タブ: {plan_title!r} / {month_label}の行: {candidates}")
    for row_index in candidates:
        row = plan_rows[row_index - 1]
        print(f"\n  [{row_index}行] ブロック={block_label_at(plan_rows, row_index)!r}")
        filled = [
            f"{index_to_col(i)}={value!r}"
            for i, value in enumerate(row[:40], start=1)
            if str(value).strip()
        ]
        print("    " + " | ".join(filled))

    print("\n=== Googleトレンドのブロック(AN〜AT)。数式か定数かを見る ===")
    formulas = read_tab_range(
        service, SPREADSHEET_ID, f"'{plan_title}'!AN1:AT56", render="FORMULA"
    )
    for row_index, row in enumerate(formulas, start=1):
        filled = [
            f"{TRENDS_COLUMNS[i]}={value!r}"
            for i, value in enumerate(row[: len(TRENDS_COLUMNS)])
            if str(value).strip()
        ]
        if filled:
            print(f"  [{row_index}行] " + " | ".join(filled))

    print(f"\n=== ダッシュボードの {month_label} の行 ===")
    dash_title = resolve_tab(titles, DASHBOARD_TAB_KEYWORDS, "ダッシュボード")
    dash_rows = read_tab(service, SPREADSHEET_ID, dash_title)
    print(f"タブ: {dash_title!r} / 行数={len(dash_rows)}")
    header = next(
        (r for r in dash_rows[:5] if any("実績" in str(v) for v in r)),
        dash_rows[0] if dash_rows else [],
    )
    for _, column, _, _ in DASHBOARD_COLUMNS:
        print(f"  {column}: 見出し={cell(header, column)!r}")
    for row_index, row in enumerate(dash_rows, start=1):
        if normalize(cell(row, "A")) == normalize(month_label):
            print(f"  [{row_index}行] " + " | ".join(
                f"{column}={cell(row, column)!r}" for _, column, _, _ in DASHBOARD_COLUMNS
            ))
    return 0


# --------------------------------------------------------------------------
# 工程⑤ ダッシュボードへの転記
# --------------------------------------------------------------------------

def build_dashboard_values(
    plan_rows: list[list],
    plan_rows_raw: list[list],
    month_label: str,
) -> dict[str, float]:
    """1店舗当たりの行からダッシュボードの9項目を組み立て、全体数の行で検算する。

    転記元は1店舗当たりの行(栗林さんの工程⑤の指示どおり)。それを鵜呑みにせず、
    全体数の行から別経路で計算した値と突き合わせる。**分母がHPBとEPARKだけ違う**
    (それぞれの掲載店舗数)のが罠で、全部を店舗数Lで割っても桁は合うため、
    間違っていても目視では気づけない。

    行の特定は表示値(`plan_rows`)、値の読み取りは生値(`plan_rows_raw`)と分ける。
    生値だと月のセルが「2026年8月」という文字列では返らず(日付として保持されている)、
    月ラベルで行を探せないため。同じタブなので行番号は共通。
    """
    per_store_index = find_month_row(
        plan_rows, PLAN_COLUMNS["month"], month_label, PLAN_BLOCK_PER_STORE
    )
    total_index = find_month_row(
        plan_rows, PLAN_COLUMNS["month"], month_label, PLAN_BLOCK_TOTAL
    )
    per_store_row = plan_rows_raw[per_store_index - 1]
    total_row = plan_rows_raw[total_index - 1]

    totals = {}
    for column in CHECK_COLUMNS:
        number = parse_number(cell(total_row, column))
        if number is None:
            if column in CHECK_OPTIONAL:
                number = 0.0
            else:
                raise ValueError(
                    f"全体数の行の {column}列 が数値ではありません(値: {cell(total_row, column)!r})。"
                    "検算できないため停止します。"
                )
        totals[column] = number

    values, mismatches = {}, []
    for key, dashboard_col, source_cols, check in DASHBOARD_COLUMNS:
        parts = []
        for column in source_cols:
            number = parse_number(cell(per_store_row, column))
            if number is None:
                raise ValueError(
                    f"1店舗当たりの行の {column}列 が数値ではありません"
                    f"(値: {cell(per_store_row, column)!r})。{key} を転記できないため停止します。"
                )
            parts.append(number)
        transcribed = sum(parts)
        expected = check(totals)
        mark = "OK " if abs(transcribed - expected) <= DASHBOARD_TOLERANCE else "NG "
        print(f"  {mark}{key:10s} → {dashboard_col}  転記元={transcribed:.4g}  検算={expected:.4g}")
        if mark == "NG ":
            mismatches.append(
                f"{key} ({dashboard_col}): 1店舗当たりの行={transcribed} / 全体数から計算={expected}"
            )
        values[key] = transcribed

    if mismatches:
        raise ValueError(
            "1店舗当たりの行と、全体数の行からの計算が一致しませんでした。"
            "どちらかの列の対応が想定と違うため停止します。\n  - " + "\n  - ".join(mismatches)
        )
    return values


# --------------------------------------------------------------------------
# 工程⑥ Googleトレンド(CSVからの転記)
# --------------------------------------------------------------------------

def parse_month_key(text) -> tuple[int, int] | None:
    """「2025/1」「2025-01」「2025年1月」「2025-01-01」を (年, 月) にする。"""
    match = re.search(r"(\d{4})\s*[-/年]\s*(\d{1,2})", str(text))
    return (int(match.group(1)), int(match.group(2))) if match else None


def parse_trends_number(text) -> float | None:
    """Googleトレンドの値。1未満は「<1」と書かれるので0として扱う。"""
    value = str(text).strip()
    if value in ("", "-"):
        return None
    if value.startswith("<"):
        return 0.0
    return parse_number(value)


def parse_trends_csv(text: str, keywords: list[str]) -> dict[tuple[int, int], dict[str, float]]:
    """GoogleトレンドのCSV(multiTimeline.csv)を月→キーワード→値にする。

    列の対応はCSVの見出しに含まれるキーワード名で取る。位置で取ると、比較の並び順が
    変わったときに黙って別のキーワードの数字が入る。見出しは
    「整骨院: (日本)」のような形なので部分一致で見る。

    キーワードはシートのAO2:AS2から渡ってくる。**シートが正**とし、CSV側にそれが
    無ければ止める。
    """
    rows = [line.split(",") for line in text.splitlines()]
    header_index = None
    for index, row in enumerate(rows):
        if sum(1 for keyword in keywords if any(keyword in c for c in row)) >= len(keywords):
            header_index = index
            break
    if header_index is None:
        preview = "\n".join(text.splitlines()[:8])
        raise ValueError(
            f"CSVに5キーワード {keywords} をすべて含む見出し行が見つかりませんでした。"
            "5つを1つの比較で取得したCSVか確認してください"
            f"(先頭8行:\n{preview}\n)。"
        )

    header = rows[header_index]
    column_of = {}
    for keyword in keywords:
        hits = [i for i, cell_text in enumerate(header) if keyword in cell_text]
        if len(hits) != 1:
            raise ValueError(
                f"CSVの見出しでキーワード『{keyword}』に対応する列を1つに決められません"
                f"(該当列: {hits} / 見出し: {header})。"
            )
        column_of[keyword] = hits[0]

    # 週次のCSVを月次として書き込ませない。GoogleトレンドはUIで指定した期間が短いと
    # 週次で返す(2025/1〜2026/8の20か月では週次だった)。週を月に畳んでも、
    # トレンド自身の月次出力は再現できない(2026-09-03に検証: 最大誤差10〜13、
    # 完全一致は25%)。**桁は合うので目視では気づけない。**
    granularity = str(header[0]).strip()
    if granularity and not any(word in granularity for word in ("月", "Month")):
        raise ValueError(
            f"CSVの粒度が月次ではありません(1列目の見出し: {granularity!r})。"
            "Googleトレンドは期間が短いと週次で返します。期間を『過去5年』など長めにして、"
            "1列目が『月』のCSVを取得し直してください。"
            "週を月に平均しても、トレンド自身の月次出力は再現できません。"
        )

    parsed: dict[tuple[int, int], dict[str, float]] = {}
    for row in rows[header_index + 1:]:
        if not row or not row[0].strip():
            continue
        month = parse_month_key(row[0])
        if month is None:
            continue
        values = {}
        for keyword, index in column_of.items():
            number = parse_trends_number(row[index]) if index < len(row) else None
            if number is None:
                raise ValueError(
                    f"{month[0]}年{month[1]}月 の『{keyword}』が数値ではありません"
                    f"(行: {row})。"
                )
            values[keyword] = number
        parsed[month] = values

    if not parsed:
        raise ValueError("CSVから月次の行を1つも読み取れませんでした。")
    return parsed


def check_joint_normalization(parsed: dict[tuple[int, int], dict[str, float]]) -> None:
    """5キーワードを1つの比較で取得したCSVかどうかを、値の形から確かめる。

    Googleトレンドは**指定期間・指定キーワードの中の最大値を100**にする。5つ同時に
    取れば100はどこか1箇所(同点でも数箇所)にしか現れないが、1キーワードずつ取ると
    **5つそれぞれに100が現れる**。別々に取ったCSVはキーワード間の比較ができないのに
    数字は自然に見えるので、ここで止める。
    """
    peaked = [
        keyword
        for keyword in next(iter(parsed.values()))
        if any(values[keyword] >= 100 for values in parsed.values())
    ]
    if not peaked:
        raise ValueError(
            "CSVのどこにも100がありません。Googleトレンドは期間内の最大値を100にするため、"
            "取得範囲か加工の仕方が想定と違います。"
        )
    if len(peaked) >= 3:
        raise ValueError(
            f"100に達しているキーワードが{len(peaked)}個あります({peaked})。"
            "1キーワードずつ取得したCSVの可能性が高く、その場合キーワード間の比較ができません。"
            "5つを1つの比較で取り直してください。"
        )


def build_trends_writes(
    plan_title: str,
    header_row: list,
    month_rows: list[list],
    parsed: dict[tuple[int, int], dict[str, float]],
    through_month: tuple[int, int],
) -> dict[str, tuple[str, str, object]]:
    """シートの各行の年月に、CSVの値を割り当てる。

    毎月**全期間を取り直して列ごと書き換える**のが正しい運用(栗林さん確認済み、
    2026-09-03)。Googleトレンドは期間内の最大値を100に正規化するため、期間が延びて
    新しい最大値が出ると**過去の月の値もすべて再スケールされる**。新しい行だけ足すと
    古い行と基準がずれた表になる。
    """
    keywords = [str(cell(header_row, column)).strip() for column in TRENDS_VALUE_COLUMNS]
    if any(not keyword for keyword in keywords):
        raise ValueError(f"シートのキーワード見出し(AO2:AS2)が読めません: {keywords}")

    planned = {}
    for offset, row in enumerate(month_rows):
        row_index = TRENDS_FIRST_ROW + offset
        month = parse_month_key(cell(row, TRENDS_MONTH_COLUMN))
        if month is None or month not in parsed:
            continue          # まだ来ていない月。空のまま残す
        if month > through_month:
            # **締まっていない月を書かない。** CSVには実行日を含む当月の行も入っており、
            # 数日分だけの値が月次として並ぶ。他の月と比較できないのに、値の大きさは
            # それらしく見えるので気づけない。対象月までに絞る。
            continue
        for keyword, column in zip(keywords, TRENDS_VALUE_COLUMNS):
            if keyword not in parsed[month]:
                raise ValueError(f"CSVに『{keyword}』の列がありません。")
            planned[f"trends_{month[0]}-{month[1]:02d}_{keyword}"] = (
                plan_title,
                f"{column}{row_index}",
                parsed[month][keyword],
            )
    if not planned:
        raise ValueError(
            "CSVの月と、シートのAN列の年月が1つも一致しませんでした。"
            "期間の指定を確認してください。"
        )
    return planned


def transfer_trends(service, csv_path: str, month_label: str, apply: bool) -> int:
    """工程⑥。CSVからAO3:AS26を書き換える。対象月より後の月は書かない。"""
    print(f"GoogleトレンドCSV: {csv_path}")
    print(f"対象月(この月まで書く): {month_label}")
    print(f"モード: {'本番書き込み' if apply else 'ドライラン(書き込まない)'}\n")

    titles = list_tab_titles(service, SPREADSHEET_ID)
    plan_title = resolve_tab(titles, PLAN_TAB_KEYWORDS, "年間計画・目標")
    rows = read_tab(service, SPREADSHEET_ID, plan_title)
    header_row = rows[TRENDS_HEADER_ROW - 1]
    month_rows = rows[TRENDS_FIRST_ROW - 1:TRENDS_LAST_ROW]
    keywords = [str(cell(header_row, column)).strip() for column in TRENDS_VALUE_COLUMNS]
    print(f"シートのキーワード(AO2:AS2): {keywords}")

    with open(csv_path, encoding="utf-8-sig") as handle:
        text = handle.read()
    try:
        parsed = parse_trends_csv(text, keywords)
        check_joint_normalization(parsed)
        through = parse_month_key(month_label)
        if through is None:
            raise ValueError(f"月ラベル『{month_label}』を解釈できません(例: 2026年8月)。")
        planned = build_trends_writes(plan_title, header_row, month_rows, parsed, through)
    except ValueError as error:
        fail(str(error))
        return 1

    months = sorted(parsed)
    print(f"CSVの期間: {months[0][0]}年{months[0][1]}月 〜 {months[-1][0]}年{months[-1][1]}月"
          f"({len(months)}か月)")
    print(f"\n書き込み先: {plan_title} の AO{TRENDS_FIRST_ROW}:AS{TRENDS_LAST_ROW}")
    before = snapshot(service, {key: (title, ref) for key, (title, ref, _) in planned.items()})
    changed = [key for key in planned if parse_number(before[key]) != planned[key][2]]
    for key in sorted(planned):
        title, ref, value = planned[key]
        mark = "*" if key in changed else " "
        print(f" {mark}{key:28s} {ref:6s} 現在={before[key]!r} → {value:g}")
    print(f"\n{len(planned)}セル中 {len(changed)}セルが変化します"
          f"(全期間を取り直すため、過去の月も再スケールされることがある)")

    if not apply:
        print("\nドライランのため書き込みませんでした。--apply で実行します。")
        return 0

    write_cells(service, planned)
    mismatches = verify(service, planned)
    if mismatches:
        print("\n書き込み後の読み返しが一致しませんでした:", file=sys.stderr)
        for line in mismatches:
            print(f"  - {line}", file=sys.stderr)
        print(f"\n書き込み前の値: {before}", file=sys.stderr)
        return 1
    print("\n書き込み後の読み返しも一致しました。")
    print("AT列(5キーワード平均)と正規化ブロックは数式なので自動で追随します。")
    return 0


# --------------------------------------------------------------------------
# 工程④ 紹介・オフライン合計の転記元を調べる(読み取りのみ)
# --------------------------------------------------------------------------

def load_referral_sources() -> list[dict]:
    with open(REFERRAL_SOURCES_PATH, encoding="utf-8") as handle:
        return json.load(handle)["sources"]


def cell_background(value: dict) -> tuple[float, float, float]:
    color = (value.get("effectiveFormat") or {}).get("backgroundColor") or {}
    return (color.get("red", 1.0), color.get("green", 1.0), color.get("blue", 1.0))


def is_plain_background(rgb: tuple[float, float, float]) -> bool:
    """白またはごく薄いグレーか。色が付いていれば False。"""
    red, green, blue = rgb
    return min(red, green, blue) > 0.92 and (max(rgb) - min(rgb)) < 0.05


def report_colored_stores(service, spreadsheet_id: str, title: str, source: dict,
                          columns: dict) -> None:
    """店舗名に色が付いている行を洗い出し、5行目の合計に含まれているかを確かめる。

    栗林さんの指示は「5行目の合計を使う」と「ピンクの店舗は除外する」の両方。
    5行目がピンクも含めた全店舗の合計なら、この2つは同時に成り立たない。
    どちらなのかを数字で確かめる。
    """
    data = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        ranges=[f"'{title}'!A1:BZ400"],
        includeGridData=True,
        fields="sheets/data/rowData/values(formattedValue,effectiveFormat/backgroundColor)",
    ).execute()
    grid = data["sheets"][0]["data"][0].get("rowData", [])

    referral_cols = {col_to_index(column) for column in columns["referral"]}
    offline_cols = {col_to_index(column) for column in columns["offline_total"]}

    colored, plain = [], []
    sums = {"colored": [0.0, 0.0], "plain": [0.0, 0.0]}
    for row_index, row in enumerate(grid, start=1):
        if row_index <= source["total_row"]:
            continue
        values = row.get("values", [])
        if not values:
            continue
        name = (values[0].get("formattedValue") or "").strip()
        alt = (values[1].get("formattedValue") if len(values) > 1 else "") or ""
        label = name or alt.strip()
        if not label:
            continue
        tinted = not is_plain_background(cell_background(values[0])) or (
            len(values) > 1 and not is_plain_background(cell_background(values[1]))
        )
        bucket = "colored" if tinted else "plain"
        for index in columns:
            number = parse_number(
                values[index - 1].get("formattedValue") if index <= len(values) else ""
            ) or 0.0
            if index in referral_cols:
                sums[bucket][0] += number
            if index in offline_cols:
                sums[bucket][1] += number
        (colored if tinted else plain).append((row_index, label, cell_background(values[0])))

    source["_colored"] = (
        f"{len(colored)}件 [" + ", ".join(label for _, label, _ in colored[:8]) + "]"
    )
    print(f"  色付きの店舗 {len(colored)}件 / 色なし {len(plain)}件")
    for row_index, label, rgb in colored[:25]:
        print(f"    [{row_index}行] {label!r} rgb=({rgb[0]:.2f},{rgb[1]:.2f},{rgb[2]:.2f})")

    total_row_values = rows[source["total_row"] - 1]
    detail = []
    for name, cols, index in (("紹介", referral_cols, 0), ("オフライン合計", offline_cols, 1)):
        header_total = sum(
            parse_number(cell(total_row_values, index_to_col(c))) or 0.0 for c in sorted(cols)
        )
        both = sums["plain"][index] + sums["colored"][index]
        line = (f"{name}: {source['total_row']}行目={header_total:g} / "
                f"色なしのみ={sums['plain'][index]:g} / 全店舗={both:g}")
        print("  " + line)
        detail.append(line)
    source["_colored"] = source.get("_colored", "") + " || " + " || ".join(detail)


def sum_columns(row: list, columns: list[str]) -> float:
    return sum(parse_number(cell(row, column)) or 0.0 for column in columns)


def source_columns(source: dict, header_row: list) -> dict[str, list[str]]:
    """設定の見出し名を、この月のタブでの列記号に直す。"""
    resolved = {
        "referral": header_columns(header_row, source["referral_headers"]),
        "offline_total": header_columns(header_row, source["offline_headers"]),
    }
    if source.get("ai_headers"):
        resolved["ai"] = header_columns(header_row, source["ai_headers"])
    return resolved


def sum_ranges(row: list, ranges: list) -> float:
    total = 0.0
    for first, last in ranges:
        for index in range(col_to_index(first), col_to_index(last) + 1):
            total += parse_number(cell(row, index_to_col(index))) or 0.0
    return total


def header_key(text) -> str:
    """見出しの照合用。全角/半角と空白の違いだけで取り違えないようにする。

    実際の見出しには『電話　予約』(全角空白)や『紹介\n予約』(改行)が混ざっている。
    """
    normalized = unicodedata.normalize("NFKC", str(text))
    return "".join(normalized.split())


def header_columns(header_row: list, names: list[str]) -> list[str]:
    """見出し名から列記号を引く。1つに定まらなければ例外。

    **列記号を設定に持たない**のは、シートに列が1本挿入されると全部ずれるため。
    ミライは2026年7月が57列、8月が58列で、実際にずれていた。
    """
    index: dict[str, list[str]] = {}
    for position, value in enumerate(header_row, start=1):
        key = header_key(value)
        if key:
            index.setdefault(key, []).append(index_to_col(position))

    columns = []
    problems = []
    for name in names:
        hits = index.get(header_key(name), [])
        if len(hits) != 1:
            problems.append(f"{name!r}: {len(hits)}件{hits if hits else ''}")
            continue
        columns.append(hits[0])
    if problems:
        raise ValueError(
            "見出しから列を決められませんでした(" + " / ".join(problems) + ")。"
            "見出しが変わったか、同じ名前の列が増えています。取り違えるより止めます。"
        )
    return columns


SUM_SPAN = re.compile(r"SUM\(\s*\$?[A-Z]{1,2}\$?(\d+)\s*:\s*\$?[A-Z]{1,2}\$?(\d+)\s*\)")


def formula_row_span(formula_row: list, columns: list[str]) -> tuple[int, int]:
    """合計行の数式から、店舗行の範囲を読む。

    『合計行より下で店舗名が入っている行』を店舗行とみなすと、シートの下のほうに
    別の表や作業用の行があったときに黙って混ざる。直営はそれで紹介がちょうど2倍に
    なっていた。5行目自身が =SUM(S6:S22) と範囲を書いているので、そちらを使う。
    範囲がひとつに定まらなければ例外(推測しない)。
    """
    spans: dict[tuple[int, int], list[str]] = {}
    for column in columns:
        match = SUM_SPAN.search(str(cell(formula_row, column)))
        if match:
            span = (int(match.group(1)), int(match.group(2)))
            spans.setdefault(span, []).append(column)
    if not spans:
        raise ValueError(
            "合計行に SUM(...) の数式が1つもありません。"
            "どの行が店舗行なのかをシートから読めないため停止します。"
        )
    if len(spans) > 1:
        detail = " / ".join(f"{start}〜{end}行: {cols}" for (start, end), cols in spans.items())
        raise ValueError(
            f"合計行の数式が複数の範囲を指しています({detail})。"
            "列ごとに数える行が違うため、まとめて合計できません。停止します。"
        )
    return next(iter(spans))


def store_rows_of(rows: list[list], total_row: int) -> list[tuple[int, str, list]]:
    """合計行より下の、店舗名(A列またはB列)が入っている行。"""
    found = []
    for row_index, row in enumerate(rows, start=1):
        if row_index <= total_row:
            continue
        label = (str(cell(row, "A")).strip() or str(cell(row, "B")).strip())
        if label:
            found.append((row_index, label, row))
    return found


def excluded_row_indexes(
    store_rows: list[tuple[int, str, list]],
    exclude_names: list[str],
) -> set[int]:
    """除外する店舗の行番号。設定の名前が1つでも見つからなければ例外。

    見つからないまま進むと、別ブランドの店舗が黙って合計に混ざる。店舗名が変わったときに
    気づける唯一の場所なので、ここで止める。
    """
    matcher_keys = {}
    for row_index, label, row in store_rows:
        for text in (str(cell(row, "A")).strip(), str(cell(row, "B")).strip(), label):
            if text:
                matcher_keys.setdefault(normalize_store_name(text), set()).add(row_index)

    found: set[int] = set()
    missing = []
    for name in exclude_names:
        hits = matcher_keys.get(normalize_store_name(name))
        if not hits:
            missing.append(name)
            continue
        found |= hits
    if missing:
        raise ValueError(
            f"除外対象の店舗 {missing} がシートに見つかりませんでした。"
            "店舗名が変わった可能性があります。黙って合計に混ぜないため停止します。"
        )
    return found


def resolve_referral_tab(service, source: dict, month_label: str) -> str:
    """その月のタブ名を決める。**完全一致で選ぶ。**

    同じ月に『2026年8月(0810)』のような途中経過のタブが並んでおり、部分一致だと
    締め切り前の数字を拾う。値としては自然に見えるので気づけない。
    """
    match = re.match(r"(\d{4})年(\d{1,2})月", month_label)
    year, month = int(match.group(1)), int(match.group(2))
    wanted = source["tab_name_pattern"].format(year=year, month=month)

    meta = service.spreadsheets().get(
        spreadsheetId=source["spreadsheet_id"], fields="sheets.properties(sheetId,title)"
    ).execute()
    titles = [sheet["properties"]["title"] for sheet in meta.get("sheets", [])]
    exact = [title for title in titles if title.strip() == wanted]
    if len(exact) != 1:
        raise ValueError(
            f"{source['label']}: タブ『{wanted}』が{len(exact)}件見つかりました"
            f"(あるタブ: {titles})。1件でなければ、どれが締め後の確定版か決められないため停止します。"
        )
    return exact[0]


def read_referral_source(service, source: dict, month_label: str) -> dict:
    """1ブランド分の 紹介 / オフライン合計 / AI を読む。"""
    sid = source["spreadsheet_id"]
    title = resolve_referral_tab(service, source, month_label)
    rows = read_tab(service, sid, title)
    total_row = rows[source["total_row"] - 1]

    formulas = read_tab_range(
        service, sid,
        f"'{title}'!A{source['total_row']}:BB{source['total_row']}",
        render="FORMULA",
    )
    formula_row = formulas[0] if formulas else []

    header_row = rows[source["total_row"] - 2] if source["total_row"] >= 2 else []
    columns = source_columns(source, header_row)
    first_row, last_row = formula_row_span(
        formula_row, sorted({c for group in columns.values() for c in group})
    )
    stores = [
        (index, label, row)
        for index, label, row in store_rows_of(rows, source["total_row"])
        if first_row <= index <= last_row
    ]
    excluded = excluded_row_indexes(stores, source.get("exclude_store_names") or [])

    # AIの4列が何のチャネルなのかは列記号だけでは分からないので、内訳をログに出す。
    result = {"label": source["label"], "tab": title, "stores": len(stores),
              "excluded": len(excluded), "span": (first_row, last_row),
              "columns": columns,
              "ai_breakdown": [
                  f"{column}={str(cell(header_row, column)).strip()}"
                  f"={parse_number(cell(total_row, column))}"
                  for column in columns.get("ai", [])
              ]}
    for key in ("referral", "offline_total", "ai"):
        if key not in columns:
            continue
        group = columns[key]
        header = sum_columns(total_row, group)
        all_stores = sum(sum_columns(row, group) for _, _, row in stores)
        # 栗林さんの指示は「5行目の合計を使う」。除外店舗はそこから引く。
        # 引く相手が5行目の集計範囲に入っている行だけなのは、範囲外の店舗は
        # 5行目に最初から入っておらず、引くと二重に減るため。
        dropped = sum(
            sum_columns(row, group) for row_index, _, row in stores if row_index in excluded
        )
        if abs(header - all_stores) >= 0.5:
            raise ValueError(
                f"{source['label']} の{key}: {source['total_row']}行目={header:g} が"
                f"{first_row}〜{last_row}行の合計={all_stores:g} と一致しません。"
                "店舗行の読み取りが想定と違うため停止します。"
            )
        result[key] = {"header": header, "all": all_stores, "kept": header - dropped}

    builtin = find_offline_total_cell(rows)
    if builtin and "offline_total" in result:
        ref, value = builtin
        result["builtin_offline"] = (ref, value)
        if abs(value - result["offline_total"]["header"]) >= 0.5:
            raise ValueError(
                f"{source['label']}: シート自身のオフライン合計 {ref}={value:g} が"
                f"範囲指定の合計={result['offline_total']['header']:g} と一致しません。"
                "範囲の指定が想定と違うため停止します。"
            )
    return result


def extract_referral(service, month_label: str) -> dict[str, float]:
    """工程④。3ブランドを合算して F(紹介) / J(オフライン合計) / X(AI) を作る。"""
    totals = {"referral": 0.0, "offline_total": 0.0, "ai": 0.0}
    for source in load_referral_sources():
        result = read_referral_source(service, source, month_label)
        first_row, last_row = result["span"]
        note = f"({first_row}〜{last_row}行の{result['stores']}店舗"
        if result["excluded"]:
            note += f" / うち除外{result['excluded']}店舗"
        note += ")"
        print(f"  {result['label']:4s} タブ={result['tab']!r} {note}")
        if "builtin_offline" in result:
            ref, value = result["builtin_offline"]
            print(f"    シート自身のオフライン合計 {ref}={value:g} と一致")
        for key in ("referral", "offline_total", "ai"):
            if key not in result:
                continue
            values = result[key]
            mark = ""
            if abs(values["kept"] - values["header"]) >= 0.5:
                mark = f"  ← 5行目そのままなら {values['header']:g}(除外分を含む)"
            print(f"    {key:14s} {values['kept']:g}{mark}")
            if key == "ai" and result["ai_breakdown"]:
                print("      内訳: " + "  ".join(result["ai_breakdown"]))
            totals[key] += values["kept"]
    return totals


def find_offline_total_cell(rows: list[list]) -> tuple[str, float] | None:
    """シート自身が持っている「オフライン合計」の値を探す。

    サンズもミライも2行目に見出し「オフライン合計」があり、その真下(3行目)に値が入っている。
    こちらの範囲指定の合計とこの値が一致すれば、範囲の指定が正しいことの裏取りになる。
    """
    for row_index, row in enumerate(rows[:4], start=1):
        for col_index, value in enumerate(row, start=1):
            if normalize(value) == "オフライン合計":
                column = index_to_col(col_index)
                below = rows[row_index] if row_index < len(rows) else []
                number = parse_number(cell(below, column))
                if number is not None:
                    return f"{column}{row_index + 1}", number
    return None


def inspect_referral(service, month_label: str) -> int:
    """紹介・オフライン合計の3シートの構造を出すだけ。書き込みはしない。"""
    summary = []
    for source in load_referral_sources():
        sid = source["spreadsheet_id"]
        print(f"\n=== {source['label']} ({sid}) ===")
        meta = service.spreadsheets().get(
            spreadsheetId=sid,
            fields="properties.title,sheets.properties(sheetId,title,gridProperties)",
        ).execute()
        print(f"タイトル: {meta['properties']['title']}")
        sheets = meta.get("sheets", [])
        gid = source["_gid_2026_08"]
        print(f"タブ数: {len(sheets)}")
        # **全部出す。** 直営は月ごとに『柔整』『交通事故』とその途中経過スナップショットが
        # 並んでおり、打ち切ると肝心のタブが見えないまま名前を推測することになる。
        for sheet in sheets:
            props = sheet["properties"]
            mark = " ←栗林さんに教わったURLのgid" if props["sheetId"] == gid else ""
            grid = props.get("gridProperties", {})
            print(f"  gid={props['sheetId']:<12} {props['title']!r} "
                  f"({grid.get('rowCount')}行×{grid.get('columnCount')}列){mark}")

        # **月から引く。gidは月が変わると別物**なので、調べたい月のタブは名前で選ぶ。
        title = resolve_referral_tab(service, source, month_label)
        rows = read_tab_range(service, sid, f"'{title}'!A1:AZ12", render="FORMATTED_VALUE")
        print(f"\n-- {title!r} の1〜12行 --")
        for row_index, row in enumerate(rows, start=1):
            filled = [
                f"{index_to_col(i)}={value!r}"
                for i, value in enumerate(row, start=1)
                if str(value).strip()
            ]
            print(f"  [{row_index}行] " + (" | ".join(filled[:26]) if filled else "(空)"))

        header_row = rows[source["total_row"] - 2]
        print(f"\n-- {source['total_row'] - 1}行目(見出し)の全列 --")
        print("  " + " | ".join(
            f"{index_to_col(i)}={str(value).strip()}"
            for i, value in enumerate(header_row, start=1)
            if str(value).strip()
        ))
        try:
            columns = source_columns(source, header_row)
        except ValueError as error:
            # 調査モードは止まらない。何が引けなかったのかを見せるのが仕事なので。
            # 設定に無い見出しも並べる。改名なら、消えた名前の近くに新しい名前があるはず。
            configured = {
                header_key(name)
                for key in ("referral_headers", "offline_headers", "ai_headers")
                for name in (source.get(key) or [])
            }
            extra = [
                f"{index_to_col(i)}={str(value).strip()!r}"
                for i, value in enumerate(header_row, start=1)
                if str(value).strip() and header_key(value) not in configured
            ]
            print(f"  ** 見出しから列を引けませんでした: {error}")
            summary.append((source["label"], title, {"紹介": float("nan"),
                            "オフライン合計": float("nan")}, None, None,
                            "(列を引けず)", str(error), {"設定に無い見出し": extra}))
            continue
        source["_columns"] = columns

        if source.get("exclude_pink_stores"):
            print("\n-- 店舗行の背景色(ピンク=別ブランド)と、合計の突き合わせ --")
            report_colored_stores(service, sid, title, source, columns)

        print("\n-- 見出しから引いた列の、5行目の値 --")
        totals = {}
        for name, key in (("紹介", "referral"), ("オフライン合計", "offline_total")):
            parts = []
            total = 0.0
            for column in columns[key]:
                value = parse_number(cell(rows[source["total_row"] - 1], column))
                parts.append(f"{column}={value if value is not None else '-'}")
                total += value or 0.0
            print(f"  {name}: 合計={total:g}")
            print(f"    {' '.join(parts)}")
            totals[name] = total

        builtin = find_offline_total_cell(rows)
        if builtin:
            ref, value = builtin
            mark = "一致" if abs(value - totals["オフライン合計"]) < 0.5 else "**不一致**"
            print(f"  シート自身のオフライン合計 {ref}={value:g} → こちらの計算と{mark}")

        # 5行目が何を計算しているのかを数式で見る。直営は5行目の紹介が
        # 「合計行より下の店舗名がある行」の合計のちょうど半分だった。理由を推測せずに確かめる。
        formulas = read_tab_range(
            service, sid,
            f"'{title}'!A{source['total_row']}:BB{source['total_row']}",
            render="FORMULA",
        )
        formula_row = formulas[0] if formulas else []
        every = sorted({c for group in columns.values() for c in group})
        try:
            span = "{}〜{}行".format(*formula_row_span(formula_row, every))
        except ValueError as error:
            span = f"読めず({error})"
        source["_span"] = span
        source["_formula"] = " ".join(
            f"{column}={cell(formula_row, column)!r}" for column in columns["referral"]
        )
        # 見出し名から引いた列が、実際どこに落ちたかを残す。列記号は月によって動く。
        source["_headers"] = {
            name: [
                f"{column}={str(cell(header_row, column)).strip()!r}"
                for column in columns[key]
            ]
            for name, key in (("紹介", "referral"), ("オフライン合計", "offline_total"),
                              ("AI", "ai"))
            if key in columns
        }
        summary.append((source["label"], title, totals, builtin, source.get("_colored"),
                        source.get("_span"), source.get("_formula"), source.get("_headers")))

    print("\n\n=== まとめ ===")
    for label, title, totals, builtin, colored, span, formula, headers in summary:
        line = (f"{label:4s} タブ={title!r} 紹介={totals['紹介']:g} "
                f"オフライン合計={totals['オフライン合計']:g}")
        if builtin:
            line += f" (シート自身の値 {builtin[0]}={builtin[1]:g})"
        if colored:
            line += f" 色付き店舗={colored}"
        print("  " + line)
        print(f"       合計行が数えている範囲={span}  紹介の数式: {formula}")
        for name, labels in (headers or {}).items():
            print(f"       {name}の見出し: " + " ".join(labels))
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
        "--trends",
        metavar="CSV",
        help=(
            "工程⑥。GoogleトレンドのCSV(5キーワードを1つの比較で取得したもの)から"
            "AO3:AS26を書き換える。AT列と正規化ブロックは数式なので触らない"
        ),
    )
    parser.add_argument(
        "--inspect-referral",
        action="store_true",
        help="工程④。紹介・オフライン合計の3シート(直営/サンズ/ミライ)の構造を出すだけ",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="書き込まず、シートの構造(タブ名・ヘッダー行・合計値)を出すだけ",
    )
    args = parser.parse_args()

    if args.inspect_referral:
        return inspect_referral(build_service(), args.month)

    if args.inspect:
        return inspect(build_service(), args.month)

    if args.trends:
        return transfer_trends(build_service(), args.trends, args.month, args.apply)

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
    row_index = find_month_row(rows, PLAN_COLUMNS["month"], args.month, PLAN_BLOCK_TOTAL)

    planned = {}
    for key, value in sorted(extracted.items()):
        if key not in WRITABLE_PLAN_KEYS:
            print(f"  skip {key}(書き込み対象外)")
            continue
        ref = f"{PLAN_COLUMNS[key]}{row_index}"
        planned[key] = (plan_title, ref, value)

    print(f"\n① ② の書き込み先: {plan_title} の {row_index}行目")
    before = snapshot(service, {key: (title, ref) for key, (title, ref, _) in planned.items()})
    for key, (title, ref, value) in sorted(planned.items()):
        print(f"  {key:24s} {ref}  現在={before[key]!r} → {value:g}")

    if args.apply:
        # ⑤は①②の結果から自動計算される行を読むので、先に①②を書いて計算させる。
        write_cells(service, planned)
        mismatches = verify(service, planned)
        if mismatches:
            print("\n①② の書き込み後の読み返しが一致しませんでした:", file=sys.stderr)
            for line in mismatches:
                print(f"  - {line}", file=sys.stderr)
            print(f"\n書き込み前の値: {before}", file=sys.stderr)
            return 1
        print("  ①② 書き込み後の読み返し: 一致")

    # --- 工程⑤ ダッシュボードへの転記 ---
    print("\n⑤ ダッシュボードへの転記(1店舗当たりの行を、全体数の行から検算しながら読む)")
    try:
        plan_rows_fresh = read_tab(service, SPREADSHEET_ID, plan_title)
        plan_rows_raw = read_tab(service, SPREADSHEET_ID, plan_title, raw=True)
        dashboard_values = build_dashboard_values(plan_rows_fresh, plan_rows_raw, args.month)
    except ValueError as error:
        if args.apply:
            print(f"\n①②は書き込み済みだが、⑤で停止した: {error}", file=sys.stderr)
            print(f"①②の書き込み前の値(巻き戻し用): {before}", file=sys.stderr)
        fail(str(error))
        return 1

    dash_title = resolve_tab(titles, DASHBOARD_TAB_KEYWORDS, "ダッシュボード")
    dash_rows = read_tab(service, SPREADSHEET_ID, dash_title)
    dash_row_index = find_month_row(dash_rows, DASHBOARD_MONTH_COLUMN, args.month)

    dash_planned = {
        f"dash_{key}": (dash_title, f"{column}{dash_row_index}", dashboard_values[key])
        for key, column, _, _ in DASHBOARD_COLUMNS
    }
    print(f"\n⑤ の書き込み先: {dash_title} の {dash_row_index}行目")
    dash_before = snapshot(
        service, {key: (title, ref) for key, (title, ref, _) in dash_planned.items()}
    )
    for key, (title, ref, value) in sorted(dash_planned.items()):
        print(f"  {key:24s} {ref}  現在={dash_before[key]!r} → {value:.4g}")

    if not args.apply:
        print("\nドライランのため書き込みませんでした。--apply で実行します。")
        return 0

    write_cells(service, dash_planned)
    before = {**before, **dash_before}
    planned = {**planned, **dash_planned}
    mismatches = verify(service, dash_planned)
    if mismatches:
        print("\n書き込み後の読み返しが一致しませんでした:", file=sys.stderr)
        for line in mismatches:
            print(f"  - {line}", file=sys.stderr)
        print(f"\n書き込み前の値: {before}", file=sys.stderr)
        return 1

    print("\n⑤ 書き込み後の読み返しも一致しました。")
    print(f"書き込み前の値(巻き戻し用): {before}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""HotPepper Beauty公開カレンダーの予約枠チェック(K/L列)。

「予約枠」Colabノートブック(手動実行前提)のロジックをそのまま移植し、GitHub Actionsで
スケジュール実行できるようにしたもの。ノートブック側の既知バグ2件は移植前に修正済み:
  - 日付キーのゼロ埋め不一致 (.claude/skills/hpb-reservation-slot-check/references/known-bugs.md #1)
  - データなしがサイレントに"○"扱いされる問題 (同 #2)
詳細はそちらを参照。ロジックを変える場合は、あちらのSKILL.mdの非交渉ルール(まず
コピーで検証、main_process相当を無断で流さない)も踏まえること。

**既定はドライラン。** 書き込むには --apply を明示する。本番の「AIチェック用ver.2」タブを
触るため、既定で書き込む設計にはしない(kpi_aggregate.pyと同じ方針)。

**書き込み対象は「AIチェック用ver.2」タブだけ。** 元の「AIチェック用」タブは既存の(手動の)
確認フローのために残されているので、このスクリプトからは一切参照・変更しない
(栗林さん指定)。読み取りも書き込みも`WORKSHEET_NAME`定数経由のみに限定し、
シート名をハードコードで増やさないこと。

認証: 環境変数 GCP_KPI_WRITER_KEY にサービスアカウントのJSON全文
(kpi_aggregate.pyと同じ書き込み用サービスアカウントを流用。
`chokuei-sunsumirai-kpi-writer@keizgroup-automation.iam.gserviceaccount.com` を
「HPB予約枠確認」スプレッドシートに編集者共有しておくこと。functions/kpi-aggregation/CLAUDE.md
参照)。
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import random
import re
import sys

import jpholiday

SHEET_ID = "15lWYMvRjY3hGVvPu_IgmGHx4ER3joCERFDEzVd8aLrI"
WORKSHEET_NAME = "AIチェック用ver.2"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def fail(msg: str) -> None:
    print(f"エラー: {msg}", file=sys.stderr)
    sys.exit(1)


def is_weekend_or_holiday(dt: datetime.datetime) -> bool:
    """土日または日本の祝日かどうかを判定"""
    return dt.weekday() >= 5 or jpholiday.is_holiday(dt)


def parse_time(time_str):
    if not time_str:
        return None
    time_str = time_str.replace("：", ":").strip()
    try:
        h, m = map(int, time_str.split(":"))
        return h * 60 + m
    except Exception:
        return None


async def scrape_hpb_robust(page, base_url, target_dates, shop_name):
    """強固な対策を施したカレンダー解析"""
    date_str = target_dates[0].strftime("%Y%m%d")
    sep = "&" if "?" in base_url else "?"
    url = f"{base_url}{sep}reserveDate={date_str}"
    calendar_data = {}
    await asyncio.sleep(random.uniform(1.5, 3.5))  # 人間らしい待機
    for attempt in range(3):
        try:
            await page.goto(url, wait_until="load", timeout=45000)
            await asyncio.sleep(2)
            if not await page.query_selector(".timeTableLeft"):
                if attempt < 2:
                    continue
                return {}
            time_elements = await page.query_selector_all(".timeTableLeft .timeCell")
            time_list = [(await t.inner_text()).strip() for t in time_elements]
            headers = await page.query_selector_all(".dayCellContainer th")
            date_to_col_idx = {}
            valid_idx = 0
            for header in headers:
                text = await header.inner_text()
                match = re.search(r"(\d+)", text)
                if match:
                    date_to_col_idx[str(int(match.group(1)))] = valid_idx
                    valid_idx += 1
            columns = await page.query_selector_all(".innerCol")
            for dt in target_dates:
                day_num = str(dt.day)
                dt_key = dt.strftime("%m/%d")
                if day_num in date_to_col_idx:
                    col_idx = date_to_col_idx[day_num]
                    if col_idx < len(columns):
                        status_elements = await columns[col_idx].query_selector_all("td")
                        day_slots = []
                        for i, status_el in enumerate(status_elements):
                            if i < len(time_list):
                                status_text = (await status_el.inner_text()).strip()
                                if not status_text:
                                    img = await status_el.query_selector("img")
                                    status_text = await img.get_attribute("alt") if img else ""
                                day_slots.append({"time": time_list[i], "status": status_text})
                        calendar_data[dt_key] = day_slots
            return calendar_data
        except Exception:
            await asyncio.sleep(5)
    return {}


def judge_occupancy_rate(slots, start_min, end_min, b_start, b_end, is_am):
    boundary = 13 * 60
    target_slots = []
    # TELを×として判定に含める
    ng_symbols = ["×", "TEL", "✕", "満席", "満員", "×(予約不可)"]
    ok_symbols = ["◎", "○", "△", "〇", "空き"]
    if not slots:
        return "-"
    for s in slots:
        t_min = parse_time(s["time"])
        if t_min is None:
            continue
        if is_am and t_min >= boundary:
            continue
        if not is_am and t_min < boundary:
            continue
        if start_min <= t_min < end_min:
            if b_start is not None and b_end is not None:
                if b_start <= t_min < b_end:
                    continue
            status = s["status"].replace(" ", "").replace("　", "")
            if any(sym in status for sym in ok_symbols) or any(sym in status for sym in ng_symbols):
                target_slots.append(status)
    if not target_slots:
        return "-"
    ng_count = sum(1 for s in target_slots if any(sym in s for sym in ng_symbols))
    return "✕" if (ng_count / len(target_slots)) >= 0.5 else "○"


def default_date_window():
    """明示指定がない場合の既定ウィンドウ: 当日PM〜2日後PM(2026-09-03、栗林さん指定)。

    毎日13:00 JSTに実行する前提(ワークフロー側のcronと対応)。実行時点で当日AMは既に
    過ぎているので、当日PMから2日後PMまでを判定対象にする。
    """
    today = datetime.datetime.now()
    end = today + datetime.timedelta(days=2)
    return today.strftime("%Y-%m-%d"), "PM", end.strftime("%Y-%m-%d"), "PM"


HISTORY_WORKSHEET_NAME = "K,L履歴"
# 種別: このスクリプトが書くのは常に"K/L自動"。"M/N確認"はSalonBoard側の週次AI目視確認
# (人が「今週分お願い」と声をかけて行うほう)が、対応する店舗・対象日を見つけたぶんだけ
# 新しい行として追記する(既存行を上書きしない — 履歴は追記専用)。
HISTORY_HEADER = ["確認日時", "店舗名", "対象日", "区分(AM/PM)", "種別", "判定", "確認結果", "備考"]


def build_spreadsheet():
    raw = os.environ.get("GCP_KPI_WRITER_KEY", "").strip()
    if not raw:
        fail(
            "GCP_KPI_WRITER_KEY が未設定です。GitHub Actionsではリポジトリシークレットから"
            "渡ります。ワークフローのenvブロックとシークレット名を確認してください。"
        )
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        fail("GCP_KPI_WRITER_KEY がJSONとして読めません(値の中身は表示しません)。")

    try:
        import gspread
        from google.oauth2 import service_account
    except ImportError:
        fail("gspread / google-auth が必要です: pip install gspread google-auth")

    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID)


def get_or_create_history_worksheet(spreadsheet):
    """K/L列は毎回上書きなので、判定結果を対象日・区分ごとに別タブへ積み上げて残す。

    チェック窓は「当日PM〜2日後PM」のローリングウィンドウで毎日実行するため、同じ対象日が
    複数回(最大3回)の実行にまたがって評価される。これを1回の実行につき1行(複数日を
    " | "で連結した文字列)にまとめてしまうと、「その対象日が正確にいつ✕に変わったか」が
    追えなくなる。なので対象日・区分(AM/PM)ごとに1行、判定が○であっても毎回記録する
    (栗林さん指定: 「重複している日の確認結果もそれぞれ残しておきたい」)。
    """
    import gspread

    try:
        return spreadsheet.worksheet(HISTORY_WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=HISTORY_WORKSHEET_NAME, rows=1000, cols=len(HISTORY_HEADER))
        ws.append_row(HISTORY_HEADER)
        return ws


async def main_process(spreadsheet, worksheet, start_date, start_half, end_date, end_half, apply: bool):
    s_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    e_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d")
    unique_dates = []
    curr = s_dt
    while curr <= e_dt:
        unique_dates.append(curr)
        curr += datetime.timedelta(days=1)

    all_data = worksheet.get_all_values()
    # 3行目から最後までの行を対象とする
    shop_rows = all_data[2:]

    # 一括書き込み用のデータを準備(K列とL列)
    bulk_updates = []
    # 履歴タブ用: 対象日・区分ごとに1行、判定結果を毎回積み上げる(K/L列自体は毎回上書きのため)
    history_rows = []
    run_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 1200},
        )
        page = await context.new_page()

        for i, row in enumerate(shop_rows):
            if not row or len(row) < 10:
                bulk_updates.append(["", ""])  # 空行対策
                continue
            shop_name, base_url = row[0], row[9]
            if "http" not in base_url:
                bulk_updates.append(["", ""])
                continue
            print(f"🔍 解析中 ({i + 1}/{len(shop_rows)}): {shop_name}")
            all_slots = await scrape_hpb_robust(page, base_url, unique_dates, shop_name)
            summary_results = []
            has_any_ng = False
            has_any_data = False
            curr_loop = s_dt
            while curr_loop <= e_dt:
                is_holiday_today = is_weekend_or_holiday(curr_loop)
                for half in ["AM", "PM"]:
                    if curr_loop == s_dt and start_half == "PM" and half == "AM":
                        continue
                    if curr_loop == e_dt and end_half == "AM" and half == "PM":
                        continue
                    is_am = half == "AM"
                    if not is_holiday_today:
                        s_t, e_t, b_t = row[1], row[2], row[3]  # 平日
                    else:
                        s_t, e_t, b_t = row[4], row[5], row[6]  # 土日祝
                    s_min, e_min = parse_time(s_t), parse_time(e_t)
                    b_s, b_e = None, None
                    if b_t and "-" in b_t:
                        p_b = b_t.split("-")
                        b_s, b_e = parse_time(p_b[0]), parse_time(p_b[1])
                    dt_key = curr_loop.strftime("%m/%d")
                    res = judge_occupancy_rate(all_slots.get(dt_key, []), s_min, e_min, b_s, b_e, is_am)
                    has_any_ng = has_any_ng or (res == "✕")
                    has_any_data = has_any_data or (res != "-")
                    summary_results.append(f"{dt_key}{half}:{res}")
                    history_rows.append(
                        [
                            run_timestamp,
                            shop_name,
                            curr_loop.strftime("%Y-%m-%d"),
                            half,
                            "K/L自動",
                            res,
                            "",
                            "",
                        ]
                    )
                curr_loop += datetime.timedelta(days=1)
            final_judge = "✕" if has_any_ng else ("○" if has_any_data else "?")
            detail = " | ".join(summary_results)
            bulk_updates.append([detail, final_judge])
            print(f"  -> 結果: {final_judge}")
        await browser.close()

    range_label = f"K3:L{2 + len(bulk_updates)}"
    if apply:
        print("\n📝 シートへ一括保存しています...")
        worksheet.update(range_name=range_label, values=bulk_updates)
        if history_rows:
            history_ws = get_or_create_history_worksheet(spreadsheet)
            history_ws.append_rows(history_rows)
            print(f"📚 履歴タブ「{HISTORY_WORKSHEET_NAME}」に{len(history_rows)}件追記しました。")
        print("✅ すべて完了しました。")
    else:
        ng_count = sum(1 for _, judge in bulk_updates if judge == "✕")
        ok_count = sum(1 for _, judge in bulk_updates if judge == "○")
        unknown_count = sum(1 for _, judge in bulk_updates if judge == "?")
        print(
            f"\n[dry-run] {range_label} には書き込みません。"
            f" 内訳: ○{ok_count} / ✕{ng_count} / ?{unknown_count}"
            f" (履歴タブへの追記対象: {len(history_rows)}件)"
            " (--apply を付けると書き込みます)"
        )
    return bulk_updates


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", help="YYYY-MM-DD。省略時は今日")
    parser.add_argument("--start-half", choices=["AM", "PM"], default="PM")
    parser.add_argument("--end-date", help="YYYY-MM-DD。省略時は2日後")
    parser.add_argument("--end-half", choices=["AM", "PM"], default="PM")
    parser.add_argument("--apply", action="store_true", help="実際にK:L列へ書き込む(既定はドライラン)")
    return parser.parse_args()


def main():
    args = parse_args()
    d_start, d_start_half, d_end, d_end_half = default_date_window()
    start_date = args.start_date or d_start
    end_date = args.end_date or d_end
    start_half = args.start_half if args.start_date else d_start_half
    end_half = args.end_half if args.end_date else d_end_half

    spreadsheet = build_spreadsheet()
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    asyncio.run(
        main_process(spreadsheet, worksheet, start_date, start_half, end_date, end_half, args.apply)
    )


if __name__ == "__main__":
    main()

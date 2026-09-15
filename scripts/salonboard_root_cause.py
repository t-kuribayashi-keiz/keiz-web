#!/usr/bin/env python3
"""SalonBoard側で、K/L列が✕になった枠の原因を切り分けてM/N列に書く。

**2026-09-03時点で未使用・保留。** GitHub Actionsワークフローからは呼ばれていない。
ルールベースの判定(このファイル)だと精度が不安定になりそう、というのが栗林さんの判断で、
当面はM/N確認を「栗林さんが声をかけたタイミングでClaudeが実Chromeで目視確認する」運用に
した(.claude/skills/hpb-reservation-slot-check/SKILL.md参照)。ログイン〜サロン選択〜
スケジュールページ遷移のPlaywright実装は動作確認済みで再利用できるので、消さずに残して
ある。将来また自動化を検討するなら、`classify_schedule()`の分類部分だけ差し替えれば
(ルールベースの代わりに、レンダリング結果をLLMに判断させるなど)このまま使えるはず。

「予約枠チェック」(hpb_slot_check.py)がHotPepper Beautyの公開カレンダーで✕と判定した
店舗について、salonboard.com管理画面のスケジュール実体を見て、以下のどれかに分類する
(2026-09-03、実際の19店舗をSalonBoard画面で目視確認して確定したパターン):

  対象外 / 定休日        : 「指定した日付は休業日です」と表示される
  ○     / 実予約あり(誤検知) : 実際の顧客予約が入っている(公開カレンダー側の誤検知)
  ✕     / 予定あり(枠ブロック) : スタッフ or ベッドの予定に「予定あり」を入れて枠を閉じている
  ✕     / 一括停止(警告)   : 赤字の一括停止警告が出ていて、予約数が全て0
  要確認 / 要確認          : 上のどれにも明確に当てはまらない

**既定はドライラン。** 書き込むには --apply を明示する。

**ログイン手順は未検証。** 本番のSalonBoard本部アカウントに対して自動ログインを試すのは
これが初めてなので、まず必ず `--mode verify-login` を人が手動実行し、ログインが成功して
サロン一覧が読めることを確認してから、cron実行(--mode apply)を有効にすること。
ログインフォームのセレクタが実際と違えば、この検証ステップで分かりやすく失敗する
(何度もリトライして本番アカウントを叩き続けたりはしない)。

認証:
  GOOGLE_SHEETS_KEY  : サービスアカウントのJSON全文(hpb_slot_check.pyと共用)
  SALONBOARD_USER_ID : SalonBoard本部アカウントのログインID
  SALONBOARD_PASSWORD: 同パスワード
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import re
import sys

SHEET_ID = "15lWYMvRjY3hGVvPu_IgmGHx4ER3joCERFDEzVd8aLrI"
# hpb_slot_check.pyと同じタブ名で揃える(栗林さんが「AIチェック用」を複製して作った
# 「AIチェック用ver.2」が自動化の対象。元の「AIチェック用」タブには一切触れないこと)。
WORKSHEET_NAME = "AIチェック用ver.2"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# --- 要検証: 実際のログインページで確認していないセレクタ ------------------------
# .claude/skills/hpb-salonboard-update/SKILL.md はこれまで「ログインは常に人が行う」
# 前提だったため、自動ログインのセレクタはまだ誰も実機で確認していない。
# `--mode verify-login` の初回実行がここで失敗したら、実際のログインページを開いて
# ここを直すこと(パスワードは画面に表示されるので、直す作業は必ずユーザー本人が行う)。
SALONBOARD_LOGIN_URL = "https://salonboard.com/login/"
SELECTOR_USER_ID = "#userId"
SELECTOR_PASSWORD = "#password"
SELECTOR_SUBMIT = "button[type='submit']"
GROUP_TOP_URL = "https://salonboard.com/CNC/groupTop/"
# --------------------------------------------------------------------------------


def fail(msg: str) -> None:
    print(f"エラー: {msg}", file=sys.stderr)
    sys.exit(1)


def build_worksheet():
    raw = os.environ.get("GOOGLE_SHEETS_KEY", "").strip()
    if not raw:
        fail("GOOGLE_SHEETS_KEY が未設定です。")
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        fail("GOOGLE_SHEETS_KEY がJSONとして読めません(値の中身は表示しません)。")

    try:
        import gspread
        from google.oauth2 import service_account
    except ImportError:
        fail("gspread / google-auth が必要です: pip install gspread google-auth")

    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(SHEET_ID)
    return spreadsheet.worksheet(WORKSHEET_NAME)


def rows_needing_root_cause(all_data):
    """L列が✕で、M列がまだ空の行を (行番号, 店舗名, K列の詳細) で返す。"""
    targets = []
    for i, row in enumerate(all_data[2:]):
        rownum = i + 3
        if len(row) < 12 or row[11] != "✕":
            continue
        m_val = row[12] if len(row) > 12 else ""
        if m_val:
            continue  # 既に確認済み
        name = row[0]
        detail = row[10] if len(row) > 10 else ""
        targets.append((rownum, name, detail))
    return targets


def first_ng_date(detail: str, today: datetime.date) -> datetime.date | None:
    """K列の詳細文字列 (例 "09/03PM:✕ | 09/04AM:○") から、最初に✕が付いた日付を返す。"""
    for part in detail.split("|"):
        part = part.strip()
        m = re.match(r"(\d{2})/(\d{2})(AM|PM):(.+)", part)
        if not m:
            continue
        month, day, _half, judge = m.groups()
        if "✕" not in judge:
            continue
        month, day = int(month), int(day)
        year = today.year
        candidate = datetime.date(year, month, day)
        # 年末年始をまたぐ「今日よりだいぶ前」の日付は来年扱いにする
        if (today - candidate).days > 60:
            candidate = datetime.date(year + 1, month, day)
        return candidate
    return None


async def login(page, user_id: str, password: str) -> None:
    await page.goto(SALONBOARD_LOGIN_URL, wait_until="load", timeout=30000)
    await page.fill(SELECTOR_USER_ID, user_id)
    await page.fill(SELECTOR_PASSWORD, password)
    await page.click(SELECTOR_SUBMIT)
    await page.wait_for_load_state("load", timeout=30000)


async def verify_login(page) -> bool:
    await page.goto(GROUP_TOP_URL, wait_until="load", timeout=30000)
    body_text = await page.inner_text("body")
    return "サロン一覧" in body_text or "サロンID" in body_text


async def open_salon(page, shop_name: str) -> bool:
    """グループトップのサロン一覧から、店舗名の完全一致リンクをクリックして入る。"""
    await page.goto(GROUP_TOP_URL, wait_until="load", timeout=30000)
    link = page.get_by_text(shop_name, exact=True)
    if await link.count() == 0:
        return False
    await link.first.click()
    await page.wait_for_load_state("load", timeout=30000)
    return True


async def classify_schedule(page, target_date: datetime.date) -> tuple[str, str]:
    date_str = target_date.strftime("%Y%m%d")
    await page.goto(
        f"https://salonboard.com/KLP/schedule/salonSchedule/?date={date_str}",
        wait_until="load",
        timeout=30000,
    )
    await asyncio.sleep(1.5)
    body_text = await page.inner_text("body")

    if "休業日です" in body_text:
        return "対象外", "定休日"

    if await page.locator(".scheduleReserveName").count() > 0:
        return "○", "実予約あり(誤検知)"

    todo_titles = await page.locator(".todoTitle").all_inner_texts()
    if any("予定あり" in t for t in todo_titles):
        return "✕", "予定あり(枠ブロック)"

    counts = await page.locator(".scheduleTimeTableReserveCount").all_inner_texts()
    all_zero = counts and all(c.strip() in ("0", "-", "") for c in counts)
    if all_zero and "一括停止" in body_text:
        return "✕", "一括停止(警告)"

    return "要確認", "要確認"


async def run(worksheet, apply: bool, mode: str):
    user_id = os.environ.get("SALONBOARD_USER_ID", "").strip()
    password = os.environ.get("SALONBOARD_PASSWORD", "").strip()
    if not user_id or not password:
        fail("SALONBOARD_USER_ID / SALONBOARD_PASSWORD が未設定です。")

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 1200})
        page = await context.new_page()

        await login(page, user_id, password)
        if not await verify_login(page):
            await browser.close()
            fail(
                "ログインを確認できませんでした。SALONBOARD_LOGIN_URL / "
                "SELECTOR_USER_ID / SELECTOR_PASSWORD / SELECTOR_SUBMIT が実際のログイン"
                "ページと合っているか、このファイル冒頭の定数を実機で確認してください。"
            )

        if mode == "verify-login":
            print("✅ ログイン確認OK。サロン一覧を読めました。")
            await browser.close()
            return

        all_data = worksheet.get_all_values()
        targets = rows_needing_root_cause(all_data)
        print(f"対象: {len(targets)}件(L列✕かつM列未記入)")

        today = datetime.date.today()
        updates = []
        for rownum, shop_name, detail in targets:
            target_date = first_ng_date(detail, today)
            if target_date is None:
                print(f"  {rownum} {shop_name}: K列から日付を特定できず、要確認扱いにします")
                updates.append({"range": f"M{rownum}:N{rownum}", "values": [["要確認", "要確認"]]})
                continue
            if not await open_salon(page, shop_name):
                print(f"  {rownum} {shop_name}: サロン一覧に完全一致する店舗名が見つかりません")
                updates.append({"range": f"M{rownum}:N{rownum}", "values": [["要確認", "サロン特定不可"]]})
                continue
            m, n = await classify_schedule(page, target_date)
            print(f"  {rownum} {shop_name} ({target_date}): {m} / {n}")
            updates.append({"range": f"M{rownum}:N{rownum}", "values": [[m, n]]})

        await browser.close()

    if apply:
        if updates:
            worksheet.batch_update(updates)
        header_row = all_data[1] if len(all_data) > 1 else []
        if len(header_row) < 13 or not header_row[12]:
            worksheet.update(range_name="M2:N2", values=[["確認結果", "備考"]])
        print(f"✅ {len(updates)}件をM/N列へ書き込みました。")
    else:
        print(f"\n[dry-run] {len(updates)}件を書き込み対象として検出しました(--apply で書き込みます)")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["verify-login", "check"],
        default="check",
        help="verify-login: ログインできるかだけ確認して終了。check: 通常の原因切り分け",
    )
    parser.add_argument("--apply", action="store_true", help="実際にM:N列へ書き込む(既定はドライラン)")
    return parser.parse_args()


def main():
    args = parse_args()
    worksheet = build_worksheet()
    asyncio.run(run(worksheet, args.apply, args.mode))


if __name__ == "__main__":
    main()

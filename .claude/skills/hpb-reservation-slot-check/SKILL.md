---
name: hpb-reservation-slot-check
description: Use this skill when working on the "予約枠" (reservation-slot check) Google Colab notebook — a Playwright-based scraper that reads each salon's PUBLIC HotPepper Beauty reservation calendar (beauty.hotpepper.jp) and judges every AM/PM half-day slot as ○ (fine) or ✕ (problem), writing results into a Google Sheet's "AIチェック用" tab. Trigger on "予約枠チェック", "予約枠ノートブック", mentions of scrape_hpb_robust / main_process / judge_occupancy_rate, or debugging why the sheet shows all-○/all-"-" results. Do NOT trigger for salonboard.com admin-backend edits — that's hpb-salonboard-update; this skill is about the read-only public-calendar scraper feeding data INTO the manual/AI review process, not the admin backend itself.
---

# HPB Reservation Slot Check (予約枠チェック)

Debugging and maintenance playbook for the "予約枠" Colab notebook. It scrapes ~142 salons'
public HotPepper Beauty reservation calendars via headless Playwright, judges each half-day
slot's occupancy, and bulk-writes K:L columns of the "AIチェック用" tab in a shared Google
Sheet. The notebook lives at a fixed Colab URL (ask the user for the current link if not
already known from context) and is considered production — many people may read the sheet
it writes to.

## Non-negotiable rules

1. **Never experiment directly on the production notebook.** If the user hasn't already
   duplicated it (Colab: ファイル → ドライブにコピーを保存), do that first and do all
   debugging/fix-verification on the copy. Only port a fix back to the original once it's
   verified end-to-end against real data in the copy.
2. **Never run `main_process()` — the full-batch scrape-and-write — without an explicit,
   fresh "yes" for that specific run**, even after the user has already approved a code fix.
   `main_process()` writes to the shared production sheet (K3:L{2+N}) and takes ~15-20
   minutes for ~142 shops; that's exactly the kind of hard-to-reverse, shared-state action
   that needs its own confirmation, separate from "the fix looks right." Comment out
   `await main_process()` while iterating and only uncomment it right before the approved run.
3. **Test on a small shop subset before trusting a fix at full scale.** Add a throwaway
   debug cell that calls the real `scrape_hpb_robust`/`judge_occupancy_rate` functions
   (already defined by the main cell) against `worksheet.get_all_values()[2:2+N]` for a
   small N (3-5), prints per-shop results, and does **not** call `worksheet.update()`. This
   validates the whole pipeline (scraping + business-hours + judging) without touching the
   shared sheet. See `references/colab-editing-gotchas.md` for exactly how to build and run
   this safely.
4. **Read `references/known-bugs.md` before assuming new "all-○" or "all-✕" behavior is a
   new bug** — the two root causes documented there (date-key zero-padding mismatch, and
   silent no-data-defaults-to-○ masking) are exactly the kind of thing that looks like a
   fresh regression but has already been diagnosed and fixed once.

## How the notebook is structured

One big cell defines everything (config constants, `is_weekend_or_holiday`, `parse_time`,
`scrape_hpb_robust`, `judge_occupancy_rate`, `main_process`) and ends with `await
main_process()`. Running that cell both defines the functions AND (if not commented out)
kicks off the live batch — see rule 2. A fresh Colab runtime has no packages installed and
no Google auth granted yet; the separate `!pip install playwright jpholiday` /
`!playwright install chromium` / `!playwright install-deps` cell(s) must run first, and
`auth.authenticate_user()` will prompt an interactive "Google 認証情報へのアクセスを許可
しますか?" dialog the first time in a new runtime — click 許可, this is expected and safe
(it's the user's own Drive/Sheets access).

`scrape_hpb_robust(page, base_url, target_dates, shop_name)` navigates to
`{base_url}{?|&}reserveDate={YYYYMMDD}`, reads `.dayCellContainer th` for date headers and
`.innerCol` / `.timeTableLeft .timeCell` for the slot grid, and returns
`{"MM/DD": [{"time":..., "status":...}, ...]}`. `judge_occupancy_rate` turns one day's slots
into "○"/"✕"/"-" (not enough data) for one half-day window given the salon's business hours
(weekday vs. weekend/holiday row of the sheet) and break time. `main_process` loops all shop
rows, calls both, and bulk-writes `K3:L{2+len(rows)}`.

## Diagnosing "everything shows ○ (or all "-")" from scratch

Work through these in order — each one was a real, confirmed cause at some point, cheapest
checks first:

1. **Confirm sheet edit permission** isn't the issue (check via Drive sharing, or that
   *some* write reaches the sheet at all via ファイル→変更履歴を表示 — a write of the wrong
   *values* still shows up in revision history, which rules out "writes aren't happening"
   even when the displayed values look unchanged).
2. **Rule out a stale/past date range** — re-run with `START_DATE`/`END_DATE` covering
   today or later.
3. **Rule out full scraping failure** — manually open one shop's
   `https://beauty.hotpepper.jp/CSP/kr/reserve/?storeId=...&couponId=...&reserveDate=...`
   URL in a real browser and confirm the calendar renders and `.timeTableLeft` exists.
4. **Rule out a lazy-load timing issue** — poll selector counts (`.timeCell`, `th`,
   `.innerCol`) at increasing delays (2s/4s/6s) after `page.goto`; if the counts are already
   stable at 2s it isn't a timing problem.
5. **Compare headless `inner_text()` output against manual-browser DOM inspection for the
   same selector** — this is the one that actually caught the real bug, see
   `references/known-bugs.md` bug #1. Headless Playwright can return a different (longer)
   string for the same element than what a human sees in DevTools.
6. **Check whether the specific shop's URL/couponId is simply dead** (HotPepper serves a
   "掲載エラー" page) rather than a scraper bug — this looks identical to a scraping failure
   (empty `calendar_data`) from the code's point of view, but it's a data-quality issue in
   the sheet's stored URL, not something the scraper can fix. See
   `references/known-bugs.md` bug #3.

## Continuous learning

Same convention as `hpb-salonboard-update`: append anything newly learned to
`references/known-bugs.md` (a new root-cause class) or `references/colab-editing-gotchas.md`
(a new browser-automation/Colab-UI quirk) rather than letting it live only in a
conversation transcript.

## K/L is now fully automated; M/N stays manual-trigger, AI-driven (2026-09-03 decision)

`scripts/hpb_slot_check.py` is the K/L scraper (this notebook's `main_process` logic,
ported 1:1) and runs daily at 13:00 JST via `.github/workflows/hpb-reservation-slot-check.yml`
— no one needs to open the Colab notebook for this anymore. Auth reuses the existing
`GCP_KPI_WRITER_KEY` write-capable service account from `functions/kpi-aggregation`
(`chokuei-sunsumirai-kpi-writer@keizgroup-automation.iam.gserviceaccount.com`) — share the
"HPB予約枠確認" spreadsheet with it as Editor; no new key/secret needed. Check window is a
daily-rolling "当日PM〜2日後PM" (`default_date_window()`), per the user's own spec.

**K/L is overwritten in place every run, so a "K,L履歴" tab (auto-created on first run)
keeps what the live columns can't: a full timeline.** Because the window rolls forward one
day at a time, the same target date gets evaluated by up to 3 different runs before it
finally passes — the user explicitly wants every one of those overlapping evaluations kept
(not deduped), specifically so "いつ枠が閉じたか" (exactly when a slot got blocked) can be
pinned down by comparing consecutive runs' judgments for the same date. So the history log
is one row per (shop, target date, AM/PM) **per run** — not one row per shop per run, and
not filtered to ✕ only; every ○ is logged too, since a ✕ is only interpretable against the
○ baseline that preceded it. Columns: `確認日時, 店舗名, 対象日, 区分(AM/PM), 種別, 判定,
確認結果, 備考`. `種別` is always `"K/L自動"` for rows this script writes.

**When doing the weekly manual M/N check (see below), append to this same "K,L履歴" tab**
— new rows, `種別="M/N確認"`, with `確認結果`/`備考` filled in and `判定` holding whatever
the live L column said at check time. Append, never edit an existing K/L-自動 row: the two
processes run on independent schedules (daily vs. weekly) and the whole point of this tab
is an untouched, append-only timeline. This is what answers the user's "備考もちゃんと
蓄積されていく?" — yes, but as its own new rows in the same tab, joinable later by
`店舗名` + `対象日` against the K/L自動 rows, not as an edit to them.

**M/N (the SalonBoard-side root-cause check) is deliberately NOT automated by rule-based
code.** A DOM-heuristic classifier (`scripts/salonboard_root_cause.py`, see its own
docstring) was built and works end-to-end, but the user judged rule-based classification
too likely to misjudge edge cases to trust unattended — see the four patterns below, where
detecting the fourth is markedly less certain than the other three. The standing decision:
**M/N stays a manual-trigger task** — the user says "今週分お願い" (or similar) on
whatever day suits that week, and a session does exactly what this file's earlier
2026-09-03 entry describes: open salonboard.com in the user's own real, already-logged-in
Chrome (`mcp__claude-in-chrome__*`, never the sandboxed browser — see
`hpb-salonboard-update/SKILL.md` rule 1) and judge each ✕ shop's schedule screen directly,
the same way this session did for the first 19 shops.

**Why not a GitHub-event-triggered cloud routine instead of a manual message, then?**
Investigated 2026-09-03: the mechanism exists (`RemoteTrigger`'s `create_webhook_trigger`,
already used by this repo's Chatwork-request routine to fire off a GitHub Issue). But that
same existing routine's own prompt states the blocker plainly: a cloud routine has no
access to the user's real, already-authenticated Chrome — `mcp__claude-in-chrome__*` only
works from a session running on the user's own machine. A cloud routine could in principle
log into SalonBoard fresh with stored credentials and judge screenshots via its own
sandboxed browser instead, but that means an unfamiliar datacenter IP authenticating into
a shared ~150-salon production admin account for the first time — plausibly enough to
trip fraud/2FA verification that would silently stall the run. Untested and not something
to gamble on without the user explicitly signing off first.

The 4 M/N categories, and the DOM signal each one keys off (confirmed live 2026-09-03 on
real salonboard.com schedule pages via `mcp__claude-in-chrome__javascript_tool`):

| M | N | Signal |
|---|---|---|
| 対象外 | 定休日 | page text contains "休業日です" |
| ○ | 実予約あり(誤検知) | `.scheduleReserveName` element present (a real customer reservation; deliberately not reading its text — that's PII) |
| ✕ | 予定あり(枠ブロック) | `.todoTitle` text contains "予定あり" (covers both the スタッフ予定 and ベッド/設備予定 sub-cases the user distinguished — `.scheduleToDo.staffTask` vs `.scheduleToDo.equipmentTask` — both collapse to the same simple label per the user's own choice) |
| ✕ | 一括停止(警告) | least-validated category: `.scheduleTimeTableReserveCount` all "0"/"-" AND page text contains "一括停止". Only ever confirmed on one real shop (上板橋駅前) via screenshot, never against the live DOM — spot-check this one specifically before trusting `--apply` |
| 要確認 | 要確認 | anything not clearly matching the above — the deliberate safe fallback, not a bug |

**Before ever running `--mode apply` for real**: `--mode verify-login` must be run once,
manually, and confirmed working. The login step (`SALONBOARD_LOGIN_URL` /
`SELECTOR_USER_ID` / `SELECTOR_PASSWORD` / `SELECTOR_SUBMIT` constants near the top of
`salonboard_root_cause.py`) was written from general knowledge, **not verified against the
real login page** — deliberately, to avoid testing login against the live production
本部 account by trial and error (which risks lockouts). `hpb-salonboard-update/SKILL.md`'s
long-standing rule was "never automate the SalonBoard password, always have the user log
in" — this script is the first exception to that, made with the user's explicit go-ahead
(2026-09-03, in exchange for scheduled/unattended M/N classification). If `verify-login`
fails, open the real login page, read off the actual field selectors, and fix the
constants — don't loop retrying guesses against the production account.

**The salon-selection click cannot be done via a stable URL/href.** salonboard.com's
`/CNC/groupTop/` salon list renders each salon name as `<a href="javascript:void(0);">`
with no `onclick` attribute and no `data-*` id — the click handler is attached via JS
event delegation, invisible to static DOM inspection. The only thing that reliably works
is a real click on the visible name text (confirmed 2026-09-03: `page.get_by_text(name,
exact=True).click()` in Playwright, matching how a real browser click was confirmed to
work manually). Once inside a salon, every other page (schedule, coupons, etc.) is
directly `goto()`-able by URL — the session holds the salon context — so this click is the
only non-URL-addressable step in the whole flow.

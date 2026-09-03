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

## Downstream, not-yet-built: SalonBoard-side root-cause check for ✕ slots

The business goal this notebook feeds is: for every slot this scraper judges ✕, a human
currently manually opens the salonboard.com admin backend to tell apart "✕ because of a
genuine customer reservation" (fine) from "✕ because staff manually blocked the slot" (a
problem worth flagging). Automating that second-stage check (likely via the
`salonboard-operator` agent / `hpb-salonboard-update` skill, writing a verdict into a new
column — M列 was discussed — of "AIチェック用") has been discussed but not yet implemented.
If picking this up, start from that framing rather than re-deriving it.

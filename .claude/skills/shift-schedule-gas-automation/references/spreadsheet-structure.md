# Spreadsheet structure (下総中山 休暇シート)

This describes the layout as it stood at the end of the source session. If the sheet has been restructured again since, re-verify with the xlsx-download technique in `gas-delivery-workflow.md` before trusting any of this.

## File organization

- Originally one spreadsheet held both stores (駅前 / 北口) with the script looping over both. Mid-project this was deliberately restructured to **one spreadsheet file per store**, each with its own copy of the script and a `STORE_LABEL` constant identifying it (e.g. `'下総中山駅前'`, `'下総中山北口'`). This makes duplicating the tool to a new store a copy-and-relabel operation instead of a code change.
- Each file has a template sheet named **原本** (never overwritten, always the copy source) and monthly sheets.
- Monthly sheet naming: **"YYYY年M月"** (e.g. `2026年9月`), not just `9月` — changed specifically so the tool keeps working across year boundaries without name collisions, since the user intends to keep using this indefinitely.
- Newly generated monthly sheets are inserted immediately to the right of **原本**, in creation order.

## Calendar grid (within a monthly sheet)

- Date rows: **4, 8, 12, 16, 20** (five week-rows for a 5-week calendar).
- Day-of-week column pairs (each day occupies 2 columns):
  - A:B = 日 (Sun), C:D = 月 (Mon), E:F = 火 (Tue), G:H = 水 (Wed), I:J = 木 (Thu), K:L = 金 (Fri), M:N = 土 (Sat)
- Each date row is followed by **3 rows** used for staff-name entry for that day (physical capacity: 3 names per day cell block).
- Font color conventions:
  - **Red (#ff0000)** = a staff member's manually-entered requested day off (希望休), entered before the automation runs. Also used for Sunday-column dates and, once the holiday feature was added, national holidays.
  - **Blue** = Saturday-column dates.
  - **Black** = auto-filled regular days off written by the script.
- Background color conventions (must be preserved/regenerated correctly — this was a recurring bug source):
  - The date row itself and the 3 entry rows below it use **different** background colors and must be set independently — a fix that copies one color into all 4 rows will overwrite the other group (this happened once: date-row white was pushed into entry rows, wiping out their green).
  - Valid-day cells get one background color (green observed); cells for days that don't exist in the given month (e.g. Feb 30) must be forced to a distinct color (black observed) — this must be actively reset on every generation, not just left over from the copied template, because the previous month's out-of-month cells otherwise bleed through.
  - **Always source the "correct" reference color/format from week 2 (the row for days 8–14)**, never from week 1. Week 1's columns rotate which day-of-week gets a real date depending on the month, so a column that has *never* held real data (e.g. column A/Sunday in a month starting on a Tuesday) can carry stale leftover formatting (font size, alignment) that looks fine until a month finally puts a real date there.

## Staff roster location (within a monthly sheet)

- The roster (list of that store's staff names) is **not** at a fixed cell address — it varies per sheet (e.g. 駅前9月 and 北口9月 both had it at B29, but the 原本 template had it at A26).
- Correct approach: **search the sheet for the literal string "名前"** to find the roster header, then read/write names relative to that found position. Never hardcode a roster cell address.

## Summary / double-check columns

- Right-side table, columns **P/Q**: P = staff name (written by the automation after it finishes, up to 8 rows), Q = a **pre-existing formula** (`=COUNTIF($A$4:$N$25,P5)`-style) that recomputes each person's total day-off count once P is filled — this is the user's manual double-check that the auto-fill plus the red requested-days sum to the target quota. The script only ever needs to write column P; Q recalculates itself.
- A separate bottom summary table (名前／有給／研修／特別休／DW) exists on the sheet but was **not** part of this automation — informational only, found during the initial structure read.
- "取得可能" (available quota) cell, **P1**: written by step ① (月次シート作成) when the user enters the target public-holiday count for the month. Step ② (公休自動入力) reads this cell to auto-detect the quota instead of asking again, and only asks the user to confirm the detected number.

## スタッフマスター (staff master) tab

Created via the script's own "スタッフマスターの雛形を作成" menu item. Final column set at end of session:

| Column | Meaning | Notes |
|---|---|---|
| 名前 | Staff name | Can be entered as full name ("姓 全角/半角スペース 名"); the script keys internally by **surname only** and warns on surname collisions. Calendar entries use surname only — this must match. |
| 性別 | Gender | Single character, "男" or "女" — matching logic checks for **substring "女"**, not exact match "女性" (an earlier version bugged on this). |
| 資格 | Qualification | Free text, e.g. 柔道整復師 (judo therapist), 鍼灸師 (acupuncturist). |
| 新患対応 | Handles new patients | "〇" or blank. |
| 院長 | Is the store director | "〇" or blank; added later in the project to support the early-month day-off cap (see business-rules.md). |

- A **所属店舗** (branch) column existed briefly (added when the file still covered multiple stores) but was **removed entirely** once the spreadsheet was split to one-file-per-store — don't re-add it unless the file goes back to covering multiple branches.
- Template column widths must be set to **fixed pixel widths**, not auto-resize-to-header text, or the sheet renders unusably narrow: 名前 120px, 性別 90px, 資格 160px, 新患対応 110px. (院長's width wasn't explicitly pinned in the observed transcript — check it and fix similarly if it looks cramped when adding it to a new template.)

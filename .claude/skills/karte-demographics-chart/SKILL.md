---
name: karte-demographics-chart
description: Use this skill whenever the user asks to build gender-ratio (男女比) and/or age-bracket (年代構成) charts from a Google Sheet of their 整骨院 (chiropractic) clinic group's カルテ (patient chart/record) data — e.g. "男女比と年代構成のグラフを作って", "年代構成のグラフを作成して", "男性・女性それぞれの年代構成も出して", "全店舗の傾向が見たい", "比率も追加して". Also trigger on "カルテ一覧", "男女比", "年代構成", "性別・年代別" mentioned alongside a Google Sheets link, or any request to turn patient demographic columns (gender/age) into a chart inside that spreadsheet. Do NOT trigger for SalonBoard/HotPepper Beauty listing or coupon work (see hpb-salonboard-update) — this is about internal karte data, a different system entirely. Do NOT default to per-store (店舗別) breakdowns; this workflow's default is whole-group aggregation unless the user explicitly asks for store-level splits.
---

# Karte Demographics Chart (男女比・年代構成)

Builds gender-ratio and age-bracket demographic charts for the user's 整骨院 (chiropractic) clinic group, aggregated across **all stores as one group** (not per-store), directly inside the Google Sheet that already holds the raw monthly カルテ一覧 (patient record list) export. Adds a new tab containing live aggregation tables and native Google Sheets charts — extracted from a session that built exactly this (男女比 pie chart, 年代構成 column chart, then a男女別年代構成 grouped chart plus percentage columns, added incrementally as the user asked for more).

## Non-negotiable rules

1. **Whole-group aggregate by default.** The founding request was explicit: "店舗別はいらないです。全店舗、つまりグループとしての傾向を見たいです。" Never break results out by store unless the user asks for that explicitly in the moment.
2. **Aggregate with live formulas (COUNTIF/COUNTIFS) referencing the raw data sheet — never paste static computed numbers.** The whole point is that re-running this next month (new カルテ data pasted into the raw sheet) should make every table and chart recalculate on its own.
3. **Build inside the same spreadsheet, in a new tab** — don't export to a separate file or a different doc.
4. **Never type Japanese text or formulas into a Google Sheets cell via direct keystroke automation.** It is unstable in this environment (confirmed in the source session — it silently mangled input) and doing it live wastes time discovering that again. Always use the clipboard-paste technique described in `references/sheets-input-technique.md` from the start.
5. **Match whatever formatting convention already exists in the sheet rather than inventing your own.** In the source session the user had already added a percentage column with a specific decimal-place style before asking for more ratio columns — the correct move was to copy that exact format (1 decimal place, e.g. "21.4%"), not pick a new one.
6. **Cross-check totals before reporting done.** Every subtotal that should logically match another (e.g. the sum of a gender's age-bracket counts vs. that gender's grand total) must actually match. This was verified at every step in the source session and caught nothing wrong, but it's a real correctness gate — a mismatch means a formula or range is off, not a "close enough" situation.

## Data this workflow expects

Raw data lives in a sheet (typically named `シート1`) with one row per patient-visit record, all stores mixed together. Two columns matter: gender and age. Exact column letters vary by spreadsheet — confirm them before writing formulas rather than assuming. See `references/data-and-aggregation.md` for the exact column layout, age-bracket definitions, and formula patterns observed in the source session.

## Standard procedure

1. Read the raw data sheet first (a file-content/read tool against the Sheet, not the browser) to confirm row count, gender column, age column, and any header quirks — don't guess column letters from a screenshot.
2. Open the spreadsheet in the browser, create a new tab, name it descriptively (source session used `男女比・年代構成`).
3. Build the gender-ratio table (counts + %) and the age-bracket table (counts + %) using COUNTIF/COUNTIFS against the raw sheet — see `references/data-and-aggregation.md` for bracket boundaries and formula shape. Use the clipboard-paste technique (rule 4) to get labels and formulas into cells.
4. Insert a chart per table: pie chart for gender ratio, column chart for age brackets. Set a clean, short title on each via the chart editor's title panel (not the auto-generated default) — see `references/sheets-input-technique.md` for the exact click path.
5. If the user asks to break age out by gender too (a common follow-up, as it was here): add a 年代 × 男 × 女 cross-tab (COUNTIFS with both conditions), then a grouped/clustered column chart from it.
6. If the user asks for ratios on the gender-specific breakdown: compute each cell's percentage **within that gender's own total** (so male% column sums to 100%, female% column sums to 100% — not both relative to the grand total), formatted to match whatever ratio column already exists in the sheet (rule 5).
7. Reposition charts so they stack cleanly without overlapping — do this by dragging, and double-check you grabbed the intended chart (the source session once misclicked and dragged the wrong one).
8. Verify totals (rule 6), then report back: a compact summary table of the final numbers/ratios, plus 1-2 sentences of actual interpretation (e.g. which gender skews toward which age brackets) — the user engaged with and valued this framing in the source session, not just raw numbers.

## Recurring cadence (assumption — confirm with user)

The founding request referred to "先月の...カルテ一覧" (last month's record list), which suggests this may be a **monthly** reporting task reusing the same spreadsheet with fresh data appended each month. This was not explicitly confirmed as recurring in the source session — treat it as a likely-monthly report until the user says otherwise, and if the raw data sheet already has this month's rows by the time this runs again, the live-formula approach (rule 2) means the existing tab's tables/charts should just update in place rather than needing to be rebuilt.

## Reference files

- `references/data-and-aggregation.md` — raw data column layout, age-bracket boundaries, and the exact COUNTIF/COUNTIFS formula patterns used.
- `references/sheets-input-technique.md` — the clipboard-paste workaround for unstable Japanese text entry, and the chart-creation/title-setting/repositioning click path in Google Sheets via browser automation.
- `references/background.md` — narrative of the source session: what was asked, in what order, and why each follow-up request was handled the way it was.

## 並行セッション対策

他のセッションがこのSkillを同時に使っている可能性がある間は、`SKILL.md`や`references/*.md`を
直接編集しない。学習は`learnings/`配下に新規ファイルとして置き、gitコマンド(`add`/`commit`/
ブランチ切り替え)は実行しない。タスク開始前に`learnings/`を読むこと。詳細・統合手順は
[`../hpb-salonboard-update/references/concurrent-sessions.md`](../hpb-salonboard-update/references/concurrent-sessions.md)を参照。

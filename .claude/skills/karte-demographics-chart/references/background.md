# Background: how this workflow came about

Source session: "性別・年代別グラフ作成" (`local_c3415f8f-a3e8-43d2-abc0-5839b755e322`).

## Context

The user (t-kuribayashi@keizgroup.jp) works for a company running roughly 150 整骨院 (seikotsuin/chiropractic) clinics — the same clinic group covered by the `hpb-salonboard-update` and `hpb-crm-reconciliation` skills, but this session was about a different data source and a different purpose: not SalonBoard listing/coupon maintenance, and not CRM×HPB visit reconciliation, but a **demographic report built from the group's own カルテ (patient chart/record) data**, for internal analysis rather than any external platform.

The user opened the session by sharing a Google Sheets link described as "先月の当社整骨院グループのカルテ一覧" (last month's patient-record list for our clinic group) and asked for two charts: 男女比 (gender ratio) and 年代構成 (age-bracket composition), built as a new tab inside that same spreadsheet. Two constraints were stated up front and turned out to matter a lot:

- "店舗別はいらないです" (don't break it out by store) — the user wanted the whole-group trend, not 150 separate slices.
- "全店舗、つまりグループとしての傾向を見たいです" (all stores together — i.e. I want to see the group-level trend) — reinforcing the same point, which is why it's called out as a non-negotiable rule rather than just a one-time preference.

## How the work actually unfolded

1. **Data discovery first.** Before touching the spreadsheet's UI, the assistant read the sheet's raw content via a file-content tool to find where gender and age actually lived (column G for gender, column Q for age, on a sheet named シート1) rather than guessing from a screenshot. This groundwork made every later formula correct on the first try.

2. **Direct typing into Sheets cells failed.** The assistant's first attempts to enter the aggregation labels/formulas by simulating keystrokes into cells did not reliably work for the Japanese text involved. It pivoted to writing the intended block of text to the clipboard via `javascript_tool` and pasting instead — this became the standard technique for the rest of the session and is the single most load-bearing technical discovery to carry forward (see `sheets-input-technique.md`).

3. **First deliverable: two charts, all-store aggregate.** A 男女比 pie chart (男 17,850 / 47.7%, 女 19,533 / 52.3%, その他・不明 0) and a 年代構成 column chart (10-year buckets, bell-curve shape peaking at 30–40代) were built from COUNTIF/COUNTIFS formulas referencing シート1 directly, so the numbers stay live if the raw data sheet is ever updated. The assistant proactively noted the "その他・不明" bucket even though it was zero, rather than dropping it — a good habit, since a future month could have a nonzero value there.

4. **First follow-up: break age out by gender.** The user asked "男性、女性それぞれの年代構成も出してください" (also show the age composition separately for men and women). The assistant added a 年代×性別 cross-tab using COUNTIFS with both a gender and an age condition, then built a grouped/clustered column chart from it (男/女 side by side per age bracket), verifying the new table's male/female column sums matched the original gender totals (17,850 / 19,533) before considering it done.

5. **Second follow-up, with a real correction: add ratios, and match existing style.** The user pointed out something the assistant hadn't noticed: "全体の年代構成比は、私がC列に比率を出していますよね？" (I already have the overall age-bracket ratio in column C, you know) — i.e. the user had pre-existed a percentage column with its own formatting convention, and the assistant's job was to extend that pattern consistently, not invent a new one. The user then asked for the same treatment on the new male/female breakdown table. The assistant:
   - Inserted two new columns (male %, female %) next to the existing male/female count columns.
   - Computed each percentage **within that gender's own total** (male% column denominators sum to the male total, female% likewise) rather than against the grand total — this is a real substantive choice, not just formatting, and it's the mathematically correct one for "each gender's own age composition."
   - Matched the exact display format already used in column C: percentages to 1 decimal place (e.g. "21.4%").
   - Verified both new ratio columns summed to ~100% before reporting done.

6. **Final report included interpretation, not just numbers.** Each time, the assistant closed with 1-2 sentences of actual trend commentary (e.g. "female skews more toward 20代, male skews more toward 30-40代") rather than just restating the table. This was not explicitly requested but wasn't corrected either — treat it as a welcomed default, worth continuing.

## Why this is captured as a skill

The session covered a complete, self-contained demographic-reporting pattern (read raw data → aggregate with live formulas → build titled charts → extend on follow-up → verify totals → summarize with interpretation) built entirely through Google Sheets browser automation, with one significant technical gotcha (clipboard-paste over direct typing) that would otherwise have to be rediscovered from scratch next time. The founding request referenced "先月の...カルテ一覧" (last month's data), suggesting this may recur monthly, but that cadence was never explicitly confirmed by the user in this session — it's an inference, not a stated fact.

## Note on eval-loop applicability

This workflow is chart/report generation from data, which is the category `session-to-skill`'s ground rules flag as a possible candidate for skill-creator's automated eval loop (no live external system, pure data-in/chart-out) — worth considering as a rule-of-thumb. In practice, though, this specific workflow's *output* is inseparable from live browser automation against the user's real, existing Google Sheet (creating a real tab, real charts, positioned in a real UI) — it's not a standalone script producing a file. Running a full automated benchmark loop against the actual production spreadsheet isn't advisable. If an eval loop is wanted later, the safer version would be: duplicate the spreadsheet (or synthesize a small fake カルテ dataset in a scratch sheet) and run the workflow against that copy, so any automated/synthetic runs never touch the user's real clinic records.

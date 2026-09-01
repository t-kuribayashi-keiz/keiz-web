# Data layout and aggregation formulas

## Raw data source (observed in the source session)

- One Google Spreadsheet, raw data on a sheet named `シート1` (Sheet1).
- One row per patient/karte record. Source session's monthly extract had 37,383 rows, all stores combined in one sheet (no separate per-store tabs to worry about).
- Relevant columns (confirmed by actually reading the sheet's content first — do this every time, don't assume the letters below are stable across spreadsheets or months):
  - **Column G** — 性別 (gender). Observed values: 男, 女. The aggregation also accounted for a possible "その他・不明" (other/unknown) bucket, which came out to 0 in the source month but the formula/table should still have a row for it so it doesn't silently disappear if it's ever non-zero.
  - **Column Q** — 年齢 (age), numeric.
- Always re-verify column letters against the actual header row before writing formulas — do not assume G/Q hold in every spreadsheet this is run against.

## Age-bracket definitions

Ten-year buckets, labeled exactly like this (matches what the user's own spreadsheet convention expects):

| Label | Age range |
|---|---|
| 10歳未満 | age < 10 |
| 10代 | 10–19 |
| 20代 | 20–29 |
| 30代 | 30–39 |
| 40代 | 40–49 |
| 50代 | 50–59 |
| 60代 | 60–69 |
| 70代 | 70–79 |
| 80代以上 | age >= 80 |

## Formula patterns

All formulas reference the raw sheet directly (never paste computed static numbers), so the tables recalculate automatically when new rows are added to the raw sheet.

**Gender count** (example, assuming raw data column G, sheet `シート1`, full-column reference or bounded to the actual data range):
```
=COUNTIF(シート1!G:G, "男")
=COUNTIF(シート1!G:G, "女")
```

**Gender ratio (%)** — divide by the grand total, format as percentage with 1 decimal place (matches the convention already present in the source sheet's own column C):
```
=B2/SUM($B$2:$B$4)
```

**Age-bracket count** (example for the 30代 bucket, age column Q):
```
=COUNTIFS(シート1!Q:Q, ">=30", シート1!Q:Q, "<40")
```
The under-10 and 80+ buckets only need one bound each (`<10` and `>=80` respectively).

**Gender × age-bracket count** (cross-tab, adds the gender condition):
```
=COUNTIFS(シート1!G:G, "男", シート1!Q:Q, ">=30", シート1!Q:Q, "<40")
=COUNTIFS(シート1!G:G, "女", シート1!Q:Q, ">=30", シート1!Q:Q, "<40")
```

**Gender × age-bracket ratio (%)** — critical detail: divide by **that gender's own column total**, not the grand total, so each gender's ratio column independently sums to 100%:
```
=B19/SUM($B$19:$B$27)   ' male %, denominator = male total
=C19/SUM($C$19:$C$27)   ' female %, denominator = female total
```
This was an explicit correction the user made — an early instinct to divide by the grand total for everything would have been wrong here.

## Verification checklist (do this every time before reporting done)

- Sum of the two (or three, if その他・不明 is nonzero) gender counts equals the grand total row count.
- Sum of all age-bracket counts equals the grand total.
- Sum of the male age-bracket counts equals the male grand total from the gender table; same for female.
- Each ratio column sums to ~100% (allow for rounding display only, e.g. 99.9%/100.1%).

In the source session these were: 男 17,850 (47.7%), 女 19,533 (52.3%), その他・不明 0 (0%), total 37,383 — and the male/female age-bracket counts summed exactly to 17,850 and 19,533 respectively.

# Reconciliation logic — `reconcileData()` in `集計自動化.gs`

This is the full understanding of the algorithm as confirmed with the user in the session this skill was extracted from (2026, the "菊池" bug-fix session). Treat this file as the living spec: whenever a fix changes one of these rules, update this file in the same pass so it doesn't drift from the deployed code.

## Spreadsheet / project identity

- Spreadsheet: `https://docs.google.com/spreadsheets/d/1zuOHVBBDmwsy0gSab1GEYLsMWvTm772q2eKqyo6hiMQ/edit` (tab gid varies by sheet).
- Bound Apps Script project name: `gen-ac-sheets`.
- 5 files exist in the project; only **`集計自動化.gs`**, function **`reconcileData()`** (~490 lines), is currently active/live. The other four (`code.gs`, `temp.gs`, `main.gs`, `merge-name.gs`) are legacy versions built around カルテNo/サロンボードID keys and different sheet names (`CRMと比較`, `table`, `temp_data`) that no longer exist in this spreadsheet — do not edit them.
- Re-verify "which file is active" by checking that the sheet/column names referenced in the code (below) still match the spreadsheet's actual tabs and headers — don't just trust this file if a long time has passed.

## Input sheets

- **`CRM`** — カルテ (patient record) data: 院名 (store name), カルテNo, 姓/名, 姓名, かな/カナ, 初回来院日 (first visit date), 電話番号, 携帯番号, 合計 (total), 初回来院動機 (first-visit motivation/source), etc.
- **`HPB`** — SalonBoard CSV import data: お店名 (store name), 来店日 (visit date), メニュー, HPBクーポン (coupon used), 電話番号, 氏名 (kana and kanji), 金額 (amount), etc.
- **`店舗名マッチ用`** — lookup table mapping HPB store-name spellings to CRM store-name spellings.
- **`店舗表示順`** — display/sort order for stores in the output.

## Normalization

- Hiragana → katakana conversion; whitespace stripped, for all name/kana comparisons.
- Store names are normalized by stripping suffix words (接骨院/整体院/整骨院/総合治療院/鍼灸院/院, and parenthetical qualifiers) into a bare matching key.
- Phone numbers: digits-only extraction; if 9+ digits and no leading 0, a leading 0 is prepended (to normalize mobile/landline formats consistently).

## CRM-side preparation

- Dedup: when store + kana name match, the record with the **oldest 初回来院日 (first visit date)** is kept as canonical (handles duplicate karte registrations for the same person).
- From the deduped set, build lookup maps for: store+kana exact match, store+kanji exact match, store+phone, and kana+phone (store-agnostic) — plus a per-store list of all customers, used for fuzzy candidate search.
- Only CRM rows whose 初回来院動機 (first-visit source) **contains "ホットペッパー"** are eligible to appear in the final output's CRM side.

## HPB-side preparation

- Rows are de-duplicated on the composite key store+kana+phone.
- **Strict split mode**: if the お名前 (name) column and 氏名(漢字) column are exactly equal, the name is split into surname/given-name on the space, enabling exact-match checks (used in one specific tie-break, referenced in code as columns Z/AD).
- Aggregates computed per customer: same-person same-month visit count (used for the ① monthly-repeat highlight) and same-person same-day visit count (used for the ⑥ same-day-warning override below).

## Matching priority (evaluated in this order; first match wins, except rule 6 which is an override applied after)

1. **Store + kana exact match** → 🟩 green if CRM-side motivation contains "ホットペッパー", else 🟨 yellow ("動機がホットペッパー以外" — contradiction: matched but the CRM record wasn't sourced from HPB).
2. **Store + kanji exact match** → same green/yellow split as above.
3. **Kana + phone match, ignoring store** → 🟦 light blue, "店舗相違" (store mismatch — registered under a different store's CRM).
4. **HPB coupon name contains "既存様限定"** (existing-customer-only coupon) → 🟢 dark green, "既存客向けクーポン使用".
5. **None of the above matched** → evaluate fuzzy candidates:
   - Store + phone only → 🩷 pink, "電話番号一致（家族の可能性）" (phone match, possible family member).
   - Name match or surname match (prefix/suffix match, or exact match when strict split mode applies) → collect candidates, then pick one by: **closest date difference first**, tie-broken by full-name match > surname-only match, tie-broken again by longer full-name string → 🩷 pink, "名前一致（本人の可能性）" or "名字一致（家族の可能性）".
   - No candidates at all → 🟧 orange, unmatched / possibly not yet in CRM.
6. **Override, applied last**: if the same store + kana + phone + date has 2+ HPB bookings on the same day → 🔵 blue, "【警告】同日に2回以上の予約あり" (warning: 2+ same-day bookings), overwriting whatever color rules 1–5 produced.

### Fix applied in the extraction session: same-day/same-surname priority over kana collision

Rules 1–2 above used to be unconditionally final — the moment a store+kana or store+kanji exact match was found, it was taken with no date sanity check. This broke when two different real people shared the same kana reading but different kanji (e.g. two customers both reading as "きくちまゆ" — one written 真由, one 真優 — one visited on a different date than the actual match). The reported symptom: a customer's HPB visit was matched to a same-kana CRM record whose visit date was 9 days off, while the real match (a same-surname relative, exact date match, noted as "夫が伺います" in CRM remarks) was never even considered because rule 1 fired first and short-circuited the whole priority chain.

**Fixed behavior**: after an exact store+kana or store+kanji match is found (rules 1–2), check whether that matched record's 初回来院日 equals the HPB 来店日. If it does — nothing changes, existing behavior holds. If it does **not**, search for an alternative CRM candidate in the same store with the same surname AND an exact date match; if found, prefer that candidate instead, classified as 🩷 pink "名字一致（同日来店を優先・家族の可能性）". This check was inserted directly after the original rules 1–2 (around line ~298–300 of `reconcileData()` as of the extraction session — re-locate by content, not line number, since line numbers shift).

### Fix applied in the extraction session: monthly-repeat highlight

New highlight rule, independent of the color/判定 logic above: if a customer's same-month visit count (`hpbObj.monthlyCount`, computed in HPB-side prep) is **2 or more**, the R (判定), S (備考), and T (月間予約数) cell backgrounds are overwritten to light blue `#cfe2f3`, regardless of whatever color rules 1–6 assigned. This is purely a highlight layer applied last — it does not change the underlying 判定/備考 text, only the background color, and only for R/S/T on that row.

Note on the spec ambiguity that produced this: the user's original phrasing was "予約回数が1以上の場合" (if visit count is 1 or more), which is literally true for every single row (every visit counts as at least 1). The real intent, confirmed via a clarifying question before implementing, was "more than one" — i.e. flag repeat/duplicate monthly bookings, not every row. The condition implemented is `monthlyCount >= 2`. The exact question/answer exchange wasn't preserved in the extracted transcript (tool-call content is elided in the session log used to build this skill) — if this comes up again, double check the current threshold intent with the user rather than assuming `>= 2` is still exactly right for a new similar request.

## Output

- A new sheet named `{検出年月}突合シート` (e.g. "2026年07月突合シート") is created per run, sorted by store display order (`店舗表示順`), with CRM columns (left, 9 columns) and HPB columns (right, 12 columns) placed side by side per matched date.
- If a sheet with that name already exists, a suffix like "(2)" is appended automatically rather than overwriting.
- 判定 (verdict) and 備考 (notes) columns carry the color coding described above as cell background colors.
- **Existing output sheets are snapshots** — re-running `reconcileData()` after a code fix is required to see the fix reflected anywhere; past sheets never update retroactively.

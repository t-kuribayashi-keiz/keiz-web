---
name: hpb-crm-reconciliation
description: Use this skill whenever the user asks to modify, debug, fix, or explain the CRM×HPB data reconciliation Google Apps Script that matches HotPepper Beauty/SalonBoard visit data against the company's CRM (カルテ) records across the chiropractic salons this reconciliation spreadsheet covers (scope not yet confirmed — see the note on salon count below) — e.g. "突合ロジックを直して", "この判定がおかしい", "◯◯様の一致相手が違う", requests to change color-coding/判定色, matching priority order, name/kana matching rules, or add a new judgment case in `集計自動化.gs` / `reconcileData()`. Also trigger on mentions of "突合シート", "突合ロジック", the reconciliation spreadsheet, GAS/Apps Script tied to CRM-HPB matching, or reports that a specific customer's match result looks wrong. Do NOT trigger for SalonBoard website coupon/content edits (that's the separate hpb-salonboard-update skill) — this skill is specifically about the Google Sheets + Apps Script reconciliation tool, not the salonboard.com admin UI.
---

# HPB × CRM Data Reconciliation (GAS)

Operational playbook for maintaining the Google Apps Script (GAS) that reconciles HotPepper Beauty (HPB/SalonBoard) visit data against the company's CRM (カルテ/patient record) data, across the chiropractic salons (整骨院/接骨院/整体院) this reconciliation spreadsheet covers. The script lives in an Apps Script project bound to a specific Google Sheet, and its job is to flag, per customer visit, whether the CRM already has a matching record — and if not, why (name mismatch, different store, phone-only match, likely family member, etc.) — using a priority-ordered set of matching rules and color codes. See `references/reconciliation-logic.md` for the full current algorithm and `references/background.md` for how this came to be and the fixes already made.

**On salon count (updated 2026-09-03):** this SKILL.md previously said "~150" as a rough guess. `data/clinics.json` is now a confirmed store master with 204 entries as of 2026-09-03 (直営135・サンズミライ18・心身堂7・スマイル11・グッド7・リラックス25・LUNA1). That is a fact about the company's overall store count, not a fact about this spreadsheet — **whether this particular CRM×HPB reconciliation tool covers all 204, just the seikotsuin-type brands (直営+サンズミライ+心身堂+スマイル+グッド ≈ 178, excluding LUNA which is a pilates studio and リラックス which is a relaxation/massage salon, not 整骨院), or some other subset has not been confirmed.** Don't assume a scope and don't restate "~150" as if it were still the best number — if the exact coverage matters for a task, ask or check which stores actually appear in the CRM/HPB source sheets.

## Non-negotiable rules

1. **Understand the whole algorithm before touching any code.** The reconciliation logic is one long function (`reconcileData()` in `集計自動化.gs`, ~490 lines) with several ordered matching rules feeding into a single color decision. A change in one branch can silently affect rows that fall through to a later branch. Before any fix, read (or re-confirm from `references/reconciliation-logic.md`) the full priority order, then confirm your understanding of the *specific* bug against real row data (see rule 3) before proposing a fix.
2. **Never let a fix touch logic outside what was asked.** The user has explicitly and standingly required this: *"今後の修正に関しては、基本的に修正箇所以外の突合ロジックには影響を与えないようにしてください"* (future fixes should not affect reconciliation logic outside the fix itself). Every fix must be a minimal, additive, scoped change to the one relevant branch/condition — never a refactor or rewrite of the surrounding function. When reporting a completed fix, explicitly state which other branches/rules were left untouched.
3. **Only one file is live.** The Apps Script project has 5 files; only `集計自動化.gs` (function `reconcileData`) is currently active — confirmed by cross-checking the sheet/column names it references (`CRM`, `HPB`, `店舗名マッチ用`, `店舗表示順`, and the output header row) against what's actually in the spreadsheet. The other four (`code.gs`, `temp.gs`, `main.gs`, `merge-name.gs`) are legacy versions keyed on different concepts (カルテNo/サロンボードID) and different sheet names (`CRMと比較`, `table`, `temp_data`) — never edit these by mistake. Re-verify this mapping if the spreadsheet's tabs or headers have changed since, rather than assuming it's still true.
4. **Investigate real data before diagnosing.** When the user reports a specific wrong match (e.g. "customer X's match is showing customer Y"), pull the actual CRM and HPB row values for that case first — don't reason from the bug description alone. The one bug fixed so far turned out to hinge on a same-kana-different-kanji name collision that was invisible without checking raw cell values.
5. **Ask before implementing an ambiguous spec.** If the user's requested rule has more than one plausible reading (e.g. "予約回数が1以上" is literally true for every row, since every row has at least 1 visit — the real intent turned out to be "more than one," i.e. a duplicate/repeat booking flag), stop and ask a clarifying question before writing any code. Implementing the literal-but-wrong reading would miscolor rows silently.
6. **Verify the edit actually landed before saving, and verify the save.** Editing happens directly in the Apps Script (Monaco) editor. Confirm the inserted code is visibly present in the editor after the edit (a naive DOM-injection technique used for reading file contents can visually corrupt/clobber the editor if not cleaned up first — reload the page if that happens) and confirm the file shows a "saved to Drive" state (no unsaved-change indicator) before considering the task done.
7. **A fix does not retroactively update past output sheets.** Each month's reconciliation output (e.g. "2026年07月突合シート") is a static snapshot from when `reconcileData()` was last run — fixing the code never changes an existing sheet. To show the user the fix working, `reconcileData()` must be re-run (via the sheet's own 実行 button, or from the Apps Script editor), which creates a fresh output sheet (auto-suffixed "(2)", "(3)", ... if a same-named sheet already exists). Always tell the user this and offer to re-run it or ask them to.

## Standard workflow

1. **On first contact with this spreadsheet, or if it's been a while, re-derive/confirm the full algorithm** rather than assuming memory of it is current — read the live Apps Script source (see `references/apps-script-editing.md` for how, since the code is not in any spreadsheet cell) and check it still matches reality: same active file, same sheet names, same column headers. Recap the full understanding back to the user in the same structure as `references/reconciliation-logic.md` and get explicit confirmation before taking any fix requests.
2. **When the user reports a problem, gather the specific evidence**: which output sheet, which row(s), and the actual underlying CRM/HPB source rows for that customer (fetch real cell values, don't just eyeball a screenshot of the output sheet).
3. **Diagnose against the priority-ordered rule list** (`references/reconciliation-logic.md`) — identify exactly which rule fired, why, and which rule should have fired instead.
4. **If the requested new rule/threshold is ambiguous, ask first** (rule 5 above).
5. **Propose a minimal fix**: name the exact branch/condition being changed and confirm nothing else changes. Get the user's go-ahead if the fix is non-trivial (for small, clearly-scoped literal bug fixes matching what the user already described precisely, proceeding directly is fine — use judgment the same way you would for the ambiguity check).
6. **Implement in the Apps Script editor** using a precise, position-based insertion (not a broad find/replace) so an accidental duplicate string elsewhere in the 490-line function can't cause the wrong spot to be edited. See `references/apps-script-editing.md` for the exact technique and its pitfalls.
7. **Confirm the change is visible in the editor, then save, then confirm the saved state.**
8. **Report back**: what changed and where (line range/branch name), explicit confirmation that other branches are untouched, and the reminder from rule 7 that existing output sheets need a re-run to reflect the fix. Offer to re-run `reconcileData()` yourself or ask the user to.
9. **Log the task** the same way other recurring HPB work is logged for this user (see Logging below) — this hasn't been established inside this specific workflow yet, so treat it as a reasonable default to propose rather than an already-confirmed requirement.

## Logging

This user tracks work time, token consumption, and plan-quota impact for recurring HPB-related tasks (see the sibling `hpb-salonboard-update` skill's logging convention). This specific reconciliation-script workflow hasn't had that convention set up yet in any observed session, but it's the same overall business process (CRM×HPB matching for the same salon group — see the salon-count note above for the current, unconfirmed-scope figure), so unless the user says otherwise, follow the same pattern: after finishing a fix, append a row to `hpb_work_log.csv` in the working directory (create with header if missing) using columns adapted from the sibling skill —

`date,task,rule_changed,items_changed,session_start,session_end,tokens_effective,usage_session_pct_delta,usage_weekly_pct_delta,notes`

using the same task-bounded start/end timestamp method and effective-token computation described in `hpb-salonboard-update/references/token-usage-logging.md`, and the same before/after usage-quota screenshot approach in `hpb-salonboard-update/references/usage-quota-tracking.md`. Since this hasn't been confirmed for this workflow specifically, mention to the user once that you're logging it this way and let them redirect you if they'd rather not.

## Reference files

- `references/reconciliation-logic.md` — the full current matching algorithm: input sheets, normalization rules, matching priority order, color codes, output layout. Treat this as the living spec; update it whenever a fix changes the actual rules, so it stays in sync with the deployed code.
- `references/apps-script-editing.md` — how to read and edit the Apps Script project's source from a browser session (it's not stored in spreadsheet cells), including the extraction and position-based-edit techniques used, and their failure modes.
- `references/background.md` — narrative of how this workflow and skill came about, and the two fixes made in the session this skill was extracted from.

## 並行セッション対策

他のセッションがこのSkillを同時に使っている可能性がある間は、`SKILL.md`や`references/*.md`
(`reconciliation-logic.md`等)を直接編集しない。学習は`learnings/`配下に新規ファイルとして
置き、Loggingセクションの`hpb_work_log.csv`への追記も同様に`hpb_work_log.d/`配下へ1行1
ファイルで置く。gitコマンド(`add`/`commit`/ブランチ切り替え)は実行しない。タスク開始前に
`learnings/`を読むこと。詳細・統合手順は
[`../hpb-salonboard-update/references/concurrent-sessions.md`](../hpb-salonboard-update/references/concurrent-sessions.md)を参照。

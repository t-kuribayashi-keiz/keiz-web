---
name: shift-schedule-gas-automation
description: Use when the user wants to build, extend, fix, or duplicate a Google Apps Script that automates data entry into a staff shift/vacation (公休) calendar Google Sheet — e.g. "このスプレッドシートの入力を自動化するGASを作りたい", "月次シートを自動生成して", "公休を自動入力して", "スタッフマスターから条件を反映して", or requests to add/adjust scheduling constraints (資格ごとの必須人数, 女性スタッフの配置, 院長の休み制限, まんべんなく割り振る). Also trigger when the user wants to duplicate this kind of shift-scheduling tool to a new store/branch, or reports a bug in a previously-delivered .gs script (色がおかしい, 名前の表記がおかしい, 書式が崩れる, 二重に聞かれる, 偏りがある). This skill was built around the 下総中山 clinic's 休暇シート (駅前/北口 stores) automation tool specifically, but the underlying technique — structural analysis via downloaded xlsx, menu-driven GAS, iterative manual-paste delivery — generalizes to building similar spreadsheet-automation tools for this user.
---

# Shift-Schedule GAS Automation

## Overview

This skill covers building and maintaining a Google Apps Script (GAS) that lives inside a staff shift/vacation-calendar Google Sheet and automates two operations via a custom spreadsheet menu: (1) generating next month's calendar sheet from a template, and (2) auto-filling each staff member's remaining regular days off (公休) around their manually-entered requested days off, subject to a set of scheduling constraints (qualification coverage, gender/new-patient coverage, director's early-month cap, even distribution). It was developed iteratively for a clinic's 下総中山駅前/北口 stores and is meant to be extended and replicated to further stores over time — the user said outright they'll keep updating it as years pass.

There is no direct Apps Script deploy API available from this environment. Every code change is delivered to the user as a complete file; the user manually pastes it into Extensions > Apps Script in the target spreadsheet and saves it. Plan every change with that round-trip in mind.

## Non-negotiable rules

- **Never infer sensitive personal attributes from appearance.** When staff photos were provided, gender was explicitly *not* inferred from them — the user was asked directly instead. Always ask for missing スタッフマスター fields (性別 etc.) rather than guessing from a photo or name.
- **Confirm ambiguous constraint language before implementing it.** "できるだけ全出勤日に勤務" was confirmed to mean *category-level* coverage (≥1 female / ≥1 新患対応 staff present each day), not "this individual should almost never take a day off" — that confirmation happened before writing the constraint, not after. Do the same for any new fuzzy scheduling request.
- **The 名前 (name) field used on the calendar and the スタッフマスター must be reconciled explicitly, not assumed.** This project hit a real bug from assuming full-name matching would just work when the calendar convention was actually surname-only. Ask/verify the exact matching convention, and warn (don't silently merge) on collisions.
- **Never claim a script fix applies to sheets that already exist.** Formatting/roster/color fixes only affect *newly generated* sheets. Every delivery that changes generation logic must tell the user which existing sheets are now stale and need to be deleted and regenerated to pick up the fix.
- **Never hardcode a "known-good" reference cell for formatting/color copying.** A bug here (day 1 in November falling on Sunday/column A, which had never held a real date before) came from assuming a fixed reference cell was safe. Always source formatting/background-color references from a row guaranteed to always hold real data (week 2, days 8–14 in this sheet), and treat date-rows and entry-rows as separate colored groups — don't let one group's fix bleed into and overwrite the other (this happened once: a date-row color fix accidentally overwrote the green entry-row background).
- **Don't ask for the same input twice across menu items.** Public-holiday quota was originally asked in both step ① and step ②; the fix was to auto-detect it from what step ① already wrote and just confirm it in step ②. Apply the same "detect and confirm, don't re-ask" principle to any new redundant prompt.

## Standard procedure

1. **Structural analysis first.** Before writing or changing generation/formatting logic, confirm the sheet's actual cell layout — don't assume it matches a prior store's sheet. A plain text read via the Drive connector is enough for content, but exact cell positions, merges, and RGB colors need the xlsx-download-and-unzip technique in `references/gas-delivery-workflow.md`. See `references/spreadsheet-structure.md` for this project's known layout (calendar grid, roster location convention, staff-master columns, summary columns).
2. **Clarify scope before coding**, especially for a first build: which of the two menu operations (or both) is wanted, and what exactly "automate the input" should do. Use targeted questions rather than assuming.
3. **Write/edit the .gs script locally** (read the current file fully before editing a function — this codebase grew large enough that grep-then-read-then-edit was the reliable pattern, not blind edits).
4. **Deliver the complete file** to the user with: how to paste it in (Extensions > Apps Script, replace `Code.gs`, save, reload sheet), any first-run permission approvals newly required (e.g. Calendar access for the holiday-coloring feature), and which existing sheets must be deleted and regenerated to see the fix.
5. **Push volatile detail into named constants** at the top of the script (e.g. `STORE_LABEL`, `DIRECTOR_EARLY_WEEK_DAYS`, `DIRECTOR_EARLY_WEEK_MAX`) so future tuning requests are a one-line change, not a re-derivation.
6. **For replicating to a new store/branch**, follow the copy-file + change-`STORE_LABEL` + swap-staff-master procedure in `references/gas-delivery-workflow.md` — the spreadsheet was deliberately restructured mid-project to one-file-per-store specifically to make this easy.

## References

- `references/spreadsheet-structure.md` — exact calendar grid layout, color conventions, staff-master columns, roster-detection convention, summary columns.
- `references/business-rules.md` — the scheduling constraints, why each was added/changed, and the current rule set.
- `references/gas-delivery-workflow.md` — how script changes get delivered and adopted, the xlsx structural-analysis technique, and the new-branch replication steps.
- `references/background.md` — narrative history of this project: why it exists, the back-and-forth with the user, and the reasoning behind key decisions.

## 並行セッション対策

他のセッションがこのSkillを同時に使っている可能性がある間は、`SKILL.md`や`references/*.md`を
直接編集しない。学習は`learnings/`配下に新規ファイルとして置き、gitコマンド(`add`/`commit`/
ブランチ切り替え)は実行しない。タスク開始前に`learnings/`を読むこと。詳細・統合手順は
[`../hpb-salonboard-update/references/concurrent-sessions.md`](../hpb-salonboard-update/references/concurrent-sessions.md)を参照。

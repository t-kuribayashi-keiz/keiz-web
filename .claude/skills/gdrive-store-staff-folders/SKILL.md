---
name: gdrive-store-staff-folders
description: Use this skill whenever the user wants to build, resume, or run the Google Drive store/staff folder management system — a GAS (Google Apps Script) project that keeps one folder per salon store, one subfolder per staff member inside it, and syncs that structure monthly against a roster spreadsheet (handling 異動/transfers by moving folders, and 退職/departures by relocating to a 退職者リスト folder, never deleting). Trigger on mentions of "店舗フォルダ", "スタッフフォルダ", "異動対応", "退職者リスト", "フォルダ整理 GAS", "Googleドライブ 店舗 スタッフ", or requests to continue this specific automation project. STATUS: as of the last working session (2026-09-01), this project is UNFINISHED — it stalled at requirements/setup, no GAS code has been written yet, and it is blocked on the user confirming the correct Drive parent folder. Don't assume a working script exists; check with the user and re-derive from `references/background.md` before writing code.
---

# Google Drive Store/Staff Folder Management (GAS)

A Google Apps Script project the user wants, to keep a Google Drive folder tree in sync with a staff roster spreadsheet: one folder per store (salon), one subfolder per staff member inside each store folder. Intended to run monthly, around day 5, to catch that month's 異動 (staff transfers). This is **not yet built** — the source session ended mid-requirements-gathering, blocked on getting an unambiguous parent folder link from the user. Treat this file as the spec + gotchas to resume from, not a proven runbook.

## Non-negotiable rules (from the user, explicit)

1. **Never delete a staff folder.** Each staff folder contains real files (documents, etc.) the user never wants lost, even by accident. Every operation that removes a staff/store folder from its current location must be a **move**, never a delete/trash.
2. **Departed staff → move to a "退職者リスト" (departed-staff list) folder, don't delete.** If a staff folder already exists in Drive under some store but that person's name is no longer in the roster spreadsheet (retired, or any other reason), move that whole folder (with its contents intact) into a 退職者リスト folder — do not remove it from Drive.
3. **Diff before any change, and require explicit user approval before applying it.** The system's job each month is: read the roster spreadsheet, compare it against the current Drive folder structure, produce a list of differences (new stores, new staff, transferred staff, apparently-departed staff), and show that list to the user. Only after the user says OK should any folder actually be created or moved. Never auto-apply a diff.
4. **Verify a Drive resource before trusting it, every time.** In the source session the user pasted a Drive link that turned out to belong to a completely unrelated app's folder ("PlaudNote"), and separately, multiple folders shared the same or a near-identical store name in different locations (e.g. `本八幡南口接骨院` appeared under three different parents, plus a plain `本八幡南口` and a numbered `058. 本八幡南口`). Always confirm a folder/file's identity with metadata/search (name, mimeType, parent, contents) before writing it into code or acting on it — don't take a pasted link at face value.
5. **Check the roster spreadsheet's real file format before assuming GAS can read it.** The user's roster is a large `.xlsx` file sitting in Google Drive in Office-compatibility mode, not a native Google Sheet. GAS's `SpreadsheetApp` service can only open native Google Sheets directly — it cannot open an xlsx binary, regardless of whether the sheet also contains embedded images. Confirm the live mimeType (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` was the state at last check) before assuming `SpreadsheetApp.openById()` will work; if it still won't, see `references/background.md` for the fallback options already discussed with the user (and already partly rejected once).

## Roster spreadsheet structure (as described by the user, not yet independently verified against real data)

- Column A: store (salon) name.
- The row immediately below a store-name cell, spanning column B rightward, holds that store's staff names (one per cell).
- No other structure/columns (e.g. employee ID, qualification) were confirmed in the source session — if the user says there's more (they mentioned social security/qualification info might exist in later discussion), re-derive from the live sheet rather than assuming this skill's description is complete.

See `references/technical-notes.md` for exact file/folder identifiers observed, sizes, and the specific duplicate-folder collisions found.

## Standard procedure (once unblocked)

1. **Pin down the parent Drive folder that holds all store folders.** Ask the user to open it in Drive and paste the address-bar URL directly (not a folder name or a guess) — then verify via file/folder search or metadata lookup that it actually contains store-named subfolders before proceeding. Do not reuse a folder ID from a much earlier message without re-confirming; the one given early in the source session pointed to the wrong app entirely.
2. **Confirm the roster spreadsheet is machine-readable.** Check its current mimeType. If it's still xlsx-in-Office-compat-mode, work out with the user (don't just impose) whether GAS's `Drive API` (advanced service) or a conversion step can read cell values without requiring a native Sheet — or whether the lightweight-mirror-sheet idea (previously proposed once, and the user pushed back wanting to keep reading their live master ledger directly) needs to be revisited. Don't re-propose the mirror-sheet idea as if it's new; acknowledge it was already discussed and rejected once, and only bring it back if reading the xlsx directly turns out to be technically impossible.
3. **Parse the roster** into a {store: [staff names]} structure per the layout above.
4. **Walk the Drive folder tree** under the confirmed parent folder to build the current {store: [staff folder names]} structure.
5. **Diff the two.** Categorize: new store (no folder yet), new staff (folder needed inside an existing store), transferred staff (staff folder exists under a different store than the roster now says), and apparently-departed staff (folder exists, name no longer in roster anywhere).
6. **Present the diff to the user in full and wait for explicit approval** before changing anything in Drive.
7. **On approval, apply changes as moves/creates only:**
   - Create new store folders / new staff folders as needed.
   - Move a transferred staff's folder (contents intact) from their old store folder to their new one.
   - Move a departed staff's folder (contents intact) into the 退職者リスト folder.
   - Never delete or trash anything.
8. **Schedule:** the user wants this run monthly, around the 5th of the month, to catch that month's transfers — set up a GAS time-driven trigger for that once the script itself is working, rather than relying on the user to run it manually every time.

## What's still open / not yet decided

- The exact parent folder ID for store folders (blocked — see rule 4).
- Whether GAS can read the roster xlsx directly, or a workaround is needed (see step 2 above).
- Whether the "退職者リスト" folder already exists somewhere, or needs to be created, and where it should live relative to the store folders.
- No notification mechanism (email? chat? in-sheet?) for presenting the monthly diff to the user was decided in the source session — don't assume one.

Full narrative of how these constraints were discovered, including the exact back-and-forth with the user, is in `references/background.md`.

## 並行セッション対策

他のセッションがこのSkillを同時に使っている可能性がある間は、`SKILL.md`や`references/*.md`を
直接編集しない。学習は`learnings/`配下に新規ファイルとして置き、gitコマンド(`add`/`commit`/
ブランチ切り替え)は実行しない。タスク開始前に`learnings/`を読むこと。詳細・統合手順は
[`../hpb-salonboard-update/references/concurrent-sessions.md`](../hpb-salonboard-update/references/concurrent-sessions.md)を参照。

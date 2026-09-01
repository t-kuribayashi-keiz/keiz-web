# Technical notes (volatile — re-verify before relying on any of this)

These are the concrete identifiers and observations from the one working session on this project (2026-09-01, session titled "Google Drive店舗・スタッフフォルダ管理システム"). Nothing below has been re-checked since; Drive contents and IDs can change, so confirm before use rather than assuming.

## Roster spreadsheet

- URL given by the user: `https://docs.google.com/spreadsheets/d/1v9TPAfbEh1tg0hEz9ha6-x637ww22hom/edit?gid=958351945#gid=958351945`
- File ID: `1v9TPAfbEh1tg0hEz9ha6-x637ww22hom`
- Actual mimeType at last check: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` — i.e. a real .xlsx binary being displayed/edited in Google Drive's Office-compatibility mode, **not** a native Google Sheet. This matters because GAS's `SpreadsheetApp` service only opens native Google Sheets.
- File size at last check: exactly 104,857,600 bytes (100 MiB) — this is at (or essentially at) the size ceiling Google allows for Office-compatibility editing of an xlsx in Drive. The UI was already showing "ドライブに変更を保存できませんでした" / read-only-mode banners, i.e. the file was failing to save changes even for its normal (human) editors before any automation touches it. The size comes from many embedded photos (used for a human-readable staff ledger), not from the amount of text data the automation actually needs.
- The user was explicitly asked (via AskUserQuestion) whether they'd accept switching automation to a separate lightweight native-Sheet mirror (store name / staff name / employee number / qualification only, no photos). **They said no** — they want the automation to keep reading this same file directly, since it's the one that gets updated every month, and pointed out the automation only needs cell values, not the images. This preference should be respected; only revisit the mirror-sheet idea if directly reading the xlsx turns out to be technically unworkable, and say so explicitly rather than quietly reverting to the earlier suggestion.

## Store folder parent — NOT YET CONFIRMED

- The user initially pasted this Drive folder link as "where the store folders live": `https://drive.google.com/drive/u/0/folders/19N6-B5NTPkeW7uJhUMy8u7uEiB_kZ4r3` — checked and this folder ID actually belongs to an unrelated app called "PlaudNote" and was empty of any store folders. This was very likely a copy/paste mistake by the user (wrong tab/wrong link), not an intentional test. Always verify a freshly-pasted folder link's contents before building against it.
- A search for a known store name, "本八幡南口", surfaced multiple, differently-parented matches, meaning store folders are not obviously consolidated under one clean, unique tree:
  - `本八幡南口接骨院` — appeared under **three different parent folders**
  - `本八幡南口` — a separate, plainer name
  - `058. 本八幡南口` — a separate folder with a numeric prefix (possibly an internal store-numbering convention used elsewhere in the Drive)
- The session ended with the assistant asking the user to open the actual parent folder that contains the store folders (the ones that have staff subfolders inside them) and paste that URL. **No reply had come in by the end of the transcript** — this is the concrete blocker to resuming implementation.
- Practical resumption step: when picking this back up, don't restart the search from scratch — ask the user directly for that URL first (per SKILL.md step 1), and if they instead give a name/keyword, expect multiple candidates and disambiguate using folder contents (does it contain staff-named subfolders matching the roster?) rather than name alone.

## Tooling used in the source session

- A Google Drive MCP connector was used for read-only investigation: `get_file_metadata`, `search_files` (tool IDs prefixed `mcp__7c9ca37d-...` in that session — the exact prefix is an internal connector instance ID and may differ in a future session; search by tool name, not by that prefix).
- No write/create/move operations were attempted yet in the source session — everything so far was read-only reconnaissance (metadata + search). No GAS project (script file, container-bound or standalone) has been created yet.

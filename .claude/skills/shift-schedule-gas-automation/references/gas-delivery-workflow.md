# Delivery workflow, structural analysis technique, and branch replication

## No direct Apps Script deployment

This environment has no API access to push code into a Google Apps Script project attached to a Sheet. Every code change follows this loop:

1. Read/edit the local copy of the `.gs` file (grep for the relevant function, read enough surrounding context, make a targeted edit — this file grew large over the session, so blind full-file rewrites were avoided in favor of function-level edits).
2. Deliver the **complete, current file** to the user as an attachment (the source session used a "SendUserFile"-style tool; use whatever equivalent file-delivery mechanism the current session offers).
3. Instruct the user explicitly:
   - Open the target spreadsheet → Extensions/拡張機能 → Apps Script.
   - Replace the contents of `Code.gs` with the delivered file's contents.
   - Save.
   - Reload the spreadsheet (the custom menu only (re)appears after reload / re-open).
   - On the very first run ever, a permissions dialog will appear (edit access to the sheet; Calendar *read* access too, once the holiday-coloring feature exists) — approve it.
4. If the change affects sheet **generation** logic (formatting, colors, roster pull, sheet naming), explicitly tell the user which **already-created** sheets are now stale and must be **deleted and regenerated** — fixes never retroactively repair sheets made under the old code. This was a recurring point of confusion in the session (e.g. after the background-color fix, the 10月 sheets had to be deleted and remade to actually look right).

## Structural analysis technique (when exact cell layout matters)

The Drive connector's plain content read is enough to understand a sheet's general content, but it is **not** enough to know exact cell coordinates, merged ranges, or RGB font/fill colors — all of which matter for calendar-formatting logic. When that precision is needed:

1. Use the Google Drive MCP tools (`mcp__<drive-connector-id>__download_file_content`, `get_file_metadata`) to download the target Google Sheet as `.xlsx`.
2. Unzip the `.xlsx` (it's a zip archive) with PowerShell or Bash.
3. Inspect the extracted `xl/worksheets/sheetN.xml` and `xl/styles.xml` directly to read exact cell references, merged cell ranges, and style/fill/font color indices. This is how the calendar grid's row numbers (4/8/12/16/20), column-pair mapping, and the red/green/black color conventions in `spreadsheet-structure.md` were actually determined — reading the rendered sheet visually was not reliable enough for pixel-exact logic.
4. Map sheet names (as seen in the Sheets UI) to the internal `sheetN.xml` files via the workbook's `xl/workbook.xml` (sheet name ↔ `r:id` ↔ file) before trusting which XML file corresponds to which visible tab.

Re-run this analysis whenever a *new* sheet variant shows up (a new store, a reformatted template) rather than assuming it matches a previously-analyzed sheet — this project hit real bugs (roster cell position varying between 原本/駅前/北口) from that kind of assumption.

## Replicating the tool to a new store/branch

The spreadsheet was deliberately restructured mid-project from "one file, loop over both stores" to **one file per store**, specifically to make this replication path simple:

1. Copy the entire spreadsheet file (Drive "make a copy") for the new store.
2. Open the copy's Apps Script and change the `STORE_LABEL` constant to the new store's name (this drives the generated sheet title, e.g. "下総中山北口　9月休暇").
3. Replace the copy's スタッフマスター tab contents with the new store's own staff list (see `spreadsheet-structure.md` for the required columns).
4. Run "①月次シートを作成" from a state where only 原本 and スタッフマスター exist, to verify the new copy works standalone before relying on it.

There is no longer a 所属店舗 (branch) column or branch-mismatch check inside a single file — that logic was removed once the one-file-per-store split happened. Don't re-introduce it unless the project goes back to a shared multi-store file.

# Reading and editing the bound Apps Script project

The reconciliation logic is **not** in any spreadsheet cell — it's in a separate Apps Script project bound to the spreadsheet (Extensions → Apps Script). This file documents how the extraction session actually got the full source out of the Monaco-based Apps Script editor and edited it safely, plus the failure modes hit along the way.

## Access path

1. The in-app/sandboxed browser tools were **not logged into Google** — that path failed immediately (search_files on the Drive connector also came back empty/unhelpful for locating the actual .gs source, since Apps Script source isn't exposed through the Drive file-content API in a simple way).
2. Switched to the `claude-in-chrome` MCP tools, which drive the user's real, already-logged-in Chrome. This is the only path that worked. Load the core `claude-in-chrome` tool set plus `javascript_tool` up front (see the claude-in-chrome MCP server instructions for the batched ToolSearch call).
3. From the spreadsheet, open Extensions → Apps Script (via the Chrome extensions/menu UI, then a new tab for the Apps Script editor opens).

## Extracting the full source (read side)

The Apps Script editor is a Monaco editor instance; naive `get_page_text` only returns whatever is currently scrolled into view / rendered, not the full file, and a plain JS `eval` returning a big string gets filtered/truncated by the tool's own output handling.

What worked: use `javascript_tool` to reach into Monaco's in-memory models (each open file is a Monaco text model) and pull `model.getValue()` for every file, then **inject the concatenated text into the page's DOM** (e.g. as a big block of paragraph elements) so that `get_page_text` — which reads real rendered DOM text — can retrieve it in one shot. In this session that meant creating ~805 paragraph elements (5 files worth of source) and reading them back via `get_page_text`.

**Pitfall**: this DOM-injection trick, if not cleaned up before you try to interact with the editor UI again (e.g. via `computer` clicks), can visually clobber/cover the real editor — hit this exact issue mid-session and had to `navigate` (reload) the page to recover a clean editor view before proceeding with edits. Always navigate/reload to reset the DOM back to a clean editor state before switching from "extract text" mode to "click and edit" mode.

## Identifying the active file

Don't assume the file that looks newest or best-named is the live one. Cross-check: does the code reference sheet names and column headers that actually exist in the live spreadsheet right now? In this session, `集計自動化.gs`'s references to `CRM`, `HPB`, `店舗名マッチ用`, `店舗表示順`, and its output header row matched the real tabs; the other four files referenced sheet names (`CRMと比較`, `table`, `temp_data`) and keys (カルテNo, サロンボードID) that don't exist anymore — that's how "only this one file is live" was confirmed, not by file name or modification date.

## Editing (write side)

- Locate the **exact insertion point** by content (a nearby unique code fragment / line content), not by assumed line number — line numbers shift as the file is edited over multiple sessions.
- Edit via **direct manipulation of the Monaco model** (something equivalent to `model.applyEdits(...)` at a specific offset/range) rather than a broad string find-and-replace. A 490-line function can easily contain a duplicate substring, and a naive replace risks editing the wrong occurrence silently.
- After editing the model, you must actually **open/render the file's tab in the visible editor** and visually confirm the inserted code appears correctly — editing the in-memory model alone doesn't guarantee the visible editor or the save pipeline picks it up correctly, especially if the earlier DOM-injection trick left stray elements around (see Pitfall above; reload first if in doubt).
- Save via the editor's normal save action (Ctrl+S equivalent, or the visible save affordance) and **confirm the saved state**: the session confirmed success by seeing the status change to "ドライブに保存しました" ("saved to Drive") and the file-list's unsaved-change dot disappear. Don't consider an edit done until you see this positive confirmation.

## After saving

Remember (see SKILL.md rule 7): saving the script does not touch any previously generated output sheet. To demonstrate the fix, `reconcileData()` needs to be re-run — either via a button on a `実行` sheet in the spreadsheet, or by running the function directly from the Apps Script editor's run controls. Confirm with the user before running it if the run has any side effects they'd want to review first (it creates a new sheet, so it's low-risk, but the user may want to be the one to trigger it or watch it happen).

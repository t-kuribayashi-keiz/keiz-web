# Colab browser-automation gotchas (予約枠チェック)

Learned 2026-09-03 debugging the notebook via `mcp__claude-in-chrome__*` browser tools.
General Colab/CodeMirror behavior, not specific to this notebook's content — reuse for any
Colab-editing task.

## Editing existing code safely

- **A single-line edit is safe; a multi-line edit typed with embedded `\n` is not.** The
  `type` browser action simulates real keystrokes, and CodeMirror's smart-indent fires on
  every Enter it sees — typing multi-line replacement text corrupts indentation on the
  following line(s), cascading worse with each subsequent line. Stick to one-line-at-a-time
  edits for anything inside an existing function body.
- **To replace one line without disturbing indentation**: click on the line, `key: End`,
  then `key: shift+Home` **twice** (the first Home press goes to the first non-whitespace
  character; the second goes to column 0 — this is standard "smart home" editor behavior).
  This selects the whole line including its leading whitespace. Then `type` the full
  replacement line (correct indentation included, no trailing newline) — since no Enter key
  is involved, auto-indent never fires.
- **Prefer Colab's own 検索と置換 (search & replace) panel over manual click+retype when
  editing a notebook you don't want to risk** (e.g. the production original, not a
  disposable debug copy). It does an exact-text substitution that can't corrupt surrounding
  indentation, and shows a match count before you commit — open it via the left sidebar's
  magnifying-glass icon, type the exact old text in 検索, the new text in 置換, confirm
  "1件の結果" (or however many you expect) before clicking すべて置換, and click OK on the
  confirmation dialog it raises. This was the reliable method for porting a verified fix
  from a debug copy back into the original notebook.
- **After any edit, re-run the cell and check for a real error, not just "it looks right
  visually."** A single wrong space is easy to miss in a screenshot; `IndentationError:
  unexpected indent` (or `expected an indented block`) in the cell's own error output is the
  actual signal. If the error message names a line number that doesn't match what you just
  edited, look at the line *above or below* your edit — a stray extra-indent on a sibling
  line is a common side-effect of an earlier fix attempt.

## Running fresh code without triggering the full pipeline

- **Reuse an existing throwaway cell rather than creating a new one.** Clicking an empty
  Colab code cell auto-opens a Gemini AI-assist side panel that silently steals subsequent
  keyboard input (typed text ends up in the Gemini chat box, not the cell) — confirmed by
  watching typed content land in the wrong place twice before figuring this out. Instead:
  click into a cell that already has *some* content, `key: ctrl+a` to select all, then type
  the replacement.
- **Two-cell debug pattern**: one cell containing
  `exec(__import__('base64').b64decode('<base64>').decode())` (which *defines* a throwaway
  async function — encode any multi-line Python this way to sidestep the auto-indent issue
  entirely, since exec's decoded string is inserted as one already-formed unit, not typed
  keystroke-by-keystroke), and a second, separate cell containing a short one-line
  `await debug_fn(n)` call. Overwrite and re-run both cells (in that order) each time the
  debug function needs to change — this reuses the same two cells across iterations instead
  of accumulating new ones.
- **A debug cell that mirrors `main_process`'s per-shop loop but limits `shop_rows` to a
  small slice and skips `worksheet.update(...)` entirely** is the way to validate a fix
  against real shops without writing to the shared sheet. It should still call the *actual*
  `scrape_hpb_robust`/`judge_occupancy_rate` functions already defined by the main cell
  (not a reimplementation), so the test is honestly exercising the real code path.

## Cell-output UI quirks

- **A long/collapsed cell output has its own internal scrollbar** — scrolling with the mouse
  positioned over an output box scrolls *inside* that box, not the notebook page, even when
  it looks like you're scrolling past it. If the page won't scroll, click on the left gutter
  margin (outside any output area) before scrolling, or collapse the output first (the small
  `∨`/`∧` chevron next to the cell's execution-count label toggles this).
- **Collapse noisy/huge cell outputs (like a `pip install` log) early** — click "非表示の出力
  を表示" / the chevron to hide them. This makes subsequent scrolling and screenshot-reading
  far more reliable for the rest of the session, since a giant install log otherwise eats
  most of the viewport.

## Fresh-runtime gotchas (a notebook that hasn't been touched yet this session)

A Colab notebook opened for the first time in a while may connect to a **brand-new runtime**
with nothing installed and no auth granted, even if the tab shows "接続済み" — that status
just means *a* kernel is attached, not that your packages/credentials from a previous run
persisted. Symptoms that mean this is what's happening:
- `NameError: name 'X' is not defined` for a variable the main cell clearly defines near the
  top — almost always means the cell's execution never actually got that far, because an
  earlier line (commonly an `import`) raised first. Scroll to the cell's own error output
  (not just re-reading the source) to see the real traceback.
- `ModuleNotFoundError: No module named 'jpholiday'` (or `playwright`) confirms it: run the
  `!pip install ...` / `!playwright install chromium` / `!playwright install-deps` cell(s)
  first — this takes roughly a minute — then re-run the main definitions cell.
- The first `auth.authenticate_user()` call in a new runtime raises a "Google 認証情報への
  アクセスをこのノートブックに許可しますか?" dialog requiring a click on 許可 — this is
  expected and safe for the notebook owner's own Drive/Sheets access, not a sign of anything
  wrong. Click it and wait; the cell that was running resumes and can legitimately take 1-2
  minutes total.
- If the Chrome extension's browser-automation connection itself drops mid-session
  (`browser_batch` times out or reports the extension disconnected) and reconnects with
  multiple browsers now listed, re-select the *same* browser that has your existing tabs —
  check via `tabs_context_mcp` after selecting, and re-pick if your known tabs aren't there.
  This is a connection-layer hiccup, unrelated to and doesn't by itself imply anything about
  the Colab runtime's own state (though the two can coincide, as they did here).

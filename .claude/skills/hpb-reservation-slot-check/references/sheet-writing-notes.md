# Writing to the Google Sheet via `claude-in-chrome` (M/N columns, K/L restores)

Confirmed 2026-09-11 while writing M/N confirmation results (26 salons) into
`AIチェック用ver.2` and restoring K/L after the false-positive incident
(`github-actions-ops.md`). This is about the *browser-automation* path (a live human/agent
session editing the sheet through Chrome), not the `gspread`-based scripts.

## ✕ and ○ silently vanish when typed via the `computer` tool's `type` action

Typing a string containing ✕ (U+2715) or ○ through `computer`'s `type` drops that
character — the rest of the string comes through fine, just not the symbol. This
reproduced 100% of the time it was tried, including a synthetic `ClipboardEvent('paste',
{clipboardData: ...})` dispatched via `javascript_tool` (same drop). **The only thing that
preserves these characters is a real OS-clipboard copy/paste**:

```js
await navigator.clipboard.writeText("✕/予定あり(枠ブロック)\t備考テキスト");
await navigator.clipboard.readText(); // read it straight back and check it matches
```

then `ctrl+v` into the target cell. Also verify the *cell's* actual content after pasting
— see the next point for why that verification isn't optional.

## The OS clipboard is not exclusively yours

If the user is doing anything else on that PC at the same time, whatever they copy can
land in the clipboard between your `writeText` and your `ctrl+v` — this happened multiple
times in one session (a stray URL, a security-tool-looking string, an unrelated email
domain all showed up in cells meant to hold M/N text). **Verify the clipboard content right
before pasting, and verify the target cell's content right after** — every single time, not
just the first time. Retry (re-`writeText`, re-paste, re-verify) rather than trusting one
attempt.

Typing a long Japanese string can also drop its leading characters if you `type`
immediately after navigating to the cell (`Return` then straight into `type`). Use `F2`
(explicit edit mode) → `wait 1s` → `type` instead — this reliably avoided the drop.

## The grid is canvas-rendered — you cannot read cell content via `document.querySelectorAll`

Only the surrounding UI chrome (name box, formula bar, toolbar) is real DOM
(`document.querySelector('input.waffle-name-box')` works for the name box). There is no JS
shortcut to bulk-read cell values this way.

**`Ctrl+F` (in-sheet find) was unreliable** in this session — consistently `0/0` matches or
a stale result that never updated to the new search term, for reasons never identified.
Don't build a row-lookup procedure around it.

**The only method that never failed for confirming "which row is this store on"**: type
`A<row>` into the name box, `Return`, then read the formula bar (zoom or
`read_page`/screenshot) — one row at a time. Slower than skimming a screenshot and counting
rows by eye, but the eyeball method produced multiple real misreads in the same session
(off-by-one row numbers, and once confusing two different stores with similar names —
二条駅前 vs 二和向台駅前). If you need many rows' worth of name→row mapping and the tab is
small enough, it may be faster to fetch the whole tab's content once through a Drive/Docs
connector (if one is available in the session) instead of navigating row-by-row — worth
trying before committing to 20+ one-at-a-time lookups.

## Don't hand-transcribe bulk tabular data into a paste payload

Converting more than a couple dozen rows of tabular data (e.g. a run log parsed into
K/L values) into a paste-ready block **by reading tool output and retyping/restructuring it
yourself** is unsafe at this scale — a 142-row conversion silently dropped 8 rows once, which
would have shifted every subsequent row onto the wrong store's data if pasted without
checking. Always do the mechanical conversion in a script (Python/etc.), and verify the row
count matches expectation before using the result.

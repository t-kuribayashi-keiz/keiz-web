# Google Sheets browser-automation technique

Everything here was worked out live in the source session via the `claude-in-chrome` MCP tools against a real Google Sheets tab. It generalizes to any task that needs to write Japanese text/formulas into Google Sheets cells or build/style a chart via the UI.

## Clipboard-paste, not direct typing

Typing Japanese text directly into a Google Sheets cell (via a keystroke-simulating `type` action) was **unstable** — it did not reliably land correctly. The fix that worked:

1. Build the full block of text you want to enter (tab-separated for multiple columns, newline-separated for multiple rows) as a single string — this can mix Japanese labels and ASCII formulas in the same paste.
2. Use `javascript_tool` to write that string to the system/browser clipboard (`navigator.clipboard.writeText(...)` or equivalent).
3. Click the target top-left cell in the sheet to select it.
4. Paste (Ctrl+V via the `computer` tool's `key` action) rather than typing.

This lets you populate a whole rectangular block (labels + formulas) in one paste instead of cell-by-cell typing, which is both more reliable and much faster. Always paste into the top-left cell of the intended range and verify the pasted values with a follow-up read (screenshot or `read_page`) before moving on — confirm computed totals match expectations (see the verification checklist in `data-and-aggregation.md`) rather than assuming the paste landed correctly.

## Creating a chart

1. Select the data range for the chart (the header + value rows/columns you want charted).
2. Open the **Insert** menu → click **グラフ** (Chart). Google Sheets will auto-insert a chart and usually auto-guesses a reasonable chart type from the shape of the selected data (e.g. a 2-column category/value table becomes a pie chart by default; a table with an age-bracket-like row axis becomes a column chart; a table with two value columns per category becomes a grouped/clustered column chart). The auto-guess was correct in every case in the source session — no need to manually force the chart type unless it looks wrong.
3. The chart editor panel opens on the right with "設定" (Setup) and "カスタマイズ" (Customize) tabs.

## Setting the chart title

The default auto-generated title is not acceptable — always set an explicit, short title (source session used 男女比, 年代構成, 男女別年代構成).

1. Switch to the **カスタマイズ** (Customize) tab in the chart editor.
2. Find the **グラフと軸のタイトル** (Chart & axis titles) section — it is often collapsed and must be clicked to expand before the title text field becomes visible/interactive. Don't assume the field is immediately usable; expand the section first.
3. Use `find` to locate the title input field, then `form_input` to set its value directly (more reliable than clicking + typing for this field).
4. Click outside the chart editor / press elsewhere to commit, then close the chart editor.

## Repositioning charts

Once multiple charts exist on the same tab, drag them so they stack vertically without overlapping (e.g. below the data tables, then each chart below the previous one). Notes from the source session:

- Click precisely on the chart you intend to move before dragging — it's easy to accidentally grab a different, already-placed chart if they're close together (this happened once: a click intended to deselect landed on the 年代構成 chart instead of empty canvas space).
- After repositioning all charts, scroll back to the top and take one final look (screenshot or read_page) at the full tab layout — tables + all charts — to confirm nothing overlaps and everything is in a sensible reading order before reporting done.

## General verification habit

Throughout, prefer reading back actual cell values / chart state (via page text extraction, zoom/screenshot, or JS evaluation) over assuming an action succeeded — this workflow involves several steps (clipboard write, paste, formula calculation, chart auto-type-guessing, title field expansion) that can silently fail or behave unexpectedly, and the source session caught and corrected several of them this way (e.g. re-clicking to expand the title section when the field wasn't there yet).

# Building and delivering the workbook

## Why not the standard `xlsx` skill's Python path

The general-purpose `anthropic-skills:xlsx` skill defaults to `openpyxl`/`pandas` scripts run
via `python`. On this machine, **`python` resolves to a non-functional Windows Store stub** —
this is confirmed independently elsewhere (see the `session-to-skill` skill's packaging notes),
and it's exactly what forced a pivot mid-session here too: the assistant started down the
openpyxl path (loaded the xlsx skill, wrote a script, tried to run it) and then explicitly
abandoned it for PowerShell + Excel COM automation once it became clear Python wasn't going to
work.

**Don't waste a round-trip re-discovering this.** Skip straight to PowerShell + Excel COM for
building the workbook on this machine, unless a future session confirms Python has started
working here.

## Building via PowerShell + Excel COM

The exact script from the source session isn't recoverable in full (only the sequence of tool
calls is preserved, not their full arguments), but the outline was:

1. Write a `.ps1` script that creates an Excel COM object (`New-Object -ComObject Excel.Application`),
   builds the workbook (sheets, headers, row/column labels, ○/×/△ cell values, colors for the
   red-corrected-name column, cell comments for non-mark notes), and saves it as `.xlsx`.
2. **Load `System.Drawing`** explicitly (`Add-Type -AssemblyName System.Drawing`) before using
   any RGB color values — the first run failed until this was added.
3. Run the script, verify the output file exists and opens cleanly.
4. If sheet order needs fixing (e.g. main table sheet must come before the notes sheet), do a
   second small PowerShell pass to reorder sheets and re-save — this can be done as a
   follow-up edit rather than redoing the whole build script.
5. **Always check for and kill stray `EXCEL.EXE` processes after the COM session.** Excel COM
   automation can leave a zombie Excel process running in the background if the script doesn't
   cleanly call `.Quit()` and release COM objects (or if a save/timeout hiccups mid-script) —
   confirmed to happen in the source run. Check with something like
   `Get-Process EXCEL -ErrorAction SilentlyContinue` and kill any leftovers before considering
   the file done; a lingering process can lock the file or silently hold stale state.

## Delivering as a Google Sheet (the default — see SKILL.md rule 2)

The user's "スプレッドシート" almost always means Google Sheets, not a handed-over `.xlsx`
file. Once the `.xlsx` is built and verified locally:

1. Use a Google Drive MCP connector's file-creation capability (in the source session this was
   an MCP tool named like `mcp__<connector-id>__create_file` — the numeric/UUID part of the
   tool name is connector-instance-specific and will differ across machines/sessions, so
   **search for it by keyword** — e.g. `ToolSearch` with a query like "google drive create
   file" or "drive upload" — rather than hardcoding a tool name from a prior session).
2. Upload the local `.xlsx` through that tool; Drive converts it to a native Google Sheet.
3. Confirm the conversion preserved the content correctly (read it back / check the returned
   link) before sending the link to the user. In the source run this conversion also collapsed
   the two-sheet workbook into one sheet with a blank-row separator (see
   `table-structure.md`) — mention that layout choice to the user rather than assuming it's
   unnoticed.
4. Share the resulting `docs.google.com/spreadsheets/...` link back to the user as the
   deliverable, not a local file path.

## If asked for Excel specifically

If the user does explicitly ask for an Excel file (rather than "スプレッドシート"), the local
`.xlsx` built in the PowerShell/COM step above is already the right deliverable — no Google
Sheets upload needed, just point them at the local path (e.g. under
`C:\Users\keizgroup634\Desktop\栗林\claude\`).

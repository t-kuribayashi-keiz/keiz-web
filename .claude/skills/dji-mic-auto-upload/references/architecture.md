# Architecture reference

Source files (original build): `C:\Users\keizgroup634\Desktop\栗林\claude\dji-mic-auto-upload\`
Recommended deployed location on a store PC: `C:\Tools\DjiMicAutoUpload` (arbitrary, just referenced consistently by the installer).

## config.json schema

```json
{
  "driveRoot": "G:\\共有ドライブ\\スタッフ音声",
  "logPath": "C:\\ProgramData\\DjiMicAutoUpload\\upload.log",
  "audioExtensions": [".wav", ".mp3"],
  "mics": [
    { "volumeLabel": "STAFF_TANAKA", "staffFolder": "田中" },
    { "volumeLabel": "STAFF_SUZUKI", "staffFolder": "鈴木" }
  ]
}
```

- `driveRoot` — local filesystem path to the Google Drive for desktop-mounted shared drive on *this* PC. Per-PC value; the one thing that must change on every new-PC deployment. Values shown are placeholders/examples from the original build, not real store paths.
- `logPath` — fixed convention, `C:\ProgramData\DjiMicAutoUpload\upload.log`. `ProgramData` is used (not a user profile folder) so the log is accessible regardless of which user is logged on when the task runs.
- `audioExtensions` — file extensions robocopy will copy; currently `.wav` and `.mp3`. Extend here if the Mic (or a future model) writes another format.
- `mics` — the volume-label → staff-folder mapping. `staffFolder` is a relative folder name created under `driveRoot` if it doesn't already exist. Adding a mic/staff member is a one-line addition here (see SKILL.md procedure B).

## Upload-DjiMic.ps1 — how it works

1. Loads `config.json` from the script's own folder by default (`$PSScriptRoot`), or a path passed via `-ConfigPath`.
2. Ensures the log directory exists.
3. **Lock file** (`upload.lock`, same folder as the log): if a lock file exists and is less than 10 minutes old, the script exits immediately without doing anything. This exists because the scheduled task fires every 1 minute — if a previous copy is still running (e.g. a very large file), this prevents overlapping/duplicate robocopy invocations. The lock is always removed in a `finally` block, including on error.
4. Checks that `config.driveRoot` exists on disk. If Google Drive for desktop isn't running / not signed in / the shared drive isn't mounted, this path won't exist — the script logs a Japanese warning and exits (exit code 1) rather than failing silently.
5. Enumerates removable volumes: `Get-Volume | Where-Object { $_.DriveType -eq 'Removable' -and $_.DriveLetter }`.
6. For each removable volume, looks up its `FileSystemLabel` against `config.mics[].volumeLabel`. Non-matches are skipped silently (so plugging in an unrelated USB drive does nothing).
7. For a match: builds the destination folder (`driveRoot\staffFolder`, created if missing) and runs:
   ```
   robocopy <sourceDrive>:\ <destRoot> .wav .mp3 /S /R:2 /W:2 /NFL /NDL /NP /XO
   ```
   - `/S` — include subfolders (the Mic's internal storage may nest recordings in subfolders).
   - `/R:2 /W:2` — retry twice, 2 seconds apart, on a locked/busy file, instead of robocopy's default (extremely long) retry behavior.
   - `/NFL /NDL /NP` — suppress per-file/per-directory listing and progress percentage, to keep the log-worthy output minimal (the script doesn't even capture robocopy's own stdout — it relies on the exit code).
   - `/XO` — **exclude older**: only copy a file if the source is newer than what's already at the destination, or if it doesn't exist at the destination yet. This is the *entire* de-duplication mechanism — no separate hash/filename tracking is used or needed. Re-running the script repeatedly (e.g. every minute while a mic stays plugged in) will not re-copy files it already copied.
8. Interprets robocopy's exit code: `0` = nothing new to copy (no log entry — this is the common case on most 1-minute ticks), `1` = files were copied (logs an "アップロード" line), `>=8` = an error occurred (logs an "エラー" line with the exit code). Codes 2–7 (extra/mismatched files, etc.) are not currently distinguished or logged.
9. All log lines are single tab-separated `timestamp\tmessage` rows appended to `logPath` in UTF-8.

## Install-ScheduledTask.ps1 — what it registers

- Task name: `DjiMicAutoUpload`.
- Action: `powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "<ScriptPath>" -ConfigPath "<ConfigPath>"` — runs hidden, bypasses execution policy for just this invocation (does not change the system-wide policy).
- Trigger: starts `AtLogOn`, then repeats every 1 minute for up to 3650 days (i.e., effectively indefinitely — Windows scheduled-task repetition triggers require a finite duration, so a ~10-year window is used as a practical "forever").
- Settings: `AllowStartIfOnBatteries`, `DontStopIfGoingOnBatteries` (store PCs are usually desktops, but this makes it laptop-safe too), `ExecutionTimeLimit` 5 minutes (kills a hung run), `MultipleInstances IgnoreNew` (belt-and-suspenders alongside the script's own lock file — a second trigger firing while one run is still active is simply skipped by Task Scheduler itself).
- Principal: runs as the currently logged-on user (`Interactive` logon type), **not** as SYSTEM or a service account — this is required so the task can see that user's mapped/signed-in Google Drive for desktop session and drive letters.
- The installer itself validates that `Upload-DjiMic.ps1` and `config.json` exist at the expected paths before registering anything, and throws a Japanese error if not.

## The encoding gotcha (already fixed once, watch for regressions)

Windows PowerShell 5.1 (the version bundled with Windows, as opposed to PowerShell 7+) auto-detects file encoding for `.ps1` scripts, and a UTF-8 file **without a byte-order mark (BOM)** gets misread as the legacy Shift-JIS codepage. Since these scripts embed Japanese strings (log messages, error text), a BOM-less save silently corrupts every non-ASCII character in the output — it doesn't throw an error, it just produces garbled text in the log file and any console output. Always save/re-save `.ps1` edits as "UTF-8 with BOM" (in most editors this is a distinct save option from plain "UTF-8"). After any edit, a quick sanity check is to run the script once and confirm a Japanese log/warning line renders correctly rather than as mojibake.

## What was never verified on real hardware

The original build session had neither a physical DJI Mic Mini 2S nor a working Google Drive for desktop sync folder available on the build PC. What *was* confirmed: the script runs, correctly detects the missing `driveRoot` and logs the expected Japanese warning, and cleans up its lock file properly on that failure path. What was *not* exercised end-to-end: an actual mic being detected by volume label and an actual robocopy successfully placing a file that then synced to Google Drive. Treat "step 4" (manual run with a real mic connected) in every new deployment as the first real test of the happy path, not a formality.

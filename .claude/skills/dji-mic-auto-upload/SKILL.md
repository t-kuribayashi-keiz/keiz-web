---
name: dji-mic-auto-upload
description: Use this skill whenever the user asks to deploy, extend, fix, or troubleshoot the DJI Mic Mini 2S auto-upload system — a PowerShell + Task Scheduler tool that detects a DJI Mic Mini 2S plugged in via USB-C and automatically robocopies its recordings into the right staff member's Google Drive shared-drive folder (Google Drive for desktop then syncs it to the cloud). Trigger on mentions of "DJI Mic", "Mic Mini 2s", "自動アップロード", "USBで自動コピー", "ボリュームラベル", "Upload-DjiMic", "config.json のマイク対応表", or requests to onboard a new mic/staff member, roll the system out to a new salon/store PC, or fix a case where recordings aren't showing up in Google Drive. Also trigger when the user talks about moving/migrating a DJI Mic between stores or PCs and asks whether anything needs re-configuring. This system was built once (2026-08-26) for one store and is designed to be replicated to further stores as the user's ~150-salon operation rolls it out — treat every new store as a normal, expected use of this skill, not a one-off.
---

# DJI Mic Mini 2S Auto-Upload

## Overview

This skill covers a small automation kit that lives in a folder (e.g. `C:\Tools\DjiMicAutoUpload`) on each store PC:

- `config.json` — the mapping of DJI Mic volume label → staff name → destination subfolder, plus the local path to the Google Drive shared-drive root and the log path.
- `Upload-DjiMic.ps1` — the worker script. Runs every minute via Task Scheduler, checks all currently-connected removable drives, matches any whose volume label appears in `config.json`, and `robocopy`s its audio files into that staff member's folder under the Google Drive sync root. Google Drive for desktop then uploads them to the cloud automatically — this script never talks to Google's API directly.
- `Install-ScheduledTask.ps1` — one-time installer that registers the "DjiMicAutoUpload" scheduled task (starts at logon, repeats every minute, runs as the logged-on user so it can see that user's mapped Google Drive).
- `README.md` — the setup/deployment instructions, written in Japanese for store-level handoff.

The live, working copy of these files (from the original build) is at `C:\Users\keizgroup634\Desktop\栗林\claude\dji-mic-auto-upload\` — start from there rather than re-writing from scratch. See `references/architecture.md` for exactly how each script works and why.

## Non-negotiable rules

- **Identify mics by USB volume label, never by USB serial number.** The two options were compared explicitly; serial-number matching was rejected because DJI's hardware/chipset was never confirmed to return a unique serial per unit (the physical mic was never actually connected during the design session to test this). Volume label is deliberately chosen as the reliable, already-verified mechanism. Do not switch to serial-number matching without first connecting a real unit and confirming uniqueness across multiple physical mics.
- **A mic's volume label never needs to be re-set when the mic moves to a different store or PC.** The label lives on the mic's own onboard storage, not on the PC. This was a specific point the user raised (mics get migrated between stores) and the answer is: relabel once per physical mic, for its lifetime — never as part of a store-transfer checklist. Only `config.json`'s `driveRoot` (a per-PC path) needs updating when moving to a new PC.
- **Never run `Install-ScheduledTask.ps1` yourself against a real/production PC.** Registering a scheduled task is a system-settings change. In the original session this script was written and syntax-checked but deliberately *not* executed, even on the build/test PC — the instruction was to hand it to the user/store PC to run themselves. Draft and verify the installer; do not execute it.
- **Save/edit the `.ps1` files as UTF-8 with BOM.** Windows PowerShell 5.1 misreads BOM-less UTF-8 as Shift-JIS, which silently corrupts the Japanese log messages (`Write-Log` output, error text). This was a real bug hit and fixed once already — check encoding after any edit to these scripts, not just syntax.
- **Don't add hash-based or filename-based dedup bookkeeping.** An early design draft proposed tracking copied-file hashes to avoid re-copying, but the shipped design relies solely on `robocopy /XO` (copy only if source is newer than an existing destination file), which already prevents duplicate/overwrite issues for this one-way copy. Keep it that simple unless a real duplication bug is observed.
- **Treat the copy step (`robocopy` triggered by a real mic + real Google Drive folder) as unverified until confirmed on an actual store PC.** In the build session, neither a physical DJI Mic Mini 2S nor a real Google Drive for desktop sync folder was available, so only the "Drive folder not found" warning path was exercised — never an actual successful file copy. Every new deployment's step 4 (manual run of `Upload-DjiMic.ps1` with a real mic plugged in, checked before installing the scheduled task) is a real verification step, not a formality — don't skip it or assume it will just work.

## Standard procedure

### A. Deploying to a new store PC (mic(s) already labeled and already in `config.json`)
1. Copy the whole tool folder to the new PC (any local path, e.g. `C:\Tools\DjiMicAutoUpload`).
2. Confirm Google Drive for desktop is installed on that PC and the relevant shared drive is mounted and accessible.
3. Edit only `driveRoot` in `config.json` to that PC's local path to the shared drive (drive letters/paths can differ machine to machine). Leave the `mics` array as-is — it travels with the mics, not the PC.
4. Manually run `.\Upload-DjiMic.ps1` with a real mic connected and confirm a file actually lands in `driveRoot\<staffFolder>`, and that it then shows as synced in the Google Drive for desktop app.
5. Only after step 4 succeeds, run `.\Install-ScheduledTask.ps1` **on that PC, by the user** — see the non-negotiable rule above.

### B. Onboarding a new mic or staff member (existing deployment)
1. Connect the new DJI Mic Mini 2S via USB-C, rename its drive to a unique label (recommend half-width alphanumeric, e.g. `STAFF_TANAKA`) via Explorer → right-click → rename. This is done once per physical mic, ever.
2. Add one entry to the `mics` array in `config.json`: `{ "volumeLabel": "<the label>", "staffFolder": "<destination subfolder name>" }`.
3. No script changes and no scheduled-task re-registration needed — the running task picks up the new `config.json` entry on its next 1-minute check.

### C. Troubleshooting "recordings aren't showing up in Drive"
1. Check `C:\ProgramData\DjiMicAutoUpload\upload.log` first — confirms whether the local copy step ran/succeeded/failed. See `references/architecture.md` for how to read robocopy's exit-code-based log lines.
2. If the log shows a successful local copy but the file isn't in the cloud, the issue is downstream in Google Drive for desktop's own sync (check its status icon/app), not this script.
3. If nothing appears in the log at all, check the scheduled task's state in Task Scheduler and confirm the mic's volume label exactly matches an entry in `config.json` (case must match `FileSystemLabel` as read by PowerShell).

### D. Extending or modifying the scripts
Read `Upload-DjiMic.ps1` fully before editing (it's short, ~70 lines) — don't patch blind. Re-verify UTF-8-with-BOM encoding after saving. See `references/architecture.md` for the lock-file mechanism (prevents overlapping runs when a copy takes >1 minute) and exactly what each robocopy flag does before changing the flag set.

## References

- `references/architecture.md` — exact script internals: config.json schema, robocopy arguments and exit-code handling, lock-file mechanism, scheduled task trigger/settings, the encoding gotcha in detail.
- `references/deployment-checklist.md` — printable-style step list for rolling this out to a new store, aimed at whoever is physically at the store PC (can be handed to non-technical staff).
- `references/background.md` — narrative of how this system's design was decided (serial number vs. volume label debate, the store-migration question that settled it, what was and wasn't verified on real hardware).

# Deployment checklist (hand this to whoever is at the store PC)

Identification method used: **volume label** (the DJI Mic's own drive name, set once and kept for the mic's lifetime — not the PC's).

## Prerequisites (per PC, one-time)

- [ ] Google Drive for desktop is installed and signed in on this PC.
- [ ] The relevant shared drive (containing the staff audio folders) is visible in File Explorer under a drive letter or mapped path.

## First-time setup on a new store PC

1. [ ] Copy the whole tool folder to the PC (any local path — e.g. `C:\Tools\DjiMicAutoUpload`).
2. [ ] Open `config.json` in a text editor. Update `driveRoot` to this PC's actual local path to the shared drive (this is the only field that's expected to differ PC to PC). Leave `mics` untouched unless this PC's mics aren't in the list yet.
3. [ ] Plug in a real DJI Mic Mini 2S that already has one of the labels listed in `config.json` (see "Onboarding a new mic" below if it doesn't).
4. [ ] Open PowerShell in the tool folder and run:
   ```powershell
   .\Upload-DjiMic.ps1
   ```
5. [ ] Confirm a recording file actually appeared under `driveRoot\<staffFolder>\`, and that Google Drive for desktop's status icon shows it as synced (not just copied locally).
6. [ ] Only once step 5 is confirmed working, run:
   ```powershell
   .\Install-ScheduledTask.ps1
   ```
   This registers a task that starts at logon and checks for a connected mic every minute. Confirm registration succeeded by checking Task Scheduler for a task named `DjiMicAutoUpload`, or by running:
   ```powershell
   Start-ScheduledTask -TaskName "DjiMicAutoUpload"
   ```

## Onboarding a new mic or staff member

1. [ ] Connect the new mic via USB-C.
2. [ ] In File Explorer, right-click the mic's drive → Rename. Give it a unique label (recommended: half-width alphanumeric, e.g. `STAFF_TANAKA`). Write down exactly what you typed — it must match `config.json` character-for-character.
3. [ ] Add one line to the `mics` array in `config.json`:
   ```json
   { "volumeLabel": "STAFF_TANAKA", "staffFolder": "田中" }
   ```
4. [ ] No further action needed — any PC already running the scheduled task will pick this mic up automatically within a minute of it being plugged in, once that PC's `config.json` (or a shared/synced copy of it) includes the new line.

## When a mic transfers to a different store

- [ ] Nothing to do to the mic itself — its volume label travels with it.
- [ ] Confirm the destination store PC already has this mic's line in its `config.json`. If the store maintains its own copy of `config.json` rather than a shared one, copy the line over.
- [ ] If the destination PC has never run this tool before, follow "First-time setup on a new store PC" above.

## Troubleshooting

| Symptom | Check |
|---|---|
| Nothing ever shows up in Drive | `C:\ProgramData\DjiMicAutoUpload\upload.log` — is anything being logged at all? |
| Log shows the "Googleドライブ同期フォルダが見つかりません" warning | Google Drive for desktop isn't running, isn't signed in, or `driveRoot` in `config.json` is wrong for this PC |
| Log shows nothing even with the mic plugged in | Check the mic's current volume label (File Explorer) exactly matches an entry in `config.json`; check Task Scheduler shows `DjiMicAutoUpload` as running/enabled |
| Log shows a successful copy but nothing appears in the Drive web UI | Local copy worked — this is now a Google Drive for desktop sync issue, check its app status icon, not this tool |
| Log shows an "エラー" line with a robocopy exit code ≥ 8 | A real copy error (permissions, disk, path length) — the exit code is logged; look it up against robocopy's documented exit codes |

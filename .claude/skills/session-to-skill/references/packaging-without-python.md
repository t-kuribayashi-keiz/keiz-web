# Packaging a .skill bundle without Python (Windows)

skill-creator's `scripts/package_skill.py` just zips the skill folder (parent-relative paths, so the skill's own folder name is the top-level entry inside the archive) and renames it to `.skill`. `python`/`python3` on this machine resolve only to the non-functional Windows Store alias, so run the equivalent in PowerShell instead:

```powershell
$src  = "C:\Users\<user>\.claude\skills\<skill-name>"
$zip  = "<output-dir>\<skill-name>.zip"
$dest = "<output-dir>\<skill-name>.skill"
if (Test-Path $zip)  { Remove-Item $zip  -Force }
if (Test-Path $dest) { Remove-Item $dest -Force }
Compress-Archive -Path $src -DestinationPath $zip -Force
Rename-Item -Path $zip -NewName "<skill-name>.skill"
```

`Compress-Archive` refuses to write directly to a `.skill` extension ("not a supported archive file format"), which is why it goes through a `.zip` first and gets renamed. Verify the internal structure before handing it over — it should contain `<skill-name>/SKILL.md` (and any `<skill-name>/references/...`) at the top level, not the bare files:

```powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead("<path-to>.skill")
$zip.Entries | ForEach-Object { $_.FullName }
$zip.Dispose()
```

Remember this only produces the file — sending it via a file-delivery tool in this Cowork/Claude Code interface does **not** trigger a one-click "Save skill" install (confirmed: it renders as an unpreviewable binary with no install affordance). Packaging is only useful here for handing over a single file instead of a folder of loose files; the user still has to place it manually into `~/.claude/skills/` on the target machine (extracting the zip there, or just copying the unpacked `SKILL.md`/`references` directly — which is simpler and skips this step entirely).

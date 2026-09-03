---
name: org-structure-table
description: Use this skill when the user wants to build or update an 組織体制表 — a matrix-style spreadsheet with roles/responsibility areas (担当) down the rows and the group's corporate entities/services across the columns, marked with ○/×/△ per cell — usually sourced from a photo of a whiteboard or meeting document plus (optionally) a recording of the meeting where it was discussed. Trigger on "組織体制表を作って", "体制表", requests to transcribe a whiteboard/handwritten org-structure photo into a spreadsheet, or follow-up requests to update/fill in ○×marks on a previously-built version of this table. This is specifically about the ROW-x-COLUMN MATRIX table format — if the user instead wants an org chart / hierarchy diagram or a role-assignment writeup (組織図, 役割分担), that is a different, related deliverable; check with the user which one they mean if it's ambiguous, since both have come up from the same restructuring discussions.
---

# Org Structure Table (組織体制表)

Builds the group's org-structure matrix — 担当 (responsibility area) rows × corporate-entity/service columns, marked ○/×/△ — from meeting materials (a photographed whiteboard/planning doc, sometimes plus an audio recording), and delivers it as a spreadsheet. Originates from an August 2026 internal meeting about a coming reorganization; the table is a living skeleton that gets its ○/×marks filled in over multiple passes as the restructuring firms up, so treat this as a repeatable procedure, not a one-off.

## Non-negotiable rules

1. **Never guess illegible handwriting.** Only transcribe a ○/×/△ mark into a cell if it is already clearly present in the source photo. If a mark is ambiguous or the handwriting can't be read with confidence, leave the cell **blank** and list it in a notes section for the user to verify against the original — do not infer what it "probably" says.
2. **"スプレッドシート" means Google Sheets, not a local Excel file.** Confirmed by direct correction in the source session: the user's first deliverable was a local `.xlsx`, and they responded "スプレッドシートがいいです" meaning they wanted a Google Sheet instead. Default to delivering the final table as a Google Sheet (via the Google Drive connector) unless the user explicitly asks for an Excel/`.xlsx` file. See `references/delivery-and-tooling.md` for the concrete steps.
3. **This machine's `python` does not work** (confirmed elsewhere: it resolves to a non-functional Windows Store stub). That means the general-purpose `xlsx` skill's Python/`openpyxl`-based scripts (including `recalc.py`) are not usable here. Build the workbook with **PowerShell + Excel COM automation** instead — see `references/delivery-and-tooling.md`.
4. **A non-mark item found in a cell (a name, a stray note) is not a ○/×/△.** Preserve it as a cell comment on that cell rather than discarding it or mis-transcribing it as a symbol. (Precedent: "栗林" — the user's own surname — turned up in a cell that could have been mistaken for a mark.)
5. **If an audio recording is provided, check whether a transcription tool is available before assuming you can't use it.** In the source session no transcription tool existed for `.m4a`, so the audio's content was simply not reflected in the table, and the user was told plainly rather than the audio being guessed at or ignored silently. If transcription still isn't available, tell the user up front and ask them to summarize the recording's key points in text instead.

## Table format

- **Rows (縦軸): 担当** — responsibility/functional areas (e.g. SEO・MEO・LLMO-type items). If the source material shows a row's assigned person corrected in **red ink** over the original text, the red version is the authoritative/latest one per the user's explicit instruction — add a distinct **「担当者（最新）」** column next to the row label to hold that corrected name, rather than overwriting or guessing at the crossed-out original.
- **Columns (横軸): 法人およびサービス** — the group's corporate entities/services. As of the source session (Aug 2026) this was a fixed set of 13, in this order:
  `直営, サンズミライ, グッド, スマイル, 心身堂, 採用, アイワ, リクスム, ピラティス, チョコザップ, リラックス, LUNA, 外部支援`
  Confirm this list with the user before reusing it — the company is actively restructuring, so the entity list itself may change between sessions. See `references/table-structure.md` for the full picture of what was actually populated in the source run.
- **Cell values:** ○ / × / △, transcribed only where already marked in the source (rule 1 above). Untouched/undecided cells stay blank — they are meant to be filled in later, by the user or in a follow-up pass with this skill.
- **A notes section is required alongside the main table** — call it 「メモ・要確認事項」 — listing: anything not reflected (e.g. unusable audio), cells left blank due to illegibility, and any adjacent reference material from the same meeting packet that doesn't fit the row/column shape (e.g. a separate typed role-assignment plan for named individuals). Don't force that extra material into the matrix — summarize it in the notes and offer to add rows if the user wants it incorporated.

## Standard procedure

1. Read whatever meeting materials are provided (photo(s), any audio). If audio can't be transcribed, say so immediately (rule 5) rather than proceeding silently without it.
2. Read the image(s) directly to extract: the row list (担当 items, with red-corrected names noted), the 13-column entity list (confirm against the known list above, updating if the user says it changed), and any ○/×/△ marks already visible.
3. Build the workbook via PowerShell + Excel COM (rule 3) — main table sheet first, notes sheet/section second. See `references/delivery-and-tooling.md` for the concrete method and gotchas (stray `EXCEL.EXE` processes, sheet ordering, `System.Drawing` for formatting).
4. Deliver as a Google Sheet by default (rule 2) — upload the finished workbook via the Google Drive connector. Note: doing it this way previously collapsed a two-tab Excel workbook (table + notes) into a single Google Sheets tab, with the notes placed below the table separated by a blank row. That's an acceptable fallback layout, but check whether true multi-tab upload is possible before defaulting to it again.
5. In your delivery message, explicitly re-state what was NOT reflected (illegible cells, unusable audio, unmapped reference material) so the user knows exactly what to check against the original — this is the main quality gate, not a full re-transcription review.

## Relationship to `org-structure-artifact` (verified 2026-09-03, not a duplicate)

The same August 2026 restructuring meeting packet also contained a typed role-assignment document (named individuals — 宇塚, 川瀬, 矢動丸, 採用 team members — mapped to duties) that this skill deliberately keeps OUT of the matrix table and only summarizes in notes. A separate skill, **`org-structure-artifact`**, covers building/updating an org-structure or role-assignment *document/Artifact* (HTML Artifact + PDF, multi-section narrative, diagram-style) from a session titled "組織図と役割分担" that came from what looks like the same restructuring effort.

A cross-functional review on 2026-09-03 read both skills' full SKILL.md bodies and confirmed **these are two different deliverables, not two views of one workflow that need merging**: this skill transcribes a photographed whiteboard/handwritten doc into a ○/×/△ spreadsheet matrix via PowerShell+Excel COM; `org-structure-artifact` builds a polished HTML/PDF narrative document (ideal structure → staff assignment → evaluation matrix) from an already-typed CSV the user provides, using the `artifact-design`/`artifact-diagramming` skills. The two only share one overlapping idea — a ○/×/△ coverage table — and even there it's this skill's entire deliverable vs. just one section (03 評価マトリクス) of the other's.

**How to choose**: if the user asks for a 組織体制表/マトリクス transcribed from a meeting photo or handwritten source, use this skill; if they ask for a 組織図/役割分担 or a polished document/PDF built from data they already have in text form, use `org-structure-artifact`. If genuinely ambiguous, ask which they mean rather than guessing.

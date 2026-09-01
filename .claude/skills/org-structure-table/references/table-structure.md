# Table structure, as actually built (Aug 2026 source run)

This is the concrete shape the table took the one time it's been built so far. Treat the
column list and specific role names as a snapshot, not a permanent spec — confirm with the
user whenever the underlying org is mid-restructuring (it was, at the time of this run).

## Sheet layout (Excel version)

- **Sheet 1 — 「組織体制」**: the main matrix. Rows = 担当 (responsibility areas), columns =
  the 13 corporate entities/services, cells = ○/×/△ where already marked in the source photo.
  A 「担当者（最新）」 column sits next to the row label, holding the red-ink-corrected name
  where the source photo showed a correction.
- **Sheet 2 — 「メモ・要確認事項」**: free-text notes — what wasn't reflected, what's illegible,
  reference material that didn't fit the matrix.

When delivered as a Google Sheet instead (see `delivery-and-tooling.md`), this collapsed into
a **single sheet**: the main table at the top, one blank row, then the notes content below it.
That collapse may have just been an artifact of how the upload was done rather than a deliberate
choice — worth testing whether a genuine multi-tab Google Sheet can be produced directly next
time, before assuming the single-sheet fallback is required.

## Columns (法人およびサービス) — 13, in this order, as of Aug 2026

1. 直営
2. サンズミライ
3. グッド
4. スマイル
5. 心身堂
6. 採用
7. アイワ
8. リクスム
9. ピラティス
10. チョコザップ
11. リラックス
12. LUNA
13. 外部支援

In the source run, only some of these columns had any ○/×/△ marks actually present in the
photo — the rest (roughly 採用 through 外部支援, i.e. columns 6–13) were left entirely blank
because the source material simply hadn't been marked yet for those columns. That is expected
and correct behavior (rule 1 in SKILL.md) — don't fill them in from guesswork just because a
row otherwise looks complete.

## Rows (担当)

Rows are functional/responsibility areas — one confirmed example from the source run was an
SEO・MEO・LLMO-type row. The exact full row list from that run is not preserved in detail here
(re-derive it from whatever fresh source photo/document the user provides each time — the row
list is exactly the kind of thing likely to shift between restructuring passes). What *is*
stable is the convention:

- If the source shows a row's responsible person's name **crossed out and rewritten in red
  ink**, the red version is authoritative (explicit user instruction). Put it in a distinct
  「担当者（最新）」 column rather than silently overwriting the row label — this keeps both
  versions visible in case the user disagrees with which one is "latest."
- A cell that looks like it might be a mark but is actually a name or stray note (confirmed
  example: "栗林" appearing where a ○/×/△ might have been expected) is **not** a mark — put it
  in a cell comment instead of transcribing it as ○/×/△ or dropping it.

## Reference material that doesn't fit the matrix

The same meeting packet included a separate typed document ("案①") proposing role assignments
for named individuals (宇塚, 川瀬, 矢動丸, and 採用-team members). This does not fit the
row(担当) × column(entity) shape of the main table. Don't force it in — summarize it in the
メモ sheet/section and explicitly offer to add rows if the user wants it incorporated. This is
also the kind of content that may belong in the separate `org-structure-artifact` skill's
deliverable instead (see SKILL.md's overlap note).

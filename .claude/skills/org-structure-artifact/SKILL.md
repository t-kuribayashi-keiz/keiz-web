---
name: org-structure-artifact
description: Use this skill when the user asks to build, update, or redesign an organizational-structure / role-assignment document for their business — e.g. "組織図を作って", "体制表を修正して", "役割分担をまとめて", turning a raw org spreadsheet/CSV into a polished org-structure deliverable, or iterating on an existing 組織体制／集客体制 Artifact (renaming sections, adjusting the diagram, fixing wording, exporting to PDF). Also trigger when the user wants to formalize a multi-axis role division (e.g. "法人軸 vs 集客軸 vs スペシャリスト" style splits) for the multi-entity salon business, or asks for a PDF export of an org/role chart with embedded Japanese fonts. Do not trigger for a simple headcount list or a generic, unrelated project org chart.
---

# Org structure / role-assignment artifact

Builds a single polished HTML Artifact (plus print-ready PDF) that presents an organization's role structure and how current staff map onto it, sourced from a raw spreadsheet/CSV of who-does-what and how well each business unit is currently covered. Extracted from the session that produced "集客体制について" (2026年8月–9月, keizgroup's ~150-salon acquisition team reorg). See `references/background.md` for the full story of how the deliverable evolved.

**Verified 2026-09-03 (cross-functional review): this is a separate skill from `org-structure-table`, not a duplicate.** Both originate from the same August 2026 restructuring effort, but the deliverables and inputs differ:

| | `org-structure-table` | `org-structure-artifact` (this skill) |
|---|---|---|
| Output | Google Sheets spreadsheet: 担当(row) × 法人/サービス(column) matrix, ○/×/△ cells | One polished HTML Artifact (+ optional print PDF): multi-section narrative (ideal structure → current-staff assignment → evaluation matrix) |
| Input | A photographed whiteboard/handwritten meeting doc (+ optional audio) | An already-typed CSV/spreadsheet/pasted text the user provides |
| Build tooling | PowerShell + Excel COM (this machine's `python` doesn't work) | `artifact-design` / `artifact-diagramming` skills, headless-Chrome PDF export |

The only overlapping concept is this skill's "03 評価マトリクス" section, which is a similar
○/×/△ coverage table — but it's one section inside a larger narrative document, not this
skill's primary deliverable. **How to choose**: if the user wants a 組織体制表/マトリクス
transcribed from a photo or handwritten source, use `org-structure-table`; if they want a
組織図/役割分担 or a polished document/PDF built from data they already have in text form, use
this skill. If genuinely ambiguous, ask which they mean (both skills' descriptions already say
to do this at intake).

## Non-negotiable rules

1. **Never try to log into the user's Google account to read a Google Sheet.** Browser access to a Sheets URL will hit a login wall this skill cannot pass. Ask the user to either (a) change sharing to "anyone with the link can view," or (b) export/paste the data as CSV or plain text. Do this immediately rather than retrying navigation.
2. **Cell color/highlighting is lost in a CSV export.** If the source spreadsheet uses color (e.g. a yellow cell to mark an unfilled/to-be-hired position), a CSV will not carry it. Explicitly ask the user which cells were highlighted and what the highlight means — do not guess from context, and do not assume blank cells are the highlighted ones.
3. **Echo back your structural reading before building anything.** State, in a compact table, which rows/columns you think are which axis, who you think owns what, and which cells are which status — then ask "did I get this right?" This session's first read of the source data mis-identified which rows were duplicates vs. a genuinely separate axis; the user had to correct it twice before the structure was confirmed.
4. **Default to positive framing when a reorg moves work away from a named person.** This user explicitly stripped negative/deficiency language (e.g. a "体制再編の2大課題" / "2 major problems with the current structure" section) from a draft and asked for it to be reframed around opportunity ("素晴らしい成果を出しているため、今度は集客に注力してほしい" instead of anything implying the person wasn't handling their old scope well). Never write internal HR/reorg copy that reads as criticizing a named staff member; if a section could read that way, flag it and ask before publishing.
5. **Don't put a name in a placeholder slot without being told to.** A "yet to be hired" position (marked yellow in the source) should stay unnamed/labeled as such (e.g. "採用予定") until the user explicitly says who now owns it. When they do name someone, also check whether they want any transitional wording removed (e.g. this user first accepted "一旦、栗林が担当する" then later asked to drop "一旦担当" entirely once the assignment was no longer meant to read as temporary).
6. **Ask, don't assume, on org-authority framing.** When it's ambiguous whether a top role should carry a named person or stay role-only (e.g. "マーケ責任者"), ask directly (this session used AskUserQuestion for exactly that) rather than picking a default.
7. **"Ideal structure" sections should contain no names and no per-entity breakdown** if the user has said the structure applies uniformly across entities/people — keep the "define the role, then assign people" narrative arc intentionally separated into two sections (see Procedure step 3). This was a specific, twice-repeated correction in the source session: an early draft that mixed structure and assignment in one diagram was rejected as "people being forced into a job description" (「人に仕事を無理やりつけているような印象」).

## Procedure

1. **Get the source data.** CSV/pasted text is fine; note any info that can't survive the format (colors, comments/notes) and ask about it explicitly (rule 2).
2. **Confirm the axis model in words first.** Get the user to state (or confirm your restatement of) each axis of responsibility before drawing anything — e.g. this business used: 法人軸 (per-entity revenue owner) / 集客軸・チャネル担当 (per-channel revenue owner) / スペシャリスト業務 (cross-channel domain specialists). Treat the axis names, count, and definitions as specific to this business and this point in time — re-derive them fresh each time rather than assuming this exact 3-axis template applies to a future request. See `references/org-structure-conventions.md` for the concrete convention as of Sept 2026.
3. **Draft the deliverable as one HTML Artifact.** Load the `artifact-design` skill (and `artifact-diagramming` if a real structure diagram is needed, not just cards) before writing markup. Use this section order — it's the narrative arc the user landed on after an explicit correction ("あるべき組織像の提示から始めて、その上で担当者を当てはめる" — define the ideal shape first, assign people second):
   - **01 あるべきチーム体制 (ideal structure)** — roles only, no people's names, no per-entity split. Once the user asks for something that "reads at a glance," this needs a real structural diagram (hierarchy/flow with labeled arrows), not just a row of cards — a stack of role cards was explicitly rejected here as unclear.
   - **02 現メンバーの当てはめ (assigning current staff)** — real names, any flat "pair" arrangements (draw/describe as non-hierarchical if that's the intent — this session paired two people on one channel and had to make sure neither box looked subordinate to the other), and the *positive-framed* rationale for any role transfers.
   - **03 評価マトリクス** — the entity × channel (or whatever the two cross-cut axes are) ○/△/× coverage table.
   - Fold any list-only section into 02 rather than keeping it separate if it just restates who's on the specialist axis — this session collapsed a standalone "04 スペシャリスト業務一覧" into 02.
   - Keep the header minimal: title + an effective-date subtitle (e.g. "組織体制 / 2026年9月〜"). Skip a long explanatory paragraph under the header — this user asked to delete it twice once the sections spoke for themselves.
4. **Apply wording corrections literally.** This workflow produces many small, exact find-and-replace instructions ("`X` を `Y` に修正"). Match the user's exact phrasing — do not paraphrase or "improve" it. Batch a turn's edits into one Artifact republish rather than republishing after every single edit.
5. **Verify against a real screenshot, not a static markup read**, whenever asked to check "did it render correctly" — take a browser screenshot of the live Artifact (or, for print output, a headless-Chrome screenshot at real dimensions) and look at it before reporting back.
6. **If asked to export a PDF**, see `references/pdf-export-headless-chrome.md` for the technique and the specific print-layout bugs hit in this session (default body margin offsetting every page, a stray whitespace text node adding phantom height, needing explicit per-section page divs rather than relying on automatic page breaks). Deliver the file to the user (e.g. their Downloads folder) with a Japanese filename matching the Artifact's title, and confirm the page-per-section split with the user rather than silently compressing sections to save a page — this user preferred one clean section per PDF page.

## What this skill does not cover

- It does not fetch data from a live Google Sheet on the user's behalf (rule 1) — that always needs a CSV/paste handoff.
- It doesn't establish a recurring cadence: nothing in the source session indicated this needs to be rebuilt on a schedule. Treat each invocation as triggered by an actual reorg/update the user is doing right now, not as a periodic job. If the user starts asking for this repeatedly (e.g. every time a new salon/entity is added), that's a signal to add a "new entity onboarding" checklist here — it doesn't exist yet because it was never observed in the source session.

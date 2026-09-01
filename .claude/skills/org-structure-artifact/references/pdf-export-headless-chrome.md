# Exporting the Artifact to a print-ready PDF

The source session generated a 4-page A4-landscape PDF from the finished HTML Artifact using a locally-installed headless Chrome driven from PowerShell (this machine's `python` is a non-functional Windows Store stub, per the session-to-skill house notes, so Chrome's own `--headless --print-to-pdf` is the practical path, not a Python/wkhtmltopdf pipeline). The exact PowerShell invocations weren't preserved in the extracted transcript — only the assistant's own narration of what it found and fixed — so treat the steps below as the debugging checklist to re-derive the commands from, not a verbatim script to paste.

## Approach

1. Save the Artifact's HTML to a local working file (not the published Artifact URL — a local copy you can add print-only CSS to).
2. Add a `@media print` block (or a dedicated print stylesheet) with:
   - `@page { size: 297mm 210mm; margin: 0; }` for A4 landscape.
   - Explicit per-section page containers (e.g. one `<div class="page">` per logical section) rather than relying on `page-break-*` / `break-*` properties to split content automatically. The session found automatic flow-based breaking unpredictable once sections had mixed content heights, and switched to "one page = one explicit container" once the count needed to land on a specific number of pages.
   - Force background colors/graphics to print: `-webkit-print-color-adjust: exact; print-color-adjust: exact;` on `html`/`body` (needed for anything relying on background fills, like the yellow highlight or diagram box colors).
3. **Embed the Japanese fonts** actually used on screen (this session used Shippori Mincho for display text and Zen Kaku Gothic New for body text) so the PDF renders identically on a machine that doesn't have those fonts installed — either via a Google Fonts `<link>` (fine for the on-screen Artifact, since Google Fonts is reachable) or, for the exported file to be fully self-contained, inline `@font-face` with base64 data URIs.
4. **Run headless Chrome to print to PDF**, roughly: launch Chrome with `--headless=new --disable-gpu --print-to-pdf=<output.pdf> --print-to-pdf-no-header --no-pdf-header-footer` (flag names vary by Chrome version — check `chrome --help` if these don't work) against the local `file:///...` path, sized to the print CSS.
5. **Verify visually before calling it done** — do not trust a static HTML read or a viewport screenshot. Take a full-page screenshot of the *rendered PDF pages themselves* at real pixel dimensions (the session used a headless-Chrome screenshot workflow specifically because "静的スナップショットは信頼できない" — static snapshots proved unreliable for catching print-layout bugs) and visually inspect for cutoff/overlap before delivering.

## Bugs actually hit in this session (check for these first)

- **`body`'s default 8px margin** silently offset every page's content away from the intended page boundary. Fix: `margin: 0` explicitly on `html, body` in the print stylesheet.
- **A stray whitespace text node inside `.page`** (e.g. leftover indentation/newline text between tags) added invisible height at the top of a page, throwing off page-break math. Fix: check for and strip whitespace-only text nodes directly inside any container you're using as a hard page boundary, or restructure so page containers only ever contain element children.
- **Page count came out higher than expected** the first couple of passes — resolved by explicitly measuring each content block's real rendered height (a small script that loads the page in headless Chrome and reads `getBoundingClientRect()`/`scrollHeight` on each candidate section) rather than eyeballing it, then hand-assigning sections to page containers to hit the target page count (4 pages, one per section, in the final version).

## Delivery

- Save the PDF to the user's Downloads folder (this session used `C:\Users\keizgroup634\Downloads\<Artifact title>.pdf`, matching the Artifact's display title) and hand it over with `SendUserFile` (or whatever the current file-delivery mechanism is).
- Also update the on-screen Artifact if wording changed after the PDF was generated — the source session had to re-export the PDF once after a late footnote-deletion request, so treat "update the doc" as implicitly "regenerate the PDF too" if a PDF was already delivered.
- State the final page count and what's on each page in the handoff message (this session: P1 ideal structure diagram / P2 marketing-lead role + policy / P3 channel + specialist roles / P4 evaluation matrix) so the user can sanity-check the split without opening the file.

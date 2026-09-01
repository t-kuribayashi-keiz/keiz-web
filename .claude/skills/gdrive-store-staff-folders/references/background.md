# Background: why this project exists, and how the one working session went

## Why the user wants this

The user manages roughly 150 stores (salons/clinics) for their company and already has a manual roster ledger: a Google Drive spreadsheet with store names in column A and, in the row directly under each store's name, that store's staff members listed across columns B onward. Staff move between stores (異動) periodically, and the roster ledger is the thing that gets updated when that happens. Today, presumably, the corresponding Google Drive folder structure (one folder per store, one subfolder per staff member holding that person's files) has to be kept in sync with the ledger by hand. The user wants that sync automated: run once a month, around the 5th (early enough in the month to catch the prior month's changes), compare the ledger against the actual Drive folder tree, and only after showing the user the differences and getting a yes, move the affected folders.

The user was explicit up front about wanting this built in **Google Apps Script (GAS)**, not as an AI-agent-run task each month, specifically because the roster file is large (due to embedded photos) and re-processing it with an LLM every month would burn a lot of tokens for what is, structurally, a very simple table. This is a case where the user deliberately wants a deterministic script rather than an AI loop for the recurring part — the AI's role here is to design/build/fix the GAS project, not to run it repeatedly.

## Key exchange 1: the "just read cells" pushback

The assistant's first move was to inspect the actual roster file via the Drive connector's `get_file_metadata`, and found it was a plain `.xlsx` file (not a native Google Sheet) sitting right at Google's ~100MB threshold for Office-compatibility editing in Drive, already showing "can't save changes" warnings in the UI. The assistant's instinct was to propose splitting the automation off from the human-facing photo-heavy ledger entirely: keep a second, lightweight, native Google Sheet containing only store name / staff name / employee number / qualification, and have GAS read that instead.

The user rejected this specific proposal, and the reasoning matters for anyone resuming this project: the shared ledger is **continuously updated every month** by the people actually doing the staffing changes, and the user does not want a second file that could drift out of sync with the real source of truth, or add a manual copy-step to their process. They also pushed back on the implied assumption — they weren't asking the automation to read the photos, just the cell values, and didn't see why the file format should force a second spreadsheet into existence. This is a "listen to the actual constraint, not the easy technical workaround" moment: the size/format problem is real, but the user's answer was "solve it without moving my source of truth," not "avoid the problem by using a different source."

Practical implication for future work on this: whoever picks this up next should not re-propose the mirror-sheet idea as if it's fresh — it was already raised and declined once. It's fine to circle back to it only if directly reading the live xlsx from GAS turns out to be genuinely impossible (as opposed to merely inconvenient), and if so, that should be explained to the user as "the earlier idea turns out to be necessary after all, here's why," not reintroduced silently.

## Key exchange 2: the wrong folder link, and the duplicate-name problem

When asked to point at the actual Drive location, the user supplied a folder URL — but it turned out to belong to an unrelated app ("PlaudNote") and contained none of the expected store folders. This was almost certainly an honest copy/paste slip (wrong browser tab or wrong link entirely), not a deliberate test, but it's a useful reminder that **every Drive link a user pastes should be verified against its actual contents before being wired into anything**, because a plausible-looking link can point somewhere completely unrelated.

Separately, the assistant tried to locate the store folders by searching for a known store name ("本八幡南口") directly, and found the situation was messier than a single clean tree: that name (or close variants) turned up in multiple different places in the Drive — a folder named with a trailing "接骨院" (clinic) suffix appeared under three different parents, plus a bare `本八幡南口` folder, plus a numbered variant `058. 本八幡南口`. This means store folders in this Drive are not guaranteed to be uniquely named or centrally located, and a naive "search for the store name, use whatever comes back" approach would be unsafe once real move/create operations are involved — it could just as easily move a staff folder into the wrong same-named store folder.

The session ended here: the assistant asked the user to manually open the real parent folder (the one whose children are the store folders that actually contain staff subfolders) and paste that exact URL, so the ambiguity could be resolved by a human who can see the real tree, rather than guessed at via search. **The user had not replied by the end of the transcript** — this is the actual, current blocker on the project, not a design question that still needs debate.

## What was never reached

Because the session stopped at the folder-identification blocker, none of the following were actually discussed, decided, or built:
- The real GAS code (no Apps Script project/file was created).
- Whether the roster xlsx can in fact be read by GAS via some route other than `SpreadsheetApp` (e.g. Drive API's export/download of sheet data) — the assistant only established that `SpreadsheetApp` itself can't open it; it did not test alternatives before the conversation moved to the folder-location question.
- Where exactly the "退職者リスト" folder should live, or whether one already exists somewhere in this Drive.
- How the monthly diff should be presented to the user for approval (email, chat message, a dedicated tab in the sheet, etc.) — nothing was decided.
- Any error-handling, logging, or audit trail for the moves themselves.

## Rules that ARE settled (carried into SKILL.md as non-negotiable)

Even though implementation never started, three points were stated clearly and unconditionally by the user and should not be re-litigated:
1. Staff folders must never be deleted — they hold real files.
2. Departed/unmatched staff folders go to a 退職者リスト folder instead of being deleted.
3. The system should surface a diff and wait for explicit user approval before moving anything — this was baked into the original request, not an assumption added later.

## No cost/time logging convention was established

Unlike the user's SalonBoard work (which has an established `hpb_work_log.csv` per-task logging habit — see the `hpb-salonboard-update` skill), no logging convention came up anywhere in this session. Don't invent one unprompted; if the user wants task-time/token logging for this project too, ask them whether they want the same CSV-log pattern applied here, rather than assuming it carries over automatically.

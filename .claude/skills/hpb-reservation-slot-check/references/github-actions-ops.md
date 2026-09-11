# Running the K/L check on GitHub Actions (運用ノート)

Everything here was confirmed 2026-09-03 / 2026-09-04 while moving the K/L check off the
Colab notebook onto `.github/workflows/hpb-reservation-slot-check.yml`. The notebook is no
longer the thing that runs daily — this workflow is — so read this before touching the
schedule, the inputs, or the log-reading procedure.

## Never schedule on the top of the hour

The first cron was `0 4 * * *` (13:00 JST). **It never fired.** GitHub's own docs warn that
on-the-hour schedules are the most congested window and can be delayed or dropped outright.
Moved to `7 4 * * *` (2026-09-04, commit `2a72322`).

Two consequences worth remembering:

- **A scheduled run that simply never appears is not evidence of a broken workflow.** Check
  whether it fired at all before debugging the code:
  `gh api "repos/t-kuribayashi-keiz/keiz-web/actions/workflows/<id>/runs?event=schedule"
  --jq '.workflow_runs[] | {created_at, status, conclusion}'`. An empty list for the
  expected day means "never scheduled", not "ran and failed".
- **Apply the same offset rule to any new cron added to this repo**, not just this one.

## Why 13:00 JST specifically

Every salon trades until 13:00, breaks, and reopens at 15:00 for the 午後の部 (栗林さん,
2026-09-03). The point of the daily run is to have the ○/✕ list sitting on the sheet
**before the afternoon session starts**, so a wrongly-blocked slot can still be fixed the
same day. A full run over ~142 shops takes 15–20 minutes, so a 13:07 start leaves ample
margin before 15:00 — if the cron ever moves later, keep that margin intact.

## `schedule` is currently disabled (2026-09-11) — do not re-enable without reading this

Despite the `7 4 * * *` cron (04:07 UTC = 13:07 JST), actual runs kept landing 4–5 hours
late (17:30–18:15 JST) for at least a week straight (2026-09-05 through 2026-09-11) — this
is a *different* problem from the original top-of-the-hour issue above (already fixed by
the `:07` offset) and has never been diagnosed; GitHub Actions schedule delays of a few
minutes are normal, but a consistent multi-hour delay every single day is not something
the "avoid :00" advice explains. On 2026-09-11 that lateness stopped being just "misses the
15:00 margin"
and turned into **active data corruption**: a run that fired at 17:52 JST overwrote a
correct 13:23 JST run's K/L results (○111/✕26/?5) with a massively inflated false-positive
set (○16/✕121/?5).

**Working theory**: `default_date_window()` starts the window at 当日PM. A run that
executes late in the day re-evaluates the *current* day's PM slots after much of that
afternoon has already elapsed — and the public calendar shows an elapsed time slot as
unavailable regardless of whether it was ever actually blocked, so the scraper reads it as
✕. The later the run, the more of today's PM has "already happened" and gets swept into
the ✕ count. A 13:07 run only has ~10 minutes of elapsed PM to misread; a 17:52 run has
almost 5 hours of it.

**Current state**: the `schedule:` trigger was removed from this workflow entirely
(2026-09-11) — `workflow_dispatch` still works, so manual/on-demand runs are unaffected.
`daily-ops-monitor` has been told this is intentional and not to report "no schedule event
today" as an anomaly for this workflow (see its own `.md`).

**Before re-enabling `schedule`**, both of these need to actually be resolved, not just the
chronic-late-firing symptom:
1. Why the firing is chronically 4-5h late in the first place (never diagnosed — the
   "avoid the top of the hour" fix from 2026-09-04 didn't touch this; `04:07 UTC` is not an
   on-the-hour minute).
2. Whether `default_date_window()`'s elapsed-same-day-PM problem needs a design fix
   independent of #1 (e.g. excluding already-past half-days from judgment) — a fix to #1
   alone reduces the *size* of the elapsed window on a future correctly-timed run, but
   doesn't make the false-positive mechanism itself go away, so a late run (for whatever
   reason, e.g. Actions congestion on a given day) would still corrupt the sheet the same way.

Tracked in `docs/backlog.md`.

## Restoring K/L after a bad run (worked example, 2026-09-11)

If a run's K/L output turns out to be wrong (the false-positive bug above, or the
zero-shops-processed bug in `known-bugs.md`), and you have a *previous* run's log that was
confirmed correct:

1. `gh run view <good-run-id> --log` and save it.
2. Parse the `🔍 解析中 (i/142): 店舗名` / `  -> 結果: 判定 (詳細)` line pairs into a
   142-row `K列詳細\tL列判定` TSV **with a script**, not by hand — see
   "Don't hand-transcribe bulk tabular data" in `references/sheet-writing-notes.md` for why
   a manual re-transcription of >100 rows is dangerous here (a real near-miss: 8 rows
   silently dropped out of 142 when done by hand, which would have shifted every subsequent
   row onto the wrong shop).
3. Set the OS clipboard directly from that TSV file (PowerShell: `Set-Clipboard -Value
   (Get-Content -Raw -Encoding UTF8 <file>)`) rather than routing it through the browser's
   own clipboard APIs, then paste into `K3` on `AIチェック用ver.2` in one shot.
4. Verify a couple of spot-check cells (e.g. the first and last row) before trusting it —
   see `references/sheet-writing-notes.md` for why a full re-paste still needs verification
   even though the source was "known good".

## Scheduled run vs. manual dispatch

- **A scheduled run writes for real.** `schedule` passes no inputs, and the workflow reads
  `${{ github.event.inputs.mode || 'apply' }}` — so the fallback is `apply`, not `dry-run`.
  There is no "the cron is only ever a dry-run" safety net; treat every schedule change as
  a change to something that writes to the production sheet.
- `concurrency: group: hpb-reservation-slot-check` with `cancel-in-progress: false` means a
  manual dispatch fired while another run is in flight **queues behind it rather than
  cancelling it**. To actually stop a run, `gh run cancel <run-id>` (used successfully
  2026-09-04 to abort a default-window run in favour of a custom-range one).

## One-off date ranges (inputs added 2026-09-04)

`workflow_dispatch` takes optional `start_date` / `start_half` / `end_date` / `end_half`, so
a single ad-hoc window can be checked **without touching the permanent rolling default**
(`default_date_window()` = 当日PM〜3日後AM). Use these for "今日だけこの範囲で見て" asks
instead of editing the script or the cron.

```
gh workflow run hpb-reservation-slot-check.yml --ref main \
  -f mode=apply \
  -f start_date=2026-09-04 -f start_half=PM \
  -f end_date=2026-09-07 -f end_half=AM
```

**Trap: passing a `*_half` without its matching date silently does nothing.** `main()` reads

```python
start_half = args.start_half if args.start_date else d_start_half
```

so the half is only honoured when the corresponding date is also supplied; otherwise it
falls back to the default (PM). The workflow does forward a lone `start_half` to the script,
so this fails quietly rather than erroring. Always pass date and half as a pair.

## Reading the log

- **Every `print` in the scrape loop passes `flush=True`** (commit `e36c13a`). Without it
  Actions shows nothing at all for ~15 minutes and a healthy run looks hung. Keep `flush=True`
  on any print added inside a long loop here.
- The per-shop line is
  `  -> 結果: ✕ (09/04PM:✕ | 09/05AM:○ | 09/05PM:○ | ...)`, and dry-runs end with a
  `内訳: ○.. / ✕.. / ?..` summary. Fastest way to review a finished run:

```
gh run view <run-id> --log > /tmp/run.log
grep -E "内訳|-> 結果" /tmp/run.log
```

## What K/L actually mean (store-level aggregation)

```python
final_judge = "✕" if has_any_ng else ("○" if has_any_data else "?")
```

- **✕** — at least one half-day in the window judged ✕. Not "the whole window is bad".
- **○** — data was found and nothing in the window was ✕.
- **?** — no data at all for any slot in the window. That is a scraping/listing problem
  (dead couponId, page not rendering), **not** "fully booked". Treat ? as "go look", not as
  a bad slot.

**Because ✕ is an any-slot OR, widening the window mechanically raises the ✕ count.** The
6-slot window (9/4PM–9/7AM) returned ✕31 where a 5-slot window on the same morning returned
✕20 — that difference is the aggregation rule, not a regression (2026-09-04). Only ever
compare ✕ counts between windows of equal width.

## The test step fails locally, and that is expected

The workflow runs `python3 -m unittest discover -s tests -p "test_hpb_slot_check.py" -v`
before the scraper, as a credential-free smoke test. **Run that same command on 栗林さん's
PC and it errors out** with `ModuleNotFoundError: No module named 'jpholiday'` (confirmed
2026-09-04) — `scripts/hpb_slot_check.py` imports `jpholiday`/`gspread`/`playwright` at
module scope, and those are only installed inside the Actions runner. `python -m unittest
discover -s tests` (the whole suite) therefore reports `FAILED (errors=1)` locally while the
other 110 tests pass.

This is a local-environment gap, **not a broken workflow and not a regression to fix**.
Either install the deps (`pip install jpholiday gspread playwright`) or scope the local run
to the other tests. Don't "fix" it by moving the imports or deleting the workflow's test
step.

## `gh` is not authenticated on disk on this PC

In a fresh session `gh auth status` reports "not logged into any GitHub hosts", and no
`hosts.yml` exists under `AppData/Roaming/GitHub CLI/` or `~/.config/gh/` — yet an earlier
session on the same machine ran `gh workflow run` / `gh run view` without trouble
(2026-09-04). So the credential is session-scoped, not persisted to disk.

Before promising any work that depends on reading Actions logs or dispatching a run, **run
`gh auth status` first**. If it comes back unauthenticated, ask the user to run
`! gh auth login` in their terminal — do not assume a previous session's access carries
over, and do not go looking for the token elsewhere on the filesystem.

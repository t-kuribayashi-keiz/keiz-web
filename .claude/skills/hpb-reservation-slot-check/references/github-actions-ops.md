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

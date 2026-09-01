# Scheduling constraints: history and current state

## Purpose

Once staff have manually entered their requested days off (希望休, red font) on a monthly calendar sheet, the automation fills in each person's *remaining* regular days off (公休) up to a per-person target quota (entered by the user in step ①, "月次シートを作成"), while respecting a set of coverage and fairness rules for the store.

## Evolution (kept for context — useful if asked to revert/retune)

1. **Initial version**: hard cap of max 2 staff off per day; hard constraint that each qualification (柔道整復師 / 鍼灸師) must have ≥1 person working every open day; soft constraint trying to keep ≥1 female staff and ≥1 新患対応 (new-patient-handling) staff working every open day (allowed to fail, but reported in the completion message if it does).
2. User asked to **interpret** "女性スタッフ／新患対応スタッフができるだけ全出勤日に勤務" before assuming — clarified as *category-level* coverage (at least one person of that category present each day), not "minimize this specific individual's days off." This was confirmed with the user before the soft-constraint code was written.
3. User later asked to **remove the "max 2 per day" cap entirely**. Removing it with nothing else in place caused very uneven results — the greedy fill (which had been going strictly in date order once qualification constraints were satisfied) piled days off onto whichever days were easiest to fill first.
4. Fix: switched the fill strategy to **even distribution** — for each staff member's remaining quota, always assign to the currently least-occupied *eligible* day first (fewest people already off that day), falling back to more-occupied days only once the emptier ones are exhausted. This, combined with the still-active qualification/coverage constraints, produces an approximately flat spread of days off across the month.
5. **院長 (director) constraint added**: a new スタッフマスター column flags the store director. That person's total days off within days 1–7 of the month (**including** any red requested days already on the calendar) must not exceed 1. Implemented as a hard constraint that blocks the automation from assigning a day in that window past the cap; if the red requests alone already exceed the cap, the script reports it as a warning rather than trying to silently fix it. Thresholds are named constants: `DIRECTOR_EARLY_WEEK_DAYS` (7) and `DIRECTOR_EARLY_WEEK_MAX` (1) — change these, don't hardcode new logic, if the rule needs tuning (e.g. a different window length).

## Current rule set (end of session)

- **Hard — qualification coverage**: every open calendar day must have at least one working (not-off) staff member for each tracked 資格 (柔道整復師, 鍼灸師).
- **Hard — director early-month cap**: the 院長-flagged staff member may have at most `DIRECTOR_EARLY_WEEK_MAX` (1) day off, red-requested or auto-assigned, within the first `DIRECTOR_EARLY_WEEK_DAYS` (7) days of the month.
- **Soft — category coverage**: try to avoid 0 female staff or 0 新患対応 staff working on any given day; if unavoidable given other constraints, allow the assignment and report it in the completion message rather than blocking.
- **Distribution**: within all of the above, always prefer filling the currently least-occupied eligible day for a given staff member, to spread everyone's days off evenly across the month.
- **No cap** on the total number of people off on a single day (the earlier "max 2" cap was removed at the user's request and not replaced with a different cap — only the distribution logic above prevents clustering).

If asked to add a new constraint, follow the same pattern already established: decide hard (block assignment) vs soft (allow + report) based on how the user describes it, confirm ambiguous "できるだけ" (as much as possible) language explicitly, and expose any numeric threshold as a named constant near the top of the script.

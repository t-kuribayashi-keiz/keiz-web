# Tracking plan-quota impact via before/after usage screenshots

Token counts computed from the transcript (see `token-usage-logging.md`) don't tell the user what a task actually cost against their Claude plan's rate limits, because the user runs multiple tasks/sessions concurrently — a token figure from this session alone can't be mapped to "how much of my quota did this specific task use." The workaround, confirmed with the user: have them send a screenshot of the Claude usage settings page (Settings → 使用量/Usage) immediately before and immediately after the task, and read the percentages directly off the image.

## What the screenshot shows

Two bars matter:
- **現在のセッション (current session)** — resets on a rolling ~5-hour window; shows a countdown like "3時間32分後にリセット" and a "N% 使用済み" figure.
- **すべてのモデル (all models, weekly)** — resets weekly on a fixed day/time (e.g. "9:00(土)にリセット"); also shows "N% 使用済み". This is the one that matters most for cumulative tracking since it doesn't reset mid-week.

(There's sometimes a separate per-model bar, e.g. "Fable" — ignore it unless the user's plan structure makes it relevant; it wasn't relevant for Sonnet 5 usage.)

## Procedure

1. **Before starting a task**, ask the user to send a screenshot of this settings page. Read off: session % used + reset countdown, weekly % used + reset day.
2. Do the task as normal.
3. **Right after finishing** (before the user moves on to something else), ask for the same screenshot again.
4. Compute the delta for each bar: `after% - before%`. Report both, but treat the **weekly** delta as the more meaningful "quota cost" figure, since the session bar resets every few hours regardless of activity and a small task can show 0% session delta just from rounding.
5. Log the deltas in `hpb_work_log.csv` alongside the token/time figures (see SKILL.md's Logging section for the column list).

## Caveats — be upfront about these, don't overclaim precision

- **Not isolated from other concurrent work.** If the user runs other tasks/sessions in the gap between the "before" and "after" screenshot, that usage is included in the delta too. This method measures "how much did the plan's usage move while this task was running," not "how much did this task alone cost" — say so if the numbers look inflated relative to the task's own token count.
- **A reset happening mid-task breaks the subtraction.** If the countdown shown in the "before" screenshot would elapse before the "after" screenshot is taken (rare for a short task, more likely for a long one straddling a 5-hour boundary), the session % may drop instead of rise. Notice this if `after% < before%` and flag it rather than reporting a nonsensical negative delta — note in the log that a reset occurred instead.
- **Percentages are coarse (whole numbers, sometimes only visible in 1% steps).** Don't present the delta with false precision — round-number percentages are all that's available.

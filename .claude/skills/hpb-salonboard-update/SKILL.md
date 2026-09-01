---
name: hpb-salonboard-update
description: Use this skill whenever the user asks to update, edit, add, remove, or bulk-change content on SalonBoard (salonboard.com) for one or more of their HotPepper Beauty salons — e.g. "update the coupon text for [salon]", "change 9月末まで to 10月末まで on these stores", "非掲載にして", "反映して", "この店舗のクーポンを直して", or any recurring SalonBoard maintenance task across the ~150 salons the user's company operates. Also trigger on mentions of "SalonBoard", "掲載管理", "クーポン掲載情報", "反映する", or the salonboard.com admin backend for a salon — even if the user doesn't name this skill explicitly. Do NOT trigger for simply browsing/reading the public beauty.hotpepper.jp listing pages with no edit intent.
---

# HPB SalonBoard Update

Operational playbook for editing content on SalonBoard (salonboard.com), the admin backend behind the user's HotPepper Beauty salon listings. The user's company runs ~150 seikotsuin (chiropractic) salons through one headquarters (本部) SalonBoard account, and wants routine SalonBoard maintenance — coupon wording rollovers, content tweaks, etc. — delegated here instead of being redone from scratch each time.

## Non-negotiable rules

1. **Never type the SalonBoard password.** Logging in is the one step that always stays with the user — have them log into SalonBoard in their real Chrome (via the `claude-in-chrome` MCP tools, not the sandboxed browser tools, since only the real Chrome carries their session) before any automation starts. If no tab is logged in yet, ask them to log in and confirm rather than attempting it yourself.
2. **Draft-saving and publishing are two separate decisions — treat them that way.** SalonBoard's coupon editor (and likely other tabs) only stages a change when you click 登録; a banner then says the change is *not yet live* until someone clicks a separate "◯◯情報を反映する" button (found on the relevant 掲載管理TOP page). The user has explicitly said they want to review the draft state before anything goes live. So: batch-editing/saving many items under one approval is fine, but **always stop and ask again, freshly, before clicking any 反映/publish button** — never fold that into the earlier "please make these edits" approval, no matter how routine the batch felt.
3. **salonboard.com is the only editable surface.** beauty.hotpepper.jp is the public, read-only consumer-facing site — never mistake it for the admin backend, and never attempt to "log in" or edit there.

## Standard workflow

0. **Ask for a usage-quota screenshot before starting.** The user wants to know each task's real cost against their Claude plan limits, which a token count alone can't show (they run several things concurrently). Ask them to send a screenshot of Settings → 使用量 (Usage) before you begin — see `references/usage-quota-tracking.md` for what to read off it. Skip this only if the user explicitly says not to bother for a given task.
1. **Confirm scope before touching anything.** Nail down: which salon(s) (name is enough — see Multi-store below), which SalonBoard section (クーポン, スタッフ, メニュー, フォトギャラリー, etc. — クーポン is the best-understood so far, see `references/coupon-editing.md`), the exact find/replace text or change, and whether currently-unpublished/archived items are in scope alongside live ones.
2. **Find every match before editing anything.** Prefer reading the whole listing page's text in one shot (e.g. a page-text extraction tool) over scrolling and screenshotting row by row — listings can run 30+ rows including old unpublished drafts, and eyeballing screenshots misses matches or costs many extra round-trips.
3. **Show the user the full match list and wait for approval.** This is where mistaken matches or scope surprises get caught cheaply, before any edit is made.
4. **Edit and save (登録) every approved item in one pass.** No need to re-confirm per item — the user's approval of the list already covers each individual save.
5. **Stop before publishing.** Ask explicitly, in that specific conversation, before clicking the 反映/publish button — see rule 2 above.
6. **Ask for the usage-quota screenshot again, right after finishing** (unless skipped in step 0), and compute the before/after delta.
7. **Log the work** — see Logging below.

## Multi-store account

The headquarters account's salon list lives at `salonboard.com/CNC/groupTop/`. Search that list for the target salon's exact name to jump into its SalonBoard without a separate login — the headquarters login covers every salon underneath it.

## Section-specific details

Detailed, field-level notes (exact click paths, character limits, quirks of specific tools like unstable element references after navigation) live in `references/`, one file per SalonBoard section, so this file stays short:

- `references/coupon-editing.md` — クーポン (coupon) tab: the only section mapped out so far.

If a task touches a section without a reference file yet (スタッフ, メニュー, フォトギャラリー, こだわり, 特集, ブログ, 口コミ), work it out live, then **write a new reference file capturing what you learned** (structure, gotchas, field names/limits) so the next task in that section skips the rediscovery. Follow the same shape as `coupon-editing.md`.

## Logging

The user wants work time, token consumption, and plan-quota impact tracked for every task, for 工数 (labor-hours/cost) visibility. After finishing (or meaningfully progressing on) any task under this skill, append one row to `hpb_work_log.csv` in the current working directory (create it with a header row if it doesn't exist yet) with columns:

`date,salon_name,salon_id,task,items_changed,published,session_start,session_end,tokens_effective,usage_session_pct_delta,usage_weekly_pct_delta,notes`

- **Time**: use the actual start/end timestamps of *this task* (the user's kick-off message → your completion report), not the whole session's `createdAt`/`lastActivityAt` — a session can span multiple tasks or long gaps where the user stepped away, which inflates whole-session figures badly (confirmed: one gap was over 11 hours). See `references/token-usage-logging.md` for how to find these bounds from the transcript.
- **Tokens**: `tokens_effective` — this task's own effective-token total, computed only from assistant turns whose timestamp falls inside that same start/end window (plus any subagent transcripts spawned for the task, in full). See `references/token-usage-logging.md` for the exact method (weights cache reads/writes/output differently — same approach the `explain-usage` skill uses).
- **Plan quota**: `usage_session_pct_delta` / `usage_weekly_pct_delta` — from the before/after usage screenshots (Standard workflow steps 0 and 6). See `references/usage-quota-tracking.md` for what to read and how to compute the delta, including the caveats about concurrent tasks and reset timing.

Do this proactively, without being asked each time — the user wants all of these figures computed and logged as a standard part of finishing any task here.

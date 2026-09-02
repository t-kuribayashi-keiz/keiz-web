---
name: hpb-salonboard-update
description: Use this skill whenever the user asks to update, edit, add, remove, or bulk-change content on SalonBoard (salonboard.com) for one or more of their HotPepper Beauty salons — e.g. "update the coupon text for [salon]", "change 9月末まで to 10月末まで on these stores", "非掲載にして", "反映して", "この店舗のクーポンを直して", or any recurring SalonBoard maintenance task across the ~150 salons the user's company operates. Also trigger on mentions of "SalonBoard", "掲載管理", "クーポン掲載情報", "反映する", or the salonboard.com admin backend for a salon — even if the user doesn't name this skill explicitly. Do NOT trigger for simply browsing/reading the public beauty.hotpepper.jp listing pages with no edit intent.
---

# HPB SalonBoard Update

Operational playbook for editing content on SalonBoard (salonboard.com), the admin backend behind the user's HotPepper Beauty salon listings. The user's company runs ~150 seikotsuin (chiropractic) salons through one headquarters (本部) SalonBoard account, and wants routine SalonBoard maintenance — coupon wording rollovers, content tweaks, etc. — delegated here instead of being redone from scratch each time.

## Non-negotiable rules

1. **Never type the SalonBoard password.** Logging in is the one step that always stays with the user — have them log into SalonBoard in their real Chrome (via the `mcp__claude-in-chrome__*` MCP tools, **not** the sandboxed `mcp__Claude_Browser__*` tools, since only the real Chrome carries their session) before any automation starts. If no tab is logged in yet, ask them to log in and confirm rather than attempting it yourself. A Chrome that isn't logged in returns `ユーザエラー / 認証エラーです。ログインしなおしてください。` at `CNC/groupTop/` — that's the signal to hand it back to the user, not to try logging in.
2. **Draft-saving and publishing are two separate decisions — treat them that way.** SalonBoard's coupon editor (and likely other tabs) only stages a change when you click 登録; a banner then says the change is *not yet live* until someone clicks a separate "◯◯情報を反映する" button (found on the relevant 掲載管理TOP page). The user has explicitly said they want to review the draft state before anything goes live. So: batch-editing/saving many items under one approval is fine, but **always stop and ask again, freshly, before clicking any 反映/publish button** — never fold that into the earlier "please make these edits" approval, no matter how routine the batch felt.
3. **salonboard.com is the only editable surface.** beauty.hotpepper.jp is the public, read-only consumer-facing site — never mistake it for the admin backend, and never attempt to "log in" or edit there.

## Before any browser action

- **Load the MCP tool schemas first.** `mcp__claude-in-chrome__*` tools are deferred in this environment — batch every tool you expect to need into **one** `ToolSearch` call (`select:` accepts a comma-separated list). Loading them one at a time wastes a round-trip each.
- **Pick the right Chrome when several are connected.** `list_connected_browsers` can return more than one, and until one is selected *every* browser call — including `tabs_context_mcp` — fails. Only one of them is likely to hold the 本部 SalonBoard session, so never guess: put every browser in front of the user with `AskUserQuestion`, then `select_browser` with the deviceId they choose. Confirm the choice is actually logged in by loading `CNC/groupTop/` before starting work.
  - **If you are running as the `salonboard-operator` subagent, you cannot do this** — `AskUserQuestion` is unavailable inside subagents (`No such tool available`, confirmed 2026-09-02). Either the caller hands you a deviceId, or exactly one browser is connected; otherwise stop and return the candidate list to the caller. Do **not** try each browser in turn until one works.
- **`tabs_context_mcp` does not work as the first item of a `browser_batch`.** Inside a batch, `createIfEmpty: true` is ignored and the batch fails with `No tab available`. Call it standalone first, then batch the rest.
- **`scroll` already returns a screenshot.** Don't follow a scroll with an explicit screenshot in the same batch — you get the same image twice and pay for both.
- **Screenshot resolution and scroll position can drift mid-session** — the same tab returned 1568×726 at one point and 958×888 later with no explicit resize (confirmed 2026-09-02). Coordinates computed from an earlier screenshot can miss once this happens. Always click against the *most recent* screenshot, never a cached one from a few turns back. If a screenshot comes back entirely blank, that almost always means the scroll position has gone past the end of the content into empty page background, not that the page failed to load — scroll back (up, or to a known anchor via `find` + `scroll_to`) and re-screenshot rather than guessing coordinates blind.

## Read-only tasks

Steps 0, 6 and the CSV row below exist to cost out *work*. For a purely read-only task (listing coupons, checking what's currently live, answering a question about a salon's listing) skip step 0/6 and skip the `hpb_work_log.csv` row — the overhead outweighs the value. Everything else in the workflow still applies, and the moment the task turns into an edit, the full workflow is back on.

## Standard workflow

0. **Ask for a usage-quota screenshot before starting.** The user wants to know each task's real cost against their Claude plan limits, which a token count alone can't show (they run several things concurrently). Ask them to send a screenshot of Settings → 使用量 (Usage) before you begin — see `references/usage-quota-tracking.md` for what to read off it. Skip this only if the user explicitly says not to bother for a given task.
1. **Confirm scope before touching anything.** Nail down: which salon(s) (name is enough — see Multi-store below), which SalonBoard section (クーポン, スタッフ, メニュー, フォトギャラリー, etc. — クーポン is the best-understood so far, see `references/coupon-editing.md`), the exact find/replace text or change, and whether currently-unpublished/archived items are in scope alongside live ones.
1b. **Confirm you're in the right salon before editing.** Every SalonBoard page footer carries `<salon name>様 / <salon ID> / …` (e.g. `都賀駅前整骨院様 / H000523612`). Read it and check it against the intended salon before the first edit — with ~150 salons behind one login, editing the wrong one is the expensive mistake.
2. **Find every match before editing anything.** Prefer reading the whole listing page's text in one shot (e.g. a page-text extraction tool) over scrolling and screenshotting row by row — listings can run 30+ rows including old unpublished drafts, and eyeballing screenshots misses matches or costs many extra round-trips. **But page text alone cannot tell you what is live.** The 順番 (order) number and the 非掲載にする / 掲載にする buttons are images, so they never appear in extracted text — a coupon list comes back as one flat run of rows with no visible boundary between the live block and the unpublished block. Use page text for *text matching*, then a screenshot pass for the *live/unpublished split*. `read_page` is not a substitute: on a 38-row coupon list it returned only 6 of the order textboxes and none of the row buttons.
3. **Show the user the full match list and wait for approval.** This is where mistaken matches or scope surprises get caught cheaply, before any edit is made.
4. **Edit and save (登録) every approved item in one pass.** No need to re-confirm per item — the user's approval of the list already covers each individual save.
5. **Stop before publishing.** Ask explicitly, in that specific conversation, before clicking the 反映/publish button — see rule 2 above.
6. **Ask for the usage-quota screenshot again, right after finishing** (unless skipped in step 0), and compute the before/after delta.
7. **Log the work** — see Logging below.

## Multi-store account

The headquarters account's salon list lives at `salonboard.com/CNC/groupTop/`. Search that list for the target salon's exact name to jump into its SalonBoard without a separate login — the headquarters login covers every salon underneath it. As of 2026-09-02 the list holds ~160 salons; `get_page_text` on that page returns the whole `salon ID + name` table in one call, which is the cheapest way to resolve a name to an ID.

**The salon-name links are `javascript:void(0);` and clicking them by element ref silently does nothing** — the tool returns `Clicked on element ref_N` and the page stays on `CNC/groupTop/`. Click them by screenshot coordinate instead. More generally: a click that reports success is not proof of navigation, so **verify the resulting URL** (`tabs_context_mcp` or a screenshot) after any click that is supposed to move you, rather than assuming it landed.

Once inside a salon, the section URLs below can be reached by direct `navigate` — the salon context is held in the session, so there's no need to re-click through the nav each time.

## Section-specific details

Section URLs under `https://salonboard.com/`, confirmed 2026-09-02 — all reachable by direct `navigate` once inside a salon:

| Section | URL |
|---|---|
| **反映 (publish) — 掲載管理TOP** | `CNK/reflect/reflectTop` |
| サロン | `CNK/draft/salonEdit` |
| スタッフ | `CNK/draft/staffList` |
| メニュー | `CNK/draft/menuEdit` |
| クーポン | `CNK/draft/couponList` |
| フォトギャラリー | `CNK/draft/photoGalleryEdit` |
| こだわり | `CNK/draft/kodawariList` |
| 特集 | `CNK/draft/specialList` |
| ブログ | `KLP/blog/blogList` |
| 口コミ | `KLP/review/reviewList` |

`CNK/reflect/reflectTop` is the page that actually publishes staged changes — **never navigate there casually**, and never click its 反映 buttons without the fresh, explicit approval required by rule 2.

Detailed, field-level notes (exact click paths, character limits, quirks of specific tools like unstable element references after navigation) live in `references/`, one file per SalonBoard section, so this file stays short:

- `references/coupon-editing.md` — クーポン (coupon) tab: the only section mapped out so far.

If a task touches a section without a reference file yet (スタッフ, メニュー, フォトギャラリー, こだわり, 特集, ブログ, 口コミ), work it out live, then **write a new reference file capturing what you learned** (structure, gotchas, field names/limits) so the next task in that section skips the rediscovery. Follow the same shape as `coupon-editing.md`.

## Continuous learning

The rule above isn't limited to brand-new sections. **At the end of every task under this skill, check whether anything happened that isn't already written down here or in `references/`** — an unexpected error message, a UI quirk, a click that reported success but did nothing, a form field or modal that behaved differently than expected, a tool limitation you worked around. If so, append it before finishing:

- Environment/tooling issues (browser automation quirks, MCP tool limits) → a bullet under **Before any browser action** above.
- SalonBoard-specific behavior (a section's form fields, click paths, error messages) → the matching `references/*.md` file, or a new one if the section doesn't have one yet.

Small, incremental notes are fine — don't wait for something dramatic. The point is that the next task (yours or another session's) starts from what this one learned instead of rediscovering it from scratch. `references/coupon-editing.md` is the working example of this — keep extending it the same way.

## Logging

The user wants work time, token consumption, and plan-quota impact tracked for every task, for 工数 (labor-hours/cost) visibility. After finishing (or meaningfully progressing on) any task under this skill, append one row to `hpb_work_log.csv` in the current working directory (create it with a header row if it doesn't exist yet) with columns:

`date,salon_name,salon_id,task,items_changed,published,session_start,session_end,tokens_effective,usage_session_pct_delta,usage_weekly_pct_delta,notes`

- **Time**: use the actual start/end timestamps of *this task* (the user's kick-off message → your completion report), not the whole session's `createdAt`/`lastActivityAt` — a session can span multiple tasks or long gaps where the user stepped away, which inflates whole-session figures badly (confirmed: one gap was over 11 hours). See `references/token-usage-logging.md` for how to find these bounds from the transcript.
- **Tokens**: `tokens_effective` — this task's own effective-token total, computed only from assistant turns whose timestamp falls inside that same start/end window (plus any subagent transcripts spawned for the task, in full). See `references/token-usage-logging.md` for the exact method (weights cache reads/writes/output differently — same approach the `explain-usage` skill uses).
- **Plan quota**: `usage_session_pct_delta` / `usage_weekly_pct_delta` — from the before/after usage screenshots (Standard workflow steps 0 and 6). See `references/usage-quota-tracking.md` for what to read and how to compute the delta, including the caveats about concurrent tasks and reset timing.

Do this proactively, without being asked each time — the user wants all of these figures computed and logged as a standard part of finishing any task here. The one exception is a purely read-only task — see **Read-only tasks** above.

---
name: hpb-salonboard-update
description: Use this skill whenever the user asks to update, edit, add, remove, or bulk-change content on SalonBoard (salonboard.com) for one or more of their HotPepper Beauty salons — e.g. "update the coupon text for [salon]", "change 9月末まで to 10月末まで on these stores", "非掲載にして", "反映して", "この店舗のクーポンを直して", or any recurring SalonBoard maintenance task across the ~150 salons the user's company operates. Also trigger on mentions of "SalonBoard", "掲載管理", "クーポン掲載情報", "反映する", or the salonboard.com admin backend for a salon — even if the user doesn't name this skill explicitly. Do NOT trigger for simply browsing/reading the public beauty.hotpepper.jp listing pages with no edit intent.
---

# HPB SalonBoard Update

Operational playbook for editing content on SalonBoard (salonboard.com), the admin backend behind the user's HotPepper Beauty salon listings. The user's company runs ~150 seikotsuin (chiropractic) salons through one headquarters (本部) SalonBoard account, and wants routine SalonBoard maintenance — coupon wording rollovers, content tweaks, etc. — delegated here instead of being redone from scratch each time.

## Non-negotiable rules

1. **Never type the SalonBoard password.** Logging in is the one step that always stays with the user — have them log into SalonBoard in their real Chrome (via the `mcp__claude-in-chrome__*` MCP tools, **not** the sandboxed `mcp__Claude_Browser__*` tools, since only the real Chrome carries their session) before any automation starts. If no tab is logged in yet, ask them to log in and confirm rather than attempting it yourself. A Chrome that isn't logged in returns `ユーザエラー / 認証エラーです。ログインしなおしてください。` at `CNC/groupTop/` — that's the signal to hand it back to the user, not to try logging in.
   - **One narrow, explicit exception (2026-09-03)**: `scripts/salonboard_root_cause.py` (see `hpb-reservation-slot-check` skill) does automate login, headless, via `SALONBOARD_USER_ID`/`SALONBOARD_PASSWORD` GitHub Actions secrets — but only for that one unattended batch-classification job, only after the user explicitly approved storing login credentials for it, and only after a manual `--mode verify-login` confirms it actually works. This rule still applies as-is to every *interactive* SalonBoard task (this skill, the `salonboard-operator` agent) — don't generalize the exception.
2. **Draft-saving and publishing are two separate decisions — treat them that way.** SalonBoard's coupon editor (and likely other tabs) only stages a change when you click 登録; a banner then says the change is *not yet live* until someone clicks a separate "◯◯情報を反映する" button (found on the relevant 掲載管理TOP page). The user has explicitly said they want to review the draft state before anything goes live. So: batch-editing/saving many items under one approval is fine, but **always stop and ask again, freshly, before clicking any 反映/publish button** — never fold that into the earlier "please make these edits" approval, no matter how routine the batch felt.
3. **salonboard.com is the only editable surface.** beauty.hotpepper.jp is the public, read-only consumer-facing site — never mistake it for the admin backend, and never attempt to "log in" or edit there.

## Before any browser action

- **Load the MCP tool schemas first.** `mcp__claude-in-chrome__*` tools are deferred in this environment — batch every tool you expect to need into **one** `ToolSearch` call (`select:` accepts a comma-separated list). Loading them one at a time wastes a round-trip each.
- **Pick the right Chrome when several are connected.** `list_connected_browsers` can return more than one, and until one is selected *every* browser call — including `tabs_context_mcp` — fails. Only one of them is likely to hold the 本部 SalonBoard session, so never guess: put every browser in front of the user with `AskUserQuestion`, then `select_browser` with the deviceId they choose. Confirm the choice is actually logged in by loading `CNC/groupTop/` before starting work.
  - **The display name (`list_connected_browsers`' `name` field, or what a user calls "Browser 1") is not stable and does not necessarily match what the caller/user meant by that name** — confirmed 2026-09-11, a browser the parent session called "Browser 1" showed up as "Browser 2" in the child's own `list_connected_browsers` (the deviceId was identical, so it was the same physical browser). **Only ever match by deviceId, never by display name**, and when handing a deviceId between sessions/callers, pass the deviceId string itself, not just a name.
  - **If you are running as the `salonboard-operator` subagent, you cannot do this** — `AskUserQuestion` is unavailable inside subagents (`No such tool available`, confirmed 2026-09-02). Either the caller hands you a deviceId, or exactly one browser is connected; otherwise stop and return the candidate list to the caller. Do **not** try each browser in turn until one works.
- **`tabs_context_mcp` does not work as the first item of a `browser_batch`.** Inside a batch, `createIfEmpty: true` is ignored and the batch fails with `No tab available`. Call it standalone first, then batch the rest.
- **`scroll` already returns a screenshot.** Don't follow a scroll with an explicit screenshot in the same batch — you get the same image twice and pay for both.
- **Screenshot resolution and scroll position can drift mid-session** — the same tab returned 1568×726 at one point and 958×888 later with no explicit resize (confirmed 2026-09-02). Coordinates computed from an earlier screenshot can miss once this happens. Always click against the *most recent* screenshot, never a cached one from a few turns back. If a screenshot comes back entirely blank, that almost always means the scroll position has gone past the end of the content into empty page background, not that the page failed to load — scroll back (up, or to a known anchor via `find` + `scroll_to`) and re-screenshot rather than guessing coordinates blind.
- **Don't reuse a numeric scroll amount across different salons/rows in `CNC/groupTop/`'s list.** The list is long (150+ rows) and small drifts in prior scrolling carry over; a scroll amount that correctly landed on one salon's row can land on an unrelated neighboring salon for the next one (confirmed 2026-09-10: an unrelated salon got clicked this way, caught only because it was a read-only step). Use `find` for the target name, `scroll_to` its ref, then **screenshot and visually confirm the row before clicking** — never click from a remembered scroll position.
- **`CNC/groupTop/` can intermittently hang** — `get_page_text`/`find`/`scroll`/`screenshot` all start failing with "Page still loading" / "Script injection timed out" after several operations on the same tab (cause unconfirmed, possibly a news-feed widget). `wait` doesn't reliably clear it. Close the tab and open a fresh one (`tabs_create_mcp` or `navigate` with `createIfEmpty`) rather than fighting the same tab.
- **The page footer (`<salon name>様 / <salon ID> / …`) can silently show a *different* salon than the one you just navigated to** — confirmed 2026-09-10: after correctly landing on one salon's TOP page, clicking a nav tab (e.g. 掲載管理→サロン) sometimes lands on the right URL but with a *different, previously-viewed* salon's data. Re-check the footer after **every** navigation that's supposed to stay in the same salon, not just once when you first enter it. If it doesn't match, don't try to recover in place — go back to `CNC/groupTop/` and re-enter.
- **A `find` query like "the 5th dropdown/checkbox" against a form with several identically-labeled controls (e.g. multiple "未選択" genre dropdowns) can return the wrong one's ref** — confirmed 2026-09-10, a value meant for slot 5 landed in slot 6. For this kind of list-of-identical-controls form, use `read_page` (`filter: interactive`) and count occurrence order yourself instead of trusting `find`'s natural-language match, and always re-screenshot/re-read after `form_input` to confirm the value landed in the intended slot.
- **A button's visual grey-out (disabled-looking) is not reflected in `read_page`'s `disabled` attribute** — confirmed 2026-09-10 on 掲載管理TOP's 反映申請 buttons, both enabled and disabled-looking ones reported no `disabled` attribute. Confirm clickability by the button's on-screen color (screenshot/`zoom`), not by reading DOM attributes.
- **A transient `ユーザエラー: サロンが選択されていません` (or `ユーザまたは、お店が切り替わっているため…`) can appear on an otherwise-correct save/navigate**, cause unconfirmed. Nothing was lost when this happened — re-enter via `CNC/groupTop/`, confirm via the footer that you're back in the right salon, and redo the edit; it succeeds on retry.

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

**The salon-name links are `javascript:void(0);`, handled by delegated JS event listeners.** Element-ref clicks and screenshot-coordinate clicks (`computer` tool) are both synthetic mouse events sent via CDP, and **both were observed to stop navigating partway through a multi-salon task** (2026-09-11: worked for the first 1–4 salons, then silently stopped firing the link's handler for every remaining salon, no matter the click method, new tabs, or re-selecting the browser). **The one method that never failed: `javascript_tool` calling `element.click()` directly on the matched `<a>`**, e.g.:

```js
Array.from(document.querySelectorAll('a'))
  .find(a => a.textContent.trim() === '柏南口整骨院')
  .click();
```

Use exact-text match (`.trim() === 店舗名`), not substring, so you don't hit a different salon whose name contains the target as a substring. Prefer this over coordinate/ref clicks for every `CNC/groupTop/` salon switch. (`salonboard-operator` needs `mcp__claude-in-chrome__javascript_tool` in its `tools:` list for this — added 2026-09-11.)

A click that reports success is still not proof of navigation either way — **verify the resulting URL** (`tabs_context_mcp` or a screenshot, or the page footer's salon name) after any click that is supposed to move you.

**If clicking stops working across several salons in a row (not just one flaky click), stop retrying coordinates/refs and suspect a real concurrent session first**, not a UI quirk: check `hpb_work_log.d/` for a recent file from another session touching the same salon/account, and re-run `list_connected_browsers` to see if the connected-browser count or deviceIds changed since you started. Two different sessions hitting the same SalonBoard account/browser at once has been confirmed (2026-09-11) to cause real symptoms — tabs freezing for 30–45s, `get_page_text` timing out, even a forced session timeout — not just click failures. Retrying harder does not fix this; identifying the collision and waiting it out (or asking the user which session should yield) does.

Once inside a salon, the section URLs below can be reached by direct `navigate` — the salon context is held in the session, so there's no need to re-click through the nav each time.

## 診療時間・定休日を聞かれたとき

`data/clinics.json` には **診療時間も定休日も入っていません**(2026-09-04に全204件のキーを数えて確認)。取り込み元スプレッドシートのファイル名が「診療時間」(ID `1Pd2S6P9sAVMTk8FBqPJHKwihhggPgmvQk6pEFkgwHl8`)なので「渡してあるはず」と食い違いやすいのですが、実際に取り込んだのは院名・住所・電話・URL・メール類だけです。

なので「定休日を扱う仕組みがリポジトリに無い」という回答自体は正しい。ただし**マスタ側にはある**ので、そこで話を止めないこと: 上記スプレッドシートのブランド別タブ、および同スプレッドシート内「AIチェック用」シートの定休日列(「木曜・日曜・第4木曜」形式)を見る。取り込み作業は `docs/backlog.md` で追跡中で、それが済むまで定休日を前提にした判定は書かない。

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

- `references/coupon-editing.md` — クーポン (coupon) tab.
- `references/menu-and-reflect-management.md` — メニュー掲載情報の無変更再登録、および掲載管理TOP(`reflectTop`)の反映申請ボタンの束ね方・有効/無効判定。

If a task touches a section without a reference file yet (スタッフ, メニュー, フォトギャラリー, こだわり, 特集, ブログ, 口コミ), work it out live, then **write a new reference file capturing what you learned** (structure, gotchas, field names/limits) so the next task in that section skips the rediscovery. Follow the same shape as `coupon-editing.md`.

## Continuous learning

The rule above isn't limited to brand-new sections. **At the end of every task under this skill, check whether anything happened that isn't already written down here or in `references/`** — an unexpected error message, a UI quirk, a click that reported success but did nothing, a form field or modal that behaved differently than expected, a tool limitation you worked around. If so, append it before finishing:

- Environment/tooling issues (browser automation quirks, MCP tool limits) → a bullet under **Before any browser action** above.
- SalonBoard-specific behavior (a section's form fields, click paths, error messages) → the matching `references/*.md` file, or a new one if the section doesn't have one yet.

Small, incremental notes are fine — don't wait for something dramatic. The point is that the next task (yours or another session's) starts from what this one learned instead of rediscovering it from scratch. `references/coupon-editing.md` is the working example of this — keep extending it the same way.

**If any other session might be running this skill right now, do not edit `SKILL.md` or `references/*.md` at all.** Editing a shared file is read → modify → write, so a concurrent write between your read and your write silently drops one side's note. Instead drop a new file into `learnings/` — different paths cannot collide, whatever the timing — and let a later single-writer pass merge it. The user routinely runs several of these at once, so treat this as the default rather than the exception. See `references/concurrent-sessions.md` for the file naming and the merge procedure.

**Read `learnings/` before starting a task.** Unmerged notes are already valid knowledge; the folder is part of this skill, not a staging area to skip.

## Logging

The user wants work time, token consumption, and plan-quota impact tracked for every task, for 工数 (labor-hours/cost) visibility. After finishing (or meaningfully progressing on) any task under this skill, record one row with the columns below. **If any other session might be running this skill, write the row as its own file under `hpb_work_log.d/` instead of appending to `hpb_work_log.csv`** (one data row, no header — see `references/concurrent-sessions.md`); two sessions appending to one CSV can drop a row. Only when you are certain you are the only session running, append directly to `hpb_work_log.csv` in the current working directory (create it with a header row if it doesn't exist yet). Columns:

`date,salon_name,salon_id,task,items_changed,published,session_start,session_end,tokens_effective,usage_session_pct_delta,usage_weekly_pct_delta,notes`

- **Time**: use the actual start/end timestamps of *this task* (the user's kick-off message → your completion report), not the whole session's `createdAt`/`lastActivityAt` — a session can span multiple tasks or long gaps where the user stepped away, which inflates whole-session figures badly (confirmed: one gap was over 11 hours). See `references/token-usage-logging.md` for how to find these bounds from the transcript.
- **Tokens**: `tokens_effective` — this task's own effective-token total, computed only from assistant turns whose timestamp falls inside that same start/end window (plus any subagent transcripts spawned for the task, in full). See `references/token-usage-logging.md` for the exact method (weights cache reads/writes/output differently — same approach the `explain-usage` skill uses).
- **Plan quota**: `usage_session_pct_delta` / `usage_weekly_pct_delta` — from the before/after usage screenshots (Standard workflow steps 0 and 6). See `references/usage-quota-tracking.md` for what to read and how to compute the delta, including the caveats about concurrent tasks and reset timing.

Also: a session running alongside others **must not run git commands** — no `add`, no `commit`, no branch switching. Sessions in one clone share an index and a working tree, so `git add -A` from one sweeps in another's half-finished edits, and a branch switch pulls the tree out from under everyone. Create files; let the consolidation pass commit them together.

Do this proactively, without being asked each time — the user wants all of these figures computed and logged as a standard part of finishing any task here. The one exception is a purely read-only task — see **Read-only tasks** above.

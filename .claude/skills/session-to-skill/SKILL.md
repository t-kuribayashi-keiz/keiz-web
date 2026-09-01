---
name: session-to-skill
description: Use this skill whenever the user asks to turn the current conversation's workflow into a reusable skill — phrases like "これをスキルにして", "このセッションをスキル化して", "他のPCでも使えるようにして", "共通スキルにして", "turn this into a skill", "make this repeatable", "package this workflow so I don't have to re-explain it next time". Also trigger proactively when a session has clearly nailed down a repeatable multi-step procedure (browser automation, a data pipeline, a recurring report) and the user signals they'll want to do this again. This is specifically for PERSONAL, user-level skills the user wants available across their own machines — not org-wide sharing.
---

# Session → Personal Skill

Turns a workflow this conversation just worked out — the tool calls, the sequence, the gotchas discovered, the corrections the user made along the way — into a personal skill the user can reuse, and carry to their other PCs. This is the meta-version of what skill-creator does: skill-creator is the general-purpose tool, this skill is *how this user specifically wants it applied* (storage location, eval approach, and packaging all differ from skill-creator's defaults because of constraints discovered the first time through).

## Ground rules specific to this user

1. **Always personal / user-level, never project-level or org-shared** unless the user explicitly says otherwise for a given skill. Store at `~/.claude/skills/<skill-name>/` (on Windows: `C:\Users\<user>\.claude\skills\<skill-name>\`), not a project's `.claude/skills/`.
2. **Extract from the conversation first, interview second.** The whole point is that the workflow already happened in this session — re-read it for the tools used, the order of steps, anything the user corrected or clarified, and input/output shapes actually observed. Only ask the user to fill genuine gaps (ambiguous scope, a rule that wasn't tested, a name/description choice), not things already visible in the transcript.
3. **Skip skill-creator's automated eval/benchmark loop by default.** Most of this user's workflows involve live external systems (SalonBoard, other production admin panels, real files, real accounts) — spawning subagents to run "test" edits against production is not safe or meaningful. Default to: draft the skill, show it to the user, let them sanity-check by using it for real next time. Only run the full eval loop if the workflow is a pure content-generation task with no external side effects (e.g. always producing a report/spreadsheet/chart from given inputs) where synthetic test runs are actually safe and informative — ask if unsure.
4. **Split volatile/technical detail into `references/`, keep SKILL.md as the stable procedure.** UI click-paths, character limits, element-finding quirks, API payloads — anything likely to need updating as the target system changes or as new sections/variants get discovered — goes in a reference file per sub-area (e.g. `references/coupon-editing.md` for one screen of a multi-screen admin tool). SKILL.md holds the parts that don't change: when to trigger, non-negotiable safety rules, and the high-level step sequence.
5. **Surface non-negotiable safety rules prominently**, near the top of SKILL.md, if the source conversation established any — e.g. "never enter this password," "never click publish without fresh confirmation," "never delete without listing first." These are usually the single most important thing to carry forward; don't bury them in a reference file.
6. **If the workflow has a natural unit of recurring cost/effort the user cares about** (money, time, item count, token consumption, plan-quota usage), carry forward whatever logging convention was set up during the conversation (e.g. an append-only CSV in the working directory) as part of the skill's own instructions, so future invocations keep logging automatically without being asked again. The user has an established pattern worth reusing rather than re-deriving:
   - **Time**: bound to the specific task's own start/end message timestamps (the kick-off message → the completion report), never a whole session's `createdAt`/`lastActivityAt` — sessions commonly cover multiple tasks or long gaps where the user stepped away (one observed gap was 11+ hours), which badly inflates a naive session-level figure.
   - **Tokens**: an "effective tokens" figure computed from the session's own transcript JSONL, counting only assistant turns whose timestamp falls in that same task-bounded window (weighting cache reads at ~0.1x, cache writes at ~2x, and output at ~5x a regular input token — the same method the `explain-usage` skill uses). See `hpb-salonboard-update/references/token-usage-logging.md` for the exact PowerShell computation (Python isn't usable on this machine).
   - **Plan-quota impact**: raw tokens don't map to "how much of my Claude plan limit did this cost," especially for a user running multiple concurrent tasks/sessions — a token count from one session can't be attributed against a shared, account-wide quota. The workaround: ask the user to send a screenshot of Settings → 使用量 (Usage) right before and right after the task, read the session-window % and weekly-all-models % off it, and log the delta. See `hpb-salonboard-update/references/usage-quota-tracking.md` for exactly what to read and its caveats (concurrent usage during the window still isn't fully isolated, and a mid-task reset breaks the subtraction).

## Procedure

0. **If this session has no relevant history to extract from** (e.g. it was just opened specifically to run this skill), don't just ask the user to re-explain everything from scratch. Ask which existing session holds the workflow (by its title, as seen in the session list), then:
   - `mcp__ccd_session_mgmt__list_sessions` to find its `sessionId` from the title.
   - `mcp__ccd_session_mgmt__list_events` on that `sessionId` to pull its transcript — this works from a completely different session, no need to open or resume the original one.
   - Proceed with step 1 below using that pulled transcript instead of "this conversation." This is the standard workaround for the session-skill-visibility bug documented below — don't treat it as an edge case, it'll come up constantly since this bug means the skill can basically never run inside the same session whose workflow it's extracting.
1. Skim back through the conversation (or the pulled transcript from step 0) and draft: what should trigger this skill, what are the non-negotiable rules, what's the step sequence, what technical detail belongs in a reference file.
2. Present the draft skill name + trigger description + rule list to the user in the chat (not just written to disk) for a quick sanity check — this is cheap and catches scope misses before they're baked into a file used repeatedly.
3. Write `SKILL.md` (and any `references/*.md`) to `~/.claude/skills/<skill-name>/`.
4. Tell the user the skill is ready — but see the important caveat below about *which* session can actually see it.

## Known bug: existing sessions don't see newly-created skills

Confirmed by testing (2026-09-01): a skill written to `~/.claude/skills/<name>/` is picked up immediately by **brand-new** sessions, but a session that was already open/created before the skill file existed will **not** see it — not even after fully restarting the Claude app. Skill availability appears to be fixed at session creation, not live-rescanned.

Practical fallout:
- **Never tell the user "go back to your other session and try it now"** — that will fail even right after the skill is created. The only session guaranteed to see a brand-new skill is a session started after the file was written.
- This is *why* step 0 above exists: since the session containing the workflow you're extracting from is (definitionally) older than the skill you're about to create, that exact session can never use the skill on itself anyway. Don't treat this as a contradiction or a reason to hesitate — extract from the old session's transcript, but expect to *use* the finished skill from a different (new, or already-post-creation) session.
- If the user reports "the skill isn't showing up," the fix is "open a new session," not troubleshooting the skill file itself — check that first before assuming the SKILL.md is broken.

## Portability to other devices (what actually works, learned the hard way)

## Portability to other devices (what actually works, learned the hard way)

- **Phone / tablet access:** No extra step needed. Claude Code's Remote Control connects another device's conversation to the session already running on this PC, and that session already has the skill locally — see the user's reference notes on Remote Control if unsure of setup.
- **A genuinely different PC:** The one-click "Save skill" install from a file card does **not** work in this Cowork/Claude Code interface (confirmed: sending a `.skill` file here just renders as an unpreviewable binary, no install button appears) — don't recommend it as if it does. The reliable path is: hand the user the skill's files (`SKILL.md` and everything under `references/`) and have them copy the whole folder into `~/.claude/skills/<skill-name>/` on the other PC. That PC also needs whatever local tool access the skill depends on (e.g. the Chrome extension + a fresh login, if it's a browser-automation skill) — the skill's instructions travel, but a live login session never does.
- **Packaging for handoff:** This machine's `python` command only resolves to a non-functional Windows Store stub (confirmed — running any python script here fails), so skill-creator's own `package_skill.py` won't run. If a zipped `.skill` bundle is wanted anyway (e.g. to send as one file instead of two), build it with PowerShell instead — see `references/packaging-without-python.md` for the exact command. It's usually simpler to just hand over the raw `SKILL.md`/`references` files for the user to copy manually.

## After creating the skill

Ask if the user wants to immediately try it for real (best sanity check available, given eval loops are skipped by default), and mention they can ask for this same session-to-skill treatment on any other session whose workflow they want to keep.

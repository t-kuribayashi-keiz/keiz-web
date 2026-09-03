# Running several sessions at once without losing what they learn

The user runs many SalonBoard sessions in parallel, and wants each one's learning to
accumulate rather than overwrite the others'. Two things this skill writes are shared, and
both break under concurrency:

1. `SKILL.md` and `references/*.md` — the **Continuous learning** step edits them
2. `hpb_work_log.csv` — the **Logging** step appends a row

## What actually goes wrong

**Same-file edits lose one side.** Editing a file is read → modify → write. If another
session writes between your read and your write, your write is built on stale content and
its change disappears. Nothing errors, the file looks fine, and the lost note is only
noticed when someone rediscovers the same quirk weeks later. Even when the tooling catches
the stale read and makes you retry, that is friction to design away, not to rely on.

**Appends lose rows the same way** when the append is done by rewriting the file.

**A shared git clone is worse than a shared file.** Sessions in one working directory share
one index and one branch:

- `git add -A` from session A sweeps in session B's half-finished edits, so B's incomplete
  work ships inside A's commit
- `index.lock` collides when two sessions commit at the same moment
- one session switching branches pulls the working tree out from under every other session

**Contradictory learning is a separate problem.** Two sessions can each discover something
true-for-them but mutually inconsistent (two click paths for the same screen, one of which
was an A/B variant). Appending both into `SKILL.md` makes the skill worse, and no amount of
locking fixes that — it needs someone to reconcile them.

## The rule: one writer per file

**A session running concurrently with others never edits a shared file. It creates a new
one.** Two sessions writing different paths cannot collide, whatever the timing.

### Learning → `learnings/`

Instead of editing `SKILL.md` or `references/*.md` at the end of a task, drop a new file:

```
.claude/skills/hpb-salonboard-update/learnings/<YYYY-MM-DDTHHmm>_<session-id-の先頭8桁>.md
```

Get the session id from `get_session` with id `"self"` (the same call
`references/token-usage-logging.md` uses to find the transcript). One file per task, never
appended to by anyone else. Content: what happened, what was expected, what to do next
time, and which file it should eventually land in.

```markdown
# 2026-09-03 クーポン編集 / 〇〇院

- 反映先: references/coupon-editing.md
- 事象: 「登録」後に一覧が古いままで、リロードしないと反映が確認できない
- 対処: 登録後は必ず一覧を再読込してから件数を数える
- 確度: 3院で再現。ブラウザキャッシュではなさそう
```

Write **確度** honestly — "1回だけ見た" and "毎回起きる" get merged very differently.

### Work log → `hpb_work_log.d/`

Instead of appending a row to `hpb_work_log.csv`, write the row as its own file:

```
hpb_work_log.d/<YYYY-MM-DDTHHmm>_<session-id-の先頭8桁>.csv
```

One data row, no header. Same columns as `hpb_work_log.csv`. The consolidated CSV stays the
thing to read; it is just no longer written by concurrent sessions.

### Git → don't commit

A session running alongside others **does not run git commands** — no `add`, no `commit`,
no branch switching. It only creates files. Consolidation commits everything at once, from
one place, so no commit ever contains another task's half-finished work.

If a session genuinely must commit (it is the only one running), stage explicit paths.
Never `git add -A` while other sessions are working in the same clone.

## Consolidation (single writer)

Later, one session — and only one — folds the queue in:

1. Read every file in `learnings/`, grouped by which reference file it targets
2. Reconcile: drop duplicates, and where two notes disagree, keep the one with the stronger
   evidence and write down that the other was seen (a contradiction is itself information —
   it usually means the UI varies by account or by A/B variant)
3. Edit `SKILL.md` / `references/*.md` accordingly
4. Append `hpb_work_log.d/*.csv` to `hpb_work_log.csv`, sorted by date
5. Delete the consumed files and commit everything in one commit

Do this when the parallel runs are finished, not while they are in flight. There is no
deadline: a note sitting in `learnings/` is already durable and already carried forward by
whoever reads the folder.

## Why this doesn't slow the next session down

An already-open session does not pick up a freshly-edited skill anyway — skill availability
is fixed when a session starts (see `session-to-skill/SKILL.md`, "Known bug"). So writing
learning into `SKILL.md` the instant it is discovered buys nothing for the sessions running
right now, and costs the collision. Batching the merge loses nothing real.

What *does* help immediately: **a session starting a SalonBoard task should read
`learnings/` first.** The queue is part of the skill's knowledge, not a staging area to be
ignored until merged.

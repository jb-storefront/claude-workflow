---
name: dispatch-slices
description: Fan out unblocked slice issues to parallel Claude Code cloud sessions, one session per slice. Discovers or takes a parent spec issue, classifies each slice AFK or HITL, confirms once, then dispatches with `claude --cloud`. Use when the user says "/dispatch-slices", "start the next slices", "work these issues in parallel", or has just finished /to-tickets.
---

# Dispatch Slices

Turn a set of ready slice issues into a set of running cloud sessions — one isolated VM per
slice, each going issue → branch → TDD → reviewed PR on its own.

This is the fan-out step of the `/grill-with-docs` → `/to-spec` → `/to-tickets` →
**`/dispatch-slices`** → `/tdd` → `/finalize-pr` → `/merge-stack` pipeline. It runs **locally**,
in the main checkout, and does no work itself: it picks the slices, writes the prompts, and
launches. Each dispatched session runs `/start-issue` as its first act.

## Input

`$ARGUMENTS`: optionally a parent spec issue number (`60` or `#60`), and/or `--limit <n>`.

- With a parent: dispatch its unblocked children.
- Without: discover unblocked open issues across the repo and ask which to dispatch.

## 1. Pre-flight — the clone the VM will get

`--cloud` clones **the GitHub remote at your current branch**, not your working tree. Unpushed
commits and uncommitted edits do not travel. So:

- `{branch}` = `git branch --show-current`; `{default}` = `gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'`.
- If `{branch}` != `{default}` → **warn**: every slice will branch off `{branch}`, not `{default}`. Ask whether that is intended before continuing.
- `git status --porcelain` non-empty → **warn** that those changes will not reach any session.
- `git log --oneline @{u}.. 2>/dev/null` non-empty → **stop**: push first, or the sessions clone stale code.

## 2. Collect the slice set

With a parent issue: `gh issue view {parent} --json number,title,body` and pull the child
references from its body (`- [ ] #NN` task-list entries, or a `## Slices` section).

Without: `gh issue list --state open --json number,title,labels,assignees --limit 30`.

Then filter to **dispatchable** slices:

- Drop anything already assigned (`assignees` non-empty) — it is in flight.
- Drop anything with an open PR: `gh pr list --state open --json closingIssuesReferences` and exclude issues already referenced.
- Drop anything whose body declares a dependency on a slice not yet merged (`## Blocked by #NN`, `Depends on #NN`). Report these as **held**, with what they wait on.

If the set is empty, report why per issue and stop.

## 3. Classify each slice: AFK or HITL

The distinction is whether a human must *look at something running* before the PR is honest.

- **AFK** — verifiable by the test suite and the quality gates alone. The default.
- **HITL** — needs a manual smoke test: visual/layout changes, a multi-process demo flow, anything the acceptance criteria describe in terms of what a person sees.

Infer from labels (`ui`, `ux`, `demo`) and from acceptance criteria that read observationally
("the buyer sees…", "the page shows…"). When genuinely ambiguous, ask — do not guess HITL, it
costs the user an interactive step.

## 4. Present the plan and confirm once

```
/dispatch-slices — {N} slices → cloud sessions

  #61  feat/…  Wire the loyalty earn line          AFK
  #62  feat/…  Rewards balance on the cart page    HITL (manual smoke)
  #63  feat/…  Reject unregistered client_id       AFK

Held:    #64 (blocked by #61)
Skipped: #59 (assigned), #60 (parent spec)

Base:    {branch} @ {short-sha}
Action:  one cloud session per slice, running independently.
Proceed?
```

Ask once. After approval, dispatch all of them without further prompting.

## 5. Dispatch

One command per slice. Reference the parent so the session can read the spec for context.

**`claude --cloud` refuses to run without a TTY**, and a skill's Bash calls are piped, so the
bare command fails with *"--cloud requires an interactive terminal"*. Wrap each dispatch in a
pty:

**AFK slice:**

```bash
script -q /dev/null claude --cloud "/start-issue {n} — refer to the spec in issue #{parent} for context — implement it with /tdd, then run /finalize-pr."
```

**HITL slice** — the session must stop rather than self-certify:

```bash
script -q /dev/null claude --cloud "/start-issue {n} — refer to the spec in issue #{parent} for context — implement it with /tdd. When the work is complete, push the branch and STOP: tell me it needs a manual smoke test and wait. Do not run /finalize-pr yourself."
```

That is the macOS/BSD `script` spelling. On Linux the equivalent is
`script -qec "claude --cloud '…'" /dev/null`.

Capture each printed session ID.

**If a dispatch stalls on a prompt, stop and hand the commands to the user.** The first
`--cloud` run in a repo whose `.claude/settings.json` pre-approves permissions hits the
workspace-trust dialog (*"This folder pre-approves N tool permissions… Do you trust this
folder?"*). That is a security decision belonging to the human, not something to answer through
a pty. Print the remaining commands for them to paste, and say why. Once they have accepted trust
once, later dispatches run unattended.

Notes that are easy to get wrong:

- **No `--dangerously-skip-permissions`.** Cloud sessions honour the repo's committed
  `.claude/settings.json` `permissions.allow`. If a session stalls on a permission prompt, the
  fix is to widen that allowlist in the repo — a reviewable change — not to bypass the check.
- **No `--worktree`, no session names to keep unique.** Each session gets its own VM.
- **Rate limits are shared** across your whole account. Ten parallel slices consume ten slices'
  worth of quota at once; there is no separate compute charge, but there is a ceiling. With a
  large set, ask before dispatching more than ~5 at a time, or honour `--limit`.

## 6. Report

```
/dispatch-slices — {N} dispatched

  #61  session_01ABC…  AFK   https://claude.ai/code/session_01ABC…
  #62  session_01DEF…  HITL  https://claude.ai/code/session_01DEF…
  #63  session_01GHI…  AFK   https://claude.ai/code/session_01GHI…

Monitor:   /tasks  (or claude.ai/code, or the Claude mobile app)
Steer:     claude -p "…" --cloud <session-id>
Take over: claude --teleport <session-id>

HITL slices (#62) will stop and wait for your smoke test. Teleport into one to run the app
locally, then /finalize-pr from your terminal.
```

## Rules

- Dispatch only; never implement a slice in this session.
- One session per slice. Never batch two issues into one session — they would share a branch and collide in `/merge-stack`.
- Never dispatch an issue that is assigned or already has an open PR.
- One confirmation (§4), then run through the whole set.
- Do not pass `--dangerously-skip-permissions`; permissions belong in the repo's committed settings.
- Never answer a workspace-trust or permission prompt on the user's behalf, through a pty or otherwise. Hand it back.
- If a `claude --cloud` invocation fails, report it and continue with the rest — a partial fan-out is fine and re-runnable, since §2 skips slices that are now assigned.

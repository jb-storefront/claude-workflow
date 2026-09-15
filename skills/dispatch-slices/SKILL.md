---
name: dispatch-slices
description: Fan out unblocked slice issues to parallel local Claude Code sessions, one git worktree per slice. Discovers or takes a parent spec issue, classifies each slice AFK or HITL, confirms once, then dispatches with `claude --bg --worktree` and captures each background session id. Use when the user says "/dispatch-slices", "start the next slices", "work these issues in parallel", or has just finished /to-tickets.
---

# Dispatch Slices

Turn a set of ready slice issues into a set of running background sessions — one git worktree per
slice, each going issue → branch → TDD → reviewed PR on its own.

This is the fan-out step of the `/grill-with-docs` → `/to-spec` → `/to-tickets` →
**`/dispatch-slices`** → `/tdd` → `/finalize-pr` → `/merge-stack` pipeline. It runs in the **main
checkout** and does no work itself: it picks the slices, writes the prompts, and launches. Each
dispatched session runs `/start-issue` as its first act.

## Input

`$ARGUMENTS`: optionally a parent spec issue number (`60` or `#60`), and/or `--limit <n>`.

- With a parent: dispatch its unblocked children.
- Without: discover unblocked open issues across the repo and ask which to dispatch.

## 1. Pre-flight — what each worktree will start from

`--worktree` creates a new branch from the **remote default branch**, not from your working tree.
`worktree.baseRef` defaults to `"fresh"`, which resolves to `origin/HEAD` (Claude Code fetches it
when the repo has not been fetched in 24 hours). Unpushed commits and uncommitted edits do not
travel. So:

- `{default}` = `gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'`;
  `{base_sha}` = `git rev-parse --short origin/{default}` after `git fetch origin {default}`.
- `git status --porcelain` non-empty → **warn** that those changes will not reach any session.
- `git log --oneline @{u}.. 2>/dev/null` non-empty → **stop**: push first, or the sessions start
  from stale code. Your current branch is irrelevant here — every worktree starts from
  `origin/{default}` whatever you have checked out. Say so rather than warning about the branch.
- `git check-ignore -q .claude/worktrees/` — non-zero means the directory is not ignored, so every
  worktree's files will show up as untracked noise in the main checkout. **Warn once** and suggest
  adding `.claude/worktrees/` to `.gitignore`.
- If the project keeps gitignored config the slices need (`.env` and friends), a `.worktreeinclude`
  at the repo root copies it into every new worktree. Check for one when `.env*` files exist in the
  main checkout but no `.worktreeinclude` does, and **warn** — otherwise each session starts without
  the config and discovers it the hard way.

State the base branch and sha in §4 so the user approving the fan-out can see exactly what each
session will start from.

## 2. Collect the slice set

With a parent issue: `gh issue view {parent} --json number,title,body` and pull the child
references from its body (`- [ ] #NN` task-list entries, or a `## Slices` section).

Without: `gh issue list --state open --json number,title,labels,assignees --limit 30`.

Then filter to **dispatchable** slices:

- Drop anything already assigned (`assignees` non-empty) — it is in flight. This is the check that
  covers the window before a PR exists, and it is load-bearing: `/start-issue` claims its issue as
  step 2, before it creates anything, so a dispatched session shows up here within seconds rather
  than only once its draft PR lands.
- Drop anything with an open PR: `gh pr list --state open --json closingIssuesReferences` and exclude issues already referenced.
- Drop anything whose body declares a dependency on a slice not yet merged (`## Blocked by #NN`, `Depends on #NN`). Report these as **held**, with what they wait on.
- Drop anything whose worktree already exists: `git worktree list --porcelain` naming
  `.claude/worktrees/issue-{n}`. A live worktree means a session is already on that slice, or one
  was left behind; either way, re-dispatching would reopen it (passing an existing name opens the
  existing worktree rather than creating one). Report it and say which.

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
/dispatch-slices — {N} slices → background sessions in worktrees

  #61  feat/…  Wire the loyalty earn line          AFK
  #62  feat/…  Rewards balance on the cart page    HITL (manual smoke)
  #63  feat/…  Reject unregistered client_id       AFK

Held:    #64 (blocked by #61)
Skipped: #59 (assigned), #60 (parent spec)

Base:    origin/{default} @ {base_sha}
Trees:   .claude/worktrees/issue-61, issue-62, issue-63
Action:  one background session per slice, each in its own worktree, running independently.
Proceed?
```

Ask once. After approval, dispatch all of them without further prompting.

## 5. Dispatch

One command per slice, run from the main checkout. Reference the parent so the session can read
the spec for context.

**AFK slice:**

```bash
claude --bg --worktree issue-{n} --dangerously-skip-permissions \
  "/start-issue {n} — refer to the spec in issue #{parent} for context — implement it with /tdd, then run /finalize-pr."
```

**HITL slice** — the session must stop rather than self-certify:

```bash
claude --bg --worktree issue-{n} --dangerously-skip-permissions \
  "/start-issue {n} — refer to the spec in issue #{parent} for context — implement it with /tdd. When the work is complete, push the branch and STOP: tell me it needs a manual smoke test and wait. Do not run /finalize-pr yourself."
```

**Name every worktree `issue-{n}`.** The mapping from worktree to slice has to be mechanical,
because `/merge-stack` and `/merge-pr` both need to find a branch's worktree later and there is
nowhere to write a note between sessions.

**Capture each background session id.** A dispatch creates the session, prints its id, and returns:

```
Starting background service…
backgrounded · 74005c92
  claude agents             list sessions
  claude attach 74005c92    open in this terminal
  claude logs 74005c92      show recent output
  claude stop 74005c92      stop this session
```

Two things about reading that output:

- **The id is the short one after `backgrounded · `** — eight hex characters. It is the `id` field
  in `claude agents --json`, and it is what `attach`, `logs`, `stop` and `rm` take. The `sessionId`
  uuid printed beside it in the JSON is a different thing; passing it to those commands does not
  work.
- **Confirm on the printed id, not on the exit code.** This CLI ignores unknown flags silently, so
  a malformed invocation can look like a clean run. Treat a dispatch with no id in its output as
  failed, whatever it exited with.

Verified against 2.1.263: the command needs no TTY and returns immediately from a skill's piped
Bash call, and no workspace-trust dialog appears when the main checkout has been trusted once — the
worktree lives inside it, under `.claude/worktrees/`.

### Why the bypass flag is right here and nowhere else

A background session has nobody to answer a permission prompt. It does not fail and it does not
auto-deny: it stalls as `Needs input` and waits indefinitely, and a fan-out of five slices can sit
idle overnight on a single `git push` nobody approved. `--dangerously-skip-permissions` is the
honest way to launch work you are not watching.

That reasoning does not extend past this step. A session a human is sitting in front of reads the
repo's committed `permissions.allow`, which is narrow and reviewable; do not add the flag to
anything interactive, and do not widen the repo's allowlist to match what a background session is
doing.

Notes that are easy to get wrong:

- **A worktree is a fresh checkout.** Dependencies are not installed and gitignored files are
  absent. `/start-issue` installs for the detected toolchain as its first act after claiming;
  `.worktreeinclude` is what carries `.env` in. Do not install into a worktree from here.
- **Rate limits are shared** across the account, and now so is the machine. Ten parallel slices
  consume ten slices' worth of quota, ten checkouts' worth of disk, and ten test runs' worth of CPU
  — and any two that start a dev server will fight over the same port. With a large set, ask before
  dispatching more than ~5 at a time, or honour `--limit`.

## 6. Report

```
/dispatch-slices — {N} dispatched

  #61  74005c92  AFK   .claude/worktrees/issue-61  worktree-issue-61
  #62  8b1e40af  HITL  .claude/worktrees/issue-62  worktree-issue-62
  #63  c93d271b  AFK   .claude/worktrees/issue-63  worktree-issue-63

Monitor:   claude agents --json          # state: working | blocked | done | failed
Watch:     claude agents                 # interactive view, needs a terminal
Take over: claude attach <id>
Stop:      claude stop <id>              # transcript kept; claude rm <id> removes the worktree too

HITL slices (#62) will stop and wait for your smoke test. Attach to one to run the app locally,
then /finalize-pr from there.
```

Each session renames its branch from `worktree-issue-{n}` to `{prefix}/{n}-{slug}` in `/start-issue`
step 3, so the branch column above is what the worktree starts on, not what the PR will be built on.

**Read progress from `claude agents --json` and from GitHub, never from `claude logs`.** `logs`
prints the session's raw terminal: ANSI escapes, cursor addressing and spinner frames, kilobytes of
it for a session that ran one command. It is for a human to look at, not for an agent to parse. The
`state` field and the slice's own issue and PR say everything a report needs.

## Rules

- Dispatch only; never implement a slice in this session.
- One session per slice, one worktree per slice, named `issue-{n}`. Never batch two issues into one session — they would share a branch and collide in `/merge-stack`.
- Never dispatch an issue that is assigned, already has an open PR, or already has a worktree.
- One confirmation (§4), then run through the whole set.
- Pass `--dangerously-skip-permissions` on these background dispatches, and nowhere else.
- A dispatch counts as done only when its output carries a background session id. An exit code is not evidence.
- Never parse `claude logs` output. Read `claude agents --json`.
- If a dispatch fails, report it and continue with the rest — a partial fan-out is fine and re-runnable, since §2 skips slices that are now assigned or already have a worktree.

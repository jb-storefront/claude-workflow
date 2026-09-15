---
name: dispatch-slices
description: Fan out unblocked slice issues to parallel Claude Code cloud sessions, one session per slice. Discovers or takes a parent spec issue, classifies each slice AFK or HITL, confirms once, then dispatches with `claude --cloud` under a pty and captures each session id. Use when the user says "/dispatch-slices", "start the next slices", "work these issues in parallel", or has just finished /to-tickets.
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

These describe the repo as the VM will clone it. State the base branch and sha in §4 so the user
approving the fan-out can see exactly what each session will start from.

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

**`claude --cloud` refuses to create a session without a TTY**, and a skill's Bash calls are piped:

```
Without an interactive terminal, --cloud can only send the prompt to an existing cloud session:
pass its ID (session_... or cse_...) or its claude.ai/code URL. To start a new cloud session,
run from a TTY.
```

Wrap each dispatch in a pty:

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

**Capture each session id.** A dispatch creates the session, prints three lines and returns:

```
Created cloud session: {auto-generated title}
View: https://claude.ai/code/{session-id}?from=cli&m=0
Resume with: claude --teleport {session-id}
```

Two things about reading that output:

- **Match `session_[A-Za-z0-9]+`; never read by line or column.** Under a pty the CLI emits its
  terminal control sequences too, so the three lines arrive wrapped in ANSI escapes.
- **Confirm on `Created cloud session:`, not on the exit code.** This CLI ignores unknown flags
  silently, so a malformed invocation can look like a clean run. Treat a dispatch with no session
  id in its output as failed, whatever it exited with.

### Why the pty is honest here

The TTY check exists because a `--cloud` that wasn't honoured would quietly start N *local*
sessions while reporting a cloud fan-out. `script` does not defeat that: it gives the process a
real controlling terminal, so the flag is honoured rather than bypassed, and the proof is in the
return value — a genuine cloud session id, which a local session cannot produce. Verified against
2.1.263. Re-verify before trusting it on a much later build; this behaviour has already changed
once, and the skill's earlier claim that a pty "buys nothing, the call does not return" was true of
2.1.220 and wrong by 2.1.263.

**One case still belongs to the human.** The first `--cloud` in a repo whose committed
`.claude/settings.json` pre-approves permissions opens the workspace-trust dialog (*"This folder
pre-approves N tool permissions… Do you trust this folder?"*). That is a security decision, and a
pty must not be used to answer it. If a dispatch stalls there, stop, hand the remaining commands to
the user, and say why. Once they have accepted trust once, later dispatches run unattended.

**A headless create exists but is not for this setup.** `--environment` exempts itself from the TTY
check, so `claude -p "<prompt>" --environment <id>` needs no pty at all. It takes a **self-hosted
runner pool** and nothing else:

```
Error: --environment expects a self-hosted environment id (ccpool_...), got "CC-cloud1"
```

An Anthropic-managed cloud environment has no `ccpool_` id, so the pty above is the path. If a
project ever runs on a self-hosted pool, prefer `--environment`: same captured id, no pty.

Notes that are easy to get wrong:

- **Never emit `--dangerously-skip-permissions`.** Cloud sessions honour the repo's committed
  `.claude/settings.json` `permissions.allow`. If a session stalls on a permission prompt, the
  fix is to widen that allowlist in the repo — a reviewable change — not to bypass the check.
- **No `--worktree`, no session names to keep unique.** Each session gets its own VM.
- **Rate limits are shared** across the whole account. Ten parallel slices consume ten slices'
  worth of quota at once; there is no separate compute charge, but there is a ceiling. With a
  large set, ask before dispatching more than ~5 at a time, or honour `--limit`.

## 6. Report

```
/dispatch-slices — {N} dispatched

  #61  session_01ABC…  AFK   https://claude.ai/code/session_01ABC…
  #62  session_01DEF…  HITL  https://claude.ai/code/session_01DEF…
  #63  session_01GHI…  AFK   https://claude.ai/code/session_01GHI…

Monitor:   claude.ai/code, or the Code tab in the Claude mobile app
Steer:     claude --cloud <session-id> -p "…"     # sends, needs no TTY, returns no reply
Take over: claude --teleport <session-id>         # from a checkout of this repo

HITL slices (#62) will stop and wait for your smoke test. Teleport into one to run the app
locally, then /finalize-pr from your terminal.
```

`claude --cloud <session-id> -p "…"` is send-only: it prints `Sent to cloud session.` and the
session's URL, never the session's reply. To read what a session said, open its URL or teleport in.
Say that rather than implying a round trip.

Verified against 2.1.263, where `claude --help` documents both: `--cloud [description|session_id|url]`
and `--teleport [session]`. `--cloud <session-id>` attaches to an existing session and is the one
cloud invocation a skill can make unaided, because it sends to a session rather than creating one;
`--teleport <session-id>` checks the session's branch out locally and errors if run from the wrong
repo. On 2.1.220 neither flag appeared in the help text, so do not read absence from `--help` as
evidence a spelling is wrong — this CLI ignores unknown flags silently, and it has documented these
two since.

## Rules

- Dispatch only; never implement a slice in this session.
- One session per slice. Never batch two issues into one session — they would share a branch and collide in `/merge-stack`.
- Never dispatch an issue that is assigned or already has an open PR.
- One confirmation (§4), then run through the whole set.
- Do not pass `--dangerously-skip-permissions`; permissions belong in the repo's committed settings.
- Never answer a workspace-trust or permission prompt on the user's behalf, through a pty or otherwise. Hand it back. The pty clears the TTY check and nothing else.
- A dispatch counts as done only when its output carries a session id. An exit code is not evidence.
- If a `claude --cloud` invocation fails, report it and continue with the rest — a partial fan-out is fine and re-runnable, since §2 skips slices that are now assigned.

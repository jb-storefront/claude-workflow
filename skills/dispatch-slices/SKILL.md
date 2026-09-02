---
name: dispatch-slices
description: Plan a fan-out of unblocked slice issues to parallel Claude Code cloud sessions, one session per slice. Discovers or takes a parent spec issue, classifies each slice AFK or HITL, and emits the ready-to-run `claude --cloud` command for each. Use when the user says "/dispatch-slices", "start the next slices", "work these issues in parallel", or has just finished /to-tickets.
---

# Dispatch Slices

Turn a set of ready slice issues into a set of dispatch commands — one isolated cloud VM per
slice, each going issue → branch → TDD → reviewed PR on its own.

This is the fan-out step of the `/grill-with-docs` → `/to-spec` → `/to-tickets` →
**`/dispatch-slices`** → `/tdd` → `/finalize-pr` → `/merge-stack` pipeline. It runs **locally**,
in the main checkout, and does no work itself: it picks the slices, writes the prompts, and hands
the commands back for the user to run. Each dispatched session runs `/start-issue` as its first
act.

**This skill plans; the human launches.** Creating a cloud session is interactive-only, so a
skill cannot do it — §5 explains why, and it is not a gap worth working around.

## Input

`$ARGUMENTS`: optionally a parent spec issue number (`60` or `#60`), and/or `--limit <n>`.

- With a parent: plan a dispatch of its unblocked children.
- Without: discover unblocked open issues across the repo and ask which to include.

## 1. Pre-flight — the clone the VM will get

`--cloud` clones **the GitHub remote at your current branch**, not your working tree. Unpushed
commits and uncommitted edits do not travel. So:

- `{branch}` = `git branch --show-current`; `{default}` = `gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'`.
- If `{branch}` != `{default}` → **warn**: every slice will branch off `{branch}`, not `{default}`. Ask whether that is intended before continuing.
- `git status --porcelain` non-empty → **warn** that those changes will not reach any session.
- `git log --oneline @{u}.. 2>/dev/null` non-empty → **stop**: push first, or the sessions clone stale code.

These describe the repo as the VM will see it *when the commands are run*, which is now some minutes
after this check. State the base branch and sha in §4 so a user who commits in between can see that
what they are about to dispatch has moved.

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

## 4. Present the plan

```
/dispatch-slices — {N} slices ready to dispatch

  #61  feat/…  Wire the loyalty earn line          AFK
  #62  feat/…  Rewards balance on the cart page    HITL (manual smoke)
  #63  feat/…  Reject unregistered client_id       AFK

Held:    #64 (blocked by #61)
Skipped: #59 (assigned), #60 (parent spec)

Base:    {branch} @ {short-sha}
```

No confirmation prompt: nothing is launched, so there is nothing to approve. The plan and the
commands below are the whole output. Go straight from here to §5.

## 5. Emit the dispatch commands

One command per slice, in a block the user can copy. Reference the parent so the session can read
the spec for context.

**AFK slice:**

```bash
claude --cloud "/start-issue {n} — refer to the spec in issue #{parent} for context — implement it with /tdd, then run /finalize-pr."
```

**HITL slice** — the session must stop rather than self-certify:

```bash
claude --cloud "/start-issue {n} — refer to the spec in issue #{parent} for context — implement it with /tdd. When the work is complete, push the branch and STOP: tell me it needs a manual smoke test and wait. Do not run /finalize-pr yourself."
```

Say how to run them: **each in its own terminal, one at a time** — not pasted as a batch, and not
through this session's `!` prefix, which is piped like any other Bash call. Each command opens the
new session interactively; once it is underway the user can leave it and the work continues on the
VM.

### Why this skill does not run them itself

Creating a cloud session is interactive-only by design. The CLI rejects `--cloud` whenever stdout
is not a TTY:

```
Error: --cloud requires an interactive terminal.
```

The guard is right. This CLI ignores unknown flags silently, so a `--cloud` that wasn't honoured
would quietly start N *local* sessions while reporting a successful cloud fan-out. Every Bash call
a skill makes is piped, which is exactly the condition the check fires on.

A pty wrapper (`script -q /dev/null claude --cloud …`) does clear the check honestly — under a real
pty the flag is genuinely honoured, not faked — but it buys nothing, because clearing the check was
never the obstacle. `claude --cloud "<task>"` *attaches* you to the new session's interactive UI
rather than printing an id and exiting: there is no id to capture, the call does not return, and the
first run in a repo whose `.claude/settings.json` pre-approves permissions opens the
workspace-trust dialog — a security decision belonging to the human, not something to answer
through a pty.

There is no headless create to fall back on. `--print` is rejected the same way (*"Cloud sessions
are interactive only"*), and `--bg` / `claude agents` are a different, local backend. The only
non-interactive cloud invocation the CLI allows is attaching to a session that already exists (§6),
which is no help before one does.

Notes that are easy to get wrong when writing the commands:

- **Never emit `--dangerously-skip-permissions`.** Cloud sessions honour the repo's committed
  `.claude/settings.json` `permissions.allow`. If a session stalls on a permission prompt, the
  fix is to widen that allowlist in the repo — a reviewable change — not to bypass the check.
- **No `--worktree`, no session names to keep unique.** Each session gets its own VM.
- **Rate limits are shared** across the whole account. Ten parallel slices consume ten slices'
  worth of quota at once; there is no separate compute charge, but there is a ceiling. With a
  large set, emit the first ~5 and say the rest can follow, or honour `--limit`.

## 6. Report what happens next

§4, §5 and §6 are one continuous message; this is its footer. Session ids do not exist until the
user runs the commands, so there are none to print — report where they will appear and what to do
with them.

```
Run each command above in its own terminal, one at a time.

Find ids:  claude.ai/code, or the Code tab in the Claude mobile app
Steer:     claude --cloud <session-id> -p "…"     # no TTY needed — runs from here
Take over: claude --teleport <session-id>         # from a checkout of this repo
Re-attach: claude --cloud <session-id>

HITL slices (#62) will stop and wait for your smoke test. Teleport into one to run the app
locally, then /finalize-pr from your terminal.
```

Both `--cloud` and `--teleport` are hidden from `claude --help`, and this CLI ignores unknown flags
silently — so absence from the help text is not evidence that a spelling is wrong, in either
direction. Verified against 2.1.220: `--cloud <session-id>` attaches to an existing session and is
the one cloud invocation that needs no TTY, because it sends to a session rather than creating one;
`--teleport <session-id>` checks the session's branch out locally and errors if run from the wrong
repo.

## Rules

- Plan and hand off. Never dispatch, and never implement a slice in this session.
- One session per slice. Never batch two issues into one session — they would share a branch and collide in `/merge-stack`.
- Never emit a command for an issue that is assigned or already has an open PR.
- No confirmation step — the plan and the commands are the output, and running them is the user's move.
- Do not pass `--dangerously-skip-permissions`; permissions belong in the repo's committed settings.
- Never wrap a dispatch in a pty, and never answer a workspace-trust or permission prompt on the user's behalf. Hand it back.
- Re-running is cheap and safe: §2 skips slices that are now assigned, so if the user dispatches only some, run `/dispatch-slices` again for the rest.

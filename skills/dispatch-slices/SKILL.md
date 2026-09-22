---
name: dispatch-slices
description: Fan out unblocked Slices to parallel local Claude Code sessions, one git worktree per Slice. Refuses a Spec still at draft or whose Criteria are not all owned by a Slice, classifies a Slice as needing a person only from `[manual]` tags, sets the Spec to in-progress at the first fan-out, then dispatches each session through /start-issue, /acceptance-tests, /tdd and /finalize-pr. Use when the user says "/dispatch-slices", "start the next slices", "work these issues in parallel", or has just finished /to-tickets.
---

# Dispatch Slices

Turn a set of ready Slices into a set of running background sessions — one git worktree per Slice,
each going issue → failing tests → TDD → reviewed PR on its own.

This is the fan-out step of the `/to-spec` → `/anchor-spec` → `/critique-spec` → `/to-tickets` →
**`/dispatch-slices`** → `/merge-stack` pipeline. It runs in the **main checkout** and builds
nothing itself: it checks the Spec, picks the Slices, writes the prompts, and launches. Each
dispatched session runs `/start-issue`, then `/acceptance-tests`, then `/tdd`, then `/finalize-pr`.

Two gates stand in front of the fan-out, and both are about the Spec rather than about any one
Slice. A Spec nobody doubted does not get built (§2). A Spec whose Criteria are not all owned does
not get built either, because the unowned ones are what quietly never ship (§4).

Artifact shapes — the Spec file, the Spec issue body, the Slice body, the Criterion grammar — are in
`CONTRACTS.md` at the repo root. This skill reads them; it does not restate them.

## Input

`$ARGUMENTS`: optionally a Spec issue number (`60` or `#60`), and/or `--limit <n>`.

- With a Spec issue: dispatch its unblocked Slices.
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
- If the project keeps gitignored config the Slices need (`.env` and friends), a `.worktreeinclude`
  at the repo root copies it into every new worktree. Check for one when `.env*` files exist in the
  main checkout but no `.worktreeinclude` does, and **warn** — otherwise each session starts without
  the config and discovers it the hard way.

State the base branch and sha in §6 so the user approving the fan-out can see exactly what each
session will start from.

## 2. Find the Spec and read its Status

**Which Spec.** With a Spec issue given, that is it. Without one, read each candidate Slice's
`## Parent` section: a Slice that names a Spec issue is governed by that Spec, and a Slice that
names none is a **lone Slice** — exempt from this section and from §4, and held to the same gate
later by `/finalize-pr`. A discovery run can therefore touch several Specs and several lone Slices
at once; check each Spec once, not once per Slice.

**Read the file, not the issue body.** The Spec file is `docs/specs/{spec}-{slug}.md` on the default
branch; find it with `ls docs/specs/{spec}-*.md`. `CONTRACTS.md` makes the file win on conflict, so
the Status this gate reads is the file's and never the issue's.

| What the Spec file says | What to do |
| --- | --- |
| The file does not exist | **Stop.** The Spec was never anchored |
| `**Status:** draft` | **Stop.** Nobody has doubted this Spec |
| `**Status:** critiqued` | Proceed. This is the first fan-out; §7 applies |
| `**Status:** in-progress` | Proceed. A fan-out already happened; §7 leaves the file alone |
| `**Status:** implemented` or `superseded` | **Warn**, and name it in the §6 confirmation |

A stop names the Spec, the Status, and the command that clears it:

```
/dispatch-slices — stopped, nothing dispatched

Spec #60 is at Status draft.

A draft Spec is one a single Claude session synthesised and nobody doubted. Dispatching it
would build every ambiguity in it five times in parallel.

  /critique-spec 60      send it to the critic and resolve the findings

Or, when the Spec is small enough that the gate is not worth it:

  /anchor-spec 60 --skip-critique "<reason>"
```

A missing file stops for the stronger version of the same reason: there is no Status, no Criteria to
own, and nothing for a session to read, because a worktree cut from the remote default branch can
see committed files and nothing else. Say `/anchor-spec {spec}` and stop. Do not fall back to the
Spec issue body — a gate that a deleted file opens is not a gate.

`implemented` and `superseded` are warnings rather than stops because both have honest readings: a
follow-up Slice on a landed Spec, or a Slice being finished on a Spec that a later one replaced.
Name it and let the human decide at §6.

## 3. Collect the Slice set

With a Spec issue: `gh issue view {spec} --json number,title,body` and pull the Slice references
from its `## Slices` task list (`- [ ] #NN` entries).

Without: `gh issue list --state open --json number,title,labels,assignees --limit 30`.

Then filter to **dispatchable** Slices:

- Drop anything already assigned (`assignees` non-empty) — it is in flight. This is the check that
  covers the window before a PR exists, and it is load-bearing: `/start-issue` claims its issue as
  step 2, before it creates anything, so a dispatched session shows up here within seconds rather
  than only once its draft PR lands.
- Drop anything with an open PR: `gh pr list --state open --json closingIssuesReferences` and exclude issues already referenced.
- Drop anything whose body declares a dependency on a Slice not yet merged (`## Blocked by #NN`, `Depends on #NN`). Report these as **held**, with what they wait on.
- Drop anything whose worktree already exists: `git worktree list --porcelain` naming
  `.claude/worktrees/issue-{n}`. A live worktree means a session is already on that Slice, or one
  was left behind; either way, re-dispatching would reopen it (passing an existing name opens the
  existing worktree rather than creating one). Report it and say which.

If the set is empty, report why per issue and stop.

## 4. Check that every Criterion is owned

Skip this for a lone Slice. For every Spec in play:

- **The Spec's Criteria** are the `### C{n}` headings in its `## Criteria` section:
  `grep -oE '^### C[0-9]+' docs/specs/{spec}-{slug}.md`.
- **The Slices' citations** are the `#{spec} C{n}` ids under each Slice's `## Acceptance criteria`
  heading, and nowhere else in the body:

  ```bash
  gh issue view {n} --json body --jq '.body' \
    | awk '/^## Acceptance criteria/{f=1;next} /^## /{f=0} f' \
    | grep -oE '#[0-9]+ C[0-9]+'
  ```

  The `awk` is the load-bearing half. A Slice's `## What to build` often mentions a neighbouring
  Criterion in passing, and a `grep` over the whole body would read that mention as ownership —
  which is the one thing this gate exists to catch.

**Read the citations from every Slice on the Spec issue's task list, not from the dispatchable set.**
Open, closed, assigned, merged: a Criterion owned by a Slice that landed last week is owned, so
`gh issue view` each entry on the task list rather than reusing what §3 returned. Reading only what
§3 left would report every already-built Criterion as orphaned, and the second fan-out of a Spec
would be the one that could never run.

Three gaps, all **stops**:

- **A Spec Criterion no Slice cites.** Name the id and its Then clause. Nothing is going to build it,
  and nothing downstream will notice: `/finalize-pr` reports the Criteria a Slice owns, so a
  Criterion no Slice owns is never reported by anybody.
- **A Slice citation the Spec does not have.** Name the Slice and the citation. This is `#60 C9`
  against a Spec whose Criteria stop at C5, or `#59 C1` where the Spec is #60 — a typo, a renumber,
  or a Slice written against a Spec that has since been edited. `/acceptance-tests` would stop on it
  too, but four sessions later and four worktrees in.
- **A Criterion two Slices both cite.** Name the id and both Slices. `CONTRACTS.md` makes a Criterion
  owned by exactly one Slice, and two owners is not twice the safety: both sessions write a test
  carrying the same id, both PRs claim it verified, and neither reviewer sees the other's. It is also
  the shape a badly-cut Slice takes, so the fix is usually to the cut rather than to the citation.

A checkbox under `## Acceptance criteria` carrying no `#{spec} C{n}` at all is the second gap in its
commonest form: `/to-tickets` wrote a plain sentence and nobody added the id. Name the Slice and
quote the line.

**Report every gap in one message**, then stop. A fan-out held once per missing id is a fan-out held
five times.

```
/dispatch-slices — stopped, nothing dispatched

Spec #60 — Loyalty earn and burn: 3 of 5 Criteria are owned.

Cited by no Slice:
  C4  Then the ledger row is reversed within one minute of the refund settling
  C5  Then a burn of more points than the balance is rejected 422

Cited but not in the Spec:
  #63  cites "#60 C9" — the Spec's Criteria end at C5
  #62  "- [ ] Rewards balance renders in the cart summary" — no id

Owned twice:
  C1  cited by both #61 and #65

Fix the Slice bodies, then dispatch again.
```

**The fix is to the Slice bodies, never to the ids.** `CONTRACTS.md` never renumbers a Criterion:
its id is already cited from a Slice, a test name, and a review comment, so closing a gap by
renumbering moves the gap somewhere nobody is looking. A Criterion nobody owns gets cited by the
Slice that should own it, or a new Slice is cut for it, or it is deleted from the Spec and leaves
its number behind as a gap. A Criterion is either owned by exactly one Slice or it is not shipping,
and that is the whole point of cutting a Spec into Slices.

## 5. Classify each Slice: AFK or HITL

One rule, and it is the whole rule:

> **A Slice is HITL when and only when one of the Criteria it owns carries `[manual]`.**

- **AFK** — every Criterion it owns is machine-checkable. The session runs to a reviewed PR alone.
- **HITL** — at least one `[manual]`. The session stops before `/finalize-pr` and waits for a person.

Read the tag from the **Spec file**, for each id the Slice cites: `grep -E '^### C[0-9]+ \[manual\]'`
on the `## Criteria` section. The Slice body repeats the tag and the Spec issue body repeats it
again, and either copy can be stale; the file wins. A lone Slice has no file, so its own checkboxes
are the Criteria and the tag is read from them.

**Nothing else classifies.** Not labels — `ui`, `ux` and `demo` on an issue mean nothing here. Not
wording — a Criterion phrased as what a person sees is still AFK when it carries no tag. The
inference this skill used to do was wrong often enough in both directions to cost more than it
saved: it sent AFK work to a human who then had to look at it, and it certified visual work nobody
had looked at. `CONTRACTS.md` gives the tag one job and gives it to nothing else.

### The observational warning

A Slice with no `[manual]` tag whose Criteria read observationally — "the buyer sees", "the page
shows", "renders", "displays", "appears" — gets **exactly one warning**, and is dispatched **AFK**
anyway:

```
  #62  no [manual] tag, but C2 reads observationally ("renders in the cart summary").
       Dispatching AFK. Tag the Criterion in the Spec if a person should check it.
```

One warning per Slice, not one per Criterion: the human needs to know the Slice is worth a second
look, and three lines saying so about the same Slice is noise, not information.

**The warning is printed in the §6 confirmation, under `Warned:`, in full.** That block is the one
thing the human reads before approving the fan-out, and a warning that exists only in this skill's
reasoning is a warning nobody sees.

The warning never changes the classification. That is what makes the rule deterministic: the same
Slice set classifies the same way on every run, by anyone, with no judgement in the loop. The
warning is how a missing tag gets noticed; the tag is how it gets fixed.

## 6. Present the plan and confirm once

```
/dispatch-slices — {N} Slices → background sessions in worktrees

Spec:    #60 — Loyalty earn and burn (critiqued → in-progress)
         5 Criteria, all owned

  #61  feat/…  Wire the loyalty earn line          AFK
  #62  feat/…  Rewards balance on the cart page    HITL (#60 C2 is [manual])
  #63  feat/…  Reject unregistered client_id       AFK

Warned:  #62  no [manual] tag, but C2 reads observationally ("renders in the cart summary").
               Dispatching AFK. Tag the Criterion in the Spec if a person should check it.
Held:    #64 (blocked by #61)
Skipped: #59 (assigned), #60 (the Spec issue)

Base:    origin/{default} @ {base_sha}
Trees:   .claude/worktrees/issue-61, issue-62, issue-63
Action:  set the Spec to in-progress on {default}, then one background session per Slice,
         each in its own worktree, running independently.
Proceed?
```

Ask once. After approval, run §7 and §8 for the whole set without further prompting.

## 7. Set the Spec's Status to in-progress

**Once per Spec §2 found, not once per fan-out.** A discovery run can be dispatching Slices from two
Specs at the same time; each is at its own point in its own lifecycle, and the one that is already
`in-progress` must not be touched while the other moves.

For each of them: only when its Spec file reads `critiqued`. At `in-progress` it is already right,
and at `implemented` or `superseded` §2 already warned — do not walk a Status backwards.

Change the one line, commit only that file, and push to the default branch, so that every worktree
§8 cuts is cut from a Spec that already says work has started:

```bash
git add docs/specs/{spec}-{slug}.md
git commit -m "docs: the Spec for #{spec} is in progress"
git push origin {default}
```

Two things can go wrong, and neither holds the fan-out:

- **The main checkout is not on `{default}`.** Do not commit the Spec onto whatever branch happens
  to be out. Report the edit the founder needs to land and carry on.
- **The push is rejected.** The default branch is protected — detected here the same way
  `/anchor-spec` detects it, by being told no. Undo the commit before carrying on:

  ```bash
  git reset --keep origin/{default}
  ```

  `--keep` rather than `--hard`: it aborts on local changes instead of destroying them. Leaving the
  commit sitting unpushed would be worse than never making it — §1 **stops** on unpushed commits, so
  the next `/dispatch-slices` on this repo would refuse to run until someone worked out why. If the
  reset aborts, say so and stop touching git; the founder's tree is theirs.

  Then report the one-line edit the founder should land, and carry on with §8.

Carrying on is deliberate, and it is not because nothing reads the value. `/critique-spec` does:
`in-progress` is one of the states it refuses to re-critique from. What makes carrying on safe is
that the state the file is left in — `critiqued` — is *also* one it refuses to run from, so the
guard holds either way and only the message a founder would see gets worse. `/merge-stack` moves
the Status to `implemented` from wherever it finds it.

What the founder loses is a line that tells a reader work has started. What they would lose by
stopping is five ready Slices, held until somebody merges a one-line pull request. Say which line
needs landing, and dispatch.

## 8. Dispatch

One command per Slice, run from the main checkout. The prompt names the four skills in the order the
session runs them, and references the Spec so the session can read it for context.

**AFK Slice:**

```bash
claude --bg --worktree issue-{n} --dangerously-skip-permissions \
  "/start-issue {n} — refer to the Spec in issue #{spec} for context. Then run /acceptance-tests, then /tdd, then /finalize-pr."
```

**HITL Slice** — the session must stop rather than self-certify:

```bash
claude --bg --worktree issue-{n} --dangerously-skip-permissions \
  "/start-issue {n} — refer to the Spec in issue #{spec} for context. Then run /acceptance-tests, then /tdd. When the work is complete, push the branch and STOP: tell me it needs a manual check and wait. Do not run /finalize-pr yourself."
```

On a lone Slice, drop the `— refer to the Spec…` clause. The rest is unchanged: a lone Slice numbers
its own Criteria and `/acceptance-tests` writes them back to the issue body.

The four skills are one chain, not a menu: a session dispatched straight to `/tdd` skips the step
that names its tests after Criteria, and arrives at `/finalize-pr` with nothing matching an id. See
`/acceptance-tests` for why that step is where it is.

**Name every worktree `issue-{n}`.** The mapping from worktree to Slice has to be mechanical,
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
auto-deny: it stalls as `Needs input` and waits indefinitely, and a fan-out of five Slices can sit
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
- **Rate limits are shared** across the account, and now so is the machine. Ten parallel Slices
  consume ten Slices' worth of quota, ten checkouts' worth of disk, and ten test runs' worth of CPU
  — and any two that start a dev server will fight over the same port. With a large set, ask before
  dispatching more than ~5 at a time, or honour `--limit`.

## 9. Report

```
/dispatch-slices — {N} dispatched

Spec:    #60 — Status in-progress on {default}

  #61  74005c92  AFK   .claude/worktrees/issue-61  worktree-issue-61
  #62  8b1e40af  HITL  .claude/worktrees/issue-62  worktree-issue-62
  #63  c93d271b  AFK   .claude/worktrees/issue-63  worktree-issue-63

Monitor:   claude agents --json          # state: working | blocked | done | failed
Watch:     claude agents                 # interactive view, needs a terminal
Take over: claude attach <id>
Stop:      claude stop <id>              # transcript kept; claude rm <id> removes the worktree too

HITL Slices (#62) will stop and wait for you to check #60 C2. Attach to one to run the app
locally, then /finalize-pr from there.
```

Each session renames its branch from `worktree-issue-{n}` to `{prefix}/{n}-{slug}` in `/start-issue`
step 3, so the branch column above is what the worktree starts on, not what the PR will be built on.

**Read progress from `claude agents --json` and from GitHub, never from `claude logs`.** `logs`
prints the session's raw terminal: ANSI escapes, cursor addressing and spinner frames, kilobytes of
it for a session that ran one command. It is for a human to look at, not for an agent to parse. The
`state` field and the Slice's own issue and PR say everything a report needs.

## Rules

- Dispatch only; never build a Slice in this session.
- Never dispatch a Spec at Status `draft`, or one with no Spec file. Neither has an override here — `/anchor-spec --skip-critique "<reason>"` is the recorded way past the Critique gate, and it is recorded in the Spec.
- Never dispatch a Spec whose Criteria are not all owned by exactly one Slice, in either direction. Report every gap at once.
- Classify HITL from `[manual]` tags and from nothing else. Never from a label, never from wording, and never by asking — the tag is the answer.
- Warn at most once per Slice about observational Criteria carrying no tag, and dispatch it AFK regardless.
- One session per Slice, one worktree per Slice, named `issue-{n}`. Never batch two Slices into one session — they would share a branch and collide in `/merge-stack`.
- Never dispatch an issue that is assigned, already has an open PR, or already has a worktree.
- One confirmation (§6), then run through the whole set.
- The dispatch prompt names `/start-issue`, `/acceptance-tests`, `/tdd`, `/finalize-pr` in that order; the HITL variant stops before `/finalize-pr`.
- Pass `--dangerously-skip-permissions` on these background dispatches, and nowhere else.
- A dispatch counts as done only when its output carries a background session id. An exit code is not evidence.
- Never parse `claude logs` output. Read `claude agents --json`.
- If a dispatch fails, report it and continue with the rest — a partial fan-out is fine and re-runnable, since §3 skips Slices that are now assigned or already have a worktree.

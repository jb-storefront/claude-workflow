---
name: finalize-pr
description: Drive a Slice PR to ready-for-human-review from its worktree. Reads the linked Slice and its Spec from whichever repository the closing reference names, auto-detects PM, runs quality gates, runs the command each [command] Criterion names, captures the Frames the repository declares for its [manual] Criteria, reports every Criterion as verified, weak, manual or unverified, dispatches the PR-writer agent, performs AI-discipline checks, ticks verified Criteria on the issue, posts the review via `gh pr review --comment`, and hands a Not blocking PR to /review-pr, which reviews the code and is the only skill that marks it ready. Use when the user says "/finalize-pr", "submit PR", "ready for review", or finishes a TDD cycle on a Slice.
---

# Finalize PR

Prove what a Slice's PR claims: a review comment that says what was actually proven, and ticked
Criteria on the Slice. When nothing here blocks, hand the PR to `/review-pr`, which runs the code
review and is the only skill that marks a PR ready. This skill never does.

## Input

`$ARGUMENTS`: a PR number (`42` or `#42`). If empty, detect from the current branch.

## The shapes this skill reads and writes

`CONTRACTS.md` at the repo root. The Slice body, the Spec, the Criterion grammar, the test
name that proves a Criterion, and the four states this skill reports are all defined there. Read it
before changing anything below, and read it instead of this skill when you want to hand-write a
Slice that this skill accepts.

Sections a Slice is missing are skipped rather than fatal, with the exceptions §2 names.

## 1. Pre-flight

- `{branch}` = `git branch --show-current`. If it's the default branch (`gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'`), **stop**.
- `git status --porcelain` — if non-empty, **stop**: commit or stash first.
- Find/create the PR:
  - With arg: `gh pr view {number} --json number,title,url,isDraft,headRefName,closingIssuesReferences,mergeStateStatus`. If `headRefName != {branch}`, stop.
  - Without arg: `gh pr list --head {branch} --json … --limit 1`. If none, open the draft
    `/start-issue` step 6 describes, which a session that never pushed it leaves to this skill:
    `{number}` from a branch named `{prefix}/{number}-{slug}`, the issue's title, and
    `Closes #{number}` as the body's first line, so §2 finds the issue. On a branch not in that
    form, `gh pr create --draft --title "{branch}" --body "Work in progress"`, and §2 reports no
    linked issue. Capture the new number/URL either way.
- Assign to current user: `{gh_user}` = `gh api user --jq '.login'`, then

  ```bash
  gh api -X POST "repos/{owner}/{repo}/issues/{pr_number}/assignees" -f "assignees[]={gh_user}"
  gh api "repos/{owner}/{repo}/issues/{pr_number}" --jq '.assignees[].login'
  ```

  `{owner}` and `{repo}` are **literal** — `gh api` fills them from the current repo. Pull requests
  are issues, so that is the right endpoint. The read-back is there because GitHub silently ignores
  assignees without push access. Non-fatal here (the PR already exists, so nothing downstream
  depends on the assignee), but if the read-back comes back without `{gh_user}`, say so in the §15
  summary rather than only in passing.
- Print a one-line pre-flight summary.

## 2. Read the Slice and its Criteria

For each issue in `closingIssuesReferences` (usually just one), read it from **the repository the
link names**, which is not always this one:

```bash
gh pr view {pr_number} --json closingIssuesReferences \
  --jq '.closingIssuesReferences[] | "\(.repository.owner.login)/\(.repository.name) \(.number)"'
gh issue view {number} --repo {owner}/{repo} --json title,body,labels
```

Carry that `{owner}/{repo}` through every later `gh issue` call in this skill, §12 included. A Slice
tracked in a backend repository and built in the front end's is normal, and a bare `gh issue view
53` reads whatever issue 53 is in the repository holding the pull request: a different Slice, or
nothing. `CONTRACTS.md` has the rule and why assuming is the worse of the two failures.

Parse, per `CONTRACTS.md`:

- `## Parent` → `{spec_issue}`, or absent on a lone Slice
- `## Acceptance criteria` → the Slice's Criteria, one per checkbox, as `{ index, id, tag, command, text, checked }`. `tag` is `manual`, `command` or none. Track index positions for ticking in §12.
- `## References for context` → repo-relative paths

If no issue is linked, skip parsing and note in the review comment that no Slice was found.

If GitHub reports no linked issue, parse the PR body for `Closes|Fixes|Resolves #(\d+)` —
`/start-issue` writes `Closes #{n}` as its first line. Note in the §15 summary when the link came
from the body rather than from GitHub's own linkage, since a hand-edited body could have dropped it.

### The id on each checkbox

`{id}` is the cited form `#60 C1`, one space, at the head of the checkbox text. Three cases:

| What the checkbox carries | `{id}` | Where the Criterion's full text lives |
| --- | --- | --- |
| `#60 C1 …`, with `## Parent` naming `#60` | `#60 C1` | the Spec, the body of issue `#60`, section `### C1` |
| `#74 C1 …` on a lone Slice, `#74` being its own number | `#74 C1` | the checkbox itself |
| no id at all | none | the checkbox itself |

The third case is a Slice written before Criterion ids existed, or written by hand without them. It
is not an error and it is not a free pass: an uncited checkbox is still a Criterion and still runs
the §10 gate. Having no id, no test can carry it, so it can reach only `weak` or `unverified`,
unless it is `[command]`, whose proof is its command and needs no id. Say in §13 and §15 that the
Slice carries no ids, because that, and not the missing test, is the thing to fix.

### The tag and the command

The tag sits immediately after the id, or at the head of the text when there is no id. A `[command]`
Criterion's command is the backticked command on its `Command:` line:

| Criterion | Where its command is |
| --- | --- |
| Cited from a Spec | The `Command:` line closing `### C{n}` in the Spec, which `spec.py read` returns as `command` |
| On a lone Slice | The checkbox itself, after `Command:` |

`CONTRACTS.md` has the grammar. A `[command]` Criterion with no `Command:` line has no command, and
§10 reports it `unverified` with `no command named`. Never compose one from the Criterion's wording.

### Read the Slice, never repair it

This skill writes exactly one thing to the Slice: §12's ticks. It never edits a Criterion's text,
id or tag, and never adds ids to a Slice that has none. Each Criterion is held to the tag it carries
on this run. When something looks wrong, record it for the `ⓘ` lines in §13 and the warnings in §15
and carry on:

- The Slice's checkboxes carry no ids.
- A checkbox tag disagrees with the Spec. The Spec wins for this run; the checkbox is stale.
- An untagged Criterion whose check is a command, such as "the dry run against the sandbox accepts
  the SQL": it belongs to `[command]`.
- A `[manual]` Criterion whose check is a command a session can run: it belongs to `[command]`.

Retagging a Criterion to change its state is passing this skill's own gate by editing the exam.
`CONTRACTS.md` has the worked example: gr4vy/gr4ce#470, where a session retagged two command
Criteria `[manual]` to clear the gate.

### The Spec

When `## Parent` names a Spec issue, the Spec is that issue's body, on the tracker. Read it from
the repository §2 read the Slice from:

```bash
python3 <this skill dir>/../../scripts/spec.py read {spec_issue} --repo {owner}/{repo}
```

Its JSON carries each Criterion as `{id, tag, text, command}`: the full Given/When/Then for each
cited id, its tag, and a `[command]` Criterion's command. Never parse the issue body by hand;
`CONTRACTS.md` has the grammar and `spec.py` is where it is tested.

**The Spec wins.** When the Spec and the Slice checkbox disagree on a Criterion's text, its tag
or its command, the Spec is right and the checkbox is stale. Report the disagreement; do not fix the
checkbox.

When `docs/agents/workflow.md` carries `**Specs:** off`, the repository keeps no Specs, and
`## Parent` is read as absent: no Spec is read, nothing is noted, and the Slice is a lone Slice
whose checkboxes are its Criteria. `CONTRACTS.md` describes the line; absent means `on`. The four
states, the gate, and the block on `unverified` are the same either way.

What `spec.py` exits with decides the rest:

- **Exit 1, not a Spec** → note it once and fall back to the checkbox text, as for a lone Slice. A
  Parent pointing at a Spec nobody anchored is worth saying out loud; it is not worth stopping for.
- **Exit 1, a legacy pointer** (its `✘` line names `spec.py migrate`) → the same fallback, and the
  note carries the migrate command from the `✘` line. The body points at a file from the old
  contract, and no reader falls back to that file.
- **Exit 2** → **stop** and relay its stderr. `gh` failed, and a Spec that could not be read is not
  a Spec that does not exist: falling back would hold every cited Criterion to a checkbox the Spec
  may contradict.

## 3. Bootstrap context

Read each file listed in `## References for context` (e.g., `CONTEXT.md`, area `CLAUDE.md`, ADRs). Skip silently when a path doesn't exist.

## 4. Auto-rebase check

`gh pr view {pr_number} --json mergeStateStatus --jq '.mergeStateStatus'`. If `BEHIND`, **stop** and tell the user to run `/rebase-pr` first, then re-run `/finalize-pr`. (Single explicit pause point — auto-invoke is intentionally deferred.)

## 5. Quality gates

Auto-detect the **toolchain** from a lockfile at the repo root, first match wins:

| Lockfile | Toolchain | Manifest that declares the gates |
| --- | --- | --- |
| `bun.lockb` | `bun` | `package.json` |
| `pnpm-lock.yaml` | `pnpm` | `package.json` |
| `package-lock.json` | `npm` | `package.json` |
| `yarn.lock` | `yarn` | `package.json` |
| `uv.lock` | `uv` | `pyproject.toml` |

A project declares its gates; this skill does not invent them. Run a gate only when the manifest
configures its tool, and report the rest as skipped.

**Node toolchains** — run, in order, **only the scripts that exist in `package.json`** (read the
`scripts` field and check first):

- `{pm} run lint`
- typecheck — accept **either** spelling: `type-check` or `typecheck`, whichever the repo defines.
- `{pm} run format:check`

**`uv`** — read `pyproject.toml` and run, in order, only what it configures:

- `[tool.ruff]` → `uv run ruff check .`
- `[tool.mypy]` → `uv run mypy`
- `[tool.ruff]` → `uv run ruff format --check .`

`[tool.ruff]` gates both ruff commands: a project that configures ruff at all gets lint and format,
because they are one tool reading one config. `[tool.ruff.lint]` implies `[tool.ruff]`.

Report each gate as run, skipped, or failed. A gate that is skipped because the manifest does not
configure it must say so in the §15 summary — a silently-absent typecheck reads as a passing
typecheck, which is how this gate went unnoticed for an entire project.

**No lockfile matched the table.** Do not skip quietly. A toolchain this skill was never taught is
a gap in the skill, and it looks identical to a clean gate run unless it is named. Record it and
surface it in §15 as `Gates: not run — unrecognised toolchain ({what was found at the root})`, then
proceed: §6 still has CI, which is where the gates actually run for a project like this.

Any failure → **stop** with the error output. Re-running after fixes is idempotent.

## 6. Test gate (conditional)

Record the outcome as one of **passed**, **failed**, or **did not run**. §10 reads it, and the three
are not interchangeable there.

### Is there a test Seam?

`CONTEXT.md` defines a **Seam** as the public boundary a test observes behaviour at. Asked of a whole
repository rather than of one behaviour, it becomes: can this skill run a test here at all? Record
the answer as **present** or **absent**, with the reason. §11 reads it to decide what a `weak`
Criterion costs.

One question settles it: **would the local branch below have a command to run?** If it names a test
command for the toolchain §5 detected, the Seam is present. If it reaches "did not run" because
nothing declares a test command, or because §5 matched no lockfile at all, the Seam is absent.

Read it off that branch rather than restating its conditions here. That keeps one list of what counts
as a runnable test command, so adding a toolchain to it cannot leave a second copy behind.

Answer it on every run, including the runs where the CI branch below short-circuits the local one.
They are different questions: CI reports whether the checks it ran passed, and this asks whether a
test command exists that this skill could run.

Record **why** it is absent, because the two reasons are different problems and only one of them is
the author's to fix:

- A toolchain was detected and declares no test command. The repository has not told its toolchain
  how to run tests.
- No lockfile matched §5's table. This skill does not recognise the toolchain, so a repository that
  does run its tests somewhere this skill cannot see reads here as one that does not run them at
  all. Name what was found at the root, the same as §5 does.

The second reason is the weaker of the two, and §13 prints it for that reason: a human who knows the
repository runs tests can then see that this skill did not find them.

If `.github/workflows/` exists with at least one workflow file that runs the project's automated
checks:

- `gh pr view {pr_number} --json statusCheckRollup`
- All `SUCCESS`/`NEUTRAL` → **passed**. Record the CI evidence and proceed.
- Any `PENDING`/`QUEUED` → warn and ask: wait, proceed, or abort? Proceeding records **did not run**,
  because a check still queued has proven nothing.
- Any `FAILURE`/`ERROR` → **failed**, and **stop**.

Otherwise, run the test gate locally for the toolchain §5 detected:

- Node → `{pm} run test` (note: for bun+vitest, this is `bun run test`, not `bun test`). No `test` script → **did not run**.
- `uv` → `uv run pytest -q`, when `pyproject.toml` has `[tool.pytest.ini_options]`. Otherwise → **did not run**.
- No toolchain detected → **did not run**, and say why in §15, the same as §5.

Failure → **stop**.

### Run the `[command]` Criteria

Every `[command]` Criterion from §2 gets one outcome: **passed** with its exit code and the head it
ran on, **failed** with the exit code and the first lines that say why, or **not run** with the
reason. §10 reads it. A failure here does not stop the skill: it makes the Criterion `unverified`,
and §11 blocks on that with the rest of the evidence in the comment.

`{head}` = `git rev-parse --short HEAD`, after confirming it matches the PR's `headRefOid`.

**CI first.** A CI check counts when the workflow file behind it has a step whose `run:` is the
Criterion's command, and the check ran on `{head}`. `SUCCESS` → passed, citing the check's name and
run URL. Anything else, or no such check → run it here.

**Run it here**, from the repository root, exactly as written:

- Print the command before running it. It came from a tracker, not from this skill.
- Run it only when it is read-only, as `CONTRACTS.md` requires. A command that deploys, pushes,
  migrates a shared database or writes outside the checkout → **not run**: `not read-only`. A person
  decides whether that Criterion is `[manual]`.
- Never edit the command to make it pass, and never substitute a near one. A command that does not
  run as written has failed.
- A credential, token or environment variable the command needs that this session lacks → **not
  run**: `needs {what}, which this session does not have`. Do not go looking for one.
- Exit 0 → **passed**. Non-zero, or a timeout → **failed**.
- Exit 0 with output saying the check skipped itself, such as a missing credential → **not run**.
  Exit 0 is the proof only when the check ran.

A `[command]` Criterion with no command (§2) → **not run**: `no command named`.

## 7. Push

`git push origin {branch}`. Stop on failure.

## 8. Capture the Frames

Run `/frames {pr_number}`. It reads `docs/agents/frames.md`, serves the built application on this
Slice's own preview port, captures one Frame per declared `[manual]` Criterion and publishes each to
the `ui-evidence` branch of this repository. `CONTRACTS.md` has the Frame, its name and where it
lands; the skill has the procedure, and this step does not restate either.

Before §9, because the PR body carries the Frames and a body written first would not have them.

Keep what it returns, per Criterion: `captured` with a filename and a URL, `MISSING` with the reason
it failed, or `no frame` where the manifest declares none. Three outcomes are not failures of this
step and are reported in §15 rather than stopping it:

- The repository declares no Frames.
- The Slice owns no `[manual]` Criterion.
- The Slice's Criteria carry no ids, so nothing can bind to a manifest row.

A `MISSING` Frame blocks in §11. Nothing else here does.

## 9. Dispatch PR Writer agent

Look for a project PR-writer agent in `.claude/agents/`. Match on the agent's **role, not its
filename** — a project names its agents for its domain (`ucp-demo-pr-writer`, `gr4ce-pr-writer`), so
read the frontmatter `name`/`description` of each file and pick the one that writes PR
descriptions. Use the Agent tool with `subagent_type` set to that frontmatter `name` and
`prompt: "Write the PR description for PR #{pr_number}."` Wait for completion.

With Frames from §8, the prompt carries them and asks for a `## Screens` section holding one
markdown image per captured Frame: the Criterion's id as the alt text, and the URL §8 returned. A reviewer who can see the change without building it
decides faster than one who reads a description of it, and the images belong in the body rather than
only in the review comment because the body is what survives on the merged pull request.

If there is none: generate a minimal PR body inline, the Criteria list (verbatim from the Slice) plus `Closes #{issue_number}`, and the same `## Screens` section, and update via `gh pr edit {pr_number} --body-file -` from a heredoc.

## 10. Classify every Criterion, and the AI-discipline pass

### The four states

Every Criterion from §2 gets exactly one state, and the state is what was **proven**, not what was
attempted. `CONTRACTS.md` defines the four; this is how to decide between them.

Two inputs:

- **Test names in the diff.** `gh pr diff {pr_number}`, added (`+`) lines only, **in test files
  only**. A Criterion has a test when such a line contains its id as a literal: the bytes `#60 C1`.
  That one rule catches a new test, a `describe` block wrapping several cases, a parametrised case,
  and a Python docstring the runner reports. It also catches an existing test **renamed** to carry
  the id, which the contract accepts as evidence, because a rename appears as an added line holding
  those bytes.

  A **test file** is one the project's own test runner collects. Use the project's layout when it
  has one; otherwise a path with a `test`, `tests`, `spec` or `__tests__` segment, or a basename
  matching `*.test.*`, `*.spec.*`, `*_test.*` or `test_*`.

  Restricting to test files is the whole difference between matching a test and matching a string.
  The id appears in the Slice body, in this skill's own review comment, and in any changelog that
  quotes one; a bare grep over the diff would read a Criterion pasted into a document as proof that
  the behaviour holds, which is the exact confusion these four states exist to end.

  `CONTRACTS.md` words this as a test that **exists**, and the diff is the right place to look for
  it because `gh pr diff` spans base to head, so it holds every commit of the Slice, and a Criterion
  id belongs to exactly one Slice. Where the two readings come apart is a test that already carried
  the id before this branch. Search the test files for the id when the diff does not have it, and
  count that as `verified` too: the contract asks whether the behaviour is proven, not who proved it.
- **The §6 test gate**, as passed, failed (this skill already stopped), or did not run.
- **The §6 command runs**, for `[command]` Criteria, as passed, failed or not run.

| State | When |
| --- | --- |
| `manual` | The Criterion carries `[manual]` |
| `verified` | It carries `[command]` and §6 ran its command to **passed** |
| `unverified` | It carries `[command]` and §6 reports **failed** or **not run** |
| `verified` | An added line **in a test file** carries the id, **and** the §6 test gate passed |
| `weak` | Code in the diff appears to implement it, but no added line carries the id |
| `unverified` | Neither a test carrying the id nor identifiable code in the diff |

Decide top to bottom. The tag decides first: `[manual]` wins over everything, because a tagged
Criterion is one nobody promised to automate, so a test that happens to carry its id does not change
what the human is asked to check. `[command]` is decided by its command alone and is never `weak`:
code that looks right is not a run. An untagged Criterion is `verified`, then `weak` or
`unverified` on whether the diff holds the code.

Cite the evidence for each: `verified` names the test's `path:line` and that the gate was green, or,
for `[command]`, the command, the head it ran on, and who ran it (this skill, or the CI check by name
and URL); a `[command]` `unverified` names the command and its exit code and failing lines, or why it
was not run;
`weak` names the `path:line` that appears to implement it; `unverified` names nothing, which is the
point of the state; `manual` names its Frame from §8, as a filename and a link, and where §8
returned none it names the check the human runs, as it always did.

A Frame does not move a Criterion out of `manual`. It shows that something rendered, which is not
the same as the behaviour holding, and `[manual]` still wins over every other state.

Red-before-green ordering is not checked. A test carrying the id and a green gate is the whole
contract.

**The four states do not depend on the test Seam.** A Criterion with code and no test carrying its
id is `weak` in every repository, whether or not §6 found a runnable test command. §11 decides what
`weak` costs; §10 only decides what is true. Never promote a `weak` Criterion to `verified` because
no test could have carried its id. The state is the one thing telling the reader that the behaviour
was not proven, and a repository that cannot prove it needs that said louder, not quieter.

**A test gate that did not run puts a test's `verified` out of reach.** Every untagged Criterion that
would otherwise have been verified is `weak`, and the evidence line reads `test gate did not run`, never `no test
carries the id`. Those are different failures and only one of them is the author's to fix. §5 and §6
already refuse to report a gate that did not run as a gate that passed; this is that same rule one
step downstream.

### Over-specification

More than ten Criteria on one Slice → **warn**, in the review comment and in §15. Never block on the
count alone. Ten is the threshold above which a Slice is doing too much; that is a fact about the
Slice's size, to be fixed in the tracker, not in this PR.

### AI-discipline pass

Run these inline, not via subagent, since they need Slice context. Load patterns from [references/ai-debris.md](references/ai-debris.md):

- **Scope creep.** Files touched outside the Slice's stated domain (inferred from the issue body + references) → flag.
- **AI-debris pass.** Walk the diff for each pattern in `references/ai-debris.md` (unrequested defensive code, backwards-compat shims for unused paths, tautological comments, stray TODOs, premature abstractions, mock-only tests, `.skip`/`.only`/`xfail` markers).
- **Explicit uncertainty.** Enumerate what couldn't be verified (e.g., behaviour that needs a manual UI check, integration that requires staging credentials). A `manual` Criterion belongs here too, phrased as the check the human runs.

## 11. Combine verdicts

Block if **any** of:

- Any Criterion is `unverified`. Everywhere, in every repository, with no exception below, and a
  `[command]` Criterion whose command failed or was not run is `unverified` like any other. A
  Criterion with no evidence at all is a different kind of thing from one the repository could not
  prove any harder, and keeping this rule absolute is what stops the one below it becoming a way to
  skip evidence.
- Any Criterion is `weak`, **and §6 found the test Seam present**. There, a test could have carried
  the id and nobody wrote it, which is the block this skill was built for.
- Any AI-debris finding is rated blocking
- Any quality gate failed
- Any Frame §8 reported `MISSING`. The manifest declared that this Criterion has a Frame and none
  came back, which is a gate that did not run rather than a judgement about the Criterion. It is
  the same rule as a failed quality gate, applied to the one piece of evidence a `manual` Criterion
  can carry.

Never block on:

- A `manual` Criterion. It is tagged precisely because a person checks it; blocking would make the
  tag mean the opposite of what it means. A Frame does not change that in either direction: a
  Criterion with one is still `manual`, and one whose manifest declares no Frame is not blocked for
  lacking what nobody said it would have.
- More than ten Criteria. That is a warning.
- A `weak` Criterion where §6 found **no test Seam**. This skill has no test command to run there,
  so it cannot hold the author to a test that carries the id, and blocking would ask for something
  the repository cannot give. It is still reported as `weak` (§10), and §13 names this rule and the
  reason the Seam is absent.

**Why the `weak` block is conditional.** A gate that fires on every pull request in a repository
that cannot possibly clear it is not a gate. It is a step people learn to write "Not blocking" past,
and once that habit exists the gate means nothing on the pull request where it was right. Narrowing
it to repositories that can clear it keeps the signal, and it costs nothing where a test Seam
exists, which is where the gate was doing the work.

Blocking is not a dead end. The PR stays a draft, the review comment says which Criterion sits in
which state and on what evidence, and the author either writes the test that carries the id or takes
the Criterion back to the tracker. A human who disagrees can mark the PR ready themselves; this
skill never takes that away from them.

## 12. Tick verified Criteria on the Slice

Tick **only** the `verified` ones, `[command]` included. `weak` is what a tick used to mean, and
ending that reading is why these four states exist; `manual` is the human's to tick once they have
run the check.

**The tick is the only edit.** For each verified Criterion, flip its `- [ ]` to `- [x]` on the exact
line §2 read, and change no other byte: not the text, not the id, not the tag, not the order. What
§2 found wrong with a Criterion goes in §13 and §15, never into this edit.

Write it with `gh issue edit {issue_number} --repo {owner}/{repo} --body-file -`. Then leave a
comment: `gh issue comment {issue_number} --repo {owner}/{repo} --body "PR #{pr_number} verified: …"`
listing each ticked Criterion by id and its evidence: the test that carries it, or the command and
the head it passed on.

`{owner}/{repo}` is the Slice's own, read in §2. Ticking the wrong repository's issue 53 is a write
that succeeds and says something false.

Read the body back and diff it against the body §2 read. The only differences allowed are `[ ]` →
`[x]` on the ticked lines. Anything else means the edit rewrote the Slice: put the §2 body back,
and report it in §15. If nothing is verified, skip the edit and the comment.

## 13. Post the review to the PR

Compose a single review body and post it as a tracked review (never `--approve`):

```
gh pr review {pr_number} --comment --body-file -
```

Body structure:

```
## /finalize-pr review — {Blocking | Not blocking}

### Criteria

- verified    #60 C1 - `test/loyalty/earn.test.ts:14`, test gate green
- manual      #60 C2 - check the cart summary renders "240 points" - [frame](https://github.com/o/r/blob/ui-evidence/pr-64/60-c2-cart-summary-balance.png?raw=true)
- weak        #60 C3 - `src/auth/client.ts:88`, no test carries the id
- unverified  #60 C4 - no test and no code found
- verified    #60 C6 - `uv run python scripts/dry_run.py --target sandbox migrations/ledger.sql` exited 0 on `3f9a2c1`, run by /finalize-pr
- unverified  #60 C7 - `pnpm vendor:check` not run: needs `VENDOR_TOKEN`, which this session does not have

{once per thing §2 found wrong with the Slice; reported, never repaired:}
ⓘ Ids: the Slice's Criteria carry no ids, so no test can be matched to one. Add them on the tracker.
ⓘ Tag: #60 C8 reads as a command ("{its wording}") and carries no tag. Tag it [command] with its
Command: line on the tracker and re-run. This run held it to the untagged rule.
ⓘ Tag: #60 C4 is [command] in the Spec and [manual] on #62. The Spec wins; fix #62.

{when §8 reported a Frame MISSING, once per Criterion:}
✘ #60 C5 - a Frame is declared at `docs/agents/frames.md:9` and none was captured: {reason}. Blocking.

{when §8 did not run, exactly one line saying which of its three reasons applied:}
ⓘ Frames: {not declared in this repository | no [manual] Criterion on this Slice | the Slice's
Criteria carry no ids}.

{when the Slice carries more than ten Criteria:}
⚠ {N} Criteria on one Slice. Above ten, a Slice is usually doing too much. Not blocking.

{when the §6 test gate did not run:}
⚠ The test gate did not run, so no Criterion can reach verified.

{always, exactly one of these two, naming the rule §11 applied and why:}
Rule: `weak` blocks. This repository has a test Seam ({what declares it}), so a test could carry a
Criterion's id.
Rule: `weak` does not block. This repository has no test Seam ({the §6 reason}), so this skill has
no test command to hold a Criterion to. `unverified` still blocks.

### AI-discipline findings
- {pattern name} — `path:line` — {blocking|not} — {why}
- (or "None.")

### Not verified
- {thing the agent couldn't verify} — {how a human can verify it}
```

No code-review or spec-drift section. Both belong to `/review-pr`, which posts its own summary.

Every Criterion the Slice owns appears in `### Criteria` with exactly one state and its evidence.
A Criterion with no state is a bug in §10, not a Criterion to leave out.

The `Rule:` line is not conditional. A review that passed and a review that blocked owe the reader
the same answer: which standard was this held to, and why that one.

## 14. Hand off to `/review-pr` (conditional)

- **Not blocking** → run `/review-pr {pr_number}`, inline in this session. It runs the code and
  security reviews, marks the PR ready if neither blocks, hands it to Copilot and an Auto-fix
  session, and posts its own summary. Do not mark the PR ready here, and do not background the
  hand-off: the session that owns the worktree is the one that can fix what the review finds.
- **Blocking** → do not invoke `/review-pr`. The PR must be a draft: if an earlier `/review-pr`
  marked it ready, return it with `gh pr ready {pr_number} --undo` and read
  `gh api "repos/{owner}/{repo}/pulls/{pr_number}" --jq '.draft'` back as `true`. A PR failing its
  Criteria must not stay ready, because `/merge-pr`'s draft gate is what stops it landing. If
  `python3 <this skill dir>/../../scripts/merge-gate.py --pr {pr_number}` names an
  `.autofix.session`, tell it to stop, so it does not keep pushing onto a PR that fails its Criteria:
  `claude -p "PR #{pr_number} is back to draft. Push nothing more until /review-pr hands it back." --cloud {session} --output-format json`.
  Print the fix list locally; do not post additional GitHub noise.

## 15. Local summary

Name the worktree when running in one, so the PR traces back to the tree that produced it and the
human knows what is still on disk. `git rev-parse --show-toplevel` gives the path; omit the
`Worktree:` line when it is the main checkout.

```
/finalize-pr — {Complete | Blocked}

PR:       #{pr_number} — {pr_title}
URL:      {pr_url}
Branch:   {branch}
Slice:    #{issue_number}
Spec:     {#60 {its title} | lone Slice, no Spec | #60 named, not a Spec | #60 named, a legacy pointer; run spec.py migrate 60 | Specs off, per docs/agents/workflow.md}
Criteria: {V} verified, {W} weak, {M} manual, {U} unverified   (of {N})
Worktree: {path}

Gates:    lint ✓  typecheck ✓  format ✓  test {✓|CI|—}   (— = the project does not configure it)
Seam:     {present ({what declares it}), `weak` blocks | absent ({the §6 reason}), `weak` does not block}
Review:   {Not blocking, handed to /review-pr ({its outcome}) | Blocking — see above, /review-pr not run}

{warnings, one per line, when they apply:}
⚠ {N} Criteria on one Slice, above ten. Not blocking.
⚠ The test gate did not run, so no Criterion can reach verified.
⚠ The Slice's Criteria carry no ids, so no test can be matched to one.
⚠ {one per §2 tag finding, as in §13}. Not changed on the tracker; fix it there.
⚠ The §12 edit changed more than the ticks and was reverted.

Next: {what /review-pr's summary said to do next | Fix the items above and re-run /finalize-pr}
```

The session and its worktree stay alive after this skill finishes. `/merge-pr` and `/merge-stack`
tear them down once the PR lands; nothing here should remove either.

## Rules

- Steps run sequentially. Step 9 depends on Step 8's Frames. Step 14 depends on Step 11's verdict.
- Never `--approve`; this skill writes context, the human pulls the merge trigger.
- Never mark the PR ready. `/review-pr` is the only skill that does.
- Re-running is safe: gates are stateless, and the PR body and issue body overwrite cleanly. Each run posts a new review comment, and a Not blocking run posts a new `/review-pr` summary too.
- Don't modify source files. The PR-writer agent may modify the PR body; the AI-discipline pass never touches code.
- If you stop, surface why and what to run next.
- A gate that did not run is never reported as a gate that passed. Whether it was a tool the project does not configure or a toolchain this skill does not know, §15 names it.
- `verified` is the only state that means the behaviour holds. Never report a Criterion verified on diff evidence alone: that is `weak`, and the distinction is the whole point of this skill.
- `weak` is reported as `weak` in every repository. The test Seam changes what `weak` costs in §11, never what §10 calls it.
- `unverified` blocks everywhere. No test Seam is a reason to hold `weak` to a lower bar; it is never a reason to accept a Criterion with no evidence at all.
- A GitHub write that returns success is not evidence it took effect. §1, §12 and §14 say what to read back.
- Read the Slice from the repository `closingIssuesReferences` names, never from the one holding the pull request. Every `gh issue` call in this skill passes `--repo`.
- A Frame never moves a Criterion out of `manual`. A declared Frame that did not get captured blocks, and that is a gate, not a state.
- A `[command]` Criterion is `verified` only when its command, as written, exited 0 on this head. Failed, skipped or not run is `unverified` and blocks. A command needing a credential this session lacks is reported as not run, never as passed.
- Never edit a Criterion's text, id or tag on the Slice. §12 ticks verified checkboxes and nothing else. A missing id or a tag that looks wrong is reported in §13 and §15 for a person to fix.

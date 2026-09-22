---
name: finalize-pr
description: Drive a Slice PR to ready-for-human-review from its worktree. Reads the linked Slice and its Spec, auto-detects PM, runs quality gates, reports every Criterion as verified, weak, manual or unverified, dispatches PR-writer and code-reviewer agents with a spec-drift question, performs AI-discipline checks, ticks verified Criteria on the issue, posts the review via `gh pr review --comment`, and marks the PR ready when not blocking. Use when the user says "/finalize-pr", "submit PR", "ready for review", or finishes a TDD cycle on a Slice.
---

# Finalize PR

Drive a Slice's PR to "ready for human review" with a review comment that says what was actually
proven, and ticked Criteria on the Slice.

## Input

`$ARGUMENTS`: a PR number (`42` or `#42`). If empty, detect from the current branch.

## The shapes this skill reads and writes

`CONTRACTS.md` at the repo root. The Slice body, the Spec file, the Criterion grammar, the test
name that proves a Criterion, and the four states this skill reports are all defined there. Read it
before changing anything below, and read it instead of this skill when you want to hand-write a
Slice that this skill accepts.

Sections a Slice is missing are skipped rather than fatal, with the exceptions §2 names.

## 1. Pre-flight

- `{branch}` = `git branch --show-current`. If it's the default branch (`gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'`), **stop**.
- `git status --porcelain` — if non-empty, **stop**: commit or stash first.
- Find/create the PR:
  - With arg: `gh pr view {number} --json number,title,url,isDraft,headRefName,closingIssuesReferences,mergeStateStatus`. If `headRefName != {branch}`, stop.
  - Without arg: `gh pr list --head {branch} --json … --limit 1`. If none, create a draft: `gh pr create --draft --title "{branch}" --body "Work in progress"` and capture the new number/URL.
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

For each issue number in `closingIssuesReferences` (usually just one): `gh issue view {number} --json title,body,labels` and parse, per `CONTRACTS.md`:

- `## Parent` → `{spec_issue}`, or absent on a lone Slice
- `## Acceptance criteria` → the Slice's Criteria, one per checkbox, as `{ index, id, text, checked }`. Track index positions for ticking in §12.
- `## References for context` → repo-relative paths

If no issue is linked, skip parsing and note in the review comment that no Slice was found.

If GitHub reports no linked issue, parse the PR body for `Closes|Fixes|Resolves #(\d+)` —
`/start-issue` writes `Closes #{n}` as its first line. Note in the §15 summary when the link came
from the body rather than from GitHub's own linkage, since a hand-edited body could have dropped it.

### The id on each checkbox

`{id}` is the cited form — `#60 C1`, one space — at the head of the checkbox text. Three cases:

| What the checkbox carries | `{id}` | Where the Criterion's full text lives |
| --- | --- | --- |
| `#60 C1 …`, with `## Parent` naming `#60` | `#60 C1` | the Spec file, section `### C1` |
| `#74 C1 …` on a lone Slice, `#74` being its own number | `#74 C1` | the checkbox itself |
| no id at all | none | the checkbox itself |

The third case is a Slice written before Criterion ids existed, or written by hand without them. It
is not an error and it is not a free pass: an uncited checkbox is still a Criterion and still runs
the §10 gate. Having no id, no test can carry it, so it can reach only `weak` or `unverified`. Say
in §15 that the Slice carries no ids, because that, and not the missing test, is the thing to fix.

### The Spec file

When `## Parent` names a Spec issue, find `docs/specs/{spec_issue}-*.md` on this branch and read its
`## Criteria` section: the full Given/When/Then for each cited id, and whether it carries `[manual]`.

**The file wins.** When the Spec file and the Slice checkbox disagree on a Criterion's text or its
`[manual]` tag, the file is right and the checkbox is stale.

No Spec file for a named Parent → note it once and fall back to the checkbox text, as for a lone
Slice. A Parent pointing at a Spec nobody anchored is worth saying out loud; it is not worth
stopping for.

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

## 7. Push

`git push origin {branch}`. Stop on failure.

## 8. Dispatch PR Writer agent

Look for a project PR-writer agent in `.claude/agents/`. Match on the agent's **role, not its
filename** — a project names its agents for its domain (`ucp-demo-pr-writer`, `gr4ce-pr-writer`), so
read the frontmatter `name`/`description` of each file and pick the one that writes PR
descriptions. Use the Agent tool with `subagent_type` set to that frontmatter `name` and
`prompt: "Write the PR description for PR #{pr_number}."` Wait for completion.

If there is none: generate a minimal PR body inline — the Criteria list (verbatim from the Slice) plus `Closes #{issue_number}` — and update via `gh pr edit {pr_number} --body @-` from a heredoc.

## 9. Dispatch the code reviewer, with the drift question

### Pick the candidate implemented Specs

A Spec names no file paths (`CONTRACTS.md` says why), so the Specs this diff might have drifted from
are found by a cheap heuristic rather than a lookup:

1. Take `docs/specs/*.md` whose `**Status:**` is `implemented`. A Spec still in progress is being
   built, not drifted from.
2. Take the changed paths: `gh pr diff {pr_number} --name-only`.
3. Keep a Spec when a word of its slug, or a `CONTEXT.md` **Language** term its Criteria use,
   appears in a changed path. Match whole words, not substrings: `cart` matches `src/cart/summary.ts`
   and not `src/descartes.ts`.
4. Drop the Spec this Slice's `## Parent` points at. Its behaviour is what the diff is meant to change.

Cheap on purpose. It over-selects, the reviewer discards what does not apply, and the finding is
advisory either way. An exact answer would need file paths inside Specs, which is the thing
`CONTRACTS.md` forbids.

### With a project code-reviewer agent

Look for one in `.claude/agents/` the same way as §8 — by role, not filename
(`ucp-demo-code-reviewer`, `gr4ce-code-reviewer`). Launch it with sentinel-line gating.
Prompt:

```
Review PR #{pr_number}.

These Specs describe behaviour that already ships:

{one line per candidate: `docs/specs/60-loyalty-earn-and-burn.md` — {its title}}
{or, with no candidates: "No implemented Specs match the changed paths."}

Flag any behaviour this diff changes that one of those Specs describes, where that Spec was
not itself edited in this diff. Report each as:

spec-drift: {spec file} — {the behaviour} — {path:line}

These drift findings are advisory. Do not count them in CRITICAL_COUNT or HIGH_COUNT, and do
not let them change VERDICT.

After your review report, append these exact sentinel lines at the very end of your response (outside of any markdown code blocks):

VERDICT: approved
CRITICAL_COUNT: 0
HIGH_COUNT: 0

OR if there are Critical or High findings:

VERDICT: changes_requested
CRITICAL_COUNT: <number>
HIGH_COUNT: <number>

VERDICT must be "approved" only if both counts are 0.
```

Parse the sentinels. If absent, **stop** and report the malformed response.

Say "no implemented Specs match" explicitly rather than dropping the paragraph: a reviewer told
there is nothing to drift from answers differently from a reviewer told nothing at all.

### With no project code-reviewer agent

Invoke Pocock's `code-review` skill through the Skill tool, `skill: "mattpocock-skills:code-review"`,
with the merge-base as its fixed point: `git merge-base origin/{default} HEAD`. Name the candidate
Specs above as its spec source, and pass the same drift instruction.

Its two axes are the two things the missing agent would have done: **Spec** is this drift check, and
**Standards** is the architectural pass. It returns findings rather than sentinels, so:

- Its **Spec**-axis findings go into `### Spec drift (advisory)` in §13, each naming the Spec and the
  behaviour, the same as an agent's `spec-drift:` lines. Advisory, like any other drift finding.
- Its **Standards**-axis Critical and High findings count the way §11 counts `changes_requested`.
- §13's `### Code-reviewer verdict` names `code-review` as the reviewer that ran, so a reader of the
  PR knows which one produced the findings.

This is what a repo with no reviewer agent gets instead of the note that nothing was enforced.

## 10. Classify every Criterion, and the AI-discipline pass

### The four states

Every Criterion from §2 gets exactly one state, and the state is what was **proven**, not what was
attempted. `CONTRACTS.md` defines the four; this is how to decide between them.

Two inputs:

- **Test names in the diff.** `gh pr diff {pr_number}`, added (`+`) lines only. A Criterion has a
  test when an added line contains its id as a literal — the bytes `#60 C1`. That one rule catches a
  new test, a `describe` block wrapping several cases, a parametrised case, and a Python docstring
  the runner reports. It also catches an existing test **renamed** to carry the id, which the
  contract accepts as evidence, because a rename appears as an added line holding those bytes.
- **The §6 test gate**, as passed, failed (this skill already stopped), or did not run.

| State | When |
| --- | --- |
| `verified` | An added line carries the id, **and** the §6 test gate passed |
| `manual` | The Criterion carries `[manual]` |
| `weak` | Code in the diff appears to implement it, but no added line carries the id |
| `unverified` | Neither a test carrying the id nor identifiable code in the diff |

Decide in that reading order with one exception: `[manual]` wins over everything. A tagged Criterion
is one nobody promised to automate, so a test that happens to carry its id does not change what the
human is asked to check. After that, `verified`; then `weak` or `unverified` on whether the diff
holds the code.

Cite the evidence for each: `verified` names the test's `path:line` and that the gate was green;
`weak` names the `path:line` that appears to implement it; `unverified` names nothing, which is the
point of the state.

Red-before-green ordering is not checked. A test carrying the id and a green gate is the whole
contract.

**A test gate that did not run puts `verified` out of reach.** Every Criterion that would otherwise
have been verified is `weak`, and the evidence line reads `test gate did not run`, never `no test
carries the id`. Those are different failures and only one of them is the author's to fix. §5 and §6
already refuse to report a gate that did not run as a gate that passed; this is that same rule one
step downstream.

### Over-specification

More than ten Criteria on one Slice → **warn**, in the review comment and in §15. Never block on the
count alone. Ten is the threshold above which a Slice is doing too much; that is a fact about the
Slice's size, to be fixed in the tracker, not in this PR.

### AI-discipline pass

Run these inline (not via subagent — they need Slice context). Load patterns from [references/ai-debris.md](references/ai-debris.md):

- **Scope creep.** Files touched outside the Slice's stated domain (inferred from the issue body + references) → flag.
- **AI-debris pass.** Walk the diff for each pattern in `references/ai-debris.md` (unrequested defensive code, backwards-compat shims for unused paths, tautological comments, stray TODOs, premature abstractions, mock-only tests, `.skip`/`.only`/`xfail` markers).
- **Explicit uncertainty.** Enumerate what couldn't be verified (e.g., behaviour that needs a manual UI check, integration that requires staging credentials). A `manual` Criterion belongs here too, phrased as the check the human runs.

## 11. Combine verdicts

Block if **any** of:

- Any Criterion is `weak` or `unverified`
- The code-reviewer returned `changes_requested`, or the `code-review` fallback returned Critical or High findings
- Any AI-debris finding is rated blocking
- Any quality gate failed

Never block on:

- A `manual` Criterion. It is tagged precisely because a person checks it; blocking would make the
  tag mean the opposite of what it means.
- A spec-drift finding. It is a question for the human, and the heuristic that raised it
  over-selects by design.
- More than ten Criteria. That is a warning.

Blocking is not a dead end. The PR stays a draft, the review comment says which Criterion sits in
which state and on what evidence, and the author either writes the test that carries the id or takes
the Criterion back to the tracker. A human who disagrees can mark the PR ready themselves; this
skill never takes that away from them.

## 12. Tick verified Criteria on the Slice

Tick **only** the `verified` ones. `weak` is what a tick used to mean, and ending that reading is
why these four states exist; `manual` is the human's to tick once they have run the check.

For each verified Criterion, edit the issue body via `gh issue edit {issue_number} --body @-` to flip
the corresponding `- [ ]` → `- [x]`. Replace by exact line match (don't restructure the body). Then
leave a comment: `gh issue comment {issue_number} --body "PR #{pr_number} verified: …"` listing each
ticked Criterion by id and the test that carries it.

If nothing is verified, skip the edit and the comment.

## 13. Post the review to the PR

Compose a single review body and post it as a tracked review (never `--approve`):

```
gh pr review {pr_number} --comment --body @-
```

Body structure:

```
## /finalize-pr review — {Blocking | Not blocking}

### Criteria

- verified    #60 C1 — `test/loyalty/earn.test.ts:14`, test gate green
- manual      #60 C2 — check the cart summary renders "240 points"
- weak        #60 C3 — `src/auth/client.ts:88`, no test carries the id
- unverified  #60 C4 — no test and no code found

{when the Slice carries more than ten Criteria:}
⚠ {N} Criteria on one Slice. Above ten, a Slice is usually doing too much. Not blocking.

{when the §6 test gate did not run:}
⚠ The test gate did not run, so no Criterion can reach verified.

### Spec drift (advisory)

- `docs/specs/60-loyalty-earn-and-burn.md` — {behaviour the diff changes} — `path:line`
- (or "None." / "No implemented Specs match the changed paths.")

### AI-discipline findings
- {pattern name} — `path:line` — {blocking|not} — {why}
- (or "None.")

### Not verified
- {thing the agent couldn't verify} — {how a human can verify it}

### Code-reviewer verdict
{reviewer that ran: the project agent's name, or `code-review`}: {summary line}.
Full report posted as a separate PR comment.
```

Every Criterion the Slice owns appears in `### Criteria` with exactly one state and its evidence.
A Criterion with no state is a bug in §10, not a Criterion to leave out.

Then post the full code-reviewer report as a separate PR comment: `gh pr comment {pr_number} --body @-` (keeps the review compact).

## 14. Mark PR ready (conditional)

- Not blocking → `gh pr ready {pr_number}`, then **verify**:
  `gh api "repos/{owner}/{repo}/pulls/{pr_number}" --jq '.draft'` must be `false`. If it still
  reads `true`, stop and report — `/merge-pr` hard-stops on drafts, so a PR that silently stayed a
  draft is a PR nobody can land.

  Then **offer auto-fix**: tell the user they can run `/autofix-pr` on this branch to have Claude
  watch the PR and respond to CI failures and review comments without anyone reopening the
  session. Offer it; don't run it — it subscribes to GitHub activity and can push commits and
  reply to reviewers under the user's account, which is theirs to opt into.
- Blocking → keep draft. Print the fix list locally; do not post additional GitHub noise.

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
Spec:     {docs/specs/60-….md | lone Slice, no Spec | #60 named, no Spec file found}
Criteria: {V} verified, {W} weak, {M} manual, {U} unverified   (of {N})
Worktree: {path}

Gates:    lint ✓  typecheck ✓  format ✓  test {✓|CI|—}   (— = the project does not configure it)
Review:   {Not blocking | Blocking — see above}

{warnings, one per line, when they apply:}
⚠ {N} Criteria on one Slice — above ten. Not blocking.
⚠ The test gate did not run — no Criterion can reach verified.
⚠ The Slice's Criteria carry no ids — no test can be matched to one.

Next: {Share PR URL with reviewers | Fix the items above and re-run /finalize-pr | Mark the PR ready, then share it}
```

The session and its worktree stay alive after this skill finishes. `/merge-pr` and `/merge-stack`
tear them down once the PR lands; nothing here should remove either.

## Rules

- Steps run sequentially. Step 9 depends on Step 8's PR description. Steps 10–13 depend on Step 9's verdict.
- Never `--approve`; this skill writes context, the human pulls the merge trigger.
- Re-running is idempotent: gates are stateless, the PR body / review comment / issue body overwrite cleanly.
- Don't modify source files. The PR-writer agent may modify the PR body; the AI-discipline pass never touches code.
- If you stop, surface why and what to run next.
- A gate that did not run is never reported as a gate that passed. Whether it was a tool the project does not configure or a toolchain this skill does not know, §15 names it.
- `verified` is the only state that means the behaviour holds. Never report a Criterion verified on diff evidence alone — that is `weak`, and the distinction is the whole point of this skill.
- A GitHub write that returns success is not evidence it took effect. §1, §12 and §14 say what to read back.

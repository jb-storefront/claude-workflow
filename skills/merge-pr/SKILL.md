---
name: merge-pr
description: Squash-merge an approved PR, tear down its worktree, its session and its Auto-fix session, and delete the branch. Hard-gates on review approval and on a /review-pr summary that names the head; soft-gates on CI and on Copilot being clean; warns on BEHIND/DIRTY merge state and recommends /rebase-pr. Use when the user says "/merge-pr", "merge this PR", or wants to land an approved PR.
---

# Merge PR

Squash-merge an approved PR, then clean up what built it. For a *set* of finished PRs, use
`/merge-stack`, which owns ordering and cross-PR conflicts; this skill handles one.

## Input

`$ARGUMENTS`: a PR number (`42` or `#42`). If empty, detect the PR from the current branch.

## 1. Pre-flight

- `git status --porcelain` — if non-empty, **stop**: commit or stash first.
- `{branch}` = `git branch --show-current`
- `{default_branch}` = `gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'`
- Find the PR:
  - With arg: `gh pr view {number} --json number,title,url,state,isDraft,headRefName,headRefOid,reviewDecision,statusCheckRollup,closingIssuesReferences`
  - Without arg: `gh pr list --head {branch} --json … --limit 1`. If none, stop.
- Validate state: `MERGED` → stop (no-op); `CLOSED` → stop; `isDraft=true` → **stop** ("Run `/review-pr {number}`; it marks the PR ready when its review does not block.").
- **Locate the branch's worktree.** `git worktree list --porcelain` → `{wt}` for `{headRefName}`,
  and `claude agents --json` → the session `id` and `state` whose `cwd` is `{wt}`. A slice built by
  `/dispatch-slices` has both; a PR written by hand has neither. §5 needs them, and it is worth
  knowing before the merge whether a session is still running against this branch.

## 2. Merge readiness

### 2a. Review approval (hard gate)

Check `{review_decision}`:
- `APPROVED` → proceed.
- `CHANGES_REQUESTED` → **stop**: address feedback first.
- `REVIEW_REQUIRED` → **stop**: get a review first.
- Empty/null → proceed with note: "No review policy configured." This is the *expected* state in this workflow, because `/finalize-pr` posts `--comment` reviews and never `--approve`.

### 2b. The reviewed head (hard gate)

`/review-pr` reviews one head, marks the PR ready and hands it to an Auto-fix session, which keeps
pushing fixes for Copilot's comments. Copilot is the only reviewer those commits meet. The latest
`/review-pr` summary's `Head:` line is the record of what the code reviewer and the security
reviewer saw, so ask the gate rather than reading the comments by eye:

```bash
python3 <this skill dir>/../../scripts/merge-gate.py --pr {pr_number} > {gate.json}
```

Exit 2 → **stop** and relay its `✘` line: a gate that could not run has not passed. Otherwise read
`.reviewed.state`:

- `fresh` → proceed.
- `stale` → **stop**: "Commits landed after `/review-pr` reviewed `{.reviewed.head}`. Run
  `/review-pr {number}` on the new head, then merge." This is the gate the Auto-fix session's
  commits pass through; never offer to merge past it.
- `blocked` → **stop**: the latest summary is `Draft` on this head. Its `### Blocking findings` say why.
- `none` → **warn**: "No `/review-pr` summary on this PR, so nothing records a review of its code."
  Ask: attempt anyway or abort? A PR opened by hand outside the workflow has none; one built by
  `/dispatch-slices` should never be here.

Keep `{.autofix.session}` for §5.

### 2c. Copilot and CI (soft gate)

`.copilot` is [clean-predicate.py](../../scripts/clean-predicate.py)'s verdict on the same snapshot.
It reads the checks as well as Copilot's threads, so a failing or running check shows up here as one
of its reasons, and there is no separate CI step.

- `clean` → proceed.
- `pending` → **warn** with its reasons (a Copilot pass on its way, a running check) and ask: wait,
  attempt, or abort?
- `not-clean` → **warn**, listing each reason: open threads with their URLs, a failing check, a
  Copilot pass on an older commit, or no pass at all. Ask: attempt anyway or abort? It is a warning,
  not a stop, so that a human can approve over a thread they have read and disagree with.

### 2d. Merge state

`gh pr view {pr_number} --json mergeStateStatus --jq '.mergeStateStatus'`:
- `CLEAN` / `HAS_HOOKS` → proceed.
- `BEHIND` → **warn**: "Branch is behind `{default_branch}`. Run `/rebase-pr`, then re-run `/finalize-pr`, before merging." Ask: attempt anyway or abort?
- `DIRTY` / `UNKNOWN` → **warn**: "Merge conflicts detected. Run `/rebase-pr` to resolve, then `/finalize-pr`." Ask: attempt anyway or abort?

## 3. Confirm

Print the pre-merge summary and ask **"Proceed with merge? This is not easily reversible."**
Stop if the user declines.

```
/merge-pr — Pre-merge

PR:       #{pr_number} — {pr_title}
URL:      {pr_url}
Branch:   {head_ref}
Worktree: {wt or "none"}  {session id and state, if any}
Review:   {review_decision or "No reviews configured"}
Reviewed: {head, first 7} by /review-pr {| none — confirmed above}
Copilot:  {clean | pending | not-clean — confirmed above}
Auto-fix: {session id | none}
CI:       {All passed | Failing | Pending}
Issues:   {linked_issues or "none"}
Action:   Squash merge {head, first 7} → {default_branch}, stop Auto-fix, stop session, remove worktree, delete branch
```

## 4. Squash merge

`gh pr merge {pr_number} --squash --delete-branch --match-head-commit {headRefOid}`

`--match-head-commit` makes GitHub refuse the merge if the head moved after §1 read it. The
Auto-fix session is still watching at this point, and a fix it pushes between the gate and the merge
would otherwise land unreviewed. A refusal for that reason means: re-run `/merge-pr`, which reads the
new head and stops at §2b until `/review-pr` has seen it.

On failure: stop and report. Never retry automatically. Never `--admin`.

## 5. Teardown (each step non-fatal — warn on failure, except where it says pause)

A slice branch is pinned to its worktree: `git branch -D` fails with *"cannot delete branch … used
by worktree at …"* until the worktree is gone, and `git worktree remove` refuses while Claude Code
holds its lock for a running session. So the order is fixed — stop, remove, delete:

- **Stop the Auto-fix session** named in §2b, if there is one:

  ```bash
  claude -p "PR #{pr_number} is merged. Stop watching it, push nothing more, and end." --cloud {session} --output-format json
  ```

  `{"ok": true}` means the message reached it. `ok: false` with an archived or missing session means
  it had already stopped; report it and carry on. A merged PR gets no further review comments, so a
  session that misses this message has nothing left to answer, but it is still told rather than left
  holding a subscription to a closed PR.

- **Stop the session** if `claude agents --json` still shows it running: `claude stop {id}`. Its
  transcript is kept and `claude attach {id}` still opens it.
- **Remove the session and its worktree**: `claude rm {id}`.

  It keeps the worktree instead of removing it in two cases, and only one offers an override.
  Verified on 2.1.263:

  ```
  kept {id} — worktree has uncommitted changes
    worktree kept at {wt}
    resolve that (commit/push, or remove the worktree), then run 'claude rm {id}' again

  kept {id} — 1 unpushed commit on {branch} ({short-sha} {subject})
    worktree: {wt}
    push it, or discard the worktree and its commits: claude rm {id} --discard-unpushed {sha}@{worktree-id}
  ```

  **Do not run either fix.** Show the user what is there — `git -C {wt} status --porcelain` and
  `git -C {wt} log --oneline @{u}..` — and hand over the command the refusal printed. The PR is
  already merged at this point, so nothing is blocked by leaving the worktree in place; discarding
  someone's work to tidy up is not a trade this skill gets to make.

  If the worktree exists but no session owns it any more, `git worktree remove {wt}` does the same
  job. If git says it is locked, the session that held it was killed; Claude Code's periodic sweep
  releases such locks, and `git worktree unlock {wt}` forces it now.
- **Prune the worktree's plugin records**, only once `{wt}` is gone from disk:

  ```bash
  python3 <this skill dir>/../../scripts/prune-plugin-entries.py {wt}
  ```

  Every session started in a worktree records a plugin install keyed by its path, and removing the
  worktree leaves those records behind, so without this `claude plugin list` grows by a few lines
  per Slice forever. The script ([prune-plugin-entries.py](../../scripts/prune-plugin-entries.py))
  refuses a path still on disk, so a kept worktree keeps its records. Skip this step when there was
  no worktree.
- **Sync the local view**: `git fetch origin {default_branch} --prune`; if currently on
  `{default_branch}`, also `git pull origin {default_branch}`.
- **Delete the local branch** if it exists (`git branch --list {head_ref}`) and is not checked out:
  `git branch -D {head_ref}`. `-D` rather than `-d` is required — a squash merge rewrites the
  commits, so `-d` always refuses. If `{head_ref}` *is* the current branch, `git switch
  {default_branch}` first.

## 6. Spec close-out

A merged Slice can be the last one a Spec was waiting on, and when it is, the feature is finished
and the Spec has to say so. Run the procedure in
[../../references/spec-close-out.md](../../references/spec-close-out.md), handing it the
`closingIssuesReferences` recorded in §1.

That procedure decides for itself whether anything is due. A merge that closed no Slice, a Slice
with no parent Spec, and a Spec with other Slices still open each leave the Spec issue exactly as
it was.

Marking the Spec `implemented` and closing its issue are issue edits, so they run from anywhere. A
command-form Verification is the exception: it runs on a fresh default-branch tree, which means the
main checkout, because that branch is checked out there. Running `/merge-pr` from inside a slice's
worktree is otherwise fine and stays fine. When a command-form Verification is due there, the
close-out has already written `implemented`, and it pauses and reports which Spec is waiting so you
can run its Verification from the main checkout.

## 7. Summary

```
/merge-pr — Complete

PR:       #{pr_number} — {pr_title}  [MERGED]
Branch:   {head_ref}  [DELETED on remote{, and locally}]
Worktree: {removed | kept — holds unpushed work, see above | none}
Auto-fix: {stopped | already stopped | none}
Issues:   {linked_issues or "none"}  [CLOSED]
Spec:     {#60 closed out — see below | #60 still has 2 Slices open | none}
```

A Spec that closed out prints its own block after this one, and a walkthrough Verification after
that, per §6's procedure.

## Rules

- Squash merge only. Never merge commits or rebase merges.
- Never `--admin`. Never retry a failed merge.
- Always confirm in step 3.
- Empty `reviewDecision` is normal here, not a blocker — `/finalize-pr` deliberately never approves.
- Never merge a head the latest `/review-pr` summary does not name, and always pass
  `--match-head-commit`, so the head that merges is the head that was reviewed.
- Copilot being clean is a warning, not a gate: a human may approve over an open thread deliberately.
- Stop the session before removing its worktree, and remove the worktree before deleting the branch.
- Never discard a worktree's uncommitted changes or unpushed commits. `--discard-unpushed` and `git worktree remove --force` are the human's to run; report the command, don't run it.

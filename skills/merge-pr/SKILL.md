---
name: merge-pr
description: Squash-merge an approved PR, tear down its worktree and session, and delete the branch. Hard-gates on review approval; soft-gates on CI; warns on BEHIND/DIRTY merge state and recommends /rebase-pr. Use when the user says "/merge-pr", "merge this PR", or wants to land an approved PR.
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
  - With arg: `gh pr view {number} --json number,title,url,state,isDraft,headRefName,reviewDecision,statusCheckRollup,closingIssuesReferences`
  - Without arg: `gh pr list --head {branch} --json … --limit 1`. If none, stop.
- Validate state: `MERGED` → stop (no-op); `CLOSED` → stop; `isDraft=true` → **stop** ("Mark it ready with `gh pr ready {number}` first.").
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

### 2b. CI checks (soft gate)

Inspect `statusCheckRollup`:
- All `SUCCESS`/`NEUTRAL` (or empty) → proceed.
- Any `FAILURE`/`ERROR` → **warn** (branch protection may block) and ask: attempt anyway or abort?
- Any `PENDING`/`QUEUED` → **warn** and ask: wait, attempt, or abort?

### 2c. Merge state

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
CI:       {All passed | Failing | Pending}
Issues:   {linked_issues or "none"}
Action:   Squash merge → {default_branch}, stop session, remove worktree, delete branch
```

## 4. Squash merge

`gh pr merge {pr_number} --squash --delete-branch`

On failure: stop and report. Never retry automatically. Never `--admin`.

## 5. Teardown (each step non-fatal — warn on failure, except where it says pause)

A slice branch is pinned to its worktree: `git branch -D` fails with *"cannot delete branch … used
by worktree at …"* until the worktree is gone, and `git worktree remove` refuses while Claude Code
holds its lock for a running session. So the order is fixed — stop, remove, delete:

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
- **Sync the local view**: `git fetch origin {default_branch} --prune`; if currently on
  `{default_branch}`, also `git pull origin {default_branch}`.
- **Delete the local branch** if it exists (`git branch --list {head_ref}`) and is not checked out:
  `git branch -D {head_ref}`. `-D` rather than `-d` is required — a squash merge rewrites the
  commits, so `-d` always refuses. If `{head_ref}` *is* the current branch, `git switch
  {default_branch}` first.

## 6. Summary

```
/merge-pr — Complete

PR:       #{pr_number} — {pr_title}  [MERGED]
Branch:   {head_ref}  [DELETED on remote{, and locally}]
Worktree: {removed | kept — holds unpushed work, see above | none}
Issues:   {linked_issues or "none"}  [CLOSED]
```

## Rules

- Squash merge only. Never merge commits or rebase merges.
- Never `--admin`. Never retry a failed merge.
- Always confirm in step 3.
- Empty `reviewDecision` is normal here, not a blocker — `/finalize-pr` deliberately never approves.
- Stop the session before removing its worktree, and remove the worktree before deleting the branch.
- Never discard a worktree's uncommitted changes or unpushed commits. `--discard-unpushed` and `git worktree remove --force` are the human's to run; report the command, don't run it.

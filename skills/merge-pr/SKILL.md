---
name: merge-pr
description: Squash-merge an approved PR, delete the branch, and clean up. Hard-gates on review approval; soft-gates on CI; warns on BEHIND/DIRTY merge state and recommends /rebase-pr. Use when the user says "/merge-pr", "merge this PR", or wants to land an approved PR.
---

# Merge PR

Squash-merge an approved PR and delete its branch. For a *set* of finished PRs, use
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

PR:      #{pr_number} — {pr_title}
URL:     {pr_url}
Branch:  {head_ref}
Review:  {review_decision or "No reviews configured"}
CI:      {All passed | Failing | Pending}
Issues:  {linked_issues or "none"}
Action:  Squash merge → {default_branch}, delete branch
```

## 4. Squash merge

`gh pr merge {pr_number} --squash --delete-branch`

On failure: stop and report. Never retry automatically. Never `--admin`.

## 5. Local catch-up (each step non-fatal — warn on failure)

The work was built in a cloud session, so there is usually nothing checked out locally for this
branch. Sync the local view and remove the branch only if it happens to exist here:

- `git fetch origin {default_branch} --prune`; if currently on `{default_branch}`, also `git pull origin {default_branch}`.
- If `{head_ref}` exists locally (`git branch --list {head_ref}`) and is not checked out: `git branch -D {head_ref}`. `-D` rather than `-d` is required — a squash merge rewrites the commits, so `-d` always refuses.
- If `{head_ref}` *is* the current branch, `git switch {default_branch}` first, then delete.

## 6. Summary

```
/merge-pr — Complete

PR:     #{pr_number} — {pr_title}  [MERGED]
Branch: {head_ref}  [DELETED on remote{, and locally}]
Issues: {linked_issues or "none"}  [CLOSED]
```

## Rules

- Squash merge only. Never merge commits or rebase merges.
- Never `--admin`. Never retry a failed merge.
- Always confirm in step 3.
- Empty `reviewDecision` is normal here, not a blocker — `/finalize-pr` deliberately never approves.

---
name: rebase-pr
description: Rebase the current feature branch onto the latest default branch, mechanically resolve conflicts (additive/disjoint only), and force-push with lease. Use when the user says "/rebase-pr", "rebase this PR", or wants to bring a branch up to date with main. Aborts on semantic conflicts.
---

# Rebase PR

Rebase the current feature branch onto the latest default branch and push.

## Input

`$ARGUMENTS`: a PR number (`42` or `#42`). If empty, detect the PR from the current branch.

## 1. Pre-flight

- `git status --porcelain` — if non-empty, **stop**: uncommitted changes must be committed or stashed first.
- `{branch}` = `git branch --show-current`
- `{default_branch}` = `gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'`
- If `{branch}` == `{default_branch}`, **stop** — switch to a feature branch first.
- Find the PR:
  - With arg: `gh pr view {number} --json number,title,url,state,headRefName`. If `headRefName != {branch}`, stop.
  - Without arg: `gh pr list --head {branch} --json number,title,url,state,headRefName --limit 1`. If none, stop.
- If `{state}` is `MERGED`, stop (no-op). If `CLOSED`, stop with an error.

## 2. Fetch and preview

- `git fetch origin {default_branch}`
- `git merge-base --is-ancestor origin/{default_branch} HEAD` — if exit 0, branch is already current; print the "Already up to date" summary and stop.
- Show what will replay: `git log --oneline origin/{default_branch}..HEAD` → `{commits_to_rebase}`
- Show what's incoming: `git log --oneline HEAD..origin/{default_branch}` → `{incoming_commits}`

## 3. Rebase

`git rebase origin/{default_branch}`. If clean, set `{conflicts_resolved}=0` and go to step 4. Otherwise:

### Conflict-resolution loop (mechanical only)

Repeat per rebase step that produces conflicts:

1. `git diff --name-only --diff-filter=U` → conflicting files.
2. For each file, read it and inspect markers (`<<<<<<<`, `=======`, `>>>>>>>`). Resolve **only** when the conflict is mechanical:
   - both sides add non-overlapping code, **or**
   - one side is a strict superset, **or**
   - changes are in clearly independent sections.
   Otherwise (both sides modify the same logic, semantic conflict requiring domain reasoning): `git rebase --abort` and **stop** with the list of unresolvable files. The branch is restored.
3. After resolving all files this step: `git add` them, increment `{conflicts_resolved}`, then `git rebase --continue`. If new conflicts arise on the next commit, repeat from 1.

## 4. Push

`git push origin {branch} --force-with-lease`. Never `--force`. Stop on failure.

Verify the PR is still open: `gh pr view {pr_number} --json state --jq '.state'`. If not `OPEN`, warn.

## 5. Summary

Print one of three variants:

```
/rebase-pr — {Complete | Complete (conflicts resolved) | No Changes}

PR:              #{pr_number} — {pr_title}
URL:             {pr_url}
Branch:          {branch}
Rebased onto:    origin/{default_branch}    (omit on No Changes)
Commits rebased: {commits_to_rebase}        (omit on No Changes)
Conflicts:       {none | {N} resolved}      (omit on No Changes)

Next: /finalize-pr to validate the rebased code.
```

## Rules

- Never `git push --force`. Always `--force-with-lease`.
- Never continue a rebase with unresolvable conflicts — abort and leave the branch unchanged.
- Never run quality checks or modify PR metadata; that's `/finalize-pr`'s job.
- Idempotent — safe to re-run; if already up to date, prints the no-op summary.

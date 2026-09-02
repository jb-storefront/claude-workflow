---
name: merge-stack
description: Squash-merge a SET of in-flight PRs in the correct order, handling stacked PRs and cross-PR conflicts. Auto-derives the order (stacking from base refs, overlap from changed files), confirms once, then runs unattended — pausing only on conflict, CI failure, or unexpected state. Use when the user says "/merge-stack", "merge these PRs", "merge the stack", or "land these PRs in order".
---

# Merge Stack

Land several finished PRs — the output of a parallel `/dispatch-slices` fan-out — onto the
default branch in the right order.

This is the capstone of the `/grill-with-docs` → `/to-spec` → `/to-tickets` → `/dispatch-slices`
→ `/tdd` → `/finalize-pr` → **`/merge-stack`** pipeline: `finalize-pr` deliberately defers the
merge to a human, and this skill performs it for a whole batch at once.

It reuses `/merge-pr`'s readiness gates (review / CI / merge-state) per PR and owns what a
single-PR merge has no concept of: ordering, stacked-PR retarget/rebase, and cross-PR conflicts.

## Concepts (why a batch needs more than N single merges)

1. **Order** — derived from real conflict relationships, not arbitrary.
2. **Stacked PRs** (`base != default`) — the base PR must land first; the dependent is then
   retargeted onto the default branch.
3. **Cross-PR conflicts** — PRs that touch the same file on adjacent lines need the *later* one
   rebased, sometimes with a deliberate "keep both" resolution.
4. **Squash-merge rebasing** — after a base PR is *squash*-merged, a plain `git rebase
   origin/{default}` tries to replay the base's commits too. The dependent must be replayed with
   `--onto` from the base's pre-merge tip.
5. **Branch-deletion ordering trap** — deleting a base branch while a dependent PR still points
   at it can **close** that PR instead of retargeting it. Retarget dependents first.
6. **Review policy once** — `/finalize-pr` posts `--comment` reviews and never `--approve`, so
   empty `reviewDecision` is the *expected, normal* state across the whole batch, not a blocker.
7. **An explicit do-NOT-merge exclusion** (e.g. a CI regression-guard issue held until others land).

Slices are built in cloud sessions, so there are no local worktrees or background sessions to
tear down. A merged PR leaves behind only its remote branch, which `--delete-branch` removes as
part of the merge.

## Input

`$ARGUMENTS`:
- A list of PR numbers — `/merge-stack 69 70 71 72 73 74`, **or**
- `--all-ready` — discover all open, non-draft PRs targeting the default branch.

Optional flags:
- `--exclude <n,…>` — PRs to never merge (the do-NOT-merge set).
- `--order <n,…>` — override the derived order (still validated against stacking).

## 1. Collect & validate

- `{default}` = `gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'`.
- `git status --porcelain` — if non-empty, **stop**. §4.3 checks branches out in this checkout;
  a dirty tree would block that or lose work.
- Note the current branch as `{return_branch}` so §6 can put the checkout back.
- Resolve the PR set (explicit list, or `--all-ready` via `gh pr list --state open --base {default} --json number --jq '.[].number'`). Drop the `--exclude` set.
- For each PR, one call:
  `gh pr view {n} --json number,title,url,state,isDraft,headRefName,baseRefName,reviewDecision,statusCheckRollup,mergeStateStatus,mergeable,closingIssuesReferences`
  plus `gh pr diff {n} --name-only` → its changed-file set.
- Bucket:
  - `MERGED` → drop (no-op).
  - `CLOSED` or `isDraft=true` → **blocked list** (report, don't merge, don't abort the batch).
  - otherwise → **mergeable set**.
- **Review policy, once:** if every PR in the mergeable set has empty/null `reviewDecision` →
  "No review policy configured — proceeding." If any is `CHANGES_REQUESTED`/`REVIEW_REQUIRED` →
  list them and ask: exclude those, or abort.
- **Snapshot base tips.** `git fetch origin --prune`, then for each PR record
  `git rev-parse origin/{headRefName}` as `{tip[pr]}`. Concept 4's `--onto` rebase and §5's
  recovery both need a base's pre-merge tip *after* its branch is gone.

## 2. Build the order

Default-independent — normal slices are `base={default}` (per `/start-issue`), so stacking is
detected, not assumed.

- **Stacking:** for each PR where `baseRefName != {default}`, it is stacked on the PR whose
  `headRefName == baseRefName`. Build the base-dependency graph and **topologically sort** so
  each base merges before its dependents. With no stacked PRs the graph is flat.
- **Overlap:** pairwise-intersect the changed-file sets.
  - Shared file + stacked relationship ⇒ expected (the rebase resolves it).
  - Shared file + *not* stacked ⇒ **flag**: "#A & #B both touch `path` — whichever merges later
    needs a rebase." Record the path(s) for the §4.3 pause note.
- **Independent** PRs (no stack edge, no overlap) ⇒ batch first, any order.
- If `--order` was given, validate it doesn't violate any stacking edge (base before dependent);
  otherwise emit the derived order.

## 3. Present the plan & confirm once

Print the ordered plan and **ask once**. After approval, run unattended — pause only on a §4/§5
trigger (non-mechanical conflict, CI failure, unexpected PR state).

```
/merge-stack — Plan ({N} PRs → {default})

Order:
  1. #69  feat/61…  base:main  CI:✓  review:none   (independent)
  2. #70  feat/62…  base:main  CI:✓  review:none   (independent)
  …
  k. #74  feat/65…  base:#73   CI:?  review:none   (STACKED on #73; overlaps #71 on SettingsPage.tsx)

Stacked:  #74 → #73
Overlaps: #74 ↔ #71  (src/features/settings/SettingsPage.tsx — later one rebases)
Blocked:  #80 (draft), #67 (excluded — CI regression guard)

Action: squash-merge each in order; retarget/rebase stacked PRs; delete branches.
Proceed? (one confirmation; then unattended)
```

## 4. Execute loop (per PR, in order)

For each PR in the order:

1. **Re-fetch fresh state** — prior merges change things:
   `gh pr view {pr} --json baseRefName,mergeStateStatus,mergeable,state`.
2. **Retarget if its base has landed** — if the recorded base was another PR's branch that is
   now merged: `gh pr edit {pr} --base {default}`.
3. **Bring up to date if `BEHIND`/`DIRTY`** — rebase with mechanical-only discipline (see
   `/rebase-pr`), in this checkout:

   ```
   git fetch origin --prune
   git switch -C {branch} origin/{branch}
   ```

   Then replay:
   - Normal case: `git rebase origin/{default}`.
   - **When this PR's base PR was squash-merged** (concept 4): replay only this PR's own commits
     with `git rebase --onto origin/{default} {tip[base_pr]} {branch}`, using the §1 snapshot.

   Resolve only mechanical conflicts (non-overlapping / superset / independent sections). For a
   flagged **overlap** (e.g. one PR changed a heading `text-[18px]`→`text-lg`, the other the box
   `border-gray-200`→`border-border`) the resolution is usually **keep both** — but treat it as a
   **pause point**: resolve deliberately per the overlap note, stage the specific files, run
   `lint` / `typecheck` / `format:check`, then `git push --force-with-lease`.

   Truly semantic conflict you can't resolve mechanically → `git rebase --abort`, **pause**, report.
4. **Wait for CI** if step 3 pushed a new commit (the push re-fires checks): poll
   `gh pr checks {pr}` until the required check is `pass`/`fail`. `fail` → **pause** and report.
5. **Retarget dependents, then merge.**
   - **Before merging,** point any not-yet-merged dependent still based on this branch at the
     default: `gh pr edit {dep} --base {default}`. This is what prevents §5's auto-close trap;
     do it even though GitHub usually retargets on its own, because "usually" is what burned this
     workflow before.
   - `git switch {default}` — never merge a branch that is currently checked out here.
   - `gh pr merge {pr} --squash --delete-branch`
   - Verify: `gh pr view {pr} --json state --jq '.state'` == `MERGED`.
6. Record: merged ✓, closing issues, branch deleted.

## 5. Pause / recovery playbook

- **Dependent PR got auto-closed** (its base branch went away before it was retargeted):
  1. Recreate the base at its old tip: `git push origin {tip[base_pr]}:refs/heads/{old_base}`.
  2. `gh pr reopen {dep}` → `gh pr edit {dep} --base {default}`.
  3. Delete the recreated base again (now safe, the dependent points at `{default}`):
     `git push origin --delete {old_base}`.
  (§4.5's retarget-before-merge is designed to avoid ever needing this.)
- **CI failure after rebase** — pause, surface the failing job URL; let the human decide.
- **Non-mechanical conflict** — abort the rebase, pause, report the files. Never guess a semantic merge.

## 6. Cleanup

- `git switch {return_branch}`; if that was a merged slice branch, `git switch {default}` instead.
- `git fetch origin --prune` — drops the remote-tracking refs for branches deleted in §4.5.
- Delete any local branches left from a §4.3 rebase checkout: for each merged `{headRef}`,
  `git branch -D {headRef}` if it exists. `-D` is required, not a fallback — a squash merge
  rewrites the commits, so `-d` always refuses.
- If `{default}` is checked out, `git pull origin {default}` to pick up the merges.
- **Verify:** per batch `{headRef}`, `git ls-remote --heads origin {headRef}` returns nothing.
  Report anything left as a stray needing manual attention.

## 7. Summary

```
/merge-stack — Complete ({M}/{N} merged)

#69  feat/61…  MERGED   issues: #61 closed   branch deleted
#70  feat/62…  MERGED   issues: #62 closed   branch deleted
…
#74  feat/65…  MERGED   (rebased --onto)     issues: #65 closed   branch deleted

Blocked/excluded: #80 (draft), #67 (excluded)
Strays:           none
```

## Rules

- Squash merge only. Never merge commits or rebase merges. Never `--admin`. Never retry a failed merge.
- Never `git push --force` — always `--force-with-lease`.
- Stage specific files when resolving a conflict; never `git add -A`.
- **Retarget dependents *before* merging a base** (avoids the auto-close trap).
- Never merge a branch that is currently checked out in this repo — switch to `{default}` first.
- One upfront confirmation (§3); then run unattended, pausing only on conflict / CI failure / unexpected PR state.
- Respect the `--exclude` set; never merge it.
- This skill expects a local checkout holding every branch in the batch, so it normally runs outside the cloud proxy. Run inside a cloud session, §4's `gh pr edit --base`, `gh pr merge`, and §5's `gh pr reopen` are all GraphQL mutations that can 403 with `This GraphQL query is not enabled for this session` — take the REST fallbacks in [references/github-proxy.md](../../references/github-proxy.md) rather than pausing the batch, and record which ones you used in §7.

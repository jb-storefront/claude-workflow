---
name: merge-stack
description: Squash-merge a SET of in-flight PRs in the correct order, handling stacked PRs, cross-PR conflicts, and the worktrees their sessions still hold. Auto-derives the order (stacking from base refs, overlap from changed files), confirms once, then runs unattended — pausing only on conflict, CI failure, or unexpected state. Use when the user says "/merge-stack", "merge these PRs", "merge the stack", or "land these PRs in order".
---

# Merge Stack

Land several finished PRs — the output of a parallel `/dispatch-slices` fan-out — onto the
default branch in the right order.

This is the capstone of the `/grill-with-docs` → `/to-spec` → `/to-tickets` → `/dispatch-slices`
→ `/tdd` → `/finalize-pr` → **`/merge-stack`** pipeline: `finalize-pr` deliberately defers the
merge to a human, and this skill performs it for a whole batch at once.

It reuses `/merge-pr`'s readiness gates (review / CI / merge-state) per PR and owns what a
single-PR merge has no concept of: ordering, stacked-PR retarget/rebase, cross-PR conflicts, and
the worktrees the slice sessions are still holding.

**Run this from the main checkout**, never from inside a slice's worktree. Claude Code blocks a
session in a worktree from running git in the main checkout, and this skill does almost nothing
else.

## Concepts (why a batch needs more than N single merges)

1. **Order** — derived from real conflict relationships, not arbitrary.
2. **Stacked PRs** (`base != default`) — the base PR must land first; the dependent is then
   retargeted onto the default branch.
3. **Cross-PR conflicts** — PRs that touch the same file on adjacent lines need the *later* one
   rebased, sometimes with a deliberate "keep both" resolution.
4. **Squash-merge rebasing** — after a base PR is *squash*-merged, a plain `git rebase
   origin/{default}` tries to replay the base's commits too. The dependent must be replayed with
   `--onto` from the base's pre-merge tip.
5. **A worktree pins its branch.** Every slice was built in `.claude/worktrees/issue-{n}`, and git
   allows one checkout per branch. From the main checkout both of these fail outright:

   ```
   $ git switch {branch}
   fatal: '{branch}' is already used by worktree at '…/.claude/worktrees/issue-{n}'
   $ git branch -D {branch}
   error: cannot delete branch '{branch}' used by worktree at '…/.claude/worktrees/issue-{n}'
   ```

   Claude Code also holds a `git worktree lock` while the session runs, so `git worktree remove`
   refuses until the session stops. Rebase **inside** the worktree; remove the worktree **before**
   deleting the branch.
6. **Branch-deletion ordering trap** — deleting a base branch while a dependent PR still points
   at it can **close** that PR instead of retargeting it. Retarget dependents first.
7. **Review policy once** — `/finalize-pr` posts `--comment` reviews and never `--approve`, so
   empty `reviewDecision` is the *expected, normal* state across the whole batch, not a blocker.
8. **An explicit do-NOT-merge exclusion** (e.g. a CI regression-guard issue held until others land).

## Input

`$ARGUMENTS`:
- A list of PR numbers — `/merge-stack 69 70 71 72 73 74`, **or**
- `--all-ready` — discover all open, non-draft PRs targeting the default branch.

Optional flags:
- `--exclude <n,…>` — PRs to never merge (the do-NOT-merge set).
- `--order <n,…>` — override the derived order (still validated against stacking).

## 1. Collect & validate

- `{default}` = `gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'`.
- `git status --porcelain` — if non-empty, **stop**. §4.3 may check a branch out in this checkout;
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
- **Snapshot worktrees.** `git worktree list --porcelain` → a `{branch → worktree path}` map, and
  `claude agents --json` → a `{cwd → id, state}` map. Together they say, per PR, whether its branch
  is pinned and whether a session is still running in it. Everything in §4.3 and §4.5 depends on
  this map, and it is cheaper to take once than to re-derive per PR.

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
trigger (non-mechanical conflict, CI failure, unexpected PR state, a worktree holding work).

```
/merge-stack — Plan ({N} PRs → {default})

Order:
  1. #69  feat/61…  base:main  CI:✓  review:none   worktree: issue-61 (done)      (independent)
  2. #70  feat/62…  base:main  CI:✓  review:none   worktree: —                    (independent)
  …
  k. #74  feat/65…  base:#73   CI:?  review:none   worktree: issue-65 (working)   (STACKED on #73; overlaps #71 on SettingsPage.tsx)

Stacked:  #74 → #73
Overlaps: #74 ↔ #71  (src/features/settings/SettingsPage.tsx — later one rebases)
Blocked:  #80 (draft), #67 (excluded — CI regression guard)
Sessions: 2 still running — they will be stopped before their PRs merge.

Action: squash-merge each in order; retarget/rebase stacked PRs; stop sessions, remove worktrees, delete branches.
Proceed? (one confirmation; then unattended)
```

A session still `working` on a PR you are about to merge is worth naming here rather than
discovering in §4.5 — it usually means the PR was finalized and the session simply never exited,
but it can also mean someone is still pushing to it.

## 4. Execute loop (per PR, in order)

For each PR in the order:

1. **Re-fetch fresh state** — prior merges change things:
   `gh pr view {pr} --json baseRefName,mergeStateStatus,mergeable,state`.
2. **Retarget if its base has landed** — if the recorded base was another PR's branch that is
   now merged: `gh pr edit {pr} --base {default}`.
3. **Bring up to date if `BEHIND`/`DIRTY`** — rebase with mechanical-only discipline (see
   `/rebase-pr`). **Where you rebase depends on the §1 worktree map:**

   - **Branch has a worktree** (`{wt}`) — rebase there. The branch is pinned to it, so a checkout
     in the main checkout would fail outright:

     ```
     git -C {wt} fetch origin --prune
     git -C {wt} rebase origin/{default}
     ```

     If the worktree is dirty (`git -C {wt} status --porcelain` non-empty), **pause**: a rebase
     would refuse anyway, and uncommitted work in a slice's tree is something a human should look
     at before it is lost.

   - **No worktree** — as before, in this checkout:

     ```
     git fetch origin --prune
     git switch -C {branch} origin/{branch}
     git rebase origin/{default}
     ```

   Then, in whichever tree:
   - Normal case: `rebase origin/{default}`.
   - **When this PR's base PR was squash-merged** (concept 4): replay only this PR's own commits
     with `rebase --onto origin/{default} {tip[base_pr]} {branch}`, using the §1 snapshot.

   Resolve only mechanical conflicts (non-overlapping / superset / independent sections). For a
   flagged **overlap** (e.g. one PR changed a heading `text-[18px]`→`text-lg`, the other the box
   `border-gray-200`→`border-border`) the resolution is usually **keep both** — but treat it as a
   **pause point**: resolve deliberately per the overlap note, stage the specific files, run
   `lint` / `typecheck` / `format:check`, then `push --force-with-lease`.

   Truly semantic conflict you can't resolve mechanically → `rebase --abort`, **pause**, report.
4. **Wait for CI** if step 3 pushed a new commit (the push re-fires checks): poll
   `gh pr checks {pr}` until the required check is `pass`/`fail`. `fail` → **pause** and report.
5. **Retarget dependents, release the branch, then merge.**
   - **Before merging,** point any not-yet-merged dependent still based on this branch at the
     default: `gh pr edit {dep} --base {default}`. This is what prevents §5's auto-close trap;
     do it even though GitHub usually retargets on its own, because "usually" is what burned this
     workflow before.
   - **Release the branch.** If the §1 map gave this branch a worktree:
     - session still running → `claude stop {id}` (its transcript is kept).
     - then `claude rm {id}`, which removes the session and its worktree.
     `claude rm` has **two** refusals, and only one of them offers an override. Verified on 2.1.263:

     ```
     kept {id} — worktree has uncommitted changes
       worktree kept at {wt}
       resolve that (commit/push, or remove the worktree), then run 'claude rm {id}' again

     kept {id} — 1 unpushed commit on {branch} ({short-sha} {subject})
       worktree: {wt}
       push it, or discard the worktree and its commits: claude rm {id} --discard-unpushed {sha}@{worktree-id}
     ```

     Either way it **pauses**: report what is there and hand over the command it printed. Do not
     run `--discard-unpushed` and do not `git worktree remove --force`. By this point the PR is
     merged, so nothing is blocked by a worktree left on disk, and only the human can tell whether
     that commit is a stray or the one thing that never got pushed.
     - no session id for the worktree (a session already reaped) → `git worktree remove {wt}`, and
       `git worktree remove --force {wt}` only when `status --porcelain` in it is empty and git is
       refusing for some other reason.
   - `git switch {default}` — never merge a branch that is currently checked out here.
   - `gh pr merge {pr} --squash --delete-branch`
   - Verify: `gh pr view {pr} --json state --jq '.state'` == `MERGED`.
6. Record: merged ✓, closing issues, branch deleted, worktree removed.

## 5. Pause / recovery playbook

- **Dependent PR got auto-closed** (its base branch went away before it was retargeted):
  1. Recreate the base at its old tip: `git push origin {tip[base_pr]}:refs/heads/{old_base}`.
  2. `gh pr reopen {dep}` → `gh pr edit {dep} --base {default}`.
  3. Delete the recreated base again (now safe, the dependent points at `{default}`):
     `git push origin --delete {old_base}`.
  (§4.5's retarget-before-merge is designed to avoid ever needing this.)
- **CI failure after rebase** — pause, surface the failing job URL; let the human decide.
- **Non-mechanical conflict** — abort the rebase, pause, report the files. Never guess a semantic merge.
- **`claude rm` kept the worktree** — pause. It says which of the two reasons applies. Report the
  worktree path, what `git -C {wt} status --porcelain` and `git -C {wt} log --oneline @{u}..` show,
  and the exact command the refusal printed, if it printed one. The human decides; this skill never
  discards work.
- **`git worktree remove` says the worktree is locked** — a session is still running in it, or was
  killed and left its lock. `claude stop {id}` first; a lock left by a killed session is released by
  Claude Code's own periodic sweep, and `git worktree unlock {wt}` forces it now.

## 6. Cleanup

- `git switch {return_branch}`; if that was a merged slice branch, `git switch {default}` instead.
- `git fetch origin --prune` — drops the remote-tracking refs for branches deleted in §4.5.
- Any worktree left for a merged branch: remove it as §4.5 does. Then delete the local branch —
  `git branch -D {headRef}` if it still exists. `-D` is required, not a fallback: a squash merge
  rewrites the commits, so `-d` always refuses. A `-D` that fails with *"used by worktree at"* means
  a worktree survived; go back and remove it rather than forcing anything.
- **Verify both:** per batch `{headRef}`, `git ls-remote --heads origin {headRef}` returns nothing,
  and `git worktree list` shows only the main checkout. Report anything left as a stray needing
  manual attention, and re-run `claude agents --json` to confirm no slice session is still alive.

## 7. Spec close-out

A batch is the normal way a Spec's last Slice lands, and it can finish more than one Spec at once.
Run the procedure in [../../references/spec-close-out.md](../../references/spec-close-out.md),
handing it every Slice the batch closed — the `closingIssuesReferences` collected in §4.6, pooled
across the whole batch.

Once, here, rather than per PR inside §4: the procedure runs a Verification against the default
branch, and mid-batch that branch is still moving. Run after §6 and it is the tree the whole batch
produced. Nothing is missed by waiting, because a Spec completes only when its last Slice closes,
and by §6 every merge in the batch has happened.

The procedure decides for itself whether anything is due, and leaves a Spec with Slices still open
untouched.

## 8. Summary

```
/merge-stack — Complete ({M}/{N} merged)

#69  feat/61…  MERGED   issues: #61 closed   branch deleted   worktree removed
#70  feat/62…  MERGED   issues: #62 closed   branch deleted   worktree —
…
#74  feat/65…  MERGED   (rebased --onto)     issues: #65 closed   branch deleted   worktree removed

Blocked/excluded: #80 (draft), #67 (excluded)
Strays:           none
Specs:            #60 closed out;  #66 still has 1 Slice open
```

Each Spec that closed out prints its own block after this one, and any walkthrough Verification
after all of them, per §7's procedure.

## Rules

- Run from the main checkout, never from inside a slice's worktree.
- Squash merge only. Never merge commits or rebase merges. Never `--admin`. Never retry a failed merge.
- Never `git push --force` — always `--force-with-lease`.
- Stage specific files when resolving a conflict; never `git add -A`.
- **Retarget dependents *before* merging a base** (avoids the auto-close trap).
- **Remove a branch's worktree before deleting the branch**, and stop its session before removing the worktree.
- Never discard a worktree's uncommitted changes or unpushed commits. `--discard-unpushed` and `git worktree remove --force` are the human's to run, and this skill only ever reports the command.
- Never merge a branch that is currently checked out here — switch to `{default}` first.
- One upfront confirmation (§3); then run unattended, pausing only on conflict / CI failure / unexpected PR state / a worktree holding work.
- Respect the `--exclude` set; never merge it.

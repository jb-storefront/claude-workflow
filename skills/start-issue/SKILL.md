---
name: start-issue
description: Begin work on a GitHub issue — claim it, name the branch, open a draft PR, and set up the worktree's environment. Pass --no-branch to work directly on the default branch. Use when the user says "/start-issue <number>", "start issue 42", or when a dispatched background session begins a slice.
---

# Start Issue

Put a slice issue into a workable state: the issue claimed, a named branch, a draft PR to collect
the work, and a worktree with its dependencies installed.

Normally this runs as the first act of a background session dispatched by `/dispatch-slices`. That
session starts in `.claude/worktrees/issue-{n}`, on a branch named `worktree-issue-{n}` cut from the
remote default branch. A worktree is a **fresh checkout**: it shares the repository's history and
remote, and nothing else. No dependencies are installed, and no gitignored file is present unless a
`.worktreeinclude` copied it in.

## Input

`$ARGUMENTS`: an issue number (`42` or `#42`), optionally followed by `--no-branch`, optionally
followed by free-text context (e.g. "— refer to the spec in issue #60 for context"). Read that
context; it tells you where the parent spec lives.

If the issue number is missing or invalid, run `gh issue list --state open --limit 10` and ask
the user to pick.

**`--no-branch` mode**: skip all branch/PR work and operate on the default branch. Run only
steps 1, 2, and 8. Useful for local work on `main`.

## Steps

1. **Fetch the issue.** `gh issue view {number} --json number,title,body,labels,assignees`. If it
   doesn't exist or isn't open, stop and report. If it is already assigned to someone else, stop
   — another session has it.

2. **Claim it.** Assign before creating anything, and stop if the claim doesn't stick.

   ```bash
   gh api -X POST "repos/{owner}/{repo}/issues/{number}/assignees" -f "assignees[]={login}"
   gh api "repos/{owner}/{repo}/issues/{number}" --jq '.assignees[].login'
   ```

   `{owner}` and `{repo}` are **literal** — `gh api` fills them from the current repo. `{login}` =
   `gh api user --jq '.login'`. If the read-back doesn't list `{login}`, **stop** —
   the issue is unclaimed, so a second session can still take it, and everything after this step
   would be work done twice.

   A 2xx on the POST is not enough. GitHub's documented contract is that assignees for users
   without push access are [silently ignored](https://docs.github.com/en/rest/issues/assignees):
   no error, empty result. A caller who trusts the status code reports a claim it never made.

   Claiming first is the point. The branch and the draft PR are also de-duplication signals —
   `/dispatch-slices` §2 drops anything with an open PR — but they arrive several steps later, and
   the window they leave open is exactly the one two sessions collide in.

3. **Build the branch name.** Prefix from labels, first matching rule wins: `bug` → `fix`;
   `feature`/`enhancement` → `feat`; `refactor` → `refactor`; `docs`/`documentation` → `docs`;
   otherwise `chore`.

   Branch is `{prefix}/{number}-{slug}`. Slug: lowercase, non-alphanumeric → hyphens, collapse
   repeats, trim, truncate ≤50 chars without cutting mid-word, strip trailing hyphens.

4. **Put the checkout on that branch.** Which command depends on where you are:

   - `git branch --show-current` starts with `worktree-` → **rename in place**:
     `git branch -m {prefix}/{number}-{slug}`. The worktree already has its own branch, cut from
     the right base and checked out here; renaming it leaves one branch where a second `checkout -b`
     would leave a stray `worktree-issue-{n}` behind for `/merge-stack` to clean up.
   - Otherwise (a plain local run) → `git checkout -b {prefix}/{number}-{slug}`.

   If the target branch name already exists — only possible when re-running in the same session —
   reuse it and skip to step 6.

   Nothing to reset either way: a worktree is new, and a local run is the user's checkout to
   manage.

5. **Initial empty commit.** `git commit --allow-empty -m "chore: start work on #{number}"`

6. **Push and open a draft PR.**

   ```
   git push -u origin {branch}
   gh pr create --draft --head {branch} --title "{issue-title}" --body "Closes #{number}

   ## Summary

   {first 1–2 sentences of the issue body, or the full body if short}

   ## Changes

   - (work in progress)
   "
   ```

   The draft PR exists from the start so CI runs against the work as it lands, and so
   `/finalize-pr` has a stable target. `/finalize-pr` rewrites this body later.

   Keep `Closes #{number}` as the body's first line. It is what links the PR to its issue for a
   human reading either one, and what `/finalize-pr` and `/merge-pr` fall back to if the linkage is
   ever edited away.

7. **Set up the environment.** A worktree has no `node_modules` and no `.venv`. Detect the
   toolchain from a lockfile at the repo root, first match wins, and install:

   | Lockfile | Install |
   | --- | --- |
   | `bun.lockb` | `bun install` |
   | `pnpm-lock.yaml` | `pnpm install` |
   | `package-lock.json` | `npm ci` |
   | `yarn.lock` | `yarn install` |
   | `uv.lock` | `uv sync` |

   No lockfile matched → skip, and say so in step 8. A toolchain this skill was never taught looks
   identical to a project with nothing to install unless it is named.

   Skip this step entirely outside a worktree — a local checkout already has its dependencies, and
   reinstalling into one is not this skill's business.

   If the install fails, **stop and report it**. Every later step assumes a working environment,
   and `/tdd` failing on a missing import is a much worse way to discover this.

   Do not write `.env` files or fetch secrets. Gitignored config reaches a worktree through the
   repo's `.worktreeinclude`; if something is missing, say which file and stop.

8. **Print the summary.**

   ```
   Issue:    #{number} — {title}
   Branch:   {branch}
   Worktree: {path}              (omit outside a worktree)
   PR:       {pr-url}
   Assigned: @me
   Deps:     {installed with {cmd} | skipped — no lockfile matched | not a worktree}

   Next: /tdd to begin work.
   ```

   In `--no-branch` mode, report `Branch: {default_branch} (working directly)` and `PR: (skipped)`.

## Rules

- Do not skip or reorder steps. If a git/gh command fails (except where marked non-fatal), stop and report.
- Use the repo's actual default branch, never a hardcoded `main`.
- Never `git reset --hard`, never delete a branch. In a worktree, a state you cannot explain is not yours to repair: report it, and let the human `claude rm` the session and re-dispatch. Locally, an unexpected branch state is the user's to resolve.
- Never edit a file or run a command in the main checkout from inside a worktree. Claude Code blocks it, and the block is right: the point of the worktree is that the other sessions cannot see your work.
- In `--no-branch` mode, do not commit, push, or open a PR. Still claim the issue — it is what tells the next dispatch this one is taken.
- Never treat a GitHub write as done because it returned success. Where a read-back is specified, run it.

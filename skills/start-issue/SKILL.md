---
name: start-issue
description: Begin work on a GitHub issue — create the branch, open a draft PR, and assign the issue. Pass --no-branch to work directly on the default branch. Use when the user says "/start-issue <number>", "start issue 42", or when a dispatched cloud session begins a slice.
---

# Start Issue

Put a slice issue into a workable state: a named branch, a draft PR to collect the work, and the
issue assigned so `/dispatch-slices` won't hand it to a second session.

Normally this runs as the first act of a cloud session dispatched by `/dispatch-slices`. The VM
is already a fresh clone at the base branch with dependencies installed by the environment's
setup script, so there is nothing to reset and nothing to install.

## Input

`$ARGUMENTS`: an issue number (`42` or `#42`), optionally followed by `--no-branch`, optionally
followed by free-text context (e.g. "— refer to the spec in issue #60 for context"). Read that
context; it tells you where the parent spec lives.

If the issue number is missing or invalid, run `gh issue list --state open --limit 10` and ask
the user to pick.

**`--no-branch` mode**: skip all branch/PR work and operate on the default branch. Run only
steps 1, 2, and 7. Useful for local work on `main`.

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
   would be work done twice. A 2xx on the POST is not enough: GitHub silently ignores assignees
   who lack push access.

   Do not use `gh issue edit --add-assignee`; it is a GraphQL mutation that fails behind the cloud
   proxy. See [the proxy reference](../../references/github-proxy.md).

   Claiming first is the point. The branch and the draft PR are also de-duplication signals —
   `/dispatch-slices` §2 drops anything with an open PR — but they arrive several steps later, and
   the window they leave open is exactly the one two sessions collide in.

3. **Build the branch name.** Prefix from labels, first matching rule wins: `bug` → `fix`;
   `feature`/`enhancement` → `feat`; `refactor` → `refactor`; `docs`/`documentation` → `docs`;
   otherwise `chore`.

   Branch is `{prefix}/{number}-{slug}`. Slug: lowercase, non-alphanumeric → hyphens, collapse
   repeats, trim, truncate ≤50 chars without cutting mid-word, strip trailing hyphens.

4. **Create the branch.** `git checkout -b {branch}`

   Nothing to reset: the clone is fresh and at the base branch the dispatcher chose. If the
   branch name already exists — only possible when re-running in the same session — reuse it and
   skip to step 6.

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

   Keep `Closes #{number}` as the body's first line. It is what `/finalize-pr` and `/merge-pr`
   fall back to when the proxy blocks the GraphQL-only `closingIssuesReferences` field.

   If `gh pr create` itself fails with `This GraphQL query is not enabled for this session`, use
   the REST form in [the proxy reference](../../references/github-proxy.md) — the draft PR is not
   optional, later steps target it.

7. **Print the summary.**

   ```
   Issue:    #{number} — {title}
   Branch:   {branch}
   PR:       {pr-url}
   Assigned: @me

   Next: /tdd to begin work.
   ```

   In `--no-branch` mode, report `Branch: {default_branch} (working directly)` and `PR: (skipped)`.

## Rules

- Do not skip or reorder steps. If a git/gh command fails (except where marked non-fatal), stop and report.
- Use the repo's actual default branch, never a hardcoded `main`.
- Never `git reset --hard`, never delete a branch. A cloud session works in a disposable clone; if its state is wrong, the answer is a new session, not a destructive fix. Locally, an unexpected branch state is the user's to resolve.
- Do not install dependencies or write env files. In a cloud session the environment's setup script owns that; locally it is already done.
- In `--no-branch` mode, do not commit, push, or open a PR. Still claim the issue — it is what tells the next dispatch this one is taken.
- Never treat a GitHub write as done because it returned success. Where a read-back is specified, run it.
- On `This GraphQL query is not enabled for this session`, consult [references/github-proxy.md](../../references/github-proxy.md). Never warn past that 403 — take the REST fallback, or stop.

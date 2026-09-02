---
name: finalize-pr
description: Drive a slice-issue PR to ready-for-human-review. Reads the linked issue, auto-detects PM, runs quality gates, dispatches PR-writer and code-reviewer agents, performs AI-discipline checks, ticks verified acceptance-criteria checkboxes on the issue, posts the review via `gh pr review --comment`, and marks the PR ready when not blocking. Use when the user says "/finalize-pr", "submit PR", "ready for review", or finishes a TDD cycle on a slice.
---

# Finalize PR

Drive a slice-issue PR to "ready for human review" with a tracked review comment and ticked acceptance-criteria checkboxes.

## Input

`$ARGUMENTS`: a PR number (`42` or `#42`). If empty, detect from the current branch.

## Slice-issue shape (this skill expects)

Slice issues have these sections in their body:

- `## Parent` — link to the PRD issue (e.g. `#15`)
- `## Acceptance criteria` — `- [ ]` checkboxes (positions tracked for ticking)
- `## References for context` — list of in-repo file paths to read before review

Issues without these sections still work; sections that are missing are skipped silently.

## 1. Pre-flight

- `{branch}` = `git branch --show-current`. If it's the default branch (`gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'`), **stop**.
- `git status --porcelain` — if non-empty, **stop**: commit or stash first.
- Find/create the PR:
  - With arg: `gh pr view {number} --json number,title,url,isDraft,headRefName,closingIssuesReferences,mergeStateStatus`. If `headRefName != {branch}`, stop.
  - Without arg: `gh pr list --head {branch} --json … --limit 1`. If none, create a draft: `gh pr create --draft --title "{branch}" --body "Work in progress"` and capture the new number/URL.
- Assign to current user: `{gh_user}` = `gh api user --jq '.login'`; `gh pr edit {pr_number} --add-assignee {gh_user}` (warn-only on failure).
- Print a one-line pre-flight summary.

## 2. Read the slice issue

For each issue number in `closingIssuesReferences` (usually just one): `gh issue view {number} --json title,body,labels` and parse:

- `## Parent` → `{parent_issue}` (PRD number, if any)
- `## Acceptance criteria` → list of `{ index, text, checked }` (track index positions for later ticking via body replacement)
- `## References for context` → list of repo-relative file paths

If no issue is linked, skip parsing and note in the eventual review comment that no slice issue was found.

## 3. Bootstrap context

Read each file listed in `## References for context` (e.g., `CONTEXT.md`, area `CLAUDE.md`, ADRs). Skip silently when a path doesn't exist.

## 4. Auto-rebase check

`gh pr view {pr_number} --json mergeStateStatus --jq '.mergeStateStatus'`. If `BEHIND`, **stop** and tell the user to run `/rebase-pr` first, then re-run `/finalize-pr`. (Single explicit pause point — auto-invoke is intentionally deferred.)

## 5. Quality gates

Auto-detect package manager from lockfile: `bun.lockb` → `bun`, `pnpm-lock.yaml` → `pnpm`, `package-lock.json` → `npm`, `yarn.lock` → `yarn`. If no lockfile, skip this step.

Run, in order, **only the scripts that exist in `package.json`** (read the `scripts` field and check first):

- `{pm} run lint`
- typecheck — accept **either** spelling: `type-check` or `typecheck`, whichever the repo defines.
- `{pm} run format:check`

Report each gate as run, skipped, or failed. A gate that is skipped because no script matched
must say so in the §15 summary — a silently-absent typecheck reads as a passing typecheck, which
is how this gate went unnoticed for an entire project.

Any failure → **stop** with the error output. Re-running after fixes is idempotent.

## 6. Test gate (conditional)

If `.github/workflows/` exists with at least one workflow file that runs tests:

- `gh pr view {pr_number} --json statusCheckRollup`
- All `SUCCESS`/`NEUTRAL` → record CI evidence and proceed.
- Any `PENDING`/`QUEUED` → warn and ask: wait, proceed, or abort?
- Any `FAILURE`/`ERROR` → **stop**.

Otherwise, run `{pm} run test` locally (note: for bun+vitest, this is `bun run test`, not `bun test`). Skip silently if no `test` script exists. Failure → **stop**.

## 7. Push

`git push origin {branch}`. Stop on failure.

## 8. Dispatch PR Writer agent

Look for a project PR-writer agent in `.claude/agents/`. Match on the agent's **role, not its
filename** — a project names its agents for its domain (`ucp-demo-pr-writer`, `gr4ce-pr-writer`), so
read the frontmatter `name`/`description` of each file and pick the one that writes PR
descriptions. Use the Agent tool with `subagent_type` set to that frontmatter `name` and
`prompt: "Write the PR description for PR #{pr_number}."` Wait for completion.

If there is none: generate a minimal PR body inline — acceptance-criteria checklist (verbatim from the issue) plus `Closes #{issue_number}` — and update via `gh pr edit {pr_number} --body @-` from a heredoc.

## 9. Dispatch Code Reviewer agent

Look for a project code-reviewer agent in `.claude/agents/` the same way — by role, not filename
(`ucp-demo-code-reviewer`, `gr4ce-code-reviewer`). If one exists, launch it with sentinel-line gating.
Prompt:

```
Review PR #{pr_number}.

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

If there is no project code-reviewer agent: skip with a note to be included in the review comment: `⚠ No project code-reviewer agent — architectural rules not enforced.`

## 10. AI-discipline review (inline)

Run these checks inline (not via subagent — they need slice context). Load patterns from [references/ai-debris.md](references/ai-debris.md):

- **Acceptance-criteria mapping.** For each `## Acceptance criteria` checkbox: locate evidence in the diff (`file:line`) or flag as **unverified**. Use `gh pr diff {pr_number}`.
- **Scope creep.** Files touched outside the slice's stated domain (inferred from the issue body + references) → flag.
- **AI-debris pass.** Walk the diff for each pattern in `references/ai-debris.md` (unrequested defensive code, backwards-compat shims for unused paths, tautological comments, stray TODOs, premature abstractions, mock-only tests, `.skip`/`.only`/`xfail` markers).
- **Explicit uncertainty.** Enumerate what couldn't be verified (e.g., behavior that needs a manual UI check, integration that requires staging credentials).

## 11. Combine verdicts

Block if **any** of:
- Code-reviewer returned `changes_requested`
- Any acceptance criterion is unverified
- Any AI-debris finding is rated blocking
- Any quality gate failed

Otherwise: non-blocking.

## 12. Tick verified checkboxes on the slice issue

For each acceptance criterion with diff evidence, edit the issue body via `gh issue edit {issue_number} --body @-` to flip the corresponding `- [ ]` → `- [x]`. Replace by exact line match (don't restructure the body). Then leave a comment: `gh issue comment {issue_number} --body "PR #{pr_number} verified: …"` listing what was ticked and the evidence.

If no criteria are verified, skip the edit and the comment.

## 13. Post the review to the PR

Compose a single review body and post it as a tracked review (never `--approve`):

```
gh pr review {pr_number} --comment --body @-
```

Body structure:

```
## /finalize-pr review — {Blocking | Not blocking}

### Acceptance criteria
- [x] {criterion} — `path:line` ({brief evidence})
- [ ] {criterion} — **unverified**

### AI-discipline findings
- {pattern name} — `path:line` — {blocking|not} — {why}
- (or "None.")

### Not verified
- {thing the agent couldn't verify} — {how a human can verify it}

### Code-reviewer verdict
{summary line}. Full report posted as a separate PR comment.
```

Then post the full code-reviewer report as a separate PR comment: `gh pr comment {pr_number} --body @-` (keeps the review compact).

## 14. Mark PR ready (conditional)

- Not blocking → `gh pr ready {pr_number}` (warn-only on failure). Then **offer auto-fix**: tell
  the user they can run `/autofix-pr` on this branch to have Claude watch the PR and respond to
  CI failures and review comments without anyone reopening the session. Offer it; don't run it —
  it subscribes to GitHub activity and can push commits and reply to reviewers under the user's
  account, which is theirs to opt into.
- Blocking → keep draft. Print the fix list locally; do not post additional GitHub noise.

## 15. Local summary

Include the session link when running in a cloud session, so the PR traces back to the run that
produced it — `CLAUDE_CODE_REMOTE_SESSION_ID` holds the id, and the transcript URL needs its
`cse_` prefix rewritten to `session_`:

```
echo "https://claude.ai/code/${CLAUDE_CODE_REMOTE_SESSION_ID/#cse_/session_}"
```

Omit the `Session:` line entirely when the variable is unset (a local run).

```
/finalize-pr — {Complete | Blocked}

PR:       #{pr_number} — {pr_title}
URL:      {pr_url}
Branch:   {branch}
Issue:    #{issue_number} ({N}/{M} acceptance criteria verified)
Session:  {transcript-url}

Gates:    lint ✓  typecheck ✓  format ✓  test {✓|CI|—}   (— = no such script in package.json)
Review:   {Not blocking | Blocking — see above}

Next: {Share PR URL with reviewers | Fix the items above and re-run /finalize-pr}
```

## Rules

- Steps run sequentially. Step 9 depends on Step 8's PR description. Step 10–13 depend on Step 9's verdict.
- Never `--approve`; this skill writes context, the human pulls the merge trigger.
- Re-running is idempotent: gates are stateless, the PR body / review comment / issue body overwrite cleanly.
- Don't modify source files. The PR-writer agent may modify the PR body; the AI-discipline pass never touches code.
- If you stop, surface why and what to run next.

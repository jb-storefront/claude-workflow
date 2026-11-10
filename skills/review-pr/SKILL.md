---
name: review-pr
description: Run the local code review on a pull request with a fresh-context reviewer and the spec-drift question, post one summary comment, and mark the PR ready when nothing blocks. The only skill that marks a PR ready. Use when the user says "/review-pr", or when /finalize-pr hands off a Not blocking PR. Not for addressing or replying to review comments on a PR.
---

# Review PR

Review a pull request and decide whether it is ready for a human. `/finalize-pr` proves the
Criteria; this skill reviews the code, says what it found in one comment, and is the only skill in
the workflow that marks a PR ready. Ready therefore always means a reviewer that did not write the
code has looked at the head commit and nothing it found blocks.

It runs two ways, and they are the same run:

- **Hand-off.** `/finalize-pr` invokes it when its own verdict is Not blocking, with the PR number.
- **On its own.** After someone pushes to a PR, `/review-pr` reviews the new head and posts a new
  summary. Every run reviews again; nothing is skipped because an earlier summary passed.

Run it **inline**, in the session that owns the branch. Never background it or hand it to a
detached agent: the session that can fix what the review finds is the one that should read it.

## Input

`$ARGUMENTS`: a PR number (`42` or `#42`). If empty, use the current branch's PR:
`gh pr list --head {branch} --json number --limit 1`. No PR → **stop**: there is nothing to review.

## 1. Pre-flight

```bash
gh pr view {pr_number} --json number,title,url,isDraft,headRefName,headRefOid,baseRefName,closingIssuesReferences,body
git fetch origin {headRefName}
```

- `{head}` = `headRefOid`. That is the commit this run reviews and the one the summary names.
- `git branch --show-current` must be `{headRefName}`, and `git rev-parse HEAD` must equal
  `{head}`. Otherwise **stop**: a checkout on another branch, unpushed commits, or a stale checkout
  all mean a reviewer reading the working tree would read code that is not the PR. Say which
  (`git status -sb` shows ahead/behind) and what to run.

## 2. Read the Slice's Parent and the repository's Specs line

The drift heuristic in §3 drops the Spec this Slice is building, so it needs the Slice's
`## Parent`. Read the Slice from the repository the closing reference names, never by bare number:

```bash
gh pr view {pr_number} --json closingIssuesReferences \
  --jq '.closingIssuesReferences[] | "\(.repository.owner.login)/\(.repository.name) \(.number)"'
gh issue view {number} --repo {owner}/{repo} --json body --jq '.body'
```

With no linked issue, read the PR body for `Closes|Fixes|Resolves #(\d+)`, as `/finalize-pr` does.
With no Slice at all, there is no Parent to drop; carry on.

When `docs/agents/workflow.md` carries `**Specs:** off`, read `## Parent` as absent. `CONTRACTS.md`
describes the line; absent means `on`.

## 3. Dispatch the code reviewer, with the drift question

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

Look for one in `.claude/agents/`. Match on the agent's **role, not its filename**: a project names
its agents for its domain (`ucp-demo-code-reviewer`, `gr4ce-code-reviewer`), so read the frontmatter
`name`/`description` of each file and pick the one that reviews code. Launch it with the Agent tool,
`subagent_type` set to that frontmatter `name`, with sentinel-line gating. It is a fresh-context
agent on purpose: the session that wrote the code does not review it. Prompt:

```
Review PR #{pr_number}.

These Specs describe behaviour that already ships:

{one line per candidate: `docs/specs/60-loyalty-earn-and-burn.md`, {its title}}
{or, with no candidates: "No implemented Specs match the changed paths."}

Flag any behaviour this diff changes that one of those Specs describes, where that Spec was
not itself edited in this diff. Report each as:

spec-drift: {spec file} | {the behaviour} | {path:line}

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

Parse the sentinels. If absent, **stop** and report the malformed response. Post nothing and mark
nothing: a review with no verdict is a review that did not happen.

Say "no implemented Specs match" explicitly rather than dropping the paragraph: a reviewer told
there is nothing to drift from answers differently from a reviewer told nothing at all.

### With no project code-reviewer agent

Invoke Pocock's `code-review` skill through the Skill tool, `skill: "mattpocock-skills:code-review"`,
with the merge-base as its fixed point: `git merge-base origin/{default} HEAD`. Name the candidate
Specs above as its spec source, and pass the same drift instruction.

Its two axes are the two things the missing agent would have done: **Spec** is this drift check, and
**Standards** is the architectural pass. It returns findings rather than sentinels, so:

- Its **Spec**-axis findings go into `### Spec drift (advisory)` in §5, each naming the Spec and the
  behaviour, the same as an agent's `spec-drift:` lines. Advisory, like any other drift finding.
- Its **Standards**-axis Critical and High findings count the way §4 counts `changes_requested`.
- §5's `Reviewer:` line names `code-review` as the reviewer that ran, so a reader of the PR knows
  which one produced the findings.

This is what a repo with no reviewer agent gets instead of the note that nothing was enforced.

## 4. Verdict

Blocking when the reviewer returned `changes_requested`, or the `code-review` fallback returned any
Critical or High finding on its **Standards** axis. The fallback stands in for the missing agent,
so it gates what that agent gated; letting it only advise would make a repo with no reviewer agent
the one place a Critical finding lands silently. Its **Spec** axis is the drift check and never
blocks.

Never block on a spec-drift finding. It is a question for the human, and the heuristic that raised
it over-selects by design. Medium and Low findings are listed, not blocking.

## 5. Post the summary

One comment, via `gh pr comment {pr_number} --body @-` from a heredoc. Its shape is in
`CONTRACTS.md`, under **The `/review-pr` summary comment**, because other skills and the tests read
it:

```
## /review-pr — {Ready | Draft}

Head: `{head, first 7}`
Reviewer: `{the project agent's frontmatter name, or code-review}` — {approved | changes_requested}, {C} Critical, {H} High

### Blocking findings
- {Critical | High} — `path:line` — {the finding, one line}
- (or "None.")

### Spec drift (advisory)
- `docs/specs/60-loyalty-earn-and-burn.md`, {behaviour the diff changes}, `path:line`
- (or "None." / "No implemented Specs match the changed paths.")

### Outcome
{Marked ready. | Left as a draft: {the blocking findings above | why}.}

<details><summary>Full reviewer report</summary>

{the reviewer's report, sentinel lines included}

</details>
```

Every Critical and High finding goes under `### Blocking findings` with its `path:line`, so the
person picking up a Draft PR does not have to open the full report to learn what stopped it.

Post a new comment on every run; never edit an earlier one. Each summary records the head it
reviewed, and the history of which commit passed and which did not is the point.

## 6. Mark ready, or keep it a draft

- **Not blocking** → `gh pr ready {pr_number}` when `isDraft` is true, then **verify**:
  `gh api "repos/{owner}/{repo}/pulls/{pr_number}" --jq '.draft'` must be `false`. If it still
  reads `true`, stop and report: `/merge-pr` hard-stops on drafts, so a PR that silently stayed a
  draft is a PR nobody can land.
- **Blocking** → the PR stays a draft. If it was already ready (a re-run after a push), return it to
  draft with `gh pr ready {pr_number} --undo` and read `.draft` back as `true`. A ready PR whose head
  blocks would tell a human it has been reviewed clean when it has not.

`{owner}` and `{repo}` are **literal** in `gh api` paths: `gh` fills them from the current repo.

## 7. Local summary

```
/review-pr — {Ready | Draft}

PR:       #{pr_number} — {pr_title}
URL:      {pr_url}
Head:     {head}
Reviewer: {name} — {verdict}, {C} Critical, {H} High
Drift:    {N} advisory finding(s) | none
Outcome:  {marked ready | left as a draft | returned to draft}

Next: {Share the PR URL with reviewers | Fix the blocking findings, push, and re-run /review-pr}
```

## Rules

- Inline only. Never background this skill or dispatch it to a detached session.
- This is the only skill that marks a PR ready. A PR is marked ready only after a review of its
  current head that does not block.
- Never `--approve`. This skill comments; the human pulls the merge trigger.
- The reviewer is always a fresh-context agent or skill, never this session's own reading of the
  diff.
- Absent sentinels stop the run. Nothing is posted and the PR's state is not changed.
- Spec drift is advisory and never blocks.
- Every run reviews the current head and posts a new summary. Do not skip a review because an
  earlier summary passed.
- A GitHub write that returns success is not evidence it took effect. §6 says what to read back.
- Read the Slice from the repository `closingIssuesReferences` names, with `--repo`.
- Do not modify source files. Fixing what the review found is the session's next step, not this
  skill's.

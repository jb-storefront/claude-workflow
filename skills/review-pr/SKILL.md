---
name: review-pr
description: Run the local code review and the security review on a pull request with fresh-context reviewers and the spec-drift question, post one summary comment, and mark the PR ready when nothing blocks. The only skill that marks a PR ready. Use when the user says "/review-pr", or when /finalize-pr hands off a Not blocking PR. Not for addressing or replying to review comments on a PR.
---

# Review PR

Review a pull request and decide whether it is ready for a human. `/finalize-pr` proves the
Criteria; this skill reviews the code and its security, says what it found in one comment, and is
the only skill in the workflow that marks a PR ready. Ready therefore always means two reviewers that
did not write the code, one for the code and one for its security, have looked at the head commit
and nothing either found blocks.

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
git fetch origin {headRefName} {baseRefName} {default}
```

- `{default}` = `gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'`, read before the
  fetch. Never assume `main`. The fetch keeps `origin/{default}` current, because the §4 fallback
  takes its fixed point from it, and `origin/{baseRefName}` current, because the security review
  reads the PR's diff against it.
- `{head}` = `headRefOid`. That is the commit this run reviews and the one the summary names.
- `git branch --show-current` must be `{headRefName}`, and `git rev-parse HEAD` must equal
  `{head}`. Otherwise **stop**: a checkout on another branch, unpushed commits, or a stale checkout
  all mean a reviewer reading the working tree would read code that is not the PR. Say which
  (`git status -sb` shows ahead/behind) and what to run. Return the PR to draft first, as below.

**A stop is never a pass.** Wherever this skill stops before §6 (a checkout that is not the PR's
head, an unusable Security reviewers list, a code reviewer that returned no sentinels, or a security
chain where no entry produced a result), it posts no summary, and if `isDraft` is false it returns
the PR to draft with `gh pr ready {pr_number} --undo` and reads `.draft` back as `true` (§6 has the
read-back). A PR left ready on a head nobody reviewed says the opposite of what
happened.

## 2. Read the Slice's Parent and the repository's Specs line

The drift heuristic in §4 drops the Spec this Slice is building, so it needs the Slice's
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

## 3. Read the Security reviewers list

`docs/agents/workflow.md` holds the chain the security review walks. `CONTRACTS.md` describes it;
this skill is its only reader. Read it with the script, never by eye and never from anywhere else:

```bash
python3 <this skill dir>/../../scripts/security-reviewers.py docs/agents/workflow.md
```

It prints one `{vendor}\t{model}` per entry, in order.

- **Exit 1** → **stop** before dispatching anything, the code reviewer included, and relay its `✘`
  line: a list whose last entry is not `claude`, a vendor with no dispatch path, or an entry that is
  not `{vendor}, {model}`. Fixing it is an edit to `docs/agents/workflow.md`, not this skill's to
  make. A stop is never a pass (§1).
- **No list, or no file** → it prints the Claude floor alone, `claude\tdefault`, and one `note:` line
  saying `/setup-workflow` adds the list. Say that once, in §8. Never borrow the Critics list.

([security-reviewers.py](../../scripts/security-reviewers.py) holds these rules so they are tested
rather than re-read on every run.)

## 4. Dispatch the code reviewer and the security reviewer, together

Both review `{head}`, and they run at the same time: dispatch the security reviewer's first entry
and the code reviewer in one message, as two Agent calls. With no project code-reviewer agent the
code review is a skill, which runs inline, so launch the security entry first and then invoke the
skill while it works. Neither waits on the other, and neither sees the other's findings.

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

Parse the sentinels. If absent, **stop** and report the malformed response. Post nothing, and
return a ready PR to draft as §1 describes: a review with no verdict is a review that did not
happen.

Say "no implemented Specs match" explicitly rather than dropping the paragraph: a reviewer told
there is nothing to drift from answers differently from a reviewer told nothing at all.

### With no project code-reviewer agent

Invoke Pocock's `code-review` skill through the Skill tool, `skill: "mattpocock-skills:code-review"`,
with the merge-base as its fixed point: `git merge-base origin/{default} HEAD`. Name the candidate
Specs above as its spec source, and pass the same drift instruction. Ask it to grade every **Standards**
finding Critical, High, Medium or Low: its own brief only separates hard violations from judgement
calls, and an ungraded finding cannot block, so without the grades the fallback always approves.

Its two axes are the two things the missing agent would have done: **Spec** is this drift check, and
**Standards** is the architectural pass. It returns findings rather than sentinels, so:

- Its **Spec**-axis findings go into `### Spec drift (advisory)` in §7, each naming the Spec and the
  behaviour, the same as an agent's `spec-drift:` lines. Advisory, like any other drift finding.
- Its **Standards**-axis Critical and High findings count the way §5 counts `changes_requested`.
- §7's `Reviewer:` line names `code-review` as the reviewer that ran, so a reader of the PR knows
  which one produced the findings. Its verdict is `changes_requested` when the **Standards** axis
  holds any Critical or High finding and `approved` otherwise, with those two counts beside it.

This is what a repo with no reviewer agent gets instead of the note that nothing was enforced.

### The security reviewer

Walk the chain §3 printed by the rules in
[../../references/chain-walking.md](../../references/chain-walking.md): which entries are
available, when an entry counts as having produced a result, where the walk ends, what to do when
every entry fails, and which entry to name. Read it before dispatching anything. The walk is
sequential within the chain and runs alongside the code reviewer, not after it.

What those rules leave to this skill:

- **A result** is a report ending in the four `SECURITY_*` sentinel lines below, zeros included. "No
  vulnerabilities found." with four zeros is a result. A report without the sentinels is nothing,
  and the walk moves on.
- **The entry that ran** is the one §7 and §8 name, as `{vendor} ({model})`.
- **When every entry fails**, **stop**: post nothing, and return a ready PR to draft (§1). A PR with
  no security review has not been reviewed, whatever the code reviewer said.

**`codex` and `google`** get this prompt, through the subagent and model prefix `/critique-spec`
§5 uses for the same vendor (`codex:codex-rescue` with `Run with --model {model}` unless the model is
`default`; `antigravity:agy-rescue` with `MODEL: {model}` and no `--add-dir`):

```
You are reviewing a pull request for security vulnerabilities, not writing code. Do not
edit, create, or delete any file, and do not run any command that changes state: no
checkout, commit, stash, install, or fetch. Read and report only.

The change is pull request #{pr_number} at commit {head}. Its diff against its base is:

  git diff origin/{baseRefName}...{head}

Report only vulnerabilities this diff introduces that have real exploitation potential.
Not style, not missing hardening, not theoretical issues, not code the diff did not
change. For each finding:

- {Critical | High | Medium | Low} — `path:line` — the vulnerability in one sentence
  Exploit: a concrete scenario: who sends what, and what they get

After your report, append these exact lines at the very end of your response, outside
any code block:

SECURITY_CRITICAL: <number>
SECURITY_HIGH: <number>
SECURITY_MEDIUM: <number>
SECURITY_LOW: <number>

With no findings, write "No vulnerabilities found." and four zeros.
```

**`claude`** is Claude Code's built-in security review, the `security-review` skill. Run it in a
fresh subagent so it runs beside the code reviewer and the session that wrote the code does not
review it: the Agent tool, `subagent_type: "general-purpose"`, the entry's model passed as
`/critique-spec` §5 describes for a `claude` entry (with `default`, pass none; the subagent runs on
this session's model, and that model is what §7 names). Prompt:

```
Invoke the `security-review` skill with the Skill tool, and do nothing else. Do not edit,
create, or delete any file. When it finishes, reply with its report verbatim, then append
these exact lines at the very end, outside any code block, counting the report's findings
by severity (it grades HIGH, MEDIUM and LOW, so SECURITY_CRITICAL is 0):

SECURITY_CRITICAL: 0
SECURITY_HIGH: <number>
SECURITY_MEDIUM: <number>
SECURITY_LOW: <number>

If the skill is not available to you, or fails, say so and append no sentinel lines.
```

The built-in reads the checkout, which §1 pinned to `{head}`, against `origin/HEAD`. Before
dispatching it, `git rev-parse --verify -q origin/HEAD` must resolve; when it does not, run
`git remote set-head origin {default}`, which writes only that remote ref. When `{baseRefName}` is
not `{default}` (a stacked PR), the built-in's diff also holds the PRs beneath this one: a finding
whose path is not in `gh pr diff {pr_number} --name-only` is listed as outside this PR and not
counted.

## 5. Verdict

Blocking when the reviewer returned `changes_requested`, the `code-review` fallback returned any
Critical or High finding on its **Standards** axis, or the security reviewer that ran counted any
Critical or High finding in this PR. The fallback stands in for the missing agent,
so it gates what that agent gated; letting it only advise would make a repo with no reviewer agent
the one place a Critical finding lands silently. Its **Spec** axis is the drift check and never
blocks.

Never block on a spec-drift finding. It is a question for the human, and the heuristic that raised
it over-selects by design. Medium and Low findings, from either reviewer, are listed, not blocking.

## 6. Mark ready, or keep it a draft

Set the PR's state before the summary is written, so the summary reports the state the PR is
actually in rather than the one this run meant to leave it in.

- **Not blocking** → `gh pr ready {pr_number}` when `isDraft` is true, then **verify**:
  `gh api "repos/{owner}/{repo}/pulls/{pr_number}" --jq '.draft'` must be `false`. If it still
  reads `true`, the outcome is `Draft` with the reason that `gh pr ready` did not take; post that
  summary in §7, then stop and report. `/merge-pr` hard-stops on drafts, so a PR that silently
  stayed a draft is a PR nobody can land.
- **Blocking** → the PR stays a draft. If it was already ready (a re-run after a push), return it to
  draft with `gh pr ready {pr_number} --undo` and read `.draft` back as `true`. A ready PR whose head
  blocks would tell a human it has been reviewed clean when it has not.

`{owner}` and `{repo}` are **literal** in `gh api` paths: `gh` fills them from the current repo.

## 7. Post the summary

One comment, via `gh pr comment {pr_number} --body-file -` from a heredoc. Its shape is in
`CONTRACTS.md`, under **The `/review-pr` summary comment**, because other skills and the tests read
it. The heading's `Ready` or `Draft` and the `### Outcome` line are the state §6 read back, never
the state it intended. The `Security:` line names the entry that ran, never one that was skipped or
returned nothing.

Every Critical and High finding, from the code reviewer and the security reviewer alike, goes under
`### Blocking findings` with its `path:line`, so the person picking up a Draft PR does not have to
open the full reports to learn what stopped it. Put each reviewer's whole report, sentinel lines
included, in its own closing `<details>` block.

Read it back. `gh pr comment` prints the new comment's URL, ending `#issuecomment-{id}`; then
`gh api "repos/{owner}/{repo}/issues/comments/{id}" --jq '.body'` must open with `## /review-pr`.
Passing `@-` to `--body` instead of `--body-file -` posts the two characters `@-` and returns
success, which is how a summary disappears without an error.

Post a new comment on every run; never edit an earlier one. Each summary records the head it
reviewed, and the history of which commit passed and which did not is the point.

## 8. Local summary

```
/review-pr — {Ready | Draft}

PR:       #{pr_number} — {pr_title}
URL:      {pr_url}
Head:     {head}
Reviewer: {name} — {verdict}, {C} Critical, {H} High
Security: {vendor} ({model}) — {C} Critical, {H} High, {M} Medium, {L} Low
          {each entry skipped, and why: unavailable, or returned nothing}
          {with no list: "No Security reviewers list; /setup-workflow adds it."}
Drift:    {N} advisory finding(s) | none
Outcome:  {marked ready | left as a draft | returned to draft}

Next: {Share the PR URL with reviewers | Fix the blocking findings, push, and re-run /review-pr}
```

## Rules

- Inline only. Never background this skill or dispatch it to a detached session.
- This is the only skill that marks a PR ready. A PR is marked ready only after a review of its
  current head that does not block.
- Never `--approve`. This skill comments; the human pulls the merge trigger.
- The reviewers are always fresh-context agents or skills, never this session's own reading of the
  diff.
- Absent sentinels stop the run. Nothing is posted, and a ready PR goes back to draft (§1).
- The Security reviewers list is read from `docs/agents/workflow.md` through
  `security-reviewers.py` and from nowhere else. A missing list runs the Claude floor; it never
  borrows the Critics list.
- The claude floor is required. A list that does not end in `claude` stops the run before anything
  is dispatched.
- The security review always runs, alongside the code review, on the same head. A Critical or High
  security finding blocks exactly as a code-reviewer one does.
- The `Security:` line names the entry that ran, never one that was skipped or returned nothing.
- Spec drift is advisory and never blocks.
- Every run reviews the current head and posts a new summary. Do not skip a review because an
  earlier summary passed.
- A GitHub write that returns success is not evidence it took effect. §6 and §7 say what to read back, and §7 never claims a state §6 did not read back.
- Read the Slice from the repository `closingIssuesReferences` names, with `--repo`.
- Do not modify source files. Fixing what the review found is the session's next step, not this
  skill's.

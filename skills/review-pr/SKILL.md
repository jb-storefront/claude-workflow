---
name: review-pr
description: Run the local code review and the security review on a pull request with fresh-context reviewers and the spec-drift question, reviewing only the commits since the last Ready review when one passed, mark the PR ready when nothing blocks, hand it to Copilot and a cloud Auto-fix session, and post one summary comment that carries /finalize-pr's Criteria when it handed off. The only skill that marks a PR ready. Use when the user says "/review-pr", or when /finalize-pr hands off a Not blocking PR. Not for addressing or replying to review comments on a PR.
---

# Review PR

Review a pull request and decide whether it is ready for a human. `/finalize-pr` proves the
Criteria; this skill reviews the code and its security, says what it found in one comment, and is
the only skill in the workflow that marks a PR ready. Ready therefore always means two reviewers that
did not write the code, one for the code and one for its security, have looked at the head commit
and nothing either found blocks.

Once the PR is ready it goes to Copilot, and an Auto-fix session in the cloud answers each Copilot
pass: it fixes or declines every thread, fixes failing checks, and pushes, until Copilot is clean or
three passes have run. This skill does not wait for any of that. It starts the session and finishes.
The Auto-fix session's commits are reviewed by Copilot alone, so `/merge-pr` and `/merge-stack`
refuse a head newer than the latest summary, and a PR Auto-fix pushed to needs `/review-pr` again
before it merges.

It runs two ways, and they are the same run:

- **Hand-off.** `/finalize-pr` invokes it when its own verdict is Not blocking, with the PR number
  and the file holding its Criteria report. `/finalize-pr` posts no comment of its own then: this
  skill's summary carries the Criteria, so a reviewer reads one comment per run, not two.
- **On its own.** After someone pushes to a PR, `/review-pr` reviews the new head and posts a new
  summary. Every run reviews again; nothing is skipped because an earlier summary passed.

**What it reviews.** The first review of a PR reviews all of it. Once a summary has said `Ready`,
everything up to the head it named was reviewed whole and passed, so a later run reviews only the
commits after that head: an Auto-fix push of three lines gets a review of three lines, with the
whole PR there for context, rather than a second full review that repeats the first. §1 decides
which, and the summary's `Scope:` line says which ran.

Run it **inline**, in the session that owns the branch. Never background it or hand it to a
detached agent: the session that can fix what the review finds is the one that should read it.

## Input

`$ARGUMENTS`: a PR number (`42` or `#42`). If empty, use the current branch's PR:
`gh pr list --head {branch} --json number --limit 1`. No PR → **stop**: there is nothing to review.

Two optional flags:

- `--criteria {path}`: the Criteria report `/finalize-pr` wrote for this head. Only `/finalize-pr`
  passes it. §8 puts it in the summary.
- `--full`: review the whole PR even when §1 would review only the newest commits. For a person who
  wants a second full look, such as after a large rework.

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
  `{head}`. An Auto-fix session pushes to the PR, so a checkout that is only behind is the normal
  state of a re-run: when `git status --porcelain` is empty and `HEAD` is an ancestor of `{head}`
  (`git merge-base --is-ancestor HEAD {head}`), run `git merge --ff-only origin/{headRefName}` and
  check again. Otherwise **stop**: a checkout on another branch, unpushed commits, or a stale checkout
  all mean a reviewer reading the working tree would read code that is not the PR. Say which
  (`git status -sb` shows ahead/behind) and what to run. Return the PR to draft first, as below.

### The scope

```bash
python3 <this skill dir>/../../scripts/merge-gate.py --pr {pr_number}
```

`{since}` = `.last_ready.head`, the head the newest `Ready` summary named. Exit 2 → **stop**, as for
any read that failed: a scope this skill could not work out is not a full review by default, it is a
run that did not happen.

Review only the commits after `{since}` when every one of these holds:

- `{since}` is not null. A `Draft` summary never sets it, because its head had blocking findings.
- `{since}` is not `{head}`. A re-run on a reviewed head reviews it whole again.
- `git merge-base --is-ancestor {since} {head}` succeeds. A rebase or a force-push rewrote what was
  reviewed, and the old head says nothing about the new commits.
- `--full` was not passed.

Then `{scope}` is `since {since}`, `{range}` is `{since}...{head}`, and `{security_base}` is
`{since}`. Otherwise `{scope}` is `full`, `{range}` is `origin/{baseRefName}...{head}`, and
`{security_base}` is `origin/{baseRefName}`.

`/finalize-pr` handing off does not force a full review. Its Criteria are re-proven on every run it
makes; the code a Ready review already passed has not changed.

**A stop is never a pass.** Wherever this skill stops before §6 (a checkout that is not the PR's
head, an unusable Security reviewers list, a Spec list `gh` could not read, a code reviewer that returned no sentinels, or a security
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
  saying `/setup-workflow` adds the list. Say that once, in §9. Never borrow the Critics list.

([security-reviewers.py](../../scripts/security-reviewers.py) holds these rules so they are tested
rather than re-read on every run.)

## 4. Dispatch the code reviewer and the security reviewer, together

Both review `{head}`, and they run at the same time: dispatch the security reviewer's first entry
and the code reviewer in one message, as two Agent calls. With no project code-reviewer agent the
code review is a skill, which runs inline, so launch the security entry first and then invoke the
skill while it works. Neither waits on the other, and neither sees the other's findings.

### Pick the candidate implemented Specs

A Spec names no file paths (`CONTRACTS.md` says why), so the Specs this diff might have drifted from
are found by a cheap heuristic rather than a lookup. Specs are Spec issues, and they live on the
tracker: `{tracker}` is the repository §2 read the Slice from, or this PR's repository when there is
no Slice.

1. Take the Spec issues whose Status is `implemented`, open or closed:
   `python3 <this skill dir>/../../scripts/spec.py list --status implemented --repo {tracker}`. A
   Spec still in progress is being built, not drifted from. Exit 2 means `gh` failed: **stop**, and a
   stop is never a pass (§1). A list that failed to load, read as no Specs, would let every drift
   through unasked.
2. Take the changed paths: `git diff --name-only {range}`.
3. Keep a Spec when a word of its title, or a `CONTEXT.md` **Language** term its Criteria use,
   appears in a changed path. Read each candidate's Criteria with
   `python3 <this skill dir>/../../scripts/spec.py read {spec} --repo {tracker}`; exit 2 there
   stops the run as in step 1. Match whole words, not substrings: `cart` matches `src/cart/summary.ts`
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

{only when {scope} is not full:}
The PR was reviewed whole at {since} and nothing blocked. Review only the commits after it:
`git diff {since}...{head}`. Read `gh pr diff {pr_number}` and the code around the change for
context, and report a finding only on a line those commits change, or on code elsewhere that
they break. Do not report what the earlier review already saw.

These Specs describe behaviour that already ships:

{one line per candidate: `#60 Loyalty earn and burn`}
{or, with no candidates: "No implemented Specs match the changed paths."}

Each Spec is the body of its issue. Read it with `gh issue view {n} --repo {tracker}`.

Flag any behaviour this diff changes that one of those Specs describes. Report each as:

spec-drift: #{spec} | {the behaviour} | {path:line}

These drift findings are advisory. Do not count them in CRITICAL_COUNT or HIGH_COUNT, and do
not let them change VERDICT.

Also walk the diff for these AI-debris patterns. A pattern rated Blocking is a High finding,
and one rated Not blocking is Medium or Low:

{the text of references/ai-debris.md from its first `##` heading to the end}

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

The AI-debris patterns come from
[../../references/ai-debris.md](../../references/ai-debris.md), pasted in rather than pointed at:
the agent runs in the project's repository, where the plugin's files are not. `/finalize-pr` no
longer looks for debris, because the session that wrote the diff is the wrong one to, so this prompt
is the only place it is checked.

Parse the sentinels. If absent, **stop** and report the malformed response. Post nothing, and
return a ready PR to draft as §1 describes: a review with no verdict is a review that did not
happen.

Say "no implemented Specs match" explicitly rather than dropping the paragraph: a reviewer told
there is nothing to drift from answers differently from a reviewer told nothing at all.

### With no project code-reviewer agent

Invoke Pocock's `code-review` skill through the Skill tool, `skill: "mattpocock-skills:code-review"`,
with `{since}` as its fixed point when `{scope}` is not full, and otherwise the merge-base:
`git merge-base origin/{default} HEAD`. Name the candidate
Specs above as its spec source, and pass the same drift instruction and the same AI-debris
patterns, as **Standards** findings graded the way the prompt above grades them. Ask it to grade every **Standards**
finding Critical, High, Medium or Low: its own brief only separates hard violations from judgement
calls, and an ungraded finding cannot block, so without the grades the fallback always approves.

Its two axes are the two things the missing agent would have done: **Spec** is this drift check, and
**Standards** is the architectural pass. It returns findings rather than sentinels, so:

- Its **Spec**-axis findings go into `### Spec drift (advisory)` in §8, each naming the Spec and the
  behaviour, the same as an agent's `spec-drift:` lines. Advisory, like any other drift finding.
- Its **Standards**-axis Critical and High findings count the way §5 counts `changes_requested`.
- §8's `Reviewer:` line names `code-review` as the reviewer that ran, so a reader of the PR knows
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

- **A result** is a report ending in the three `SECURITY_*` sentinel lines the prompt asks for,
  zeros included. "No vulnerabilities found." with three zeros is a result. A report without the
  sentinels is nothing, and the walk moves on.
- **The entry that ran** is the one §8 and §9 name, as `{vendor} ({model})`.
- **When every entry fails**, **stop**: post nothing, and return a ready PR to draft (§1). A PR with
  no security review has not been reviewed, whatever the code reviewer said.

**One prompt, for every vendor.** Read
[../../references/security-review-prompt.md](../../references/security-review-prompt.md), take the
text under its `## Prompt` heading, and fill in `{pr_number}`, `{base}` (`{security_base}`) and
`{head}`. Change nothing else. It is Anthropic's Claude Code security review, adapted only so that it
runs the same on any vendor, so whichever entry runs, the review asks the same questions of the same
diff and grades on the same scale.

Each vendor gets it through the subagent and model prefix `/critique-spec` §5 uses for that vendor:

- **`codex`**: `codex:codex-rescue`, prefixed `Run with --model {model}` unless the model is
  `default`.
- **`google`**: `antigravity:agy-rescue`, prefixed `MODEL: {model}` with no `--add-dir`.
- **`claude`**: the Agent tool with `subagent_type: "general-purpose"` (the prompt's read-only rule
  forbids its write tools) and the entry's model passed as `/critique-spec` §5 describes. With
  `default`, pass none: the subagent runs on this session's model, and that model is what §8 names.

## 5. Verdict

Blocking when the reviewer returned `changes_requested`, the `code-review` fallback returned any
Critical or High finding on its **Standards** axis, or the security reviewer that ran counted any
High finding. The security prompt grades High, Medium and Low; its High is the same bar as a code
reviewer's Critical or High: directly exploitable. The fallback stands in for the missing agent,
so it gates what that agent gated; letting it only advise would make a repo with no reviewer agent
the one place a Critical finding lands silently. Its **Spec** axis is the drift check and never
blocks.

Never block on a spec-drift finding. It is a question for the human, and the heuristic that raised
it over-selects by design. Resolving it is a person's call, made as an edit to the Spec issue or a
fix to the diff, as `CONTRACTS.md` describes under **Keeping an implemented Spec true**; this skill
reports the drift and leaves the Spec alone. Medium and Low findings, from either reviewer, are listed, not blocking.

## 6. Mark ready, or keep it a draft

Set the PR's state before the summary is written, so the summary reports the state the PR is
actually in rather than the one this run meant to leave it in.

- **Not blocking** → `gh pr ready {pr_number}` when `isDraft` is true, then **verify**:
  `gh api "repos/{owner}/{repo}/pulls/{pr_number}" --jq '.draft'` must be `false`. If it still
  reads `true`, the outcome is `Draft` with the reason that `gh pr ready` did not take; post that
  summary in §8, then stop and report. `/merge-pr` hard-stops on drafts, so a PR that silently
  stayed a draft is a PR nobody can land.
- **Blocking** → the PR stays a draft. If it was already ready (a re-run after a push), return it to
  draft with `gh pr ready {pr_number} --undo` and read `.draft` back as `true`. A ready PR whose head
  blocks would tell a human it has been reviewed clean when it has not.

`{owner}` and `{repo}` are **literal** in `gh api` paths: `gh` fills them from the current repo.

## 7. Hand the PR to Copilot and Auto-fix (Ready only)

Only when §6 read the PR back as ready. A Draft PR goes to neither: Copilot would review code
already known to change, and the session would push fixes onto a head that blocks.

### The repository's Copilot rules

```bash
gh api "repos/{owner}/{repo}/rules/branches/{baseRefName}" \
  --jq '[.[] | select(.type == "copilot_code_review") | .parameters]'
```

GitHub returns the rules every active ruleset applies to the base branch, so this needs no reading
of ruleset conditions. `{auto}` is true when any rule is listed: one requests Copilot when a PR is
marked ready. `{on_push}` is true when any has `review_on_push: true`: Copilot reviews each later
push, which is what lets the Auto-fix session reach a second and third pass. The session has no tool
to request a reviewer (it works through GitHub's MCP tools, not `gh`), so without `{on_push}` the
first pass is the only one.

A `gh api` error here is not a rule: treat both as false and name the error on the `Copilot:` line.

### The first Copilot pass

- **`{auto}`** → wait up to a minute for a `review_requested` event naming `Copilot` in
  `gh api "repos/{owner}/{repo}/issues/{pr_number}/timeline" --paginate`, created after the PR was
  marked ready. When it appears, the ruleset made the request: do not request again. When it does
  not, fall through to the next bullet.
- **Otherwise** → `gh pr edit {pr_number} --add-reviewer "@copilot"`. Never an `@copilot` comment.
  Read the timeline back for the `review_requested` event; a command that succeeded with no event
  has not requested anything.
- **No request could be made** (the command failed, or no event followed: GHES, Copilot review
  disabled, out of premium requests) → Copilot does not run on this PR. The PR stays ready, and the
  summary's first line under the heading says Copilot did not run and why, in the error's own words.

### The Auto-fix session

One session per PR. Two would push to the same branch and answer the same threads.

1. **Reuse one that is still running.** Run
   `python3 <this skill dir>/../../scripts/merge-gate.py --pr {pr_number}`. When `.autofix.session`
   names a session, tell it about the new head:

   ```bash
   claude -p "/review-pr reviewed {head} and the PR is ready. Carry on watching it under the same rules." --cloud {session} --output-format json
   ```

   `"ok": true` → reuse it, and start nothing. `"ok": false` (archived, not found) → start one.
2. **Start one** from this worktree. `claude --cloud` clones the remote at the current branch, and
   a worktree under `.claude/worktrees/` inherits the main checkout's workspace trust. A folder that
   was never trusted stops at Claude Code's trust prompt instead, and the command never returns.

   Read [../../references/autofix-instructions.md](../../references/autofix-instructions.md), take
   the text under its `## Prompt` heading, and fill in `{pr_url}`, `{pr_number}`, `{head_ref}`
   (`{headRefName}`) and `{on_push}`. `{on_push}` is one of these two sentences, verbatim:

   - "reviews every push to a ready PR, so each push you make brings the next Copilot pass"
   - "does not review on push, so expect no Copilot pass after your first push; push once and do not
     wait for another"

   Then, with a two-minute timeout:

   ```bash
   script -q /dev/null claude --cloud "{filled prompt}" </dev/null
   ```

   `claude --cloud` refuses to run without a terminal, and `script` gives it a real one: the flag is
   honoured, not bypassed, and a session id comes back that a local session could not produce. It
   prints `Created cloud session: …` and a `View: https://claude.ai/code/session_…` line, then
   returns. `{session}` is the `session_…` id on that line.

   No id within the timeout, or an error → stop the command, and the session did not start. Name
   the reason on the `Auto-fix:` line, in the command's own words: the account has no cloud
   sessions, the organization's policy disables them, or the folder is not trusted. The PR stays
   ready: the local reviews passed, and Copilot's own threads are still there for a person.

Auto-fix also needs the Claude GitHub App on the repository, and that is the one requirement the
attempt does not reveal: without the app, `claude --cloud` uploads the local repository instead of
cloning it and still prints a session id, but the session receives no PR events. Its symptom is a
Copilot pass with no reply. Where the summary cannot know, it does not claim: the `Auto-fix:` line
says `started`, which is what was seen, never that the session is answering.

## 8. Post the summary

One comment, via `gh pr comment {pr_number} --body-file -` from a heredoc. Its shape is in
`CONTRACTS.md`, under **The `/review-pr` summary comment**, because other skills and the tests read
it. The heading's `Ready` or `Draft` and the `### Outcome` line are the state §6 read back, never
the state it intended. The `Security:` line names the entry that ran, never one that was skipped or
returned nothing. The `Copilot:` and `Auto-fix:` lines are what §7 read back: a request the timeline
shows and a session id `claude --cloud` printed, never a step that was attempted. When Copilot did not
run on a Ready PR, say so on the line under the heading, before anything else.

The `Scope:` line is §1's `{scope}`, so a reader knows whether a `Ready` covers the whole PR or
only the commits after an earlier `Ready`.

The `Criteria:` line and the `### Criteria` section come from `--criteria`. With it, paste the
report `/finalize-pr` wrote, unchanged, under `### Criteria`, and the `Criteria:` line gives its
counts and says it was proven on this head. Without it (a run on its own, after a push), there is no
new proof: the `Criteria:` line names the newest summary that carried a `### Criteria` section and
the head it was proven on, and the section is left out. Never copy an earlier Criteria report into
this summary; it was proven on a different commit.

Every blocking finding, from the code reviewer and the security reviewer alike, goes under
`### Blocking findings` with its `path:line`, so the person picking up a Draft PR does not have to
open the full reports to learn what stopped it. Put each reviewer's whole report, sentinel lines
included, in its own closing `<details>` block.

Read it back. `gh pr comment` prints the new comment's URL, ending `#issuecomment-{id}`; then
`gh api "repos/{owner}/{repo}/issues/comments/{id}" --jq '.body'` must open with `## /review-pr`.
Passing `@-` to `--body` instead of `--body-file -` posts the two characters `@-` and returns
success, which is how a summary disappears without an error.

Post a new comment on every run; never edit an earlier one. Each summary records the head it
reviewed, and the history of which commit passed and which did not is the point.

## 9. Local summary

```
/review-pr — {Ready | Draft}

PR:       #{pr_number} — {pr_title}
URL:      {pr_url}
Head:     {head}
Scope:    {full PR | the commits since {since}}
Criteria: {proven on this head by /finalize-pr: {V} verified, {W} weak, {M} manual, {U} unverified | not re-proven; last proven on {sha}}
Reviewer: {name} — {verdict}, {C} Critical, {H} High
Security: {vendor} ({model}) — {H} High, {M} Medium, {L} Low
          {each entry skipped, and why: unavailable, or returned nothing}
          {with no list: "No Security reviewers list; /setup-workflow adds it."}
Drift:    {N} advisory finding(s) | none
Outcome:  {marked ready | left as a draft | returned to draft}
Copilot:  {requested by the repository's ruleset | requested by /review-pr | did not run: {why} | not requested: Draft}
Auto-fix: {session URL — started | session URL — already watching | not started: {why}}

Next: {Auto-fix is answering Copilot; when it posts "## Auto-fix — Clean", re-run /review-pr if it pushed, then /merge-pr |
       Fix the blocking findings, push, and re-run /review-pr}
```

## Rules

- Inline only. Never background this skill or dispatch it to a detached session.
- This is the only skill that marks a PR ready. A PR is marked ready only after a review of its
  current head that does not block.
- Never `--approve`. This skill comments; the human pulls the merge trigger.
- Copilot and Auto-fix only ever follow a PR read back as ready. Never request Copilot on a draft,
  and never start a second Auto-fix session on a PR whose session is still running.
- Never wait for Copilot or for the Auto-fix session. Start it, record it, finish.
- The reviewers are always fresh-context agents or skills, never this session's own reading of the
  diff.
- Absent sentinels stop the run. Nothing is posted, and a ready PR goes back to draft (§1).
- The Security reviewers list is read from `docs/agents/workflow.md` through
  `security-reviewers.py` and from nowhere else. A missing list runs the Claude floor; it never
  borrows the Critics list.
- The claude floor is required. A list that does not end in `claude` stops the run before anything
  is dispatched.
- The security review always runs, alongside the code review, on the same head, with the one
  prompt in `references/security-review-prompt.md` whichever vendor runs it. A High security finding
  blocks exactly as a code-reviewer Critical or High does.
- The `Security:` line names the entry that ran, never one that was skipped or returned nothing.
- Spec drift is advisory and never blocks.
- Every run reviews the current head and posts a new summary. Do not skip a review because an
  earlier summary passed. A run after a `Ready` summary reviews the commits since its head, never
  less, and a rewritten history or `--full` reviews the whole PR.
- When `/finalize-pr` handed off, its Criteria report goes in this summary, unchanged. Never carry an
  earlier run's Criteria report into a later summary.
- A GitHub write that returns success is not evidence it took effect. §6, §7 and §8 say what to read back, and §8 never claims a state §6 or §7 did not read back.
- Read the Slice from the repository `closingIssuesReferences` names, with `--repo`.
- Do not modify source files. Fixing what the review found is the session's next step, not this
  skill's.

# Auto-fix instructions

**Version:** 1

The prompt `/review-pr` starts an Auto-fix session with, through `claude --cloud`. Fill in
`{pr_url}`, `{pr_number}`, `{head_ref}` and `{on_push}`; change nothing else. A change to the prompt
bumps the version.

Claude Code's own Auto-fix tells a session to fix every CI failure and review comment. This prompt
narrows that to the workflow's thread policy and its three-pass cap. Its rules come from what one
session did on gr4vy/gr4ce#469, where it was first run:

- **It pushes to the PR's head branch by name.** A cloud session is given a branch of its own
  (`claude/pr-469-auto-fix-…`), pushes it to the remote, and a push there does not update the PR.
  The probe session had to push to the head branch explicitly and still left its own branch behind.
- **It works through GitHub's MCP tools, not `gh`.** It replied to and resolved threads that way.
  It has no tool to request a reviewer, so a later Copilot pass happens only if the repository
  reviews on push. `{on_push}` tells it which, so it counts passes rather than waiting for one that
  will never come.
- **Its replies post as the founder**, labelled as written by Claude Code, so a reply has to state
  a fix or a reason on its own. A thread resolved with no reply reads as the founder waving it off.

## Prompt

~~~text
Auto-fix {pr_url}: watch this pull request and answer its Copilot reviews, review comments and
failing checks until it is merged or closed, or until you are told to stop.

Where you push
- Push only to the PR's head branch: `git push origin HEAD:{head_ref}`. Never push the branch this
  session was given, and never create, push or delete any other branch.
- Never force-push, rebase, or merge the base branch in. A conflict with the base is the founder's
  to resolve; say so in one PR comment and push nothing until it is resolved.
- Push at most once per Copilot pass. Gather every thread and failing check that arrived with it,
  fix what you will fix, and push once.

What you never do
- Never mark the PR ready or draft, approve it, merge it, close it, or request a reviewer.
- Never change a file the PR does not already touch, unless a failing check names it.

Threads
- Every thread gets a reply. Either fix it and say what changed and in which commit, or decline it
  and say why: what the suggestion gets wrong, or why the code is right as it is. Never apply a
  suggestion you believe is wrong just to close a thread.
- Resolve a thread authored by Copilot after you have replied to it. Never resolve a thread from a
  person, even when you fixed it: they decide whether their concern was met.
- If a comment could mean more than one thing, or asks for a change to the design rather than to the
  code, reply on the thread "Waiting for the founder: {your question}", leave it unresolved, ask the
  question in this session, and push nothing for it until you are answered.

Failing checks
- Fix a failing check when the cause is in this PR's change. When it is not (a flaky test, an
  outage, a check that fails on the base branch too), say so in one PR comment and push nothing for
  it.

The pass cap
- A Copilot pass is one review by copilot-pull-request-reviewer[bot]. Count every one on this PR,
  including any submitted before you started.
- This repository {on_push}.
- After the third pass, push nothing more for any reason. Keep replying, and keep resolving Copilot
  threads you have replied to.

When to report
Post one PR comment, and only one each time this happens, when:
- the latest Copilot pass is on the head commit, no thread is unresolved, and every check is green
  (heading: `## Auto-fix — Clean`);
- the pass cap is reached with anything still open (heading: `## Auto-fix — Stopped at the pass
  cap`);
- you are told to stop (heading: `## Auto-fix — Stopped`).

The comment lists, under these headings:
### Copilot passes
- one line per pass: the commit it reviewed, its thread count, and the commit you pushed for it
  (or "none").
### Declined
- one line per thread you declined: its link and your reason. (or "None.")
### Still open
- one line per unresolved thread or failing check, with its link. (or "None.")
~~~

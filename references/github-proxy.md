# The cloud GitHub proxy

Shared by every skill in this plugin. In a Claude Code cloud session, all GitHub traffic goes
through a proxy that keeps the real credential outside the VM. Per the
[cloud environments docs](https://code.claude.com/docs/en/cloud-environments#github-proxy):

> the proxy serves only a pinned set of GraphQL operations for pull-request workflows. The proxy
> rejects everything else on the GraphQL endpoint with a 403 that says `This GraphQL query is not
> enabled for this session` and names the REST fallback, `gh api repos/{owner}/{repo}/...`. The
> restriction applies to every request through the proxy regardless of the credentials you supply,
> so a `GH_TOKEN` you set gets the same 403.

Two consequences that shape everything below:

- **A token does not fix this.** It is a property of the environment, not of authentication. Do
  not respond to the 403 by hunting for credentials.
- **The pinned set is undocumented.** Nothing here should encode a guess about which operations
  are permitted, because that guess would rot silently the moment the set changes.

Nearly every `gh` subcommand these skills use is GraphQL underneath, including the read-only
`--json` ones. `gh pr diff` and `gh api` are the exceptions — both are REST.

## Rules

1. **Assignment is always REST.** Never `gh issue edit --add-assignee` or `gh pr edit
   --add-assignee`. See [Claiming an issue](#claiming-an-issue) — this is the one operation whose
   quiet failure breaks a cross-session invariant, so it gets a single path that behaves the same
   locally and in the cloud rather than a fallback that only runs when something already went
   wrong.

2. **Everything else: run the `gh` form, and fall back on the signature.** If a command fails with
   `This GraphQL query is not enabled for this session`, look it up in the table and run the REST
   equivalent. Triggering on the actual error keeps this correct without anyone maintaining a list
   of what the proxy currently permits.

3. **This 403 is never a warning.** Either the table gives a fallback and you run it, or the table
   says none exists and you **stop and tell the human what to do by hand**. A step that warns and
   continues leaves the workflow in a state a later step assumes is impossible — an unassigned
   issue two sessions can grab, or a correct-but-permanently-draft PR that `/merge-pr` refuses.

4. **Any 403 you worked around belongs in the skill's final summary.** The point of a fallback is
   that the work still lands, not that nobody hears about it.

## Claiming an issue

`gh issue edit {n} --add-assignee` fires `ReplaceActorsForAssignable` and `IssueUpdate`. The PR
spelling is worse: `gh pr edit {n} --add-assignee` also issues a `PullRequestProjectItems` query,
and the docs say Projects v2 is unreachable through the proxy at all.

Use REST. Pull requests are issues, so one endpoint covers both:

```bash
gh api -X POST "repos/{owner}/{repo}/issues/{n}/assignees" -f "assignees[]={login}"
```

Then **read the assignment back**, because a 2xx here does not mean it worked:

```bash
gh api "repos/{owner}/{repo}/issues/{n}" --jq '.assignees[].login'
```

GitHub's own contract is that assignees for users without push access are
"[silently ignored](https://docs.github.com/en/rest/issues/assignees)" — no error, empty result.
A caller who trusts the status code reports a claim it never made.

## `gh pr ready` has no fallback

`markPullRequestReadyForReview` exists only in GraphQL. REST's
[update-pull-request](https://docs.github.com/en/rest/pulls/pulls) endpoint takes `title`, `body`,
`state`, `base`, and `maintainer_can_modify` — **not `draft`**, which is writable only at creation.

So if this operation is outside the pinned set there is no workaround, and the honest move is to
stop rather than warn. The PR is finished and correct; it is just still a draft, and `/merge-pr`
hard-stops on drafts. A human clears it in one action, from outside the proxy:

```bash
gh pr ready {n}          # from a local checkout
```

or the **Ready for review** button on the PR page.

## Fallback table

Every GraphQL operation below was read off the wire with `GH_DEBUG=api` or confirmed in
[`cli/cli@trunk`](https://github.com/cli/cli).

**`{owner}` and `{repo}` are literal.** `gh api` substitutes them from the current repository, so
type them as written — unlike every other `{brace}` in these skills, they are not yours to fill in.
Quote the endpoint so no shell touches them. `{n}`, `{b}`, and the rest *are* placeholders.

### Mutations

| `gh` command | GraphQL operation | REST fallback |
|---|---|---|
| `issue edit {n} --add-assignee` | `ReplaceActorsForAssignable`, `IssueUpdate` | `gh api -X POST "repos/{owner}/{repo}/issues/{n}/assignees" -f "assignees[]={login}"` — **use unconditionally** |
| `pr edit {n} --add-assignee` | same, plus a Projects v2 query | same endpoint (`/issues/{n}/assignees`) — **use unconditionally** |
| `issue edit {n} --body` | `IssueUpdate` | `gh api -X PATCH "repos/{owner}/{repo}/issues/{n}" -F body=@-` |
| `pr edit {n} --body` | `PullRequestUpdate` | `gh api -X PATCH "repos/{owner}/{repo}/pulls/{n}" -F body=@-` |
| `pr edit {n} --base {b}` | `PullRequestUpdate` | `gh api -X PATCH "repos/{owner}/{repo}/pulls/{n}" -f base={b}` |
| `issue comment {n}` / `pr comment {n}` | `addComment` | `gh api -X POST "repos/{owner}/{repo}/issues/{n}/comments" -F body=@-` |
| `pr review {n} --comment` | `addPullRequestReview` | `gh api -X POST "repos/{owner}/{repo}/pulls/{n}/reviews" -f event=COMMENT -F body=@-` |
| `pr create --draft` | `PullRequestCreate` | `gh api -X POST "repos/{owner}/{repo}/pulls" -f title={t} -f head={b} -f base={d} -F draft=true -F body=@-` |
| `pr merge {n} --squash` | `mergePullRequest` | `gh api -X PUT "repos/{owner}/{repo}/pulls/{n}/merge" -f merge_method=squash` |
| `pr merge --delete-branch` | *(none — already REST)* | `gh api -X DELETE "repos/{owner}/{repo}/git/refs/heads/{branch}"` |
| `pr reopen {n}` | `reopenPullRequest` | `gh api -X PATCH "repos/{owner}/{repo}/pulls/{n}" -f state=open` |
| `pr ready {n}` | `markPullRequestReadyForReview` | **none** — stop, see above |

Two `gh api` habits worth keeping:

- `-F body=@-` reads the body from stdin, so heredocs work exactly as they do with `gh pr edit
  --body @-`.
- **A bare `-f`/`-F` makes the request a POST.** On a read, pass `-X GET` as well, or the endpoint
  answers a create request you didn't mean to send — which on `/pulls` is a 422 about a missing
  `base`, not an error message that points anywhere near the mistake.

### Reads

These are the likeliest members of the pinned "pull-request workflows" set, so they may well never
403. Fallbacks anyway:

| `gh` command | REST fallback |
|---|---|
| `pr view {n} --json …` | `gh api "repos/{owner}/{repo}/pulls/{n}"` |
| `issue view {n} --json …` | `gh api "repos/{owner}/{repo}/issues/{n}"` |
| `pr list --head {b} --json …` | `gh api -X GET "repos/{owner}/{repo}/pulls" -f state=open --jq '[.[] \| select(.head.ref=="{b}")]'` |
| `issue list --state open --json …` | `gh api -X GET "repos/{owner}/{repo}/issues" -f state=open --jq '[.[] \| select(has("pull_request")\|not)]'` — REST's issue list includes PRs |
| `repo view --json defaultBranchRef` | `gh api "repos/{owner}/{repo}" --jq '.default_branch'` |
| `pr view --json mergeStateStatus` | `gh api "repos/{owner}/{repo}/pulls/{n}" --jq '.mergeable_state'` — lowercase (`clean`, `behind`, `dirty`, `blocked`) |
| `pr view --json statusCheckRollup` | `gh api "repos/{owner}/{repo}/commits/{head_sha}/check-runs"` |
| `pr diff {n}` | *(already REST — no fallback needed)* |

**`closingIssuesReferences` has no REST equivalent.** GitHub does not expose a PR's linked issues
outside GraphQL. Within this plugin that costs nothing: `/start-issue` writes `Closes #{n}` as the
first line of every PR body, so parse the body for `Closes|Fixes|Resolves #(\d+)` instead. Say in
the summary that the link came from the body rather than from GitHub's own linkage.

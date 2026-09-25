---
name: frames
description: Capture the Frames a repository declares for a Slice's [manual] Criteria and publish them where a reviewer can see them. Reads docs/agents/frames.md, serves the built application on the Slice's own port block, drives Chrome through the chrome-devtools MCP, writes each Frame to the ui-evidence branch of the pull request's repository, and reports one row per Criterion. Use when the user says "/frames", "capture the screenshots", "show the UI change", or when /finalize-pr or a HITL session reaches the Frames step.
---

# Frames

Capture what a `[manual]` Criterion says a person would see, and put it where the person reviewing
the pull request will see it without building anything.

`/finalize-pr` runs this as a step. A HITL session runs it directly before it stops, so that the
smoke test starts from a picture rather than from a checkout. A human can type it.

## The shapes this skill reads and writes

`CONTRACTS.md` at the repo root: the Frame, its name, `docs/agents/frames.md`, where a Frame lands,
and the port block. Read it before changing anything below.

## Input

`$ARGUMENTS`: a PR number (`42` or `#42`). If empty, detect from the current branch.

## 1. Pre-flight

- Find the PR: `gh pr view {number} --json number,headRefName,closingIssuesReferences`. Without an
  argument, `gh pr list --head $(git branch --show-current) --json … --limit 1`.
- Read the Slice from **the repository the link names**, never from the pull request's own:

  ```bash
  gh pr view {n} --json closingIssuesReferences \
    --jq '.closingIssuesReferences[] | "\(.repository.owner.login)/\(.repository.name)#\(.number)"'
  gh issue view {issue} --repo {owner}/{repo} --json title,body
  ```

  A Slice tracked in one repository and built in another is normal, and a bare `gh issue view 53`
  reads whatever issue 53 is here. `CONTRACTS.md` has the rule and the reason.
- Parse `## Acceptance criteria` for the Criteria this Slice owns and their ids.
- **No `docs/agents/frames.md`** → report `frames: not declared in this repository` and stop, with
  nothing blocking. A repository that does not produce Frames is not failing anything.
- **No `[manual]` Criterion on this Slice** → report `frames: no [manual] Criterion` and stop.
- **Criteria carry no ids** → report `frames: skipped, the Slice's Criteria carry no ids` and stop,
  with nothing blocking. A Frame binds by id and there is nothing here to bind to.

## 2. Read the manifest and take the rows for this Slice

Parse `docs/agents/frames.md`: the `**Serve:**` line, and the table rows whose `Criterion` column
matches an id this Slice owns.

Every `[manual]` Criterion now falls into one of two sets, and they are reported differently at the
end:

- **declared** — it has a row. A Frame is expected, and its absence blocks.
- **undeclared** — it has none. Reported as `manual` with no Frame, blocking nothing.

No row for any of them → report and stop, as in §1.

## 3. Compute the port block

`base = 20000 + (issue_number mod 4000) * 10`, per `CONTRACTS.md`. The preview server is `base + 1`.

A dispatched session was told its block in its prompt. Use that when it is there, and compute it
when it is not; both give the same number, which is the point of deriving it from the issue.

## 4. Load the browser tools before using them

The chrome-devtools MCP tools arrive deferred, and a session that has not loaded them will report
the server as missing. One call, before anything else:

```
ToolSearch: select:mcp__chrome-devtools__new_page,mcp__chrome-devtools__navigate_page,mcp__chrome-devtools__resize_page,mcp__chrome-devtools__take_screenshot
```

No `mcp__chrome-devtools__*` tools after that call → **stop and say so**. The server is not
configured in this repository. `CONTRACTS.md` names what it needs, and the repository's `.mcp.json`
has to be on the default branch to reach a worktree.

## 5. Serve the application

Run the manifest's `**Serve:**` command with `{port}` substituted for `base + 1`, in the background,
and wait for it to answer:

```bash
until curl -sf "http://localhost:{port}/" >/dev/null; do sleep 1; done
```

Stop it in §8 whatever happens above. A serve command that fails is a stop with its output, not a
Frame that quietly did not get taken.

## 6. Capture each declared Frame

Per row, in order:

1. `new_page` at `http://localhost:{port}{path}`, in an isolated context. Keep the `pageId` it
   returns: `take_screenshot` needs it, whatever its schema says is required.
2. `resize_page` to the row's viewport.
3. `take_screenshot` with `filePath` set to `artifacts/ui/{id-slug}-{description}.png`, absolute.
   The slug is the Criterion's cited id per `CONTRACTS.md`; the description comes from the scene.

A `filmstrip` row is the same three steps with several captures of one page as it changes, stitched
into one image top to bottom. Capture a frame before the first interaction and one after the last,
so the strip reads as a sequence rather than as an ending.

**Read every Frame back before publishing it.** A capture that raced the render is a green-looking
step that publishes a blank page, and a blank page in a review comment is worse than no Frame: it
says the screen was checked. Check that the file is a PNG of the viewport's dimensions, and look at
it.

## 7. Publish to the evidence branch

Create `ui-evidence` in the **pull request's** repository the first time, as an orphan branch
carrying no history. The contents API cannot create a branch, and a ref cut from the default branch
would carry a copy of the whole tree, so this is three calls through the git data API:

```bash
gh api "repos/{owner}/{repo}/git/ref/heads/ui-evidence" >/dev/null 2>&1 || {
  tree=$(jq -n '{tree:[{path:"README.md",mode:"100644",type:"blob",
    content:"Frames published by /frames, one directory per pull request. Never merged."}]}' \
    | gh api -X POST "repos/{owner}/{repo}/git/trees" --input - --jq '.sha')
  commit=$(jq -n --arg t "$tree" '{message:"ui-evidence",tree:$t,parents:[]}' \
    | gh api -X POST "repos/{owner}/{repo}/git/commits" --input - --jq '.sha')
  gh api -X POST "repos/{owner}/{repo}/git/refs" -f ref=refs/heads/ui-evidence -f sha="$commit"
}
```

`parents: []` is what makes it a root commit. Everything after this is the contents API, which needs
the branch to exist and will 404 with `Branch not found` when it does not.

Then one call per Frame, through the contents API, so nothing is committed from the worktree and
the Slice's own branch stays exactly what the author wrote:

```bash
gh api -X PUT "repos/{owner}/{repo}/contents/pr-{pr}/{frame}.png" \
  -f branch=ui-evidence -f message="frames for #{pr}" -f "content=$(base64 -i {path})"
```

The URL a reviewer opens is
`https://github.com/{owner}/{repo}/blob/ui-evidence/pr-{pr}/{frame}.png?raw=true`.

Read the response's `content.sha` back. A 2xx from GitHub is not proof the write landed, and this
repository's skills read every GitHub write back.

## 8. Stop the server

Whatever happened above, including a stop in §5, §6 or §7.

## 9. Report

One row per `[manual]` Criterion, in the shape `/finalize-pr` puts in its review comment:

```
frames — 3 declared, 3 captured, published to ui-evidence

  #60 C2  captured   60-c2-cart-summary-balance.png   https://github.com/o/r/blob/ui-evidence/pr-64/…
  #60 C5  captured   60-c5-empty-cart.png             https://github.com/o/r/blob/ui-evidence/pr-64/…
  #60 C7  MISSING    declared at docs/agents/frames.md:9, capture failed: {reason}
  #60 C9  no frame   not declared in the manifest
```

`MISSING` blocks. `no frame` does not. `CONTRACTS.md` has the asymmetry and why it is the only part
of this that is a gate.

## Rules

- Never change a Criterion's state. A `[manual]` Criterion with a Frame is still `manual`, and a
  Frame is never evidence that a behaviour holds.
- Never capture a scene fed by anything but fixtures. No tenant data, no live credential, no card
  number, no session token on screen or in a captured URL.
- Never commit a Frame to the Slice's branch. Frames go to `ui-evidence` through the API.
- Never invent a scene. A Criterion with no manifest row has no Frame, and that is reported, not
  improvised around.
- Never publish a Frame nobody looked at. Read each one back first.
- Never start a server on a port outside this Slice's block, and never kill a process this skill
  did not start.
- Idempotent. Re-running replaces the Frames for this PR and nothing else.

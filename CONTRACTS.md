# Contracts

The shape of every artifact the slice workflow reads and writes, written down once.

A skill is free to change how it works. What it may not change unilaterally is the shape of what it
leaves behind, because another skill reads it. This document is that boundary. Read it to hand-write
a Spec file, a Spec issue body, or a Slice body that every skill in the plugin accepts, without
reading a single skill first.

It describes shapes, not skill behaviour. When you want to know what `/critique-spec` does, read
`/critique-spec`. When you want to know what it leaves on disk, read this.

Vocabulary is `CONTEXT.md`'s: Spec, Spec issue, Slice, Criterion, Seam, Critique, Verification.

## On this vocabulary

`CONTEXT.md` gives each term an _Avoid_ list. Those lists govern the words this document and the
skills choose when naming a concept. They do not reach inside a literal string that already exists
in the world. Three such strings appear below and are deliberate:

- **`## User Stories`** and **`## Acceptance criteria`** are section headings that Pocock's
  `/to-spec` and `/to-tickets` write. They are quoted here as the exact bytes a parser matches.
- **review comment** is a code review on a pull request. A Critique is a second model doubting a
  Spec before any Slice is built. Different artifacts, and the _Avoid_ entry exists to stop the
  second being called the first.
- **task list** is GitHub's own name for a `- [ ] #NN` block, and the _Avoid_ entry it brushes
  against governs what a Slice may be called rather than what GitHub calls its own checkbox syntax.

A term this document introduces that is not in `CONTEXT.md` and not one of the above is a bug in one
of the two files.

## The Spec file

### Location

```
docs/specs/{spec-issue-number}-{slug}.md
```

One file per Spec, on the default branch. The number is the Spec issue's; the slug is a lowercased,
hyphenated cut of its title. ADR 0001 records why the file lives in the repo and the Spec issue is
only its handle: every Slice worktree is cut from the remote default branch, so a committed file is
the only thing every parallel session can read.

**The file wins on conflict.** If the Spec issue body and the file disagree, the file is right and
the body is stale.

### Shape

```markdown
# {Spec title}

**Status:** draft
**Tracker:** #60

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

## Verification

Command: `pnpm test:e2e loyalty`
```

The first seven sections are `/to-spec`'s output, carried over unchanged. `## Criteria` and
`## Verification` are added by `/anchor-spec`.

### Verification takes one of two forms

Exactly one, never both:

- **Command form.** A line beginning `Command:` followed by a single runnable command. Run on a
  fresh checkout of the default branch after the last Slice merges.
- **Walkthrough form.** A line beginning `Walkthrough:` followed by numbered steps a person
  performs. Printed as the last thing the human is asked to do.

Command form is preferred wherever the feature can be proven that way.

### Lines that appear as the Spec moves

`**Status:**` and `**Tracker:**` are present from the first commit. Two more are appended in place,
each exactly one line:

```markdown
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
behaviour and name Seams. `/finalize-pr` finds the Specs a diff touches by matching Spec slugs and
`CONTEXT.md` terms against changed paths, which is why it needs no paths written down.

## Status, and who writes each value

Five values. One skill owns each transition, so a reader always knows whether the file describes the
code or an intention.

| Status | Meaning | Written by | When |
| --- | --- | --- | --- |
| `draft` | Synthesised, nobody has doubted it | `/anchor-spec` | On the first commit of the file |
| `critiqued` | A second model doubted it and the findings are resolved | `/critique-spec` | After the grilling round is applied |
| `in-progress` | At least one Slice is being built | `/dispatch-slices` | At the first fan-out |
| `implemented` | Every Slice landed and the Verification ran | `/merge-stack`, or `/merge-pr` for a single Slice | When the last Slice merges |
| `superseded` | A later Spec replaced it | by hand | Never automatically |

`/anchor-spec --skip-critique "<reason>"` is the one path that reaches `critiqued` without
`/critique-spec`, and it writes the reason into the Critique line.

`/dispatch-slices` refuses to fan out a Spec still at `draft`.

## The Spec issue body after anchoring

`/anchor-spec` rewrites the body it found to three things and nothing else:

```markdown
Spec: `docs/specs/60-loyalty-earn-and-burn.md` on the default branch

## Criteria

- C1 Loyalty ledger holds one credit row per earn-eligible line
- C2 [manual] Rewards balance renders in the cart summary
- C3 Unregistered client_id is rejected 401 within 200 ms

## Slices

- [ ] #61
- [ ] #62
- [ ] #63
```

The pointer is the repo-relative path, not a link: GitHub does not resolve relative links inside an
issue body, and a hardcoded blob URL pins a branch and a host.

**No prose.** The pointer, the Criteria list with ids and tags, the Slices task list. Whatever
narrative `/to-spec` published is now in the file, and a second copy on GitHub is a second thing to
drift.

The Criteria list is one line per Criterion: the id, the `[manual]` tag when present, and a summary
short enough to read in the issue. The full Given/When/Then lives in the file.

The body stays a body: labels, assignment, the Slices task list, and closing references keep working
exactly as they did before any of this.

## The Slice body

The sections the workflow reads. A hand-written Slice that carries them is indistinguishable from a
published one.

`/to-tickets` writes four of them: `## Parent`, `## What to build`, `## Acceptance criteria` and
`## Blocked by`. `## Seam` and `## References for context` are not in its template, so they arrive
by hand or not at all.

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

## References for context

- CONTEXT.md
- docs/adr/0001-specs-live-in-the-repo.md

## Blocked by

- None (can start immediately)
```

- **`## Parent`** holds the Spec issue reference, or is absent on a lone Slice.
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
```

Same grammar, same states in the review comment, same block on anything unverified. Skipping the
Spec is not a way to skip the tests.

## The Criterion grammar

### Ids

`C1`, `C2`, `C3`, in order, unique within one Spec. Never renumbered: a Criterion that is dropped
leaves a gap, because its id is already cited from a Slice, a test name, and a review comment.

Two forms:

| Form | Where |
| --- | --- |
| `C1` | Inside its own Spec file |
| `#60 C1` | Cited from a Slice body, carried in a test name, or named in a review comment |

The cited form is `#<spec-issue-number> C<n>`, one space between. It is globally unique, which is
what lets `/finalize-pr` match a test to a Criterion across repositories and across time.

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

A Criterion a person must check carries `[manual]` immediately after its id, in the Spec file, in
the Spec issue body, and in the Slice that cites it:

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

## The four Criterion states in the `/finalize-pr` review comment

`/finalize-pr` reports every Criterion the Slice owns as exactly one of four states. The state is
what was proven, not what was attempted.

| State | Rule |
| --- | --- |
| **verified** | A test whose name carries the Criterion's id exists, and the test gate passed |
| **weak** | Code in the diff appears to implement it, but no test carries the id |
| **manual** | The Criterion carries `[manual]`; listed for the human to check |
| **unverified** | Neither a test carrying the id nor identifiable code in the diff |

Shape in the comment:

```markdown
### Criteria

- verified    #60 C1 - `test/loyalty/earn.test.ts:14`, test gate green
- manual      #60 C2 - check the cart summary renders "240 points"
- weak        #60 C3 - `src/auth/client.ts:88`, no test carries the id
```

**verified is the only state that means the behaviour holds.** `weak` means there is code, which is
what "verified" used to mean and is why these four states exist.

`/finalize-pr` blocks on any `unverified`, in every repository, and never blocks on `manual`.

`weak` blocks only where a **test Seam** exists: where the toolchain `/finalize-pr` detects exposes a
runnable test command, so a test name carrying a Criterion's id is something the repository can
actually collect. Where none does, `weak` is the best state any Criterion can reach, and blocking
there would make every pull request unmergeable forever rather than asking the author for anything.

The Criterion is still reported as `weak` either way. What the test Seam changes is what `weak`
costs, never what it is called, and the review comment names which of the two rules it applied and
why, so a reader is never guessing which standard was used.

Red-before-green ordering is not checked. A test carrying the id and a green gate is the whole
contract.

Above ten Criteria on one Slice, `/finalize-pr` warns. It never blocks on the count.

## The per-repo workflow file

```
docs/agents/workflow.md
```

Beside `issue-tracker.md`, `triage-labels.md` and `domain.md`. One ordered list, and nothing else:

```markdown
**Critics:**
1. codex, default
2. google, gemini-3.8-flash-high
3. claude, claude-opus-5
```

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

Written by `/setup-workflow`, read by `/critique-spec`, and by nothing else. Changing the critics, or
their order, is an edit to this file and not a release of the plugin. There is no mode line and no
gate switch here: which gates block is not per-repo configuration.

Nothing in this file is loaded into a session's context. It is read on demand by the one skill that
needs it.

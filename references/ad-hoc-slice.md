# Ad hoc Slice

What `/create-bug` and `/create-feature` both do once they know what they are filing. They file
work that never went through a Spec, and what they leave behind is a **lone Slice**: the body
`CONTRACTS.md` describes, indistinguishable to `/dispatch-slices`, `/acceptance-tests` and
`/finalize-pr` from a Slice `/to-tickets` published.

Written once, here, because both skills owe exactly the same shape and a second copy is a second
thing to drift. The Slice body itself is `CONTRACTS.md`'s, under _The Slice body_ and _The
Criterion grammar_. Read those sections alongside this.

## Repo context

Read these before drafting, and skip any that do not exist without mentioning it:

- `docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md`, `docs/agents/domain.md`
- `CONTEXT.md` at the repo root, or the one a `CONTEXT-MAP.md` points at
- the ADRs that touch the area, and the area's `CLAUDE.md`

Every domain concept in the issue carries its `CONTEXT.md` term. When the issue contradicts an ADR,
the body says so: _Contradicts ADR-NNNN (…), worth reopening because…_

An area `CLAUDE.md` often names a prerequisite for changing that area, such as a design file to
start from or a contract document to update in the same change. One a test or gate can check
becomes a Criterion; any other becomes a line under `## References for context`. Either way the
session that builds the Slice meets it.

## Why a lone Slice, even under a Spec

A Slice with a `## Parent` owns Criteria of that Spec, and `/acceptance-tests` stops when the Spec
file is missing or the cited id is not in it. Ad hoc work adds behaviour no Spec Criterion
describes, so it owns none. Its checkboxes are filed with no id, and `/acceptance-tests` numbers
them `#{number} C{n}` under the Slice's own number and writes the ids back.

When the work belongs to an open Spec's area, link it to the Spec issue natively as a sub-issue and
name the Spec under `## Related`. The Spec issues are the open issues with sub-issues:

```bash
gh api graphql -f query='query($o:String!,$r:String!){repository(owner:$o,name:$r){issues(states:OPEN,first:100,orderBy:{field:UPDATED_AT,direction:DESC}){nodes{number title subIssues{totalCount}}}}}' \
  -f o={owner} -f r={repo} --jq '.data.repository.issues.nodes[] | select(.subIssues.totalCount>0) | "#\(.number) \(.title)"'
```

`{owner}` and `{repo}` come from `gh repo view --json owner,name`. Link the Slice to the Spec whose
sub-issues already change the code this Slice changes. No such Spec, or two equally, means no link,
which is common.

## Duplicates and related work

Search on two or three glossary terms with `gh issue list --state all --search "{terms}"`. An open
duplicate stops the skill: report it and ask whether to comment on it instead. Anything related goes
under `## Related`, with its state. A related issue whose PR has merged is history, not a blocker.

## How many Slices

A PR lands in one repository, so behaviour that needs a PR in two repositories is two Slices: one
per repository, the downstream one blocked by the upstream one, both filed in this tracker. Each
cuts through every layer its repository holds, and each is demoable against the other. The
downstream Slice's Criteria describe its own repository's behaviour, and its `## Blocked by` names
the upstream Slice by number once that one is filed.

A Slice carries at most ten Criteria, the count above which `/finalize-pr` warns. More than ten is
two Slices' worth of behaviour.

Behaviour still under argument, or work that needs more Slices than that, is a Spec. Say so,
recommend `/grill-with-docs` then `/to-spec`, and file nothing.

## The body

The sections `CONTRACTS.md` names, in this order, with the headings byte-exact. The type's own
sections come first.

```markdown
{the type's own sections, from the skill}

## What to build

{the behaviour as the user or caller meets it, stated as a decision}

## Seam

{the public boundary the tests observe this behaviour at, and an existing test that already uses it}

## Acceptance criteria

- [ ] {one measurable behaviour per box}

## Worth deciding

- {a choice this Slice makes, and why this way}
- **Open:** {a choice that needs a person before the Slice is built}

## References for context

- CONTEXT.md: {the terms that matter here}
- {repo-relative path}: {why it matters}

## Blocked by

- None (can start immediately)

## Related

- #N ({state}): {how it relates}
```

`## Worth deciding` and `## Related` are optional; omit an empty one.

**What to build** names functions and files where they locate the change, and keeps the list of
files for References. A hedge is a Worth deciding entry, so What to build reads as the answer.

**Seam** is the one section `/to-tickets` cannot fill and `/acceptance-tests` stops without in a
dispatched session. The skill found it while investigating; writing it here is what lets the Slice
run unattended.

**Acceptance criteria** are one line each, with no id, and each line states a Criterion under
`CONTRACTS.md`'s grammar: measurable, resolving to pass or fail. Observe behaviour at the Seam, not
the wording of a message. A Criterion only a person can check carries `[manual]` at its start.

**References for context** starts with `CONTEXT.md`, then the ADRs and area `CLAUDE.md`, then the
source and test files. A path in another repository is written `{owner}/{repo}:{path}`.

## Title

One sentence stating the behaviour, in glossary terms. A bug's title states the defect as a
present-tense fact ("The ledger credits a refunded line twice"). A feature's states what becomes
true ("A reader can export the ledger as CSV"). The type label carries the type. A title opens with
`[{repo}]` when the Slice's PR lands in a repository other than this tracker.

## Confirm, then publish

Show the title, labels, Spec link, blockers and full body of every Slice, and wait for approval.
Publishing is outward-facing; this is the step `/to-tickets` spends on its quiz.

Create each Slice the way `docs/agents/issue-tracker.md` says, upstream first so a downstream Slice
can name it under `## Blocked by`. Labels are exactly two, the type and one triage label, the triage
label by the first rule that matches:

1. `needs-info`: the report lacks what a reproduction or a Criterion needs.
2. `needs-triage`: `## Worth deciding` holds an **Open:** entry.
3. `ready-for-human`: a person has to do the work (console access, another team, a credential).
4. `ready-for-agent`: otherwise.

A `[manual]` Criterion leaves the label alone. An agent builds that Slice, and `/dispatch-slices`
routes it to a person for the check.

Label strings come from `docs/agents/triage-labels.md` when it exists. A label missing from
`gh label list` is left off, and the report names it.

## Native links

The `## Related` and `## Blocked by` text is for readers; GitHub's sub-issue list and dependency view
read the native links. Both mutations take node ids, from `gh issue view {n} --json id --jq .id`.

```bash
gh api graphql -f query='mutation($p:ID!,$c:ID!){addSubIssue(input:{issueId:$p,subIssueId:$c}){issue{number}}}' -f p={spec issue id} -f c={slice id}
gh api graphql -f query='mutation($i:ID!,$b:ID!){addBlockedBy(input:{issueId:$i,blockingIssueId:$b}){issue{number}}}' -f i={slice id} -f b={blocker id}
```

Done when, for every Slice filed, `gh api repos/{owner}/{repo}/issues/{n}/parent` names the Spec
issue it was linked to and `gh api repos/{owner}/{repo}/issues/{n}/dependencies/blocked_by` lists
every blocker. Report each Slice's URL, its labels, and those two read-backs.

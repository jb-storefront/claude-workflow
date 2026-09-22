---
name: acceptance-tests
description: Turn a Slice's Criteria into one failing test each, named with the Criterion's id, written at the Slice's Seam, run to show red, and committed. Asks for the Seam when the Slice names none, renames an existing test rather than duplicating it, and writes nothing for a [manual] Criterion. Use when the user says "/acceptance-tests", when a dispatched session has finished /start-issue, or before starting /tdd on a Slice.
---

# Acceptance Tests

Turn the Criteria a Slice owns into failing tests that carry their ids, before a line of
implementation exists. The Spec stops being a description and becomes an oracle: `/tdd` then runs
its red-green cycle inside a boundary somebody already agreed to, and `/finalize-pr` can call a
Criterion verified because a test carrying its id went green, not because the diff looks like it
tried.

Normally this runs as the second act of a dispatched session, after `/start-issue` and before
`/tdd`. The branch, the draft PR and the worktree already exist.

**This skill writes tests and nothing else.** No implementation, no stub that makes a test pass, no
production file touched. Every test it leaves behind is failing when it commits. Making them pass is
`/tdd`'s job, and a skill that does both hands `/tdd` a green suite and no work.

Read `CONTRACTS.md` before parsing anything: it defines the cited-id form, the test-name form, and
the Slice body this skill reads.

## Input

`$ARGUMENTS`: a Slice's number (`42` or `#42`). If empty, derive it from the current branch, which
`/start-issue` names `{prefix}/{number}-{slug}`. If that fails, read the PR's
`closingIssuesReferences`, and failing that the `Closes #{n}` line `/start-issue` writes as the
first line of the PR body.

If the number is still missing, **stop** and ask. Guessing which Slice you are on writes tests for
somebody else's Criteria.

## 1. Read the Slice

```bash
gh issue view {number} --json number,title,body,labels,url
```

Parse the body for the sections `CONTRACTS.md` describes:

- `## Parent` for the Spec issue number, or absent on a lone Slice
- `## Seam` for the public boundary the tests observe behaviour at, or absent
- `## Acceptance criteria` for the checkboxes citing the Criteria this Slice owns
- `## References for context` for repo-relative paths to read first

Read every path under `## References for context` that exists, plus `CONTEXT.md`, before writing a
test name. Test names are read by people and matched by `/finalize-pr`; they use the project's
words, not synonyms invented at the keyboard.

## 2. Resolve the Criteria to their full text

A Slice checkbox carries an id and a summary. The Given/When/Then the test has to assert lives
somewhere else, and the summary is not enough to write an assertion from.

**With a `## Parent`.** The Slice cites a Spec:

- The Spec file is `docs/specs/{parent-number}-{slug}.md` on the default branch. Find it with
  `ls docs/specs/{parent-number}-*.md`; a worktree is cut from the remote default branch, so it is
  already there.
- Read its `## Criteria` section. For every id the Slice cites, take the whole Criterion: its
  Given/When/Then or its EARS line, and its `[manual]` tag if it carries one.
- A cited id with no matching Criterion in the file, or a Spec file that does not exist, is a
  **stop**. Report which id and which path. Writing a test from a one-line summary is how a
  Criterion quietly becomes whatever the agent assumed it meant.

**With no `## Parent`.** A lone Slice is its own Spec:

- Its `## Acceptance criteria` checkboxes are the Criteria, numbered in order under its own issue
  number: the first becomes `#{number} C1`, the second `#{number} C2`, and so on. Never renumber on
  a re-run; read the ids already present and continue from the highest.
- The checkbox text is usually one line, not Given/When/Then. Do not invent the missing clauses.
  Read it as the Then, derive the Given and the When from `## What to build`, and put the proposal
  in the §3 confirmation. A lone Slice is held to the same gate, and the same gate needs a
  measurable Then.
- Once the ids are agreed, **write them back into the issue body**, each as a prefix of its
  checkbox text in the `#{number} C{n}` form:

  ```bash
  gh issue edit {number} --body-file {path}
  gh issue view {number} --json body --jq '.body' | grep -c '#{number} C'
  ```

  The read-back is not ceremony. `/finalize-pr` matches a test to a checkbox on those literal bytes,
  so ids that exist only inside test names leave every Criterion unverified at the gate.

`[manual]` Criteria are set aside here and carried to §7. They get no test.

## 3. Confirm the Seam

**No test is written at an unconfirmed Seam.**

When the Slice carries a `## Seam` section, that is the Seam. Read it and name it back in the
confirmation below, so a wrong Seam is caught before the tests are written rather than after.

When it does not, **ask**, and write nothing until an answer comes back. `## Seam` is not in
`/to-tickets`'s template, so its absence is normal, and it is exactly why this skill asks instead of
reading. Offer the candidates you found: the public entry points the Slice's prose implies, and the
boundaries the repo's existing tests already observe. Name the one you would pick, and do not
proceed on your own recommendation.

In a dispatched session with nobody to answer, **stop and report**: the Slice needs a `## Seam`
section and a re-dispatch. A Seam guessed by an unattended agent is the failure this gate exists to
prevent, and an hour of unattended work at the wrong boundary costs more than the round trip.

Confirm in one message, before writing anything: the Seam, the Criteria with their ids and full
text, which are `[manual]`, which existing test you intend to rename, and the test command you will
run. One confirmation, then work.

## 4. Learn the repo's test conventions

Read the tests that already exist at or near the confirmed Seam, and match them: the runner, where
files live, how they are named, how fixtures and setup are shared, whether cases are `test` or `it`,
how the suite is run. This skill contributes tests to a suite somebody else will keep. It does not
bring its own style.

Detect the test command the way `/finalize-pr` §5 does, from the lockfile at the repo root and the
manifest that declares the scripts, so the command the §7 summary reports is the one CI will run.

**No runner at the confirmed Seam** is a **stop**. Choosing a test framework is a standing decision
about the repo, not a side effect of starting a Slice. Report what the Seam is, report that nothing
runs tests there, and let the human decide. Some Seams are static gates rather than suites: a repo
whose only automated check is a validator has one, and a Criterion proved by that validator is a
Criterion whose test is a case added to it, not a suite scaffolded beside it.

## 5. Cover each Criterion exactly once

Work one Criterion at a time, in id order. For each, in this order:

1. **Is it already carried?** `grep -r '#{spec-number} C{n}'` across the test tree. A hit means an
   earlier run of this skill already covered it. Leave it alone and record it as already carried.

2. **Does a test already cover the behaviour?** Search the suite at the Seam for a test asserting
   what this Criterion's Then asserts. If one exists, **rename it to carry the id** rather than
   writing a second test for the same behaviour:

   ```diff
   - test("rejects an unregistered client", ...)
   + test("#60 C3 rejects an unregistered client with 401 within 200 ms", ...)
   ```

   A renamed test counts as the Criterion's test, and no duplicate is written for it. If the
   existing test asserts something weaker than the Then, strengthen the assertion to the Then's
   measurable form as part of the rename. That is the Criterion, and a rename that leaves a weaker
   assertion behind is a green test proving less than its name claims.

3. **Otherwise write one failing test.** The id is the prefix of the name, in the cited form
   `CONTRACTS.md` gives: `#60 C1` from a Slice with a Parent, `#74 C1` on a lone Slice.

   ```
   test("#60 C1 loyalty ledger holds one credit row per earn-eligible line", ...)
   ```

   Anything that puts those literal bytes in the name the runner reports works: a `describe` block
   wrapping several cases, a parametrised case, a Python `def test_60_c1_…` whose docstring carries
   the id where the runner reports docstrings.

   The Criterion's clauses are the test's structure. Given is the arrangement, When is the single
   act, Then is the assertion, and the assertion is the Then's measurable value taken from the Spec
   rather than recomputed the way the implementation would compute it. An EARS Criterion has the
   same two halves: the trigger is the act, the SHALL is the assertion.

   Write the test against the Seam's public interface only. No internal collaborator mocked, no
   private function called, no state read through a side channel. A test that reaches inside breaks
   on the first refactor and proves nothing about the Criterion.

## 6. Run them, and make sure they are red for the right reason

Run the suite. Every test written or renamed in §5 must fail, and each must fail because the
behaviour is absent: an assertion that did not hold, or a symbol that does not exist yet.

Two failures do not count as red, and both are fixed before committing:

- **A broken test.** A syntax error, a bad import, a collection or compile error. The suite never
  reached the assertion, so nothing was proven about the Criterion. Fix the test.
- **A green test.** It passes on the first run. Either the behaviour already exists, in which case
  §5.2 applies and the existing test should have been renamed, or the assertion is vacuous. Never
  weaken or delete an assertion to force red, and never add a failing stub to production code to
  manufacture it. Work out which of the two it is and say so.

A renamed test that was green before the rename and is green after is not a failure to fix. Record
it as already passing: the Criterion's behaviour exists, the id now names it, and `/tdd` has nothing
to do for that one. Say so in §7 rather than breaking a working test to satisfy a ritual.

Keep the command and its output. That run is the evidence the §7 summary reports, and a re-run after
the commit proves nothing about the state that was committed.

## 7. Commit, and report

Commit the tests alone:

```bash
git add {test paths}
git commit -m "test: failing Criterion tests for #{number}

Covers #{spec-number} C1, C3. C2 is [manual]."
```

Nothing but test files in the commit. If `git status --porcelain` shows a production file changed,
**stop** and explain what changed it. This skill did not.

Then print:

```
Slice:    #{number} - {title}
Spec:     docs/specs/{parent}-{slug}.md   (or "none" on a lone Slice)
Seam:     {the confirmed Seam}

Criteria
  #60 C1  test written     test/loyalty/earn.test.ts:14     failing
  #60 C3  test renamed     test/auth/client.test.ts:88      failing
  #60 C5  already carried  test/auth/client.test.ts:120     failing
  #60 C2  [manual]         the human checks: {the Then}

Test run: {command}
  {N} failing, {M} passing. Every Criterion test above is red.

Committed: {sha}

Next: /tdd to turn them green.
```

`[manual]` Criteria are always listed, always with the Then a person will check, and never with a
test. The list is what the human works from at review, so a tagged Criterion missing from it is a
check nobody does.

## Rules

- No test at an unconfirmed Seam, and no Seam inferred from labels, filenames, or the Slice's
  wording when the section is absent. Ask, or stop.
- One test per non-manual Criterion, and the count is checkable: N cited non-manual Criteria leave N
  tests on the branch, each carrying its id.
- Never write a test for a `[manual]` Criterion, and never drop one from the summary.
- Never touch production code. Not a stub, not a scaffold, not an import that makes a test compile.
  A missing symbol is a valid red.
- Never weaken an assertion, and never delete an existing test. Rename it if it covers the
  behaviour; leave it if it does not.
- Red before the commit, and the run that proves it is the one reported. Do not report a run you did
  not do.
- Ids are never renumbered. A Criterion's id is already cited from a Slice, a test name, and a
  review comment, so a gap is correct and a renumber is a break.
- On a re-run, cover what is not yet carried and leave the rest alone. Running this skill twice on
  the same Slice leaves the same tests, not two copies of them.

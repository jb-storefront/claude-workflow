# Spec close-out

What `/merge-pr` and `/merge-stack` do when a merge turns out to have landed a Spec's **last**
Slice. At that moment the feature is finished, and three things are owed: the Spec stops describing
an intention and starts describing the code, the whole feature gets proven rather than only its
Slices, and the Spec issue leaves the open list.

Written once, here, because both merge skills owe exactly the same thing and a second copy is a
second thing to drift. Neither skill owns it: `CONTRACTS.md` puts `implemented` on both.

Artifact shapes (the Spec, the Spec issue body, the Slice body, the Verification forms) are
`CONTRACTS.md`'s, not this document's. Read it alongside this.

## Input

The Slice issues the merge closed: one PR's `closingIssuesReferences` for `/merge-pr`, the same
pooled across the batch for `/merge-stack`.

## Where this runs

Nothing here writes to the repository. The Spec is the body of its Spec issue, so marking it
`implemented` is an issue edit, and every step except one runs from wherever the calling skill
already is.

The exception is a command-form Verification (§3), which proves the feature against the code the
merges produced and so needs a fresh default-branch tree. That tree is the main checkout, on the
default branch, with a clean tree. Not a slice worktree: the default branch is checked out in the
main checkout, so `git switch {default}` inside a worktree fails with *"already used by worktree at
…"* before anything else is attempted.

```
git branch --show-current   # note it as {return_branch}
git fetch origin {default} --prune
git switch {default}
git pull --ff-only origin {default}
git status --porcelain      # must be empty
```

Anything here failing → **pause and report**. A command run on a tree you cannot account for proves
nothing about the default branch.

Switch back to `{return_branch}` once the command has run, if it still exists. The calling skill
already chose where the checkout should end up, and this is a detour through the default branch,
not a decision to leave the human there. A walkthrough Verification runs nothing, so it never
leaves the branch you found.

## 1. Is anything due?

Most merges owe nothing. Establish that first, and cheaply.

For each closed Slice `{slice}`, find the Spec issue it is a sub-issue of:

```
gh api 'repos/{owner}/{repo}/issues/{slice}/parent' --jq .number
```

- A number → that is `{spec}`. This covers a lone Slice linked under a Spec too: it is on the
  Spec's roster, so its merge can be the one that lands the Spec.
- HTTP 404 (*No parent issue found*) → read the Slice's `## Parent` instead. An issue reference
  there is `{spec}`; the roster check below stops on it, because it names a Spec it was never
  linked to. **No `## Parent`, or no issue reference in it → a lone Slice** with no Spec, so there
  is nothing to close out. Skip it.

Dedupe the `{spec}` set — a batch often closes several Slices of one Spec — then for each `{spec}`:

- Read the Spec's roster, which `CONTRACTS.md` makes the Spec issue's sub-issues:

  ```
  python3 <this skill dir>/../../scripts/spec-slices.py {spec}
  ```

  ([spec-slices.py](../scripts/spec-slices.py).) Exit 1 → **pause and report** its `✘` lines as
  they are, and leave this Spec untouched: each names a Slice that is not a sub-issue, so the
  roster cannot say whether every Slice landed. Exit 2 → **pause and report**.

  Each Slice's `state` there is the tracker's own. A `## Slices` task list's checkbox is never
  read: a hand-written one can be ticked for an open issue.
- **Any Slice still `OPEN` → nothing is due for this Spec.** Leave the Spec issue exactly as it is,
  and say so in one line: `#60: 2 of 5 Slices still open, Spec untouched`.
- Every Slice `CLOSED` → the close-out runs for this Spec. An empty roster is never "every Slice
  closed": the Slice that brought you here is a sub-issue of `{spec}`, so an empty roster means the
  tracker changed underneath you. **Pause and report.**

Then read the Spec itself, which is due:

```
python3 <this skill dir>/../../scripts/spec.py read {spec}
```

([spec.py](../scripts/spec.py).) Pass `--repo {owner}/{name}` when the Spec issue lives in another
repository. Keep the JSON: §2 has nothing to read from it, but §3 reads its `verification` and §6
its `title`.

- Exit 1 → **pause and report** the `✘` line as it is, and leave this Spec untouched. When the line
  names `spec.py migrate`, the body is a pointer to a Spec file from before Specs lived in the issue:
  say to run that command first, which brings the Spec back into the issue. Writing
  `implemented` into a body that is not a Spec is worse than stopping.
- Exit 2 → **pause and report**. The tracker could not be read, which says nothing about the Spec.

## 2. Mark the Spec implemented

Two writes, both through `spec.py`, which reads each one back and exits non-zero when it did not
land:

```
python3 <this skill dir>/../../scripts/spec.py set-status {spec} implemented
python3 <this skill dir>/../../scripts/spec.py header {spec} landed "#61, #62, #63, 2026-09-24"
```

The Landed text is the pull requests, in the roster's order (the order GitHub lists the Spec
issue's sub-issues, which `spec-slices.py` keeps), then the date the last one merged (`date +%F`).

Each Slice's PR comes from the tracker, so a Slice merged weeks ago in some other session is listed
as readily as the one that just landed:

```
gh issue view {slice} --json closedByPullRequestsReferences --jq '.closedByPullRequestsReferences[].number'
```

A Slice closed by hand has no PR there. List the ones that exist and note the gap in the summary
rather than stopping. The Landed line records what built the Spec, and a Slice that closed without
a PR is a fact about the Spec worth seeing.

Either write exiting non-zero → **pause and report** its `✘` line. A refused transition (a Spec
still at `draft`, say) means something upstream was skipped, and that is the human's to see, not
this procedure's to paper over.

**`implemented` is written regardless of what the Verification goes on to do.** It means every
Slice landed, which is already true and does not become untrue if §3 fails. A failing Verification
produces a bug issue in §4; it does not roll the Status back to a value that would then claim the
code was never written.

Write it before running the Verification, not after. The Verification is the slow, fallible step:
it can hang, fail, or take the session down with it, and the state it would otherwise strand is
the one fact this whole procedure exists to record.

## 3. Run the Verification

Read `verification` from the JSON §1 kept. `CONTRACTS.md` gives it exactly one of two forms, and
`spec.py` reports `null` when the section is absent or carries neither or both. `null` →
**pause and report**; a Spec that does not say how it is proven cannot be closed out.

### Command form

`{"form": "command", "command": …}`. Take the checkout described under *Where this runs*, run the
command from the repo root on that fresh default-branch tree, and report **the command, its exit
code and its output**, not a verdict about it:

```
Verification: `pnpm test:e2e loyalty`
  exit 0
  ✓ 14 passed (8.2s)
```

Then switch back to `{return_branch}`. Exit non-zero → §4.

### Walkthrough form

`{"form": "walkthrough", "steps": …}`. Nothing to run, and no checkout to take. Carry the steps
through to §6 and print them **last**, after every other line of the summary, so the human's own
check is the thing left on screen rather than something scrolled past.

A walkthrough is never marked passed or failed here. Nobody has performed it yet.

## 4. A failing command opens a bug

The command form failed. Open a bug issue against the Spec, and stop there.

```
gh issue create \
  --title "Verification failed for #{spec}: {spec title}" \
  --body "The Verification for #{spec} failed on \`{default}\` at {sha} after its last Slice merged.

Spec issue: #{spec}

Command: \`{command}\`
Exit: {code}

\`\`\`
{output, tail-trimmed}
\`\`\`

Every Slice landed, so the Spec is marked implemented. What to do about this failure — fix forward,
or revert the Slices in the Landed line — is not decided here."
```

Apply the `needs-triage` triage role, resolved to this repo's actual label through
`docs/agents/triage-labels.md`. If that label does not exist in the repo, create the issue without
it rather than failing the close-out.

Report the new issue's number and URL in the summary, and **do not revert anything.** A revert
undoes several merged Slices on the default branch, and which of them is at fault is exactly what
nobody knows yet. The bug issue is the artifact; the decision stays the human's.

§5 still runs. The Spec issue closing and the bug issue opening are the same statement: the feature
is built, and this specific failure is now the live work.

## 5. Close the Spec issue

```
gh issue close {spec} --reason completed --comment "Implemented. Every Slice landed.

Landed: #61, #62, #63
Verification: {passed | failed, see #NN | walkthrough, printed for the human}"
```

Read it back — `gh issue close` reporting success is not the issue being closed:

```
gh issue view {spec} --json state --jq '.state'      # expect CLOSED
```

Still `OPEN` → report it as a stray. The Spec already reads `implemented`, so nothing is lost; the
issue just needs closing by hand. A closed issue stays readable and editable, which is how an
`implemented` Spec stays anchored to the code it describes.

## 6. What to print

Fold this into the calling skill's own summary, then the walkthrough — if there is one — after it.

```
Spec close-out — #{spec} {spec title}

Slices:       #61 #62 #63  (all closed)
Spec:         #60 [implemented, Landed 2026-09-24]
Verification: `pnpm test:e2e loyalty` → exit 0
Spec issue:   #60 [CLOSED]
```

```
Verification for #60 — walkthrough, for you to perform:

  1. Open the cart page with two earn-eligible lines in the basket.
  2. Submit the order.
  3. Confirm the rewards balance rises by one point per whole currency unit.
```

Skip the whole block for a Spec §1 found nothing due for; the one-line `2 of 5 Slices still open`
note is the entire report in that case.

## Rules

- Establish that something is due before touching anything. No Spec, Slices still open, or a Slice
  with no parent Spec each mean the Spec issue is left untouched.
- The Spec's Slices are its sub-issues, read through `spec-slices.py`. Trust the tracker's `state`
  for whether a Slice is closed, never a task list's checkbox, and never close out on an empty
  roster.
- Read and write the Spec only through `spec.py`. A body it will not parse is paused on, never
  edited by hand.
- Write `implemented` regardless of the Verification's result, and before running the
  Verification.
- Take the default-branch checkout only to run a command-form Verification.
- Report the Verification's command, exit code and output. Never summarise it as a verdict.
- Never revert a Slice, and never re-run a failed Verification hoping for a different answer. Open
  the bug issue and hand the decision over.
- Print a walkthrough Verification last, after everything else the calling skill prints.
- Read back every GitHub write this document specifies a read-back for.
- Leave the checkout on the branch you found it on.

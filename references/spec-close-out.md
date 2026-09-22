# Spec close-out

What `/merge-pr` and `/merge-stack` do when a merge turns out to have landed a Spec's **last**
Slice. At that moment the feature is finished, and three things are owed: the Spec file stops
describing an intention and starts describing the code, the whole feature gets proven rather than
only its Slices, and the Spec issue leaves the open list.

Written once, here, because both merge skills owe exactly the same thing and a second copy is a
second thing to drift. Neither skill owns it: `CONTRACTS.md` puts `implemented` on both.

Artifact shapes — the Spec file, the Spec issue body, the Slice body, the Verification forms — are
`CONTRACTS.md`'s, not this document's. Read it alongside this.

## Input

The Slice issues the merge closed: one PR's `closingIssuesReferences` for `/merge-pr`, the same
pooled across the batch for `/merge-stack`.

## Where this runs

The main checkout, on the default branch, with a clean tree. Not a slice worktree: the default
branch is checked out in the main checkout, so `git switch {default}` inside a worktree fails with
*"already used by worktree at …"* before anything else is attempted.

```
git branch --show-current   # note it as {return_branch}
git fetch origin {default} --prune
git switch {default}
git pull --ff-only origin {default}
git status --porcelain      # must be empty
```

Anything here failing → **pause and report**. Every step below either reads the tree the batch
produced or commits to it, and neither is safe on a checkout you cannot account for.

Switch back to `{return_branch}` once §6 is done, if it still exists — the calling skill already
chose where the checkout should end up, and this procedure is a detour through the default branch,
not a decision to leave the human there.

## 1. Is anything due?

Most merges owe nothing. Establish that first, and cheaply.

For each closed Slice `{slice}`:

- `gh issue view {slice} --json body --jq '.body'`
- Read `## Parent`. **No `## Parent`, or no issue reference in it → a lone Slice.** It has no Spec,
  so there is nothing to close out. Skip it.
- Otherwise the issue number in that section is `{spec}`.

Dedupe the `{spec}` set — a batch often closes several Slices of one Spec — then for each `{spec}`:

- `gh issue view {spec} --json body,title,state`
- Read the `## Slices` task list for every issue reference in it. That list is the Spec's roster of
  Slices.
- Ask the tracker for each one's state: `gh issue view {n} --json state --jq '.state'`.

  **Not the checkbox.** GitHub ticks `- [x]` on its own when a referenced issue closes, but a
  hand-written Spec issue can carry a ticked box for an issue that is open, and an unticked one for
  an issue that is closed. The issue's own `state` is the fact; the checkbox is a rendering of it.
- **Any Slice still `OPEN` → nothing is due for this Spec.** Leave the Spec file and the Spec issue
  exactly as they are, and say so in one line: `#60 — 2 of 5 Slices still open, Spec untouched`.
- Every Slice `CLOSED` → the close-out runs for this Spec.

Then read the Spec file's path from the first line of the Spec issue body, which `/anchor-spec`
wrote as a repo-relative path in backticks:

```
Spec: `docs/specs/60-loyalty-earn-and-burn.md` on the default branch
```

No such pointer, or the path is not on disk → **pause and report**. Do not guess the filename from
the issue number and title: a Spec whose title was edited after anchoring no longer slugs back to
its own file, and writing `implemented` into a file that was never the Spec is worse than stopping.

## 2. Mark the Spec implemented

Two edits to the Spec file, both in its header block:

- `**Status:**` → `implemented`.
- Append a `**Landed:**` line after the last header line already present (`**Tracker:**`, or
  `**Critique:**` when the Spec was critiqued):

  ```markdown
  **Landed:** #61, #62, #63, 2026-09-24
  ```

  The pull requests, in the order the Slices appear in the Spec issue's `## Slices` list, then the
  date the last one merged (`date +%F`).

  Each Slice's PR comes from the tracker, so a Slice merged weeks ago in some other session is
  listed as readily as the one that just landed:

  ```
  gh issue view {slice} --json closedByPullRequestsReferences --jq '.closedByPullRequestsReferences[].number'
  ```

  A Slice closed by hand has no PR there. List the ones that exist and note the gap in the summary
  rather than stopping — the Landed line records what built the Spec, and a Slice that closed
  without a PR is a fact about the Spec worth seeing.

**`implemented` is written regardless of what the Verification goes on to do.** It means every
Slice landed, which is already true and does not become untrue if §4 fails. A failing Verification
produces a bug issue in §5; it does not roll the Status back to a value that would then claim the
code was never written.

## 3. Commit it to the default branch

```
git add {spec_file}
git commit -m "docs: mark #{spec} implemented"
git push origin {default}
```

**Push rejected → open a pull request instead**, the way `/anchor-spec` does when the default
branch is protected:

```
git switch -c docs/{spec}-implemented
git push -u origin docs/{spec}-implemented
gh pr create --title "Mark #{spec} implemented" --body "Records that every Slice of #{spec} landed."
git switch {default}
```

Then carry on with §4 and report the pull request in the summary. The Verification runs against the
default branch, and the Spec's Status line is not part of what it proves.

Commit before verifying, not after. The Verification is the slow, fallible step — it can hang, fail,
or take the session down with it — and the state it would otherwise strand is the one fact this
whole procedure exists to record.

## 4. Run the Verification

Read the Spec file's `## Verification` section. `CONTRACTS.md` gives it exactly one of two forms.
Neither present, or both → **pause and report**; a Spec that does not say how it is proven cannot be
closed out.

### Command form

A line beginning `Command:` followed by one runnable command. Run it from the repo root on the
default branch, the tree §3 just committed to, and report **the command, its exit code and its
output** — not a verdict about it:

```
Verification: `pnpm test:e2e loyalty`
  exit 0
  ✓ 14 passed (8.2s)
```

Exit non-zero → §5.

### Walkthrough form

A line beginning `Walkthrough:` followed by numbered steps. Nothing to run. Carry the steps through
to §7 and print them **last**, after every other line of the summary, so the human's own check is
the thing left on screen rather than something scrolled past.

A walkthrough is never marked passed or failed here. Nobody has performed it yet.

## 5. A failing command opens a bug

The command form failed. Open a bug issue against the Spec, and stop there.

```
gh issue create \
  --title "Verification failed for #{spec}: {spec title}" \
  --body "The Verification for #{spec} failed on \`{default}\` at {sha} after its last Slice merged.

Spec issue: #{spec}
Spec file: \`{spec_file}\`

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

§6 still runs. The Spec issue closing and the bug issue opening are the same statement — the feature
is built, and this specific failure is now the live work.

## 6. Close the Spec issue

```
gh issue close {spec} --reason completed --comment "Implemented. Every Slice landed; Spec file: \`{spec_file}\` on \`{default}\`.

Landed: #61, #62, #63
Verification: {passed | failed, see #NN | walkthrough, printed for the human}"
```

Read it back — `gh issue close` reporting success is not the issue being closed:

```
gh issue view {spec} --json state --jq '.state'      # expect CLOSED
```

Still `OPEN` → report it as a stray. The Spec file is already correct on the default branch, so
nothing is lost; the issue just needs closing by hand.

## 7. What to print

Fold this into the calling skill's own summary, then the walkthrough — if there is one — after it.

```
Spec close-out — #{spec} {spec title}

Slices:       #61 #62 #63  (all closed)
Spec file:    docs/specs/60-loyalty-earn-and-burn.md  [implemented, Landed 2026-09-24]
Committed:    {pushed to main | PR #91 — default branch is protected}
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
  with no parent Spec each mean the Spec file and the Spec issue are left untouched.
- Trust the tracker's `state` for whether a Slice is closed, never the task list's checkbox.
- Read the Spec file's path from the Spec issue's pointer line. Never reconstruct it from the issue
  number and title.
- Write `implemented` regardless of the Verification's result, and commit it before running the
  Verification.
- Report the Verification's command, exit code and output. Never summarise it as a verdict.
- Never revert a Slice, and never re-run a failed Verification hoping for a different answer. Open
  the bug issue and hand the decision over.
- Print a walkthrough Verification last, after everything else the calling skill prints.
- Read back every GitHub write this document specifies a read-back for.
- Leave the checkout on the branch you found it on.

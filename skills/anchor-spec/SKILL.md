---
name: anchor-spec
description: Turn a published Spec issue into a persisted Spec file on the default branch — derive numbered Given/When/Then Criteria and a Verification from its user stories, confirm them with the founder, commit the file, and rewrite the issue body to a pointer, the Criteria list, and the Slices task list. Opens a pull request instead when the default branch rejects the push. Use when the user says "/anchor-spec", "anchor the spec", "persist this spec", or has just finished /to-spec.
---

# Anchor Spec

Take the Spec issue `/to-spec` published and leave one Spec file on the default branch at Status
`draft`, with a Spec issue whose body points at it.

This is the step between `/to-spec` and `/to-tickets` in the
`/to-spec` → **`/anchor-spec`** → `/critique-spec` → `/to-tickets` → `/dispatch-slices` loop. It runs
in the **main checkout**, on the default branch, because that is the one commit every Slice worktree
is cut from.

Nothing here forks Pocock's `/to-spec`. This skill runs after it and reads what it published.

`CONTRACTS.md` at the repo root owns the shapes this skill writes: the Spec file, the Spec issue
body, and the Criterion grammar. Read it alongside this skill; where the two disagree, `CONTRACTS.md`
is right.

## Input

`$ARGUMENTS`: a Spec issue number (`60` or `#60`), optionally followed by
`--skip-critique "<reason>"`.

If the number is missing or invalid, run `gh issue list --state open --limit 10` and ask which
issue to anchor.

`--skip-critique "<reason>"` is the one path to Status `critiqued` that does not run
`/critique-spec`. It writes the reason into the Critique line, so the skip is auditable. A reason is
required; `--skip-critique` with no reason is an error, not an empty reason.

## 1. Pre-flight

This skill commits to the default branch, so it needs a checkout it is safe to commit on.

- **Not in a worktree.** `git rev-parse --git-common-dir` differing from `--git-dir` means this is a
  worktree. **Stop**: a worktree sits on a Slice branch, and the Spec belongs on the default branch
  every worktree is cut from.
- `{default}` = `gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'`. Never a
  hardcoded `main`.
- `git fetch origin {default}`, then `git switch {default}`. If the switch fails on local changes,
  **stop** and report — the founder's working tree is theirs to resolve.
- `git log --oneline origin/{default}..{default}` non-empty → **stop**. Anchoring pushes the default
  branch, and pushing somebody's unrelated unpushed commits as a side effect of writing a Spec is
  not this skill's business. Ask them to push or move those commits first.

## 2. Read the Spec

`gh issue view {number} --json number,title,body,labels,state`. Not found, or not open → **stop**
and report.

Then decide which source you are deriving from:

- **First anchoring.** The body holds `/to-spec`'s prose. Derive from the body.
- **Re-anchoring.** A file already exists at `docs/specs/{number}-*.md`, or the body already starts
  with a `Spec:` pointer line. The prose is in the file now and the issue body no longer has it.
  Derive from the **file**, never from the body: `CONTRACTS.md` says the file wins on conflict, and
  a body rewritten by an earlier run holds only summaries.

On a re-anchoring, read the existing Criteria first and **never renumber them**. Their ids are
already cited from Slices, test names, and review comments. A Criterion you drop leaves a gap; a
Criterion you add takes the next id after the highest one ever used in that file.

## 3. Derive the Criteria

Read `## User Stories` for the behaviour, and the rest of the Spec for the numbers that make a Then
measurable — `## Implementation Decisions` and `## Testing Decisions` are where the thresholds,
error codes, and limits usually are.

The grammar is `CONTRACTS.md`'s, and these are the parts that go wrong most:

- **Given/When/Then by default**, three clauses, one per line. **EARS** —
  `WHEN <trigger> THE SYSTEM SHALL <behaviour>`, one line — for a constraint that holds always and
  would need a fictional Given: a latency, a limit, a status code.
- **Every Then resolves to pass or fail.** "Fast", "gracefully", "correct", "properly",
  "reasonable", "appropriate" each mark a Then not yet written. Replace it with the number, the
  status code, or the literal string a reader can check. An EARS `SHALL` clause is held to exactly
  the same bar — the form changes, the measurability requirement does not.
- **`[manual]` immediately after the id** on any Criterion a human must check. This tag is the only
  thing that later decides a Slice needs a person, so a Criterion whose check you cannot imagine
  automating gets tagged now. It is tagged because automating it is not worth it, not because it is
  hard to write.
- **Ids are `C1`, `C2`, `C3`** in order.

Stories do not map one-to-one onto Criteria. Collapse two stories that describe the same observable
behaviour into one Criterion; split a story that promises two separately checkable things into two;
write none for a story that is pure rationale with nothing to observe.

**Name no file paths.** Not in a Criterion, not anywhere you write. A path is a promise about
structure that the next refactor breaks silently. Name behaviour, and name the Seam.

## 4. Propose the Verification

The Verification proves the **whole feature** after the last Slice lands, which is what makes it
different from a Criterion. Exactly one form, never both:

- **`Command:`** followed by a single runnable command, to be run on a fresh checkout of the default
  branch after the last Slice merges. Preferred wherever the feature can be proven this way.
- **`Walkthrough:`** followed by numbered steps a person performs, printed as the last thing the
  founder is asked to do.

Prefer command form. Reach for a walkthrough when what the feature changes is something only a
person can see.

## 5. Confirm before writing anything

Show the founder the full proposed Criteria — every clause, not a summary — and the proposed
Verification, and say plainly that nothing has been written yet. Then wait.

The Spec is theirs, not yours. This is the same beat `/to-spec` runs when it confirms seams.

Alongside the proposal, raise anything you had to decide for them:

- A story you wrote no Criterion for, and why.
- A Then you had to pick a number for because the Spec never gave one.
- A file path in the carried-over sections. Carry those sections over unchanged — they are the
  founder's prose, not yours to silently rewrite — but a path in a Spec is what makes a Spec rot,
  so name it and let them decide.

Apply what they change, then proceed. Do not write on a silence or on an ambiguous answer.

## 6. Write the Spec file

`docs/specs/{number}-{slug}.md`, creating `docs/specs/` if it is not there. Slug: the issue title
lowercased, non-alphanumeric runs to hyphens, repeats collapsed, trimmed, truncated to ≤50 chars
without cutting mid-word, trailing hyphens stripped.

```markdown
# {Spec title}

**Status:** draft
**Tracker:** #{number}

{the sections /to-spec produced, carried over unchanged}

## Criteria

### C1
Given ...
When ...
Then ...

### C2 [manual]
Given ...
When ...
Then ...

## Verification

Command: `{command}`
```

The carried-over sections are `## Problem Statement`, `## Solution`, `## User Stories`,
`## Implementation Decisions`, `## Testing Decisions`, `## Out of Scope` and `## Further Notes`, in
that order, byte for byte. One that `/to-spec` did not write is skipped, not invented.

`## Criteria` and `## Verification` are yours, and they go last.

With `--skip-critique "<reason>"`, the Status line reads `critiqued` instead of `draft` and one
Critique line is appended after the Tracker line:

```markdown
**Status:** critiqued
**Tracker:** #{number}
**Critique:** skipped, {reason}, {YYYY-MM-DD}
```

Without the flag there is no Critique line at all. `/critique-spec` writes it when it runs.

## 7. Commit to the default branch, or open a pull request

Commit only the Spec file. Whatever else is in the working tree stays there.

```bash
git add docs/specs/{number}-{slug}.md
git commit -m "docs: anchor the Spec for #{number}"
git push origin {default}
```

**If the push succeeds, you are done with git.** Go to step 8.

**If the push is rejected**, the default branch is protected. That is detected here and nowhere
else: there is no mode, no flag, and no setting that says so, and reading the branch protection API
needs admin rights the founder may not have. Recover onto a branch:

```bash
git branch docs/{number}-{slug}           # name the commit without moving HEAD
git reset --keep origin/{default}         # default branch back to the remote's tip
git switch docs/{number}-{slug}
git push -u origin docs/{number}-{slug}
gh pr create --title "Anchor the Spec for #{number}" --body "Anchors the Spec for #{number} at Status draft.

Dispatch waits for this to merge: every Slice worktree is cut from the remote default branch, so the Spec file has to be there before a Slice can read it.
"
```

`--keep` rather than `--hard`: it aborts on local changes instead of destroying them. If it aborts,
**stop and report** — the commit is safe on `docs/{number}-{slug}` and the founder's tree is theirs.

The pull request body must **not** carry `Closes #{number}`. The Spec issue is the Spec's handle for
the whole feature and closes only when the Spec reaches `implemented`. A closing reference here would
shut it on the first merge.

Then tell the founder, in the summary, that `/dispatch-slices` must wait for that pull request to
merge.

## 8. Rewrite the Spec issue body

`gh issue edit {number} --body-file -` with exactly three things:

```markdown
Spec: `docs/specs/{number}-{slug}.md` on the default branch

## Criteria

- C1 {one-line summary}
- C2 [manual] {one-line summary}

## Slices

- [ ] #61
- [ ] #62
```

- The pointer is the **repo-relative path, not a link**. GitHub does not resolve relative links in
  an issue body, and a blob URL pins a branch and a host.
- One line per Criterion: the id, the `[manual]` tag when it carries one, and a summary short enough
  to read in the issue. The full Given/When/Then stays in the file.
- The Slices task list: carry over any `- [ ] #NN` list already in the body. On a first anchoring
  there is none, because `/to-tickets` has not run yet — leave the heading with nothing under it.
  That empty section is where `/to-tickets` writes.

Rewrite the body on **both** paths out of step 7. When the Spec file is still sitting in a pull
request, the pointer names where it is about to be rather than where it is, and that is the right
trade: `/to-tickets` needs the Criteria list to cite ids from, and the pointer comes true the moment
the pull request merges. The summary is what tells the founder to wait.

**No prose survives.** Whatever narrative `/to-spec` published now lives in the file, and a second
copy on GitHub is a second thing to drift.

Labels, assignment, and closing references are untouched — this rewrites the body and nothing else.

## 9. Print the summary

```
Spec:     #{number} — {title}
File:     docs/specs/{number}-{slug}.md
Status:   {draft | critiqued (critique skipped: {reason})}
Criteria: {n} ({m} manual)
Verify:   {Command: ... | Walkthrough, {k} steps}
Landed:   {pushed to {default} | PR {url} — dispatch waits for this to merge}

Next: {/critique-spec {number} | /to-tickets, then /dispatch-slices {number}}
```

`Next:` is `/critique-spec` at Status `draft`, and `/to-tickets` when the critique was skipped.

## Rules

- **Confirm before writing.** Step 5 is not optional and not a formality. Nothing reaches disk, git,
  or GitHub before the founder answers.
- **Never renumber a Criterion.** Ids are cited from Slices, test names, and review comments. A
  dropped Criterion leaves a gap in the sequence; that gap is correct.
- **The file wins on conflict.** On any re-run, derive from the file, not from the issue body.
- **Never write a file path into a Spec.**
- **Never put `Closes #{number}` on the anchoring pull request.**
- **Never `git reset --hard`, and never force-push.** `--keep` is the only reset here.
- Run in the main checkout, never in a worktree.
- If a git or `gh` command fails anywhere outside the expected push rejection in step 7, stop and
  report rather than working around it.

---
name: create-bug
description: File a bug as a lone Slice that /dispatch-slices, /acceptance-tests and /finalize-pr read like any other. Use when the user says "/create-bug", "file a bug", "this is broken", or "open a bug for …".
---

# Create bug

File a bug outside the Spec loop as a lone Slice. The shape, the labels, the links and the
confirmation are [../../references/ad-hoc-slice.md](../../references/ad-hoc-slice.md)'s, and the
Slice body is `CONTRACTS.md`'s. Read both before step 1.

## Steps

1. **Load the repo context** that the reference names.
2. **Reproduce it.** Trace the code path and confirm the bug on the current default branch without
   changing the checkout. Record the short commit SHA, the environment and the date. A local
   reproduction of a bug reported from a deployed environment counts; say which. A bug you could
   not reproduce is still fileable, as `needs-info`, with what you tried.
3. **Find the cause.** Separate the root cause from the symptom it was reported as. When the report
   names a downstream effect of a more basic defect, the Slice is about the basic one. A cause you
   could not verify is written as a hypothesis naming where to look.
4. **Find the tests that pin it.** A test asserting the defect as today's behaviour changes with the
   fix. Name it in `## Worth deciding`, so the change reads as the fix and not as a weakened test.
5. **Decide the fix.** Write `## What to build` as the fix you would ship, and the Seam its tests
   observe. Real alternatives become `## Worth deciding` entries.
6. **Find the Spec, duplicates and Slice count**, per the reference.
7. **Draft** each Slice: the bug's sections below, then the reference's body.
8. **Confirm, publish, link**, per the reference. The type label is `bug`.

## The bug's sections

```markdown
## What goes wrong

{actual against expected, from the user's side, and who is affected}

## Steps to reproduce

1. …

{verified on {sha}, {environment}, {date}; or: not reproduced, and what was tried}

## Cause

{verified, with its evidence; or: hypothesis, look at …}

## Severity

{critical | high | medium | low}: {who is hit, how often, and whether any figure or data is wrong}
```

## The bug's Criteria

The first Criterion is the one that goes **red** on the bug today: the defect, observed at the Seam.
Then one per behaviour the fix guarantees, including each neighbouring behaviour that must survive
it. Severity stays in the body.

## Bug description

`$ARGUMENTS`

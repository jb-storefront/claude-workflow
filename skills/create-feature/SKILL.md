---
name: create-feature
description: File a feature request as a lone Slice that /dispatch-slices, /acceptance-tests and /finalize-pr read like any other, or route it to /grill-with-docs when it is a Spec. Use when the user says "/create-feature", "file a feature request", "propose a feature", "I want to add …", or "we need a feature for …".
---

# Create feature

File a feature outside the Spec loop as a lone Slice. The shape, the labels, the links and the
confirmation are [../../references/ad-hoc-slice.md](../../references/ad-hoc-slice.md)'s, and the
Slice body is `CONTRACTS.md`'s. Read both before step 1.

## Steps

1. **Load the repo context** that the reference names.
2. **Map where it lands.** Trace every code path the feature crosses, end to end, in every
   repository it touches, and the existing pattern each layer follows. Find the highest Seam that
   observes the behaviour, and an existing test at that Seam.
3. **Count the Slices**, per the reference. A Spec goes to `/grill-with-docs`, and this skill files
   nothing for it.
4. **Decide the behaviour.** Write `## What to build` as the behaviour you would ship. Every choice
   you made on the user's behalf is a `## Worth deciding` entry, and every choice that still needs
   them is an **Open:** one.
5. **Find the Spec and duplicates**, per the reference.
6. **Draft** each Slice: the feature's sections below, then the reference's body.
7. **Confirm, publish, link**, per the reference. The type label is `enhancement`.

## The feature's sections

```markdown
## Why

{the problem from the user's side: who hits it, when, and what it costs them today}
```

And after `## Worth deciding`:

```markdown
## Out of scope

- {each neighbouring behaviour this Slice leaves alone}
```

## The feature's Criteria

One per behaviour the feature guarantees, observed at the Seam. Then one for each existing
behaviour the change could plausibly break. A new dependency, a migration or a breaking change is a
Criterion or a `## Worth deciding` entry.

## Feature description

`$ARGUMENTS`

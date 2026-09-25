# Slice workflow

The vocabulary of the spec-to-merge loop this plugin runs: one persisted spec per feature, cut into slices that parallel sessions build in their own worktrees and land as reviewed PRs.

## Language

**Spec**:
The persisted document describing one feature's behaviour, from problem through criteria to how the whole thing is verified.
_Avoid_: PRD, plan, tracker issue

**Spec issue**:
The tracker issue that is a Spec's handle: it carries the labels, the assignment, and the closing references, and points at the Spec.
_Avoid_: parent issue, PRD issue, tracker issue

**Slice**:
One vertical cut through every layer of a feature, tracked as one issue, built in one session, landed as one PR.
_Avoid_: ticket, task, child issue, slice issue

**Criterion**:
One Given/When/Then line in a Spec, carrying an id, that resolves to pass or fail. EARS form ("WHEN ... THE SYSTEM SHALL ...") is used for constraints that are not user behaviour.
_Avoid_: AC, acceptance criterion, requirement, user story

**Seam**:
The public boundary a test observes behaviour at, agreed before any test is written.
_Avoid_: interface under test, test boundary

**Critique**:
The findings a second model returns on a Spec before any Slice is dispatched: ambiguities, missing edge cases, decisions an agent would make silently, and criteria that do not resolve to pass or fail.
_Avoid_: review, red team, analysis

**Verification**:
The Spec's end-to-end proof that the whole feature works, run or walked through after the last Slice lands. Distinct from a Criterion, which proves one behaviour.
_Avoid_: smoke test, QA, acceptance test

**Scene**:
One screen of an application rendered from fixtures the repository controls, reached at a path, so that what it shows depends on the code under review and on nothing else.
_Avoid_: story, demo page, fixture page

**Frame**:
The image of a Scene that a `[manual]` Criterion is proven by, named after that Criterion's id. Stands to a manual Criterion as a test stands to an automated one.
_Avoid_: screenshot, capture, visual

**Port block**:
The ten ports one Slice owns while its session runs, derived from its issue number so that parallel Slices never contend for one.
_Avoid_: port range, port offset

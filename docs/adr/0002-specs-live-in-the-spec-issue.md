# Specs live in the Spec issue, not in the repo

Supersedes 0001.

0001 moved every Spec into `docs/specs/{issue}-{slug}.md` on the default branch so that a Spec would
outlive its feature and something could detect the code drifting from it. Both goals held. The cost
was that every change to a Spec became a change to the repository: moving `draft` to `critiqued` to
`in-progress` to `implemented` took four commits, and on a protected default branch four pull
requests, each waiting on review and CI to record one line, and so did every edit to the prose.

We put the Spec back in the body of its Spec issue and keep everything 0001 bought with the file.
A closed issue is still readable and editable, so an `implemented` Spec outlives its feature there as
well as it did on disk. `/review-pr` finds the implemented Specs a diff touches by listing Spec
issues at that Status instead of globbing a directory. The Status line, the Criterion grammar and
the gates are unchanged. One script, `scripts/spec.py`, reads and writes the body, so the grammar is
enforced in one place rather than by convention.

With nothing left to persist, `/anchor-spec` had one job left, deriving the Criteria, and it moved
into `/critique-spec`: the critic doubts the proposed Criteria and the founder settles both in one
round, instead of confirming Criteria in one skill and reopening them in the next. Bringing a Spec
anchored under 0001 back into its issue is `spec.py migrate`, a deterministic copy, so it is a tested
script rather than a skill.

0001's other argument, that a committed file is the only thing every parallel worktree can read,
did not survive contact: every session already reads its Slice from the tracker with `gh`, and
reading the Spec the same way costs nothing. It also fixes a case the file got wrong, a Slice built
in a different repository from the one holding its Spec, where the file was never on the pull
request's branch at all.

What we give up: a Spec change can no longer ride in the same pull request as the code that changes
the behaviour, and a Spec's history is GitHub's edit history rather than `git log`. A running Slice
also reads the Spec as it is now rather than as it was when its worktree was cut. We take all three:
a Spec is edited far more often than code needs to be atomic with it, and a Slice reading the
current Spec is the behaviour we want.

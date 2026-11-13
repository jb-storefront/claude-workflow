# Changelog

Releases 2.2.0 to 2.8.0 shipped without a changelog. Their entries below were written afterwards
from the version bumps in git history. Numbers in parentheses are pull requests.

## 3.1.0 (unreleased)

Each check after the code is written now runs in one place.

- `/finalize-pr` pushes first and reads the quality gates from CI on the pushed head. It runs lint,
  typecheck, format and tests locally only in a repository with no CI that runs them. It used to
  run them locally and then read CI too, and read CI before pushing, so the rollup could belong to
  an older commit.
- `/finalize-pr` stops only when the branch conflicts with its base. Being behind no longer stops
  it, because a `pull_request` check tests the merge with the current base; `/merge-pr` still warns.
- The AI-debris pass moves from `/finalize-pr` to the `/review-pr` code reviewer, which runs in a
  fresh context. The catalog is now `references/ai-debris.md`. `/finalize-pr`'s review comment
  drops its `### AI-discipline findings` section.
- `/merge-pr` folds its CI step into the Copilot step, which already read the checks.
- After a `Ready` summary, `/review-pr` reviews only the commits since the head it named, with the
  whole PR as context, instead of reviewing the whole PR again. An Auto-fix push of a few lines gets
  a review of those lines. The summary's new `Scope:` line says which ran; a rebase, a force-push or
  `--full` brings back a full review. `merge-gate.py` reports `last_ready`, and the security prompt
  (now version 2) takes any revision as `{base}`.
- One comment per run. A Not blocking `/finalize-pr` no longer posts its own review: it hands its
  Criteria report to `/review-pr`, whose summary carries it under `### Criteria` with a new
  `Criteria:` line. A Blocking `/finalize-pr` still posts its report, since `/review-pr` does not
  run.
- The code-reviewer agent template says the quality gates and the generic security review belong
  to other steps, and keeps only the project's own security invariants.

## 3.0.0 (2026-11-12)

### Breaking

- **The Spec is the body of its Spec issue again.** Specs no longer live in
  `docs/specs/{n}-{slug}.md`, so a Status change or a body edit no longer needs a pull request.
  ADR 0002 supersedes ADR 0001. (#70)
- **`/anchor-spec` is removed.** `/critique-spec` now derives the Criteria and the Verification from
  the user stories and writes the Spec into the issue once, after the critique round. Run
  `/critique-spec` straight after `/to-spec`. (#70)
- **A Spec issue that still points at a Spec file stops `/dispatch-slices`.** Run
  `python3 scripts/spec.py migrate {n}` to copy the file back into the issue body. It keeps the
  Status and leaves the file for you to delete. (#70)

### Added

- `scripts/spec.py` is the only reader and writer of a Spec issue body, and it refuses any Status
  transition the contract does not allow. (#70)

### Upgrading from 2.1.0

Everything below shipped in 2.2.0 to 2.8.0 and 3.0.0. The release got stricter in some places
and deliberately looser in others, and you need both lists to know what will stop you.

**Now blocks**

- `/dispatch-slices` stops on a Spec at Status `draft`. Nobody has doubted it yet.
- `/dispatch-slices` stops on a Spec issue whose body is a legacy Spec-file pointer, and names
  `spec.py migrate`. (3.0.0)
- `/dispatch-slices` stops on a coverage gap: a Spec Criterion that no Slice cites, a Slice citation
  the Spec does not have, or a Criterion two Slices both cite.
- `/dispatch-slices` and the Spec close-out stop on a Slice that names the Spec, under `## Parent`
  or a legacy `## Slices` list, but is not linked as a sub-issue. The stop prints the command that
  links it. (2.6.0)
- `/finalize-pr` blocks on any `unverified` Criterion, everywhere.
- `/finalize-pr` blocks on a `weak` Criterion **where a test Seam exists**.
- `/finalize-pr` blocks on a Frame the repository's manifest declared that did not come back.
- `/finalize-pr` blocks on a `[command]` Criterion whose command failed or did not run, including
  when a credential is missing. (2.8.0)
- `/review-pr` is the only skill that marks a PR ready. It returns a PR to draft on a Critical or
  High code-review finding, or a High security finding. (2.5.0)
- `/merge-pr` and `/merge-stack` refuse a head newer than the one the latest `/review-pr` summary
  reviewed, and merge with `--match-head-commit`. (2.7.0)

**Narrowed or made optional**

- A Spec issue with no `**Status:**` line warns rather than stopping. It means the Spec was never
  anchored, which is not the same as skipping a step.
- A Parent at `implemented` or `superseded` warns rather than stopping.
- `**Specs:** off` in `docs/agents/workflow.md` turns every Spec gate off for a repository that
  keeps no Specs. Every Slice is then a lone Slice, held to the same tests.
- `weak` never blocks where no test Seam exists. A gate that fires on every pull request in a
  repository teaches people to ignore it.
- `[manual]` never blocks, and a Frame does not change that in either direction.
- A Copilot pass that is not clean is a warning at merge, not a refusal. (2.7.0)

**Skills added**

`/critique-spec`, `/acceptance-tests`, `/setup-workflow`, `/frames`, `/review-pr`, `/create-bug`,
`/create-feature`, `/create-infra-request`.

**Skills removed**

- `/anchor-spec`, which shipped in 2.2.0 to 2.8.0. (3.0.0)
- `/retro`. Use Pocock's, which arrives with the dependency. (2.3.0)

**Behaviour removed**

- The label and wording inference that decided which Slices need a person. `[manual]` tags alone
  decide.
- The empty commit `/start-issue` made to open its draft PR. The PR now opens with the first real
  commit.

## 2.8.0 (2026-11-11)

- A Criterion proven by running a command carries `[command]` and a `Command:` line. `/finalize-pr`
  runs it and reports `verified` on exit 0. A command that failed or did not run is `unverified`,
  never `weak`. (#69)
- `/finalize-pr` ticks verified Criteria and changes no other byte of the Slice. It reports a
  missing id or a wrong-looking tag for a person to fix. (#69)

## 2.7.0 (2026-11-11)

- `/review-pr` hands a ready PR to Copilot and one cloud Auto-fix session, capped at three Copilot
  passes, and finishes without waiting. (#68)
- `/merge-pr` and `/merge-stack` refuse a head newer than the latest `/review-pr` summary, merge
  with `--match-head-commit`, and stop the Auto-fix session first. Copilot not being clean is a
  warning. (#68)

## 2.6.0 (2026-11-11)

- A Spec's Slices are its GitHub sub-issues, and the Spec issue body drops its `## Slices` task
  list. A legacy entry that is not a sub-issue stops every reader with the command that links it.
  (#66)

## 2.5.0 (2026-11-11)

- New `/review-pr`: code review, security review and the spec-drift check, run from a fresh context
  and posted as one summary. It is the only skill that marks a PR ready. `/finalize-pr` keeps the
  evidence work and hands a passing PR on. (#60)
- `/review-pr` walks the Security reviewers list, and every vendor gets Anthropic's Claude Code
  security review prompt. (#64)
- `/setup-workflow` writes a Security reviewers list into the per-repo workflow file. (#61)
- The rules for walking an ordered model chain live in `references/chain-walking.md`, cited by
  `/critique-spec` and `/review-pr`. (#58)
- `scripts/clean-predicate.py` decides whether a PR is clean, pending, or not. (#59)

## 2.4.0 (2026-11-10)

- New `/create-infra-request`: raises an Infrastructure request on the team that owns the
  infrastructure, instead of a hand-made change. (#62)

## 2.3.1 (2026-11-10)

- `/merge-pr` and `/merge-stack` prune the plugin records a removed worktree leaves behind. (#50)

## 2.3.0 (2026-11-10)

- `/retro` is removed in favour of Pocock's, which the dependency now installs. (#49)

## 2.2.0 (2026-11-10)

Everything from the Spec work in #12. It landed between 2026-09-21 and 2026-11-10 without a
version bump, so all of it first shipped here.

- Installing `workflow` installs `mattpocock-skills@claude-plugins-official` as a dependency. (#48)
- `CONTRACTS.md`, the glossary and ADR 0001 land, and `./scripts/validate.sh` runs on every pull
  request. (#23, #24)
- New `/anchor-spec`, which wrote the Spec file and rewrote the Spec issue. (#25)
- New `/critique-spec`, which sends the Spec to a second model and resolves the findings with you.
  It walks an ordered critic chain, Codex then Google then Claude, and falls through on a vendor
  that is installed but cannot answer. (#27, #33)
- New `/acceptance-tests`, which turns a Slice's Criteria into failing tests named with each
  Criterion's id. (#28)
- `/finalize-pr` reports each Criterion as `verified`, `weak`, `manual` or `unverified`, blocks on
  `unverified`, and checks for Spec drift. It blocks on `weak` only where a test Seam exists. (#30,
  #40)
- New `/setup-workflow`, which makes a bare repo ready for the loop. (#26)
- The merge skills set a Spec to `implemented`, run its Verification and close its Spec issue when
  the last Slice lands. (#29)
- `/dispatch-slices` refuses a `draft` or uncovered Spec, and `[manual]` tags alone decide which
  Slices need a person. A missing Spec warns instead of stopping. (#32, #39)
- `**Specs:** off` in the per-repo workflow file declares a repository keeps no Specs. (#43)
- A `[manual]` Criterion is shown by a Frame from the new `/frames`. Each dispatched Slice owns a
  ten-port block derived from its issue number. `/finalize-pr` reads a Slice from whichever
  repository the closing reference names. (#44)
- New `/create-bug` and `/create-feature`, which file ad hoc work as a lone Slice. (#45)
- `/start-issue` makes no empty commit, and the draft PR opens with the first real one. (#47)
- `/estimate-from-history` reads author dates, so a rebased pull request is no longer discarded.
  (#41)

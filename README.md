# claude-workflow

Personal [Claude Code](https://code.claude.com) skills for a spec-to-merge loop over
GitHub-tracked vertical slices, each running in its own **git worktree** on your machine.

## Install

Three commands, then restart Claude Code (or run `/reload-plugins`):

```bash
claude plugin marketplace add anthropics/claude-plugins-official
claude plugin marketplace add jb-storefront/claude-workflow
claude plugin install workflow@jb-workflow
```

That one install brings in both halves of the workflow. The loop leans on four skills from
[mattpocock/skills](https://github.com/mattpocock/skills) (`/grill-with-docs`, `/to-spec`,
`/to-tickets`, `/tdd`), and this plugin declares `mattpocock-skills@claude-plugins-official` as a
dependency, so Claude Code installs and enables it alongside. The first `marketplace add` is there
because a fresh Claude Code does not always know Anthropic's official marketplace, and without it
the dependency cannot resolve and **this plugin refuses to load**.

Check it worked:

```bash
claude plugin list
```

Both `workflow@jb-workflow` and `mattpocock-skills@claude-plugins-official` should say
`enabled`. If `workflow` says `failed to load` with *Dependency ... is not installed*, the official
marketplace is missing: run the first command above, then `claude plugin install
mattpocock-skills@claude-plugins-official`.

Upgrading an existing install? `claude plugin marketplace update jb-workflow`, then
`claude plugin update workflow@jb-workflow`. [CHANGELOG.md](CHANGELOG.md) says what now blocks and
what no longer does. Read its "Upgrading from 2.1.0" section if you are coming from 2.1.0 or earlier.

## Set up a repo

Run once in the **main checkout** of each repo that will use the loop, and commit what they write:

```
/setup-matt-pocock-skills   →  issue tracker, triage labels, domain-doc layout (docs/agents/)
/setup-workflow             →  everything in "What a repo needs" below, plus agent templates
```

Order matters: `/setup-workflow` checks that Pocock's setup has run and tells you if it has not.
Both explore first, show a draft, and write only after you confirm, and both are safe to re-run.

`/setup-workflow` also commits the plugin block into `.claude/settings.json`, so anyone who clones
the repo is offered both plugins when they first trust the workspace:

```json
{
  "extraKnownMarketplaces": {
    "jb-workflow": {
      "source": { "source": "github", "repo": "jb-storefront/claude-workflow" }
    },
    "claude-plugins-official": {
      "source": { "source": "github", "repo": "anthropics/claude-plugins-official" }
    }
  },
  "enabledPlugins": {
    "workflow@jb-workflow": true,
    "mattpocock-skills@claude-plugins-official": true
  }
}
```

## The loop

```
/grill-with-docs     →  reach shared understanding, update CONTEXT.md and ADRs inline   (Pocock)
/to-spec             →  publish the spec as a tracker issue                             (Pocock)
/critique-spec       →  add Given/When/Then Criteria, have another vendor's model doubt them, settle both
/to-tickets          →  break the spec into independently-grabbable slice issues        (Pocock)
/dispatch-slices     →  fan the unblocked slices out to parallel background sessions
  └ per slice, inside its own worktree:
      /start-issue      →  claim, branch, install deps; draft PR on the first commit
      /acceptance-tests →  one failing test per Criterion, at the Slice's Seam
      /tdd              →  red-green-refactor to the acceptance criteria               (Pocock)
      /frames           →  capture what a [manual] criterion says a person would see
      /finalize-pr      →  gates, Criteria, PR description; hands a passing PR on
      /review-pr        →  code review, security review and spec drift; the only skill that marks ready;
                           hands the PR to Copilot and a cloud Auto-fix session that answers it
/merge-stack         →  land the batch in dependency order, tearing down worktrees
```

Everything not marked (Pocock) ships in this plugin, as do `/rebase-pr` and `/merge-pr` for the
single-PR cases.

**When to skip the Spec half:** when the behaviour is already settled and fits in one Slice per
repository with ten Criteria or fewer, file it with `/create-bug` or `/create-feature` and start at
`/dispatch-slices`. Everything from there on still runs, so skipping the Spec is not a way to skip
the tests. A repository that keeps no Specs at all says so once with `**Specs:** off` in
`docs/agents/workflow.md`: `/dispatch-slices` then treats every Slice as a lone one and runs no
Spec gate.

### How far this has been proven

The per-Slice half has run on real pull requests in another repository: `/finalize-pr`,
`/review-pr`, and the Copilot and Auto-fix handoff, and `/create-bug` and `/create-feature` have
been dry-run against real cases. Every pull request here runs `./scripts/validate.sh`, which
validates the plugin and marketplace manifests and runs the test suites for the scripts the skills
call. **No Spec has yet gone through the whole loop**, from `/grill-with-docs` to the close-out
that marks it `implemented`. Until one has, treat the Spec half as validated statically and not
proven end to end.

`/critique-spec` is best with Codex or Antigravity installed, so the doubt comes from another
vendor. Neither is required, and neither is installed for you: `/setup-workflow` reports which
are missing and prints the commands. Without them the Claude critic still runs. `/review-pr`'s
security review walks its own list the same way, and every vendor gets the same prompt: Anthropic's
Claude Code security review, adapted to run anywhere.

Four more sit beside the loop rather than inside it:

- **`/create-bug`** and **`/create-feature`** file ad hoc work as a lone Slice, shaped so the loop
  runs it like one `/to-tickets` published, with its Seam already written. Work that turns out to
  be a Spec goes to `/grill-with-docs` instead.
- **`/create-infra-request`** raises an Infrastructure request on the team that owns the
  infrastructure a change needs, in the tracker and shape the repo's `docs/agents/infrastructure.md`
  declares, instead of a pull request on their repository or a resource changed by hand.
- **`/estimate-from-history`** sizes work against the repo's own merged PRs instead of human
  intuition, which is wrong by an order of magnitude when the work is done by parallel sessions.
  It answers in slices first and quotes a band, never a point estimate.

For a retrospective on a finished session, use Pocock's `/retro`. It proposes changes to the
agent's *environment* (navigation pointers, automated checks, reviewer rules) rather than to the
code.

## What a repo needs before the first fan-out

Run `/setup-workflow` (see [Set up a repo](#set-up-a-repo)). It gitignores `.claude/worktrees/`,
writes a `.worktreeinclude` when the repo has gitignored config a worktree would otherwise lack,
commits the plugin block, writes `docs/agents/workflow.md`, copies the agent templates, and adds
the pointer block to `CLAUDE.md`. Re-run it rather than editing those by hand.

Two things it cannot do for you:

- **Workspace trust accepted once.** Run `claude` in the repo and accept the dialog. Worktrees live
  inside the trusted checkout, so background sessions never ask again.
- **`gh` authenticated with push access to the repo.** Not a convenience: `/start-issue` claims
  its issue by adding an assignee, and GitHub silently ignores assignees without push access. The
  skill reads the assignment back and stops, so without push access every dispatched session dies
  on its first step.

Dependencies are not a precondition: `/start-issue` installs them in each worktree from the
project's lockfile.

`/estimate-from-history` additionally wants `.claude/calibration/calibration.json`, committed. It
generates it from the repo's merged PRs on first use; see that skill for the knobs.

## Design notes

**Isolation is git's job, and the CLI manages it.** Each slice runs in
`.claude/worktrees/issue-{n}`, a separate working directory sharing the repository's history and
remote. `claude --bg --worktree issue-{n}` creates it, `claude agents --json` lists what is
running, and `claude rm <id>` removes the session and its worktree. None of that has to be
hand-rolled any more, which is most of why this version is shorter than the one it replaces.

**Isolation stops at the filesystem, so ports are handed out rather than found.** A worktree keeps
five sessions from seeing each other's files and does nothing about the machine they share, where
every tool's default port is the same number in all five. Each Slice owns ten ports derived from its
issue number, `/dispatch-slices` puts the resolved range in the prompt, and a listening port outside
that range is declared to belong to someone else. The bug this ends is not the collision, which a
session usually survives. It is the reasoning that follows one: a session finds a port taken, cannot
explain it, and goes looking, sometimes as far as killing the process holding it.

**`manual` was the one Criterion state with no evidence.** `verified` cites a test, `weak` cites the
code, `unverified` cites nothing and says so, and `manual` cited a sentence asking a reviewer to go
and look, which meant building the branch before they could disagree with anything. `/frames`
captures the screen a `[manual]` Criterion describes from fixtures the repo controls, names the file
after the Criterion's id so the binding is mechanical rather than a judgement, and publishes it to a
`ui-evidence` branch the default branch never merges. A Frame is evidence for a `manual` Criterion;
it never promotes one, because a screen that rendered is not a behaviour that holds.

**A worktree pins its branch, and that shapes the merge skills.** Git allows one checkout per
branch, so while a slice's worktree exists the main checkout cannot `git switch` to that branch or
`git branch -D` it. `/rebase-pr` and `/merge-stack` therefore rebase *inside* the worktree with
`git -C`, and `/merge-pr` and `/merge-stack` stop the session and remove the worktree before
deleting the branch. Getting that order wrong produces *"already used by worktree at"* and a branch
nobody can clean up.

**Verified against 2.1.263.** The dispatch prints `backgrounded · {id}` and returns without a TTY,
so a skill can launch a fan-out from a piped Bash call. Worktrees land at `.claude/worktrees/<name>`
on a branch `worktree-<name>`, cut from the **remote** default branch (`worktree.baseRef` defaults
to `"fresh"`; set it to `"head"` to branch from local HEAD instead). The short id after
`backgrounded · ` is the `id` field in `claude agents --json`, not the `sessionId` uuid beside it.
Re-verify on a much later build rather than trusting the note; the fan-out step has already been
rewritten twice for CLI behaviour that changed underneath it.

**`claude logs` is for humans.** It prints the session's raw terminal — ANSI escapes, cursor
addressing, spinner frames, kilobytes of it for a session that ran one command. No skill here parses
it. Progress comes from `claude agents --json` (`state`: working / blocked / done / failed) and from
the slice's own issue and PR.

**Background sessions get `--dangerously-skip-permissions`; nothing else does.** A detached session
has nobody to answer a permission prompt, so it stalls as `Needs input` and waits indefinitely — an
overnight fan-out can idle on a single `git push`. Sessions a human is watching read the repo's
committed `permissions.allow`, which is narrow and reviewable, and they keep it.

**Agents stay with their project.** `/finalize-pr` dispatches a PR-writer and `/review-pr` a
code-reviewer, both found in the project's own `.claude/agents/`, matched by role rather than filename, because a
useful reviewer knows the domain (`ucp-demo-code-reviewer`, `gr4ce-code-reviewer`). This plugin ships
no agents; with none in the project, `/finalize-pr` writes the PR body inline and `/review-pr`
runs Pocock's `code-review` skill in place of the reviewer.

**A GitHub write that returns 2xx is not a GitHub write that happened.** Adding an assignee over
REST silently ignores users without push access, so `/start-issue` claims its issue and then reads
the assignment back before creating a branch. That ordering matters more than the retry does: the
claim is what stops `/dispatch-slices` handing the same slice to a second session, and it is worth
nothing if it lands after the branch and PR it was meant to protect.

**The human still pulls the merge trigger.** `/finalize-pr` and `/review-pr` only ever comment,
never `--approve`, so an empty `reviewDecision` is the normal state across a batch — `/merge-pr` and
`/merge-stack` both treat it as such rather than as a missing gate.

**Copilot is answered in the cloud, and its fixes are re-reviewed before they merge.** Once
`/review-pr` marks a PR ready it starts an Auto-fix session (Claude Code's own, in a cloud session)
that fixes or declines each Copilot thread and failing check, up to three Copilot passes. That needs
the Claude GitHub App on the repository and cloud sessions on the plan; without them the PR is still
ready and the summary says Auto-fix did not start. Copilot is the only reviewer the session's
commits meet, so `/merge-pr` and `/merge-stack` refuse a head newer than the latest `/review-pr`
summary, merge with `--match-head-commit`, and stop the session before they touch the branch.
Repositories with a Copilot ruleset that reviews on push get every pass; without one, Copilot sees
the first push only.

**Nothing discards work to tidy up.** `claude rm` keeps a worktree that holds uncommitted changes
or unpushed commits, and for unpushed commits it prints the `--discard-unpushed` value that would
override it. The merge skills report that command and stop; they never run it.

## License

MIT

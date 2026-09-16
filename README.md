# claude-workflow

Personal [Claude Code](https://code.claude.com) skills for a spec-to-merge loop over
GitHub-tracked vertical slices, each running in its own **git worktree** on your machine.

## The loop

```
/grill-with-docs   →  reach shared understanding, update CONTEXT.md and ADRs inline
/to-spec           →  publish the spec as a tracker issue
/to-tickets        →  break the spec into independently-grabbable slice issues
/dispatch-slices   →  fan the unblocked slices out to parallel background sessions  ← this plugin
  └ per slice, inside its own worktree:
      /start-issue →  claim, branch, draft PR, install deps                          ← this plugin
      /tdd         →  red-green-refactor to the acceptance criteria
      /finalize-pr →  gates, PR description, code review, ready-for-human            ← this plugin
/merge-stack       →  land the batch in dependency order, tearing down worktrees     ← this plugin
```

`/grill-with-docs`, `/to-spec`, `/to-tickets`, and `/tdd` come from
[mattpocock/skills](https://github.com/mattpocock/skills); this plugin supplies the four that
surround them, plus `/rebase-pr` and `/merge-pr` for the single-PR cases.

Two more sit beside the loop rather than inside it:

- **`/estimate-from-history`** sizes work against the repo's own merged PRs instead of human
  intuition, which is wrong by an order of magnitude when the work is done by parallel sessions.
  It answers in slices first and quotes a band, never a point estimate.
- **`/retro`** reviews a finished session and proposes changes to the agent's *environment* —
  navigation pointers, automated checks, reviewer rules — rather than to the code.

## Install

```bash
claude plugin marketplace add jb-storefront/claude-workflow
claude plugin install workflow@jb-workflow
```

Declaring the plugin in the repo's committed `.claude/settings.json` makes it load in every
worktree of that repo, and for everyone who clones it:

```json
{
  "extraKnownMarketplaces": {
    "jb-workflow": {
      "source": { "source": "github", "repo": "jb-storefront/claude-workflow" }
    }
  },
  "enabledPlugins": {
    "workflow@jb-workflow": true,
    "mattpocock-skills@claude-plugins-official": true
  }
}
```

## What a repo needs before the first fan-out

- **`.claude/worktrees/` in `.gitignore`** — that is where Claude Code puts them, and without the
  ignore every worktree's files show up as untracked noise in your main checkout.
- **Workspace trust accepted once.** Run `claude` in the repo and accept the dialog. Worktrees live
  inside the trusted checkout, so background sessions never ask again.
- **A `.worktreeinclude`** if the project has gitignored config the slices need. A worktree is a
  fresh checkout: `.env` and friends are not there unless this file copies them.

  ```text
  .env
  .env.local
  ```

- **`gh` authenticated with push access to the repo.** Not a convenience: `/start-issue` claims
  its issue by adding an assignee, and GitHub silently ignores assignees without push access. The
  skill reads the assignment back and stops, so without push access every dispatched session dies
  on its first step.

Dependencies are not a precondition — `/start-issue` installs them in each worktree from the
project's lockfile.

`/estimate-from-history` additionally wants `.claude/calibration/calibration.json`, committed. It
generates it from the repo's merged PRs on first use; see that skill for the knobs.

## Design notes

**Isolation is git's job, and the CLI manages it.** Each slice runs in
`.claude/worktrees/issue-{n}`, a separate working directory sharing the repository's history and
remote. `claude --bg --worktree issue-{n}` creates it, `claude agents --json` lists what is
running, and `claude rm <id>` removes the session and its worktree. None of that has to be
hand-rolled any more, which is most of why this version is shorter than the one it replaces.

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

**Agents stay with their project.** `/finalize-pr` dispatches a PR-writer and a code-reviewer
found in the project's own `.claude/agents/`, matched by role rather than filename, because a
useful reviewer knows the domain (`ucp-demo-code-reviewer`, `gr4ce-code-reviewer`). This plugin ships
no agents; `/finalize-pr` degrades to an inline PR body and a noted gap when a project has none.

**A GitHub write that returns 2xx is not a GitHub write that happened.** Adding an assignee over
REST silently ignores users without push access, so `/start-issue` claims its issue and then reads
the assignment back before creating a branch. That ordering matters more than the retry does: the
claim is what stops `/dispatch-slices` handing the same slice to a second session, and it is worth
nothing if it lands after the branch and PR it was meant to protect.

**The human still pulls the merge trigger.** `/finalize-pr` posts `--comment` reviews and never
`--approve`, so an empty `reviewDecision` is the normal state across a batch — `/merge-pr` and
`/merge-stack` both treat it as such rather than as a missing gate.

**Nothing discards work to tidy up.** `claude rm` keeps a worktree that holds uncommitted changes
or unpushed commits, and for unpushed commits it prints the `--discard-unpushed` value that would
override it. The merge skills report that command and stop; they never run it.

## License

MIT

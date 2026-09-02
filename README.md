# claude-workflow

Personal [Claude Code](https://code.claude.com) skills for a spec-to-merge loop over
GitHub-tracked vertical slices, run in **cloud sessions** rather than local git worktrees.

## The loop

```
/grill-with-docs   →  reach shared understanding, update CONTEXT.md and ADRs inline
/to-spec           →  publish the spec as a tracker issue
/to-tickets        →  break the spec into independently-grabbable slice issues
/dispatch-slices   →  fan the unblocked slices out to parallel cloud sessions   ← this plugin
  └ per slice, inside its own VM:
      /start-issue →  branch, draft PR, assign                                  ← this plugin
      /tdd         →  red-green-refactor to the acceptance criteria
      /finalize-pr →  gates, PR description, code review, ready-for-human        ← this plugin
/merge-stack       →  land the batch in dependency order                        ← this plugin
```

`/grill-with-docs`, `/to-spec`, `/to-tickets`, and `/tdd` come from
[mattpocock/skills](https://github.com/mattpocock/skills); this plugin supplies the four that
surround them, plus `/rebase-pr` and `/merge-pr` for the single-PR cases.

## Install

```bash
claude plugin marketplace add jb-storefront/claude-workflow
claude plugin install workflow@jb-workflow
```

Declare the plugin in the repo's committed `.claude/settings.json` rather than in your user
settings — user-scoped `enabledPlugins` do not travel to a cloud VM:

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

### That declaration is not enough for cloud sessions

`extraKnownMarketplaces` and `enabledPlugins` apply only **after a human accepts the
workspace-trust dialog**, and a fresh cloud VM has nobody to accept it. The keys never activate,
so no marketplace is known and no plugin installs. Committed `.claude/agents/` is *not*
trust-gated and loads normally, which makes the failure look selective and easy to misread:
agents present, skills missing.

Install them from the environment's **setup script** instead — it runs as plain bash before
Claude Code launches, so it sidesteps trust rather than waiting on it:

```bash
claude plugin marketplace add jb-storefront/claude-workflow
claude plugin install workflow@jb-workflow
```

Keep the `.claude/settings.json` block as well; it is what resolves the plugin locally, where a
human does accept the dialog once.

## Design notes

**Isolation is the cloud's job, not git's.** Every slice gets its own VM and its own clone, so
these skills carry no worktree naming, no worktree-pinned branch deletion, and no background
session teardown. A merged PR leaves behind exactly one thing — its remote branch — and
`--delete-branch` removes it.

**Permissions belong in the repo.** Background worktree sessions needed
`--dangerously-skip-permissions` because a human could not see their prompts. Cloud sessions read
the repo's committed `permissions.allow`, so the grant is narrow, reviewable in a PR, and
identical locally and remotely. None of these skills pass the bypass flag.

**Agents stay with their project.** `/finalize-pr` dispatches a PR-writer and a code-reviewer
found in the project's own `.claude/agents/`, matched by role rather than filename, because a
useful reviewer knows the domain (`adk-code-reviewer`, `gr4ce-code-reviewer`). This plugin ships
no agents; `/finalize-pr` degrades to an inline PR body and a noted gap when a project has none.

**The human still pulls the merge trigger.** `/finalize-pr` posts `--comment` reviews and never
`--approve`, so an empty `reviewDecision` is the normal state across a batch — `/merge-pr` and
`/merge-stack` both treat it as such rather than as a missing gate.

## License

MIT

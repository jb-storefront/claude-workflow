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

**The fan-out step plans; the human launches.** Creating a cloud session is interactive-only —
`claude --cloud` refuses a non-interactive stdout, because this CLI ignores unknown flags silently
and a `--cloud` that wasn't honoured would start N *local* sessions while reporting a successful
cloud fan-out. Every Bash call a skill makes is piped, so `/dispatch-slices` can never run its own
dispatch. A pty wrapper clears the check honestly but gains nothing: the command attaches you to
the new session's UI rather than printing an id and exiting, and its first run in a repo opens the
workspace-trust dialog, which is the human's to answer. So the skill does the part that is actually
hard — picking the unblocked slices, classifying them AFK or HITL, writing the prompts — and emits
the commands to run. Steering afterwards *is* automatable: `claude --cloud <session-id> -p "…"`
attaches rather than creates, and needs no TTY.

**Permissions belong in the repo.** Background worktree sessions needed
`--dangerously-skip-permissions` because a human could not see their prompts. Cloud sessions read
the repo's committed `permissions.allow`, so the grant is narrow, reviewable in a PR, and
identical locally and remotely. None of these skills pass the bypass flag.

**Agents stay with their project.** `/finalize-pr` dispatches a PR-writer and a code-reviewer
found in the project's own `.claude/agents/`, matched by role rather than filename, because a
useful reviewer knows the domain (`ucp-demo-code-reviewer`, `gr4ce-code-reviewer`). This plugin ships
no agents; `/finalize-pr` degrades to an inline PR body and a noted gap when a project has none.

**The cloud GitHub proxy only serves some of GraphQL.** All GitHub traffic from a cloud session
goes through a proxy that keeps the real credential outside the VM, and it serves only a pinned,
undocumented set of GraphQL operations — rejecting the rest with a 403 no token can fix. Most of
`gh` is GraphQL underneath, including the read-only `--json` commands. These skills do not try to
guess which operations are permitted; that list would rot. Instead they use REST unconditionally
for issue assignment, fall back to REST on the actual 403 everywhere else, and stop outright at the
one operation with no REST equivalent at all — `gh pr ready`, because `draft` is writable only when
a PR is created. [references/github-proxy.md](references/github-proxy.md) holds the mapping.

**A GitHub write that returns 2xx is not a GitHub write that happened.** Adding an assignee over
REST silently ignores users without push access, so `/start-issue` claims its issue and then reads
the assignment back before creating a branch. That ordering matters more than the retry does: the
claim is what stops `/dispatch-slices` handing the same slice to a second session, and it is worth
nothing if it lands after the branch and PR it was meant to protect.

**The human still pulls the merge trigger.** `/finalize-pr` posts `--comment` reviews and never
`--approve`, so an empty `reviewDecision` is the normal state across a batch — `/merge-pr` and
`/merge-stack` both treat it as such rather than as a missing gate.

## License

MIT

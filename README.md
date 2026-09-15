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

**The fan-out step dispatches under a pty.** Creating a cloud session needs a TTY, and every Bash
call a skill makes is piped, so `/dispatch-slices` wraps each dispatch in `script -q /dev/null`.
That is not a bypass. The check exists because this CLI ignores unknown flags silently, so a
`--cloud` that wasn't honoured would start N *local* sessions while reporting a cloud fan-out;
`script` gives the process a real controlling terminal, so the flag is honoured for real, and the
proof comes back in the output as a genuine cloud session id. The command creates, prints
`Created cloud session:` with the id and its URL, and returns, which is what lets the skill capture
ids and report them.

Two things the pty does not buy. It cannot answer the workspace-trust dialog that the first
`--cloud` opens in a repo whose committed settings pre-approve permissions — that is the human's,
and a stalled dispatch is handed back. And it is unnecessary on a **self-hosted runner pool**, where
`--environment <ccpool_…>` creates a session headlessly; a managed environment has no such id, so
the pty is the path there.

This has already changed once: on 2.1.220 the same command attached to an interactive UI instead of
printing an id, which made an automated fan-out impossible and is why an earlier version of the
skill only planned. Verified against 2.1.263. Re-verify on a much later build rather than trusting
the note.

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

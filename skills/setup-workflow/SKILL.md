---
name: setup-workflow
description: Make a bare repo ready for the slice workflow: gitignore the worktrees directory, write a worktreeinclude when gitignored environment files exist, merge the marketplace and plugin block into the repo's committed settings, write the per-repo workflow file, copy the PR-writer, code-reviewer and test-writer agent templates, and add the pointer block to CLAUDE.md. Explores first, shows the draft, writes on confirmation, and is safe to re-run. Use when the user says "/setup-workflow", "set this repo up for the loop", or is adopting the workflow plugin on a new repo.
disable-model-invocation: true
---

# Setup Workflow

Turn a repo that has never run the loop into one that can. One run leaves the README's
prerequisites done; a second run changes nothing and says so.

This is a prompt-driven skill, not a script. **Explore, draft, confirm, write**, in that order,
every time. Nothing is written before the user has seen what it will be.

It writes only into the repo you run it in. It never installs a CLI, never enables a plugin, and
never writes a third-party plugin into the repo's shared settings. Where something is missing that
this skill will not install, it prints the command and moves on.

## Input

`$ARGUMENTS`: nothing. An optional `--dry-run` stops after the draft and writes nothing at all.

Run this in the **main checkout**, not a worktree. Everything it writes is committed configuration
that every future worktree is cut from, so writing it inside one puts it on a slice branch where
no other session can see it. Detect it with:

```bash
[ "$(git rev-parse --git-dir)" != "$(git rev-parse --git-common-dir)" ] && echo "in a worktree"
```

The two agree in a main checkout and diverge in a worktree, where the git dir is
`.git/worktrees/{name}` and the common dir is the repository's real `.git`. In a worktree,
**stop** and say so.

## 1. Explore

Read the repo. Assume nothing, and record for each artifact whether it is **absent**, **present
and correct**, or **present and incomplete**. That three-way answer is what makes the second run
a no-op instead of an overwrite.

**The repo itself**

- `git rev-parse --show-toplevel`, and `gh repo view --json nameWithOwner,defaultBranchRef`.
- `git status --porcelain`. Uncommitted changes are not fatal, but say how many files are already
  dirty so the user can tell this skill's diff from their own.

**The six artifacts**

| What | How to read it |
| --- | --- |
| Worktrees ignored | `git check-ignore -v .claude/worktrees/` |
| Environment files | `git check-ignore` over the `.env*` files found in the checkout; `.worktreeinclude` at the root |
| Settings block | `.claude/settings.json`, parsed rather than grepped |
| Workflow file | `docs/agents/workflow.md` |
| Agent templates | `.claude/agents/*.md`, reading each file's frontmatter |
| Pointer block | `CLAUDE.md`, then `.claude/CLAUDE.md`, then `AGENTS.md` |

Three of those need care:

**Worktrees ignored.** `git check-ignore -v` prints the file and line that did the ignoring. A
match from the user's *global* excludes file still counts as ignored on this machine, and is worth
nothing to anyone else who clones the repo. Treat the entry as present only when the source is a
tracked ignore file in this repo. Exit 1 with no output means not ignored at all.

**Environment files.** Find candidates with `git ls-files --others --ignored --exclude-standard`
filtered to basenames matching `.env*`, which by construction returns only files git is already
ignoring. A committed `.env.example` is therefore never in the list, correctly: it is in every
worktree already. **Read none of them.** Their paths are all this skill needs and their contents
are secrets.

**Agent templates.** `/finalize-pr` and `/review-pr` find agents by the role in their frontmatter, not by filename,
because a project names them for its domain (`ucp-demo-code-reviewer`). So read the `name` and
`description` of every file in `.claude/agents/` and decide, per role, whether the repo already has
an agent that writes PR descriptions, one that reviews code, and one that writes tests. A repo that
has a domain-taught reviewer under some other name **has that role covered**, and this skill must
not hand it a generic template.

**Whether the repo has a test Seam.** A lockfile at the repo root from the table `/finalize-pr`
detects toolchains by: `bun.lockb`, `pnpm-lock.yaml`, `package-lock.json`, `yarn.lock`, `uv.lock`.
This decides the value the draft proposes for the workflow file's `**Specs:**` line, and only that.
A repo with no test Seam cannot verify a Spec's Criteria, so a Spec anchored for it holds Criteria
nothing can check; the draft proposes `off` there and `on` everywhere else. The user sees the
proposal in §2 before anything is written, and the file is theirs to edit afterwards.

**Three third-party dependencies, checked and never installed**

- **Pocock's skills.** Installed: `claude plugin list` mentions `mattpocock-skills`. Setup has run:
  `docs/agents/issue-tracker.md` and `docs/agents/domain.md` both exist. The plugin can be present
  while its setup has not run, and the second is the one the loop depends on.
- **Codex.** CLI: `command -v codex`. Plugin: `claude plugin list` mentions `codex@openai-codex`,
  which is [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc) and supplies the
  `codex-rescue` agent that `/critique-spec` dispatches as `codex:codex-rescue`.
- **Antigravity.** CLI: `command -v agy`. Plugin: `claude plugin list` mentions
  `antigravity@marcosnahuel-antigravity`, which is
  [MarcosNahuel/antigravity-plugin-cc](https://github.com/MarcosNahuel/antigravity-plugin-cc) and
  supplies the `agy-rescue` agent that `/critique-spec` dispatches as `antigravity:agy-rescue`.

Report each CLI and its plugin **separately**. A plugin installs without its CLI, and in that state
`/critique-spec` finds the agent and the agent has nothing to run. Neither vendor missing is a
broken repo: `/critique-spec` walks its Critics list and the Claude entry at the end always runs.
What a missing vendor costs is the gate's whole point, a model from another vendor doubting what a
Claude session wrote, so say which vendors this machine can actually reach.

## 2. Draft

Print one block per artifact, in the order of §3, each marked with what will happen:

```
  write    .gitignore                 + .claude/worktrees/
  write    .worktreeinclude           + .env, + .env.local
  merge    .claude/settings.json      + 2 extraKnownMarketplaces, + 2 enabledPlugins
  write    docs/agents/workflow.md    new (Specs: on, has a test Seam; critics and security reviewers: codex, google, claude)
  copy     .claude/agents/            + pr-writer.md, + test-writer.md
  skip     .claude/agents/            code-reviewer: ucp-demo-code-reviewer.md covers the role
  append   CLAUDE.md                  + ## Slice workflow
```

Show the **full literal content** of anything new: the settings block, the workflow file, and the
pointer block. For the workflow file, that is the draft the script in §3 step 4 prints without
`--write`, new file or changed one alike. Show the merged result for the settings file, not the fragment, so the user can see
their other keys survived.

Then ask once:

> Write these? (the workflow file's lists are an edit afterwards, not a release)

Nothing is written before that answer. `--dry-run` stops here.

## 3. Write

In this order. Each step is a no-op when §1 found it already correct, and says `unchanged` rather
than saying nothing.

**1. Gitignore the worktrees directory.** Append to the repo's `.gitignore`:

```
.claude/worktrees/
```

Create the file if there is none. Without this, every worktree's files are untracked noise in the
main checkout.

**2. Write `.worktreeinclude`, only when §1 found gitignored environment files.** One path per
line, the paths as found:

```text
.env
.env.local
```

A worktree is a fresh checkout and gitignored files are not in it. When the file already exists,
**merge**: append the paths it is missing, keep every line it already has, and reorder nothing. A
line the user wrote that matches nothing today may match something tomorrow.

When no gitignored environment file exists, write no `.worktreeinclude` at all. An empty one is a
file the next reader has to work out the meaning of.

**3. Merge the marketplace and plugin block into `.claude/settings.json`.**

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

This file is **committed**, which is the point: the plugin then loads in every worktree of the repo
and for everyone who clones it, rather than on one machine.

Merge, never replace:

```bash
block=$(mktemp) && merged=$(mktemp)
cat > "$block" <<'JSON'
{ ...the block above... }
JSON
jq --indent 2 -s '.[0] * .[1]' .claude/settings.json "$block" > "$merged"
mv "$merged" .claude/settings.json
```

`*` merges objects recursively, so every other key survives: `permissions`, `hooks`, `model`,
whatever the repo already had. An `enabledPlugins` map that already lists other plugins keeps
them.

Two details that decide whether the second run is really a no-op:

- **Match the file's existing indentation.** jq rewrites the whole file, defaulting to two spaces.
  On a repo that indents with four or with tabs, that turns a one-key merge into a whole-file
  reformat the user did not ask for. Read the indentation of the existing file and pass
  `--indent 4` or `--tab` to match it.
- **`mktemp`, not a fixed `/tmp` path.** Several sessions of this repo can be running at once, and
  two of them sharing `/tmp/block.json` is one of them writing the other's settings.

Compare the merged result against the original before writing. If they are byte-identical, report
`unchanged` and leave the file's mtime alone.

If the file exists and is not valid JSON, **stop**. Do not write. Report the parse error and the
path: a settings file someone is mid-edit on is not this skill's to repair.

Everything above is first-party: one marketplace is this plugin's own, the other is Anthropic's
official one, and `mattpocock-skills` comes from it and is a hard dependency of the loop. This
plugin's manifest declares that dependency, so a fresh Claude Code without the official marketplace
refuses to load `workflow` at all; declaring the marketplace here is what lets a fresh clone
resolve it.

**Nothing about Codex goes in this file**, on any run. Enabling a third-party plugin for everyone
who clones the repo is a decision for a human, and §4 prints the commands instead.

**4. Write the per-repo workflow file.** `docs/agents/workflow.md`, beside Pocock's
`issue-tracker.md`, `triage-labels.md` and `domain.md`. Three settings, and nothing else;
`CONTRACTS.md` describes all three:

```markdown
**Specs:** on

**Critics:**
1. codex, default
2. google, gemini-3.8-flash-high
3. claude, claude-opus-5

**Security reviewers:**
1. codex, default
2. google, gemini-3.8-flash-high
3. claude, claude-opus-5
```

A script writes it, not this prose. Run it once without `--write` for the §2 draft, and again with
`--write` after the confirmation:

```bash
python3 <this skill dir>/../../scripts/workflow-file.py docs/agents/workflow.md --specs {on|off}
python3 <this skill dir>/../../scripts/workflow-file.py docs/agents/workflow.md --specs {on|off} --write
```

Its first line is `new`, `update` with what it changes, or `unchanged`. The rest is the file as it
will stand. Report its word in §4. Exit 1 with a `✘` line names something only the user can fix,
such as a list whose last entry is not `claude`. The script still made any change it reported, and
left the flagged lines exactly as they were. Relay each `✘` line in §4; a list with no floor is
one `/critique-spec` or `/review-pr` will stop on until the user puts a `claude` entry last. The script
([workflow-file.py](../../scripts/workflow-file.py)) exists because the rules below are about
leaving bytes alone, and code keeps that promise better than prose does.

Nothing in the file is loaded into a session's context. `/critique-spec` reads the Critics list,
walking it in order and running the first entry that can actually produce a Critique on this
machine. `/review-pr` walks the Security reviewers list the same way for its security review.
`/dispatch-slices`, `/acceptance-tests` and `/finalize-pr` read the Specs line. Changing any of them
is an edit to this file and not a release of this plugin, so say so in §4.

**The Specs value is the one §1 chose**: `on` when the repo has a test Seam, `off` when it has none.
Absent means `on`, so the line is written even when it says `on`: it is where the next reader learns
the setting exists. `off` turns every Spec gate off for the repo and makes every Slice a lone
Slice; it does not skip the tests, because `/finalize-pr` holds a lone Slice to its own Criteria.
Name the value and the reason in §2 and §4. `--specs` only matters for a new file.

**Both lists get all three entries, in the same default order, even when the CLIs are missing.** An
entry costs nothing when its vendor is absent, because the skill walking the list skips it and moves
on. A user who installs Codex or Antigravity next month then gets a working chain without editing
anything. Writing only the Claude entry would make installing a CLI a silent no-op. They are two
lists so that spec critique and security review can be reordered independently.

**The last entry of each list must name `claude`**, because it is the only vendor that runs with
nothing installed. `/critique-spec` stops on a list whose last entry is any other vendor, so never
write one and never reorder a user's list in a way that moves their Claude entry off the end.

**`default` in the model position means let that vendor's wrapper choose.** It is written on the
`codex` entry because the Codex plugin's own runtime says to leave `--model` unset unless the user
asks for a specific one; `codex-rescue` passes a concrete name straight through to `--model`, and
maps the word `spark` to `gpt-5.3-codex-spark`. The `google` entry names a model instead, because
`agy-rescue` omits `--model` unless the caller supplies one, and the id is checked against
`agy models` before dispatch. Any id from that list works; `gemini-3.8-flash-high` is the default
here because a Critique is a read-and-report job.

**An existing file is left alone, with two exceptions.** The user's choice of critics is the whole
reason this file exists, so the script never touches the Specs line, the Critics list, an existing
Security reviewers list, a line it does not recognise, or the file's line endings. That includes a
file with no `**Specs:**` line: absent means `on`, and adding the line to someone's file is an edit
they did not ask for. A list without a `claude` floor is reported, never repaired. The two
exceptions, both shown in the §2 draft before anything is written:

- **No `**Security reviewers:**` list.** The script adds the default list directly after the
  Critics list. It does not copy the repo's Critics order: the lists are separate on purpose, and
  the default is the documented starting point.
- **The superseded two-line shape, `**Critic:**` and `**Fallback:**`.** The script rewrites it as
  the Critics list its two lines already encode, keeping both vendors and both models in that order.
  It never adds, drops, or reorders an entry while doing it: this converts a shape, it does not
  choose a critic.

**5. Copy the agent templates.** From this skill's `templates/agents/` into the repo's
`.claude/agents/`:

- [templates/agents/pr-writer.md](templates/agents/pr-writer.md)
- [templates/agents/code-reviewer.md](templates/agents/code-reviewer.md)
- [templates/agents/test-writer.md](templates/agents/test-writer.md)

Copy a template **only for a role §1 found uncovered**. A repo whose reviewer is called
`gr4ce-code-reviewer` has that role; overwriting it with a generic template would throw away the
domain knowledge that makes a reviewer worth having. Skip it and name the file that covers it.

Each template carries exactly one `{{DOMAIN}}` placeholder. Leave it in place. Filling it in is
the user's job, and §4 tells them so. Offer to name the copies for the repo
(`ucp-demo-pr-writer.md`) since that is what real projects do, but do not require it:
`/finalize-pr` and `/review-pr` match on the role in the frontmatter and do not care about the filename.

**6. Append the pointer block.** Pick the file the same way `/setup-matt-pocock-skills` does, so
the two skills never write to different files in the same repo:

- `CLAUDE.md` at the root, if it exists.
- Else `.claude/CLAUDE.md`, if it exists.
- Else `AGENTS.md`, if it exists.
- Else **ask** which to create. Never create `AGENTS.md` in a repo that has `CLAUDE.md`, or the
  reverse.

Append:

```markdown
## Slice workflow

One Spec per feature, cut into Slices that parallel sessions build in their own worktrees:
`/to-spec` → `/critique-spec` → `/to-tickets` → `/dispatch-slices` → per Slice
`/start-issue` → `/acceptance-tests` → `/tdd` → `/finalize-pr` → `/review-pr` → `/merge-stack`.

Specs live in the body of their Spec issue. Nothing about a Spec is committed, and changing one is
an issue edit, never a pull request.

The shape of every artifact the loop reads and writes is documented once, in the workflow plugin's
[CONTRACTS.md](https://github.com/jb-storefront/claude-workflow/blob/main/CONTRACTS.md). Read it
before hand-writing or parsing a Spec or a Slice body.
```

If a `## Slice workflow` heading already exists, leave the section as it stands. It may have been
edited on purpose, and a pointer block is not worth clobbering a sentence someone wrote.

**One exception: the block an earlier version of this skill appended.** When Specs were committed
files, this step wrote the same section with these two paragraphs in place of the second and third
above:

```markdown
Specs live in `docs/specs/`, one file per Spec, committed to the default branch. The Spec issue is
only its handle, and the file wins when the two disagree.

The shape of every artifact the loop reads and writes is documented once, in the workflow plugin's
[CONTRACTS.md](https://github.com/jb-storefront/claude-workflow/blob/main/CONTRACTS.md). Read it
before hand-writing or parsing a Spec file, a Spec issue body, or a Slice body.
```

A `## Slice workflow` section whose text is exactly that old block, every line as shipped, is the
plugin's own stale prose rather than something a user wrote, and it now sends every session looking
for a directory nothing writes to. Replace it with the block above, show both in the §2 draft, and
report it as `updated`. Any other difference, a single word included, means a person touched the
section: leave it alone and report it as `stale, edited by hand`, quoting the line that still names
`docs/specs/`, so the user can fix it themselves.

**A `docs/specs/` directory already in the repo is left where it is.** Nothing reads it any more,
but it may hold Specs written before they moved into their issues, and deleting committed history
is not this skill's call. Say so in §4.

## 4. Report

```
Repo:      {owner}/{repo} on {default branch}

  {written | unchanged}  .gitignore              .claude/worktrees/
  {written | unchanged | not needed}  .worktreeinclude    {paths, or "no gitignored .env files"}
  {merged | unchanged}   .claude/settings.json   marketplace + 2 plugins
  {written | updated | unchanged}  docs/agents/workflow.md Specs: {on | off} ({has | no} test Seam); critics and security reviewers: codex → google → claude
  {copied | unchanged}   .claude/agents/         {files, or which existing agent covers each role}
  {appended | updated | unchanged | stale, edited by hand} {CLAUDE.md}   ## Slice workflow

Still yours to do:
  - (Only when docs/specs/ exists.) docs/specs/ is no longer used: Specs live in their Spec issues
    now. Any Spec file still in it predates that; `python3 <plugin>/scripts/spec.py migrate {n}`
    brings one back into its issue.
    The directory was left in place.
  - Fill in the {{DOMAIN}} paragraph in each copied agent. Until then they review generically.
  - Run `claude` in this repo once and accept the workspace trust dialog. Worktrees live inside
    the trusted checkout, so background sessions never ask again.
  - `gh auth status`. /start-issue claims its issue by assignment, and GitHub silently ignores
    assignees without push access.
  - Commit these files. They are only worth anything to the next worktree once they are on the
    default branch.
```

Then the two dependency reports, printed only when something is missing.

**Pocock's skills**, when the plugin is absent or its setup has not run:

```
Pocock's skills: setup has not run in this repo
  /to-spec, /to-tickets and /tdd are the inner loop, and they read docs/agents/issue-tracker.md
  and docs/agents/domain.md, which are not here.

  Run:  /setup-matt-pocock-skills

  (If the plugin itself is missing: claude plugin install mattpocock-skills@claude-plugins-official)
```

**Codex**, when the CLI or the plugin is missing:

```
Codex: unavailable, so /critique-spec and /review-pr skip entry 1 of their lists

  codex plugin  {installed | not found}   /plugin marketplace add openai/codex-plugin-cc
                                          /plugin install codex@openai-codex
                                          /reload-plugins
  codex CLI     {on PATH | not found}     /codex:setup

  /codex:setup comes with the plugin, reports whether Codex is ready, and offers to install the
  CLI. To do it yourself: npm install -g @openai/codex, then !codex login. Codex needs Node 18.18
  or later and a ChatGPT subscription or an OpenAI API key.

  Nothing about Codex was written into .claude/settings.json: enabling a third-party plugin for
  everyone who clones this repo is yours to decide, not this skill's.
```

**Antigravity**, when the CLI or the plugin is missing, in the same shape and for the same reason:

```
Google: unavailable, so /critique-spec and /review-pr skip entry 2 of their lists

  antigravity plugin  {installed | not found}   /plugin marketplace add MarcosNahuel/antigravity-plugin-cc
                                                /plugin install antigravity@marcosnahuel-antigravity
                                                /reload-plugins
  agy CLI             {on PATH | not found}     /antigravity:setup

  /antigravity:setup comes with the plugin and reports whether agy is installed and responding.
  To do it yourself, install the Antigravity CLI from https://antigravity.google/cli, then run
  `agy` once in a real terminal to sign in.

  Nothing about Antigravity was written into .claude/settings.json: enabling a third-party plugin
  for everyone who clones this repo is yours to decide, not this skill's.
```

For each vendor, print the plugin lines before the CLI lines, because the plugin's own setup command
ships with it and is the better way to get the CLI. Telling someone to install a binary first and
then install the plugin that would have done it for them is the wrong order.

**Sign-in is the part neither check can see.** Both CLIs are on `PATH` and logged out on a fresh
machine, and in that state `/critique-spec` dispatches the entry and gets nothing back. It falls
through to the next entry, so the gate still works, but the vendor the user thought they had
configured is not the one doubting their Spec. Say so once: an installed CLI is reported here as
present, and only a real Critique proves it is signed in.

Close with: re-running `/setup-workflow` is safe and reports `unchanged` for everything already
done. Changing the critics, the security reviewers, their order, or the Specs value is an edit to `docs/agents/workflow.md`.

## Rules

- **Explore, draft, confirm, write.** Never write before the confirmation, on any run, including
  one where every artifact is absent and the answer looks obvious.
- **Idempotent means unchanged, not rewritten.** Re-running must not reorder a file, restyle JSON,
  or replace a user's chosen critics, agent, or pointer prose. Report `unchanged` and move on. The
  one pointer block it replaces is its own earlier one, word for word (§3 step 6).
- **Merge, never replace, for `.claude/settings.json` and `.worktreeinclude`.** Both are files the
  repo owns and this skill is a guest in.
- **Never read or print a `.env` file.** Paths only.
- **Never install, enable, or authenticate anything.** Print the command.
- **Never write a third-party plugin into `.claude/settings.json`.**
- **Never overwrite an existing agent.** A role the repo already covers is a role this skill skips.
- **Run in the main checkout.** Stop if `git rev-parse --git-common-dir` says otherwise.
- Stop on invalid JSON in `.claude/settings.json` rather than writing over it.

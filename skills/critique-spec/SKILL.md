---
name: critique-spec
description: Send a drafted Spec to a second model for doubt, post its findings on the Spec issue, resolve each one with the founder, and set the Spec's Status to critiqued. Use when the user says "/critique-spec <issue>", "critique the spec", "get a second opinion on the spec", or has just finished /anchor-spec and before /dispatch-slices.
---

# Critique Spec

A Spec is one Claude session's synthesis of a conversation. Nothing in that session doubted it, and
the failure mode is not a wrong Spec but a plausible one: an ambiguity every reader resolves
differently, an edge case nobody raised, a decision an agent will make silently in three parallel
worktrees and make three different ways.

This skill is the gate between a drafted Spec and any Slice being built. A different vendor's model
reads the Spec and reports doubts, the founder resolves every one of them, and the Spec file moves
from `draft` to `critiqued`. `/dispatch-slices` refuses to fan out a Spec still at `draft`, so until
this runs, or `/anchor-spec --skip-critique "<reason>"` recorded a reason for not running it, no
Slice starts.

Read `CONTRACTS.md` at the repo root before hand-checking anything here: the Spec file's shape, the
Status table, the Critique line, and the per-repo workflow file are all defined there, and this
skill only writes what that document says.

## Input

`$ARGUMENTS`: a Spec issue number (`60` or `#60`). If it is missing or not a number, run
`gh issue list --state open --limit 10` and ask which Spec to critique.

## 1. Find the Spec file and check it is critiquable

The Spec file is `docs/specs/{number}-{slug}.md`; the slug is not knowable from the issue number
alone, so glob for it:

```bash
ls docs/specs/{number}-*.md
```

**Stop and say why** when any of these hold. Each is a reason the run cannot produce a valid
Critique, and each names the fix:

| Condition | What to say |
| --- | --- |
| No file matches | The Spec is not anchored. Run `/anchor-spec {number}` first. |
| More than one matches | Two files claim the same Spec issue. Name both and ask which is the Spec. |
| No `**Status:**` line | The file is not a Spec in the shape `CONTRACTS.md` describes. |
| Status is `critiqued` | Already critiqued. Name the existing Critique line. To redo it, set the Status back to `draft` by hand. |
| Status is `in-progress`, `implemented` or `superseded` | Slices are already building from it, or it is history. Critiquing now would change a Spec that Slices are citing. |

Only `draft` proceeds. The check is on the file, never the Spec issue body: the file wins on
conflict.

Be on the default branch with a clean tree before writing anything, because step 8 commits there.
`git status --porcelain` non-empty → stop and say so rather than committing someone else's work
alongside the Spec edit.

## 2. Read the Critics list from the per-repo workflow file

`docs/agents/workflow.md` holds one ordered list and nothing else:

```markdown
**Critics:**
1. codex, default
2. google, gemini-3.8-flash-high
3. claude, claude-opus-5
```

Each entry is `{vendor}, {model}`. Read it here, on demand. Nothing from this file belongs in a
session's context, which is why it sits outside `CLAUDE.md` and why no other skill reads it.

Two shapes of this file are unusable, and each stops the run before any critic is dispatched:

| Condition | What to say |
| --- | --- |
| The last entry's vendor is not `claude` | The chain has no floor. Name the last entry, and say that the final entry must be a Claude model because it is the only vendor that runs with nothing installed. |
| An entry names a vendor that is not `codex`, `google` or `claude` | Name it, and say there is no dispatch path for it. Do not guess one. |

**When the file does not exist**, do not invent a chain. There is no configured model to pass, so
every vendor that needs one is unavailable by definition: go straight to the Claude fallback on
`claude-opus-5`, say once that `docs/agents/workflow.md` is missing and that `/setup-workflow`
writes it, and record the critic that actually ran. A guessed model name in a `--model` flag fails
loudly at best and silently runs something else at worst.

A file in the superseded two-line shape, `**Critic:**` and `**Fallback:**`, is read as the two-entry
chain it encodes, in that order. Say once that the file is in the old shape and that
`/setup-workflow` rewrites it. `CONTRACTS.md` documents only the list.

## 3. Walk the chain and pick the critic that runs

The point of this gate is that a different vendor's model doubts what a Claude session wrote. That
is why the Claude entry sits last: it is the floor that makes the gate work on a machine which has
installed nothing, not the critic the gate wants.

Take the entries in order. An entry runs only if it is **available**, and it counts only if it
**produces findings**. Two questions, in that order, and both have to be answered before moving on.

**The first entry that produces findings ends the walk.** Do not dispatch anything below it, do not
run a second critic for comparison, and do not fall through to the Claude entry because an earlier
entry's findings look thin. One Critique per run, from one entry, and the chain exists to find which
entry that is — not to collect several opinions.

**Available.** What each vendor needs before it is worth dispatching:

| Vendor | Available when all of these hold |
| --- | --- |
| `codex` | `command -v codex` finds the CLI, and `codex:codex-rescue` appears in this session's available agent types |
| `google` | `command -v agy` finds the CLI, `antigravity:agy-rescue` appears in this session's available agent types, and the entry's model id appears in `agy models` |
| `claude` | always — it is the session you are already in |

Check every part. A plugin without its CLI dispatches an agent that cannot reach a model, and a CLI
without its plugin leaves nothing to dispatch.

**The `agy models` check is not optional for a `google` entry.** Run it and match the entry's model
against the ids in the first column:

```bash
agy models
```

It prints one tab-separated `{id}\t{display label}` per line under a `Fetching available models...`
header. Match on the id, which is what `--model` takes. An id that is absent — misspelled, or not
offered on this account's tier — makes the entry unavailable: **say the id is unavailable, do not
dispatch agy, and move to the next entry.** Which ids exist depends on the account, so this has to
be read live and never from a list baked into this skill. `agy models` on a signed-out account
cannot answer, which is the same answer: unavailable, move on.

**Produces findings.** Availability is not usability. A CLI can be installed and logged out, and
both of these CLIs sit in exactly that state on a fresh machine. An unauthenticated headless
`agy --print` exits 0 having written nothing, a failure the antigravity plugin documents; a
dispatched agent can also return an error, a re-auth instruction, or an empty report. None of those
is a Critique.

So when a dispatched entry returns nothing usable — no findings under the seven headings, an empty
report, or the agent's own message that it could not reach a model — **say which entry returned
nothing and move to the next entry.** Falling through on a silent failure, and not only on absent
tooling, is what makes the Claude floor reachable in the case it exists for.

**When every entry has been tried and none produced findings, stop.** Report that no critic produced
a Critique, name what each entry did, and write no Critique line and no comment. A Spec left at
`draft` is a gate that held; a Critique line naming a critic that produced nothing is a gate that
lied.

Whichever entry runs, **hold on to which one it was**. The Critique line names it, and a line naming
a critic that did not run is worse than no line.

## 4. Write the prompt

One prompt, used verbatim by whichever entry of the chain runs, so the paths are comparable and a
Critique reads the same whoever produced it. Fill in the paths and the Spec title; change nothing
else.

```
You are doubting a specification, not writing code. Do not edit, create, or delete any
file, and do not run any command that changes state. Read and report only.

Read, in this order:

- {spec_file_path} — the Spec you are doubting
- CONTEXT.md — this project's glossary; its Avoid lists govern what things may be called
- {each ADR under docs/adr/ that touches this Spec's area, by path}

Report doubts about the Spec under these seven headings. Under each, either list findings
or write "None". A finding is one sentence naming the problem, plus one sentence on why it
matters. Quote the Spec text you are doubting.

1. Ambiguities — wording two competent readers would implement differently.
2. Missing edge cases — behaviour the Spec does not say anything about.
3. Decisions an agent would make silently — choices the Spec leaves open that an
   implementer must settle, and will settle differently in each parallel session.
4. Vocabulary conflicting with the glossary — terms used that CONTEXT.md lists under
   Avoid, or terms used in a sense CONTEXT.md does not define.
5. Criteria that are not binary — any Criterion whose Then a reasonable reader could mark
   either way. Quote the Then clause.
6. Scope missing from Out of Scope — work a reader would assume is included that the
   Spec does not exclude.
7. Over-specification — detail that constrains implementation without describing
   behaviour, or Criteria that are a sledgehammer for the change being made.

Do not propose an implementation. Do not rewrite the Spec. Do not rank or soften the
findings. Report what you doubt.
```

The read-only instruction leads because a critic that edits the Spec has pre-empted the founder's
resolution in step 7, which is the one step of this skill that is not the agent's to make.

## 5. Dispatch the entry

Every vendor is dispatched through the Agent tool. Only the subagent and how the model is named
differ.

**`codex`.** `subagent_type: "codex:codex-rescue"`, with the step 4 prompt prefixed by one line
naming the model:

```
Run with --model {model} from the per-repo workflow file. Do not substitute another model.
```

When the entry's model is `default`, say so instead and let the wrapper choose: the Codex plugin
asks callers to leave `--model` unset unless a specific model was requested, and `default` is the
entry recording that choice.

**`google`.** `subagent_type: "antigravity:agy-rescue"`, with the step 4 prompt prefixed by:

```
MODEL: {model}
Run agy with --model {model}. Do not substitute another model. This is read-only:
do not pass --add-dir and do not write any file.
```

`agy-rescue` is a thin forwarding wrapper around `agy --print`, the same role `codex-rescue` plays
for Codex. It omits `--model` unless the caller asks for one, so the entry's model has to be named
here or the Critique line would record a model that was never passed. Step 3 has already confirmed
the id against `agy models`, which is what makes naming it safe.

**`claude`.** The step 4 prompt, `model` set to the entry's model, and a read-only `subagent_type`:
prefer a read-only agent type the project offers (`Explore` is one); otherwise `general-purpose`,
whose write tools the prompt's first paragraph forbids.

If the Agent tool rejects the model you pass — the workflow file may name a model this harness
addresses by a different alias — **do not run on the default**. Map the configured name to the alias
the tool accepts if an obvious one exists, and name the mapping in what you report. If no obvious
mapping exists, the entry is unavailable: say so and move to the next one, the same as any other
entry that cannot run as configured. What must never happen is the Critique line claiming a model
that did not run.

Wait for the agent to finish. **An agent that returns nothing usable has not failed the run, it has
failed its entry:** apply step 3's fall-through, say which entry returned nothing, and try the next.
Do not write the findings yourself, at any point in the chain. This session synthesised the Spec;
this session doubting it is the thing the gate exists to prevent, which is also why the Claude entry
is a fresh subagent and not this session reading the Spec again.

## 6. Post the findings as one comment

One comment on the Spec issue, holding the critic's report unedited under a heading that names the
critic and the date:

```bash
gh issue comment {number} --body-file {findings_file}
```

Write the findings to a temporary file rather than inlining them, so backticks and quotes in the
report survive the shell.

One comment, not one per finding: the Critique is a single artifact that the Critique line links to,
and a teammate reading the issue should find the doubts in one place.

Keep the returned URL. Its `#issuecomment-{id}` fragment is the id the Critique line carries.

## 7. Resolve every finding with the founder

One round. Present every finding at once, numbered, and take a resolution for each. Do not go back
for a second pass: this is a gate on the Spec, not a redesign of it.

Each finding ends in exactly one of three states:

| Resolution | What it means | What you do |
| --- | --- | --- |
| **accepted** | The doubt is real | Edit the Spec so the doubt no longer applies |
| **moved to Out of Scope** | Real, but not this feature | Add a line to `## Out of Scope` naming it |
| **rejected** | Not a problem | Record the founder's reason, change nothing |

A finding with no resolution is not resolved. If the founder leaves one open, ask again for that one
rather than proceeding, because `/dispatch-slices` will not ask.

Where a finding says a Criterion is not binary, the accepted edit rewrites the Then clause until it
resolves to pass or fail. `CONTRACTS.md` has the measurable/not-measurable table.

**Never renumber a Criterion.** A Criterion dropped in this round leaves a gap in the ids, because
its id may already be cited from a Slice, a test name, or a review comment. Adding one takes the
next unused number.

## 8. Apply, set the Status, commit

Apply the accepted edits to the Spec file. Then change the Status line in place and append one
Critique line directly after `**Tracker:**`:

```markdown
**Status:** critiqued
**Tracker:** #60
**Critique:** google (gemini-3.8-flash-high), #60 comment 2847193044, 2026-09-18
```

The critic is `{vendor} ({model})` — the one that actually ran, from step 3. The comment reference
is `#{number} comment {id}` from step 6. The date is today's, `YYYY-MM-DD`.

**The Spec stays a description of behaviour.** The findings live in the comment; the resolutions
live in the Spec only as changed behaviour. Do not append a findings section, a resolution log, or a
rejected-with-reason list to the file. The rejected reasons go in what you report to the founder and
in the commit message, not in the Spec. A Spec that accumulates its own history stops being readable
as a description of the code, which is the whole reason ADR 0001 put it in the repo.

Commit on the default branch:

```bash
git add {spec_file_path}
git commit -m "Critique {number}: resolve {n} findings and mark the Spec critiqued"
git push
```

**Push, and open a pull request if the push is rejected.** Every Slice worktree is cut from the
remote default branch, so a Status of `critiqued` that only exists locally gates nothing: the
sessions that read it never see it. A protected default branch rejects the push. Detect it that way
rather than declaring it in a setting, then move the commit onto a branch and open a pull request
for it:

```bash
git switch -c chore/{number}-critique
git push -u origin chore/{number}-critique
gh pr create --head chore/{number}-critique --title "Critique {number}: mark the Spec critiqued" --body "..."
```

`switch -c` carries the commit onto the new branch and leaves the local default branch pointing at
it too. That is untidy and harmless: it reconciles when the pull request merges. Do not rewind the
default branch to tidy it. A history rewrite to fix cosmetics is not a trade this skill makes, and
the founder's checkout is not this skill's to reset.

Tell the founder to dispatch after it merges, and report `Status: draft → critiqued (pending #{pr})`
rather than a bare `critiqued`. This is the same rejection-detected path `/anchor-spec` takes, and
the reason neither skill carries a mode.

## 9. Report

```
Spec:     docs/specs/{number}-{slug}.md
Critic:   {vendor} ({model}) — entry {i} of {n} in the Critics list
Skipped:  {one line per earlier entry, naming it and why it did not run}
Findings: {n} — {a} accepted, {o} moved to Out of Scope, {r} rejected
Comment:  {comment_url}
Status:   draft → critiqued
Commit:   {sha} pushed to {default_branch}

Next: /dispatch-slices {number}
```

List each rejected finding with the founder's reason underneath. It is the only place that reason is
written down, and the next reader of this Spec deserves to know what was doubted and waved through.

## Rules

- Only a Spec at `draft` is critiqued. Every other Status stops the run with the reason named.
- The file is the Spec. When it and the Spec issue body disagree, the file is right.
- Never write the findings yourself, and never let the critic write the Spec. The critic doubts, the
  founder resolves, this skill edits.
- Never claim a critic that did not run. The Critique line names the entry that produced the
  findings, never an earlier one that was skipped or returned nothing.
- An entry that is absent, that cannot be run as configured, or that returns nothing usable is
  skipped, not fatal. The chain is only exhausted when its last entry has been tried.
- When no entry produces findings, write no Critique line and no comment, and leave the Spec at
  `draft`.
- Never renumber a Criterion.
- The last entry of the Critics list must name `claude`. Without a floor the chain can run out,
  and a gate that can run out is not a gate.
- Never dispatch a `google` entry whose model id `agy models` does not list.
- Nothing from `docs/agents/workflow.md` enters the session's context beyond the entries this skill
  walks.
- The Status change is only real once it is on the remote default branch.

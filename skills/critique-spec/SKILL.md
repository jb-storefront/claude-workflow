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

## 2. Read the critic from the per-repo workflow file

`docs/agents/workflow.md` holds two lines and nothing else:

```markdown
**Critic:** codex, gpt-6-astra
**Fallback:** claude, claude-opus-5
```

Read it here, on demand. Nothing from this file belongs in a session's context, which is why it sits
outside `CLAUDE.md` and why no other skill reads it.

**When the file does not exist**, do not invent a critic. There is no configured model to pass, so
the Codex path is unavailable by definition: go straight to the fallback on `claude-opus-5`, say
once that `docs/agents/workflow.md` is missing and that `/setup-workflow` writes it, and record the
critic that actually ran. A guessed model name in a `--model` flag fails loudly at best and silently
runs something else at worst.

## 3. Choose the critic

The point of this gate is that a different vendor's model doubts what a Claude session wrote, so
Codex is tried first and the Claude fallback exists only so the gate works on a machine that has
never installed it.

Codex is available when **both** hold:

- `command -v codex` finds the CLI, and
- the `codex:codex-rescue` subagent appears in this session's available agent types.

Either one absent means the fallback runs. Check both: the plugin without the CLI dispatches an
agent that cannot reach a model, and the CLI without the plugin leaves nothing to dispatch.

Whichever runs, **hold on to which one it was**. The Critique line names it, and a line naming a
critic that did not run is worse than no line.

## 4. Write the prompt

One prompt, used verbatim by whichever critic runs, so the two paths are comparable. Fill in the
paths and the Spec title; change nothing else.

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

## 5. Dispatch the critic

**Codex path.** Use the Agent tool with `subagent_type: "codex:codex-rescue"` and the step 4 prompt,
prefixed with one line telling it which model to use:

```
Run with --model {critic_model} from the per-repo workflow file. Do not substitute another model.
```

The model is passed explicitly because the whole value of this gate is which model ran, and a
default is not that.

**Fallback path.** Use the Agent tool with the step 4 prompt, `model` set to the fallback model, and
a read-only `subagent_type`: prefer a read-only agent type the project offers (`Explore` is one);
otherwise `general-purpose`, whose write tools the prompt's first paragraph forbids.

If the Agent tool rejects the model you pass — the workflow file may name a model this harness
addresses by a different alias — **say so and stop rather than running on the default**. Map the
configured name to the alias the tool accepts if an obvious one exists, and name the mapping in what
you report. What must never happen is the Critique line claiming a model that did not run.

Wait for the agent to finish. An agent that returns nothing usable is a failed run: report it and
stop. Do not write the findings yourself. This session synthesised the Spec; this session doubting
it is the thing the gate exists to prevent.

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
**Critique:** codex (gpt-6-astra), #60 comment 2847193044, 2026-09-18
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
Critic:   {vendor} ({model}){, fallback — Codex not installed}
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
- Never claim a critic that did not run. If the configured model could not be passed, stop.
- Never renumber a Criterion.
- Nothing from `docs/agents/workflow.md` enters the session's context beyond the two values this
  skill needs.
- The Status change is only real once it is on the remote default branch.

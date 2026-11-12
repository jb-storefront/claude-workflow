---
name: critique-spec
description: Turn a Spec issue /to-spec published into a critiqued Spec. Derive numbered Given/When/Then Criteria and a Verification from its user stories, send the whole Spec to a second model for doubt, settle the Criteria and every finding with the founder in one round, and write the result into the issue body at Status critiqued. Use when the user says "/critique-spec <issue>", "critique the spec", "add criteria to the spec", "get a second opinion on the spec", or has just finished /to-spec and before /to-tickets.
---

# Critique Spec

A Spec is one Claude session's synthesis of a conversation. Nothing in that session doubted it, and
the failure mode is not a wrong Spec but a plausible one: an ambiguity every reader resolves
differently, an edge case nobody raised, a decision an agent will make silently in three parallel
worktrees and make three different ways.

This skill turns what `/to-spec` published into a Spec the rest of the loop can build from. It
derives the Criteria and the Verification, a different vendor's model doubts the whole thing, and
the founder settles the Criteria and every doubt in one sitting. Only then is anything written: the
Status line, `## Criteria` and `## Verification` go into the Spec issue's body at `critiqued`.

It is the step between `/to-spec` and `/to-tickets` in the
`/to-spec` → **`/critique-spec`** → `/to-tickets` → `/dispatch-slices` loop. `/dispatch-slices`
refuses a Spec that is not anchored, or still at `draft`, so until this runs, or runs with
`--skip-critique "<reason>"`, no Slice starts.

The critic sees the Criteria before the founder confirms them, on purpose. Confirming Criteria and
then reopening them for a critic's doubts is two passes over the same decisions; one pass with both
in front of the founder is cheaper and settles more.

Nothing here forks Pocock's `/to-spec`. This skill runs after it and reads what it published.

Read `CONTRACTS.md` at the repo root before hand-checking anything here: the Spec's shape, the
Status table, the Critique line, and the per-repo workflow file are all defined there, and this
skill only writes what that document says.

## Input

`$ARGUMENTS`: a Spec issue number (`60` or `#60`), optionally followed by
`--skip-critique "<reason>"`. If the number is missing or not a number, run
`gh issue list --state open --limit 10` and ask which Spec to critique.

`--skip-critique "<reason>"` derives and confirms the Criteria exactly as a full run does, and
skips the critic: steps 5 to 7 do not run, and the Spec is written at `critiqued` with the reason in
its Critique line, so the skip is auditable. It is for a change too small to be worth doubting, such
as a two-Criterion bug fix. A reason is required; `--skip-critique` with no reason is an error, not
an empty reason.

## 1. Read the Spec issue and decide which run this is

```bash
python3 <this skill dir>/../../scripts/spec.py read {number}
```

([spec.py](../../scripts/spec.py).) Every read of a Spec goes through it. What it returns decides
the run:

| What `spec.py read` returns | What to do |
| --- | --- |
| Exit 1, the issue carries no `**Status:**` line | **First run.** The body is `/to-spec`'s prose. Read it with `gh issue view {number} --json title,body,state` and go on to step 2 |
| `status` is `draft` | **Re-run.** The Spec already carries Criteria, from a run whose critics all failed. Skip steps 2 to 4 and critique the Spec as it stands |
| `status` is `critiqued` | **Stop.** Already critiqued; name the Critique line. To redo it, run `spec.py set-status {number} draft` first |
| `status` is `in-progress`, `implemented` or `superseded` | **Stop.** Slices are building from it, or it is history. Critiquing now would change a Spec that Slices are citing |
| Exit 1, the `✘` line names a Spec anchored to a file | **Stop** and print the `✘` line: it carries the `spec.py migrate` command that brings the Spec back into its issue |
| Exit 1, any other `✘` line | **Stop** and print it. The body has a Status line but does not parse; fix the issue by hand |
| Exit 2 | **Stop.** `gh` could not read the issue; report its error |

A first run on a closed issue stops too: `/to-spec` publishes open issues, and a closed one is
either finished or abandoned.

`--skip-critique` on a re-run applies the same skip to the Spec as it stands: go to step 9.

## 2. Derive the Criteria

Read `## User Stories` for the behaviour, and the rest of the Spec for the numbers that make a Then
measurable — `## Implementation Decisions` and `## Testing Decisions` are where the thresholds,
error codes, and limits usually are.

The grammar is `CONTRACTS.md`'s, and these are the parts that go wrong most:

- **Given/When/Then by default**, three clauses, one per line. **EARS** —
  `WHEN <trigger> THE SYSTEM SHALL <behaviour>`, one line — for a constraint that holds always and
  would need a fictional Given: a latency, a limit, a status code.
- **Every Then resolves to pass or fail.** "Fast", "gracefully", "correct", "properly",
  "reasonable", "appropriate" each mark a Then not yet written. Replace it with the number, the
  status code, or the literal string a reader can check. An EARS `SHALL` clause is held to exactly
  the same bar — the form changes, the measurability requirement does not.
- **`[manual]` immediately after the id** on any Criterion a human must check. This tag is the only
  thing that later decides a Slice needs a person, so a Criterion whose check you cannot imagine
  automating gets tagged now. It is tagged because automating it is not worth it, not because it is
  hard to write.
- **`[command]` immediately after the id** on a Criterion proven by running a command rather than by
  a test: a sandbox dry run, a vendor or schema check. Close it with a `Command:` line naming the
  exact command, runnable from the repository root, read-only, and exiting 0 exactly when the Then
  holds. Never `[manual]` for a check a session can run, even one needing a credential some
  sessions lack: `CONTRACTS.md` has why. Not for lint, typecheck, format or the test suite, which
  `/finalize-pr` already runs on every pull request. Ask the founder for the command when the Spec
  does not give it; a guessed command is a Criterion nobody can prove.
- **At most one tag** per Criterion.
- **Ids are `C1`, `C2`, `C3`** in order.

Stories do not map one-to-one onto Criteria. Collapse two stories that describe the same observable
behaviour into one Criterion; split a story that promises two separately checkable things into two;
write none for a story that is pure rationale with nothing to observe.

**Name no file paths.** Not in a Criterion, not anywhere you write. A path is a promise about
structure that the next refactor breaks silently. Name behaviour, and name the Seam. A `Command:`
line is the one exception, as it is for the Verification: a command that rots fails loudly.

## 3. Propose the Verification

The Verification proves the **whole feature** after the last Slice lands, which is what makes it
different from a Criterion. Exactly one form, never both:

- **`Command:`** followed by a single runnable command, to be run on a fresh checkout of the default
  branch after the last Slice merges. Preferred wherever the feature can be proven this way.
- **`Walkthrough:`** followed by numbered steps a person performs, printed as the last thing the
  founder is asked to do.

Prefer command form. Reach for a walkthrough when what the feature changes is something only a
person can see.

## 4. Compose the Spec, and write nothing yet

The proposed Spec is the issue body as it stands, with three additions and nothing else changed:

```markdown
**Status:** draft

{the body /to-spec published, byte for byte}

## Criteria

### C1
Given ...
When ...
Then ...

### C2 [manual]
Given ...
When ...
Then ...

### C3 [command]
WHEN ... THE SYSTEM SHALL ...
Command: `{the exact command}`

## Verification

Command: `{command}`
```

- **Add, never rewrite.** `/to-spec`'s sections are the founder's prose and stay as they are. A file
  path in them is raised in step 8, not silently removed.
- **No `# title` line.** The issue's title is the Spec's title.
- `## Criteria` and `## Verification` go last, with every clause and every `Command:` line in full.

Hold it in a temporary file. It is what the critic doubts in step 6 and what step 9 writes once the
founder has settled it. Nothing reaches the issue before step 8 is answered.

## 5. Read the Critics list from the per-repo workflow file

`docs/agents/workflow.md` holds the ordered list this skill reads, and a `**Specs:**` line it does
not; `CONTRACTS.md` describes both. Read the list, ignore the rest:

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

## 6. Walk the chain, and dispatch the critic that runs

The point of this gate is that a different vendor's model doubts what a Claude session wrote. That
is why the Claude entry sits last: it is the floor that makes the gate work on a machine which has
installed nothing, not the critic the gate wants.

Walk the Critics list by the rules in
[../../references/chain-walking.md](../../references/chain-walking.md): which entries are
available, when an entry counts as having produced findings, where the walk ends, what to do when
every entry fails, and which entry to name. Read it before dispatching anything.

What those rules leave to this skill:

- **Findings** are findings under the seven headings of step 6's prompt. An entry that returns
  anything else has produced nothing, and the walk moves on.
- **The entry that ran** is the critic the Critique line names in step 9.
- **When every entry fails**, post no comment and write no Critique line. Step 8 still runs on the
  Criteria alone, and step 9 writes the Spec at `draft`.

### The prompt

One prompt, used verbatim by whichever entry of the chain runs, so the paths are comparable and a
Critique reads the same whoever produced it. Fill in the Spec's title, its body, and the ADR paths;
change nothing else.

The Spec goes into the prompt itself, not as a path or a `gh` command for the critic to run. The
`codex` and `google` wrappers run another vendor's CLI, which may have no `gh` auth and may be
sandboxed to the working directory, so neither a `gh` call nor a file in this session's scratchpad
is something every critic can be relied on to read. Text in the prompt reaches all three the same
way. The body the critic gets is the one step 4 composed: `/to-spec`'s sections with the proposed
`## Criteria` and `## Verification` below them, or on a re-run the Spec as it stands on the issue.

```
You are doubting a specification, not writing code. Do not edit, create, or delete any
file, and do not run any command that changes state. Read and report only.

The Spec you are doubting is issue #{number}, "{spec title}". Its full body is between
the two SPEC lines below. It is the whole Spec; do not look for it on disk.

----- SPEC BEGIN -----
{spec body, verbatim}
----- SPEC END -----

Then read, in this order:

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
resolution in step 8, which is the one step of this skill that is not the agent's to make.

### Dispatching an entry

Every vendor is dispatched through the Agent tool. Only the subagent and how the model is named
differ.

**`codex`.** `subagent_type: "codex:codex-rescue"`, with the step 6 prompt prefixed by one line
naming the model:

```
Run with --model {model} from the per-repo workflow file. Do not substitute another model.
```

When the entry's model is `default`, say so instead and let the wrapper choose: the Codex plugin
asks callers to leave `--model` unset unless a specific model was requested, and `default` is the
entry recording that choice.

**`google`.** `subagent_type: "antigravity:agy-rescue"`, with the step 6 prompt prefixed by:

```
MODEL: {model}
Run agy with --model {model}. Do not substitute another model. This is read-only:
do not pass --add-dir and do not write any file.
```

`agy-rescue` is a thin forwarding wrapper around `agy --print`, the same role `codex-rescue` plays
for Codex. It omits `--model` unless the caller asks for one, so the entry's model has to be named
here or the Critique line would record a model that was never passed. Step 6 has already confirmed
the id is offered on this account, which is what makes naming it safe.

**`claude`.** The step 6 prompt, `model` set to the entry's model, and a read-only `subagent_type`:
prefer a read-only agent type the project offers (`Explore` is one); otherwise `general-purpose`,
whose write tools the prompt's first paragraph forbids.

If the Agent tool rejects the model you pass — the workflow file may name a model this harness
addresses by a different alias — **do not run on the default**. Map the configured name to the alias
the tool accepts if an obvious one exists, and name the mapping in what you report. If no obvious
mapping exists, the entry is unavailable: say so and move to the next one, the same as any other
entry that cannot run as configured. What must never happen is the Critique line claiming a model
that did not run.

Wait for the agent to finish. **An agent that returns nothing usable has not failed the run, it has
failed its entry:** apply step 6's fall-through, say which entry returned nothing, and try the next.
Do not write the findings yourself, at any point in the chain. This session derived the Criteria;
this session doubting them is the thing the gate exists to prevent, which is also why the Claude entry
is a fresh subagent and not this session reading the Spec again.

## 7. Post the findings as one comment

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

The comment can quote Criteria the issue does not carry yet. That is expected: the critic doubted
the proposed Spec, and step 9 writes the settled one.

## 8. Settle the Criteria and every finding with the founder

One round, everything at once. Do not go back for a second pass: this is a gate on the Spec, not a
redesign of it.

On a first run, show:

1. **The proposed Criteria**, every clause, not a summary, and the proposed **Verification**.
2. **What you decided for them**: a story you wrote no Criterion for, and why; a Then you picked a
   number for because the Spec never gave one; a file path in `/to-spec`'s sections, which is what
   makes a Spec rot, named so they can decide.
3. **The critic's findings**, numbered, each quoting the text it doubts.

On a re-run there is no proposal, only the findings. With `--skip-critique`, or when every critic
failed, there are no findings, only the proposal; say which, and why.

Say plainly that nothing has been written yet, then wait. The Spec is the founder's, not yours.
Apply what they change to the Criteria and the Verification, and take a resolution for each finding.
Each finding ends in exactly one of three states:

| Resolution | What it means | What you do |
| --- | --- | --- |
| **accepted** | The doubt is real | Edit the Spec so the doubt no longer applies |
| **moved to Out of Scope** | Real, but not this feature | Add a line to `## Out of Scope` naming it |
| **rejected** | Not a problem | Record the founder's reason, change nothing |

A finding with no resolution is not resolved, and a silence is not a confirmation. If the founder
leaves anything open, ask again for that one rather than proceeding, because `/dispatch-slices` will
not ask.

Where a finding says a Criterion is not binary, the accepted edit rewrites the Then clause until it
resolves to pass or fail. `CONTRACTS.md` has the measurable/not-measurable table.

**Never renumber a Criterion.** Ids are cited from Slices, test names and review comments once they
exist. A Criterion dropped in this round leaves a gap; one added takes the next unused number.

## 9. Write the Spec, then its Critique line and Status

**Write the body.** Read the issue body again immediately before writing. If it differs from what
step 1 read, someone edited the Spec while the critic ran or the founder was deciding: **stop**,
show what changed, and start again from step 1 rather than overwriting their edit. Otherwise write
the settled Spec from its temporary file, so backticks and quotes survive the shell, and read it
back:

```bash
gh issue edit {number} --body-file - < {body_file}
python3 <this skill dir>/../../scripts/spec.py read {number}
```

On a first run the body is step 4's composition with step 8's changes, at `**Status:** draft`. On a
re-run it is the body as it stood with step 8's changes; leave its header lines alone and skip the
write when nothing was accepted or moved. A read that exits non-zero means the write broke the
Spec's shape: **stop** and print the `✘` line before setting any Status.

**Then the Critique line and the Status**, through the script, which keeps the header order and
reads each write back:

```bash
python3 <this skill dir>/../../scripts/spec.py header {number} critique "{the Critique line}"
python3 <this skill dir>/../../scripts/spec.py set-status {number} critiqued
```

The Critique line is `{vendor} ({model}), #{number} comment {id}, {YYYY-MM-DD}`: the critic that
actually ran from step 6, the comment from step 7, and today's date. With `--skip-critique` it is
`skipped, {reason}, {YYYY-MM-DD}`. The header then reads:

```markdown
**Status:** critiqued
**Critique:** google (gemini-3.8-flash-high), #60 comment 2847193044, 2026-09-18
```

**When every critic failed**, write the body and stop there: no Critique line, no Status change.
The Spec stays at `draft`, which is exactly what `draft` means: anchored, and nobody has doubted it.
A later `/critique-spec {number}` is a re-run that critiques it.

Either script command exiting non-zero → **stop** and report it. The Status is `critiqued` when
`set-status` reads it back, and not before.

**The Spec stays a description of behaviour.** The findings live in the comment; the resolutions
live in the Spec only as changed behaviour. Do not append a findings section, a resolution log, or a
rejected-with-reason list to the body. A Spec that accumulates its own history stops being readable
as a description of the code, and being that description is the Spec's whole job.

**Record the resolutions in one follow-up comment** on the Spec issue, after the Status is set,
whenever there were findings:

```bash
gh issue comment {number} --body-file {resolutions_file}
```

One line per finding, numbered as step 8 presented them: `accepted`, `moved to Out of Scope`, or
`rejected`, and for a rejected finding the founder's reason. The rejected reasons are the part that
matters: the next reader of this Spec deserves to know what was doubted and waved through, and the
body is not the place for it.

## 10. Report

```
Spec:     #{number} {title}
Criteria: {n} ({m} manual, {k} command)
Verify:   {Command: ... | Walkthrough, {k} steps}
Critic:   {vendor} ({model}), entry {i} of {n} in the Critics list | skipped: {reason} | every entry failed
Skipped:  {one line per earlier entry, naming it and why it did not run}
Findings: {n}: {a} accepted, {o} moved to Out of Scope, {r} rejected
Comment:  {comment_url}
Resolved: {resolutions_comment_url}
Status:   {(none) | draft} → {critiqued | draft}

Next: {/to-tickets, then /dispatch-slices {number} | /critique-spec {number} once a critic can run}
```

List each rejected finding with the founder's reason underneath, the same reasons the resolutions
comment carries.

## Rules

- **Nothing is written before the founder answers step 8.** Not the body, not the Status. The
  findings comment is the one write before it, and it holds only the critic's own words.
- **Add to `/to-spec`'s body, never rewrite it.** The Status line goes above it; `## Criteria` and
  `## Verification` go below it.
- Only an unanchored issue or a Spec at `draft` is critiqued. Every other Status stops the run with
  the reason named.
- The Spec is the body of its Spec issue, read through `spec.py`. Header lines are written only
  through `spec.py`; the body is edited only by re-reading it and writing it back whole.
- Never write the findings yourself, and never let the critic write the Spec. The critic doubts, the
  founder resolves, this skill edits.
- The Critics chain is walked by
  [../../references/chain-walking.md](../../references/chain-walking.md). The Critique line names
  the entry that ran, never one that was skipped or returned nothing.
- When no entry produces findings, post no comment, write no Critique line, and leave the Spec at
  `draft` with its confirmed Criteria.
- **Never renumber a Criterion.**
- **Never write a file path into a Spec.** A `Command:` line is the one exception.
- The last entry of the Critics list must name `claude`. Without a floor the chain can run out,
  and a gate that can run out is not a gate.
- Nothing from `docs/agents/workflow.md` enters the session's context beyond the entries this skill
  walks.
- The Status change is real once `spec.py set-status` reads it back. Nothing here touches the
  repository.

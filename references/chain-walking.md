# Walking a chain

How a skill picks which entry of an ordered model chain runs. `/critique-spec` walks the Critics
list with these rules, and any other skill that walks a chain of the same `{vendor}, {model}` shape
cites this file rather than restating them. `CONTRACTS.md` describes the lists themselves.

Written once, here, because two copies of the same walk drift, and a drifted walk is one where a
security review and a Critique disagree about what counts as having run.

The citing skill owns what a usable result looks like and what it writes once an entry produces one.
This file owns the walk.

## The walk

Take the entries in order. An entry runs only if it is **available**, and it counts only if it
**produces findings**. Two questions, in that order, and both have to be answered before moving on.

**The first entry that produces findings ends the walk.** Do not dispatch anything below it, do not
run a second entry for comparison, and do not fall through to the last entry because an earlier
entry's findings look thin. One result per run, from one entry: the chain exists to find which entry
that is, not to collect several opinions.

## Available

What each vendor needs before it is worth dispatching:

| Vendor | Available when all of these hold |
| --- | --- |
| `codex` | `command -v codex` finds the CLI, and `codex:codex-rescue` appears in this session's available agent types |
| `google` | `command -v agy` finds the CLI, `antigravity:agy-rescue` appears in this session's available agent types, and the entry's model id appears in `agy models` |
| `claude` | always, since it is the session you are already in |

Check every part. A plugin without its CLI dispatches an agent that cannot reach a model, and a CLI
without its plugin leaves nothing to dispatch.

**The `agy models` check is not optional for a `google` entry.** Run it and match the entry's model
against the ids in the first column:

```bash
agy models
```

It prints one tab-separated `{id}\t{display label}` per line under a `Fetching available models...`
header. Match on the id, which is what `--model` takes. An id that is absent (misspelled, or not
offered on this account's tier) makes the entry unavailable: **say the id is unavailable, do not
dispatch agy, and move to the next entry.** Which ids exist depends on the account, so this has to
be read live and never from a list baked into a skill. `agy models` on a signed-out account cannot
answer, which is the same answer: unavailable, move on.

Never dispatch a `google` entry whose model id `agy models` does not list.

## Produces findings

Availability is not usability. A CLI can be installed and logged out, and both of these CLIs sit in
exactly that state on a fresh machine. An unauthenticated headless `agy --print` exits 0 having
written nothing, a failure the antigravity plugin documents; a dispatched agent can also return an
error, a re-auth instruction, or an empty report. None of those is a result.

So when a dispatched entry returns nothing usable (no findings in the shape the citing skill asks
for, an empty report, or the agent's own message that it could not reach a model), **say which entry
returned nothing and move to the next entry.** Falling through on a silent failure, and not only on
absent tooling, is what makes the last entry reachable in the case it exists for.

An entry that is absent, that cannot be run as configured, or that returns nothing usable is
skipped, not fatal. The chain is only exhausted when its last entry has been tried.

## Every entry failed

**When every entry has been tried and none produced findings, stop.** Report that no entry produced
a result, name what each entry did, and write nothing the citing skill would have written from a
result. A gate that held is honest; a record naming an entry that produced nothing is a gate that
lied.

## Name the entry that ran

Whichever entry runs, **hold on to which one it was**. Everything the citing skill writes names that
entry, `{vendor} ({model})`, never an earlier one that was skipped or returned nothing. A record
naming an entry that did not run is worse than no record.

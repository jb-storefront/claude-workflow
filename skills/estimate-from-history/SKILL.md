---
name: estimate-from-history
description: Size work against what this repo's own merged PRs actually cost, instead of guessing from human intuition. Use when asked how long something will take, how big a piece of work is, whether a spec is too large, how to break work into slices, or when writing a plan or roadmap that implies effort. Also use before pushing back on a request as "too big" or "not worth the complexity": check the corpus first.
---

# Estimate from history

Human effort intuition is wrong here by an order of magnitude, because the work
is done by parallel agent sessions, not people. Don't correct for that with a
fudge factor. Replace the guess with this repo's measured history.

## The one thing to get right

**Per-slice effort is not predictable from anything you know up front.** This is
measured, not assumed: on gr4vy/ucp-demo, acceptance-criteria count correlates
with actual effort at r=-0.06 and files-touched at r=+0.19. The only features
that correlate (lines added, commit count) are outputs of doing the work.

So never say "this slice looks big, call it four hours." Say what the corpus
supports: a slice costs about the median, half of them land in the p25-p75 band,
and the variance is real. The estimable quantity is **how many slices**, not how
long each one takes.

## Procedure

1. **Get a corpus.** A corpus is per repo and lives *in* that repo, at
   `.claude/calibration/`. Never in this skill's own directory: a plugin update
   replaces that directory, and one repo's numbers are wrong for another repo.

   Read `.claude/calibration/calibration.json`. If it is missing, older than
   ~30 days, or records a different `repo` than the one you are in, regenerate
   it with the `scripts/mine_history.py` that sits next to this SKILL.md:

   ```bash
   python3 <this skill dir>/scripts/mine_history.py \
     --repo <owner>/<name> --out-dir .claude/calibration
   ```

   It needs `gh` authenticated with `repo` scope. It reads merged PRs, pins when
   work started, discards rebased PRs whose timestamps collapsed, and writes
   `calibration.json` plus a readable `CALIBRATION.md`.

   Commit both files. The calibration is a measurement of the team's history,
   not a local cache, and every session that estimates should read the same one.

   If the repo has no corpus and you cannot generate one, say that the estimate
   is uncalibrated and give the slice count only. Do not fall back to intuition
   for the minutes, and do not reuse another repo's median.

2. **Decompose into slices.** A slice is one issue, one PR, one session. Use the
   parent-fanout number as a sanity check: if a spec decomposes into far fewer
   slices than the historical median, the slices are probably too coarse.

3. **Answer in slices first.** Lead with the count, what each touches, what
   blocks what, and which can run in parallel. That is the part that is real.

4. **Only then convert, and show the band.** Multiply slices by the median, and
   quote p25-p75 so the uncertainty stays visible. Prefer the throughput number
   for anything calendar-shaped: slices per active day beats summing minutes,
   because it already contains review, rework and context switching.

5. **Say active days, never calendar days.** The corpus records both, and they
   differ by a lot. Elapsed calendar time is dominated by when someone chose to
   work, which is not something to predict.

## Reporting

Good:

> Six slices. Four are independent and can dispatch in parallel; the schema
> slice blocks the other two. At this repo's median of 75 min per slice that is
> roughly 7 hours of agent time, most likely 6-11 given the usual spread, and
> at 3 slices per active day about two active days.

Bad:

> This is a fairly large feature, probably 2-3 weeks of work.

Bad for a different reason:

> This slice has 14 acceptance criteria so it will take about 3 hours.

## Never use size to refuse

Sizing exists to sequence work and to decide where to check in, not to decide
whether to start. "Too big", "not worth the complexity" and "we can do that
later" are not conclusions this skill supports. If something genuinely should
not be done, the reason is a dependency, a risk, or missing information. Name
that instead.

## Applying it to a new repo

The miner assumes nothing except merged PRs. Two things sharpen it:

- A start-of-work marker commit. Default pattern is `start work on #(\d+)`,
  written by the `/start-issue` skill. Override with `--start-marker`. Without
  one it falls back to the first commit on the branch and GitHub's closing
  reference, which is looser but still works.
- Squash-on-merge is fine and needs no accommodation. GitHub keeps the PR's
  branch commits after a squash, and the miner reads those, not the merge
  commit. Do not recommend changing a repo's merge policy for this skill's
  benefit.
- The miner reads author dates, which survive a rebase. Committer dates do not:
  a rebase-before-merge rewrites every one of them to the rebase moment, which
  is what a collapsed PR usually means. If PRs are still being excluded, they
  were rewritten by something that reset authorship too.

Tuning knobs: `--gap-cap` (default 45 min; a longer gap between commits counts
as away rather than working) and `--rebase-window` (default 10 min).

## Re-check the correlations

`CALIBRATION.md` recomputes the predictor table every run. If some feature ever
starts correlating strongly on a larger corpus, the advice above changes and you
should say so. Read the table; don't assume this file's numbers are current.

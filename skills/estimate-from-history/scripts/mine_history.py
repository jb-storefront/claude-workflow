#!/usr/bin/env python3
"""Mine a GitHub repo's merged PRs into an effort-calibration corpus.

Reads history through `gh api graphql`, reconstructs how long each slice
actually took, and writes calibration.json + CALIBRATION.md.

The output is deliberately distributional, not a per-slice predictor. See the
correlation block it prints: on repos using a slice workflow, the up-front
features (acceptance-criteria count, expected file count) do not predict
effort, so the honest calibration is "a slice costs roughly X, count slices".
"""

import argparse
import json
import os
import re
import statistics as st
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

PR_QUERY = """
query($owner:String!,$name:String!,$cursor:String){
  repository(owner:$owner,name:$name){
    pullRequests(states:MERGED,first:50,after:$cursor,orderBy:{field:CREATED_AT,direction:DESC}){
      pageInfo{hasNextPage endCursor}
      nodes{
        number title createdAt mergedAt additions deletions changedFiles
        labels(first:20){nodes{name}}
        closingIssuesReferences(first:5){nodes{number}}
        commits(first:100){nodes{commit{committedDate authoredDate messageHeadline}}}
      }
    }
  }
}
"""

ISSUE_QUERY = """
query($owner:String!,$name:String!,$cursor:String){
  repository(owner:$owner,name:$name){
    issues(first:100,after:$cursor,states:[OPEN,CLOSED]){
      pageInfo{hasNextPage endCursor}
      nodes{number title state createdAt closedAt body labels(first:20){nodes{name}}}
    }
  }
}
"""


def gh_graphql(query, owner, name, path):
    """Page through a GraphQL connection, returning all nodes."""
    nodes, cursor = [], None
    while True:
        cmd = ["gh", "api", "graphql", "-f", f"query={query}",
               "-F", f"owner={owner}", "-F", f"name={name}"]
        cmd += ["-F", f"cursor={cursor}"] if cursor else ["-F", "cursor="]
        out = subprocess.run(cmd, capture_output=True, text=True)
        if out.returncode != 0:
            sys.exit(f"gh api graphql failed:\n{out.stderr.strip()}")
        conn = json.loads(out.stdout)["data"]["repository"][path]
        nodes += conn["nodes"]
        if not conn["pageInfo"]["hasNextPage"]:
            return nodes
        cursor = conn["pageInfo"]["endCursor"]


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def authored(commit):
    """When the commit was written. Survives rebase; committedDate does not."""
    return commit.get("authoredDate") or commit["committedDate"]


def count_checkboxes(body):
    return len(re.findall(r"^\s*[-*]\s*\[[ xX]\]", body or "", re.M))


def parent_of(body):
    m = re.search(r"##\s*Parent\s*\n+\s*#(\d+)", body or "")
    return int(m.group(1)) if m else None


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = st.mean(xs), st.mean(ys)
    den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else None


def pct(vals, p):
    s = sorted(vals)
    return s[min(int(len(s) * p), len(s) - 1)]


def analyse_pr(pr, start_re, gap_cap, rebase_window):
    """Reconstruct one PR's effort. Returns a record, possibly marked unusable."""
    # Author dates, not committer dates. A rebase rewrites every committer date
    # to the rebase moment and leaves author dates alone, so reading committer
    # dates discards every PR that was rebased before merge.
    commits = sorted((c["commit"] for c in pr["commits"]["nodes"]), key=authored)
    times = [ts(authored(c)) for c in commits]
    merged = ts(pr["mergedAt"])

    rec = {
        "pr": pr["number"], "title": pr["title"],
        "files": pr["changedFiles"], "additions": pr["additions"],
        "deletions": pr["deletions"], "commits": len(commits),
        "merged_at": pr["mergedAt"],
        "labels": [l["name"] for l in pr["labels"]["nodes"]],
        "issue": None, "active_minutes": None, "span_minutes": None,
        "usable": False, "excluded": None,
    }

    # Issue linkage: the start-work marker commit is most reliable because it
    # also pins when work began; fall back to GitHub's own closing reference.
    if commits:
        m = start_re.search(commits[0]["messageHeadline"])
        if m:
            rec["issue"] = int(m.group(1))
    if rec["issue"] is None:
        refs = pr["closingIssuesReferences"]["nodes"]
        if refs:
            rec["issue"] = refs[0]["number"]

    if not times:
        rec["excluded"] = "no commits"
        return rec

    rec["span_minutes"] = round((merged - times[0]).total_seconds() / 60, 1)

    # Author dates survive a rebase, so this now catches only the genuine case:
    # a branch whose commits really were all written within a few minutes, or
    # one rewritten by something that reset authorship too.
    if len(times) >= 2 and (times[-1] - times[0]) < timedelta(minutes=rebase_window):
        rec["excluded"] = "author timestamps collapsed"
        return rec

    # Gap-capped active time: sum the intervals between commits, treating any
    # gap longer than the cap as time away rather than time working. This is
    # what turns a PR left open over a weekend back into its real work window.
    active = 0.0
    for a, b in zip(times, times[1:]):
        active += min((b - a).total_seconds() / 60, gap_cap)
    active += min((merged - times[-1]).total_seconds() / 60, gap_cap)

    rec["active_minutes"] = round(active, 1)
    rec["usable"] = True
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--gap-cap", type=float, default=45.0,
                    help="minutes; a longer gap between commits counts as away, not working")
    ap.add_argument("--rebase-window", type=float, default=10.0,
                    help="minutes; multi-commit PRs authored within less than this are discarded")
    ap.add_argument("--start-marker", default=r"start work on #(\d+)",
                    help="regex with one capture group for the issue number")
    args = ap.parse_args()

    owner, name = args.repo.split("/", 1)
    start_re = re.compile(args.start_marker)

    prs = gh_graphql(PR_QUERY, owner, name, "pullRequests")
    issues = gh_graphql(ISSUE_QUERY, owner, name, "issues")
    by_num = {i["number"]: i for i in issues}

    records = [analyse_pr(p, start_re, args.gap_cap, args.rebase_window) for p in prs]
    for r in records:
        i = by_num.get(r["issue"])
        r["acceptance_criteria"] = count_checkboxes(i["body"]) if i else None
        r["parent"] = parent_of(i["body"]) if i else None

    usable = [r for r in records if r["usable"]]
    if not usable:
        sys.exit("No usable PRs found. Check --start-marker and --rebase-window.")

    active = [r["active_minutes"] for r in usable]
    slice_stats = {
        "n": len(usable), "min": min(active), "p25": pct(active, 0.25),
        "median": st.median(active), "p75": pct(active, 0.75), "max": max(active),
    }

    # Do the predictors actually predict? Recomputed every run so this stops
    # being an assumption and starts being a measurement.
    correlations = {}
    for field in ("acceptance_criteria", "files", "additions", "commits"):
        pairs = [(r[field], r["active_minutes"]) for r in usable if r.get(field) is not None]
        if len(pairs) >= 3:
            r_val = pearson([p[0] for p in pairs], [p[1] for p in pairs])
            correlations[field] = round(r_val, 2) if r_val is not None else None

    # Throughput on days work actually shipped, not calendar days.
    per_day = Counter(ts(r["merged_at"]).date() for r in records)
    dates = sorted(per_day)
    throughput = {
        "active_days": len(per_day),
        "calendar_days": (dates[-1] - dates[0]).days + 1 if dates else 0,
        "median_per_active_day": st.median(per_day.values()),
        "max_per_active_day": max(per_day.values()),
    }

    # How many slices a parent spec decomposes into.
    fanout = defaultdict(list)
    for i in issues:
        p = parent_of(i["body"])
        if p:
            fanout[p].append(i["number"])
    sizes = [len(v) for v in fanout.values()]
    parent_stats = ({"n_parents": len(sizes), "median_slices": st.median(sizes),
                     "min": min(sizes), "max": max(sizes)} if sizes else None)

    calibration = {
        "repo": args.repo,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "params": {"gap_cap": args.gap_cap, "rebase_window": args.rebase_window},
        "slice_active_minutes": slice_stats,
        "correlations_with_active_minutes": correlations,
        "throughput": throughput,
        "parent_fanout": parent_stats,
        "excluded": Counter(r["excluded"] for r in records if r["excluded"]),
        "records": records,
    }

    os.makedirs(args.out_dir, exist_ok=True)
    out_json = f"{args.out_dir.rstrip('/')}/calibration.json"
    with open(out_json, "w") as f:
        json.dump(calibration, f, indent=1, default=str)

    s, t = slice_stats, throughput
    lines = [
        f"# Effort calibration: {args.repo}",
        "",
        f"Generated {calibration['generated_at']} from {len(records)} merged PRs "
        f"({s['n']} usable, {len(records) - s['n']} excluded).",
        "",
        "## What one slice costs",
        "",
        f"| min | p25 | median | p75 | max |",
        f"|----|----|----|----|----|",
        f"| {s['min']:.0f}m | {s['p25']:.0f}m | **{s['median']:.0f}m** | {s['p75']:.0f}m | {s['max']:.0f}m |",
        "",
        f"Half of all slices land between {s['p25']:.0f} and {s['p75']:.0f} minutes of active agent time.",
        "",
        "## Do up-front features predict effort?",
        "",
        "| feature | r vs active minutes | usable up front? |",
        "|---|---|---|",
    ]
    known = {"acceptance_criteria": "yes", "files": "estimated",
             "additions": "no, only known after", "commits": "no, only known after"}
    for k, v in correlations.items():
        lines.append(f"| {k} | {v:+.2f} | {known.get(k, '?')} |")
    lines += [
        "",
        "## Throughput",
        "",
        f"- {t['median_per_active_day']:.0f} slices on a median active day, {t['max_per_active_day']} at peak",
        f"- {t['active_days']} active days spread over {t['calendar_days']} calendar days",
    ]
    if parent_stats:
        p = parent_stats
        lines.append(f"- a parent spec decomposes into {p['median_slices']:.0f} slices "
                     f"(range {p['min']}-{p['max']}, n={p['n_parents']})")
    if calibration["excluded"]:
        lines += ["", "## Excluded", ""]
        lines += [f"- {v} x {k}" for k, v in calibration["excluded"].items()]

    out_md = f"{args.out_dir.rstrip('/')}/CALIBRATION.md"
    with open(out_md, "w") as f:
        f.write("\n".join(lines) + "\n")

    print("\n".join(lines))
    print(f"\nwrote {out_json} and {out_md}")


if __name__ == "__main__":
    main()

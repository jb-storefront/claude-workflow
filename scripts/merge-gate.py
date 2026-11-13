#!/usr/bin/env python3
"""Decide whether a PR's head was reviewed, whether Copilot is clean, and which Auto-fix session to stop.

Usage:
  merge-gate.py --pr {number} [--repo owner/repo]   gather the snapshot with gh, then judge it
  merge-gate.py [snapshot.json]                     judge a snapshot (stdin when no path)

/merge-pr and /merge-stack run this before a merge. /review-pr reviews one head
and hands the PR to an Auto-fix session, which goes on pushing fixes for
Copilot's comments. Those commits are seen by Copilot and by nobody else, so a
head the latest /review-pr summary does not name has not been reviewed.

The snapshot is clean-predicate.py's, plus:

  comments   [{author, body, created_at}]   the PR's issue comments

Prints JSON and exits 0:

  reviewed   {state: fresh | stale | blocked | none, head, summary_url}
             fresh    the latest summary is Ready and names the head commit
             stale    the latest summary names an earlier commit
             blocked  the latest summary names the head and is Draft
             none     /review-pr never posted a summary here
  last_ready {head, summary_url}   the newest Ready summary's head, or nulls.
             /review-pr reviews only the commits after it, because everything
             up to it was reviewed whole and passed.
  autofix    {session}   the newest summary's Auto-fix session id, or null
  copilot    clean-predicate.py's verdict, unchanged

Exits 2 when the snapshot cannot be read or gathered, so a failure never reads
as a verdict.
"""

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "clean_predicate", Path(__file__).with_name("clean-predicate.py")
)
clean_predicate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(clean_predicate)

# CONTRACTS.md, "The /review-pr summary comment": the first line and the
# Head: and Auto-fix: lines are read by machines.
HEADING = re.compile(r"^## /review-pr — (Ready|Draft)\s*$")
HEAD_LINE = re.compile(r"^Head:\s*`([0-9a-f]{7,40})`", re.M)
AUTOFIX_LINE = re.compile(r"^Auto-fix:.*?\b(session_[A-Za-z0-9]+)", re.M)


def first_line(body):
    return (body or "").lstrip().split("\n", 1)[0].strip()


def summaries(snap):
    found = [c for c in snap["comments"] if HEADING.match(first_line(c["body"]))]
    return sorted(found, key=lambda c: clean_predicate.instant(c["created_at"]))


def reviewed(snap, found):
    if not found:
        return {"state": "none", "head": None, "summary_url": None}
    latest = found[-1]
    m = HEAD_LINE.search(latest["body"])
    head = m.group(1) if m else None
    outcome = HEADING.match(first_line(latest["body"])).group(1)
    if not head or not snap["head_sha"].startswith(head):
        state = "stale"
    elif outcome == "Draft":
        state = "blocked"
    else:
        state = "fresh"
    return {"state": state, "head": head, "summary_url": latest.get("url")}


def last_ready(found):
    # A Draft summary's head had blocking findings, so it is never a point to
    # review from; only a head a review passed whole is.
    for c in reversed(found):
        if HEADING.match(first_line(c["body"])).group(1) == "Ready":
            m = HEAD_LINE.search(c["body"])
            if m:
                return {"head": m.group(1), "summary_url": c.get("url")}
    return {"head": None, "summary_url": None}


def autofix(found):
    # A re-run of /review-pr reuses a live session and says so, but a summary
    # written before Auto-fix existed has no line, so look back past it.
    for c in reversed(found):
        m = AUTOFIX_LINE.search(c["body"])
        if m:
            return {"session": m.group(1)}
    return {"session": None}


def judge(snap):
    found = summaries(snap)
    return {
        "reviewed": reviewed(snap, found),
        "last_ready": last_ready(found),
        "autofix": autofix(found),
        "copilot": clean_predicate.judge(snap),
    }


def gh(*args):
    out = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def paged(path):
    pages = gh("api", "--paginate", "--slurp", path)
    return [item for page in pages for item in page]


THREADS = """
query($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id isResolved path line
          comments(first: 1) { nodes { author { login } url } }
        }
      }
    }
  }
}
"""


def threads(owner, name, number):
    out, after = [], None
    while True:
        args = ["api", "graphql", "-f", f"query={THREADS}", "-f", f"owner={owner}",
                "-f", f"name={name}", "-F", f"number={number}"]
        if after:
            args += ["-f", f"after={after}"]
        page = gh(*args)["data"]["repository"]["pullRequest"]["reviewThreads"]
        for t in page["nodes"]:
            first = (t["comments"]["nodes"] or [{}])[0]
            out.append({
                "id": t["id"],
                "author": ((first.get("author") or {}).get("login")),
                "resolved": t["isResolved"],
                "path": t["path"],
                "line": t["line"],
                "url": first.get("url"),
            })
        if not page["pageInfo"]["hasNextPage"]:
            return out
        after = page["pageInfo"]["endCursor"]


def gather(repo, number):
    if not repo:
        repo = gh("repo", "view", "--json", "nameWithOwner")["nameWithOwner"]
    owner, name = repo.split("/", 1)
    base = f"repos/{repo}"
    pull = gh("api", f"{base}/pulls/{number}")
    head = pull["head"]["sha"]
    commit = gh("api", f"{base}/commits/{head}")
    runs = gh("api", "--paginate", "--slurp", f"{base}/commits/{head}/check-runs?per_page=100")
    return {
        "head_sha": head,
        "head_committed_at": commit["commit"]["committer"]["date"],
        "reviews": [
            {
                "author": (r.get("user") or {}).get("login"),
                "state": r["state"],
                "commit_id": r["commit_id"],
                "submitted_at": r.get("submitted_at") or "1970-01-01T00:00:00Z",
            }
            for r in paged(f"{base}/pulls/{number}/reviews?per_page=100")
        ],
        "threads": threads(owner, name, number),
        "checks": [
            {"name": c["name"], "status": c["status"], "conclusion": c["conclusion"]}
            for page in runs
            for c in page["check_runs"]
        ],
        "timeline": [
            {
                "event": e.get("event"),
                "requested_reviewer": (e.get("requested_reviewer") or {}).get("login"),
                "actor": (e.get("actor") or {}).get("login"),
                "created_at": e.get("created_at"),
            }
            for e in paged(f"{base}/issues/{number}/timeline?per_page=100")
            if e.get("created_at")
        ],
        "comments": [
            {
                "author": (c.get("user") or {}).get("login"),
                "body": c["body"],
                "created_at": c["created_at"],
                "url": c["html_url"],
            }
            for c in paged(f"{base}/issues/{number}/comments?per_page=100")
        ],
    }


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", nargs="?")
    parser.add_argument("--pr", type=int)
    parser.add_argument("--repo")
    args = parser.parse_args(argv)
    try:
        if args.pr:
            snap = gather(args.repo, args.pr)
        elif args.snapshot:
            snap = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        else:
            snap = json.loads(sys.stdin.read())
        verdict = judge(snap)
    except subprocess.CalledProcessError as exc:
        print(f"✘ gh failed: {' '.join(exc.cmd[:4])}: {exc.stderr.strip()[-300:]}", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f"✘ cannot read snapshot: {exc!r}", file=sys.stderr)
        return 2
    print(json.dumps(verdict, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

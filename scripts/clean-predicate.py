#!/usr/bin/env python3
"""Decide whether a PR is clean, pending, or not-clean, and say why.

Usage: clean-predicate.py [snapshot.json]    (reads stdin when no path is given)

Clean means the latest Copilot pass covers the head commit, no review thread
is unresolved, and every check is green. /review-pr (planned in #51) gathers
the snapshot with `gh` and asks this script, so the predicate lives in one
place instead of being re-derived in prose on every run.

The snapshot, every field required:

  head_sha            the PR's head commit
  head_committed_at   that commit's committer date, ISO 8601
  reviews             [{author, state, commit_id, submitted_at}]
  threads             [{id, author, resolved, path, line, url}]
  checks              [{name, status, conclusion}]   (check-run shape)
  timeline            [{event, requested_reviewer, actor, created_at}]

Any other field is ignored, `requested_reviewers` included: it is carried in
the fixtures to show the request list is empty while a pass is on its way.

Prints {"state": ..., "reasons": [{"kind": ..., ...}]} and exits 0. Exits 2
when the snapshot cannot be read or lacks a field.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# The timeline names the requested reviewer `Copilot`; REST reviews are
# authored by `copilot-pull-request-reviewer[bot]`; GraphQL thread authors
# drop the `[bot]`. All three are the same reviewer (gr4ce #447).
COPILOT_LOGINS = {"copilot", "copilot-pull-request-reviewer"}


def is_copilot(login):
    login = (login or "").lower()
    if login.endswith("[bot]"):
        login = login[: -len("[bot]")]
    return login in COPILOT_LOGINS


def instant(stamp):
    # String order breaks across `Z`, `+01:00` and fractional seconds, and
    # Python 3.9's fromisoformat does not accept `Z`.
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def copilot_reasons(snap):
    head = snap["head_sha"]
    passes = sorted(
        (r for r in snap["reviews"] if is_copilot(r["author"]) and r["state"] != "PENDING"),
        key=lambda r: instant(r["submitted_at"]),
    )
    latest = passes[-1] if passes else None
    if latest and latest["commit_id"] == head:
        return []

    # Never the reviewer request list: it empties the moment Copilot is
    # requested, so only the timeline shows a pass still on its way.
    #
    # The committer date is when the head was made, not when it was pushed, so
    # a request can postdate it and still be for an older head. A request is
    # only outstanding if no Copilot pass has landed since.
    since = instant(snap["head_committed_at"])
    if latest:
        since = max(since, instant(latest["submitted_at"]))
    outstanding = sorted(
        (
            e["created_at"]
            for e in snap["timeline"]
            if e["event"] == "review_requested"
            and is_copilot(e.get("requested_reviewer"))
            and instant(e["created_at"]) >= since
        ),
        key=instant,
    )
    if outstanding:
        return [{"kind": "copilot-pass-pending", "requested_at": outstanding[-1]}]
    if latest:
        return [{"kind": "stale-copilot-pass", "commit": latest["commit_id"], "head": head}]
    return [{"kind": "no-copilot-pass"}]


def thread_reasons(snap):
    return [
        {
            "kind": "unresolved-copilot-thread" if is_copilot(t["author"]) else "unresolved-human-thread",
            "thread": {k: t.get(k) for k in ("id", "author", "path", "line", "url")},
        }
        for t in snap["threads"]
        if not t["resolved"]
    ]


GREEN_CONCLUSIONS = {"success", "neutral", "skipped"}


def check_reasons(snap):
    reasons = []
    for c in snap["checks"]:
        if (c["status"] or "").lower() != "completed":
            reasons.append({"kind": "pending-check", "check": c["name"], "status": c["status"]})
        elif (c["conclusion"] or "").lower() not in GREEN_CONCLUSIONS:
            reasons.append({"kind": "failing-check", "check": c["name"], "conclusion": c["conclusion"]})
    return reasons


# Every reason is reported, so a caller waiting on a pending pass still sees
# the thread that will hold the PR back once it lands; the state is the worst.
NOT_CLEAN = {
    "stale-copilot-pass",
    "no-copilot-pass",
    "unresolved-copilot-thread",
    "unresolved-human-thread",
    "failing-check",
}


def judge(snap):
    reasons = copilot_reasons(snap) + thread_reasons(snap) + check_reasons(snap)
    state = "clean"
    if any(r["kind"] in NOT_CLEAN for r in reasons):
        state = "not-clean"
    elif reasons:
        state = "pending"
    return {"state": state, "reasons": reasons}


def main(argv):
    try:
        raw = Path(argv[0]).read_text(encoding="utf-8") if argv else sys.stdin.read()
        verdict = judge(json.loads(raw))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # A snapshot missing a field must not read as a verdict, so it gets
        # the same exit as one that is not JSON at all.
        print(f"✘ cannot read snapshot: {exc!r}", file=sys.stderr)
        return 2
    print(json.dumps(verdict, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

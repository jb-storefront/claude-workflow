#!/usr/bin/env python3
"""Cases for merge-gate.py, the check /merge-pr and /merge-stack run before a merge.

The Seam is the script run on a PR snapshot: JSON in, a verdict out. Each case
starts from one clean, freshly reviewed PR and changes the one thing it is
about, so a case that fails names the field that broke it.

The question the gate exists for: an Auto-fix session pushes after /review-pr
reviewed the head, and those commits were never seen by the code reviewer or
the security reviewer. The latest /review-pr summary's `Head:` line is the
record of what was reviewed, so a head it does not name is a head nobody
reviewed.
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
GATE = HERE / "merge-gate.py"

HEAD = "c0ffee2c0ffee2c0ffee2c0ffee2c0ffee2c0ffe"
OLD = "beef001beef001beef001beef001beef001beef0"
SESSION = "session_017XVWEMpGFUjrGnHQddvZt5"


def summary(outcome, head, autofix=SESSION):
    lines = [
        f"## /review-pr — {outcome}",
        "",
        f"Head: `{head[:7]}`",
        "Reviewer: `code-review` — approved, 0 Critical, 0 High",
        "Security: `claude (default)` — 0 High, 0 Medium, 0 Low",
        "Copilot: requested by the repository's ruleset",
    ]
    if autofix:
        lines.append(f"Auto-fix: [{autofix}](https://claude.ai/code/{autofix}) — watching")
    lines += ["", "### Outcome", "Marked ready."]
    return "\n".join(lines)


def comment(body, at, author="jb-storefront"):
    return {"author": author, "body": body, "created_at": at}


BASE = {
    "head_sha": HEAD,
    "head_committed_at": "2026-11-01T10:00:00Z",
    "reviews": [
        {
            "author": "copilot-pull-request-reviewer[bot]",
            "state": "COMMENTED",
            "commit_id": HEAD,
            "submitted_at": "2026-11-01T10:20:00Z",
        }
    ],
    "threads": [],
    "checks": [{"name": "validate", "status": "completed", "conclusion": "success"}],
    "timeline": [
        {
            "event": "review_requested",
            "requested_reviewer": "Copilot",
            "actor": "jb-storefront",
            "created_at": "2026-11-01T10:15:00Z",
        }
    ],
    "comments": [comment(summary("Ready", HEAD), "2026-11-01T10:14:00Z")],
}


def snapshot(**changes):
    snap = copy.deepcopy(BASE)
    snap.update(changes)
    return snap


def gate(snap):
    proc = subprocess.run(
        [sys.executable, str(GATE)], input=json.dumps(snap), capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise AssertionError(f"exit {proc.returncode}: {proc.stderr.strip()[-300:]}")
    return json.loads(proc.stdout)


def is_(actual, expected, what):
    return actual == expected, f"{what} is {actual!r}, expected {expected!r}"


def test_a_ready_summary_on_the_head_is_fresh():
    """a Ready summary naming the head commit reads as reviewed"""
    return is_(gate(snapshot())["reviewed"]["state"], "fresh", "reviewed.state")


def test_a_push_after_the_review_is_stale():
    """a head newer than the latest summary's Head: reads as stale, naming both commits"""
    snap = snapshot(comments=[comment(summary("Ready", OLD), "2026-11-01T09:00:00Z")])
    reviewed = gate(snap)["reviewed"]
    if reviewed["state"] != "stale":
        return False, f"reviewed.state is {reviewed['state']!r}, expected 'stale'"
    if reviewed.get("head") != OLD[:7]:
        return False, f"reviewed.head is {reviewed.get('head')!r}, expected {OLD[:7]!r}"
    return True, ""


def test_no_summary_is_none():
    """a PR /review-pr never summarised reads as none"""
    return is_(gate(snapshot(comments=[]))["reviewed"]["state"], "none", "reviewed.state")


def test_the_latest_summary_decides():
    """a Draft summary after a Ready one on the same head reads as blocked"""
    snap = snapshot(
        comments=[
            comment(summary("Ready", HEAD), "2026-11-01T10:14:00Z"),
            comment(summary("Draft", HEAD), "2026-11-01T10:40:00Z"),
        ]
    )
    return is_(gate(snap)["reviewed"]["state"], "blocked", "reviewed.state")


def test_comments_are_ordered_by_time_not_by_position():
    """an older summary listed last does not override a newer one"""
    snap = snapshot(
        comments=[
            comment(summary("Ready", HEAD), "2026-11-01T10:14:00Z"),
            comment(summary("Ready", OLD), "2026-11-01T09:00:00Z"),
        ]
    )
    return is_(gate(snap)["reviewed"]["state"], "fresh", "reviewed.state")


def test_a_quoted_heading_is_not_a_summary():
    """a comment that quotes the summary heading below its first line is not a summary"""
    quoting = comment("Thanks!\n\n" + summary("Ready", HEAD), "2026-11-01T11:00:00Z", "a-human")
    snap = snapshot(comments=[comment(summary("Ready", OLD), "2026-11-01T09:00:00Z"), quoting])
    return is_(gate(snap)["reviewed"]["state"], "stale", "reviewed.state")


def test_the_autofix_session_is_read_from_the_latest_summary_that_names_one():
    """the Auto-fix session comes from the newest summary carrying an Auto-fix: line"""
    snap = snapshot(
        comments=[
            comment(summary("Ready", OLD), "2026-11-01T09:00:00Z"),
            comment(summary("Ready", HEAD, autofix=None), "2026-11-01T10:14:00Z"),
        ]
    )
    return is_(gate(snap)["autofix"]["session"], SESSION, "autofix.session")


def test_no_autofix_line_is_no_session():
    """with no Auto-fix: line in any summary there is no session to stop"""
    snap = snapshot(comments=[comment(summary("Ready", HEAD, autofix=None), "2026-11-01T10:14:00Z")])
    return is_(gate(snap)["autofix"]["session"], None, "autofix.session")


def test_last_ready_names_the_newest_ready_summary_past_a_later_draft():
    """last_ready is the newest Ready summary's head, even when a Draft summary came after it"""
    snap = snapshot(
        comments=[
            comment(summary("Ready", OLD), "2026-11-01T09:00:00Z"),
            comment(summary("Draft", HEAD), "2026-11-01T10:40:00Z"),
        ]
    )
    return is_(gate(snap)["last_ready"]["head"], OLD[:7], "last_ready.head")


def test_no_ready_summary_is_no_last_ready():
    """with only Draft summaries there is no last_ready head, so the next review is a full one"""
    snap = snapshot(comments=[comment(summary("Draft", OLD), "2026-11-01T09:00:00Z")])
    return is_(gate(snap)["last_ready"]["head"], None, "last_ready.head")


def test_copilot_is_judged_by_the_clean_predicate():
    """an unresolved Copilot thread makes copilot not-clean, with the thread named"""
    thread = {
        "id": "PRRT_copilot1",
        "author": "copilot-pull-request-reviewer",
        "resolved": False,
        "path": "src/x.py",
        "line": 3,
        "url": "https://github.com/o/r/pull/1#discussion_r1",
    }
    copilot = gate(snapshot(threads=[thread]))["copilot"]
    if copilot["state"] != "not-clean":
        return False, f"copilot.state is {copilot['state']!r}, expected 'not-clean'"
    if [r["kind"] for r in copilot["reasons"]] != ["unresolved-copilot-thread"]:
        return False, f"copilot.reasons are {copilot['reasons']}"
    return True, ""


def test_a_clean_reviewed_pr_is_clean():
    """a freshly reviewed PR whose latest Copilot pass is on the head is clean"""
    return is_(gate(snapshot())["copilot"]["state"], "clean", "copilot.state")


def test_a_snapshot_without_comments_exits_2():
    """a snapshot missing the comments field exits 2 rather than reading as unreviewed"""
    snap = snapshot()
    del snap["comments"]
    proc = subprocess.run(
        [sys.executable, str(GATE)], input=json.dumps(snap), capture_output=True, text=True
    )
    return proc.returncode == 2, f"exit {proc.returncode}, expected 2"


def main():
    cases = [v for k, v in globals().items() if k.startswith("test_")]
    failed = 0
    for case in cases:
        try:
            ok, why = case()
        except Exception as exc:  # a crash is a failed case, not a crashed suite
            ok, why = False, f"raised {exc!r}"
        print(f"  {'ok ' if ok else 'BAD'}  {case.__doc__.strip()}" + ("" if ok else f": {why}"))
        failed += not ok
    if failed:
        print(f"✘ {failed} of {len(cases)} merge-gate cases behaved unexpectedly")
        return 1
    print(f"✔ {len(cases)} merge-gate cases behave as specified")
    return 0


if __name__ == "__main__":
    sys.exit(main())

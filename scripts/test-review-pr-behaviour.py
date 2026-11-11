#!/usr/bin/env python3
"""Behavioural cases for /review-pr, observed on a live pull request.

The Seam is a PR's state on GitHub after a run: draft or ready, and the
comments posted on it. Each case reads that state through `gh` and checks it,
so it runs after a real /finalize-pr or /review-pr run on a scratch PR, not in
CI. validate.sh does not call it, because it needs a PR to look at.

    test-review-pr-behaviour.py --repo gr4vy/gr4ce C1 448
    test-review-pr-behaviour.py --repo gr4vy/gr4ce C3 449 --finding src/x.py
    test-review-pr-behaviour.py --repo gr4vy/gr4ce C5 451 --finding docs/specs/9-x.md

The comment shapes it reads are defined in CONTRACTS.md, under the /review-pr
summary comment.
"""

import argparse
import json
import re
import subprocess
import sys

FINALIZE_HEAD = re.compile(r"^## /finalize-pr review — (Blocking|Not blocking)\s*$")
REVIEW_HEAD = re.compile(r"^## /review-pr — (Ready|Draft)\s*$")


def gh(*args):
    out = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def paged(path):
    # --paginate concatenates one JSON array per page; --slurp wraps them.
    pages = gh("api", "--paginate", "--slurp", path)
    return [item for page in pages for item in page]


class PR:
    def __init__(self, repo, number):
        self.repo, self.number = repo, number
        pull = gh("api", f"repos/{repo}/pulls/{number}")
        self.draft = pull["draft"]
        self.head = pull["head"]["sha"]
        self.finalize_reviews = [
            r for r in paged(f"repos/{repo}/pulls/{number}/reviews")
            if FINALIZE_HEAD.match(first_line(r["body"]))
        ]
        self.summaries = [
            c for c in paged(f"repos/{repo}/issues/{number}/comments")
            if REVIEW_HEAD.match(first_line(c["body"]))
        ]


def first_line(body):
    return (body or "").lstrip().split("\n", 1)[0].strip()


def field(body, name):
    m = re.search(rf"^{name}:\s*`?([^`\n]+?)`?(?:\s+—.*)?$", body, re.M)
    return m.group(1).strip() if m else None


def section(body, heading):
    """The lines under a `### {heading}` heading, up to the next heading."""
    m = re.search(rf"^### {re.escape(heading)}[^\n]*\n(.*?)(?=^#{{2,3}} |^<details>|\Z)", body, re.M | re.S)
    return m.group(1).strip() if m else None


def verdict_of(review):
    return FINALIZE_HEAD.match(first_line(review["body"])).group(1)


def check_54_c1(pr, _):
    """#54 C1 a passing PR: no code-reviewer section, /review-pr summary names the reviewer, PR ready."""
    if not pr.finalize_reviews:
        return False, "no /finalize-pr review on the PR"
    fin = pr.finalize_reviews[-1]
    if verdict_of(fin) != "Not blocking":
        return False, f"latest /finalize-pr review is {verdict_of(fin)}"
    if re.search(r"^###\s+Code-reviewer", fin["body"], re.M | re.I):
        return False, "the /finalize-pr review still carries a code-reviewer section"
    if re.search(r"^###\s+Spec drift", fin["body"], re.M | re.I):
        return False, "the /finalize-pr review still carries a spec-drift section"
    after = [c for c in pr.summaries if c["created_at"] >= fin["submitted_at"]]
    if not after:
        return False, "no /review-pr summary posted after the /finalize-pr review"
    summary = after[-1]["body"]
    reviewed = field(summary, "Head")
    if not reviewed or not pr.head.startswith(reviewed):
        return False, f"the /review-pr summary reviewed {reviewed}, head is {pr.head}"
    reviewer = field(summary, "Reviewer")
    if not reviewer:
        return False, "the /review-pr summary names no reviewer"
    if REVIEW_HEAD.match(first_line(summary)).group(1) != "Ready":
        return False, "the /review-pr summary does not report Ready"
    if pr.draft:
        return False, "the PR is still a draft"
    return True, f"reviewer {reviewer}, PR ready"


def check_54_c2(pr, _):
    """#54 C2 a Blocking /finalize-pr verdict: /review-pr not invoked, PR stays a draft."""
    if not pr.finalize_reviews:
        return False, "no /finalize-pr review on the PR"
    fin = pr.finalize_reviews[-1]
    if verdict_of(fin) != "Blocking":
        return False, f"latest /finalize-pr review is {verdict_of(fin)}"
    later = [c for c in pr.summaries if c["created_at"] >= fin["submitted_at"]]
    if later:
        return False, "a /review-pr summary was posted after the Blocking review"
    if not pr.draft:
        return False, "the PR was marked ready"
    return True, "no /review-pr summary, PR is a draft"


def check_54_c3(pr, finding):
    """#54 C3 a planted defect the reviewer blocks on: PR stays a draft, summary names the finding."""
    if not pr.summaries:
        return False, "no /review-pr summary on the PR"
    summary = pr.summaries[-1]["body"]
    reviewed = field(summary, "Head")
    if not reviewed or not pr.head.startswith(reviewed):
        return False, f"the latest /review-pr summary reviewed {reviewed}, head is {pr.head}"
    if REVIEW_HEAD.match(first_line(summary)).group(1) != "Draft":
        return False, "the latest /review-pr summary does not report Draft"
    blocking = section(summary, "Blocking findings")
    if not blocking or re.fullmatch(r"(?:-\s*)?None\.", blocking):
        return False, "the summary lists no blocking finding"
    if finding and finding not in blocking:
        return False, f"no blocking finding names {finding}"
    if not pr.draft:
        return False, "the PR was marked ready"
    return True, "PR is a draft, blocking finding named"


def check_54_c4(pr, _):
    """#54 C4 a ready PR with a new commit: /review-pr on its own reviews again and posts a new summary."""
    heads = [field(c["body"], "Head") for c in pr.summaries]
    outcomes = [REVIEW_HEAD.match(first_line(c["body"])).group(1) for c in pr.summaries]
    if len(heads) < 2:
        return False, f"{len(heads)} /review-pr summaries, expected at least two"
    if not heads[-1] or not pr.head.startswith(heads[-1]):
        return False, f"latest summary reviewed {heads[-1]}, head is {pr.head}"
    # The Given: an earlier run marked the PR ready on a commit that is no longer the head.
    if not any(o == "Ready" and h and not pr.head.startswith(h) for h, o in zip(heads, outcomes)):
        return False, "no earlier summary marked the PR ready on a different commit"
    on_head = [r for r in pr.finalize_reviews if r.get("commit_id") == pr.head]
    if on_head:
        return False, "/finalize-pr also ran on the new head, so /review-pr did not run on its own"
    # Whatever the new review decided, the PR's state must agree with it.
    if pr.draft != (outcomes[-1] == "Draft"):
        return False, f"latest summary says {outcomes[-1]} but the PR's draft is {pr.draft}"
    return True, f"{len(heads)} summaries, latest {outcomes[-1]} on {pr.head[:7]}"


def check_54_c5(pr, spec):
    """#54 C5 a PR touching an implemented Spec's area: spec drift surfaced in the /review-pr summary."""
    if not pr.summaries:
        return False, "no /review-pr summary on the PR"
    drift = section(pr.summaries[-1]["body"], "Spec drift (advisory)")
    if drift is None:
        return False, "the summary has no spec drift section"
    if not spec:
        return False, "pass --finding with the Spec file the drift should name"
    if spec not in drift:
        return False, f"spec drift does not name {spec}: {drift!r}"
    return True, f"drift names {spec}"


CHECKS = {f"C{n}": globals()[f"check_54_c{n}"] for n in range(1, 6)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("criterion", choices=sorted(CHECKS))
    p.add_argument("pr", type=int)
    p.add_argument("--finding", help="the path the blocking finding or the drift must name")
    a = p.parse_args()
    check = CHECKS[a.criterion]
    ok, why = check(PR(a.repo, a.pr), a.finding)
    print(f"  {'ok ' if ok else 'BAD'}  {check.__doc__}\n       {a.repo}#{a.pr}: {why}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Static cases for the /finalize-pr to /review-pr hand-off.

Two properties of the shipped files, checkable without a PR: /finalize-pr has
no step left that marks a PR ready, because only /review-pr may do that, and
/review-pr is a skill the plugin can load.
"""

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FINALIZE = ROOT / "skills" / "finalize-pr" / "SKILL.md"
REVIEW = ROOT / "skills" / "review-pr" / "SKILL.md"

_spec = importlib.util.spec_from_file_location(
    "check_skill_frontmatter", Path(__file__).with_name("check-skill-frontmatter.py")
)
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)


def test_54_c6_finalize_pr_has_no_step_that_marks_the_pr_ready():
    """#54 C6"""
    text = FINALIZE.read_text(encoding="utf-8")
    hits = [
        f"line {n}: {line.strip()}"
        for n, line in enumerate(text.splitlines(), start=1)
        if re.search(r"\bgh pr ready\b", line)
    ]
    return not hits, "; ".join(hits)


def test_54_c7_review_pr_skill_passes_the_frontmatter_check():
    """#54 C7"""
    if not REVIEW.is_file():
        return False, f"{REVIEW.relative_to(ROOT)} does not exist"
    problems = checker.check(REVIEW)
    return not problems, "; ".join(problems)


def test_no_skill_posts_a_body_of_at_dash():
    """gh body from stdin"""
    # `gh pr comment --body @-` posts the two characters `@-` and returns success; only
    # `--body-file -` reads stdin. Seen on gr4vy/gr4ce#453, where the review summary was lost.
    hits = [
        f"{md.relative_to(ROOT)}:{n}"
        for md in sorted((ROOT / "skills").rglob("*.md"))
        for n, line in enumerate(md.read_text(encoding="utf-8").splitlines(), start=1)
        if "--body @-" in line
    ]
    return not hits, "; ".join(hits)


def main():
    cases = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for case in cases:
        try:
            ok, why = case()
        except Exception as exc:
            ok, why = False, f"raised {exc!r}"
        label = case.__doc__.strip()
        if ok:
            print(f"  ok   {label} {case.__name__}")
        else:
            print(f"  BAD  {label} {case.__name__}: {why}")
            failed += 1
    if failed:
        print(f"✘ {failed} of {len(cases)} hand-off cases failed")
        return 1
    print(f"✔ {len(cases)} hand-off cases pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

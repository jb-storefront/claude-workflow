#!/usr/bin/env python3
"""Cases for the shared chain-walking reference.

/critique-spec walks the Critics chain and /review-pr will walk the Security
reviewers chain. Both cite one reference for the rules, so the two cannot
drift. What drifts in practice is a copy: a skill that still carries its own
availability checks next to the citation is a skill whose next edit lands in
one place and not the other. These cases hold the rules to the reference and
the citation to a file that exists.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "references" / "chain-walking.md"
CRITIQUE = ROOT / "skills" / "critique-spec" / "SKILL.md"

# The availability checks are commands and agent types, not prose, so their
# presence is checkable without asserting on wording.
AVAILABILITY = [
    "command -v codex",
    "command -v agy",
    "agy models",
    "codex:codex-rescue",
    "antigravity:agy-rescue",
]

LINK = re.compile(r"\]\(([^)\s]*chain-walking\.md)\)")


def read(path):
    return path.read_text(encoding="utf-8") if path.is_file() else None


def test_55_c1_rules_live_in_the_reference_not_in_critique_spec():
    """#55 C1 every chain-walking rule is stated in the reference and cited, not restated, by /critique-spec"""
    problems = []
    ref = read(REFERENCE)
    skill = read(CRITIQUE)
    if ref is None:
        return [f"{REFERENCE.relative_to(ROOT)} does not exist"]
    for needle in AVAILABILITY:
        if needle not in ref:
            problems.append(f"reference does not state the availability check `{needle}`")
    for needle in ("command -v codex", "command -v agy", "agy models"):
        if needle in skill:
            problems.append(f"/critique-spec still restates the availability check `{needle}`")
    if not LINK.search(skill):
        problems.append("/critique-spec does not cite the reference")
    return problems


def test_55_c3_citation_resolves_on_disk():
    """#55 C3 /critique-spec's citation of the reference resolves to a file the references check finds"""
    skill = read(CRITIQUE)
    links = LINK.findall(skill)
    if not links:
        return ["/critique-spec has no markdown link to chain-walking.md"]
    return [
        f"/critique-spec links to {target}, which is not on disk"
        for target in links
        if not (CRITIQUE.parent / target).resolve().is_file()
    ]


TESTS = [test_55_c1_rules_live_in_the_reference_not_in_critique_spec, test_55_c3_citation_resolves_on_disk]


def main():
    bad = 0
    for test in TESTS:
        problems = test()
        name = test.__doc__.split("\n")[0]
        if problems:
            bad += 1
            print(f"  BAD  {name}")
            for p in problems:
                print(f"       {p}")
        else:
            print(f"  ok   {name}")
    if bad:
        print(f"✘ {bad} of {len(TESTS)} chain-reference cases failed")
        return 1
    print(f"✔ {len(TESTS)} chain-reference cases hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())

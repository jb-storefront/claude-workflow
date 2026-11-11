#!/usr/bin/env python3
"""Cases for the Security reviewers list /review-pr walks.

The Seam is security-reviewers.py run as /review-pr runs it: a workflow file
in, the chain (or a stop) out. The skill dispatches whatever the script prints
and stops wherever it exits 1, so the list's rules hold here or nowhere.

Two cases read the shipped files instead, because the contract says who reads
the list and that is a property of the skills, not of a run.
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "security-reviewers.py"
REVIEW = ROOT / "skills" / "review-pr" / "SKILL.md"

CRITICS = "**Critics:**\n1. google, gemini-3.8-flash-high\n2. claude, claude-opus-5\n"


def run(content):
    """Run the script on a workflow file holding `content`, or on no file when it is None."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "workflow.md"
        if content is not None:
            path.write_text(content, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True
        )
    entries = [tuple(line.split("\t")) for line in proc.stdout.splitlines()]
    return proc.returncode, entries, proc.stderr


def test_a_list_ending_in_another_vendor_stops():
    """a list whose last entry is not claude stops, and offers no entry to dispatch"""
    code, entries, err = run(
        "**Security reviewers:**\n1. claude, claude-opus-5\n2. codex, default\n"
    )
    if code != 1:
        return False, f"exit {code}, expected 1"
    if entries:
        return False, f"printed {entries} alongside the stop"
    if "codex" not in err:
        return False, f"the stop does not name the last entry: {err!r}"
    return True, "stopped"


def test_an_unknown_vendor_stops():
    """an entry naming a vendor with no dispatch path stops"""
    code, entries, err = run(
        "**Security reviewers:**\n1. mistral, large\n2. claude, claude-opus-5\n"
    )
    if code != 1 or entries:
        return False, f"exit {code}, printed {entries}"
    return ("mistral" in err), err.strip()


def test_an_entry_without_a_model_stops():
    """an entry that is not `{vendor}, {model}` stops"""
    code, entries, _ = run("**Security reviewers:**\n1. codex\n2. claude, claude-opus-5\n")
    return code == 1 and not entries, f"exit {code}, printed {entries}"


def test_an_empty_list_stops():
    """a heading with no entries has no floor and stops"""
    code, entries, _ = run("**Security reviewers:**\n\n**Specs:** on\n")
    return code == 1 and not entries, f"exit {code}, printed {entries}"


def test_a_missing_list_runs_the_floor_and_says_so_once():
    """a file with no Security reviewers list runs the claude floor and says once that /setup-workflow adds it"""
    code, entries, err = run("**Specs:** on\n\n" + CRITICS)
    if code != 0:
        return False, f"exit {code}: {err!r}"
    if entries != [("claude", "default")]:
        return False, f"chain is {entries}, expected the claude floor alone"
    if err.count("/setup-workflow") != 1:
        return False, f"/setup-workflow named {err.count('/setup-workflow')} times: {err!r}"
    return True, "floor alone, one note"


def test_a_missing_file_runs_the_floor_and_says_so_once():
    """no workflow file at all runs the claude floor and says so once"""
    code, entries, err = run(None)
    ok = code == 0 and entries == [("claude", "default")] and err.count("/setup-workflow") == 1
    return ok, f"exit {code}, chain {entries}, stderr {err!r}"


def test_the_critics_list_is_never_borrowed():
    """a missing Security reviewers list does not fall back to the Critics list"""
    _, entries, _ = run(CRITICS)
    return ("google", "gemini-3.8-flash-high") not in entries, f"chain is {entries}"


def test_a_valid_list_is_walked_in_order():
    """a valid list prints every entry, in the file's order, untouched by the Critics list"""
    code, entries, err = run(
        CRITICS
        + "\n**Security reviewers:**\n1. google, gemini-3.8-flash-high\n"
        "2. codex, default\n3. claude, claude-opus-5\n"
    )
    want = [("google", "gemini-3.8-flash-high"), ("codex", "default"), ("claude", "claude-opus-5")]
    if code != 0 or err:
        return False, f"exit {code}, stderr {err!r}"
    return entries == want, f"chain is {entries}"


def test_review_pr_reads_the_list_through_the_script():
    """/review-pr runs the script, cites the chain-walking reference, and does not restate the availability checks"""
    text = REVIEW.read_text(encoding="utf-8")
    problems = []
    if "security-reviewers.py" not in text:
        problems.append("does not run security-reviewers.py")
    links = re.findall(r"\]\(([^)\s]*chain-walking\.md)\)", text)
    if not links:
        problems.append("does not cite references/chain-walking.md")
    for target in links:
        if not (REVIEW.parent / target).resolve().is_file():
            problems.append(f"links to {target}, which is not on disk")
    for needle in ("command -v codex", "command -v agy"):
        if needle in text:
            problems.append(f"restates the availability check `{needle}`")
    return not problems, "; ".join(problems)


def test_no_other_skill_reads_the_list():
    """no skill but /review-pr walks the Security reviewers list (/setup-workflow only writes it)"""
    readers = []
    for md in sorted((ROOT / "skills").glob("*/SKILL.md")):
        skill = md.parent.name
        if skill in ("review-pr", "setup-workflow"):
            continue
        text = md.read_text(encoding="utf-8")
        if "Security reviewers" in text or "security-reviewers.py" in text:
            readers.append(skill)
    return not readers, f"also read by: {', '.join(readers)}"


def main():
    cases = [v for k, v in globals().items() if k.startswith("test_")]
    failed = 0
    for case in cases:
        try:
            ok, why = case()
        except Exception as exc:
            ok, why = False, f"raised {exc!r}"
        if ok:
            print(f"  ok   {case.__doc__}")
        else:
            print(f"  BAD  {case.__doc__}: {why}")
            failed += 1
    if failed:
        print(f"✘ {failed} of {len(cases)} Security reviewers cases failed")
        return 1
    print(f"✔ {len(cases)} Security reviewers cases pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

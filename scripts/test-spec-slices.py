#!/usr/bin/env python3
"""Cases for spec-slices.py, the one reader of a Spec's roster of Slices.

The Seam is the script run as the skills run it, against a fake `gh` on PATH
that answers from a dict the case builds. The fake behaves as GitHub does in
the one way that matters most here: the sub-issues endpoint returns its first
page only, unless the caller asks gh to paginate.

The last case reads the shipped skills instead, because which skills read the
roster through the script is a property of the files, not of a run.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "spec-slices.py"

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
world = json.loads(open(os.environ["FAKE_GH_WORLD"]).read())
args = sys.argv[1:]
if world.get("fail"):
    print("gh: Could not resolve to an issue", file=sys.stderr)
    sys.exit(1)
if args[:2] == ["issue", "view"]:
    print(json.dumps({"body": world["spec_body"]}))
elif args[:1] == ["api"] and any("/sub_issues" in a for a in args):
    pages = world["sub_issue_pages"]
    if "--paginate" not in args:
        pages = pages[:1]
    if "--slurp" in args:
        print(json.dumps(pages))
    else:
        print("".join(json.dumps(p) for p in pages))
elif args[:2] == ["issue", "list"]:
    print(json.dumps(world.get("search", [])))
else:
    print(f"fake gh: unexpected call {args}", file=sys.stderr)
    sys.exit(3)
'''


def issue(number, state="open", parent=60, title=None, assignees=()):
    body = f"## Parent\n\n#{parent}\n\n## What to build\n\nx\n" if parent else "## Related\n\n#60\n"
    return {
        "number": number,
        "title": title or f"Slice {number}",
        "state": state,
        "assignees": [{"login": a} for a in assignees],
        "body": body,
    }


def search_hit(number, body, state="OPEN"):
    return {"number": number, "title": f"Issue {number}", "state": state, "body": body}


SPEC_BODY = "**Status:** in-progress\n\n## Criteria\n\n### C1\nGiven a\nWhen b\nThen c\n"


def run(world, spec="60"):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        gh = tmp / "bin" / "gh"
        gh.parent.mkdir()
        gh.write_text(FAKE_GH, encoding="utf-8")
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        (tmp / "world.json").write_text(json.dumps(world), encoding="utf-8")
        env = dict(os.environ, FAKE_GH_WORLD=str(tmp / "world.json"))
        env["PATH"] = f"{gh.parent}{os.pathsep}{env['PATH']}"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), spec], capture_output=True, text=True, env=env
        )
    out = json.loads(proc.stdout) if proc.returncode == 0 and proc.stdout.strip() else None
    return proc.returncode, out, proc.stdout, proc.stderr


def numbers(out):
    return [s["number"] for s in out["slices"]]


def test_the_roster_is_every_sub_issue_past_the_first_page_in_github_order():
    """the roster is every sub-issue, open and closed, past GitHub's first page, in GitHub's order"""
    world = {
        "spec_body": SPEC_BODY,
        "sub_issue_pages": [[issue(63), issue(61, "closed")], [issue(62)]],
    }
    code, out, _, err = run(world)
    if code != 0:
        return False, f"exit {code}: {err!r}"
    return numbers(out) == [63, 61, 62], f"roster is {numbers(out)}"


def test_state_and_assignees_come_from_the_tracker():
    """each Slice carries the tracker's state as OPEN or CLOSED, and its assignees' logins"""
    world = {
        "spec_body": SPEC_BODY,
        "sub_issue_pages": [[issue(61, "closed"), issue(62, assignees=["ada"])]],
    }
    code, out, _, err = run(world)
    if code != 0:
        return False, f"exit {code}: {err!r}"
    got = [(s["number"], s["state"], s["assignees"]) for s in out["slices"]]
    return got == [(61, "CLOSED", []), (62, "OPEN", ["ada"])], f"got {got}"


def test_a_lone_slice_linked_under_the_spec_owns_none_of_its_criteria():
    """a sub-issue whose ## Parent does not name the Spec is on the roster with parent false"""
    url_parent = issue(63)
    url_parent["body"] = "## Parent\n\nhttps://github.com/o/r/issues/60\n"
    world = {
        "spec_body": SPEC_BODY,
        "sub_issue_pages": [[issue(61), issue(62, parent=None), url_parent]],
    }
    code, out, _, err = run(world)
    if code != 0:
        return False, f"exit {code}: {err!r}"
    got = {s["number"]: s["parent"] for s in out["slices"]}
    return got == {61: True, 62: False, 63: True}, f"parent flags {got}"


def test_an_empty_roster_is_an_empty_list():
    """a Spec with no sub-issues and no stale list prints an empty roster and exits 0"""
    code, out, _, err = run({"spec_body": SPEC_BODY, "sub_issue_pages": [[]]})
    return code == 0 and out["slices"] == [], f"exit {code}, out {out}, stderr {err!r}"


def test_a_task_list_entry_that_is_not_a_sub_issue_stops():
    """a ## Slices entry that is not a sub-issue stops, prints no roster, and names the fix"""
    world = {
        "spec_body": SPEC_BODY + "\n## Slices\n\n- [x] #61\n- [ ] #62\n",
        "sub_issue_pages": [[]],
    }
    code, _, stdout, err = run(world)
    if code != 1:
        return False, f"exit {code}, expected 1"
    if stdout.strip():
        return False, f"printed a roster alongside the stop: {stdout!r}"
    problems = [f"#{n} not named" for n in (61, 62) if f"#{n}" not in err]
    if "sub_issues" not in err:
        problems.append("no command that links it")
    return not problems, "; ".join(problems) or err


def test_a_task_list_that_agrees_with_the_sub_issues_is_ignored_with_a_note():
    """a ## Slices list whose every entry is a sub-issue is not read, and says once that it can be deleted"""
    world = {
        "spec_body": SPEC_BODY + "\n## Slices\n\n- [ ] #61\n",
        "sub_issue_pages": [[issue(61), issue(62)]],
    }
    code, out, _, err = run(world)
    if code != 0:
        return False, f"exit {code}: {err!r}"
    if numbers(out) != [61, 62]:
        return False, f"roster is {numbers(out)}, expected the sub-issues"
    return err.count("can be deleted") == 1, f"stderr {err!r}"


def test_an_empty_slices_heading_is_silent():
    """an empty ## Slices heading is neither read nor noted"""
    world = {"spec_body": SPEC_BODY + "\n## Slices\n\n", "sub_issue_pages": [[issue(61)]]}
    code, out, _, err = run(world)
    return code == 0 and numbers(out) == [61] and not err, f"exit {code}, stderr {err!r}"


def test_an_issue_naming_the_spec_as_parent_but_not_linked_stops():
    """an issue whose ## Parent names the Spec but is not a sub-issue stops, and mentions elsewhere do not"""
    world = {
        "spec_body": SPEC_BODY,
        "sub_issue_pages": [[issue(61)]],
        "search": [
            search_hit(61, "## Parent\n\n#60\n"),
            search_hit(64, "## Parent\n\n#60\n\n## What to build\n\ny\n"),
            search_hit(65, "## Related\n\n#60\n"),
            search_hit(66, "## Parent\n\n#600\n"),
            search_hit(60, SPEC_BODY),
        ],
    }
    code, _, stdout, err = run(world)
    if code != 1 or stdout.strip():
        return False, f"exit {code}, stdout {stdout!r}"
    problems = []
    if "#64" not in err:
        problems.append("#64 not named")
    for n in (61, 65, 66):
        if f"#{n}" in err:
            problems.append(f"#{n} named, but it is linked or does not name #60 as its Parent")
    return not problems, "; ".join(problems) or err


def test_every_problem_is_reported_in_one_run():
    """a stale list entry and an unlinked Parent are both named by the same run"""
    world = {
        "spec_body": SPEC_BODY + "\n## Slices\n\n- [ ] #62\n",
        "sub_issue_pages": [[issue(61)]],
        "search": [search_hit(64, "## Parent\n\n#60\n")],
    }
    code, _, _, err = run(world)
    return code == 1 and "#62" in err and "#64" in err, f"exit {code}, stderr {err!r}"


def test_a_gh_failure_is_not_a_roster():
    """gh failing exits 2 and prints no roster, so no reader mistakes it for a Spec with no Slices"""
    code, _, stdout, _ = run({"fail": True})
    return code == 2 and not stdout.strip(), f"exit {code}, stdout {stdout!r}"


READERS = {
    "skills/dispatch-slices/SKILL.md",
    "references/spec-close-out.md",
}


def test_every_roster_reader_goes_through_the_script():
    """dispatch-slices and spec-close-out each run spec-slices.py"""
    missing = [p for p in sorted(READERS) if "spec-slices.py" not in (ROOT / p).read_text()]
    return not missing, f"not run by: {', '.join(missing)}"


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
        print(f"✘ {failed} of {len(cases)} spec-slices cases failed")
        return 1
    print(f"✔ {len(cases)} spec-slices cases pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

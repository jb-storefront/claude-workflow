#!/usr/bin/env python3
"""Cases for spec.py, the one reader and writer of a Spec issue body.

The Seam is the script run as the skills run it, against a fake `gh` on PATH
that answers from, and writes back to, a JSON world the case builds. An edit
the script makes is therefore visible to the read-back it makes after it, the
same as on GitHub.

The last cases read the shipped skills instead, because which skills go
through the script, and that none still reads a Spec file, are properties of
the files, not of a run.
"""

import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "spec.py"

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
path = os.environ["FAKE_GH_WORLD"]
world = json.loads(open(path).read())
args = sys.argv[1:]
world.setdefault("calls", []).append(args)
def save():
    open(path, "w").write(json.dumps(world))
if world.get("fail"):
    save()
    print("gh: Could not resolve to an issue", file=sys.stderr)
    sys.exit(1)
repo = args[args.index("--repo") + 1] if "--repo" in args else "here"
if args[:2] == ["issue", "view"]:
    issue = world["issues"].get(f"{repo}#{args[2]}")
    save()
    if issue is None:
        print("gh: Could not resolve to an issue", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(issue))
elif args[:2] == ["issue", "edit"]:
    key = f"{repo}#{args[2]}"
    body = sys.stdin.read()
    if not world.get("drop_edits"):
        world["issues"][key]["body"] = body
    world.setdefault("edits", []).append(key)
    save()
elif args[:1] == ["api"] and "/contents/" in args[1]:
    owner_repo, file_path = args[1].split("/contents/", 1)
    owner_repo = owner_repo.replace("repos/", "", 1)
    key = f"{'here' if owner_repo == '{owner}/{repo}' else owner_repo}:{file_path}"
    content = world.get("files", {}).get(key)
    save()
    if content is None:
        print("gh: Not Found (HTTP 404)", file=sys.stderr)
        sys.exit(1)
    sys.stdout.write(content)
elif args[:2] == ["issue", "list"]:
    save()
    print(json.dumps([dict(i, number=int(k.split("#")[1])) for k, i in world["issues"].items()
                      if k.startswith(repo + "#")]))
else:
    save()
    print(f"fake gh: unexpected call {args}", file=sys.stderr)
    sys.exit(3)
'''

SPEC = """**Status:** {status}

## Problem Statement

Buyers earn nothing.

## User Stories

1. As a buyer I earn points.

## Criteria

### C1
Given a cart holding one earn-eligible line
When the buyer submits the order
Then the ledger holds one credit row

### C2 [manual]
Given the balance is 240 points
When the buyer opens the cart page
Then the summary reads "240 points"

### C4 [command]
WHEN the migration is dry run THE SYSTEM SHALL accept it
Command: `uv run python scripts/dry_run.py --target sandbox`

## Verification

Command: `pnpm test:e2e loyalty`
"""


def issue(status="draft", title="Loyalty earn and burn", state="OPEN", body=None):
    return {"title": title, "state": state, "body": body if body is not None else SPEC.format(status=status)}


def run(world, *args):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        gh = tmp / "bin" / "gh"
        gh.parent.mkdir()
        gh.write_text(FAKE_GH, encoding="utf-8")
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        world_path = tmp / "world.json"
        world_path.write_text(json.dumps(world), encoding="utf-8")
        env = dict(os.environ, FAKE_GH_WORLD=str(world_path))
        env["PATH"] = f"{gh.parent}{os.pathsep}{env['PATH']}"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env
        )
        after = json.loads(world_path.read_text(encoding="utf-8"))
    out = None
    if proc.returncode == 0 and proc.stdout.strip().startswith(("{", "[")):
        out = json.loads(proc.stdout)
    return proc.returncode, out, proc.stdout, proc.stderr, after


def body_of(after, key="here#60"):
    return after["issues"][key]["body"]


# read


def test_read_returns_status_criteria_and_verification():
    """read gives the Status, every Criterion with its tag and command, and the Verification"""
    code, out, _, err, _ = run({"issues": {"here#60": issue()}}, "read", "60")
    if code != 0:
        return False, f"exit {code}: {err!r}"
    got = (
        out["status"],
        [(c["id"], c["tag"], c["command"]) for c in out["criteria"]],
        out["verification"],
    )
    want = (
        "draft",
        [
            ("C1", None, None),
            ("C2", "manual", None),
            ("C4", "command", "uv run python scripts/dry_run.py --target sandbox"),
        ],
        {"form": "command", "command": "pnpm test:e2e loyalty"},
    )
    return got == want, f"got {got}"


def test_read_keeps_each_criterion_text_whole():
    """a Criterion's text is its Given/When/Then lines, without the id heading"""
    code, out, _, err, _ = run({"issues": {"here#60": issue()}}, "read", "60")
    if code != 0:
        return False, f"exit {code}: {err!r}"
    text = out["criteria"][0]["text"]
    want = (
        "Given a cart holding one earn-eligible line\n"
        "When the buyer submits the order\n"
        "Then the ledger holds one credit row"
    )
    return text == want, f"C1 text is {text!r}"


def test_read_honours_repo():
    """--repo reads the Spec from that repository, not the current one"""
    world = {"issues": {"here#21": issue(status="draft"), "gr4vy/gr4ce#21": issue(status="in-progress")}}
    code, out, _, err, _ = run(world, "read", "21", "--repo", "gr4vy/gr4ce")
    if code != 0:
        return False, f"exit {code}: {err!r}"
    return out["status"] == "in-progress", f"status {out['status']}"


def test_read_gives_a_walkthrough_its_steps():
    """a Walkthrough Verification comes back with its steps"""
    body = SPEC.format(status="draft").replace(
        "Command: `pnpm test:e2e loyalty`", "Walkthrough:\n1. Open the cart.\n2. Submit."
    )
    code, out, _, err, _ = run({"issues": {"here#60": issue(body=body)}}, "read", "60")
    if code != 0:
        return False, f"exit {code}: {err!r}"
    v = out["verification"]
    return v == {"form": "walkthrough", "steps": "1. Open the cart.\n2. Submit."}, f"got {v}"


def test_read_gives_no_verification_when_both_forms_are_present():
    """a Verification carrying both forms is not a Verification"""
    body = SPEC.format(status="draft").replace(
        "Command: `pnpm test:e2e loyalty`", "Command: `x`\nWalkthrough:\n1. y"
    )
    code, out, _, err, _ = run({"issues": {"here#60": issue(body=body)}}, "read", "60")
    if code != 0:
        return False, f"exit {code}: {err!r}"
    return out["verification"] is None, f"got {out['verification']}"


def test_read_refuses_an_issue_that_is_not_a_spec():
    """an issue with no Status line exits 1, so no gate reads a Status that is not there"""
    code, out, _, err, _ = run({"issues": {"here#60": issue(body="## Problem Statement\n\nx\n")}}, "read", "60")
    return code == 1 and out is None and "Status" in err, f"exit {code}, stderr {err!r}"


def test_a_status_line_below_the_header_is_not_the_status():
    """a Status line quoted in the prose does not make an issue a Spec"""
    body = "## Further Notes\n\n**Status:** implemented\n"
    code, _, _, err, _ = run({"issues": {"here#60": issue(body=body)}}, "read", "60")
    return code == 1, f"exit {code}, stderr {err!r}"


def test_read_names_a_spec_anchored_to_a_file_under_the_old_contract():
    """a body that is only a pointer to docs/specs exits 1 and names the migration as the fix"""
    body = "Spec: `docs/specs/60-loyalty.md` on the default branch\n\n## Criteria\n\n- C1 a\n"
    code, _, _, err, _ = run({"issues": {"here#60": issue(body=body)}}, "read", "60")
    return code == 1 and "migrate" in err and "docs/specs/60-loyalty.md" in err, f"exit {code}, {err!r}"


def test_read_refuses_a_duplicate_or_mistagged_criterion():
    """a repeated id or an unknown tag exits 1 rather than guessing which Criterion is meant"""
    dup = SPEC.format(status="draft").replace("### C4 [command]", "### C1 [command]")
    bad = SPEC.format(status="draft").replace("### C2 [manual]", "### C2 [later]")
    a = run({"issues": {"here#60": issue(body=dup)}}, "read", "60")
    b = run({"issues": {"here#60": issue(body=bad)}}, "read", "60")
    return (a[0], b[0]) == (1, 1), f"duplicate exit {a[0]} {a[3]!r}, bad tag exit {b[0]} {b[3]!r}"


def test_gh_failing_exits_2():
    """gh failing exits 2 with nothing on stdout, so no reader mistakes it for a Spec"""
    code, _, stdout, _, _ = run({"fail": True, "issues": {}}, "read", "60")
    return code == 2 and not stdout.strip(), f"exit {code}, stdout {stdout!r}"


# set-status


def test_set_status_changes_only_the_status_line():
    """set-status rewrites the Status line and leaves every other byte of the body alone"""
    code, _, _, err, after = run({"issues": {"here#60": issue("critiqued")}}, "set-status", "60", "in-progress")
    if code != 0:
        return False, f"exit {code}: {err!r}"
    want = SPEC.format(status="in-progress")
    return body_of(after) == want, f"body became {body_of(after)!r}"


def test_set_status_walks_only_forward():
    """each owned transition is allowed, and walking a Status backwards is refused untouched"""
    allowed = [("draft", "critiqued"), ("critiqued", "in-progress"), ("in-progress", "implemented"),
               ("critiqued", "implemented"), ("critiqued", "draft"), ("implemented", "superseded")]
    refused = [("draft", "in-progress"), ("in-progress", "critiqued"), ("implemented", "in-progress"),
               ("superseded", "implemented"), ("in-progress", "draft")]
    wrong = []
    for frm, to in allowed:
        code, _, _, err, after = run({"issues": {"here#60": issue(frm)}}, "set-status", "60", to)
        if code != 0 or f"**Status:** {to}" not in body_of(after):
            wrong.append(f"{frm}→{to} refused: {err.strip()}")
    for frm, to in refused:
        code, _, _, _, after = run({"issues": {"here#60": issue(frm)}}, "set-status", "60", to)
        if code != 1 or after.get("edits"):
            wrong.append(f"{frm}→{to} allowed")
    return not wrong, "; ".join(wrong)


def test_set_status_to_the_current_status_writes_nothing():
    """setting the Status it already has exits 0 and makes no edit"""
    code, _, out, err, after = run({"issues": {"here#60": issue("in-progress")}}, "set-status", "60", "in-progress")
    return code == 0 and not after.get("edits") and "unchanged" in out, f"exit {code}, edits {after.get('edits')}"


def test_set_status_reads_back_what_it_wrote():
    """an edit GitHub reports as done but did not keep exits 1"""
    world = {"drop_edits": True, "issues": {"here#60": issue("critiqued")}}
    code, _, _, err, _ = run(world, "set-status", "60", "in-progress")
    return code == 1 and "read back" in err, f"exit {code}, stderr {err!r}"


def test_set_status_honours_repo():
    """--repo writes the Status in that repository's Spec issue"""
    world = {"issues": {"here#21": issue("critiqued"), "gr4vy/gr4ce#21": issue("critiqued")}}
    code, _, _, err, after = run(world, "set-status", "21", "in-progress", "--repo", "gr4vy/gr4ce")
    if code != 0:
        return False, f"exit {code}: {err!r}"
    return (
        "in-progress" in body_of(after, "gr4vy/gr4ce#21") and "critiqued" in body_of(after, "here#21"),
        f"edits {after.get('edits')}",
    )


# header lines


def test_header_lines_go_in_contract_order():
    """Critique and Landed land in the header after Status, in that order, whatever order they are set"""
    world = {"issues": {"here#60": issue("in-progress")}}
    code, _, _, err, after = run(world, "header", "60", "landed", "#61, #62, 2026-09-24")
    if code != 0:
        return False, f"landed exit {code}: {err!r}"
    world = {"issues": {"here#60": after["issues"]["here#60"]}}
    code, _, _, err, after = run(world, "header", "60", "critique", "google (gemini), #60 comment 1, 2026-09-18")
    if code != 0:
        return False, f"critique exit {code}: {err!r}"
    head = body_of(after).split("\n\n## ")[0]
    want = (
        "**Status:** in-progress\n"
        "**Critique:** google (gemini), #60 comment 1, 2026-09-18\n"
        "**Landed:** #61, #62, 2026-09-24"
    )
    return head == want, f"header is {head!r}"


def test_a_header_line_set_twice_is_replaced_not_repeated():
    """a second Critique replaces the first, so a re-critiqued Spec carries one Critique line"""
    world = {"issues": {"here#60": issue("draft")}}
    _, _, _, _, after = run(world, "header", "60", "critique", "codex (default), #60 comment 1, 2026-09-18")
    world = {"issues": {"here#60": after["issues"]["here#60"]}}
    code, _, _, err, after = run(world, "header", "60", "critique", "claude (opus), #60 comment 2, 2026-09-19")
    body = body_of(after)
    return code == 0 and body.count("**Critique:**") == 1 and "comment 2" in body, f"body {body!r}"


# list


def test_list_finds_closed_specs_at_a_status_and_nothing_else():
    """list --status implemented returns Spec issues at that Status, open or closed, and no other issue"""
    world = {"issues": {
        "here#60": issue("implemented", state="CLOSED"),
        "here#61": issue("in-progress"),
        "here#62": issue(body="## Parent\n\n#60\n\n**Status:** implemented\n"),
        "here#63": issue("implemented", title="Refunds"),
    }}
    code, out, _, err, _ = run(world, "list", "--status", "implemented")
    if code != 0:
        return False, f"exit {code}: {err!r}"
    got = sorted((s["number"], s["title"]) for s in out)
    return got == [(60, "Loyalty earn and burn"), (63, "Refunds")], f"got {got}"


# migrate


OLD_FILE = """# Loyalty earn and burn

**Status:** implemented
**Tracker:** #60
**Critique:** google (gemini), #60 comment 1, 2026-09-18
**Landed:** #61, #62, 2026-09-24

## Problem Statement

Buyers earn nothing.

## Criteria

### C1
Given a cart
When the buyer submits
Then the ledger holds one row

## Verification

Command: `pnpm test:e2e loyalty`
"""

POINTER = "Spec: `docs/specs/60-loyalty.md` on the default branch\n\n## Criteria\n\n- C1 ledger row\n"


def test_migrate_brings_the_file_into_the_body_without_the_title_or_tracker():
    """migrate writes the file into the body, dropping only the # title and Tracker lines"""
    world = {"issues": {"here#60": issue(body=POINTER, state="CLOSED")},
             "files": {"here:docs/specs/60-loyalty.md": OLD_FILE}}
    code, _, out, err, after = run(world, "migrate", "60")
    if code != 0:
        return False, f"exit {code}: {err!r}"
    want = OLD_FILE.replace("# Loyalty earn and burn\n\n", "").replace("**Tracker:** #60\n", "")
    return body_of(after) == want and "docs/specs/60-loyalty.md" in out, f"body {body_of(after)!r}"


def test_a_migrated_spec_reads_with_its_status_and_history():
    """after migrate, read gives the Status, Critique and Landed the file had reached"""
    world = {"issues": {"here#60": issue(body=POINTER)}, "files": {"here:docs/specs/60-loyalty.md": OLD_FILE}}
    _, _, _, _, after = run(world, "migrate", "60")
    code, out, _, err, _ = run({"issues": after["issues"]}, "read", "60")
    if code != 0:
        return False, f"exit {code}: {err!r}"
    got = (out["status"], out["critique"], out["landed"], [c["id"] for c in out["criteria"]])
    want = ("implemented", "google (gemini), #60 comment 1, 2026-09-18", "#61, #62, 2026-09-24", ["C1"])
    return got == want, f"got {got}"


def test_migrate_keeps_a_slices_task_list_the_pointer_body_carried():
    """a ## Slices task list on the old body survives, so no Slice drops off the roster unseen"""
    body = POINTER + "\n## Slices\n\n- [ ] #61\n- [x] #62\n"
    world = {"issues": {"here#60": issue(body=body)}, "files": {"here:docs/specs/60-loyalty.md": OLD_FILE}}
    code, _, _, err, after = run(world, "migrate", "60")
    if code != 0:
        return False, f"exit {code}: {err!r}"
    return body_of(after).rstrip().endswith("## Slices\n\n- [ ] #61\n- [x] #62"), f"body {body_of(after)!r}"


def test_migrate_reads_the_file_from_the_specs_repository():
    """--repo reads the file and writes the body in that repository"""
    world = {"issues": {"gr4vy/gr4ce#60": issue(body=POINTER)},
             "files": {"gr4vy/gr4ce:docs/specs/60-loyalty.md": OLD_FILE}}
    code, _, _, err, after = run(world, "migrate", "60", "--repo", "gr4vy/gr4ce")
    return code == 0 and body_of(after, "gr4vy/gr4ce#60").startswith("**Status:** implemented"), f"exit {code}: {err!r}"


def test_migrate_on_a_spec_already_in_its_issue_writes_nothing():
    """migrate on a body that is already a Spec exits 0 and makes no edit"""
    code, _, out, _, after = run({"issues": {"here#60": issue("draft")}}, "migrate", "60")
    return code == 0 and not after.get("edits") and "unchanged" in out, f"exit {code}, {out!r}"


def test_migrate_refuses_a_file_that_is_not_on_the_default_branch():
    """a pointer whose file never merged exits 1 and leaves the body alone"""
    code, _, _, err, after = run({"issues": {"here#60": issue(body=POINTER)}, "files": {}}, "migrate", "60")
    return code == 1 and not after.get("edits") and "docs/specs/60-loyalty.md" in err, f"exit {code}, {err!r}"


def test_migrate_refuses_a_file_that_does_not_parse_as_a_spec():
    """a file with no Status line exits 1 rather than writing a body no reader accepts"""
    world = {"issues": {"here#60": issue(body=POINTER)},
             "files": {"here:docs/specs/60-loyalty.md": "# Loyalty\n\n## Criteria\n"}}
    code, _, _, err, after = run(world, "migrate", "60")
    return code == 1 and not after.get("edits"), f"exit {code}, {err!r}"


def test_the_legacy_pointer_error_names_the_migrate_command():
    """read on a pointer body tells the reader the exact migrate command to run"""
    code, _, _, err, _ = run({"issues": {"here#60": issue(body=POINTER)}}, "read", "60")
    return code == 1 and re.search(r"spec\.py migrate 60", err), f"exit {code}, {err!r}"


# the shipped files


READERS = {
    "skills/critique-spec/SKILL.md",
    "skills/dispatch-slices/SKILL.md",
    "skills/acceptance-tests/SKILL.md",
    "skills/finalize-pr/SKILL.md",
    "skills/review-pr/SKILL.md",
    "references/spec-close-out.md",
}


def test_every_spec_reader_goes_through_the_script():
    """every skill that reads or writes a Spec runs spec.py"""
    missing = [p for p in sorted(READERS) if not re.search(r"\bspec\.py\b", (ROOT / p).read_text())]
    return not missing, f"not run by: {', '.join(missing)}"


# How every reader under the old contract found a Spec file: a templated or
# globbed path under docs/specs. Naming the old location in prose, to tell a
# person about a legacy pointer, is fine; locating a file there is not.
LOCATES_A_SPEC_FILE = re.compile(r"docs/specs/(\{|\*)")


def test_nothing_shipped_names_a_skill_that_is_gone():
    """no skill, reference, script or contract sends anyone to /anchor-spec"""
    shipped = [*ROOT.glob("skills/**/*.md"), *ROOT.glob("references/*.md"), *ROOT.glob("scripts/*.py"),
               ROOT / "CONTRACTS.md", ROOT / "README.md", ROOT / "CONTEXT.md"]
    found = [str(p.relative_to(ROOT)) for p in shipped
             if p.name != "test-spec.py" and "anchor-spec" in p.read_text()]
    return not found and not (ROOT / "skills" / "anchor-spec").exists(), f"still name it: {', '.join(found)}"


def test_no_shipped_file_still_reads_a_spec_file():
    """no skill, reference or agent template locates a Spec under docs/specs"""
    shipped = [*ROOT.glob("skills/**/*.md"), *ROOT.glob("references/*.md")]
    found = [str(p.relative_to(ROOT)) for p in shipped if LOCATES_A_SPEC_FILE.search(p.read_text())]
    return not found, f"still locate a Spec file: {', '.join(found)}"


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
        print(f"✘ {failed} of {len(cases)} spec cases failed")
        return 1
    print(f"✔ {len(cases)} spec cases pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

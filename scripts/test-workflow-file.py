#!/usr/bin/env python3
"""Cases for workflow-file.py.

The file it writes is the repo's own choice of critics and security
reviewers, so the cases that matter most are the ones where it must leave
bytes alone: the Specs line, the Critics list, and a Security reviewers list
someone already ordered.
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WRITER = Path(__file__).with_name("workflow-file.py")
# This repo's docs/agents/workflow.md as it stood before #53 migrated it. Frozen
# here because the migrated file no longer has the precondition C2 starts from.
THIS_REPO = (
    '# Workflow\n'
    '\n'
    "Per-repo settings for the slice workflow. `CONTRACTS.md` describes this file's shape.\n"
    '\n'
    '**Specs:** off\n'
    '\n'
    '**Critics:**\n'
    '1. codex, default\n'
    '2. google, gemini-3.8-flash-high\n'
    '3. claude, claude-opus-5\n'
)


def run(path, *args):
    return subprocess.run(
        [sys.executable, str(WRITER), str(path), *args],
        capture_output=True,
        text=True,
    )


def entries(text, heading):
    """The `{vendor}, {model}` entries of the numbered list under a heading."""
    lines = text.splitlines()
    try:
        start = lines.index(f"**{heading}:**")
    except ValueError:
        return None
    out = []
    for line in lines[start + 1:]:
        m = re.match(r"^\d+\.\s+(.+)$", line)
        if not m:
            break
        out.append(tuple(part.strip() for part in m.group(1).split(",", 1)))
    return out


def block(text, heading):
    """The heading line and its list, as the exact bytes in the file."""
    m = re.search(rf"^\*\*{re.escape(heading)}:\*\*\n(?:\d+\..*\n?)*", text, re.M)
    return m.group(0) if m else None


def specs_line(text):
    m = re.search(r"^\*\*Specs:\*\*.*$", text, re.M)
    return m.group(0) if m else None


def case(label, check):
    root = Path(tempfile.mkdtemp())
    try:
        ok, why = check(root)
    except Exception as exc:  # a crash is a failed case, not a crashed suite
        ok, why = False, f"raised {exc!r}"
    finally:
        shutil.rmtree(root)
    if not ok:
        print(f"  BAD  {label}: {why}")
    return ok


def c1_new_file_mirrors_critics(root):
    f = root / "docs" / "agents" / "workflow.md"
    proc = run(f, "--specs", "on", "--write")
    if proc.returncode != 0:
        return False, f"exit {proc.returncode}: {proc.stderr.strip()}"
    if not f.is_file():
        return False, "no file written"
    text = f.read_text()
    critics = entries(text, "Critics")
    security = entries(text, "Security reviewers")
    if not critics:
        return False, "new file has no Critics list"
    if security != critics:
        return False, f"Security reviewers {security} differ from Critics {critics}"
    if security[-1][0] != "claude":
        return False, f"last Security reviewers entry is {security[-1]}, not claude"
    return True, ""


def migrated_copy_of_this_repo(root):
    f = root / "workflow.md"
    f.write_text(THIS_REPO)
    return f


def c2_existing_file_gains_the_list(root):
    f = migrated_copy_of_this_repo(root)
    before = f.read_text()
    if entries(before, "Security reviewers") is not None:
        return False, "fixture already carries a Security reviewers list"

    draft = run(f)
    if draft.returncode != 0:
        return False, f"draft exit {draft.returncode}: {draft.stderr.strip()}"
    if f.read_text() != before:
        return False, "the draft run wrote to the file"
    if entries(draft.stdout, "Security reviewers") is None:
        return False, "the draft does not show the Security reviewers list"

    proc = run(f, "--write")
    if proc.returncode != 0:
        return False, f"write exit {proc.returncode}: {proc.stderr.strip()}"
    after = f.read_text()
    if not entries(after, "Security reviewers"):
        return False, "the list was not added"
    if specs_line(after) != specs_line(before):
        return False, f"Specs line changed: {specs_line(before)!r} -> {specs_line(after)!r}"
    if block(after, "Critics") != block(before, "Critics"):
        return False, "Critics list is not byte-identical"
    return True, ""


def c3_second_rerun_is_unchanged(root):
    f = migrated_copy_of_this_repo(root)
    first = run(f, "--write")
    if first.returncode != 0:
        return False, f"first run exit {first.returncode}: {first.stderr.strip()}"
    before_bytes, before_mtime = f.read_bytes(), f.stat().st_mtime_ns
    proc = run(f, "--write")
    if proc.returncode != 0:
        return False, f"second run exit {proc.returncode}: {proc.stderr.strip()}"
    if proc.stdout.splitlines()[:1] != ["unchanged"]:
        return False, f"second run reported {proc.stdout.splitlines()[:1]}, not unchanged"
    if f.read_bytes() != before_bytes or f.stat().st_mtime_ns != before_mtime:
        return False, "second run rewrote the file"
    return True, ""


def c4_existing_list_left_alone(root):
    f = root / "workflow.md"
    f.write_text(
        "**Specs:** on\n"
        "\n"
        "**Critics:**\n"
        "1. codex, default\n"
        "2. google, gemini-3.8-flash-high\n"
        "3. claude, claude-opus-5\n"
        "\n"
        "**Security reviewers:**\n"
        "1. google, gemini-3.8-pro\n"
        "2. codex, gpt-5.5\n"
        "3. claude, claude-opus-5\n"
    )
    before = f.read_text()
    proc = run(f, "--write")
    if proc.returncode != 0:
        return False, f"exit {proc.returncode}: {proc.stderr.strip()}"
    after = f.read_text()
    if block(after, "Security reviewers") != block(before, "Security reviewers"):
        return False, "existing Security reviewers list is not byte-identical"
    return True, ""


def old_shape_becomes_the_list_it_encodes(root):
    f = root / "workflow.md"
    f.write_text(
        "**Specs:** off\n"
        "\n"
        "**Critic:** google, gemini-3.8-pro\n"
        "\n"
        "**Fallback:** claude, claude-opus-5\n"
    )
    proc = run(f, "--write")
    if proc.returncode != 0:
        return False, f"exit {proc.returncode}: {proc.stderr.strip()}"
    after = f.read_text()
    want = [("google", "gemini-3.8-pro"), ("claude", "claude-opus-5")]
    if entries(after, "Critics") != want:
        return False, f"Critics became {entries(after, 'Critics')}, expected {want}"
    if "**Critic:**" in after or "**Fallback:**" in after:
        return False, "old-shape lines survived the conversion"
    if specs_line(after) != "**Specs:** off":
        return False, f"Specs line became {specs_line(after)!r}"
    if not entries(after, "Security reviewers"):
        return False, "no Security reviewers list added"
    return True, ""


def unknown_lines_survive(root):
    f = migrated_copy_of_this_repo(root)
    f.write_text(f.read_text() + "\nA note someone left here.\n")
    run(f, "--write")
    if "\nA note someone left here.\n" not in f.read_text():
        return False, "a line the writer does not own was dropped"
    return True, ""


def crlf_survives(root):
    f = root / "workflow.md"
    original = THIS_REPO.replace("\n", "\r\n").encode()
    f.write_bytes(original)
    proc = run(f, "--write")
    if proc.returncode != 0:
        return False, f"exit {proc.returncode}: {proc.stderr.strip()}"
    after = f.read_bytes()
    if not after.startswith(original):
        return False, "the CRLF lines it does not own were rewritten"
    if b"\n" in after.replace(b"\r\n", b""):
        return False, "the added list uses LF in a CRLF file"
    return True, ""


def content_after_critics_stays_separate(root):
    f = root / "workflow.md"
    f.write_text(
        "**Critics:**\n"
        "1. codex, default\n"
        "2. claude, claude-opus-5\n"
        "Notes here\n"
    )
    run(f, "--write")
    after = f.read_text()
    if entries(after, "Critics") != [("codex", "default"), ("claude", "claude-opus-5")]:
        return False, f"Critics became {entries(after, 'Critics')}"
    if "claude-opus-5\n\nNotes here\n" not in after:
        return False, f"the line after the lists is no longer its own paragraph: {after!r}"
    return True, ""


def fallback_before_critic_converts_cleanly(root):
    f = root / "workflow.md"
    f.write_text(
        "**Fallback:** claude, claude-opus-5\n"
        "\n"
        "**Critic:** codex, default\n"
    )
    run(f, "--write")
    after = f.read_text()
    if entries(after, "Critics") != [("codex", "default"), ("claude", "claude-opus-5")]:
        return False, f"Critics became {entries(after, 'Critics')}"
    if after.startswith("\n"):
        return False, "the conversion left a leading blank line"
    return True, ""


def floorless_list_is_flagged_and_left_alone(root):
    f = root / "workflow.md"
    f.write_text(
        "**Critics:**\n"
        "1. claude, claude-opus-5\n"
        "2. codex, default\n"
        "\n"
        "**Security reviewers:**\n"
        "1. codex, default\n"
    )
    before = f.read_bytes()
    proc = run(f, "--write")
    if f.read_bytes() != before:
        return False, "a user's list was rewritten to fix its floor"
    if proc.returncode == 0:
        return False, "exited 0 on lists whose last entry is not claude"
    if "Critics" not in proc.stderr or "Security reviewers" not in proc.stderr:
        return False, f"did not name both floorless lists: {proc.stderr.strip()!r}"
    return True, ""


def unreadable_path_fails_cleanly(root):
    proc = run(root)
    if proc.returncode == 0:
        return False, "exited 0 on a directory"
    if "Traceback" in proc.stderr:
        return False, "crashed with a traceback"
    return True, ""


def write_keeps_file_mode(root):
    f = migrated_copy_of_this_repo(root)
    f.chmod(0o644)
    run(f, "--write")
    mode = f.stat().st_mode & 0o777
    if mode != 0o644:
        return False, f"mode became {oct(mode)}, was 0o644"
    fresh = root / "new" / "workflow.md"
    run(fresh, "--write")
    if fresh.stat().st_mode & 0o044 != 0o044:
        return False, f"a new file is not group/other readable: {oct(fresh.stat().st_mode & 0o777)}"
    return True, ""


def lone_critic_is_flagged(root):
    f = root / "workflow.md"
    f.write_text("**Critic:** codex, default\n")
    proc = run(f, "--write")
    if proc.returncode == 0:
        return False, "exited 0 on a Critic line with no Fallback"
    if "**Critic:** codex, default\n" not in f.read_text():
        return False, "the lone Critic line was rewritten"
    return True, ""


CASES = [
    ("--write keeps an existing file's mode, and a new file is readable", write_keeps_file_mode),
    ("a lone old-shape Critic line is flagged and left alone", lone_critic_is_flagged),
    ("CRLF line endings survive", crlf_survives),
    ("content right after Critics stays its own paragraph", content_after_critics_stays_separate),
    ("Fallback above Critic converts without a stray blank line",
     fallback_before_critic_converts_cleanly),
    ("a list whose last entry is not claude is flagged and left alone",
     floorless_list_is_flagged_and_left_alone),
    ("an unreadable path fails without a traceback", unreadable_path_fails_cleanly),
    ("an old Critic/Fallback file becomes the Critics list it encodes",
     old_shape_becomes_the_list_it_encodes),
    ("lines the writer does not own survive", unknown_lines_survive),
    ("#53 C1 a new file's Security reviewers list mirrors Critics and ends in claude",
     c1_new_file_mirrors_critics),
    ("#53 C2 an existing file gains the list, shown in the draft, Specs and Critics byte-identical",
     c2_existing_file_gains_the_list),
    ("#53 C3 a second re-run reports unchanged and leaves the file byte-identical",
     c3_second_rerun_is_unchanged),
    ("#53 C4 an existing Security reviewers list in another order is left byte-identical",
     c4_existing_list_left_alone),
]


def main():
    bad = [label for label, check in CASES if not case(label, check)]
    if bad:
        print(f"✘ {len(bad)} of {len(CASES)} workflow-file cases behaved unexpectedly")
        return 1
    print(f"✔ {len(CASES)} workflow-file cases behave as specified")
    return 0


if __name__ == "__main__":
    sys.exit(main())

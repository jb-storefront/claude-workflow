#!/usr/bin/env python3
"""Cases for check-skill-frontmatter.py.

A linter's failure mode is the false positive: it turns the default branch red
over a SKILL.md that was fine, and the next person deletes the gate rather than
the bug. So the passing cases here matter at least as much as the failing ones,
and every spelling a real frontmatter uses is one of them.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHECKER = Path(__file__).with_name("check-skill-frontmatter.py")

# (label, skill directory name, SKILL.md text, should the checker exit 0)
CASES = [
    ("valid bare", "demo", '---\nname: demo\ndescription: does a thing\n---\n# d\n', True),
    ("valid quoted", "demo", '---\nname: "demo"\ndescription: "does a thing"\n---\n# d\n', True),
    ("valid single-quoted", "demo", "---\nname: 'demo'\ndescription: 'a thing'\n---\n# d\n", True),
    ("folded description", "demo", '---\nname: demo\ndescription: >\n  folded\n  text\n---\n# d\n', True),
    ("allowed-tools list", "demo", '---\nname: demo\ndescription: d\nallowed-tools: [Bash, Read]\n---\n# d\n', True),
    ("allowed-tools list + comment", "demo", '---\nname: demo\ndescription: d\nallowed-tools: [Bash]  # only bash\n---\n# d\n', True),
    ("CRLF line endings", "demo", '---\r\nname: demo\r\ndescription: d\r\n---\r\n# d\r\n', True),
    ("colon inside value", "demo", '---\nname: demo\ndescription: does x: then y\n---\n# d\n', True),
    ("hash with no space", "demo", '---\nname: demo\ndescription: issue #18 handling\n---\n# d\n', True),

    ("empty quoted description", "demo", '---\nname: demo\ndescription: ""\n---\n# d\n', False),
    ("empty bare description", "demo", '---\nname: demo\ndescription:\n---\n# d\n', False),
    ("missing name", "demo", '---\ndescription: d\n---\n# d\n', False),
    ("unclosed flow in name", "demo", '---\nname: [unclosed\ndescription: d\n---\n# d\n', False),
    ("unclosed quote in name", "demo", '---\nname: "unclosed\ndescription: d\n---\n# d\n', False),
    ("name mismatches dir", "demo", '---\nname: other\ndescription: d\n---\n# d\n', False),
    ("quoted name mismatches dir", "demo", '---\nname: "other"\ndescription: d\n---\n# d\n', False),
    ("no frontmatter", "demo", '# just a heading\n', False),
    ("unterminated frontmatter", "demo", '---\nname: demo\ndescription: d\n# no close\n', False),
]


def run(label, dirname, text, should_pass):
    root = Path(tempfile.mkdtemp())
    try:
        skill = root / "skills" / dirname
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(text, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(CHECKER), str(root / "skills")],
            capture_output=True,
            text=True,
        )
        passed = proc.returncode == 0
        if passed == should_pass:
            return True
        want = "accept" if should_pass else "reject"
        print(f"  BAD  {label}: expected the checker to {want} it, and it did not")
        for line in proc.stdout.strip().splitlines():
            print(f"       {line}")
        return False
    finally:
        shutil.rmtree(root)


def main():
    if not CHECKER.is_file():
        print(f"✘ {CHECKER} is missing")
        return 1
    bad = [c for c in CASES if not run(*c)]
    if bad:
        print(f"✘ {len(bad)} of {len(CASES)} frontmatter cases behaved unexpectedly")
        return 1
    print(f"✔ {len(CASES)} frontmatter cases behave as specified")
    return 0


if __name__ == "__main__":
    sys.exit(main())

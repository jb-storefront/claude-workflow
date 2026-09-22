#!/usr/bin/env python3
"""Check every skill's SKILL.md frontmatter.

`claude plugin validate` reads the two manifests and stops there: pointed at this
repo's root, at the plugin manifest, or at `skills/` itself, it reports
`contents: []` and exits 0 for a SKILL.md whose YAML does not parse. So the one
file a skill actually is goes unchecked by the gate that is supposed to keep the
default branch installable.

Checked here: the frontmatter delimiters, that `name` and `description` are
present and non-empty, and that `name` matches the directory Claude Code loads
the skill by.

No YAML library. A skill's frontmatter is flat by design — two scalars — and a
gate that runs on a bare runner is worth more than one that parses YAML nobody
writes here. Anything this reader cannot read is reported rather than guessed at.
"""

import sys
from pathlib import Path

REQUIRED = ("name", "description")
FLOW_OPENERS = {"[": "]", "{": "}"}


def frontmatter(text):
    """Return the frontmatter block, or raise ValueError saying what is wrong."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("no frontmatter: the file must open with a line containing only ---")
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return lines[1:i]
    raise ValueError("unterminated frontmatter: no closing --- found")


def fields(block):
    """Map the block's top-level keys to their raw values.

    Indented lines belong to the value above them and are left alone; a scalar
    that opens a YAML flow collection and never closes it is rejected rather
    than silently read as the string it is not.
    """
    out = {}
    problems = []
    for line in block:
        if not line.strip() or line[0].isspace() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            problems.append(f"`{line.strip()}` is not a `key: value` line")
            continue
        value = value.strip()
        closer = FLOW_OPENERS.get(value[:1])
        if closer and not value.endswith(closer):
            problems.append(f"`{key.strip()}` opens a YAML collection that never closes")
            continue
        out[key.strip()] = value
    return out, problems


def check(skill_md):
    """Return a list of problem strings for one SKILL.md. Empty means it passed."""
    try:
        block = frontmatter(skill_md.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [str(exc)]

    found, problems = fields(block)

    for key in REQUIRED:
        if not found.get(key, "").strip():
            problems.append(f"missing or empty `{key}`")

    expected = skill_md.parent.name
    name = found.get("name", "").strip()
    if name and name != expected:
        problems.append(
            f"`name: {name}` does not match the directory `{expected}` "
            "that Claude Code loads the skill by"
        )

    return problems


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "skills")
    if not root.is_dir():
        print(f"✘ no {root}/ directory to check")
        return 1

    skills = sorted(p for p in root.iterdir() if p.is_dir())
    if not skills:
        print(f"✘ {root}/ holds no skills")
        return 1

    failed = 0
    for skill in skills:
        skill_md = skill / "SKILL.md"
        if not skill_md.is_file():
            print(f"✘ {skill}/ has no SKILL.md")
            failed = 1
            continue
        for problem in check(skill_md):
            print(f"✘ {skill_md}: {problem}")
            failed = 1

    if not failed:
        print(f"✔ {len(skills)} skills carry a well-formed SKILL.md frontmatter")
    return failed


if __name__ == "__main__":
    sys.exit(main())

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

No YAML library, so this gate runs on a bare runner. `name` and `description` are
scalars, which is the whole of what a reader needs to understand to check them;
every other key is read as opaque and left alone, because judging a value this
reader was not written to parse is how a linter invents failures.
"""

import sys
from pathlib import Path

REQUIRED = ("name", "description")
FLOW_OPENERS = "[{"
QUOTES = ("'", '"')


def scalar(value):
    """Read one frontmatter value as the string YAML would produce.

    Handles the two spellings a scalar actually takes in these files: quoted, and
    bare with an optional trailing comment. Returns None when the value is not a
    scalar at all, which for a required key is an error the caller reports.
    """
    value = value.strip()
    if value[:1] in QUOTES:
        quote = value[0]
        end = value.find(quote, 1)
        return value[1:end] if end != -1 else None
    # `value[:1] in FLOW_OPENERS` would be true for the empty string, since every
    # string contains "". That reports a missing value as a list.
    if value and value[0] in FLOW_OPENERS:
        return None
    # An unquoted ` #` starts a comment; `#` with no leading space does not.
    comment = value.find(" #")
    return (value[:comment] if comment != -1 else value).strip()


def frontmatter(text):
    """Return the frontmatter block's lines, or raise ValueError saying what is wrong."""
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("no frontmatter: the file must open with a line containing only ---")
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return lines[1:i]
    raise ValueError("unterminated frontmatter: no closing --- found")


def fields(block):
    """Map the block's top-level keys to their raw values.

    Indented lines belong to the value above them and are left alone, so a folded
    or block scalar survives as whatever its first line said.
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
        out[key.strip()] = value
    return out, problems


def check(skill_md):
    """Return a list of problem strings for one SKILL.md. Empty means it passed."""
    try:
        block = frontmatter(skill_md.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        return [str(exc)]

    found, problems = fields(block)
    values = {}

    for key in REQUIRED:
        if key not in found:
            problems.append(f"missing `{key}`")
            continue
        value = scalar(found[key])
        if value is None:
            problems.append(f"`{key}` must be a single value, not a list or an unclosed quote")
        elif not value:
            problems.append(f"empty `{key}`")
        else:
            values[key] = value

    expected = skill_md.parent.name
    if "name" in values and values["name"] != expected:
        problems.append(
            f"`name: {values['name']}` does not match the directory `{expected}` "
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
        noun = "skill carries" if len(skills) == 1 else "skills carry"
        print(f"✔ {len(skills)} {noun} a well-formed SKILL.md frontmatter")
    return failed


if __name__ == "__main__":
    sys.exit(main())

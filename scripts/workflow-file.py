#!/usr/bin/env python3
"""Write or migrate the per-repo workflow file for /setup-workflow.

Usage: workflow-file.py <path> [--specs on|off] [--write]

Prints one status line, then the file as it would stand afterwards. Writes
only with --write. CONTRACTS.md describes the file's shape.
"""

import argparse
import re
import sys
from pathlib import Path

DEFAULT_CHAIN = (
    "1. codex, default\n"
    "2. google, gemini-3.8-flash-high\n"
    "3. claude, claude-opus-5\n"
)


def new_file(specs):
    return (
        f"**Specs:** {specs}\n"
        "\n"
        "**Critics:**\n"
        f"{DEFAULT_CHAIN}"
        "\n"
        "**Security reviewers:**\n"
        f"{DEFAULT_CHAIN}"
    )


def convert_old_shape(lines):
    """Rewrite `**Critic:**` + `**Fallback:**` as the two-entry list they encode."""
    if any(l.startswith("**Critics:**") for l in lines):
        return lines, False
    critic = next((i for i, l in enumerate(lines) if l.startswith("**Critic:**")), None)
    fallback = next((i for i, l in enumerate(lines) if l.startswith("**Fallback:**")), None)
    if critic is None or fallback is None:
        return lines, False
    first = lines[critic][len("**Critic:**"):].strip()
    second = lines[fallback][len("**Fallback:**"):].strip()
    # Drop the blank line that separated the two old lines, so the list stays one block.
    drop = {fallback}
    if fallback > 0 and fallback - 1 != critic and lines[fallback - 1].strip() == "":
        drop.add(fallback - 1)
    out = []
    for i, line in enumerate(lines):
        if i == critic:
            out += ["**Critics:**\n", f"1. {first}\n", f"2. {second}\n"]
        elif i not in drop:
            out.append(line)
    return out, True


def add_security_reviewers(lines):
    """Add the default list after the Critics list, or at the end without one."""
    if any(l.startswith("**Security reviewers:**") for l in lines):
        return lines, False
    out = list(lines)
    at = len(out)
    heading = next((i for i, l in enumerate(out) if l.startswith("**Critics:**")), None)
    if heading is not None:
        at = heading + 1
        while at < len(out) and re.match(r"^\d+\.\s", out[at]):
            at += 1
    if at > 0 and not out[at - 1].endswith("\n"):
        out[at - 1] += "\n"
    out.insert(at, "\n**Security reviewers:**\n" + DEFAULT_CHAIN)
    return out, True


def migrate(text):
    lines, converted = convert_old_shape(text.splitlines(keepends=True))
    lines, added = add_security_reviewers(lines)
    done = []
    if converted:
        done.append("converted Critic/Fallback to a Critics list")
    if added:
        done.append("added Security reviewers")
    return "".join(lines), done


def main(argv):
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("path")
    ap.add_argument("--specs", choices=["on", "off"], default="on")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    path = Path(args.path)

    if path.exists():
        before = path.read_text()
        content, done = migrate(before)
        if content == before:
            print("unchanged")
            return 0
        print("update  " + "; ".join(done))
    else:
        content = new_file(args.specs)
        print(f"new  Specs: {args.specs}")
    print(content, end="")
    if args.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

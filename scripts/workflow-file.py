#!/usr/bin/env python3
"""Write or migrate the per-repo workflow file for /setup-workflow.

Usage: workflow-file.py <path> [--specs on|off] [--write]

Prints one status line (`new`, `update` with what changes, or `unchanged`),
then the file as it would stand afterwards. Writes only with --write.
CONTRACTS.md describes the file's shape.

An existing file is the repo's own choice of critics and security reviewers,
so every line this script does not add is kept byte for byte, line endings
included. Exit 1 means a list has no `claude` floor: the file is still left
alone, because fixing someone's chain is their call.
"""

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

DEFAULT_CHAIN = [
    "1. codex, default",
    "2. google, gemini-3.8-flash-high",
    "3. claude, claude-opus-5",
]
LIST_ITEM = re.compile(r"^\d+\.\s+(.*)$")


def find(lines, prefix):
    return next((i for i, l in enumerate(lines) if l.startswith(prefix)), None)


def blank(line):
    return line.strip() == ""


def list_end(lines, heading):
    at = heading + 1
    while at < len(lines) and LIST_ITEM.match(lines[at].rstrip("\r\n")):
        at += 1
    return at


def new_file(specs):
    return "\n".join(
        [f"**Specs:** {specs}", "", "**Critics:**", *DEFAULT_CHAIN,
         "", "**Security reviewers:**", *DEFAULT_CHAIN, ""]
    )


def convert_old_shape(lines, eol):
    """Rewrite `**Critic:**` + `**Fallback:**` as the two-entry list they encode."""
    critic, fallback = find(lines, "**Critic:**"), find(lines, "**Fallback:**")
    if find(lines, "**Critics:**") is not None or critic is None or fallback is None:
        return lines, False
    first = lines[critic][len("**Critic:**"):].strip()
    second = lines[fallback][len("**Fallback:**"):].strip()
    # Take one blank line with the Fallback line, so neither a gap nor a
    # leading blank is left where it stood.
    drop = {fallback}
    if fallback > 0 and blank(lines[fallback - 1]) and fallback - 1 != critic:
        drop.add(fallback - 1)
    elif fallback + 1 < len(lines) and blank(lines[fallback + 1]) and fallback + 1 != critic:
        drop.add(fallback + 1)
    out = []
    for i, line in enumerate(lines):
        if i == critic:
            out += [f"**Critics:**{eol}", f"1. {first}{eol}", f"2. {second}{eol}"]
        elif i not in drop:
            out.append(line)
    return out, True


def add_security_reviewers(lines, eol):
    """Add the default list after the Critics list, or at the end without one."""
    if find(lines, "**Security reviewers:**") is not None:
        return lines, False
    out = list(lines)
    heading = find(out, "**Critics:**")
    at = len(out) if heading is None else list_end(out, heading)
    if at > 0 and not out[at - 1].endswith("\n"):
        out[at - 1] += eol
    block = [eol, f"**Security reviewers:**{eol}", *(e + eol for e in DEFAULT_CHAIN)]
    if at < len(out) and not blank(out[at]):
        block.append(eol)
    out[at:at] = block
    return out, True


def migrate(text):
    eol = "\r\n" if "\r\n" in text else "\n"
    lines, converted = convert_old_shape(text.splitlines(keepends=True), eol)
    lines, added = add_security_reviewers(lines, eol)
    done = []
    if converted:
        done.append("converted Critic/Fallback to a Critics list")
    if added:
        done.append("added Security reviewers")
    return "".join(lines), done


def floorless(text):
    """Names of the lists whose last entry is not a `claude` one."""
    lines = text.splitlines()
    bad = []
    for name in ("Critics", "Security reviewers"):
        heading = find(lines, f"**{name}:**")
        if heading is None:
            continue
        items = lines[heading + 1:list_end(lines, heading)]
        last = LIST_ITEM.match(items[-1]).group(1) if items else ""
        if last.split(",", 1)[0].strip() != "claude":
            bad.append(name)
    return bad


def write_atomically(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as out:
            out.write(content)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def main(argv):
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("path")
    ap.add_argument("--specs", choices=["on", "off"], default="on")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    path = Path(args.path)

    if path.exists():
        try:
            # newline="" keeps CRLF as CRLF, so untouched lines stay untouched.
            with open(path, encoding="utf-8", newline="") as f:
                before = f.read()
        except (OSError, UnicodeDecodeError) as exc:
            print(f"✘ cannot read {path}: {exc}", file=sys.stderr)
            return 1
        content, done = migrate(before)
        status = "update  " + "; ".join(done) if done else "unchanged"
    else:
        before, content, status = None, new_file(args.specs), f"new  Specs: {args.specs}"

    print(status)
    if content != before:
        print(content, end="")
        if args.write:
            write_atomically(path, content)

    bad = floorless(content)
    for name in bad:
        print(f"✘ the {name} list's last entry is not claude, so it has no floor", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

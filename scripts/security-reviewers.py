#!/usr/bin/env python3
"""Read the Security reviewers list for /review-pr.

Usage: security-reviewers.py [path]   (default: docs/agents/workflow.md)

Prints the chain /review-pr walks, one `{vendor}\t{model}` per line, in order.
CONTRACTS.md describes the list.

No file, or a file with no Security reviewers list, prints the Claude floor
alone as `claude\tdefault`, and one `note:` line on stderr saying that
/setup-workflow adds the list. The Critics list is never read in its place.

Exit 1 with a `✘` line on stderr, and nothing on stdout, when the list cannot
be walked: an entry that is not `{vendor}, {model}`, a vendor with no dispatch
path, or a last entry that is not claude. /review-pr stops on any of them
before dispatching anything, so no half-walked chain can name a reviewer.
"""

import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "workflow_file", Path(__file__).with_name("workflow-file.py")
)
workflow_file = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(workflow_file)

VENDORS = ("codex", "google", "claude")
HEADING = "**Security reviewers:**"
FLOOR = ("claude", "default")
NOTE = (
    "note: no Security reviewers list in {path}, so the Claude floor runs alone; "
    "/setup-workflow adds the list"
)


def chain(text):
    """The list's entries, or None when the text has no list. Raises ValueError when unusable."""
    lines = text.splitlines()
    heading = workflow_file.find(lines, HEADING)
    if heading is None:
        return None
    items = lines[heading + 1:workflow_file.list_end(lines, heading)]
    if not items:
        raise ValueError("the Security reviewers list has no entries, so it has no claude floor")
    entries = []
    for item in items:
        body = workflow_file.LIST_ITEM.match(item).group(1).strip()
        vendor, sep, model = (part.strip() for part in body.partition(","))
        if not sep or not vendor or not model:
            raise ValueError(f"`{body}` is not `{{vendor}}, {{model}}`")
        if vendor not in VENDORS:
            raise ValueError(f"`{body}` names vendor {vendor}, which has no dispatch path")
        entries.append((vendor, model))
    if entries[-1][0] != "claude":
        last = ", ".join(entries[-1])
        raise ValueError(f"the last entry is `{last}`, not claude, so the chain has no floor")
    return entries


def main(argv):
    path = Path(argv[0]) if argv else Path("docs/agents/workflow.md")
    try:
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        entries = chain(text)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"✘ cannot read {path}: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"✘ {exc}", file=sys.stderr)
        return 1
    if entries is None:
        print(NOTE.format(path=path), file=sys.stderr)
        entries = [FLOOR]
    for vendor, model in entries:
        print(f"{vendor}\t{model}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

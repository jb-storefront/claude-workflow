#!/usr/bin/env python3
"""Read a Spec's roster of Slices: the sub-issues of its Spec issue.

Usage: spec-slices.py {spec}     (run inside a clone; gh resolves the repo)

CONTRACTS.md makes the Spec issue's sub-issues the only roster of its Slices.
/dispatch-slices and the Spec close-out read it here, so the
pagination and the back-compat rule live in one tested place.

Prints, and exits 0:

  {"spec": 60, "slices": [{"number", "title", "state", "assignees", "parent"}]}

in the order GitHub returns the sub-issues, every page of them, every state.
`state` is the tracker's, OPEN or CLOSED. `parent` is true when the Slice's
`## Parent` names this Spec, so it may own the Spec's Criteria; false for a
lone Slice linked under the Spec, which owns none.

Exits 1 with one `✘` line per problem on stderr, and nothing on stdout, when
the sub-issues cannot be trusted as the whole roster:

  - the Spec issue body still carries a `## Slices` task list naming an issue
    that is not a sub-issue (a Spec anchored before sub-issues were the roster)
  - an issue's `## Parent` names the Spec but it is not a sub-issue (a Slice
    /to-tickets published without linking)

Each line carries the command that links the issue. A `## Slices` list whose
every entry is a sub-issue is not read, and one `note:` on stderr says
it can be deleted. An empty `## Slices` heading is ignored.

Exits 2 when gh fails, so no reader mistakes an error for a Spec with no Slices.
"""

import json
import re
import subprocess
import sys

LIST_ITEM = re.compile(r"^\s*[-*]\s")
REFERENCE = re.compile(r"(?:#|/issues/)(\d+)(?!\d)")
LINK = (
    "gh api -X POST 'repos/{{owner}}/{{repo}}/issues/{spec}/sub_issues' "
    "-F sub_issue_id=\"$(gh api 'repos/{{owner}}/{{repo}}/issues/{n}' --jq .id)\""
)


class GhError(Exception):
    pass


def gh(*args):
    proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise GhError(proc.stderr.strip() or f"gh {' '.join(args)} exited {proc.returncode}")
    return json.loads(proc.stdout)


def section(body, heading):
    """The lines under `## {heading}`, up to the next `## `, or None when absent."""
    lines = (body or "").splitlines()
    for i, line in enumerate(lines):
        if line.strip() == f"## {heading}":
            rest = lines[i + 1:]
            end = next((j for j, l in enumerate(rest) if l.startswith("## ")), len(rest))
            return rest[:end]
    return None


def names(lines, spec):
    return any(int(n) == spec for line in lines or [] for n in REFERENCE.findall(line))


def task_list(body):
    entries = []
    for line in section(body, "Slices") or []:
        if LIST_ITEM.match(line):
            entries += [int(n) for n in REFERENCE.findall(line)[:1]]
    return entries


def roster(spec):
    body = gh("issue", "view", str(spec), "--json", "body")["body"]
    # The endpoint pages at 30 by default and gh returns one page unless told
    # to paginate; --slurp turns the pages into one JSON array of arrays.
    pages = gh(
        "api", "--paginate", "--slurp",
        f"repos/{{owner}}/{{repo}}/issues/{spec}/sub_issues?per_page=100",
    )
    subs = [i for page in pages for i in page]
    linked = {i["number"] for i in subs}

    problems = []
    listed = task_list(body)
    for n in listed:
        if n not in linked:
            problems.append(
                f"#{n} is on #{spec}'s ## Slices task list but is not a sub-issue of it; "
                f"link it: {LINK.format(spec=spec, n=n)}"
            )

    # Search by the bare number: it matches `#60` and `/issues/60` alike, and
    # the ## Parent filter below throws away every other mention.
    hits = gh(
        "issue", "list", "--state", "all", "--search", f"{spec} in:body",
        "--limit", "1000", "--json", "number,title,state,body",
    )
    for hit in sorted(hits, key=lambda h: h["number"]):
        n = hit["number"]
        if n == spec or n in linked or n in listed:
            continue
        if names(section(hit["body"], "Parent"), spec):
            problems.append(
                f"#{n} names #{spec} under ## Parent but is not a sub-issue of it; "
                f"link it: {LINK.format(spec=spec, n=n)}"
            )

    note = None
    if listed and not problems:
        note = (
            f"note: #{spec}'s body still carries a ## Slices task list; it is not read, "
            "and can be deleted from the body"
        )

    slices = [
        {
            "number": i["number"],
            "title": i["title"],
            "state": i["state"].upper(),
            "assignees": [a["login"] for a in i.get("assignees") or []],
            "parent": names(section(i.get("body"), "Parent"), spec),
        }
        for i in subs
    ]
    return slices, problems, note


def main(argv):
    if len(argv) != 1 or not argv[0].lstrip("#").isdigit():
        print("usage: spec-slices.py {spec}", file=sys.stderr)
        return 2
    spec = int(argv[0].lstrip("#"))
    try:
        slices, problems, note = roster(spec)
    except (GhError, json.JSONDecodeError, KeyError) as exc:
        print(f"✘ cannot read #{spec}'s sub-issues: {exc}", file=sys.stderr)
        return 2
    if problems:
        for p in problems:
            print(f"✘ {p}", file=sys.stderr)
        return 1
    if note:
        print(note, file=sys.stderr)
    print(json.dumps({"spec": spec, "slices": slices}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

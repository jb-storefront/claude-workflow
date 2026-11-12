#!/usr/bin/env python3
"""Read and write a Spec, which is the body of its Spec issue.

Usage (run inside a clone; gh resolves the repo unless --repo names one):

  spec.py read {spec} [--repo o/r]
  spec.py set-status {spec} {status} [--repo o/r]
  spec.py header {spec} critique|landed "{text}" [--repo o/r]
  spec.py list --status {status} [--repo o/r]
  spec.py migrate {spec} [--repo o/r]

CONTRACTS.md gives the Spec's shape. Every skill that reads a Status, a
Criterion or a Verification reads it here, and every skill that writes a header
line writes it here, so the grammar and the Status transitions live in one
tested place rather than in seven skills' prose.

read prints, and exits 0:

  {"spec", "title", "state", "status", "critique", "landed",
   "criteria": [{"id", "tag", "text", "command"}],
   "verification": {"form": "command", "command"} | {"form": "walkthrough", "steps"} | null}

`tag` is "manual", "command" or null. `command` is the backticked command on a
`[command]` Criterion's `Command:` line, or null. `verification` is null when
the section is absent, or carries neither form or both.

set-status rewrites the `**Status:**` line and no other byte, then reads the
body back. It walks only the transitions CONTRACTS.md owns; asking for the
Status the Spec already has writes nothing and prints `unchanged`.

header sets the `**Critique:**` or `**Landed:**` line, replacing one already
there, keeping the header in the order Status, Critique, Landed.

list prints the Spec issues, open and closed, whose Status is the one asked
for, as [{"number", "title", "state"}].

migrate brings a Spec anchored to a committed file under the old contract back
into its issue. It reads the file the body's `Spec:` pointer names from the
repository's default branch, drops the `# title` and `**Tracker:**` lines,
keeps everything else byte for byte, carries over any `## Slices` task list the
old body held so spec-slices.py can still check it, and writes the result as
the body. It never touches the file. On a body that is already a Spec it writes
nothing and prints `unchanged`.

Exits 1, with a `✘` line on stderr and nothing on stdout, when the issue is not
a Spec in CONTRACTS.md's shape, a transition is refused, or a write did not
read back. Exits 2 when gh fails, so no reader mistakes an error for a Spec.
"""

import json
import re
from pathlib import Path
import subprocess
import sys

STATUSES = ("draft", "critiqued", "in-progress", "implemented", "superseded")

# Every transition a skill owns, plus the two a person makes: critiqued back to
# draft to redo a Critique, and anything to superseded.
ALLOWED = {
    ("draft", "critiqued"),
    ("critiqued", "draft"),
    ("critiqued", "in-progress"),
    ("critiqued", "implemented"),
    ("in-progress", "implemented"),
} | {(s, "superseded") for s in STATUSES if s != "superseded"}

HEADER_ORDER = ("Status", "Critique", "Landed")
HEADER_LINE = re.compile(r"^\*\*(Status|Critique|Landed):\*\*\s*(.*?)\s*$")
CRITERION = re.compile(r"^### (C\d+)(?: \[([^\]]*)\])?\s*$")
COMMAND = re.compile(r"^Command:\s*`([^`]+)`\s*$")
OLD_POINTER = re.compile(r"^Spec:\s*`(docs/specs/[^`]+)`")


class GhError(Exception):
    pass


class NotASpec(Exception):
    pass


def gh(*args, stdin=None):
    proc = subprocess.run(["gh", *args], capture_output=True, text=True, input=stdin)
    if proc.returncode != 0:
        raise GhError(proc.stderr.strip() or f"gh {' '.join(args)} exited {proc.returncode}")
    return proc.stdout


def repo_args(repo):
    return ["--repo", repo] if repo else []


def fetch(spec, repo):
    out = gh("issue", "view", str(spec), "--json", "title,state,body", *repo_args(repo))
    return json.loads(out)


def split_header(body):
    """The header lines above the first `## `, and everything from it on."""
    lines = (body or "").split("\n")
    end = next((i for i, l in enumerate(lines) if l.startswith("## ")), len(lines))
    return lines[:end], lines[end:]


def header_fields(body):
    head, _ = split_header(body)
    fields = {}
    for line in head:
        m = HEADER_LINE.match(line)
        if m:
            fields[m.group(1)] = m.group(2)
    return fields


def section(body, heading):
    lines = (body or "").split("\n")
    for i, line in enumerate(lines):
        if line.strip() == f"## {heading}":
            rest = lines[i + 1:]
            end = next((j for j, l in enumerate(rest) if l.startswith("## ")), len(rest))
            return rest[:end]
    return None


def criteria(body, spec):
    found, current = [], None
    for line in section(body, "Criteria") or []:
        if line.startswith("### "):
            m = CRITERION.match(line)
            if not m:
                raise NotASpec(f"#{spec}: {line.strip()!r} is not a Criterion heading")
            cid, tag = m.group(1), m.group(2)
            if tag is not None and tag not in ("manual", "command"):
                raise NotASpec(f"#{spec} {cid} carries [{tag}]; a Criterion is [manual], [command] or untagged")
            if any(c["id"] == cid for c in found):
                raise NotASpec(f"#{spec} has two Criteria with id {cid}")
            current = {"id": cid, "tag": tag, "lines": []}
            found.append(current)
        elif current is not None:
            current["lines"].append(line)
    out = []
    for c in found:
        lines = c["lines"]
        while lines and not lines[-1].strip():
            lines.pop()
        while lines and not lines[0].strip():
            lines.pop(0)
        command = None
        if c["tag"] == "command" and lines:
            m = COMMAND.match(lines[-1].strip())
            if m:
                command = m.group(1)
        out.append({"id": c["id"], "tag": c["tag"], "text": "\n".join(lines), "command": command})
    return out


def verification(body):
    lines = [l for l in section(body, "Verification") or []]
    commands = [l for l in lines if l.startswith("Command:")]
    walks = [i for i, l in enumerate(lines) if l.startswith("Walkthrough:")]
    if len(commands) + len(walks) != 1:
        return None
    if commands:
        m = COMMAND.match(commands[0].strip())
        return {"form": "command", "command": m.group(1)} if m else None
    i = walks[0]
    first = lines[i][len("Walkthrough:"):].strip()
    steps = ([first] if first else []) + lines[i + 1:]
    return {"form": "walkthrough", "steps": "\n".join(steps).strip()}


def old_pointer(body):
    m = OLD_POINTER.match((body or "").lstrip().split("\n", 1)[0])
    return m.group(1) if m else None


def migrate_command(spec, repo):
    here = Path(__file__).resolve()
    return f"python3 {here} migrate {spec}" + (f" --repo {repo}" if repo else "")


def parse(spec, issue, repo=None):
    body = issue.get("body") or ""
    path = old_pointer(body)
    if path:
        raise NotASpec(
            f"#{spec} points at {path}, a Spec anchored to a file under the old contract; "
            f"bring it back into the issue with: {migrate_command(spec, repo)}"
        )
    fields = header_fields(body)
    status = fields.get("Status")
    if status is None:
        raise NotASpec(f"#{spec} carries no **Status:** line above its first section, so it is not a Spec")
    if status not in STATUSES:
        raise NotASpec(f"#{spec} is at Status {status!r}, which is not one of {', '.join(STATUSES)}")
    return {
        "spec": spec,
        "title": issue.get("title"),
        "state": (issue.get("state") or "").upper(),
        "status": status,
        "critique": fields.get("Critique"),
        "landed": fields.get("Landed"),
        "criteria": criteria(body, spec),
        "verification": verification(body),
    }


def with_header(body, name, value):
    head, rest = split_header(body)
    fields = {}
    other = []
    for line in head:
        m = HEADER_LINE.match(line)
        if m:
            fields[m.group(1)] = m.group(2)
        elif line.strip():
            other.append(line)
    fields[name] = value
    ordered = [f"**{k}:** {fields[k]}" for k in HEADER_ORDER if k in fields]
    # Anything else above the first section is kept, below the header lines.
    new_head = ordered + ([""] + other if other else [])
    return "\n".join(new_head + ([""] if rest else []) + rest)


def write(spec, repo, body):
    gh("issue", "edit", str(spec), "--body-file", "-", *repo_args(repo), stdin=body)
    back = fetch(spec, repo).get("body") or ""
    if back.rstrip("\n") != body.rstrip("\n"):
        raise NotASpec(f"#{spec}: the edit did not read back; the body on GitHub is not what was written")


def cmd_read(spec, repo):
    print(json.dumps(parse(spec, fetch(spec, repo), repo)))


def migrated(content):
    """The file's content as a body: no `# title`, no `**Tracker:**`, nothing else changed."""
    head, rest = split_header(content)
    head = [l for l in head if not l.startswith("# ") and not l.startswith("**Tracker:**")]
    while head and not head[0].strip():
        head.pop(0)
    return "\n".join(head + rest)


def cmd_migrate(spec, repo):
    issue = fetch(spec, repo)
    body = issue.get("body") or ""
    path = old_pointer(body)
    if not path:
        parse(spec, issue, repo)
        print(f"#{spec} is already a Spec in its issue (unchanged)")
        return
    # The contents API reads the default branch when no ref is given, which is
    # where an anchored Spec file lived, and needs no local clone of that repo.
    target = f"repos/{repo}" if repo else "repos/{owner}/{repo}"
    try:
        content = gh("api", f"{target}/contents/{path}", "-H", "Accept: application/vnd.github.raw")
    except GhError as exc:
        if "404" in str(exc):
            raise NotASpec(f"#{spec} points at {path}, which is not on the default branch; nothing to migrate")
        raise
    new = migrated(content)
    slices = [l for l in section(body, "Slices") or []]
    if any(l.strip() for l in slices):
        while slices and not slices[0].strip():
            slices.pop(0)
        new = new.rstrip("\n") + "\n\n## Slices\n\n" + "\n".join(slices).rstrip("\n") + "\n"
    try:
        parse(spec, {"body": new}, repo)
    except NotASpec as exc:
        raise NotASpec(f"{path} does not read as a Spec, so the body was left alone: {exc}")
    write(spec, repo, new)
    print(f"#{spec} migrated from {path}; nothing reads the file any more, and it can be deleted")


def cmd_set_status(spec, repo, status):
    if status not in STATUSES:
        raise NotASpec(f"{status!r} is not a Status; one of {', '.join(STATUSES)}")
    issue = fetch(spec, repo)
    current = parse(spec, issue)["status"]
    if current == status:
        print(f"#{spec} Status: {status} (unchanged)")
        return
    if (current, status) not in ALLOWED:
        raise NotASpec(f"#{spec} is at {current}; {current} → {status} is not a transition CONTRACTS.md allows")
    write(spec, repo, with_header(issue["body"], "Status", status))
    print(f"#{spec} Status: {current} → {status}")


def cmd_header(spec, repo, which, text):
    names = {"critique": "Critique", "landed": "Landed"}
    if which not in names or not text.strip():
        raise NotASpec("header takes critique or landed, and the line's text")
    issue = fetch(spec, repo)
    parse(spec, issue)
    write(spec, repo, with_header(issue["body"], names[which], text.strip()))
    print(f"#{spec} {names[which]}: {text.strip()}")


def cmd_list(repo, status):
    if status not in STATUSES:
        raise NotASpec(f"{status!r} is not a Status; one of {', '.join(STATUSES)}")
    # Search narrows the candidates; the parse decides, because search ignores
    # the markdown and matches the phrase anywhere in a body.
    hits = json.loads(gh(
        "issue", "list", "--state", "all", "--search", f'"Status: {status}" in:body',
        "--limit", "1000", "--json", "number,title,state,body", *repo_args(repo),
    ))
    out = []
    for hit in sorted(hits, key=lambda h: h["number"]):
        try:
            if parse(hit["number"], hit)["status"] == status:
                out.append({"number": hit["number"], "title": hit["title"], "state": hit["state"].upper()})
        except NotASpec:
            continue
    print(json.dumps(out))


def usage():
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


def main(argv):
    repo = None
    if "--repo" in argv:
        i = argv.index("--repo")
        if i + 1 >= len(argv):
            return usage()
        repo = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if not argv:
        return usage()
    cmd, rest = argv[0], argv[1:]
    try:
        if cmd == "list":
            if len(rest) != 2 or rest[0] != "--status":
                return usage()
            cmd_list(repo, rest[1])
            return 0
        if not rest or not rest[0].lstrip("#").isdigit():
            return usage()
        spec = int(rest[0].lstrip("#"))
        if cmd == "read" and len(rest) == 1:
            cmd_read(spec, repo)
        elif cmd == "set-status" and len(rest) == 2:
            cmd_set_status(spec, repo, rest[1])
        elif cmd == "migrate" and len(rest) == 1:
            cmd_migrate(spec, repo)
        elif cmd == "header" and len(rest) == 3:
            cmd_header(spec, repo, rest[1], rest[2])
        else:
            return usage()
    except NotASpec as exc:
        print(f"✘ {exc}", file=sys.stderr)
        return 1
    except (GhError, json.JSONDecodeError, KeyError) as exc:
        print(f"✘ cannot reach the Spec issue: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

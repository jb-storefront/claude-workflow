#!/usr/bin/env python3
"""Drop Claude Code's plugin-install records for worktrees that no longer exist.

Usage: prune-plugin-entries.py <worktree path>...

Every session that starts in a worktree records a project- or local-scope
install for each plugin the repo enables, keyed by that worktree's path.
Removing the worktree does not remove the records, and there is no CLI to do
it: `claude plugin uninstall --scope project` has to run inside the project,
which is gone. Left alone they pile up, a few per plugin per Slice, until
`claude plugin list` is hundreds of lines of directories nobody can open.

Only paths that are already gone are pruned. A path still on disk is refused
outright, because its records are live and its sessions may be reading them.
"""

import json
import os
import sys
import tempfile
from pathlib import Path


def records_file():
    config = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    return Path(config) / "plugins" / "installed_plugins.json"


def main(argv):
    if not argv:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2

    targets = {os.path.normpath(os.path.abspath(p)) for p in argv}
    live = sorted(p for p in targets if os.path.lexists(p))
    if live:
        for p in live:
            print(f"✘ {p} is still on disk; remove the worktree first", file=sys.stderr)
        return 1

    f = records_file()
    if not f.is_file():
        print(f"nothing to prune: {f} does not exist")
        return 0

    data = json.loads(f.read_text(encoding="utf-8"))
    plugins = data.get("plugins", {})
    removed = []
    for plugin in list(plugins):
        kept = []
        for e in plugins[plugin]:
            path = e.get("projectPath")
            if path and os.path.normpath(path) in targets:
                removed.append((plugin, e.get("scope"), e.get("version"), path))
            else:
                kept.append(e)
        if kept:
            plugins[plugin] = kept
        else:
            del plugins[plugin]

    if not removed:
        print("nothing to prune: no plugin records for " + ", ".join(sorted(targets)))
        return 0

    # Claude Code rewrites this file itself, so a reader must never see half of ours.
    fd, tmp = tempfile.mkstemp(dir=f.parent, prefix=f.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out, indent=2)
            out.write("\n")
        os.chmod(tmp, f.stat().st_mode & 0o777)
        os.replace(tmp, f)
    except BaseException:
        os.unlink(tmp)
        raise

    for plugin, scope, version, path in removed:
        print(f"pruned {plugin} ({scope}, {version}) for {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

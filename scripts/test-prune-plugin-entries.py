#!/usr/bin/env python3
"""Cases for prune-plugin-entries.py.

The file it edits is Claude Code's record of every plugin install on the
machine, so the cases that matter most are the ones where it must leave an
entry alone: a worktree still on disk, a different path that shares a prefix,
a user-scope install with no path at all.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PRUNER = Path(__file__).with_name("prune-plugin-entries.py")


def entry(path=None, scope="project", version="1.0.0"):
    e = {"scope": scope, "installPath": "/cache/x", "version": version}
    if path is not None:
        e["projectPath"] = str(path)
    return e


def run_pruner(config, *paths):
    env = {**os.environ, "CLAUDE_CONFIG_DIR": str(config)}
    return subprocess.run(
        [sys.executable, str(PRUNER), *map(str, paths)],
        capture_output=True,
        text=True,
        env=env,
    )


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


def setup(root, plugins):
    config = root / "config"
    (config / "plugins").mkdir(parents=True)
    f = config / "plugins" / "installed_plugins.json"
    f.write_text(json.dumps({"version": 2, "plugins": plugins}, indent=2))
    return config, f


def load(f):
    return json.loads(f.read_text())["plugins"]


def removes_gone_worktree(root):
    gone = root / "repo" / ".claude" / "worktrees" / "issue-1"
    keep = root / "repo"
    keep.mkdir()
    config, f = setup(root, {
        "a@m": [entry(scope="user"), entry(keep), entry(gone)],
        "b@m": [entry(gone, scope="local")],
    })
    proc = run_pruner(config, gone)
    if proc.returncode != 0:
        return False, f"exit {proc.returncode}: {proc.stderr.strip()}"
    p = load(f)
    if [e.get("projectPath") for e in p["a@m"]] != [None, str(keep)]:
        return False, f"a@m left as {p['a@m']}"
    if p.get("b@m"):
        return False, f"b@m still has {p['b@m']}"
    return True, ""


def refuses_path_on_disk(root):
    live = root / "repo" / ".claude" / "worktrees" / "issue-2"
    live.mkdir(parents=True)
    config, f = setup(root, {"a@m": [entry(live)]})
    before = f.read_text()
    proc = run_pruner(config, live)
    if proc.returncode == 0:
        return False, "exited 0 for a path that still exists"
    if f.read_text() != before:
        return False, "edited the file for a path that still exists"
    return True, ""


def exact_match_only(root):
    gone = root / "wt" / "issue-1"
    sibling = root / "wt" / "issue-12"
    config, f = setup(root, {"a@m": [entry(gone), entry(sibling)]})
    run_pruner(config, gone)
    left = [e["projectPath"] for e in load(f)["a@m"]]
    if left != [str(sibling)]:
        return False, f"left {left}, expected only the sibling"
    return True, ""


def trailing_slash_matches(root):
    gone = root / "wt" / "issue-3"
    config, f = setup(root, {"a@m": [entry(gone)]})
    run_pruner(config, str(gone) + "/")
    if load(f).get("a@m"):
        return False, "a trailing slash on the argument stopped the match"
    return True, ""


def nothing_to_do_leaves_file(root):
    gone = root / "wt" / "issue-4"
    config, f = setup(root, {"a@m": [entry(scope="user")]})
    before_bytes, before_mtime = f.read_bytes(), f.stat().st_mtime_ns
    proc = run_pruner(config, gone)
    if proc.returncode != 0:
        return False, f"exit {proc.returncode} with nothing to prune"
    if f.read_bytes() != before_bytes or f.stat().st_mtime_ns != before_mtime:
        return False, "rewrote the file with nothing to prune"
    return True, ""


def missing_file_is_fine(root):
    config = root / "config"
    config.mkdir()
    proc = run_pruner(config, root / "wt" / "issue-5")
    if proc.returncode != 0:
        return False, f"exit {proc.returncode} with no installed_plugins.json"
    return True, ""


def keeps_other_top_level_keys(root):
    gone = root / "wt" / "issue-6"
    config, f = setup(root, {"a@m": [entry(gone)]})
    data = json.loads(f.read_text())
    data["future"] = {"x": 1}
    f.write_text(json.dumps(data))
    run_pruner(config, gone)
    after = json.loads(f.read_text())
    if after.get("version") != 2 or after.get("future") != {"x": 1}:
        return False, f"top-level keys changed: {sorted(after)}"
    return True, ""


CASES = [
    ("removes every plugin's entry for a gone worktree", removes_gone_worktree),
    ("refuses a path still on disk", refuses_path_on_disk),
    ("issue-1 does not match issue-12", exact_match_only),
    ("trailing slash still matches", trailing_slash_matches),
    ("nothing to prune leaves the file untouched", nothing_to_do_leaves_file),
    ("no installed_plugins.json is not an error", missing_file_is_fine),
    ("keys it does not know survive", keeps_other_top_level_keys),
]


def main():
    if not PRUNER.is_file():
        print(f"✘ {PRUNER} is missing")
        return 1
    bad = [label for label, check in CASES if not case(label, check)]
    if bad:
        print(f"✘ {len(bad)} of {len(CASES)} prune cases behaved unexpectedly")
        return 1
    print(f"✔ {len(CASES)} prune cases behave as specified")
    return 0


if __name__ == "__main__":
    sys.exit(main())

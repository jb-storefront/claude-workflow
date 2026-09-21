# Specs live in the repo; the tracker issue is only the handle

`to-spec` publishes a spec to the issue tracker, and that issue closes when the last slice merges, so
the spec does not outlive the feature and nothing can detect the code drifting from it. We anchor
every Spec as `docs/specs/{issue}-{slug}.md` on the default branch, with a Status line, and keep the
Spec issue as the handle for labels, assignment, task lists, and closing references. The file wins
on conflict. The alternative, one place on GitHub, was simpler to run but left `finalize-pr` with
nothing a diff could touch.

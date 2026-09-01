# AI-debris pattern catalog

Patterns that signal an AI agent overshot the task or worked around the absence of real context. Use this catalog during step 10 of `/finalize-pr`. Each entry: what to look for in the diff, why it's a flag, severity.

---

## Unrequested defensive code
- **Look for:** `try/catch` around operations that cannot throw under the call contract; null/undefined checks on internal values already typed as non-nullable; "defensive" `if (typeof x === 'string')` for parameters already typed.
- **Why:** Trust internal code and framework guarantees. Defensive code at non-boundary points adds noise and hides real bugs.
- **Severity:** Not blocking (unless it masks errors that should surface).

## Backwards-compat shims for unused code paths
- **Look for:** re-exports, aliased names, `// kept for compatibility` comments, optional parameters preserved "in case anyone is still calling it" when the change is internal.
- **Why:** Internal refactors don't need migration scaffolding. Trust the codebase to be greppable.
- **Severity:** Blocking — these decay quickly and signal the agent doesn't trust its own change.

## Tautological comments
- **Look for:** `// fetches the user` above `function fetchUser()`; `// loop over items` above a `for` loop; JSDoc that restates parameter names without adding semantics.
- **Why:** Comments should explain *why* something non-obvious is true, not *what* well-named code already says.
- **Severity:** Not blocking, but always remove.

## Stray TODO/FIXME without a tracking issue
- **Look for:** `// TODO`, `// FIXME`, `// HACK` added in this PR with no linked issue or follow-up.
- **Why:** These rot. If the work matters, file an issue; if it doesn't, delete the comment.
- **Severity:** Not blocking; ask the author to either remove or link to an issue.

## Premature abstractions
- **Look for:** a new helper with exactly one caller; an interface with one implementation; a generic that's never reused; a "registry" pattern with two entries.
- **Why:** Three similar lines is better than one wrong abstraction. Abstract on the third occurrence, not the first.
- **Severity:** Blocking when the abstraction shapes future code; otherwise not blocking.

## Mock-only tests
- **Look for:** test files where the asserts target mock call counts (`expect(mock).toHaveBeenCalledWith…`) and not observable behavior; tests that pass because the implementation calls the mock the agent set up.
- **Why:** Aligns with `~/.claude/skills/tdd/tests.md` — tests should exercise public interfaces and survive refactors. Mock-shape assertions test implementation, not behavior.
- **Severity:** Blocking — these tests give false confidence.

## `.skip` / `.only` / `xfail` markers added in this PR
- **Look for:** `it.skip`, `it.only`, `describe.skip`, `test.only`, `@pytest.mark.skip`, `@pytest.mark.xfail` introduced by the diff.
- **Why:** Either a test that was supposed to pass is being silenced, or focus-only mode leaked from local debugging.
- **Severity:** Blocking unless the skip has an explicit "remove after X" condition recorded in the issue.

## Scope creep
- **Look for:** files modified outside the slice's stated domain (inferred from the issue body, `## References for context`, and the slice's title); incidental refactors of code the slice doesn't touch.
- **Why:** Slice PRs should be reviewable against a single acceptance contract. Drive-by changes belong in their own slice.
- **Severity:** Blocking — even if the changes are correct, they bloat the review and tangle history.

## Modified context files without justification
- **Look for:** files listed under `## References for context` in the issue body that the diff modifies. These are usually read-only inputs.
- **Why:** Context files (`CONTEXT.md`, area `CLAUDE.md`, ADRs) define the language of the area. Modifying them as a side effect of a slice often means the slice's premise changed without the issue being updated.
- **Severity:** Blocking — either update the issue to reflect the new contract or revert the context change.

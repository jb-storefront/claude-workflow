#!/usr/bin/env python3
"""Cases for clean-predicate.py, one JSON snapshot per case.

The fixtures under fixtures/clean-predicate encode what GitHub was seen to do
on gr4ce #447: the timeline names the requested reviewer `Copilot`, the review
arrives authored by `copilot-pull-request-reviewer[bot]` with state COMMENTED
and commit_id equal to head, and the reviewer request list is already empty
while the pass is still on its way.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
PREDICATE = HERE / "clean-predicate.py"
FIXTURES = HERE / "fixtures" / "clean-predicate"
REPO = HERE.parent


def judge(fixture):
    proc = subprocess.run(
        [sys.executable, str(PREDICATE), str(FIXTURES / f"{fixture}.json")],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(f"exit {proc.returncode}: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def kinds(result):
    return [r["kind"] for r in result["reasons"]]


def expect(result, state, *reason_kinds):
    if result["state"] != state:
        return False, f"state {result['state']!r}, expected {state!r} ({result['reasons']})"
    if sorted(kinds(result)) != sorted(reason_kinds):
        return False, f"reasons {kinds(result)}, expected {list(reason_kinds)}"
    return True, ""


def reason(result, kind):
    return next(r for r in result["reasons"] if r["kind"] == kind)


def c1_clean(_):
    return expect(judge("clean"), "clean")


def c2_pending_after_request(_):
    return expect(judge("pending-after-request"), "pending", "copilot-pass-pending")


def c3_stale_pass(_):
    r = judge("stale-pass")
    ok, why = expect(r, "not-clean", "stale-copilot-pass")
    if not ok:
        return ok, why
    snapshot = json.loads((FIXTURES / "stale-pass.json").read_text())
    stale = reason(r, "stale-copilot-pass")
    if stale.get("commit") != snapshot["reviews"][0]["commit_id"]:
        return False, f"stale reason names commit {stale.get('commit')!r}"
    return True, ""


def c4_unresolved_copilot_thread(_):
    r = judge("unresolved-copilot-thread")
    ok, why = expect(r, "not-clean", "unresolved-copilot-thread")
    if not ok:
        return ok, why
    if reason(r, "unresolved-copilot-thread").get("thread", {}).get("id") != "PRRT_copilot1":
        return False, f"reason does not name the thread: {r['reasons']}"
    return True, ""


def c5_unresolved_human_thread(_):
    r = judge("unresolved-human-thread")
    ok, why = expect(r, "not-clean", "unresolved-human-thread")
    if not ok:
        return ok, why
    if reason(r, "unresolved-human-thread").get("thread", {}).get("id") != "PRRT_human1":
        return False, f"reason does not name the thread: {r['reasons']}"
    return True, ""


def c6_failing_check(_):
    r = judge("failing-check")
    ok, why = expect(r, "not-clean", "failing-check")
    if not ok:
        return ok, why
    if reason(r, "failing-check").get("check") != "validate":
        return False, f"reason does not name the check: {r['reasons']}"
    return True, ""


def c7_pending_check(_):
    r = judge("pending-check")
    ok, why = expect(r, "pending", "pending-check")
    if not ok:
        return ok, why
    if reason(r, "pending-check").get("check") != "validate":
        return False, f"reason does not name the check: {r['reasons']}"
    return True, ""


def c8_no_pass_ever(_):
    return expect(judge("no-pass-ever"), "not-clean", "no-copilot-pass")


def c9_resolved_earlier_thread(_):
    return expect(judge("resolved-earlier-thread"), "clean")


def c10_both_logins_are_copilot(_):
    # The request names `Copilot`: were it not recognised, this would be no-copilot-pass.
    ok, why = expect(judge("pending-after-request"), "pending", "copilot-pass-pending")
    if not ok:
        return False, f"request naming Copilot: {why}"
    # The review is by the [bot] login: were it not recognised, this would not be clean.
    ok, why = expect(judge("clean"), "clean")
    if not ok:
        return False, f"review by copilot-pull-request-reviewer[bot]: {why}"
    # Thread authors come back from GraphQL without the [bot] suffix.
    ok, why = expect(judge("unresolved-copilot-thread"), "not-clean", "unresolved-copilot-thread")
    if not ok:
        return False, f"thread by copilot-pull-request-reviewer: {why}"
    return True, ""


def c11_runs_in_validate(_):
    validate = (REPO / "scripts" / "validate.sh").read_text()
    if not re.search(r"^[^#\n]*python3 scripts/test-clean-predicate\.py", validate, re.M):
        return False, "scripts/validate.sh does not run scripts/test-clean-predicate.py"
    return True, ""


def c12_context_defines_copilot_pass(_):
    context = (REPO / "CONTEXT.md").read_text()
    m = re.search(r"^\*\*Copilot pass\*\*:\n(.+)$", context, re.M)
    if not m or not m.group(1).strip():
        return False, "CONTEXT.md has no **Copilot pass** definition"
    return True, ""


CASES = [
    ("#52 C1 latest Copilot pass on head, no open threads, checks green is clean", c1_clean),
    ("#52 C2 right after a Copilot request with an empty request list is pending", c2_pending_after_request),
    ("#52 C3 latest Copilot pass on an earlier commit, no later request, is not-clean as stale", c3_stale_pass),
    ("#52 C4 an unresolved Copilot thread is not-clean and named", c4_unresolved_copilot_thread),
    ("#52 C5 an unresolved human thread is not-clean and named as human", c5_unresolved_human_thread),
    ("#52 C6 a failing check is not-clean and named", c6_failing_check),
    ("#52 C7 a running check beside a clean Copilot pass is pending and named", c7_pending_check),
    ("#52 C8 no Copilot pass and no request ever is not-clean as no-pass", c8_no_pass_ever),
    ("#52 C9 a resolved thread from an earlier pass beside a clean latest pass is clean", c9_resolved_earlier_thread),
    ("#52 C10 Copilot and copilot-pull-request-reviewer[bot] both count as Copilot", c10_both_logins_are_copilot),
    ("#52 C11 the validate script runs these cases", c11_runs_in_validate),
    ("#52 C12 CONTEXT.md defines Copilot pass", c12_context_defines_copilot_pass),
]


def case(label, check):
    try:
        ok, why = check(None)
    except Exception as exc:  # a crash is a failed case, not a crashed suite
        ok, why = False, f"raised {exc!r}"
    print(f"  {'ok ' if ok else 'BAD'}  {label}" + ("" if ok else f": {why}"))
    return ok


def main():
    bad = [label for label, check in CASES if not case(label, check)]
    if bad:
        print(f"✘ {len(bad)} of {len(CASES)} clean-predicate cases behaved unexpectedly")
        return 1
    print(f"✔ {len(CASES)} clean-predicate cases behave as specified")
    return 0


if __name__ == "__main__":
    sys.exit(main())

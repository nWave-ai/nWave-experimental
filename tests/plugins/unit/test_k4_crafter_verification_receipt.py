"""Crafter terminal evidence is one CRAFTER-RESULT, never a second receipt."""

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
AUTO = ROOT / "nWave/skills/nw-auto/SKILL.md"
CRAFTERS = (
    ROOT / "nWave/agents/nw-software-crafter.md",
    ROOT / "nWave/agents/nw-functional-software-crafter.md",
)
RESULT_FIELDS = (
    "verdict",
    "contract",
    "candidate",
    "oracle",
    "first-production-mutation-tool-call",
    "changed-targets",
    "verification",
    "residuals",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _crafter_result(path: Path) -> str:
    body = _text(path)
    return body[body.index("## Terminal Result") : body.index("## Constraints")]


#: Matched by step TEXT, not its leading digit -- fa7d9730a's compile-
#: contract insertion already renumbered these once (3->4, 4->5); a
#: literal "3."/"4." pin breaks on the next insertion too.
_VALIDATE_CHARTER_STEP = re.compile(r"^\d+\. Validate the charter", re.MULTILINE)
_FINALIZE_STEP = re.compile(r"^\d+\. Invoke the `nw-finalize`", re.MULTILINE)


def _step_index(pattern: re.Pattern[str], body: str) -> int:
    match = pattern.search(body)
    assert match is not None, f"step matching {pattern.pattern!r} not found"
    return match.start()


def _auto_join() -> str:
    """The route step that dispatches the crafter and reads its
    `CRAFTER-RESULT`, up to (not including) the finalize step."""
    body = _text(AUTO)
    return body[
        _step_index(_VALIDATE_CHARTER_STEP, body) : _step_index(_FINALIZE_STEP, body)
    ]


def _route_boundaries() -> str:
    body = _text(AUTO)
    return body[body.index("## Route boundaries") :]


@pytest.mark.parametrize("crafter", CRAFTERS, ids=("oo", "fp"))
def test_both_crafters_emit_the_same_terminal_result(crafter: Path) -> None:
    result = _crafter_result(crafter)
    assert "CRAFTER-RESULT" in result
    for field in RESULT_FIELDS:
        assert f"{field}:" in result
    assert "terminal green verification" in result
    assert "Missing, stale or nonterminal evidence is `INDETERMINATE`" in result


def test_auto_validates_result_identity_scope_and_commands_before_examiner() -> None:
    body = _text(AUTO)
    join = " ".join(_auto_join().split())
    assert _step_index(_VALIDATE_CHARTER_STEP, body) < _step_index(_FINALIZE_STEP, body)
    assert "terminal `CRAFTER-RESULT`" in join
    for obligation in (
        "matching contract",
        "opaque candidate identity",
        "oracle, changed targets, first-mutation bound",
        "terminal zero-exit results for every declared verification command",
    ):
        assert obligation in join
    assert join.index("Require terminal `CRAFTER-RESULT`") < join.index(
        "dispatch one source-blind Vera pass"
    )


def test_bad_result_is_non_pass_and_has_no_substitute_or_repair() -> None:
    join = " ".join(_auto_join().split())
    assert "A PASS opens the single-writer causal window" in join
    assert (
        "no actor may mutate production targets, contract, oracle or charters" in join
    )
    boundaries = " ".join(_route_boundaries().split())
    assert "each individual Agent result is terminal" in boundaries
    assert "no retry/resume/`SendMessage` correction" in boundaries
    assert "stop, report blocker (no silent substitution)" in boundaries


def test_retired_mini_receipt_does_not_survive_the_join() -> None:
    join = _auto_join()
    for retired in ("outcome: PASS|FAIL", "`argv`", "`scope`", "`exit_code`"):
        assert retired not in join
    body = _text(AUTO)
    finalize_section = body[_step_index(_FINALIZE_STEP, body) :]
    assert "create no receipt, ledger or progress artifact" in finalize_section

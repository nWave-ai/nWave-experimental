"""Regression (GDP-3/GDP-4): the carpaccio slice gate's PLAIN AT-review
rejection must carry a HOW naming the producing tool, not ONLY a bare
``{reason, error}`` token.

Charter: ``docs/product/expectations/fix-carpaccio-at-review-rejection-self-
explains/the-plain-at-review-rejection-names-how-to-produce-the-evidence.md``.

Found in ``src/des/cli/carpaccio_format.py`` ``_at_review_rejection(reason,
slice_id)`` (line 829): it builds ``{"reason": reason, "error": f"AT-review
gate rejected slice {slice_id}: {reason}"}`` with NO ``how`` field and no
producing-tool name. This is the PLAIN path every ``at_kind="gherkin"``
(default) call in ``carpaccio_slice_gate.py`` hits directly via
``_check_verdict_record`` -- record-presence / non-APPROVED / stale-AT-set /
stale-content-hash. (Contrast the sibling ``_no_scenarios_rejection``, which
IS self-describing, and the ``at_kind="pytest-regression"`` path, which is
ALREADY enriched via ``_with_mechanical_remedy`` -- this AT targets the
unenriched Gherkin/default path.)

Driving surface (Mandate-13 driving-port-only, Layer 3 composition,
IN-PROCESS default): the REAL ``des.cli.carpaccio_slice_gate.main()`` CLI
driver, captured via ``capsys`` -- same pattern as
``tests/des/unit/cli/test_carpaccio_mechanical_seal.py`` (the pytest-
regression sibling suite covering the ALREADY-enriched path) and
``tests/bugs/des/test_gate_g_verdict_self_explains_how_and_human_surface.py``
(the GDP-3 sibling regression AT this one mirrors).

Fixture shape reused verbatim from
``tests/scripts/cli/atdd_pure_carpaccio_slice_gate/steps/composition.py``
(``_build_valid_in_size`` / ``_provision_no_record`` / ``_provision_approved_
valid``): a ``[REF] Slice Plan`` feature-delta row + a legacy-dir ``.feature``
file with one tagged scenario -- the same slice-plan/AT-discovery mechanism
this AT patches the REJECTION OUTPUT of, not the mechanism itself.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from des.cli.carpaccio_slice_gate import main as carpaccio_gate_main


_FEATURE_ID = "carpaccio-at-review-how-fixture"
_ENTERING_SLICE = "slice-01"

_SCENARIO_BODY = (
    "given a fixture precondition\n"
    "when the fixture action occurs\n"
    "then the fixture outcome holds"
)


def _feature_dir(repo: Path) -> Path:
    return repo / "docs" / "feature" / _FEATURE_ID


def _acceptance_dir(repo: Path) -> Path:
    # Legacy feature-scoped acceptance dir (feature_at_files._legacy_acceptance_dir):
    # a `.feature` file here binds to the feature with NO file-level `@feature-`
    # tag required.
    return repo / "tests" / "scripts" / "cli" / _FEATURE_ID / "acceptance"


def _ledger_path(repo: Path) -> Path:
    return repo / ".nwave" / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"


def _make_repo(tmp_path: Path) -> Path:
    """A repo with a valid, in-size slice plan + a matching tagged `.feature`
    file for ``slice-01`` -- clears carpaccio assertions 1-4 so `check_at_review`
    (assertion 5) is the ONLY thing left to decide the verdict."""
    repo = tmp_path / "repo"
    feature_dir = _feature_dir(repo)
    feature_dir.mkdir(parents=True)
    feature_dir.joinpath("feature-delta.md").write_text(
        "# Feature Delta: carpaccio AT-review how fixture\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        "| slice-01 | Operator previews a plan | pending | @walking-skeleton | "
        "thinnest end-to-end vertical |\n",
        encoding="utf-8",
    )
    acceptance_dir = _acceptance_dir(repo)
    acceptance_dir.mkdir(parents=True)
    acceptance_dir.joinpath("slice.feature").write_text(
        "Feature: carpaccio AT-review how fixture\n\n"
        "@slice-01\n"
        "Scenario: fixture scenario 1\n"
        "  Given a fixture precondition\n"
        "  When the fixture action occurs\n"
        "  Then the fixture outcome holds\n",
        encoding="utf-8",
    )
    return repo


def _write_approved_verdict(repo: Path) -> None:
    """Mint a valid APPROVED ATReviewVerdict for `slice-01` -- the record-set
    and content-hash exactly matching the single scenario `_make_repo` wrote,
    so `check_at_review` clears without hitting ANY rejection reason."""
    ledger_path = _ledger_path(repo)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": "ATReviewVerdict",
        "schema_version": "1.0.0",
        "slice_id": _ENTERING_SLICE,
        "verdict": "APPROVED",
        "reviewer_agent_id": "nw-acceptance-designer-reviewer",
        "at_ids": ["AT-1"],
        "at_content_hash": hashlib.sha256(_SCENARIO_BODY.encode("utf-8")).hexdigest(),
        "timestamp": "2026-07-07T00:00:00Z",
        "findings_summary": [],
    }
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _run_gate(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    """Drive the REAL `des carpaccio-slice-gate` CLI (`main()`) in-process,
    default `at_kind="gherkin"` -- the PLAIN, unenriched rejection path."""
    exit_code = carpaccio_gate_main(
        [
            "--feature-id",
            _FEATURE_ID,
            "--entering-slice",
            _ENTERING_SLICE,
            "--repo-root",
            str(repo),
        ]
    )
    stdout = capsys.readouterr().out
    payload: dict[str, object] = next(
        (
            json.loads(line)
            for line in stdout.splitlines()
            if line.strip().startswith("{")
        ),
        {},
    )
    return exit_code, payload


def test_gherkin_at_review_rejection_names_a_how_routing_to_the_producing_tool(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """POSITIVE AT (active-RED today): a slice with NO ledger record at all
    hits `_check_verdict_record`'s `_at_review_rejection("absent", ...)` --
    the PLAIN path, never wrapped by `_with_mechanical_remedy` (that wrapper
    fires only for `at_kind="pytest-regression"`). The gate must STILL reject
    (the check stays intact -- exit 45, reason "absent") but the payload must
    additionally carry a `how` naming a concrete producing-tool command
    (`des record-at-review-verdict` and/or `des verify-red-green
    --record-red`). Today it emits ONLY `{event, slice_id, reason, error}` --
    no `how` key at all -- so this is RED for a semantic reason (the missing
    remediation), not a crash.
    """
    repo = _make_repo(tmp_path)
    # No ledger file is written at all -- `_latest_verdict_record` returns
    # None -- the record-presence reason ("absent").

    exit_code, payload = _run_gate(repo, capsys)

    # The check stays intact: the slice IS still rejected (exit 45).
    assert exit_code == 45, f"expected AT_REVIEW_NOT_APPROVED (45), got {payload!r}"
    assert payload.get("event") == "ATReviewGateRejected", payload
    assert payload.get("slice_id") == _ENTERING_SLICE, payload
    assert payload.get("reason") == "absent", payload

    # HOW -- the part that is MISSING today (RED for the right reason: a
    # semantic AssertionError naming the absent remediation, not a crash).
    # Today's bare payload is exactly {event, slice_id, reason, error} --
    # `payload.get("how")` is None.
    how = payload.get("how")
    assert isinstance(how, str) and how, (
        "the AT-review rejection must carry a 'how' naming a concrete "
        "producing-tool command (GDP-3/GDP-4) -- got a bare payload with no "
        f"'how' field at all: {payload!r}"
    )

    producing_tool_named = (
        "record-at-review-verdict" in how or "verify-red-green" in how
    )
    assert producing_tool_named, (
        "the 'how' must route to the producing tool -- either "
        "`des record-at-review-verdict --verdict APPROVED ...` (the "
        "reviewer-verdict path) or `des verify-red-green --record-red` (the "
        f"mechanical-seal path) -- got: {how!r}"
    )


@pytest.mark.negative_at
def test_slice_with_approved_verdict_never_raises_the_at_review_rejection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE AT (control -- green today, stays green after the fix): a
    slice carrying a valid, matching APPROVED AT-review record clears the
    gate outright (no rejection, no false positive). The 'how' remediation
    string must never leak into a cleared verdict's payload."""
    repo = _make_repo(tmp_path)
    _write_approved_verdict(repo)

    exit_code, payload = _run_gate(repo, capsys)

    assert exit_code == 0, f"a compliant slice must clear, got {payload!r}"
    assert payload.get("event") == "SliceCleared", payload
    assert payload.get("at_evidence") is None, (
        f"the gherkin path carries no at_evidence attestation label -- got {payload!r}"
    )

    payload_text = json.dumps(payload, sort_keys=True)
    assert "record-at-review-verdict" not in payload_text, payload
    assert "verify-red-green" not in payload_text, payload

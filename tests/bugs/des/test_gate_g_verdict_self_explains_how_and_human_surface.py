"""Regression (GDP-3): gate-G's FAIL/UNVERIFIED verdict must carry a HOW +
a human-readable surface line, not ONLY a raw ``{"verdict","diagnostic"}``
JSON blob.

Charter: ``docs/product/expectations/fix-gate-g-self-explains/
the-gate-g-verdict-carries-a-how-and-a-human-surface.md``.

Found in ``src/des/cli/gate_g.py`` (``_failed`` builds a diagnostic naming
WHAT diverged -- e.g. ``"ExampleTableRow 'empty-dataset' has no covering
scenario"`` -- with no HOW remediation, and ``main()`` prints that diagnostic
as the sole line of output, wrapped in JSON, with zero plain-text human
surface). The standing what/why/how rule (every failure explains WHAT, WHY,
HOW) is violated: an operator reading gate-G's FAIL output today sees WHICH
row is uncovered but no instruction for what to DO about it, and no
human-readable line at all -- only the raw JSON.

CRITICAL CONSTRAINT (asymmetric authority, preserved -- do NOT change):
gate-G intentionally exits 0 for EVERY verdict (PASS/FAIL/UNVERIFIED/
INDETERMINATE/NOT_APPLICABLE) -- it objects, it never authorizes; the
verdict TOKEN in the JSON payload carries the outcome, not the process exit
code (``main()``'s literal ``return 0`` at the end, unconditional on
``envelope.verdict``). Both ATs below pin ``exit_code == 0`` -- a fix that
makes gate-G exit non-zero on FAIL/UNVERIFIED would break this pin and must
be rejected.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition,
IN-PROCESS default): the REAL ``des.cli.gate_g.main()`` CLI driver -- the
thin wrapper over ``evaluate_gate_g`` that owns stdout printing -- captured
via ``capsys``, same pattern as
``tests/bugs/des/test_verify_red_green_how_message_junit_out_placeholder.py``.
No subprocess fork; the entry point + composition-root driving port is
``main(argv)`` itself.

Fixture shape reused verbatim from the proven, GREEN gate-G AT precedent
(``tests/des/acceptance/coherence_codefact/steps/composition_slice_03_gate_g.py``
``_render_design_contract`` / ``_render_at_feature``): a prose
``## Wave: DESIGN / [REF] Code-Design`` example-table in a ``feature-delta.md``
diffed against a Gherkin ``.feature`` AT module -- the same design↔AT
coherence mechanism GDP-3 patches the OUTPUT of, not the mechanism itself.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from des.cli.gate_g import main


_DESIGN_SECTION_HEADING = "## Wave: DESIGN / [REF] Code-Design"


def _render_design_contract(rows: tuple[str, ...]) -> str:
    """A feature-delta with a prose `[REF] Code-Design` example-table."""
    lines = [
        "# feature-delta f-export-csv (regression fixture)",
        "",
        _DESIGN_SECTION_HEADING,
        "",
        "Operation: `export_csv(rows: list[Row], *, bom: bool = False) -> bytes`",
        "",
        "| ExampleTableRow | Input | Output |",
        "|-----------------|-------|--------|",
    ]
    for row in rows:
        lines.append(f"| {row} | <input-{row}> | <output-{row}> |")
    lines.append("")
    return "\n".join(lines)


def _render_at_feature(scenarios: tuple[str, ...]) -> str:
    """A Gherkin AT `.feature` whose scenarios cover (a subset of) the rows."""
    lines = ["Feature: Operator exports a CSV", ""]
    for scenario in scenarios:
        lines.append(f"  Scenario: Operator exports the {scenario} case")
        lines.append(f"    Given the {scenario} dataset")
        lines.append("    When the operator exports a CSV")
        lines.append(f"    Then the {scenario} CSV is produced")
        lines.append("")
    return "\n".join(lines)


def _write_feature_root(
    tmp_path: Path, *, design_rows: tuple[str, ...], at_scenarios: tuple[str, ...]
) -> tuple[Path, Path]:
    """Write a real feature-root: a `feature-delta.md` + a real AT `.feature`
    module directory. Returns ``(design_contract_path, at_module_path)`` --
    the exact ``(design_contract_path, at_module_path)`` pair
    ``evaluate_gate_g`` / ``main`` accept."""
    root = tmp_path / "feature_under_diff"
    at_module_path = root / "tests" / "acceptance"
    at_module_path.mkdir(parents=True, exist_ok=True)
    design_contract_path = root / "feature-delta.md"
    design_contract_path.write_text(
        _render_design_contract(design_rows), encoding="utf-8"
    )
    (at_module_path / "export_csv.feature").write_text(
        _render_at_feature(at_scenarios), encoding="utf-8"
    )
    return design_contract_path, at_module_path


def _run_gate_g(
    capsys: pytest.CaptureFixture[str], design_contract_path: Path, at_module_path: Path
) -> tuple[int, dict[str, Any], str]:
    """Drive the REAL `des gate-design-at-coherence` CLI (`main()`) in-process.

    Returns ``(exit_code, json_payload, raw_stdout)`` so a Then can assert on
    the exit code, the parsed verdict envelope, AND the raw text surface
    (whether a human-readable line exists alongside the JSON).
    """
    exit_code = main(
        [
            "--design-contract",
            str(design_contract_path),
            "--at-module",
            str(at_module_path),
        ]
    )
    raw = capsys.readouterr().out
    payload: dict[str, Any] | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            payload = json.loads(stripped)
            break
    assert payload is not None, f"no JSON verdict line in gate-G stdout: {raw!r}"
    return exit_code, payload, raw


def test_fail_verdict_carries_a_how_and_a_human_readable_surface_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """POSITIVE AT (active-RED today): a design contract with a DROPPED row
    (an ExampleTableRow no AT scenario covers) makes gate-G return FAIL. The
    exit code must STAY 0 (asymmetric authority, pinned -- already true
    today). The diagnostic must name WHAT (the row) -- already true today --
    AND a concrete HOW (e.g. `author a scenario tagged @row:<row>`) -- this
    is the part that fails today, gate-G's `_failed()` emits WHAT only. The
    output must also carry >=1 human-readable line, not ONLY the raw JSON
    blob -- this also fails today (`main()` prints exactly one JSON line).
    """
    design_contract_path, at_module_path = _write_feature_root(
        tmp_path,
        design_rows=("full-dataset", "single-row", "empty-dataset"),
        at_scenarios=("full-dataset", "single-row"),  # "empty-dataset" DROPPED
    )

    exit_code, payload, raw = _run_gate_g(capsys, design_contract_path, at_module_path)

    # Asymmetric authority is preserved -- ALREADY PASSING today, and must
    # keep passing after the fix (the fix adds a HOW, it never flips this).
    assert exit_code == 0, (
        "gate-G must exit 0 for EVERY verdict (asymmetric authority: it "
        f"objects, it never authorizes) -- got exit_code={exit_code}"
    )
    assert payload["verdict"] == "fail", f"expected FAIL verdict, got {payload!r}"

    diagnostic = payload["diagnostic"]
    # WHAT -- already present today (this assertion already passes).
    assert "empty-dataset" in diagnostic, (
        f"the diagnostic must name the dropped ExampleTableRow -- got {diagnostic!r}"
    )

    # HOW -- the part that is MISSING today (RED for the right reason: a
    # semantic AssertionError naming the absent remediation, not a crash).
    how_present = "@row:" in diagnostic or "author a scenario" in diagnostic
    assert how_present, (
        "gate-G's FAIL diagnostic must carry a concrete, actionable HOW (e.g. "
        "'author a scenario tagged @row:<row>') alongside the mechanical "
        f"WHAT -- it names only the WHAT: {diagnostic!r}"
    )

    # Human-readable surface -- also MISSING today: main() prints ONLY the
    # raw JSON line, so no non-JSON line exists in stdout.
    human_lines = [
        line for line in raw.splitlines() if line.strip() and not line.startswith("{")
    ]
    assert human_lines, (
        "gate-G's FAIL/UNVERIFIED output must include >=1 human-readable "
        "surface line (a '✗'/plain-text line), not ONLY the raw JSON blob -- "
        f"stdout carried nothing but JSON: {raw!r}"
    )


@pytest.mark.negative_at
def test_pass_verdict_never_emits_a_spurious_row_remediation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE AT (control -- green today, stays green after the fix): a
    coherent design+AT set (every row covered) returns PASS. The exit code
    stays 0 (unchanged by the fix), and -- unlike the FAIL/UNVERIFIED case --
    the output must NOT emit a spurious HOW/`@row:` remediation: the HOW
    belongs only on FAIL/UNVERIFIED verdicts, never leaking into a PASS.
    """
    design_contract_path, at_module_path = _write_feature_root(
        tmp_path,
        design_rows=("full-dataset", "single-row", "empty-dataset"),
        at_scenarios=("full-dataset", "single-row", "empty-dataset"),  # bijective
    )

    exit_code, payload, raw = _run_gate_g(capsys, design_contract_path, at_module_path)

    assert exit_code == 0
    assert payload["verdict"] == "pass", f"expected PASS verdict, got {payload!r}"
    assert payload["diagnostic"] == ""

    assert "@row:" not in raw, (
        f"a PASS verdict must never emit a spurious `@row:` remediation: {raw!r}"
    )
    assert "author a scenario" not in raw, (
        f"a PASS verdict must never emit a spurious remediation instruction: {raw!r}"
    )

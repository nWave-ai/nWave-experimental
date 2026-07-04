"""evolution-plan P1.4 role projections — the observed proofs, pinned as regression.

`des feature-delta-schema project --role <role> --slice <slice-id> <file>` (P4
`project_for_role` in `src/des/cli/feature_delta_schema.py`) is the role-scoped
markdown projection over the ONE SSOT feature-delta.md. These tests ARE the
P1.4 done-currency, made permanent:

- B1 (positive): the crafter projection on a real-shaped feature-delta emits
  Value Statement + Definition of Done + Reuse Analysis + Design Decisions,
  and OMITS everything else (the Problem prose, the Test-Reuse section, the
  other slice's DoD bullet). The size ratio projection/full is reported.
- B2 (negative): the Reuse Analysis section is MANDATORY, NON-PROJECTABLE-AWAY
  for the crafter role. A malformed (unparseable) Reuse Analysis table makes
  the projector REFUSE loud (exit 2, what/why/how) rather than silently
  shipping a slim projection missing it.
- B3 (leanest): the examiner projection emits ONLY the value statement + the
  preamble spec-row refs — no DoD, no Reuse Analysis, no Design Decisions.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from des.cli.feature_delta_schema import main


if TYPE_CHECKING:
    from pathlib import Path


_WELL_FORMED_DELTA = """# Feature Delta — sandbox-demo

**Wave**: DESIGN (solution-architect) · **Mode**: propose · **Scope**: sandbox demo
**Backlog**: `docs/product/backlog.md` §F-SANDBOX-DEMO
**Design ADR**: ADR-SANDBOX-001

## Problem (F-SANDBOX-DEMO, Critical)

Some problem prose that must NOT leak into the crafter or examiner projection.
This paragraph is intentionally long-winded so a naive "include everything"
projector would visibly balloon the projection/full size ratio.

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|-------|-----------------|--------|------------|----------------|
| slice-01 | The user sees the sandbox flow complete end to end | pending | @walking-skeleton | first vertical |
| slice-02 | The user sees the second flow complete | pending | | |

## Wave: DISCUSS / [REF] Definition of Done

- The sandbox endpoint returns 200 (slice-01)
- The sandbox demo logs an audit event (slice-01)
- The sandbox dashboard renders the second flow (slice-02)

## Wave: DESIGN / [REF] Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Reuse the existing adapter | avoids a new module |

## Reuse Analysis

| Existing Component | File | Overlap | Decision | Justification |
|---|---|---|---|---|
| WidgetService | src/widget_service.py | already renders widgets | EXTEND | add the second-flow method |

## Test Reuse & Consolidation Analysis

| Existing Test/DSL-Step | File | Overlap | Decision | Justification |
|---|---|---|---|---|
| test_widget_render | tests/test_widget.py | already covers rendering | REUSE | import the step |
"""

#: Reuse Analysis header columns swapped (File, Existing Component, ...) — an
#: unparseable/malformed table per DDD-8's fixed-column contract.
_MALFORMED_REUSE_DELTA = _WELL_FORMED_DELTA.replace(
    "| Existing Component | File | Overlap | Decision | Justification |",
    "| File | Existing Component | Overlap | Decision | Justification |",
)


def _write(tmp_path: Path, content: str) -> Path:
    target = tmp_path / "feature-delta.md"
    target.write_text(content, encoding="utf-8")
    return target


def test_crafter_projection_carries_value_dod_reuse_decisions_and_omits_rest(
    tmp_path: Path, capsys: object
) -> None:
    """B1 positive: crafter gets Value+DoD+Reuse+Decisions, omits the rest."""
    target = _write(tmp_path, _WELL_FORMED_DELTA)

    exit_code = main(
        ["project", "--role", "crafter", "--slice", "slice-01", str(target)]
    )

    assert exit_code == 0
    out = capsys.readouterr().out  # type: ignore[attr-defined]

    # Present: value statement, DoD (slice-01 only), Reuse Analysis, Decisions.
    assert "The user sees the sandbox flow complete end to end" in out
    assert "sandbox endpoint returns 200 (slice-01)" in out
    assert "logs an audit event (slice-01)" in out
    assert "WidgetService" in out
    assert "Reuse the existing adapter" in out

    # Omitted: the Problem prose, the OTHER slice's DoD bullet, the Test-Reuse
    # section (not in the crafter role's contract).
    assert "problem prose" not in out
    assert "second flow complete" not in out or "renders the second flow" not in out
    assert "test_widget_render" not in out
    assert "Test Reuse & Consolidation Analysis" not in out

    # Size ratio projection/full is reported in the header.
    match = re.search(r"ratio=([0-9.]+)", out)
    assert match is not None, f"no size ratio reported in output: {out!r}"
    ratio = float(match.group(1))
    assert 0 < ratio < 1, f"expected a slimming ratio in (0,1); got {ratio}"


def test_crafter_projection_refuses_loud_on_malformed_reuse_analysis(
    tmp_path: Path, capsys: object
) -> None:
    """B2 negative: malformed Reuse Analysis -> exit 2, never a silent slim
    projection that drops the mandatory Reuse Analysis rows."""
    target = _write(tmp_path, _MALFORMED_REUSE_DELTA)

    exit_code = main(
        ["project", "--role", "crafter", "--slice", "slice-01", str(target)]
    )

    assert exit_code == 2
    err = capsys.readouterr().err  # type: ignore[attr-defined]
    assert "Reuse Analysis" in err
    assert "what=" in err and "why=" in err and "how=" in err
    assert "never be projected away" in err or "MANDATORY" in err


def test_examiner_projection_carries_only_value_statement_and_spec_refs(
    tmp_path: Path, capsys: object
) -> None:
    """B3 leanest: examiner gets ONLY value statement + spec refs."""
    target = _write(tmp_path, _WELL_FORMED_DELTA)

    exit_code = main(
        ["project", "--role", "examiner", "--slice", "slice-01", str(target)]
    )

    assert exit_code == 0
    out = capsys.readouterr().out  # type: ignore[attr-defined]

    assert "The user sees the sandbox flow complete end to end" in out
    assert "F-SANDBOX-DEMO" in out  # spec-row ref (Backlog line)
    assert "ADR-SANDBOX-001" in out  # spec-row ref (Design ADR line)

    assert "Definition of Done" not in out
    assert "Reuse Analysis" not in out
    assert "Design Decisions" not in out
    assert "problem prose" not in out

    match = re.search(r"ratio=([0-9.]+)", out)
    assert match is not None
    ratio = float(match.group(1))
    assert 0 < ratio < 1

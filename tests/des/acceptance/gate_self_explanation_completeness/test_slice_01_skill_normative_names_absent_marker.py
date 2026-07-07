"""Slice-01 AT (gate-self-explanation-completeness): skill_normative FAIL names
the absent marker text, WHY, HOW, and the skill file path -- not just
skill + clause-id.

Feature: gate-self-explanation-completeness (feature-delta slice-01;
docs/feature/gate-self-explanation-completeness/feature-delta.md).
Charter: docs/product/expectations/gate-self-explanation-completeness/
  slice-01-skill-normative-names-the-absent-marker.md

Layer: acceptance -- drives the REAL `des skill-normative-gate` CLI IN-PROCESS
through the real dispatcher (`des.cli.__main__.main`), the same Mandate-13
driving port the sibling skill_normative_content_gate feature already proved
out (L2 in-process default, `tests/common/in_process_cli.run_cli_in_process`).
No new SUT/test-infra class -- the feature-delta Reuse Analysis calls for
EXTENDing `FailingClause.render()` only; this AT is self-contained (builds its
own tmp manifest + tmp skill copy) rather than reaching into the sibling
feature's private `gate_steps` package, keeping the two feature test trees
decoupled while driving the identical real production surface.

Status: active-RED (ADR-025). `FailingClause.render()`
(src/des/domain/skill_normative_clause.py:61-63) TODAY renders ONLY
"{skill} -- {clause_id}". This AT asserts the FAIL message additionally
carries:
  1. the ABSENT marker TEXT (not just the clause-id),
  2. a WHY (the clause is normative -- the skill must state it),
  3. a concrete HOW (re-add the marker to the named SKILL.md; a pointer to the
     clause manifest),
  4. the skill file PATH to edit.
None of these are present yet -> the assertions raise a semantic
AssertionError on message CONTENT, not an import/collection error.

Constraint (feature-delta Prerequisites): this AT asserts message CONTENT
only -- it does NOT touch verdict logic (exit code 1 / FAIL is pinned as a
precondition, unchanged by this slice).
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process


# tests/des/acceptance/gate_self_explanation_completeness/<this file>
#   parents[0]=gate_self_explanation_completeness [1]=acceptance [2]=des
#   [3]=tests [4]=nWave-dev
_REPO_ROOT = Path(__file__).resolve().parents[4]
_REAL_MANIFEST_PATH = _REPO_ROOT / "nWave" / "data" / "skill-normative-clauses.json"

# The real, byte-exact clause this AT drives (DESIGN §6 seed manifest, grep-
# verified present in the shipped skill -- same anchor the sibling
# skill_normative_content_gate feature's domain_types.py pins).
_SKILL = "nw-test-design-mandates-composition-contract"
_CLAUSE_ID = "protocol-driver:assert-shipped-artifact"
_MARKER = "artifact the SUT actually shipped"


def _real_skill_asset() -> Path:
    return _REPO_ROOT / "nWave" / "skills" / _SKILL / "SKILL.md"


def test_real_clause_is_registered_with_the_expected_marker() -> None:
    """Precondition pin: the real manifest still carries this clause verbatim.

    Guards the fixture against silent drift -- if this fails, the AT below is
    not exercising the clause it claims to.
    """
    manifest = json.loads(_REAL_MANIFEST_PATH.read_text(encoding="utf-8"))
    entry = next(c for c in manifest["clauses"] if c["clause_id"] == _CLAUSE_ID)
    assert entry["skill"] == _SKILL
    assert entry["marker"] == _MARKER


def test_fail_message_names_absent_marker_why_how_and_skill_path(tmp_path) -> None:
    """FAIL on a deleted clause names the marker text + why + how + skill path.

    # covers: gate-self-explanation-completeness slice-01
    """
    # Given: a real-text copy of the shipped skill with the clause's marker
    # deleted (Pillar 3 -- real text, never a fabricated oracle) ...
    real_text = _real_skill_asset().read_text(encoding="utf-8")
    assert _MARKER in real_text, (
        f"real-surface precondition broken: marker {_MARKER!r} absent from "
        f"shipped {_real_skill_asset()}"
    )
    stripped = real_text.replace(_MARKER, "[[clause removed by AT fixture]]")
    mutated_skill_path = tmp_path / "skills" / _SKILL / "SKILL.md"
    mutated_skill_path.parent.mkdir(parents=True, exist_ok=True)
    mutated_skill_path.write_text(stripped, encoding="utf-8")

    # ... and a one-clause manifest pointing at that mutated copy.
    manifest_path = tmp_path / "skill-normative-clauses.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "clauses": [
                    {
                        "skill": _SKILL,
                        "clause_id": _CLAUSE_ID,
                        "marker": _MARKER,
                        "asset": str(mutated_skill_path),
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # When: the maintainer runs the skill-normative gate through the REAL
    # `des` dispatcher, in-process (no interpreter fork -- L2 default).
    exit_code, stdout, _stderr = run_cli_in_process(
        [
            "skill-normative-gate",
            "--manifest",
            str(manifest_path),
            "--root",
            str(_REPO_ROOT),
        ],
        cwd=_REPO_ROOT,
    )

    # Then: FAIL, exit 1 (pinned precondition -- unchanged by this slice) ...
    assert exit_code == 1, f"expected FAIL exit code 1; got {exit_code}\n{stdout}"

    # ... and the message names the absent marker TEXT (element 1) ...
    assert _MARKER in stdout, (
        f"FAIL message must name the ABSENT marker text {_MARKER!r} -- a "
        f"demanding user cannot know what to re-add without it; got:\n{stdout}"
    )

    # ... states WHY it matters (element 2: it is a normative clause the
    # skill must state) ...
    lowered = stdout.lower()
    assert "normative clause" in lowered and "must state" in lowered, (
        "FAIL message must state WHY: that the clause is normative and the "
        f"skill must state it; got:\n{stdout}"
    )

    # ... names a concrete HOW (element 3: re-add the marker + a pointer to
    # the clause manifest the clause was registered from) ...
    assert "add" in lowered and "manifest" in lowered, (
        "FAIL message must name a concrete HOW: re-add the marker, and cite "
        f"the clause manifest; got:\n{stdout}"
    )
    assert str(manifest_path) in stdout, (
        "FAIL message HOW must point at the clause manifest path "
        f"{manifest_path!s} so the user can see the exact required text; "
        f"got:\n{stdout}"
    )

    # ... and names the skill file PATH the user must edit (element 4).
    assert str(mutated_skill_path) in stdout, (
        f"FAIL message must name the skill file path {mutated_skill_path!s} "
        f"to edit; got:\n{stdout}"
    )


def test_compliant_skill_does_not_emit_the_self_explaining_fail_surface() -> None:
    """NEGATIVE AT (GS-8): a COMPLIANT skill must NOT emit the self-explaining
    FAIL surface for its clause -- no false positive, and the gate PASSES.

    # covers: gate-self-explanation-completeness slice-01

    The self-explaining FAIL surface (marker text + "normative clause" + "must
    state" + a HOW) is only correct on a REAL failure. Driving the gate against
    the real shipped manifest + the real unmutated skill (the marker IS present
    → no failing clause) must NOT produce that surface for this clause. This
    guards the crafter's slice-01 fix against over-emitting the diagnostic on a
    passing clause (the wrong-outcome class the negative-AT gate demands). It is
    GREEN today (a compliant skill already passes) and stays GREEN after the fix.
    """
    # When: the gate runs against the real shipped manifest + real skills — the
    # protocol-driver clause's marker IS present, so this clause does NOT fail.
    exit_code, stdout, _stderr = run_cli_in_process(
        [
            "skill-normative-gate",
            "--manifest",
            str(_REAL_MANIFEST_PATH),
            "--root",
            str(_REPO_ROOT),
        ],
        cwd=_REPO_ROOT,
    )

    # Then: the gate PASSES (exit 0) — the compliant corpus has no failing clause.
    assert exit_code == 0, (
        f"the real compliant corpus must PASS (exit 0); got {exit_code}\n{stdout}"
    )

    # And: the self-explaining FAIL surface for this clause is NOT produced —
    # no marker-naming, no WHY phrasing. A compliant clause must never trigger
    # the "here is what/why/how to fix" diagnostic (no false positive).
    lowered = stdout.lower()
    assert _MARKER not in stdout, (
        "compliant skill must NOT emit the absent-marker text — the "
        f"self-explaining FAIL surface is a false positive here; got:\n{stdout}"
    )
    assert "normative clause" not in lowered and "must state" not in lowered, (
        "compliant skill must NOT emit the WHY phrasing of the FAIL surface "
        f"(no false positive); got:\n{stdout}"
    )

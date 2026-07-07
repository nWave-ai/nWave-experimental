# @feature-des-dispatch-ssot-renderer
# @slice-01
"""Fase-1 code-layer ATs -- LANE_PROFILES is a drift-checked PROJECTION of the
`nWave/dispatch/atdd_pure.yaml` `profiles.lane` SSOT block, never a second
hand-authored copy.

Feature `des-dispatch-ssot-renderer` (design:
docs/feature/des-dispatch-ssot-renderer/design/dispatch-ssot-design.md,
Phase 1 "Establish the SSOT" + Open Review Point A resolved: the YAML is the
SSOT, `src/des/domain/lane_profile.py::LANE_PROFILES` stays a PURE LITERAL --
no YAML I/O in the domain (D1/D2) -- projected + drift-checked from OUTSIDE
the domain). Mirrors the docgen `GENERATED:mode-descriptor` Layer-C
agreement-leg pattern (`scripts/docgen.py::check_registry_runtime_agreement`
-- registry says X, the running system says Y, name the disagreement, empty
list = fresh/in-sync); see also the mode-registry-single-locus slice-02/05
precedent (`tests/des/acceptance/mode_registry_single_locus/`), which
established the same projection-vs-literal shape for `nWave/flavors/*.yaml`.

Driving port (Mandate 16, no-direct-domain-testing): every AT below drives
`des.application.dispatch_lane_ssot.check_lane_profile_drift(repo_root)` -- a
pure, composition-root-callable function. This mirrors the SAME "a pure
function IS the driving port" precedent this epic already set one file over
(`AtddPurePromptValidator.validate_prompt` in
`test_atdd_pure_prompt_validator_lane_profile.py`) -- never a bare
`LANE_PROFILES` shape assertion with no port between.

Active-RED contract: `des.application.dispatch_lane_ssot` is a Mandate-7 RED
scaffold (`__SCAFFOLD__ = True`); `check_lane_profile_drift` unconditionally
raises `AssertionError` today, so every scenario below fails with a semantic
AssertionError (impl missing), never an ImportError/collection error -- the
module exists (created by DISTILL), only its body is unimplemented.

CONTRACT_SHAPE: bounded-change (a finite, closed-world comparison over the
lane rows a hand-authored YAML declares -- no unbounded input space, no PBT;
Mandate 9 v2 OR-reduction: real filesystem in the driven set -> @real-io,
example-based).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from des.application.dispatch_lane_ssot import check_lane_profile_drift
from des.domain.lane_profile import LANE_PROFILES


# The real repo root -- tests/des/unit/application/<this file> -> parents[4] is
# the checkout root, mirroring the established
# `test_flavor_dispatcher_parser_characterization.py` precedent
# (`Path(__file__).resolve().parents[4] / "nWave" / "flavors"`).
_REPO_ROOT = Path(__file__).resolve().parents[4]
_REAL_DISPATCH_YAML = _REPO_ROOT / "nWave" / "dispatch" / "atdd_pure.yaml"


def _working_copy_dispatch_dir(tmp_path: Path) -> Path:
    """A tmp_path copy of the real `nWave/dispatch/` tree (`atdd_pure.yaml` only
    -- the drift-check's sole input), so a scenario can mutate the SSOT text
    without touching the real repo."""
    dispatch_dir = tmp_path / "nWave" / "dispatch"
    dispatch_dir.mkdir(parents=True)
    (dispatch_dir / "atdd_pure.yaml").write_text(
        _REAL_DISPATCH_YAML.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path


# --- AT-1 (positive -- the shipped SSOT and the shipped literal agree) ------


def test_lane_profiles_matches_the_dispatch_ssot_for_every_lane() -> None:
    """The REAL, shipped `LANE_PROFILES` (once DELIVER populates `bugfix`
    alongside the already-shipped `prefactoring`) must agree, lane-by-lane,
    with the REAL, shipped `nWave/dispatch/atdd_pure.yaml`'s `profiles.lane`
    block -- run against the live repo tree, no working copy, no mutation.

    This is the drift-check's PRIMARY promise: the generator (`des dispatch`,
    Phase 2) and the checker (the section validator, via `LANE_PROFILES`)
    share ONE source, so they cannot silently diverge.
    """
    drift = check_lane_profile_drift(_REPO_ROOT)
    assert drift == [], (
        "the shipped LANE_PROFILES literal must be a byte-faithful projection "
        f"of nWave/dispatch/atdd_pure.yaml's profiles.lane block. drift={drift}"
    )


# --- AT-2 (negative -- a YAML-side edit to an existing lane is named) ------


def test_drift_in_a_known_lane_required_sections_is_named(tmp_path: Path) -> None:
    """Editing the working copy's `bugfix` row to drop a section (diverging it
    from the live `LANE_PROFILES["bugfix"].required_sections`) must be caught
    and NAMED -- the check never silently accepts a YAML-side edit the domain
    literal has not been updated to track.
    """
    workspace = _working_copy_dispatch_dir(tmp_path)
    yaml_path = workspace / "nWave" / "dispatch" / "atdd_pure.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    assert "drop_sections: []" in text, (
        "fixture assumption: the shipped bugfix row declares `drop_sections: []` "
        "-- update this fixture if the SSOT's bugfix row shape changes."
    )
    mutated = text.replace(
        "drop_sections: []", "drop_sections: [TIMEOUT_INSTRUCTION]", 1
    )
    yaml_path.write_text(mutated, encoding="utf-8")

    drift = check_lane_profile_drift(workspace)

    assert drift != [], (
        "a working copy whose bugfix row drops TIMEOUT_INSTRUCTION -- diverging "
        "from the live LANE_PROFILES['bugfix'].required_sections -- must be "
        "reported as drift, never silently accepted."
    )
    assert any("bugfix" in entry for entry in drift), (
        f"the drift report must NAME the diverged lane ('bugfix'). drift={drift}"
    )


# --- AT-3 (negative -- a YAML-only lane with no literal counterpart) --------


def test_yaml_only_lane_absent_from_the_literal_is_named(tmp_path: Path) -> None:
    """A working copy declaring a THIRD lane (`canary`) the live `LANE_PROFILES`
    has no entry for must be reported as drift -- the SSOT->literal direction
    of the projection, symmetric to AT-2's literal-tracks-YAML direction.
    """
    workspace = _working_copy_dispatch_dir(tmp_path)
    yaml_path = workspace / "nWave" / "dispatch" / "atdd_pure.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    assert "    bugfix:" in text, (
        "fixture assumption: the shipped profiles.lane block declares a "
        "top-level 'bugfix:' row at 4-space indent."
    )
    canary_row = (
        "    canary:\n"
        "      drop_sections: []\n"
        "      guard_kind: RED_TO_GREEN\n"
        "      at_requirement: REQUIRED\n"
        "      feature_readiness: true\n"
        "      skipped_invariants: []\n"
        "      annotation_token: canary\n"
        "      requires: []\n"
    )
    mutated = text.replace("    bugfix:", canary_row + "    bugfix:", 1)
    yaml_path.write_text(mutated, encoding="utf-8")

    drift = check_lane_profile_drift(workspace)

    assert any("canary" in entry for entry in drift), (
        "a lane declared in the YAML SSOT with no LANE_PROFILES counterpart "
        f"must be reported by name. drift={drift}"
    )


# --- AT-4 (litmus -- the live LANE_PROFILES is consulted, never cached) ----


def test_check_consults_the_live_lane_profiles_not_a_cached_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Structural claim: the drift-check reads `des.domain.lane_profile.
    LANE_PROFILES` at CALL TIME. Proven by substituting the datum to a version
    missing the `bugfix` entry entirely and observing the check report
    `bugfix` as YAML-only -- against the REAL, unmodified repo tree, so the
    only thing that changed is the substituted datum, never the SSOT file.
    """
    from des.application import dispatch_lane_ssot

    substituted = {k: v for k, v in LANE_PROFILES.items() if k != "bugfix"}
    monkeypatch.setattr(dispatch_lane_ssot, "LANE_PROFILES", substituted, raising=False)

    drift = check_lane_profile_drift(_REPO_ROOT)

    assert any("bugfix" in entry for entry in drift), (
        "with LANE_PROFILES substituted to omit 'bugfix', the check must "
        "report 'bugfix' as present in the YAML SSOT but absent from the "
        f"(substituted) live datum -- proving live consultation. drift={drift}"
    )


# --- AT-5 (domain-purity guard -- D1/D2, no YAML I/O in the domain) --------


_FORBIDDEN_IO_TOKENS: tuple[str, ...] = (
    "import yaml",
    "subset_parser",
    "read_text(",
    "open(",
    ".yaml",
)


def test_lane_profile_domain_module_carries_no_yaml_io() -> None:
    """D1/D2 (pure domain, no I/O): `src/des/domain/lane_profile.py` -- the
    file `LANE_PROFILES` is declared in -- must contain NONE of the YAML/file
    I/O tokens the projection mechanism uses. `LANE_PROFILES` stays a PURE
    LITERAL; the projection + drift-check live OUTSIDE the domain (this
    file's own driving port, `dispatch_lane_ssot.check_lane_profile_drift`).
    """
    domain_file = _REPO_ROOT / "src" / "des" / "domain" / "lane_profile.py"
    source = domain_file.read_text(encoding="utf-8")
    found = [
        token for token in _FORBIDDEN_IO_TOKENS if re.search(re.escape(token), source)
    ]
    assert found == [], (
        "src/des/domain/lane_profile.py must stay a pure literal with zero "
        f"YAML/file I/O -- forbidden tokens found: {found}. Projection logic "
        "belongs in des.application.dispatch_lane_ssot, never the domain."
    )


# --- AT-6/7/8 (WS-3 Fase-1 hardening -- Vera-caught crash defects) ---------
#
# `check_lane_profile_drift`'s declared contract is `-> list[str]`: EVERY
# input, however hostile, must yield a diagnostic ENTRY in the returned list
# -- never a raised exception / traceback. The examiner (Vera) exercised the
# shipped function with three hostile repo-root shapes and caught it raising
# in all three (confirmed empirically against the current implementation:
# `FileNotFoundError`, `ValueError`, `ValueError` respectively). These three
# ATs promote those catches to a permanent regression gate (evolution-plan
# "promote caught classes to deterministic gates").
#
# Each AT calls `check_lane_profile_drift` UNGUARDED (no `pytest.raises`) and
# captures any propagating exception into a local, so the FIRST assertion
# (`exc is None`) is the RED reason -- a real AssertionError on the
# returns-a-list-with-diagnostic contract, never a pytest collection/error
# report on an uncaught exception.


def test_missing_yaml_file_returns_diagnostic_not_raise(tmp_path: Path) -> None:
    """`tmp_path` has NO `nWave/dispatch/atdd_pure.yaml` at all (not even the
    parent directories). The contract is `-> list[str]`: this must come back
    as a non-empty diagnostic list naming the expected (missing) path -- it
    must NOT raise `FileNotFoundError`.

    Confirmed empirically: the current implementation raises
    `FileNotFoundError: [Errno 2] No such file or directory: '.../
    atdd_pure.yaml'` via the unguarded `Path.read_text()` call -- a crash,
    not a diagnostic.
    """
    expected_path = tmp_path / "nWave" / "dispatch" / "atdd_pure.yaml"

    result: list[str] | None = None
    exc: Exception | None = None
    try:
        result = check_lane_profile_drift(tmp_path)
    except Exception as caught:
        exc = caught

    assert exc is None, (
        "check_lane_profile_drift must return a diagnostic list[str] for a "
        f"missing SSOT YAML, never raise -- raised {exc!r} instead."
    )
    assert isinstance(result, list), (
        f"expected a list[str] diagnostic result, got {result!r}"
    )
    assert result, "a missing SSOT YAML must produce at least one diagnostic entry"
    assert any(
        "not found" in entry.lower() and str(expected_path) in entry for entry in result
    ), (
        "the diagnostic must clearly say the YAML file was not found and name "
        f"the expected path {str(expected_path)!r}. result={result!r}"
    )


def test_malformed_yaml_returns_diagnostic_not_raise(tmp_path: Path) -> None:
    """The SSOT YAML file EXISTS but is syntactically broken (unstructured
    text, no `profiles:`/`full:`/`sections:` shape, an unclosed bracket).
    The contract is `-> list[str]`: this must come back as a diagnostic list
    naming the YAML as malformed/unparseable -- it must NOT raise
    `ValueError`, and the diagnostic must NOT be the misleading
    "profiles.full.sections not found" phrasing (that message implies a
    well-formed-but-incomplete YAML, not a broken one).

    Confirmed empirically: the current implementation raises
    `ValueError: profiles.full.sections not found in the dispatch SSOT YAML`
    via `_read_full_sections` -- a crash with a misleading message, not a
    malformed-YAML diagnostic.
    """
    dispatch_dir = tmp_path / "nWave" / "dispatch"
    dispatch_dir.mkdir(parents=True)
    (dispatch_dir / "atdd_pure.yaml").write_text(
        "this is not yaml : [ at all { broken\nrandom garbage\n", encoding="utf-8"
    )

    result: list[str] | None = None
    exc: Exception | None = None
    try:
        result = check_lane_profile_drift(tmp_path)
    except Exception as caught:
        exc = caught

    assert exc is None, (
        "check_lane_profile_drift must return a diagnostic list[str] for a "
        f"malformed SSOT YAML, never raise -- raised {exc!r} instead."
    )
    assert isinstance(result, list), (
        f"expected a list[str] diagnostic result, got {result!r}"
    )
    assert result, "a malformed SSOT YAML must produce at least one diagnostic entry"
    misleading_phrase = "profiles.full.sections not found"
    assert not any(misleading_phrase in entry for entry in result), (
        "the diagnostic must not reuse the misleading "
        f"{misleading_phrase!r} phrasing (that implies well-formed-but-"
        f"incomplete, not broken) YAML. result={result!r}"
    )
    assert any(
        ("malform" in entry.lower()) or ("pars" in entry.lower()) for entry in result
    ), (
        "the diagnostic must clearly name the YAML as malformed/unparseable. "
        f"result={result!r}"
    )


def test_yaml_missing_profiles_lane_block_returns_diagnostic_not_raise(
    tmp_path: Path,
) -> None:
    """The SSOT YAML EXISTS and is well-formed enough for
    `profiles.full.sections` to parse, but it lacks the `profiles.lane` block
    entirely. The contract is `-> list[str]`: this must come back as a
    diagnostic list naming the missing `lane` block -- it must NOT raise
    `ValueError`.

    Confirmed empirically: the current implementation raises
    `ValueError: profiles.lane block not found in the dispatch SSOT YAML` via
    `_read_lane_drop_sections` -- a crash, not a diagnostic.
    """
    dispatch_dir = tmp_path / "nWave" / "dispatch"
    dispatch_dir.mkdir(parents=True)
    (dispatch_dir / "atdd_pure.yaml").write_text(
        "profiles:\n  full:\n    sections: [SECTION_A, SECTION_B]\n",
        encoding="utf-8",
    )

    result: list[str] | None = None
    exc: Exception | None = None
    try:
        result = check_lane_profile_drift(tmp_path)
    except Exception as caught:
        exc = caught

    assert exc is None, (
        "check_lane_profile_drift must return a diagnostic list[str] when the "
        f"YAML has no profiles.lane block, never raise -- raised {exc!r} instead."
    )
    assert isinstance(result, list), (
        f"expected a list[str] diagnostic result, got {result!r}"
    )
    assert result, "a YAML missing profiles.lane must produce at least one entry"
    assert any(
        "lane" in entry.lower()
        and ("missing" in entry.lower() or "not found" in entry.lower())
        for entry in result
    ), (
        "the diagnostic must clearly name the missing profiles.lane block. "
        f"result={result!r}"
    )

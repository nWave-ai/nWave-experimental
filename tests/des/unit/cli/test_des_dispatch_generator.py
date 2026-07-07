"""Regression ATs -- WS-3 Fase-2 of `des-dispatch-ssot-renderer`: THE GENERATOR.

Design: docs/feature/des-dispatch-ssot-renderer/design/dispatch-ssot-design.md
("des dispatch -- the renderer contract", §4). Fase-1 (the `LANE_PROFILES`
drift-check against `nWave/dispatch/atdd_pure.yaml`'s `profiles.lane` block)
already shipped -- see `tests/des/unit/application/
test_lane_profile_dispatch_ssot_drift_check.py` +
`src/des/application/dispatch_lane_ssot.py`. This Fase-2 file is the sibling
regression suite for the GENERATOR itself: `des dispatch` must RENDER a
dispatch prompt from the SAME SSOT (`nWave/dispatch/atdd_pure.yaml` +
`LANE_PROFILES`) the EXISTING (unwired) renderer helpers in
`src/des/application/prompt_rendering_service.py` and the EXISTING checker
(`AtddPurePromptValidator`) already consume -- so the generator and the
checker share ONE source and cannot silently diverge (the system-pays
principle, 2026-07-06: the SYSTEM produces the checked artifact, the operator
supplies only the fuzzy fill).

THE POINT (the killer observable): today a human orchestrator hand-assembles
the atdd_pure crafter dispatch (marker triple + DES-PROJECT-ID + DES-WAVE +
DES-LANE + the 12 mandatory `# SECTION` headers + a DESIGN_CONTEXT ADR
citation) and gets it REJECTED one-requirement-at-a-time by
`AtddPurePromptValidator` (empirically: 8 rounds for FR-11's small fix).
`des dispatch` must GENERATE a dispatch that PASSES the dispatch gates BY
CONSTRUCTION.

Driving surface (P1-P4 in-process active-RED pattern, `nw-distill-red-
scaffolding`; mirrors the established `test_feature_delta_doctor.py`
precedent for a not-yet-registered subcommand): the STABLE, always-present
entry `des.cli.__main__` is driven via subprocess
(`python -m des.cli.__main__ dispatch ...`) -- NEVER the not-yet-existing
`des.cli.dispatch` module directly. `dispatch` is absent from the
`_SubcommandRow` registry today, so argparse's OWN internal dispatch (a
runtime call inside the CHILD process, never a collection-time import)
rejects it with a clean `invalid choice` exit 2 -- confirmed empirically
(2026-07-07): stdout empty (with `NWAVE_FRESHNESS=skip`), stderr carries
`des: error: argument subcommand: invalid choice: 'dispatch' ...`, exit 2,
NO traceback. Every AT below therefore fails today for a genuine semantic
AssertionError (a specific expectation about the FUTURE `dispatch` behavior
does not hold against today's argparse usage error) -- never an ImportError
or a collection error.

INFERRED CRAFTER CONTRACT (documented here so the crafter has an unambiguous
target; flag back to DISTILL if a specific choice below is wrong):

    des dispatch --mode atdd_pure --project-id <id> --slice <slice-NN>
                 --phase <ATDDPurePhase value> [--lane <lane_id>]
                 [--intent "<free text>"]
                 [--defect "<free text>" --regression-test <test_name>]  # bugfix lane
                 [--repo-root <path>]   # locate nWave/dispatch/*.yaml; default cwd

  * Emits the DES-* marker set from `nWave/dispatch/atdd_pure.yaml:markers`,
    rendered in the claude_code vendor syntax `nWave/dispatch/vendors.yaml`
    declares: `"<!-- {key} : {value} -->"`.
  * Emits one `# {SECTION_ID}` header per section in the resolved profile
    (`profiles.full.sections` by default; a recognized `--lane` substitutes
    that lane's `LANE_PROFILES[lane].required_sections`).
  * A `--lane` carrying `requires: [lane_justification]` (today: `bugfix`)
    combines `--defect` + `--regression-test` into ONE `DES-LANE-JUSTIFICATION`
    marker value naming both (mirrors the shape
    `_lane_justification_names_defect_and_test` in
    `des.cli.verify_readiness_pre_dispatch` already requires: non-vacuous text
    plus a `test_<name>` token).
  * A missing/invalid `--project-id` / `--phase` / `--lane` is a CLEAR,
    self-explaining non-zero-exit error -- never a Python traceback
    (STANDING every-failure-explains-what-why-how mandate).
  * `--repo-root` (optional, default cwd) resolves `nWave/dispatch/*.yaml` --
    mirrors the existing `--repo-root`-taking gates
    (`verify-deliver-entry-contract`, the bugfix-lane readiness gate) so the
    section set is SSOT-DERIVED, never hardcoded into the generator.

CONTRACT_SHAPE: bounded-change (a finite, closed-world rendering over a
hand-authored SSOT registry -- no unbounded input space, no PBT; Mandate 9 v2
OR-reduction: real filesystem + real subprocess in the driven set ->
@real-io, example-based).

covers: F-des-dispatch-ssot-renderer (Fase-2, the generator)
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from des.application.atdd_pure_prompt_validator import (
    ATDD_PURE_MANDATORY_SECTIONS,
    AtddPurePromptValidator,
)
from des.application.dispatch_lane_ssot import _read_full_sections
from des.domain.atdd_pure_phases import ATDDPurePhase
from des.domain.lane_profile import LANE_PROFILES


# tests/des/unit/cli/<this file> -> parents[4] is the checkout root, mirroring
# the established test_feature_delta_doctor.py / dispatch_lane_ssot AT precedent.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DISPATCH_YAML = _REPO_ROOT / "nWave" / "dispatch" / "atdd_pure.yaml"

# The claude_code vendor's marker rendering, read verbatim from
# `nWave/dispatch/vendors.yaml` (`marker_syntax: "<!-- {key} : {value} -->"`)
# -- asserting against the SAME literal the vendor SSOT declares, not an
# independently-invented format.
_MARKER_SYNTAX = "<!-- {key} : {value} -->"

_DES_LANE_JUSTIFICATION_PATTERN = re.compile(
    r"<!--\s*DES-LANE-JUSTIFICATION\s*:\s*(.+?)\s*-->"
)


def _marker(key: str, value: str) -> str:
    return _MARKER_SYNTAX.format(key=key, value=value)


# ---------------------------------------------------------------------------
# Driving-port helpers (subprocess boundary, mirrors _doctor_argv/_doctor_env)
# ---------------------------------------------------------------------------


def _dispatch_argv(*args: str) -> list[str]:
    """Build the `python -m des.cli.__main__ dispatch` argv.

    Drives the STABLE, always-present dispatcher module (never the absent
    `des.cli.dispatch`) -- the P1 invariant of the in-process active-RED
    pattern, applied at the subprocess boundary so the absent subcommand
    surfaces as a clean argparse `invalid choice` (exit 2) inside the child,
    never a collection-time ImportError in this process.
    """
    return [sys.executable, "-m", "des.cli.__main__", "dispatch", *args]


def _dispatch_env() -> dict[str, str]:
    """Env with `src` on PYTHONPATH; freshness gate skipped (confirmed
    empirically 2026-07-07: without this, `des` prints a
    `des.runtime.freshness.autoskipped` JSON line to stdout ahead of any
    subcommand output, an unrelated cross-cutting concern that would
    otherwise confound this AT's stdout assertions)."""
    env = dict(os.environ)
    src = str(_REPO_ROOT / "src")
    env["PYTHONPATH"] = (
        f"{src}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else src
    )
    env["NWAVE_FRESHNESS"] = "skip"
    return env


def _run_dispatch(
    *args: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Invoke `des dispatch` as a CLI subprocess and capture exit code + stdio."""
    return subprocess.run(
        _dispatch_argv(*args),
        capture_output=True,
        text=True,
        timeout=30,
        env=_dispatch_env(),
        cwd=str(cwd) if cwd is not None else None,
    )


# ---------------------------------------------------------------------------
# AT-1 -- GATE-VALID BY CONSTRUCTION (the core promise)
# ---------------------------------------------------------------------------


def test_dispatch_generates_gate_valid_prompt_by_construction() -> None:
    """`des dispatch --mode atdd_pure --project-id demo --slice slice-01
    --phase A_GREEN` must emit, on stdout, a dispatch prompt carrying the
    complete marker set + ALL 12 canonical `# SECTION` headers, and that
    prompt must round-trip through the REAL production
    `AtddPurePromptValidator` to an ALLOWED verdict in one shot -- the exact
    ceremony a human orchestrator today hand-assembles and gets rejected on
    one requirement at a time (FR-11: 8 rounds for a small fix).

    FAILS TODAY: `dispatch` is not a registered subcommand; the child process
    exits 2 (argparse `invalid choice`), not 0.
    """
    result = _run_dispatch(
        "--mode",
        "atdd_pure",
        "--project-id",
        "demo",
        "--slice",
        "slice-01",
        "--phase",
        "A_GREEN",
        "--intent",
        "wire the missing seam",
    )

    assert result.returncode == 0, (
        "expected exit 0 once `des dispatch` exists and renders a "
        "gate-valid prompt; got "
        f"{result.returncode} (today: argparse 'invalid choice' -- "
        "'dispatch' is not yet a registered subcommand). "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    prompt = result.stdout

    for key, value in (
        ("DES-VALIDATION", "required"),
        ("DES-PROJECT-ID", "demo"),
        ("DES-MODE", "atdd_pure"),
        ("DES-PHASE", "A_GREEN"),
        ("DES-SLICE", "slice-01"),
        ("DES-WAVE", "deliver"),
    ):
        expected = _marker(key, value)
        assert expected in prompt, (
            f"missing marker {expected!r} in the generated dispatch prompt:\n{prompt}"
        )

    missing_sections = [
        section
        for section in ATDD_PURE_MANDATORY_SECTIONS
        if f"# {section}" not in prompt
    ]
    assert missing_sections == [], (
        "generated prompt is missing mandatory section header(s) "
        f"{missing_sections} -- every one of the 12 canonical atdd_pure "
        f"sections (ATDD_PURE_MANDATORY_SECTIONS) must be present.\n{prompt}"
    )

    outcome = AtddPurePromptValidator().validate_prompt(prompt)
    assert outcome.task_invocation_allowed, (
        "the generated prompt must round-trip through the REAL "
        "AtddPurePromptValidator to an ALLOWED verdict (gate-valid BY "
        f"CONSTRUCTION, not merely by eye) -- errors={outcome.errors}. "
        f"prompt=\n{prompt}"
    )


# ---------------------------------------------------------------------------
# AT-2 -- LANE-AWARE (bugfix: additive markers, full section set unchanged)
# ---------------------------------------------------------------------------


def test_dispatch_bugfix_lane_emits_lane_markers_and_exact_section_set() -> None:
    """`--lane bugfix` additionally emits `DES-LANE: bugfix` +
    `DES-LANE-JUSTIFICATION` (combining `--defect` + `--regression-test`, the
    shape `verify_readiness_pre_dispatch._lane_justification_names_defect_and_test`
    already requires downstream) and emits EXACTLY
    `LANE_PROFILES["bugfix"].required_sections` -- no more, no less.

    FAILS TODAY: `dispatch` is not a registered subcommand; the child process
    exits 2, not 0.
    """
    result = _run_dispatch(
        "--mode",
        "atdd_pure",
        "--project-id",
        "demo",
        "--slice",
        "slice-01",
        "--phase",
        "A_GREEN",
        "--lane",
        "bugfix",
        "--defect",
        "off-by-one in _resolve_head_sha returns the parent commit",
        "--regression-test",
        "test_resolve_head_sha_returns_head",
    )

    assert result.returncode == 0, (
        "expected exit 0 once `des dispatch --lane bugfix` exists; got "
        f"{result.returncode}. stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    prompt = result.stdout

    assert _marker("DES-LANE", "bugfix") in prompt, (
        f"missing DES-LANE marker for the bugfix lane:\n{prompt}"
    )

    justification_match = _DES_LANE_JUSTIFICATION_PATTERN.search(prompt)
    assert justification_match is not None, (
        f"missing a DES-LANE-JUSTIFICATION marker in the bugfix dispatch:\n{prompt}"
    )
    justification = justification_match.group(1)
    assert "test_resolve_head_sha_returns_head" in justification, (
        "the lane justification must NAME the regression test -- "
        f"justification={justification!r}"
    )
    assert "off-by-one" in justification, (
        "the lane justification must NAME the defect -- "
        f"justification={justification!r}"
    )

    present_sections = {
        section for section in ATDD_PURE_MANDATORY_SECTIONS if f"# {section}" in prompt
    }
    expected_sections = set(LANE_PROFILES["bugfix"].required_sections)
    assert present_sections == expected_sections, (
        "the bugfix lane must emit EXACTLY LANE_PROFILES['bugfix']."
        f"required_sections -- present={sorted(present_sections)} "
        f"expected={sorted(expected_sections)}"
    )


def test_dispatch_prefactoring_lane_drops_at_recording_sections() -> None:
    """`--lane prefactoring` DROPS `AT_COMPLETION_LEDGER` + `RECORDING_INTEGRITY`
    per `LANE_PROFILES["prefactoring"].required_sections` (a behavior-preserving
    prefactoring never writes AT-recording sections) -- exercising the actual
    DROP semantics the bugfix lane (whose `drop_sections` is empty) cannot.

    FAILS TODAY: `dispatch` is not a registered subcommand; the child process
    exits 2, not 0.
    """
    result = _run_dispatch(
        "--mode",
        "atdd_pure",
        "--project-id",
        "demo",
        "--slice",
        "slice-01",
        "--phase",
        "A_GREEN",
        "--lane",
        "prefactoring",
    )

    assert result.returncode == 0, (
        "expected exit 0 once `des dispatch --lane prefactoring` exists; got "
        f"{result.returncode}. stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    prompt = result.stdout

    present_sections = {
        section for section in ATDD_PURE_MANDATORY_SECTIONS if f"# {section}" in prompt
    }
    expected_sections = set(LANE_PROFILES["prefactoring"].required_sections)
    assert present_sections == expected_sections, (
        "the prefactoring lane must emit EXACTLY LANE_PROFILES['prefactoring']."
        f"required_sections -- present={sorted(present_sections)} "
        f"expected={sorted(expected_sections)}"
    )
    for dropped in ("AT_COMPLETION_LEDGER", "RECORDING_INTEGRITY"):
        assert dropped not in present_sections, (
            f"the prefactoring lane must DROP {dropped!r} -- a behavior-"
            f"preserving prefactoring never writes AT-recording sections. "
            f"present={sorted(present_sections)}"
        )


# ---------------------------------------------------------------------------
# AT-3 -- SSOT-DRIVEN (no 4th hardcoded copy of the section list)
# ---------------------------------------------------------------------------


def test_dispatch_section_set_is_derived_from_the_dispatch_ssot_yaml() -> None:
    """The emitted section set must equal `profiles.full.sections` read
    DIRECTLY from `nWave/dispatch/atdd_pure.yaml` (via the EXISTING scoped
    reader `dispatch_lane_ssot._read_full_sections`, reused rather than
    re-derived) -- the proxy that the generator projects the SSOT rather than
    restating a hardcoded list. Adding/removing a section in the YAML must
    change this comparison, not just `ATDD_PURE_MANDATORY_SECTIONS`
    (AT-1 already locks that constant separately).

    FAILS TODAY: `dispatch` is not a registered subcommand; the child process
    exits 2, not 0.
    """
    yaml_sections = _read_full_sections(_DISPATCH_YAML.read_text(encoding="utf-8"))

    result = _run_dispatch(
        "--mode",
        "atdd_pure",
        "--project-id",
        "demo",
        "--slice",
        "slice-01",
        "--phase",
        "A_GREEN",
    )

    assert result.returncode == 0, (
        f"expected exit 0; got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    prompt = result.stdout

    present_in_yaml_order = tuple(
        section for section in yaml_sections if f"# {section}" in prompt
    )
    assert present_in_yaml_order == yaml_sections, (
        "the emitted section set must equal profiles.full.sections read "
        "DIRECTLY from nWave/dispatch/atdd_pure.yaml (proxy for 'no 4th "
        f"hardcoded copy') -- yaml={yaml_sections} "
        f"present={present_in_yaml_order}"
    )


def test_dispatch_section_set_changes_when_the_ssot_yaml_gains_a_section(
    tmp_path: Path,
) -> None:
    """Stronger mutation proof: copy the REAL `nWave/dispatch/` tree into a
    tmp workspace, ADD a brand-new section (`ZZZ_PROBE_SECTION`) to
    `profiles.full.sections` in the WORKING COPY only, and confirm the
    mutation reaches the rendered output via a `--repo-root` override --
    proving the section list is READ from the SSOT at render time, never
    hardcoded into the generator (so "adding a section to the YAML would
    change the output", per the design ask).

    ASSUMPTION documented for the crafter: `des dispatch` accepts
    `--repo-root` to locate `nWave/dispatch/atdd_pure.yaml`, mirroring the
    existing `--repo-root`-taking gates (`verify-deliver-entry-contract`,
    the bugfix-lane readiness gate). If the crafter's actual contract
    resolves the SSOT differently, adjust this ONE test to match -- the
    proxy assertion above (`test_dispatch_section_set_is_derived_from_the_
    dispatch_ssot_yaml`) already locks the non-negotiable behavioural
    requirement without depending on this flag.

    FAILS TODAY: `dispatch` is not a registered subcommand; the child process
    exits 2, not 0.
    """
    real_yaml = _DISPATCH_YAML.read_text(encoding="utf-8")
    assert "TIMEOUT_INSTRUCTION]" in real_yaml, (
        "fixture assumption: profiles.full.sections ends with "
        "TIMEOUT_INSTRUCTION] -- update this fixture if the SSOT shape changes."
    )
    mutated = real_yaml.replace(
        "TIMEOUT_INSTRUCTION]", "TIMEOUT_INSTRUCTION, ZZZ_PROBE_SECTION]", 1
    )
    assert mutated.count("sections:\n") == 1, (
        "fixture assumption: exactly one top-level 'sections:' key -- update "
        "this fixture if the SSOT shape changes."
    )
    mutated = mutated.replace(
        "sections:\n",
        "sections:\n  - id: ZZZ_PROBE_SECTION\n    template: |\n      probe body\n",
        1,
    )

    dispatch_dir = tmp_path / "nWave" / "dispatch"
    dispatch_dir.mkdir(parents=True)
    (dispatch_dir / "atdd_pure.yaml").write_text(mutated, encoding="utf-8")
    vendors_src = _REPO_ROOT / "nWave" / "dispatch" / "vendors.yaml"
    (dispatch_dir / "vendors.yaml").write_text(
        vendors_src.read_text(encoding="utf-8"), encoding="utf-8"
    )

    result = _run_dispatch(
        "--mode",
        "atdd_pure",
        "--project-id",
        "demo",
        "--slice",
        "slice-01",
        "--phase",
        "A_GREEN",
        "--repo-root",
        str(tmp_path),
    )

    assert result.returncode == 0, (
        f"expected exit 0; got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "# ZZZ_PROBE_SECTION" in result.stdout, (
        "a section ADDED to the working-copy SSOT YAML must appear in the "
        "rendered output -- proving the generator reads profiles.full."
        f"sections at render time rather than a hardcoded literal. "
        f"stdout={result.stdout!r}"
    )


# ---------------------------------------------------------------------------
# AT-4 -- DEGRADE-LOUD on hostile input (front-loaded, never a crash Vera
# catches later)
# ---------------------------------------------------------------------------


def test_invalid_phase_value_is_a_clear_error_never_a_traceback() -> None:
    """An unrecognized `--phase` value must be a CLEAR, self-explaining
    non-zero-exit error naming the bad value -- never a Python traceback.

    FAILS TODAY: today's error ("invalid choice: 'dispatch'") never names
    the offending --phase value 'NOT_A_REAL_PHASE', nor lists a valid phase.
    """
    result = _run_dispatch(
        "--mode",
        "atdd_pure",
        "--project-id",
        "demo",
        "--slice",
        "slice-01",
        "--phase",
        "NOT_A_REAL_PHASE",
    )
    combined = result.stdout + result.stderr

    assert "Traceback" not in combined, (
        "an invalid --phase must produce a clean error, never a Python "
        f"traceback. combined output={combined!r}"
    )
    assert result.returncode != 0, "an invalid --phase must exit non-zero"
    assert "NOT_A_REAL_PHASE" in combined, (
        f"the error must NAME the offending --phase value. combined={combined!r}"
    )
    valid_phase_names = {member.value for member in ATDDPurePhase}
    assert any(name in combined for name in valid_phase_names), (
        "the error must guide the caller toward a valid --phase value (one "
        f"of {sorted(valid_phase_names)}). combined={combined!r}"
    )


def test_missing_project_id_is_a_clear_error_never_a_traceback() -> None:
    """A missing `--project-id` must be a CLEAR, self-explaining non-zero-exit
    error naming the missing argument -- never a Python traceback.

    FAILS TODAY: today's error ("invalid choice: 'dispatch'") never mentions
    --project-id at all.
    """
    result = _run_dispatch(
        "--mode",
        "atdd_pure",
        "--slice",
        "slice-01",
        "--phase",
        "A_GREEN",
    )
    combined = result.stdout + result.stderr

    assert "Traceback" not in combined, (
        "a missing --project-id must produce a clean error, never a Python "
        f"traceback. combined output={combined!r}"
    )
    assert result.returncode != 0, "a missing --project-id must exit non-zero"
    assert "project-id" in combined.lower() or "project_id" in combined.lower(), (
        f"the error must NAME the missing --project-id argument. combined={combined!r}"
    )


def test_unknown_lane_is_a_clear_error_never_a_traceback() -> None:
    """An unrecognized `--lane` value must be a CLEAR, self-explaining
    non-zero-exit error naming the bad value -- never a Python traceback.

    FAILS TODAY: today's error ("invalid choice: 'dispatch'") never names
    the offending --lane value 'not_a_real_lane', nor lists a known lane.
    """
    result = _run_dispatch(
        "--mode",
        "atdd_pure",
        "--project-id",
        "demo",
        "--slice",
        "slice-01",
        "--phase",
        "A_GREEN",
        "--lane",
        "not_a_real_lane",
    )
    combined = result.stdout + result.stderr

    assert "Traceback" not in combined, (
        "an unknown --lane must produce a clean error, never a Python "
        f"traceback. combined output={combined!r}"
    )
    assert result.returncode != 0, "an unknown --lane must exit non-zero"
    assert "not_a_real_lane" in combined, (
        f"the error must NAME the offending --lane value. combined={combined!r}"
    )
    assert any(lane in combined for lane in LANE_PROFILES), (
        "the error must guide the caller toward a known lane "
        f"{sorted(LANE_PROFILES)}. combined={combined!r}"
    )

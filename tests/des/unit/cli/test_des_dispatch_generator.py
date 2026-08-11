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
the retired prompt renderer and the existing checker
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
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import yaml

from des.application.atdd_pure_prompt_validator import (
    ATDD_PURE_MANDATORY_SECTIONS,
    AtddPurePromptValidator,
)
from des.application.dispatch_lane_ssot import _read_full_sections
from des.domain.atdd_pure_phases import ATDDPurePhase
from des.domain.lane_profile import LANE_PROFILES
from tests.common.in_process_cli import run_module_in_process


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

#: ADR-SSOT-002 S4a: every test-running (`runs_tests=True`) dispatch now
#: REQUIRES an explicit `--repo-root <ROOT>` + `--delivery-contract <PATH>`
#: pair, `PATH` resolved ONLY against `ROOT` (locked by the 19-test locator
#: suite, `tests/des/acceptance/test_dispatch_delivery_contract_locator.py`).
#: The real, checked-in, schema-valid ThinDeliveryContract fixture that
#: suite already proves against -- reused here rather than a second,
#: drifting hand-authored contract literal.
_DELIVERY_CONTRACT_FIXTURE_REL = (
    "docs/delivery-contracts/retarget-des-dispatch-contract.json"
)
_DELIVERY_CONTRACT_FIXTURE = _REPO_ROOT / _DELIVERY_CONTRACT_FIXTURE_REL


def _seed_delivery_contract(
    root: Path, rel_path: str = "delivery-contract.json"
) -> str:
    """Copy the real ThinDeliveryContract fixture under `root` and return its
    ROOT-relative PATH -- for a test driving an isolated `--repo-root` (a
    tmp workspace), which cannot resolve a PATH relative to the real
    checkout root."""
    dst = root / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_DELIVERY_CONTRACT_FIXTURE, dst)
    return rel_path


def _contract_args(root: Path, *, seed: bool = True) -> tuple[str, str, str, str]:
    """The `--repo-root <root> --delivery-contract <PATH>` pair a test-
    running dispatch against `root` now requires. `seed=True` (the default)
    copies the fixture under `root` first, for an isolated tmp workspace;
    `seed=False` reuses the real checked-in fixture in place, for a dispatch
    driven against the real checkout root (`_REPO_ROOT`) -- never a second
    copy of a file already on disk there."""
    rel_path = _seed_delivery_contract(root) if seed else _DELIVERY_CONTRACT_FIXTURE_REL
    return ("--repo-root", str(root), "--delivery-contract", rel_path)


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
    argv = _dispatch_argv(*args)
    exit_code, out, err = run_module_in_process(
        argv[2], *argv[3:], cwd=cwd, env=_dispatch_env()
    )
    return subprocess.CompletedProcess(
        args=argv, returncode=exit_code, stdout=out, stderr=err
    )


# ---------------------------------------------------------------------------
# AT-1 -- GATE-VALID BY CONSTRUCTION (the core promise)
# ---------------------------------------------------------------------------


def test_dispatch_generates_gate_valid_prompt_by_construction(tmp_path: Path) -> None:
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
        *_contract_args(_REPO_ROOT, seed=False),
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
        *_contract_args(_REPO_ROOT, seed=False),
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
        *_contract_args(_REPO_ROOT, seed=False),
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
        *_contract_args(_REPO_ROOT, seed=False),
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
        *_contract_args(tmp_path),
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


# ---------------------------------------------------------------------------
# AT-5 -- DESIGN_CONTEXT never points to a nonexistent file (bug
# fix-des-dispatch-broken-design-context-pointer)
#
# ROOT CAUSE (RCA, evidence-backed): `_design_context_body(agent, feature_id)`
# (src/des/cli/dispatch.py:308-317) hardcodes
# `f"Design reference: docs/feature/{feature_id}/feature-delta.md\n"` for
# every code-facing agent regardless of `lane` (it takes no `lane` param) and
# regardless of whether that file actually exists on disk. A bugfix lane has
# no feature-delta.md by design (the RCA doc is the design source) -- so the
# bugfix crafter dispatch envelope names a file that will never resolve, and
# `_feature_delta_readiness_advisory` (which WOULD warn) is unconditionally
# skipped for the bugfix lane (`_LANES_REQUIRING_JUSTIFICATION` gate at
# dispatch.py:672, keyed wrong -- it should key on `LaneProfile.
# feature_readiness`, which is True for bugfix) -- so bugfix loses both the
# correct pointer AND the warning. Charter oracle:
# docs/product/expectations/fix-des-dispatch-broken-design-context-pointer/
# the-dispatch-envelope-never-points-a-crafter-at-a-file-that-does-not-exist.md
#
# Driving surface: SAME hermetic subprocess boundary as AT-1..AT-4 above
# (`python -m des.cli.__main__ dispatch`) -- never a stubbed generator. Each
# AT here runs the REAL CLI in an isolated ``tmp_path`` cwd (so
# ``docs/feature/<id>/feature-delta.md`` existence is test-controlled) with
# ``NWAVE_REPO_ROOT`` popped from the child env so the project-root axis
# resolves via cwd, never a leaked ambient value (`resolve_repo_root`'s
# flag > env > cwd precedence, src/des/domain/repo_path_resolver.py).
#
# CONTRACT_SHAPE: bounded-change (same finite, closed-world SSOT-rendering
# shape as the rest of this file -- example-based, no PBT).
# ---------------------------------------------------------------------------


def _isolated_dispatch_env() -> dict[str, str]:
    """`_dispatch_env()` plus `NWAVE_REPO_ROOT` popped -- so the child
    process's project-root axis (`resolve_repo_root`) resolves via its cwd,
    never a leaked ambient value from the outer test-runner environment."""
    env = _dispatch_env()
    env.pop("NWAVE_REPO_ROOT", None)
    return env


# ---------------------------------------------------------------------------
# AT-6 -- proactive wave-floor advisory AT GENERATION time (defect 2,
# docs/mikado/EXECUTION-SSOT-des-optimization.md, 2026-07-29)
#
# ROOT CAUSE: the WAVE_MARKER_BYPASS refusal's guidance ("generate this with
# `des dispatch`, never hand-assemble it") only ever reached the operator
# INSIDE the refusal -- after a hand-assembled prompt was already dispatched
# and the effort already spent (GDP-5). `des dispatch` is the ONE authoring
# surface an operator already touches for every dispatch; it must say the
# same thing PROACTIVELY, at that surface, before any dispatch is attempted
# (GDP-2), and its HOW must be "you are already using the producing tool" --
# never an instruction to repair anything by hand (GDP-4).
#
# Driving surface: SAME hermetic subprocess boundary as AT-5 above (`python -m
# des.cli.__main__ dispatch`), isolated `tmp_path` cwd so the wave-active
# floor file is test-controlled and never a leaked ambient one.
# ---------------------------------------------------------------------------

_WAVE_FLOOR_REL = Path(".nwave") / "wave-active" / "active.json"


def _arm_wave_floor(tmp_path: Path, *, wave: str, provenance: str) -> None:
    """Write a wave-active floor file directly (mirrors the production store's
    JSON shape) -- no need to drive the writer for a pure fixture precondition."""
    import json

    floor = tmp_path / _WAVE_FLOOR_REL
    floor.parent.mkdir(parents=True, exist_ok=True)
    floor.write_text(
        json.dumps({"wave": wave, "provenance": provenance}), encoding="utf-8"
    )


def _run_plain_dispatch(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """An ORDINARY dispatch, unrelated to any armed wave (no --wave given)."""
    return subprocess.run(
        _dispatch_argv(
            "--mode",
            "atdd_pure",
            "--project-id",
            "probe-wave-floor-advisory",
            "--slice",
            "slice-01",
            "--phase",
            "A_GREEN",
            *_contract_args(tmp_path),
        ),
        capture_output=True,
        text=True,
        timeout=30,
        env=_isolated_dispatch_env(),
        cwd=str(tmp_path),
    )


def test_dispatch_warns_proactively_when_a_wave_floor_is_armed(
    tmp_path: Path,
) -> None:
    """POSITIVE (the fix, RED today): with an armed wave floor under the
    dispatch's cwd, `des dispatch` must print a proactive advisory to STDERR
    naming the armed wave and pointing at the SAME `des dispatch` invocation
    the operator is already running -- BEFORE any WAVE_MARKER_BYPASS refusal
    could ever fire. Generation must still succeed (advisory, never a block).

    FAILS TODAY: `des dispatch` never reads the wave-active floor at all, so
    stderr carries no advisory regardless of an armed floor.
    """
    _arm_wave_floor(tmp_path, wave="distill", provenance="inferred")

    result = _run_plain_dispatch(tmp_path)

    assert result.returncode == 0, (
        "an armed wave floor must not block generation -- this is an "
        f"ADVISORY, never a gate; got exit {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "distill" in result.stderr and "wave floor is armed" in result.stderr, (
        "stderr must proactively name the armed wave BEFORE any dispatch is "
        f"attempted; got stderr={result.stderr!r}"
    )
    assert "des dispatch" in result.stderr, (
        "the advisory's HOW must point at the producing tool (`des dispatch`) "
        f"the operator is already running, never a manual-repair instruction; "
        f"got stderr={result.stderr!r}"
    )


def test_dispatch_advisory_is_silent_when_no_wave_floor_is_armed(
    tmp_path: Path,
) -> None:
    """NEGATIVE (no regression / no noise): with NO wave-active floor file at
    all, `des dispatch` must emit no wave-floor advisory -- proving the
    advisory is conditioned on a genuinely armed floor, not unconditional
    stderr noise on every invocation.
    """
    result = _run_plain_dispatch(tmp_path)

    assert result.returncode == 0, (
        f"expected exit 0; got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "wave floor is armed" not in result.stderr, (
        "no wave floor is armed under this cwd -- stderr must carry no "
        f"wave-floor advisory; got stderr={result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# AT-7 -- slice-01 SSOT content-parity merge
# (dispatch-template-ssot-reconciliation, mikado D12)
#
# Design: docs/feature/dispatch-template-ssot-reconciliation/design/
#         dispatch-template-ssot-reconciliation-design.md, section 3 (the
#         per-section reconciliation table) + Decisions 3/4.
# Feature delta: docs/feature/dispatch-template-ssot-reconciliation/
#                feature-delta.md, Slice Plan row slice-01.
#
# THE POINT: a real `des dispatch` render for the CODE-FACING crafter path
# (--phase A_GREEN, no --lane) is content-poorer today than either
# `nWave/dispatch/atdd_pure.yaml`'s unread `sections[].template` or the
# hand-authored `nw-execute/SKILL.md` block for 7 of the 12 canonical
# sections (DES_METADATA, SKILL_LOADING, QUALITY_GATES, AT_COMPLETION_LEDGER,
# BOUNDARY_RULES, TERMINATING_RUN, TIMEOUT_INSTRUCTION) -- verified absent
# below, section by section, against the actual production strings in
# `nWave/dispatch/atdd_pure.yaml` and `nw-execute/SKILL.md:218-326`. Slice-01
# merges that content into `dispatch.py::_section_body`'s crafter branch
# WITHOUT flattening the role branching every OTHER agent/lane/wave already
# renders correctly (examiner, charter product-owner, phaseless authoring
# wave, armed middle slot) -- the second half of every AT below (or its own
# dedicated sibling AT) pins that those branches are UNCHANGED.
#
# Driving surface: SAME hermetic subprocess boundary as AT-1..AT-6 above
# (`python -m des.cli.__main__ dispatch`).
#
# CONTRACT_SHAPE: bounded-change (finite, closed-world SSOT-rendering merge --
# example-based, no PBT).
#
# covers: F-dispatch-template-ssot-reconciliation (D12, slice-01)
# ---------------------------------------------------------------------------

_SECTION_PATTERN_CACHE: dict[str, re.Pattern[str]] = {}


def _section_text(prompt: str, section_id: str) -> str:
    """Extract one `# {section_id}` section body verbatim (mirrors
    `_design_context_section`, generalized to any section id)."""
    pattern = _SECTION_PATTERN_CACHE.get(section_id)
    if pattern is None:
        pattern = re.compile(
            rf"# {re.escape(section_id)}\n(.*?)(?=\n# [A-Z_]+\n|\Z)", re.DOTALL
        )
        _SECTION_PATTERN_CACHE[section_id] = pattern
    match = pattern.search(prompt)
    assert match is not None, f"no {section_id!r} section found in prompt:\n{prompt}"
    return match.group(1)


def _run_crafter_dispatch(feature_id: str = "demo") -> subprocess.CompletedProcess[str]:
    """The CODE-FACING crafter path this slice's merges target: a plain
    `--phase A_GREEN` dispatch, no `--lane`, default `--wave` (deliver)."""
    return _run_dispatch(
        "--mode",
        "atdd_pure",
        "--project-id",
        feature_id,
        "--slice",
        "slice-01",
        "--phase",
        "A_GREEN",
        "--intent",
        "merge the dispatch-template-ssot-reconciliation content",
        *_contract_args(_REPO_ROOT, seed=False),
    )


# --- half 1: the crafter path gains the merged content (RED today) --------


def _run_design_wave_dispatch(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """A phaseless authoring-wave dispatch (`--wave design`) -- resolves to
    `nw-solution-architect` via `_WAVE_AGENTS`, never the crafter."""
    return subprocess.run(
        _dispatch_argv(
            "--mode",
            "atdd_pure",
            "--project-id",
            "probe-skill-loading-design-wave",
            "--slice",
            "feature-end",
            "--wave",
            "design",
        ),
        capture_output=True,
        text=True,
        timeout=30,
        env=_isolated_dispatch_env(),
        cwd=str(tmp_path),
    )


def _run_distill_dispatch() -> subprocess.CompletedProcess[str]:
    """A `D_DISTILL` phase dispatch -- resolves to `nw-acceptance-designer`
    via `_PHASE_AGENTS`. Code-facing, but never the crafter."""
    return _run_dispatch(
        "--mode",
        "atdd_pure",
        "--project-id",
        "probe-skill-loading-distill",
        "--slice",
        "slice-01",
        "--phase",
        "D_DISTILL",
        *_contract_args(_REPO_ROOT, seed=False),
    )


#: ROOT CAUSE (graphify-proved, 2026-08-08): the retired `_DEFAULT_SKILL_
#: LOADING` constant hardcoded the software-crafter's OWN skill list and was
#: the fallback SKILL_LOADING body for EVERY agent this generator resolves
#: that is not one of the two non-code-facing overrides (examiner, charter
#: product-owner) -- including `nw-solution-architect` (design wave) and
#: `nw-acceptance-designer` (D_DISTILL), agents whose own `nWave/agents/
#: *.md` Skill Loading table names none of those crafter skills. The prior
#: exact-prose test below (`test_crafter_skill_loading_gains_the_yaml_
#: merged_content`) enshrined that leak by asserting the crafter's list
#: verbatim; it is REPLACED by the role-neutral properties below: every
#: code-facing agent's SKILL_LOADING must point at ITS OWN spec file by
#: name, never at another role's file or skill list.
_CODE_FACING_SKILL_LOADING_PROBES: dict[
    str, Callable[[], subprocess.CompletedProcess[str]]
] = {
    "nw-software-crafter": _run_crafter_dispatch,
    "nw-acceptance-designer": _run_distill_dispatch,
}

#: A crafter-only skill name that used to leak into every role's
#: SKILL_LOADING body via the retired hardcoded default -- never any role's
#: table but the crafter's own.
_CRAFTER_ONLY_SKILLS: tuple[str, ...] = (
    "nw-crafter-discipline-atdd-pure",
    "nw-code-design-oo",
    "nw-code-design-fp",
    "nw-refactor",
    "nw-mutation-test",
)


def test_skill_loading_points_each_code_facing_agent_at_its_own_spec_file() -> None:
    """Each code-facing dispatch's SKILL_LOADING must name ONLY the resolved
    agent's own spec file (`{agent}.md`) as the skill-loading SSOT, emit the
    `[SKILL LOADED]` observability marker instruction, and never name
    another probed role's spec file or a crafter-only skill (the exact
    defect the retired `_DEFAULT_SKILL_LOADING` body caused).
    """
    rendered: dict[str, str] = {}
    for agent, run in _CODE_FACING_SKILL_LOADING_PROBES.items():
        result = run()
        assert result.returncode == 0, (
            f"expected exit 0 for {agent}; got {result.returncode}. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        rendered[agent] = _section_text(result.stdout, "SKILL_LOADING")

    for agent, skill_loading in rendered.items():
        assert f"{agent}.md" in skill_loading, (
            f"{agent}'s SKILL_LOADING must point at its own spec file -- "
            f"got:\n{skill_loading}"
        )
        assert "[SKILL LOADED]" in skill_loading, (
            f"{agent}'s SKILL_LOADING must require the observable "
            f"`[SKILL LOADED]` marker -- got:\n{skill_loading}"
        )
        for other_agent in rendered:
            if other_agent != agent:
                assert f"{other_agent}.md" not in skill_loading, (
                    f"{agent}'s SKILL_LOADING must never name {other_agent}'s "
                    f"spec file -- got:\n{skill_loading}"
                )
        for skill in _CRAFTER_ONLY_SKILLS:
            if agent != "nw-software-crafter":
                assert skill not in skill_loading, (
                    f"{agent}'s SKILL_LOADING must never name the "
                    f"crafter-only skill {skill!r} -- got:\n{skill_loading}"
                )


def test_skill_loading_design_wave_points_at_the_architect_never_the_crafter(
    tmp_path: Path,
) -> None:
    """A `--wave design` dispatch resolves to `nw-solution-architect`
    (`_WAVE_AGENTS`) -- its SKILL_LOADING must point at
    `nw-solution-architect.md`, never at the crafter's spec file or any
    crafter-only skill (the exact leak the retired hardcoded default caused
    for every non-special-cased agent).
    """
    result = _run_design_wave_dispatch(tmp_path)
    assert result.returncode == 0, (
        f"expected exit 0; got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    skill_loading = _section_text(result.stdout, "SKILL_LOADING")

    assert "nw-solution-architect.md" in skill_loading, (
        f"design-wave SKILL_LOADING must point at nw-solution-architect.md -- "
        f"got:\n{skill_loading}"
    )
    assert "nw-software-crafter.md" not in skill_loading, (
        f"design-wave SKILL_LOADING must never point at the crafter's spec "
        f"file -- got:\n{skill_loading}"
    )
    for skill in _CRAFTER_ONLY_SKILLS:
        assert skill not in skill_loading, (
            f"design-wave SKILL_LOADING must never name the crafter-only "
            f"skill {skill!r} -- got:\n{skill_loading}"
        )


def test_crafter_quality_gates_gains_the_runner_agnostic_and_wiring_check_content() -> (
    None
):
    """QUALITY_GATES (crafter, `runs_tests=True`) must gain, from
    `atdd_pure.yaml` PLUS `nw-execute/SKILL.md` (design §3 row 7), the
    runner-agnostic mandate, the `uptime`/load>10 pause, the `src/des/**`
    import ban (F-D-09), the ruff+mypy-clean bullet, and the Skill-only
    wiring-check bullet.

    FAILS TODAY: the crafter's QUALITY_GATES body is
    "All the slice's ATs pass before commit. No new tests authored by the
    crafter.\\n" -- none of the five items below are present (verified).
    """
    result = _run_crafter_dispatch()
    assert result.returncode == 0, (
        f"expected exit 0; got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    quality_gates = _section_text(result.stdout, "QUALITY_GATES")

    assert "uv run python -m pytest" in quality_gates, (
        "QUALITY_GATES must name the project's resolved runner (design §3 "
        f"row 7, runner-agnostic mandate) -- got:\n{quality_gates}"
    )
    assert "NEVER a bare" in quality_gates and "python" in quality_gates, (
        "QUALITY_GATES must forbid a bare `python` invocation (target-"
        f"machine-agnostic mandate) -- got:\n{quality_gates}"
    )
    assert "load>10" in quality_gates, (
        "QUALITY_GATES must carry the `uptime`/load>10 pause bullet -- "
        f"got:\n{quality_gates}"
    )
    assert "scripts" in quality_gates and "F-D-09" in quality_gates, (
        "QUALITY_GATES must carry the src/des/** must NOT import scripts.* "
        f"(F-D-09) bullet -- got:\n{quality_gates}"
    )
    assert "ruff" in quality_gates and "mypy" in quality_gates, (
        f"QUALITY_GATES must carry the ruff+mypy-clean bullet -- got:\n{quality_gates}"
    )
    assert "Wiring check" in quality_gates, (
        "QUALITY_GATES must carry the Skill-only wiring-check bullet -- "
        f"got:\n{quality_gates}"
    )
    assert "files_to_modify" in quality_gates and "git diff" in quality_gates, (
        "the wiring-check bullet must name files_to_modify + git diff -- "
        f"got:\n{quality_gates}"
    )


def test_crafter_at_completion_ledger_gains_ledger_path_and_corrected_commit_ownership() -> (
    None
):
    """AT_COMPLETION_LEDGER (crafter) must gain the Skill's ledger-path +
    "records of truth" detail (design §3 row 8), corrected per Decision 4:
    the crafter commits via `des commit-slice` -- NEVER the superseded
    "orchestrator drives commit" claim the YAML carries, and never a stale
    `G_COMMIT` (legacy 7-phase) reference.

    FAILS TODAY: the crafter's AT_COMPLETION_LEDGER body is "Record phase
    outcomes to the AT-completion ledger.\\n" -- none of the positive items
    below are present (verified).
    """
    feature_id = "probe-ledger-merge"
    result = _run_crafter_dispatch(feature_id)
    assert result.returncode == 0, (
        f"expected exit 0; got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    ledger = _section_text(result.stdout, "AT_COMPLETION_LEDGER")

    assert ".nwave/telemetry/atdd-pure/" in ledger, (
        f"AT_COMPLETION_LEDGER must name the ledger path -- got:\n{ledger}"
    )
    assert "records of truth" in ledger.lower(), (
        f"AT_COMPLETION_LEDGER must carry the 'records of truth' detail "
        f"(design §3 row 8) -- got:\n{ledger}"
    )
    assert "des commit-slice" in ledger, (
        "AT_COMPLETION_LEDGER must correctly name the crafter committing "
        f"via `des commit-slice` (Decision 4) -- got:\n{ledger}"
    )
    assert "orchestrator drives commit" not in ledger.lower(), (
        "AT_COMPLETION_LEDGER must NOT carry the superseded "
        "'orchestrator drives commit' claim (Decision 4 names this WRONG) "
        f"-- got:\n{ledger}"
    )
    assert "G_COMMIT" not in ledger, (
        "AT_COMPLETION_LEDGER must not carry a stale legacy 7-phase "
        f"G_COMMIT reference (Decision 2) -- got:\n{ledger}"
    )


def test_crafter_boundary_rules_gains_the_four_concrete_skill_rules() -> None:
    """BOUNDARY_RULES (crafter, `runs_tests=True`) must gain the 4 concrete
    Skill-only rules named in design §3 row 10: the files_to_modify scope,
    the no-roadmap/no-step-log-in-atdd_pure rule, the no-AT-authorship rule,
    and the no-E_BATCH_REFACTOR/deep-review-here rule -- ON TOP OF the
    existing "stay within the slice's value statement" sentence (superset,
    never a replacement).

    FAILS TODAY: the crafter's BOUNDARY_RULES body is "Stay within slice
    {slice}'s value statement.\\n" -- none of the four items below are
    present (verified).
    """
    result = _run_crafter_dispatch()
    assert result.returncode == 0, (
        f"expected exit 0; got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    boundary = _section_text(result.stdout, "BOUNDARY_RULES")

    assert "files_to_modify" in boundary, (
        f"BOUNDARY_RULES must name the files_to_modify scope rule -- got:\n{boundary}"
    )
    assert "roadmap" in boundary.lower() and "step log" in boundary.lower(), (
        "BOUNDARY_RULES must name the no-roadmap/no-step-log-in-atdd_pure "
        f"rule -- got:\n{boundary}"
    )
    assert "acceptance test" in boundary.lower() and (
        "do not author" in boundary.lower() or "not author" in boundary.lower()
    ), f"BOUNDARY_RULES must name the no-AT-authorship rule -- got:\n{boundary}"
    assert "E_BATCH_REFACTOR" in boundary, (
        "BOUNDARY_RULES must name the no-E_BATCH_REFACTOR/deep-review-here "
        f"rule -- got:\n{boundary}"
    )
    assert "slice-01" in boundary and "value statement" in boundary, (
        "the pre-existing 'stay within the slice's value statement' "
        f"sentence must remain (superset, never replaced) -- got:\n{boundary}"
    )


def test_crafter_terminating_run_uses_a_project_declared_command() -> None:
    """TERMINATING_RUN refuses to invent a command after runner retirement."""
    result = _run_crafter_dispatch()
    assert result.returncode == 0, (
        f"expected exit 0; got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    terminating = _section_text(result.stdout, "TERMINATING_RUN")

    assert "project-declared focused test command" in terminating, terminating
    assert "if no command is declared" in terminating, terminating
    assert "Report files created/modified" in terminating, (
        "the pre-existing 'report files created/modified' sentence must "
        f"remain (superset, never replaced) -- got:\n{terminating}"
    )


def test_crafter_timeout_instruction_gains_the_sendmessage_and_verbatim_evidence_mandates() -> (
    None
):
    """TIMEOUT_INSTRUCTION (crafter) must gain, from `atdd_pure.yaml`
    (design §3 row 12), the SendMessage-is-the-return-value mandate and the
    verbatim-evidence-on-repeat mandate -- ON TOP OF the existing
    `_NO_BACKGROUND_TURN_CLOSE` constant (superset, never a replacement).

    FAILS TODAY: neither mandate's text is present in the crafter's
    TIMEOUT_INSTRUCTION body (verified).
    """
    result = _run_crafter_dispatch()
    assert result.returncode == 0, (
        f"expected exit 0; got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    timeout = _section_text(result.stdout, "TIMEOUT_INSTRUCTION")

    assert "SendMessage" in timeout, (
        "TIMEOUT_INSTRUCTION must carry the SendMessage-is-the-return-value "
        f"mandate -- got:\n{timeout}"
    )
    assert "return value" in timeout.lower(), (
        f"TIMEOUT_INSTRUCTION must say the final message IS the return "
        f"value -- got:\n{timeout}"
    )
    assert "already done" in timeout.lower() and "evidence" in timeout.lower(), (
        "TIMEOUT_INSTRUCTION must carry the verbatim-evidence-on-repeat "
        f"mandate (reply with evidence for work already done) -- got:\n{timeout}"
    )
    assert "Never end your turn waiting for a background job" in timeout, (
        "the pre-existing _NO_BACKGROUND_TURN_CLOSE constant must remain "
        f"(superset, never replaced) -- got:\n{timeout}"
    )


def test_crafter_des_metadata_restores_a_command_line() -> None:
    """DES_METADATA (crafter) must gain a `Command:` line back (design §3
    row 1 + Decision 3): DERIVED from the already-declared `--wave`/`--lane`,
    never a new `--command` CLI flag -- this AT pins only the non-negotiable
    behavioural requirement (the line exists and is non-empty for a
    dispatch whose wave IS honestly derivable, i.e. `deliver`), leaving the
    EXACT command string to the crafter (Decision 3 also permits omitting
    the line entirely for a wave/lane pair with no honest derivation).

    FAILS TODAY: the crafter's DES_METADATA body is "Slice: ...\\nFeature:
    ...\\nPhase: A_GREEN\\n" -- no `Command:` line at all (verified).
    """
    result = _run_crafter_dispatch()
    assert result.returncode == 0, (
        f"expected exit 0; got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    des_metadata = _section_text(result.stdout, "DES_METADATA")

    assert re.search(r"(?m)^Command: \S", des_metadata) is not None, (
        "DES_METADATA must restore a non-empty `Command:` line for a "
        f"dispatch whose wave (deliver) is honestly derivable -- got:\n{des_metadata}"
    )


# --- half 2: every OTHER role branch keeps rendering its own body ----------
# (currently GREEN -- these pin TODAY's correct behavior so the crafter-path
# merge above cannot flatten the role branching while making it pass; per
# the standing mandate "pin the correct behaviour of neighbouring branches.")


def test_examiner_unarmed_dispatch_body_is_unperturbed_by_the_crafter_merge(
    tmp_path: Path,
) -> None:
    """The examiner's UNARMED C_REVIEWER_AUDIT dispatch (no charter
    directory for the feature) must keep rendering its own
    non-code-facing SKILL_LOADING/QUALITY_GATES/DESIGN_CONTEXT bodies
    UNCHANGED -- none of the crafter-path merge content belongs here.
    """
    result = subprocess.run(
        _dispatch_argv(
            "--mode",
            "atdd_pure",
            "--project-id",
            "probe-examiner-unarmed",
            "--slice",
            "slice-01",
            "--phase",
            "C_REVIEWER_AUDIT",
            *_contract_args(tmp_path),
        ),
        capture_output=True,
        text=True,
        timeout=30,
        env=_isolated_dispatch_env(),
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, (
        f"expected exit 0; got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    prompt = result.stdout

    skill_loading = _section_text(prompt, "SKILL_LOADING")
    assert skill_loading == (
        "No technical or code-reasoning skills to load -- examining is not "
        "implementation, and code-reasoning knowledge corrupts the examiner's "
        "epistemology.\n"
    ), f"examiner SKILL_LOADING must stay unchanged -- got:\n{skill_loading}"

    quality_gates = _section_text(prompt, "QUALITY_GATES")
    assert quality_gates == (
        "There are no tests to run and no ATs to author. Exercise the real "
        "product surface directly and form a verdict on what you observed.\n"
    ), f"examiner QUALITY_GATES must stay unchanged -- got:\n{quality_gates}"

    design_context = _section_text(prompt, "DESIGN_CONTEXT")
    assert design_context.startswith(
        "N/A -- this dispatch is non-code-facing by ROLE INTENT"
    ), f"examiner DESIGN_CONTEXT must stay non-code-facing -- got:\n{design_context}"


def test_charter_product_owner_dispatch_body_is_unperturbed_by_the_crafter_merge(
    tmp_path: Path,
) -> None:
    """The charter-authoring product-owner (`--lane charter`) must keep
    rendering its own SKILL_LOADING/QUALITY_GATES/DESIGN_CONTEXT bodies
    UNCHANGED -- in particular it must never gain the crafter's TDD/quality
    skill-loading, which the RCA this branch exists to fix explicitly
    forbade (nw-tdd-methodology corrupts the charter-authoring epistemology).
    """
    result = subprocess.run(
        _dispatch_argv(
            "--mode",
            "atdd_pure",
            "--project-id",
            "probe-charter-lane",
            "--slice",
            "slice-01",
            "--lane",
            "charter",
        ),
        capture_output=True,
        text=True,
        timeout=30,
        env=_isolated_dispatch_env(),
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, (
        f"expected exit 0; got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    prompt = result.stdout

    skill_loading = _section_text(prompt, "SKILL_LOADING")
    assert skill_loading == (
        "Load nw-expectation-charter for charter-authoring competence -- no "
        "code-reasoning or TDD/quality-framework skills; charter authoring is "
        "not implementation.\n"
    ), (
        f"charter product-owner SKILL_LOADING must stay unchanged -- got:\n{skill_loading}"
    )
    assert "nw-tdd-methodology" not in skill_loading, (
        "charter product-owner must NEVER gain the crafter's TDD skill-"
        f"loading -- got:\n{skill_loading}"
    )

    design_context = _section_text(prompt, "DESIGN_CONTEXT")
    assert design_context.startswith(
        "N/A -- this dispatch is non-code-facing by ROLE INTENT"
    ), (
        f"charter product-owner DESIGN_CONTEXT must stay non-code-facing -- got:\n{design_context}"
    )


def test_phaseless_authoring_wave_dispatch_body_is_unperturbed_by_the_crafter_merge(
    tmp_path: Path,
) -> None:
    """A phaseless authoring-wave dispatch (`--wave design`, no `--phase`,
    no `--lane`) must keep rendering its OWN QUALITY_GATES/BOUNDARY_RULES
    bodies UNCHANGED (the "the {wave} wave's own gate stack decides this
    dispatch..." / "Produce only the {wave} wave's artifacts..." bodies) --
    the crafter-path merge must never leak into a wave that writes no code
    and runs no tests.
    """
    result = subprocess.run(
        _dispatch_argv(
            "--mode",
            "atdd_pure",
            "--project-id",
            "probe-design-wave",
            "--slice",
            "feature-end",
            "--wave",
            "design",
        ),
        capture_output=True,
        text=True,
        timeout=30,
        env=_isolated_dispatch_env(),
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, (
        f"expected exit 0; got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    prompt = result.stdout

    quality_gates = _section_text(prompt, "QUALITY_GATES")
    assert quality_gates == (
        "The design wave's own gate stack decides this dispatch "
        "(see nWave/waves/design.yaml for the authoritative gate-ids and "
        "the output contract). Author the wave's [REF] sections; run no "
        "tests and write no production code.\n"
    ), f"design-wave QUALITY_GATES must stay unchanged -- got:\n{quality_gates}"

    boundary = _section_text(prompt, "BOUNDARY_RULES")
    assert boundary == (
        "Produce only the design wave's artifacts. Do NOT implement, "
        "and do NOT pre-empt a downstream wave's decisions.\n"
    ), f"design-wave BOUNDARY_RULES must stay unchanged -- got:\n{boundary}"


def test_armed_middle_slot_dispatch_body_is_unperturbed_by_the_crafter_merge(
    tmp_path: Path,
) -> None:
    """A C_REVIEWER_AUDIT dispatch ARMED by a slice-mapped expectation
    charter must keep rendering `_armed_middle_slot_section_body`'s
    charter-only envelope UNCHANGED -- SKILL_LOADING and QUALITY_GATES stay
    the charter-only prose; TASK_CONTEXT names the charter path -- none of
    the crafter-path merge content belongs in this envelope either.
    """
    feature_id = "probe-armed-middle-slot"
    charter_dir = tmp_path / "docs" / "product" / "expectations" / feature_id
    charter_dir.mkdir(parents=True)
    (charter_dir / "the-outcome.md").write_text(
        "# Some Charter\n\nSpec rows: slice-01\n", encoding="utf-8"
    )

    result = subprocess.run(
        _dispatch_argv(
            "--mode",
            "atdd_pure",
            "--project-id",
            feature_id,
            "--slice",
            "slice-01",
            "--phase",
            "C_REVIEWER_AUDIT",
            *_contract_args(tmp_path),
        ),
        capture_output=True,
        text=True,
        timeout=30,
        env=_isolated_dispatch_env(),
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, (
        f"expected exit 0; got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    prompt = result.stdout

    skill_loading = _section_text(prompt, "SKILL_LOADING")
    assert skill_loading == (
        "Your only specification is the named expectation charter. "
        "Do not load technical or code-reasoning skills.\n"
    ), f"armed middle slot SKILL_LOADING must stay unchanged -- got:\n{skill_loading}"

    quality_gates = _section_text(prompt, "QUALITY_GATES")
    assert quality_gates == (
        "Exercise the real product surface directly; do not substitute "
        "an implementation review for observation.\n"
    ), f"armed middle slot QUALITY_GATES must stay unchanged -- got:\n{quality_gates}"

    task_context = _section_text(prompt, "TASK_CONTEXT")
    assert "the-outcome.md" in task_context, (
        f"armed middle slot TASK_CONTEXT must name the charter path -- got:\n{task_context}"
    )
    assert "Walk the promised outcome through the real surface" in task_context, (
        "armed middle slot TASK_CONTEXT must keep its charter-only "
        f"instruction -- got:\n{task_context}"
    )


# ---------------------------------------------------------------------------
# AT-8 -- slice-02 SSOT reconciliation: dead-field removal + render invariance
# (dispatch-template-ssot-reconciliation, mikado D12)
#
# Design: docs/feature/dispatch-template-ssot-reconciliation/design/
#         dispatch-template-ssot-reconciliation-design.md §4 (Component
#         decomposition -- markers[]/sections[].template RETIRED) + §7 Slice
#         Plan row 2. Feature delta:
#         docs/feature/dispatch-template-ssot-reconciliation/feature-delta.md,
#         DISCUSS DoD item 2 + Slice Plan row slice-02.
#
# THE POINT: `nWave/dispatch/atdd_pure.yaml`'s `sections[].template` field and
# top-level `markers:` block are VERIFIED dead -- `dispatch.py:40` imports
# ONLY `_read_full_sections` (profiles.full.sections) from
# `dispatch_lane_ssot`, never a `template` key reader; `_read_marker_syntax`
# reads `vendors.yaml`, never this file's `markers:` block. Confirmed
# empirically (2026-08-03): stripping both fields from a working copy leaves
# every rendered dispatch shape below byte-identical but for the one
# genuinely non-deterministic marker (`DES-CAUSAL-ID`, `uuid.uuid4().hex` --
# `dispatch.py:1346`). The header comment mislabels both fields as
# consumed ("RENDERS a dispatch from this" / "filled by the renderer");
# `sections[].id` entries MUST survive -- `profiles.full.sections` genuinely
# reads them (AT-3 above already locks that).
#
# Reuse: this file already owns `_DISPATCH_YAML` (the real-file fixture),
# `_read_full_sections` (imported for AT-3), and the subprocess driving-port
# helpers (`_dispatch_argv`/`_dispatch_env`/`_isolated_dispatch_env`) AT-3/
# AT-5/AT-7 already drive the identical SSOT through -- extended here rather
# than a parallel harness.
# `test_lane_profile_dispatch_ssot_drift_check.py` drift-checks
# `profiles.lane` vs `LANE_PROFILES` -- a DIFFERENT YAML block entirely; not
# the right home for a `sections[].template`/`markers:` deletion assertion.
#
# CONTRACT_SHAPE: bounded-change (finite, closed-world YAML-shape + render-
# diff over a hand-authored SSOT file -- example-based, no PBT).
#
# covers: F-dispatch-template-ssot-reconciliation (D12, slice-02)
# ---------------------------------------------------------------------------

_DEAD_FIELD_TOKENS: tuple[str, ...] = ("template:", "markers:")

_CAUSAL_ID_LINE_PATTERN = re.compile(r"<!-- DES-CAUSAL-ID : [0-9a-f]{32} -->")


def _header_comment_block(text: str) -> str:
    """The file's leading contiguous `#`-prefixed comment block, ending at
    the first non-comment, non-blank line (`version: 1`) -- the prose the
    DoD's "header comment must claim only what is true" targets."""
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("#"):
            lines.append(line)
        elif line.strip() == "":
            continue
        else:
            break
    return "\n".join(lines)


def test_slice02_dispatch_ssot_yaml_sheds_dead_fields_but_keeps_section_ids() -> None:
    """(property 1) `nWave/dispatch/atdd_pure.yaml` must carry NO
    `sections[].template` field and NO `markers:` block, and its header
    comment must no longer claim `des dispatch` consumes either --
    `sections[].id` entries SURVIVE because `profiles.full.sections`
    genuinely reads them (AT-3 above).

    FAILS TODAY: the real committed file still declares 12 `template: |`
    block scalars plus a `markers:` block (verified), and its header claims
    `des dispatch` "RENDERS a dispatch from this" while a sibling comment
    calls `sections[].template` "each section's scaffold template ...
    filled by the renderer" -- both fields are verified zero-reader dead
    weight (see the module docstring above).
    """
    text = _DISPATCH_YAML.read_text(encoding="utf-8")

    for token in _DEAD_FIELD_TOKENS:
        assert token not in text, (
            f"nWave/dispatch/atdd_pure.yaml must carry no {token!r} -- "
            "verified zero readers (dispatch.py:40 imports only "
            "_read_full_sections; _read_marker_syntax reads vendors.yaml, "
            f"never this file's markers: block). Found {token!r} in the "
            "committed YAML."
        )

    parsed = yaml.safe_load(text)
    section_ids = [section["id"] for section in parsed["sections"]]
    assert section_ids == list(_read_full_sections(text)), (
        "sections[].id entries must survive the deletion, in the SAME "
        f"order profiles.full.sections declares -- got {section_ids!r}"
    )
    assert len(section_ids) == 12, (
        f"expected all 12 canonical section ids to survive; got {section_ids!r}"
    )

    header = _header_comment_block(text).lower()
    for false_claim_token in ("template", "markers"):
        assert false_claim_token not in header, (
            "the header comment must no longer claim des dispatch consumes "
            f"a {false_claim_token!r} field it no longer carries -- header "
            f"block:\n{_header_comment_block(text)}"
        )


def _strip_dead_yaml_fields(text: str) -> str:
    """Programmatically strip the top-level `markers:` block and every
    `template: |` block-scalar entry from a dispatch SSOT YAML text --
    mirrors exactly what slice-02 does to the real file, applied to a
    disposable working copy so this AT never depends on whether the real
    repo's file has been edited yet (it works identically before AND after)."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.rstrip("\n") == "markers:":
            i += 1
            while i < len(lines) and (
                lines[i].startswith("  ")
                or lines[i].startswith("#")
                or lines[i].strip() == ""
            ):
                i += 1
            continue
        out.append(line)
        i += 1
    text = "".join(out)

    lines = text.splitlines(keepends=True)
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == "template: |":
            indent = len(line) - len(line.lstrip(" "))
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() == "":
                    i += 1
                    continue
                nxt_indent = len(nxt) - len(nxt.lstrip(" "))
                if nxt_indent > indent:
                    i += 1
                    continue
                break
            continue
        out.append(line)
        i += 1
    return "".join(out)


def _mask_volatile_markers(prompt: str) -> str:
    """Mask the one genuinely non-deterministic marker (`DES-CAUSAL-ID`,
    `uuid.uuid4().hex` per dispatch.py:1346) so two renders of otherwise
    identical input compare byte-identical."""
    return _CAUSAL_ID_LINE_PATTERN.sub("<!-- DES-CAUSAL-ID : MASKED -->", prompt)


#: A representative sample of dispatch shapes spanning the role/lane
#: branches AT-1/AT-2/AT-7 already exercise (plain crafter, bugfix lane,
#: prefactoring lane, charter lane, phaseless authoring wave) -- broad enough
#: that a field genuinely read by ANY branch would surface a divergence.
_INVARIANCE_DISPATCH_SHAPES: tuple[tuple[str, ...], ...] = (
    (
        "--mode",
        "atdd_pure",
        "--project-id",
        "demo",
        "--slice",
        "slice-01",
        "--phase",
        "A_GREEN",
        "--intent",
        "probe render invariance",
    ),
    (
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
        "probe defect",
        "--regression-test",
        "test_probe",
    ),
    (
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
    ),
    (
        "--mode",
        "atdd_pure",
        "--project-id",
        "demo",
        "--slice",
        "slice-01",
        "--lane",
        "charter",
    ),
    (
        "--mode",
        "atdd_pure",
        "--project-id",
        "demo",
        "--slice",
        "feature-end",
        "--wave",
        "design",
    ),
)


def _render_all_shapes(workspace: Path) -> list[str]:
    """Render every `_INVARIANCE_DISPATCH_SHAPES` entry against `workspace`
    (via `--repo-root`) and return the masked stdout for each, in order.
    Every phase-bearing (test-running) shape also gets the `--delivery-
    contract` pair seeded under `workspace`; the phaseless authoring-wave and
    `--lane charter` shapes stay contract-free."""
    renders = []
    for shape in _INVARIANCE_DISPATCH_SHAPES:
        extra_args = (
            _contract_args(workspace)
            if "--phase" in shape
            else ("--repo-root", str(workspace))
        )
        result = subprocess.run(
            _dispatch_argv(*shape, *extra_args),
            capture_output=True,
            text=True,
            timeout=30,
            env=_isolated_dispatch_env(),
            cwd=str(workspace),
        )
        assert result.returncode == 0, (
            f"expected exit 0 for shape {shape!r} against {workspace}; got "
            f"{result.returncode}. stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        renders.append(_mask_volatile_markers(result.stdout))
    return renders


def test_slice02_dispatch_render_is_byte_identical_before_and_after_the_yaml_deletion(
    tmp_path: Path,
) -> None:
    """(property 2, render-invariance) `des dispatch` must render BYTE-
    IDENTICAL output (modulo the DES-CAUSAL-ID per-invocation uuid, masked
    above) for every dispatch shape in `_INVARIANCE_DISPATCH_SHAPES`,
    comparing a render taken BEFORE the dead-field deletion against one taken
    AFTER -- both captured from the SAME `--repo-root` workspace, so only the
    YAML mutation (never a path/cwd/agent-resolution difference) can explain
    a divergence. This is the mechanical proof the two fields were truly
    unread: it holds NOW (they are dead already, per the module docstring
    above) and must keep holding once slice-02 physically deletes them from
    the real file -- the render is unperturbed either way.

    Deliberately NOT hand-transcribed expected bytes and NOT a committed
    golden file (the deletion could silently invalidate a golden fixture) --
    the baseline is captured fresh, inside this test, from whatever
    `des dispatch` currently emits against a disposable working copy.
    """
    dispatch_dir = tmp_path / "nWave" / "dispatch"
    dispatch_dir.mkdir(parents=True)
    yaml_path = dispatch_dir / "atdd_pure.yaml"
    yaml_path.write_text(_DISPATCH_YAML.read_text(encoding="utf-8"), encoding="utf-8")
    vendors_src = _REPO_ROOT / "nWave" / "dispatch" / "vendors.yaml"
    (dispatch_dir / "vendors.yaml").write_text(
        vendors_src.read_text(encoding="utf-8"), encoding="utf-8"
    )

    before_renders = _render_all_shapes(tmp_path)

    mutated_text = _strip_dead_yaml_fields(yaml_path.read_text(encoding="utf-8"))
    for token in _DEAD_FIELD_TOKENS:
        assert token not in mutated_text, (
            f"fixture bug: _strip_dead_yaml_fields must remove {token!r} "
            f"from the working copy -- mutated text:\n{mutated_text}"
        )
    yaml_path.write_text(mutated_text, encoding="utf-8")

    after_renders = _render_all_shapes(tmp_path)

    for shape, before, after in zip(
        _INVARIANCE_DISPATCH_SHAPES, before_renders, after_renders, strict=True
    ):
        assert before == after, (
            "des dispatch must render byte-identical output before/after "
            f"deleting sections[].template + markers: for shape {shape!r} "
            "-- this is the proof the fields were truly unread.\n"
            f"BEFORE:\n{before}\nAFTER:\n{after}"
        )

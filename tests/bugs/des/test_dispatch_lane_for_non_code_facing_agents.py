"""Regression ATs -- fix-po-charter-dispatch-marker-lane.

RCA: docs/feature/fix-po-charter-dispatch-marker-lane/deliver/rca.md

ONE root cause, two faces: the atdd_pure dispatch contract assumes every
dispatched agent is CODE-FACING. Two agents the spine itself MANDATES are
not, and the contract has no lane for either.

  * Face A (RCA §2-§4, §7): a PO-charter-authoring dispatch (`nw-bugfix`
    Phase 0-charter / `nw-deliver` EXAMINE-arming) has no honest envelope.
    The ONLY passing shape BORROWS `DES-PHASE: D_DISTILL` +
    `DES-SLICE: feature-end` -- a semantic falsehood (`D_DISTILL` names "the
    upstream DISTILL-wave acceptance-designer RETURN",
    `atdd_pure_phases.py:70-71`) that then corrupts the SubagentStop
    DISTILL-exit check (RCA §4a, live-reproduced: the RCA agent investigating
    this bug BECAME its victim).
  * Face B (RCA §4): `des dispatch --phase C_REVIEWER_AUDIT` (the EXAMINE
    slot) generates an envelope naming `nw-software-crafter` +
    `nw-tdd-methodology` -- precisely what `nw-user-examiner` (Vera) must
    NOT have (her spec forbids technical skills and source/design access BY
    CONSTRUCTION).

Driving surfaces (Mandate-16, pytest-regression convention already
established by `tests/des/acceptance/distill_signoff_feature_end_wiring/
steps/composition.py` and `tests/des/acceptance/wave_dispatch_exemption_ssot/
steps/composition.py`): the real `des dispatch` CLI module (`des.cli.
dispatch.main`), the real production `PreToolUseService`
(`service_factory.create_pre_tool_use_service`), and the real SubagentStop
DISTILL-exit gate handler (`subagent_stop_handler._handle_distill_exit_gate`)
-- driven in-process, never a decomposed/re-implemented stand-in.

Author-only regression test -- no production code touched (per dispatch
instruction). Every assertion below is a REAL assertion on observable
behaviour of shipped production code; a failure is a semantic AssertionError,
never an import/collection error (Mandate 7 -- RED-not-BROKEN).

covers: fix-po-charter-dispatch-marker-lane (Face A + Face B, both faces of
the one root cause: closed phase/wave vocabulary with no lane for a
spine-mandated, cross-wave control/utility sub-dispatch)
"""

from __future__ import annotations

import contextlib
import io
import json
import uuid
from pathlib import Path

import pytest

from des.adapters.driven.filesystem.wave_active_filesystem_store import (
    WaveActiveFilesystemStore,
)
from des.adapters.driven.logging.null_audit_log_writer import NullAuditLogWriter
from des.adapters.drivers.hooks import service_factory, subagent_stop_handler
from des.application.atdd_pure_prompt_validator import _REVIEW_PROFILE_SECTIONS
from des.cli import dispatch
from des.domain.wave_active import WaveActiveRecord, WaveProvenance
from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput


# tests/bugs/des/<this file> -> parents[3] == checkout root (mirrors the
# established `tests/des/acceptance/wave_dispatch_exemption_ssot/steps/
# composition.py` REPO_ROOT resolution style).
_REPO_ROOT = Path(__file__).resolve().parents[3]

# The claude_code vendor's marker rendering, verbatim
# (`nWave/dispatch/vendors.yaml:marker_syntax`) -- mirrors
# `tests/des/unit/cli/test_des_dispatch_generator.py`.
_MARKER_SYNTAX = "<!-- {key} : {value} -->"


def _marker(key: str, value: str) -> str:
    return _MARKER_SYNTAX.format(key=key, value=value)


def _run_dispatch_main(argv: list[str]) -> tuple[int, str, str]:
    """Drive `des dispatch`'s real `main()` in-process; capture exit/stdout/stderr.

    `main()` uses `argparse`, which raises `SystemExit` for a usage error
    (missing required arg / invalid choice) -- caught here so the test body
    asserts a real, semantic `AssertionError` on the observed exit code,
    never an uncaught `SystemExit` crash.
    """
    stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
    try:
        with (
            contextlib.redirect_stdout(stdout_buf),
            contextlib.redirect_stderr(stderr_buf),
        ):
            exit_code = dispatch.main(argv)
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
    return exit_code, stdout_buf.getvalue(), stderr_buf.getvalue()


def _examine_section_body(section_id: str) -> str:
    """Minimal body per review-profile section; DESIGN_CONTEXT is deliberately
    citation-free (no DDD/ADR/SYS id, no feature-delta.md path, no brief.md) --
    the exact shape `design_context_carries_architecture` refuses today."""
    if section_id == "DESIGN_CONTEXT":
        return "N/A -- Vera the examiner has no source or design access by design.\n"
    return "ok\n"


def _build_examine_prompt_without_design_citation(feature_id: str) -> str:
    """A well-formed atdd_pure C_REVIEWER_AUDIT (EXAMINE) dispatch prompt,
    carrying the real 7-section review profile (`_REVIEW_PROFILE_SECTIONS`,
    the SAME SSOT `AtddPurePromptValidator` selects for a review dispatch),
    but with NO real architecture citation in DESIGN_CONTEXT."""
    marker_lines = [
        _marker("DES-VALIDATION", "required"),
        _marker("DES-PROJECT-ID", feature_id),
        _marker("DES-MODE", "atdd_pure"),
        _marker("DES-PHASE", "C_REVIEWER_AUDIT"),
        _marker("DES-SLICE", "slice-01"),
    ]
    section_lines = [
        f"# {section_id}\n{_examine_section_body(section_id)}"
        for section_id in _REVIEW_PROFILE_SECTIONS
    ]
    return "\n".join(marker_lines) + "\n\n" + "\n".join(section_lines) + "\n"


# ---------------------------------------------------------------------------
# 1. A charter-authoring dispatch has an honest envelope (RCA Face A, §7(a)).
# ---------------------------------------------------------------------------


def test_charter_dispatch_envelope_generated_honestly_without_borrowing_d_distill() -> (
    None
):
    """`des dispatch` must GENERATE a valid envelope for a PO authoring an
    expectation charter, WITHOUT requiring a DELIVER `--phase` (charter
    authoring is not one of the 3 canonical DELIVER phases, RCA §7(a):
    `ATDDPurePhase` "stays DELIVER-carpaccio-scoped per its own docstring")
    and WITHOUT declaring `D_DISTILL` (which specifically claims to be "the
    DISTILL-wave acceptance-designer return", `atdd_pure_phases.py:70-71`).

    FAILS TODAY: `--phase` is `required=True` (no charter-shaped dispatch can
    omit it) and `--lane charter` is not a member of `LANE_PROFILES`
    (`{"prefactoring", "bugfix"}` only) -- so this invocation, mirroring the
    RCA's own recommended `--lane charter --agent nw-product-owner` shape
    (§7(a)), is refused by argparse today.
    """
    feature_id = f"probe-charter-{uuid.uuid4().hex[:8]}"
    exit_code, stdout, stderr = _run_dispatch_main(
        [
            "--mode",
            "atdd_pure",
            "--project-id",
            feature_id,
            "--slice",
            "slice-01",
            "--lane",
            "charter",
            "--intent",
            "author the expectation charter for slice-01",
            "--repo-root",
            str(_REPO_ROOT),
        ]
    )

    assert exit_code == 0, (
        "`des dispatch` must be able to GENERATE an honest envelope for a "
        "PO charter-authoring dispatch (RCA §7(a) recommendation: `--lane "
        "charter --agent nw-product-owner`, independent of `ATDDPurePhase` "
        "which stays DELIVER-carpaccio-scoped) -- today `--phase` is "
        "required and `--lane charter` is not a recognised lane, so this "
        f"invocation is refused by argparse. exit_code={exit_code}, "
        f"stderr={stderr!r}"
    )
    assert "Agent: nw-product-owner" in stdout, (
        "the generated charter envelope must name nw-product-owner as the "
        f"dispatched agent (AGENT_IDENTITY section). stdout={stdout!r}"
    )
    assert "<!-- DES-PHASE : D_DISTILL -->" not in stdout, (
        "a charter-authoring dispatch must NOT declare D_DISTILL -- that "
        "marker specifically asserts 'the DISTILL-wave acceptance-designer "
        "return' (atdd_pure_phases.py:70-71), which a PO-charter dispatch "
        f"is not (RCA §5: this borrowing corrupts the audit trail). "
        f"stdout={stdout!r}"
    )


# ---------------------------------------------------------------------------
# 2. The EXAMINE envelope names the EXAMINER, not the crafter (RCA Face B).
# ---------------------------------------------------------------------------


def test_examine_envelope_names_examiner_not_crafter() -> None:
    """A `C_REVIEWER_AUDIT` (EXAMINE) envelope generated by `des dispatch`
    must name `nw-user-examiner`, and must NEVER instruct the loading of
    technical/code-reasoning skills.

    NEGATIVE AT (anti-recurrence, RCA Face B): today `des dispatch --phase
    C_REVIEWER_AUDIT` emits BOTH `Agent: nw-software-crafter` (the
    `_DEFAULT_AGENT` fallback -- only `D_DISTILL` is overridden in
    `_PHASE_AGENTS`) AND `nw-tdd-methodology` (the hardcoded SKILL_LOADING
    body, identical for every phase) -- precisely what Vera's spec forbids
    by construction ("an examiner who reads code becomes a sixth inspector").
    """
    feature_id = f"probe-examine-{uuid.uuid4().hex[:8]}"
    exit_code, stdout, stderr = _run_dispatch_main(
        [
            "--mode",
            "atdd_pure",
            "--project-id",
            feature_id,
            "--slice",
            "slice-01",
            "--phase",
            "C_REVIEWER_AUDIT",
            "--intent",
            "examine slice-01's charter",
            "--repo-root",
            str(_REPO_ROOT),
        ]
    )
    assert exit_code == 0, (
        f"dispatch generation itself must succeed for C_REVIEWER_AUDIT "
        f"today. exit_code={exit_code}, stderr={stderr!r}"
    )

    assert "Agent: nw-user-examiner" in stdout, (
        "a C_REVIEWER_AUDIT (EXAMINE) envelope must name nw-user-examiner as "
        f"the dispatched agent, not the default crafter. stdout={stdout!r}"
    )
    assert "Agent: nw-software-crafter" not in stdout, (
        "NEGATIVE AT: the EXAMINE envelope must never name "
        "nw-software-crafter -- Vera (nw-user-examiner) is a non-technical "
        "demanding beta tester; handing her the crafter identity is the "
        f"loaded-gun defect this RCA names. stdout={stdout!r}"
    )
    assert "nw-tdd-methodology" not in stdout, (
        "NEGATIVE AT: the EXAMINE envelope must never instruct loading "
        "technical/code-reasoning skills (nw-tdd-methodology) -- Vera's "
        "spec forbids source/design access by construction. "
        f"stdout={stdout!r}"
    )


# ---------------------------------------------------------------------------
# 3. DESIGN_CONTEXT is not forced on a non-code-facing dispatch (RCA Face B).
# ---------------------------------------------------------------------------


def test_dispatch_guard_accepts_examiner_dispatch_without_architecture_citation() -> (
    None
):
    """The dispatch guard (the real, production-wired `PreToolUseService`)
    must ACCEPT an examiner (`nw-user-examiner`) dispatch that carries no
    architecture citation in DESIGN_CONTEXT.

    NEGATIVE AT: the guard must NEVER refuse an examiner dispatch *for
    lacking design context* -- the examiner's exclusion from design is the
    instrument, not an omission.

    FAILS TODAY: `AtddPurePromptValidator` selects the 7-section REVIEW
    profile for a `C_REVIEWER_AUDIT` dispatch (`_REVIEW_PROFILE_SECTIONS`),
    which still includes DESIGN_CONTEXT -- and the SAME
    `design_context_carries_architecture` content-presence gate an
    implementation dispatch is held to fires on a citation-free body,
    refusing the dispatch.
    """
    feature_id = f"probe-guard-{uuid.uuid4().hex[:8]}"
    prompt = _build_examine_prompt_without_design_citation(feature_id)

    service = service_factory.create_pre_tool_use_service(
        audit_writer_factory=lambda: NullAuditLogWriter()
    )
    decision = service.validate(
        PreToolUseInput(
            prompt=prompt, subagent_type="nw-user-examiner", wave_entering=False
        )
    )

    assert decision.action == "allow", (
        "the dispatch guard must ACCEPT an examiner dispatch carrying NO "
        "architecture citation in DESIGN_CONTEXT (Vera's exclusion from "
        "design is the instrument, not an omission) -- today "
        "AtddPurePromptValidator applies the SAME "
        "design_context_carries_architecture content-presence gate to the "
        f"review profile, so it refuses. decision={decision!r}"
    )
    reason = decision.reason or ""
    assert "DESIGN_CONTEXT carries no architecture citation" not in reason, (
        "NEGATIVE AT: an examiner dispatch must never be refused for "
        "lacking design context -- that is Vera's exclusion by design, "
        f"never a defect to fix by adding a citation. reason={reason!r}"
    )


# ---------------------------------------------------------------------------
# 4. The exit check does not misread a borrowed/cross-wave-child return
#    (RCA §4a -- live-reproduced against the RCA agent itself).
# ---------------------------------------------------------------------------


def test_distill_exit_gate_does_not_misread_cross_wave_child_return(
    tmp_path: Path, capsys
) -> None:
    """A charter/examine sub-dispatch returning inside an ACTIVE `deliver`
    wave -- using the ONLY envelope that passes entry today (the borrowed
    `DES-PHASE: D_DISTILL` + `DES-SLICE: feature-end` declaration, RCA §2
    table) -- must NOT be treated by the SubagentStop DISTILL-exit check as
    a completed whole-feature DISTILL. The honest declaration must be exempt
    at EXIT as well as at ENTRY (RCA §4a).

    NEGATIVE AT: no rejection loop -- the exit-gate handler must not demand
    a slice plan from a `feature-delta.md` that legitimately does not exist
    for this feature-id (this was never a real feature-wide DISTILL wave).

    FAILS TODAY: `_handle_distill_exit_gate` unconditionally treats an
    `atdd_pure_phase == "D_DISTILL"` + `slice_id == "feature-end"` return as
    a real DISTILL-wave completion and calls `_slice_plan_slice_ids`, which
    raises `FileNotFoundError` for a feature-id with no feature-delta.md --
    caught and re-emitted as a `SlicePlanParseUnresolved` block, EVEN THOUGH
    an active `deliver` wave floor (seeded below) is the exact positive
    signal this was a cross-wave-child return, not a genuine DISTILL-wave
    exit (RCA §4a: this is the SECOND, independent consumer of the same
    borrowed envelope, beyond the PreToolUse entry gate).
    """
    feature_id = f"probe-exit-{uuid.uuid4().hex[:8]}"
    (tmp_path / ".nwave" / "des").mkdir(parents=True, exist_ok=True)

    # Seed an ACTIVE `deliver` wave floor -- the real signal (already read by
    # the PreToolUse WAVE_MARKER_BYPASS hinge) that this D_DISTILL-phase
    # return is happening INSIDE another wave's floor, not as a top-level
    # DISTILL-wave completion.
    store = WaveActiveFilesystemStore()
    store.arm(
        tmp_path,
        WaveActiveRecord(
            wave="deliver", provenance=WaveProvenance.COMMAND, entry_pending=False
        ),
    )

    # No docs/feature/<feature_id>/feature-delta.md -- this was never a real
    # feature-wide DISTILL wave (RCA §4a's exact live reproduction).
    resolved = subagent_stop_handler._AtddPureResolvedContext(
        project_id=feature_id,
        slice_id="feature-end",
        atdd_pure_phase="D_DISTILL",
        project_root_marker=None,
        effective_cwd=str(tmp_path),
        at_kind=None,
    )
    hook_input: dict[str, object] = {"cwd": str(tmp_path)}

    subagent_stop_handler._handle_distill_exit_gate(resolved, hook_input, "test-hook")
    stdout = capsys.readouterr().out
    payload: dict[str, object] = json.loads(stdout) if stdout.strip() else {}

    assert payload.get("event") != "SlicePlanParseUnresolved", (
        "a cross-wave-child return (charter/examine dispatch returning "
        "inside an ACTIVE `deliver` wave floor, carrying the borrowed "
        "D_DISTILL declaration) must NOT be misread as a completed "
        "whole-feature DISTILL demanding a slice plan from a feature-delta "
        f"that never existed for this feature-id. Observed block: {stdout!r}"
    )
    assert payload.get("decision") != "block", (
        "the exit gate must not BLOCK a cross-wave-child return at all -- "
        f"it must recognise the active deliver-wave floor. Observed: {stdout!r}"
    )


# ---------------------------------------------------------------------------
# 5. Fault-injection / positive control -- the guard can still say NO.
# ---------------------------------------------------------------------------


def test_dispatch_guard_still_refuses_a_genuinely_incomplete_atdd_pure_dispatch() -> (
    None
):
    """Before believing a YES, check the guard can still say NO: a
    genuinely defective atdd_pure dispatch (missing DES-PROJECT-ID) is
    STILL refused by the SAME production `PreToolUseService`. The fix must
    widen the vocabulary (accept honest cross-wave-child / examiner
    declarations), NOT punch a hole in the enforcement -- this positive
    control must stay GREEN both before and after the fix lands.
    """
    prompt = "\n".join(
        [
            _marker("DES-VALIDATION", "required"),
            _marker("DES-MODE", "atdd_pure"),
            _marker("DES-PHASE", "C_REVIEWER_AUDIT"),
            _marker("DES-SLICE", "slice-01"),
            # DES-PROJECT-ID deliberately omitted -- the real defect.
        ]
    )

    service = service_factory.create_pre_tool_use_service(
        audit_writer_factory=lambda: NullAuditLogWriter()
    )
    decision = service.validate(
        PreToolUseInput(
            prompt=prompt, subagent_type="nw-user-examiner", wave_entering=False
        )
    )

    assert decision.action == "block", (
        "a genuinely incomplete atdd_pure dispatch (no DES-PROJECT-ID) must "
        "still be refused -- widening the vocabulary for honest "
        "cross-wave-child/examiner declarations must not weaken this "
        f"enforcement. decision={decision!r}"
    )
    assert decision.reason is not None and "DES-PROJECT-ID" in decision.reason, (
        "the refusal must name the missing DES-PROJECT-ID marker (GDP-3 "
        f"what/why/how). reason={decision.reason!r}"
    )


# ---------------------------------------------------------------------------
# 6. The cure relocated the disease -- the charter envelope still hands the
#    PO the design (RCA follow-up: DESIGN_CONTEXT + SKILL_LOADING body).
# ---------------------------------------------------------------------------


def test_charter_dispatch_envelope_does_not_hand_the_design_to_the_product_owner() -> (
    None
):
    """The whole reason a FRESH product-owner writes the charter is that they
    have NOT seen the design: an author who knows how it was built writes a
    promise the build happens to keep. That is the mirror, and the mirror
    always returns a perfect image. `des dispatch --lane charter` must not
    hand the PO that mirror.

    FAILS TODAY on both counts, observed on the real generated envelope
    (`LANE_PROFILES["charter"].required_sections` includes DESIGN_CONTEXT,
    and `dispatch._section_body` renders `Design reference: docs/feature/
    <id>/feature-delta.md` for EVERY agent unconditionally; SKILL_LOADING
    only special-cases the examiner agent, so the PO still gets `Always load
    at phase entry: nw-tdd-methodology, nw-quality-framework` -- the
    CRAFTER's code-reasoning skills):

        # DESIGN_CONTEXT
        Design reference: docs/feature/<id>/feature-delta.md   <- hands the mirror

        # SKILL_LOADING
        Always load at phase entry: nw-tdd-methodology, ...    <- crafter skills
    """
    feature_id = f"probe-charter-design-{uuid.uuid4().hex[:8]}"
    exit_code, stdout, stderr = _run_dispatch_main(
        [
            "--mode",
            "atdd_pure",
            "--project-id",
            feature_id,
            "--slice",
            "slice-01",
            "--lane",
            "charter",
            "--intent",
            "author the expectation charter for slice-01",
            "--repo-root",
            str(_REPO_ROOT),
        ]
    )
    assert exit_code == 0, f"dispatch generation must succeed. stderr={stderr!r}"

    assert "feature-delta.md" not in stdout, (
        "the charter envelope must not point the fresh PO at the design/"
        "build history -- an author who has seen how it was built writes a "
        "promise the build happens to keep (the mirror); handing the PO the "
        f"mirror disqualifies them by construction. stdout={stdout!r}"
    )
    assert "nw-tdd-methodology" not in stdout, (
        "the charter envelope must not instruct the PO to load the "
        "crafter's code-reasoning / TDD methodology skills -- charter "
        f"authoring is not implementation. stdout={stdout!r}"
    )


# ---------------------------------------------------------------------------
# 7. NEGATIVE AT (durable, catches the CLASS) -- no envelope generated for a
#    NON-CODE-FACING lane may carry ANY reference to the product's design,
#    source, or acceptance tests.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "extra_argv",
    [
        pytest.param(
            [
                "--lane",
                "charter",
                "--intent",
                "author the expectation charter for slice-01",
            ],
            id="charter-lane-product-owner",
        ),
        pytest.param(
            ["--phase", "C_REVIEWER_AUDIT", "--intent", "examine slice-01"],
            id="examine-phase-examiner",
        ),
    ],
)
def test_no_non_code_facing_lane_envelope_references_design_source_or_tests(
    extra_argv: list[str],
) -> None:
    """NEGATIVE AT (the durable one -- catches the CLASS, not one section
    name): no envelope `des dispatch` generates for a NON-CODE-FACING lane
    (charter-authoring PO, examiner) may carry ANY reference to the
    product's design, source, or acceptance tests.

    This fix already relocated this lie ONCE: the false phase moved out of
    the marker block (the original RCA Face A/B, now fixed) and the design
    pointer relocated INTO the body (`DESIGN_CONTEXT: Design reference:
    docs/feature/<id>/feature-delta.md`, plus a crafter-flavoured
    SKILL_LOADING body). This AT exists to stop the lie relocating a SECOND
    time -- whatever section name the next leak picks, "does the generated
    envelope text contain a path/word naming the design, the source, or the
    ATs" is the class-level, section-name-agnostic check.

    FAILS TODAY for both parametrized cases: the charter envelope leaks via
    DESIGN_CONTEXT + SKILL_LOADING (case 1); the examiner envelope -- widely
    believed already clean -- ALSO leaks the SAME `Design reference:
    docs/feature/<id>/feature-delta.md` line via the unconditional
    DESIGN_CONTEXT body, confirmed by live-driving `des dispatch --phase
    C_REVIEWER_AUDIT` (case 2). The 5 pre-existing tests in this file never
    looked at DESIGN_CONTEXT's content -- only at markers and AGENT_IDENTITY
    -- so this class of leak passed unnoticed.
    """
    feature_id = f"probe-leak-{uuid.uuid4().hex[:8]}"
    exit_code, stdout, stderr = _run_dispatch_main(
        [
            "--mode",
            "atdd_pure",
            "--project-id",
            feature_id,
            "--slice",
            "slice-01",
            *extra_argv,
            "--repo-root",
            str(_REPO_ROOT),
        ]
    )
    assert exit_code == 0, f"dispatch generation must succeed. stderr={stderr!r}"

    forbidden_tokens = (
        "feature-delta.md",
        "docs/feature/",
        "tests/des/",
        "tests/bugs/",
        "nw-tdd-methodology",
    )
    for token in forbidden_tokens:
        assert token not in stdout, (
            "NEGATIVE AT: a non-code-facing envelope must never reference "
            f"the design/source/ATs -- found forbidden token {token!r} in "
            f"the generated envelope (argv={extra_argv!r}). stdout={stdout!r}"
        )


# ---------------------------------------------------------------------------
# 8. ROUND-TRIP INVARIANT (durable, catches the CLASS): the envelope
#    `des dispatch` GENERATES for a NON-CODE-FACING dispatch must be
#    ACCEPTED by the SAME production guard that polices every dispatch.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "extra_argv,subagent_type",
    [
        pytest.param(
            [
                "--lane",
                "charter",
                "--intent",
                "author the expectation charter for slice-01",
            ],
            "nw-product-owner",
            id="charter-lane-product-owner",
        ),
        pytest.param(
            ["--phase", "C_REVIEWER_AUDIT", "--intent", "examine slice-01"],
            "nw-user-examiner",
            id="examine-phase-examiner",
        ),
    ],
)
def test_generated_non_code_facing_envelope_is_accepted_by_the_same_guard(
    extra_argv: list[str], subagent_type: str
) -> None:
    """ROUND-TRIP INVARIANT (the durable AT -- catches the CLASS, never one
    section name): whatever envelope `des dispatch` GENERATES for a
    NON-CODE-FACING lane/phase, the SAME production `PreToolUseService`
    guard that polices every dispatch must ACCEPT it. A producing tool that
    emits an artifact its own gate rejects has failed at its only job -- the
    sibling feature `examinable-gate-surface` hit the identical class a few
    hours earlier in the shape of a fixture rather than an envelope.

    Never hand-built, never hardcoded: this test GENERATES the envelope with
    the real `des dispatch` CLI, then feeds THAT exact text into the real
    guard -- so it breaks again whenever the two sides drift, whatever the
    drift is about next time.

    FAILS TODAY for the charter-lane-product-owner case only (the
    examine-phase-examiner case is already exempted by name via
    `_is_examine_dispatch`, so it passes both before and after -- it is the
    positive control INSIDE this same round-trip, proving the assertion
    is not vacuously satisfiable): the charter lane's dispatch carries NO
    `DES-PHASE` marker at all (RCA fix-po-charter-dispatch-marker-lane,
    Face A) -- so `_is_examine_dispatch` (which keys ONLY on the raw
    `C_REVIEWER_AUDIT` DES-PHASE marker) never recognises it, and the
    generated `DESIGN_CONTEXT` body ("N/A -- this dispatch is non-code-facing;
    no source, design, or acceptance-test access by construction.") is held
    to the SAME `design_context_carries_architecture` content-presence gate
    a code-facing dispatch must satisfy -- and is refused for "carries no
    architecture citation", even though the generator correctly rendered it
    that way BY CONSTRUCTION for a non-code-facing agent.
    """
    feature_id = f"probe-roundtrip-{uuid.uuid4().hex[:8]}"
    exit_code, stdout, stderr = _run_dispatch_main(
        [
            "--mode",
            "atdd_pure",
            "--project-id",
            feature_id,
            "--slice",
            "slice-01",
            *extra_argv,
            "--repo-root",
            str(_REPO_ROOT),
        ]
    )
    assert exit_code == 0, f"dispatch generation must succeed. stderr={stderr!r}"

    service = service_factory.create_pre_tool_use_service(
        audit_writer_factory=lambda: NullAuditLogWriter()
    )
    decision = service.validate(
        PreToolUseInput(prompt=stdout, subagent_type=subagent_type, wave_entering=False)
    )

    assert decision.action == "allow", (
        "ROUND-TRIP INVARIANT: the envelope `des dispatch` GENERATED for a "
        "non-code-facing dispatch must be ACCEPTED by the SAME production "
        "guard that polices every dispatch -- a producing tool that emits "
        "an artifact its own gate rejects has failed at its only job. "
        f"argv={extra_argv!r}, decision={decision!r}, stdout={stdout!r}"
    )


# ---------------------------------------------------------------------------
# 9. COHERENCE GUARD (durable, catches the CLASS): a phaseless, non-code-
#    facing lane combined with ANY explicit --phase is a self-contradictory
#    request -- REFUSE it, loudly, naming the conflict.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("phase_value", list(dispatch._canonical_phase_values()))
def test_dispatch_refuses_phaseless_lane_combined_with_explicit_phase(
    phase_value: str,
) -> None:
    """NEGATIVE AT (the durable one -- catches the CLASS, not today's single
    lane+phase pairing): `des dispatch` already validates every input's
    SHAPE -- `--lane` against `LANE_PROFILES`, `--phase` against the
    canonical `ATDDPurePhase` values, `--project-id` presence (test 5 above)
    -- but never their COHERENCE. A phaseless, non-code-facing lane
    (`charter`, `PHASELESS_LANES`) combined with an explicit `--phase` is
    the one request that slips through: each part is individually valid (a
    real lane, a real phase), and the COMBINATION is nonsense -- the
    `charter` lane belongs to a product-owner authoring an expectation
    charter and declares NO `ATDDPurePhase` at all (`PHASELESS_LANES`,
    `lane_profile.py`), while e.g. `C_REVIEWER_AUDIT` belongs to the
    examiner and `A_GREEN`/`D_REFACTOR_COMMIT` belong to the crafter.
    Reproduced live by the orchestrator (`des dispatch --mode atdd_pure
    --project-id demo --slice slice-01 --lane charter --phase
    C_REVIEWER_AUDIT --intent x`): exit 0, emitting `Phase:
    C_REVIEWER_AUDIT` / `Agent: nw-product-owner` in the SAME envelope --
    an incoherent artifact the very charter written for this fix forbids
    ("the machinery must REFUSE to produce a usable envelope, loudly,
    naming what's wrong -- it must not silently invent a best-guess
    envelope").

    Parametrized over EVERY canonical `ATDDPurePhase` value (not just
    `C_REVIEWER_AUDIT`) -- the next contradiction this class needs to catch
    will be a different pairing (e.g. `charter` + `A_GREEN`), so this test
    pins the CLASS ("no phaseless lane may combine with ANY explicit
    phase"), not one example of it.

    FAILS TODAY for every parametrized phase: `main()` only refuses a
    MISSING `--phase` for a lane that is NOT phaseless (`if phase is None
    and args.lane not in PHASELESS_LANES`) -- it never refuses the inverse:
    an EXPLICIT `--phase` for a lane that IS phaseless.
    """
    feature_id = f"probe-coherence-{uuid.uuid4().hex[:8]}"
    exit_code, stdout, stderr = _run_dispatch_main(
        [
            "--mode",
            "atdd_pure",
            "--project-id",
            feature_id,
            "--slice",
            "slice-01",
            "--lane",
            "charter",
            "--phase",
            phase_value,
            "--intent",
            "x",
            "--repo-root",
            str(_REPO_ROOT),
        ]
    )

    assert exit_code != 0, (
        "a self-contradictory dispatch (phaseless lane 'charter' + explicit "
        f"--phase {phase_value}) must be REFUSED -- not silently accepted "
        f"into a best-guess envelope. exit_code={exit_code}, stdout={stdout!r}"
    )
    assert stdout == "", (
        "a refused, incoherent dispatch must never emit a usable envelope "
        f"on stdout (GDP-6 -- no silent-wrong artifact). stdout={stdout!r}"
    )
    assert "charter" in stderr, (
        f"the refusal must NAME the offending lane (GDP-3 WHAT). stderr={stderr!r}"
    )
    assert phase_value in stderr, (
        f"the refusal must NAME the offending phase (GDP-3 WHAT). stderr={stderr!r}"
    )
    assert "--phase" in stderr, (
        "the refusal must point at the offending flag as the remediation "
        "(GDP-3 HOW: drop --phase, or use a phase-bearing lane). "
        f"stderr={stderr!r}"
    )


# ---------------------------------------------------------------------------
# 10. POSITIVE CONTROLS survive the coherence guard -- it must refuse ONLY
#     the incoherent combinations, never a legitimate dispatch shape.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "extra_argv",
    [
        pytest.param(
            ["--lane", "charter", "--intent", "author the expectation charter"],
            id="charter-lane-alone-no-phase",
        ),
        pytest.param(
            ["--phase", "C_REVIEWER_AUDIT", "--intent", "examine slice-01"],
            id="phase-alone-no-lane",
        ),
        pytest.param(
            [
                "--lane",
                "bugfix",
                "--phase",
                "A_GREEN",
                "--defect",
                "x",
                "--regression-test",
                "test_x",
                "--intent",
                "fix x",
            ],
            id="code-facing-lane-plus-phase",
        ),
    ],
)
def test_dispatch_still_accepts_coherent_lane_phase_combinations(
    extra_argv: list[str],
) -> None:
    """POSITIVE CONTROL (must stay GREEN both before AND after the coherence
    fix lands): the guard added by
    `test_dispatch_refuses_phaseless_lane_combined_with_explicit_phase`
    above must refuse ONLY the incoherent combination (a phaseless lane +
    an explicit phase) -- never a legitimate dispatch shape. If that
    sibling test's assertion could be satisfied by a guard that refuses
    EVERY dispatch, THIS test is what proves it does not: the `charter`
    lane alone (no phase -- its own phaseless shape), a canonical phase
    alone (no lane -- the ordinary code-facing/examiner routing), and a
    CODE-FACING lane explicitly combined with its phase (`bugfix` +
    `A_GREEN` -- a coherent, intended lane+phase pairing) must all keep
    generating a usable envelope, exit 0, both today and after the fix.
    """
    feature_id = f"probe-coherence-control-{uuid.uuid4().hex[:8]}"
    exit_code, stdout, stderr = _run_dispatch_main(
        [
            "--mode",
            "atdd_pure",
            "--project-id",
            feature_id,
            "--slice",
            "slice-01",
            *extra_argv,
            "--repo-root",
            str(_REPO_ROOT),
        ]
    )

    assert exit_code == 0, (
        "a coherent dispatch shape must NEVER be refused by the coherence "
        f"guard. argv={extra_argv!r}, exit_code={exit_code}, stderr={stderr!r}"
    )
    assert stdout != "", (
        "a coherent dispatch must emit a real, usable envelope. "
        f"argv={extra_argv!r}, stdout={stdout!r}"
    )

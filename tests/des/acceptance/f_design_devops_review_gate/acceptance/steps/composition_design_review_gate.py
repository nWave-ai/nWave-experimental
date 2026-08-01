"""Composition root for f-design-devops-review-gate slice-01 (walking skeleton).

DRIVING SURFACE (Mandate-13 driving-port-only -- TWO real wired seams, no
direct-domain import for business logic):

  * Layer 3 composition (AT-1) -- the REAL spine
    ``wave_gate_stack_dispatch.resolve_stack("design", "gate-out")`` reading the
    SHIPPED canonical wave-contract registry ``nWave/waves/design.yaml`` in the
    repo. This is the entry the live SubagentStop gate-out caller uses once the
    ``"discuss"`` literal is lifted to the active wave (brief §7 surface 1,
    subagent_stop_service.py:311 ``resolve_stack("discuss", "gate-out")``). The
    observable is the ordered gate-id sequence the resolution returns for the
    DESIGN gate-out boundary, read over the SHIPPED registry FILE (Mandate-14
    @real-io: the test would fail if the registry file is absent).

  * Layer 3 subprocess (AT-2..4) -- the REAL ``des record-design-review`` /
    ``des verify-design-review`` CLIs as black-box processes via the single
    ``des.cli.__main__`` dispatcher. The observable surface is the process exit
    code + the structured JSON verdict payload, nothing else. No production
    review-gate module is imported-and-called at the step boundary.

DORMANT-SEAM RECONCILIATION (Mandate-15 / S3): the DESIGN driving-surface declares
the load-bearing net-new seams reached from the dispatcher's + the CLI's real
entry points:

  (seam-1) the canonical registry file ``nWave/waves/design.yaml`` carrying the
           ``gate_stack.gate-out`` SSOT-A with the ``verify-design-review`` row
           (brief §3 reconciliation: the registry HOME, NOT the flavor) -- the
           DATA home of the new DESIGN gate stack, resolved through the WIRED
           spine ``resolve_stack``.
  (seam-2) the ``des verify-design-review`` CONSUMER veto CLI -- reads the latest
           ``DesignReviewVerdict`` ledger record, seals the feature-delta, and
           delegates to the (generalized) ``ReviewVerdictGate.evaluate`` core,
           projecting PASS/VETOED/INDETERMINATE onto exit 0/1.
  (seam-3) the ``des record-design-review`` PRODUCER CLI -- records a real
           solution-architect-reviewer verdict (BOTH approved AND needs-revision,
           O-4 / DDD-6).

Each slice-01 AT NAMES one of these seams, drives it through the REAL entry point,
and asserts an observable effect (the resolved gate-id sequence for AT-1; the
process exit code + JSON verdict for AT-2..4).

RED contract (fail-for-right-reason, atdd_pure active-RED -- NOT @skip):
  * AT-1: ``nWave/waves/design.yaml`` does not exist at HEAD, so the spine resolves
    an EMPTY DESIGN gate-out stack -> a semantic AssertionError naming the missing
    registry file / verify-design-review row.
  * AT-2..4: ``verify-design-review`` / ``record-design-review`` are NOT registered
    in the ``des`` dispatcher ``_REGISTRY`` at HEAD, so the subprocess exits
    non-zero with an "unknown subcommand" error -> the observed verdict is neither
    pass/vetoed/indeterminate -> a semantic AssertionError naming the missing CLI
    seam. Every dependency (pytest-bdd, the ``des`` dispatcher subprocess, the tmp
    work-tree) resolves cleanly -- these are deliberate missing-functionality REDs,
    not test bugs.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process

from .domain_types import GateOutcome, ReviewerVerdict, WaveBoundary


# tests/des/acceptance/f_design_devops_review_gate/acceptance/steps/<this file>
#   parents: [0]=steps [1]=acceptance [2]=f_design_devops_review_gate
#            [3]=acceptance [4]=des [5]=tests [6]=REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[6]

# The SHIPPED canonical wave-contract registry dir (ADR-FLOW-006 D1).
_WAVES_DIR = REPO_ROOT / "nWave" / "waves"
_DESIGN_REGISTRY_FILE = _WAVES_DIR / "design.yaml"

# The DESIGN wave whose gate-out stack is migrated to the canonical registry.
_DESIGN_WAVE = "design"

# The gate-id the DESIGN gate-out stack MUST carry (brief §6 / §7 surface 1).
_VERIFY_DESIGN_GATE_ID = "verify-design-review"

# The reviewer whose verdict the DESIGN producer records (brief §6).
_REVIEWER_AGENT_ID = "nw-solution-architect-reviewer"

# The feature under gate -- a synthetic feature id provisioned in the tmp tree.
_GATED_FEATURE_ID = "synthetic-design-feature"

# Narrow line-oriented registry scan primitives (read #1 of AT-1) -- stdlib `re`
# ONLY, no `des.*` import, no `import yaml` (Mandate-13 driving-port-only +
# Invariant-4 target-machine agnostic). Mirror the SHIPPED coherence gate's
# narrow YAML scan (verify_wave_contract_coherence.py: _TOP_LEVEL_KEY / a
# `gate_id:` line matcher) over the SAME registry shape as nWave/waves/discuss.yaml.
#
# A top-level (zero-indent) ``key:`` -- used to locate the ``gate_stack`` block
# and to detect the block's end (the next top-level key).
_TOP_LEVEL_KEY = re.compile(r"^([A-Za-z0-9_-]+):\s*$")
# A boundary sub-key under ``gate_stack`` (two-space indent ``gate-in:`` /
# ``gate-out:``), and the end of one boundary (the next same-indent sub-key).
_BOUNDARY_KEY = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
# A ``gate_id: <id>`` row line inside a boundary's stack.
_GATE_ID_LINE = re.compile(r"^\s*-?\s*gate_id:\s*([A-Za-z0-9_-]+)\s*$")


def _design_sequence_declared_in_registry_file(
    boundary: WaveBoundary,
) -> tuple[str, ...]:
    """Read the DESIGN gate-id sequence DIRECTLY from the registry FILE.

    Independent read #1 of the AT-1 two-reads cross-check: a direct stdlib parse
    of the SHIPPED ``nWave/waves/design.yaml`` file, walking ``gate_stack[boundary]``
    WITHOUT going through the spine. This is the DECLARED sequence -- what a
    maintainer authored in the registry (the registry HOME per brief §2/§3,
    mirroring the existing ``nWave/waves/discuss.yaml`` shape).

    At HEAD the file is absent -> returns the empty tuple (the RED for AT-1).
    """
    try:
        text = _DESIGN_REGISTRY_FILE.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError, OSError):
        return ()
    return _scan_boundary_gate_ids(text, boundary.value)


def _scan_boundary_gate_ids(registry_text: str, boundary: str) -> tuple[str, ...]:
    """Narrow stdlib line scan: the ordered ``gate_id`` sequence for ``boundary``.

    Pure-Python `re` over the SHIPPED registry's line shape (mirroring
    nWave/waves/discuss.yaml + the coherence gate's scan): find the top-level
    ``gate_stack:`` block, then the ``  <boundary>:`` sub-key inside it, then
    collect the ``gate_id:`` rows until the next same-indent sub-key (or the next
    top-level key) ends the boundary. No `des.*`, no `import yaml` -- the read is
    genuinely independent of the spine's resolve_stack path (read #2).
    """
    lines = registry_text.splitlines()
    in_gate_stack = False
    in_boundary = False
    gate_ids: list[str] = []
    for line in lines:
        top = _TOP_LEVEL_KEY.match(line)
        if top is not None:
            # A top-level key ends any in-progress gate_stack block.
            in_gate_stack = top.group(1) == "gate_stack"
            in_boundary = False
            continue
        if not in_gate_stack:
            continue
        sub = _BOUNDARY_KEY.match(line)
        if sub is not None:
            # A boundary sub-key ends the previous boundary and opens its own.
            in_boundary = sub.group(1) == boundary
            continue
        if not in_boundary:
            continue
        gate_id = _GATE_ID_LINE.match(line)
        if gate_id is not None:
            gate_ids.append(gate_id.group(1))
    return tuple(gate_ids)


def _design_sequence_resolved_by_spine(boundary: WaveBoundary) -> tuple[str, ...]:
    """Resolve the DESIGN gate-id sequence through the WIRED spine entry.

    Independent read #2 of the AT-1 two-reads cross-check: drives the REAL
    ``wave_gate_stack_dispatch.resolve_stack(wave, boundary)`` -- the entry the
    live SubagentStop gate-out caller uses (subagent_stop_service.py:311 calls
    ``wgs.resolve_stack("discuss", "gate-out")``; this feature lifts that literal
    to the active wave so a DESIGN return resolves the DESIGN stack). The spine
    reads the canonical registry as the SOLE gate-stack source (ADR-FLOW-006 D6,
    post-slice-06 MOVE), so this proves the registry -> dispatcher wiring.

    At HEAD ``nWave/waves/design.yaml`` is absent -> the spine resolves the empty
    stack (the RED for AT-1).
    """
    from des.application import wave_gate_stack_dispatch

    resolved = wave_gate_stack_dispatch.resolve_stack(_DESIGN_WAVE, boundary.value)
    return tuple(
        str(row["gate_id"])
        for row in resolved.rows
        if isinstance(row, dict) and "gate_id" in row
    )


@dataclass
class CliResult:
    """Observable outcome of one ``des`` subcommand subprocess invocation."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def payload(self) -> dict[str, object]:
        """The single-line JSON object the surface emits (empty dict if none)."""
        for line in (self.stdout + "\n" + self.stderr).splitlines():
            stripped = line.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                with contextlib.suppress(json.JSONDecodeError):
                    return json.loads(stripped)
        return {}


def _run_des_subprocess(subcommand_argv: list[str], *, cwd: Path) -> CliResult:
    """Run ``des.cli.__main__ <subcommand> ...`` in-process under ``cwd``.

    The SSOT des-CLI driving-surface runner, shared by the DESIGN (slice-01) and
    DEVOPS (slice-02) compositions -- the test-side echo of the production-side
    "one generic mechanism, thin per-wave bindings" contract. Drives the
    production ``des.cli.__main__.main`` dispatcher in-process via the shared
    ``run_cli_in_process`` driver (the in-process analogue of the former
    ``python -m des.cli.__main__ <subcommand>`` subprocess), capturing exit code +
    stdout + stderr.

    Env-parity per the established gate suite: the load-bearing
    ``NWAVE_FRESHNESS=skip`` (cwd is the synthetic tmp tree; without it the
    freshness wrapper may refuse before the gate logic runs, read from
    ``os.environ`` at runtime) is applied to ``os.environ`` around the in-process
    call and RESTORED in ``finally`` (shared-process safe). ``PIPENV_DONT_LOAD_ENV``
    / ``PYTHONPATH`` are carried for parity though inert in-process. The CLI is
    exercised as a black box -- exit code + JSON stdout are the only observables.
    """
    env_overrides = {
        "NWAVE_FRESHNESS": "skip",
        "PIPENV_DONT_LOAD_ENV": "1",
        "PYTHONPATH": str(REPO_ROOT / "src")
        + os.pathsep
        + os.environ.get("PYTHONPATH", ""),
    }
    saved = {key: os.environ.get(key) for key in env_overrides}
    os.environ.update(env_overrides)
    try:
        exit_code, stdout, stderr = run_cli_in_process(list(subcommand_argv), cwd=cwd)
    finally:
        for key, prior in saved.items():
            if prior is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prior
    return CliResult(exit_code=exit_code, stdout=stdout, stderr=stderr)


@dataclass
class DesignReviewGateComposition:
    """Drives the DESIGN review-verdict gate through its TWO real wired seams.

    AT-1 reads the SHIPPED repo registry (no tmp tree needed). AT-2..4 operate on
    a tmp work-tree carrying the feature-delta the verdict seals against + the
    AT-completion ledger the verdict is recorded into.
    """

    repo_dir: Path
    feature_id: str = field(default=_GATED_FEATURE_ID)
    _resolved_boundary: WaveBoundary | None = field(default=None)
    _verify_result: CliResult | None = field(default=None)
    _record_result: CliResult | None = field(default=None)

    # ---- paths --------------------------------------------------------------

    @property
    def _feature_delta_path(self) -> Path:
        return self.repo_dir / "docs" / "feature" / self.feature_id / "feature-delta.md"

    # ---- AT-1 given/when/then: registry -> spine seam ------------------------

    def given_design_registry_file_is_shipped(self) -> None:
        """Arm the SUT to read the SHIPPED canonical registry file from the repo.

        No fixture authoring of the expected output -- the registry FILE is the
        shipped artifact the SUT reads (Mandate-13 protocol-driver: assert a
        shipped artifact, never a string the test fabricated). At HEAD the file is
        absent; the absence is the RED.
        """
        # Nothing to set up beyond pointing at the shipped path -- the file itself
        # (or its absence) is the contract under test.

    def when_dispatcher_resolves_design_gate_out_from_registry(
        self, boundary: WaveBoundary
    ) -> None:
        """Drive the REAL spine resolving the DESIGN gate-out stack from the registry.

        The When does not itself read; it records WHICH boundary the Then must
        cross-check, so the per-scenario parameter is bound (not dropped). The two
        independent reads happen in the Then.
        """
        self._resolved_boundary = boundary

    def then_resolved_sequence_equals_registry_declared(
        self, boundary: WaveBoundary
    ) -> None:
        """The spine-resolved gate-id sequence equals the registry-FILE-declared one.

        Walking-skeleton end-to-end wiring proof (Mandate-15 seam-1): two
        INDEPENDENT reads of the DESIGN gate-out gate-id sequence must agree --

          (read #1) the sequence DECLARED in the registry FILE, read directly with
                    the stdlib subset parser, NOT through the spine; and
          (read #2) the sequence the WIRED spine entry resolves
                    (``wave_gate_stack_dispatch.resolve_stack``, the live
                    SubagentStop gate-out path).

        Agreement proves resolve_stack ACTUALLY reads the registry and returns the
        declared sequence (registry -> dispatcher wiring) -- NOT registry==registry
        (the reads use different code paths). The sequence must be NON-EMPTY so a
        both-empty trivial pass cannot satisfy it.

        RED at HEAD: ``nWave/waves/design.yaml`` is absent -> read #1 is empty ->
        semantic AssertionError naming the missing registry file.
        """
        self._assert_boundary_matches_when(boundary)
        declared = _design_sequence_declared_in_registry_file(boundary)
        resolved = _design_sequence_resolved_by_spine(boundary)
        assert declared, (
            "the DESIGN gate-out gate stack must be DECLARED (non-empty) in the "
            f"canonical registry file {_DESIGN_REGISTRY_FILE} (brief §3 "
            "reconciliation: the registry HOME, mirroring nWave/waves/discuss.yaml; "
            "ADR-FLOW-006 D6 -- the dispatcher reads the registry as the SOLE "
            "gate-stack source) -- read #1 resolved EMPTY (the registry file does "
            f"not exist yet). {self._observed()}"
        )
        assert resolved == declared, (
            "the WIRED spine entry wave_gate_stack_dispatch.resolve_stack must "
            f"resolve the DESIGN {boundary.value} stack to the SAME gate-id "
            "sequence the registry FILE declares (walking-skeleton end-to-end "
            "wiring, AT-1) -- two independent reads (registry-FILE-declared vs "
            "spine-resolved) must agree, proving resolve_stack reads the registry, "
            f"not registry==registry; declared {declared!r}, spine-resolved "
            f"{resolved!r}. {self._observed()}"
        )

    def then_resolved_stack_includes_verify_design_review(
        self, boundary: WaveBoundary
    ) -> None:
        """The resolved DESIGN gate-out stack carries the verify-design-review gate.

        Seam-named oracle (Mandate-15 seam-1 + seam-2): the gate-out stack the spine
        resolves must include the ``verify-design-review`` CONSUMER veto gate-id
        (brief §6 / §7 surface 1) -- the row that makes the review-verdict actually
        fire on the DESIGN return. RED at HEAD: the registry file is absent -> the
        resolved stack is empty -> semantic AssertionError naming the missing row.
        """
        self._assert_boundary_matches_when(boundary)
        resolved = _design_sequence_resolved_by_spine(boundary)
        assert _VERIFY_DESIGN_GATE_ID in resolved, (
            f"the DESIGN {boundary.value} stack the spine resolves must include the "
            f"{_VERIFY_DESIGN_GATE_ID!r} gate (brief §6: the CONSUMER veto row that "
            "fires the DESIGN review-verdict on the wave return) -- the resolved "
            f"sequence {resolved!r} does not carry it. {self._observed()}"
        )

    def _assert_boundary_matches_when(self, boundary: WaveBoundary) -> None:
        assert self._resolved_boundary is not None, (
            "the dispatcher resolution must run (When) before asserting (Then)"
        )
        assert self._resolved_boundary is boundary, (
            f"Then boundary {boundary.value!r} must match the boundary resolved in "
            f"When ({self._resolved_boundary.value!r}) -- scenario wiring drift"
        )

    # ---- AT-2..4 given: the gated DESIGN feature substrate --------------------

    def given_design_feature_with_no_recorded_verdict(self) -> None:
        """Provision a tmp DESIGN feature with a feature-delta and an empty ledger.

        Precondition state ONLY (NOT the SUT): the feature-delta is the artefact
        the verify gate seals against; NO DesignReviewVerdict is recorded -- the
        ledger stays empty until a When records one through the REAL producer CLI.
        No fixture authors the expected verdict (No Fixture Theater): the verdict,
        when present, is written by ``des record-design-review``, not the test.
        """
        self._feature_delta_path.parent.mkdir(parents=True, exist_ok=True)
        self._feature_delta_path.write_text(
            "# Feature Delta: synthetic DESIGN feature fixture\n\n"
            "## Wave: DESIGN\n\n"
            "### [REF] Inherited commitments\n\n"
            "| Origin | Commitment | DDD | Impact |\n"
            "|--------|------------|-----|--------|\n"
            "| n/a | a synthetic DESIGN deliverable the gate seals against | n/a | "
            "the bytes the review verdict's content seal binds to |\n",
            encoding="utf-8",
        )

    # ---- AT-3/AT-4 when: record a real reviewer verdict ----------------------

    def when_reviewer_records_verdict(self, verdict: ReviewerVerdict) -> None:
        """Record a real solution-architect-reviewer verdict via the PRODUCER CLI.

        Drives the REAL ``des record-design-review --feature-id <id> --verdict <v>
        --reviewer-agent-id <a>`` as a subprocess (Mandate-13 seam-3). The agent
        NEVER hands the gate a verdict; it triggers the RECORDING (DDD-6 / §22.7).
        Writes BOTH approved AND needs-revision (O-4 both-outcomes).

        RED at HEAD: ``record-design-review`` is not registered in the des
        dispatcher -> the subprocess exits non-zero ("unknown subcommand") and no
        record is written -> the downstream verify When observes no recorded
        verdict, and the Then fires a semantic AssertionError.
        """
        self._record_result = self._run_des(
            [
                "record-design-review",
                "--feature-id",
                self.feature_id,
                "--verdict",
                verdict.value,
                "--reviewer-agent-id",
                _REVIEWER_AGENT_ID,
                "--repo-root",
                str(self.repo_dir),
            ]
        )

    # ---- AT-2..4 when: verify the gate ---------------------------------------

    def when_design_review_gate_is_verified(self) -> None:
        """Verify the DESIGN review-verdict gate via the CONSUMER veto CLI.

        Drives the REAL ``des verify-design-review --feature-id <id>`` as a
        subprocess (Mandate-13 seam-2). The observable is the process exit code +
        the JSON verdict payload. RED at HEAD: ``verify-design-review`` is not
        registered in the des dispatcher -> the subprocess exits non-zero with an
        "unknown subcommand" error -> the observed verdict is none of
        pass/vetoed/indeterminate -> the Then fires a semantic AssertionError
        naming the missing CLI seam.
        """
        self._verify_result = self._run_des(
            [
                "verify-design-review",
                "--feature-id",
                self.feature_id,
                "--repo-root",
                str(self.repo_dir),
            ]
        )

    # ---- AT-2..4 then: the projected gate verdict ----------------------------

    def then_gate_refuses_with_indeterminate(self) -> None:
        """The verify gate REFUSES the DESIGN return with INDETERMINATE (absent).

        AT-2 (error path): no DesignReviewVerdict recorded -> the
        ReviewVerdictGate core returns INDETERMINATE("absent") -> the CLI projects
        exit 1 + verdict "indeterminate". Absence reads as a veto, NEVER a silent
        PASS (no-silent-pass, DDD-7). RED at HEAD: the CLI does not exist, so the
        observed verdict is not "indeterminate".
        """
        self._assert_gate_verdict(GateOutcome.INDETERMINATE, expected_exit=1)

    def then_gate_passes_with_pass(self) -> None:
        """The verify gate PASSES the DESIGN return with "no objection found".

        AT-3 (happy path): after an artefact-current APPROVED verdict is recorded,
        the gate returns PASS -> exit 0 + verdict "pass" ("no objection found", NOT
        an authorizing GO -- §22.0). RED at HEAD: the producer CLI never recorded
        a verdict (unknown subcommand) and the verify CLI does not exist, so the
        observed verdict is not "pass".
        """
        self._assert_gate_verdict(GateOutcome.PASS, expected_exit=0)

    def then_gate_vetoes_with_vetoed(self) -> None:
        """The verify gate VETOES the DESIGN return on a needs-revision verdict.

        AT-4 (error path): a recorded NEEDS_REVISION verdict -> the core returns
        VETOED -> exit 1 + verdict "vetoed". A reviewer veto is mechanically
        honored (DDD-6). RED at HEAD: same missing-CLI reason as AT-2/AT-3.
        """
        self._assert_gate_verdict(GateOutcome.VETOED, expected_exit=1)

    def _assert_gate_verdict(
        self, expected: GateOutcome, *, expected_exit: int
    ) -> None:
        result = self._verify_result
        assert result is not None, (
            "the DESIGN review-verdict gate must be verified (When) before "
            "asserting its verdict (Then)"
        )
        observed_verdict = result.payload.get("verdict")
        assert observed_verdict == expected.value, (
            "the `des verify-design-review` CONSUMER veto CLI must project the "
            f"DESIGN review verdict as {expected.value!r} on exit {expected_exit} "
            "(brief §6 driving ports / DDD-7 GateVerdict projection: it reads the "
            "latest DesignReviewVerdict ledger record, seals the feature-delta, and "
            "delegates to ReviewVerdictGate.evaluate) -- the CLI is not registered "
            "in the des dispatcher yet, so the subprocess returned exit "
            f"{result.exit_code} with verdict {observed_verdict!r}. "
            f"{self._cli_observed()}"
        )
        assert result.exit_code == expected_exit, (
            f"the verify gate must project verdict {expected.value!r} onto exit "
            f"{expected_exit} (PASS->0, VETOED/INDETERMINATE->1) -- observed exit "
            f"{result.exit_code}. {self._cli_observed()}"
        )

    # ---- the des CLI subprocess (the REAL driving surface) -------------------

    def _run_des(self, subcommand_argv: list[str]) -> CliResult:
        """Run ``python -m des.cli.__main__ <subcommand> ...`` as a subprocess."""
        return _run_des_subprocess(subcommand_argv, cwd=self.repo_dir)

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"registry_file_exists={_DESIGN_REGISTRY_FILE.is_file()}; "
            f"waves_dir={_WAVES_DIR}; resolved_boundary={self._resolved_boundary!r}"
        )

    def _cli_observed(self) -> str:
        verify = self._verify_result
        record = self._record_result
        return (
            "verify=(exit="
            + (str(verify.exit_code) if verify else "n/a")
            + ", payload="
            + (repr(verify.payload) if verify else "n/a")
            + ", stderr="
            + (repr(verify.stderr[:200]) if verify else "n/a")
            + "); record=(exit="
            + (str(record.exit_code) if record else "n/a")
            + ", stderr="
            + (repr(record.stderr[:200]) if record else "n/a")
            + ")"
        )

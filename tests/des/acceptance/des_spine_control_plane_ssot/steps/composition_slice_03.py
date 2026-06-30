"""Composition root for des-spine-control-plane-ssot slice-03 (Mandate-12 SSOT).

Pillar 3 (App as in production): the SUT is the REAL spine mode-reading driving
ports — `des verify-integrity` (the verify role, wired at `des.cli.__main__:45`
kebab dispatcher -> `des.cli.verify_deliver_integrity:main`) and `des init-log`
(the DELIVER-dispatch role, `des.cli.init_log:main`) — invoked exactly as the
operator + `/nw-deliver` invoke them. The mode-resolution SSOT behavior is
observed via the process exit code + the structured/plain-text refusal surface,
NEVER by importing the resolver functions.

Mandate-13 (invariant 1+2): every service method drives a CLI as a Layer-3
SUBPROCESS black-box — NEVER a direct
`from des.application.workflow_mode import _resolve_workflow_mode` +
function-boundary call, NEVER `from des.cli.init_log import resolve_dispatch_mode`.
The resolver functions are NEVER imported in this composition; the AT observes
only each CLI's exit code + output stream. This is the driving-port-only boundary:
the mode answer is read off the port's real behaviour, not an internal call.

Mandate-13 (invariant 5) — Python-only, git-free, cross-OS: the UNCONFIGURED
topology (the #65 trigger) is constructed by simply NOT writing a
`.nwave/config.yaml`. No git, no shell tool. `NWAVE_FRESHNESS=skip` isolates the
slice-01 install-freshness gate so the mode-resolution behavior is observed
without freshness chatter confounding the assertion (DV-1: per-subprocess tests
set skip) AND so the result is not masked by the `.git/`-adjacency autoskip
(RCA #68 P1-B: a skip-masked freshness state must not confound this assertion).

Mandate-12 criterion 2/3: `ModeResolutionFixture` is the single source of truth
for ALL business logic the step methods need. Step bodies in
`steps_slice_03_mode_resolution.py` delegate here — each body is <=2 statements
ending in one `mode_resolution_fixture.<method>(...)` call (or one assertion),
no control flow inline.

DISTILL-authored RED scaffold (ADR-025): `des verify-integrity` + `des init-log`
ALREADY EXIST, but slice-03's NEW behavior does NOT:
  * DDD-5/7 — `verify_deliver_integrity.py:539` resolves the mode via
    `_resolve_workflow_mode` (absent -> `classic`). On an UNCONFIGURED atdd_pure
    project it mis-resolves to classic, falls to `:542`, and refuses exit 2
    `roadmap.json not found` (#65). Witnessed at DISTILL HEAD: exit 2.
  * DDD-5 — `init_log.py:135` ALSO uses `_resolve_workflow_mode` (absent ->
    classic), so on an UNCONFIGURED project init-log CREATES a log (exit 0)
    while the DELIVER-dispatch `resolve_dispatch_mode` says atdd_pure: the two
    spine ports DISAGREE on the absent-key answer. Witnessed: init-log exit 0
    (created log), verify exit 2 (phantom roadmap).
So AT-01 RED-fails (the verifier must resolve atdd_pure + check the ledger, never
exit 2 on a phantom roadmap) and AT-02 RED-fails (init-log must refuse-as-atdd_pure
so its answer EQUALS verify's) for MISSING_FUNCTIONALITY — NOT import error
(Mandate-7 RED-vs-BROKEN preserved). The explicit-mode control behaviors
(EXPLICIT_ATDD_PURE -> verify takes the atdd_pure branch already) pass today as
regression pins the consolidation must not break.

Layer 3 (subprocess against tmp_path): example-only (Mandate 9 v2 — @real-io
because the driven set includes a real filesystem adapter the CLIs read config +
ledger from). No PBT machinery. Sad path (#65 phantom roadmap) is one explicit
named example (Mandate 11).
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from des.cli.init_log import main as _init_log_main
from des.cli.verify_deliver_integrity import main as _verify_integrity_main
from tests.common.in_process_cli import run_cli_in_process

from .domain_types_slice_03 import (
    ROADMAP_NOT_FOUND_MARKER,
    DispatchOutcome,
    DispatchRun,
    ModeConfig,
    ProjectProbe,
    VerifyOutcome,
    VerifyRun,
)


_VERIFY_OK_EXIT = 0
_VERIFY_VIOLATION_EXIT = 1
_VERIFY_USAGE_EXIT = 2  # the #65 `roadmap.json not found` exit
_INIT_LOG_REFUSE_ATDD_PURE_EXIT = 1
_INIT_LOG_CREATED_EXIT = 0

_FEATURE_ID = "demo-feature"

# The init-log refusal banner emitted when it resolves atdd_pure (the spine is
# roadmap-free / execution-log-free). Verbatim substring from init_log.main
# (`:137`, "workflow.mode is atdd_pure"). The AT recognises the atdd_pure mode
# answer at the DELIVER port by this refusal, never by an internal resolver call.
_INIT_LOG_ATDD_PURE_REFUSAL = "workflow.mode is atdd_pure"


@dataclass
class ModeResolutionFixture:
    """Composition-root service for des-spine-control-plane-ssot slice-03 ATs.

    Pillar 3: drives the SAME `des verify-integrity` + `des init-log` CLIs the
    operator + `/nw-deliver` invoke, against a synthetic project under tmp_path.
    The unconfigured-vs-explicit mode seam, the #65 phantom-roadmap refusal, and
    the cross-port mode-answer agreement are all expressed as filesystem topology
    (write or omit `.nwave/config.yaml`). The AT observes each port's mode answer
    via exit code + output stream.

    Mandate-12 criterion 3: every public method is the SSOT for one piece of
    business logic. Step bodies do typed lookup + one method call; nothing more.
    """

    _tmp_path: Path

    # --- project construction (the unconfigured-vs-explicit mode seam) ------

    def build_project(self, *, mode_config: ModeConfig) -> ProjectProbe:
        """Lay out a synthetic atdd_pure-shaped project under tmp_path. GIT-FREE.

        UNCONFIGURED          -> NO `.nwave/config.yaml` written (the #65 trigger:
                                 the absent key forces the absent-key default).
        EXPLICIT_ATDD_PURE    -> `.nwave/config.yaml` with `workflow.mode: atdd_pure`.
        EXPLICIT_CLASSIC      -> `.nwave/config.yaml` with `workflow.mode: classic`.

        Every project carries the artifact the ATDD-pure spine actually wrote —
        a per-feature AT-completion ledger (NOT a roadmap.json) — so the verify
        path, once it resolves atdd_pure, reaches its verdict by checking the
        ledger that EXISTS rather than a roadmap.json that never did. No
        roadmap.json is ever written (the atdd_pure spine is roadmap-free): a
        missing roadmap must be a non-event under the resolved mode, which is
        exactly the #65-dissolution.
        """
        project_dir = self._tmp_path / mode_config.name.lower()
        deliver_dir = project_dir / "docs" / "feature" / _FEATURE_ID / "deliver"
        deliver_dir.mkdir(parents=True, exist_ok=True)
        self._write_atdd_pure_ledger(deliver_dir)
        self._write_mode_config(project_dir, mode_config)
        return ProjectProbe(
            project_dir=str(project_dir),
            deliver_dir=str(deliver_dir),
            mode_config=mode_config,
        )

    # --- the driving-port fires (real spine CLIs as subprocesses) -----------

    def run_verify_integrity(self, project: ProjectProbe) -> VerifyRun:
        """Fire the REAL `des verify-integrity` CLI on the project's deliver dir.

        Mandate-13 Layer-3 subprocess black-box: spawn the canonical CLI by
        module-path and observe only its stdout / stderr / exit code. The mode
        resolvers are NEVER imported. This is the SAME definition the operator +
        the DELIVER finalize path invoke. The #65-dissolution observable: on an
        UNCONFIGURED atdd_pure project the verifier must resolve atdd_pure and
        check the AT-completion ledger (NOT exit 2 on a phantom `roadmap.json not
        found`).
        """
        completed = _run_spine_cli([project.deliver_dir], main=_verify_integrity_main)
        return self._classify_verify_run(completed)

    def run_init_log(self, project: ProjectProbe) -> DispatchRun:
        """Fire the REAL `des init-log` CLI (the DELIVER-dispatch port).

        Mandate-13 Layer-3 subprocess black-box. init-log's OBSERVABLE mode
        answer is its refusal behaviour: under atdd_pure it REFUSES to create a
        log (the spine is roadmap-free, exit 1); under classic it CREATES an
        execution-log.json (exit 0). AT-02 pairs THIS answer with
        verify-integrity's answer on the SAME unconfigured project — post-SSOT
        both must resolve atdd_pure.
        """
        completed = _run_spine_cli(
            ["--project-dir", project.project_dir, "--feature-id", _FEATURE_ID],
            main=_init_log_main,
        )
        return self._classify_dispatch_run(completed)

    # --- pure classifiers (SSOT for the observable-outcome derivation) ------

    @staticmethod
    def _classify_verify_run(
        completed: subprocess.CompletedProcess[str],
    ) -> VerifyRun:
        """Derive the port-exposed VerifyRun from a completed subprocess.

        EXIT-CODE-EXACT + marker-exact: a PHANTOM_ROADMAP_REFUSAL is exit 2 AND
        the `roadmap.json not found` marker on the stream (the #65 signature). A
        RESOLVED_ATDD_PURE run took the atdd_pure branch — exit 0 (clean ledger)
        or exit 1 (atdd_pure-shaped integrity violation) WITHOUT the phantom
        marker. Anything else is UNEXPECTED so a verdict never passes for the
        wrong reason.
        """
        combined = completed.stdout + "\n" + completed.stderr
        roadmap_hunt = ROADMAP_NOT_FOUND_MARKER in combined
        outcome = ModeResolutionFixture._verify_outcome(
            completed.returncode, roadmap_hunt
        )
        return VerifyRun(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            outcome=outcome,
            roadmap_hunt=roadmap_hunt,
        )

    @staticmethod
    def _verify_outcome(exit_code: int, roadmap_hunt: bool) -> VerifyOutcome:
        """Map (exit, roadmap-hunt) -> VerifyOutcome. Pure decision table (SSOT)."""
        if exit_code == _VERIFY_USAGE_EXIT and roadmap_hunt:
            return VerifyOutcome.PHANTOM_ROADMAP_REFUSAL
        if exit_code in (_VERIFY_OK_EXIT, _VERIFY_VIOLATION_EXIT) and not roadmap_hunt:
            return VerifyOutcome.RESOLVED_ATDD_PURE
        return VerifyOutcome.UNEXPECTED

    @staticmethod
    def _classify_dispatch_run(
        completed: subprocess.CompletedProcess[str],
    ) -> DispatchRun:
        """Derive the port-exposed DispatchRun from a completed subprocess.

        EXIT-CODE-EXACT + marker-exact: REFUSED_ATDD_PURE is exit 1 AND the
        `workflow.mode is atdd_pure` refusal banner; CREATED_LOG_CLASSIC is exit 0
        AND the `Created execution-log.json` banner. Anything else is UNEXPECTED.
        """
        combined = completed.stdout + "\n" + completed.stderr
        outcome = ModeResolutionFixture._dispatch_outcome(
            completed.returncode, combined
        )
        return DispatchRun(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            outcome=outcome,
        )

    @staticmethod
    def _dispatch_outcome(exit_code: int, combined: str) -> DispatchOutcome:
        """Map (exit, stream) -> DispatchOutcome. Pure decision table (SSOT)."""
        if (
            exit_code == _INIT_LOG_REFUSE_ATDD_PURE_EXIT
            and _INIT_LOG_ATDD_PURE_REFUSAL in combined
        ):
            return DispatchOutcome.REFUSED_ATDD_PURE
        if (
            exit_code == _INIT_LOG_CREATED_EXIT
            and "Created execution-log.json" in combined
        ):
            return DispatchOutcome.CREATED_LOG_CLASSIC
        return DispatchOutcome.UNEXPECTED

    # --- cross-port agreement (AT-02 observable) ----------------------------

    @staticmethod
    def ports_agree_on_atdd_pure(verify: VerifyRun, dispatch: DispatchRun) -> bool:
        """True iff BOTH spine ports resolved the atdd_pure mode answer.

        SSOT for the cross-port default-consistency check (Context-B referential
        transparency) so the step body stays a thin delegate (Mandate-12
        criterion 3). The DELIVER port (init-log) resolving atdd_pure = it
        REFUSED (roadmap-free); the verify port resolving atdd_pure = it took the
        atdd_pure branch (no phantom roadmap hunt). Equal answers = no divergence.
        """
        return (
            verify.outcome is VerifyOutcome.RESOLVED_ATDD_PURE
            and dispatch.outcome is DispatchOutcome.REFUSED_ATDD_PURE
        )

    # --- synthetic atdd_pure artifacts (git-free filesystem) ----------------

    @staticmethod
    def _write_atdd_pure_ledger(deliver_dir: Path) -> None:
        """Seed a minimal AT-completion ledger so the verifier has the atdd_pure
        artifact to inspect (NOT a roadmap.json) once it RESOLVES atdd_pure.

        The atdd_pure spine writes its audit trail to a per-feature append-only
        JSONL ledger (ADR-028 D3), NOT a roadmap.json. Seeding THIS ledger means
        that, once the verifier resolves atdd_pure, it reaches its verdict by
        reading the artifact that EXISTS — proving the #65-dissolution end-to-end
        (verify checks the ledger, never the phantom roadmap).

        GIT-FREE, ZERO-PRODUCTION-IMPORT (Mandate-13, slice-01 house style): the
        ledger is hand-written JSONL, NOT routed through the production
        `AtCompletionLedger` writer — keeping the AT composition free of ANY
        `des.*` production import at the test boundary (slice-01 reimplements the
        canonical hasher in-harness for the same reason). A minimal ledger trips
        the verifier's M7 write-contract on the atdd_pure branch (a feature-scoped
        integrity violation, exit 1) — which is STILL `RESOLVED_ATDD_PURE` with
        `roadmap_hunt=False`: the load-bearing #65-dissolution observable is the
        ABSENCE of the classic `roadmap.json not found` phantom-refusal, NOT a
        clean exit-0. The `_is_resolved_atdd_pure_exit` universe predicate accepts
        BOTH the clean (0) and atdd_pure-integrity-violation (1) verdicts; the
        forbidden value is exit 2 (the classic phantom hunt). This keeps the AT
        decoupled from the M7 `record_hash` internals — it asserts the mode
        RESOLUTION, not the ledger's full integrity verdict.
        """
        import json

        ledger_dir = deliver_dir / ".nwave" / "telemetry" / "atdd-pure"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        record = {"seq": 1, "event": "SliceCommitVerified", "feature_id": _FEATURE_ID}
        (ledger_dir / f"{_FEATURE_ID}.jsonl").write_text(
            json.dumps(record) + "\n", encoding="utf-8"
        )

    @staticmethod
    def _write_mode_config(project_dir: Path, mode_config: ModeConfig) -> None:
        """Write (or, for UNCONFIGURED, deliberately omit) `.nwave/config.yaml`.

        UNCONFIGURED writes NOTHING — the absent file is the #65 trigger. The
        explicit cases write a minimal two-level `workflow:`/`mode:` block the
        stdlib-only resolver parses (the DES bundle stays PyYAML-free).
        """
        if mode_config is ModeConfig.UNCONFIGURED:
            return
        mode_value = (
            "atdd_pure" if mode_config is ModeConfig.EXPLICIT_ATDD_PURE else "classic"
        )
        config_dir = project_dir / ".nwave"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            f"workflow:\n  mode: {mode_value}\n", encoding="utf-8"
        )


def _run_spine_cli(
    flags: list[str], *, main: Callable[[list[str]], int]
) -> subprocess.CompletedProcess[str]:
    """Drive a spine CLI EDGE (`main(argv)`) in-process (Mandate-13 driving-port).

    Replaces the former `python -m des.cli.X` subprocess (env=`_spine_env()`):
    the spine CLIs resolve every path from their absolute args (deliver dir /
    `--project-dir`), so cwd is irrelevant; `NWAVE_FRESHNESS=skip` is set on
    `os.environ` for the call (restored after) to isolate the slice-01
    install-freshness gate exactly as the subprocess env did (RCA #68 / DV-1).
    Returns a `CompletedProcess` so the pure classifiers stay unchanged.
    """
    prior = os.environ.get("NWAVE_FRESHNESS")
    os.environ["NWAVE_FRESHNESS"] = "skip"
    try:
        exit_code, stdout, stderr = run_cli_in_process(flags, cwd=Path.cwd(), main=main)
    finally:
        if prior is None:
            os.environ.pop("NWAVE_FRESHNESS", None)
        else:
            os.environ["NWAVE_FRESHNESS"] = prior
    return subprocess.CompletedProcess(
        args=list(flags), returncode=exit_code, stdout=stdout, stderr=stderr
    )


__all__ = ["ModeResolutionFixture"]

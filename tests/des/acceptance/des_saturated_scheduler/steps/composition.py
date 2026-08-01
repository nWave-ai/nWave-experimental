"""Production-edge composition for the saturated scheduler walking skeleton.

The sole SUT entry is the stable ``des.cli.__main__.main`` dispatcher, driven
through ``run_cli_in_process``. No scheduler module is imported: the absent
route is reached inside the dispatcher at runtime, keeping the DISTILL tests
active-RED rather than collection-broken.

The only authority over a lane's state is the artifact that exists or is
missing, so this composition never hands the scheduler a state table. It writes
the real plan bytes, and it attests artifacts through the production
``AtCompletionLedger`` writer — the same authority the rest of the system uses
to record completion. Every asserted observation comes back from DES stdout and
from the real workspace after the call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from des.adapters.driven.logging.at_completion_ledger import (
    SLICE_COMMIT_VERIFIED,
    AtCompletionLedger,
)
from tests.common.in_process_cli import run_cli_in_process

from .domain_types import CommandObservation, FeatureId, SchedulerRun


_FEATURE_ID = FeatureId("scheduler-demo")

# The producing slice of ``acceptance-test.v1`` is slice-01: attesting that one
# artifact while slice-01 itself remains unfinished is what makes the
# artifact-granular readiness rule falsifiable.
_PRODUCING_SLICE = "slice-01"

_FEATURE_DELTA = """# Feature Delta — scheduler-demo

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | Independent acceptance evidence is ready. | planned | @walking_skeleton | Seeds the first artifact. |
| slice-02 | Independent guidance can be dispatched. | planned | consumes artifact: acceptance-test.v1 | Waits only for the named artifact. |
| slice-03 | A second reasoning lane can proceed independently. | planned |  | No dependency is declared. |
| slice-04 | A local commit operation follows its verification seal. | planned | consumes artifact: verification-seal.v1 | The single local lane remains ordered. |
"""


def provision_feature_plan(root: Path) -> Path:
    """Write the prerequisite plan shared by focused and installed-port tests."""
    path = root / "docs" / "feature" / str(_FEATURE_ID) / "feature-delta.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_FEATURE_DELTA, encoding="utf-8")
    return path


class UnexpectedProcessSpawn(AssertionError):
    """Raised if the scheduler attempts an execution boundary during a plan read."""


def _forbid_process_spawn(*_args: object, **_kwargs: object) -> None:
    raise UnexpectedProcessSpawn(
        "WHAT: des schedule attempted to start a process; "
        "WHY: scheduling is plan-only and OSS dispatch belongs to the native-agent "
        "consumer under hooks; HOW: emit a lane snapshot without an execution call."
    )


@dataclass
class SaturatedSchedulerComposition:
    """Real filesystem inputs plus captured real DES driving-port observations."""

    root: Path

    @property
    def feature_id(self) -> FeatureId:
        return _FEATURE_ID

    @property
    def feature_delta_path(self) -> Path:
        return (
            self.root / "docs" / "feature" / str(self.feature_id) / "feature-delta.md"
        )

    @property
    def evidence_path(self) -> Path:
        """The real audit substrate the production ledger writer owns."""
        return AtCompletionLedger(project_root=self.root).ledger_path()

    def provision_feature_plan(self) -> None:
        provision_feature_plan(self.root)

    def provision_empty_current_evidence(self) -> None:
        """No ledger is created: absence is a real evidence state, not a stub."""
        assert self.evidence_path.exists() is False

    def attest_acceptance_test_artifact(self) -> None:
        """Attest the artifact through the production writer, not by hand.

        The producing slice stays unfinished: only its acceptance-test artifact
        earns terminal evidence. A consumer lane must become ready on that
        artifact alone.
        """
        AtCompletionLedger(project_root=self.root).append_gate_event(
            SLICE_COMMIT_VERIFIED,
            slice_id=_PRODUCING_SLICE,
            feature_id=str(self.feature_id),
        )

    def corrupt_current_evidence(self) -> None:
        """Leave evidence present but undecodable — a real unreadable input."""
        path = self.evidence_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\xff\xfe not a ledger record \x00\x01\n")

    def run_schedule_twice(self) -> SchedulerRun:
        before = self.feature_delta_path.read_bytes()
        evidence_before = self._evidence_bytes()
        first = self._schedule()
        second = self._schedule()
        return SchedulerRun(first, second, before, evidence_before)

    def run_schedule_once(self) -> CommandObservation:
        return self._schedule()

    def workspace_is_unchanged(self, run: SchedulerRun) -> bool:
        return (
            self.feature_delta_path.read_bytes() == run.feature_delta_before
            and self._evidence_bytes() == run.evidence_before
        )

    def _evidence_bytes(self) -> bytes | None:
        path = self.evidence_path
        return path.read_bytes() if path.exists() else None

    def _schedule(self) -> CommandObservation:
        return self._run(
            ("schedule", "--feature-id", str(self.feature_id), "--format", "json")
        )

    def _run(self, argv: tuple[str, ...]) -> CommandObservation:
        # These guards only intercept process creation. A compliant command performs
        # ordinary in-process filesystem reads, then returns a snapshot/diagnostic.
        with (
            patch("subprocess.Popen", _forbid_process_spawn),
            patch("subprocess.run", _forbid_process_spawn),
            patch("os.system", _forbid_process_spawn),
        ):
            exit_code, stdout, stderr = run_cli_in_process(list(argv), cwd=self.root)
        return CommandObservation(exit_code=exit_code, stdout=stdout, stderr=stderr)

    @staticmethod
    def json_event(observation: CommandObservation) -> dict[str, object]:
        """Return DES's one JSON event or raise a WHAT/WHY/HOW active-RED assertion."""
        for line in observation.stdout.splitlines():
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        raise AssertionError(
            "WHAT: des schedule emitted no lane-snapshot JSON event; "
            "WHY: the scheduler route and its read-only snapshot renderer are not "
            "implemented; "
            "HOW: register des schedule and emit the documented lane snapshot. "
            f"Captured exit={observation.exit_code}, stderr={observation.stderr!r}."
        )

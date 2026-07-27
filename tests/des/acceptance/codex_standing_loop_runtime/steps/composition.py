"""Production-surface composition for Codex bounded-continuation ATs.

The only driven behaviour is the public ``des loop`` command and the real
SessionStart hook over its stdin protocol.  The temporary project filesystem is
real; no loop runner, ledger, or selection component is invoked directly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process, run_module_in_process

from .domain_types import BudgetObservation, LimitKind, SessionObservation


def _json_object(text: str) -> dict[str, object]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


@dataclass
class BoundedContinuationComposition:
    """One operator journey through the public command and SessionStart ports."""

    project: Path
    outcome: str | None = None
    before: dict[str, object] = field(default_factory=dict)
    after: dict[str, object] = field(default_factory=dict)
    durable_before: dict[str, object] = field(default_factory=dict)
    durable_after: dict[str, object] = field(default_factory=dict)
    future_arm: dict[str, object] = field(default_factory=dict)
    due_arm: dict[str, object] = field(default_factory=dict)
    observation: SessionObservation | None = None
    budget_observation: BudgetObservation | None = None
    requested_limit: LimitKind | None = None

    def arm_due_work(self, outcome: str) -> None:
        self.outcome = outcome
        self.project.mkdir(parents=True, exist_ok=True)
        exit_code, stdout, _stderr = run_cli_in_process(
            [
                "loop",
                "arm",
                "--project",
                str(self.project),
                "--loop",
                "standing",
                "--idempotency-key",
                "codex-session-start",
                "--max-tokens",
                "1200",
                "--max-wall-seconds",
                "30",
                "--outcome",
                outcome,
                "--format",
                "json",
            ],
            cwd=self.project,
        )
        self.due_arm = _json_object(stdout)
        assert exit_code == 0 and self.due_arm.get("status") == "ok", (
            "WHAT: the public loop control did not arm the fixture work. "
            "WHY: SessionStart can only offer work the operator has already authorised. "
            "HOW: keep `des loop arm` as the sole durable control surface."
        )

    def add_future_due_work(self) -> None:
        """Stage the second unit through the public control, never a fixture seam."""
        exit_code, stdout, _stderr = run_cli_in_process(
            [
                "loop",
                "arm",
                "--project",
                str(self.project),
                "--loop",
                "standing",
                "--idempotency-key",
                "future-codex-session-start",
                "--max-tokens",
                "1200",
                "--max-wall-seconds",
                "30",
                "--cooldown-seconds",
                "1800",
                "--format",
                "json",
            ],
            cwd=self.project,
        )
        self.future_arm = _json_object(stdout)
        assert exit_code == 0 and self.future_arm.get("status") == "ok", (
            "WHAT: the public loop control did not stage the future continued-work unit. "
            "WHY: a SessionStart offer may only select a unit that is due. "
            "HOW: retain a public due-time control that records the later unit separately."
        )

    def start_codex(self) -> None:
        self.before = self.capture_universe()
        self.durable_before = self.capture_durable_loop_state()
        exit_code, stdout, _stderr = run_module_in_process(
            "des.adapters.drivers.hooks.hook_router",
            "session-start",
            "--host-provenance=codex",
            stdin_text=json.dumps(
                {"hook_event_name": "SessionStart", "cwd": str(self.project)}
            ),
            cwd=str(self.project),
        )
        self.after = self.capture_universe()
        self.durable_after = self.capture_durable_loop_state()
        public_text = stdout.lower()
        self.observation = SessionObservation(
            exit_code=exit_code,
            public_text=public_text,
            loop_state=self.after["public.loop.state"]
            if isinstance(self.after["public.loop.state"], str)
            else None,
            attestation_claimed=any(
                token in public_text
                for token in (
                    "continued-work completed",
                    "continued work completed",
                    "continued-work attestation",
                    "continued work attestation",
                )
            ),
            refusal_has_what_why_how=False,
            offered_opportunity_count=public_text.count("continued-work opportunity:"),
        )

    def choose_unsafe_limit(self, kind: LimitKind) -> None:
        """Record the operator's requested bound; the public command acts later."""
        self.requested_limit = kind

    def arm_unsafe_work(self) -> None:
        """Drive the public control surface once for the chosen unsafe bound."""
        assert self.requested_limit is not None
        kind = self.requested_limit
        self.project.mkdir(parents=True, exist_ok=True)
        argv = [
            "loop",
            "arm",
            "--project",
            str(self.project),
            "--loop",
            "standing",
            "--format",
            "json",
        ]
        if kind is not LimitKind.MISSING:
            argv.extend(
                (
                    "--idempotency-key",
                    f"unsafe-{kind.value}",
                    "--max-tokens",
                    "0" if kind is LimitKind.ZERO else "-1",
                )
            )
        exit_code, stdout, stderr = run_cli_in_process(argv, cwd=self.project)
        payload = _json_object(stdout)
        diagnostic = payload.get("diagnostic", {})
        self.observation = SessionObservation(
            exit_code=exit_code,
            public_text=f"{stdout}\n{stderr}".lower(),
            loop_state=None,
            attestation_claimed=False,
            refusal_has_what_why_how=isinstance(diagnostic, dict)
            and all(
                isinstance(diagnostic.get(key), str) and diagnostic[key]
                for key in ("what", "why", "how")
            ),
            offered_opportunity_count=0,
        )
        self.before = {"public.loop.state": None, "public.loop.attestations": ()}
        self.after = self.capture_universe()

    def arm_constrained_work(self, token_allowance: int) -> None:
        """Arm one real public loop with the operator's finite allowance."""
        self.project.mkdir(parents=True, exist_ok=True)
        exit_code, stdout, _stderr = run_cli_in_process(
            [
                "loop",
                "arm",
                "--project",
                str(self.project),
                "--loop",
                "standing",
                "--idempotency-key",
                "constrained-continuation",
                "--max-tokens",
                str(token_allowance),
                "--max-wall-seconds",
                "3",
                "--format",
                "json",
            ],
            cwd=self.project,
        )
        assert exit_code == 0 and _json_object(stdout).get("status") == "ok", (
            "WHAT: the public loop control did not arm the constrained continued work. "
            "WHY: the operator cannot observe enforcement unless the requested allowance is live. "
            "HOW: accept a positive bounded request through `des loop arm`."
        )

    def advance_constrained_work_twice(self) -> None:
        """Drive two distinct operator requests through the real command edge."""
        self.before = self.capture_universe()
        first_exit, first_stdout, _first_stderr = run_cli_in_process(
            [
                "loop",
                "tick",
                "--project",
                str(self.project),
                "--idempotency-key",
                "first-constrained-advance",
                "--format",
                "json",
            ],
            cwd=self.project,
        )
        second_exit, second_stdout, _second_stderr = run_cli_in_process(
            [
                "loop",
                "tick",
                "--project",
                str(self.project),
                "--idempotency-key",
                "second-constrained-advance",
                "--format",
                "json",
            ],
            cwd=self.project,
        )
        inspect_exit, inspect_stdout, _inspect_stderr = run_cli_in_process(
            ["loop", "inspect", "--project", str(self.project), "--format", "json"],
            cwd=self.project,
        )
        self.after = self.capture_universe()
        self.budget_observation = BudgetObservation(
            first_exit_code=first_exit,
            first_event=_json_object(first_stdout),
            second_exit_code=second_exit,
            second_event=_json_object(second_stdout),
            inspection_exit_code=inspect_exit,
            inspection=_json_object(inspect_stdout),
        )

    def capture_universe(self) -> dict[str, object]:
        if not self.project.exists():
            return {"public.loop.state": None, "public.loop.attestations": ()}
        _exit_code, stdout, _stderr = run_cli_in_process(
            ["loop", "list", "--project", str(self.project), "--format", "json"],
            cwd=self.project,
        )
        _inspect_exit, inspect_stdout, _inspect_stderr = run_cli_in_process(
            ["loop", "inspect", "--project", str(self.project), "--format", "json"],
            cwd=self.project,
        )
        payload = _json_object(stdout)
        inspection = _json_object(inspect_stdout)
        state = payload.get("state", {})
        attestations = inspection.get("attestations")
        return {
            "public.loop.state": state.get("desired")
            if isinstance(state, dict)
            else None,
            "public.loop.attestations": tuple(attestations)
            if isinstance(attestations, list)
            else None,
        }

    def capture_durable_loop_state(self) -> dict[str, object]:
        """Read list and inspection facts exclusively from the public loop CLI."""
        _list_exit, list_stdout, _list_stderr = run_cli_in_process(
            ["loop", "list", "--project", str(self.project), "--format", "json"],
            cwd=self.project,
        )
        _inspect_exit, inspect_stdout, _inspect_stderr = run_cli_in_process(
            ["loop", "inspect", "--project", str(self.project), "--format", "json"],
            cwd=self.project,
        )
        listing = _json_object(list_stdout)
        inspection = _json_object(inspect_stdout)
        attestations = inspection.get("attestations")
        return {
            "public.loop.list": listing.get("state", {}),
            "public.loop.attestations": tuple(attestations)
            if isinstance(attestations, list)
            else None,
            "public.loop.future_due_count": listing.get("state", {}).get(
                "future_due_count"
            )
            if isinstance(listing.get("state"), dict)
            else None,
        }

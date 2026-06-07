"""Composition root for slice-01 (BypassCause StrEnum extraction).

Wires three driving surfaces against the spine-ledger gate:

  * AT-1 parity outline — drives the production gate script
    `python -m scripts.hooks.spine_ledger_gate` as a real subprocess (Layer 3
    driving port per Mandate-13) across five cause branches. Asserts the
    stdout JSON cause field on each branch matches the documented vocabulary.
    Real I/O: filesystem (tmp_path target carries `.nwave/telemetry/atdd-pure/`,
    `.nwave/disabled-gates`, audit log), subprocess, env var.

  * AT-2 type-safety — imports `BypassCause` from the production module
    (`scripts.hooks.spine_ledger_gate`). PARITY-UNIT EXEMPTION per the
    fix-installer-self-referential-des-import slice-01 precedent: comparing
    an enum member to its expected string value IS the contract. The
    exemption is documented in `at-scaffold-notes-slice-01.md`.

  * AT-3 regression-zero — invokes the predecessor-feature acceptance suite
    via `pytest` as a real subprocess (Layer 3+). The SUT is the predecessor
    suite directory; the contract is "every scenario in the suite still
    passes under the refactored gate".

Business logic — subprocess construction, target tree seeding, slice-trailer
synthesis, ledger evidence seeding via the real `AtCompletionLedger` writer,
pytest invocation — lives here as the single source of truth (Mandate-12
criterion 3: step bodies ≤2 statements, final statement is a composition
method call, zero control flow).

Standalone (NO inheritance from sibling features' fixtures): this is a fresh
feature per the dispatch contract. The cause-branch wiring is intentionally
duplicated from the predecessor `KillSwitchFixture` / `LedgerEvidenceFixture`
to keep this slice self-contained — the predecessor feature's fixtures
exercise the FULL contract; this slice exercises only the cause-vocabulary
surface.

RED-for-the-right-reason:

  * AT-1 parity outline — RED-edge case: today the gate ships literal `_CAUSE_*`
    string constants, so the outline PASSES on the current implementation
    (the cause strings are already correct). Its RED fires if DELIVER's
    refactor accidentally drifts a cause-value spelling. This is a negative
    regression guard: GREEN before AND after DELIVER, RED only on regression.
    Pre-DELIVER classification: PASSING.

  * AT-2 type-safety — the symbol `BypassCause` does NOT exist on the
    production module today. The import inside `inspect_value_object` raises
    `ImportError` which the fixture wraps as `AssertionError` so the Red
    Gate snapshot classifies the test as RED (not BROKEN). DELIVER's
    extraction makes this test GREEN.

  * AT-3 regression-zero — today the predecessor suite is GREEN (15/15).
    The test runs a real pytest subprocess against the predecessor directory
    and asserts a 15-pass outcome. PASSING today; RED fires only if DELIVER's
    refactor regresses any predecessor scenario.

Mandate-13 (driving-port-only): AT-1 and AT-3 are Layer 3 subprocess driving
ports. AT-2 imports `BypassCause` directly — parity-unit exemption per
fix-installer slice-01 precedent (comparing an enum extracted as a value
object to its expected literal IS the contract; there is no driving-port
surface that observes the enum's TYPE — only its VALUE through stdout, which
AT-1 already covers).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


# Repo root: tests/installer/acceptance/<feature>/steps/composition.py -> up five levels.
_REPO_ROOT = Path(__file__).resolve().parents[5]
_GATE_MODULE = "scripts.hooks.spine_ledger_gate"
_BYPASS_ENV = "NWAVE_SPINE_LEDGER_GATE_BYPASS"
_DISABLED_GATES_RELPATH = Path(".nwave") / "disabled-gates"
_TELEMETRY_RELPATH = Path(".nwave") / "telemetry" / "atdd-pure"
_AUDIT_LOG_DIR_RELPATH = Path(".nwave") / "des" / "logs"
_GATE_NAME = "spine-ledger-gate"
_PREDECESSOR_SUITE_RELPATH = Path(
    "tests/installer/acceptance/atdd-spine-ledger-enforcement-gate-v2"
)
_PREDECESSOR_AT_COUNT = 15

# Branch -> precondition recipe + expected (exit_code, cause) tuple. The
# composition fixture consumes this table to set up each AT-1 parametrize
# case without inlining business logic in step bodies.
#
# - env-bypass: env var set, telemetry empty, slice trailer present -> exit 0
# - file-bypass: disabled-gates file lists gate, telemetry empty -> exit 0
# - dormant: no telemetry dir at all -> exit 0
# - block-refused: telemetry dir present but EMPTY of records, slice trailer
#   present and unverified -> exit 1
# - block-allowed: telemetry dir present, a healthy ledger seeded with the
#   trailer's slice id -> exit 0
_BRANCH_CONTRACTS: dict[str, tuple[int, str]] = {
    "env-bypass": (0, "operator-env-bypass"),
    "file-bypass": (0, "operator-file-bypass"),
    "dormant": (0, "spine-telemetry-absent"),
    "block-refused": (1, "block-ledger-evidence-missing"),
    "block-allowed": (0, "ledger-evidence-present"),
}


@dataclass(frozen=True)
class GateInvocation:
    """One captured invocation of the spine-ledger gate subprocess."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def stdout_json(self) -> dict:
        """Parse the single-line JSON verdict from stdout, or {} if absent."""
        for line in self.stdout.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                continue
        return {}


@dataclass(frozen=True)
class ValueObjectInspection:
    """Captured inspection of the production `BypassCause` value object."""

    is_str_enum: bool
    member_values: dict[str, str]
    import_error: str | None = None


@dataclass(frozen=True)
class PytestSubprocessResult:
    """One captured pytest subprocess invocation."""

    exit_code: int
    stdout: str
    stderr: str
    passed_count: int


def _audit_log_path(target_root: Path) -> Path:
    """Return today's UTC-dated audit log path under the target root."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return target_root / _AUDIT_LOG_DIR_RELPATH / f"audit-{today}.log"


def _seed_verified_slice_record(
    target_root: Path, feature_id: str, slice_id: str
) -> None:
    """Append one M7-shape `SliceCommitVerified` record via `AtCompletionLedger`.

    Mirrors the predecessor-feature seeding helper (composition.py:337). Goes
    through the real ledger writer so the M7 contract (seq + record_hash) is
    satisfied — slice-01 production reads through the same writer (Mandate-12
    SSOT), so the seeding MUST match.
    """
    src_path = _REPO_ROOT / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    from des.adapters.driven.logging.at_completion_ledger import (  # type: ignore[import-not-found]
        AtCompletionLedger,
    )

    ledger = AtCompletionLedger(feature_id, target_root)
    ledger.append_gate_event(event="SliceCommitVerified", slice_id=slice_id)


class BypassCauseFixture:
    """Drives the spine-ledger gate across cause branches and inspects BypassCause.

    Standalone (no inheritance — this is a fresh feature per the dispatch
    contract). Exposes three concern groups:

      * Cause-branch wiring (AT-1) — `wire_branch(branch_name)` seeds the
        tmp_path target for one of five named branches; `run_gate()` invokes
        the production gate subprocess; `assert_branch_outcome()` checks
        exit code + stdout cause against the documented contract.

      * Value-object inspection (AT-2) — `inspect_value_object()` imports
        `BypassCause` from `scripts.hooks.spine_ledger_gate` and captures
        its type + member values; `assert_*` helpers verify enum-shape +
        per-member value contracts.

      * Predecessor-suite regression (AT-3) — `run_predecessor_suite()`
        invokes pytest as a real subprocess against the predecessor feature's
        acceptance directory; `assert_predecessor_suite_all_pass()` verifies
        the documented 15-pass outcome.
    """

    def __init__(self, target_root: Path) -> None:
        self._target_root = target_root
        self._target_root.mkdir(parents=True, exist_ok=True)
        self._commit_msg_path = self._target_root / "candidate-commit-msg.txt"
        self._wired_branch: str | None = None

    # ---- AT-1 cause-branch wiring + invocation ----

    def wire_branch(self, branch_name: str) -> None:
        """Seed the tmp_path target tree for one of the five cause branches.

        The branch table fully describes each precondition; the method
        consults `_BRANCH_CONTRACTS` for the expected outcome (used by the
        Then-side assertion) and performs the per-branch FS / env setup.
        """
        assert branch_name in _BRANCH_CONTRACTS, (
            f"Unknown branch {branch_name!r}; expected one of "
            f"{sorted(_BRANCH_CONTRACTS)}"
        )
        self._commit_msg_path.write_text(
            "chore(test): synthetic candidate commit\n\nSlice-Id: slice-99\n",
            encoding="utf-8",
        )
        if branch_name == "env-bypass":
            (self._target_root / _TELEMETRY_RELPATH).mkdir(parents=True, exist_ok=True)
            os.environ[_BYPASS_ENV] = "1"
        elif branch_name == "file-bypass":
            (self._target_root / _TELEMETRY_RELPATH).mkdir(parents=True, exist_ok=True)
            path = self._target_root / _DISABLED_GATES_RELPATH
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{_GATE_NAME}\n", encoding="utf-8")
            os.environ.pop(_BYPASS_ENV, None)
        elif branch_name == "dormant":
            os.environ.pop(_BYPASS_ENV, None)
        elif branch_name == "block-refused":
            (self._target_root / _TELEMETRY_RELPATH).mkdir(parents=True, exist_ok=True)
            os.environ.pop(_BYPASS_ENV, None)
        elif branch_name == "block-allowed":
            _seed_verified_slice_record(
                self._target_root, feature_id="pista1v2-fixture", slice_id="slice-99"
            )
            os.environ.pop(_BYPASS_ENV, None)
        self._wired_branch = branch_name

    def run_gate(self) -> GateInvocation:
        """Invoke the production gate script as a real subprocess against the target."""
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                _GATE_MODULE,
                "--commit-msg-file",
                str(self._commit_msg_path),
                "--ledger-root",
                str(self._target_root / _TELEMETRY_RELPATH),
                "--target-root",
                str(self._target_root),
            ],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env={**os.environ},
        )
        return GateInvocation(
            exit_code=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )

    def assert_branch_cause(
        self, invocation: GateInvocation, expected_cause: str
    ) -> None:
        """Assert the stdout JSON `cause` field equals the expected branch cause."""
        actual = invocation.stdout_json.get("cause")
        assert actual == expected_cause, (
            f"Expected stdout JSON cause {expected_cause!r}; got {actual!r}.\n"
            f"stdout: {invocation.stdout!r}\nstderr: {invocation.stderr!r}"
        )

    def assert_stdout_is_single_line_json(self, invocation: GateInvocation) -> None:
        """Assert stdout contains exactly one parseable single-line JSON verdict."""
        non_empty_lines = [
            line for line in invocation.stdout.splitlines() if line.strip()
        ]
        assert len(non_empty_lines) == 1, (
            f"Expected exactly one non-empty stdout line; got "
            f"{len(non_empty_lines)}.\nstdout: {invocation.stdout!r}"
        )
        # Parse must succeed (stdout_json silently returns {} on parse fail,
        # so we re-attempt explicitly to surface a clear AssertionError).
        try:
            json.loads(non_empty_lines[0])
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"Expected stdout to be valid single-line JSON; got "
                f"{non_empty_lines[0]!r} (parse error: {exc!s})"
            ) from None

    def assert_branch_exit_code(
        self, invocation: GateInvocation, expected_exit_code: int
    ) -> None:
        """Assert exit code matches the documented branch contract."""
        assert invocation.exit_code == expected_exit_code, (
            f"Expected exit code {expected_exit_code}; got {invocation.exit_code}.\n"
            f"stdout: {invocation.stdout!r}\nstderr: {invocation.stderr!r}"
        )

    @staticmethod
    def expected_exit_code_for_branch(branch_name: str) -> int:
        """Look up the documented exit code for a named branch."""
        return _BRANCH_CONTRACTS[branch_name][0]

    @staticmethod
    def expected_cause_for_branch(branch_name: str) -> str:
        """Look up the documented cause string for a named branch."""
        return _BRANCH_CONTRACTS[branch_name][1]

    # ---- AT-2 value-object inspection ----

    def inspect_value_object(self) -> ValueObjectInspection:
        """Import `BypassCause` from the production module + capture its shape.

        Parity-unit exemption (Mandate-13 footnote): the SUT for AT-2 is a
        value object whose contract is "be a StrEnum with these named members
        and these string values". There is no driving-port surface that
        observes the enum's type independently from its value — the stdout
        cause field (AT-1's surface) only sees the string value, not the type.
        Comparing the enum's type AND member-name-to-value mapping to its
        documented contract IS the test contract.

        The fixture catches `ImportError` (raised when `BypassCause` does not
        yet exist on the module — the RED-edge for AT-2 today) and surfaces
        it as a populated `import_error` field so the Then-side assertion
        raises a clean `AssertionError` (Mandate 7 RED-not-BROKEN).
        """
        src_path = _REPO_ROOT / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))
        scripts_path = _REPO_ROOT
        if str(scripts_path) not in sys.path:
            sys.path.insert(0, str(scripts_path))
        try:
            from scripts.hooks.spine_ledger_gate import (  # type: ignore[import-not-found]
                BypassCause,
            )
        except ImportError as exc:
            return ValueObjectInspection(
                is_str_enum=False,
                member_values={},
                import_error=str(exc),
            )

        from enum import StrEnum

        is_str_enum = isinstance(BypassCause, type) and issubclass(BypassCause, StrEnum)
        member_values: dict[str, str] = {}
        if is_str_enum:
            for name, member in BypassCause.__members__.items():
                member_values[name] = str(member.value)
        return ValueObjectInspection(
            is_str_enum=is_str_enum,
            member_values=member_values,
            import_error=None,
        )

    def assert_value_object_is_str_enum(
        self, inspection: ValueObjectInspection
    ) -> None:
        """Assert the imported value object is a `StrEnum` subclass."""
        assert inspection.import_error is None, (
            f"Expected `BypassCause` to be importable from "
            f"`scripts.hooks.spine_ledger_gate`; got ImportError: "
            f"{inspection.import_error}"
        )
        assert inspection.is_str_enum, (
            "Expected `BypassCause` to be a subclass of `StrEnum`; "
            "got a value that is not a StrEnum subclass."
        )

    def assert_value_object_member_value(
        self,
        inspection: ValueObjectInspection,
        member_name: str,
        expected_value: str,
    ) -> None:
        """Assert the value object carries a named member with the expected value."""
        actual = inspection.member_values.get(member_name)
        assert actual == expected_value, (
            f"Expected `BypassCause.{member_name}` to have value "
            f"{expected_value!r}; got {actual!r}.\n"
            f"Captured members: {inspection.member_values!r}"
        )

    # ---- AT-3 predecessor-suite regression ----

    def run_predecessor_suite(self) -> PytestSubprocessResult:
        """Invoke pytest against the predecessor-feature acceptance directory.

        Real subprocess (Layer 3+) — invokes the pipenv-installed pytest so
        the predecessor suite's conftest + steps + composition load the way
        they do on a developer's machine. Captures stdout for the trailing
        passed-count line (`====== 15 passed in X.XXs ======`).
        """
        suite_dir = _REPO_ROOT / _PREDECESSOR_SUITE_RELPATH
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(suite_dir),
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
            ],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            env={**os.environ},
        )
        passed_count = _extract_pytest_passed_count(completed.stdout or "")
        return PytestSubprocessResult(
            exit_code=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            passed_count=passed_count,
        )

    def assert_predecessor_suite_all_pass(self, result: PytestSubprocessResult) -> None:
        """Assert pytest exited 0 with every scenario passing."""
        assert result.exit_code == 0, (
            f"Expected predecessor suite to exit 0 (all-pass); got "
            f"{result.exit_code}.\n"
            f"stdout (tail): {result.stdout[-2000:]!r}\n"
            f"stderr (tail): {result.stderr[-2000:]!r}"
        )

    def assert_predecessor_suite_count(
        self, result: PytestSubprocessResult, expected_count: int
    ) -> None:
        """Assert pytest's summary line reports the expected pass count."""
        assert result.passed_count == expected_count, (
            f"Expected predecessor suite to report {expected_count} passing "
            f"tests; got {result.passed_count}.\n"
            f"stdout (tail): {result.stdout[-2000:]!r}"
        )

    @staticmethod
    def predecessor_at_count() -> int:
        """Return the documented predecessor AT count (15 per feature-delta)."""
        return _PREDECESSOR_AT_COUNT


def _extract_pytest_passed_count(stdout: str) -> int:
    """Parse the passing-count from pytest stdout via the language-agnostic contract.

    Primary surface: the repo's custom pytest plugin emits a single-line JSON
    contract `NWAVE_TEST_RESULT:{"passed":N,"failed":...,...}` per
    [[feedback_target_machine_language_not_python_2026_05_22]]. The contract
    is the SSOT — never parse the human-readable summary when the contract is
    present (the customised plugin in this repo suppresses the standard
    `N passed in X.XXs` summary line in favour of a Rich-rendered table that
    the legacy regex cannot read).

    Fallback: standard pytest summary regex (`N passed`) for runners that
    have not installed the contract emitter. Returns 0 if neither shape
    matches (the test's assertion then surfaces a clean failure).
    """
    import re

    contract_match = re.search(r'NWAVE_TEST_RESULT:\{[^}]*"passed":\s*(\d+)', stdout)
    if contract_match:
        return int(contract_match.group(1))
    summary_match = re.search(r"(\d+)\s+passed", stdout)
    return int(summary_match.group(1)) if summary_match else 0

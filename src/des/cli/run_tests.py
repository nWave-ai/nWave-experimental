"""des.cli.run_tests -- the TestRunnerPort CLI composition root (ADR-042).

The driving port of the per-language test-runner adapter. Invoked as a
subprocess (the ``run_tests`` module entry, ``--target <dir> --out <path>``) it
runs a REAL test invocation over the target directory and emits one
``nwave.test_result.v1`` JSON whose counts are byte-faithful to what actually
ran -- read from the runner's own structured result objects, NEVER scraped from
the runner's human-readable stdout.

Two emissions:

  * a real RUN -> ``nwave.test_result.v1`` whose ``passed`` / ``failed`` /
    ``collected`` / ``exit_code`` (and the remaining frozen count fields) come
    from the actual pytest run. A genuinely-failing target therefore surfaces
    ``failed > 0`` -- this is the anti-theater witness: the counts cannot be a
    hard-coded green template, they vary with the target.
  * a fail-safe ABSTAIN -> when the named runner cannot be invoked, the port
    emits a ``nwave.earned_verdict.v1``-shaped ABSTAIN envelope
    (``status: "ABSTAIN"``, ``reason: "runner-absent"``) IN PLACE of a run. It
    MUST NOT fabricate a passing ``test_result.v1`` for a run that never
    happened -- a fabricated green is the exact theater the whole gate exists to
    prevent.

LANGUAGE_BOUND adapter: the pytest runner literal lives HERE (catalog #1,
correct). It is never leaked into the target-blind verdict CORE
(``des.domain.earned_verdict``), which branches on counts alone.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


TEST_RESULT_SCHEMA = "nwave.test_result.v1"
EARNED_VERDICT_SCHEMA = "nwave.earned_verdict.v1"

# The runner this adapter implements. ``--runner`` defaults here; any other
# value names a runner this adapter cannot invoke -> fail-safe ABSTAIN.
_PYTEST_RUNNER = "pytest"
_RUNNER_ABSENT_REASON = "runner-absent"
_ABSTAIN_STATUS = "ABSTAIN"


class _CountCollector:
    """A pytest plugin that tallies real test outcomes from the runner's own
    ``TestReport`` objects -- never from parsed stdout.

    pytest classifies every call-phase report into exactly one ``category``
    via :func:`_pytest.terminal.TerminalReporter`-equivalent logic; this plugin
    reads that same structured outcome (``outcome`` + the ``wasxfail`` marker)
    and increments the matching frozen-contract count. Reading the report keeps
    the counts byte-faithful to what pytest itself recorded, for any target.
    """

    def __init__(self) -> None:
        self.counts: dict[str, int] = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "xfailed": 0,
            "xpassed": 0,
            "error": 0,
        }
        self.collected = 0

    def pytest_collection_modifyitems(self, items: list[object]) -> None:
        self.collected = len(items)

    def pytest_runtest_logreport(self, report: object) -> None:
        self.counts[_category(report)] += 1 if _is_counted(report) else 0


def _is_counted(report: object) -> bool:
    """Whether this phase report contributes a count.

    A run produces a setup / call / teardown report per test; only the
    call-phase report (or a failing setup/teardown -- a collection/fixture
    error) names a counted outcome. Passing setup/teardown phases are not
    re-counted.
    """
    when = getattr(report, "when", None)
    if when == "call":
        return True
    return getattr(report, "outcome", None) == "failed"


def _category(report: object) -> str:
    """Map one pytest report onto its frozen-contract count category."""
    if getattr(report, "when", None) != "call":
        return "error"
    outcome = getattr(report, "outcome", None)
    is_x = getattr(report, "wasxfail", None) is not None
    if outcome == "passed":
        return "xpassed" if is_x else "passed"
    if outcome == "skipped":
        return "xfailed" if is_x else "skipped"
    return "xfailed" if is_x else "failed"


def main(argv: list[str] | None = None) -> int:
    """Run the target through the test-runner port. Returns a process exit code."""
    args = _parse_args(argv)
    if not _runner_is_invokable(args.runner):
        _write_envelope(args.out, _abstain_envelope())
        return 2
    collector = _CountCollector()
    exit_code = _run_pytest(args.target, collector)
    _write_envelope(args.out, _test_result_envelope(collector, exit_code))
    return exit_code


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the ``--target --runner --out`` argv contract."""
    parser = argparse.ArgumentParser(prog="run-tests")
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--runner", default=_PYTEST_RUNNER)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args(argv)


def _runner_is_invokable(runner: str) -> bool:
    """Whether the named runner is one this adapter can actually invoke.

    This adapter implements pytest, run in-process via ``pytest.main``. A runner
    name this adapter does not implement, or a pytest that is not importable in
    this interpreter, cannot be invoked -> the fail-safe ABSTAIN path. The check
    is real (an actual import probe), not a hard-coded allow-list.
    """
    if runner != _PYTEST_RUNNER:
        return False
    return importlib.util.find_spec("pytest") is not None


def _run_pytest(target: Path, collector: _CountCollector) -> int:
    """Run pytest over the target with the count-collecting plugin attached.

    The exit code is pytest's own ``ExitCode`` int -- 0 when every test passed,
    nonzero when a test failed or the run errored. Counts come from the attached
    plugin's tally of the runner's ``TestReport`` objects.
    """
    import pytest

    return int(
        pytest.main(
            [str(target), "-p", "no:cacheprovider", "-p", "no:randomly", "-q"],
            plugins=[collector],
        )
    )


def _test_result_envelope(
    collector: _CountCollector, exit_code: int
) -> dict[str, object]:
    """Assemble a complete frozen ``nwave.test_result.v1`` from the real run.

    Every frozen field is emitted (``error`` singular, per the byte-identity
    contract with the SF pytest-plugin emission) and every count is the runner's
    own tally -- so the envelope varies faithfully with the target.
    """
    counts = collector.counts
    return {
        "schema": TEST_RESULT_SCHEMA,
        "runner": _PYTEST_RUNNER,
        "exit_code": exit_code,
        "collected": collector.collected,
        "passed": counts["passed"],
        "failed": counts["failed"],
        "xfailed": counts["xfailed"],
        "xpassed": counts["xpassed"],
        "skipped": counts["skipped"],
        "deselected": 0,
        "error": counts["error"],
    }


def _abstain_envelope() -> dict[str, object]:
    """Assemble the fail-safe ABSTAIN envelope for an un-invokable runner.

    A ``nwave.earned_verdict.v1``-shaped ABSTAIN emitted IN PLACE of a run: no
    ``test_result.v1`` is produced, so the gate can never read a never-executed
    target as green (``reason: "runner-absent"``).
    """
    return {
        "schema": EARNED_VERDICT_SCHEMA,
        "status": _ABSTAIN_STATUS,
        "reason": _RUNNER_ABSENT_REASON,
    }


def _write_envelope(out: Path, envelope: dict[str, object]) -> None:
    """Write an emitted envelope as JSON to ``out``."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover - subprocess entry point
    sys.exit(main(sys.argv[1:]))

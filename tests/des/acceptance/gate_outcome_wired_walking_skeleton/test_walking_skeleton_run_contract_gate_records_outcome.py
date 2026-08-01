"""FEATURE walking skeleton (gate-outcome-record-seam) -- the ONE
`@walking_skeleton` subprocess-e2e scenario for this entire feature, owned by
slice-04 per the feature's own deferred decision (feature-delta.md, `[REF] WS
Strategy -- slice-02`: "slice-04's DISTILL dispatch owns the feature's
`@walking_skeleton` decision").

DIRECT-SURFACE feature (an operator runs `des run-contract-gate` directly;
no packaging/install step sits between the driving port and the consumer) --
the normal driving-port walking skeleton applies, no Artifact Lineage
Closure obligation.

Why `run-contract-gate`, not one of the other 4 named gates: DDD-5's own
Reuse Analysis names it "already self-times... already accepts an injectable
OutputPort -- the natural exemplar", the peer-evidence-selected first
population member. It is also the first point where "run the gate for real,
read the ledger, see the typed verdict" becomes an observable, real-subprocess
user journey -- the exact test slice-02's WS-deferral reasoning named as the
condition for slice-04 to satisfy.

Litmus (Cockburn/GOOS): a non-technical stakeholder confirms "yes, that is
what an operator needs" -- run the real installed gate against a real (tiny)
Python project; see its digest verdict print; then find, on the SAME repo, a
durable ledger record naming that exact run's outcome. No component is
substituted: real subprocess fork (`python -m des.cli.run_contract_gate`),
real pytest --collect-only nested run, real JSONL ledger file on disk.

Tagged `@walking_skeleton @driving_port` per the feature's tagging
convention (`nw-distill-port-treatment-policy`).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.domain.gate_outcome import GateVerdict


_GATE_NAME = "run-contract-gate"


def _plant_tiny_pytest_project(repo_root: Path) -> None:
    """A real, minimal, fast-collecting pytest project -- one passing test."""
    (repo_root / "pyproject.toml").write_text(
        "[project]\nname = 'ws-outcome-fixture'\nversion = '0.0.1'\n",
        encoding="utf-8",
    )
    tests_dir = repo_root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_fixture.py").write_text(
        "def test_it_passes():\n    assert True\n", encoding="utf-8"
    )


def test_walking_skeleton_run_contract_gate_records_its_own_outcome(
    tmp_path: Path,
) -> None:
    """@walking_skeleton @driving_port

    Given an operator has a real (tiny) Python project on disk
    When the operator runs the REAL installed `des run-contract-gate
      --collect-only --print-digest` as a genuine subprocess (no interpreter
      shortcut, no monkeypatch)
    Then the gate prints its digest verdict and exits 0 (the existing,
      unchanged contract)
    And a durable `GateOutcomeRecorded` ledger record naming
      `gate="run-contract-gate"` and `outcome=PASS` is findable on disk
      afterward, through the SAME driving port every other reader of this
      seam uses (`AtCompletionLedger.read_records`).
    """
    _plant_tiny_pytest_project(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "des.cli.run_contract_gate",
            "--repo",
            str(tmp_path),
            "--collect-only",
            "--print-digest",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, (
        "the real installed run-contract-gate must PASS a tiny valid pytest "
        f"project -- exit={completed.returncode}, stdout={completed.stdout!r}, "
        f"stderr={completed.stderr!r}"
    )
    stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
    assert stdout_lines, "expected at least the bare digest line on stdout"

    # The durable, operator-queryable half of the walking skeleton: the SAME
    # driving port (AtCompletionLedger) any future reader uses to answer
    # "did run-contract-gate pass or fail, last time it ran".
    ledger = AtCompletionLedger(project_root=tmp_path)
    records = [
        record
        for record in ledger.read_records(event_type="GateOutcomeRecorded")
        if record.get("gate") == _GATE_NAME
    ]
    assert len(records) == 1, (
        f"expected exactly one durable GateOutcomeRecorded record for "
        f"{_GATE_NAME!r} after the real subprocess run -- got {records!r}"
    )
    assert records[0].get("outcome") == GateVerdict.PASS.value, records[0]

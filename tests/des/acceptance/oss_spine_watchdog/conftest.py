"""Composition root + shared fixtures for oss-spine-watchdog slice-01.

Pillar 3 (App as in production): the SUT is the REAL collection-health precheck
driving port — the contract gate's `--collect-only` collection probe, invoked
exactly as the G_COMMIT exit-gate precheck (DESIGN OQ-1 / R-2) would invoke it:

    python -m des.cli run-contract-gate --collect-only --print-digest --repo <proj>

against a synthetic project tree under tmp_path. The fresh-interpreter worker
(`_collect_scope_worker.py`) actually collects the contract-marked tests; on a
broken-import module pytest collection aborts (exit 2) and the gate emits a
single-line `MalformedInput` event; on a clean suite it prints a bare gate-scope
digest (exit 0). The AT observes the precheck's decision via the process exit
code + the parsed stdout payload — NEVER an internal call.

Mandate-13 (invariant 1+2): the driving port is the contract-gate CLI subprocess.
This conftest NEVER does `from des.cli.run_contract_gate import _collect_scope`
(or any `from des.{domain,application,adapters}.X import Y`) to invoke the probe
at the test boundary — the only production reference is the subprocess module-path
string `des.cli` (a Layer-3 subprocess driving port, the tolerable-variant of S2).

Mandate-12 criterion 2/3: `CollectionPrecheckFixture` is the single source of
truth for ALL business logic the step methods need. Step bodies in
`steps_slice_01_collection_precheck.py` delegate here — each body is ≤2 statements
ending in one `fixture.<method>(...)` call (or one assertion), no control flow
inline.

DISTILL-authored RED scaffold (ADR-025): the precheck's collection-crash
DETECTION (exit 2) + clean-pass (exit 0) ALREADY work today (empirically witnessed
2026-06-01) — those are the regression pins (AT-02). The slice-01 NEW behavior
that does NOT exist yet is KPI-3: the worker emits only `{"pytest_exit_code": 2}`
and the gate only `"collection failed: pytest collection exited 2"` — NEITHER
NAMES THE CRASHING MODULE (DESIGN R-1: "the ONE genuine gap — EXTEND
`_collect_scope_worker.py` to capture and emit the crashing module identifier").
So AT-01 (named-module) + AT-03 (named-module even under NWAVE_FRESHNESS=skip)
RED-fail with an assertion mismatch (`crash_named` is False today) — NOT an import
error (Mandate-7 RED-vs-BROKEN preserved). AT-02 (clean-pass) GREEN-passes today
as the no-false-positive regression pin.

Layer 3 (subprocess against tmp_path): example-only (Mandate 9 v2 — @real-io
because the driven set includes a real filesystem adapter + a real fresh-interpreter
pytest subprocess). No PBT machinery imported.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from .steps.domain_types import (
    ContractSuiteProbe,
    FreshnessOptOut,
    PrecheckOutcome,
    PrecheckVerdict,
    SuiteCollectability,
)


# Repo root = .../nWave-dev (this file lives 4 dirs deep under tests/des/...).
_REPO_ROOT = Path(__file__).resolve().parents[4]
_REPO_SRC = _REPO_ROOT / "src"

# The single broken-import token the synthetic crashing module imports. Used by
# the fixture to build the crash AND by the assertion to recognise the module the
# precheck must name (KPI-3). One SSOT for the crash topology.
_CRASHING_MODULE_REL = "tests/test_broken_import_xyz.py"


def _parse_gate_event_line(stdout_text: str) -> dict | None:
    """Extract the first single-line JSON gate event from the precheck stdout.

    On a collection crash the gate emits one `{"event": "MalformedInput", ...}`
    line (`run_contract_gate.py:384`). On a clean collection the first stdout line
    is the bare digest (NOT JSON) — this returns None for that case. Pure function.
    """
    for raw_line in stdout_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("event"):
            return payload
    return None


def _first_digest_line(stdout_text: str) -> str | None:
    """Return the bare gate-scope digest the clean precheck prints, if any.

    A clean `--collect-only --print-digest` prints the digest as the first plain
    stdout line (`run_contract_gate.py:389`). Recognise it as a 64-hex-char line
    that is not JSON. Returns None when no such line is present. Pure function.
    """
    for raw_line in stdout_text.splitlines():
        line = raw_line.strip()
        if len(line) == 64 and all(c in "0123456789abcdef" for c in line):
            return line
    return None


def _crash_named(payload: dict | None) -> tuple[bool, str | None]:
    """Decide whether a collection-crash payload NAMES the crashing module (KPI-3).

    The KPI-3 contract (DISCUSS KPI-3 / DESIGN R-1): on a collection crash the
    precheck payload must carry a NON-EMPTY crashing-module identifier — NOT just
    a bare `pytest collection exited 2`. DESIGN R-1 specifies the worker will
    register a `pytest_collectreport` hook and surface the failing collector's
    `nodeid`; the gate threads it into the `MalformedInput` payload.

    We recognise the named module under any of the reuse-first field placements
    DESIGN left open (a dedicated `crashing_module` field is the recommended
    placement; the error string carrying the module path is the fallback). The
    module is "named" iff the payload references the synthetic crashing module's
    path — a bare `pytest collection exited 2` (today's output) is NOT named.

    Returns (crash_named, named_module). Pure function.
    """
    if payload is None:
        return False, None
    # Preferred placement (DESIGN R-1 recommendation): a dedicated field.
    dedicated = payload.get("crashing_module")
    if isinstance(dedicated, str) and dedicated.strip():
        return True, dedicated
    # Fallback placement: the error string names the module path. The crashing
    # module's basename must appear — a bare "pytest collection exited 2" does not.
    error = payload.get("error")
    if isinstance(error, str) and "test_broken_import_xyz" in error:
        return True, error
    return False, None


class CollectionPrecheckFixture:
    """Composition-root service for oss-spine-watchdog slice-01 ATs.

    Pillar 3: builds a synthetic DES project under tmp_path (clean or
    broken-import contract suite) and fires the SAME collection-health precheck
    the G_COMMIT exit-gate precheck fires — the contract-gate `--collect-only`
    CLI subprocess (DESIGN OQ-1). The clean-vs-crash topology and the env-parity
    no-skip requirement are all expressed as filesystem + env topology. The AT
    observes the precheck's decision via exit code + parsed stdout payload.

    Mandate-12 criterion 3: every public method is the SSOT for one piece of
    business logic. Step bodies do a typed lookup + one method call; nothing more.
    """

    def __init__(self, tmp_path: Path) -> None:
        self._tmp_path = tmp_path

    # --- synthetic contract-suite construction (the collection seam) -------

    def build_contract_suite(
        self, *, collectability: SuiteCollectability
    ) -> ContractSuiteProbe:
        """Lay out a synthetic DES project whose contract suite the precheck runs.

        Every project gets a `conftest.py` that marks each collected item with the
        contract marker (`unit`) so the gate's `-m "unit or integration or
        acceptance"` scope is non-empty, plus one clean contract test. For
        COLLECTION_CRASHES, ALSO drop one contract test module with an import-time
        crash (a broken import) — pytest collection aborts (exit 2), the #68 root.

        GIT-FREE, pure filesystem. The crashing module is isolated to this
        tmp_path project so it cannot poison the real test tree's collection
        (DEVOPS CI constraint: reproduce the SHAPE, not the BLAST RADIUS).
        """
        project_root = self._tmp_path / "synthetic-project"
        tests_dir = project_root / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (project_root / "conftest.py").write_text(
            "import pytest\n\n\n"
            "def pytest_collection_modifyitems(config, items):\n"
            "    for item in items:\n"
            "        item.add_marker(pytest.mark.unit)\n",
            encoding="utf-8",
        )
        (tests_dir / "test_clean_contract.py").write_text(
            "def test_collects_fine():\n    assert True\n", encoding="utf-8"
        )
        crashing_module_rel = None
        if collectability is SuiteCollectability.COLLECTION_CRASHES:
            (tests_dir / "test_broken_import_xyz.py").write_text(
                "import this_module_does_not_exist_xyz  # noqa\n\n\n"
                "def test_never_runs():\n    assert True\n",
                encoding="utf-8",
            )
            crashing_module_rel = _CRASHING_MODULE_REL
        return ContractSuiteProbe(
            project_root=project_root,
            collectability=collectability,
            crashing_module_rel=crashing_module_rel,
        )

    # --- the driving-port fire (real contract-gate collection probe) -------

    def run_precheck(
        self,
        suite: ContractSuiteProbe,
        *,
        opt_out: FreshnessOptOut = FreshnessOptOut.UNSET,
    ) -> PrecheckOutcome:
        """Fire the REAL collection-health precheck on the synthetic project.

        The driving port is the contract-gate collection probe exactly as the
        G_COMMIT exit-gate precheck runs it (DESIGN OQ-1 / R-2):

            python -m des.cli run-contract-gate --collect-only --print-digest
                   --repo <synthetic-project>

        ── The two DISTINCT freshness concerns (disentangled empirically, 2026-06-01) ──
        There are TWO independent freshness surfaces, and slice-01 tests only the
        COLLECTION, never the install-freshness gate:

        1. The `des.cli` IMPORT-TIME install-freshness gate (`des/cli/__init__.py:18`
           `assert_fresh_or_explain()`) refuses the WHOLE CLI with exit 78 when there
           is no install manifest — which a synthetic tmp_path project never has. This
           gate is NOT what slice-01 tests; it must be bypassed so the contract gate
           can run at all. We bypass it with `NWAVE_FRESHNESS=skip` on EVERY precheck.

        2. The CONTRACT-SUITE COLLECTION — the thing slice-01 tests. Empirically, a
           pytest COLLECTION crash returns exit 2 INDEPENDENTLY of `NWAVE_FRESHNESS`:
           `NWAVE_FRESHNESS=skip` skips concern (1) but the collection STILL runs and
           STILL crashes on a broken import. This is the precise RCA #68 P1-B lesson —
           the skip masked the install-freshness gate's hook-regression, but the
           collection crash is a pytest-collection failure that the skip does NOT and
           MUST NOT mask (DISCUSS D-7 / DV-4: "the collection runs no-skip").

        ── ENV-PARITY earned-trust probe (AT-03) ──
        `opt_out=SKIP` proves the collection-crash detection + KPI-3 naming is
        INVARIANT to `NWAVE_FRESHNESS` — even with the operator's skip set, the
        collection crash is still detected AND named. Because concern (1) is already
        skipped on every precheck (to get past the missing-manifest exit-78 on the
        synthetic tree), the AT-03 difference is the ASSERTION that the COLLECTION
        verdict is unchanged by the skip — the masked-collection bug shape cannot
        recur (the collection is never the thing the skip touches).

        PYTHONPATH points at the real `src/` so `des.cli` resolves; CWD is the
        synthetic project root so `--repo` and collection rootdir agree. Returns a
        PrecheckOutcome capturing the port-exposed observables: exit code, the
        parsed `MalformedInput` payload (crash) or bare digest (clean), and the
        KPI-3 crash-named / named-module signals.
        """
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(_REPO_SRC),
            # Bypass concern (1) — the install-freshness gate — on EVERY precheck:
            # a synthetic tmp_path project has no install manifest, so the gate would
            # exit-78 the CLI before the contract gate runs. This is NOT the surface
            # slice-01 tests; the COLLECTION (concern 2) runs regardless and is what
            # the ATs assert against. `opt_out=SKIP` (AT-03) is then the env-parity
            # ASSERTION that the collection verdict is invariant to this skip.
            "NWAVE_FRESHNESS": "skip",
        }
        for var in ("LC_ALL", "LANG", "PYTHONIOENCODING", "HOME"):
            if var in os.environ:
                env[var] = os.environ[var]
        # AT-03 env-parity probe: opt_out=SKIP is the scenario asserting the
        # collection-crash naming is invariant to the operator's freshness skip.
        # The baseline already carries the skip (concern 1 bypass), so SKIP here is
        # a no-op on the env — the AT's value is the ASSERTION that the COLLECTION
        # verdict (exit 2 + named module) is unchanged, reproducing the #68 P1-B
        # shape where the skip masked freshness but never the collection crash.
        _ = opt_out  # the skip is already set above; opt_out drives the assertion

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "des.cli",
                "run-contract-gate",
                "--collect-only",
                "--print-digest",
                "--repo",
                str(suite.project_root),
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(suite.project_root),
            timeout=120,
        )
        payload = _parse_gate_event_line(completed.stdout)
        digest = _first_digest_line(completed.stdout)
        crash_named, named_module = _crash_named(payload)
        verdict = (
            PrecheckVerdict.PROCEED
            if completed.returncode == 0
            else PrecheckVerdict.LOUD_NAMED
        )
        return PrecheckOutcome(
            exit_code=completed.returncode,
            crash_named=crash_named,
            named_module=named_module,
            verdict=verdict,
            stdout_payload=payload,
            digest=digest,
        )


# Closed-enum sanity: cite every PrecheckVerdict the assertions reference so an
# enum rename surfaces here as an unused-name lint at refactor time.
_ENUM_CITATIONS = (
    PrecheckVerdict.PROCEED,
    PrecheckVerdict.LOUD_NAMED,
)


@pytest.fixture
def collection_precheck_fixture(tmp_path) -> CollectionPrecheckFixture:
    """The single composition-root service all step methods delegate to."""
    return CollectionPrecheckFixture(tmp_path)


@pytest.fixture
def state() -> dict:
    """Per-scenario scratchpad: `suite`, `opt_out`, `outcome`, `before`."""
    return {}


__all__ = [
    "CollectionPrecheckFixture",
]

"""Composition root for the contract-gate digest-undercount slice-01 ATs.

Drives the SUT exclusively through the real ``des run-contract-gate
--collect-only --print-digest`` CLI subprocess (Layer 3, Mandate-13). NO
production import -- the gate is exercised via ``python -m
des.cli.run_contract_gate`` as a child process, and the only observations are
the CLI's exit code + the bare digest on stdout + the emitted
``GateScopeDigest`` JSON event on stderr.

Why subprocess (not just convention, ADR-001 Earned-Trust probe #3): the fix
runs pytest's in-process collection API. Driving the CLI as a child keeps that
in-process pytest pollution inside the short-lived CLI interpreter, never the
AT's own pytest session -- Mandate-13 is here a CORRECTNESS isolation boundary.

State-delta + Universe (Mandate 8): the assertion step asserts via
``assert_state_delta`` over a port-exposed universe (exit code, the PARITY of
the GateScopeDigest event's ``node_id_count`` vs ``collected_count``, idempotence
flag, repo-mutation flag) -- never internal struct fields.

Layer 3 (subprocess / real I/O) -> example-only, no PBT (Mandate 9 / 11).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from nwave_ai.state_delta import assert_state_delta, set_to

from .domain_types import (
    Coverage,
    GateOutcome,
    GateVerdict,
    ScopeIntegrity,
    SuiteShape,
)


# The CLI exit code the gate uses to fail closed on an untrustworthy collection
# (malformed input). Exit 0/1 mean the gate produced a verdict.
_FAIL_CLOSED_EXIT = 2

# A populated, parametrized suite -- a real `-q` collect reports N>0 collected.
_POPULATED_SUITE = (
    "import pytest\n\n\n"
    "@pytest.mark.unit\n"
    '@pytest.mark.parametrize("case", range(6))\n'
    "def test_contract_case(case):\n"
    '    """populated suite."""\n'
    "    assert case >= 0\n"
)
# The tamper: empty ``session.items`` at ``tryfirst pytest_collection_finish``,
# so the populated suite is collected (count > 0 upstream) but every per-node
# identity is suppressed before the digest. Mirrors the sibling
# atdd_pure_spine_dogfood_defects lying-tree fixture VERBATIM.
_SUPPRESS_AFTER_COLLECTION_CONFTEST = (
    "import pytest\n\n\n"
    "@pytest.hookimpl(tryfirst=True)\n"
    "def pytest_collection_finish(session):\n"
    "    session.items[:] = []\n"
)
_TAMPER_PYPROJECT = (
    "[tool.pytest.ini_options]\n"
    'markers = ["unit: u", "integration: i", "acceptance: a"]\n'
    'testpaths = ["tests"]\n'
)


# The Earned-Trust parity ORACLE (ADR-001 probe #1) -- SCALE-INVARIANT. It
# replaces a magnitude floor (which would only prove "more than N node-ids" and
# would silently pass a future grown-then-re-collapsed suite -- the regression
# class this gate exists to catch).
#
# Oracle: the digested-set cardinality (``node_id_count``) must equal pytest's
# OWN in-process collected count (``collected_count`` = len(session.items) from
# the SAME in-process session, ADR-001 §82-86), modulo the documented
# hypothesis-rerun duplicates. ADR-001 §98 measured the (fspath, item.name)
# identity at 4504 / 4523 -- exactly 19 collected items are the same test
# re-collected under hypothesis rerun, whose collapse is CORRECT not a defect.
# So the parity tolerance is ``0 <= collected_count - node_id_count <= 19``.
#
# Why stronger than a magnitude floor AND stronger than == stdout
# `_collected_count`: it reads pytest's IN-PROCESS ``len(session.items)``,
# immune to the very stdout-parse heuristic this feature removes. A re-collapse
# at ANY scale breaks parity (gap >> tolerance), where a magnitude floor would
# have passed it silently. The only constant here is the ADR-sourced rerun
# tolerance; no suite-size magic.
_HYPOTHESIS_RERUN_TOLERANCE = 19

# Repo root carrying the live contract suite. This file lives at
# tests/des/cli/fix_contract_gate_digest_undercount/steps/composition.py ->
# parents[4] is the repo root.
_LIVE_REPO = Path(__file__).resolve().parents[4]


class ContractGateDigestComposition:
    """Owns the repo-under-gate + the CLI invocation + the observable outcome.

    All business logic (suite staging, CLI invocation, fingerprinting) lives
    here; step bodies are thin delegations (Mandate-12).
    """

    def __init__(self, tmp_path: Path) -> None:
        self._tmp_path = tmp_path
        self._repo: Path | None = None
        self._first: subprocess.CompletedProcess[str] | None = None
        self._second: subprocess.CompletedProcess[str] | None = None
        self._first_event: dict[str, object] | None = None
        self._repo_fp_before: str | None = None
        self._repo_fp_after: str | None = None
        # slice-02: the exit-gate (verify) path observables.
        self._verify_tree: Path | None = None
        self._verify_outcome: GateOutcome | None = None

    # -- Given ----------------------------------------------------------------

    def use_suite(self, shape: SuiteShape) -> None:
        """Choose the test tree the gate will fingerprint."""
        self._repo = (
            _LIVE_REPO
            if shape is SuiteShape.CANONICAL_LIVE
            else self._stage_collapse_prone_project()
        )

    def stage_tree(self, integrity: ScopeIntegrity) -> None:
        """Stage a committed git tree whose collected scope is honest or suppressed.

        Both trees carry the SAME populated, parametrized suite. The SUPPRESSED
        tree adds the ``tryfirst pytest_collection_finish`` tamper conftest. A
        ``Gate-Scope:`` trailer is anchored on HEAD to the digest the gate
        currently emits, so the exit-gate ``--verify-gate-scope`` path has a
        trailer to verify against.
        """
        self._verify_tree = self._materialise_tree(integrity)

    # -- When -----------------------------------------------------------------

    def run_print_digest_twice(self) -> None:
        """Invoke the real CLI ``--collect-only --print-digest`` twice.

        Twice, so idempotence (Earned-Trust probe #2) is observable; repo
        fingerprint captured before/after to assert the read-only contract.
        """
        repo = self._require_repo()
        self._repo_fp_before = self._fingerprint_repo(repo)
        self._first = self._invoke_print_digest(repo)
        self._second = self._invoke_print_digest(repo)
        self._repo_fp_after = self._fingerprint_repo(repo)
        self._first_event = self._parse_event(self._first)

    # -- Then -----------------------------------------------------------------

    def assert_coverage(self, coverage: Coverage) -> None:
        """Assert the digest fingerprints the full canonical scope (or not).

        Observable universe (port-exposed only):
          - ``exit_code``         -- the CLI exit code (0 success).
          - ``digest_covers_full_scope`` -- the PARITY ORACLE: the digested-set
            cardinality (``node_id_count``) equals pytest's in-process
            ``collected_count`` (``len(session.items)``) modulo the documented
            hypothesis-rerun tolerance. Scale-invariant; the fix MUST emit BOTH
            ``node_id_count`` AND ``collected_count`` on the GateScopeDigest
            event for this to be observable through the driving port.
          - ``digest_idempotent`` -- two consecutive runs byte-identical.
          - ``repo_unchanged``    -- --print-digest never mutates the repo.
        """
        first, second = self._require_runs()
        node_id_count = self._field("node_id_count")
        collected_count = self._field("collected_count")
        before = {
            "exit_code": None,
            "digest_covers_full_scope": None,
            "digest_idempotent": None,
            "repo_unchanged": None,
        }
        after = {
            "exit_code": first.returncode,
            "digest_covers_full_scope": self._parity_holds(
                node_id_count, collected_count
            ),
            "digest_idempotent": first.stdout.strip() == second.stdout.strip(),
            "repo_unchanged": self._repo_fp_before == self._repo_fp_after,
        }
        expected_full_scope = coverage is Coverage.FULL_CANONICAL
        assert_state_delta(
            before,
            after,
            universe={
                "exit_code",
                "digest_covers_full_scope",
                "digest_idempotent",
                "repo_unchanged",
            },
            expected={
                "exit_code": set_to(0),
                "digest_covers_full_scope": set_to(expected_full_scope),
                "digest_idempotent": set_to(True),
                "repo_unchanged": set_to(True),
            },
        )

    # -- When (slice-02) ------------------------------------------------------

    def verify_gate_scope_via_commit_gate(self) -> None:
        """Drive the EXIT-GATE path the G_COMMIT gate actually runs.

        ``--verify-gate-scope`` re-derives a fresh digest and compares it to the
        commit's ``Gate-Scope:`` trailer -- the path the exit gate invokes, NOT
        ``--print-digest`` (slice-01 wired its parity guard only into
        ``--print-digest``, so driving only that path would miss the latent gap
        this slice closes). Exit 2 = fail-closed; exit 0/1 = verdict produced.
        """
        tree = self._require_verify_tree()
        run = self._invoke_verify_gate_scope(tree)
        verdict = (
            GateVerdict.FAILED_CLOSED
            if run.returncode == _FAIL_CLOSED_EXIT
            else GateVerdict.PRODUCED
        )
        self._verify_outcome = GateOutcome(
            verdict=verdict,
            exit_code=run.returncode,
            stdout=run.stdout,
            stderr=run.stderr,
        )

    # -- Then (slice-02) ------------------------------------------------------

    def assert_gate_verdict(self, expected: GateVerdict) -> None:
        """Assert the exit-gate verdict, via the port-exposed observable universe.

        Observable universe (port-exposed only):
          - ``gate_verdict`` -- FAILED_CLOSED (exit 2) vs PRODUCED (exit 0/1),
            the only outcome the exit gate exposes to its caller.
        """
        outcome = self._require_verify_outcome()
        before = {"gate_verdict": None}
        after = {"gate_verdict": outcome.verdict}
        assert_state_delta(
            before,
            after,
            universe={"gate_verdict"},
            expected={"gate_verdict": set_to(expected)},
        )

    # -- internals ------------------------------------------------------------

    def _require_verify_tree(self) -> Path:
        assert self._verify_tree is not None, "tree not staged (Given step missing)"
        return self._verify_tree

    def _require_verify_outcome(self) -> GateOutcome:
        assert self._verify_outcome is not None, "gate not verified (When step missing)"
        return self._verify_outcome

    def _materialise_tree(self, integrity: ScopeIntegrity) -> Path:
        repo = (self._tmp_path / f"{integrity.value}_tree").resolve()
        pkg = repo / "tests"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "test_populated.py").write_text(_POPULATED_SUITE)
        if integrity is ScopeIntegrity.SUPPRESSED:
            (pkg / "conftest.py").write_text(_SUPPRESS_AFTER_COLLECTION_CONFTEST)
        (repo / "pyproject.toml").write_text(_TAMPER_PYPROJECT)
        self._git(repo, "init", "-q")
        self._git(repo, "config", "user.email", "t@t")
        self._git(repo, "config", "user.name", "t")
        self._git(repo, "add", "-A")
        self._git(repo, "commit", "-q", "-m", "contract suite")
        run = self._invoke_print_digest(repo)
        digest = run.stdout.strip().splitlines()[0] if run.stdout.strip() else ""
        self._git(
            repo,
            "commit",
            "-q",
            "--amend",
            "-m",
            f"contract suite\n\nGate-Scope: {digest}",
        )
        return repo

    @staticmethod
    def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = {
            k: v
            for k, v in __import__("os").environ.items()
            if not k.startswith("PYTEST")
        }
        return subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, env=env
        )

    def _invoke_verify_gate_scope(self, repo: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "des.cli.run_contract_gate",
                "--repo",
                str(repo),
                "--verify-gate-scope",
                "--commit",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )

    def _require_repo(self) -> Path:
        assert self._repo is not None, "suite not chosen (Given step missing)"
        return self._repo

    def _require_runs(
        self,
    ) -> tuple[subprocess.CompletedProcess[str], subprocess.CompletedProcess[str]]:
        assert self._first is not None and self._second is not None, (
            "CLI not invoked (When step missing)"
        )
        return self._first, self._second

    def _field(self, name: str) -> object:
        """Read a named field off the first run's GateScopeDigest event.

        ``None`` when the event is absent OR the field is absent. On master the
        event carries NEITHER ``node_id_count`` NOR ``collected_count``, so both
        reads return None -> parity cannot hold -> RED for the right reason.
        """
        return self._first_event.get(name) if self._first_event else None

    def _parity_holds(self, node_id_count: object, collected_count: object) -> bool:
        """The scale-invariant parity oracle.

        True iff BOTH counts are present positive ints AND the digested set
        covers pytest's in-process collected scope within the documented
        hypothesis-rerun tolerance:

            collected_count > 0
            node_id_count   > 0
            0 <= collected_count - node_id_count <= _HYPOTHESIS_RERUN_TOLERANCE

        The lower ``> 0`` bound is the non-vacuity sanity guard. The bounded
        gap is the ONLY legitimate collapse (the same test re-collected under
        hypothesis rerun). Any larger gap is the undercount this gate exists to
        catch -- at ANY suite scale.
        """
        if not (isinstance(node_id_count, int) and isinstance(collected_count, int)):
            return False
        if node_id_count <= 0 or collected_count <= 0:
            return False
        gap = collected_count - node_id_count
        return 0 <= gap <= _HYPOTHESIS_RERUN_TOLERANCE

    def _invoke_print_digest(self, repo: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "des.cli.run_contract_gate",
                "--repo",
                str(repo),
                "--collect-only",
                "--print-digest",
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )

    def _parse_event(
        self, completed: subprocess.CompletedProcess[str]
    ) -> dict[str, object] | None:
        events = [
            json.loads(line.strip())
            for line in completed.stderr.splitlines()
            if line.strip().startswith("{") and _is_json(line.strip())
        ]
        matches = [e for e in events if e.get("event") == "GateScopeDigest"]
        return matches[0] if matches else None

    def _fingerprint_repo(self, repo: Path) -> str:
        """Stable mtime fingerprint -- read-only contract probe.

        --print-digest must NOT write trailers, run the suite, or mutate the
        tree. For the live repo, fingerprint a small stable anchor set; for the
        tmp project, walk it whole.
        """
        if repo == _LIVE_REPO:
            anchors = [
                repo / "pyproject.toml",
                repo / "src" / "des" / "cli" / "run_contract_gate.py",
            ]
            parts = [f"{p}:{p.stat().st_mtime_ns}" for p in anchors if p.exists()]
        else:
            parts = [
                f"{p.relative_to(repo)}:{p.stat().st_mtime_ns}"
                for p in sorted(repo.rglob("*"))
                if p.is_file()
            ]
        return hashlib.sha256("\n".join(parts).encode()).hexdigest()

    def _stage_collapse_prone_project(self) -> Path:
        """Stage a tmp pytest project whose stdout-parse collapses but whose
        canonical (fspath::item.name) collection does not.

        Mirrors the empirical anchor: one class with 14 methods sharing a class
        docstring + a 6-case parametrized function. Stock ``-q`` collect stdout
        emits byte-identical docstring-summary lines that ``set()`` collapses,
        while ``session.items`` keeps every ``item.name`` distinct.
        """
        proj = self._tmp_path / "collapse_proj"
        (proj / "tests").mkdir(parents=True, exist_ok=True)
        (proj / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\n"
            'addopts = "-q"\n'
            "markers = [\n"
            '  "unit: unit", "integration: integration", "acceptance: acceptance",\n'
            "]\n"
            'testpaths = ["tests"]\n'
        )
        (proj / "tests" / "conftest.py").write_text("")
        methods = "\n".join(
            f"    def test_case_{i}(self):\n        assert True\n" for i in range(14)
        )
        (proj / "tests" / "test_collapse.py").write_text(
            "import pytest\n\n\n"
            "@pytest.mark.unit\n"
            "class TestCollapse:\n"
            '    """One shared class docstring -- the collapse anchor."""\n\n'
            f"{methods}\n\n"
            "@pytest.mark.unit\n"
            '@pytest.mark.parametrize("n", [0, 1, 2, 3, 4, 5])\n'
            "def test_param(n):\n"
            '    """One shared function docstring -- parametrize collapse."""\n'
            "    assert n >= 0\n"
        )
        return proj


def _is_json(line: str) -> bool:
    try:
        json.loads(line)
        return True
    except json.JSONDecodeError:
        return False

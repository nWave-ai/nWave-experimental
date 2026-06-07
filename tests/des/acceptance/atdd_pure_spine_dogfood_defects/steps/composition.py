"""Composition root for fix-atdd-pure-spine-dogfood-defects (Mandate-12 SSOT).

Port-to-port: every service method drives a REAL production entry point --
`des.cli.run_contract_gate.main` (the canonical contract-gate CLI) and
`des.domain.des_marker_parser` (the U0 marker domain) -- not a decomposed
helper. Step bodies invoke these service methods and never inline business
logic (Mandate-12 criterion 3).

The composition wires the production interpreter-backed CLI for slice-00 and
slice-01 (Architecture of Reference: a driving port -> real adapter, CLI runner
via subprocess). slice-02 drives the pure-function marker domain directly.
"""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from des.cli import run_contract_gate

from .domain_types import (
    CollectScope,
    CollectVerdict,
    Digest,
    DispatchPhase,
    DispatchRecognition,
    DispatchScope,
    GuardOutcome,
)


# The repo root -- the contract tree slice-00 and slice-01 probe.
_REPO_ROOT = Path(__file__).resolve().parents[5]

# pytest's exit code on a collection error (defect-3 condition (a), S-8).
_PYTEST_COLLECTION_ERROR_EXIT = 2
# pytest's exit code on a genuinely-empty suite.
_PYTEST_NO_TESTS_EXIT = 5
# the exit code `run_contract_gate` returns when it fails closed -- it raises
# `_CollectionError`, the CLI maps that to exit 2 (DoD-2). Exit-code-exact:
# any OTHER non-zero is a wrong failure mode, surfaced as GuardOutcome.UNEXPECTED.
_GATE_FAIL_CLOSED_EXIT = 2


@dataclass
class CollectProbeResult:
    """The observable outcome of a `pytest --collect-only` probe.

    The EXIT CODE is the authoritative collection signal (residuality S-8,
    DoD-2): exit 2 == collection error, anything else == collected. The
    `error_count` string-parse is defence-in-depth ONLY -- a Then step must
    never assert on it alone (HIGH 4).
    """

    exit_code: int
    error_count: int
    node_id_count: int

    @property
    def verdict(self) -> CollectVerdict:
        """The user-observable collection verdict -- keyed on the exit code.

        Authoritative signal: `exit_code == 2` ⟺ HAS_ERRORS. The string-parsed
        `error_count` is NOT consulted here -- it is corroborating telemetry
        only, surfaced via `error_count` for defence-in-depth assertions.
        """
        return (
            CollectVerdict.HAS_ERRORS
            if self.exit_code == _PYTEST_COLLECTION_ERROR_EXIT
            else CollectVerdict.CLEAN
        )


@dataclass
class GateRunResult:
    """The observable outcome of a `run_contract_gate` CLI invocation."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def outcome(self) -> GuardOutcome:
        """How the gate resolved -- derived EXIT-CODE-EXACT (BLOCKER 1).

        DoD-2 requires the guard to raise `_CollectionError` -> exit 2
        SPECIFICALLY. A wrong failure mode (exit 1 `GateScopeUnverified`, exit
        3/5, argparse error, uncaught exception) is NOT silently absorbed into
        FAILED_CLOSED -- it surfaces as UNEXPECTED, so a fail-closed Then step
        catches a wrong-exit defect instead of passing for the wrong reason.
        """
        if self.exit_code == 0:
            return GuardOutcome.DIGEST_PRINTED
        if self.exit_code == _GATE_FAIL_CLOSED_EXIT:
            return GuardOutcome.FAILED_CLOSED
        return GuardOutcome.UNEXPECTED

    @property
    def digest(self) -> Digest:
        """The bare digest line printed on stdout (empty when none)."""
        first = self.stdout.strip().splitlines()
        return Digest(first[0] if first else "")


@dataclass
class SpineDogfoodComposition:
    """Production composition root for the three atdd_pure-spine defect fixes."""

    repo: Path = _REPO_ROOT
    last_collect: CollectProbeResult | None = field(default=None)
    last_gate_run: GateRunResult | None = field(default=None)
    last_recognition: DispatchRecognition | None = field(default=None)

    # --- slice-00: contract-suite collection ------------------------------

    def probe_contract_collection(self, root: Path | None = None) -> CollectProbeResult:
        """Run the real `pytest --collect-only` contract probe over a tree.

        Drives the exact collect scope slice-01's guard fingerprints. The
        collect argv is `-o "addopts=--strict-markers -q"` -- it clears the
        inherited `addopts` (dropping the inherited `-q`/`-ra` that would
        otherwise combine with anything to a `-qq` double-quiet) and re-supplies
        BOTH `--strict-markers` (residuality S-1) AND exactly one `-q`. The
        custom `tests/conftest.py` plugin emits `path::nodeid` lines ONLY at
        exactly single-`-q`: at zero `-q` it prints a domain table (0 node-ids),
        at `-qq` it prints per-file counts (0 node-ids). This is the SAME
        corrected argv slice-01's `_collect_node_ids` fix uses.

        ``root`` defaults to the real repo (the slice-00 walking-skeleton
        scope); passing a synthetic tree drives the AT(3) broken-import probe.
        """
        target = root if root is not None else self.repo
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-m",
                "unit or integration or acceptance",
                "--collect-only",
                "-o",
                "addopts=--strict-markers -q",
                "-p",
                "no:cacheprovider",
            ],
            cwd=target,
            capture_output=True,
            text=True,
        )
        text = completed.stdout + completed.stderr
        error_count = sum(
            int(tok)
            for line in text.splitlines()
            if "error" in line.lower() and "during collection" in line.lower()
            for tok in line.split()
            if tok.isdigit()
        )
        node_ids = [ln for ln in completed.stdout.splitlines() if "::" in ln]
        self.last_collect = CollectProbeResult(
            exit_code=completed.returncode,
            error_count=error_count,
            node_id_count=len(node_ids),
        )
        return self.last_collect

    # --- slice-01: the E2 contract gate -----------------------------------

    def run_collect_only_digest(self, repo: Path) -> GateRunResult:
        """Invoke `run_contract_gate --collect-only --print-digest` on ``repo``.

        Drives the real CLI entry point `run_contract_gate.main` -- the same
        definition the U2 G_COMMIT exit gate invokes.
        """
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            exit_code = run_contract_gate.main(
                ["--repo", str(repo), "--collect-only", "--print-digest"]
            )
        self.last_gate_run = GateRunResult(
            exit_code=exit_code, stdout=out.getvalue(), stderr=err.getvalue()
        )
        return self.last_gate_run

    def test_tree_for_scope(self, root: Path, scope: CollectScope) -> Path:
        """Resolve the contract test tree the slice-01 guard runs against.

        Every untrustworthy scope is a synthetic on-disk tree materialised
        under ``root`` -- the closed, fixture-controlled reproduction of the
        guard's trigger condition. ZERO_NODES_EXIT_ZERO is the populated-suite/
        zero-node-ids tree built by ``make_zero_nodes_tree``; COLLECTION_ERROR
        is the broken-import tree. Tree-shape selection lives here, not in the
        step body (Mandate-12 criterion 3).

        ZERO_NODES_EXIT_ZERO is NOT the real repo: once slice-01's
        `_collect_node_ids` fix lands, the real repo collects cleanly and DOES
        emit `path::nodeid` lines -- it can no longer reproduce the populated-
        but-zero-node-ids state. The synthetic tree reproduces that state
        deterministically and independently of the very fix this AT verifies.
        """
        if scope is CollectScope.ZERO_NODES_EXIT_ZERO:
            return self.make_zero_nodes_tree(root)
        return self.make_test_tree(root, scope)

    def make_zero_nodes_tree(self, root: Path) -> Path:
        """Materialise a tree that reports a populated suite yet parses to zero
        node-ids -- the EXACT condition `run_contract_gate`'s fail-closed guard
        is built to catch (DoD-2).

        The tree carries N>0 contract-marked tests, so pytest's `-q`
        collect summary genuinely prints `<N> tests collected` (the guard's
        `_collected_count` reads N>0). A tree-local `conftest.py` empties
        `session.items` in a `tryfirst` `pytest_collection_finish` hook AFTER
        pytest has computed `session.testscollected` -- so the `-q` collect
        printer iterates an empty item list and emits ZERO `path::nodeid`
        lines, while the populated count summary still prints.

        This drives the gate's REAL `_collect_node_ids` path (the gate's own
        hardcoded `-o "addopts=--strict-markers -q"` argv): a populated count
        with zero parsed node-ids -- the guard MUST raise `_CollectionError`
        -> exit 2. The reproduction is independent of the double-`-q` defect
        slice-01 removes, so the AT genuinely reds if the guard regresses.

        BLOCKER 2 / residuality R-3: the synthetic tree is anchored
        MECHANICALLY to its real pytest signature before the guard sees it --
        a raw `pytest --collect-only -q` of the tree is asserted to report a
        populated `tests collected` count while emitting zero `::` node-id
        lines (exit 0). A drift in the hook semantics fails HERE, not silently
        downstream.
        """
        (root / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\n"
            'markers = ["unit", "integration", "acceptance"]\n'
        )
        (root / "test_populated.py").write_text(
            "import pytest\n\n"
            "@pytest.mark.unit\ndef test_a():\n    assert True\n\n"
            "@pytest.mark.acceptance\ndef test_b():\n    assert True\n"
        )
        # The trigger mechanism: empty session.items in collection_finish
        # (tryfirst), AFTER session.testscollected is fixed. pytest's -q
        # collect printer then lists zero node-ids, but still prints the
        # populated `<N> tests collected` summary line.
        (root / "conftest.py").write_text(
            "import pytest\n\n\n"
            "@pytest.hookimpl(tryfirst=True)\n"
            "def pytest_collection_finish(session):\n"
            "    # session.testscollected is already computed; emptying\n"
            "    # session.items suppresses the per-node `::` listing while\n"
            "    # the populated count summary still prints -- the exact\n"
            "    # populated-suite / zero-node-ids state the guard catches.\n"
            "    session.items = []\n"
        )
        self._anchor_zero_nodes_collect(root)
        return root

    @staticmethod
    def _anchor_zero_nodes_collect(tree: Path) -> None:
        """Assert ``tree`` raw-collects to a populated count with zero `::` lines.

        The fixture-anchor precondition for ZERO_NODES_EXIT_ZERO (BLOCKER 2 /
        R-3): a raw `pytest --collect-only -q` of the synthetic tree is
        verified to (a) exit 0, (b) print a `<N>/<M> tests collected` summary
        with N>0, and (c) emit ZERO `path::nodeid` lines. This IS the guard's
        trigger condition -- verified mechanically before `run_contract_gate`
        ever sees the tree, so a drift in the conftest-hook mechanism fails
        here rather than passing the AT for the wrong reason.
        """
        raw = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-m",
                "unit or integration or acceptance",
                "--collect-only",
                "-o",
                "addopts=--strict-markers -q",
                "-p",
                "no:cacheprovider",
                str(tree),
            ],
            cwd=tree,
            capture_output=True,
            text=True,
        )
        node_lines = [
            ln
            for ln in raw.stdout.splitlines()
            if "::" in ln and not ln.startswith(" ")
        ]
        count = run_contract_gate._collected_count(raw.stdout)
        assert raw.returncode == 0, (
            f"zero-nodes synthetic tree at {tree} raw-collected with exit "
            f"{raw.returncode}, expected 0 -- the fixture is not anchored to "
            f"the populated-suite trigger state (BLOCKER 2 / residuality R-3)"
        )
        assert count > 0, (
            f"zero-nodes synthetic tree at {tree} reported {count} collected "
            "tests, expected a populated suite (N>0) -- the guard's "
            "`_collected_count` would not see a populated suite"
        )
        assert not node_lines, (
            f"zero-nodes synthetic tree at {tree} emitted {len(node_lines)} "
            "`::` node-id line(s), expected zero -- the conftest hook did not "
            "suppress the node listing (BLOCKER 2 / residuality R-3)"
        )

    def make_test_tree(self, root: Path, scope: CollectScope) -> Path:
        """Materialise a synthetic contract test tree in one of the closed scopes.

        Drives the slice-01 guard's enumerable condition universe -- a tree that
        collects cleanly, errors during collection, or carries no contract-marked
        tests. The CLI then runs against this real on-disk tree.

        BLOCKER 2 / residuality R-3: the synthetic COLLECTION_ERROR and
        GENUINELY_EMPTY trees are MECHANICALLY anchored to their real pytest
        failure mode here -- a raw `pytest --collect-only` of the tree is
        asserted to yield the expected exit code (2 for a genuine collection
        error, 5 for no-tests-found) BEFORE the guard logic is ever exercised.
        Without this anchor a slice-01 error scenario could pass post-fix for
        the wrong reason (e.g. exit 5 "no tests" mistaken for a collection
        error).
        """
        (root / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\n"
            'markers = ["unit", "integration", "acceptance"]\n'
        )
        if scope is CollectScope.COLLECTION_ERROR:
            (root / "test_broken.py").write_text(
                "import pytest\nimport a_module_that_does_not_exist  # noqa\n\n"
                "@pytest.mark.unit\ndef test_x():\n    assert True\n"
            )
            # A broken import errors during collection regardless of any marker
            # filter -- anchor with an UNFILTERED raw collect (a filter could
            # mask the error if the broken module carried no matching marker).
            self._anchor_raw_collect_exit(
                root, _PYTEST_COLLECTION_ERROR_EXIT, contract_filter=False
            )
        elif scope is CollectScope.GENUINELY_EMPTY:
            (root / "test_unmarked.py").write_text(
                "def test_no_contract_marker():\n    assert True\n"
            )
            # "Genuinely empty" means empty UNDER THE CONTRACT MARKER FILTER --
            # the one unmarked test exists, but `unit or integration or
            # acceptance` deselects it, so the contract scope is exit 5. Anchor
            # with the SAME filter the real probe applies (BLOCKER 2 caught the
            # unfiltered anchor mis-classifying this tree as exit 0).
            self._anchor_raw_collect_exit(
                root, _PYTEST_NO_TESTS_EXIT, contract_filter=True
            )
        else:  # REAL_NON_EMPTY
            (root / "test_real.py").write_text(
                "import pytest\n\n"
                "@pytest.mark.unit\ndef test_a():\n    assert True\n\n"
                "@pytest.mark.acceptance\ndef test_b():\n    assert True\n"
            )
        return root

    @staticmethod
    def _anchor_raw_collect_exit(
        tree: Path, expected_exit: int, *, contract_filter: bool
    ) -> None:
        """Assert a raw `pytest --collect-only` of ``tree`` yields ``expected_exit``.

        The fixture-anchor precondition (BLOCKER 2 / R-3): the synthetic tree's
        real pytest failure mode is verified MECHANICALLY before the guard
        under test ever sees it. A drift in pytest's exit-code semantics, or a
        mis-authored synthetic tree, fails HERE -- not silently downstream.

        ``contract_filter`` selects whether the anchor applies the contract
        marker filter (`unit or integration or acceptance`): the GENUINELY_EMPTY
        scope is "empty under the contract filter", so it must be anchored WITH
        the filter; a COLLECTION_ERROR errors regardless and is anchored without.
        """
        args = [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-p",
            "no:cacheprovider",
        ]
        if contract_filter:
            args += ["-m", "unit or integration or acceptance"]
        args.append(str(tree))
        raw = subprocess.run(args, cwd=tree, capture_output=True, text=True)
        assert raw.returncode == expected_exit, (
            f"synthetic tree at {tree} collected raw with exit {raw.returncode}, "
            f"expected {expected_exit} -- the fixture is not anchored to the "
            f"real failure mode (BLOCKER 2 / residuality R-3)"
        )

    # --- slice-02: the U0 marker contract ---------------------------------

    def classify_dispatch(
        self, phase: DispatchPhase, scope: DispatchScope
    ) -> DispatchRecognition:
        """Classify a feature-end / per-slice dispatch via the U0 domain.

        Drives `des.domain.des_marker_parser` -- the single chokepoint both U0
        sites delegate to -- through a synthesised dispatch prompt.
        """
        from des.domain.des_marker_parser import (
            DesMarkerParser,
            classify_atdd_pure_dispatch,
        )

        prompt = (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-MODE : atdd_pure -->\n"
            f"<!-- DES-PHASE : {phase.value} -->\n"
            f"<!-- DES-SLICE : {scope.value} -->\n"
        )
        markers = DesMarkerParser().parse(prompt)
        self.last_recognition = DispatchRecognition(
            classify_atdd_pure_dispatch(markers)
        )
        return self.last_recognition

"""Composition root for fix-whole-tree-contract-gate-runner-aware slice-01 (Mandate-12 SSOT).

Mandate-13 (Driving-Port-Only Boundary, Layer-3 subprocess e2e): the SUT is the
REAL contract gate, driven EXCLUSIVELY through its shipped CLI entry point
``python -m des.cli.run_contract_gate --repo <fixture>`` -- NO direct
``des.{domain,application,adapters}`` import. The only business logic in this
module is fixture staging + subprocess driving; the step bodies delegate here
and never inline logic (Mandate-12 criterion 3).

Hermeticity (``tests/meta/test_acceptance_hermeticity.py``): NO ``~/.claude`` /
``expanduser`` paths. Fixtures are synthetic single-lockfile tmp trees; the
subprocess resolves ``des.cli`` via ``PYTHONPATH=<repo>/src`` only.

active-RED note: at HEAD the whole-tree gate hardcodes pytest, so the gate's
output never carries the net-new ``WholeTreeRunnerResolved`` event -- every
``observable()``-based assertion RED-fails for the right reason (missing
functionality), and this composition imports ONLY stdlib + subprocess so the
suite COLLECTS cleanly (RED, not BROKEN).
"""

from __future__ import annotations

import os
from pathlib import Path

from .domain_types import DigestMode, GateOutcome, RepoRunnerOverride, TargetKind


# Repo root resolved from THIS file (Python + filesystem only, no git):
# .../tests/des/acceptance/<feature>/steps/composition.py -> 5 parents up.
_REPO_ROOT: Path = Path(__file__).resolve().parents[5]
_SRC_ROOT: Path = _REPO_ROOT / "src"

# A minimal Rust crate body: one #[test] so the resolved cargo run facet has a
# real test to (attempt to) run. The gate must resolve cargo from the SINGLE
# Cargo.toml lockfile (test_runner_port._REGISTRY) regardless of cargo presence.
_CARGO_TOML = """[package]
name = "whole_tree_runner_aware_fixture"
version = "0.0.0"
edition = "2021"
"""
_RUST_LIB = """pub fn answer() -> i32 { 42 }

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn answers_42() { assert_eq!(answer(), 42); }
}
"""

# A minimal Python project: one pyproject.toml (the single lockfile the gate
# resolves pytest from) + a trivial test so the pytest path has a tree to walk.
_PYPROJECT_TOML = """[project]
name = "whole-tree-runner-aware-py-fixture"
version = "0.0.0"
"""
_PY_TEST = "def test_truth():\n    assert True\n"

# A polyglot ROOT (D8): BOTH a Cargo.toml AND a package.json declaring vitest at
# the root -> resolve() matches 2 lockfiles, has no single-lockfile fast-path and
# no feature context -> degrades-LOUD INDETERMINATE (D2) UNLESS a repo-level
# .nwave/runner.json declares the runner (D8). package.json MUST carry the
# "vitest" substring (test_runner_port._REGISTRY requires_substring) to match.
_PACKAGE_JSON = """{
  "name": "whole-tree-runner-aware-polyglot-fixture",
  "devDependencies": { "vitest": "^1.0.0" }
}
"""


class WholeTreeGateComposition:
    """Drives the REAL whole-tree contract gate against a synthetic target repo."""

    def __init__(self) -> None:
        self._target: Path | None = None
        self._outcome: GateOutcome | None = None
        # slice-04: an UNRECOGNIZED target is driven through BOTH whole-tree
        # routers (the default RUN leg + a DIGEST leg) in one scenario, so the
        # fallback is pinned on BOTH (the two routers share the conflation).
        self._run_leg: GateOutcome | None = None
        self._digest_leg: GateOutcome | None = None

    # --- Given: stage a single-lockfile target ------------------------------

    def given_single_lockfile_target(self, kind: TargetKind, root: Path) -> None:
        """Write a minimal single-lockfile fixture repo of the given kind."""
        self._target = self._stage(kind, root)

    @staticmethod
    def _stage(kind: TargetKind, root: Path) -> Path:
        if kind is TargetKind.RUST:
            (root / "Cargo.toml").write_text(_CARGO_TOML, encoding="utf-8")
            (root / "src").mkdir(parents=True, exist_ok=True)
            (root / "src" / "lib.rs").write_text(_RUST_LIB, encoding="utf-8")
        elif kind is TargetKind.POLYGLOT:
            (root / "Cargo.toml").write_text(_CARGO_TOML, encoding="utf-8")
            (root / "package.json").write_text(_PACKAGE_JSON, encoding="utf-8")
            (root / "src").mkdir(parents=True, exist_ok=True)
            (root / "src" / "lib.rs").write_text(_RUST_LIB, encoding="utf-8")
        elif kind is TargetKind.UNRECOGNIZED:
            # A lockfile-less tree (slice-04 D9): a collectible Python test file
            # but ZERO recognized lockfiles -> resolve() -> UnrecognizedRunner.
            # The test file is the PRECONDITION (a tree exists to fall back ONTO),
            # never the expected output -- pre-#73 the pytest path collected it.
            (root / "test_truth.py").write_text(_PY_TEST, encoding="utf-8")
        else:
            (root / "pyproject.toml").write_text(_PYPROJECT_TOML, encoding="utf-8")
            (root / "test_truth.py").write_text(_PY_TEST, encoding="utf-8")
        return root

    # --- Given (slice-03): a polyglot root + an optional repo-level override -

    def given_polyglot_root(self, root: Path) -> None:
        """Stage a polyglot ROOT (Cargo.toml + package.json) the gate cannot
        disambiguate on its own (no feature context, no single-lockfile fast-path)."""
        self._target = self._stage(TargetKind.POLYGLOT, root)

    # --- Given (slice-04): a lockfile-less / unrecognized target -------------

    def given_unrecognized_target(self, root: Path) -> None:
        """Stage a tree with NO recognized lockfile (slice-04 D9).

        ``resolve(root, None)`` matches zero registry rows -> the 0-lockfile
        ``UnrecognizedRunner`` subtype. Both whole-tree routers MUST fall back to
        pytest (the home runner) rather than degrade to an ambiguous refusal."""
        self._target = self._stage(TargetKind.UNRECOGNIZED, root)

    def declare_repo_runner(self, override: RepoRunnerOverride) -> None:
        """Write the repo-level ``.nwave/runner.json`` whole-tree declaration (D8).

        The operator's whole-tree runner declaration, staged into the target root.
        Its bytes (valid key / unknown key / malformed) come from the typed
        ``RepoRunnerOverride`` -- the composition writes them verbatim; ``resolve``
        consults the file only when ``feature is None`` (whole-tree)."""
        assert self._target is not None, "given step must stage a root first"
        nwave_dir = self._target / ".nwave"
        nwave_dir.mkdir(parents=True, exist_ok=True)
        (nwave_dir / "runner.json").write_text(override.content, encoding="utf-8")

    # --- When: drive the shipped CLI entry via subprocess (Layer-3) ----------

    def run_whole_tree_gate(self) -> None:
        """Invoke `python -m des.cli.run_contract_gate --repo <target>` (no mode flags)."""
        assert self._target is not None, "given step must stage a target first"
        self._outcome = self._drive(self._target, ())

    # --- When (slice-02): drive a whole-tree DIGEST mode ---------------------

    def run_whole_tree_digest_mode(self, mode: DigestMode) -> None:
        """Invoke a whole-tree digest mode (`--committed-scope-digest` /
        `--verify-gate-scope` / `--collect-only --print-digest`) against the target.

        REUSES the slice-01 subprocess driving port + ``GateOutcome`` combined-
        channel event parse; only the mode argv tail differs. The digest leg must
        enumerate through the resolved runner's OWN enumerate facet (slice-02 D5),
        never the slice-01 D6 no-digest placeholder.
        """
        assert self._target is not None, "given step must stage a target first"
        self._outcome = self._drive(self._target, mode.argv)

    # --- When (slice-04): drive BOTH whole-tree routers over one target ------

    def run_whole_tree_run_and_digest_legs(self) -> None:
        """Drive the staged target through BOTH whole-tree routers (slice-04 D9).

        The default RUN leg (no mode flags -> ``_maybe_route_through_runner_whole_tree``)
        AND a DIGEST leg (``--collect-only --print-digest`` ->
        ``_maybe_route_digest_through_runner``) share the IDENTICAL
        unrecognized-vs-ambiguous conflation, so the fallback is pinned on BOTH
        within one scenario -- fixing only the digest leg would leave the run leg
        asymmetric and still-regressed (ADR-FLOW-011 D9)."""
        assert self._target is not None, "given step must stage a target first"
        self._run_leg = self._drive(self._target, ())
        self._digest_leg = self._drive(self._target, DigestMode.PRINT_DIGEST.argv)

    def run_leg(self) -> GateOutcome:
        assert self._run_leg is not None, "when step must drive both legs first"
        return self._run_leg

    def digest_leg(self) -> GateOutcome:
        assert self._digest_leg is not None, "when step must drive both legs first"
        return self._digest_leg

    @staticmethod
    def _drive(target: Path, mode_args: tuple[str, ...]) -> GateOutcome:
        # In-process driving port via the real `run_contract_gate.main` EDGE.
        # The --verify-gate-scope leg emits the WholeTreeRunnerResolved event to
        # the captured channels and THEN raises an uncaught CalledProcessError
        # from the gate's own `git log` on the (deliberately non-git) synthetic
        # target. `catch_all=True` reproduces the subprocess crash boundary: the
        # partial stdout/stderr captured BEFORE the raise are preserved and the
        # escaping exception is degraded to exit 1 (the code the Then-steps read).
        from des.cli import run_contract_gate
        from tests.common.in_process_cli import run_cli_in_process

        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(_SRC_ROOT), env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)
        exit_code, stdout, stderr = run_cli_in_process(
            ["--repo", str(target), *mode_args],
            cwd=str(_REPO_ROOT),
            main=run_contract_gate.main,
            env=env,
            catch_all=True,
        )
        return GateOutcome(exit_code=exit_code, stdout=stdout, stderr=stderr)

    # --- Then: the shipped observable ---------------------------------------

    def observable(self) -> GateOutcome:
        assert self._outcome is not None, "when step must run the gate first"
        return self._outcome

    def diag(self) -> str:
        """A reviewer-readable dump of the gate's actual output (RED diagnosis)."""
        return self._diag_one("gate", self._outcome)

    def diag_both_legs(self) -> str:
        """A reviewer-readable dump of BOTH whole-tree legs (slice-04 RED diagnosis)."""
        return self._diag_one("run-leg", self._run_leg) + self._diag_one(
            "digest-leg", self._digest_leg
        )

    @staticmethod
    def _diag_one(label: str, o: GateOutcome | None) -> str:
        if o is None:
            return f"\n--- {label}: (not yet run) ---\n"
        return (
            f"\n--- {label} exit={o.exit_code} ---\n"
            f"[events]   {o.events()}\n"
            f"[stdout]   {o.stdout.strip()[:1000]}\n"
            f"[stderr]   {o.stderr.strip()[:1000]}\n"
        )

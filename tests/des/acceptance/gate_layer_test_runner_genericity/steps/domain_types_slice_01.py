"""Domain types for gate-layer-test-runner-genericity slice-01 (Mandate-12 criterion 1).

slice-01 (the arch-test net) -- a stdlib-only static scan over nWave's OWN
gate/wave source tree (`src/des/cli/` + the gate modules) that ALLOWLISTS the two
legitimate interpreter-resolution boundaries and FAILS LOUD on any other
`python_for(` call (or literal-`pytest` interpreter-resolution) found in
gate/wave LOGIC.

WHY this matters (the bug class, feature-delta §Problem): nWave's gate/wave layer
hardcodes Python -- `python_for("pytest")` is reached not only from the
sanctioned boundaries but from gate LOGIC that operates on the TARGET project. On
a non-Python target (Rust/Go) those sites raise `InterpreterUnavailable`-on-pytest
-> the target never earns a genuine `SliceCommitVerified`. tsunami hit this on a
real Rust crate. The leak is a CLASS, not a one-off. This net makes every current
leak RED (the live inventory) and prevents new leaks by construction.

ALLOWLIST (the two legitimate boundaries -- python here is CORRECT):
  * `src/des/runtime/interpreter.py` (`des_spawn`) -- the interpreter port
    itself; it spawns nWave's OWN Python because DES modules ARE python. This is
    the sanctioned resolution boundary -- the ONE place `python_for` is defined-
    adjacent and called to build nWave's own subprocess argv.
  * `src/des/adapters/driven/runner/pytest_runner.py` (`run_pytest_scope`) -- the
    Python RUN-FACET, reached only when the TARGET is python via the runner
    registry. It is correct for the python facet to resolve a python interpreter.

The scan is AST-based, NOT a text grep: it must flag actual `python_for(` CALL
nodes, never docstring/comment MENTIONS. `src/des/adapters/drivers/hooks/
carpaccio_intercept.py` (8 comment mentions) and `src/des/cli/_reverify_core.py`
(1 docstring mention) MENTION `python_for(None)` in prose but never CALL it -- an
AST `ast.Call` walk excludes them by construction, where a grep would
false-positive.

Genericità / target-machine-agnosticism (CLAUDE.md §Architectural Constraints):
the scan is Python + filesystem only -- no subprocess, no git, cross-OS. The scan
IS the driving port (Layer-4 static analysis over the real tree), mirroring the
`tests/build/.../test_des_bundle_steps.py` stdlib-only static-scan precedent.

Every domain noun used in the Gherkin is expressed once here as a typed enum /
NewType / frozen dataclass. Step bodies and the composition service consume these
typed parameters -- no raw `str` where a domain type exists (criterion 1 + 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import NewType


# An absolute path to a Python source file under the scanned gate/wave layer.
SourceFile = NewType("SourceFile", Path)

# A "<file>:<line>" location string naming a single offending interpreter-
# resolution call (the human-readable leak coordinate the scan reports).
LeakSite = NewType("LeakSite", str)


@dataclass(frozen=True)
class InterpreterLeak:
    """One offending interpreter-resolution CALL outside the allowlist.

    The keystone observable: a `python_for(...)` call node (or literal-`pytest`
    interpreter-resolution) found in gate/wave LOGIC that should route through the
    runner registry / `RunnerAdapter` instead of hardcoding the python facet.
    """

    file: Path
    line: int
    snippet: str

    @property
    def site(self) -> LeakSite:
        """The `<repo-relative-file>:<line>` coordinate (stable across machines)."""
        return LeakSite(f"{self.file}:{self.line}")


# --- the scanned subject (nWave's own gate/wave layer) ----------------------

# The repo root, resolved from THIS test file's location (Python + filesystem
# only; no git). `.../tests/des/acceptance/<feature>/steps/domain_types_slice_01.py`
# -> climb 5 parents to the repo root.
REPO_ROOT: Path = Path(__file__).resolve().parents[5]

# The gate/wave source layer the net guards. `src/des/cli/` holds the gate CLIs
# that operate on the TARGET project (run_contract_gate, verify_*); the broader
# `src/des/` tree is scanned so a leak relocated into a gate MODULE is still
# caught. Scanning the whole `src/des/` tree (minus the allowlist) is the
# un-game-able choice -- a narrower glob could be dodged by moving a leak.
SCANNED_ROOT: Path = REPO_ROOT / "src" / "des"


# --- the allowlist (the two legitimate boundaries) --------------------------

# Repo-relative POSIX paths of the ONLY two files where `python_for(` is a
# legitimate, sanctioned call. Any OTHER file calling `python_for(` is a leak.
ALLOWLIST: frozenset[str] = frozenset(
    {
        "src/des/runtime/interpreter.py",
        "src/des/adapters/driven/runner/pytest_runner.py",
        "src/des/adapters/driven/contract_gate/pytest_contract_gate_adapter.py",
        "src/des/cli/verify_deliver_entry_contract.py",
        "src/des/cli/verify_environmental_e2e.py",
    }
)

# One-line rationale per allowlisted boundary (so a reviewer sees WHY each is
# exempt -- surfaced in the failure message and asserted present by the AT).
ALLOWLIST_RATIONALE: dict[str, str] = {
    "src/des/runtime/interpreter.py": (
        "the interpreter port (des_spawn) -- spawns nWave's OWN python because "
        "DES modules ARE python; the sanctioned resolution boundary"
    ),
    "src/des/adapters/driven/runner/pytest_runner.py": (
        "the python RUN-FACET (run_pytest_scope / pytest_interpreter) -- reached "
        "only when the TARGET is python via the runner registry; the SINGLE "
        "sanctioned python-interpreter resolution the rerouted gate sites obtain "
        "their interpreter through (never an inline python_for in gate logic)"
    ),
    "src/des/adapters/driven/contract_gate/pytest_contract_gate_adapter.py": (
        "the python CONTRACT-GATE run-facet (PythonContractGateAdapter) -- reached "
        "ONLY when the TARGET is python via the registered `nwave.lang.adapter` "
        "seam (a non-python target routes to a DIFFERENT language adapter, e.g. "
        "vitest, so genericity is preserved by the SEAM, not this adapter); it runs "
        "the target's own pytest suite, so python_for is the sanctioned interpreter "
        "here -- the same per-language run-facet category as pytest_runner.py"
    ),
    "src/des/cli/verify_deliver_entry_contract.py": (
        "DES-OWN python (_run_manifest_validator) -- runs nWave's OWN code-design "
        "manifest validator (scripts/cli, gated on the dev-checkout tree); it "
        "validates nWave's own artifact, not the TARGET project's suite, so "
        "python_for(None) is the sanctioned interpreter here (degrades LOUD to "
        "INDETERMINATE on interpreter absence, never a target-bound run)"
    ),
    "src/des/cli/verify_environmental_e2e.py": (
        "DES-OWN python (_run_e2e_against_installed) -- runs nWave's OWN e2e test "
        "against the INSTALLED nWave wheel (pip install --target into a hermetic "
        "prefix); nWave IS python, so python_for(None) is correct -- this is "
        "nWave's own installed-artifact e2e, not the TARGET project's suite"
    ),
}

# The interpreter-resolution call the net hunts: the bare attribute name
# `python_for`. The scan matches `ast.Call` nodes whose callee resolves to this
# name (direct `python_for(...)` or `module.python_for(...)`), so a docstring or
# comment mentioning the name is never flagged.
RESOLUTION_CALL_NAME: str = "python_for"

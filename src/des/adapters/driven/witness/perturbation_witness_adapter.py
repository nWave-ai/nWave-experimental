"""Isolated-copy differential perturbation witness adapter (slice-03).

WHY-NEW-FILE: src/des/adapters/driven/witness/perturbation_witness_adapter.py
  CLOSEST-EXISTING: src/des/adapters/driven/git/ (the git adapters) -- the only
    other adapter family that touches a source tree.
  EXTENSION-COST: the git adapters mutate-and-revert the LIVE working tree via
    version control; this adapter is the exact ANTITHESIS (ADR-001 Alt B
    rejected: git-based mutate-then-revert violates the git-free invariant + the
    no-git-stash mandate). It perturbs an ISOLATED tempfile copy and reverts by
    ``shutil.rmtree`` discard. Folding it into the git family would re-introduce
    the live-tree mutation the design exists to forbid.
  PARALLEL-RATIONALE: architecture.md sec.4 adjudicated
    this as a CREATE_NEW driven adapter realizing ``ClauseWitnessPort``; it holds
    ONLY a sandbox-root capability (effect-isolation principle 12) -- a distinct
    capability set + lifecycle from every existing adapter.

THE MECHANISM (ADR-001 §Decision, architecture.md sec.4):

  1. RESOLVE   clause -> production target (module::symbol) from the `# target:`
  2. SANDBOX   copy the repo's src/ subtree + the claimed AT module -> tmp root
  3. BASELINE  run the AT against the UNperturbed copy (must be GREEN)
  4. PERTURB   in the COPY only, AST-replace the target symbol's body with a
               WRONG-but-type-plausible RETURN (bool predicate -> invert; else a
               same-shape sentinel) -- NOT a bare raise (coverage-equivalent)
  5. PERTURBED run the SAME AT against the perturbed copy
  6. DISCRIMINATE  witnessed REQUIRES baseline GREEN AND perturbed FAILING AND
               the failure is a semantic AssertionError raised IN THE AT FILE
               (not an import/collection/setup/runtime error from the
               perturbation site). else: survived / red-for-wrong-reason /
               baseline-not-green
  7. DISCARD   shutil.rmtree the sandbox (revert-by-discard, never git)

Invariants held: git-free (no git invoked), working-tree-safe (the live tree is
NEVER addressed -- perturbation hits the copy only), language-agnostic (this is
the Python adapter; the gate logic is pure + language-neutral behind the port).

slice-03 scope: the three-state discrimination floor needed by DT-7 / DT-8 /
DT-12. The full red-for-wrong-reason reason-discrimination taxonomy (DT-6/DT-6b)
is slice-04; the earned-trust degrade path beyond the probe floor (DT-11) is
slice-05. This adapter ships the minimum that GREENs the slice-03 ATs:
witnessed / survived / target-unresolved, plus a not-witnessed verdict for the
red-for-wrong-reason pole (full taxonomy deferred).
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from des.ports.clause_witness_port import (
    ATRef,
    ProbeReport,
    WitnessReport,
)
from des.runtime.interpreter import des_spawn


@dataclass(frozen=True)
class _RunResult:
    """The structured outcome of one sandboxed AT run (internal value)."""

    passed: bool
    exc_type: str
    frame_file: str


# Verdict evidence vocabulary (ADR-001 §Decision). Mirrors the typed
# ``ClauseVerdict`` the ATs assert against; kept as module constants here so the
# adapter has no import edge into the test-side domain_types.
EVIDENCE_WITNESSED = "witnessed"
EVIDENCE_SURVIVED = "survived"
EVIDENCE_TARGET_UNRESOLVED = "target-unresolved"
EVIDENCE_BASELINE_NOT_GREEN = "baseline-not-green"
EVIDENCE_RED_FOR_WRONG_REASON = "red-for-wrong-reason"

# The witness subprocess time budget (fail-open: a timeout is NOT a witness).
_RUN_TIMEOUT_SECONDS = 30


class PerturbationWitnessAdapter:
    """Realize ``ClauseWitnessPort`` via isolated-copy differential perturbation.

    Constructed with a ``repo`` root (the project tree whose src/ holds the
    resolvable targets + whose tests hold the claimed ATs). The adapter copies
    into a tempfile sandbox under the system temp dir -- it NEVER mutates
    ``repo``. The live tree is outside its mutation capability by construction.
    """

    def __init__(self, repo: Path) -> None:
        self._repo = repo

    # ---- port: witness -------------------------------------------------

    def witness(self, clause_id: str, at_refs: list[ATRef]) -> WitnessReport:
        """Behavioral witness verdict for ``clause_id`` (ADR-001 §6 differential).

        A clause is ``witnessed`` iff ANY of its claimed ATs satisfies the
        three-condition differential. The first non-witnessed reason encountered
        (target-unresolved / survived / red-for-wrong-reason / baseline-not-
        green) is surfaced as the clause's evidence.
        """
        if not at_refs:
            return WitnessReport(
                clause_id=clause_id,
                witnessed=False,
                evidence=EVIDENCE_TARGET_UNRESOLVED,
            )
        last: WitnessReport | None = None
        for at_ref in at_refs:
            report = self._witness_one(clause_id, at_ref)
            if report.witnessed:
                return report
            last = report
        assert last is not None
        return last

    def _witness_one(self, clause_id: str, at_ref: ATRef) -> WitnessReport:
        """Run the isolated-copy differential for one claimed AT."""
        resolved = self._resolve_target(at_ref.target)
        if resolved is None:
            return WitnessReport(
                clause_id=clause_id,
                witnessed=False,
                evidence=EVIDENCE_TARGET_UNRESOLVED,
            )
        module_rel, symbol = resolved
        sandbox = Path(tempfile.mkdtemp(prefix="clause-witness-"))
        try:
            return self._run_differential(
                clause_id=clause_id,
                at_ref=at_ref,
                sandbox=sandbox,
                module_rel=module_rel,
                symbol=symbol,
            )
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)

    def _run_differential(
        self,
        clause_id: str,
        at_ref: ATRef,
        sandbox: Path,
        module_rel: Path,
        symbol: str,
    ) -> WitnessReport:
        """Sandbox + baseline + perturb + perturbed-run + discriminate."""
        sandbox_src = sandbox / "src"
        shutil.copytree(self._repo / "src", sandbox_src)
        at_copy = sandbox / "at_module.py"
        at_copy.write_text(
            (self._repo / at_ref.at_path).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        baseline = self._run_at(sandbox_src, at_copy)
        if not baseline.passed:
            return WitnessReport(
                clause_id=clause_id,
                witnessed=False,
                evidence=EVIDENCE_BASELINE_NOT_GREEN,
                sandbox_observed=True,
            )

        target_file = sandbox_src / module_rel
        perturbed = self._perturb_symbol_return(
            target_file.read_text(encoding="utf-8"), symbol
        )
        if perturbed is None:
            # Symbol vanished from the copy -- treat as unresolved, never a pass.
            return WitnessReport(
                clause_id=clause_id,
                witnessed=False,
                evidence=EVIDENCE_TARGET_UNRESOLVED,
                sandbox_observed=True,
            )
        target_file.write_text(perturbed, encoding="utf-8")

        result = self._run_at(sandbox_src, at_copy)
        return self._discriminate(clause_id, at_copy, result)

    def _discriminate(
        self, clause_id: str, at_copy: Path, result: _RunResult
    ) -> WitnessReport:
        """ADR-001 §6 verdict from the perturbed run's structured outcome."""
        if result.passed:
            # Perturbed run still GREEN: the AT does not assert the target's
            # return (vacuous / unrelated assert) -> survived.
            return WitnessReport(
                clause_id=clause_id,
                witnessed=False,
                evidence=EVIDENCE_SURVIVED,
                sandbox_observed=True,
            )
        if self._is_assertion_in_at_body(at_copy, result):
            return WitnessReport(
                clause_id=clause_id,
                witnessed=True,
                evidence=EVIDENCE_WITNESSED,
                sandbox_observed=True,
            )
        # RED for a non-assertion reason (import/setup/crash) -> NOT a witness.
        # slice-04 hardens the full taxonomy; slice-03 only needs not-witnessed.
        return WitnessReport(
            clause_id=clause_id,
            witnessed=False,
            evidence=f"{EVIDENCE_RED_FOR_WRONG_REASON}:{result.exc_type}",
            sandbox_observed=True,
        )

    # ---- port: probe ---------------------------------------------------

    def probe(self) -> ProbeReport:
        """Earned-trust self-test: classify four toy ATs (ADR-001 §Target Res).

        slice-03 floor: a genuine asserting AT -> witnessed; a pass-body vacuous
        AT -> survived. (The full four-pole probe -- import-coupled-vacuous +
        born-red -- is the slice-05 degrade-path ceiling; this is the minimum
        the gate needs to trust the adapter at composition.)
        """
        toy = Path(tempfile.mkdtemp(prefix="clause-witness-probe-"))
        try:
            src = toy / "src" / "probeapp"
            src.mkdir(parents=True)
            (toy / "src" / "probeapp" / "__init__.py").write_text("", "utf-8")
            (src / "widget.py").write_text(
                "def accept(value):\n    return value > 0\n", "utf-8"
            )
            genuine = toy / "tests" / "g" / "test_genuine.py"
            genuine.parent.mkdir(parents=True)
            genuine.write_text(
                "from probeapp.widget import accept\n\n"
                "def test_witness():\n    assert accept(1) is True\n",
                "utf-8",
            )
            vacuous = toy / "tests" / "g" / "test_vacuous.py"
            vacuous.write_text(
                "from probeapp.widget import accept\n\n"
                "def test_witness():\n    accept(1)\n",
                "utf-8",
            )
            adapter = PerturbationWitnessAdapter(toy)
            gen = adapter.witness(
                "PROBE-GENUINE",
                [ATRef("s", "probeapp.widget::accept", "tests/g/test_genuine.py")],
            )
            vac = adapter.witness(
                "PROBE-VACUOUS",
                [ATRef("s", "probeapp.widget::accept", "tests/g/test_vacuous.py")],
            )
            ok = gen.evidence == EVIDENCE_WITNESSED and vac.evidence == (
                EVIDENCE_SURVIVED
            )
            return ProbeReport(
                ok=ok,
                detail=f"genuine={gen.evidence} vacuous={vac.evidence}",
            )
        finally:
            shutil.rmtree(toy, ignore_errors=True)

    # ---- target resolution ---------------------------------------------

    def _resolve_target(self, target: str) -> tuple[Path, str] | None:
        """Resolve ``module::symbol`` to (relative source path, symbol).

        Returns None when the carrier is unparseable, the module file is absent
        under the repo's src/, or the symbol is not defined in that file.
        """
        if "::" not in target:
            return None
        module, _, symbol = target.partition("::")
        module = module.strip()
        symbol = symbol.strip()
        if not module or not symbol:
            return None
        module_rel = Path(*module.split(".")).with_suffix(".py")
        source_file = self._repo / "src" / module_rel
        if not source_file.is_file():
            return None
        if not self._defines_symbol(source_file.read_text(encoding="utf-8"), symbol):
            return None
        return module_rel, symbol

    @staticmethod
    def _defines_symbol(source: str, symbol: str) -> bool:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return False
        return any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == symbol
            for node in ast.walk(tree)
        )

    # ---- AST perturbation ----------------------------------------------

    def _perturb_symbol_return(self, source: str, symbol: str) -> str | None:
        """Replace ``symbol``'s body with a wrong-but-type-plausible RETURN.

        Returns the perturbed source, or None if the symbol is absent. A bare
        ``raise`` is explicitly NOT used (ADR-001 §E: coverage-equivalent); the
        replacement returns a wrong value so a genuine asserting AT FAILS its
        assertion while a vacuous AT stays GREEN.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None
        transformer = _WrongReturnTransformer(symbol)
        new_tree = transformer.visit(tree)
        if not transformer.replaced:
            return None
        ast.fix_missing_locations(new_tree)
        return ast.unparse(new_tree)

    # ---- subprocess test run -------------------------------------------

    def _run_at(self, sandbox_src: Path, at_copy: Path) -> _RunResult:
        """Run the copied AT module against ``sandbox_src`` in a subprocess.

        Self-contained pure-Python: the runner imports the AT module from the
        sandbox (its src/ on sys.path), calls every ``test_*`` function, and
        prints a structured JSON outcome. NOT the full hook / contract gate --
        a plain in-sandbox test invocation (the prompt's recursion guard).
        """
        runner = (
            "import sys, json, importlib.util, traceback\n"
            f"sys.path.insert(0, {str(sandbox_src)!r})\n"
            f"spec = importlib.util.spec_from_file_location('at_module', {str(at_copy)!r})\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "outcome = {'passed': True, 'exc_type': '', 'frame_file': ''}\n"
            "try:\n"
            "    spec.loader.exec_module(mod)\n"
            "    for name in dir(mod):\n"
            "        if name.startswith('test_'):\n"
            "            getattr(mod, name)()\n"
            "except BaseException as exc:\n"
            "    tb = exc.__traceback__\n"
            "    last = tb\n"
            "    while last is not None and last.tb_next is not None:\n"
            "        last = last.tb_next\n"
            "    outcome['passed'] = False\n"
            "    outcome['exc_type'] = type(exc).__name__\n"
            "    outcome['frame_file'] = last.tb_frame.f_code.co_filename if last else ''\n"
            "print(json.dumps(outcome))\n"
        )
        # Resolve the interpreter through the sanctioned boundary (F-21 guard):
        # the witness runner imports the AT module directly (no pytest needed),
        # so the no-capability resolution suffices.
        try:
            completed = des_spawn(
                None,
                script=runner,
                capture_output=True,
                text=True,
                timeout=_RUN_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return _RunResult(passed=False, exc_type="Timeout", frame_file="")
        for line in reversed(completed.stdout.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            return _RunResult(
                passed=bool(data.get("passed")),
                exc_type=str(data.get("exc_type", "")),
                frame_file=str(data.get("frame_file", "")),
            )
        # No structured line -> the runner itself failed to start: not a witness.
        return _RunResult(passed=False, exc_type="RunnerError", frame_file="")

    @staticmethod
    def _is_assertion_in_at_body(at_copy: Path, result: _RunResult) -> bool:
        """ADR-001 §6c: AssertionError raised in the AT file, not production.

        The right-reason RED is an ``AssertionError`` whose deepest frame is the
        AT module itself -- not an import / setup / crash in the perturbed
        production frame.
        """
        return (
            result.exc_type == "AssertionError" and Path(result.frame_file) == at_copy
        )


class _WrongReturnTransformer(ast.NodeTransformer):
    """Replace a named function's body with a wrong-but-type-plausible return."""

    def __init__(self, symbol: str) -> None:
        self._symbol = symbol
        self.replaced = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if node.name != self._symbol:
            return node
        self.replaced = True
        node.body = [ast.Return(value=self._wrong_value(node))]
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        if node.name != self._symbol:
            return node
        self.replaced = True
        node.body = [ast.Return(value=self._wrong_value(node))]
        return node

    @staticmethod
    def _wrong_value(node: ast.AST) -> ast.expr:
        """A type-plausible wrong return: invert a bool predicate, else None.

        A bool-annotated function returns ``False`` (the inversion that makes a
        ``is True`` assertion FAIL); anything else returns a same-shape sentinel
        (``None``) -- still wrong enough that a genuine value-asserting AT fails
        while a vacuous AT stays green (ADR-001 step 4 + 6c fallback).
        """
        returns = getattr(node, "returns", None)
        if isinstance(returns, ast.Name) and returns.id == "bool":
            return ast.Constant(value=False)
        return ast.Constant(value=None)

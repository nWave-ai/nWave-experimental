"""Whole-tree AST arch-test: ``des.domain.repo_path_resolver.resolve_repo_root``
is the SOLE authority for resolving the target repo root -- a hand-rolled
duplicate is refused, named file+line, WHAT/WHY/HOW.

Companion to ``test_repo_root_resolution_ssot.py`` (which pins the two
BEHAVIOURAL drift axes on the three known offenders). This module pins the
STRUCTURAL invariant: nothing outside the SSOT re-implements its contract.

DETECTION -- two independent, property-keyed rules (not a hand-picked file
list -- the scan walks the WHOLE ``src/`` + ``scripts/`` tree):

* **Rule A (env-var read).** Any ``os.environ.get("NWAVE_REPO_ROOT")`` /
  ``os.environ["NWAVE_REPO_ROOT"]`` / ``os.getenv("NWAVE_REPO_ROOT")`` read
  outside the SSOT module. Reading THIS specific env var only makes sense
  for one purpose -- resolving the repo root -- so any code that reads it
  directly has, by construction, opted into duplicating the SSOT's contract
  instead of calling it.
* **Rule B (repo-root-named parents-fallback).** Any function whose NAME
  self-describes as computing "the repo root" (matches ``repo_root``,
  case-insensitively) whose body ALSO contains a ``__file__``-relative
  ancestor walk (``Path(__file__)....parents[N]`` or 2+ chained ``.parent``
  accesses). Keying on the FUNCTION NAME (not the assigned variable's name,
  and not bare ``parents[N]`` presence) is deliberate: a function that
  merely locates a sibling asset next to itself (e.g.
  ``_default_omission_classes_path`` in
  ``coverage_map_verify_service.py`` / ``verify_coverage_map.py``, or the
  many ``_SHIPPED_..._DIR`` / ``_REPO_ROOT`` module-level asset anchors
  throughout ``src/des/cli/*.py``) is NOT named "repo root" and is
  correctly left alone -- it never claims to answer the SSOT's question.

SCOPE -- ``src/`` + ``scripts/`` only, excluding ``.venv``, ``node_modules``,
``dist``, ``lib``, ``__pycache__``, ``.git``, and the SSOT module itself.
``tests/`` is DELIBERATELY excluded (not merely skipped by directory-name
convention, but a considered exclusion): dozens of test step-composition
files define a LOCAL ``_repo_root()`` helper to locate THIS checkout for
fixture setup (e.g. ``tests/des/acceptance/*/steps/composition*.py``), and
``tests/scripts/cli/test_cohort_classifier.py`` directly reads/writes
``os.environ["NWAVE_REPO_ROOT"]`` as PART OF exercising the CLI under test --
neither is a production reimplementation of repo-root resolution; scanning
them would fire on test fixtures, not defects.

DELIBERATELY NOT FLAGGED (considered and excluded, not silently omitted):
``scripts/docgen.py:1243`` (``args.root or Path(__file__).resolve()
.parent.parent``), ``scripts/build_dist.py:98``, ``scripts/build_plugin.py:
1126``, and ``scripts/install/project_claude_section.py:42`` share the
same ``<arg> or Path(__file__)...parent(s)`` SYNTACTIC shape but do NOT
read ``NWAVE_REPO_ROOT`` and are not named "repo root" -- they resolve a
DIFFERENT concept (the dev-only build/install tooling's own checkout root,
which never runs installed and so is correct-by-construction to resolve via
``__file__``). Flagging them would force this bugfix's scope past its
diagnosed causal-id (three CLI modules duplicating ``resolve_repo_root``'s
env-var contract) into unrelated build tooling. Recorded here explicitly
per the "decide on the property, never the designation" gate discipline --
this is a reasoned exclusion, not an allowlist that quietly swallows a
violation; a follow-up widening this guard to the build-script family is a
separate, explicit decision.

RED now: ``scan_for_offenders(REPO_ROOT)`` names the three known offenders
(``src/des/cli/mode_locus_gate.py``, ``src/des/cli/mode_registry_
completeness.py``, ``scripts/cli/cohort_classifier.py``). GREEN once the
crafter routes all three through ``resolve_repo_root`` -- and this guard
stays armed against a FOURTH.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path


# tests/bugs/des/<this file> -> parents[3] = repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]

_SSOT_RELATIVE = Path("src") / "des" / "domain" / "repo_path_resolver.py"
_SCAN_ROOT_NAMES: tuple[str, ...] = ("src", "scripts")
_EXCLUDED_DIR_NAMES: frozenset[str] = frozenset(
    {".venv", "node_modules", "dist", "lib", "__pycache__", ".git"}
)
_TARGET_ENV_VAR = "NWAVE_REPO_ROOT"
_REPO_ROOT_NAME_RE = re.compile(r"repo_root", re.IGNORECASE)


@dataclass(frozen=True)
class Offender:
    """One hand-rolled duplicate of ``resolve_repo_root``'s contract."""

    relative_path: str
    line_number: int
    rule: str
    detail: str

    def render(self) -> str:
        return f"  {self.relative_path}:{self.line_number} [{self.rule}] {self.detail}"


# ---------------------------------------------------------------------------
# Rule A -- os.environ.get/getenv/subscript("NWAVE_REPO_ROOT") outside SSOT.
# ---------------------------------------------------------------------------


def _constant_str(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_os_dotted(func: ast.expr, attr: str) -> bool:
    """True when *func* is exactly ``os.<attr>`` (e.g. ``os.getenv``)."""
    return (
        isinstance(func, ast.Attribute)
        and func.attr == attr
        and isinstance(func.value, ast.Name)
        and func.value.id == "os"
    )


def _is_os_environ_get(func: ast.expr) -> bool:
    """True when *func* is exactly ``os.environ.get``."""
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "get"
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "environ"
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == "os"
    )


def _is_os_environ(node: ast.expr) -> bool:
    """True when *node* is exactly ``os.environ``."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def _env_read_offenders(tree: ast.Module, relative_path: str) -> list[Offender]:
    offenders: list[Offender] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if (
                _is_os_environ_get(node.func) or _is_os_dotted(node.func, "getenv")
            ) and (node.args and _constant_str(node.args[0]) == _TARGET_ENV_VAR):
                offenders.append(
                    Offender(
                        relative_path,
                        node.lineno,
                        "env-read",
                        f"reads os.environ NWAVE_REPO_ROOT directly (line {node.lineno})",
                    )
                )
        elif isinstance(node, ast.Subscript) and _is_os_environ(node.value):
            if _constant_str(node.slice) == _TARGET_ENV_VAR:
                offenders.append(
                    Offender(
                        relative_path,
                        node.lineno,
                        "env-read",
                        f"reads os.environ['NWAVE_REPO_ROOT'] directly (line {node.lineno})",
                    )
                )
    return offenders


# ---------------------------------------------------------------------------
# Rule B -- a "*repo_root*"-named function with a __file__-relative ancestor
# fallback (Path(__file__)....parents[N] or 2+ chained .parent) in its body.
# ---------------------------------------------------------------------------


def _mentions_dunder_file(expr: ast.AST) -> bool:
    return any(isinstance(n, ast.Name) and n.id == "__file__" for n in ast.walk(expr))


def _is_parents_subscript(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "parents"
    )


def _has_chained_parent_accesses(node: ast.AST, min_chain: int = 2) -> bool:
    """True when *node* contains an Attribute chain of >= *min_chain* ``.parent``."""
    for candidate in ast.walk(node):
        if not (isinstance(candidate, ast.Attribute) and candidate.attr == "parent"):
            continue
        depth = 1
        cursor = candidate.value
        while isinstance(cursor, ast.Attribute) and cursor.attr == "parent":
            depth += 1
            cursor = cursor.value
        if depth >= min_chain:
            return True
    return False


def _contains_file_relative_ancestor_walk(func: ast.FunctionDef) -> int | None:
    """Line of a ``__file__``-relative ancestor walk inside *func*'s body, if any."""
    for node in ast.walk(func):
        if not _mentions_dunder_file(node):
            continue
        if _is_parents_subscript(node) or _has_chained_parent_accesses(node):
            return getattr(node, "lineno", func.lineno)
    return None


def _repo_root_named_fallback_offenders(
    tree: ast.Module, relative_path: str
) -> list[Offender]:
    offenders: list[Offender] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if not _REPO_ROOT_NAME_RE.search(node.name):
            continue
        line = _contains_file_relative_ancestor_walk(node)
        if line is not None:
            offenders.append(
                Offender(
                    relative_path,
                    line,
                    "repo-root-named-fallback",
                    f"function {node.name!r} (def at line {node.lineno}) falls back to a "
                    f"__file__-relative ancestor walk at line {line}",
                )
            )
    return offenders


# ---------------------------------------------------------------------------
# Whole-tree scan.
# ---------------------------------------------------------------------------


def _scanned_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    ssot_absolute = (repo_root / _SSOT_RELATIVE).resolve()
    for root_name in _SCAN_ROOT_NAMES:
        scan_dir = repo_root / root_name
        if not scan_dir.is_dir():
            continue
        for path in sorted(scan_dir.rglob("*.py")):
            if path.resolve() == ssot_absolute:
                continue
            if any(
                part in _EXCLUDED_DIR_NAMES
                for part in path.relative_to(repo_root).parts
            ):
                continue
            files.append(path)
    return files


def scan_for_offenders(repo_root: Path) -> list[Offender]:
    """Every hand-rolled duplicate of ``resolve_repo_root``'s contract in *repo_root*.

    Pure read (Mandate 8): rewrites nothing. Stdlib-only (``ast`` + ``re``).
    """
    offenders: list[Offender] = []
    for path in _scanned_files(repo_root):
        relative_path = str(path.relative_to(repo_root))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            # A file that does not parse as Python cannot host a repo-root
            # reimplementation this scan can detect; skip rather than crash
            # the whole guard on an unrelated syntax problem elsewhere.
            continue
        offenders.extend(_env_read_offenders(tree, relative_path))
        offenders.extend(_repo_root_named_fallback_offenders(tree, relative_path))
    return offenders


def _render_offenders(offenders: list[Offender]) -> str:
    return "\n".join(
        o.render() for o in sorted(offenders, key=lambda o: o.relative_path)
    )


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------


def test_scanner_flags_env_read_and_repo_root_named_fallback_but_not_sibling_asset_lookup(
    tmp_path: Path,
) -> None:
    """Scanner self-check on a SYNTHETIC fixture (GDP-8 witness corollary):
    proves the two rules fire on the antipattern shapes and do NOT fire on a
    legitimate sibling-asset lookup, independent of the live repo's current
    state."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    violating = src_dir / "hand_rolled_gate.py"
    violating.write_text(
        "import os\n"
        "from pathlib import Path\n\n\n"
        "def _repo_root(root_arg):\n"
        "    if root_arg is not None:\n"
        "        return Path(root_arg)\n"
        "    override = os.environ.get('NWAVE_REPO_ROOT')\n"
        "    if override:\n"
        "        return Path(override)\n"
        "    return Path(__file__).resolve().parents[3]\n",
        encoding="utf-8",
    )

    legitimate = src_dir / "template_locator.py"
    legitimate.write_text(
        "from pathlib import Path\n\n\n"
        "def _template_path():\n"
        '    """Locate a sibling template shipped next to this module."""\n'
        "    return Path(__file__).parent / 'template.txt'\n",
        encoding="utf-8",
    )

    offenders = scan_for_offenders(tmp_path)
    offending_files = {o.relative_path for o in offenders}

    assert "src/hand_rolled_gate.py" in offending_files, (
        f"scanner must flag the synthetic hand-rolled duplicate; got {offending_files!r}"
    )
    assert "src/template_locator.py" not in offending_files, (
        "scanner must NOT flag a legitimate sibling-asset lookup (no NWAVE_REPO_ROOT "
        f"read, function not named repo_root); got {offending_files!r}"
    )
    rules = {o.rule for o in offenders if o.relative_path == "src/hand_rolled_gate.py"}
    assert rules == {"env-read", "repo-root-named-fallback"}, (
        f"both rules should independently fire on the synthetic offender; got {rules!r}"
    )


def test_whole_tree_has_zero_hand_rolled_repo_root_reimplementations() -> None:
    """The live-repo guard: nothing outside the SSOT duplicates
    ``resolve_repo_root``'s contract.

    RED now: names the three known offenders (mode_locus_gate.py,
    mode_registry_completeness.py, cohort_classifier.py). GREEN once the
    crafter routes all three through
    ``des.domain.repo_path_resolver.resolve_repo_root`` -- and stays armed
    against a fourth.
    """
    offenders = scan_for_offenders(REPO_ROOT)
    assert not offenders, (
        "WHAT: the following file(s) hand-roll a duplicate of "
        "des.domain.repo_path_resolver.resolve_repo_root's contract instead "
        "of calling it:\n"
        f"{_render_offenders(offenders)}\n"
        "WHY: a duplicate drifts -- the known drift is a __file__-relative "
        "parents[N] fallback (broken-by-design once installed, since it "
        "resolves outside the SSOT's flag/env/cwd chain) and/or an "
        "`is not None` guard that fails to fall through on an empty-string "
        "override. HOW: import resolve_repo_root from "
        "des.domain.repo_path_resolver and delegate to it instead of "
        "re-deriving the root."
    )


if __name__ == "__main__":
    import sys

    import pytest

    raise SystemExit(pytest.main([__file__, "-v", *sys.argv[1:]]))

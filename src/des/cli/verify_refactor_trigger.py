"""``des verify-refactor-trigger`` -- the P1.3 signal-driven refactor trigger.

Expectation (evolution-plan P1.3): an unconditional refactor pass never runs
again. Detector findings on the touched set are the trigger AND the
expectations: zero findings -> no refactor pass runs; findings -> the list IS
the crafter's refactor brief, and impact is the measured findings-delta on
re-run. The detector set explicitly includes the SSOT-violation classes --
a crafter that writes alternative/duplicate code trips this gate at slice
commit with the finding as its brief (Ale 2026-07-03: "il crafter spesso crea
codice alternativo e viola SSOT").

Arm chain (the code-analysis PORT; every verdict declares its ``"arm"``):

  1. tsunami arm -- a ``tsunami`` executable is probed on PATH. When present
     the verdict says so HONESTLY, but the adapter is not yet wired
     (follow-up): findings still come from the AST arm, never faked.
  2. AST fallback arm (pure Python, stdlib ``ast``; SHIPPED with the runtime
     per the target-machine-independence mandate) -- per touched ``.py`` file
     and cross-file over the touched set:
       duplicated_code            -- normalized N-line blocks appearing >1x
       duplicated_constant        -- same str/number constant defined in
                                     more than one touched module
       parallel_enum_definitions  -- two Enum classes sharing >= threshold
                                     of member names (the seat-status class)
       long_function              -- function body longer than threshold
       unused_import              -- imported name never referenced
  3. no arm applicable (non-Python files, tsunami absent/unwired) ->
     exit 2 ``RefactorTriggerIndeterminate`` LOUD -- NEVER a silent
     zero-findings that actually means nobody-looked.

Verdicts (every failure states WHAT failed, WHY, and HOW to fix):

    0  RefactorTriggerClean         -- assessed, zero findings; no pass runs
    1  RefactorTriggerFired         -- findings list = the refactor brief
    2  RefactorTriggerIndeterminate -- could not assess; NEVER a pass

Python + stdlib only. ``git`` is consulted only for ``--diff-base`` and its
absence degrades LOUD to INDETERMINATE, never a crash or a silent pass.
"""

from __future__ import annotations

import argparse
import ast
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from des.cli._emit_json import emit_json_line as _emit
from des.cli._repo_root_arg import add_repo_root_argument


_EXIT_CLEAN = 0
_EXIT_FIRED = 1
_EXIT_INDETERMINATE = 2

_DEFAULT_FUNC_LINES = 60
_DEFAULT_DUP_BLOCK_LINES = 5
_DEFAULT_ENUM_OVERLAP = 0.8

_ENUM_BASE_NAMES = frozenset({"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag"})
_TRIVIAL_INTS = frozenset({-1, 0, 1})
_TRIVIAL_FLOATS = frozenset({-1.0, 0.0, 1.0})
_MIN_ENUM_MEMBERS = 2


@dataclass(frozen=True)
class _Finding:
    """One detector finding: a row of the crafter's refactor brief."""

    finding_class: str
    file: str
    line: int
    brief: str

    def payload(self) -> dict[str, object]:
        return {
            "class": self.finding_class,
            "file": self.file,
            "line": self.line,
            "brief": self.brief,
        }


@dataclass(frozen=True)
class _PyModule:
    """One parsed touched Python module."""

    path: Path
    source: str
    tree: ast.Module


@dataclass(frozen=True)
class _Thresholds:
    """The --threshold-* knobs, resolved."""

    func_lines: int
    dup_block_lines: int
    enum_overlap: float


@dataclass(frozen=True)
class _ConstantDef:
    """One module/class-level constant definition site."""

    key: tuple[str, str]
    name: str
    file: str
    line: int
    display: str


@dataclass(frozen=True)
class _EnumDef:
    """One Enum class definition site with its member names."""

    name: str
    file: str
    line: int
    members: frozenset[str]


def _indeterminate(arm: str, what: str, why: str, how: str) -> int:
    _emit(
        {
            "event": "RefactorTriggerIndeterminate",
            "arm": arm,
            "what": what,
            "why": why,
            "how": how,
        }
    )
    print(f"⚠ INDETERMINATE — {what}. {why} Fix: {how}")
    return _EXIT_INDETERMINATE


def _probe_tsunami() -> str:
    """Honest tier-1 probe: is a ``tsunami`` executable on PATH?"""
    if shutil.which("tsunami") is not None:
        return "tsunami present, adapter not wired: follow-up"
    return "tsunami absent"


# --- AST fallback arm: the five detectors ----------------------------------


def _long_functions(mod: _PyModule, max_lines: int) -> list[_Finding]:
    findings: list[_Finding] = []
    for node in ast.walk(mod.tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        length = (node.end_lineno or node.lineno) - node.lineno + 1
        if length <= max_lines:
            continue
        findings.append(
            _Finding(
                finding_class="long_function",
                file=str(mod.path),
                line=node.lineno,
                brief=(
                    f"function '{node.name}' is {length} lines "
                    f"(> {max_lines}): extract steps into named helpers"
                ),
            )
        )
    return findings


def _unused_imports(mod: _PyModule) -> list[_Finding]:
    imported: list[tuple[str, int]] = []
    for node in ast.walk(mod.tree):
        if isinstance(node, ast.Import):
            imported.extend(
                (alias.asname or alias.name.split(".")[0], node.lineno)
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
            imported.extend(
                (alias.asname or alias.name, node.lineno)
                for alias in node.names
                if alias.name != "*"
            )
    used = {n.id for n in ast.walk(mod.tree) if isinstance(n, ast.Name)}
    used |= {n.attr for n in ast.walk(mod.tree) if isinstance(n, ast.Attribute)}
    return [
        _Finding(
            finding_class="unused_import",
            file=str(mod.path),
            line=line,
            brief=f"import '{name}' is never referenced: remove it",
        )
        for name, line in imported
        if name not in used
    ]


def _normalized_lines(source: str) -> list[tuple[int, str]]:
    """(original_lineno, stripped_text) for non-blank, non-comment lines."""
    kept: list[tuple[int, str]] = []
    for lineno, raw in enumerate(source.splitlines(), start=1):
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        kept.append((lineno, text))
    return kept


def _duplicate_blocks(mods: list[_PyModule], block_lines: int) -> list[_Finding]:
    """Normalized N-line blocks appearing >1x across the touched set.

    Shift-adjacent continuation windows of the same duplicate are collapsed
    so an M-line duplication reports once, at its start.
    """
    occurrences: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for mod in mods:
        norm = _normalized_lines(mod.source)
        for i in range(len(norm) - block_lines + 1):
            window = norm[i : i + block_lines]
            key = "\n".join(text for _, text in window)
            occurrences[key].append((str(mod.path), window[0][0]))
    groups = sorted(
        (locs for locs in occurrences.values() if len(locs) > 1),
        key=lambda locs: locs[0],
    )
    findings: list[_Finding] = []
    seen: set[frozenset[tuple[str, int]]] = set()
    for locs in groups:
        shifted_up = frozenset((path, line - 1) for path, line in locs)
        seen.add(frozenset(locs))
        if shifted_up in seen:
            continue
        sites = ", ".join(f"{path}:{line}" for path, line in locs)
        brief = (
            f"{block_lines}-line block duplicated at {sites}: "
            "extract ONE shared implementation (SSOT)"
        )
        findings.extend(
            _Finding(finding_class="duplicated_code", file=path, line=line, brief=brief)
            for path, line in locs
        )
    return findings


def _is_enum_class(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Attribute) and base.attr in _ENUM_BASE_NAMES:
            return True
        if isinstance(base, ast.Name) and base.id in _ENUM_BASE_NAMES:
            return True
    return False


def _is_significant_constant(value: object) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int):
        return value not in _TRIVIAL_INTS
    if isinstance(value, float):
        return value not in _TRIVIAL_FLOATS
    if isinstance(value, str):
        return len(value) > 1
    return False


def _constant_assignment(node: ast.stmt) -> tuple[str, ast.Constant] | None:
    if (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
    ):
        return node.targets[0].id, node.value
    if (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and isinstance(node.value, ast.Constant)
    ):
        return node.target.id, node.value
    return None


def _constant_defs(mod: _PyModule) -> list[_ConstantDef]:
    """Module-level and non-enum class-level str/number constant definitions.

    Enum class bodies are excluded: parallel enums are owned by the
    ``parallel_enum_definitions`` detector, not double-reported here.
    """
    defs: list[_ConstantDef] = []

    def _collect(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                if not _is_enum_class(node):
                    _collect(node.body)
                continue
            assignment = _constant_assignment(node)
            if assignment is None:
                continue
            name, constant = assignment
            if not _is_significant_constant(constant.value):
                continue
            defs.append(
                _ConstantDef(
                    key=(type(constant.value).__name__, repr(constant.value)),
                    name=name,
                    file=str(mod.path),
                    line=node.lineno,
                    display=repr(constant.value),
                )
            )

    _collect(mod.tree.body)
    return defs


def _duplicated_constants(mods: list[_PyModule]) -> list[_Finding]:
    by_key: dict[tuple[str, str], list[_ConstantDef]] = defaultdict(list)
    for mod in mods:
        for definition in _constant_defs(mod):
            by_key[definition.key].append(definition)
    findings: list[_Finding] = []
    for defs in by_key.values():
        files = {d.file for d in defs}
        if len(files) < 2:
            continue
        sites = ", ".join(f"{d.file}:{d.line} ({d.name})" for d in defs)
        brief = (
            f"constant {defs[0].display} defined in {len(files)} touched "
            f"modules ({sites}): define it ONCE in a shared home (SSOT)"
        )
        findings.extend(
            _Finding(
                finding_class="duplicated_constant",
                file=d.file,
                line=d.line,
                brief=brief,
            )
            for d in defs
        )
    return findings


def _enum_defs(mod: _PyModule) -> list[_EnumDef]:
    defs: list[_EnumDef] = []
    for node in ast.walk(mod.tree):
        if not isinstance(node, ast.ClassDef) or not _is_enum_class(node):
            continue
        members: set[str] = set()
        for stmt in node.body:
            if (
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
            ):
                members.add(stmt.targets[0].id)
            elif (
                isinstance(stmt, ast.AnnAssign)
                and isinstance(stmt.target, ast.Name)
                and stmt.value is not None
            ):
                members.add(stmt.target.id)
        defs.append(
            _EnumDef(
                name=node.name,
                file=str(mod.path),
                line=node.lineno,
                members=frozenset(m for m in members if not m.startswith("_")),
            )
        )
    return defs


def _parallel_enums(mods: list[_PyModule], overlap: float) -> list[_Finding]:
    enums = [e for mod in mods for e in _enum_defs(mod)]
    findings: list[_Finding] = []
    for i, first in enumerate(enums):
        for second in enums[i + 1 :]:
            finding_pair = _enum_pair_findings(first, second, overlap)
            findings.extend(finding_pair)
    return findings


def _enum_pair_findings(
    first: _EnumDef, second: _EnumDef, overlap: float
) -> list[_Finding]:
    if len(first.members) < _MIN_ENUM_MEMBERS:
        return []
    if len(second.members) < _MIN_ENUM_MEMBERS:
        return []
    shared = first.members & second.members
    larger = max(len(first.members), len(second.members))
    ratio = len(shared) / larger
    if ratio < overlap:
        return []
    brief = (
        f"enum '{first.name}' at {first.file}:{first.line} and enum "
        f"'{second.name}' at {second.file}:{second.line} share "
        f"{len(shared)}/{larger} members ({ratio:.0%}): keep ONE enum (SSOT)"
    )
    return [
        _Finding(
            finding_class="parallel_enum_definitions",
            file=e.file,
            line=e.line,
            brief=brief,
        )
        for e in (first, second)
    ]


def _analyze(mods: list[_PyModule], thresholds: _Thresholds) -> list[_Finding]:
    findings: list[_Finding] = []
    findings.extend(_duplicate_blocks(mods, thresholds.dup_block_lines))
    findings.extend(_duplicated_constants(mods))
    findings.extend(_parallel_enums(mods, thresholds.enum_overlap))
    for mod in mods:
        findings.extend(_long_functions(mod, thresholds.func_lines))
        findings.extend(_unused_imports(mod))
    findings.sort(key=lambda f: (f.file, f.line, f.finding_class))
    return findings


# --- input resolution -------------------------------------------------------


def _files_from_diff(repo: Path, base: str, arm: str) -> list[str] | int:
    cmd = ["git", "-C", str(repo), "diff", "--name-only", f"{base}...HEAD"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        return _indeterminate(
            arm,
            what="git is not available on this machine",
            why="--diff-base resolves the touched set via `git diff --name-only`.",
            how="install git, or pass the touched files explicitly via --files.",
        )
    except subprocess.TimeoutExpired:
        return _indeterminate(
            arm,
            what="`git diff` timed out after 60s",
            why="the repository did not answer.",
            how="check repository health, or pass the files via --files.",
        )
    if proc.returncode != 0:
        return _indeterminate(
            arm,
            what=f"`git diff --name-only {base}...HEAD` failed "
            f"(exit {proc.returncode})",
            why=proc.stderr.strip()[-2000:],
            how="check that the ref exists in this repo, or use --files.",
        )
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _resolve_selection(
    args: argparse.Namespace, repo: Path, arm: str
) -> list[Path] | int:
    if args.files and args.diff_base is not None:
        return _indeterminate(
            arm,
            what="--files and --diff-base are mutually exclusive",
            why="the touched set must have exactly one declared source.",
            how="pass either --files or --diff-base, not both.",
        )
    if not args.files and args.diff_base is None:
        return _indeterminate(
            arm,
            what="no input given",
            why="neither --files nor --diff-base was provided.",
            how=(
                "pass the touched files via --files <path> (repeatable), "
                "or a base ref via --diff-base <ref>."
            ),
        )
    if args.files:
        paths = [(repo / f).resolve() for f in args.files]
        missing = [p for p in paths if not p.is_file()]
        if missing:
            return _indeterminate(
                arm,
                what="missing file(s): " + ", ".join(str(m) for m in missing),
                why="the gate cannot assess what it cannot find.",
                how="pass existing files via --files.",
            )
        return paths
    names_or_exit = _files_from_diff(repo, args.diff_base, arm)
    if isinstance(names_or_exit, int):
        return names_or_exit
    resolved = ((repo / name).resolve() for name in names_or_exit)
    return [p for p in resolved if p.is_file()]


def _normalized_exts(raw: list[str] | None) -> frozenset[str]:
    exts = raw if raw else [".py"]
    return frozenset(e if e.startswith(".") else f".{e}" for e in exts)


# --- verdict emitters --------------------------------------------------------


def _fired(
    arm: str,
    findings: list[_Finding],
    analyzed: list[Path],
    unassessed: list[Path],
) -> int:
    _emit(
        {
            "event": "RefactorTriggerFired",
            "arm": arm,
            "what": f"{len(findings)} refactor finding(s) on the touched set",
            "why": (
                "detector findings above thresholds are the trigger AND the "
                "expectations for the refactor pass."
            ),
            "how": (
                "this findings list IS the refactor brief: fix each site "
                "(extract the shared home for the SSOT classes), then re-run "
                "this gate to measure the findings-delta."
            ),
            "findings": [f.payload() for f in findings],
            "files_analyzed": [str(p) for p in analyzed],
            "unassessed": [str(p) for p in unassessed],
        }
    )
    print(f"✗ FIRED — {len(findings)} refactor finding(s) [arm: {arm}]")
    for finding in findings:
        print(
            f"  {finding.file}:{finding.line} [{finding.finding_class}] {finding.brief}"
        )
    return _EXIT_FIRED


def _clean(arm: str, analyzed: list[Path]) -> int:
    _emit(
        {
            "event": "RefactorTriggerClean",
            "arm": arm,
            "findings": [],
            "files_analyzed": [str(p) for p in analyzed],
        }
    )
    print(f"✓ CLEAN — no refactor trigger on {len(analyzed)} file(s) [arm: {arm}]")
    return _EXIT_CLEAN


def _parse_modules(paths: list[Path], arm: str) -> list[_PyModule] | int:
    mods: list[_PyModule] = []
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            return _indeterminate(
                arm,
                what=f"cannot parse {path}",
                why=str(exc),
                how="fix the file (it must be valid Python) and re-run.",
            )
        mods.append(_PyModule(path=path, source=source, tree=tree))
    return mods


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="des verify-refactor-trigger",
        description=(
            "Signal-driven refactor trigger (evolution P1.3): detector "
            "findings on the touched set are the trigger AND the refactor "
            "brief; zero findings -> no refactor pass runs; no applicable "
            "arm -> INDETERMINATE, never a silent zero-findings."
        ),
        epilog=(
            "Detector classes (AST arm): duplicated_code, "
            "duplicated_constant, parallel_enum_definitions, long_function, "
            "unused_import. Arm chain: tsunami (probed; adapter follow-up) "
            "-> pure-Python AST fallback -> INDETERMINATE."
        ),
    )
    add_repo_root_argument(
        parser, "--repo", default=".", help="Path to the repository root."
    )
    parser.add_argument(
        "--files",
        action="append",
        default=[],
        help="Touched file to assess (relative to --repo); repeatable.",
    )
    parser.add_argument(
        "--diff-base",
        default=None,
        help="Git ref; touched set = `git diff --name-only <ref>...HEAD`.",
    )
    parser.add_argument(
        "--ext",
        action="append",
        default=None,
        help="File extension in scope (default: .py); repeatable.",
    )
    parser.add_argument(
        "--threshold-func-lines",
        type=int,
        default=_DEFAULT_FUNC_LINES,
        help=f"long_function fires above this length (default {_DEFAULT_FUNC_LINES}).",
    )
    parser.add_argument(
        "--threshold-dup-block-lines",
        type=int,
        default=_DEFAULT_DUP_BLOCK_LINES,
        help=(
            "duplicated_code window size in normalized lines "
            f"(default {_DEFAULT_DUP_BLOCK_LINES})."
        ),
    )
    parser.add_argument(
        "--threshold-enum-overlap",
        type=float,
        default=_DEFAULT_ENUM_OVERLAP,
        help=(
            "parallel_enum_definitions fires at this member-name overlap "
            f"ratio (default {_DEFAULT_ENUM_OVERLAP})."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo = Path(args.repo).resolve()
    tsunami_note = _probe_tsunami()
    no_arm = f"none ({tsunami_note})"

    selection_or_exit = _resolve_selection(args, repo, no_arm)
    if isinstance(selection_or_exit, int):
        return selection_or_exit
    selected = selection_or_exit

    ast_arm = f"ast-fallback ({tsunami_note})"
    if not selected:
        return _clean(ast_arm, [])

    exts = _normalized_exts(args.ext)
    in_scope = [p for p in selected if p.suffix in exts]
    py_files = [p for p in in_scope if p.suffix == ".py"]
    unassessed = [p for p in in_scope if p.suffix != ".py"]

    if not py_files:
        skipped = ", ".join(str(p) for p in selected)
        return _indeterminate(
            no_arm,
            what=f"no arm can assess the selected set ({len(selected)} file(s))",
            why=(
                f"{tsunami_note}; the shipped AST fallback arm is "
                f"Python-only; nothing was analyzed ({skipped}) — a "
                "zero-findings verdict here would mean nobody-looked."
            ),
            how=(
                "install+wire tsunami for non-Python arms, or point "
                "--files/--ext at Python sources."
            ),
        )

    thresholds = _Thresholds(
        func_lines=args.threshold_func_lines,
        dup_block_lines=args.threshold_dup_block_lines,
        enum_overlap=args.threshold_enum_overlap,
    )
    mods_or_exit = _parse_modules(py_files, ast_arm)
    if isinstance(mods_or_exit, int):
        return mods_or_exit
    findings = _analyze(mods_or_exit, thresholds)

    if findings:
        return _fired(ast_arm, findings, py_files, unassessed)
    if unassessed:
        skipped = ", ".join(str(p) for p in unassessed)
        return _indeterminate(
            ast_arm,
            what=(f"{len(unassessed)} in-scope file(s) had no arm to assess them"),
            why=(
                f"zero findings on the Python subset, but {skipped} was "
                "never analyzed — reporting Clean would be a silent "
                "nobody-looked."
            ),
            how=(
                "install+wire tsunami for non-Python arms, or narrow --ext "
                "to the extensions an arm covers."
            ),
        )
    return _clean(ast_arm, py_files)


if __name__ == "__main__":
    sys.exit(main())

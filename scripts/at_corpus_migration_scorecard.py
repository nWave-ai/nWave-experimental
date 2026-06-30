#!/usr/bin/env python3
"""GOAL CONTRACT for slow-AT consolidation PHASE 2 (F-TEST-CORPUS-MIGRATION-IN-PROCESS).

THIS SCRIPT *IS* THE MEASUREMENT of "how much of the existing slow AT corpus has
been migrated off subprocess-fork to in-process". Same committed code + same repo
state -> same number (deterministic, stdlib only, no git, no external tools).

THE RULE (nw-distill-port-treatment-policy): subprocess-e2e is reserved for
``@walking_skeleton`` -- the ONE scenario per command that proves the installed
artifact is wired end-to-end. EVERY OTHER acceptance test must drive its entry
point IN-PROCESS (real ``cli main(argv)`` / application-service + a fake
``OutputPort``), no interpreter fork. A non-``@walking_skeleton`` AT that forks an
interpreter is the migration target.

UNIT = a non-WS MIGRABLE interpreter-fork SPAWN-SITE in an acceptance test: a
``subprocess`` spawner whose first arg-list element is ``sys.executable`` or a
Python interpreter literal (``python``/``python3``), or an ``os.exec*`` call, in a
file/scenario that carries NO ``@walking_skeleton`` marker. An external-tool
subprocess (first arg ``git``/``sh``/a non-Python binary) is NOT a migration
target -- it is EXEMPT (legitimately ``@requires_external``, like the lone
``@walking_skeleton`` survivor). Classification is precise AST first-arg
inspection (semantic parity with the production gate
``des.cli.axis_b_levers._is_interpreter_spawn``), git-free and target-machine
agnostic -- NOT a text regex (the old regex over-counted external-tool forks AND
double-counted the ``subprocess.run`` + ``sys.executable`` attribute pair on one
call). DONE for the phase <=> ZERO non-WS migrable interpreter-forks remain.

TWO MODES. The DEFAULT (``_scan``) is a FILE-level gradient tracker: a file
mixing a legit WS fork with non-WS forks is counted "mixed" and reported
separately -- its non-WS forks still need migrating, but the file is not a pure
target. ``--per-site`` (``_scan_per_site``) is the un-gameable DONE contract: it
DELEGATES to the production readiness gate's precise per-scenario classifier
(``des.cli.axis_b_levers.scan_spawn_sites``), so a fork is KEEP iff its ENCLOSING
scenario carries ``@walking_skeleton`` (incl. pytest-bdd scenario-tag binding) and
the scorecard count AGREES with the gate BY CONSTRUCTION (one detector, no drift).
A fork in a file that merely MENTIONS "walking skeleton" in prose is MIGRATE.

Usage:
    python scripts/at_corpus_migration_scorecard.py
    python scripts/at_corpus_migration_scorecard.py --json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import cast


REPO = Path(__file__).resolve().parents[1]
TESTS = REPO / "tests"

_WS = re.compile(r"walking.?skeleton", re.IGNORECASE)

# Precise interpreter-fork classifier (semantic parity with the production gate
# ``des.cli.axis_b_levers._is_interpreter_spawn`` — ONE detector definition, two
# homes). A spawn-site is a MIGRABLE interpreter-fork iff it is a ``subprocess``
# spawner whose first arg-list element is ``sys.executable`` or a bare Python
# interpreter literal (``python`` / ``python3`` / ``python3.12``), OR an
# ``os.exec*`` call. An external-tool subprocess (first arg ``git`` / ``sh`` /
# ``bash`` / any non-Python binary) is NOT migrable and is EXEMPT — it is
# legitimately ``@requires_external`` (like the ``@walking_skeleton`` survivor).
# Pure AST first-arg inspection: git-free, target-machine-agnostic, and counts
# ONE CALL node per fork (the old regex double-counted the ``subprocess.run`` +
# ``sys.executable`` attribute pair on a single call, and matched external-tool
# forks — together the source of the inflated 311/350 over-count).
_INTERPRETER_LITERAL = re.compile(r"^python(3(\.\d+)?)?$")
_SUBPROCESS_SPAWNERS = frozenset({"run", "Popen", "call", "check_call", "check_output"})
_OS_EXEC_FUNCS = frozenset(
    {
        "system",
        "popen",
        "execl",
        "execle",
        "execlp",
        "execlpe",
        "execv",
        "execve",
        "execvp",
        "execvpe",
    }
)


def _acceptance_test_files() -> list[Path]:
    if not TESTS.exists():
        return []
    return sorted(
        p
        for p in TESTS.rglob("*.py")
        if "/acceptance/" in p.as_posix()
        and p.name.startswith(("test_", "composition"))
    )


def _scan() -> dict[str, object]:
    pure_files: list[str] = []  # fork + NO walking_skeleton marker = full target
    mixed_files: list[str] = []  # fork + a walking_skeleton marker = partial
    pure_spawn = 0
    mixed_spawn = 0
    by_dir: dict[str, int] = {}
    for p in _acceptance_test_files():
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        forks = sum(1 for node in ast.walk(tree) if _is_spawn_call(node))
        if forks == 0:
            continue
        rel = p.relative_to(REPO).as_posix()
        top = "/".join(rel.split("/")[:3])
        if _WS.search(text):
            mixed_files.append(rel)
            mixed_spawn += forks
        else:
            pure_files.append(rel)
            pure_spawn += forks
            by_dir[top] = by_dir.get(top, 0) + forks
    return {
        "pure_files": pure_files,
        "mixed_files": mixed_files,
        "pure_spawn": pure_spawn,
        "mixed_spawn": mixed_spawn,
        "by_dir": by_dir,
    }


def _render_text(s: dict[str, object]) -> str:
    pure_files = cast("list[str]", s["pure_files"])
    mixed_files = cast("list[str]", s["mixed_files"])
    pure_spawn = cast("int", s["pure_spawn"])
    mixed_spawn = cast("int", s["mixed_spawn"])
    by_dir = dict(
        sorted(cast("dict[str, int]", s["by_dir"]).items(), key=lambda kv: -kv[1])
    )
    done = pure_spawn == 0 and mixed_spawn == 0
    lines = [
        "=" * 80,
        "  SLOW-AT PHASE 2 — corpus migration to in-process (subprocess-e2e = @walking_skeleton ONLY)",
        "-" * 80,
        f"  PURE non-WS files (full migration target) : {len(pure_files):>4}  "
        f"({pure_spawn} spawn-sites)",
        f"  MIXED files (WS + non-WS forks, partial)   : {len(mixed_files):>4}  "
        f"({mixed_spawn} spawn-sites)",
        "",
        "  non-WS spawn-sites by directory (the migration heat-map):",
    ]
    for d, n in list(by_dir.items())[:10]:
        lines.append(f"    {n:>4}  {d}")
    total_target = pure_spawn  # the pure non-WS forks are the contract number
    lines += [
        "-" * 80,
        f"  PHASE-2 DONE (zero non-WS forks remain): {'YES' if done else 'no'}",
        f"  CONTRACT NUMBER (pure non-WS spawn-sites to migrate): {total_target}",
        "  (subprocess-e2e legitimately survives ONLY in @walking_skeleton scenarios)",
        "=" * 80,
    ]
    return "\n".join(lines)


def _scan_per_site() -> dict[str, object]:
    """The DEEPER proof (DDD-5): non-WS spawn-sites PER SCENARIO, GATE-PARITY.

    DELEGATES to the production gate's precise per-scenario classifier
    (``des.cli.axis_b_levers.scan_spawn_sites`` with ``classify_per_site``) so the
    scorecard's un-gameable DONE number AGREES with the readiness gate BY
    CONSTRUCTION — one detector, one classification, no drift. The rule
    (ADR-TEST-003): a fork is KEEP iff its ENCLOSING scenario carries
    ``@walking_skeleton`` (incl. the pytest-bdd scenario-tag binding the gate
    resolves via the bound ``.feature``), else MIGRATE. A fork in a file that
    merely MENTIONS "walking skeleton" in prose/comment but sits in a non-WS
    scenario is therefore MIGRATE — closing the blind spot the old loose
    file-level ``_WS`` text exemption (``file_is_ws``) wrongly EXEMPTED.

    The gate scans the whole tests tree; the scorecard projects the gate's
    ``classified_sites`` onto its own acceptance universe (``_acceptance_test_files``)
    so the file-level gradient (``_scan``) and the per-site contract count over the
    SAME files. Resolves OPEN QUESTION 4: the contract fields are
    ``per_site_non_ws_count`` / ``by_scenario`` / ``by_dir`` / ``done`` (``done``
    iff the count is zero).

    ``des`` is imported lazily so the file-level gradient mode (``_scan``) stays
    stdlib-only and runs on a checkout where the package is not importable.
    """
    from des.cli import axis_b_levers

    report = axis_b_levers.scan_spawn_sites(TESTS, "python", classify_per_site=True)
    acceptance = {str(path) for path in _acceptance_test_files()}
    by_scenario: list[dict[str, object]] = []
    by_dir: dict[str, int] = {}
    count = 0
    for site in report.classified_sites:
        abs_path, line_str, _name = site.location.rsplit(":", 2)
        if abs_path not in acceptance:
            continue
        rel = Path(abs_path).relative_to(REPO).as_posix()
        top = "/".join(rel.split("/")[:3])
        if site.decision == axis_b_levers.MIGRATE:
            count += 1
            by_dir[top] = by_dir.get(top, 0) + 1
        by_scenario.append(
            {
                "file": rel,
                "scenario": site.enclosing_scenario,
                "tags": list(site.scenario_tags),
                "spawn_line": int(line_str),
                "decision": site.decision,
            }
        )
    return {
        "per_site_non_ws_count": count,
        "by_scenario": by_scenario,
        "by_dir": dict(sorted(by_dir.items(), key=lambda kv: -kv[1])),
        "done": count == 0,
    }


def _is_spawn_call(node: ast.AST) -> bool:
    """True iff ``node`` is a MIGRABLE interpreter-fork CALL (external-tool exempt).

    Semantic parity with ``des.cli.axis_b_levers._is_interpreter_spawn`` /
    ``_is_os_exec_call``: a ``subprocess`` spawner whose first arg-list element is
    ``sys.executable`` or a Python interpreter literal, or an ``os.exec*`` call.
    An external-tool subprocess (first arg a non-Python binary like ``git``) is
    NOT a spawn here — it is EXEMPT (the inflation the old regex counted).
    """
    return isinstance(node, ast.Call) and (
        _is_interpreter_spawn(node) or _is_os_exec_call(node)
    )


def _is_interpreter_spawn(call: ast.Call) -> bool:
    """True iff ``call`` is a ``subprocess.*`` spawner forking a Python interpreter."""
    func = call.func
    if not (isinstance(func, ast.Attribute) and func.attr in _SUBPROCESS_SPAWNERS):
        return False
    if not (isinstance(func.value, ast.Name) and func.value.id == "subprocess"):
        return False
    if not call.args:
        return False
    first_arg = call.args[0]
    if not (isinstance(first_arg, (ast.List, ast.Tuple)) and first_arg.elts):
        return False
    first = first_arg.elts[0]
    return _is_sys_executable(first) or _is_interpreter_literal(first)


def _is_sys_executable(node: ast.expr) -> bool:
    """True iff ``node`` is the ``sys.executable`` attribute access."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "executable"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    )


def _is_interpreter_literal(node: ast.expr) -> bool:
    """True iff ``node`` is a bare Python interpreter string literal."""
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and bool(_INTERPRETER_LITERAL.match(node.value))
    )


def _is_os_exec_call(call: ast.Call) -> bool:
    """True iff ``call`` is an ``os.exec*`` / ``os.system`` / ``os.popen`` spawn."""
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr in _OS_EXEC_FUNCS
        and isinstance(func.value, ast.Name)
        and func.value.id == "os"
    )


def _render_per_site_text(s: dict[str, object]) -> str:
    count = cast("int", s["per_site_non_ws_count"])
    by_dir = cast("dict[str, int]", s["by_dir"])
    done = cast("bool", s["done"])
    lines = [
        "=" * 80,
        "  SLOW-AT PHASE 2 — per-scenario non-WS spawn-site count (the un-gameable DONE)",
        "-" * 80,
        f"  per_site_non_ws_count (non-WS forks PER SCENARIO): {count}",
        "",
        "  non-WS spawn-sites by directory (the migration heat-map):",
    ]
    for directory, total in list(by_dir.items())[:10]:
        lines.append(f"    {total:>4}  {directory}")
    lines += [
        "-" * 80,
        f"  PHASE-2 DONE (zero non-WS spawn-sites remain): {'YES' if done else 'no'}",
        "=" * 80,
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--per-site",
        action="store_true",
        help="count non-WS spawn-sites PER SCENARIO (the un-gameable DONE contract)",
    )
    args = parser.parse_args(argv)
    scan = _scan_per_site if args.per_site else _scan
    render = _render_per_site_text if args.per_site else _render_text
    s = scan()
    if args.json:
        print(json.dumps(s, indent=2))
    else:
        print(render(s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""The neutral observation decoder cannot reach execution or outward layers.

The owner and its transitive dependencies remain governed. Package facades are
checked on executed import lines, not dormant lazy exports or typing branches.
@contract-shape: real-io
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3] / "src"
OWNER = "des.domain.oracle_observation"
OUTWARD = ("des.application", "des.cli", "des.adapters")
RUNTIME = {
    "subprocess",
    "os",
    "sys",
    "shutil",
    "socket",
    "multiprocessing",
    "asyncio",
    "platform",
    "ctypes",
    "importlib",
    "runpy",
}


def imports(module: str, path: Path, executed: set[int] | None = None) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    edges = set()
    for node in ast.walk(tree):
        if executed is not None and getattr(node, "lineno", None) not in executed:
            continue
        if isinstance(node, ast.Import):
            edges.update(item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom):
            target = (
                importlib.util.resolve_name(
                    "." * node.level + (node.module or ""), package
                )
                if node.level
                else node.module or ""
            )
            edges.add(target)
            edges.update(
                target + "." + alias.name for alias in node.names if alias.name != "*"
            )
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"__import__", "eval", "exec"}
        ):
            edges.add("dynamic-runtime-discovery")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr
            in {
                "read_text",
                "read_bytes",
                "write_text",
                "write_bytes",
                "open",
                "exists",
                "glob",
                "rglob",
                "getenv",
                "import_module",
            }
        ):
            edges.add("ambient-runtime-discovery")
    return edges


def violations(graph: dict[str, set[str]], owner: str) -> list[tuple[str, ...]]:
    pending = [(owner,)]
    seen = set()
    found = []
    while pending:
        trace = pending.pop()
        module = trace[-1]
        if module in seen:
            continue
        seen.add(module)
        dependencies = set(graph.get(module, ()))
        # Package containment is not an owner dependency on lazy exports.
        for target in dependencies:
            path = (*trace, target)
            if (
                target.startswith(OUTWARD)
                or target.split(".")[0] in RUNTIME
                or target in {"dynamic-runtime-discovery", "ambient-runtime-discovery"}
            ):
                found.append(path)
            elif target in graph:
                pending.append(path)
    return found


def test_neutral_observation_owner_has_no_transitive_outward_or_runtime_dependencies():
    population = {}
    for path in ROOT.parent.rglob("*.py"):
        relative = path.relative_to(ROOT.parent)
        if any(part.startswith(".") for part in relative.parts):
            continue
        parts = relative.with_suffix("").parts
        if parts[0] == "src":
            parts = parts[1:]
        population[".".join(parts).removesuffix(".__init__")] = path
    assert OWNER in population, (
        "WHAT: neutral observation owner is absent; WHY: the declared decoder boundary must own validation; HOW: implement the declared domain module without outward dependencies"
    )
    graph = {}
    pending = [OWNER]
    while pending:
        module = pending.pop()
        if module in graph or module not in population:
            continue
        edges = imports(module, population[module])
        # Initializers are measured separately on executable import behavior.
        graph[module] = edges
        pending.extend(
            edge for edge in edges if edge in population and edge not in graph
        )
    broken = violations(graph, OWNER)
    executed = executed_import_lines(ROOT, OWNER)
    for module, lines in executed.items():
        if module in population and population[module].name == "__init__.py":
            edges = imports(module, population[module], set(lines))
            # Loading the existing facade's lazy loader does not execute it.
            edges.discard("importlib")
            pending = [edge for edge in edges if edge in population]
            while pending:
                dependency = pending.pop()
                if dependency in graph:
                    continue
                graph[dependency] = imports(dependency, population[dependency])
                pending.extend(
                    edge
                    for edge in graph[dependency]
                    if edge in population and edge not in graph
                )
            broken.extend(violations({**graph, module: edges}, module))
    assert not broken, (
        f"WHAT: outward/runtime dependency paths {broken}; WHY: observation domain must not execute or discover ambient runtime; HOW: move effects to the existing application execution owner; governed population={sorted(population)}"
    )


def test_boundary_oracle_distinguishes_clean_scope_from_added_transitive_outward_dependency():
    clean = {OWNER: {"des.domain.added"}, "des.domain.added": {"json"}}
    broken = {
        **clean,
        "des.domain.added": {"des.domain.another"},
        "des.domain.another": {"subprocess"},
    }
    assert violations(clean, OWNER) == [], (
        "WHAT: pure added module falsely refused; WHY: standard-library pure decoding is allowed; HOW: preserve permitted inward dependency paths"
    )
    assert violations(broken, OWNER), (
        "WHAT: transitive execution dependency escaped the checker; WHY: newly added modules belong to its governed scope; HOW: traverse every reachable project import"
    )


def executed_import_lines(root: Path, owner: str) -> dict[str, list[int]]:
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--probe", str(root), owner],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"WHAT: import probe could not complete: {result.stderr}; WHY: an incapable "
        "checker cannot certify absence; HOW: repair the module's executable imports"
    )
    return json.loads(result.stdout)


def test_executed_initializer_distinguishes_lazy_exports_from_outward_import(tmp_path):
    package = tmp_path / "boundary_control"
    package.mkdir()
    initializer = package / "__init__.py"
    initializer.write_text(
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n    import subprocess\n"
        "def __getattr__(name):\n    import subprocess\n"
    )
    (package / "owner.py").write_text("import json\n")
    clean = executed_import_lines(tmp_path, "boundary_control.owner")
    assert not violations(
        {
            "boundary_control": imports(
                "boundary_control", initializer, set(clean["boundary_control"])
            )
        },
        "boundary_control",
    ), (
        "WHAT: dormant facade falsely refused; WHY: it executes no outward dependency; HOW: measure executable import lines"
    )
    initializer.write_text(initializer.read_text() + "import subprocess\n")
    broken = executed_import_lines(tmp_path, "boundary_control.owner")
    assert violations(
        {
            "boundary_control": imports(
                "boundary_control", initializer, set(broken["boundary_control"])
            )
        },
        "boundary_control",
    ), (
        "WHAT: added initializer execution escaped; WHY: initialization can violate the boundary; HOW: retain executed initializer dependencies"
    )


if __name__ == "__main__":
    import importlib

    observed: dict[str, set[int]] = {}
    probe_root = Path(sys.argv[2]).resolve()

    def trace(frame, event, arg):
        if event == "line":
            filename = Path(frame.f_code.co_filename)
            if filename.is_relative_to(probe_root):
                observed.setdefault(frame.f_globals["__name__"], set()).add(
                    frame.f_lineno
                )
        return trace

    sys.settrace(trace)
    importlib.import_module(sys.argv[3])
    sys.settrace(None)
    print(json.dumps({name: sorted(lines) for name, lines in observed.items()}))

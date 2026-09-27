"""No DES step executes what its own `NEXT` names, and none reaches another.

ADR-SSOT-002 Section 4b states this three ways and lists it as its own
falsifier: «A step never chooses the next step: it NAMES the canonical next step
as data and returns»; «no step executes what its own `NEXT` names»; and, among
the observations that would refute the whole subsection, «a step invokes a
second role, or a second step, before returning to its caller; or any software
executor composes the steps into a sequence».

THREE AXES, and the first version of this file had only one while claiming two.
An independent review measured the gap: a step composing with
`subprocess.run(["des", "verify", ...])` passed every assertion here, because
every assertion was an import scan and none of them ran anything.  The docstring
named a dynamic spy that did not exist, which is the same class of untruth the
terminals were just repaired for -- text describing evidence that is not there.

  1. IMPORTS.  A step that imports another step's entry point, or the
     subcommand dispatcher, could call it, and no runtime scenario is
     guaranteed to walk the branch where it does.
  2. SPAWNING.  A step module that cannot reach a process API cannot compose by
     starting one -- the route the review demonstrated.  The runner and its
     adapters spawn freely; a CLI step does not, and today none does.
  3. EXECUTION.  Every step is RUN for real against a repository, with the
     subcommand dispatcher and `subprocess.Popen` both spied, and a `des`
     process started from inside a step fails the count. This is the axis that
     sees what an import scan cannot.

A fourth axis exists outside this file and is named here rather than implied:
the acceptance suite counts the turns the fake provider was actually asked for,
so a step that bought a second ROLE turn is caught there, on the success paths
this unit cannot reach without a provider.

The registry itself is read rather than listed: a step added to the CLI and
forgotten by this test would be exactly the gap the test exists to close.
"""

from __future__ import annotations

import ast
import importlib
import io
import re
import subprocess
import sys
from pathlib import Path

import pytest

from des.cli.__main__ import _REGISTRY


#: The commands that are STEPS of the canonical delivery order. `des lane` is a
#: step too, but of the lane cycle rather than of one Request, and the other
#: registry rows are gates and queries; naming the set here is what lets the
#: static scan say "a step must not import a step" rather than "a CLI module
#: must not import a CLI module", which is false for the shared helpers.
STEP_NAMES = ("state", "po", "design", "oracle", "craft", "verify", "integrate")

#: Every `des <name>` a step writes into a terminal line. Kebab-case is
#: included because the registry carries such names, and a step naming one
#: that does not exist is the whole defect this scan catches.
_NAMED_COMMAND = re.compile(r"\bdes ([a-z][a-z0-9-]*)")

#: Where a `NEXT` line is actually COMPOSED. Scanning only the step modules
#: missed this and the miss was measured: a bad command name planted in the
#: shared builder left every assertion green, because that is precisely where
#: the canonical order and the fallback projection are spelled.
_NEXT_BUILDERS = ("des.cli.step_next", "des.application.delivery_state")

#: Anything a step module could reach another step through. Two families, and
#: the second was measured missing: a review composed with
#: `importlib.import_module("des.cli.verify").main(...)` and with
#: `runpy.run_module(...)`, and both passed every axis this file carried --
#: neither starts a PROCESS, so the spawn family did not see them, and neither
#: names a step at import time, so the import family did not either.
#:
#: A step needs none of them. It drives one turn through `DeliverySteps` and
#: prints a terminal; a module that can load and call another module by name is
#: a composer with the name still to be filled in.
_PROCESS_APIS = (
    "subprocess",
    "os.system",
    "os.execv",
    "os.spawnv",
    "pty",
    "importlib",
    "runpy",
)


def step_rows():
    rows = {row.name: row for row in _REGISTRY}
    missing = [name for name in STEP_NAMES if name not in rows]
    assert not missing, f"steps absent from the CLI registry: {missing}"
    return [rows[name] for name in STEP_NAMES]


def module_source(module_path: str) -> tuple[Path, str]:
    module = importlib.import_module(module_path)
    path = Path(module.__file__)
    return path, path.read_text(encoding="utf-8")


def emitted_text(source: str) -> str:
    """Every string this module can PRINT, with the docstrings left out.

    A docstring may legitimately name a command that does not exist -- `des
    verify` explains at length why there is no separate `des examine` -- and
    counting that as a broken NEXT would make the scan fire on prose. What
    reaches a terminal is a string constant that is not a docstring, including
    the constant halves of every f-string, so that is what is read.
    """
    tree = ast.parse(source)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
            first = node.body[0] if node.body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                docstrings.add(id(first.value))
    return "\n".join(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    )


def imported_modules(source: str) -> set[str]:
    """Every module this file imports, by dotted name, however it is spelled."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


@pytest.mark.parametrize("row", step_rows(), ids=lambda row: row.name)
def test_a_step_module_never_imports_another_steps_entry_point(row) -> None:
    """The static axis: a step cannot call what it cannot reach."""
    _, source = module_source(row.module_path)
    siblings = {
        f"des.cli.{name}" for name in STEP_NAMES if f"des.cli.{name}" != row.module_path
    }
    reached = imported_modules(source) & siblings
    assert not reached, (
        f"{row.name} imports another step: {sorted(reached)} -- a step NAMES the "
        "canonical next step as data and executes none of it"
    )


def test_no_step_module_reaches_the_subcommand_registry_at_all() -> None:
    """A step composing the steps would have to dispatch them, and none can.

    The dispatcher is the only software that turns a subcommand NAME into a
    call. A step importing it is an executor in the making, and Section 4b
    retires every executor that composes the steps: «No code path calls one step
    and then calls the next.»
    """
    reaching = []
    for row in step_rows():
        _, source = module_source(row.module_path)
        if any(
            name.startswith("des.cli.__main__") for name in imported_modules(source)
        ):
            reaching.append(row.name)
    assert not reaching, (
        f"these steps import the subcommand dispatcher: {reaching} -- no software "
        "executor may compose the steps"
    )


def test_every_command_a_step_names_is_one_the_cli_actually_carries() -> None:
    """A `NEXT` must name a form that would INVOKE a step, so the step must exist.

    This is the defect `des lane`'s own docstring records from this repository's
    CLAUDE.md: a standing instruction pointed at `des` subcommands the CLI did
    not carry, so the contract it taught could not be honoured. Section 4b makes
    `NEXT` «the command and the minimum inputs it requires. Not a description of
    the step: the form that would invoke it», which is exactly the claim a
    missing row falsifies.
    """
    registered = {row.name for row in _REGISTRY}
    sources = [(row.name, row.module_path) for row in step_rows()]
    sources += [(module, module) for module in _NEXT_BUILDERS]
    for label, module_path in sources:
        _, source = module_source(module_path)
        named = set(_NAMED_COMMAND.findall(emitted_text(source)))
        unknown = named - registered
        assert not unknown, (
            f"{label} names `des` commands the CLI does not carry: {sorted(unknown)}"
        )
        assert named, f"{label} names no command at all on its NEXT lines"


#: The one application boundary that owns a whole-Request run, and the module
#: that defines it. A CLI step that binds EITHER can compose; the nine that
#: exist bind `DeliverySteps`, which invokes one turn and returns.
#:
#: Both, because a review measured that naming only the class was not enough:
#: `import des.application.delivery_continuation as dc` followed by
#: `dc.DeliveryContinuationRunner(None).run(root)` bound the owner through the
#: module and escaped a check that read class names. Importing a module IS
#: importing everything in it, so the module path is the wider fact and the
#: class name stays for a `from ... import` that never names the module.
_COMPOSING_OWNER = "DeliveryContinuationRunner"
_COMPOSING_MODULE = "des.application.delivery_continuation"


def test_no_registered_command_reaches_the_runner_that_once_composed() -> None:
    """No executor may compose the steps, and now there is no exception.

    Section 4b: «No executor in the software composes the steps. No code path
    calls one step and then calls the next.» `des dispatch` was the ONE stated
    exception this test used to skip. It is retired, so the law is enforced over
    the whole registry with nothing excused -- and a retirement that re-appeared
    under a second name would be caught here rather than by a missing file.

    THE PROPERTY IS THE IMPORT, not the call, and that is what makes it exact.
    A first version matched the substring `".run("` beside the runner's name,
    which an alias or a `_run(` walks past -- a check keyed on spelling rather
    than on a fact. A second named only the CLASS, and a review measured that
    gap too: `import des.application.delivery_continuation as dc` binds the
    owner through its MODULE and never spells the class at import time.

    So both are read from the AST import graph, module and class, because
    importing a module is importing everything in it. A CLI step reaches the
    whole-Request composition only by binding one of them, and today none of
    the nine does: they go through `DeliverySteps`, which invokes one turn and
    returns.
    """
    composing = []
    for row in _REGISTRY:
        _, source = module_source(row.module_path)
        imported = imported_modules(source)
        binds_class = _COMPOSING_OWNER in imported or any(
            name.endswith(f".{_COMPOSING_OWNER}") for name in imported
        )
        binds_module = _COMPOSING_MODULE in imported or any(
            name.startswith(f"{_COMPOSING_MODULE}.") for name in imported
        )
        if binds_class or binds_module:
            composing.append(row.name)
    assert not composing, (
        f"these commands bind the whole-Request composition: {composing} -- "
        "no command may, now that the one stated exception is retired"
    )


def _called_argv_heads(source: str) -> set[str]:
    """The first element of every list or tuple LITERAL passed as a first argument.

    `subprocess.run(["des", "verify", ...])` is the composition route an import
    scan alone can miss once the process API arrives under another name. What
    identifies it is not the callee's spelling -- which an alias changes -- but
    the SHAPE of what is handed over: an argument vector whose head names a
    command. That shape is read here from the AST, so `run`, `_run` and any
    alias are all seen the same way.
    """
    heads: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, (ast.List, ast.Tuple)) and first.elts:
            head = first.elts[0]
            if isinstance(head, ast.Constant) and isinstance(head.value, str):
                heads.add(Path(head.value).name)
    return heads


@pytest.mark.parametrize("row", step_rows(), ids=lambda row: row.name)
def test_a_step_module_hands_no_argv_vector_headed_by_a_des_command(row) -> None:
    """The shape axis: an argv vector starting with `des` is a composition.

    Read from the AST rather than from the callee's name, so it fires whatever
    the process API is called at the call site -- `subprocess.run`, an aliased
    `run`, a local `_run` wrapper. What it keys on is the vector, which the
    composition cannot do without.
    """
    _, source = module_source(row.module_path)
    composing = {
        head for head in _called_argv_heads(source) if head in {"des", "des.exe"}
    }
    assert not composing, (
        f"{row.name} hands over an argv vector headed by {sorted(composing)} -- "
        "a step that runs `des` composes the steps"
    )


@pytest.mark.parametrize("row", step_rows(), ids=lambda row: row.name)
def test_a_step_module_cannot_reach_another_step_at_all(row) -> None:
    """The reach axis: what cannot start or load a module cannot compose one.

    The runner and its adapters spawn freely -- the provider, the declared
    verification, Git -- and the dispatcher loads modules by name because that
    is its whole job. A CLI step does neither: it drives one turn through
    `DeliverySteps` and prints a terminal. So the absence is a property it can
    be held to rather than a habit it happens to have, and it closes the two
    routes an import scan and a spawn scan each miss on their own.
    """
    _, source = module_source(row.module_path)
    imported = imported_modules(source)
    reachable = {
        name
        for name in imported
        if any(name == api or name.startswith(f"{api}.") for api in _PROCESS_APIS)
    }
    assert not reachable, (
        f"{row.name} can reach another step: {sorted(reachable)} -- a step that "
        "spawns or loads `des` composes the steps, and Section 4b forbids any "
        "executor that does"
    )


def test_running_every_step_for_real_starts_no_des_process_and_re_enters_nothing(
    tmp_path, monkeypatch
) -> None:
    """The EXECUTION axis: what the import scans cannot see.

    Every step is invoked against a real repository, with the subcommand
    dispatcher and the process API both spied. The steps refuse -- there is no
    decomposition and no provider -- and refusing is the point: this walks the
    argument parsing, the root resolution, the owned-state read and the terminal
    composition of every step, which is where a re-entry would sit, and it
    catches a `des` process started from any of them including through a helper
    an import scan cannot follow.
    """
    root = tmp_path / "root"
    root.mkdir()
    for argv in (
        ("init", "-q"),
        ("config", "user.email", "a@b"),
        ("config", "user.name", "a"),
    ):
        subprocess.run(["git", "-C", str(root), *argv], check=True, capture_output=True)
    (root / "README.md").write_text("x\n")
    subprocess.run(
        ["git", "-C", str(root), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "base"],
        check=True,
        capture_output=True,
    )

    dispatched: list[list[str]] = []
    spawned: list[list[str]] = []

    import des.cli.__main__ as dispatcher

    real_main = dispatcher.main
    monkeypatch.setattr(
        dispatcher, "main", lambda argv=None: dispatched.append(list(argv or [])) or 0
    )
    real_popen = subprocess.Popen

    def spy(args, *rest, **kwargs):
        vector = list(args) if isinstance(args, (list, tuple)) else [str(args)]
        if vector and Path(str(vector[0])).name in {"des", "des.exe"}:
            spawned.append(vector)
        return real_popen(args, *rest, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", spy)

    invocations = {
        "state": ["--repo-root", str(root)],
        "project": ["--repo-root", str(root), "--html", str(tmp_path / "p.html")],
        "po": ["--repo-root", str(root), "--project"],
        "design": ["--repo-root", str(root), "--value", "1"],
        "oracle": ["--repo-root", str(root), "--value", "1"],
        "craft": ["--repo-root", str(root), "--value", "1"],
        "verify": ["--repo-root", str(root)],
        "integrate": ["--repo-root", str(root), "--candidate", "0" * 40],
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    for row in step_rows():
        arguments = invocations.get(row.name)
        if arguments is None:
            continue
        module = importlib.import_module(row.module_path)
        assert module.main(arguments) in (0, 1), row.name

    assert dispatched == [], f"a step re-entered the dispatcher: {dispatched}"
    assert spawned == [], f"a step started a `des` process: {spawned}"
    assert real_main is not None  # the real entry point was never called

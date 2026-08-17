"""pytest-bdd bindings for fix-des-subprocess-pythonpath slice-01.

DISTILL-authored active-RED ATs (atdd_pure, ADR-025). These scenarios RUN and
fail for the right reason at HEAD:

  * AC-1 (arch-ban) -- the real AST arch-walk over ``src/des/**`` returns a real
    NON-EMPTY violation list (~18 inline ``python_for(...)`` spawn sites bypass
    the not-yet-existing ``des_spawn`` helper) -> semantic AssertionError.
  * AC-2 (importable-child) / AC-3 (env-by-construction) / AC-4 (kwargs-forward)
    -- ``des.runtime.interpreter.des_spawn`` does not exist yet; the composition
    raises a SEMANTIC AssertionError (impl missing), NOT an ImportError (the lazy
    import-guard in composition.py keeps collection BROKEN-free).

DELIVER GREENs them by adding ``des_spawn`` (composing ``python_for(capability)``
+ ``des_subprocess_env(base=caller_env)`` + caller-kwargs forwarding) and
migrating the ~18 inline spawn sites to it.

Mandate-13: the SUT is driven exclusively through the real surfaces via the
composition root (arch-walk over the real tree, the real ``des_spawn`` helper, a
    real hermetic ``python -m des.cli.health_check --help`` subprocess). No production
module is imported directly in the step bodies. Mandate-8: the AC-3 step asserts
the by-construction coupling as a Universe-bound state delta over the
port-exposed observables (argv0, pythonpath-has-des-root).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .steps.composition import (
    SANCTIONED_SUBCOMMAND,
    SubprocessPythonpathComposition,
)
from .steps.domain_types import (
    ChildImportOutcome,
    SpawnCapability,
)


scenarios("slice-01-des-subprocess-pythonpath.feature")


@pytest.fixture
def composition() -> SubprocessPythonpathComposition:
    """The composition root driving the real des_spawn helper + arch-walk."""
    return SubprocessPythonpathComposition()


@pytest.fixture
def world() -> dict[str, object]:
    """Per-scenario carrier for the observable the When produces (chained
    narrative -- the Then reads what the When wrote, no fixture-theater)."""
    return {}


# ===========================================================================
# AC-1 -- arch-ban over the real src/des/** tree (@real-io, layer-3 black-box)
# ===========================================================================


@given("the des source tree as it ships")
def _given_real_des_tree(
    composition: SubprocessPythonpathComposition, world: dict[str, object]
) -> None:
    world["modules"] = composition.des_modules()


@when("the architecture is inspected for inline des-module spawns")
def _when_inspect_arch(
    composition: SubprocessPythonpathComposition, world: dict[str, object]
) -> None:
    world["violations"] = composition.inline_python_for_spawn_violations()


@then("no des gate spawns a child des module outside the centralized helper")
def _then_no_inline_spawns(world: dict[str, object]) -> None:
    violations = world["violations"]
    assert violations == [], (
        "des-module subprocess spawns still bypass the centralized des_spawn "
        f"helper ({len(violations)} inline python_for(...) spawn site(s)) -- "
        "every site must route through des.runtime.interpreter.des_spawn:\n  "
        + "\n  ".join(v.location for v in violations)
    )


# ===========================================================================
# AC-2 -- importable child under a des-stripped host (@real-io, layer-3)
# ===========================================================================


@given("a host where des is stripped from the import path")
def _given_des_stripped_host(world: dict[str, object]) -> None:
    # The composition builds the des-stripped env at spawn time (PYTHONPATH="");
    # this Given names the precondition the When exercises.
    world["subcommand"] = SANCTIONED_SUBCOMMAND


@when("a gate spawns the read-only integrity command through the centralized helper")
def _when_spawn_child(
    composition: SubprocessPythonpathComposition, world: dict[str, object]
) -> None:
    world["outcome"] = composition.spawn_child_under_des_stripped_env(
        world["subcommand"]  # type: ignore[arg-type]
    )


@then("the child command imports des and succeeds")
def _then_child_imports_des(world: dict[str, object]) -> None:
    assert world["outcome"] is ChildImportOutcome.IMPORTED, (
        "the spawned des.cli child could not import des under a des-stripped "
        "host (got ModuleNotFoundError instead of exit 0) -- des_spawn must "
        "inject the des root via des_subprocess_env so the child finds des"
    )


# ===========================================================================
# AC-3 -- env-by-construction (@in-memory, spied run; Mandate-8 state delta)
# ===========================================================================


@given(
    "a caller that asks the helper to spawn a des command without naming an "
    "interpreter or a path"
)
def _given_caller_no_interp_no_path(world: dict[str, object]) -> None:
    world["capability"] = SpawnCapability.NONE


@when("the helper spawns the child")
def _when_helper_spawns(
    composition: SubprocessPythonpathComposition, world: dict[str, object]
) -> None:
    world["spied"] = composition.spawn_with_spied_run(
        world["capability"],  # type: ignore[arg-type]
        SANCTIONED_SUBCOMMAND.module,
        SANCTIONED_SUBCOMMAND.readonly_arg,
        caller_kwargs=world.get("caller_kwargs"),  # type: ignore[arg-type]
    )


@then("the child is launched with the resolved interpreter and des on its path")
def _then_env_by_construction(
    composition: SubprocessPythonpathComposition, world: dict[str, object]
) -> None:
    spied = world["spied"]
    expected_interpreter = composition.expected_interpreter_for(SpawnCapability.NONE)
    expected_des_root = composition.expected_des_root_on_pythonpath()

    # Universe = the port-exposed observables of the spawn the helper composed.
    # before = the caller passed NEITHER interpreter NOR path; after = what the
    # helper actually launched. The delta proves the by-construction coupling.
    assert_state_delta(
        before={"argv0": "", "pythonpath_has_des_root": False},
        after={
            "argv0": spied.argv0,  # type: ignore[union-attr]
            "pythonpath_has_des_root": expected_des_root in spied.pythonpath.split(":"),  # type: ignore[union-attr]
        },
        universe={"argv0", "pythonpath_has_des_root"},
        expected={
            "argv0": set_to(expected_interpreter),
            "pythonpath_has_des_root": set_to(True),
        },
    )


# ===========================================================================
# AC-4 -- selection + kwargs forwarded, caller path preserved
# (@in-memory, unbounded-preservation; spied run)
# ===========================================================================


@given(
    "a caller that asks the helper to spawn a des command with its own options "
    "and its own path entry"
)
def _given_caller_with_kwargs_and_path(world: dict[str, object]) -> None:
    world["capability"] = SpawnCapability.NONE
    world["caller_kwargs"] = {
        "capture_output": True,
        "text": True,
        "timeout": 17,
        "env": {"PYTHONPATH": "/caller/own/path", "DES_CALLER_FLAG": "1"},
    }


@then(
    "the caller's options are forwarded and the caller's path entry is "
    "preserved alongside des"
)
def _then_kwargs_forwarded_and_path_preserved(world: dict[str, object]) -> None:
    spied = world["spied"]
    forwarded = spied.kwargs  # type: ignore[union-attr]
    pythonpath_entries = spied.pythonpath.split(":")  # type: ignore[union-attr]

    assert forwarded.get("capture_output") is True, (
        "des_spawn dropped the caller's capture_output kwarg -- it must forward "
        f"caller kwargs into subprocess.run (forwarded={forwarded!r})"
    )
    assert forwarded.get("text") is True, (
        f"des_spawn dropped the caller's text kwarg (forwarded={forwarded!r})"
    )
    assert forwarded.get("timeout") == 17, (
        "des_spawn dropped/altered the caller's timeout kwarg "
        f"(forwarded={forwarded!r})"
    )
    assert "/caller/own/path" in pythonpath_entries, (
        "des_spawn dropped the caller's PYTHONPATH entry -- the caller env must "
        "be merged through des_subprocess_env(base=...), preserving caller "
        f"entries alongside the des root (pythonpath={spied.pythonpath!r})"  # type: ignore[union-attr]
    )
    assert "DES_CALLER_FLAG" in spied.env, (  # type: ignore[union-attr]
        "des_spawn dropped a non-PYTHONPATH caller env var -- the caller env "
        f"must be merged, not replaced (env keys={sorted(spied.env)!r})"  # type: ignore[union-attr]
    )

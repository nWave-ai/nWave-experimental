"""Acceptance tests -- pre-push + CI blocking wiring (DISTILL, slice-05).

Feature-delta: docs/feature/language-port-realization-gate/feature-delta.md
  Wave: DESIGN / [REF] Architecture & Contract -- slice-05 (blocking-wiring)
  Wave: DISCUSS / [REF] Slice Plan -- slice-05

Slice-05 value (the observable): the ``--check-port-realization`` gate
(shipped slice-03) is wired as a BLOCKING pre-push hook + a CI job + a
pyproject breadcrumb, so a partial-language registration (a plugin declaring
a port ``True``-but-stub) is blocked MECHANICALLY on every push -- not only
when a maintainer remembers to run the CLI by hand.

Contract under test (DOES NOT EXIST YET -- active-RED by design). Three
additive edits, all EXTEND, no new module:

  1. **Pre-push hook** (``.pre-commit-config.yaml``): one ``repo: local``
     hook mirroring the existing ``des-declare-done-pre-push`` shape
     (``language: system``, ``pass_filenames: false``, ``always_run: true``,
     ``stages: [pre-push]``), ``entry`` invoking
     ``python3 -m scripts.cli.validate_language_adapter_catalog
     --check-port-realization``.
  2. **CI backstop** (``.github/workflows/ci.yml``): one job
     ``port-realization-gate`` mirroring the existing ``probe-method-check``
     job shape (checkout + setup-python + single ``run:`` step invoking the
     same script), wired into Stage 2 (``framework-validation``'s ``needs``
     list, the same graph position ``probe-method-check`` already occupies)
     -- GDP-6: CI is the backstop a local ``git push --no-verify`` cannot
     bypass.
  3. **Breadcrumb** -- a one-line comment above the pyproject
     ``[project.entry-points."nwave.lang.adapter"]`` block pointing at the
     gate (GDP-2 inline affordance). ALREADY SHIPPED as part of slice-04
     (verified by direct ``Read`` before authoring) -- the assertion below is
     a stable regression guard, not a RED witness for this slice.

Active-RED scaffolding: NONE of the touched symbols are CREATE_NEW (both
config files already exist, already parse as valid YAML, and already host
sibling hooks/jobs of the exact shape this slice mirrors) -- the RED-ness is
BEHAVIORAL/CONFIGURATIONAL (a hook/job that does not yet exist in the parsed
structure), never a missing-module ``ImportError``. Every failing assertion
below is a semantic ``AssertionError`` naming WHAT is missing (mirrors the
``_load_gate_runner`` MISSING_FUNCTIONALITY convention slice-03's AT
established in this same feature).

Driving surface (Mandate-13 driving-port-only): the two config files
(``.pre-commit-config.yaml``, ``.github/workflows/ci.yml``) ARE the shipped
artifacts this slice's value is entirely about -- reading them via
``yaml.safe_load`` is the established precedent in this repo
(``tests/build/test_precommit_hooks_bare_interpreter_parity.py``:
``yaml.safe_load(PRE_COMMIT_CONFIG.read_text(...))``). The behavioral
scenario additionally drives the REAL CLI as a subprocess (Layer 3
subprocess, ``@real-io @subprocess``) through the hook's own extracted
``entry`` command -- proving the wiring actually blocks, not merely that the
YAML shape looks right. The fixture technique (a synthetic, controlled
"liar" language-adapter plugin whose ``port_coverage`` declares ``True`` for
a stub-backed port) is REUSED verbatim from
``synthetic_language_adapter_fixtures.py`` (slice-02/03/04's own
test-brittleness fix #92) -- never coupling to nWave-dev's own (mutable)
adapter implementation state.

CONTRACT_SHAPE: unbounded-preservation for every scenario -- every assertion
is a read-only inspection of a config file plus one read-only probe
subprocess; no repo state is mutated by any scenario.

Negative ATs (GS-8, ``@pytest.mark.negative_at``): the behavioral hook
scenario asserts the WRONG outcome (a partial-language registration NOT
being rejected) is not produced (name stem ``_rejects_``); the CI-job
scenario asserts the WRONG outcome (a non-zero gate exit being silently
swallowed by the CI job) is not produced (name stem ``_never_``).
"""

from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml


_REPO_ROOT = Path(__file__).resolve().parents[4]
_PRE_COMMIT_CONFIG = _REPO_ROOT / ".pre-commit-config.yaml"
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

_CHECK_PORT_REALIZATION_FLAG = "--check-port-realization"
_GATE_SCRIPT_MODULE = "scripts.cli.validate_language_adapter_catalog"
_CI_JOB_ID = "port-realization-gate"
_FRAMEWORK_VALIDATION_JOB_ID = "framework-validation"

_SYNTHETIC_FIXTURES_MODULE = (
    "tests.build.language_port_realization_gate.acceptance."
    "synthetic_language_adapter_fixtures"
)
_CSHARP_PLUGIN_TARGET = (
    f"{_SYNTHETIC_FIXTURES_MODULE}:SyntheticLiarLanguageAdapterPluginCSharp"
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _pre_commit_config() -> dict[str, Any]:
    return yaml.safe_load(_PRE_COMMIT_CONFIG.read_text(encoding="utf-8"))


def _ci_workflow_config() -> dict[str, Any]:
    return yaml.safe_load(_CI_WORKFLOW.read_text(encoding="utf-8"))


def _find_check_port_realization_hook() -> dict[str, Any] | None:
    """The ``repo: local`` hook whose ``entry`` invokes the gate, if any."""
    config = _pre_commit_config()
    for repo in config.get("repos", []):
        for hook in repo.get("hooks", []):
            if _CHECK_PORT_REALIZATION_FLAG in hook.get("entry", ""):
                return hook
    return None


def _require_check_port_realization_hook() -> dict[str, Any]:
    """Return the pre-push hook or raise a MISSING_FUNCTIONALITY AssertionError."""
    hook = _find_check_port_realization_hook()
    if hook is None:
        raise AssertionError(
            "MISSING_FUNCTIONALITY: .pre-commit-config.yaml declares no "
            f"`repo: local` hook whose `entry` invokes {_CHECK_PORT_REALIZATION_FLAG!r} "
            "(feature-delta slice-05, docs/feature/language-port-realization-gate/"
            "feature-delta.md [REF] Architecture & Contract -- slice-05). Add one "
            "hook mirroring `des-declare-done-pre-push`'s shape (language: system, "
            "pass_filenames: false, always_run: true, stages: [pre-push]) with "
            f"entry: python3 -m {_GATE_SCRIPT_MODULE} {_CHECK_PORT_REALIZATION_FLAG}. "
            f"Re-check with: python -m {_GATE_SCRIPT_MODULE} {_CHECK_PORT_REALIZATION_FLAG}."
        )
    return hook


def _find_port_realization_gate_job() -> dict[str, Any] | None:
    config = _ci_workflow_config()
    jobs = config.get("jobs", {})
    return jobs.get(_CI_JOB_ID)


def _require_port_realization_gate_job() -> dict[str, Any]:
    job = _find_port_realization_gate_job()
    if job is None:
        raise AssertionError(
            f"MISSING_FUNCTIONALITY: .github/workflows/ci.yml declares no job "
            f"named {_CI_JOB_ID!r} (feature-delta slice-05 [REF] Architecture & "
            f"Contract -- slice-05). Add one job mirroring `probe-method-check`'s "
            f"shape (checkout + setup-python + single `run:` step invoking "
            f"`python3 -m {_GATE_SCRIPT_MODULE} {_CHECK_PORT_REALIZATION_FLAG}`), "
            f"wired into Stage 2 by adding {_CI_JOB_ID!r} to "
            f"`{_FRAMEWORK_VALIDATION_JOB_ID}`'s `needs` list -- the same graph "
            f"position `probe-method-check` already occupies. Re-check with: "
            f"python -m {_GATE_SCRIPT_MODULE} {_CHECK_PORT_REALIZATION_FLAG}."
        )
    return job


def _run_step_commands(job: dict[str, Any]) -> list[str]:
    return [
        step["run"]
        for step in job.get("steps", [])
        if isinstance(step, dict) and "run" in step
    ]


# ---------------------------------------------------------------------------
# Scenario 1 -- the pre-push hook exists and has the correct blocking shape.
# @in-memory
# CONTRACT_SHAPE: unbounded-preservation
# ---------------------------------------------------------------------------


def test_pre_commit_declares_a_blocking_pre_push_hook_for_check_port_realization() -> (
    None
):
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: feature-delta Slice Plan slice-05 + [REF] Architecture &
    Contract -- slice-05 ("Pre-push blocking gate").

    ``.pre-commit-config.yaml`` must declare a ``repo: local`` hook whose
    ``entry`` invokes ``--check-port-realization``, mirroring
    ``des-declare-done-pre-push``'s exact blocking shape: ``language:
    system``, ``pass_filenames: false``, ``always_run: true``, staged only
    at ``pre-push``. TODAY no such hook exists -- this fails first, for the
    right (semantic) reason.
    """
    hook = _require_check_port_realization_hook()

    assert hook.get("language") == "system", (
        f"expected `language: system` (mirrors des-declare-done-pre-push): {hook!r}"
    )
    assert hook.get("pass_filenames") is False, (
        f"expected `pass_filenames: false` (mirrors des-declare-done-pre-push): {hook!r}"
    )
    assert hook.get("always_run") is True, (
        f"expected `always_run: true` (mirrors des-declare-done-pre-push): {hook!r}"
    )
    stages = hook.get("stages") or []
    assert "pre-push" in stages, (
        f"expected `stages: [pre-push]` (mirrors des-declare-done-pre-push), "
        f"got stages={stages!r}: {hook!r}"
    )
    assert _GATE_SCRIPT_MODULE in hook.get("entry", ""), (
        f"expected the entry to invoke `{_GATE_SCRIPT_MODULE}`: {hook!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 2 -- NEGATIVE AT: the wired hook's entry, invoked exactly as
# pre-push would invoke it, actually REJECTS a partial-language registration
# (a synthetic liar plugin) -- the block is real, not merely YAML shape.
# @real-io @subprocess
# CONTRACT_SHAPE: unbounded-preservation
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_pre_push_hook_entry_rejects_a_partial_language_registration() -> None:
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: feature-delta Summary ("blocked mechanically on every
    push") + [REF] Architecture & Contract -- slice-05.

    Negative AT (GS-8): asserts the WRONG outcome -- a partial-language
    registration (a plugin declaring ``port_coverage[X]=True`` while ``X``
    is stub-backed) NOT being rejected by the wired hook's own ``entry``
    command -- is NOT produced. The hook's ``entry`` is extracted VERBATIM
    from ``.pre-commit-config.yaml`` and run exactly as pre-push would run
    it (plus ``--plugin <synthetic-liar>``, the repeatable probing flag
    shipped in slice-03), against the CONTROLLED
    ``SyntheticLiarLanguageAdapterPluginCSharp`` fixture (never nWave-dev's
    own mutable adapter state, per test-brittleness fix #92). TODAY this
    fails at hook-lookup (no hook exists yet) -- once wired, the CLI's
    already-shipped GAP lane makes this assertion durable.
    """
    hook = _require_check_port_realization_hook()
    entry_tokens = shlex.split(hook["entry"])

    completed = subprocess.run(
        [*entry_tokens, "--plugin", _CSHARP_PLUGIN_TARGET],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    combined_output = completed.stdout + completed.stderr

    assert completed.returncode != 0, (
        f"expected the pre-push hook's own entry command to REJECT (non-zero "
        f"exit) a partial-language registration -- got exit "
        f"{completed.returncode}. This is the WRONG outcome (silent accept) "
        f"the negative AT guards against. output={combined_output!r}"
    )
    assert "csharp" in combined_output, (
        f"expected the offending synthetic plugin named in the rejection "
        f"output: {combined_output!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 3 -- the CI job exists, mirrors probe-method-check's shape, and
# runs the same gate script.
# @in-memory
# CONTRACT_SHAPE: unbounded-preservation
# ---------------------------------------------------------------------------


def test_ci_yml_declares_port_realization_gate_job_running_the_same_script() -> None:
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: feature-delta [REF] Architecture & Contract -- slice-05
    ("CI backstop"). GDP-6: CI is the backstop a local
    `git push --no-verify` cannot bypass.

    ``.github/workflows/ci.yml`` must declare a job named
    ``port-realization-gate`` mirroring ``probe-method-check``'s shape
    (checkout + setup-python + a single ``run:`` step invoking the same
    gate script), and that job must be wired into ``framework-validation``'s
    ``needs`` list -- the same graph position ``probe-method-check`` already
    occupies, so the gate genuinely blocks Stage 2 rather than merely
    existing unreferenced in the workflow file.
    """
    job = _require_port_realization_gate_job()

    step_uses = [
        step.get("uses", "") for step in job.get("steps", []) if isinstance(step, dict)
    ]
    assert any("actions/checkout" in uses for uses in step_uses), (
        f"expected a checkout step (mirrors probe-method-check): {job!r}"
    )
    assert any("actions/setup-python" in uses for uses in step_uses), (
        f"expected a setup-python step (mirrors probe-method-check): {job!r}"
    )

    run_commands = _run_step_commands(job)
    assert len(run_commands) == 1, (
        f"expected a single `run:` step (mirrors probe-method-check's "
        f"single-script-invocation shape), got {len(run_commands)}: {job!r}"
    )
    assert _GATE_SCRIPT_MODULE in run_commands[0], (
        f"expected the run step to invoke `{_GATE_SCRIPT_MODULE}`: {run_commands[0]!r}"
    )
    assert _CHECK_PORT_REALIZATION_FLAG in run_commands[0], (
        f"expected the run step to pass `{_CHECK_PORT_REALIZATION_FLAG}`: "
        f"{run_commands[0]!r}"
    )

    ci_config = _ci_workflow_config()
    framework_validation = ci_config["jobs"][_FRAMEWORK_VALIDATION_JOB_ID]
    needs = framework_validation.get("needs", [])
    assert _CI_JOB_ID in needs, (
        f"expected {_CI_JOB_ID!r} wired into `{_FRAMEWORK_VALIDATION_JOB_ID}`'s "
        f"`needs` list (the same graph position `probe-method-check` already "
        f"occupies) so the gate actually blocks Stage 2 -- got needs={needs!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 4 -- NEGATIVE AT: the CI job never silently swallows a non-zero
# gate exit (no continue-on-error, no `|| true` escape hatch).
# @in-memory
# CONTRACT_SHAPE: unbounded-preservation
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_ci_job_port_realization_gate_never_swallows_a_nonzero_gate_exit() -> None:
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: GDP-6 (no silent-wrong) + feature-delta [REF]
    Architecture & Contract -- slice-05 ("CI is the backstop a local
    `git push --no-verify` cannot bypass").

    Negative AT (GS-8): asserts the WRONG outcome -- a non-zero gate exit
    being silently swallowed by the CI job (``continue-on-error: true`` at
    job or step level, or a `run:` command suffixed with an exit-code
    override like ``|| true`` / ``|| exit 0``) -- is NOT produced. A CI
    backstop that can silently pass despite a gap defeats the entire
    purpose of slice-05.
    """
    job = _require_port_realization_gate_job()

    assert job.get("continue-on-error") is not True, (
        f"the job must never set `continue-on-error: true` -- that would "
        f"silently swallow a non-zero gate exit: {job!r}"
    )
    for step in job.get("steps", []):
        if not isinstance(step, dict):
            continue
        assert step.get("continue-on-error") is not True, (
            f"no step may set `continue-on-error: true` on the gate-invoking "
            f"job: {step!r}"
        )

    for run_command in _run_step_commands(job):
        assert not re.search(r"\|\|\s*(true|exit\s+0)\b", run_command), (
            f"the run step must never suffix an exit-code override that "
            f"silently swallows a non-zero gate exit: {run_command!r}"
        )


# ---------------------------------------------------------------------------
# Scenario 5 -- the GDP-2 inline breadcrumb above the pyproject entry-points
# block is present (already shipped as part of slice-04; stable regression
# guard, not a RED witness for THIS slice).
# @in-memory
# CONTRACT_SHAPE: unbounded-preservation
# ---------------------------------------------------------------------------


def test_pyproject_breadcrumb_points_at_the_check_port_realization_gate() -> None:
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: feature-delta [REF] Architecture & Contract -- slice-05
    ("Breadcrumb -- folds into the slice-04 pyproject.toml edit").

    A one-line comment above the `[project.entry-points."nwave.lang.
    adapter"]` block must point at the re-check command (GDP-2 inline
    affordance at the authoring site). Verified ALREADY PRESENT by direct
    `Read` before authoring this slice (shipped as part of slice-04) -- this
    assertion is a stable regression guard for slice-05's own value
    statement, not a RED witness (the other 4 scenarios above carry the RED
    for this slice).
    """
    assert re.search(
        rf"Re-check with.*{re.escape(_CHECK_PORT_REALIZATION_FLAG)}",
        _PYPROJECT.read_text(encoding="utf-8"),
    ), (
        "expected a GDP-2 inline breadcrumb comment ('Re-check with: ... "
        f"{_CHECK_PORT_REALIZATION_FLAG}') above the entry-points block."
    )

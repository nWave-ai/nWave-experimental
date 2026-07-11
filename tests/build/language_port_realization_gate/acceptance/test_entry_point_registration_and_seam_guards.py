"""Acceptance tests -- entry-points + seam-catch + reentrancy-guard (DISTILL, slice-04a, `@coupled`).

Feature-delta: docs/feature/language-port-realization-gate/feature-delta.md
  Wave: DESIGN / [REF] Architecture & Contract -- slice-04a
  Wave: DISCUSS / [REF] Slice Plan -- slice-04a

Contract under test (DOES NOT EXIST YET as a coupled vertical -- active-RED by
design; every symbol touched already EXISTS on disk, only their BODIES are
missing the slice-04a behaviour, so no hidden-import scaffold (P1-P4) is
needed anywhere in this file -- every import below is a plain module-top
import of an already-importable production module):

  1. **Entry-point registration** (``pyproject.toml``,
     ``[project.entry-points."nwave.lang.adapter"]``): two NEW rows,
     ``nwave-lang-python`` / ``nwave-lang-typescript``, pointing at
     ``scripts.install.plugins.nwave_lang_{python,typescript}:NwaveLang{Python,
     Typescript}`` -- ABSENT today (confirmed by direct ``Read`` before
     authoring; only ``_conformance_fixture`` + ``nwave-lang-rust`` are
     registered).
  2. **ADR-ULAR-005 seam-catch**: ``des.cli.verify_environmental_e2e.
     _maybe_route_through_registered_e2e_adapter`` and
     ``scripts.cli.check_robustness_density.
     _maybe_route_through_registered_density_adapter`` currently call their
     resolved facet's stub-backed method(s) UNGUARDED -- a genuinely
     registered stub facet (the REAL, already-shipped
     ``Python{EnvironmentalE2E,RobustnessDensity}Adapter``, both 100% ``raise
     NotImplementedError`` per the feature-delta's verified smoking gun)
     crashes the seam TODAY with an uncaught ``NotImplementedError``. Slice-
     04a wraps the facet invocation in ``try/except NotImplementedError:
     return None``, falling through to the legacy hardcoded body.
  3. **ADR-ULAR-004 reentrancy-guard arming**: the guard module
     (``des.adapters.driven.runner.reentrancy_guard``, ``is_routing_active_for``
     / ``routing_active_for``) is ALREADY SHIPPED but Tsunami-confirmed
     UNWIRED (zero production call sites) -- none of the 3 seams
     (``_maybe_route_through_registered_{e2e,density}_adapter`` above, PLUS
     ``des.cli.run_contract_gate._maybe_route_through_registered_contract_gate``)
     consult it today. Slice-04a wires all 3: ``if
     is_routing_active_for(repo): emit-skip; return None`` before entering
     ``with routing_active_for(repo): ...``.

Why this is a SINGLE `@coupled` vertical, ONE test file, not 3: the feature-
delta's justification is that entry-points ALONE crashes every Python/TS
target (defect 2, ADR-ULAR-005 Context), and entry-points + seam-catch
WITHOUT the reentrancy guard reproduces the 8-nested-pytest/22-minute-kill
failure on any self-dogfooding target (defect 3, ADR-ULAR-004 Context) -- no
2-of-3 subset is safely shippable. Each scenario below witnesses exactly one
FACET of this one root cause (entry-points flipping ``facet`` from always-
``None`` to real).

Active-RED scaffolding: NONE of the touched symbols are CREATE_NEW (every
module/function already exists and imports cleanly) -- the RED-ness is
BEHAVIORAL (a function that crashes today, or a config table missing two
rows), never a missing-symbol ``ImportError``. Scenario 1 fails today at a
plain semantic ``AssertionError`` (the pyproject rows are absent). Scenarios
2-7 fail today because the seam either crashes (uncaught
``NotImplementedError``) or invokes the facet it should have skipped (an
uncaught sentinel ``RuntimeError`` proving the call happened) -- captured as a
child-process marker, never a raw traceback leaking into this process.

CRITICAL test-mechanism note (per the dispatch's explicit guidance):
``importlib.metadata.entry_points()`` reads the INSTALLED ``.dist-info`` --
editing ``pyproject.toml`` does NOT change it live without a reinstall.
Scenario 1 therefore NEVER depends on -- or mutates -- the live editable
install: it (a) asserts the two new rows exist as TEXT in ``pyproject.toml``
(the RED witness for defect 1, a plain source-of-truth read, no reinstall
needed) and (b) separately monkeypatches
``des.testarch.port_realization_discovery.metadata.entry_points`` in-process
(pytest ``monkeypatch``, this process only -- ``port_realization_discovery``
never touches ``GLOBAL_REGISTRY``, so no subprocess isolation is required
here) to prove the DEFAULT (``discovery_source=None``) discovery path finds
both plugins once they are visible under the group, closing the exact gap
slice-03's own AT explicitly left out of scope ("python/typescript are
deliberately NOT yet wired there, out of this feature's scope").

Scenarios 2-7 (the seam-catch + reentrancy-guard witnesses) instead drive a
FRESH CHILD interpreter per scenario (mirrors the sibling
``unified-language-adapter-registry`` slice-02 precedent,
``tests/des/acceptance/unified_language_adapter_registry/steps/composition.py``:
"isolation is structural, not fixture-managed") -- ``GLOBAL_REGISTRY`` is a
process-scoped module-level singleton; mutating it in THIS test process would
leak registrations across tests and pollute the rest of the suite. Each child
(a) registers the REAL shipped ``NwaveLangPython`` plugin's facets (or a
call-counting/exception-raising fixture double for the negative reentrancy
witnesses) into its OWN fresh ``GLOBAL_REGISTRY``, then (b) calls the exact
private seam function under test directly -- the composition-root function
itself IS the driving port for this slice (Mandate-13), matching
``test_port_realization_discovery.py``'s own precedent of calling
``resolve_and_probe_port_realization`` directly.

Driving surface (Mandate-13 driving-port-only): scenario 1 is Layer 3
composition (in-process, `@in-memory`, the composition-root gate-runner
function called directly with an injected/monkeypatched discovery source).
Scenarios 2-7 are Layer 3 subprocess (`@real-io @subprocess`, a REAL child
interpreter), each driving one of the 3 already-shipped seam functions
directly, the same "composition-root function IS the driving port" pattern
one process boundary over (the subprocess exists ONLY for ``GLOBAL_REGISTRY``
isolation, never to route around a missing symbol).

CONTRACT_SHAPE: scenario 1 is unbounded-preservation (a read-only inspection,
no state mutation, mirrors the sibling CLI file's classification). Scenarios
2-7 are bounded-change (each turns an uncaught crash / an unguarded facet
invocation into a specific, bounded fallback -- ``return None`` -- never a
new class of failure).

Negative ATs (GS-8, `@pytest.mark.negative_at`): scenarios 5 ("real-adapter
still propagates" -- the WRONG outcome, a swallowed genuine
``RunnerAdapterUnavailable``, must NOT be produced) and 6-7-8... wait, see the
per-scenario markers below (the reentrancy-bounded scenarios assert the
WRONG outcome -- the facet actually being invoked while the guard is held --
is NOT produced).

Tag: `@coupled` (feature-delta Slice Plan slice-04a).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[4]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

# ---------------------------------------------------------------------------
# Design pins (feature-delta [REF] Architecture & Contract -- slice-04a): the
# EXACT two entry-points rows slice-04a adds, verbatim.
# ---------------------------------------------------------------------------

_ENTRY_POINTS_HEADER = '[project.entry-points."nwave.lang.adapter"]'
_PYTHON_ENTRY_ROW = (
    'nwave-lang-python = "scripts.install.plugins.nwave_lang_python:NwaveLangPython"'
)
_TYPESCRIPT_ENTRY_ROW = (
    "nwave-lang-typescript = "
    '"scripts.install.plugins.nwave_lang_typescript:NwaveLangTypescript"'
)
_PYTHON_ENTRY_VALUE = "scripts.install.plugins.nwave_lang_python:NwaveLangPython"
_TYPESCRIPT_ENTRY_VALUE = (
    "scripts.install.plugins.nwave_lang_typescript:NwaveLangTypescript"
)
_CHECK_PORT_REALIZATION_FLAG = "--check-port-realization"

VERIFY_ENVIRONMENTAL_E2E = "verify_environmental_e2e"
CHECK_ROBUSTNESS_DENSITY = "check_robustness_density"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _entry_points_block_text() -> str:
    """Return the raw text of the ``nwave.lang.adapter`` entry-points TABLE.

    Plain text slice between the table header and the next ``[`` header --
    deliberately NOT a TOML parse (``tomllib`` needs 3.11+; this repo floors
    at 3.10, and a text slice is sufficient + hermetic for a literal-row
    presence check).
    """
    text = _PYPROJECT.read_text(encoding="utf-8")
    header_index = text.find(_ENTRY_POINTS_HEADER)
    assert header_index != -1, (
        f"MISSING_FUNCTIONALITY: {_ENTRY_POINTS_HEADER!r} not found in "
        f"{_PYPROJECT} at all."
    )
    body_start = header_index + len(_ENTRY_POINTS_HEADER)
    next_header = text.find("\n[", body_start)
    return text[body_start : next_header if next_header != -1 else len(text)]


def _run_child(program: str) -> subprocess.CompletedProcess[str]:
    """Drive a FRESH child interpreter (structural ``GLOBAL_REGISTRY`` isolation)."""
    return subprocess.run(
        [sys.executable, "-c", program],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _python_target_repo(tmp_path: Path) -> Path:
    """A minimal real target repo that resolves the ``pytest`` runner token."""
    repo = tmp_path / "python-target"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "fixture-target"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    return repo


# ---------------------------------------------------------------------------
# Scenario 1 -- entry-point registration (defect 1) + default discovery sees
# both plugins and FAILS LOUD on their 4 stub-backed ports.
# @in-memory
# CONTRACT_SHAPE: unbounded-preservation
# ---------------------------------------------------------------------------


def test_pyproject_registers_python_and_typescript_entry_points_and_default_discovery_flags_both(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: feature-delta Slice Plan slice-04a + [REF] Architecture &
    Contract -- slice-04a ("Entry-point registration").

    Part A (the RED witness for defect 1, a plain source read -- no
    reinstall, no live registry): ``pyproject.toml``'s
    ``[project.entry-points."nwave.lang.adapter"]`` table must contain both
    the ``nwave-lang-python`` and ``nwave-lang-typescript`` rows, verbatim.
    TODAY only ``_conformance_fixture``/``nwave-lang-rust`` are registered --
    this assertion fails first, for the right (semantic) reason.

    Part B (closes the exact gap slice-03's own AT left out of scope):
    monkeypatching ``des.testarch.port_realization_discovery``'s
    ``metadata.entry_points`` to reflect what Part A just confirmed
    ``pyproject.toml`` declares, the DEFAULT (``discovery_source=None``)
    ``--check-port-realization`` gate-runner must discover BOTH plugins and
    FAIL LOUD (exit 1) naming both plugins and all 4 stub-backed offenders --
    the contrast to today's live-registry T1 in
    ``test_check_port_realization_cli.py`` (exit 0, only the fixture +
    honest rust plugin registered).
    """
    block = _entry_points_block_text()
    assert _PYTHON_ENTRY_ROW in block, (
        f"MISSING_FUNCTIONALITY: pyproject.toml's "
        f"{_ENTRY_POINTS_HEADER!r} table does not yet declare "
        f"{_PYTHON_ENTRY_ROW!r} (feature-delta slice-04a). block={block!r}"
    )
    assert _TYPESCRIPT_ENTRY_ROW in block, (
        f"MISSING_FUNCTIONALITY: pyproject.toml's "
        f"{_ENTRY_POINTS_HEADER!r} table does not yet declare "
        f"{_TYPESCRIPT_ENTRY_ROW!r} (feature-delta slice-04a). block={block!r}"
    )
    assert re.search(
        rf"Re-check with.*{re.escape(_CHECK_PORT_REALIZATION_FLAG)}",
        _PYPROJECT.read_text(encoding="utf-8"),
    ), (
        "MISSING_FUNCTIONALITY: expected a GDP-2 inline breadcrumb comment "
        f"('Re-check with: ... {_CHECK_PORT_REALIZATION_FLAG}') above the "
        "entry-points block (feature-delta slice-04a)."
    )

    from importlib.metadata import EntryPoint

    from des.testarch import port_realization_discovery as discovery_mod

    fake_entry_points = (
        EntryPoint(
            name="nwave-lang-python",
            value=_PYTHON_ENTRY_VALUE,
            group="nwave.lang.adapter",
        ),
        EntryPoint(
            name="nwave-lang-typescript",
            value=_TYPESCRIPT_ENTRY_VALUE,
            group="nwave.lang.adapter",
        ),
    )

    def _fake_entry_points(*, group: str | None = None) -> tuple[EntryPoint, ...]:
        return fake_entry_points if group == "nwave.lang.adapter" else ()

    monkeypatch.setattr(discovery_mod.metadata, "entry_points", _fake_entry_points)

    from scripts.cli.validate_language_adapter_catalog import (
        run_port_realization_gate,
    )

    exit_code = run_port_realization_gate(None)

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exit_code == 1, (
        f"expected the GAP lane -- both plugins are visible under the "
        f"(monkeypatched) group and both declare 2 stub-backed ports -- got "
        f"exit {exit_code}. output={combined_output!r}"
    )
    for plugin_id in ("python", "typescript"):
        for port in (VERIFY_ENVIRONMENTAL_E2E, CHECK_ROBUSTNESS_DENSITY):
            assert plugin_id in combined_output and port in combined_output, (
                f"expected offender ({plugin_id}, {port}) named in the "
                f"default-discovery FAIL-LOUD output: {combined_output!r}"
            )


# ---------------------------------------------------------------------------
# Scenario 2 -- ADR-ULAR-005 seam-catch: the environmental-e2e seam, given a
# REGISTERED STUB facet, falls through to None instead of crashing.
# @real-io @subprocess
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_environmental_e2e_seam_falls_through_without_crashing_on_a_registered_stub_facet(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: feature-delta [REF] Architecture & Contract -- slice-04a
    (ADR-ULAR-005 seam-catch, ``verify_environmental_e2e.py``
    ``_maybe_route_through_registered_e2e_adapter``, unguarded calls at
    lines 101/103/105).

    Registering the REAL shipped ``NwaveLangPython`` plugin's facets (whose
    ``PythonEnvironmentalE2EAdapter.build`` is a pure
    ``raise NotImplementedError`` stub, the feature-delta's verified smoking
    gun) and invoking the seam on a Python-resolving target must return
    ``None`` -- TODAY it crashes with an uncaught ``NotImplementedError``.
    """
    repo = _python_target_repo(tmp_path)
    program = f"""
import importlib
from pathlib import Path

plugin_mod = importlib.import_module("scripts.install.plugins.nwave_lang_python")
registry_mod = importlib.import_module("des.adapters.driven.runner.runner_registry")
plugin_mod.NwaveLangPython().register_adapters(registry_mod.GLOBAL_REGISTRY)

seam_mod = importlib.import_module("des.cli.verify_environmental_e2e")
repo = Path({str(repo)!r})
try:
    result = seam_mod._maybe_route_through_registered_e2e_adapter(
        repo, repo / "e2e_spec.py"
    )
    print("SEAM_RESULT:" + repr(result))
except NotImplementedError as exc:
    print("SEAM_CRASHED:" + str(exc))
"""
    completed = _run_child(program)
    combined_output = completed.stdout + completed.stderr

    assert "SEAM_RESULT:None" in completed.stdout, (
        f"expected the seam to fall through to None on a registered stub "
        f"facet, never crash: {combined_output!r}"
    )
    assert "SEAM_CRASHED" not in combined_output, (
        f"the seam must never let a registered stub facet's "
        f"NotImplementedError escape uncaught: {combined_output!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 3 -- ADR-ULAR-005 seam-catch: the robustness-density seam, given a
# REGISTERED STUB facet, falls through to None instead of crashing.
# @real-io @subprocess
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_robustness_density_seam_falls_through_without_crashing_on_a_registered_stub_facet(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: feature-delta [REF] Architecture & Contract -- slice-04a
    (ADR-ULAR-005 seam-catch, ``check_robustness_density.py``
    ``_maybe_route_through_registered_density_adapter``, unguarded call at
    line 218).

    Registering the REAL shipped ``NwaveLangPython`` plugin's facets (whose
    ``PythonRobustnessDensityAdapter.covered_domain_ids`` is a pure
    ``raise NotImplementedError`` stub) and invoking the seam on a
    Python-resolving target must return ``None`` -- TODAY it crashes with an
    uncaught ``NotImplementedError``.
    """
    repo = _python_target_repo(tmp_path)
    program = f"""
import importlib
from pathlib import Path

plugin_mod = importlib.import_module("scripts.install.plugins.nwave_lang_python")
registry_mod = importlib.import_module("des.adapters.driven.runner.runner_registry")
plugin_mod.NwaveLangPython().register_adapters(registry_mod.GLOBAL_REGISTRY)

seam_mod = importlib.import_module("scripts.cli.check_robustness_density")
repo = Path({str(repo)!r})
try:
    result = seam_mod._maybe_route_through_registered_density_adapter(repo)
    print("SEAM_RESULT:" + repr(result))
except NotImplementedError as exc:
    print("SEAM_CRASHED:" + str(exc))
"""
    completed = _run_child(program)
    combined_output = completed.stdout + completed.stderr

    assert "SEAM_RESULT:None" in completed.stdout, (
        f"expected the seam to fall through to None on a registered stub "
        f"facet, never crash: {combined_output!r}"
    )
    assert "SEAM_CRASHED" not in combined_output, (
        f"the seam must never let a registered stub facet's "
        f"NotImplementedError escape uncaught: {combined_output!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 4 -- NEGATIVE AT: the seam-catch is NotImplementedError-specific,
# never a blanket except -- a genuine RunnerAdapterUnavailable from a REAL
# (non-stub) registered contract-gate facet must still propagate.
# @real-io @subprocess
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_contract_gate_seam_still_propagates_a_genuine_runner_adapter_unavailable(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: feature-delta [REF] Architecture & Contract -- slice-04a
    (contract-gate seam gains ONLY the reentrancy-guard wrap, "no
    NotImplementedError catch needed here, PythonContractGateAdapter/
    VitestContractGateAdapter are REAL implementations, not stubs").

    Negative AT (GS-8): asserts the WRONG outcome -- a genuine
    ``RunnerAdapterUnavailable`` raised by a REAL (non-stub) registered
    facet being silently swallowed -- is NOT produced. A fixture facet
    deliberately raises it; the seam must let it propagate uncaught, proving
    slice-04a never widens the catch into a blanket ``except``.
    """
    repo = _python_target_repo(tmp_path)
    program = f"""
import importlib
from pathlib import Path

registry_mod = importlib.import_module("des.adapters.driven.runner.runner_registry")
ports_mod = importlib.import_module("des.ports.test_runner_port")


class _FixtureUnavailableContractGateFacet:
    def collect_scope(self, repo):
        return []

    def run_suite(self, repo):
        raise ports_mod.RunnerAdapterUnavailable(
            "pytest", "fixture: genuine (non-stub) adapter failure"
        )


registry_mod.GLOBAL_REGISTRY.register_contract_gate(
    "pytest", _FixtureUnavailableContractGateFacet()
)

gate_mod = importlib.import_module("des.cli.run_contract_gate")
repo = Path({str(repo)!r})
try:
    result = gate_mod._maybe_route_through_registered_contract_gate(repo)
    print("SEAM_RESULT:" + repr(result))
except ports_mod.RunnerAdapterUnavailable as exc:
    print("SEAM_PROPAGATED:" + str(exc))
"""
    completed = _run_child(program)
    combined_output = completed.stdout + completed.stderr

    assert "SEAM_PROPAGATED:" in completed.stdout, (
        f"expected the genuine RunnerAdapterUnavailable to propagate "
        f"uncaught -- the seam-catch must be NotImplementedError-specific, "
        f"never a blanket except: {combined_output!r}"
    )
    assert "SEAM_RESULT:" not in completed.stdout, (
        f"a genuine (non-stub) adapter failure must never be silently "
        f"swallowed into a routed result: {combined_output!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 5 -- NEGATIVE AT: reentrancy-guard bounded -- the contract-gate
# seam, when routing is already active for the SAME repo, skips (LOUD) and
# returns None instead of invoking the facet (never recurses).
# @real-io @subprocess
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_contract_gate_seam_skips_instead_of_recursing_when_routing_already_active(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: feature-delta [REF] Architecture & Contract -- slice-04a
    (ADR-ULAR-004 reentrancy-guard arming,
    ``_maybe_route_through_registered_contract_gate``, guard wrap around the
    facet lookup at line 2340 / call at line 2343).

    Negative AT (GS-8): asserts the WRONG outcome -- the facet actually
    being INVOKED while routing is already active for the SAME repo (the
    unbounded-recursion failure mode ADR-ULAR-004 exists to prevent) -- is
    NOT produced. A call-counting fixture facet proves zero invocations;
    TODAY the guard is unwired so the facet IS called (the sentinel fires).
    """
    repo = _python_target_repo(tmp_path)
    program = f"""
import importlib
from pathlib import Path

registry_mod = importlib.import_module("des.adapters.driven.runner.runner_registry")
guard_mod = importlib.import_module("des.adapters.driven.runner.reentrancy_guard")

calls = []


class _CallCountingContractGateFacet:
    def collect_scope(self, repo):
        return []

    def run_suite(self, repo):
        calls.append("run_suite-was-called")
        raise RuntimeError("SENTINEL: must never be invoked while guard active")


registry_mod.GLOBAL_REGISTRY.register_contract_gate(
    "pytest", _CallCountingContractGateFacet()
)

gate_mod = importlib.import_module("des.cli.run_contract_gate")
repo = Path({str(repo)!r})
try:
    with guard_mod.routing_active_for(repo):
        result = gate_mod._maybe_route_through_registered_contract_gate(repo)
    print("SEAM_RESULT:" + repr(result))
except RuntimeError as exc:
    print("SENTINEL_TRIGGERED:" + str(exc))
print("CALLS:" + str(len(calls)))
"""
    completed = _run_child(program)
    combined_output = completed.stdout + completed.stderr

    assert "SEAM_RESULT:None" in completed.stdout, (
        f"expected the seam to skip (return None) instead of invoking the "
        f"facet while routing is already active: {combined_output!r}"
    )
    assert "CALLS:0" in completed.stdout, (
        f"the facet must never be invoked while the guard is active for the "
        f"SAME repo: {combined_output!r}"
    )
    assert "SENTINEL_TRIGGERED" not in combined_output, (
        f"the facet's sentinel must never fire -- it must never be called: "
        f"{combined_output!r}"
    )
    assert re.search(
        r"reentran|routing.{0,30}active|skip", combined_output, re.IGNORECASE
    ), (
        f"expected a LOUD skip advisory naming the reentrancy skip (GDP-3): "
        f"{combined_output!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 6 -- NEGATIVE AT: reentrancy-guard bounded -- the environmental-e2e
# seam skips instead of recursing when routing is already active.
# @real-io @subprocess
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_environmental_e2e_seam_skips_instead_of_recursing_when_routing_already_active(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: feature-delta [REF] Architecture & Contract -- slice-04a
    (ADR-ULAR-004 reentrancy-guard arming applied to
    ``_maybe_route_through_registered_e2e_adapter``, the SAME guard wrap
    around its try/except-wrapped facet invocation block).

    Negative AT (GS-8): asserts the WRONG outcome -- the facet actually
    being invoked while routing is already active -- is NOT produced.
    """
    repo = _python_target_repo(tmp_path)
    program = f"""
import importlib
from pathlib import Path

registry_mod = importlib.import_module("des.adapters.driven.runner.runner_registry")
guard_mod = importlib.import_module("des.adapters.driven.runner.reentrancy_guard")

calls = []


class _CallCountingE2EFacet:
    def build(self, feature_root):
        calls.append("build-was-called")
        raise RuntimeError("SENTINEL: must never be invoked while guard active")

    def install(self, artifact, prefix):
        calls.append("install-was-called")
        raise RuntimeError("SENTINEL: must never be invoked while guard active")

    def run_against_installed(self, e2e_path, prefix, junit_path, work_dir):
        calls.append("run_against_installed-was-called")
        raise RuntimeError("SENTINEL: must never be invoked while guard active")


registry_mod.GLOBAL_REGISTRY.register_environmental_e2e(
    "pytest", _CallCountingE2EFacet()
)

seam_mod = importlib.import_module("des.cli.verify_environmental_e2e")
repo = Path({str(repo)!r})
try:
    with guard_mod.routing_active_for(repo):
        result = seam_mod._maybe_route_through_registered_e2e_adapter(
            repo, repo / "e2e_spec.py"
        )
    print("SEAM_RESULT:" + repr(result))
except RuntimeError as exc:
    print("SENTINEL_TRIGGERED:" + str(exc))
print("CALLS:" + str(len(calls)))
"""
    completed = _run_child(program)
    combined_output = completed.stdout + completed.stderr

    assert "SEAM_RESULT:None" in completed.stdout, (
        f"expected the seam to skip (return None) instead of invoking the "
        f"facet while routing is already active: {combined_output!r}"
    )
    assert "CALLS:0" in completed.stdout, (
        f"the facet must never be invoked while the guard is active for the "
        f"SAME repo: {combined_output!r}"
    )
    assert "SENTINEL_TRIGGERED" not in combined_output, (
        f"the facet's sentinel must never fire -- it must never be called: "
        f"{combined_output!r}"
    )
    assert re.search(
        r"reentran|routing.{0,30}active|skip", combined_output, re.IGNORECASE
    ), (
        f"expected a LOUD skip advisory naming the reentrancy skip (GDP-3): "
        f"{combined_output!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 7 -- NEGATIVE AT: reentrancy-guard bounded -- the
# robustness-density seam skips instead of recursing when routing is already
# active.
# @real-io @subprocess
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_robustness_density_seam_skips_instead_of_recursing_when_routing_already_active(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: feature-delta [REF] Architecture & Contract -- slice-04a
    (ADR-ULAR-004 reentrancy-guard arming applied to
    ``_maybe_route_through_registered_density_adapter``, the SAME guard wrap
    around its try/except-wrapped facet invocation block).

    Negative AT (GS-8): asserts the WRONG outcome -- the facet actually
    being invoked while routing is already active -- is NOT produced.
    """
    repo = _python_target_repo(tmp_path)
    program = f"""
import importlib
from pathlib import Path

registry_mod = importlib.import_module("des.adapters.driven.runner.runner_registry")
guard_mod = importlib.import_module("des.adapters.driven.runner.reentrancy_guard")

calls = []


class _CallCountingDensityFacet:
    def covered_domain_ids(self, at_scope_dir):
        calls.append("covered_domain_ids-was-called")
        raise RuntimeError("SENTINEL: must never be invoked while guard active")


registry_mod.GLOBAL_REGISTRY.register_robustness_density(
    "pytest", _CallCountingDensityFacet()
)

seam_mod = importlib.import_module("scripts.cli.check_robustness_density")
repo = Path({str(repo)!r})
try:
    with guard_mod.routing_active_for(repo):
        result = seam_mod._maybe_route_through_registered_density_adapter(repo)
    print("SEAM_RESULT:" + repr(result))
except RuntimeError as exc:
    print("SENTINEL_TRIGGERED:" + str(exc))
print("CALLS:" + str(len(calls)))
"""
    completed = _run_child(program)
    combined_output = completed.stdout + completed.stderr

    assert "SEAM_RESULT:None" in completed.stdout, (
        f"expected the seam to skip (return None) instead of invoking the "
        f"facet while routing is already active: {combined_output!r}"
    )
    assert "CALLS:0" in completed.stdout, (
        f"the facet must never be invoked while the guard is active for the "
        f"SAME repo: {combined_output!r}"
    )
    assert "SENTINEL_TRIGGERED" not in combined_output, (
        f"the facet's sentinel must never fire -- it must never be called: "
        f"{combined_output!r}"
    )
    assert re.search(
        r"reentran|routing.{0,30}active|skip", combined_output, re.IGNORECASE
    ), (
        f"expected a LOUD skip advisory naming the reentrancy skip (GDP-3): "
        f"{combined_output!r}"
    )

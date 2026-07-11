"""Acceptance tests -- ``--check-port-realization`` CLI mode (DISTILL, slice-03).

Feature-delta: docs/feature/language-port-realization-gate/feature-delta.md
  Wave: DESIGN / [REF] Architecture & Contract + [REF] Slice Plan (slice-03)

Contract under test (DOES NOT EXIST YET -- active-RED by design):
``scripts/cli/validate_language_adapter_catalog.py`` gains a new
``--check-port-realization`` mode reusing the existing exit-lane contract
(``0`` conformant / ``1`` gap / ``3`` INDETERMINATE, mirroring
``--check-conformance``): it drives slice-02's ``port_realization_discovery``
composition root over the registered ``nwave.lang.adapter`` plugins and
FAIL-LOUDs one block per stub-backed-but-declared-True port, naming WHAT
(port + stub method @file:line), the Protocol/interface to implement, the
adapter file, and the HOW re-check command (GDP-3/4).

Design pin this AT establishes (necessary because no prior slice fixed it,
mirroring the DDD-D6 pattern ``run_conformance_gate`` already uses in this
same CLI module): the new mode's composition-root gate-runner is
``run_port_realization_gate(discovery_source=None) -> int``, where
``discovery_source`` is ONE of:

  * ``None`` -- read the live registry (``entry_points(group=
    "nwave.lang.adapter")``) and resolve-and-probe it (T1 below).
  * an iterable of ``LanguageAdapterPlugin`` instances -- the injected
    plugins to AST-stub-probe directly (mirrors slice-02's own
    ``resolve_and_probe_port_realization(plugins)`` signature exactly; T2-T4
    below drive the REAL shipped ``NwaveLangPython``/``NwaveLangTypescript``
    instances this way).
  * an iterable of ``EntryPoint`` -- raw entry points to resolve+probe (the
    unresolvable corpus drives the exit-3 loud lane, T5 below).

FACTUAL CORRECTION established by reading the live registry before authoring
(``importlib.metadata.entry_points(group="nwave.lang.adapter")`` at HEAD):
only ``_conformance_fixture`` (``port_coverage == {}``, vacuously conformant)
and ``nwave-lang-rust`` (declares only ``test-runner=True``, genuinely
implemented) are REGISTERED today. ``NwaveLangPython``/``NwaveLangTypescript``
are NOT wired into ``pyproject.toml``'s ``nwave.lang.adapter`` entry-points
group -- that wiring is explicitly OUT of this feature's scope (slice-04's
value statement only adds a breadcrumb comment + the pre-push/CI gate, never
the python/typescript registration itself; see the feature-delta's closing
NOTE about a separate, awaiting-Ale re-slice of a DIFFERENT feature's
registration slice). So the REAL LIVE registry is honestly CONFORMANT today
(T1) -- the "real already-shipped lie" smoking gun the feature-delta's
Summary describes is reachable ONLY by injecting the real plugin instances
directly (T2-T4), exactly mirroring how slice-02's own AT bypasses
``entry_points`` (see ``test_port_realization_discovery.py``'s docstring:
"entry-point registration NOT required"). This is NOT a weaker test than the
feature intends -- it is the same "reads adapter source directly" seam
slice-02 already established, one composition layer up.

Active-RED scaffolding (hidden-import P1-P4, ``nw-distill-red-scaffolding``):
the whole ``run_port_realization_gate`` symbol is CREATE_NEW on an existing
module (``scripts/cli/validate_language_adapter_catalog.py`` already exists
and imports cleanly) -- so T2-T5 defer the symbol lookup to CALL TIME inside
``_load_gate_runner()``, catching ``ImportError``/``AttributeError`` and
re-raising a semantic ``AssertionError`` (MISSING_FUNCTIONALITY). T1 and T6
need no hidden import at all -- they drive the REAL CLI as a subprocess
(the ``--check-port-realization`` flag is simply unrecognized today, which
already RED-fails their assertions for a semantic reason: T1 expects exit 0,
today's unrecognized-flag path raises ``FileNotFoundError`` trying to open a
catalog literally named ``--check-port-realization`` -> exit 1; T6 expects
the flag documented in usage, which it is not).

Driving surface (Mandate-13 driving-port-only): T1 + T6 drive the real CLI
via subprocess (Layer 3 subprocess, ``@real-io @subprocess``); T2-T5 drive
the composition-root gate-runner directly with injected sources (Layer 3
composition, ``@in-memory`` for T5's raw ``EntryPoint`` corpus and T2-T4's
real-plugin-instance corpus alike -- neither touches the live registry or
performs file I/O beyond ``inspect.getsource`` on already-imported classes).
No C1 (``registry_conformance``) or C2 (``port_realization_discovery``)
domain function is called directly by these tests -- only the CLI-level
gate-runner (the composition root), matching the sibling
``ConformanceGateService`` precedent
(``tests/build/language_adapter_registry_self_enforcement/acceptance/steps/conformance_gate_composition.py``).

CONTRACT_SHAPE: unbounded-preservation for every scenario -- the gate is a
read-only inspection (no state mutation); the exit code + printed diagnostic
are the port-exposed observables.

Vera examine findings pinned here (post-A_GREEN, this file EXTENDED to
RED-witness the deviations -- production code NOT touched by this change):

1. **Exit-0 silence.** The real CLI's ``--check-port-realization`` mode
   exits 0 over the live registry with ZERO stdout. T1 is STRENGTHENED to
   assert a truthful non-empty summary (the conformant outcome named + a
   count of plugins/ports probed) -- exit-0 must never be silent.
2. **Silent skip of unknown declared ports.** ``nwave-lang-rust`` declares
   ``port_coverage["test-runner"] = True``; ``test-runner`` sits OUTSIDE the
   3-port probe catalog and today is silently ``continue``d
   (``resolve_and_probe_port_realization_with_detail``). T1b pins that the
   out-of-catalog declared port is VISIBLY noted (plugin + port named,
   marked not-probed) while STILL exiting 0 -- it is not a gap, but silence
   is also wrong.
3. **No CLI probing surface for a specific/unregistered plugin.** The
   founder's core surface ("I add C# and the failures tell me what to
   implement") has no CLI entry point today -- ``run_port_realization_gate``
   already accepts an injected ``Iterable[LanguageAdapterPlugin]`` (T2-T4
   drive it in-process), but the real CLI's ``main()`` ignores any argv
   beyond the mode flag. T7/T8 pin a repeatable ``--plugin <module>:<Class>``
   flag on ``--check-port-realization`` that loads the named plugin
   class(es) and probes THEM directly (T7: the real shipped liar plugins,
   exit 1 GAP with all 4 offenders + full anatomy; T8: an unresolvable
   target, exit 3 INDETERMINATE, no raw traceback).
"""

from __future__ import annotations

import re
import subprocess
import sys
from importlib.metadata import EntryPoint
from pathlib import Path

import pytest

from tests.build.language_port_realization_gate.acceptance.synthetic_language_adapter_fixtures import (
    SyntheticLiarLanguageAdapterPluginCSharp,
    SyntheticLiarLanguageAdapterPluginKotlin,
)


_REPO_ROOT = Path(__file__).resolve().parents[4]

# Test-brittleness fix (#92): the gap-lane scenarios (T2/T3/T4/T7) originally
# drove the REAL shipped `NwaveLangPython`/`NwaveLangTypescript` plugins,
# pinning the "registered-but-stub-backed" premise to nWave-dev's OWN,
# mutable adapter state. Once `implement-language-adapter-facets` genuinely
# implemented those facets, the premise silently went false and the gate no
# longer flagged them -- the ATs failed for a STALE reason, not a regression.
# The gap-lane scenarios now drive two CONTROLLED synthetic liar plugins
# (`SyntheticLiarLanguageAdapterPlugin{CSharp,Kotlin}`), whose stub-state is
# fixed by the fixture, never by the live repo. T1/T1b keep asserting the
# REAL live registry is CONFORMANT -- that is a genuine, desirable guard
# ("nWave-dev's own registry never lies"), stable precisely because the
# shipped facets are real.
_SYNTHETIC_FIXTURES_MODULE = (
    "tests.build.language_port_realization_gate.acceptance."
    "synthetic_language_adapter_fixtures"
)
_SYNTHETIC_FIXTURES_FILE = (
    "tests/build/language_port_realization_gate/acceptance/"
    "synthetic_language_adapter_fixtures.py"
)
_CSHARP_PLUGIN_TARGET = (
    f"{_SYNTHETIC_FIXTURES_MODULE}:SyntheticLiarLanguageAdapterPluginCSharp"
)
_KOTLIN_PLUGIN_TARGET = (
    f"{_SYNTHETIC_FIXTURES_MODULE}:SyntheticLiarLanguageAdapterPluginKotlin"
)

# --- the 3 ports in scope (LanguageAdapterPlugin.port_coverage) ------------

RUN_CONTRACT_GATE = "run_contract_gate"
VERIFY_ENVIRONMENTAL_E2E = "verify_environmental_e2e"
CHECK_ROBUSTNESS_DENSITY = "check_robustness_density"

_CHECK_PORT_REALIZATION_FLAG = "--check-port-realization"

# WHY -- the file whose bodies are pure `raise NotImplementedError` stubs for
# the two declared-but-lying ports. With the brittleness fix, BOTH the
# environmental-e2e and robustness-density stubs live in the ONE synthetic
# fixtures module (repo-relative, matching how the catalog CLI reports
# `witnesses:` paths). Every synthetic liar plugin's gaps resolve to it.
_ADAPTER_FILE_BY_PLUGIN_PORT = {
    ("csharp", VERIFY_ENVIRONMENTAL_E2E): _SYNTHETIC_FIXTURES_FILE,
    ("csharp", CHECK_ROBUSTNESS_DENSITY): _SYNTHETIC_FIXTURES_FILE,
    ("kotlin", VERIFY_ENVIRONMENTAL_E2E): _SYNTHETIC_FIXTURES_FILE,
    ("kotlin", CHECK_ROBUSTNESS_DENSITY): _SYNTHETIC_FIXTURES_FILE,
}

# HOW -- the Protocol each stub-backed port must implement (feature-delta:
# "the exact Protocol/file to implement").
_PROTOCOL_BY_PORT = {
    VERIFY_ENVIRONMENTAL_E2E: "EnvironmentalE2EPort",
    CHECK_ROBUSTNESS_DENSITY: "RobustnessDensityPort",
}

# WHAT -- at least one of these method names must be cited for the port. The
# port's declared-covered surface AST-probes ALL of its Protocol's methods;
# `EnvironmentalE2EPort` has 3 (build/install/run_against_installed), all
# stubs, `RobustnessDensityPort` has 1 (covered_domain_ids). WHICH method the
# CLI cites among a multi-method port's several stubs is a slice-03
# implementation detail this AT deliberately does not over-pin -- it only
# requires that a REAL stub method name from the port's surface is named.
_CANDIDATE_STUB_METHODS_BY_PORT = {
    VERIFY_ENVIRONMENTAL_E2E: ("build", "install", "run_against_installed"),
    CHECK_ROBUSTNESS_DENSITY: ("covered_domain_ids",),
}

_ALL_GAP_PAIRS = tuple(_ADAPTER_FILE_BY_PLUGIN_PORT.keys())


# ---------------------------------------------------------------------------
# Driving-port helpers
# ---------------------------------------------------------------------------


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Drive the REAL CLI as a subprocess (Layer 3 subprocess)."""
    return subprocess.run(
        [sys.executable, "-m", "scripts.cli.validate_language_adapter_catalog", *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _load_gate_runner():
    """Hidden-import (P1-P4): defer the missing symbol lookup to CALL time.

    ``scripts/cli/validate_language_adapter_catalog.py`` ALREADY EXISTS and
    imports cleanly (it hosts ``run_conformance_gate`` + the catalog-schema
    mode) -- only ``run_port_realization_gate`` is absent. A module-top
    ``from scripts.cli.validate_language_adapter_catalog import
    run_port_realization_gate`` would fail COLLECTION -> BROKEN, which
    ``des verify-red-green`` refuses. So the lookup happens here, at CALL
    time, re-raised as a semantic ``AssertionError`` (MISSING_FUNCTIONALITY)
    -- active-RED, never BROKEN.
    """
    try:
        from scripts.cli.validate_language_adapter_catalog import (
            run_port_realization_gate,
        )
    except ImportError as exc:
        raise AssertionError(
            "MISSING_FUNCTIONALITY: scripts/cli/validate_language_adapter_catalog.py "
            "does not yet define `run_port_realization_gate` (feature-delta slice-03, "
            "docs/feature/language-port-realization-gate/feature-delta.md [REF] "
            "Architecture & Contract). Add `run_port_realization_gate(discovery_source"
            "=None) -> int` mirroring `run_conformance_gate`'s DDD-D6 discovery-source "
            "parameter: `None` reads the live `nwave.lang.adapter` registry; an "
            "iterable of `LanguageAdapterPlugin` instances is AST-stub-probed "
            "directly (mirrors slice-02's `resolve_and_probe_port_realization`); an "
            "iterable of `EntryPoint` is resolved+probed (drives the exit-3 loud "
            "lane on an unresolvable target). Wire `main()` to dispatch "
            f"`{_CHECK_PORT_REALIZATION_FLAG}` into it before this AT can pass. "
            f"Re-check with: python -m scripts.cli.validate_language_adapter_catalog "
            f"{_CHECK_PORT_REALIZATION_FLAG}. Root cause: {exc}"
        ) from exc
    return run_port_realization_gate


def _gap_offenders(combined_output: str) -> set[tuple[str, str]]:
    """Which (plugin_id, port) pairs does the combined stdout+stderr name?"""
    return {
        (plugin_id, port)
        for plugin_id in ("csharp", "kotlin")
        for port in (VERIFY_ENVIRONMENTAL_E2E, CHECK_ROBUSTNESS_DENSITY)
        if plugin_id in combined_output and port in combined_output
    }


# ---------------------------------------------------------------------------
# T1 -- the real CLI, over the REAL live registry, today: CONFORMANT (exit 0).
# @real-io @subprocess
# CONTRACT_SHAPE: unbounded-preservation
# ---------------------------------------------------------------------------


def test_check_port_realization_over_the_real_live_registry_reports_conformant() -> (
    None
):
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: feature-delta Slice Plan slice-03 ("exit 0 conformant").

    Today, ONLY `_conformance_fixture` (declares no ports at all) and
    `nwave-lang-rust` (declares only the genuinely-implemented `test-runner`
    port) are registered in the live `nwave.lang.adapter` entry-points group
    (verified via `importlib.metadata.entry_points` before authoring --
    python/typescript are deliberately NOT yet wired there, out of this
    feature's scope). So the real CLI over the real live registry exits 0
    CONFORMANT -- the durable target this mode must hit, independent of
    whether/when a future feature registers python/typescript.

    STRENGTHENED (Vera examine finding #1): exit 0 today is SILENT (zero
    stdout) -- a maintainer cannot distinguish "verified conformant" from
    "the flag was silently ignored". The summary must name the conformant
    outcome AND carry a count of plugins/ports probed (GDP-3: self-
    explaining, never a bare exit code).
    """
    completed = _run_cli(_CHECK_PORT_REALIZATION_FLAG)

    assert completed.returncode == 0, (
        f"expected the CONFORMANT lane (only `_conformance_fixture` + "
        f"`nwave-lang-rust` are registered today, neither lies) -- got exit "
        f"{completed.returncode}. stdout={completed.stdout!r} "
        f"stderr={completed.stderr!r}"
    )
    assert completed.stdout.strip(), (
        f"expected a truthful non-empty summary on stdout -- exit-0 must "
        f"never be silent. stderr={completed.stderr!r}"
    )
    assert "conformant" in completed.stdout.lower(), (
        f"expected the summary to name the conformant outcome: {completed.stdout!r}"
    )
    assert re.search(r"\d+", completed.stdout), (
        f"expected the summary to carry a count of plugins/ports probed: "
        f"{completed.stdout!r}"
    )


# ---------------------------------------------------------------------------
# T1b -- the live registry's one out-of-catalog declared port
# (nwave-lang-rust declares test-runner=True, outside the 3-port probe
# catalog) is NOTED, not silently skipped -- and never flagged as a false
# gap (still exit 0).
# @real-io @subprocess
# CONTRACT_SHAPE: unbounded-preservation
# ---------------------------------------------------------------------------


def test_check_port_realization_over_the_real_live_registry_notes_unregistered_port_noted_not_flagged() -> (
    None
):
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: Vera examine finding #2.

    `nwave-lang-rust` declares `port_coverage["test-runner"] = True`;
    `test-runner` sits OUTSIDE the 3-port probe catalog
    (`run_contract_gate` / `verify_environmental_e2e` /
    `check_robustness_density`) and today is silently `continue`d
    (`resolve_and_probe_port_realization_with_detail`, `port not in
    _PORT_METHOD_NAMES`). It is NOT a gap -- the port is genuinely out of
    this gate's scope -- but silence is also wrong: a maintainer reading a
    bare exit-0 cannot tell "verified nothing to report" from "silently
    ignored a declared port". The gate must VISIBLY note the unknown/
    out-of-catalog declared port (plugin + port named, marked not-probed)
    while STILL exiting 0.
    """
    completed = _run_cli(_CHECK_PORT_REALIZATION_FLAG)
    combined_output = completed.stdout + completed.stderr

    assert completed.returncode == 0, (
        f"an out-of-catalog declared port is NOT a gap -- must still exit "
        f"0. got exit {completed.returncode}. stdout={completed.stdout!r} "
        f"stderr={completed.stderr!r}"
    )
    assert "rust" in combined_output and "test-runner" in combined_output, (
        f"expected the unregistered/out-of-catalog port to be named "
        f"(plugin `rust`, port `test-runner`): {combined_output!r}"
    )
    assert re.search(
        r"not[- ]probed|unknown port|outside.{0,40}catalog|out-of-catalog",
        combined_output,
        re.IGNORECASE,
    ), (
        f"expected the note to mark the port as not-probed/out-of-catalog "
        f"-- never silent, never a false gap: {combined_output!r}"
    )


# ---------------------------------------------------------------------------
# T2 -- two synthetic liar plugins, injected directly: GAP (exit 1), naming
# all 4 (plugin, port) offenders. Fixture-sourced stub-state (#92), STABLE
# regardless of nWave-dev's own shipped-facet implementation status.
# @in-memory
# CONTRACT_SHAPE: unbounded-preservation
# ---------------------------------------------------------------------------


def test_check_port_realization_flags_both_synthetic_liar_plugins_with_four_gaps_total(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: feature-delta Summary ("Verified smoking gun" -- a
    registered-but-stub-backed plugin lies on exactly 2 of its 3 declared
    ports).

    Injecting two CONTROLLED `SyntheticLiarLanguageAdapterPlugin{CSharp,
    Kotlin}()` instances (each declares all 3 ports True; backs
    `run_contract_gate` genuinely, `verify_environmental_e2e` +
    `check_robustness_density` with pure stubs) into the gate -- bypassing
    the live registry, mirroring slice-02's "entry-point registration NOT
    required" seam -- must exit 1 GAP and name exactly the 4 offenders:
    neither plugin's lie leaks onto, nor is masked by, the other.
    """
    run_port_realization_gate = _load_gate_runner()

    exit_code = run_port_realization_gate(
        [
            SyntheticLiarLanguageAdapterPluginCSharp(),
            SyntheticLiarLanguageAdapterPluginKotlin(),
        ]
    )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exit_code == 1, (
        f"expected the GAP lane (both synthetic liar plugins declare "
        f"port_coverage=True for 2 stub-backed ports each) -- got exit "
        f"{exit_code}. output={combined_output!r}"
    )
    assert _gap_offenders(combined_output) == set(_ALL_GAP_PAIRS), (
        f"expected exactly the 4 (plugin, port) offenders named: {combined_output!r}"
    )


# ---------------------------------------------------------------------------
# T3 -- FAIL-LOUD anatomy (GDP-3/4): each gap names WHAT (port + stub method
# @file:line), the Protocol to implement, the adapter file, and the HOW
# re-check command.
# @in-memory
# CONTRACT_SHAPE: unbounded-preservation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("plugin_id", "port"),
    _ALL_GAP_PAIRS,
    ids=[f"{plugin_id}-{port}" for plugin_id, port in _ALL_GAP_PAIRS],
)
def test_check_port_realization_gap_carries_fail_loud_anatomy(
    plugin_id: str, port: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: feature-delta [REF] Architecture & Contract ("FAIL-LOUD
    stderr per gap (WHAT: port+method; WHY: stub body @file:line; HOW: the
    Protocol + adapter file to implement + the re-check command)").

    A gap that only names the port, with no method/file/line/Protocol/
    re-check, forces the maintainer to go spelunking -- exactly the ceremony
    GDP-3/4 forbid. Every one of the 4 gaps must self-explain.
    """
    run_port_realization_gate = _load_gate_runner()

    run_port_realization_gate(
        [
            SyntheticLiarLanguageAdapterPluginCSharp(),
            SyntheticLiarLanguageAdapterPluginKotlin(),
        ]
    )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err

    adapter_file = _ADAPTER_FILE_BY_PLUGIN_PORT[(plugin_id, port)]
    protocol_name = _PROTOCOL_BY_PORT[port]
    candidate_methods = _CANDIDATE_STUB_METHODS_BY_PORT[port]

    assert plugin_id in combined_output and port in combined_output, (
        f"WHAT (plugin + port) missing from the FAIL-LOUD output: {combined_output!r}"
    )
    assert any(method in combined_output for method in candidate_methods), (
        f"WHAT (stub method name, one of {candidate_methods}) missing: "
        f"{combined_output!r}"
    )
    assert re.search(rf"{re.escape(adapter_file)}:\d+", combined_output), (
        f"WHY (stub body @file:line, expected `{adapter_file}:<line>`) "
        f"missing: {combined_output!r}"
    )
    assert protocol_name in combined_output, (
        f"HOW (the Protocol to implement, `{protocol_name}`) missing: "
        f"{combined_output!r}"
    )
    assert _CHECK_PORT_REALIZATION_FLAG in combined_output, (
        f"HOW (the re-check command naming `{_CHECK_PORT_REALIZATION_FLAG}`) "
        f"missing: {combined_output!r}"
    )


# ---------------------------------------------------------------------------
# T4 -- NEGATIVE AT: the genuinely-implemented `run_contract_gate` port must
# NOT appear among the gaps for either synthetic liar plugin, even though the
# other two declared ports ARE flagged (guards against over-flagging every
# declared port blindly).
# @in-memory
# CONTRACT_SHAPE: unbounded-preservation
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_check_port_realization_does_not_flag_the_genuinely_implemented_contract_gate_port(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: feature-delta Summary.

    The synthetic liar plugin backs `run_contract_gate` with a genuine
    (non-stub) facet -- `run_contract_gate` must never appear among the gaps
    for either plugin, even though both declare it `True` and their other
    two ports ARE flagged (guards against over-flagging every declared port
    blindly; WRONG outcome asserted absent).
    """
    run_port_realization_gate = _load_gate_runner()

    run_port_realization_gate(
        [
            SyntheticLiarLanguageAdapterPluginCSharp(),
            SyntheticLiarLanguageAdapterPluginKotlin(),
        ]
    )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert RUN_CONTRACT_GATE not in combined_output, (
        f"run_contract_gate is genuinely implemented for both synthetic liar "
        f"plugins -- must not be flagged: {combined_output!r}"
    )


# ---------------------------------------------------------------------------
# T5 -- an unresolvable discovery target degrades LOUD to exit 3, never a
# raw traceback, never a false 0.
# @in-memory
# CONTRACT_SHAPE: unbounded-preservation
# ---------------------------------------------------------------------------


def test_check_port_realization_over_an_unresolvable_target_degrades_to_indeterminate(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: feature-delta [REF] Architecture & Contract ("reusing
    the existing exit-lane contract (0 conformant / 1 gap / 3
    INDETERMINATE)"); GDP-6 (no silent-wrong).

    An injected entry point whose target module cannot be imported is a
    GENUINE resolution failure (real `.load()` attempt, real
    `ModuleNotFoundError`) -- the gate must degrade LOUDLY: exit 3 with a
    diagnostic, never swallow it into a false CONFORMANT (0) and never leak
    a raw Python traceback to the maintainer.
    """
    run_port_realization_gate = _load_gate_runner()

    unresolvable = (
        EntryPoint(
            name="ghost_unresolvable_lang_plugin",
            value="nonexistent.module:GhostUnresolvableLanguageAdapter",
            group="nwave.lang.adapter",
        ),
    )
    exit_code = run_port_realization_gate(unresolvable)

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exit_code == 3, (
        f"expected the INDETERMINATE lane (an unresolvable discovery target) -- "
        f"got exit {exit_code}. output={combined_output!r}"
    )
    assert exit_code != 0, (
        "must never silently report CONFORMANT on an unresolvable probe input"
    )
    assert "Traceback (most recent call last)" not in combined_output, (
        f"must degrade LOUD with a diagnostic, never a raw Python traceback: "
        f"{combined_output!r}"
    )


# ---------------------------------------------------------------------------
# T6 -- the real CLI's own usage/help documents the new mode (GDP-3 self-
# explaining at the point of invocation, before any gap is even hit).
# @real-io @subprocess
# CONTRACT_SHAPE: unbounded-preservation
# ---------------------------------------------------------------------------


def test_cli_usage_documents_the_check_port_realization_mode() -> None:
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: feature-delta [REF] Architecture & Contract (the CLI
    "reus[es] the existing exit-lane contract"); GDP-2 (inline affordance at
    the authoring surface, not only at gate failure).

    Running the CLI with no arguments prints its usage line and exits 2
    (the existing malformed-invocation lane). That usage line must document
    the new `--check-port-realization` mode alongside the existing
    `--check-conformance` mode, so a maintainer discovers the mode from the
    CLI itself, not from spelunking the source.
    """
    completed = _run_cli()

    assert completed.returncode == 2, (
        f"expected the existing malformed-invocation lane -- got exit "
        f"{completed.returncode}. stderr={completed.stderr!r}"
    )
    assert _CHECK_PORT_REALIZATION_FLAG in completed.stderr, (
        f"expected the CLI usage line to document the new mode: {completed.stderr!r}"
    )


# ---------------------------------------------------------------------------
# T7 -- the `--plugin <module>:<Class>` CLI flag (repeatable): probe a
# SPECIFIC/unregistered plugin directly, bypassing the live registry -- the
# founder's core surface ("I add C# and the failures tell me what to
# implement").
# @real-io @subprocess
# CONTRACT_SHAPE: unbounded-preservation
# ---------------------------------------------------------------------------


def test_check_port_realization_plugin_flag_flags_both_synthetic_liar_plugins_with_four_gaps_total() -> (
    None
):
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: Vera examine finding #3.

    The real CLI must expose a repeatable `--plugin <module>:<Class>` flag
    on `--check-port-realization` that loads the NAMED plugin class(es) and
    probes THEM instead of the live registry (the composition-root
    `run_port_realization_gate` already accepts an
    `Iterable[LanguageAdapterPlugin]` discovery source -- T2/T3 drive it
    in-process; this test drives the SAME real behaviour end-to-end through
    the real CLI subprocess entry point, the surface an operator actually
    invokes).

    Smoking gun (fixture-sourced, #92): two CONTROLLED synthetic liar plugin
    classes, loaded via `--plugin`, must exit 1 GAP naming both plugins (by
    `target_language`: `csharp`/`kotlin`) and exactly the 4 (plugin, port)
    offenders, each carrying the full FAIL-LOUD anatomy (port, stub method
    @file:line, Protocol, re-check command) -- GDP-3/4. Driving the
    synthetic fixtures (not nWave-dev's own shipped plugins) keeps this
    end-to-end CLI assertion STABLE regardless of the repo's own facet state.
    """
    completed = _run_cli(
        _CHECK_PORT_REALIZATION_FLAG,
        "--plugin",
        _CSHARP_PLUGIN_TARGET,
        "--plugin",
        _KOTLIN_PLUGIN_TARGET,
    )
    combined_output = completed.stdout + completed.stderr

    assert completed.returncode == 1, (
        f"expected the GAP lane (both --plugin-named plugins declare "
        f"port_coverage=True for 2 stub-backed ports each) -- got exit "
        f"{completed.returncode}. output={combined_output!r}"
    )
    assert "csharp" in combined_output and "kotlin" in combined_output, (
        f"expected both --plugin-named plugins named by target_language: "
        f"{combined_output!r}"
    )
    assert _gap_offenders(combined_output) == set(_ALL_GAP_PAIRS), (
        f"expected exactly the 4 (plugin, port) offenders named: {combined_output!r}"
    )
    for plugin_id, port in _ALL_GAP_PAIRS:
        adapter_file = _ADAPTER_FILE_BY_PLUGIN_PORT[(plugin_id, port)]
        protocol_name = _PROTOCOL_BY_PORT[port]
        candidate_methods = _CANDIDATE_STUB_METHODS_BY_PORT[port]

        assert plugin_id in combined_output and port in combined_output, (
            f"WHAT (plugin + port) missing for {(plugin_id, port)}: {combined_output!r}"
        )
        assert any(method in combined_output for method in candidate_methods), (
            f"WHAT (stub method name, one of {candidate_methods}) missing "
            f"for {(plugin_id, port)}: {combined_output!r}"
        )
        assert re.search(rf"{re.escape(adapter_file)}:\d+", combined_output), (
            f"WHY (stub body @file:line, expected `{adapter_file}:<line>`) "
            f"missing for {(plugin_id, port)}: {combined_output!r}"
        )
        assert protocol_name in combined_output, (
            f"HOW (the Protocol to implement, `{protocol_name}`) missing "
            f"for {(plugin_id, port)}: {combined_output!r}"
        )
        assert _CHECK_PORT_REALIZATION_FLAG in combined_output, (
            f"HOW (the re-check command naming "
            f"`{_CHECK_PORT_REALIZATION_FLAG}`) missing: {combined_output!r}"
        )


# ---------------------------------------------------------------------------
# T8 -- an unresolvable `--plugin` target degrades LOUD to exit 3, never a
# raw traceback.
# @real-io @subprocess
# CONTRACT_SHAPE: unbounded-preservation
# ---------------------------------------------------------------------------


def test_check_port_realization_plugin_flag_over_an_unresolvable_target_degrades_to_indeterminate() -> (
    None
):
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: Vera examine finding #3 (degrade lane); GDP-6 (no
    silent-wrong).

    `--plugin not.a.module:Nope` names a module that cannot be imported --
    a genuine resolution failure at the real CLI entry point. The gate must
    degrade LOUDLY: exit 3 with a diagnostic naming the unresolvable target,
    never a raw Python traceback, never a silent CONFORMANT (0).
    """
    completed = _run_cli(
        _CHECK_PORT_REALIZATION_FLAG,
        "--plugin",
        "not.a.module:Nope",
    )
    combined_output = completed.stdout + completed.stderr

    assert completed.returncode == 3, (
        f"expected the INDETERMINATE lane (an unresolvable --plugin "
        f"target) -- got exit {completed.returncode}. "
        f"output={combined_output!r}"
    )
    assert completed.returncode != 0, (
        "must never silently report CONFORMANT on an unresolvable --plugin target"
    )
    assert "Traceback (most recent call last)" not in combined_output, (
        f"must degrade LOUD with a diagnostic, never a raw Python traceback: "
        f"{combined_output!r}"
    )
    assert re.search(r"not\.a\.module|Nope", combined_output), (
        f"expected the diagnostic to name the unresolvable --plugin target: "
        f"{combined_output!r}"
    )

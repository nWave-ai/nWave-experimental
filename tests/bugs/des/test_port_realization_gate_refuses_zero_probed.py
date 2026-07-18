"""RED regression test (#61, Rex RCA): the port-realization gate vacuous-passes on 0 probed.

``run_port_realization_gate`` (``scripts/cli/validate_language_adapter_catalog.py``
~:411-463) computes ``plugin_count`` but never floor-checks it before returning
``PORT_REALIZATION_GATE_CONFORMANT`` (exit 0) on ``not verdict.flagged`` -- so a
misconfigured interpreter (``PYTHONPATH=src`` with no ``nwave.lang.adapter``
entry-points installed/resolvable) that discovers ZERO plugins via the LIVE
discovery path (``discovery_source=None``) still gets a clean "conformant" bill of
health. "I verified nothing" is being reported as "I verified it's fine" --
same vacuous-pass family as #48 (cargo-nextest ``tests-run==0``) and #73
(readiness gate clearing on zero scenarios).

Charter: docs/product/expectations/fix-port-realization-not-vacuous-on-zero-probed/
gate-refuses-to-certify-when-zero-plugins-probed.md

Seam chosen (box-light, in-process, no subprocess): the LIVE discovery path
(``discovery_source=None``) resolves the ``nwave.lang.adapter`` entry-points via
exactly one call site --
``des.testarch.port_realization_discovery._discover_registered_plugins`` ->
``metadata.entry_points(group="nwave.lang.adapter")``. Monkeypatching
``metadata.entry_points`` at that module hermetically reproduces "misconfigured
interpreter probes zero plugins" without touching ``sys.path``/env vars or
forking an interpreter -- and, symmetrically, injecting one REAL resolvable
entry point (the in-tree ``ConformanceFixtureLanguageAdapter``, already the
repo's designated always-conformant probe fixture) reproduces "a correctly
configured interpreter probing >=1 real plugin" for the over-correction guard.

This deliberately does NOT touch the explicit-empty-list boundary contract
(``resolve_and_probe_port_realization([])`` / Scenario 10 in
``test_port_realization_discovery.py``) -- that is a DIFFERENT, legitimate case
("caller explicitly declares zero plugins to probe") the charter itself
distinguishes from "the live discovery mechanism found nothing because it is
broken". This file's ``test_explicit_empty_plugin_list_stays_conformant`` pins
that distinction as a regression guard against an over-broad fix.

Driving surface (Mandate-16 driving-port-only): drives the real composition-root
gate-runner ``run_port_realization_gate`` (the same symbol the CLI's ``main()``
dispatches to for ``--check-port-realization``) directly, in-process --
Layer 3 composition, mirroring the existing sibling ATs in
``tests/build/language_port_realization_gate/acceptance/test_check_port_realization_cli.py``.

Author-only: this file authors the RED test. A crafter fixes
``run_port_realization_gate``/``run_conformance_gate`` against it later. Do not
weaken or skip these assertions to make them pass.
"""

from __future__ import annotations

from importlib.metadata import EntryPoint
from typing import TYPE_CHECKING

import pytest

from des.testarch import port_realization_discovery as _discovery
from scripts.cli import validate_language_adapter_catalog as _catalog_cli
from scripts.cli.validate_language_adapter_catalog import (
    CONFORMANCE_GATE_CONFORMANT,
    CONFORMANCE_GATE_INDETERMINATE,
    PORT_REALIZATION_GATE_CONFORMANT,
    PORT_REALIZATION_GATE_INDETERMINATE,
    run_conformance_gate,
    run_port_realization_gate,
)


if TYPE_CHECKING:
    from collections.abc import Iterable


_GROUP = "nwave.lang.adapter"

# The repo's own designated always-conformant live-registry fixture (declares
# no ports at all -- see pyproject.toml [project.entry-points."nwave.lang.adapter"]
# and the CLI AT's docstring: "only `_conformance_fixture` (port_coverage == {},
# vacuously conformant) ... are REGISTERED today"). Reused here (not invented)
# to inject a REAL >=1-plugin live-discovery corpus without depending on the
# repo's own mutable python/typescript registration state.
_CONFORMANCE_FIXTURE_TARGET = (
    "scripts.install.plugins._conformance_fixture_language_adapter:"
    "ConformanceFixtureLanguageAdapter"
)


def _patch_live_entry_points(
    monkeypatch: pytest.MonkeyPatch, entries: tuple[EntryPoint, ...]
) -> None:
    """Replace the port-realization LIVE discovery read with ``entries``.

    Patches ``metadata.entry_points`` at its one call site inside
    ``des.testarch.port_realization_discovery._discover_registered_plugins`` --
    the only code path ``run_port_realization_gate(discovery_source=None)``
    reaches. Never touches the real installed entry-points registry.
    """

    def _fake_entry_points(*, group: str) -> tuple[EntryPoint, ...]:
        assert group == _GROUP, f"unexpected entry-points group probed: {group!r}"
        return entries

    monkeypatch.setattr(_discovery.metadata, "entry_points", _fake_entry_points)


def _patch_conformance_gate_entry_points(
    monkeypatch: pytest.MonkeyPatch, entries: tuple[EntryPoint, ...]
) -> None:
    """Replace ``run_conformance_gate``'s LIVE discovery read with ``entries``.

    ``run_conformance_gate`` (the sibling gate, same defect family) resolves
    ``entry_points`` imported directly into
    ``scripts.cli.validate_language_adapter_catalog`` -- a different call site
    than the port-realization gate's, so it needs its own patch target.
    """

    def _fake_entry_points(*, group: str) -> tuple[EntryPoint, ...]:
        assert group == _GROUP, f"unexpected entry-points group probed: {group!r}"
        return entries

    monkeypatch.setattr(_catalog_cli, "entry_points", _fake_entry_points)


# ---------------------------------------------------------------------------
# 1. CORE (RED today) -- zero plugins probed via the LIVE discovery path must
#    NOT be certified CONFORMANT/exit-0.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_zero_probed_via_live_discovery_refuses_conformant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A misconfigured interpreter probing 0 plugins is 'I could not verify',
    never 'it's fine'.

    Reproduces Rex's repro (``PYTHONPATH=src`` with no entry-points
    installed) hermetically: the live ``nwave.lang.adapter`` entry-points
    read returns empty while ``discovery_source=None`` (the default/live
    mode the real CLI's ``--check-port-realization`` dispatches to). RED
    today: the gate currently returns ``PORT_REALIZATION_GATE_CONFORMANT``
    (0) unconditionally whenever ``not verdict.flagged`` -- it never
    floor-checks the plugin count it already computes.
    """
    _patch_live_entry_points(monkeypatch, ())

    exit_code = run_port_realization_gate()

    assert exit_code != PORT_REALIZATION_GATE_CONFORMANT, (
        "vacuous-pass: 0 plugins probed via the live discovery path must "
        "never be certified CONFORMANT (exit 0) -- probing nothing is not "
        "verifying it's fine."
    )
    assert exit_code == PORT_REALIZATION_GATE_INDETERMINATE, (
        f"expected the INDETERMINATE lane ({PORT_REALIZATION_GATE_INDETERMINATE}) "
        f"for a genuinely broken/misconfigured live-discovery read -- got exit "
        f"{exit_code}."
    )


# ---------------------------------------------------------------------------
# 2. NEGATIVE (loud + non-zero + self-explaining) -- the refusal message must
#    name 0-probed and point at the likely cause, never a bare exit code.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_zero_probed_refusal_is_loud_never_conformant_wording(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The zero-probed refusal names WHAT (0 probed) and WHY (likely cause).

    Negative guard: must NOT print "conformant" or any other success/green
    wording (GDP-3/6) -- the message must instead point the maintainer at
    the interpreter/entry-points cause, and the exit code must be non-zero
    so a script reading only ``$?`` sees failure.
    """
    _patch_live_entry_points(monkeypatch, ())

    exit_code = run_port_realization_gate()

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err

    assert exit_code != 0, (
        f"a script checking only the exit code must see failure on a "
        f"0-probed live-discovery run -- got exit {exit_code}."
    )
    assert "conformant" not in combined_output.lower(), (
        f"0 plugins probed must never print success/green wording: {combined_output!r}"
    )
    assert "0" in combined_output, (
        f"expected the message to name that 0 plugins were probed: {combined_output!r}"
    )
    assert (
        "entry-point" in combined_output.lower()
        or "entry point" in combined_output.lower()
        or "interpreter" in combined_output.lower()
    ), (
        f"expected the message to point at the likely cause (interpreter / "
        f"entry-points not installed or resolvable): {combined_output!r}"
    )


# ---------------------------------------------------------------------------
# 3. NEGATIVE (over-correction guard) -- a real conformant run (>=1 plugin
#    probed via the live path) must STILL report CONFORMANT/exit-0.
# ---------------------------------------------------------------------------


def test_at_least_one_probed_via_live_discovery_stays_conformant(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The fix must be scoped to the 0-probed live lane -- never 'always fail'.

    Injecting one REAL, resolvable, always-conformant plugin
    (``ConformanceFixtureLanguageAdapter``) into the live discovery path must
    still report CONFORMANT/exit-0 naming a truthful >=1 plugin-probed count
    -- a correct fix does not break a genuinely healthy run.
    """
    entries: Iterable[EntryPoint] = (
        EntryPoint(
            name="_conformance_fixture",
            value=_CONFORMANCE_FIXTURE_TARGET,
            group=_GROUP,
        ),
    )
    _patch_live_entry_points(monkeypatch, tuple(entries))

    exit_code = run_port_realization_gate()

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exit_code == PORT_REALIZATION_GATE_CONFORMANT, (
        f"a genuinely healthy live run (>=1 real plugin probed, 0 gaps) "
        f"must stay CONFORMANT (exit 0) -- got exit {exit_code}. "
        f"output={combined_output!r}"
    )
    assert "1 plugin" in combined_output or "1 plugin(s)" in combined_output, (
        f"expected the summary to carry the truthful >=1 plugin-probed "
        f"count: {combined_output!r}"
    )


# ---------------------------------------------------------------------------
# 4. NEGATIVE (over-correction guard) -- the explicit-empty-list boundary
#    contract (a DIFFERENT, legitimate zero case) must stay unaffected.
# ---------------------------------------------------------------------------


def test_explicit_empty_plugin_list_stays_conformant() -> None:
    """Explicit ``discovery_source=[]`` is a legitimate zero -- NOT the bug.

    Mirrors Scenario 10 (``test_discovery_reports_an_empty_plugin_list_as_
    conformant`` in ``test_port_realization_discovery.py``) one composition
    layer up: a caller explicitly passing an empty plugin iterable (not the
    ``None``/live-discovery default) is declaring "nothing to probe by
    design", distinct from a misconfigured live discovery finding nothing.
    This case MUST remain CONFORMANT/exit-0 -- a fix that floor-checks
    ``plugin_count == 0`` unconditionally (rather than only on the live
    ``discovery_source=None`` path) would wrongly break this boundary
    contract.
    """
    exit_code = run_port_realization_gate([])

    assert exit_code == PORT_REALIZATION_GATE_CONFORMANT, (
        f"an explicit empty plugin list is a legitimate 'nothing to probe "
        f"by design' case -- must stay CONFORMANT (exit 0), got exit "
        f"{exit_code}. A fix must not blanket-fail on any 0 count."
    )


# ---------------------------------------------------------------------------
# 5. Sibling defect -- ``run_conformance_gate`` shares the same vacuous-pass
#    shape on 0 plugins probed via its own live discovery path.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_conformance_gate_zero_probed_via_live_discovery_refuses_conformant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sibling of the core assertion: ``run_conformance_gate`` has the same gap.

    ``run_conformance_gate`` computes a verdict over
    ``realized_by_plugin`` (one entry per discovered plugin) but never
    floor-checks that the map is non-empty before returning
    ``CONFORMANCE_GATE_CONFORMANT`` on ``not verdict.flagged`` -- an empty
    ``realized_by_plugin`` is vacuously non-flagged. RED today for the same
    root cause as the port-realization gate.
    """
    _patch_conformance_gate_entry_points(monkeypatch, ())

    exit_code = run_conformance_gate()

    assert exit_code != CONFORMANCE_GATE_CONFORMANT, (
        "vacuous-pass: 0 plugins probed via the live discovery path must "
        "never be certified CONFORMANT (exit 0) for run_conformance_gate "
        "either -- same root cause as the port-realization gate."
    )
    assert exit_code == CONFORMANCE_GATE_INDETERMINATE, (
        f"expected the INDETERMINATE lane ({CONFORMANCE_GATE_INDETERMINATE}) "
        f"for a genuinely broken/misconfigured live-discovery read -- got "
        f"exit {exit_code}."
    )

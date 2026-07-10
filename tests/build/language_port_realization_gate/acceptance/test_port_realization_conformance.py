"""Acceptance tests -- `detect_port_realization_conformance` (DISTILL, slice-01).

Feature-delta: docs/feature/language-port-realization-gate/feature-delta.md
  Wave: DESIGN / [REF] Architecture & Contract + [REF] Slice Plan (slice-01)

Contract under test (DOES NOT EXIST YET -- active-RED by design):
`src/des/testarch/rules/registry_conformance.py::detect_port_realization_conformance`
is a NEW pure sibling detector, additive to the module's existing per-plugin
x per-capability 2-D shape (`detect_per_plugin_capability_conformance`,
`PerPluginCapabilityViolation`/`PerPluginCapabilityVerdict`,
`CAPABILITY_NOT_REALIZED_BY_PLUGIN_BREACH`). This slice mirrors that exact
dataclass/return convention one axis over: PORTS instead of capabilities.

Signature (feature-delta line 34): `detect_port_realization_conformance(plugin_ports,
is_stub_by_plugin)`.
  * `plugin_ports: Mapping[str, Mapping[str, bool]]` -- per plugin id, the
    plugin's self-declared `port_coverage` map (`{port_name: declared_covered}`),
    the 3 ports in scope being `run_contract_gate`, `verify_environmental_e2e`,
    `check_robustness_density` (`LanguageAdapterPlugin.port_coverage`).
  * `is_stub_by_plugin: Mapping[str, Mapping[str, bool]]` -- per plugin id,
    whether that port's BACKING ADAPTER METHOD is stub-backed (AST
    stub-detection result -- INJECTED here, never probed by this pure rule;
    the real AST probe is slice-02's composition-root concern).
  * Returns `PortRealizationVerdict(violations: tuple[PortRealizationViolation, ...])`
    with a `flagged` property (`bool(violations)`), mirroring every sibling
    verdict dataclass in this module.

Breach rule: a `(plugin_id, port)` pair is flagged iff the plugin DECLARES
`plugin_ports[plugin_id][port] is True` AND that port `is_stub_by_plugin[plugin_id][port]
is True` -- the exact registered-but-stubbed lie the real, already-shipped
`NwaveLangPython.port_coverage` commits (feature-delta Summary: `True` declared
for `verify_environmental_e2e` + `check_robustness_density` while both adapters'
bodies are 100% `raise NotImplementedError`). A plugin declaring `False` for a
stub port is NOT flagged -- declaring `False` for an unimplemented port is an
HONEST admission, not a lie; only the `True`+stub combination is dishonest.
`kind` on every violation is `PORT_NOT_REALIZED_BY_PLUGIN_BREACH =
"port_not_realized_by_plugin"`.

Slice-01 scope (feature-delta Slice Plan row): PURE detector only, over
INJECTED `{plugin: {port: bool}}` fixtures -- NO live `nwave.lang.adapter`
registry read, NO AST stub-probing, NO recursion risk. The live-registry
resolve-and-probe composition root is slice-02 (`port_realization_discovery.py`,
CREATE_NEW, out of this slice's scope).

Active-RED scaffolding (hidden-import P1-P4, `nw-distill-red-scaffolding`):
`registry_conformance.py` ALREADY EXISTS (it hosts multiple sibling
detectors); only the `detect_port_realization_conformance` symbol + its two
dataclasses + breach constant are absent. If those absent NAMES were imported
at module TOP, collection would fail with `ImportError: cannot import name
...` -> BROKEN (COLLECT 0), which the `des verify-red-green` seal REFUSES
(it requires COLLECT >= 1 and a SEMANTIC failure). So the missing-symbol
references live INSIDE a hidden-import helper (`_load_detector()`) each test
body calls: the file collects cleanly (the existing module imports fine), and
each test fails at CALL TIME with a semantic `AssertionError`
(MISSING_FUNCTIONALITY) -- active-RED, not BROKEN. The crafter resolves it by
adding the four symbols to the existing module.

Driving surface (Mandate-13 driving-port-only): the pure detector function
itself IS the driving port for this slice -- no composition root, no
subprocess, no live I/O (PURE over its arguments, per feature-delta).

CONTRACT_SHAPE: pure-function (every scenario in this module -- the detector
takes plain data in, returns a plain-data verdict, no state mutation).
"""

from __future__ import annotations

from types import ModuleType

import pytest


# ---------------------------------------------------------------------------
# The 3 ports in scope (LanguageAdapterPlugin.port_coverage, feature-delta).
# ---------------------------------------------------------------------------

RUN_CONTRACT_GATE = "run_contract_gate"
VERIFY_ENVIRONMENTAL_E2E = "verify_environmental_e2e"
CHECK_ROBUSTNESS_DENSITY = "check_robustness_density"
ALL_PORTS = (RUN_CONTRACT_GATE, VERIFY_ENVIRONMENTAL_E2E, CHECK_ROBUSTNESS_DENSITY)

# The four symbols slice-01 must add to the EXISTING registry_conformance module.
_REQUIRED_SYMBOLS = (
    "detect_port_realization_conformance",
    "PortRealizationViolation",
    "PortRealizationVerdict",
    "PORT_NOT_REALIZED_BY_PLUGIN_BREACH",
)


# ---------------------------------------------------------------------------
# Hidden-import helper (P1 + P3, `nw-distill-red-scaffolding`): the module
# ALREADY exists and imports cleanly, so collection stays green (COLLECT >= 1);
# the ABSENT names are resolved at CALL TIME inside a test body, surfacing as a
# semantic AssertionError (MISSING_FUNCTIONALITY) -- active-RED, never a
# collection ImportError (BROKEN).
# ---------------------------------------------------------------------------


def _load() -> ModuleType:
    from des.testarch.rules import registry_conformance as mod

    missing = [name for name in _REQUIRED_SYMBOLS if not hasattr(mod, name)]
    if missing:
        raise AssertionError(
            "MISSING_FUNCTIONALITY: "
            "src/des/testarch/rules/registry_conformance.py does not yet define "
            f"{missing}. Add the pure sibling detector "
            "`detect_port_realization_conformance(plugin_ports, is_stub_by_plugin)` "
            "+ `PortRealizationViolation` / `PortRealizationVerdict` dataclasses "
            '+ `PORT_NOT_REALIZED_BY_PLUGIN_BREACH = "port_not_realized_by_plugin"`, '
            "mirroring the module's existing per-plugin x per-capability 2-D shape, "
            "before this AT can pass."
        )
    return mod


def _named_offenders(verdict: object) -> set[tuple[str, str]]:
    return {(v.plugin_id, v.port) for v in verdict.violations}


# ---------------------------------------------------------------------------
# Scenario 1 -- POSITIVE: the real smoking gun, mirrored as an injected fixture
# (Ale: "I add csharp to the toml and the failures tell me what to implement").
# A plugin declares run_contract_gate=True(non-stub), verify_environmental_e2e=
# True(STUB), check_robustness_density=True(STUB) -- the gate flags exactly the
# 2 stub-backed declared-covered ports, naming the plugin + each port.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


def test_detector_flags_every_declared_covered_port_that_is_stub_backed() -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: DISCUSS Elevator Pitch

    A plugin declaring `port_coverage[X]=True` for a port whose backing
    adapter method is stub-backed is a registered-but-stubbed lie -- the gate
    flags exactly those `(plugin, port)` pairs, naming both the plugin and
    each stubbed port, and leaves the one genuinely-realized declared port
    unflagged.
    """
    plugin_ports = {
        "csharp": {
            RUN_CONTRACT_GATE: True,
            VERIFY_ENVIRONMENTAL_E2E: True,
            CHECK_ROBUSTNESS_DENSITY: True,
        }
    }
    is_stub_by_plugin = {
        "csharp": {
            RUN_CONTRACT_GATE: False,
            VERIFY_ENVIRONMENTAL_E2E: True,
            CHECK_ROBUSTNESS_DENSITY: True,
        }
    }

    mod = _load()
    verdict = mod.detect_port_realization_conformance(plugin_ports, is_stub_by_plugin)

    assert verdict.flagged is True, (
        f"expected the gate to flag a stubbed lie: {verdict!r}"
    )
    assert len(verdict.violations) == 2, (
        f"expected exactly 2 breaches (the 2 stub-backed declared ports), "
        f"got {len(verdict.violations)}: {verdict.violations!r}"
    )
    assert _named_offenders(verdict) == {
        ("csharp", VERIFY_ENVIRONMENTAL_E2E),
        ("csharp", CHECK_ROBUSTNESS_DENSITY),
    }, verdict.violations
    assert all(
        v.kind == mod.PORT_NOT_REALIZED_BY_PLUGIN_BREACH for v in verdict.violations
    ), (
        f"every violation must carry kind={mod.PORT_NOT_REALIZED_BY_PLUGIN_BREACH!r}: "
        f"{verdict.violations!r}"
    )
    assert all(isinstance(v, mod.PortRealizationViolation) for v in verdict.violations)


# ---------------------------------------------------------------------------
# Scenario 2 -- NEGATIVE AT: a fully-realized plugin must NOT be flagged.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_detector_does_not_flag_a_plugin_whose_declared_ports_are_all_realized() -> (
    None
):
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: DISCUSS Elevator Pitch

    A plugin declaring `port_coverage[X]=True` for every port, where NONE of
    the backing adapter methods are stub-backed, is fully realized -- the
    gate must NOT false-flag it (zero breaches, `flagged is False`).
    """
    plugin_ports = {
        "rust": {
            RUN_CONTRACT_GATE: True,
            VERIFY_ENVIRONMENTAL_E2E: True,
            CHECK_ROBUSTNESS_DENSITY: True,
        }
    }
    is_stub_by_plugin = {
        "rust": {
            RUN_CONTRACT_GATE: False,
            VERIFY_ENVIRONMENTAL_E2E: False,
            CHECK_ROBUSTNESS_DENSITY: False,
        }
    }

    verdict = _load().detect_port_realization_conformance(
        plugin_ports, is_stub_by_plugin
    )

    assert verdict.flagged is False, (
        f"a fully-realized plugin must NOT be flagged (WRONG outcome asserted "
        f"absent): {verdict.violations!r}"
    )
    assert verdict.violations == ()


# ---------------------------------------------------------------------------
# Scenario 3 -- NEGATIVE AT: declaring False for a stub port is HONEST, not a
# breach -- guards against over-flagging (you only promised what you declared).
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_detector_does_not_flag_an_honestly_undeclared_stub_port() -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: DISCUSS Elevator Pitch

    A plugin declaring `port_coverage[X]=False` for a port whose backing
    method happens to be stub-backed is being HONEST (it never claimed to
    cover that port) -- the gate must NOT flag that pair, even though the
    method is genuinely a stub. Only `True`+stub is a lie; `False`+stub is
    truthful non-coverage.
    """
    plugin_ports = {
        "go": {
            RUN_CONTRACT_GATE: True,
            VERIFY_ENVIRONMENTAL_E2E: False,
            CHECK_ROBUSTNESS_DENSITY: True,
        }
    }
    is_stub_by_plugin = {
        "go": {
            RUN_CONTRACT_GATE: False,
            # Backing method IS a stub, but the plugin never declared
            # coverage for it -- honest, must not be flagged.
            VERIFY_ENVIRONMENTAL_E2E: True,
            CHECK_ROBUSTNESS_DENSITY: False,
        }
    }

    verdict = _load().detect_port_realization_conformance(
        plugin_ports, is_stub_by_plugin
    )

    assert verdict.flagged is False, (
        f"declaring False for an unimplemented port is honest, not a lie -- "
        f"must NOT be flagged (WRONG outcome asserted absent): "
        f"{verdict.violations!r}"
    )
    assert verdict.violations == ()


# ---------------------------------------------------------------------------
# Scenario 4 -- PBT/parametrize density: the full (declared, is_stub) x port
# cross-product, single-port-at-a-time, isolating each of the 3 in-scope
# ports independently.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("port", ALL_PORTS)
@pytest.mark.parametrize(
    ("declared", "is_stub", "expect_flagged"),
    [
        (True, True, True),
        (True, False, False),
        (False, True, False),
        (False, False, False),
    ],
    ids=[
        "declared_and_stub_backed_breaches",
        "declared_and_realized_conformant",
        "undeclared_stub_backed_not_flagged",
        "undeclared_realized_not_flagged",
    ],
)
def test_detector_flags_exactly_the_declared_and_stub_backed_combination(
    port: str, declared: bool, is_stub: bool, expect_flagged: bool
) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: DISCUSS Elevator Pitch

    Across the full (declared, is_stub) truth table for each in-scope port
    independently, the gate flags a `(plugin, port)` pair iff BOTH declared
    is True AND is_stub is True -- the AND-gate is exact, never a false
    positive on the other 3 combinations.
    """
    plugin_ports = {"typescript": dict.fromkeys(ALL_PORTS, False)}
    is_stub_by_plugin = {"typescript": dict.fromkeys(ALL_PORTS, False)}
    plugin_ports["typescript"][port] = declared
    is_stub_by_plugin["typescript"][port] = is_stub

    verdict = _load().detect_port_realization_conformance(
        plugin_ports, is_stub_by_plugin
    )

    if expect_flagged:
        assert verdict.flagged is True
        assert _named_offenders(verdict) == {("typescript", port)}
    else:
        assert verdict.flagged is False, (
            f"declared={declared} is_stub={is_stub} on {port!r} must NOT "
            f"flag: {verdict.violations!r}"
        )
        assert verdict.violations == ()


# ---------------------------------------------------------------------------
# Scenario 5 -- PBT/parametrize density: multiple plugins in one registry
# snapshot are flagged INDEPENDENTLY -- a lie in one plugin never leaks a
# false positive onto a clean sibling plugin, nor does a clean plugin mask a
# lying one.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


def test_detector_flags_independently_across_multiple_plugins_in_one_registry() -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: DISCUSS Elevator Pitch

    Given a registry snapshot with 3 plugins -- one lying on 2 ports, one
    fully realized, one honestly under-declaring a stub port -- the gate
    names ONLY the lying plugin's 2 stub-backed pairs; the other two plugins
    contribute zero violations each.
    """
    plugin_ports = {
        "csharp": {
            RUN_CONTRACT_GATE: True,
            VERIFY_ENVIRONMENTAL_E2E: True,
            CHECK_ROBUSTNESS_DENSITY: True,
        },
        "rust": {
            RUN_CONTRACT_GATE: True,
            VERIFY_ENVIRONMENTAL_E2E: True,
            CHECK_ROBUSTNESS_DENSITY: True,
        },
        "go": {
            RUN_CONTRACT_GATE: True,
            VERIFY_ENVIRONMENTAL_E2E: False,
            CHECK_ROBUSTNESS_DENSITY: True,
        },
    }
    is_stub_by_plugin = {
        "csharp": {
            RUN_CONTRACT_GATE: False,
            VERIFY_ENVIRONMENTAL_E2E: True,
            CHECK_ROBUSTNESS_DENSITY: True,
        },
        "rust": {
            RUN_CONTRACT_GATE: False,
            VERIFY_ENVIRONMENTAL_E2E: False,
            CHECK_ROBUSTNESS_DENSITY: False,
        },
        "go": {
            RUN_CONTRACT_GATE: False,
            VERIFY_ENVIRONMENTAL_E2E: True,
            CHECK_ROBUSTNESS_DENSITY: False,
        },
    }

    verdict = _load().detect_port_realization_conformance(
        plugin_ports, is_stub_by_plugin
    )

    assert _named_offenders(verdict) == {
        ("csharp", VERIFY_ENVIRONMENTAL_E2E),
        ("csharp", CHECK_ROBUSTNESS_DENSITY),
    }, verdict.violations
    assert len(verdict.violations) == 2, (
        f"rust (fully realized) and go (honest under-declaration) must "
        f"contribute zero violations: {verdict.violations!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 6 -- boundary: an empty registry is trivially conformant.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


def test_detector_reports_an_empty_registry_as_conformant() -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: DISCUSS Elevator Pitch

    No plugins registered -> the cross-product is empty -> zero violations,
    conformant (never an error on the empty-input boundary).
    """
    verdict = _load().detect_port_realization_conformance({}, {})

    assert verdict.flagged is False
    assert verdict.violations == ()

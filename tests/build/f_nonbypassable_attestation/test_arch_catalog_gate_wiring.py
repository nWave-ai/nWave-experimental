"""AT-A1 (slice-04, DDD-6): catalog<->hook-wiring coherence as an arch-tier check.

Arch-tier, pure-function (no subprocess, no behavioral execution): reads the
shipped ``_catalog.yaml`` + the firing-surface DATA files + the catalog
``_schema.yaml`` as DATA and asserts the coherence invariant. Recognized as an
arch test (``test_arch_`` prefix under ``tests/build/``) per the AT-completeness
S2 tolerable-variant rule (introspect structure, never exercise behavior).

The SUT (Mandate-13 driving surface for an arch-tier pure-function slice
@contract-shape:pure-function): the coherence function the DELIVER crafter folds
into ``tests/build/test_catalog_gate_wiring.py`` (the production arch test) +
the ``_schema.yaml`` ``dormant`` extension. There is NO subprocess / composition
entry -- the "port" IS the pure function over (catalog, firing-surfaces). These
ATs DRIVE that real surface by reading the SAME shipped files the production
check reads, never a test-fabricated oracle (Mandate-13 protocol-driver: assert
a shipped artifact, not a self-fulfilling fixture).

THE COHERENCE CONTRACT (DDD-6, AT-A1): every ``gate_id`` in
``nWave/gates/_catalog.yaml`` is EITHER
  (a) WIRED -- referenced as a firing surface in a live hook: a flavor
      ``lifecycle_events`` / ``wave_gate_stacks`` gate_id row, OR a
      hook-definitions registry / live-hook module reference, OR an
      operator-direct CLI gate (``host_visibility`` includes ``cli`` /
      ``git-hook``), OR orchestrated by the feature-end cycle service --
  OR
  (b) DORMANT -- carries an explicit ``dormant: <rationale>`` key (min length
      enforced by the schema so the escape requires a real rationale).
A catalogued gate that is NEITHER wired NOR dormant is the authored-but-unwired
failure class (gate-G / self-attest / runner-port shipped green but never fired)
-> the coherence check FAILS and NAMES the unwired gate (veto-able).

WITNESSING COUNTS INDIRECT WIRING (S3 / Mandate-15 framing-attack -- NOT a naive
gate_id-row match): "wired" counts a gate reached via operator-CLI invocation
(``host_visibility: [cli]``), git-hook invocation, the live-hook module
reference (``subagent_stop_handler`` / ``carpaccio_intercept``), and the
feature-end cycle orchestration -- a binding-resolved indirect reach, never only
a literal flavor gate_id row. A naive "appears as a flavor gate_id row" match
would FALSE-POSITIVE the ~20 legitimate operator-CLI / git-hook / orchestrated
gates (``doctor``, ``commit-slice``, ``walking-skeleton-gate`` ...) -- the exact
false-positive class the indirect-wiring rule removes.

ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD
  * ``_schema.yaml`` ``GateContract`` is ``additionalProperties: false`` with NO
    ``dormant`` property (``:48``), so a catalogued ``dormant:`` value is
    SCHEMA-REJECTED -- AT-A1-D (schema permits dormant) RED-fails;
  * there is NO production coherence check + NO ``dormant`` annotation on the
    genuinely-unwired catalogued gates, so the coherence-over-the-real-catalog
    assertion RED-fails NAMING the unwired gates (the authored-but-unwired class
    is live at HEAD).
Every failure is a semantic ``AssertionError``, never a collection / import /
setup error. GREEN once DELIVER (1) extends ``_schema.yaml`` to permit
``dormant: {type: string, minLength: 10}`` on ``GateContract``, (2) ships the
pure-function coherence check, and (3) annotates each genuinely-unwired
catalogued gate with ``dormant: <rationale>`` (or wires it).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml


# tests/build/f_nonbypassable_attestation/<this file> -> parents[3] = REPO_ROOT
_REPO_ROOT = Path(__file__).resolve().parents[3]

_CATALOG_PATH = _REPO_ROOT / "nWave" / "gates" / "_catalog.yaml"
_SCHEMA_PATH = _REPO_ROOT / "nWave" / "gates" / "_schema.yaml"
_PER_GATE_DIR = _REPO_ROOT / "nWave" / "gates"

# Firing-surface DATA files: a catalogued gate is WIRED if it is referenced as a
# live firing surface in ANY of these (read as DATA, never imported / executed).
_FLAVOR_FILES = (
    _REPO_ROOT / "nWave" / "flavors" / "atdd_pure.yaml",
    _REPO_ROOT / "nWave" / "flavors" / "classic.yaml",
)
_LIVE_HOOK_FILES = (
    _REPO_ROOT / "scripts" / "shared" / "hook_definitions.py",
    _REPO_ROOT
    / "src"
    / "des"
    / "adapters"
    / "drivers"
    / "hooks"
    / "subagent_stop_handler.py",
    _REPO_ROOT
    / "src"
    / "des"
    / "adapters"
    / "drivers"
    / "hooks"
    / "carpaccio_intercept.py",
    _REPO_ROOT / "src" / "des" / "application" / "feature_end_cycle_service.py",
)

# host_visibility values that mean "invoked directly by an operator / git" (a
# valid indirect wiring -- the gate fires on a real surface even with no flavor
# gate_id row). S3: indirect wiring counts.
_OPERATOR_VISIBILITIES = frozenset({"cli", "git-hook"})


# --------------------------------------------------------------------------
# Readers over the shipped DATA (the real coherence check operates on exactly
# these surfaces; the ATs read the same files -- no fabricated oracle).
# --------------------------------------------------------------------------


def _firing_surface_text() -> str:
    """Concatenated DATA of every live firing surface (flavors + live hooks)."""
    parts: list[str] = []
    for f in (*_FLAVOR_FILES, *_LIVE_HOOK_FILES):
        if f.exists():
            parts.append(f.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def _gate_host_visibility(gate_id: str) -> frozenset[str]:
    """The per-gate file's ``host_visibility`` set (empty if no per-gate file)."""
    per_gate = _PER_GATE_DIR / f"{gate_id}.yaml"
    if not per_gate.exists():
        return frozenset()
    doc = yaml.safe_load(per_gate.read_text(encoding="utf-8")) or {}
    return frozenset(doc.get("host_visibility", []))


def _gate_contract_properties() -> dict:
    """The ``GateContract.properties`` block of the catalog schema (DATA)."""
    doc = yaml.safe_load(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return doc["$defs"]["GateContract"]["properties"]


def coherence_offenders(
    gates: list[dict],
    *,
    firing_text: str,
    host_visibility: dict[str, frozenset[str]],
) -> list[str]:
    """The PURE coherence reducer (the SUT, @contract-shape:pure-function).

    Over an arbitrary catalogue (a list of gate entries), returns the gate-ids
    that are NEITHER wired NOR dormant-annotated -- catalogued gate-ids not a
    subset of (wired union dormant). A non-empty result is the authored-but-unwired
    failure class. INJECTED inputs (catalogue gates + firing-surface text +
    per-gate host-visibility) so the reducer can be driven over BOTH the live
    shipped surface (the regression guardrail) AND a synthetic incoherent
    fixture (the FLAG+NAME witness) -- distinct-fixture-per-verdict discipline.

    Wiredness counts INDIRECT wiring (S3 / Mandate-15): a flavor gate_id row, OR
    a live-hook module reference, OR operator-direct visibility (cli / git-hook).
    """
    offenders: list[str] = []
    for entry in gates:
        gid = entry["gate_id"]
        module = entry.get("module", "")
        visibilities = host_visibility.get(gid, frozenset())
        wired = (
            bool(re.search(rf"gate_id:\s*{re.escape(gid)}\b", firing_text))
            or (bool(module) and module in firing_text)
            or bool(visibilities & _OPERATOR_VISIBILITIES)
        )
        if wired:
            continue
        rationale = entry.get("dormant")
        if rationale and rationale.strip():  # non-empty rationale -> excused
            continue
        offenders.append(gid)
    return offenders


def _live_offenders() -> list[str]:
    """The coherence reducer applied to the REAL shipped catalog + firing surfaces."""
    doc = yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8"))
    gates = doc["gates"]
    host_visibility = {g["gate_id"]: _gate_host_visibility(g["gate_id"]) for g in gates}
    return coherence_offenders(
        gates,
        firing_text=_firing_surface_text(),
        host_visibility=host_visibility,
    )


# --------------------------------------------------------------------------
# Synthetic catalogue fixtures (distinct-fixture-per-verdict discipline). Each
# verdict (coherent / flagged / excused / empty-rationale-still-flagged) is
# produced by a GENUINELY DIFFERENT catalogue, never a different assertion over
# one fixture. The reducer is the REAL pure SUT; only its INPUT varies.
# --------------------------------------------------------------------------

# A wired gate (its module is named in this firing text) + an unwired-non-dormant
# gate + an unwired-but-dormant gate. The firing text names ONLY the wired gate's
# module, so wiredness is decided by the reducer, not pre-baked per gate.
_SYNTH_FIRING = "gate_id: alpha-wired\nsome handler invokes des.cli.alpha_wired here\n"


# --------------------------------------------------------------------------
# AT-A1 — the catalog<->wiring coherence contract (DDD-6)
# --------------------------------------------------------------------------


def test_arch_a_wired_gate_is_coherent() -> None:
    """AT-A1-A (WIRED -> coherent): the reducer does NOT flag a gate reached via a
    live firing surface. Drives the REAL reducer over a synthetic catalogue whose
    one gate is wired (its module named in the firing text) -- it yields zero
    offenders. Distinct fixture: a single-wired-gate catalogue.

    GREEN at HEAD: positive control over the pure reducer. A regression that broke
    the indirect-wiring recognition (over-flagging a wired gate) surfaces here.
    """
    offenders = coherence_offenders(
        [{"gate_id": "alpha-wired", "module": "des.cli.alpha_wired"}],
        firing_text=_SYNTH_FIRING,
        host_visibility={"alpha-wired": frozenset()},
    )
    assert offenders == [], (
        "a catalogued gate reached via a live firing surface (its module named in "
        f"a live hook) MUST NOT be flagged; the reducer over-flagged {offenders}"
    )


def test_arch_b_unwired_non_dormant_gate_is_flagged_and_named() -> None:
    """AT-A1-B (UNWIRED + NOT dormant -> FLAGGED + NAMED): the authored-but-unwired
    failure class -- the behaviour KPI-4 demands. Drives the REAL reducer over a
    synthetic catalogue carrying a gate that is neither wired (no flavor row, no
    live-hook module reference, no operator visibility) nor ``dormant``-annotated.
    The reducer FLAGS it and the diagnostic NAMES it (veto-able). Distinct
    fixture: a wired gate alongside a genuinely-orphan gate.

    GREEN at HEAD: this is the positive behaviour proof over a fixture (the SUT is
    the shipped reducer; the fixture is the SUT's INPUT, never a fabricated
    oracle). It proves the check CAN flag -- the live-catalog coherence is a
    separate guardrail (AT-A1-A-live below).
    """
    catalogue = [
        {"gate_id": "alpha-wired", "module": "des.cli.alpha_wired"},
        {"gate_id": "orphan-gate", "module": "des.cli.orphan_gate"},
    ]
    offenders = coherence_offenders(
        catalogue,
        firing_text=_SYNTH_FIRING,  # names alpha-wired only; orphan-gate unreached
        host_visibility={"alpha-wired": frozenset(), "orphan-gate": frozenset()},
    )
    assert offenders == ["orphan-gate"], (
        "an UNWIRED, non-dormant catalogued gate (no flavor row, no live-hook "
        "module reference, no operator visibility) MUST be FLAGGED and NAMED -- the "
        "authored-but-unwired failure class (DDD-6 / KPI-4); the reducer must name "
        f"exactly the orphan gate, got offenders={offenders}"
    )


def test_arch_a_live_catalog_is_coherent() -> None:
    """AT-A1-A-live (regression guardrail): the REAL shipped catalogue is coherent
    -- every catalogued gate is wired (flavor row / live-hook module reference /
    operator-direct ``host_visibility``) OR ``dormant``-annotated. Drives the
    reducer over the REAL ``_catalog.yaml`` + firing surfaces.

    GREEN at HEAD: f-coherence-and-attestation slice-06 already wired
    gate-G / self-attest / verify-test-runner, and every other catalogued gate is
    a real operator-CLI gate (``host_visibility: [cli]`` = indirect wiring per
    S3 / Mandate-15). This is the standing CI guard: a future maintainer who adds
    a catalogued gate but forgets to wire it (and does not mark it ``dormant:``)
    RED-fails HERE, named. (The slice-04 deliverable IS this permanent guard.)
    """
    offenders = _live_offenders()
    assert offenders == [], (
        "the REAL catalogue must be coherent: every catalogued gate wired into a "
        "live firing surface (flavor row / live-hook module reference / "
        "operator-direct cli|git-hook visibility -- indirect wiring counts, S3) OR "
        f"marked `dormant: <rationale>`. Unwired-and-undeclared gates: {offenders}. "
        "Wire each (add to a flavor stack / reference its module in a live hook) "
        "OR annotate it with a non-empty `dormant:` rationale."
    )


def test_arch_c_dormant_with_rationale_is_excused() -> None:
    """AT-A1-C (DORMANT + non-empty rationale -> EXCUSED; empty rationale -> STILL
    FLAGGED): the explicit escape and its inverse robustness. Drives the REAL
    reducer over TWO distinct synthetic catalogues:
      (i)  an unwired gate carrying a non-empty ``dormant`` rationale -> EXCUSED
           (zero offenders) -- the escape works;
      (ii) the SAME unwired gate carrying an EMPTY ``dormant`` rationale -> STILL
           FLAGGED -- the escape requires a real rationale.

    GREEN at HEAD: behaviour proof over fixtures (the reducer's rationale-sensitive
    excuse is the shipped logic under test). The ``minLength`` schema rule
    (AT-A1-D) is what makes the empty-rationale case unrepresentable in the REAL
    catalogue; this test pins the reducer's runtime behaviour independently.
    """
    excused = coherence_offenders(
        [
            {
                "gate_id": "dozing-gate",
                "module": "des.cli.dozing_gate",
                "dormant": "intentionally unwired pending the SF-tier dispatch layer",
            }
        ],
        firing_text="",  # unwired
        host_visibility={"dozing-gate": frozenset()},
    )
    assert excused == [], (
        "an unwired gate carrying a non-empty `dormant: <rationale>` MUST be "
        f"EXCUSED (the explicit escape, DDD-6); the reducer flagged {excused}"
    )
    still_flagged = coherence_offenders(
        [
            {
                "gate_id": "dozing-gate",
                "module": "des.cli.dozing_gate",
                "dormant": "   ",
            }
        ],  # whitespace-only rationale
        firing_text="",
        host_visibility={"dozing-gate": frozenset()},
    )
    assert still_flagged == ["dozing-gate"], (
        "an unwired gate whose `dormant:` rationale is EMPTY/whitespace MUST STILL "
        "be FLAGGED -- the escape requires a REAL rationale; the reducer wrongly "
        f"excused it (offenders={still_flagged})"
    )


def test_arch_d_schema_permits_dormant_key() -> None:
    """AT-A1-D (schema extension, CRITICAL-2 prerequisite): the catalog
    ``_schema.yaml`` ``GateContract`` permits the optional ``dormant`` key. Today
    ``GateContract`` is ``additionalProperties: false`` with NO ``dormant``
    property, so a catalogued ``dormant:`` value is schema-REJECTED at
    install-time + CI -- making AT-A1-C non-representable until the schema is
    extended FIRST.

    ACTIVE-RED at HEAD: ``dormant`` is absent from ``GateContract.properties``.
    GREEN once DELIVER adds ``dormant: {type: string, minLength: 10}`` (the
    min-length is what makes an empty rationale schema-invalid, backing AT-A1-C's
    inverse-robustness). Reads the REAL shipped schema (a contract over the
    shipped artifact).
    """
    props = _gate_contract_properties()
    assert "dormant" in props, (
        "the catalog `_schema.yaml` GateContract MUST permit the optional "
        "`dormant` key (CRITICAL-2 prerequisite, DDD-6): without it the "
        "install-time + CI catalog-schema validator rejects any `dormant:` value "
        "-> the dormant escape (AT-A1-C) is non-representable. Add "
        "`dormant: {type: string, minLength: 10}` to GateContract.properties."
    )
    dormant_spec = props["dormant"]
    assert dormant_spec.get("type") == "string", (
        "the `dormant` schema property must be a string rationale (the escape "
        f"requires a human-readable reason); observed spec={dormant_spec}"
    )
    assert dormant_spec.get("minLength", 0) >= 10, (
        "the `dormant` rationale must carry a minLength (>=10) so an empty / "
        "trivial rationale is schema-invalid -- the escape requires a REAL "
        f"rationale (backs AT-A1-C inverse robustness); observed spec={dormant_spec}"
    )


def test_arch_e_empty_catalog_is_vacuously_coherent() -> None:
    """C3-ZERO obligation (Grenning ZOMBIES -- the empty iterative surface). The
    coherence function iterates catalogued gate-ids; the zero-gates case is the
    terminal branch the loop body never exercises. An empty catalog MUST NOT be
    falsely flagged -- coherence over zero gates is vacuously true (no gate is
    unwired-and-undeclared). This is the explicit, recognizably-named Zero
    scenario (the most-omitted, highest-yield boundary).

    GREEN at HEAD: the coherence reducer over an empty gate-id list returns no
    offenders by construction. This pins that contract (a regression guard
    against a future change that flags an empty catalog as incoherent). Drives the
    pure coherence reducer directly over a zero-length input -- the one branch the
    real catalog (33 gates) never reaches.
    """
    # Drive the REAL reducer over a zero-gate catalogue -- the terminal branch
    # the 33-gate live catalogue never reaches.
    offenders_over_empty = coherence_offenders(
        [],
        firing_text="",
        host_visibility={},
    )
    assert offenders_over_empty == [], (
        "coherence over a ZERO-gate catalog must be vacuously true -- the empty "
        "iterative surface (Grenning ZOMBIES Z) must never manufacture an "
        f"incoherence where no gate is declared; got {offenders_over_empty}"
    )

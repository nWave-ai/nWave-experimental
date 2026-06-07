"""Domain types for slice-04 -- the APPLICABILITY-AWARE feature-end done-gate.

slice-04 of fix-feature-end-ws-gate-applicability (env-e2e + coverage-map legs,
Atlas-APPROVED 2026-06-06). Every domain noun in the slice-04 Gherkin is
expressed once here as a typed enum (Mandate-12 criterion 1 -- the domain types
module exists with typed enums for every domain noun used in Gherkin). Step
bodies and the composition service consume these typed parameters; no raw ``str``
is passed where a domain enum exists.

The behaviour this slice specifies (verified from the ratified DESIGN at HEAD
``ceb19f6a0``, ``feature-delta.md`` slice-04 DDD-1..DDD-6): the feature-end cycle
has THREE refusing legs; slices 01-03 fixed only the walking-skeleton floor (leg
1). slice-04 makes the env-e2e leg (leg 2) and the coverage-map leg (leg 3)
applicability-aware:

  * leg 2 (env-e2e) -- when the walking-skeleton floor grants NOT_APPLICABLE, the
    env-e2e leg is inapplicable by the SAME mechanical delta cross-check (the
    feature ships no installable artifact). The cycle SKIPS the env-e2e
    subprocess and mints a DISTINCT ``EnvironmentalE2eNotApplicable`` marker
    (NEVER a false ``EnvironmentalE2eVerified``). A feature whose delta ADDS a
    new installable root is WS-FAILed (slice-03) -> the env-e2e NA branch is
    never reached: the dodge is CAUGHT.
  * leg 3 (coverage-map) -- opt-in-until-adopted via a REPO-LEVEL switch
    ``coverage_map_adoption`` (``"active" | "inactive"``, absent-key ⇒
    inactive) read from ``repo_root/.nwave/des-config.json`` through the standard
    ``DESConfig`` loader. NA is granted ONLY while adoption is inactive
    repo-wide AND the map is genuinely absent -> the cycle mints
    ``CoverageMapNotApplicableAt{Distill,Deliver}Exit``. A present-but-half-baked
    map, an active-adoption absent map, and a feature self-shipping its OWN
    ``des-config.json`` are ALL CAUGHT (held to the real verify / the repo
    switch). A malformed repo switch degrades toward MORE rigour (active /
    hard-verify), the OPPOSITE direction of an absent key (inactive / NA).

  The downstream backstop: ``des verify-integrity`` reconciles each applicable
  required record by itself OR its NA marker. A leg with NEITHER record is still
  caught (``FeatureEndCycleIncomplete``) -- slice-04 does NOT weaken the
  silent-skip guard.

None of the NA arms exist at HEAD -- the cycle's ``_run_walking_skeleton_gate``
returns a proceed-Path (not a distinguished NA), so the env-e2e leg runs and
false-refuses on ``GateExit.MISSCOPED=3``; the coverage leg hard-refuses on an
absent ``distill/coverage-map.md`` with no adoption switch. So the HONEST-NA
slice-04 scenarios RED-fail for the right reason (MISSING_FUNCTIONALITY); the
dodge-catch scenarios already pass at HEAD (the dodge IS caught today by the
hard-refuse) -- see the per-scenario RED/green breakdown in the step module.
"""

from __future__ import annotations

from enum import Enum


class FeatureShape(str, Enum):
    """The shape of the staged feature whose feature-end-cycle verdict is decided.

    Each value stages a feature (and, where the leg keys on git, a REAL git
    work-tree) so the divergence is keyed on the feature's actual on-disk /
    in-delta signature, never on a declared field. The walking-skeleton manifest
    declaration (``walking_skeleton_applicable: false`` + a non-empty rationale)
    is IDENTICAL across the env-e2e pair; only the git delta differs.

    HONEST_NON_INSTALLABLE
        -- Pair A1: a monorepo-internal feature whose git delta adds NO new
           build-system file; the WS floor grants NA; the cycle propagates NA to
           the env-e2e leg and mints ``EnvironmentalE2eNotApplicable``. The
           feature-delta carries no ``## Environmental E2E`` block.

    DODGE_ADDS_INSTALLABLE
        -- Pair A2: the feature's git delta ADDS a new ``pyproject.toml`` at a new
           root (genuinely installable) yet declares ``walking_skeleton_applicable:
           false``. The WS floor catches the lie (delta cross-check, slice-03) ->
           the cycle refuses at leg 1; the env-e2e NA branch is NEVER reached. No
           NA marker is minted.

    HONEST_NO_COVERAGE_INACTIVE
        -- Pair B1: repo adoption-switch INACTIVE; the feature has NO
           ``distill/coverage-map.md``. The coverage leg grants NA and mints the
           two ``CoverageMapNotApplicableAt*`` markers.

    DODGE_HALF_BAKED_MAP
        -- Pair B2: repo adoption-switch INACTIVE; the feature HAS a
           structurally-incomplete ``distill/coverage-map.md`` (a lone heading, no
           mandatory sections). A PRESENT map is ALWAYS held to the real §5.3
           verify, never NA -> the verify refuses with ``StructuralIncomplete``; no
           NA marker is minted. The ``StructuralIncomplete`` token POSITIVELY
           witnesses the coverage leg was REACHED.

    DODGE_ACTIVE_NO_MAP
        -- Pair B3: repo adoption-switch ACTIVE; the feature has NO
           ``distill/coverage-map.md``. Active adoption holds every feature to the
           real verify -> hard-refuse with ``SignoffMissing`` (absent file); no NA
           marker. The ``SignoffMissing`` token POSITIVELY witnesses the coverage
           leg was REACHED under active adoption.

    PRESENT_INCOMPLETE_MAP_ACTIVE
        -- Pair B4: repo adoption-switch ACTIVE; the feature HAS a present-but-
           structurally-incomplete ``distill/coverage-map.md``. The real §5.3
           verify runs and refuses with ``StructuralIncomplete`` -> the cycle is
           held to the real check and NEVER records NA. (A genuinely human-signed
           map's verified PASS is the production verify core's own contract,
           covered by the oss-feature-end verified-path ATs, not slice-04's NA
           mechanism. B4 here pins the slice-04 invariant: a PRESENT map is really
           checked, never waved through as NA -- the ``StructuralIncomplete`` token
           witnesses the coverage leg was REACHED.)

    SELF_GRANTED_NA_DODGE
        -- Pair B5: the REPO switch is ACTIVE; the FEATURE ships its OWN
           ``feature_dir/.nwave/des-config.json`` declaring ``coverage_map_adoption:
           inactive`` (attempting to self-grant NA); no ``distill/coverage-map.md``.
           The cycle reads the REPO-level switch, IGNORING the feature's
           self-shipped config -> the active repo switch wins -> hard-refuse; no NA
           marker. Proves a feature CANNOT flip its own adoption state.

    DEGRADE_ABSENT_KEY
        -- Pair B6a: the repo ``des-config.json`` is present + parseable but carries
           NO ``coverage_map_adoption`` key; no map. Absent key ⇒ inactive
           (permissive NA) -> NA markers minted.

    DEGRADE_MALFORMED_FILE
        -- Pair B6b: the repo ``des-config.json`` is malformed / unreadable JSON; no
           map. Malformed file ⇒ active (hard-verify, toward MORE rigour) ->
           hard-refuse; no NA marker. The OPPOSITE degrade direction to B6a.

    SILENT_SKIP_LEG
        -- Pair C2: a feature whose ledger carries NEITHER the verified record NOR
           the NA marker for a required leg (simulating a leg silently skipped).
           ``des verify-integrity`` still catches it as ``FeatureEndCycleIncomplete``
           -- the slice-04 NA mechanism did not weaken the silent-skip backstop.
    """

    HONEST_NON_INSTALLABLE = "honest_non_installable"
    DODGE_ADDS_INSTALLABLE = "dodge_adds_installable"
    HONEST_NO_COVERAGE_INACTIVE = "honest_no_coverage_inactive"
    DODGE_HALF_BAKED_MAP = "dodge_half_baked_map"
    DODGE_ACTIVE_NO_MAP = "dodge_active_no_map"
    PRESENT_INCOMPLETE_MAP_ACTIVE = "present_incomplete_map_active"
    SELF_GRANTED_NA_DODGE = "self_granted_na_dodge"
    DEGRADE_ABSENT_KEY = "degrade_absent_key"
    DEGRADE_MALFORMED_FILE = "degrade_malformed_file"
    SILENT_SKIP_LEG = "silent_skip_leg"


class CycleOutcome(str, Enum):
    """The operator-observable outcome of one ``des feature-end run`` invocation.

    PROCEEDS_PAST_LEG -- the cycle did NOT refuse at the leg under test; the leg
                         was granted NA (or verified) and the cycle moved past it.
                         Derived from the cycle NOT emitting that leg's refusal.
    REFUSES           -- the cycle fail-closed at the leg under test (exit
                         non-zero); the leg was held to the real gate / verify.
    """

    PROCEEDS_PAST_LEG = "proceeds_past_leg"
    REFUSES = "refuses"


class LegMarker(str, Enum):
    """A ledger event name the cycle mints (or must NOT mint) for an applicable leg.

    These are the NEW NA-marker event names slice-04 introduces plus the existing
    verified records they stand in place of -- the audit vocabulary the divergence
    pair asserts on. They are read back from the raw ledger JSONL (a pure
    filesystem read, never a ``des.*`` import -- the S2 driving-port-only
    boundary).

    ENVIRONMENTAL_E2E_NOT_APPLICABLE
        -- the NEW env-e2e NA marker (DDD-2). Minted on the WS-NA propagation
           path; reconciles the env-e2e leg in place of the verified record.
    ENVIRONMENTAL_E2E_VERIFIED
        -- the positive-proof env-e2e record. MUST NOT be minted on the NA path
           (minting it on an un-run leg would be theater, DDD-2).
    ENVIRONMENTAL_E2E_GATE_RAN
        -- the env-e2e heartbeat ("the cycle reached this leg"). The downstream
           required-set already demands it; the NA path still appends it.
    COVERAGE_MAP_NOT_APPLICABLE_AT_DISTILL_EXIT
        -- the NEW coverage-map NA marker at the distill touchpoint (DDD-3).
    COVERAGE_MAP_NOT_APPLICABLE_AT_DELIVER_EXIT
        -- the NEW coverage-map NA marker at the deliver touchpoint (DDD-3).
    COVERAGE_MAP_VERIFIED_AT_DISTILL_EXIT
        -- the coverage-map verified record (today's path, B4). MUST NOT be minted
           on a refused / NA path.
    COVERAGE_MAP_VERIFIED_AT_DELIVER_EXIT
        -- the coverage-map verified record at the deliver touchpoint (B4).
    """

    ENVIRONMENTAL_E2E_NOT_APPLICABLE = "EnvironmentalE2eNotApplicable"
    ENVIRONMENTAL_E2E_VERIFIED = "EnvironmentalE2eVerified"
    ENVIRONMENTAL_E2E_GATE_RAN = "EnvironmentalE2eGateRan"
    COVERAGE_MAP_NOT_APPLICABLE_AT_DISTILL_EXIT = (
        "CoverageMapNotApplicableAtDistillExit"
    )
    COVERAGE_MAP_NOT_APPLICABLE_AT_DELIVER_EXIT = (
        "CoverageMapNotApplicableAtDeliverExit"
    )
    COVERAGE_MAP_VERIFIED_AT_DISTILL_EXIT = "CoverageMapVerifiedAtDistillExit"
    COVERAGE_MAP_VERIFIED_AT_DELIVER_EXIT = "CoverageMapVerifiedAtDeliverExit"


class IntegrityVerdict(str, Enum):
    """The verdict ``des verify-integrity`` reports over a feature's ledger.

    RECONCILES_APPLICABLE_LEG
        -- ``verify-integrity`` does NOT report the leg-under-test's required
           record as missing: the leg's NA marker reconciled it (Pair C1). The
           leg the slice-04 NA mechanism made applicable-aware is satisfied.
    MISSING_LEG_RECORD
        -- ``verify-integrity`` reports ``FeatureEndCycleIncomplete`` whose
           ``missing_records`` NAMES the leg-under-test's required record: a leg
           that minted NEITHER the verified record NOR the NA marker is still
           caught (Pair C2 -- the silent-skip backstop is intact).
    """

    RECONCILES_APPLICABLE_LEG = "reconciles_applicable_leg"
    MISSING_LEG_RECORD = "missing_leg_record"


class ReasonMarker(str, Enum):
    """A substring identifying WHICH cause a cycle refusal / verdict reports.

    ADDED_INSTALLABLE_PATH
        -- a token of the WS-floor diagnostic naming the SPECIFIC delta-added
           build-system path when the env-e2e dodge (A2) adds a new installable
           root yet declares not-applicable. Kept in sync with the staged
           added-path basename (slice-03 ``new_pkg``).
    SIGNOFF_MISSING
        -- the coverage-map refusal token the verify core reports when the
           ``distill/coverage-map.md`` is ABSENT under active adoption
           (``coverage_map_verify_service.py:328-333`` -> ``SignoffMissing``).
           Witnessing this token in the refusal reason POSITIVELY PROVES the
           coverage leg was REACHED (B3/B5/B6b) -- the absent-file refusal can only
           surface once the cycle propagated WS-NA -> env-e2e-NA past leg 2.
    STRUCTURAL_INCOMPLETE
        -- the coverage-map refusal token the verify core reports when a PRESENT
           but structurally-incomplete map (missing a mandatory section / wrong L1
           order) is held to the real §5.3 verify
           (``coverage_map_verify_service.py:341-346`` -> ``StructuralIncomplete``).
           Witnessing this token POSITIVELY PROVES the coverage leg was REACHED and
           a present map is ALWAYS really verified, never NA (B2/B4).
    """

    ADDED_INSTALLABLE_PATH = "new_pkg"
    SIGNOFF_MISSING = "SignoffMissing"
    STRUCTURAL_INCOMPLETE = "StructuralIncomplete"


__all__ = [
    "CycleOutcome",
    "FeatureShape",
    "IntegrityVerdict",
    "LegMarker",
    "ReasonMarker",
]

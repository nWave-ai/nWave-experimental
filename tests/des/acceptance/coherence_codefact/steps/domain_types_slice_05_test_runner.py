"""Typed domain vocabulary for the f-coherence-and-attestation slice-05 ATs.

slice-05 (the LAST slice, JOB-028): the per-language ``TestRunnerPort`` resolved
from the installed env by FILESYSTEM lockfile inspection (never hardcoded pytest)
+ the §V.B ATs@slice / full-suite-once@feature-end allocation + the
removal-of-obsolete (C10: the hardcoded-pytest-over-whole-tree at every
commit-slice is SUPERSEDED).

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the slice-05
Gherkin names is expressed once here as a typed enum / frozen dataclass, so the
composition methods consume typed parameters (no raw ``str`` where an enum
exists). The DSL emerges from these typed concepts -- the runner-resolution
scenario ranges over the LOCKED ``(lockfile -> runner)`` mapping table (a
``@parametrize``-shaped Scenario Outline) rather than over decorator
proliferation.

slice-05 REUSES the §17 GateVerdict set for the INDETERMINATE degrade
(ADR-GV-001, CONSUMED unchanged, no sixth -- C6). ``pytest`` is the nWave-dev
DOGFOOD runner BEHIND the port, NOT the universal executor (C3); these types
name target runners abstractly so a non-Python target (domain example 2,
``acme-web`` TypeScript/``vitest``) is a first-class case.

These types are TEST-LOCAL (they never import production code) -- the ATs drive
the SUT only through composition-root driving ports / the real ``des`` subprocess
(Mandate-13).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# §17 GateVerdict -- the FIVE verdicts (ADR-GV-001), CONSUMED unchanged. No
# sixth (C6). slice-05 uses only INDETERMINATE (the unrecognized-runner
# degrade-LOUD), but the AT-side mirror carries the full set so the assertion
# can prove the degrade landed on one of the LOCKED five, never a sixth.
# ---------------------------------------------------------------------------


class GateVerdict(Enum):
    """The §17 uniform-failure-machine verdict set (ADR-GV-001, 5 verdicts)."""

    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    UNVERIFIED = "unverified"
    INDETERMINATE = "indeterminate"


# The LOCKED §17 verdict-token set -- the unrecognized-runner degrade must be
# INDETERMINATE, and it must be ONE of these (never a sixth, C6).
LOCKED_GATE_VERDICTS: frozenset[str] = frozenset(v.value for v in GateVerdict)


# ---------------------------------------------------------------------------
# slice-05 scenario vocabulary -- the per-language test runners + the lockfiles
# that resolve them. Resolution is by FILESYSTEM inspection of the installed
# target (lockfile / build-manifest presence), NEVER a hardcoded pytest
# (C3 / OB-RUNNER / §V.A). The (lockfile -> runner) mapping below mirrors the
# DESIGN OB-RUNNER resolution registry; DELIVER owns the production registry,
# this AT-side table is the CONTENT-DISTINCT fixture per case.
# ---------------------------------------------------------------------------


class TargetRunner(Enum):
    """A per-language test runner the ``TestRunnerPort`` resolves to.

    Abstract runner identities (NOT the concrete binary argv) -- the observable
    the AT asserts on is "which runner the port resolved", not how it shells
    out. ``pytest`` is the nWave-dev DOGFOOD runner behind the port, one row
    among equals -- NEVER the universal executor (C3).
    """

    PYTEST = "pytest"
    VITEST = "vitest"
    GO_TEST = "go-test"
    CARGO_TEST = "cargo-test"


# The CONTENT-DISTINCT lockfile fixtures per recognized-runner case. Each case
# writes a DIFFERENT marker file into a fresh tmp_path target so a deterministic
# resolver cannot map two distinct inputs to the same runner: a resolver that
# always returns pytest RED-fails the vitest/go/cargo rows.
#
#   (lockfile filename, lockfile content) -> resolved TargetRunner
#
# The content is a minimal-but-real manifest body so the resolver inspects a
# genuine file, not an empty touch -- (filesystem inspection of the INSTALLED
# target, §V.A). `package.json` carries a `vitest` devDependency so the resolver
# can distinguish npm-test=vitest; go.mod / Cargo.toml are language-unambiguous.
@dataclass(frozen=True)
class LockfileFixture:
    """A recognized-runner case: the lockfile to plant + the runner it resolves to."""

    filename: str
    content: str
    runner: TargetRunner


# The recognized-runner resolution table (CONTENT-DISTINCT per row -- §V.A).
RECOGNIZED_LOCKFILES: tuple[LockfileFixture, ...] = (
    LockfileFixture(
        filename="pyproject.toml",
        content='[project]\nname = "acme-svc"\n[tool.pytest.ini_options]\n',
        runner=TargetRunner.PYTEST,
    ),
    LockfileFixture(
        filename="package.json",
        content='{\n  "name": "acme-web",\n  "devDependencies": {"vitest": "^1.0.0"}\n}\n',
        runner=TargetRunner.VITEST,
    ),
    LockfileFixture(
        filename="go.mod",
        content="module github.com/acme/svc\n\ngo 1.22\n",
        runner=TargetRunner.GO_TEST,
    ),
    LockfileFixture(
        filename="Cargo.toml",
        content='[package]\nname = "acme-cli"\nedition = "2021"\n',
        runner=TargetRunner.CARGO_TEST,
    ),
)

# Lookup by lockfile filename (the Gherkin Scenario-Outline parameter token).
RECOGNIZED_BY_FILENAME: dict[str, LockfileFixture] = {
    fx.filename: fx for fx in RECOGNIZED_LOCKFILES
}


# The unrecognized-target fixture (AT-17): a target carrying NO recognized
# lockfile -- an unsupported language (domain example 2 counter-case `elixir`:
# `mix.exs`). The resolver MUST degrade LOUD to INDETERMINATE (N=0), NEVER a
# hardcoded-pytest fallback, never silent-pass (C3 / §17).
UNRECOGNIZED_LOCKFILE_FILENAME = "mix.exs"
UNRECOGNIZED_LOCKFILE_CONTENT = "defmodule Acme.MixProject do\n  use Mix.Project\nend\n"


# ---------------------------------------------------------------------------
# slice-05 allocation vocabulary -- the ATs@slice / full-suite-once@feature-end
# split (§V.B) + the removal-of-obsolete (C10).
# ---------------------------------------------------------------------------


# The DISCRIMINATING phrase of the obsolete hardcoded-pytest-over-whole-tree the
# removal-AT (AT-19) keys on. It is the §V.B "current divergence to correct" the
# C10 removal supersedes: the contract suite runs `pytest -m "<marker>"` over the
# WHOLE tree at EVERY commit-slice. The marker literal `unit or integration or
# acceptance` (run_contract_gate.py `_CONTRACT_MARKER`) is the discriminating
# token -- a multi-word phrase unique to the obsolete whole-tree run, never a
# common substring (the prose-surface discriminating-phrase rule, Mandate-13).
OBSOLETE_WHOLE_TREE_MARKER = "unit or integration or acceptance"


@dataclass(frozen=True)
class RunnerResolution:
    """The observable slice of a ``TestRunnerPort.resolve`` the slice-05 ATs assert on.

    Port-exposed names only (Mandate-8 universe discipline): the resolved runner
    identity OR the §17 INDETERMINATE degrade + the reason it names -- NEVER an
    internal resolver field, never a line number.

    ``runner``   -- the resolved ``TargetRunner`` token when a recognized
                    lockfile was found (the resolver returned a runner adapter).
    ``verdict``  -- the §17 GateVerdict token when the runner could NOT be
                    resolved (unrecognized lockfile / unsupported language ->
                    INDETERMINATE, degrade-LOUD, N=0).
    ``reason``   -- the non-empty reason the resolver names on the INDETERMINATE
                    degrade (Invariant 2 -- no silent degrade; it MUST NOT name a
                    hardcoded-pytest fallback).
    """

    runner: str | None
    verdict: str | None
    reason: str | None


@dataclass(frozen=True)
class SliceGateScope:
    """The observable slice of a slice-scoped contract-gate RUN (AT-18).

    Port-exposed names only: the set of test node-ids the gate actually RAN when
    scoped to ONE slice, and whether the whole-tree run was invoked. The AT
    asserts the gate RUNS the slice's ATs ONLY (proportional / fast) and does
    NOT run the whole tree (the §V.B re-allocation).

    ``ran_node_ids``        -- the node-ids the slice-scoped gate RAN (the slice's
                               own ATs). Empty / None when no slice-scoped RUN
                               happened.
    ``ran_whole_tree``      -- True iff the gate ran the WHOLE-tree contract suite
                               (the obsolete behavior the slice-gate re-scope
                               supersedes). The §V.B allocation requires this be
                               False for a slice-scoped gate.
    ``out_of_slice_ran``    -- node-ids the gate RAN that do NOT belong to the
                               entering slice (a leak past the slice scope). Empty
                               on a correctly-scoped run.
    """

    ran_node_ids: tuple[str, ...] | None
    ran_whole_tree: bool | None
    out_of_slice_ran: tuple[str, ...] | None


@dataclass(frozen=True)
class FeatureEndAllocation:
    """The observable slice of the feature-end full-suite leg (AT-19).

    Port-exposed names only: whether the feature-end cycle runs a DISTINCT clean
    full-suite leg ONCE, and whether the obsolete hardcoded-pytest-over-whole-tree
    at every commit-slice has been REMOVED.

    ``full_suite_leg_present`` -- True iff ``feature_end_cycle_service`` runs a
                                  distinct clean full-suite leg at feature-end
                                  (the §V.B "full-suite-once" allocation).
    ``obsolete_whole_tree_at_slice_present`` -- True iff the obsolete
                                  hardcoded-pytest-over-whole-tree at EVERY
                                  commit-slice is STILL present (the removal-AT
                                  requires this be False -- the C10 removal-absence).
    """

    full_suite_leg_present: bool | None
    obsolete_whole_tree_at_slice_present: bool | None

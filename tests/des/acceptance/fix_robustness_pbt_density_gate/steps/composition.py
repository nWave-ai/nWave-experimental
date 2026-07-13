"""Composition root for the fix-robustness-pbt-density-gate acceptance suite.

Mandate-12 criterion 2/3 + Pillar 3: the SUT is wired through the PRODUCTION
composition root -- the real ``scripts.cli.check_robustness_density`` CLI
invoked as a ``python -m`` subprocess. Slice-01 stages a real per-scenario
tmp workspace holding a ``unbounded-domains.yaml`` projection (a subset of
the M-feature ``component-manifest.yaml`` schema) and a real test file
carrying or omitting a ``# domain:``-tagged ``@given``. The CLI walks the
staged tree and exits 0/1/2.

ALL business logic lives in this module's service methods -- the single
source of truth. Step bodies in ``common_steps.py`` delegate to these
methods and never inline business logic (Mandate-12 criterion 3).

The five slices share this one composition root. The step-method vocabulary
(``given_*`` / ``when_*`` / ``then_*`` named in domain language) is the
shared contract (Mandate 10).

Slice-01 is layer 5 (WS @wiring_e2e, subprocess + real I/O). Per Mandate
9/11 the slice is example-only -- no PBT machinery is imported here. The
``check_robustness_density`` CLI is shipped (DELIVER, slice-01); DELIVER's
GREEN implementation is what the slice-01 ATs exercise via subprocess.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from des.cli import at_review_verdict
from scripts.hooks import subagent_stop_robustness_gate
from tests.common.in_process_cli import run_cli_in_process, run_hook_in_process
from tests.env_parity import seed_dev_checkout_marker

from .domain_types import DomainId, RobustnessGateExit


# The robustness gate CLI lives at ``scripts/cli/check_robustness_density.py``
# (feature-delta H1: hosted in ``scripts/cli/`` because the gate has no
# DES-runtime coupling). Invoke as ``python -m scripts.cli.check_robustness_density``
# from the repo root so PEP-420 namespace import of ``scripts.cli.*`` resolves.
_REPO_ROOT = Path(__file__).resolve().parents[5]

# Slice-04 fixture mutmut reports live committed in the suite directory
# (per M2 architect mandate: fixture-only, NEVER live mutmut invocation).
# The composition copies one fixture per scenario into the per-scenario tmp
# workspace; the production CLI's layer-2 branch reads the staged copy.
_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "mutmut"

# --- slice-04 mutmut fixture JSON schema (gate-internal contract) -----------
#
# The slice-04 fixture mutmut reports follow a MINIMAL gate-specific shape,
# documented inline here so the contract survives review without external
# references. The shape is intentionally narrower than mutmut's own
# ``.mutmut-cache`` because v1's CLI consumes only what the three-state R5
# logic requires; the gate is NOT a general mutmut report consumer. Future
# v2 (paired-falsifier fixture, backlog) MAY converge on the upstream
# schema; v1 declares its own minimal contract so slice-04 ships without
# coupling to mutmut's internal cache format (which differs across mutmut
# 2.x point releases).
#
# Top-level JSON object:
#   {
#     "mutmut_ran": bool,              // false ONLY for partial-truncation cases (gate-internal)
#     "positive_control": {
#       "seeded": bool,                // the probe per R5 Earned-Trust principle 13
#       "killed": bool                 // mutmut discriminates iff seeded && killed
#     },
#     "mutants": {                     // keyed by manifest `sut:` symbol verbatim
#       "<sut_symbol>": {
#         "killed":   int,             // >0 satisfies layer-2 (when positive_control valid)
#         "survived": int              // for diagnostics; gate uses `killed` for verdict
#       }
#     }
#   }
#
# The classification logic the production CLI's layer-2 branch must
# implement against this shape:
#   * JSON unparseable                 -> REPORT_MALFORMED       -> exit 3 (Unavailable)
#   * mutmut_ran == false               -> REPORT_MALFORMED       -> exit 3 (Unavailable)
#   * mutants == {}                     -> REPORT_EMPTY           -> exit 3 (Unavailable)
#   * declared sut NOT in mutants       -> REPORT_PARTIAL_MISSING -> exit 3 (Unavailable)
#   * positive_control.killed != true   -> POSITIVE_CONTROL_FAIL  -> exit 3 (Unavailable)
#   * mutants[sut].killed == 0          -> KILL_RATE_ZERO         -> exit 1 (NotFalsifiable)
#   * mutants[sut].killed >  0          -> KILL_RATE_POSITIVE     -> exit 0 (PASS)
_MUTMUT_FIXTURE_SCHEMA_DOC = __doc__  # Marker so grep finds this constant.


# A minimal well-formed ``unbounded-domains.yaml`` projection that conforms to
# the M-feature ``component-manifest.schema.json`` subset relevant at DISTILL.
# Slice-01 only exercises ``unbounded-input-domains[].id`` -- everything else
# in the schema is held constant per-scenario.
_DECLARATION_TEMPLATE = """\
schema-version: "1.0"
feature-id: fix-robustness-pbt-density-gate-fixture
unbounded-input-domains:
  - id: {domain_id}
    sut: tests/fixture/test_target.py::function_under_test
    domain: arbitrary input domain for the fixture function
    why-unbounded: arbitrary input space for slice-01 walking-skeleton fixture
    canonical-category: C6
    declared-at: design
"""


# A test file body that DOES tag a ``# domain:``-marked ``@given`` for the
# named declared domain id. Slice-01 only checks presence -- strategy
# triviality (layers 1+3) is slice-03's job, kill-rate (layer 2) is
# slice-04's.
_COVERED_TEST_BODY_TEMPLATE = '''\
"""Slice-01 walking-skeleton fixture test -- declares one PBT for domain {domain_id}."""

from hypothesis import given, strategies as st


# domain: {domain_id}
@given(payload=st.text())
def test_function_under_test_property(payload: str) -> None:
    """Trivial body -- slice-01 only verifies the # domain: tag is present."""
    assert isinstance(payload, str)
'''

# A test file body that contains NO ``# domain:``-tagged ``@given`` -- the
# declared domain is uncovered.
_UNCOVERED_TEST_BODY_TEMPLATE = '''\
"""Slice-01 walking-skeleton fixture test -- example-based, no @given for domain {domain_id}."""


def test_function_under_test_example() -> None:
    """Example-based -- declared domain id has no @given coverage in scope."""
    assert True
'''


# A deliberately unparseable YAML document for slice-01 AT3.
_MALFORMED_YAML_BODY = "schema-version: 1.0\nunbounded-input-domains: [unclosed-list\n"


# --- slice-02 declaration-state templates -----------------------------------
#
# Slice-02 introduces three declaration-state staging primitives that the
# slice-01 templates do NOT cover. Kept additive (Mandate-12 / no-refactor
# discipline). Each template is a per-scenario fixture body the composition
# stages on disk under a tmp workspace; the production CLI walks them.

# AT1: a parseable YAML document that is missing the
# ``unbounded-input-domains`` block entirely. The slice AT scope still has
# acceptance tests present -- the gate must refuse this configuration
# (RobustnessDeclarationMissing, exit 1). Closes the
# F-DES-PHASE-TELEMETRY-SINGLE-SOURCE silent-stale-pass pattern: a defaulted
# / silently-absent field is a degraded record, never a vacuous pass.
_BLOCK_MISSING_DECLARATION_BODY = """\
schema-version: "1.0"
feature-id: fix-robustness-pbt-density-gate-fixture
"""

# A trivial test file body present in the slice-02 AT scope so AT1's
# "...while acceptance tests exist in the scope" precondition is real --
# the gate's empty-declaration guard only fires when the slice has any AT.
_NEUTRAL_AT_BODY = '''\
"""Slice-02 fixture: a neutral acceptance test exists in scope (no @given)."""


def test_neutral_in_scope() -> None:
    """Example-based -- presence in AT scope is the only relevant property."""
    assert True
'''

# AT2: an explicitly-empty declaration carrying the M-schema's
# ``unbounded-input-domains-empty-rationale`` one-line rationale field. The
# gate accepts this as a legitimate "no unbounded domains" claim (exit 0);
# B6 places the honesty veto on M's DESIGN-wave reviewer upstream, not on
# this gate. The gate must NOT re-litigate.
_EXPLICIT_EMPTY_WITH_RATIONALE_BODY = """\
schema-version: "1.0"
feature-id: fix-robustness-pbt-density-gate-fixture
unbounded-input-domains: []
unbounded-input-domains-empty-rationale: "Feature is methodology-only; no SUT input domain to cover."
"""

# AT3: a DISTILL projection that carries a domain entry with
# ``declared-at: distill`` for an id that has no matching entry in the
# DESIGN component manifest. The gate rejects this at the provenance
# boundary (RobustnessProvenanceViolation, exit 1) per DECISION D1 --
# DISTILL projects, never authors.
_DISTILL_PROVENANCE_DECLARATION_TEMPLATE = """\
schema-version: "1.0"
feature-id: fix-robustness-pbt-density-gate-fixture
unbounded-input-domains:
  - id: {domain_id}
    sut: tests/fixture/test_target.py::function_under_test
    domain: arbitrary input domain authored fresh at DISTILL
    why-unbounded: arbitrary input space authored at DISTILL without DESIGN provenance
    canonical-category: C6
    declared-at: distill
"""

# The DESIGN component manifest fixture for AT3: parseable, well-formed,
# but contains NO entry matching the DISTILL projection's domain id. The
# provenance check must detect the missing back-reference.
_MANIFEST_WITHOUT_DOMAIN_TEMPLATE = """\
schema-version: "1.0"
feature-id: fix-robustness-pbt-density-gate-fixture
unbounded-input-domains:
  - id: some-other-unrelated-domain-{nonce}
    sut: tests/fixture/test_other.py::other_function_under_test
    domain: a different domain that the design did declare
    why-unbounded: present so the manifest is non-empty but does not back AT3's id
    canonical-category: C6
    declared-at: design
"""


# --- slice-03 genuineness-layer templates (anti-shallow-PBT, layers 1+3) ----
#
# Slice-03 introduces three shallow-PBT staging primitives. The production
# CLI must walk the AT-scope file AST and reject:
#   - layer 1: a @given strategy that is trivial-by-AST (st.just / narrow
#     sampled_from / narrow integers), including via single-hop module-local
#     indirection per B5 (the strategy reached through a helper return);
#   - layer 3: a test body whose ONLY assertion is a tautology
#     (assert True / assert x == x / assert result is not None as sole
#     assertion), including via single-hop module-local indirection.
#
# Slice-03 stages real test-file bodies that exhibit each shallow shape.
# The gate must classify them as shallow and emit RobustnessPBTShallow on
# stdout with exit 1 (CHECK_FAILED). The AT-scope file body is the input
# domain probed by the gate's own AST parser.

# AT1: trivial strategy reached via a SINGLE-HOP module-local helper.
# `_strategy()` returns `st.just("x")` so the @given site sees a Call to a
# Name; the layer-1 AST walker MUST follow the helper return one hop and
# classify the resolved expression as trivial. This is the canonical B5
# evasion the design explicitly closes for blocking layers.
_TRIVIAL_STRATEGY_VIA_HELPER_TEST_BODY_TEMPLATE = '''\
"""Slice-03 fixture: trivial @given strategy reached via single-hop helper (B5)."""

from hypothesis import given, strategies as st


def _strategy():
    """Module-local helper -- returns a trivial st.just strategy."""
    return st.just("only-this-one-value")


# domain: {domain_id}
@given(payload=_strategy())
def test_function_under_test_property(payload: str) -> None:
    """Body reaches into the SUT non-trivially so layer 3 alone would not flag it."""
    assert isinstance(payload, str)
    assert len(payload) > 0
'''


# AT2: tautology-only assertion reached via a SINGLE-HOP module-local
# helper. `_check(result)` returns `result == result` so the test body's
# only assertion is a Call to a Name; the layer-3 AST walker MUST follow
# the helper return one hop and classify the resolved expression as a
# tautology. Strategy is genuinely unbounded so layer 1 alone would not
# flag it.
_TAUTOLOGY_ASSERT_VIA_HELPER_TEST_BODY_TEMPLATE = '''\
"""Slice-03 fixture: tautology-only assertion reached via single-hop helper (B5)."""

from hypothesis import given, strategies as st


def _check(result):
    """Module-local helper -- returns a tautology (`result == result`)."""
    return result == result


# domain: {domain_id}
@given(payload=st.text())
def test_function_under_test_property(payload: str) -> None:
    """Body asserts only through a helper that returns a tautology."""
    result = payload.upper()
    assert _check(result)
'''


# AT3: adversarial test-file AST exhibiting the canonical indirect-
# parametrize-source evasion (V4 / R6 dogfood). `_cases()` returns a list,
# so `@pytest.mark.parametrize("x", _cases())` reaches the value list via
# a Call node; the gate's advisory candidate-(c) AST heuristic cannot
# classify the domain (open vs finite) and MUST emit a deterministic
# verdict (advisory-only on this path) WITHOUT CRASHING. This is the
# gate's own parser hardness probe -- the slice's highest-risk surface
# per the architect.
_ADVERSARIAL_INDIRECT_PARAMETRIZE_TEST_BODY_TEMPLATE = '''\
"""Slice-03 fixture: adversarial AST -- indirect parametrize source (V4)."""

import pytest


def _cases():
    """Module-local helper -- returns a list literal one hop away."""
    return ["alpha", "beta", "gamma"]


# domain: {domain_id}
@pytest.mark.parametrize("x", _cases())
def test_function_under_test_indirect_parametrize(x: str) -> None:
    """Indirect parametrize source: gate AST cannot classify the value list."""
    assert isinstance(x, str)
'''


@dataclass
class RobustnessGateResult:
    """Observable outcome of one ``check_robustness_density`` invocation.

    Universe entries are port-exposed only (CLI exit code + the diagnostic
    token written to stdout) -- never internal struct fields (Mandate 8).
    Slice-01 only asserts on ``exit_code``; later slices extend the universe
    to verdict tokens.
    """

    exit_code: RobustnessGateExit | None = None
    # slice-02 widens the universe with the human-surface diagnostic token
    # captured from stdout. Required because slice-02 distinguishes three
    # exit-1 sub-classes (coverage miss / declaration missing / provenance
    # violation) that share a single exit code -- the discriminating
    # observable lives in stdout, NOT in the exit code alone. Closes the
    # universe-too-narrow trap (research/closed-world-effect-assertion
    # 2026-05-15): a slice-02 AT that asserts on exit_code ONLY would
    # vacuously pass against the slice-01 CLI's accidental crashes.
    stdout: str = ""
    # slice-05 wiring universe extension: the wiring slice's discriminating
    # observables sit at a SECOND port surface beyond the gate CLI itself --
    # the verdict producer's ledger-write decision (AT1), the SubagentStop
    # hook chain's dispatch-block decision (AT2), and the producer-emitted
    # manifest's gate-refusal verdict (AT3). Each field below captures one
    # port-exposed observable per Mandate 8 universe-bound assertion. Earlier
    # slices leave these None -- their universe is exit_code + stdout only.
    verdict_record_written: bool | None = None
    verdict_producer_stderr: str = ""
    dispatch_blocked: bool | None = None
    hook_chain_diagnostic: str = ""


@dataclass
class RobustnessGateComposition:
    """Production composition root for the robustness PBT density gate CLI.

    Wires the real ``scripts.cli.check_robustness_density`` CLI as a
    ``python -m`` subprocess. The SSOT service methods below are the only
    place business logic lives -- step bodies delegate here.
    """

    repo_root: Path = field(default_factory=Path.cwd)
    result: RobustnessGateResult = field(default_factory=RobustnessGateResult)
    # slice-01 staging: per-scenario tmp dir holding the staged projection
    # file + the staged AT-scope test file. The CLI is invoked against this
    # workspace; all writes land OUTSIDE the source tree.
    _scenario_workspace: Path | None = field(default=None, init=False)
    _declaration_path: Path | None = field(default=None, init=False)
    _at_scope_dir: Path | None = field(default=None, init=False)
    _declared_domain_id: DomainId | None = field(default=None, init=False)
    # slice-02 adds an optional DESIGN component manifest path. When set,
    # the CLI is invoked with ``--component-manifest <path>`` so the gate
    # can perform the DECISION D1 provenance check. Slice-01 scenarios
    # leave this None -- the CLI runs without the flag, preserving the
    # slice-01 invocation shape verbatim.
    _component_manifest_path: Path | None = field(default=None, init=False)
    # slice-04 adds an optional fixture mutmut report path. When set, the
    # CLI is invoked with ``--mutmut-report <path>`` so the gate's
    # layer-2 mutmut-delta proxy branch can read the kill-rate / positive-
    # control JSON. Earlier slices leave this None -- the CLI runs without
    # the flag, preserving slice-01/02/03 invocation shapes verbatim.
    _mutmut_report_path: Path | None = field(default=None, init=False)

    # --- slice-01: walking-skeleton declared-domain-coverage check ----------

    def given_declared_domain_with_coverage(self, domain_id: DomainId) -> None:
        """Stage a projection declaring ``domain_id`` and a test covering it.

        Writes a per-scenario tmp workspace with two artifacts: the
        ``unbounded-domains.yaml`` declaring one domain with the given id,
        and a single test file in the AT scope carrying a
        ``# domain: {domain_id}``-tagged ``@given``-decorated test function.
        """
        workspace = Path(tempfile.mkdtemp(prefix="robust-gate-slice01-covered-"))
        declaration_path = workspace / "unbounded-domains.yaml"
        at_scope_dir = workspace / "at_scope"
        at_scope_dir.mkdir()
        declaration_path.write_text(
            _DECLARATION_TEMPLATE.format(domain_id=domain_id), encoding="utf-8"
        )
        (at_scope_dir / "test_target_property.py").write_text(
            _COVERED_TEST_BODY_TEMPLATE.format(domain_id=domain_id), encoding="utf-8"
        )
        self._scenario_workspace = workspace
        self._declaration_path = declaration_path
        self._at_scope_dir = at_scope_dir
        self._declared_domain_id = domain_id

    def given_declared_domain_without_coverage(self, domain_id: DomainId) -> None:
        """Stage a projection declaring ``domain_id`` and a test that does NOT cover it.

        Writes a per-scenario tmp workspace with the declaration file naming
        ``domain_id`` and a single example-based test file in the AT scope
        carrying NO ``@given`` (and therefore no ``# domain:`` tag).
        """
        workspace = Path(tempfile.mkdtemp(prefix="robust-gate-slice01-uncovered-"))
        declaration_path = workspace / "unbounded-domains.yaml"
        at_scope_dir = workspace / "at_scope"
        at_scope_dir.mkdir()
        declaration_path.write_text(
            _DECLARATION_TEMPLATE.format(domain_id=domain_id), encoding="utf-8"
        )
        (at_scope_dir / "test_target_example.py").write_text(
            _UNCOVERED_TEST_BODY_TEMPLATE.format(domain_id=domain_id), encoding="utf-8"
        )
        self._scenario_workspace = workspace
        self._declaration_path = declaration_path
        self._at_scope_dir = at_scope_dir
        self._declared_domain_id = domain_id

    def given_malformed_declaration(self) -> None:
        """Stage a per-scenario workspace with an unparseable declaration document.

        The CLI must reject the document at the parser boundary (exit 2)
        without crashing. The AT scope directory is still staged -- the CLI
        should never reach it because parsing fails first.
        """
        workspace = Path(tempfile.mkdtemp(prefix="robust-gate-slice01-malformed-"))
        declaration_path = workspace / "unbounded-domains.yaml"
        at_scope_dir = workspace / "at_scope"
        at_scope_dir.mkdir()
        declaration_path.write_text(_MALFORMED_YAML_BODY, encoding="utf-8")
        self._scenario_workspace = workspace
        self._declaration_path = declaration_path
        self._at_scope_dir = at_scope_dir

    # --- slice-02: empty-declaration guard + D1 provenance check ------------

    def given_declaration_missing_block_with_ats_in_scope(self) -> None:
        """Stage a parseable declaration that omits the unbounded block + a neutral AT.

        The declaration document is valid YAML but carries no
        ``unbounded-input-domains:`` block; the slice AT scope holds at
        least one acceptance test so the gate's empty-declaration guard
        precondition is satisfied. The gate must refuse this configuration
        (RobustnessDeclarationMissing, exit 1) -- absence is not a pass.
        """
        workspace = Path(tempfile.mkdtemp(prefix="robust-gate-slice02-missing-"))
        declaration_path = workspace / "unbounded-domains.yaml"
        at_scope_dir = workspace / "at_scope"
        at_scope_dir.mkdir()
        declaration_path.write_text(_BLOCK_MISSING_DECLARATION_BODY, encoding="utf-8")
        (at_scope_dir / "test_neutral_in_scope.py").write_text(
            _NEUTRAL_AT_BODY, encoding="utf-8"
        )
        self._scenario_workspace = workspace
        self._declaration_path = declaration_path
        self._at_scope_dir = at_scope_dir

    def given_explicit_empty_declaration_with_rationale(self) -> None:
        """Stage an explicit-empty declaration carrying the schema's rationale field.

        The legitimate "no unbounded domains" claim per the M schema's
        ``oneOf`` branch. The gate accepts this (exit 0); the honesty veto
        on the rationale lives upstream at M's DESIGN-wave reviewer (B6
        owned residue). No AT-scope contents required -- the explicit-empty
        path short-circuits the coverage walk.
        """
        workspace = Path(
            tempfile.mkdtemp(prefix="robust-gate-slice02-empty-rationale-")
        )
        declaration_path = workspace / "unbounded-domains.yaml"
        at_scope_dir = workspace / "at_scope"
        at_scope_dir.mkdir()
        declaration_path.write_text(
            _EXPLICIT_EMPTY_WITH_RATIONALE_BODY, encoding="utf-8"
        )
        self._scenario_workspace = workspace
        self._declaration_path = declaration_path
        self._at_scope_dir = at_scope_dir

    def given_distill_authored_domain_absent_from_manifest(
        self, domain_id: DomainId
    ) -> None:
        """Stage a distill-authored projection + a manifest that lacks the id.

        The DISTILL projection declares ``domain_id`` with
        ``declared-at: distill``; the staged DESIGN component manifest is
        well-formed but contains no entry with that id. The gate, invoked
        with ``--component-manifest <path>``, must detect the missing
        back-reference and exit 1 (RobustnessProvenanceViolation) per
        DECISION D1. Also stages a covered test file so the only failing
        check is provenance, not coverage -- isolating the AT3 universe.
        """
        workspace = Path(tempfile.mkdtemp(prefix="robust-gate-slice02-provenance-"))
        declaration_path = workspace / "unbounded-domains.yaml"
        manifest_path = workspace / "component-manifest.yaml"
        at_scope_dir = workspace / "at_scope"
        at_scope_dir.mkdir()
        declaration_path.write_text(
            _DISTILL_PROVENANCE_DECLARATION_TEMPLATE.format(domain_id=domain_id),
            encoding="utf-8",
        )
        # Nonce keeps the manifest's "other" id deterministically distinct
        # from the projection id across re-runs sharing a workspace prefix.
        manifest_path.write_text(
            _MANIFEST_WITHOUT_DOMAIN_TEMPLATE.format(nonce=domain_id),
            encoding="utf-8",
        )
        (at_scope_dir / "test_target_property.py").write_text(
            _COVERED_TEST_BODY_TEMPLATE.format(domain_id=domain_id),
            encoding="utf-8",
        )
        self._scenario_workspace = workspace
        self._declaration_path = declaration_path
        self._at_scope_dir = at_scope_dir
        self._component_manifest_path = manifest_path
        self._declared_domain_id = domain_id

    # --- slice-03: genuineness layers 1 + 3 (anti-shallow-PBT) --------------

    def given_trivial_strategy_via_helper(self, domain_id: DomainId) -> None:
        """Stage a covered projection + a test whose strategy is trivial-via-helper.

        Single-hop B5 evasion: the @given site sees a Call to a Name
        (``_strategy()``) whose return is ``st.just(...)``. The gate's
        layer-1 AST walker MUST follow the helper return one hop and
        classify the resolved expression as trivial -- emitting
        ``RobustnessPBTShallow`` on stdout with exit 1.
        """
        workspace = Path(tempfile.mkdtemp(prefix="robust-gate-slice03-trivial-helper-"))
        declaration_path = workspace / "unbounded-domains.yaml"
        at_scope_dir = workspace / "at_scope"
        at_scope_dir.mkdir()
        declaration_path.write_text(
            _DECLARATION_TEMPLATE.format(domain_id=domain_id), encoding="utf-8"
        )
        (at_scope_dir / "test_target_property.py").write_text(
            _TRIVIAL_STRATEGY_VIA_HELPER_TEST_BODY_TEMPLATE.format(domain_id=domain_id),
            encoding="utf-8",
        )
        self._scenario_workspace = workspace
        self._declaration_path = declaration_path
        self._at_scope_dir = at_scope_dir
        self._declared_domain_id = domain_id

    def given_tautology_assert_via_helper(self, domain_id: DomainId) -> None:
        """Stage a covered projection + a test whose only assert is tautology-via-helper.

        Single-hop B5 evasion: the test body's only assertion is a Call to
        a Name (``_check(result)``) whose return is ``result == result``.
        The gate's layer-3 AST walker MUST follow the helper return one
        hop and classify the resolved expression as a tautology -- emitting
        ``RobustnessPBTShallow`` on stdout with exit 1.
        """
        workspace = Path(
            tempfile.mkdtemp(prefix="robust-gate-slice03-tautology-helper-")
        )
        declaration_path = workspace / "unbounded-domains.yaml"
        at_scope_dir = workspace / "at_scope"
        at_scope_dir.mkdir()
        declaration_path.write_text(
            _DECLARATION_TEMPLATE.format(domain_id=domain_id), encoding="utf-8"
        )
        (at_scope_dir / "test_target_property.py").write_text(
            _TAUTOLOGY_ASSERT_VIA_HELPER_TEST_BODY_TEMPLATE.format(domain_id=domain_id),
            encoding="utf-8",
        )
        self._scenario_workspace = workspace
        self._declaration_path = declaration_path
        self._at_scope_dir = at_scope_dir
        self._declared_domain_id = domain_id

    def given_adversarial_indirect_parametrize(self, domain_id: DomainId) -> None:
        """Stage a covered projection + a test exhibiting the indirect parametrize source.

        R6 dogfood: the gate's own AST parser is the SUT here. The staged
        test file uses ``@pytest.mark.parametrize("x", _cases())`` -- the
        canonical V4 indirect-source case the gate cannot classify
        (advisory-only on this path per the architect spec). The gate MUST
        NOT crash; the AT body asserts a deterministic verdict (passing
        coverage walk because the @given is genuine, parametrize is
        unrelated to the genuineness layers).
        """
        workspace = Path(
            tempfile.mkdtemp(prefix="robust-gate-slice03-adversarial-ast-")
        )
        declaration_path = workspace / "unbounded-domains.yaml"
        at_scope_dir = workspace / "at_scope"
        at_scope_dir.mkdir()
        declaration_path.write_text(
            _DECLARATION_TEMPLATE.format(domain_id=domain_id), encoding="utf-8"
        )
        # Two files: the @given-covered file proving genuine coverage, plus
        # the adversarial indirect-parametrize file the gate's AST parser
        # must survive. Slice-04 will tighten this; slice-03 only proves
        # the parser does not crash on the V4 case.
        (at_scope_dir / "test_target_property.py").write_text(
            _COVERED_TEST_BODY_TEMPLATE.format(domain_id=domain_id),
            encoding="utf-8",
        )
        (at_scope_dir / "test_target_indirect_parametrize.py").write_text(
            _ADVERSARIAL_INDIRECT_PARAMETRIZE_TEST_BODY_TEMPLATE.format(
                domain_id=domain_id
            ),
            encoding="utf-8",
        )
        self._scenario_workspace = workspace
        self._declaration_path = declaration_path
        self._at_scope_dir = at_scope_dir
        self._declared_domain_id = domain_id

    # --- slice-04: genuineness layer 2 (mutmut-delta proxy, R5 3-state) -----

    def given_layer2_kill_rate_positive(self, domain_id: DomainId) -> None:
        """Stage a covered projection + a fixture mutmut report with positive kill-rate.

        Layer-2 happy path (R5 cell ``KILL_RATE_POSITIVE``): the fixture
        mutmut JSON declares the positive control as seeded AND killed
        (mutmut discriminates in this environment), and the declared sut
        symbol has at least one killed mutant. The gate's layer-2 branch
        MUST exit 0 -- the PBT discriminates a broken SUT from a correct
        one.

        M2 invariant: this stages a COMMITTED fixture JSON document and
        DOES NOT invoke live mutmut. The fixture lives under
        ``fixtures/mutmut/`` in the suite directory; the composition
        copies it into the per-scenario tmp workspace so the staged path
        is host-isolated.
        """
        self._stage_layer2_scenario(
            domain_id=domain_id,
            fixture_name="valid_killing.json",
            workspace_prefix="robust-gate-slice04-killrate-positive-",
        )

    def given_layer2_kill_rate_zero(self, domain_id: DomainId) -> None:
        """Stage a covered projection + a fixture mutmut report with kill-rate 0.

        Layer-2 refusal (R5 cell ``KILL_RATE_ZERO``): the fixture mutmut
        JSON declares the positive control as seeded AND killed (mutmut
        IS discriminating -- this is the gate-side proof the run is
        trustworthy), and the declared sut symbol has zero killed
        mutants. The gate's layer-2 branch MUST exit 1 emitting
        ``RobustnessPBTNotFalsifiable`` -- the PBT cannot tell a broken
        SUT from a correct one.
        """
        self._stage_layer2_scenario(
            domain_id=domain_id,
            fixture_name="zero_kills.json",
            workspace_prefix="robust-gate-slice04-killrate-zero-",
        )

    def given_layer2_report_untrustworthy(self, domain_id: DomainId) -> None:
        """Stage a covered projection + a fixture mutmut report the gate cannot trust.

        R5 unavailable cell: AT3 covers the untrustworthy-report space
        through ONE canonical fixture (``positive_control_failed.json``)
        -- the positive control was seeded but NOT killed, so mutmut is
        not discriminating in this environment and NO kill-rate verdict
        from the same run can be trusted. The gate MUST exit 3 emitting
        ``RobustnessLayer2Unavailable`` -- neither pass nor fail, holds
        the feature out of ``ready``.

        The four sibling untrustworthy fixtures (``malformed.json``,
        ``empty.json``, ``partial.json``, ``positive_control_failed.json``
        itself) are staged on disk for the production CLI's R5 branch to
        be exercised in DELIVER's GREEN against each. AT3 itself
        instantiates the canonical positive-control-failed cell (the
        Earned-Trust principle-13 probe) because all four classify
        identically at the gate-verdict universe (exit 3 + Unavailable
        token); DELIVER may add slice-04-bis or table-driven Examples
        rows for the other three without changing the AT shape.
        """
        self._stage_layer2_scenario(
            domain_id=domain_id,
            fixture_name="positive_control_failed.json",
            workspace_prefix="robust-gate-slice04-unavailable-",
        )

    def _stage_layer2_scenario(
        self,
        *,
        domain_id: DomainId,
        fixture_name: str,
        workspace_prefix: str,
    ) -> None:
        """Shared layer-2 scenario stager.

        All three slice-04 cells stage the same shape: per-scenario tmp
        workspace, a covered projection declaring ``domain_id``, a
        single ``# domain:``-tagged ``@given`` AT-scope file (so layers
        1+3 are satisfied and the only deciding layer is 2), and a copy
        of the named fixture mutmut JSON. The CLI is invoked with
        ``--mutmut-report <path>`` at the staged fixture path.

        Mandate-12 criterion 3: one body, ≤2 statements per cell-facing
        ``given_*`` method, all business logic SSOT here.
        """
        # Lazy local imports keep the module's top-level import list
        # minimal-by-default and survive the formatter's unused-import
        # pass on intermediate edits; the layer-2 staging is the only
        # call-site that exercises json/shutil.
        import shutil as _shutil

        workspace = Path(tempfile.mkdtemp(prefix=workspace_prefix))
        declaration_path = workspace / "unbounded-domains.yaml"
        at_scope_dir = workspace / "at_scope"
        at_scope_dir.mkdir()
        declaration_path.write_text(
            _DECLARATION_TEMPLATE.format(domain_id=domain_id), encoding="utf-8"
        )
        (at_scope_dir / "test_target_property.py").write_text(
            _COVERED_TEST_BODY_TEMPLATE.format(domain_id=domain_id), encoding="utf-8"
        )
        fixture_src = _FIXTURE_DIR / fixture_name
        assert fixture_src.is_file(), (
            f"slice-04 fixture {fixture_src} missing -- M2 mandate requires"
            f" committed fixture mutmut reports; live mutmut invocation is"
            f" forbidden"
        )
        staged_report = workspace / fixture_name
        _shutil.copyfile(str(fixture_src), str(staged_report))
        self._scenario_workspace = workspace
        self._declaration_path = declaration_path
        self._at_scope_dir = at_scope_dir
        self._declared_domain_id = domain_id
        self._mutmut_report_path = staged_report

    def run_gate_against_staged_scope(self) -> RobustnessGateResult:
        """Invoke ``check_robustness_density`` against the staged workspace.

        Walking-skeleton (slice-01): spawns the real production CLI as a
        ``python -m scripts.cli.check_robustness_density`` subprocess from
        the repo root. The CLI parses the staged ``unbounded-domains.yaml``,
        walks the staged AT-scope directory for ``# domain:``-tagged
        ``@given`` strategies, and exits 0/1/2 -- the slice-01 verdict
        universe (Mandate 9/11: real subprocess + real I/O at layer 5).

        Slice-02 extends the invocation surface: when a DESIGN component
        manifest is staged, the CLI is invoked with
        ``--component-manifest <path>`` so the DECISION D1 provenance check
        can read it. Slice-01 scenarios leave the manifest path None and
        the invocation shape is unchanged.
        """
        assert self._declaration_path is not None, "Given step must stage a declaration"
        assert self._at_scope_dir is not None, "Given step must stage an AT scope dir"
        argv = [
            sys.executable,
            "-m",
            "scripts.cli.check_robustness_density",
            "--declaration",
            str(self._declaration_path),
            "--at-scope",
            str(self._at_scope_dir),
        ]
        if self._component_manifest_path is not None:
            argv.extend(["--component-manifest", str(self._component_manifest_path)])
        if self._mutmut_report_path is not None:
            # Slice-04 universe extension: pass the fixture mutmut JSON path
            # so the gate's layer-2 mutmut-delta proxy branch reads it. The
            # production CLI MUST add the flag in DELIVER; until then this
            # extra argv element causes argparse to error (exit 2) -- still a
            # RIGHT-reason RED because the slice-04 ATs assert on the new
            # diagnostic tokens (RobustnessPBTNotFalsifiable / -Unavailable)
            # which the slice-03 CLI cannot emit.
            argv.extend(["--mutmut-report", str(self._mutmut_report_path)])
        completed = subprocess.run(
            argv,
            cwd=str(_REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
        )
        # Slice-02 universe extension: capture stdout so AT thens can assert
        # on the human-surface diagnostic token (e.g.
        # ``RobustnessDeclarationMissing``, ``RobustnessProvenanceViolation``)
        # rather than the exit code alone. The slice-01 CLI raises a bare
        # KeyError on missing-block; a slice-02 AT that asserts only on
        # the exit code would vacuously match the CHECK_FAILED value the
        # crash happens to emit -- the diagnostic-token assertion makes the
        # RIGHT-reason RED genuine. RobustnessGateExit(int) construction
        # tolerates only the {0, 1, 2} subset; slice-02 stays within that
        # subset and so the int->enum coercion is safe here.
        try:
            exit_code = RobustnessGateExit(completed.returncode)
        except ValueError:
            # An out-of-enum return code (e.g. a CLI crash with exit 1
            # promoted to exit 2 elsewhere) is itself the failure signal --
            # let the assertion on diagnostic_token fire downstream.
            exit_code = None
        return RobustnessGateResult(
            exit_code=exit_code,
            stdout=completed.stdout or "",
        )

    # --- slice-05: wiring (last slice -- feature-delta § 6 line 410) -------
    #
    # GREEN (DELIVER, slice-05): the production wiring substrate is shipped
    # (at_review_verdict consumes check_robustness_density exit code, the
    # SubagentStop hook intercept is registered as
    # scripts/hooks/subagent_stop_robustness_gate.py, the
    # framework-catalog quality_gates: registry carries
    # robustness-pbt-density-gate). The methods below drive the SUT through
    # the production composition root per Mandate-13:
    #   * AT1 -- Layer 3 subprocess via python -m scripts.cli.at_review_verdict
    #     with --robustness-declaration / --robustness-at-scope wiring args
    #   * AT2 -- Layer 4 wiring_e2e via the real subagent_stop_robustness_gate
    #     hook script (the production composition root, NEVER mocked per B4)
    #   * AT3 -- Layer 3 subprocess against a real M-producer-emitted
    #     component-manifest.yaml (NEVER a hand-authored fixture per B1)
    #
    # The slice-05 universe extends RobustnessGateResult with the
    # wiring-effect fields (verdict_record_written, verdict_producer_stderr,
    # dispatch_blocked, hook_chain_diagnostic) the AT thens assert on.

    # AT3 production-emitted manifest: a real component-manifest.yaml
    # authored by the M producer (the nw-design step) per M slice-04's §4.1
    # enumerate-unbounded-domains procedure. This is the "throwaway feature"
    # surrogate -- a committed M-producer artifact whose declared unbounded
    # domains are real (validate_component_manifest passes them) and whose
    # AT scope can be staged WITHOUT any # domain:-tagged @given coverage,
    # so the gate's slice-01 coverage walk refuses with
    # RobustnessCoverageMiss. The path is filesystem-grounded against the
    # repo tree per feedback_architect_must_filesystem_ground_roadmap.
    _AT3_M_PRODUCER_MANIFEST = (
        "docs/feature/F-LANGUAGE-ADAPTER-PLUGIN-INFRASTRUCTURE/design/"
        "component-manifest.yaml"
    )

    def given_slice_refused_by_robustness_gate(self, domain_id: DomainId) -> None:
        """Stage a slice the robustness gate refuses (covered-but-no-PBT).

        AT1 / AT2 substrate: reuses the slice-01 uncovered-domain stager.
        The declared domain is named but the staged AT-scope test file
        carries NO ``# domain:`` tag, so the gate's slice-01 coverage walk
        emits ``RobustnessCoverageMiss`` and exits 1. This is the
        SHALLOWEST refusal shape that exercises the wiring -- AT1 + AT2
        assert on the WIRING effect (verdict-producer / hook-chain
        blocking), NOT on which refusal shape the gate selected.
        """
        self.given_declared_domain_without_coverage(domain_id)

    def when_run_at_review_verdict_producer_with_gate_wired(self) -> None:
        """Drive the real at_review_verdict CLI with the gate wired into its DISTILL exit.

        AT1 SUT: the real ``scripts/cli/at_review_verdict.py`` producer
        subprocess invoked via ``python -m`` with
        ``--robustness-declaration`` + ``--robustness-at-scope`` pointing at
        the staged workspace. The producer's ``record_review_outcome``
        consults ``check_robustness_density`` first; on non-zero gate exit
        the APPROVED ledger record is NOT written and the gate's stdout
        diagnostic is forwarded to the producer's stderr.

        Mandate-13 driving-port-only: Layer 3 subprocess driving-port
        invocation. The wiring sits inside ``record_review_outcome`` --
        composition NEVER imports it directly.

        Universe captured: ``verdict_record_written`` (port-exposed
        observable: did an APPROVED ATReviewVerdict line land in the
        ledger?) + ``verdict_producer_stderr`` (port-exposed observable:
        the producer's stderr channel forwarding the gate's diagnostic).
        """
        assert self._declaration_path is not None, "Given step must stage a declaration"
        assert self._at_scope_dir is not None, "Given step must stage an AT scope dir"

        # Per-scenario throwaway feature so the AT-completion ledger lives
        # in an isolated tmp tree; the ledger-write check inspects this
        # ledger file's existence after the invocation.
        feature_id = "fix-robustness-pbt-density-gate-slice05-at1"
        slice_id = "slice-05"
        project_root = self._scenario_workspace
        assert project_root is not None, "Given step must stage a workspace"

        # des record-at-review-verdict now refuses an APPROVED verdict for
        # an unresolvable feature/slice (feature-delta.md absent, or
        # slice_id not a Slice Plan row) -- the silent-false-cert fix. Stage
        # a minimal feature-delta.md with a genuine slice-05 Slice Plan row
        # in this per-scenario workspace so the existence check passes and
        # AT1 still exercises its OWN concern (the robustness-gate wiring
        # effect), not the feature/slice-existence gate.
        feature_delta_path = (
            project_root / "docs" / "feature" / feature_id / "feature-delta.md"
        )
        feature_delta_path.parent.mkdir(parents=True, exist_ok=True)
        feature_delta_path.write_text(
            f"# Feature Delta: {feature_id}\n\n"
            "## Wave: DISCUSS / [REF] Slice Plan\n\n"
            "| Slice | Value statement | Status | Annotation | Justification |\n"
            "|---|---|---|---|---|\n"
            "| slice-05 | robustness gate wired into AT-review producer | done | | |\n",
            encoding="utf-8",
        )

        # Env-parity (F21/RCA-#68): the producer consults check_robustness_density
        # as a NESTED subprocess with cwd=--repo-root (= this workspace). Mark the
        # workspace as a developer checkout so that nested gate autoskips the
        # runtime-freshness probe instead of fail-closed exit 78 on the
        # manifest-less tmp tree — otherwise the freshness refusal pre-empts the
        # gate's own RobustnessCoverageMiss diagnostic. See tests/env_parity.py.
        seed_dev_checkout_marker(project_root)

        # Composition signs through the real producer; the producer's HMAC
        # key resolution is env-first then file-fallback. Tests stage an
        # in-process env key so the producer signs deterministically.
        # In-process analogue of the former des.cli.at_review_verdict module-form
        # (corpus-migration): drive the production producer CLI EDGE
        # `at_review_verdict.main(argv)`. The producer consults
        # check_robustness_density as a NESTED subprocess (cwd=--repo-root), so
        # the signing key + PYTHONPATH the original fork passed via `env=` are set
        # on os.environ around the call (the nested subprocess inherits them);
        # save/restore in finally so the shared test process is never mutated.
        saved_env = dict(os.environ)
        os.environ["NWAVE_REVIEWER_SIGNING_KEY"] = "slice-05-test-signing-key"
        os.environ["PYTHONPATH"] = os.pathsep.join(
            (str(_REPO_ROOT / "src"), str(_REPO_ROOT))
        )
        try:
            _exit_code, _stdout, producer_stderr = run_cli_in_process(
                [
                    "--feature-id",
                    feature_id,
                    "--slice-id",
                    slice_id,
                    "--verdict",
                    "APPROVED",
                    "--reviewer-agent-id",
                    "nw-acceptance-designer-reviewer",
                    "--repo-root",
                    str(project_root),
                    "--robustness-declaration",
                    str(self._declaration_path),
                    "--robustness-at-scope",
                    str(self._at_scope_dir),
                ],
                cwd=_REPO_ROOT,
                main=at_review_verdict.main,
            )
        finally:
            os.environ.clear()
            os.environ.update(saved_env)

        # The wiring-effect observable: did an APPROVED ATReviewVerdict
        # line land in the per-scenario ledger? The producer routes through
        # AtCompletionLedger.append_review_verdict which writes to
        # .nwave/telemetry/atdd-pure/{feature_id}.jsonl under project_root.
        ledger_path = (
            project_root / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
        )
        record_written = ledger_path.is_file() and "ATReviewVerdict" in (
            ledger_path.read_text(encoding="utf-8") if ledger_path.is_file() else ""
        )

        self.result = RobustnessGateResult(
            verdict_record_written=record_written,
            verdict_producer_stderr=producer_stderr or "",
        )

    def given_real_subagent_dispatch_prepared(self, domain_id: DomainId) -> None:
        """Stage a real sub-agent dispatch payload for the SubagentStop hook chain AT.

        AT2 substrate (B4 mandate -- live, NEVER mocked): the hook
        intercept executable is the real
        ``scripts/hooks/subagent_stop_robustness_gate.py`` shipped by
        slice-05 GREEN. Staging marks the composition as "AT2 dispatch
        prepared" -- the gate-CLI declaration + AT-scope are already
        staged by the AT2 Given (which calls into
        ``given_slice_refused_by_robustness_gate``); no additional state
        is needed beyond the AT1 substrate.
        """
        # The hook script is the production composition root probed by
        # AT2; grep-verified existence at slice-05 GREEN time.
        hook_script = (
            _REPO_ROOT / "scripts" / "hooks" / "subagent_stop_robustness_gate.py"
        )
        assert hook_script.is_file(), (
            "slice-05 AT2 substrate missing: the production SubagentStop "
            f"hook intercept {hook_script} is not present on disk"
        )

    def when_real_subagent_dispatch_passes_through_subagent_stop_hook_chain(
        self,
    ) -> None:
        """Drive a real sub-agent dispatch through the real SubagentStop hook chain.

        AT2 SUT: the real ``scripts/hooks/subagent_stop_robustness_gate.py``
        executable invoked as a ``python -m`` subprocess with the gate
        declaration + AT-scope wired through the documented env-var
        contract (``NWAVE_ROBUSTNESS_GATE_DECLARATION`` +
        ``NWAVE_ROBUSTNESS_GATE_AT_SCOPE``). A Claude-Code-shaped JSON
        SubagentStop payload is delivered on stdin (the hook drains and
        ignores it -- the decision is driven by the gate CLI exit code,
        not the payload shape). On non-zero gate exit the hook emits
        ``{"decision": "block", "reason": "<gate stdout>"}`` and exits 2.

        B4 INVARIANT (feature-delta § 6 lines 443-449): "slice-05 AT2
        MUST therefore be a live integration test against the real
        SubagentStop hook chain -- a real sub-agent dispatch that the
        intercept actually blocks on a non-zero CLI exit -- never a
        mocked hook dispatch." This composition drives THE PRODUCTION
        HOOK SCRIPT itself (not a mock), via the real Claude-Code
        SubagentStop protocol (stdin JSON + decision JSON on stdout +
        exit 2 for block).

        Mandate-13 driving-port-only: Layer 4 wiring_e2e driving-port
        invocation -- the SubagentStop hook script is the production
        composition root for the gate intercept.
        """
        assert self._declaration_path is not None, "Given step must stage a declaration"
        assert self._at_scope_dir is not None, "Given step must stage an AT scope dir"

        # A realistic Claude-Code SubagentStop hook delivery JSON payload.
        # The hook drains stdin but does not interpret it -- the block
        # decision is driven by the gate CLI exit code, NOT the payload
        # shape (so the test does not couple to an internal payload
        # schema). This payload is shape-realistic so the integration is
        # genuinely live, not a degenerate empty-stdin shortcut.
        subagent_stop_payload = json.dumps(
            {
                "session_id": "slice-05-at2-test-session",
                "hook_event_name": "SubagentStop",
                "subagent_type": "nw-acceptance-designer",
                "tool_use_id": "slice-05-at2-tool-use",
            }
        )

        # In-process analogue of the stdin-protocol fork
        # `python -m scripts.hooks.subagent_stop_robustness_gate` (corpus-
        # migration): the production hook EDGE `main()` drains the SubagentStop
        # JSON from sys.stdin and decides from the gate CLI exit code. The hook
        # spawns check_robustness_density as a NESTED subprocess, so the 3
        # NWAVE_ROBUSTNESS_GATE_* env vars are set on os.environ around the call
        # (inherited by the nested subprocess); save/restore in finally.
        saved_env = dict(os.environ)
        os.environ["NWAVE_ROBUSTNESS_GATE_DECLARATION"] = str(self._declaration_path)
        os.environ["NWAVE_ROBUSTNESS_GATE_AT_SCOPE"] = str(self._at_scope_dir)
        os.environ["NWAVE_ROBUSTNESS_GATE_REPO_ROOT"] = str(_REPO_ROOT)
        try:
            exit_code, hook_stdout, _hook_stderr = run_hook_in_process(
                subagent_stop_robustness_gate.main,
                stdin_text=subagent_stop_payload,
                cwd=_REPO_ROOT,
            )
        finally:
            os.environ.clear()
            os.environ.update(saved_env)

        # The hook's contract: exit 2 + a JSON decision payload on stdout
        # signals a block per Claude Code's hook protocol. The dispatch is
        # "blocked" iff the hook returned exit 2.
        dispatch_blocked = exit_code == 2
        hook_chain_diagnostic = hook_stdout or ""

        self.result = RobustnessGateResult(
            dispatch_blocked=dispatch_blocked,
            hook_chain_diagnostic=hook_chain_diagnostic,
        )

    def given_throwaway_feature_with_real_m_producer_manifest(
        self, domain_id: DomainId
    ) -> None:
        """Stage a throwaway feature whose component-manifest.yaml is M-producer-emitted.

        AT3 substrate (B1 mandate -- NEVER a hand-authored fixture): the
        composition wires the gate against a REAL M-producer-emitted
        ``component-manifest.yaml`` -- the
        ``F-LANGUAGE-ADAPTER-PLUGIN-INFRASTRUCTURE/design/component-manifest.yaml``
        artifact, authored through the M slice-04 ``nw-design`` step per
        M slice-04 §4.1 enumerate-unbounded-domains procedure. This is
        the genuine M-producer output (validate_component_manifest
        passes it) -- NOT a hand-authored fixture.

        The throwaway feature workspace stages the producer-emitted
        manifest AS the gate's declaration source AND an AT-scope dir
        with NO ``# domain:``-tagged ``@given`` coverage, so the gate's
        slice-01 coverage walk refuses with ``RobustnessCoverageMiss``.

        B1 INVARIANT (feature-delta § 6 lines 451-462): the gate's
        crafted-against-fixture surface is bridged to genuine
        M-producer output. The producer-to-gate seam is demonstrated
        end-to-end -- if the producer's output diverges in shape from
        the hand-authored fixtures slices 01-04 used, this AT surfaces
        the divergence.
        """
        m_producer_manifest = _REPO_ROOT / self._AT3_M_PRODUCER_MANIFEST
        assert m_producer_manifest.is_file(), (
            "slice-05 AT3 substrate missing: the real M-producer-emitted "
            f"component-manifest at {m_producer_manifest} is not present "
            "(M slice-04 producer artifact required for B1)"
        )

        # Per-scenario throwaway feature workspace. The M-producer manifest
        # is copied verbatim into the workspace so the gate's reads land on
        # the genuine producer output, host-isolated from the source tree.
        workspace = Path(tempfile.mkdtemp(prefix="robust-gate-slice05-at3-"))
        declaration_path = workspace / "unbounded-domains.yaml"
        at_scope_dir = workspace / "at_scope"
        at_scope_dir.mkdir()
        declaration_path.write_text(
            m_producer_manifest.read_text(encoding="utf-8"), encoding="utf-8"
        )
        # AT-scope holds a single example-based test with NO @given -- so
        # the gate's coverage walk refuses every declared domain in the
        # M-producer manifest (none are covered).
        (at_scope_dir / "test_no_coverage.py").write_text(
            "def test_no_pbt_coverage() -> None:\n    assert True\n",
            encoding="utf-8",
        )
        self._scenario_workspace = workspace
        self._declaration_path = declaration_path
        self._at_scope_dir = at_scope_dir
        self._declared_domain_id = domain_id

    def when_run_robustness_gate_against_real_m_producer_manifest(self) -> None:
        """Drive check_robustness_density against the real M-producer-emitted manifest.

        AT3 SUT: the real ``scripts/cli/check_robustness_density.py`` CLI
        invoked via ``python -m`` subprocess against the M-producer
        manifest staged by the AT3 Given. The gate parses the producer's
        ACTUAL output (not a fixture) and walks the staged AT scope. Per
        the AT3 universe, the gate refuses (exit 1 +
        ``RobustnessCoverageMiss`` on stdout) because the throwaway
        feature has no PBT coverage.

        Mandate-13 driving-port-only: Layer 3 subprocess driving-port
        invocation -- mirrors ``run_gate_against_staged_scope``'s
        precedent. Composition NEVER imports
        ``check_robustness_density`` directly.

        The dedicated AT3 method (vs reusing ``run_gate_against_staged_scope``)
        keeps the diff-stat showing slice-05 wires the gate against the
        REAL M-producer manifest, an audit-visible distinction from the
        slice-01 hand-authored fixture path.
        """
        # The AT3 invocation shape mirrors slice-01's
        # ``run_gate_against_staged_scope`` -- only the staged declaration
        # path's PROVENANCE differs (M-producer-emitted, not template).
        # The SUT is the same gate CLI; the wiring contract is that the
        # gate handles real producer output as readily as hand-authored
        # fixtures (no shape drift between producer and crafted manifests).
        self.result = self.run_gate_against_staged_scope()

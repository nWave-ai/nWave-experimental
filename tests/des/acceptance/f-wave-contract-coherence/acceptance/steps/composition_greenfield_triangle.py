"""Composition root for f-wave-contract-coherence slice-05 (greenfield triangle).

Dissolves the DISCUSS greenfield triangle (ADR-FLOW-002 Q4, retired into slice-05;
brief §6) through THREE real shipped seams -- no fixture theater, each AT drives the
artifact the maintainer actually ships:

  * AT-12 -- the REAL shipped DISCUSS gate-IN spine seam. The §22.0 token authority
    is the production pure core ``DiscussGateIn.evaluate``; the veto-vs-advisory
    routing the declass touches is the production
    ``PreToolUseService._discuss_gate_in_invoker`` closure. We build the REAL
    ``PreToolUseService`` wired with ONLY a greenfield ``ProductSsotReader`` double
    (the invoker path reads nothing else), obtain the REAL shipped invoker, and run
    it for the catalogued ``validate-feature-delta`` gate-id. Observable = the
    gate-IN decision the spine emits for a greenfield project: a §17 veto stdout
    (``exit!=0`` / ``verdict==fail``) vs a non-blocking pass/advisory. At HEAD the
    spine routes EVERY non-PASS token -- including ``MIGRATION_UNMET`` -- to
    ``veto_stdout`` (``pre_tool_use_service.py:359-374``), so a greenfield entry is
    HARD-BLOCKED -> AT-12's "does not hard-block" Then fires a semantic
    AssertionError. GREEN once DELIVER declasses MIGRATION_UNMET (and ONLY
    MIGRATION_UNMET) veto -> advisory.

  * AT-13 -- the REAL shipped DISCUSS prose (``nWave/tasks/nw/discuss.md`` +
    ``nWave/skills/nw-discuss/SKILL.md``), scanned over the filesystem (TextSearch
    floor, ADR-LA-001 tier-3; pure-Python ``re``, NEVER the ``grep`` binary). At HEAD
    both loci carry the stale "DISCUSS will bootstrap / create docs/product"
    contradiction (``SKILL.md:126`` + ``discuss.md:77,224``) and attribute the
    bootstrap to DISCUSS, not DIVERGE -> AT-13's Thens fire. GREEN once DELIVER
    reconciles both loci to "DIVERGE owns the greenfield bootstrap; DISCUSS proceeds
    via the soft-gate".

  * AT-14 -- the REAL shipped layout validator
    ``scripts/validation/validate_feature_layout.py`` + the REAL shipped command
    prose. The validator ALREADY rejects a legacy ``discuss/*.md`` companion (the
    end-state half that holds today -- idempotency); the command prose STILL
    enumerates legacy ``discuss/*.md`` files as produced outputs
    (``discuss.md:137-153``) -> AT-14's prose Then fires. GREEN once DELIVER retires
    the legacy output enumeration from the command prose.

DORMANT-SEAM RECONCILIATION (Mandate-15 / S3): slice-05 introduces NO net-new
load-bearing seam -- it DECLASSES an existing one (the gate-IN MIGRATION_UNMET veto)
and reconciles prose. AT-12 NAMES the real gate-IN spine seam
(``DiscussGateIn.evaluate`` routed through ``_discuss_gate_in_invoker``) and drives
it through the REAL ``PreToolUseService``, asserting the observable gate-IN decision.

Step bodies delegate to this composition (Mandate-12, no logic in step bodies); the
``locus`` example column is coerced to ``DiscussBootstrapLocus`` at the step boundary.

Active-RED scaffold (atdd_pure -- NOT @skip): every Then fires a semantic
AssertionError at HEAD (hard veto on greenfield / stale bootstrap claim / surviving
legacy output enumeration), never a collection / import / setup error. The two
end-state halves that a prior Q4 ship may already satisfy (the validator already
rejects legacy companions) are asserted as end-state -> green either way (idempotent).
"""

from __future__ import annotations

import importlib.util
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from des.ports.driven_ports.product_ssot_reader import ProductSsotReader, SsotPresence


if TYPE_CHECKING:
    from .domain_types import DiscussBootstrapLocus


# tests/des/acceptance/f-wave-contract-coherence/acceptance/steps/<this file>
#   parents[6] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[6]

# The catalogued DISCUSS gate-IN gate-id the spine routes to DiscussGateIn.evaluate
# (pre_tool_use_service.py:355). The invoker fails closed for any other gate-id.
_DISCUSS_GATE_IN_GATE_ID = "validate-feature-delta"

# The shipped layout validator that retires the legacy discuss/*.md output form.
_LAYOUT_VALIDATOR = REPO_ROOT / "scripts" / "validation" / "validate_feature_layout.py"

# A legacy multi-file DISCUSS output path -- the form the inline feature-delta
# `## Wave: DISCUSS / [REF] <Section>` SSOT replaces. The validator must reject it.
_LEGACY_DISCUSS_COMPANION = "discuss/story-map.md"

# The shipped DISCUSS command prose (AT-14 enumerates its produced outputs).
_DISCUSS_COMMAND_PROSE = REPO_ROOT / "nWave" / "tasks" / "nw" / "discuss.md"

# --- lexical patterns (TextSearch floor, ADR-LA-001 tier-3; git-free) ------------

# A stale "DISCUSS bootstraps / creates / initializes docs/product" claim -- the
# contradiction AT-13 forbids. Matches the shipped phrasings ("DISCUSS will bootstrap
# it", "DISCUSS will create it", "first wave initializes it").
_STALE_DISCUSS_BOOTSTRAPS = re.compile(
    r"DISCUSS\s+(?:will\s+)?(?:bootstrap|create)\b"
    r"|first\s+wave\s+initializes",
    re.IGNORECASE,
)

# The reconciled statement: DIVERGE owns the greenfield bootstrap. AT-13 requires
# its presence in both loci.
_DIVERGE_OWNS_BOOTSTRAP = re.compile(r"DIVERGE\b[^.\n]*\bbootstrap", re.IGNORECASE)

# A legacy `discuss/<file>.md` produced-output enumeration in the command prose --
# a backtick-or-path mention of a file UNDER the `discuss/` wave subdir (the retired
# multi-file form). Excludes the bare `discuss/` dir and the gate-decisions path.
_LEGACY_DISCUSS_OUTPUT = re.compile(r"discuss/[A-Za-z0-9_{}-]+\.md", re.IGNORECASE)


# === AT-12 -- greenfield gate-IN double ==========================================


@dataclass(frozen=True)
class _GreenfieldSsotReader(ProductSsotReader):
    """A ProductSsotReader returning a GREENFIELD presence: docs/product absent.

    The greenfield project state the MIGRATION_UNMET declass targets: the migration
    gate (docs/product/) is absent and no SSOT docs exist. This is a legitimate
    driven-port double for the external/non-deterministic filesystem read (the AT
    pins the greenfield INPUT; the SUT is the real gate-IN spine seam)."""

    def ssot_present(self, project_root: Path) -> SsotPresence:
        return SsotPresence(
            product_dir_present=False,
            vision=False,
            backlog=False,
            glossary=False,
            jobs=False,
            indeterminate=False,
        )


@dataclass(frozen=True)
class _UnreadableRootSsotReader(ProductSsotReader):
    """A ProductSsotReader whose read MECHANISM failed -> degrade-LOUD INDETERMINATE.

    AT-12 asserts the declass is SCOPED to MIGRATION_UNMET only: the INDETERMINATE
    degrade-loud veto (an unreadable root) MUST remain a hard block."""

    def ssot_present(self, project_root: Path) -> SsotPresence:
        return SsotPresence(
            product_dir_present=False,
            vision=False,
            backlog=False,
            glossary=False,
            jobs=False,
            indeterminate=True,
        )


@dataclass(frozen=True)
class _GateInDecision:
    """The observable boundary DTO of one shipped gate-IN invoker run."""

    exit_code: int
    verdict: str | None
    reason: str | None


def _run_shipped_gate_in(reader: ProductSsotReader) -> _GateInDecision:
    """Drive the REAL shipped DISCUSS gate-IN spine seam over ``reader``.

    Builds the production ``PreToolUseService`` wired with ONLY the injected
    ``ProductSsotReader`` (the gate-IN invoker path reads nothing else), obtains the
    REAL shipped ``_discuss_gate_in_invoker`` closure, and runs it for the
    catalogued ``validate-feature-delta`` gate-id. The closure returns the shipped
    ``(exit_code, json_stdout)`` boundary the spine emits."""
    from des.application.pre_tool_use_service import PreToolUseService

    service = PreToolUseService(
        marker_parser=None,  # type: ignore[arg-type]
        prompt_validator=None,  # type: ignore[arg-type]
        audit_writer=None,  # type: ignore[arg-type]
        time_provider=None,  # type: ignore[arg-type]
        product_ssot_reader=reader,
    )
    invoke = service._discuss_gate_in_invoker()
    exit_code, stdout = invoke(_DISCUSS_GATE_IN_GATE_ID, {})
    payload = json.loads(stdout)
    return _GateInDecision(
        exit_code=exit_code,
        verdict=payload.get("verdict"),
        reason=payload.get("reason"),
    )


@dataclass
class GreenfieldTriangleComposition:
    """Drives the three real shipped seams that dissolve the greenfield triangle."""

    _greenfield_decision: _GateInDecision | None = field(default=None)
    _locus_path: Path | None = field(default=None)
    _locus_label: str | None = field(default=None)

    # ---- AT-12: greenfield gate-IN ------------------------------------------

    def given_greenfield_project(self) -> None:
        """PRECONDITION: a greenfield project where docs/product is absent.

        Pins the greenfield INPUT (the driven-port read result); the SUT remains the
        real gate-IN spine seam driven in the When."""
        # The greenfield presence is supplied via the _GreenfieldSsotReader double at
        # When time -- this Given records the precondition intent (no I/O).
        self._greenfield_decision = None

    def when_discuss_gate_in_evaluated_for_greenfield(self) -> None:
        """Drive the REAL shipped gate-IN spine seam over a greenfield presence."""
        self._greenfield_decision = _run_shipped_gate_in(_GreenfieldSsotReader())

    def then_gate_in_does_not_hard_block(self) -> None:
        """The greenfield gate-IN decision is NOT a hard block.

        End-state (idempotent): a greenfield DISCUSS entry must be allowed to proceed
        -- MIGRATION_UNMET is declassed veto -> advisory (ADR-FLOW-002 Q4). The
        shipped spine emits a veto as ``(exit_code=1, verdict="fail")``
        (``veto_stdout``); a non-blocking pass/advisory is ``exit_code==0`` /
        ``verdict!="fail"`` (``pass_stdout`` or an advisory token). RED at HEAD: the
        spine routes MIGRATION_UNMET to ``veto_stdout`` -> ``(1, "fail")`` -> this
        fires a semantic AssertionError naming the surviving hard veto."""
        decision = self._require_greenfield_decision()
        assert not (decision.exit_code != 0 and decision.verdict == "fail"), (
            "a greenfield DISCUSS gate-IN entry (docs/product absent) must NOT be "
            "hard-blocked -- the MIGRATION_UNMET token is declassed veto -> advisory "
            "(ADR-FLOW-002 Q4, retired into slice-05). The shipped spine "
            "(PreToolUseService._discuss_gate_in_invoker) instead emitted a §17 veto "
            f"(exit_code={decision.exit_code}, verdict={decision.verdict!r}, "
            f"reason={decision.reason!r}). DELIVER slice-05 must declass MIGRATION_UNMET "
            "(and ONLY MIGRATION_UNMET) so a greenfield entry proceeds."
        )

    def then_indeterminate_veto_left_intact(self) -> None:
        """The declass is SCOPED to MIGRATION_UNMET: an unreadable root still hard-blocks.

        Scope guard (ADR-FLOW-002 Q4: "scope = MIGRATION_UNMET only; INDETERMINATE /
        MISSING_SSOT untouched"). Drives the same shipped seam over an
        INDETERMINATE presence and asserts the degrade-LOUD veto survives -- so the
        declass cannot be over-applied into a silent-pass on an unreadable root
        (Invariant 2). This Then is GREEN at HEAD (the veto holds today) and must STAY
        green after the declass -- it pins the scope boundary."""
        decision = _run_shipped_gate_in(_UnreadableRootSsotReader())
        assert decision.exit_code != 0 and decision.verdict == "fail", (
            "the INDETERMINATE degrade-LOUD veto must remain a HARD block after the "
            "MIGRATION_UNMET declass -- an unreadable product-SSOT root is NEVER "
            "coerced to a silent pass (Invariant 2, §17 no-silent-pass). The shipped "
            f"gate-IN spine emitted (exit_code={decision.exit_code}, "
            f"verdict={decision.verdict!r}) for an INDETERMINATE presence; the declass "
            "must be scoped to MIGRATION_UNMET only and leave this veto intact."
        )

    # ---- AT-13: bootstrap-ownership reconcile -------------------------------

    def given_shipped_bootstrap_prose(self, locus: DiscussBootstrapLocus) -> None:
        """Bind the REAL shipped DISCUSS prose locus whose bootstrap claim AT-13 checks."""
        prose_path = REPO_ROOT / locus.value
        assert prose_path.is_file(), (
            f"the shipped DISCUSS prose locus {locus.value!r} must exist on disk (it "
            f"is the real artifact the reconcile edits); resolved to {prose_path}"
        )
        self._locus_path = prose_path
        self._locus_label = locus.value

    def then_no_stale_discuss_bootstraps_claim(self) -> None:
        """The shipped prose carries NO stale "DISCUSS bootstraps docs/product" claim.

        End-state (idempotent): the contradiction is removed. RED at HEAD: both loci
        carry "DISCUSS will bootstrap it" (SKILL.md:126) / "DISCUSS will create it"
        (discuss.md:77,224) -> the scan matches -> semantic AssertionError naming the
        surviving claim. GREEN once DELIVER reconciles to DIVERGE-owns."""
        prose_text = self._read_locus()
        match = _STALE_DISCUSS_BOOTSTRAPS.search(prose_text)
        assert match is None, (
            f"the shipped DISCUSS prose {self._locus_label} still carries the stale "
            f"bootstrap-ownership claim {match.group(0)!r} (the greenfield triangle "
            "side (2)): it says DISCUSS bootstraps/creates docs/product, contradicting "
            "the canonical DISCOVER -> DIVERGE -> DISCUSS order where DIVERGE owns the "
            "bootstrap. DELIVER slice-05 must reconcile both loci to DIVERGE-owns."
        )

    def then_attributes_bootstrap_to_diverge(self) -> None:
        """The shipped prose attributes the greenfield bootstrap to DIVERGE.

        End-state (idempotent): the reconciled positive statement is present. RED at
        HEAD: neither locus names DIVERGE as the bootstrap owner -> semantic
        AssertionError. GREEN once DELIVER adds the DIVERGE-owns statement."""
        prose_text = self._read_locus()
        assert _DIVERGE_OWNS_BOOTSTRAP.search(prose_text) is not None, (
            f"the shipped DISCUSS prose {self._locus_label} must attribute the "
            "greenfield bootstrap to DIVERGE (the reconciled statement -- DIVERGE owns "
            "it, DISCUSS proceeds via the soft-gate); no such statement found. DELIVER "
            "slice-05 must add the DIVERGE-owns-bootstrap reconcile to both loci."
        )

    # ---- AT-14: legacy discuss/*.md retirement ------------------------------

    def given_layout_validator_and_command_prose(self) -> None:
        """PRECONDITION: the shipped layout validator + DISCUSS command prose both exist."""
        assert _LAYOUT_VALIDATOR.is_file(), (
            f"the shipped layout validator must exist on disk; resolved to "
            f"{_LAYOUT_VALIDATOR}"
        )
        assert _DISCUSS_COMMAND_PROSE.is_file(), (
            f"the shipped DISCUSS command prose must exist on disk; resolved to "
            f"{_DISCUSS_COMMAND_PROSE}"
        )

    def then_validator_rejects_legacy_discuss_output(self) -> None:
        """The shipped layout validator REJECTS a legacy `discuss/*.md` companion.

        End-state (idempotent -- this half holds at HEAD): the inline feature-delta
        form is the SSOT; a legacy `discuss/<file>.md` companion is a layout
        offender. Drives the REAL shipped validator's classifier over the legacy path
        and asserts it is NOT accepted (an offence is reported)."""
        classify = self._load_validator_classifier()
        offence = classify(_LEGACY_DISCUSS_COMPANION)  # LayoutOffender | None
        assert offence is not None, (
            f"the shipped layout validator must REJECT a legacy DISCUSS multi-file "
            f"output {_LEGACY_DISCUSS_COMPANION!r} (the retired form -- the inline "
            "`## Wave: DISCUSS / [REF] <Section>` feature-delta form is the SSOT); the "
            "validator accepted it instead. The legacy multi-file output form must be "
            "retired (greenfield triangle side (3))."
        )

    def then_command_prose_enumerates_no_legacy_outputs(self) -> None:
        """The shipped DISCUSS command prose enumerates NO legacy `discuss/*.md` outputs.

        End-state: the command no longer LISTS legacy multi-file outputs as produced
        artifacts. RED at HEAD: `discuss.md:137-153` still enumerates
        `journey-{name}-visual.md`, `story-map.md`, `shared-artifacts-registry.md`
        etc. under `discuss/` -> the scan matches -> semantic AssertionError naming
        the surviving enumeration. GREEN once DELIVER retires the legacy output list."""
        prose_text = _DISCUSS_COMMAND_PROSE.read_text(encoding="utf-8")
        matches = sorted(set(_LEGACY_DISCUSS_OUTPUT.findall(prose_text)))
        assert not matches, (
            "the shipped DISCUSS command prose (nWave/tasks/nw/discuss.md) still "
            f"enumerates legacy multi-file outputs under `discuss/`: {matches}. The "
            "legacy multi-file output form is retired -- DISCUSS findings are inline "
            "`## Wave: DISCUSS / [REF] <Section>` sections in feature-delta.md. DELIVER "
            "slice-05 must remove the legacy `discuss/*.md` output enumeration."
        )

    # ---- helpers ------------------------------------------------------------

    def _require_greenfield_decision(self) -> _GateInDecision:
        assert self._greenfield_decision is not None, (
            "the DISCUSS gate-IN must be evaluated (When) before asserting the "
            "greenfield decision (Then)"
        )
        return self._greenfield_decision

    def _read_locus(self) -> str:
        assert self._locus_path is not None, (
            "the DISCUSS bootstrap-ownership prose locus must be bound (Given) before "
            "the bootstrap claim is asserted (Then)"
        )
        return self._locus_path.read_text(encoding="utf-8")

    def _load_validator_classifier(self):
        """Load the shipped layout validator's per-path classifier STANDALONE.

        Loads `validate_feature_layout.py` from its file (side-effect-free module,
        stdlib-only) and returns its `_classify_path` callable -- the REAL shipped
        rule that decides whether a feature-relative path is a layout offender
        (returns a ``LayoutOffender`` or ``None``). The AT asserts exactly what the
        shipped validator enforces (no test-private copy of the rule, Mandate-12
        SSOT)."""
        spec = importlib.util.spec_from_file_location(
            "des_slice05_layout_validator", _LAYOUT_VALIDATOR
        )
        assert spec is not None and spec.loader is not None, (
            f"cannot load the shipped layout validator from {_LAYOUT_VALIDATOR!r}"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module._classify_path

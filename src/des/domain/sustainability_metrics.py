"""sustainability_metrics — the BALANCED-DENOMINATOR pure core (slice-04, DDD-4/5/10).

The "less" half of the sustainability gradient. slice-03 made the section rows
mechanically checkable git-free; this module adds the MEASURED denominator the gate
reports as EVIDENCE cells plus the blind-add cross-check that gives a CONSOLIDATE/REUSE
claim the same mechanical force as the completeness "more" gate:

  * A — ``consolidation_delta_loc``: the net test-LOC delta for the slice (added minus
    deleted test-LOC). A consolidating slice has a delta <= 0 (the @property invariant).
  * C — ``adoption_ratio``: the generic-framework / DSL adoption ratio, read from the
    section's declared decisions (REUSE/EXTEND/CONSOLIDATE = adopting the shared
    framework; CREATE_NEW = adding bespoke surface).
  * the blind-add cross-check: a CONSOLIDATE/REUSE claim contradicted by a net test-LOC
    INCREASE in the real diff is unmasked as ``blind-add`` (-> top-level
    ``blind-add-detected``). When the git diff cannot run the cross-check is
    ``indeterminate`` (DDD-4/10 degrade-LOUD; NEVER a fabricated ``consistent``).

Contract shape (DDD-10): this module is PURE — every function reads its inputs and
returns a typed value, performing ZERO I/O. The git diff (an unbounded-preservation
read) is performed by the driven adapter and handed in as a typed value
(``TestLocDelta`` | ``GitDiffUnavailable``); the classification here is total over both.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# The declared sustainability INTENT the cross-check tests against the diff
# ---------------------------------------------------------------------------

#: The decision tokens that DECLARE a consolidation/reuse intent — a row carrying one of
#: these CLAIMS the slice reuses/folds existing surface rather than adding bespoke tests.
#: A claim of this kind contradicted by a net test-LOC INCREASE is the blind add the
#: cross-check unmasks. (Mirror of the slice-03 decision vocabulary, consolidate subset.)
_CONSOLIDATION_INTENT_TOKENS: frozenset[str] = frozenset({"REUSE", "CONSOLIDATE"})


class ConsolidateOnAddVerdict(str, Enum):
    """The closed cross-check verdict the consolidate-on-add (add-AND-improve) leg reports.

    SSOT consumed by ``validate_feature_delta`` + the slice-07 ATs. The leg compares the
    consolidating run's net test-LOC against the add-only baseline for the same added scope:

      * ``realized``      — the run's net test-LOC is BELOW the add-only baseline (the gain
                            is strictly negative); the add-AND-improve actually bent the
                            curve relative to a pure add;
      * ``not-realized``  — the section DECLARES consolidate-on-add but the run's net
                            test-LOC is NOT below the add-only baseline (gain >= 0); the
                            add-AND-improve claim is an add-only masquerade; drives the
                            top-level ``consolidate-on-add-not-realized`` verdict;
      * ``indeterminate`` — no add-only baseline was supplied, so the gain cannot be
                            computed. Degrade LOUD, exit non-zero, NEVER a fabricated pass
                            (DDD-4 / DDD-10) — the baseline is the denominator.
    """

    REALIZED = "realized"
    NOT_REALIZED = "not-realized"
    INDETERMINATE = "indeterminate"


class ExistingBaseTrendVerdict(str, Enum):
    """The closed cross-check verdict the existing-base near-duplicate-step trend leg
    reports (slice-09, DDD-16C/17C — the ACTIVE counter-gradient).

    SSOT consumed by ``validate_feature_delta`` + the slice-09 ATs. The leg compares the
    current run's existing-base near-duplicate-step ratio (a real fraction over an AST
    step-shape corpus) against the prior committed ratio (read git-free from the prior
    feature-delta section, supplied as the ``--prior-existing-base-ratio`` value):

      * ``improved``      — the current ratio is STRICTLY BELOW the prior committed ratio;
                            the existing base improved this run (the counter-gradient bent
                            the existing-base curve); accepted on trend, exit 0;
      * ``regressed``     — the current ratio is ABOVE the prior committed ratio; the
                            existing base got WORSE; the trend break is gated; drives the
                            top-level ``existing-base-duplication-regressed`` verdict;
      * ``indeterminate`` — the ratio cannot be decided: the AST step-shape corpus is
                            unavailable (the CodeFactPort returns no step-shape fact) OR no
                            prior committed ratio was supplied (the trend denominator is
                            absent). DDD-17C degrade-LOUD: exit non-zero, NEVER a fabricated
                            ``0.0`` ratio and NEVER a fabricated downward trend.
    """

    IMPROVED = "improved"
    REGRESSED = "regressed"
    INDETERMINATE = "indeterminate"


class BlindAddVerdict(str, Enum):
    """The closed cross-check verdict the git-diff blind-add leg reports (DDD-4).

    SSOT consumed by ``validate_feature_delta`` + the slice-04 ATs:

      * ``consistent``    — the declared intent matches the observed net test-LOC delta;
      * ``blind-add``     — a CONSOLIDATE/REUSE claim contradicted by a net test-LOC
                            INCREASE (the claim is unmasked); drives ``blind-add-detected``;
      * ``indeterminate`` — the git-diff cross-check could NOT run (git absent / not a
                            repo). Degrade LOUD, exit non-zero, NEVER a fabricated pass.
    """

    CONSISTENT = "consistent"
    BLIND_ADD = "blind-add"
    INDETERMINATE = "indeterminate"


# ---------------------------------------------------------------------------
# Typed git-diff result values — the adapter's output, the cross-check's input
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TestLocDelta:
    """A computed net test-LOC delta (added minus deleted test-LOC). Pure value.

    ``net`` <= 0 is a consolidating slice; ``net`` > 0 is a net add.
    """

    net: int


@dataclass(frozen=True)
class ConsolidateOnAddGain:
    """The consolidate-on-add gain — the run's net test-LOC minus the add-only baseline.

    ``loc`` < 0 means the consolidating run netted strictly BELOW the add-only baseline for
    the same added scope (the add-AND-improve bent the curve); ``loc`` >= 0 means the run
    did NOT beat the baseline (the add-only masquerade). Pure value.
    """

    loc: int


@dataclass(frozen=True)
class GitDiffUnavailable:
    """The git-diff cross-check could not run (git absent / not a work-tree). Pure value.

    Carries the LOUD reason so the gate's ``indeterminate`` verdict names WHY it refused
    to decide — never a silent or fabricated pass (DDD-4 / DDD-10).
    """

    reason: str


# ---------------------------------------------------------------------------
# A — consolidation-delta + C — adoption-ratio (pure evidence cells)
# ---------------------------------------------------------------------------


def adoption_ratio(decisions: list[str]) -> float:
    """C — the generic-framework / DSL adoption ratio over a section's decisions. Pure.

    The fraction of decision rows that ADOPT shared surface (REUSE/EXTEND/CONSOLIDATE)
    rather than add bespoke surface (CREATE_NEW). A section with no decision rows has a
    ratio of 0.0 (no adoption observed).
    """
    if not decisions:
        return 0.0
    adopting = sum(1 for token in decisions if token != "CREATE_NEW")
    return adopting / len(decisions)


# ---------------------------------------------------------------------------
# The blind-add cross-check — total over (TestLocDelta | GitDiffUnavailable)
# ---------------------------------------------------------------------------


def classify_blind_add(
    decisions: list[str], delta: TestLocDelta | GitDiffUnavailable
) -> BlindAddVerdict:
    """Classify the declared intent against the observed net test-LOC delta. Pure.

    - ``GitDiffUnavailable`` -> ``indeterminate`` (degrade-LOUD; the cross-check could
      not run, so it refuses to decide — never a fabricated ``consistent``);
    - a CONSOLIDATE/REUSE claim with a net test-LOC INCREASE (``net`` > 0) ->
      ``blind-add`` (the claim is contradicted by the diff);
    - otherwise -> ``consistent``.
    """
    if isinstance(delta, GitDiffUnavailable):
        return BlindAddVerdict.INDETERMINATE
    claims_consolidation = any(
        token in _CONSOLIDATION_INTENT_TOKENS for token in decisions
    )
    if claims_consolidation and delta.net > 0:
        return BlindAddVerdict.BLIND_ADD
    return BlindAddVerdict.CONSISTENT


# ---------------------------------------------------------------------------
# The consolidate-on-add (add-AND-improve) gain — pure, git-free (slice-07, DDD-4/16C)
# ---------------------------------------------------------------------------


def consolidate_on_add_gain(
    net_loc: int, add_only_baseline_loc: int
) -> ConsolidateOnAddGain:
    """The consolidate-on-add gain: the run's net test-LOC minus the add-only baseline. Pure.

    ``gain = net_loc - add_only_baseline_loc``. A strictly-negative gain means the
    consolidating run netted BELOW the add-only baseline for the same added scope — the
    add-AND-improve actually bent the +94%/feature curve. A non-negative gain means the run
    did NOT beat the pure-add baseline (the add-only masquerade).
    """
    return ConsolidateOnAddGain(loc=net_loc - add_only_baseline_loc)


def existing_base_duplication_ratio(
    near_duplicate_groups: int, total_step_definitions: int
) -> float:
    """The existing-base near-duplicate-step ratio over an AST step-shape corpus. Pure.

    The fraction of the existing test base that is near-duplicate step shape:
    ``near_duplicate_groups / total_step_definitions``. A near-duplicate group is a set of
    step definitions sharing one normalized body shape (the AST step-shape corpus the
    CodeFactPort supplies); ``total_step_definitions`` is the count of step definitions in
    that corpus. The result is a real fraction in [0.0, 1.0]: a corpus with no near-duplicate
    groups (or no step definitions at all) has a ratio of 0.0.

    git-free, deterministic — the step-shape counts are the CodeFactPort's (impure) job; this
    classifier is total over them.
    """
    if total_step_definitions <= 0:
        return 0.0
    return near_duplicate_groups / total_step_definitions


def classify_existing_base_trend(
    ratio: float, prior_committed_ratio: float | None
) -> ExistingBaseTrendVerdict:
    """Classify the current existing-base ratio against the prior committed ratio. Pure.

    - no prior committed ratio  -> ``indeterminate`` (the trend denominator is absent;
      degrade-LOUD, NEVER a fabricated downward trend — DDD-17C);
    - ratio < prior             -> ``improved`` (the existing base got better this run);
    - ratio >= prior            -> ``regressed`` (the existing base did NOT improve;
      the downward-trend gate, DDD-16C).

    The ``indeterminate``-on-absent-corpus boundary is NOT decided here: an unavailable AST
    step-shape corpus means there is no ratio to classify at all, so the CLI shell short-
    circuits to ``indeterminate`` before a ratio can be computed (DDD-17C degrade-LOUD).
    """
    if prior_committed_ratio is None:
        return ExistingBaseTrendVerdict.INDETERMINATE
    if ratio < prior_committed_ratio:
        return ExistingBaseTrendVerdict.IMPROVED
    return ExistingBaseTrendVerdict.REGRESSED


def classify_consolidate_on_add(gain: ConsolidateOnAddGain) -> ConsolidateOnAddVerdict:
    """Classify a computed consolidate-on-add gain. Pure.

    - gain < 0  -> ``realized``     (netted strictly below the add-only baseline);
    - gain >= 0 -> ``not-realized`` (did not beat the baseline — the add-only masquerade).

    The ``indeterminate`` verdict is NOT produced here: it is the absent-baseline boundary,
    classified at the CLI before a gain can be computed (DDD-4 / DDD-10 degrade-LOUD).
    """
    if gain.loc < 0:
        return ConsolidateOnAddVerdict.REALIZED
    return ConsolidateOnAddVerdict.NOT_REALIZED


__all__ = [
    "BlindAddVerdict",
    "ConsolidateOnAddGain",
    "ConsolidateOnAddVerdict",
    "ExistingBaseTrendVerdict",
    "GitDiffUnavailable",
    "TestLocDelta",
    "adoption_ratio",
    "classify_blind_add",
    "classify_consolidate_on_add",
    "classify_existing_base_trend",
    "consolidate_on_add_gain",
    "existing_base_duplication_ratio",
]

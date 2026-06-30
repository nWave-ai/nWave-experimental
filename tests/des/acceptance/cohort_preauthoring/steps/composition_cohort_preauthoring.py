"""Composition root for the fix-cohort-gate-preauthoring slice-01 ATs.

Mandate-16 driving-port-only (Layer 3 composition): each behaviour is driven
through the REAL production seam the DESIGN [REF] Driving Ports pins --
``scripts/cli/cohort_classifier`` ``_count_ats`` (the candidate-AT count for the
``feature_delta`` kind). The count function is reached through a LAZY import
inside the driving-port invocation; the step bodies delegate to these composition
methods (Mandate-15 -- no logic in step bodies).

DRIVING SURFACE: ``cohort_classifier._count_ats(delta_path, "feature_delta")`` --
the real count function the cohort gate consumes (its single caller is the CLI
``main``; the [REF] Driving Ports section names this function as the seam to
extend). The composition stages a crafted feature-delta under a TEMPORARY
directory (the pytest ``tmp_path``) and drives the real count over it. No
real repository feature-delta is read, and no personal-hook home-directory path
is touched anywhere -- the texts are synthesised in-process (hermetic).

active-RED scaffold (atdd_pure -- NOT @skip): the new counting seam
(a candidate-list parse + the larger-of-the-two return for the ``feature_delta``
kind) is ABSENT at HEAD, so the count function reports 0 for a Test-Placement-only
delta and reports only the authored count when both are present. The ``Then``
reads the reported count and fires a NAMED semantic ``AssertionError`` -- never a
collection / import / setup error. GREEN once DELIVER lands the candidate-list
count + the larger-of-the-two return.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from .domain_types_cohort_preauthoring import CandidateAtCount, FeatureDeltaShape


# Repo root: this file is tests/des/acceptance/cohort_preauthoring/steps/<this>;
# parents[5] is the repository root that holds ``scripts/`` (steps=0, package=1,
# acceptance=2, des=3, tests=4, repo=5).
_REPO_ROOT = Path(__file__).resolve().parents[5]

# The REAL production count function lives at scripts/cli/cohort_classifier.py.
# It is loaded directly from its file path (NOT via ``import scripts.cli``)
# because a test package ``tests/scripts/cli/`` shadows the ``scripts.cli`` name
# in ``sys.modules`` during collection -- a plain package import would resolve to
# the test shadow (a wrong-reason BROKEN failure), not the production module.
_COHORT_CLASSIFIER_PATH = _REPO_ROOT / "scripts" / "cli" / "cohort_classifier.py"


def _load_cohort_classifier() -> ModuleType:
    """Load the production cohort_classifier module from its file path."""
    spec = importlib.util.spec_from_file_location(
        "_cohort_preauthoring_real_classifier", _COHORT_CLASSIFIER_PATH
    )
    assert spec is not None and spec.loader is not None, (
        f"cannot load real cohort_classifier from {_COHORT_CLASSIFIER_PATH}"
    )
    module = importlib.util.module_from_spec(spec)
    # Register before exec_module: cohort_classifier uses ``from __future__ import
    # annotations`` + a @dataclass, whose string-annotation resolution requires the
    # module to be present in sys.modules during execution.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# The DISTILL Test Placement section heading the cohort gate keys on (the
# pre-authoring candidate-AT enumeration lives under it as a numbered list).
_TEST_PLACEMENT_HEADING = "## Wave: DISTILL / [REF] Test Placement"


def _render_feature_delta(shape: FeatureDeltaShape) -> str:
    """Synthesise a hermetic feature-delta text from a typed shape.

    The numbered candidate-AT list goes under the Test Placement heading; the
    authored scenarios go in a separate Gherkin block. Both are realistic prose,
    not assertion-shaped fixtures -- they are PRECONDITION inputs only.
    """
    parts: list[str] = ["# Feature Delta: synthetic-cohort-preauthoring", ""]

    if shape.placement_candidate_count is not None:
        parts.append(_TEST_PLACEMENT_HEADING)
        parts.append("")
        for i in range(1, shape.placement_candidate_count + 1):
            parts.append(f"{i}. AC-{i} candidate acceptance test number {i}.")
        parts.append("")
        # A following heading so the section has a clean lower boundary.
        parts.append("## Wave: DISTILL / [REF] Pre-requisites")
        parts.append("None.")
        parts.append("")

    if shape.authored_scenario_count > 0:
        parts.append("Feature: synthetic authored scenarios")
        for i in range(1, shape.authored_scenario_count + 1):
            parts.append(f"  Scenario: authored scenario {i}")
            parts.append("    Given a precondition")
            parts.append("    When an action occurs")
            parts.append("    Then an outcome holds")
        parts.append("")

    return "\n".join(parts) + "\n"


class CohortPreauthoringComposition:
    """Drives the REAL cohort classifier count over a crafted hermetic feature-delta."""

    def __init__(self) -> None:
        self._shape: FeatureDeltaShape | None = None
        self._placement_count: int | None = None
        self._authored_count: int = 0
        self._observed: CandidateAtCount | None = None

    # --- Given (preconditions: plant the feature-delta volumes) --------------

    def given_placement_candidate_count(self, count: int) -> None:
        self._placement_count = count

    def given_no_placement_section(self) -> None:
        self._placement_count = None

    def given_authored_scenario_count(self, count: int) -> None:
        self._authored_count = count

    def given_no_authored_scenarios(self) -> None:
        self._authored_count = 0

    # --- When (drive the REAL count function over the staged delta) ----------

    def when_classifier_counts_candidates(self, tmp_path: Path) -> None:
        """Stage the crafted feature-delta under tmp_path; drive the real count.

        Lazy import of the production count function inside the driving-port
        invocation so collection is clean regardless of seam state.
        """
        shape = FeatureDeltaShape(
            placement_candidate_count=self._placement_count,
            authored_scenario_count=self._authored_count,
        )
        delta_dir = tmp_path / "docs" / "feature" / "synthetic-cohort-preauthoring"
        delta_dir.mkdir(parents=True, exist_ok=True)
        delta_path = delta_dir / "feature-delta.md"
        delta_path.write_text(_render_feature_delta(shape), encoding="utf-8")

        cohort_classifier = _load_cohort_classifier()  # lazy driving-port load

        reported = cohort_classifier._count_ats(delta_path, "feature_delta")
        self._observed = CandidateAtCount(value=reported)

    # --- Then (assert on the port-exposed observable) ------------------------

    def then_reported_count_is(self, expected: int) -> None:
        assert self._observed is not None, (
            "no candidate-AT count was observed -- the count function was never "
            "driven (When step did not run)"
        )
        assert self._observed.value == expected, (
            "the cohort classifier reported candidate-AT count "
            f"{self._observed.value}, expected {expected} "
            f"(placement={self._placement_count}, authored={self._authored_count}); "
            "the pre-authoring candidate-list count + larger-of-the-two return is "
            "not yet implemented for the feature_delta kind"
        )

"""Pure-domain registry for rigor-gated DISTILL review steps.

A review step (e.g. Eclipse = ``nw-product-owner-reviewer``) either fires or
does not for a given project, decided purely from three inputs: the step
catalog, the per-step overrides under ``rigor.review_steps``, and the
profile-level ``rigor.review_enabled`` flag. No I/O happens here -- the
config-read lives in the ``DESConfig`` adapter, which delegates to
``ReviewStepResolver``.

Resolution precedence (DSN-3, EXACT)::

    enabled = True if always_on else (override.enabled if present else review_enabled)
    model = override.model if (override present and has model) else reviewer_model
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar, cast


_T = TypeVar("_T")


@dataclass(frozen=True)
class ReviewStepDefinition:
    """Catalog entry for one DISTILL review step.

    ``always_on`` steps (e.g. Sentinel) fire regardless of toggles; the rest
    follow the per-step override, falling back to the profile review flag.
    """

    id: str
    agent: str
    always_on: bool


# Extensible catalog -- later slices append further reviewers. slice-01 needs
# Eclipse (toggleable PO reviewer) and Sentinel (always-on AT-design reviewer);
# slice-03 adds Architect and Forge as the remaining cost-driven (toggleable)
# DISTILL reviewers, each independently togglable via the resolver; slice-06
# adds swarm (placeholder for the upcoming end-of-epic adversarial swarm /
# per-wave reviewers) -- proving the registry absorbs a new catalog member
# through the exact same resolver path, with zero resolver-logic changes
# (DD-D4/DSN-5).
REVIEW_STEP_CATALOG: tuple[ReviewStepDefinition, ...] = (
    ReviewStepDefinition(
        id="eclipse", agent="nw-product-owner-reviewer", always_on=False
    ),
    ReviewStepDefinition(
        id="architect", agent="nw-solution-architect-reviewer", always_on=False
    ),
    ReviewStepDefinition(
        id="forge", agent="nw-platform-architect-reviewer", always_on=False
    ),
    ReviewStepDefinition(
        id="sentinel", agent="nw-acceptance-designer-reviewer", always_on=True
    ),
    ReviewStepDefinition(
        id="swarm", agent="nw-epic-end-swarm-reviewer", always_on=False
    ),
)


@dataclass(frozen=True)
class ResolvedReviewStepSet:
    """The firing review steps for a project; ``.active()`` yields them.

    ``model_for(step_id)`` exposes each active step's RESOLVED model (DSN-3
    model precedence): the per-step override model when pinned, else the
    profile-level reviewer model.

    ``is_always_on(step_id)`` exposes the catalog hard-pin (DD-D3): the Sentinel
    structural-correctness reviewer reports ``True`` and no config can disable
    it, while the cost-driven reviewers report ``False``. This turns the
    implicit ``always_on`` short-circuit into an inspectable contract.

    ``requires_agreement(step_id)`` exposes the per-step ``require_agreement``
    opt-in (ADR-RST-002, DD-2/DD-4): strict opt-in with no profile-level
    cascaded default -- an absent override resolves ``False`` regardless of
    the step's ``always_on``/``enabled`` status (DD-5 orthogonality).
    """

    _active: tuple[ReviewStepDefinition, ...]
    _models: dict[str, str]
    _always_on: dict[str, bool]
    _requires_agreement: dict[str, bool]

    def active(self) -> tuple[ReviewStepDefinition, ...]:
        """Return the review steps that fire (each carrying ``.id``)."""
        return self._active

    def model_for(self, step_id: str) -> str:
        """Return the resolved model for an active review step."""
        return self._models[step_id]

    def is_always_on(self, step_id: str) -> bool:
        """Return the catalog ``always_on`` hard-pin for a review step."""
        return self._always_on[step_id]

    def requires_agreement(self, step_id: str) -> bool:
        """Return the resolved ``require_agreement`` opt-in for a review step."""
        return self._requires_agreement[step_id]


class ReviewStepResolver:
    """Pure resolver: ``(catalog, overrides, review_enabled, reviewer_model)``."""

    def resolve(
        self,
        catalog: tuple[ReviewStepDefinition, ...],
        overrides: dict,
        review_enabled: bool,
        reviewer_model: str,
    ) -> ResolvedReviewStepSet:
        """Apply the DSN-3 enabled + model precedence to every catalog step."""
        active = tuple(
            step
            for step in catalog
            if self._is_enabled(step, overrides, review_enabled)
        )
        models = {
            step.id: self._model_for(step, overrides, reviewer_model) for step in active
        }
        always_on = {step.id: step.always_on for step in catalog}
        requires_agreement = {
            step.id: self._requires_agreement(step, overrides) for step in catalog
        }
        return ResolvedReviewStepSet(active, models, always_on, requires_agreement)

    def _is_enabled(
        self,
        step: ReviewStepDefinition,
        overrides: dict,
        review_enabled: bool,
    ) -> bool:
        if step.always_on:
            return True
        return bool(self._override_value(step, overrides, "enabled", review_enabled))

    def _model_for(
        self,
        step: ReviewStepDefinition,
        overrides: dict,
        reviewer_model: str,
    ) -> str:
        return self._override_value(step, overrides, "model", reviewer_model)

    def _requires_agreement(
        self,
        step: ReviewStepDefinition,
        overrides: dict,
    ) -> bool:
        return bool(self._override_value(step, overrides, "require_agreement", False))

    def _override_value(
        self,
        step: ReviewStepDefinition,
        overrides: dict,
        key: str,
        default: _T,
    ) -> _T:
        """Return this step's override ``key``, or ``default`` when absent.

        Consolidates the lookup shape ``_is_enabled``/``_model_for``/
        ``_requires_agreement`` each repeated verbatim (no override for this
        step -> ``default``; override present but ``key`` unset -> ``default``)
        -- a Shotgun Surgery smell where a future per-step attribute would
        otherwise need a fourth copy of this exact fallback logic.
        """
        override = overrides.get(step.id)
        if override is None:
            return default
        return cast("_T", override.get(key, default))

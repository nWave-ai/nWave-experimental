"""DISCUSS gate pure cores + verdict VOs (slice-07, nwave-flow-v2-enforcement).

SHAPE per DESIGN feature-delta § "Wave: DESIGN / [REF] slice-07 code-design
(DISCUSS gate wiring)". Pure data + pure decision; NO I/O. The filesystem reads
live in the injected capability ports (``ProductSsotReader`` / ``FeatureDeltaReader``);
these cores take the already-read result and decide deterministically.

- ``DiscussGateIn.evaluate(presence)`` decides the gate-IN precondition verdict.
- ``DiscussGateOut.evaluate(feature_delta_content)`` decides the gate-OUT
  readiness-for-DESIGN verdict; it is the §21.2.4 idempotent, re-runnable seam
  callable (same content -> same token).

Asymmetric authority (§22.0): a non-PASS token is a VETO (block), NEVER an
authorizing GO. PASS = "no objection found". INDETERMINATE is NEVER coerced to
PASS (§17 no-silent-pass): an unreadable root / absent delta degrades LOUD.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from types import ModuleType

    from des.cli.validate_feature_delta import SlicePlanResult
    from des.ports.driven_ports.product_ssot_reader import SsotPresence


# The slice-06 MECC floor (`validate_slice_plan_content` + `VERDICT_ACCEPTED`)
# lives in `des.cli.validate_feature_delta`. That module is a SELF-CONTAINED pure
# functional core (stdlib-only imports, no side-effects of its own) -- but its
# PARENT package `des.cli` runs the runtime-freshness gate at `__init__` import
# time (`des.cli.__init__` -> `assert_fresh_or_explain()`), a CLI
# composition-root concern. A DOMAIN core must NOT trigger that CLI side-effect
# (hexagonal dependency direction + the generality mandate: domain logic is
# Python + filesystem only, no CLI composition-root coupling). So we load the
# pure validator module STANDALONE from its file -- resolved from the
# side-effect-free `des` package location (robust across install layouts, not a
# hardcoded path) -- bypassing `des.cli.__init__`. The loaded module is cached.
_VALIDATE_FEATURE_DELTA_MODULE: ModuleType | None = None


def _validate_feature_delta() -> ModuleType:
    """Load `des.cli.validate_feature_delta` standalone (no `des.cli.__init__`).

    Resolves the module file from the `des` package location and loads it via
    `importlib.util` so the parent `des.cli` package -- and its import-time
    freshness gate -- is never executed. Cached after the first load.
    """
    global _VALIDATE_FEATURE_DELTA_MODULE
    if _VALIDATE_FEATURE_DELTA_MODULE is not None:
        return _VALIDATE_FEATURE_DELTA_MODULE
    import des

    module_path = (
        Path(des.__file__).resolve().parent / "cli" / "validate_feature_delta.py"
    )
    spec = importlib.util.spec_from_file_location(
        "des._discuss_gate_validate_feature_delta", module_path
    )
    if spec is None or spec.loader is None:  # pragma: no cover - import infra
        raise ImportError(f"cannot load slice-plan validator from {module_path!r}")
    module = importlib.util.module_from_spec(spec)
    # Register under the synthetic spec name BEFORE exec so that any @dataclass
    # defined in the loaded module can resolve its ``__module__`` during class
    # construction: under ``from __future__ import annotations`` dataclasses runs
    # ``sys.modules.get(cls.__module__).__dict__`` for every field annotation, and
    # an unregistered synthetic module makes that ``None`` (stdlib spec_from_file
    # idiom; the cache below still short-circuits repeat loads).
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _VALIDATE_FEATURE_DELTA_MODULE = module
    return module


class DiscussGateInToken(str, Enum):
    """Closed set -- the gate-IN precondition verdict (non-representable garbage).

    ``(str, Enum)`` is the repo-conformant spelling of the design's ``StrEnum``
    (mirrors ``WaveProvenance``): a closed token set with lowercase ``.value``.
    """

    PASS = "pass"  # all DISCUSS entry preconditions satisfied
    MISSING_SSOT = "missing-ssot"  # a required docs/product/ SSOT doc is absent
    MIGRATION_UNMET = "migration-unmet"  # docs/product/ absent (old non-migrated model)
    INDETERMINATE = (
        "indeterminate"  # the check MECHANISM could not run (unreadable root)
    )


class DiscussGateOutToken(str, Enum):
    """Closed set -- the gate-OUT (readiness-for-DESIGN) verdict."""

    PASS = "pass"  # MECC floor found NO objection (structural + cohesion)
    SLICE_PLAN_REJECTED = (
        "slice-plan-rejected"  # validate_slice_plan_content != accepted
    )
    INDETERMINATE = "indeterminate"  # feature-delta unreadable / absent (degrade-LOUD)


@dataclass(frozen=True)
class DiscussGateInResult:
    """The gate-IN decision VO.

    INVARIANT: ``token`` is the ONLY authority the caller reads; ``detail`` is a
    human diagnostic. A non-PASS token is a VETO (block), NEVER an authorizing GO
    (§22.0). PASS = "no objection found".
    """

    token: DiscussGateInToken
    detail: str


@dataclass(frozen=True)
class DiscussGateOutResult:
    """The gate-OUT decision VO.

    INVARIANT: ``token`` derives DETERMINISTICALLY from ``slice_plan_verdict``
    (PASS iff the verdict is ``accepted``). INVARIANT: INDETERMINATE is NEVER
    coerced to PASS -- an unreadable delta degrades LOUD (§17 no-silent-pass).
    """

    token: DiscussGateOutToken
    detail: str
    slice_plan_verdict: str


class DiscussGateIn:
    """Pure-CORE gate-IN decision (NO I/O -- takes the read result)."""

    @staticmethod
    def evaluate(presence: SsotPresence) -> DiscussGateInResult:
        """Decide the gate-IN precondition verdict from a ``SsotPresence`` read.

        Order (degrade-LOUD first, then coarsest unmet, then per-doc):
          indeterminate            -> INDETERMINATE (the read mechanism could not run)
          not product_dir_present  -> MIGRATION_UNMET (docs/product/ absent)
          any required doc missing -> MISSING_SSOT
          else                     -> PASS (no objection found, NOT authorization)
        """
        if presence.indeterminate:
            return DiscussGateInResult(
                token=DiscussGateInToken.INDETERMINATE,
                detail=(
                    "the DISCUSS gate-IN precondition check could not run "
                    "(product SSOT root unreadable) -- degrade-LOUD, never a "
                    "silent pass"
                ),
            )
        if not presence.product_dir_present:
            return DiscussGateInResult(
                token=DiscussGateInToken.MIGRATION_UNMET,
                detail=(
                    "docs/product/ is absent -- the product migration-gate is "
                    "unmet, so the discuss wave cannot start from an un-migrated "
                    "product model"
                ),
            )
        missing = presence.missing_docs()
        if missing:
            return DiscussGateInResult(
                token=DiscussGateInToken.MISSING_SSOT,
                detail=(
                    "the product SSOT is incomplete -- missing "
                    f"{', '.join(missing)} under docs/product/"
                ),
            )
        return DiscussGateInResult(
            token=DiscussGateInToken.PASS,
            detail="all DISCUSS entry preconditions satisfied (no objection found)",
        )


class DiscussGateOut:
    """The re-runnable, idempotent gate-OUT seam check (§21.2.4)."""

    @staticmethod
    def evaluate(feature_delta_content: str | None) -> DiscussGateOutResult:
        """Decide the gate-OUT verdict from the feature-delta content.

        Order (§8 gate-OUT, structural FIRST):
          content is None -> INDETERMINATE (delta unreadable/absent; degrade-LOUD)
          slice plan != accepted -> SLICE_PLAN_REJECTED (the MECC floor:
            structural 5-column AND slice-06 cohesion-MECC in ONE call)
          else -> PASS (no objection found; readiness-for-DESIGN, NOT a GO)

        IDEMPOTENT + RE-RUNNABLE: same content -> same token. This property IS
        the §21.2.4 seam contract a future DESIGN gate-IN re-runs.
        """
        if feature_delta_content is None:
            return DiscussGateOutResult(
                token=DiscussGateOutToken.INDETERMINATE,
                detail=(
                    "the feature-delta could not be read (absent / unreadable) -- "
                    "degrade-LOUD, the gate-OUT is never coerced to a silent pass"
                ),
                slice_plan_verdict="indeterminate",
            )
        validator = _validate_feature_delta()
        slice_plan: SlicePlanResult = validator.validate_slice_plan_content(
            feature_delta_content
        )
        if slice_plan.verdict != validator.VERDICT_ACCEPTED:
            return DiscussGateOutResult(
                token=DiscussGateOutToken.SLICE_PLAN_REJECTED,
                detail=(
                    "the DISCUSS slice plan is not value-bearing -- "
                    f"{slice_plan.detail}"
                ),
                slice_plan_verdict=slice_plan.verdict,
            )
        return DiscussGateOutResult(
            token=DiscussGateOutToken.PASS,
            detail="the DISCUSS slice plan is value-bearing (no objection found)",
            slice_plan_verdict=slice_plan.verdict,
        )

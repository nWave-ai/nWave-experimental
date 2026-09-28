"""The invocable steps of the canonical order, each returning to its caller.

ADR-SSOT-002 Section 4b: «The DES exposes steps that may be invoked singly.
Each takes minimal typed input and returns one closed outcome ... A step never
chooses the next step: it NAMES the canonical next step as data and returns,
and the orchestrator calls again or does something else.»

WHY THIS IS A FACADE AND NOT A SECOND RUNNER.  Section 4b preserves «exactly one
resident software boundary that owns measurement, construction, enactment and
the handover», and names a second such owner as its own falsifier.  So every
step here delegates to `DeliveryContinuationRunner`, which keeps the whole
measuring and enacting half unchanged.  What this module adds is the part the
runner never had: taking the shared lock for ONE step, resolving the provider
port for ONE turn, and returning the closed outcome together with the role's
diagnostic instead of falling through into the next role.

WHAT IT DELIBERATELY DOES NOT HOLD.  No phase, no status, no attempt count, no
progress label, and no memory between calls.  Section 4b: «no process
composes.»  A step re-derives everything it needs from the two owned facts --
the persisted handover and the turn records -- so calling it twice after a
crash resumes rather than duplicates, and nothing here can be a second source
of truth about where a Request stands.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, cast

from des.adapters.driven.config.des_config import DESConfig
from des.application.delivery_continuation import (
    AcceptanceFinding,
    CraftSettlement,
    DeliveryContinuationRunner,
    DeliveryOutcome,
    DesignOptions,
    FailureDetail,
    FrozenHandover,
    OracleSettlement,
    RequestRewrite,
    RoleTurn,
    SelectedValue,
)
from des.application.design_document_producer import (
    DesignAuthorityBinding,
    DesignPublicationWidenings,
    bound_authority_headings,
    bound_value_headings,
    judge_design_destination,
    publish_design_document,
)
from des.application.discuss_document_producer import publish_discuss_document
from des.application.distill_document_producer import publish_distill_document
from des.application.evolution_document_producer import publish_evolution_document
from des.application.handover import (
    Blocked,
    BoundDesign,
    HandoverValue,
    SharedDesign,
    acquire_delivery_lock,
    bind_design_facts,
    bind_shared_design,
    create_constructed_handover,
    design_basis_sha256,
    rewrite_handover,
    stored_handover,
)
from des.application.operational_document_producer import publish_operational_document
from des.domain.algebraic_modelling_tools import algebra_line
from des.domain.delivery_disposition import Disposition
from des.domain.design_document import DesignDocument, DesignDocumentInvalid
from des.domain.discuss_contract import HOW_TO_FIX as DISCUSS_HOW_TO_FIX
from des.domain.discuss_document import (
    DiscussDocument,
    DiscussDocumentInvalid,
    DiscussValue,
)
from des.domain.distill_document import (
    V2_HOW,
    AcceptanceBrief,
    DistillDocument,
    DistillDocumentInvalid,
    PublishedAcceptance,
    SelectedAcceptanceRevision,
)
from des.domain.document_scope import DocumentScope, Project, legacy_scope
from des.domain.evolution_document import EvolutionDocument, EvolutionDocumentInvalid
from des.domain.feature_documents import FeatureDocumentsInvalid
from des.domain.operational_document import (
    OperationalDocument,
    OperationalDocumentInvalid,
)
from des.ports.driven_ports.task_invocation_port import DesignFacts, ModelRun


if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from des.application.handover import StoredHandover
    from des.ports.driven_ports.task_invocation_port import TaskInvocationPort


@dataclass(frozen=True, slots=True)
class StepOutcome:
    """One step's closed outcome, plus the facts and words it carries back.

    `facts` are terminal lines the step measured and the orchestrator reads --
    the values a decomposition produced, a candidate SHA, a captured exit code.
    `diagnostic` is the role's own words forwarded VERBATIM when a role ran, and
    `None` when none did; nothing in this module or its callers parses it.

    `turns_bought` counts the provider turns whose PROCESS ran, which is not the
    same as the answers received: an envelope the boundary refuses costs a turn
    and leaves no diagnostic. Deriving "did a role run" from the diagnostic told
    a reader the software had refused before buying one over a turn the provider
    log shows was bought (measured 2026-09-06), so the count travels beside it.
    """

    disposition: Disposition
    failure: FailureDetail | None = None
    facts: tuple[str, ...] = ()
    diagnostic: str | None = None
    turns_bought: int = 0
    role: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.disposition is Disposition.Success


@dataclass(frozen=True, slots=True)
class RoleInvocation:
    """The one host-selected role turn and its closed step observation."""

    outcome: StepOutcome
    model_run: ModelRun | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DecompositionInput:
    """Everything ONE Product Owner turn is given, carried as one value.

    `request` is the Request to decompose, or `None` to correct the one the
    handover already carries.  `finding` is the correction the turn must answer.
    `operational_facts` are the DEVOPS constraints put in front of the Product
    Owner.  All three reach the runner: `finding` on the rewrite and on the first
    decomposition alike, `operational_facts` on the decomposition.

    Keyword-only because `request` and `finding` are both `str | None`: nothing
    here checks annotations at runtime, so a positional transposition would
    decompose the correction text AS the Request.
    """

    request: str | None
    finding: str | None = None
    operational_facts: dict[str, object] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ArchitectTurn:
    """Which value ONE architect turn is for, and how it differs from a first pass.

    `finding` is the correction the turn must answer, `None` on a first pass over
    an unbound value.  `competence` is an explicit construction parameter: absent,
    the invoked role resolves exactly as it otherwise would.

    Keyword-only because `finding` and `competence` are both `str | None`: nothing
    here checks annotations at runtime, so a positional transposition would send
    the correction text as the competence the role is resolved with.
    """

    position: int
    finding: str | None = None
    competence: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ReplacementModes:
    """Which of the three EXCLUSIVE DESIGN replacement or recovery modes was asked.

    They travel as one value because they are one decision: the step refuses when
    more than one is set, in the step's own words -- «DESIGN replacement and
    recovery modes are exclusive».

    Deliberately NOT `DesignPublicationWidenings`, which carries these same three
    beside `allow_untracked_recovery`: that fourth one is MEASURED by the step
    from what the value already carries, and a caller-facing record holding it
    would let a caller widen the one recovery the step exists to decide.

    Keyword-only because all three members are `bool`: nothing here checks
    annotations at runtime, so a positional transposition would ask for a legacy
    migration where a bound replacement was meant.
    """

    replace_current: bool = False
    migrate_legacy_rendering: bool = False
    replace_unbound: bool = False

    @property
    def conflicting(self) -> bool:
        """Whether more than one of the three exclusive modes was asked for."""
        return (
            sum(
                (
                    self.replace_current,
                    self.migrate_legacy_rendering,
                    self.replace_unbound,
                )
            )
            > 1
        )


#: No replacement and no recovery: construct over what is not yet there.  A
#: module constant rather than a default-argument call, which ruff's B008 refuses.
_NO_REPLACEMENT = ReplacementModes()


def blocked_disposition(blocked: Blocked) -> Disposition:
    """The ONE reading of `Blocked`'s two booleans (ADR-DES-003 §4).

    Three CLI files re-derived it inline, which is three chances to disagree
    about one value. It lives here, next to the other carrier translation.
    """
    if blocked.refusal:
        return Disposition.Refusal
    if blocked.retry:
        return Disposition.Retry
    return Disposition.Indeterminate


def _from_blocked(blocked: Blocked) -> StepOutcome:
    """One mapping from a software refusal into a step's terminal shape."""
    return StepOutcome(
        blocked_disposition(blocked),
        FailureDetail(blocked.what, blocked.why, blocked.how),
    )


def _from_outcome(
    outcome: DeliveryOutcome,
    diagnostic: str | None,
    turns_bought: int = 0,
    role: str | None = None,
) -> StepOutcome:
    return StepOutcome(
        outcome.disposition, outcome.failure, (), diagnostic, turns_bought, role
    )


def _retaining_bound_facts(
    supplied: DiscussValue, bound: HandoverValue | None
) -> HandoverValue:
    """Carry an already-bound value's downstream facts onto its corrected shape.

    DISCUSS names an observation and its dependencies; it never names the DESIGN
    authority or the acceptance projection keyed to that observation.  A
    correction therefore preserves those facts wherever the observation itself
    survives, and starts a renamed or newly added observation unbound.
    """
    if bound is None:
        return HandoverValue(supplied.observation, supplied.dependencies, None)
    return replace(
        bound, observation=supplied.observation, dependencies=supplied.dependencies
    )


def _feature_scope(
    stored: StoredHandover | None,
    explicit: DocumentScope | str | None,
    *,
    project: bool = False,
) -> DocumentScope | StepOutcome:
    """Select an explicit scope or inherit the complete durable identity."""
    bound = stored.scope if stored is not None else None
    if project and explicit is not None:
        return _scope_refusal(
            "DocumentScopeConflict",
            "more than one document scope was supplied",
            "supply exactly one of --project, --epic ID, --feature ID, or --slice FEATURE_ID SLICE_ID",
        )
    if project:
        if stored is not None and not isinstance(bound, Project):
            return _scope_refusal(
                "FeatureScopeMismatch",
                f"the active handover is bound to {bound}, not project scope",
                "continue the bound feature or explicitly replace DISCUSS scope",
            )
        return Project()
    if explicit is not None:
        try:
            explicit = legacy_scope(explicit)
        except FeatureDocumentsInvalid as error:
            return _scope_refusal(error.what, error.why, error.how)
        if stored is not None and bound != explicit:
            return _scope_refusal(
                "FeatureScopeMismatch",
                f"the active handover is bound to {bound}, not {explicit}",
                "omit --feature to continue the bound scope, or finish that "
                "Request before starting another",
            )
    if explicit is None and stored is None:
        return _scope_refusal(
            "DocumentScopeMissing",
            "no explicit scope was supplied and no handover can provide it",
            "supply exactly one of --project, --epic ID, --feature ID, or --slice FEATURE_ID SLICE_ID",
        )
    return explicit if explicit is not None else bound


def _scope_refusal(what: str, why: str, how: str) -> StepOutcome:
    return StepOutcome(Disposition.Refusal, FailureDetail(what, why, how))


def _scoped_destination(
    resolve: Callable[..., str | None], root: Path, feature: DocumentScope | str | None
) -> str | StepOutcome | None:
    """A destination resolved at the scope, or a refusal that wrote nothing."""
    try:
        return resolve(root, feature)
    except FeatureDocumentsInvalid as error:
        return _scope_refusal(error.what, error.why, error.how)


def _design_destination(root: Path, scope: DocumentScope) -> str | StepOutcome:
    """The configured DESIGN destination at the resolved scope, or a refusal."""
    destination = _scoped_destination(
        DESConfig.design_document_destination, root, scope
    )
    if isinstance(destination, StepOutcome):
        return destination
    if destination is None:
        return StepOutcome(
            Disposition.Refusal,
            FailureDetail(
                "DesignDestinationMissing",
                "no effective documents.design.destination is configured",
                "configure documents.design.destination in repository or global config",
            ),
        )
    return destination


def _heading_owned(owner: str) -> StepOutcome:
    return StepOutcome(
        Disposition.Refusal,
        FailureDetail(
            "DesignAuthorityHeadingOwned",
            f"the manifest heading is already owned by {owner}",
            "choose a heading no other DESIGN section of this Request owns",
        ),
    )


def _has_selection(value: HandoverValue) -> bool:
    return bool(value.acceptance) or value.acceptance_oracle is not None


def _selection_is(
    value: HandoverValue, revision: SelectedAcceptanceRevision, stored: StoredHandover
) -> bool:
    """The stored selection IS this complete revision, over the current DESIGN."""
    return (
        value.acceptance == revision.obligations
        and value.acceptance_oracle == revision.oracle
        and value.acceptance_supports == revision.supports
        and value.acceptance_verification == revision.verification
        and value.acceptance_oracle_verification_index
        == revision.oracle_verification_index
        and value.acceptance_design_basis_sha256
        == design_basis_sha256(stored.shared_design, value)
    )


def _selected(
    value: HandoverValue, revision: SelectedAcceptanceRevision, stored: StoredHandover
) -> HandoverValue:
    """The value with the complete revision selected over the current DESIGN."""
    return replace(
        value,
        acceptance=revision.obligations,
        acceptance_oracle=revision.oracle,
        acceptance_supports=revision.supports,
        acceptance_verification=revision.verification,
        acceptance_oracle_verification_index=revision.oracle_verification_index,
        acceptance_design_basis_sha256=design_basis_sha256(stored.shared_design, value),
    )


def _published(value: HandoverValue) -> PublishedAcceptance:
    return PublishedAcceptance(
        value.observation,
        value.acceptance,
        cast("str", value.acceptance_oracle),
        value.acceptance_supports,
    )


@dataclass(slots=True)
class DeliverySteps:
    """Each method is ONE step: it locks, runs one turn, and returns."""

    invoker: TaskInvocationPort | None = None
    #: Explicit --feature of the step being run; the durable binding is the
    #: handover's own feature_id (see _feature_scope).
    _feature: DocumentScope | str | None = None
    _project: bool = False

    def decompose(
        self,
        root: Path,
        given: DecompositionInput,
        feature: DocumentScope | str | None = None,
        project: bool = False,
    ) -> StepOutcome:
        """One Product Owner turn over the given Request, recorded as the graph.

        IDEMPOTENT against the handover, which is what makes a re-invocation
        after a crash a resume rather than a second paid turn: a graph that
        already exists for this exact Request is REPORTED, never re-elicited and
        never overwritten.  A graph that exists for a DIFFERENT Request is
        refused LOUD with both moves named, and this step deletes nothing --
        the bytes on disk are somebody's unfinished delivery.
        """
        self._feature = feature
        self._project = project
        return self._locked(
            root, lambda runner, port: self._decompose(runner, port, root, given)
        )

    def design(
        self,
        root: Path,
        position: int,
        finding: str | None = None,
        *,
        competence: str | None = None,
        feature: DocumentScope | str | None = None,
    ) -> StepOutcome:
        """One architect turn for the value at `position`, derived and bound.

        REPEATABLE, which is what makes a correction the same step rather than a
        second one.  Called again over a bound value with `finding`, the turn
        receives the CURRENT typed facts beside the finding and what it returns
        REPLACES them.  Which finding goes back to which role, and whether to
        spend a turn on it at all, is the orchestrator's decision.

        `competence` is an explicit construction parameter: absent, the invoked
        role resolves exactly as before; the orchestrator passes it only when
        this turn needs a different competence than the role's ordinary one.
        """
        self._feature = feature
        turn = ArchitectTurn(position=position, finding=finding, competence=competence)
        return self._locked(
            root, lambda runner, port: self._design(runner, port, root, turn)
        )

    def design_document(
        self,
        root: Path,
        position: int,
        raw: str,
        *,
        modes: ReplacementModes = _NO_REPLACEMENT,
        feature: DocumentScope | str | None = None,
    ) -> StepOutcome:
        """Bind a caller-supplied closed v1 document without a provider turn."""
        try:
            document = DesignDocument.from_json(raw)
        except DesignDocumentInvalid as error:
            return StepOutcome(
                Disposition.Refusal,
                FailureDetail(
                    "InvalidDesignDocument",
                    str(error),
                    "provide the complete closed v1 DESIGN JSON manifest",
                ),
            )
        lock = acquire_delivery_lock(root)
        if isinstance(lock, Blocked):
            return _from_blocked(lock)
        try:
            stored = _graph(root)
            if isinstance(stored, StepOutcome):
                return stored
            ready = _value_at(stored, position)
            if isinstance(ready, StepOutcome):
                return ready
            scope = _feature_scope(stored, feature)
            if isinstance(scope, StepOutcome):
                return scope
            destination = _design_destination(root, scope)
            if isinstance(destination, StepOutcome):
                return destination
            authority_locator = f"{destination}#{document.heading}"
            if (
                stored.shared_design is not None
                and stored.shared_design.authority_locator == authority_locator
            ):
                return _heading_owned("the shared feature DESIGN")
            if isinstance(ready.authority, DesignFacts) and (
                ready.authority.authority_locator
                and ready.authority.authority_locator != authority_locator
            ):
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "DesignAuthorityIdentityMismatch",
                        "the manifest heading does not equal this value's persisted "
                        "DESIGN authority locator",
                        "keep the original configured path and heading for this value",
                    ),
                )
            if modes.conflicting:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "InvalidDesignMigration",
                        "DESIGN replacement and recovery modes are exclusive",
                        "choose one of bound replacement, legacy migration, or unbound recovery",
                    ),
                )
            if modes.replace_current and (
                not isinstance(ready.authority, DesignFacts)
                or not ready.authority.authority_locator
                or ready.authority.authority_locator != authority_locator
            ):
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "DesignAuthorityIdentityMismatch",
                        "--replace-current requires the selected value's persisted "
                        "DESIGN authority locator",
                        "first bind this value through the closed DESIGN constructor",
                    ),
                )
            if modes.migrate_legacy_rendering and ready.authority is not None:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "DesignLegacyMigrationNotRequired",
                        "the selected value already has persisted DESIGN facts",
                        "use ordinary DESIGN correction only when the semantic facts change",
                    ),
                )
            if modes.replace_unbound and ready.authority is not None:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "DesignUnboundRecoveryNotRequired",
                        "the selected value already has persisted DESIGN facts",
                        "use ordinary DESIGN correction only when the semantic facts change",
                    ),
                )
            facts = document.facts_at(authority_locator)
            allow_untracked_recovery = ready.authority is None or (
                ready.authority == facts
                and ready.design_semantic_sha256 == document.semantic_sha256
            )
            published = publish_design_document(
                root,
                destination,
                document,
                widenings=DesignPublicationWidenings(
                    allow_untracked_recovery=allow_untracked_recovery,
                    replace_current=modes.replace_current,
                    migrate_legacy_rendering=modes.migrate_legacy_rendering,
                    replace_unbound=modes.replace_unbound,
                ),
                binding=DesignAuthorityBinding(
                    authority_locator=(
                        ready.authority.authority_locator
                        if isinstance(ready.authority, DesignFacts)
                        and ready.authority.authority_locator
                        else None
                    ),
                    published_headings=bound_authority_headings(stored, destination),
                ),
            )
            if isinstance(published, Blocked):
                return _from_blocked(published)
            bound = bind_design_facts(
                root,
                stored,
                position,
                BoundDesign(facts, semantic_sha256=document.semantic_sha256),
                authority_persisted=published.authority_persisted,
            )
            if isinstance(bound, Blocked):
                if published.authority_persisted:
                    return StepOutcome(
                        Disposition.Indeterminate,
                        FailureDetail(
                            "DesignProjectionMixed",
                            "the complete DESIGN authority section was persisted but "
                            "the handover facts could not be compare-and-swap bound: "
                            + bound.why,
                            "inspect the authority and handover together before retrying",
                        ),
                    )
                return _from_blocked(bound)
            return StepOutcome(
                Disposition.Success,
                facts=(
                    f"DOCUMENT: {published.locator}",
                    f"DOCUMENT-SHA256: {published.digest}",
                    f"DESIGN-FACTS: {document.facts_json(facts)}",
                    "SCHEMA-VERSION: 1",
                ),
            )
        finally:
            lock.release()

    def shared_design_document(
        self,
        root: Path,
        raw: str,
        *,
        modes: ReplacementModes = _NO_REPLACEMENT,
        feature: DocumentScope | str | None = None,
    ) -> StepOutcome:
        """Bind the one DESIGN section shared by every value, buying no turn."""
        try:
            document = DesignDocument.from_json(raw)
        except DesignDocumentInvalid as error:
            return StepOutcome(
                Disposition.Refusal,
                FailureDetail(
                    "InvalidDesignDocument",
                    str(error),
                    "provide the complete closed v1 DESIGN JSON manifest",
                ),
            )
        lock = acquire_delivery_lock(root)
        if isinstance(lock, Blocked):
            return _from_blocked(lock)
        try:
            stored = _graph(root)
            if isinstance(stored, StepOutcome):
                return stored
            if feature is None and not stored.has_explicit_scope:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "SharedDesignScopeImplicit",
                        "the handover carries no persisted scope and no --feature "
                        "was given, so the shared design would land in an implied scope",
                        "pass --feature ID to construct the scope explicitly",
                    ),
                )
            # Explicit --feature on a scope-less graph CONSTRUCTS the scope; only
            # a persisted (or legacy feature_id) scope is compared, never Project.
            scope = _feature_scope(
                stored if stored.has_explicit_scope or stored.feature_id else None,
                feature,
            )
            if isinstance(scope, StepOutcome):
                return scope
            destination = _design_destination(root, scope)
            if isinstance(destination, StepOutcome):
                return destination
            locator = f"{destination}#{document.heading}"
            bound = stored.shared_design
            if document.heading in bound_value_headings(stored, destination):
                return _heading_owned("a value of this Request")
            if bound is not None and bound.authority_locator != locator:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "DesignAuthorityIdentityMismatch",
                        "the manifest heading does not equal the persisted shared "
                        "DESIGN authority locator",
                        "keep the original configured path and heading for the shared design",
                    ),
                )
            if modes.conflicting:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "InvalidDesignMigration",
                        "DESIGN replacement and recovery modes are exclusive",
                        "choose one of bound replacement, legacy migration, or unbound recovery",
                    ),
                )
            if bound is None and modes.replace_current:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "DesignAuthorityIdentityMismatch",
                        "--replace-current requires an already bound shared design",
                        "bind the shared design first, without --replace-current",
                    ),
                )
            if modes.migrate_legacy_rendering and bound is not None:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "DesignLegacyMigrationNotRequired",
                        "the shared DESIGN already has persisted facts",
                        "use ordinary DESIGN correction only when the semantic facts change",
                    ),
                )
            if modes.replace_unbound and bound is not None:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "DesignUnboundRecoveryNotRequired",
                        "the shared DESIGN already has persisted facts",
                        "use ordinary DESIGN correction only when the semantic facts change",
                    ),
                )
            if (
                bound is not None
                and not modes.replace_current
                and bound.semantic_sha256 != document.semantic_sha256
            ):
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "DesignAuthorityDrift",
                        "the shared DESIGN input differs semantically from the bound one",
                        "supply --replace-current to replace the shared design",
                    ),
                )
            facts = document.facts_at(locator)
            published = publish_design_document(
                root,
                destination,
                document,
                widenings=DesignPublicationWidenings(
                    allow_untracked_recovery=bound is None or bound.design == facts,
                    replace_current=modes.replace_current,
                    migrate_legacy_rendering=modes.migrate_legacy_rendering,
                    replace_unbound=modes.replace_unbound,
                ),
                binding=DesignAuthorityBinding(
                    authority_locator=bound.authority_locator if bound else None,
                    published_headings=bound_authority_headings(stored, destination),
                ),
            )
            if isinstance(published, Blocked):
                return _from_blocked(published)
            shared = SharedDesign(
                locator,
                hashlib.sha256(document.markdown().encode()).hexdigest(),
                document.semantic_sha256,
                facts,
            )
            rebound = bind_shared_design(root, stored, shared, scope=scope)
            if isinstance(rebound, Blocked):
                if published.authority_persisted:
                    return StepOutcome(
                        Disposition.Indeterminate,
                        FailureDetail(
                            "DesignProjectionMixed",
                            "the shared DESIGN section was persisted but the handover "
                            "binding could not be compare-and-swap written: "
                            + rebound.why,
                            "inspect the authority and handover together before retrying",
                        ),
                    )
                return _from_blocked(rebound)
            state = (
                "bound"
                if bound is None
                else "unchanged"
                if bound == shared
                else "replaced"
            )
            return StepOutcome(
                Disposition.Success,
                facts=(
                    f"AUTHORITY: {locator}",
                    f"SECTION-SHA256: {shared.section_sha256}",
                    f"SEMANTIC-SHA256: {shared.semantic_sha256}",
                    f"SHARED: {state}",
                ),
            )
        finally:
            lock.release()

    def operational_document(
        self,
        root: Path,
        raw: str,
        *,
        replace_current: bool = False,
        feature: DocumentScope | str | None = None,
        project: bool = False,
    ) -> StepOutcome:
        """Construct DEVOPS authority without resolving a provider or successor."""
        try:
            document = OperationalDocument.from_json(raw)
        except OperationalDocumentInvalid as error:
            return StepOutcome(
                Disposition.Refusal,
                FailureDetail(
                    "InvalidOperationalDocument",
                    str(error),
                    "provide the complete closed v1 OperationalDocumentInput JSON",
                ),
            )
        lock = acquire_delivery_lock(root)
        if isinstance(lock, Blocked):
            return _from_blocked(lock)
        try:
            stored = stored_handover(root)
            if isinstance(stored, Blocked):
                return _from_blocked(stored)
            scope = _feature_scope(stored, feature, project=project)
            if isinstance(scope, StepOutcome):
                return scope
            destination = _scoped_destination(
                DESConfig.operational_document_destination, root, scope
            )
            if isinstance(destination, StepOutcome):
                return destination
            if destination is None:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "OperationalDestinationMissing",
                        "no effective documents.devops.destination is configured",
                        "configure documents.devops.destination",
                    ),
                )
            published = publish_operational_document(
                root, destination, document, replace_current=replace_current
            )
            if isinstance(published, Blocked):
                return _from_blocked(published)
            if published.sidecar_failure is not None:
                failure = published.sidecar_failure
                return StepOutcome(
                    Disposition.Indeterminate,
                    FailureDetail(
                        failure.what,
                        "OperationalProjectionMixed: the Markdown authority was "
                        "persisted but the OperationalFacts sidecar was not confirmed: "
                        + failure.why,
                        "inspect the authority and sidecar together, then retry the "
                        "same OperationalDocumentInput",
                    ),
                )
            return StepOutcome(
                Disposition.Success,
                facts=(
                    f"DOCUMENT: {published.locator}",
                    f"DOCUMENT-SHA256: {published.digest}",
                    f"OPERATIONAL-FACTS: {published.facts_path}",
                ),
            )
        finally:
            lock.release()

    def evolution_document(self, root: Path, raw: str) -> StepOutcome:
        try:
            document = EvolutionDocument.from_json(raw)
        except EvolutionDocumentInvalid as error:
            return StepOutcome(
                Disposition.Refusal,
                FailureDetail(
                    "InvalidEvolutionDocument",
                    str(error),
                    "provide the complete closed v1 feature-evolution JSON",
                ),
            )
        lock = acquire_delivery_lock(root)
        if isinstance(lock, Blocked):
            return _from_blocked(lock)
        try:
            published = publish_evolution_document(
                root,
                DESConfig.evolution_document_destination(
                    root, document.date, document.feature_id
                ),
                document,
            )
            if isinstance(published, Blocked):
                return _from_blocked(published)
            return StepOutcome(
                Disposition.Success,
                facts=(
                    f"DOCUMENT: {published.locator}",
                    f"DOCUMENT-SHA256: {published.digest}",
                ),
            )
        finally:
            lock.release()

    def discuss_document(
        self,
        root: Path,
        raw: str,
        *,
        project: bool,
        replace_current: bool = False,
        feature: DocumentScope | str | None = None,
    ) -> StepOutcome:
        """Construct the DISCUSS authority, or explicitly correct the current one.

        ``replace_current`` supersedes the owned brief and its ordered graph in
        one turn.  The correction is SELECTIVE: every downstream fact already
        bound to an observation that survives the correction is carried over
        unchanged, and only an observation the supplied graph drops or renames
        loses the facts that were keyed to it.
        """
        if project == (feature is not None):
            return _scope_refusal(
                "DocumentScopeMissing" if not project else "DocumentScopeConflict",
                "DISCUSS requires exactly one explicit scope",
                "supply --project, --epic ID, --feature ID, or --slice FEATURE_ID SLICE_ID",
            )
        try:
            document = DiscussDocument.from_json(raw)
        except DiscussDocumentInvalid as error:
            return StepOutcome(
                Disposition.Refusal,
                FailureDetail(
                    "InvalidDiscussDocument",
                    str(error),
                    DISCUSS_HOW_TO_FIX,
                ),
            )
        lock = acquire_delivery_lock(root)
        if isinstance(lock, Blocked):
            return _from_blocked(lock)
        try:
            stored = stored_handover(root)
            if isinstance(stored, Blocked):
                return _from_blocked(stored)
            if replace_current and (
                stored is None or stored.request != document.request
            ):
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "DiscussAuthorityIdentityMismatch",
                        "--replace-current requires a persisted graph carrying this "
                        "Request",
                        "construct this Request through des discuss before correcting "
                        "it",
                    ),
                )
            requested_scope = Project() if project else legacy_scope(feature)
            scope_changed = (
                replace_current
                and stored is not None
                and stored.scope != requested_scope
            )
            retained = (
                {value.observation: value for value in stored.values}
                if replace_current and stored is not None and not scope_changed
                else {}
            )
            graph = tuple(
                _retaining_bound_facts(value, retained.get(value.observation))
                for value in document.values
            )
            if (
                not replace_current
                and stored is not None
                and (
                    stored.request != document.request
                    or tuple(
                        (value.observation, value.dependencies)
                        for value in stored.values
                    )
                    != tuple((value.observation, value.dependencies) for value in graph)
                )
            ):
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "DiscussHandoverConflict",
                        "stored and supplied request/value graphs are incompatible; supply --replace-current to correct the persisted graph",
                        "resume the stored graph or rerun with --replace-current",
                    ),
                )
            if replace_current:
                if feature is not None:
                    try:
                        legacy_scope(feature)
                    except FeatureDocumentsInvalid as error:
                        return _scope_refusal(error.what, error.why, error.how)
                scope = requested_scope
            else:
                scope = _feature_scope(stored, feature, project=project)
                if isinstance(scope, StepOutcome):
                    return scope
            destination = _scoped_destination(
                DESConfig.discuss_document_destination, root, scope
            )
            if isinstance(destination, StepOutcome):
                return destination
            published = publish_discuss_document(
                root,
                destination,
                document,
                replace_current=replace_current,
            )
            if isinstance(published, Blocked):
                return _from_blocked(published)
            if (
                replace_current
                and stored is not None
                and (graph != stored.values or scope_changed)
            ):
                rewritten = rewrite_handover(
                    root,
                    stored.raw,
                    document.request,
                    graph,
                    feature_id=scope,
                )
                if isinstance(rewritten, Blocked):
                    return StepOutcome(
                        Disposition.Indeterminate,
                        FailureDetail(
                            rewritten.what,
                            f"{rewritten.why}; DISCUSS authority may already have changed at {published.locator}",
                            rewritten.how,
                        ),
                        (
                            f"DOCUMENT: {published.locator}",
                            f"DOCUMENT-SHA256: {published.digest}",
                        ),
                    )
            if stored is None:
                created = create_constructed_handover(
                    root, document.request, graph, scope
                )
                if isinstance(created, Blocked):
                    return StepOutcome(
                        # The document has already been published.  Even a
                        # refusal-shaped winner mismatch cannot truthfully
                        # claim that this multi-file construction refused
                        # before writing an authority.
                        Disposition.Indeterminate,
                        FailureDetail(
                            created.what,
                            f"{created.why}; DISCUSS authority may already have changed at {published.locator}",
                            created.how,
                        ),
                        (
                            f"DOCUMENT: {published.locator}",
                            f"DOCUMENT-SHA256: {published.digest}",
                        ),
                    )
            return StepOutcome(
                Disposition.Success,
                facts=(
                    f"DOCUMENT: {published.locator}",
                    f"DOCUMENT-SHA256: {published.digest}",
                ),
            )
        finally:
            lock.release()

    def distill_document(
        self,
        root: Path,
        raw: str,
        *,
        replace_current: bool = False,
        feature: DocumentScope | str | None = None,
    ) -> StepOutcome:
        try:
            document = DistillDocument.from_json(raw)
        except DistillDocumentInvalid as error:
            return StepOutcome(
                Disposition.Refusal,
                FailureDetail(
                    "InvalidDistillDocument",
                    str(error),
                    V2_HOW,
                ),
            )
        lock = acquire_delivery_lock(root)
        if isinstance(lock, Blocked):
            return _from_blocked(lock)
        try:
            stored = stored_handover(root)
            if isinstance(stored, Blocked):
                return _from_blocked(stored)
            if stored is None:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "DistillHandoverMissing",
                        "DISTILL requires the existing Request/value graph",
                        "run the producer that establishes the Request first",
                    ),
                )
            incoming = {value.observation: value for value in document.values}
            stored_by_observation = {
                value.observation: value for value in stored.values
            }
            unknown = tuple(
                value.observation
                for value in document.values
                if value.observation not in stored_by_observation
            )
            if unknown:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "DistillHandoverConflict",
                        "supplied observations are not in the stored graph",
                        "supply acceptance facts only for existing observations",
                    ),
                )
            for supplied in document.values:
                value = stored_by_observation[supplied.observation]
                if (
                    not replace_current
                    and _has_selection(value)
                    and not _selection_is(value, supplied.revision, stored)
                ):
                    return StepOutcome(
                        Disposition.Refusal,
                        FailureDetail(
                            "DistillHandoverConflict",
                            "the stored selection differs from the supplied "
                            "revision, or was made over another DESIGN, or is "
                            "an incomplete schema_version 1 selection",
                            "supply the complete schema_version 2 revision with "
                            "--replace-current to replace the selection",
                        ),
                    )
            prior_brief = AcceptanceBrief(
                tuple(_published(value) for value in stored.values if value.acceptance)
            )
            merged_brief = AcceptanceBrief(
                tuple(
                    PublishedAcceptance(
                        value.observation,
                        incoming[value.observation].obligations,
                        incoming[value.observation].oracle,
                        incoming[value.observation].supports,
                    )
                    if value.observation in incoming
                    else _published(value)
                    for value in stored.values
                    if value.observation in incoming or value.acceptance
                )
            )
            scope = _feature_scope(stored, feature)
            if isinstance(scope, StepOutcome):
                return scope
            destination = _scoped_destination(
                DESConfig.distill_document_destination, root, scope
            )
            if isinstance(destination, StepOutcome):
                return destination
            published = publish_distill_document(
                root,
                destination,
                merged_brief,
                stored.request,
                prior_brief if prior_brief.values else None,
            )
            if isinstance(published, Blocked):
                return _from_blocked(published)
            values = tuple(
                _selected(value, incoming[value.observation].revision, stored)
                if value.observation in incoming
                else value
                for value in stored.values
            )
            from des.application.handover import rewrite_handover

            updated = (
                stored
                if values == stored.values
                else rewrite_handover(root, stored.raw, stored.request, values)
            )
            if isinstance(updated, Blocked):
                return StepOutcome(
                    Disposition.Indeterminate,
                    FailureDetail(
                        updated.what,
                        f"{updated.why}; DISTILL authority may already have changed at {published.locator}",
                        updated.how,
                    ),
                    (
                        f"DOCUMENT: {published.locator}",
                        f"DOCUMENT-SHA256: {published.digest}",
                    ),
                )
            return StepOutcome(
                Disposition.Success,
                facts=(
                    f"DOCUMENT: {published.locator}",
                    f"DOCUMENT-SHA256: {published.digest}",
                ),
            )
        finally:
            lock.release()

    def oracle(
        self, root: Path, position: int, finding: str | None = None
    ) -> StepOutcome:
        """Author or correct one value's oracle, measure it RED, and judge it.

        The RED measurement runs before the judgement because it is free next to
        it: on run 23 the reviewer approved a broken oracle in 27.4s of paid turn
        while the same oracle answers `broken` to an execution in 1.1s of wall.

        A refusal that ONE named owner may still repair carries that owner back
        as DATA -- the reviewer's own closed word, never read by this software --
        so the orchestrator can choose which step answers it.
        """
        return self._locked(
            root,
            lambda runner, port: self._oracle(runner, port, root, position, finding),
        )

    def craft(self, root: Path, position: int) -> StepOutcome:
        """One crafter turn for this value's batch, returning its blocker as data.

        A refusing turn names WHO can unblock it in a closed word of its typed
        payload, and this step forwards that word on `BLOCKED-BY` and stops.
        The composed run spends one window on the role it names; a step invoked
        alone must not, because that choice is the orchestrator's (Section 4b).
        """
        return self._locked(
            root, lambda runner, port: self._craft(runner, port, root, position)
        )

    def verify(self, root: Path) -> StepOutcome:
        """One whole-Request candidate and its declared native observation."""
        return self._locked_native(root, lambda runner: self._verify(runner, root))

    def invoke_role(
        self,
        root: Path,
        cwd: Path,
        role_id: str,
        prompt: str,
        semantic_task: str | None = None,
    ) -> RoleInvocation:
        """Issue one already-selected host role and return its typed observation.

        The CLI binds the selected runtime and the persisted role input. This
        boundary owns the one provider turn, its cooperative lock, and the
        truthful turn telemetry; it neither sequences another role nor
        interprets the returned model result.
        """
        runner = DeliveryContinuationRunner(self.invoker)
        port = runner.resolve_port(root)
        if isinstance(port, DeliveryOutcome):
            return RoleInvocation(_from_outcome(port, None))
        lock = acquire_delivery_lock(root)
        if isinstance(lock, Blocked):
            return RoleInvocation(_from_blocked(lock))
        try:
            invoked = runner._invoke(
                port,
                cwd,
                RoleTurn(role=role_id, prompt=prompt, semantic_task=semantic_task),
                FrozenHandover(raw=None),
            )
            if isinstance(invoked, DeliveryOutcome):
                return RoleInvocation(
                    _from_outcome(
                        invoked,
                        runner.last_diagnostic,
                        runner.turns_bought,
                        runner.last_role,
                    )
                )
            return RoleInvocation(
                StepOutcome(
                    Disposition.Success,
                    diagnostic=runner.last_diagnostic,
                    turns_bought=runner.turns_bought,
                    role=runner.last_role,
                ),
                invoked,
            )
        finally:
            lock.release()

    def integrate(
        self, root: Path, candidate: str, on_my_evidence: str | None = None
    ) -> StepOutcome:
        """Compare-and-swap one candidate in, reconcile, and close the graph.

        `on_my_evidence` is an optional host rationale retained for compatibility.
        Integration performs candidate identity, compare-and-swap, reconciliation,
        and cleanup mechanics; it does not interpret role observations as admission.
        """
        return self._locked(
            root,
            lambda runner, _port: self._integrate(
                runner, root, candidate, on_my_evidence
            ),
        )

    # ----------------------------------------------------------------- inner

    def _decompose(
        self,
        runner: DeliveryContinuationRunner,
        port: TaskInvocationPort,
        root: Path,
        given: DecompositionInput,
    ) -> StepOutcome:
        # `request` is the only one of the three that is re-bound below -- an
        # absent Request resumes the stored one -- so it is the only one taken
        # out of the record.
        request = given.request
        stored = stored_handover(root)
        if isinstance(stored, Blocked):
            return _from_blocked(stored)
        scope = _feature_scope(stored, self._feature, project=self._project)
        if isinstance(scope, StepOutcome):
            return scope
        checked = _scoped_destination(
            DESConfig.discuss_document_destination, root, scope
        )
        if isinstance(checked, StepOutcome):
            return checked
        runner.feature_id = scope
        if request is None:
            if stored is None:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "FindingRequestUnavailable",
                        "a finding on stdin requires an existing Request to correct",
                        "supply the original Request on stdin and additional context "
                        "as --finding <text>, or create the Request first",
                    ),
                )
            request = stored.request
        if stored is not None and stored.request == request and given.finding is None:
            # L1: the same Request over the graph it produced is a resume.
            return StepOutcome(Disposition.Success, facts=_value_facts(stored))
        if stored is not None:
            # ADR-DES-003 §7: a Request that differs is not a mismatch to
            # refuse. It is a REWRITE, and the six hand deletions of the
            # handover on 2026-09-05/06 are what it replaces.
            rewritten = runner.rewrite_request(
                root, port, stored, request, finding=given.finding
            )
            diagnostic = runner.last_diagnostic
            if isinstance(rewritten, DeliveryOutcome):
                return _from_outcome(
                    rewritten, diagnostic, runner.turns_bought, runner.last_role
                )
            graph, split = rewritten
            return StepOutcome(
                Disposition.Success,
                facts=(*_value_facts(graph), *_split_facts(graph, split)),
                diagnostic=diagnostic,
                turns_bought=runner.turns_bought,
                role=runner.last_role,
            )
        decomposed = runner.decompose(
            root, port, request, given.operational_facts, finding=given.finding
        )
        diagnostic = runner.last_diagnostic
        if isinstance(decomposed, DeliveryOutcome):
            return _from_outcome(
                decomposed, diagnostic, runner.turns_bought, runner.last_role
            )
        return StepOutcome(
            Disposition.Success,
            facts=_value_facts(decomposed),
            diagnostic=diagnostic,
            turns_bought=runner.turns_bought,
            role=runner.last_role,
        )

    def _design(
        self,
        runner: DeliveryContinuationRunner,
        port: TaskInvocationPort,
        root: Path,
        turn: ArchitectTurn,
    ) -> StepOutcome:
        stored = _graph(root)
        if isinstance(stored, StepOutcome):
            return stored
        ready = _value_at(stored, turn.position)
        if isinstance(ready, StepOutcome):
            return ready
        if turn.finding is None and ready.authority is not None:
            # L1 (ADR-DES-003 §2): the second call over a bound value succeeds,
            # changes nothing and costs nothing. Without this it re-bought the
            # architect and SILENTLY REPLACED the bound facts, so a retry after
            # a lost terminal was a paid overwrite. Re-binding is spelled
            # `--finding -` and nothing else.
            # A designation is not evidence. Before the zero-cost Success is
            # composed, the value's own recorded locator is resolved against the
            # document ON DISK; a record and a file that disagree are reported,
            # never confirmed. Intercepted here, ahead of derivation, so the
            # refusal is about that one disagreement.
            disagreement = runner.confirm_recorded_authority(
                root, ready.authority, turn.position
            )
            if disagreement is not None:
                return _from_outcome(disagreement, None)
            facts = runner.derive_authority(root, ready.authority)
            if isinstance(facts, DeliveryOutcome):
                return _from_outcome(facts, None)
            return StepOutcome(
                Disposition.Success,
                facts=(
                    f"VALUE-{turn.position}: "
                    f"{json.dumps(ready.observation, ensure_ascii=False)}",
                    f"PARADIGM: {facts.paradigm}",
                    f"ORACLE: {facts.acceptance_oracle_locator}",
                    "TARGETS: "
                    + ", ".join(
                        f"{path} ({decision})"
                        for path, decision in facts.target_decisions
                    ),
                    algebra_line(),
                    "RECORDED: this value's typed design facts are already bound "
                    "over these bytes, so no turn was bought; re-bind with "
                    f"`des design --repo-root <root> --value {turn.position} "
                    "--finding -`",
                ),
            )
        # The STEP owns the destination and the role owns only the heading, so
        # the configured document is resolved here, at the same application
        # boundary the closed-document path resolves it at, and handed in.
        scope = _feature_scope(stored, self._feature)
        if isinstance(scope, StepOutcome):
            return scope
        destination = _scoped_destination(
            DESConfig.design_document_destination, root, scope
        )
        if isinstance(destination, StepOutcome):
            return destination
        # A destination the post-turn rule would refuse is refused HERE, on the
        # only expression that reaches a provider invocation, so the operator
        # pays nothing for an answer the software already knows it must refuse.
        # The judgement is the destination-only half of the very rule
        # `publish_design_document` applies afterwards, which is kept: a
        # destination replaced DURING the turn is still refused after it.
        if destination is not None:
            # The bound headings are threaded, never re-read inside the
            # producer: the pre-turn judge and the post-turn publish read the
            # SAME `stored` and cannot disagree about what this Request wrote.
            unsafe = judge_design_destination(
                root, destination, bound_authority_headings(stored, destination)
            )
            if unsafe is not None:
                return _from_blocked(unsafe)
        designed = runner.design_value(
            root,
            port,
            stored,
            ready,
            options=DesignOptions(
                finding=turn.finding,
                competence=turn.competence,
                destination=destination,
            ),
        )
        diagnostic = runner.last_diagnostic
        if isinstance(designed, DeliveryOutcome):
            return _from_outcome(
                designed, diagnostic, runner.turns_bought, runner.last_role
            )
        _, facts = designed
        # Printed only when a section was actually published, so a caller can
        # read from the terminal alone that this turn produced document bytes,
        # in the same two rows the closed-document path already prints.
        published = runner.published_design
        document = (
            ()
            if published is None
            else (
                f"DOCUMENT: {published.locator}",
                f"DOCUMENT-SHA256: {published.digest}",
            )
        )
        unchanged = (
            ("UNCHANGED: the accepted correction repeated the bound typed facts",)
            if runner.design_unchanged
            else ()
        )
        return StepOutcome(
            Disposition.Success,
            facts=(
                f"VALUE-{turn.position}: "
                f"{json.dumps(ready.observation, ensure_ascii=False)}",
                f"PARADIGM: {facts.paradigm}",
                f"ORACLE: {facts.acceptance_oracle_locator}",
                "TARGETS: "
                + ", ".join(
                    f"{path} ({decision})" for path, decision in facts.target_decisions
                ),
                *document,
                *unchanged,
                # Section 1a item 6 is settled HERE, where the typed facts that
                # would carry an algebra are bound, and it is stated in both
                # directions: a line printed only when the checker is missing
                # would teach the reader that silence means the obligation met.
                algebra_line(),
            ),
            diagnostic=diagnostic,
            turns_bought=runner.turns_bought,
            role=runner.last_role,
        )

    def _oracle(
        self,
        runner: DeliveryContinuationRunner,
        port: TaskInvocationPort,
        root: Path,
        position: int,
        finding: str | None,
    ) -> StepOutcome:
        stored = _graph(root)
        if isinstance(stored, StepOutcome):
            return stored
        ready = _value_at(stored, position)
        if isinstance(ready, StepOutcome):
            return ready
        if ready.authority is None:
            return _unbound_design(position)
        design = runner.selected_authority(root, stored, position)
        if isinstance(design, DeliveryOutcome):
            return _from_outcome(design, None, runner.turns_bought, runner.last_role)
        # The settlement is consulted ONLY when there is no finding, so
        # `--finding -` is untouched BY CONSTRUCTION rather than by a second
        # rule: re-opening an approved oracle is the orchestrator's decision and
        # no record may pre-empt it.
        if finding is None:
            settlement = runner.oracle_settlement(root, stored, ready, design)
            named = (
                f"VALUE-{position}: {json.dumps(ready.observation, ensure_ascii=False)}"
            )
            if settlement is OracleSettlement.RecordedOverCurrentBytes:
                return StepOutcome(
                    Disposition.Success,
                    facts=(
                        named,
                        f"ORACLE: {design.acceptance_oracle_locator}",
                        "RECORDED: this value's approved oracle turn is already a "
                        "recorded fact over these exact bytes, so no turn was bought",
                    ),
                )
            if settlement is OracleSettlement.SettledByItsOwnExecution:
                # The measured row is printed, not summarised away: it is what
                # makes the red arm and the green arm distinguishable by an
                # examiner, and ADR-DES-003 §3 G3 records the surviving
                # violation as a branch that PROMISES evidence it does not show.
                return StepOutcome(
                    Disposition.Success,
                    facts=(
                        named,
                        f"ORACLE: {design.acceptance_oracle_locator}",
                        *_oracle_red_facts(runner.settled_oracle_measured),
                        f"WITNESS: the tracked oracle {design.acceptance_paths[0]} "
                        "was executed on the current workspace bytes and RESOLVED "
                        "to its own verdict, so this value's moved oracle record "
                        "was re-pointed at them and no acceptance-designer turn "
                        "was bought",
                    ),
                )
        measurement = runner.oracle_value(
            root, port, SelectedValue(stored, ready, design), finding=finding
        )
        diagnostic = runner.last_diagnostic
        red = _oracle_red_facts(measurement.measured)
        refusal = measurement.refusal
        if refusal is None:
            return StepOutcome(
                Disposition.Success,
                facts=(
                    f"VALUE-{position}: "
                    f"{json.dumps(ready.observation, ensure_ascii=False)}",
                    f"ORACLE: {design.acceptance_oracle_locator}",
                    *red,
                ),
                diagnostic=diagnostic,
                turns_bought=runner.turns_bought,
                role=runner.last_role,
            )
        if isinstance(refusal, AcceptanceFinding):
            terminal = refusal.terminal
            assert terminal.failure is not None
            return StepOutcome(
                terminal.disposition,
                terminal.failure,
                facts=(*red, f"DEFECT-OWNER: {refusal.owner.value}"),
                diagnostic=diagnostic,
                turns_bought=runner.turns_bought,
                role=runner.last_role,
            )
        # The cost travels with the refusal, like everywhere else. Omitting it
        # here reported a REJECTING acceptance designer as costing nothing --
        # the same class this lane already repaired once at the terminal, found
        # again by the reference model on a generated sequence.
        return StepOutcome(
            refusal.disposition,
            refusal.failure,
            tuple(red),
            diagnostic,
            turns_bought=runner.turns_bought,
            role=runner.last_role,
        )

    def _craft(
        self,
        runner: DeliveryContinuationRunner,
        port: TaskInvocationPort,
        root: Path,
        position: int,
    ) -> StepOutcome:
        stored = _graph(root)
        if isinstance(stored, StepOutcome):
            return stored
        ready = _value_at(stored, position)
        if isinstance(ready, StepOutcome):
            return ready
        if ready.authority is None:
            return _unbound_design(position)
        design = runner.selected_authority(root, stored, position)
        if isinstance(design, DeliveryOutcome):
            return _from_outcome(design, None, runner.turns_bought, runner.last_role)
        # ONE closed word, three arms, and the step composes one terminal for
        # each.  Branching on two booleans here would put the settlement rule in
        # this facade, where `des state`'s own reader could not see it.
        settlement = runner.craft_settlement(root, stored, ready, design)
        named = f"VALUE-{position}: {json.dumps(ready.observation, ensure_ascii=False)}"
        if settlement is CraftSettlement.RecordedOverCurrentBytes:
            return StepOutcome(
                Disposition.Success,
                facts=(
                    named,
                    "RECORDED: this value's craft turn is already a recorded fact "
                    "over its mutable targets, so no turn was bought",
                ),
            )
        if settlement is CraftSettlement.SettledByGreenOracle:
            # The step STATES what settled the record.  A success that merely
            # went quiet would be indistinguishable from the recorded-current
            # resume above, and an operator whose bytes had moved would have no
            # way to tell that an execution -- not a coincidence -- closed it.
            return StepOutcome(
                Disposition.Success,
                facts=(
                    named,
                    f"WITNESS: the tracked oracle {design.acceptance_paths[0]} was "
                    "executed on the current workspace bytes and observed GREEN, "
                    "so this value's moved craft record was re-pointed at them "
                    "and no crafter turn was bought",
                ),
            )
        crafted = runner.craft_value(root, port, stored, ready, design)
        diagnostic = runner.last_diagnostic
        if isinstance(crafted, DeliveryOutcome):
            blocker = runner.last_blocker
            return StepOutcome(
                crafted.disposition,
                crafted.failure,
                facts=() if blocker is None else (f"BLOCKED-BY: {blocker}",),
                diagnostic=diagnostic,
                turns_bought=runner.turns_bought,
                role=runner.last_role,
            )
        return StepOutcome(
            Disposition.Success,
            facts=(
                f"VALUE-{position}: "
                f"{json.dumps(ready.observation, ensure_ascii=False)}",
                "TARGETS: " + ", ".join(path for path, _ in design.target_decisions),
                *(f"SILENT: {sentence}" for sentence in crafted),
            ),
            diagnostic=diagnostic,
            turns_bought=runner.turns_bought,
            role=runner.last_role,
        )

    def _verify(
        self,
        runner: DeliveryContinuationRunner,
        root: Path,
    ) -> StepOutcome:
        stored = _graph(root)
        if isinstance(stored, StepOutcome):
            return stored
        prepared = _prepared(runner, root, stored)
        if isinstance(prepared, StepOutcome):
            return prepared
        recorded = runner.verified_candidate(root, stored)
        if recorded is not None:
            # The native observation is candidate-bound and durable. Re-running
            # would execute its declared argv a second time rather than recover
            # the one measurement already made.
            if runner.load_native_evidence_identity(root, recorded):
                assert runner.native_evidence_locator is not None
                assert runner.native_evidence_sha256 is not None
                return StepOutcome(
                    Disposition.Success,
                    facts=(
                        f"CANDIDATE: {recorded}",
                        f"NATIVE-EVIDENCE: {runner.native_evidence_locator}",
                        f"NATIVE-EVIDENCE-SHA256: {runner.native_evidence_sha256}",
                        "RECORDED: this candidate already has native evidence, so no command ran",
                    ),
                )
            return StepOutcome(
                Disposition.Indeterminate,
                FailureDetail(
                    "NativeEvidenceUnavailable",
                    f"candidate {recorded} has a verify record but no single readable native observation bound to it",
                    "inspect .nwave/des/logs/native and explicitly decide whether to rebuild native evidence",
                ),
            )
        verified = runner.verify_request(root, None, stored, prepared)
        diagnostic = runner.last_diagnostic
        if isinstance(verified, DeliveryOutcome):
            # The measurement survives the refusal: Section 4b forbids a
            # terminal to omit a fact the software already held, and the owner
            # a judge named IS the orchestrator's next move. With the pre-craft
            # judge retired, the whole-diff reviewer is the oracle's only
            # independent judge, so a finding it charges to the oracle must
            # reach the author's step rather than the crafter's.
            owner = runner.last_review_owner
            charged = runner.last_review_value
            # The POSITIONS a finding can be answered at. When the judge named a
            # value the form is exact; when it did not, every position of this
            # Request is lawful and none is invented -- the cardinality is the
            # honest fork signal (G7), not a guess dressed as one form.
            positions = [
                str(index)
                for index, value in enumerate(stored.values, start=1)
                if charged is None or value.observation == charged
            ]
            return StepOutcome(
                verified.disposition,
                verified.failure,
                facts=(
                    f"RADIUS: {runner.radius}",
                    *(() if owner is None else (f"DEFECT-OWNER: {owner}",)),
                    *(
                        ()
                        if owner is None
                        else (f"DEFECT-POSITIONS: {','.join(positions)}",)
                    ),
                ),
                diagnostic=diagnostic,
                turns_bought=runner.turns_bought,
                role=runner.last_role,
            )
        _, candidate, evidence = verified
        locator = runner.native_evidence_locator
        digest = runner.native_evidence_sha256
        if locator is None or digest is None:
            return StepOutcome(
                Disposition.Indeterminate,
                FailureDetail(
                    "NativeEvidenceUnretained",
                    f"candidate {candidate} completed native verification but its observation could not be persisted",
                    "restore write access to .nwave/des/logs/native and verify again",
                ),
            )
        if not runner.persist_native_radius(root, candidate):
            return StepOutcome(
                Disposition.Indeterminate,
                FailureDetail(
                    "NativeRadiusUnretained",
                    f"candidate {candidate} native radius could not be persisted",
                    "restore .nwave/des/logs/radius write access",
                ),
            )
        runner.record_verified_candidate(root, stored, candidate, None)
        return StepOutcome(
            Disposition.Success,
            facts=(
                f"CANDIDATE: {candidate}",
                f"NATIVE-EVIDENCE: {locator}",
                f"NATIVE-EVIDENCE-SHA256: {digest}",
                f"RADIUS: {runner.radius}",
                *(
                    f"NATIVE: exit={item.exit_status} origin={item.origin} "
                    f"argv={' '.join(item.argv)}"
                    for item in evidence
                ),
            ),
            diagnostic=diagnostic,
            turns_bought=runner.turns_bought,
            role=runner.last_role,
        )

    def _integrate(
        self,
        runner: DeliveryContinuationRunner,
        root: Path,
        candidate: str,
        on_my_evidence: str | None = None,
    ) -> StepOutcome:
        already = runner.destination_is(root, candidate)
        stored = _graph(root)
        if isinstance(stored, StepOutcome):
            if already:
                # A truthful HOW on a repeat. The graph is closed BECAUSE this
                # candidate was integrated, and the inherited message told the
                # reader to decompose a Request first -- an accurate sentence
                # about a different situation, which is the class this project
                # records as «a rejection that lies about its own cause».
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "AlreadyIntegrated",
                        f"{candidate} is already the destination and its graph "
                        "is closed, so there is nothing left to swap",
                        "nothing is owed for this Request; start the next one "
                        "by piping it into `des po` on stdin",
                    ),
                )
            return stored
        # ADR-DES-003 §2.4 gives this step exactly two preconditions: a verify
        # record covers the candidate, and the candidate is a one-parent commit.
        # Deriving every value's facts BEFORE that check added a third the design
        # does not list -- `DesignUnbound` on a Request whose values are not all
        # bound -- and §4's class rule is «one per `requires` bit of §2.4». It is
        # also unnecessary: a verified candidate implies the values were designed,
        # because `verify` refuses without them. The reference model found this.
        record = runner.verification_record(root, stored)
        verified = None if record is None else record.candidate
        superseded = record is not None and not record.covers_current_upstream
        if verified != candidate or superseded:
            return StepOutcome(
                Disposition.Refusal,
                FailureDetail(
                    "CandidateUnverified",
                    f"no current verification record covers {candidate}"
                    + (
                        "; it was verified against a Request graph a wave "
                        "producer has since corrected, so the evidence covering "
                        "it was collected before the correction"
                        if superseded and verified == candidate
                        else f"; the recorded candidate is {verified}"
                        if verified is not None
                        else " and none is recorded for this Request"
                    ),
                    "verify it first with `des verify --repo-root <root>`, then "
                    "integrate the CANDIDATE that step printed",
                ),
            )
        prepared = _prepared(runner, root, stored)
        if isinstance(prepared, StepOutcome):
            return prepared
        base = runner.candidate_base(root, candidate)
        if isinstance(base, StepOutcome):
            return base
        integrated = runner.integrate_candidate(root, stored, prepared, base, candidate)
        if integrated.disposition is not Disposition.Success:
            return _from_outcome(
                integrated, None, runner.turns_bought, runner.last_role
            )
        return StepOutcome(
            Disposition.Success,
            facts=(
                f"INTEGRATED: {candidate}",
                "CLEANUP: complete",
            ),
        )

    def _locked(
        self,
        root: Path,
        work: Callable[[DeliveryContinuationRunner, TaskInvocationPort], StepOutcome],
    ) -> StepOutcome:
        """Take the checkout's one cooperative lock for the duration of ONE step.

        Each step still takes the lock for its own duration, so concurrent
        mutation stays impossible; what disappears with the retired composition
        is only the implicit ceiling of one PROCESS per Request (Section 4b,
        «The risk this amendment accepts»).
        """
        runner = DeliveryContinuationRunner(self.invoker)
        port = runner.resolve_port(root)
        if isinstance(port, DeliveryOutcome):
            return _from_outcome(port, None)
        lock = acquire_delivery_lock(root)
        if isinstance(lock, Blocked):
            return _from_blocked(lock)
        try:
            return work(runner, port)
        finally:
            lock.release()

    def _locked_native(
        self,
        root: Path,
        work: Callable[[DeliveryContinuationRunner], StepOutcome],
    ) -> StepOutcome:
        """Run a native-only step without resolving a model provider."""
        runner = DeliveryContinuationRunner(self.invoker)
        lock = acquire_delivery_lock(root)
        if isinstance(lock, Blocked):
            return _from_blocked(lock)
        try:
            return work(runner)
        finally:
            lock.release()


def _value_facts(stored: StoredHandover) -> tuple[str, ...]:
    """The ordered values the graph carries, one labelled line each."""
    return tuple(
        f"VALUE-{position}: {json.dumps(value.observation, ensure_ascii=False)}"
        for position, value in enumerate(stored.values, start=1)
    )


def _graph(root: Path) -> StoredHandover | StepOutcome:
    """The persisted graph a per-value step operates on, or why there is none.

    An absent graph is a REFUSAL and not a crash: the orchestrator invoked a
    step before the one that produces its input, and the terminal names that
    step rather than leaving a traceback to be interpreted.
    """
    stored = stored_handover(root)
    if isinstance(stored, Blocked):
        return _from_blocked(stored)
    if stored is None:
        return StepOutcome(
            Disposition.Refusal,
            FailureDetail(
                "HandoverAbsent",
                "no decomposition is recorded in this repository, so there is no "
                "value at any position to work on",
                "decompose one Request first -- pipe it into `des po` on stdin",
            ),
        )
    return stored


def _value_at(stored: StoredHandover, position: int) -> HandoverValue | StepOutcome:
    """The value at a 1-based canonical position, or the refusal that says none is.

    Positions are 1-based and are the ORDER the graph is stored in, which is the
    same order `des state` prints.  A position outside it names the real range
    rather than reporting an empty result, because "there is no value 9" and
    "value 9 carries nothing" are different facts.
    """
    if not 1 <= position <= len(stored.values):
        return StepOutcome(
            Disposition.Refusal,
            FailureDetail(
                "ValueOutOfRange",
                f"this Request carries {len(stored.values)} value(s), numbered 1 "
                f"to {len(stored.values)}, and {position} is outside that range",
                "read `des state --repo-root <root>` for the ordered values, then "
                "invoke this step with one of their positions",
            ),
        )
    return stored.values[position - 1]


def _oracle_red_facts(measured: tuple[dict[str, object], ...]) -> tuple[str, ...]:
    """One line per measured oracle: what was executed and what it answered.

    The whole record is not printed.  A JUnit failure list is a transcript, and
    the terminal's job is to say which oracle, on which axis, with what exit --
    the evidence itself already reached the roles that judge and repair it.

    `diagnostic=` carries the tail `_oracle_diagnosis` already measured off the
    real subprocess's own channels -- NOT a rerun and NOT the raw report: two
    native vectors can share path/verdict/axis/exit (e.g. both merely
    `exit-status-only`) while the tool itself said something entirely
    different, and that distinction is the fact the LLM needs to choose its
    next turn.  It is escaped, never re-executed: `_oracle_diagnosis` already
    flattens its own text, but a subprocess is untrusted output, so any stray
    newline, carriage return or embedded `ORACLE-RED:` token is neutralised
    HERE, at the one place this record crosses into the public terminal, using
    `json.dumps(..., ensure_ascii=True)`: every control character (not just
    CR/LF), every non-ASCII line/paragraph separator (U+2028/U+2029), and every
    backslash is escaped into a single-line, non-executing JSON string
    literal, so a subprocess cannot spoof a second terminal line, a fake
    `LABEL:`, or a raw terminal escape sequence by writing such bytes into a
    channel this record echoes.
    """
    return tuple(
        f"ORACLE-RED: {item.get('path')} verdict={item.get('verdict')} "
        f"axis={item.get('axis')} exit={item.get('exit')} "
        f"diagnostic={json.dumps(str(item.get('diagnostic', '')), ensure_ascii=True)}"
        for item in measured
    )


def _unbound_design(position: int) -> StepOutcome:
    """The one refusal every per-value step owes an unbound value.

    Written once because three steps consume the same bound facts, and a second
    spelling of "this value has no design yet" is a second contract for one
    state.
    """
    return StepOutcome(
        Disposition.Refusal,
        FailureDetail(
            "DesignUnbound",
            "this value carries no bound design facts, so nothing declares its "
            "oracle, its targets or its verification",
            f"bind them first with `des design --repo-root <root> --value {position}`",
        ),
    )


def _prepared(
    runner: DeliveryContinuationRunner,
    root: Path,
    stored: StoredHandover,
) -> list[tuple[str, object]] | StepOutcome:
    """Every value of the Request with its derived facts, or why one is not ready.

    The candidate is WHOLE-REQUEST: Section 4a's shape has every value share the
    single candidate, so none of them is verified unless all of them are. A
    value that is not ready is named by POSITION, with the step that would make
    it ready, rather than reported as a missing set.
    """
    prepared: list[tuple[str, object]] = []
    for position, value in enumerate(stored.values, start=1):
        if value.authority is None:
            return _unbound_design(position)
        design = runner.selected_authority(root, stored, position)
        if isinstance(design, DeliveryOutcome):
            return _from_outcome(design, None, runner.turns_bought, runner.last_role)
        prepared.append((value.observation, design))
    return prepared


def _split_facts(graph: StoredHandover, split: RequestRewrite) -> tuple[str, ...]:
    """All three sets of a rewrite, always, so the split can be corrected.

    ADR-DES-003 §7: the terminal shows both lists. Reporting only what was kept
    would make an archived value indistinguishable from one that never existed,
    and the archived bytes unreachable in practice even though the ref holds
    them.
    """
    positions = {
        value.observation: index for index, value in enumerate(graph.values, 1)
    }
    rows = [
        f"KEPT: VALUE-{positions[observation]} "
        f"{json.dumps(observation, ensure_ascii=False)}"
        for observation in split.kept
    ]
    rows += [
        f"ARCHIVED: {json.dumps(observation, ensure_ascii=False)} -- not in the "
        "new decomposition"
        for observation in split.archived
    ]
    rows += [
        f"NEW: VALUE-{positions[observation]} "
        f"{json.dumps(observation, ensure_ascii=False)}"
        for observation in split.fresh
    ]
    if split.archive is not None:
        rows.append(f"ARCHIVE: {split.archive}")
    return tuple(rows)

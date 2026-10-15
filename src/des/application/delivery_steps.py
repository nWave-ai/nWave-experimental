"""Deterministic document construction, native measurement and persistence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, cast

from des.adapters.driven.config.des_config import DESConfig
from des.adapters.driven.task_invocation.model_envelope import decode_model_run
from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    DeliveryOutcome,
    FailureDetail,
    SelectedValue,
)
from des.application.design_document_producer import (
    DesignAuthorityBinding,
    DesignPublicationWidenings,
    bound_authority_headings,
    bound_value_headings,
    publish_design_document,
)
from des.application.discuss_document_producer import publish_discuss_document
from des.application.distill_document_producer import publish_distill_document
from des.application.evolution_document_producer import publish_evolution_document
from des.application.handover import (
    Blocked,
    BoundDesign,
    HandoverValue,
    ProductAuthority,
    SharedDesign,
    acquire_delivery_lock,
    bind_design_facts,
    bind_shared_design,
    create_constructed_handover,
    design_basis_sha256,
    rewrite_handover,
    shared_design_defects,
    stored_candidate_handover,
    stored_handover,
)
from des.application.operational_document_producer import publish_operational_document
from des.application.verification_workspace import (
    WorkspaceUnavailable,
    acquire_verification_lock,
)
from des.domain.architecture_brief_resolver import (
    target_acceptance_support_conflict,
    target_acceptance_support_conflict_text,
)
from des.domain.delivery_disposition import Disposition
from des.domain.design_document import (
    DesignDocument,
    DesignDocumentInvalid,
    resolve_inheritance,
)
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
from des.ports.driven_ports.task_invocation_port import (
    DesignFacts,
    MalformedModelEnvelope,
    ModelOutcome,
    ModelRun,
    PreNormalizedDesign,
)


if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from des.application.handover import StoredHandover


@dataclass(frozen=True, slots=True)
class StepOutcome:
    """One step's closed outcome, plus the facts and words it carries back.

    `facts` are terminal lines the step measured and the orchestrator reads --
    the values a decomposition produced, a candidate SHA, a captured exit code.
    `diagnostic` contains host-declared role words; neither it nor the role
    identifier proves execution or measures the host's model expenditure.
    """

    disposition: Disposition
    failure: FailureDetail | None = None
    facts: tuple[str, ...] = ()
    diagnostic: str | None = None
    role: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.disposition is Disposition.Success


@dataclass(frozen=True, slots=True, kw_only=True)
class ReplacementModes:
    """Explicit, exclusive bound replacement and unbound recovery."""

    replace_current: bool = False
    replace_unbound: bool = False

    @property
    def conflicting(self) -> bool:
        """Whether incompatible replacement modes were requested."""
        return (
            sum(
                (
                    self.replace_current,
                    self.replace_unbound,
                )
            )
            > 1
        )


#: No replacement and no recovery: construct over what is not yet there.  A
#: module constant rather than a default-argument call, which ruff's B008 refuses.
_NO_REPLACEMENT = ReplacementModes()

#: The repair for a manifest the decoder refused.  The WHY names the first
#: offending field; the grammar is printed by `des design --help`, so the HOW
#: points there instead of restating "a complete manifest", which named no
#: field and no source of the grammar (codex retest 2026-10-01, both cases).
_DESIGN_MANIFEST_HOW = (
    "correct the field named in WHY (the closed manifest grammar is printed "
    "by `des design --help`), then resubmit the whole manifest on stdin"
)


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
    role: str | None = None,
) -> StepOutcome:
    return StepOutcome(outcome.disposition, outcome.failure, (), diagnostic, role)


def _host_result(raw: str, role: str) -> ModelRun | StepOutcome:
    """Decode a declared host observation, never evidence of DES execution."""
    try:
        result = decode_model_run(json.loads(raw)["structured_output"], role_id=role)
    except (
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        MalformedModelEnvelope,
    ) as error:
        return StepOutcome(
            Disposition.Refusal,
            FailureDetail(
                "HostResultMalformed",
                str(error),
                error.how
                if isinstance(error, MalformedModelEnvelope) and error.how is not None
                else "supply the host specialist's complete structured_output JSON",
            ),
        )
    if result.outcome is not ModelOutcome.Accepted:
        return StepOutcome(
            Disposition.Refusal
            if result.outcome is ModelOutcome.Rejected
            else Disposition.Indeterminate,
            FailureDetail(
                "HostRoleResult",
                result.diagnostic,
                "the host selects the owner and any next action from this observation",
            ),
            facts=()
            if result.craft_blocker is None
            else (f"BLOCKED-BY: {result.craft_blocker.value}",),
            diagnostic=result.diagnostic,
        )
    return result


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
        return HandoverValue(
            supplied.observation, supplied.dependencies, None, change=supplied.change
        )
    return replace(
        bound,
        observation=supplied.observation,
        dependencies=supplied.dependencies,
        change=supplied.change,
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


def _inheritance_refusal(defects: tuple[str, ...]) -> StepOutcome:
    manifest = any(
        defect.startswith("DesignInheritanceContradiction") for defect in defects
    )
    why = "\n".join(defects)
    if manifest:
        why += "\nUNRUN: bound-state reference checks (manifest did not decode)"
    return _scope_refusal(
        "InvalidDesignDocument" if manifest else "DesignInheritanceRefused",
        why,
        "correct the named references and resubmit des design --input -",
    )


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
    """Explicit construction and measurement operations; model execution is host-owned."""

    def design_document(
        self,
        root: Path,
        position: int,
        raw: str,
        *,
        modes: ReplacementModes = _NO_REPLACEMENT,
        feature: DocumentScope | str | None = None,
    ) -> StepOutcome:
        """Bind a caller-supplied normalized document without a provider turn."""
        try:
            document = DesignDocument.from_json(raw, value=position)
        except DesignDocumentInvalid as error:
            return StepOutcome(
                Disposition.Refusal,
                FailureDetail(
                    "InvalidDesignDocument",
                    f"{len(error.defects)} diagnostic entries:\n"
                    + "\n".join(error.defects),
                    error.how(_DESIGN_MANIFEST_HOW),
                ),
            )
        lock = acquire_delivery_lock(root)
        if isinstance(lock, Blocked):
            return _from_blocked(lock)
        try:
            stored = _graph(root, repair=modes.replace_current, position=position)
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
            previous_locator = (
                ready.authority
                if isinstance(ready.authority, str)
                else ready.authority.authority_locator
                if ready.authority is not None
                else None
            )
            if previous_locator and previous_locator != authority_locator:
                old = isinstance(ready.authority, (PreNormalizedDesign, str))
                if not (
                    old
                    and modes.replace_current
                    and previous_locator.partition("#")[0] == destination
                ):
                    return _scope_refusal(
                        "DesignAuthorityIdentityMismatch",
                        "the selected scope must retain its bound destination and compiled identity",
                        "keep the bound destination and use --replace-current to rebind old authority",
                    )
            if modes.conflicting:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "InvalidDesignMigration",
                        "DESIGN replacement and recovery modes are exclusive",
                        "choose bound replacement or unbound recovery",
                    ),
                )
            if modes.replace_current and not previous_locator:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "DesignAuthorityIdentityMismatch",
                        "--replace-current requires the selected value's persisted "
                        "DESIGN authority locator",
                        "first bind this value through the closed DESIGN constructor",
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
            resolved = resolve_inheritance(
                stored.shared_design.design if stored.shared_design else None,
                (
                    value.authority
                    for index, value in enumerate(stored.values, 1)
                    if index != position and isinstance(value.authority, DesignFacts)
                ),
                facts,
            )
            if isinstance(resolved, tuple):
                return _inheritance_refusal(resolved)
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
                    replace_unbound=modes.replace_unbound,
                ),
                binding=DesignAuthorityBinding(
                    authority_locator=previous_locator,
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
                    f"SEMANTIC-SHA256: {document.semantic_sha256}",
                    f"DESIGN-FACTS: {document.facts_json(facts)}",
                    "SCHEMA-VERSION: 2",
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
            document = DesignDocument.from_json(raw, shared=True)
        except DesignDocumentInvalid as error:
            return StepOutcome(
                Disposition.Refusal,
                FailureDetail(
                    "InvalidDesignDocument",
                    f"{len(error.defects)} diagnostic entries:\n"
                    + "\n".join(error.defects),
                    error.how(_DESIGN_MANIFEST_HOW),
                ),
            )
        lock = acquire_delivery_lock(root)
        if isinstance(lock, Blocked):
            return _from_blocked(lock)
        try:
            stored = _graph(root, repair=modes.replace_current)
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
                if not (
                    isinstance(bound.design, PreNormalizedDesign)
                    and modes.replace_current
                    and bound.authority_locator.partition("#")[0] == destination
                ):
                    return _scope_refusal(
                        "DesignAuthorityIdentityMismatch",
                        "shared replacement must retain the bound destination and compiled identity",
                        "keep the destination and use --replace-current to rebind old shared authority",
                    )
            if modes.conflicting:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "InvalidDesignMigration",
                        "DESIGN replacement and recovery modes are exclusive",
                        "choose bound replacement or unbound recovery",
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
            defects = shared_design_defects(stored, facts)
            if defects:
                return _inheritance_refusal(defects)
            published = publish_design_document(
                root,
                destination,
                document,
                widenings=DesignPublicationWidenings(
                    allow_untracked_recovery=bound is None or bound.design == facts,
                    replace_current=modes.replace_current,
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
                    error.how(
                        "provide the complete closed v1 OperationalDocumentInput JSON"
                    ),
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

    def discuss_document(  # noqa: PLR0913 - explicit command scope and authority CAS operands
        self,
        root: Path,
        raw: str,
        *,
        project: bool,
        replace_current: bool = False,
        expected_authority_sha256: str | None = None,
        feature: DocumentScope | str | None = None,
    ) -> StepOutcome:
        """Construct the DISCUSS authority, or explicitly correct the current one.

        ``replace_current`` supersedes the owned brief and its ordered graph in
        one turn.  The correction is SELECTIVE: every downstream fact already
        bound to an observation that survives the correction is carried over
        unchanged, and only an observation the supplied graph drops or renames
        loses the facts that were keyed to it.
        """
        if expected_authority_sha256 is not None and not replace_current:
            return StepOutcome(
                Disposition.Refusal,
                FailureDetail(
                    "InvalidDiscussInput",
                    "--expected-authority-sha256 is valid only with --replace-current",
                    "supply --replace-current with --expected-authority-sha256 "
                    "using the current DISCUSS DOCUMENT-SHA256",
                ),
            )
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
                    error.how(DISCUSS_HOW_TO_FIX),
                ),
            )
        lock = acquire_delivery_lock(root)
        if isinstance(lock, Blocked):
            return _from_blocked(lock)
        try:
            stored = stored_handover(root)
            if isinstance(stored, Blocked):
                return _from_blocked(stored)
            persisted_digest = (
                stored.product_authority.sha256
                if stored is not None and stored.product_authority is not None
                else None
            )
            correction_how = (
                "rerun des po or des discuss with the persisted scope, --input - "
                f"--replace-current --expected-authority-sha256 {persisted_digest}"
                if persisted_digest is not None
                else "construct or rebind the unchanged Request through des po or "
                "des discuss --input - with its persisted scope before correcting it"
            )
            if replace_current:
                if expected_authority_sha256 is not None:
                    if stored is None or persisted_digest != expected_authority_sha256:
                        return StepOutcome(
                            Disposition.Refusal,
                            FailureDetail(
                                "DiscussAuthorityIdentityMismatch",
                                f"supplied authority digest {expected_authority_sha256!r} "
                                "does not identify a persisted graph with product authority; "
                                f"persisted digest: {persisted_digest or 'none bound'}",
                                correction_how,
                            ),
                        )
                    defect = DeliveryContinuationRunner.product_authority_defect(
                        root, stored
                    )
                    if defect is not None:
                        return StepOutcome(
                            Disposition.Refusal,
                            FailureDetail(defect.what, defect.why, defect.how),
                        )
                elif stored is None or stored.request != document.request:
                    return StepOutcome(
                        Disposition.Refusal,
                        FailureDetail(
                            "DiscussAuthorityIdentityMismatch",
                            "--replace-current without an expected authority digest "
                            "requires a persisted graph carrying this Request",
                            correction_how,
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
                        (value.observation, value.dependencies, value.change)
                        for value in stored.values
                    )
                    != tuple(
                        (value.observation, value.dependencies, value.change)
                        for value in graph
                    )
                )
            ):
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "DiscussHandoverConflict",
                        "stored and supplied request/value graphs are incompatible; supply --replace-current to correct the persisted graph",
                        correction_how
                        if stored.request != document.request
                        else "resume the stored graph or rerun with --replace-current",
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
            product_authority = ProductAuthority(published.locator, published.digest)
            if stored is not None and (
                (replace_current and (graph != stored.values or scope_changed))
                or stored.product_authority != product_authority
            ):
                rewritten = rewrite_handover(
                    root,
                    stored.raw,
                    document.request,
                    graph if replace_current else stored.values,
                    feature_id=scope,
                    product_authority=product_authority,
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
                    root,
                    document.request,
                    graph,
                    scope,
                    product_authority=product_authority,
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
                    error.how(V2_HOW),
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
            for position, value in enumerate(stored.values, start=1):
                if value.observation not in incoming:
                    continue
                opaque = DeliveryContinuationRunner.design_consumption_defect(
                    stored, position
                )
                if opaque is not None:
                    return _from_blocked(opaque)
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
            conflicts = tuple(
                (position, conflict)
                for position, value in enumerate(stored.values, start=1)
                if value.observation in incoming
                and isinstance(value.authority, DesignFacts)
                and (
                    conflict := target_acceptance_support_conflict(
                        incoming[value.observation].oracle,
                        (target.path for target in value.authority.targets),
                        incoming[value.observation].supports,
                    )
                )
                is not None
            )
            if conflicts:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "TargetAcceptanceSupportConflict",
                        "; ".join(
                            f"value {position}: "
                            + target_acceptance_support_conflict_text(conflict)
                            for position, conflict in conflicts
                        ),
                        "remove each named DESIGN target from that value's "
                        "acceptance_supports and resubmit the DISTILL revision; "
                        "if the oracle truly needs a new fixture, it is "
                        "acceptance-owned and not a DESIGN target",
                    ),
                )
            # Decide every value before any document byte is published, so a
            # refused or failed selection leaves no acceptance brief behind.
            values = tuple(
                _selected(value, incoming[value.observation].revision, stored)
                if value.observation in incoming
                else value
                for value in stored.values
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
        self, root: Path, position: int, raw: str, *, baseline: str | None = None
    ) -> StepOutcome:
        """Record a host author's result and measure its existing public oracle."""
        return self._locked_native(
            root,
            lambda runner: self._oracle(runner, root, position, raw, baseline=baseline),
        )

    def craft(self, root: Path, position: int, raw: str) -> StepOutcome:
        """Measure and record an implementation supplied by the host-selected crafter."""
        return self._locked_native(
            root, lambda runner: self._craft(runner, root, position, raw)
        )

    def prefactoring(self, root: Path, position: int, phase: str) -> StepOutcome:
        """Measure one explicitly selected preservation phase; perform no move."""
        return self._locked_native(
            root, lambda runner: self._prefactoring(runner, root, position, phase)
        )

    def _prefactoring(
        self, runner: DeliveryContinuationRunner, root: Path, position: int, phase: str
    ) -> StepOutcome:
        stored = _graph(root, consuming=True, position=position)
        if isinstance(stored, StepOutcome):
            return stored
        ready = _value_at(stored, position)
        if isinstance(ready, StepOutcome):
            return ready
        if ready.authority is None:
            return _unbound_design(root, (position,))
        design = runner.selected_authority(root, stored, position)
        if isinstance(design, DeliveryOutcome):
            return _from_outcome(design, None)
        measured = runner.measure_prefactoring(
            root, SelectedValue(stored, ready, design), phase
        )
        if isinstance(measured, DeliveryOutcome):
            return _from_outcome(measured, None)
        locator, evidence = measured
        return StepOutcome(
            Disposition.Success,
            facts=(
                f"VALUE-{position}: {json.dumps(ready.observation, ensure_ascii=False)}",
                f"PREFACTORING-PHASE: {phase}",
                "PREFACTORING-OBSERVATION: GREEN basis=exit-status-only",
                f"NATIVE-EVIDENCE: {locator}",
                *(
                    f"PREFACTORING-ARGV: {json.dumps(item.argv)} exit={item.exit_status}"
                    for item in evidence
                ),
            ),
        )

    def verify(self, root: Path, *, fresh: bool = False) -> StepOutcome:
        """Recover an observation, or explicitly measure the declared checks again."""
        return self._locked_native(
            root,
            lambda runner: self._verify(runner, root, fresh=fresh),
            verification=True,
        )

    def reverify_integrated(self, root: Path, candidate: str) -> StepOutcome:
        """Explicitly measure HEAD using a retained, never revived, graph."""
        return self._locked_native(
            root,
            lambda runner: self._reverify_integrated(runner, root, candidate),
            verification=True,
        )

    def integrate(self, root: Path, candidate: str) -> StepOutcome:
        """Apply the explicit candidate identity, compare-and-swap and cleanup operation."""
        return self._locked_native(
            root, lambda runner: self._integrate(runner, root, candidate)
        )

    # ----------------------------------------------------------------- inner

    def _oracle(
        self,
        runner: DeliveryContinuationRunner,
        root: Path,
        position: int,
        raw: str,
        *,
        baseline: str | None = None,
    ) -> StepOutcome:
        stored = _graph(root, consuming=True, position=position)
        if isinstance(stored, StepOutcome):
            return stored
        ready = _value_at(stored, position)
        if isinstance(ready, StepOutcome):
            return ready
        if ready.authority is None:
            return _unbound_design(root, (position,))
        design = runner.selected_authority(root, stored, position)
        if isinstance(design, DeliveryOutcome):
            return _from_outcome(design, None)
        result = _host_result(raw, "nw-acceptance-designer")
        if isinstance(result, StepOutcome):
            return result
        measurement = runner.measure_oracle(
            root,
            SelectedValue(stored, ready, design),
            explicit=baseline,
            request_base=None,
        )
        facts = (
            f"VALUE-{position}: {json.dumps(ready.observation, ensure_ascii=False)}",
            f"ORACLE: {design.acceptance_oracle_locator}",
            *(
                (
                    f"ORACLE-BASELINE: {measurement.baseline[0].sha} "
                    f"source={measurement.baseline[1].value}",
                )
                if measurement.baseline is not None
                else ()
            ),
            *_oracle_red_facts(measurement.measured),
        )
        if measurement.refusal is not None:
            return StepOutcome(
                measurement.refusal.disposition,
                measurement.refusal.failure,
                facts,
                result.diagnostic,
            )
        return StepOutcome(
            Disposition.Success, facts=facts, diagnostic=result.diagnostic
        )

    def _craft(
        self, runner: DeliveryContinuationRunner, root: Path, position: int, raw: str
    ) -> StepOutcome:
        stored = _graph(root, consuming=True, position=position)
        if isinstance(stored, StepOutcome):
            return stored
        ready = _value_at(stored, position)
        if isinstance(ready, StepOutcome):
            return ready
        if ready.authority is None:
            return _unbound_design(root, (position,))
        design = runner.selected_authority(root, stored, position)
        if isinstance(design, DeliveryOutcome):
            return _from_outcome(design, None)
        role = (
            "nw-functional-software-crafter"
            if design.paradigm == "functional"
            else "nw-software-crafter"
        )
        result = _host_result(raw, role)
        if isinstance(result, StepOutcome):
            return result
        refused = runner.record_craft(root, SelectedValue(stored, ready, design))
        if refused is not None:
            return _from_outcome(refused, result.diagnostic)
        return StepOutcome(
            Disposition.Success,
            facts=(
                f"VALUE-{position}: {json.dumps(ready.observation, ensure_ascii=False)}",
                "TARGETS: " + ", ".join(path for path, _ in design.target_decisions),
                "WITNESS: the recorded public oracle observed GREEN on the host-supplied implementation",
            ),
            diagnostic=result.diagnostic,
        )

    def _reverify_integrated(
        self, runner: DeliveryContinuationRunner, root: Path, candidate: str
    ) -> StepOutcome:
        stored = stored_candidate_handover(root, candidate)
        if isinstance(stored, Blocked):
            return _from_blocked(stored)
        if stored is None:
            return StepOutcome(
                Disposition.Refusal,
                FailureDetail(
                    "IntegratedCandidateUnknown",
                    f"no retained candidate handover for {candidate} in {root}",
                    "pass the INTEGRATED sha printed by des integrate in this worktree; "
                    f"when a Request is active use des verify --repo-root {root}",
                ),
            )
        head = runner.integrated_head(root, candidate)
        if isinstance(head, DeliveryOutcome):
            return _from_outcome(head, None)
        prepared = _prepared(runner, root, stored)
        if isinstance(prepared, StepOutcome):
            return StepOutcome(
                Disposition.Indeterminate,
                FailureDetail(
                    "IntegratedCandidateUnobservable",
                    f"{prepared.failure.what}: {prepared.failure.why}",
                    prepared.failure.how,
                ),
            )
        verified = runner.reverify_integrated(
            root, stored, prepared, candidate, head=head
        )
        maintenance = (
            ()
            if runner.workspace_maintenance is None
            else runner.workspace_maintenance.report
        )
        if isinstance(verified, DeliveryOutcome):
            return StepOutcome(
                verified.disposition, verified.failure, facts=maintenance
            )
        head, evidence = verified
        locator = runner.native_evidence_locator
        digest = runner.native_evidence_sha256
        if locator is None or digest is None:
            return StepOutcome(
                Disposition.Indeterminate,
                FailureDetail(
                    "NativeEvidenceUnretained",
                    f"HEAD {head} completed native verification but its observation could not be persisted",
                    "restore write access to .nwave/des/logs/native and verify again",
                ),
            )
        return StepOutcome(
            Disposition.Success,
            facts=(
                f"INTEGRATED-CANDIDATE: {candidate}",
                f"REVERIFIED: {head}",
                f"NATIVE-EVIDENCE: {locator}",
                f"NATIVE-EVIDENCE-SHA256: {digest}",
                *(
                    f"NATIVE: exit={item.exit_status} origin={item.origin} "
                    f"argv={' '.join(item.argv)}"
                    for item in evidence
                ),
                *maintenance,
            ),
        )

    def _verify(
        self,
        runner: DeliveryContinuationRunner,
        root: Path,
        *,
        fresh: bool = False,
    ) -> StepOutcome:
        stored = _graph(root, consuming=True)
        if isinstance(stored, StepOutcome):
            return stored
        recorded = runner.verified_candidate(root, stored)
        if fresh:
            invalidated = runner.invalidate_verification(root, stored)
            if invalidated is not None:
                return _from_outcome(invalidated, None)
        prepared = _prepared(runner, root, stored)
        if isinstance(prepared, StepOutcome):
            return prepared
        if recorded is not None and not fresh:
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
                    "inspect .nwave/des/logs/native; use des verify --fresh to measure again",
                ),
            )
        verified = runner.verify_request(
            root, stored, prepared, candidate=recorded if fresh else None
        )
        maintenance = (
            ()
            if runner.workspace_maintenance is None
            else runner.workspace_maintenance.report
        )
        if isinstance(verified, DeliveryOutcome):
            return StepOutcome(
                verified.disposition,
                verified.failure,
                facts=(f"RADIUS: {runner.radius}", *maintenance),
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
        if not runner.persist_candidate_observations(root, candidate, stored, prepared):
            return StepOutcome(
                Disposition.Indeterminate,
                FailureDetail(
                    "NativeRadiusUnretained",
                    f"candidate {candidate} native radius and oracle witness "
                    "snapshot could not be persisted",
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
                *maintenance,
            ),
        )

    def _integrate(
        self, runner: DeliveryContinuationRunner, root: Path, candidate: str
    ) -> StepOutcome:
        already = runner.destination_is(root, candidate)
        stored = _graph(root)
        if isinstance(stored, StepOutcome):
            if (
                already
                and stored.failure is not None
                and stored.failure.what == "HandoverAbsent"
            ):
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
                        "nothing is owed for this Request; construct the next one "
                        "with a closed DISCUSS manifest using `des po --input -` and an explicit scope",
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
                        "; the selected graph, authority, or owned bytes no longer "
                        "match the recorded candidate measurement"
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
            return _from_outcome(integrated, None)
        return StepOutcome(
            Disposition.Success,
            facts=(
                f"INTEGRATED: {candidate}",
                "CLEANUP: complete",
            ),
        )

    def _locked_native(
        self,
        root: Path,
        work: Callable[[DeliveryContinuationRunner], StepOutcome],
        *,
        verification: bool = False,
    ) -> StepOutcome:
        """Run a native-only step without resolving a model provider."""
        runner = DeliveryContinuationRunner()
        lock = acquire_delivery_lock(root)
        if isinstance(lock, Blocked):
            return _from_blocked(lock)
        verification_lock = None
        try:
            if verification:
                try:
                    verification_lock = acquire_verification_lock(root)
                except (OSError, WorkspaceUnavailable) as error:
                    return _from_blocked(
                        Blocked(
                            "VerificationWorkspaceUnavailable",
                            str(error),
                            "restore the canonical Git repository and its verification lease",
                        )
                    )
                if isinstance(verification_lock, Blocked):
                    return _from_blocked(verification_lock)
                runner.verification_lease_held = True
            return work(runner)
        finally:
            if verification_lock is not None and not isinstance(
                verification_lock, Blocked
            ):
                verification_lock.release()
            lock.release()


def _value_facts(stored: StoredHandover) -> tuple[str, ...]:
    """The ordered values the graph carries, one labelled line each."""
    return tuple(
        f"VALUE-{position}: {json.dumps(value.observation, ensure_ascii=False)}"
        for position, value in enumerate(stored.values, start=1)
    )


def _graph(
    root: Path,
    *,
    consuming: bool = False,
    position: int | None = None,
    repair: bool = False,
) -> StoredHandover | StepOutcome:
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
                "construct host product facts with `des po --input -` and an explicit scope",
            ),
        )
    if consuming:
        defect = DeliveryContinuationRunner.design_consumption_defect(stored, position)
        if defect is not None:
            return _from_blocked(defect)
    if repair:
        authority = (
            stored.shared_design.design
            if position is None and stored.shared_design
            else stored.values[position - 1].authority
            if position is not None and 1 <= position <= len(stored.values)
            else None
        )
        if isinstance(authority, (str, PreNormalizedDesign)):
            return stored
    defect = DeliveryContinuationRunner.product_authority_defect(root, stored)
    if defect is not None:
        return _from_blocked(defect)
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
        + (
            f" native-evidence={item['native_evidence_locator']}"
            if item.get("native_evidence_locator")
            else ""
        )
        + f" diagnostic={json.dumps(str(item.get('diagnostic', '')), ensure_ascii=True)}"
        for item in measured
    )


def _unbound_design(root: Path, positions: tuple[int, ...]) -> StepOutcome:
    """The one refusal every step owes the unbound values it needs.

    Written once because four steps consume the same bound facts, and a second
    spelling of "this value has no design yet" is a second contract for one
    state.  Every unbound position is named at once, each with its own DESIGN
    invocation: a whole-Request step that named only the first made the host
    discover the rest one refusal at a time (codex retest 2026-10-01,
    durable-reservations: values 2, 3 and 4 were all unbound at `des verify`).
    """
    named = ", ".join(str(position) for position in positions)
    return StepOutcome(
        Disposition.Refusal,
        FailureDetail(
            "DesignUnbound",
            f"value(s) {named} carry no bound design facts, so nothing declares "
            "their oracle, targets or verification",
            "submit a closed DESIGN manifest for each: "
            + "; ".join(
                f"`des design --repo-root {root} --value {position} --input -`"
                for position in positions
            ),
        ),
    )


def _prepared(
    runner: DeliveryContinuationRunner,
    root: Path,
    stored: StoredHandover,
) -> list[tuple[str, object]] | StepOutcome:
    """Every value of the Request with its derived facts, or why one is not ready.

    The candidate is WHOLE-REQUEST: Section 4a's shape has every value share the
    single candidate, so none of them is verified unless all of them are. The
    first value that is not ready decides the refusal, in graph order; when it
    is unbound, every later unbound value is named with it, by POSITION, each
    with the step that would make it ready.
    """
    prepared: list[tuple[str, object]] = []
    for position, value in enumerate(stored.values, start=1):
        if value.authority is None:
            return _unbound_design(
                root,
                tuple(
                    later
                    for later, item in enumerate(stored.values, start=1)
                    if later >= position and item.authority is None
                ),
            )
        design = runner.selected_authority(root, stored, position)
        if isinstance(design, DeliveryOutcome):
            return _from_outcome(design, None)
        prepared.append((value.observation, design))
    return prepared

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

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.adapters.driven.config.des_config import DESConfig
from des.application.delivery_continuation import (
    AcceptanceFinding,
    DeliveryContinuationRunner,
    DeliveryOutcome,
    FailureDetail,
    RequestRewrite,
)
from des.application.design_document_producer import publish_design_document
from des.application.discuss_document_producer import publish_discuss_document
from des.application.distill_document_producer import publish_distill_document
from des.application.evolution_document_producer import publish_evolution_document
from des.application.handover import (
    Blocked,
    HandoverValue,
    acquire_delivery_lock,
    bind_design_facts,
    create_constructed_handover,
    stored_handover,
)
from des.application.operational_document_producer import publish_operational_document
from des.domain.algebraic_modelling_tools import algebra_line
from des.domain.delivery_disposition import Disposition
from des.domain.design_document import DesignDocument, DesignDocumentInvalid
from des.domain.discuss_document import DiscussDocument, DiscussDocumentInvalid
from des.domain.distill_document import DistillDocument, DistillDocumentInvalid
from des.domain.evolution_document import EvolutionDocument, EvolutionDocumentInvalid
from des.domain.operational_document import (
    OperationalDocument,
    OperationalDocumentInvalid,
)
from des.domain.verification_verdict import ADMITTED


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


@dataclass(slots=True)
class DeliverySteps:
    """Each method is ONE step: it locks, runs one turn, and returns."""

    invoker: TaskInvocationPort | None = None

    def decompose(
        self,
        root: Path,
        request: str,
        finding: str | None = None,
        operational_facts: dict[str, object] | None = None,
    ) -> StepOutcome:
        """One Product Owner turn over `request`, recorded as the owned graph.

        IDEMPOTENT against the handover, which is what makes a re-invocation
        after a crash a resume rather than a second paid turn: a graph that
        already exists for this exact Request is REPORTED, never re-elicited and
        never overwritten.  A graph that exists for a DIFFERENT Request is
        refused LOUD with both moves named, and this step deletes nothing --
        the bytes on disk are somebody's unfinished delivery.
        """
        return self._locked(
            root,
            lambda runner, port: self._decompose(
                runner, port, root, request, finding, operational_facts
            ),
        )

    def design(
        self, root: Path, position: int, finding: str | None = None
    ) -> StepOutcome:
        """One architect turn for the value at `position`, derived and bound.

        REPEATABLE, which is what makes a correction the same step rather than a
        second one.  Called again over a bound value with `finding`, the turn
        receives the CURRENT typed facts beside the finding and what it returns
        REPLACES them.  Which finding goes back to which role, and whether to
        spend a turn on it at all, is the orchestrator's decision.
        """
        return self._locked(
            root,
            lambda runner, port: self._design(runner, port, root, position, finding),
        )

    def design_document(self, root: Path, position: int, raw: str) -> StepOutcome:
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
            destination = DESConfig.design_document_destination(root)
            if destination is None:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "DesignDestinationMissing",
                        "no effective documents.design.destination is configured",
                        "configure documents.design.destination in repository or global config",
                    ),
                )
            allow_untracked_recovery = (
                ready.authority is None or ready.authority == document.facts
            )
            published = publish_design_document(
                root,
                destination,
                document,
                allow_untracked_recovery=allow_untracked_recovery,
            )
            if isinstance(published, Blocked):
                return _from_blocked(published)
            bound = bind_design_facts(
                root,
                stored,
                position,
                document.facts,
                authority_persisted=published.authority_persisted,
            )
            if isinstance(bound, Blocked):
                return _from_blocked(bound)
            return StepOutcome(
                Disposition.Success,
                facts=(
                    f"DOCUMENT: {published.locator}",
                    f"DOCUMENT-SHA256: {published.digest}",
                    f"DESIGN-FACTS: {document.facts_json()}",
                ),
            )
        finally:
            lock.release()

    def operational_document(self, root: Path, raw: str) -> StepOutcome:
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
        destination = DESConfig.operational_document_destination(root)
        if destination is None:
            return StepOutcome(
                Disposition.Refusal,
                FailureDetail(
                    "OperationalDestinationMissing",
                    "no effective documents.devops.destination is configured",
                    "configure documents.devops.destination",
                ),
            )
        lock = acquire_delivery_lock(root)
        if isinstance(lock, Blocked):
            return _from_blocked(lock)
        try:
            published = publish_operational_document(root, destination, document)
            if isinstance(published, Blocked):
                return _from_blocked(published)
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

    def discuss_document(self, root: Path, raw: str) -> StepOutcome:
        try:
            document = DiscussDocument.from_json(raw)
        except DiscussDocumentInvalid as error:
            return StepOutcome(
                Disposition.Refusal,
                FailureDetail(
                    "InvalidDiscussDocument",
                    str(error),
                    "provide the complete closed v1 DISCUSS JSON manifest",
                ),
            )
        lock = acquire_delivery_lock(root)
        if isinstance(lock, Blocked):
            return _from_blocked(lock)
        try:
            stored = stored_handover(root)
            if isinstance(stored, Blocked):
                return _from_blocked(stored)
            graph = tuple(
                HandoverValue(value.observation, value.dependencies, None)
                for value in document.values
            )
            if stored is not None and (
                stored.request != document.request
                or tuple(
                    (value.observation, value.dependencies) for value in stored.values
                )
                != tuple((value.observation, value.dependencies) for value in graph)
            ):
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "DiscussHandoverConflict",
                        "stored and supplied request/value graphs are incompatible; replacement or supersession is not implemented here",
                        "resume the stored graph or use an explicit future replacement protocol",
                    ),
                )
            published = publish_discuss_document(
                root, DESConfig.discuss_document_destination(root), document
            )
            if isinstance(published, Blocked):
                return _from_blocked(published)
            if stored is None:
                created = create_constructed_handover(root, document.request, graph)
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

    def distill_document(self, root: Path, raw: str) -> StepOutcome:
        try:
            document = DistillDocument.from_json(raw)
        except DistillDocumentInvalid as error:
            return StepOutcome(
                Disposition.Refusal,
                FailureDetail(
                    "InvalidDistillDocument",
                    str(error),
                    "provide the complete closed v1 DISTILL JSON manifest",
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
                existing = (
                    value.acceptance,
                    value.acceptance_oracle,
                    value.acceptance_supports,
                )
                proposed = (supplied.obligations, supplied.oracle, supplied.supports)
                if (
                    value.acceptance
                    or value.acceptance_oracle is not None
                    or value.acceptance_supports
                ) and existing != proposed:
                    return StepOutcome(
                        Disposition.Refusal,
                        FailureDetail(
                            "DistillHandoverConflict",
                            "stored acceptance facts differ from the supplied facts",
                            "resume with the same acceptance facts",
                        ),
                    )
            published = publish_distill_document(
                root,
                DESConfig.distill_document_destination(root),
                document,
                stored.request,
            )
            if isinstance(published, Blocked):
                return _from_blocked(published)
            values = tuple(
                HandoverValue(
                    value.observation,
                    value.dependencies,
                    value.authority,
                    incoming[value.observation].obligations
                    if value.observation in incoming
                    else value.acceptance,
                    incoming[value.observation].oracle
                    if value.observation in incoming
                    else value.acceptance_oracle,
                    incoming[value.observation].supports
                    if value.observation in incoming
                    else value.acceptance_supports,
                )
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
        """One whole-Request candidate, verified natively, reviewed and judged."""
        return self._locked(root, lambda runner, port: self._verify(runner, port, root))

    def integrate(
        self, root: Path, candidate: str, on_my_evidence: str | None = None
    ) -> StepOutcome:
        """Compare-and-swap one candidate in, reconcile, and close the graph.

        `on_my_evidence` is the orchestrator's own reason for integrating a
        candidate the judge did not admit. Whether that evidence is enough is a
        SEMANTIC decision, and ADR-DES-003 leaves semantic decisions to the
        model: this software measures, records and enacts. What it does keep is
        the trace -- the decision is written down with the verdict it went over.
        """
        return self._locked(
            root,
            lambda runner, _port: self._integrate(
                runner, root, candidate, on_my_evidence
            ),
        )

    def devops(
        self, root: Path, request: str, authority: str, section: str
    ) -> StepOutcome:
        """One OPTIONAL platform-architect turn, upstream of any decomposition.

        It is refused once a Request is already decomposed. Constraints are
        durable authority the whole run is BOUND to, so writing them after the
        graph exists would retroactively change what every earlier turn was
        measured against -- the same reason `AuthorityDrift` refuses a designer
        that rewrites an approved section.
        """
        return self._locked(
            root,
            lambda runner, port: self._devops(
                runner, port, root, request, authority, section
            ),
        )

    # ----------------------------------------------------------------- inner

    def _decompose(
        self,
        runner: DeliveryContinuationRunner,
        port: TaskInvocationPort,
        root: Path,
        request: str,
        finding: str | None = None,
        operational_facts: dict[str, object] | None = None,
    ) -> StepOutcome:
        stored = stored_handover(root)
        if isinstance(stored, Blocked):
            return _from_blocked(stored)
        if stored is not None and stored.request == request and finding is None:
            # L1: the same Request over the graph it produced is a resume.
            return StepOutcome(Disposition.Success, facts=_value_facts(stored))
        if stored is not None:
            # ADR-DES-003 §7: a Request that differs is not a mismatch to
            # refuse. It is a REWRITE, and the six hand deletions of the
            # handover on 2026-09-05/06 are what it replaces.
            rewritten = runner.rewrite_request(
                root, port, stored, request, finding=finding
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
        decomposed = runner.decompose(root, port, request, operational_facts)
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
        position: int,
        finding: str | None,
    ) -> StepOutcome:
        stored = _graph(root)
        if isinstance(stored, StepOutcome):
            return stored
        ready = _value_at(stored, position)
        if isinstance(ready, StepOutcome):
            return ready
        if finding is None and ready.authority is not None:
            # L1 (ADR-DES-003 §2): the second call over a bound value succeeds,
            # changes nothing and costs nothing. Without this it re-bought the
            # architect and SILENTLY REPLACED the bound facts, so a retry after
            # a lost terminal was a paid overwrite. Re-binding is spelled
            # `--finding -` and nothing else.
            facts = runner.derive_authority(root, ready.authority)
            if isinstance(facts, DeliveryOutcome):
                return _from_outcome(facts, None)
            return StepOutcome(
                Disposition.Success,
                facts=(
                    f"VALUE-{position}: "
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
                    f"`des design --repo-root <root> --value {position} "
                    "--finding -`",
                ),
            )
        designed = runner.design_value(root, port, stored, ready, finding=finding)
        diagnostic = runner.last_diagnostic
        if isinstance(designed, DeliveryOutcome):
            return _from_outcome(
                designed, diagnostic, runner.turns_bought, runner.last_role
            )
        _, facts = designed
        unchanged = (
            ("UNCHANGED: the accepted correction repeated the bound typed facts",)
            if runner.design_unchanged
            else ()
        )
        return StepOutcome(
            Disposition.Success,
            facts=(
                f"VALUE-{position}: {json.dumps(ready.observation, ensure_ascii=False)}",
                f"PARADIGM: {facts.paradigm}",
                f"ORACLE: {facts.acceptance_oracle_locator}",
                "TARGETS: "
                + ", ".join(
                    f"{path} ({decision})" for path, decision in facts.target_decisions
                ),
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
        design = runner.derive_authority(root, ready.authority)
        if isinstance(design, DeliveryOutcome):
            return _from_outcome(design, None, runner.turns_bought, runner.last_role)
        if finding is None and runner.oracle_turn_complete(root, stored, ready, design):
            return StepOutcome(
                Disposition.Success,
                facts=(
                    f"VALUE-{position}: "
                    f"{json.dumps(ready.observation, ensure_ascii=False)}",
                    f"ORACLE: {design.acceptance_oracle_locator}",
                    "RECORDED: this value's approved oracle turn is already a "
                    "recorded fact over these exact bytes, so no turn was bought",
                ),
            )
        measurement = runner.oracle_value(
            root, port, stored, ready, design, finding=finding
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
        design = runner.derive_authority(root, ready.authority)
        if isinstance(design, DeliveryOutcome):
            return _from_outcome(design, None, runner.turns_bought, runner.last_role)
        from dataclasses import replace

        if ready.acceptance:
            # A present DISTILL projection owns every field, including an
            # explicitly empty support tuple.
            oracle = ready.acceptance_oracle
            assert oracle is not None
            design = replace(
                design,
                acceptance_obligations=ready.acceptance,
                acceptance_oracle_locator=oracle,
                acceptance_paths=(
                    oracle.partition("::")[0],
                    *ready.acceptance_supports,
                ),
            )
        if runner.craft_turn_complete(root, stored, ready, design):
            return StepOutcome(
                Disposition.Success,
                facts=(
                    f"VALUE-{position}: "
                    f"{json.dumps(ready.observation, ensure_ascii=False)}",
                    "RECORDED: this value's craft turn is already a recorded fact "
                    "over its mutable targets, so no turn was bought",
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
        port: TaskInvocationPort,
        root: Path,
    ) -> StepOutcome:
        stored = _graph(root)
        if isinstance(stored, StepOutcome):
            return stored
        prepared = _prepared(runner, root, stored)
        if isinstance(prepared, StepOutcome):
            return prepared
        recorded = runner.verified_candidate(root, stored)
        if recorded is not None and runner.verified_verdict(root, stored) == ADMITTED:
            # L1: the candidate is built, reviewed and examined. Rebuilding it
            # would re-buy a whole-diff review and a source-blind judgement to
            # reach the state it is already in.
            return StepOutcome(
                Disposition.Success,
                facts=(
                    f"CANDIDATE: {recorded}",
                    "RECORDED: this candidate is already verified and examined "
                    "over these bytes, so no turn was bought",
                ),
            )
        verified = runner.verify_request(root, port, stored, prepared)
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
        runner.record_verified_candidate(root, stored, candidate, ADMITTED)
        return StepOutcome(
            Disposition.Success,
            facts=(
                f"CANDIDATE: {candidate}",
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
        verified = runner.verified_candidate(root, stored)
        if verified != candidate:
            return StepOutcome(
                Disposition.Refusal,
                FailureDetail(
                    "CandidateUnverified",
                    f"no verification record covers {candidate}"
                    + (
                        f"; the recorded candidate is {verified}"
                        if verified is not None
                        else " and none is recorded for this Request"
                    ),
                    "verify it first with `des verify --repo-root <root>`, then "
                    "integrate the CANDIDATE that step printed",
                ),
            )
        verdict = runner.verified_verdict(root, stored)
        if verdict != ADMITTED:
            # NOT a sequence refusal: the state admits the step, and what is
            # missing is a DECISION only the orchestrator can take. So the
            # refusal names the form that takes it instead of sending the reader
            # back to a step that would re-buy two judgements to hear the same
            # word again.
            if on_my_evidence is None:
                return StepOutcome(
                    Disposition.Refusal,
                    FailureDetail(
                        "CandidateNotAdmitted",
                        f"the judge answered {verdict or 'nothing readable'} on "
                        f"{candidate}, and integrating over that is your "
                        "decision to take, not this software's",
                        "answer the finding at the step that owns it, or take "
                        "the decision: `des integrate --repo-root <root> "
                        f"--candidate {candidate} --on-my-evidence -` with your "
                        "reason on stdin",
                    ),
                )
            unrecorded = runner.record_integration_decision(
                root, stored, candidate, verdict or "unreadable", on_my_evidence
            )
            if unrecorded is not None:
                return _from_outcome(
                    unrecorded, None, runner.turns_bought, runner.last_role
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
                *(
                    ()
                    if on_my_evidence is None or verdict == ADMITTED
                    else (f"DECIDED-BY: orchestrator over a {verdict} judgement",)
                ),
            ),
        )

    def _devops(
        self,
        runner: DeliveryContinuationRunner,
        port: TaskInvocationPort,
        root: Path,
        request: str,
        authority: str,
        section: str,
    ) -> StepOutcome:
        existing = stored_handover(root)
        if isinstance(existing, Blocked):
            return _from_blocked(existing)
        # An admissible order, so it is MEASURED and not refused (ADR-DES-003
        # §2.5). The refusal it replaces claimed the content class on an
        # argument -- «it would change what earlier turns were bound to» -- with
        # no measured incident behind it; the count is the fact the orchestrator
        # actually needs, because those values were decomposed without these
        # constraints in front of the Product Owner.
        decomposed_before = 0 if existing is None else len(existing.values)
        locator = runner.devops_constraints(root, port, request, authority, section)
        diagnostic = runner.last_diagnostic
        if isinstance(locator, DeliveryOutcome):
            return _from_outcome(
                locator, diagnostic, runner.turns_bought, runner.last_role
            )
        facts = [f"CONSTRAINTS: {locator}"]
        if decomposed_before:
            facts.append(f"DECOMPOSED-BEFORE: {decomposed_before}")
        return StepOutcome(
            Disposition.Success,
            facts=tuple(facts),
            diagnostic=diagnostic,
            turns_bought=runner.turns_bought,
            role=runner.last_role,
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
    """
    return tuple(
        f"ORACLE-RED: {item.get('path')} verdict={item.get('verdict')} "
        f"axis={item.get('axis')} exit={item.get('exit')}"
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
        design = runner.derive_authority(root, value.authority)
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

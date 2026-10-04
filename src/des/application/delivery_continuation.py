"""Deterministic native evidence, candidate construction and Git integration."""

from __future__ import annotations

import contextlib
import errno
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, ClassVar
from xml.etree import ElementTree

from des.adapters.driven.codefact.code_fact_chain import CodeFactChain
from des.adapters.driven.config.workspace_paths import (
    CANDIDATE_RECEIPT,
    WorkspacePaths,
    resolve_workspace_paths,
)
from des.adapters.driven.git.git_observation import (
    GitObservation,
    declared_child_environment,
    observe_bytes,
    observe_text,
)
from des.application.candidate_radius import INDETERMINATE, candidate_radius
from des.application.commit_message_attribution import attribute_commit_message
from des.application.handover import (
    Blocked,
    HandoverValue,
    StoredHandover,
    design_basis_sha256,
    design_facts_defect,
    finalize_handover,
    handover_path,
    read_handover,
    retain_candidate_handover,
    stored_candidate_handover,
)
from des.application.head_advance import AdvanceRefusal, HeadAdvance
from des.application.verification_maintenance import (
    WorkspaceMaintenance,
    workspace_maintenance,
)
from des.application.verification_workspace import (
    CandidateSourceChanged,
    VerificationWorkspace,
)
from des.domain.architecture_brief_resolver import (
    canonical_paradigm,
    extract_acceptance_support_locators,
    extract_declared_oracle_verification_indices,
    extract_declared_paradigms,
    extract_declared_target_table,
    extract_declared_verification_commands,
    extract_obligations,
    extract_oracle_citations,
    is_repository_relative_whole_file_locator,
    target_acceptance_support_conflict,
    target_acceptance_support_conflict_text,
)
from des.domain.delivery_disposition import Disposition
from des.domain.distill_document import selected_revision_sha256
from des.domain.exercised_modules import (
    NOT_APPLICABLE,
    ExercisedModules,
    exercised_modules,
    invokes_pytest,
)
from des.domain.feature_documents import FeatureDocumentsInvalid
from des.domain.integration_commit_message import (
    CommitMessageRule,
    IntegrationFacts,
    compose_integration_message,
)
from des.domain.repository_format_contract import (
    FormatContract,
    declared_format_contract,
)
from des.domain.request_stimulus import (
    declared_test_paths,
    path_under_test_paths,
    touches_test_paths,
)
from des.domain.turn_record_ref import (
    CRAFT_TURN,
    ORACLE_TURN,
    ORACLE_WITNESS_TURN,
    VALUE_TURN_ROLES,
    VERIFY_OUTCOME_TURN,
    VERIFY_TURN,
    archive_ref,
    turn_ref,
    verify_upstream_ref,
)
from des.domain.verification_authority_resolver import (
    ResolvedAuthoritySection,
    authority_section_sha256,
    resolve_authority_section,
)
from des.ports.driven_ports.task_invocation_port import (
    ApplicableADR,
    ApplicableAgreementAnalysis,
    ApplicableArchitecturalTests,
    ApplicableContractTests,
    ApplicableImpactClosure,
    ApplicablePrefactoring,
    DefectOwner,
    DesignFacts,
    NotApplicable,
    PublicOracle,
    ReuseAnalysis,
    UnassessedDesignDecision,
)
from des.runtime.spawn import (
    SpawnQuiescenceError,
    SpawnRefusal,
    classify_spawn_refusal,
    resolve_executable,
    spawn,
)


if TYPE_CHECKING:
    from collections.abc import Callable

    from des.domain.distill_document import AcceptanceObligation


# Complete constructor replacement preserves the Request and historical evidence.
_DESIGN_FACTS_REPAIR = (
    "supply complete typed DESIGN facts; for an already-bound value invoke "
    "des design --repo-root ROOT --value N --replace-current --input - "
    "with the complete current manifest, preserving the existing heading and graph"
)


#: The turn-record namespace and its two roles now have a SECOND reader -- the
#: read-only state projection -- so the grammar is SSOT in
#: `des.domain.turn_record_ref` and these are its local spellings.
#: The subject grammar of the verify judgement record. A constant prefix, so a
#: reader that finds some other commit under the ref answers "unknown" rather
#: than reading an arbitrary subject line as a verdict.
_VERDICT_SUBJECT = "nwave verify: "
#: The subject of an oracle witness record; its body is the JSON history.
_WITNESS_SUBJECT = "nwave witness: oracle"

_ORACLE_TURN = ORACLE_TURN
_CRAFT_TURN = CRAFT_TURN


@dataclass(frozen=True, slots=True)
class FailureDetail:
    what: str
    why: str
    how: str


@dataclass(frozen=True, slots=True)
class SliceOutcome:
    observation: str
    disposition: Disposition
    failure: FailureDetail | None = None
    integrated_sha: str | None = None
    cleanup_complete: bool = False


@dataclass(frozen=True, slots=True)
class DeliveryOutcome:
    disposition: Disposition
    failure: FailureDetail | None = None
    integrated_sha: str | None = None
    cleanup_complete: bool = False
    slices: tuple[SliceOutcome, ...] = ()


#: The design's own declared native verification vectors.
DECLARED_ORIGIN = "declared"

#: The exercise measure of an execution no session report reached: the default
#: for a record built outside the execution loop, and the honest answer for a
#: command that starts no pytest session at all.
UNEXERCISED = ExercisedModules(NOT_APPLICABLE, None, None)


@dataclass(frozen=True, slots=True)
class NativeEvidence:
    """One native execution, plus the facts that say what it observed.

    `origin` records the supplied provenance of the vector.  The current public
    verification path executes design-declared vectors and records that fact;
    the field remains evidence metadata rather than a second execution path.

    `touches_test_paths` is a MEASUREMENT of the argv against the subject's
    declared test paths, never a verdict.  Whether a promise about the product
    verified only by such commands counts as observed on the product is the
    reader's decision (`boundary:software-measures-model-decides`).

    `exercised` is the SECOND half of that same question, and the half the flag
    cannot answer: which of the subject's product files the execution actually
    imported.  `touches_test_paths` is binary over the argv's paths, so it is
    true for every pytest argv ever written -- it caught run 24, whose declared
    verification drove a stand-in under the test tree, and it rejected run 34,
    whose oracle drove the product from a path of the same shape.  The two
    differ in what the session loaded, never in the argv, so the argv cannot
    tell them apart.  Import metadata supplements the candidate-bound argv,
    exit, stdout, stderr, and installed observations.  Its absence means
    unmeasured, not that the product was unexercised, and cannot automatically
    pass or fail a candidate.  Both are measurements; neither is a verdict.

    `exit_status` is None for a stimulus the runner could not complete, and
    `stderr` then carries the kernel or timeout diagnostic.  Null rather than
    0, because a zero would read as a successful observation of an incomplete
    command (GDP-6). `incomplete` makes that state explicit for a durable record
    that contains earlier commands which did execute.

    `duration_seconds`, `cwd`, and `declared_environment` describe the one
    command invocation.  They are captured before the spawn (apart from the
    elapsed duration), including for a launch refusal or timeout.  The
    environment is a closed nonsecret projection, including native toolchain
    selections; absent invocation context remains unknown.
    """

    argv: tuple[str, ...]
    exit_status: int | None
    stdout: str
    stderr: str
    origin: str = DECLARED_ORIGIN
    touches_test_paths: bool = False
    exercised: ExercisedModules = UNEXERCISED
    incomplete: bool = False
    incomplete_what: str | None = None
    incomplete_why: str | None = None
    incomplete_how: str | None = None
    duration_seconds: float | None = None
    cwd: str | None = None
    declared_environment: tuple[tuple[str, str], ...] | None = None
    executable: str | None = None


@dataclass(frozen=True, slots=True)
class OracleRedRefusal:
    """One EXECUTED oracle set that is not RED, before any craft turn is paid.

    Two texts, because they answer two different readers.  ``finding`` is the
    verbatim execution -- argv, exit status, both captured channels -- and it
    travels to the acceptance author, who owns the oracle and can act on
    nothing else.  ``terminal`` is the runner's own outcome, whose WHY names
    the file, the verdict and the excerpt an operator reads first.  Collapsing
    them would either bury the operator under a whole pytest transcript or send
    the author a judgement instead of the output.
    """

    finding: str
    terminal: DeliveryOutcome


@dataclass(frozen=True, slots=True)
class OracleExecution:
    """Every authored oracle's MEASURED red, and the refusal if one is not red.

    The two travel together because they come from ONE execution.  `measured`
    is the observation -- verdict, axis, counts, argv, exit status and the
    report's own failure entries -- for every oracle including the admitted
    ones, and it is delivered to the roles that judge and repair the oracle but
    cannot run it.  `refusal` is None whenever the set may proceed.

    MEASURED, runs 31 and 32b (2026-09-06), the same class twice: an oracle
    that was `red` on every axis this runner held -- exit 1, one failure, zero
    errors -- and red because it compared two absolute roots that can never be
    equal.  The reviewer approved it from its BYTES, a crafter implemented
    behind it, and the refusal came two paid turns later from a native run.
    The discriminating fact was in the first lines of a pytest output nobody
    downstream of the execution was ever shown.
    """

    measured: tuple[dict[str, object], ...]
    refusal: OracleRedRefusal | None


@dataclass(frozen=True, slots=True)
class AcceptanceFinding:
    """One refusal of the oracle set that ONE named owner may still answer.

    The owner is the reviewer's own closed word, or `Oracle` by construction
    for an executed-red refusal: those bytes were written by the acceptance
    designer and by nobody else, so no judgement is needed to attribute them.

    `measured` travels with the finding so the one correction window reads the
    same observed execution the refusing turn read, rather than a second
    measurement that may disagree with it.
    """

    finding: str
    owner: DefectOwner
    value: str | None
    terminal: DeliveryOutcome
    measured: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class MeasuredOracleSet:
    """One measurement of the oracle set: what it measured, and what refused it.

    The two travel together because a caller that ADMITS the set still needs
    the measurement.  Returning a bare `None` for "admitted" made the executed
    RED unreachable outside the runner's own loop, and a step invoked alone has
    to report the evidence it was admitted on -- an admission with its evidence
    dropped is a designation, not a property (GDP-8).

    `refusal` is `None` when the set is admitted, an `AcceptanceFinding` when
    ONE named owner may still repair it, and a bare outcome when nothing can.
    """

    measured: tuple[dict[str, object], ...]
    refusal: AcceptanceFinding | DeliveryOutcome | None


@dataclass(frozen=True, slots=True)
class ScopeObservation:
    """Paths that changed outside a role's own, split by what the runner knows.

    The runner observes bytes, never writers.  A path it has already DERIVED for
    this Request is delivery surface: some value owns it, so another role
    changing it is an attributable scope violation.  A path it has derived
    nothing about could equally be the provider's own config dir, an interpreter
    cache or another process sharing the checkout, so it stays unattributed.

    `attributed` is therefore bounded by what the runner has derived SO FAR, not
    by the whole Request: values are designed one at a time, and a value whose
    authority is not yet bound has no owned paths anywhere to read.  Every
    message built from this split says only that.

    The same single comparison also answers the opposite question: `in_scope`
    holds the role's OWN allowed paths whose record or bytes moved, so an
    accepted turn that produced no bytes at all is observable without a second
    walk of the workspace.
    """

    attributed: tuple[str, ...] = ()
    unattributed: tuple[str, ...] = ()
    in_scope: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class NativeRun:
    """How ONE ordered native execution is labelled, and what it may keep.

    `origin` labels every record the execution produces and decides the refusal
    policy: a DECLARED vector the kernel will not start leaves the run with no
    verification, so it terminates, while any other provenance is retained as an
    unobserved stimulus instead.  `changed` is the candidate's own changed paths,
    which the exercise measure intersects with what each execution imported.
    `capture_incomplete` keeps a declared command's partial observation beside
    its terminal fact rather than returning that fact alone.

    Every call site in THIS module asks for the declared label and nothing else;
    the other provenance is what the unobserved-stimulus arm of the execution
    loop exists for, and no code here supplies it.
    """

    origin: str = DECLARED_ORIGIN
    changed: tuple[str, ...] = ()
    capture_incomplete: bool = False


#: The declared-vector execution with nothing retained -- what a caller that
#: names no policy gets.  ONE shared frozen value, so no signature carries a
#: constructor call in a default argument.
_DECLARED_NATIVE_RUN = NativeRun()


@dataclass(frozen=True, slots=True, kw_only=True)
class CommandObservation:
    """The facts of ONE command invocation that are not its result.

    Captured before the spawn apart from the elapsed duration, so a launch
    refusal and a fired bound carry exactly what a completed command carries.
    The two builders of a `NativeEvidence` with NO exit status -- the stimulus
    that never started, and the declared command whose observation is partial --
    take this record instead of six loose arguments, which is what keeps them
    from disagreeing about which invocation they are each describing.

    Keyword-only: `origin` and `cwd` are both strings, nothing here enforces
    annotations at runtime, and a positional swap would report a provenance as
    the working directory a command ran in.
    """

    origin: str
    touches_test_paths: bool
    # Required, with no default. `UNEXERCISED` is not a neutral placeholder: it is a
    # positive claim that the command imported no product module, and the
    # `NativeEvidence` docstring above states the opposite rule, that absence means
    # unmeasured. A record built without this must fail to construct rather than
    # quietly assert something about what ran. All four construction sites pass it.
    exercised: ExercisedModules
    duration_seconds: float | None = None
    cwd: str | None = None
    declared_environment: tuple[tuple[str, str], ...] | None = None
    executable: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnRecordTarget:
    """Where one role's turn records are written, and which values they cover.

    `base` is the commit the record is parented on, which is what makes a stale
    record self-invalidating: one taken before an integration cannot match after
    one.  `request` keys the ref namespace, and `values` are the (observation,
    selected-revision identity) pairs the record is a fact about.

    Keyword-only: `base` and `request` are both strings, nothing here enforces
    annotations at runtime, and swapping them would key every record under a ref
    named by a commit sha.
    """

    base: str
    request: str
    values: tuple[tuple[str, RecordIdentity], ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeWindow:
    """The window one turn's scope is measured in.

    `status` and `workspace` are the porcelain records and the bytes of every
    path they name, observed BEFORE the turn, so the comparison after it reads
    the same two axes.  `declared` is every path this Request has DERIVED so
    far: a changed path it names is attributable delivery surface, and a path it
    does not name reaches the third state rather than a refusal naming a writer
    the runner never observed.
    """

    status: str
    workspace: dict[str, tuple[str, bytes | str]]
    declared: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VerifiedCandidate:
    """One candidate SHA and the declared native evidence its execution produced."""

    sha: str
    evidence: tuple[NativeEvidence, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Integration:
    """The one compare-and-swap an integration performs, and what it must leave.

    `base` is the expected-old commit and `candidate` the commit that replaces
    it.  `foreign_status` and `foreign_bytes` are the state OUTSIDE this
    Request's owned paths as it stood immediately before the swap: the
    reconciliation proves them equivalent afterwards, or reports cleanup as
    unproven rather than answering with a Success nobody verified.

    Keyword-only: `base`, `candidate` and `foreign_status` are all strings,
    nothing here enforces annotations at runtime, and a positional swap would
    compare and swap in the opposite direction without saying so.
    """

    base: str
    candidate: str
    foreign_status: str
    foreign_bytes: dict[str, tuple[str, bytes | str]]


@dataclass(frozen=True, slots=True)
class SelectedValue:
    """One value of a Request, as the three facts a per-value step consumes.

    `stored` is the persisted graph the value belongs to, `ready` is the value
    itself, and `design` is the runner's ephemeral projection of the authority it
    is bound to -- the selected acceptance revision where one exists, and the
    DESIGN facts otherwise.  `design` is derived by the caller and never here,
    which is what keeps `selected_authority` the ONE source of that projection.
    """

    stored: StoredHandover
    ready: HandoverValue
    design: AuthorityFacts


_PRODUCT_ROOT = Path("docs/product")


@dataclass(frozen=True, slots=True)
class AuthorityFacts:
    """The runner's ephemeral projection of one resolved durable section."""

    locator: str
    modified_authority_paths: tuple[str, ...]
    target_decisions: tuple[tuple[str, str], ...]
    paradigm: str
    decisions: tuple[str, ...]
    obligations: tuple[str, ...]
    acceptance_oracle_locator: str
    acceptance_paths: tuple[str, ...]
    native_verification_argvs: tuple[tuple[str, ...], ...]
    oracle_verification_index: int
    acceptance_obligations: tuple[AcceptanceObligation, ...] = ()
    required_verification_argvs: tuple[tuple[str, ...], ...] = ()
    required_check_paths: tuple[str, ...] = ()
    architectural_tests: ApplicableArchitecturalTests | NotApplicable | None = None
    contract_tests: ApplicableContractTests | NotApplicable | None = None
    prefactoring: ApplicablePrefactoring | NotApplicable | None = None
    agreement_analysis: ApplicableAgreementAnalysis | NotApplicable | None = None
    reuse_analysis: ReuseAnalysis | UnassessedDesignDecision | None = None
    impact_closure: (
        ApplicableImpactClosure | NotApplicable | UnassessedDesignDecision | None
    ) = None
    adr: ApplicableADR | NotApplicable | None = None
    public_oracle: PublicOracle | None = None

    @property
    def oracle_verification_argv(self) -> tuple[str, ...]:
        """The explicitly selected vector for this authority's oracle."""
        return self.native_verification_argvs[self.oracle_verification_index]

    @property
    def selected_revision_sha256(self) -> str:
        """The identity of all DESIGN facts a turn is allowed to reuse.

        A selected oracle revision alone omits architecture decisions and
        target ownership.  Those omissions let a changed DESIGN reuse a turn
        that never saw its current authority.
        """
        selected = selected_revision_sha256(
            self.acceptance_obligations or None,
            self.acceptance_oracle_locator,
            self.acceptance_paths[1:],
            self.native_verification_argvs,
            self.oracle_verification_index,
        )
        payload = json.dumps(
            {
                "selected": selected,
                "locator": self.locator,
                "targets": self.target_decisions,
                "paradigm": self.paradigm,
                "decisions": self.decisions,
                "obligations": self.obligations,
                "required_verification": self.required_verification_argvs,
                "architectural_tests": self._decision_wire(self.architectural_tests),
                "contract_tests": self._decision_wire(self.contract_tests),
                "prefactoring": self._decision_wire(self.prefactoring),
                "agreement_analysis": self._decision_wire(self.agreement_analysis),
                "reuse_analysis": self._decision_wire(self.reuse_analysis),
                "impact_closure": self._decision_wire(self.impact_closure),
                "adr": self._decision_wire(self.adr),
                **(
                    {"public_oracle": asdict(self.public_oracle)}
                    if self.public_oracle is not None
                    else {}
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _decision_wire(decision: object | None) -> object:
        if decision is None:
            return None
        wire = asdict(decision)
        # A decision without an applicability tag (the reuse analysis) is its
        # own fields; every tagged one leads with its tag, as persisted.
        return (
            {"applicability": decision.applicability, **wire}
            if hasattr(decision, "applicability")
            else wire
        )


@dataclass(frozen=True, slots=True)
class RecordIdentity:
    """The selected revision and cited DESIGN sections a turn records."""

    revision: str
    design_sections: str

    @classmethod
    def of(
        cls,
        root: Path,
        stored: StoredHandover,
        value: HandoverValue,
        design: AuthorityFacts,
    ) -> RecordIdentity | None:
        sections = DeliveryContinuationRunner().cited_design_sections(
            root, stored, value
        )
        if sections is None:
            return None
        encoded = json.dumps(
            [[locator, digest] for locator, digest in sections], separators=(",", ":")
        ).encode("utf-8")
        return cls(design.selected_revision_sha256, hashlib.sha256(encoded).hexdigest())


@dataclass(frozen=True, slots=True)
class VerificationRecord:
    """One recorded verification, and whether the graph it covers is current."""

    candidate: str
    covers_current_upstream: bool


_RUNNER_OWNED_PREFIX = ".nwave/des/"
"""The runner's own state directory: the handover it rewrites, and the turn
records it writes as diagnostics.  No role ever declares a path under it, so a
byte there is the runner's BY CONSTRUCTION and can never be a role's drift.
Measured 2026-09-05: without this, recording every turn made six public
acceptance tests fail with `WorkspaceDriftUnattributed` naming the runner's own
record, because `--untracked-files=all` reports it like any other byte.  The
exclusion is exactly this prefix and not `.nwave/` -- telemetry, audit and
observability under that root belong to other writers and stay observable.  The
handover does not lose a guard by leaving this comparison: `handover_unchanged`
is its compare-and-set, and it is the one that was always doing that work."""


def _runner_owned_record(paths: list[str]) -> bool:
    """Whether one porcelain record speaks only about the runner's own state."""
    return all(path.startswith(_RUNNER_OWNED_PREFIX) for path in paths)


def _status_records(status: str) -> tuple[list[tuple[str, list[str]]], list[str]]:
    """One porcelain-v1 NUL traversal: (record, its paths) pairs plus the tail.

    A rename or copy record owns the following NUL field as its source path, so
    both the foreign-record filter and the dirty-path list read the same walk
    rather than two drifting copies of it.  The runner's own records are dropped
    HERE, in that single walk, so the foreign-record filter and the dirty-path
    list cannot disagree about what the runner owns.
    """
    records = status.split("\0")
    parsed: list[tuple[str, list[str]]] = []
    index = 0
    while index < len(records) - 1:
        record = records[index]
        if len(record) < 4 or record[2] != " " or not record[3:]:
            return parsed, records[index:-1]
        paths = [record[3:]]
        index += 1
        if "R" in record[:2] or "C" in record[:2]:
            if index >= len(records) - 1 or not records[index]:
                return parsed, [record, *records[index:-1]]
            paths.append(records[index])
            index += 1
        if not _runner_owned_record(paths):
            parsed.append((record, paths))
    return parsed, []


def _foreign_status(status: str, owned: tuple[str, ...]) -> str:
    """Return porcelain records that cannot be attributed to the Request."""
    owned_paths = set(owned)
    parsed, tail = _status_records(status)
    kept = [
        field
        for record, paths in parsed
        if not all(path in owned_paths for path in paths)
        for field in (record, *paths[1:])
    ]
    return "\0".join(kept + tail)


def _status_paths(status: str) -> tuple[str, ...]:
    """Extract only paths already observable in porcelain-v1 NUL records."""
    parsed, _ = _status_records(status)
    return tuple(path for _, paths in parsed for path in paths)


def _workspace_bytes(
    root: Path, paths: tuple[str, ...]
) -> dict[str, tuple[str, bytes | str]]:
    """Snapshot only paths already dirty in the initial porcelain observation.

    Total over the filesystem, not only over the paths git named.  Every probe
    here reads the WORLD -- `is_symlink`, `readlink`, `read_bytes` all raise
    `OSError` on a permission change, a vanished mount, a path that stopped
    being what porcelain said it was between the two observations -- and this
    snapshot is compared BEFORE and AFTER a model turn, so the window for that
    change is exactly as wide as the turn.  An unreadable path is recorded as
    the reason it could not be read, which keeps the comparison honest in both
    directions: unreadable-then-unreadable-for-the-same-reason is not drift,
    while readable-then-unreadable IS, and the runner degrades LOUD instead of
    crashing mid-delivery.
    """
    snapshot: dict[str, tuple[str, bytes | str]] = {}
    for relative in paths:
        path = root / relative
        try:
            if path.is_symlink():
                snapshot[relative] = ("symlink", str(path.readlink()))
            elif path.is_file():
                snapshot[relative] = ("file", path.read_bytes())
            else:
                snapshot[relative] = ("absent", "")
        except OSError as unreadable:
            snapshot[relative] = ("unreadable", f"{type(unreadable).__name__}")
    return snapshot


def _readable_text(content: bytes | str) -> str:
    """One prompt-safe rendering of either half of a workspace snapshot value."""
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    return content


def _foreign_bytes(
    snapshot: dict[str, tuple[str, bytes | str]], owned: tuple[str, ...]
) -> dict[str, tuple[str, bytes | str]]:
    owned_paths = set(owned)
    return {path: value for path, value in snapshot.items() if path not in owned_paths}


#: Stands in for a porcelain tail Git wrote but this parser could not read.  A
#: real path is never empty and never carries a space, so no path can collide.
_UNPARSED_STATUS = "an unparsable porcelain record"


def _foreign_records(status: str, owned: tuple[str, ...]) -> dict[str, str]:
    """Each unowned porcelain record keyed by the path it reports.

    `_foreign_status` answers *whether* unowned state moved; this answers
    *which path* moved, so a rejection can name the bytes it rejects over
    (GDP-3).  Both read the same `_status_records` walk.
    """
    owned_paths = set(owned)
    parsed, tail = _status_records(status)
    records = {
        paths[0]: "\0".join((record, *paths[1:]))
        for record, paths in parsed
        if not all(path in owned_paths for path in paths)
    }
    if tail:
        # An unparsable porcelain tail reports no path at all.  Keyed under a
        # name Git can never emit, it still moves the comparison rather than
        # vanishing from it, and reads as prose in a rejection.
        records[_UNPARSED_STATUS] = "\0".join(tail)
    return records


def _scope_changes(
    before_status: str,
    before_bytes: dict[str, tuple[str, bytes | str]],
    after_status: str,
    after_bytes: dict[str, tuple[str, bytes | str]],
    owned: tuple[str, ...],
) -> tuple[str, ...]:
    """Every path outside `owned` whose porcelain record or bytes moved."""
    before_records = _foreign_records(before_status, owned)
    after_records = _foreign_records(after_status, owned)
    before = _foreign_bytes(before_bytes, owned)
    after = _foreign_bytes(after_bytes, owned)
    return tuple(
        sorted(
            {
                path
                for path in (*before_records, *after_records, *before, *after)
                if before_records.get(path) != after_records.get(path)
                or before.get(path) != after.get(path)
            }
        )
    )


def _scope_observation(
    changed: tuple[str, ...],
    declared: tuple[str, ...],
    allowed: tuple[str, ...] = (),
    owns: Callable[[str], bool] | None = None,
) -> ScopeObservation:
    """Split observed change by ownership, then by whether a fact names it.

    Ownership is answered by an enumerated set, by a PROPERTY of the path, or by
    both.  A role whose surface is a region rather than a list -- every path
    under the subject's test paths, say -- cannot be described by enumeration
    without the runner first guessing which files that region will contain, and
    a guess is exactly the designation GDP-8 forbids deciding on.
    """
    allowed_paths, declared_paths = set(allowed), set(declared)

    def owned(path: str) -> bool:
        return path in allowed_paths or (owns is not None and owns(path))

    outside = tuple(path for path in changed if not owned(path))
    return ScopeObservation(
        tuple(path for path in outside if path in declared_paths),
        tuple(path for path in outside if path not in declared_paths),
        tuple(path for path in changed if owned(path)),
    )


def _repo_local_markdown(root: Path, relative: str) -> Path | None:
    """The real Markdown file a repo-relative reference names, or None.

    Authority is admitted by property, never by directory or filename: no
    absolute path, no traversal, no symlink resolving outside the root.
    """
    reference = PurePosixPath(relative)
    if reference.is_absolute() or ".." in reference.parts or reference.suffix != ".md":
        return None
    path = root / reference
    try:
        if path.is_symlink() or not path.is_file():
            return None
    except OSError:
        # The same EACCES `Path.is_file` lets through.  `None` is already this
        # function's answer for every world in which the document cannot be
        # honestly read, and its caller turns it into `ArchitectureAuthority
        # Unresolved`, so the unreadable case needs no new shape.
        return None
    try:
        resolved, resolved_root = path.resolve(strict=True), root.resolve()
    except OSError:
        return None
    return path if resolved.is_relative_to(resolved_root) else None


def _markdown_text(root: Path, relative: str) -> str | None:
    """The current UTF-8 text of one repo-local Markdown document, or None."""
    path = _repo_local_markdown(root, relative)
    if path is None:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _authority_bytes(
    root: Path, paths: tuple[str, ...]
) -> tuple[tuple[str, bytes], ...] | None:
    """Read the exact approved authority bytes without interpreting prose.

    Admitted by PROPERTY, exactly as `_repo_local_markdown` already admits an
    authority document: a path that is a symlink, or that resolves outside the
    root, names bytes this repository does not own, and approving them as this
    Request's immutable evidence would let a link decide what the oracle says.
    `None` is the one answer for every world in which the bytes cannot be
    honestly read, and every caller already turns it into a Disposition.
    """
    try:
        resolved_root = root.resolve()
        readable = []
        for path in paths:
            candidate = root / path
            if candidate.is_symlink():
                return None
            if not candidate.resolve(strict=True).is_relative_to(resolved_root):
                return None
            readable.append((path, candidate.read_bytes()))
    except OSError:
        return None
    return tuple(readable)


class DeliveryContinuationRunner:
    """One process-local owner; it accepts no caller-authored handover."""

    def __init__(self) -> None:
        self._radius = INDETERMINATE
        self._native_evidence_locator: str | None = None
        self._native_evidence_sha256: str | None = None
        self._reusing_verification_workspace = False
        self.verification_lease_held = False
        self._verification_writers_quiescent = True
        #: True ONLY while candidate verification measurement runs (reuse
        #: workspace OR isolated cold checkout): the measured native child
        #: is spawned as its own session leader so its whole subtree can be
        #: reaped and quiescence OBSERVED. Every other spawn (oracle,
        #: craft, services) keeps plain semantics -- no blanket reaping.
        #: The cold path previously skipped this, so a cold verify's child
        #: inherited the CALLER's process group -- a test harness running
        #: verify was killpg-able by its own cleanup (bg316 exit 137).
        self._verification_measurement_group = False
        #: Set at the workspace boundary; ``report`` lines are observable
        #: step facts, ``None`` when no candidate workspace was entered.
        self.workspace_maintenance: WorkspaceMaintenance | None = None

    @staticmethod
    def _fail(d: Disposition, what: str, why: str, how: str) -> DeliveryOutcome:
        return DeliveryOutcome(d, FailureDetail(what, why, how))

    def _blocked(self, blocked: Blocked) -> DeliveryOutcome:
        """One mapping from a software refusal to this runner's terminal shape."""
        return self._fail(
            Disposition.Refusal if blocked.refusal else Disposition.Indeterminate,
            blocked.what,
            blocked.why,
            blocked.how,
        )

    @staticmethod
    def _git(
        root: Path, *args: str, env: dict[str, str] | None = None
    ) -> GitObservation:
        """One TOTAL text observation of git -- it answers or says why it cannot.

        The helper this replaced called `spawn` directly and was typed as total
        while two inputs from the world escaped it as a bare traceback across
        every phase: git absent from `PATH` (`FileNotFoundError`) and git output
        that is not UTF-8 (`UnicodeDecodeError`, because `text=True` decodes and
        the decoder has no fallback).  Both are now CONSTRUCTED into the same
        non-zero-`returncode` shape each call site already consumes, and the
        seam carries the GIT tier and a declared child environment with them.
        """
        return observe_text(root, *args, env=env)

    def _git_failure(
        self,
        *observed: GitObservation,
        disposition: Disposition,
        what: str,
        how: str,
        why: str | None = None,
    ) -> DeliveryOutcome:
        """The ONE way a failed git observation becomes a terminal outcome.

        Routing every site through here is what makes forgetting the non-answer
        unrepresentable (GDP-0): a phase names the disposition for "git refused",
        and cannot name one for "git never answered" -- that case is always
        Indeterminate, carrying the seam's own WHAT/WHY/HOW (GDP-3, GDP-8).  A
        phase-level Retry or Refusal there would assert a repository fact the
        runner never observed.
        """
        for observation in observed:
            if observation.unanswered is not None:
                return self._fail(
                    Disposition.Indeterminate,
                    observation.unanswered.what,
                    observation.unanswered.why,
                    observation.unanswered.how,
                )
        return self._fail(
            disposition,
            what,
            why if why is not None else "".join(o.stderr for o in observed),
            how,
        )

    def _advance_failure(self, refused: AdvanceRefusal) -> DeliveryOutcome:
        """One mapping from the shared HEAD-advance vocabulary into a terminal.

        A git that never ANSWERED stays Indeterminate carrying the seam's own
        WHAT/WHY/HOW, exactly as `_git_failure` decides for every other site: a
        phase-level Retry there would assert a repository fact this runner never
        observed.
        """
        if refused.unanswered is not None:
            return self._fail(
                Disposition.Indeterminate,
                refused.unanswered.what,
                refused.unanswered.why,
                refused.unanswered.how,
            )
        return self._fail(Disposition.Retry, refused.what, refused.why, refused.how)

    @property
    def radius(self) -> str:
        """The candidate radius the last `verify` measured (ADR-DES-003 §6)."""
        return self._radius

    @property
    def native_evidence_locator(self) -> str | None:
        """The durable locator for this verify call's native observation."""
        return self._native_evidence_locator

    @property
    def native_evidence_sha256(self) -> str | None:
        """The content digest paired with ``native_evidence_locator``."""
        return self._native_evidence_sha256

    def persist_candidate_observations(
        self,
        root: Path,
        candidate: str,
        stored: StoredHandover,
        prepared: list[tuple[str, AuthorityFacts]],
    ) -> bool:
        """Seal radius and witness history at verify, not at later preparation.

        Value refs are released at integration. Keeping their projection beside
        the candidate-bound radius preserves the same packet after that cleanup,
        and a later oracle measurement cannot rewrite this candidate's history.
        """
        if self._native_evidence_sha256 is None:
            return False
        directory = root / ".nwave" / "des" / "logs" / "radius"
        body = {
            "candidate_sha": candidate,
            "native_evidence_sha256": self._native_evidence_sha256,
            "native_evidence_locator": self._native_evidence_locator,
            "radius": self._radius,
            "oracle_witnesses": [
                self.oracle_witness(root, stored, observation, design)
                for observation, design in prepared
            ],
        }
        payload = json.dumps(
            {
                **body,
                "payload_sha256": hashlib.sha256(
                    json.dumps(body, sort_keys=True).encode()
                ).hexdigest(),
            },
            sort_keys=True,
        ).encode()
        path = directory / f"{candidate}.json"
        try:
            directory.mkdir(parents=True, exist_ok=True)
            history = directory / f"{candidate}-{self._native_evidence_sha256}.json"
            if not history.exists():
                history.write_bytes(payload)
            descriptor, temporary = tempfile.mkstemp(
                prefix=f".{candidate}-", dir=directory
            )
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
            Path(temporary).replace(path)
            return path.read_bytes() == payload
        except OSError:
            return False

    def load_native_evidence_identity(self, root: Path, candidate: str) -> bool:
        """Load one complete, candidate-bound native observation for reuse.

        The candidate record is sufficient to avoid a second declared command
        only when its durable native bytes are still readable and unambiguous.
        Older verify refs without this record are not evidence of a successful
        native execution.
        """
        directory = root / ".nwave" / "des" / "logs" / "native"
        bound_digest = None
        try:
            snapshot = root / ".nwave/des/logs/radius" / f"{candidate}.json"
            if snapshot.exists():
                binding = json.loads(snapshot.read_bytes())
                if not isinstance(binding, dict):
                    return False
                seal = binding.pop("payload_sha256", None)
                if (
                    binding.get("candidate_sha") != candidate
                    or seal
                    != hashlib.sha256(
                        json.dumps(binding, sort_keys=True).encode()
                    ).hexdigest()
                ):
                    return False
                bound_digest = binding.get("native_evidence_sha256")
                locator = binding.get("native_evidence_locator")
            else:
                locator = None
            if locator is not None:
                path = root / locator
                if path.parent != directory or not path.name.startswith(
                    f"{candidate}-"
                ):
                    return False
            else:
                records = sorted(directory.glob(f"{candidate}-*.json"))
                if len(records) != 1:
                    return False
                path = records[0]
        except (OSError, ValueError, TypeError):
            return False
        try:
            payload = path.read_bytes()
            decoded = json.loads(payload)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False
        if not isinstance(decoded, list):
            return False
        embedded_digest, separator, _rest = path.name[len(candidate) + 1 :].partition(
            "-"
        )
        actual_digest = hashlib.sha256(payload).hexdigest()
        if (
            not separator
            or len(embedded_digest) != 64
            or any(character not in "0123456789abcdef" for character in embedded_digest)
            or embedded_digest != actual_digest
            or (bound_digest is not None and bound_digest != actual_digest)
        ):
            return False
        self._native_evidence_locator = path.relative_to(root).as_posix()
        self._native_evidence_sha256 = actual_digest
        return True

    #: Recorded in place of a file's bytes when the world refused the read.
    #: A real file's content is never this value, and the marker is the same on
    #: both sides of a before/after comparison, so an unreadable path that stays
    #: unreadable is not reported as drift while one that BECOMES unreadable is.
    _UNREADABLE = b"\0nwave-unreadable\0"

    @staticmethod
    def _snapshot(root: Path, relative_root: Path) -> dict[str, bytes]:
        """The durable product tree as bytes -- total over an unreadable tree.

        `rglob` and `read_bytes` both reach the filesystem and both raise
        `OSError`; this snapshot brackets a model turn whose whole purpose is to
        touch files, so a permission change, a vanished entry or a broken mount
        during that turn used to leave the runner as a bare traceback rather
        than as one of its four dispositions.
        """
        directory = root / relative_root
        try:
            if not directory.is_dir():
                return {}
            entries = DeliveryContinuationRunner._walk(directory)
        except OSError as unwalkable:
            return {relative_root.as_posix(): f"{type(unwalkable).__name__}".encode()}
        snapshot: dict[str, bytes] = {}
        for path in entries:
            try:
                snapshot[path.relative_to(root).as_posix()] = path.read_bytes()
            except OSError:
                snapshot[path.relative_to(root).as_posix()] = (
                    DeliveryContinuationRunner._UNREADABLE
                )
        return snapshot

    @staticmethod
    def _walk(directory: Path) -> list[Path]:
        """Every regular file under `directory`, or `OSError` if it cannot be read.

        `Path.rglob` is deliberately NOT used, and the reason is a silent-wrong
        it hides: pathlib's globber SWALLOWS the `OSError` from a directory it
        may not enter and yields nothing, so an unreadable product tree came
        back as an EMPTY tree.  Comparing empty against empty then answered "the
        read-only role changed nothing" -- proof the runner did not have, on the
        exact question this snapshot exists to settle.  `os.scandir` raises, and
        a raise the caller records beats a silence it cannot see.
        """
        found: list[Path] = []
        pending = [directory]
        while pending:
            with os.scandir(pending.pop()) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir():
                        pending.append(Path(entry.path))
                    elif entry.is_file():
                        found.append(Path(entry.path))
        return sorted(found)

    @staticmethod
    def _changed(before: dict[str, bytes], after: dict[str, bytes]) -> bool:
        return before != after

    @staticmethod
    def _regular_file(path: Path) -> bool | None:
        """Whether `path` is a regular file -- `None` when the world refused to say.

        `Path.is_file` reads as total and is not: it swallows only the errnos
        that already MEAN absence (ENOENT, ENOTDIR, ELOOP, EBADF) and lets
        EACCES through, so a directory that stops being searchable during a
        model turn raised across the whole runner.  Found by the generated
        property in `tests/des/acceptance/dispatch_owns_e2_e4/
        test_runner_totality_over_system_domains.py`, not by inspection.

        The third state reaches the caller (GDP-8 arity corollary) rather than
        collapsing into `False`: "the author never created it" and "I could not
        look" ask the reader for opposite repairs, and a rejection that names
        the wrong one is worse than a bare traceback.
        """
        try:
            return path.is_file()
        except OSError:
            return None

    @staticmethod
    def _path_present(path: Path) -> bool | None:
        """Whether `path` exists at all -- `None` when the world refused to say.

        `Path.exists` carries the same partiality as `Path.is_file`, on a
        question the runner asks about a path it does NOT own (the handover),
        where a wrong answer either invents a protocol violation or hides one.
        """
        try:
            return path.exists()
        except OSError:
            return None

    @staticmethod
    def _git_bytes(root: Path, *args: str) -> bytes | None:
        """One byte-exact Git observation, or None when Git could not answer.

        Git paths and blobs are bytes.  Decoding them through the process locale
        would make eligibility depend on the environment and would raise on the
        first non-UTF-8 byte, so every caller decodes strictly and treats a
        failure as ineligible.

        `None` now covers one more world than "git exited non-zero": an absent
        or unrunnable git, and a fired GIT-tier bound, which used to leave this
        helper as a `FileNotFoundError` crossing the whole runner.  The byte
        path never decodes, so it has no undecodable case of its own.  What the
        `bytes | None` shape cannot carry is WHICH of those held -- every caller
        already answers "git could not observe this" with a self-explaining
        Disposition naming `restore Git`, and widening the shape would reach
        into a function another lane owns; the residue is declared in
        `defects.md` rather than hidden.
        """
        completed = observe_bytes(root, *args)
        return None if completed.returncode else completed.stdout

    @staticmethod
    def _utf8(raw: bytes | None) -> str | None:
        try:
            return None if raw is None else raw.decode("utf-8")
        except UnicodeDecodeError:
            return None

    def _observed_scope(
        self, root: Path
    ) -> tuple[str, dict[str, tuple[str, bytes | str]]] | DeliveryOutcome:
        """One pre-invocation workspace observation, or a typed Git failure."""
        status = self._git(
            root, "status", "--porcelain=v1", "-z", "--untracked-files=all"
        )
        if status.returncode:
            return self._git_failure(
                status,
                disposition=Disposition.Retry,
                what="GitUnavailable",
                how="restore Git",
            )
        return status.stdout, _workspace_bytes(root, _status_paths(status.stdout))

    def _scope_drift(
        self,
        root: Path,
        before: ScopeWindow,
        allowed: tuple[str, ...] = (),
        owns: Callable[[str], bool] | None = None,
    ) -> ScopeObservation | DeliveryOutcome:
        """Observe one comparison: outside the role's own paths, and those themselves.

        `before` carries the two axes of the pre-turn observation together with
        the paths this Request has already declared, because all three are read
        by the single comparison below and a site holding one without the others
        cannot make it.
        """
        status = self._git(
            root, "status", "--porcelain=v1", "-z", "--untracked-files=all"
        )
        if status.returncode:
            return self._git_failure(
                status,
                disposition=Disposition.Retry,
                what="GitUnavailable",
                how="restore Git",
            )
        paths = tuple(dict.fromkeys((*before.workspace, *_status_paths(status.stdout))))
        after_bytes = _workspace_bytes(root, paths)
        return _scope_observation(
            _scope_changes(
                before.status, before.workspace, status.stdout, after_bytes, ()
            ),
            before.declared,
            allowed,
            owns,
        )

    def _designer_owns(
        self, root: Path, acceptance_paths: tuple[str, ...]
    ) -> Callable[[str], bool]:
        """The designer owns test substrate and the authority's acceptance paths.

        The PROPERTY, not the target table (GDP-8). Runs 25 and 26 both
        refused the designer for realigning a code-fact adapter UNIT TEST the
        architect had also named in `targets` -- so the runner read it as
        production and refused work the designer's own obligations demanded.
        Two runs, roughly $2.6 and 25 minutes, and a rewritten Request bought
        zero defects. A path is
        test substrate because of where it sits, and naming it somewhere else
        never moves it.

        The authority may declare a test outside the subject's pytest layout.
        That explicit declaration belongs to the acceptance designer; unrelated
        production paths remain outside its scope.  Existing test substrate
        stays owned by `path_under_test_paths`, the same measurement the
        request stimulus uses.
        """
        test_paths = self._subject_test_paths(root)
        declared_acceptance = frozenset(acceptance_paths)
        return lambda path: (
            path in declared_acceptance or path_under_test_paths(path, test_paths)
        )

    @staticmethod
    def _crafter_owns(
        prepared: list[tuple[str, AuthorityFacts]],
    ) -> Callable[[str], bool]:
        """Every path this Request declares except the oracles is the crafter's.

        The ORACLE is the property worth protecting, and it is the only one:
        RED to GREEN must be bought by production, never by editing the test
        that measures it (ADR-SSOT-002 sec 12).  Everything else the Request
        declares -- a sibling value's target, a support the target table does
        not name -- was a cage built on the DESIGNATION, and across 14 recorded
        runs it refused nothing real.  `mutable_targets` still travels to the
        crafter and still orders the batches; it stopped being the wall.

        Outside the Request nothing is permitted, so a byte no fact names still
        reaches the third state instead of a refusal that names a writer the
        runner never observed.
        """
        oracles = {design.acceptance_paths[0] for _, design in prepared}
        owned = set(DeliveryContinuationRunner._request_owned_paths(prepared))
        return lambda path: path in owned and path not in oracles

    @staticmethod
    def _production_scope_drift(role: str, drift: ScopeObservation) -> DeliveryOutcome:
        """The ONE refusal the designer's scope keeps: bytes outside test paths.

        The RED is measured on production the designer did not touch, and that
        is the whole promise -- so the refusal names the paths that broke it
        rather than repeating the rule (GDP-3).  There is no second name for the
        same property: `AcceptanceCorrectionScopeDrift` and `ForeignScopeDrift`
        both meant "the designer changed something it does not own" and are
        gone, because one rule that answers both is not two rules.
        """
        return DeliveryContinuationRunner._fail(
            Disposition.Refusal,
            "ProductionScopeDrift",
            f"{role} changed bytes outside the subject's test paths: "
            + ", ".join(drift.attributed),
            "restore those paths and rerun from a new Request",
        )

    @staticmethod
    def _unattributed(role: str, drift: ScopeObservation) -> DeliveryOutcome:
        """The third state: bytes moved, and the runner cannot say by whom.

        `--untracked-files=all` observes the whole root, so a provider config
        dir, an interpreter cache or a second process sharing the checkout is
        indistinguishable from the role's own write.  Declaring that reaches
        the aggregate (GDP-8) instead of a refusal that names a culprit the
        runner never observed (GDP-3, GDP-6).

        Both sentences are built from the observation and nothing else.  The WHY
        claims only the two properties actually measured -- not owned by `role`,
        not among the paths derived so far -- because the Request may still
        declare a path no value has produced yet.  The HOW names those paths and
        stops: which tool wrote them is not observed, so a remedy naming one
        would be advice this run never earned.
        """
        paths = ", ".join(drift.unattributed)
        return DeliveryContinuationRunner._fail(
            Disposition.Indeterminate,
            "WorkspaceDriftUnattributed",
            f"bytes changed that {role} does not own and that no value prepared "
            f"so far in this Request declares, and the runner observes bytes, "
            f"not writers: {paths}",
            f"restore {paths} and rerun",
        )

    @staticmethod
    def _ignored_supports(
        root: Path, supports: tuple[str, ...]
    ) -> tuple[str, ...] | None:
        """The declared supports this repository IGNORES, or None when Git cannot say.

        WHY IGNORED AND NOT UNTRACKED, measured 2026-09-05.  Untracked is the
        stronger predicate and the wrong one: a support is not always a file
        that already exists.  `nw-acceptance-designer` authors the oracle AND
        its declared supports in the same turn, and five public acceptance tests
        exercise exactly that -- the runner derives the authority BEFORE the
        author has written a byte, so demanding tracked-ness here would refuse
        every RED_TO_GREEN Request in the tree.  What the measured defect
        actually was is narrower and stays decidable: a support that the
        repository IGNORES is a generated artifact by construction, never
        evidence a reviewer can reproduce from the commit.

        One `check-ignore` for the whole set names the culprits (GDP-3) without
        N spawns.  The paths travel on `--stdin` because `-z` is accepted only
        there.  Its exit status is the ANSWER, not an error: 0 means at least one
        path is ignored, 1 means none is, and anything else means Git could not
        decide -- which returns None so the caller degrades on THAT cause rather
        than reporting a clean set (GDP-6).

        The default index-aware reading is the wanted one, measured 2026-09-05
        on a repository whose `.gitignore` carries `build/`: a TRACKED
        `build/tracked.json` is NOT reported, while an untracked
        `build/untracked.json` matched by the same pattern IS.  So a file the
        repository really carries is never called generated, even when a pattern
        would match it.  `--no-index` would report both and is therefore not
        passed.

        A MISSING `git` is not a verdict either.  Git is not a runtime
        dependency of DES (`.../CLAUDE.md`, Portability), so this probe goes
        through the same total seam the rest of the runner's git does: an
        absent tool or a fired bound becomes the same None, and the caller says
        the check could not run instead of letting a traceback escape the
        application layer.  It used to hold its own `try` around a raw spawn,
        which made it total for the absent tool and left it inheriting the
        45-minute RUN bound the GIT tier exists to replace.
        """
        if not supports:
            return ()
        completed = observe_bytes(
            root,
            "check-ignore",
            "-z",
            "--stdin",
            stdin="\0".join(supports).encode("utf-8"),
        )
        if completed.unanswered is not None:
            return None
        if completed.returncode not in (0, 1):
            return None
        listed = DeliveryContinuationRunner._utf8(completed.stdout)
        if listed is None:
            return None
        ignored = {entry for entry in listed.split("\0") if entry}
        return tuple(path for path in supports if path in ignored)

    @staticmethod
    def _admit_supports(
        root: Path, supports: tuple[str, ...]
    ) -> DeliveryOutcome | None:
        """Refuse an authority whose declared supports are generated artifacts.

        Enforced HERE, at the one derivation both authority spellings pass
        through, and NOT in the typed schema: a JSON schema cannot express
        "this repository ignores that path", and the Markdown resolver is a
        domain function with no repository to ask.  The runner derives BEFORE it
        binds, so a refused authority is never persisted and the next run
        re-elicits DESIGN for that value; the HOW still names the durable case,
        because a handover written before this rule existed carries the bad
        locator into every resume.

        Measured 2026-09-05, run 12: DESIGN declared a 60 MB generated
        structural index file ignored by Git, and the runner inlined its bytes
        into the review prompt, exceeding the per-argument process limit.
        """
        ignored = DeliveryContinuationRunner._ignored_supports(root, supports)
        if ignored is None:
            return DeliveryContinuationRunner._fail(
                Disposition.Indeterminate,
                "SupportAdmissibilityUnobservable",
                "Git could not report which declared acceptance supports this "
                "repository ignores",
                "restore Git in this repository and rerun",
            )
        if not ignored:
            return None
        return DeliveryContinuationRunner._fail(
            Disposition.Indeterminate,
            "AcceptanceSupportIgnored",
            "declared acceptance support is ignored by this repository, so it is "
            "a generated artifact rather than evidence reproducible from the "
            "commit: " + ", ".join(ignored),
            "have DESIGN declare acceptance supports this repository does not "
            "ignore; when the authority is already bound, delete "
            ".nwave/des/handover.json to re-elicit DESIGN for this Request -- "
            "the generated artifact itself is never removed",
        )

    @staticmethod
    def _derive(
        root: Path, locator: str | DesignFacts, *, admit_verification: bool = True
    ) -> AuthorityFacts | DeliveryOutcome:
        """Derive runner facts by rereading one durable authority section.

        ``admit_verification=False`` leaves the DESIGN verification and target
        admission to the caller, which overrides it with a selected revision's
        own commands and then admits THAT tuple, so a discarded DESIGN argv is
        never judged.
        """
        if isinstance(locator, DesignFacts):
            defect = design_facts_defect(locator)
            if defect is not None:
                return DeliveryContinuationRunner._fail(
                    Disposition.Indeterminate,
                    "DesignFactsMalformed",
                    f"bound DESIGN facts are inadmissible: {defect}",
                    _DESIGN_FACTS_REPAIR,
                )
            inadmissible = DeliveryContinuationRunner._admit_supports(
                root, locator.acceptance_supports
            )
            if inadmissible is not None:
                return inadmissible
            oracle = locator.oracle.partition("::")[0]
            check_obligations = tuple(
                obligation
                for decision in (locator.architectural_tests, locator.contract_tests)
                if decision.applicability == "applicable"
                for obligation in decision.obligations
            )
            required_commands = tuple(
                dict.fromkeys(
                    locator.verification[item.verification_index]
                    for item in check_obligations
                )
            )
            preservation = locator.prefactoring
            preservation_paths = (
                (
                    preservation.existing_oracle.partition("::")[0],
                    *preservation.acceptance_supports,
                )
                if isinstance(preservation, ApplicablePrefactoring)
                else ()
            )
            required_paths = tuple(
                dict.fromkeys(
                    (
                        *(item.oracle.partition("::")[0] for item in check_obligations),
                        *preservation_paths,
                    )
                )
            )
            typed = AuthorityFacts(
                locator.authority_locator or f"typed:{locator.oracle}",
                (),
                tuple((target.path, target.decision) for target in locator.targets),
                locator.paradigm,
                locator.decisions,
                locator.obligations,
                locator.oracle,
                tuple(
                    dict.fromkeys(
                        (oracle, *locator.acceptance_supports, *required_paths)
                    )
                ),
                locator.verification,
                locator.oracle_verification_index,
                required_verification_argvs=required_commands,
                required_check_paths=required_paths,
                architectural_tests=locator.architectural_tests,
                contract_tests=locator.contract_tests,
                prefactoring=locator.prefactoring,
                agreement_analysis=locator.agreement_analysis,
                reuse_analysis=locator.reuse_analysis,
                impact_closure=locator.impact_closure,
                adr=locator.adr,
                public_oracle=locator.public_oracle,
            )
            if not admit_verification:
                return typed
            unresolvable = DeliveryContinuationRunner._admit_verification_executables(
                root, typed
            )
            if unresolvable is not None:
                return unresolvable
            return DeliveryContinuationRunner._admit_targets(typed) or typed
        document, separator, heading = locator.partition("#")
        text = _markdown_text(root, document) if separator and heading else None
        # `:(literal)` disarms pathspec magic: without it Git wildmatches the
        # untrusted locator, so an untracked `notes/[x].md` passes on a tracked
        # `notes/x.md`.  Tracked identity is the exact path, never a glob.
        if (
            text is None
            or DeliveryContinuationRunner._git_bytes(
                root, "ls-files", "--error-unmatch", "--", f":(literal){document}"
            )
            is None
        ):
            return DeliveryContinuationRunner._fail(
                Disposition.Indeterminate,
                "ArchitectureAuthorityUnresolved",
                "authority locator must name one readable section of a tracked "
                "repo-local Markdown document",
                "bind a valid durable authority locator",
            )
        section = resolve_authority_section(
            text, heading, locator=locator, doc_part=document
        )
        if not isinstance(section, ResolvedAuthoritySection):
            return DeliveryContinuationRunner._fail(
                Disposition.Indeterminate,
                "ArchitectureAuthorityUnresolved",
                "authority locator is missing or ambiguous",
                "repair durable authority",
            )
        targets = extract_declared_target_table(section.text)
        paradigms = [
            canonical_paradigm(item)
            for item in extract_declared_paradigms(section.text)
        ]
        oracles = extract_oracle_citations(section.text)
        supports = extract_acceptance_support_locators(section.text)
        commands = extract_declared_verification_commands(section.text)
        oracle_verification_indices = extract_declared_oracle_verification_indices(
            section.text
        )
        obligations = tuple(extract_obligations(section.text))
        if (
            not isinstance(targets, list)
            or not targets
            or len(paradigms) != 1
            or paradigms[0] is None
            or len(oracles) != 1
            or not commands
            or len(oracle_verification_indices) != 1
            or len(set(oracles + supports)) != len(oracles + supports)
            or not all(
                is_repository_relative_whole_file_locator(row.path) for row in targets
            )
            or not all(
                command and all(part for part in command) for command in commands
            )
        ):
            return DeliveryContinuationRunner._fail(
                Disposition.Indeterminate,
                "ArchitectureAuthorityIncomplete",
                "resolved authority lacks complete unambiguous consumed facts",
                "declare exactly one oracle verification command index that names "
                "one declared verification command in the existing durable authority",
            )
        inadmissible = DeliveryContinuationRunner._admit_supports(root, tuple(supports))
        if inadmissible is not None:
            return inadmissible
        oracle = oracles[0].partition("::")[0]
        conflict = target_acceptance_support_conflict(
            oracles[0], (row.path for row in targets), supports
        )
        if conflict is not None:
            return DeliveryContinuationRunner._fail(
                Disposition.Indeterminate,
                "TargetAcceptanceSupportConflict",
                target_acceptance_support_conflict_text(conflict),
                "correct the durable authority's target table or its acceptance "
                "support locators so no craft target is also a support",
            )
        declared = AuthorityFacts(
            locator,
            (document,),
            tuple((row.path, row.decision) for row in targets),
            paradigms[0],
            (),
            obligations,
            oracles[0],
            (oracle, *supports),
            tuple(tuple(command) for command in commands),
            oracle_verification_indices[0],
        )
        binding = DeliveryContinuationRunner._admit_oracle_verification_binding(
            declared
        )
        if binding is not None:
            return binding
        unresolvable = DeliveryContinuationRunner._admit_verification_executables(
            root, declared
        )
        if unresolvable is not None:
            return unresolvable
        return DeliveryContinuationRunner._admit_targets(declared) or declared

    @staticmethod
    def _admit_oracle_verification_binding(
        facts: AuthorityFacts,
    ) -> DeliveryOutcome | None:
        index = facts.oracle_verification_index
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or not 0 <= index < len(facts.native_verification_argvs)
        ):
            return DeliveryContinuationRunner._fail(
                Disposition.Indeterminate,
                "OracleVerificationBindingInvalid",
                "the declared oracle verification command index "
                f"{index!r} does not name one of the "
                f"{len(facts.native_verification_argvs)} declared verification commands",
                "set the oracle verification command index to an existing "
                "zero-based verification command ordinal in the durable authority",
            )
        return None

    @staticmethod
    def _admit_verification_executables(
        root: Path, facts: AuthorityFacts
    ) -> DeliveryOutcome | None:
        """Refuse a verification argv whose first token cannot start here.

        This runs while authority facts are still ephemeral.  A missing
        repository-relative executable is the one constructive exception: a
        delivery may declare that exact target, oracle, or support for creation,
        so refusing it before its author can materialize the path would make a
        valid ``CREATE_NEW`` delivery impossible.  Every other missing argv0
        would reach native verification only after publication, binding, and
        paid turns, even though resolving it performs no process execution.
        """
        materializable = {
            os.path.normpath(path)
            for path in (
                *(target for target, _ in facts.target_decisions),
                *facts.acceptance_paths,
            )
        }
        separators = (os.sep, *((os.altsep,) if os.altsep else ()))
        for index, argv in enumerate(facts.native_verification_argvs):
            argv0 = argv[0]
            has_separator = any(separator in argv0 for separator in separators)
            normalized = os.path.normpath(argv0)
            repository_relative = (
                has_separator
                and not Path(argv0).is_absolute()
                and is_repository_relative_whole_file_locator(normalized)
            )
            if resolve_executable(argv0, cwd=root) is not None and (
                not has_separator or Path(argv0).is_absolute() or repository_relative
            ):
                continue
            if repository_relative and normalized in materializable:
                continue
            return DeliveryContinuationRunner._fail(
                Disposition.Indeterminate,
                "VerificationExecutableUnresolvable",
                f"verification[{index}] declares `{argv0}`, which does not resolve "
                "to an executable in this repository or on PATH and is not a "
                "declared delivery path that this value can materialize",
                "declare an executable available on PATH or an executable absolute "
                "or repository-relative path; a missing repository-relative argv0 "
                "must normalize to a declared target, oracle, or acceptance support",
            )
        return None

    @staticmethod
    def _admit_targets(facts: AuthorityFacts) -> DeliveryOutcome | None:
        """Refuse a target table whose only declared path is the oracle.

        With the oracle removed from the mutable set, a table naming nothing
        else authorizes the crafter to change no byte at all, and the runner
        would send that contradiction to a paid turn exactly as it sent run
        15's empty set.  Making it unrepresentable at the derivation is not
        available -- the target table is the model's own semantic decision --
        so the refusal fires at the earliest point the software holds the fact
        (GDP-1), which is `_derive`, after the architect turn and BEFORE the
        bind.  The value therefore stays unbound and the next run re-elicits
        DESIGN for it, which is the HOW this names and the reason the
        derive-before-bind order exists.

        The decision column is NOT consulted: `EXTEND`/`CREATE_NEW` is a
        designation about whether a FILE already exists, never about who
        writes it (`integration_commit_message.py`), so an existing oracle
        extended by its author is legitimate and refusing on that word would
        decide on a designation (GDP-8).  What is refused is the property that
        actually harms: no production path left for the crafter.
        """
        if DeliveryContinuationRunner._mutable_targets(facts):
            return None
        oracle = facts.acceptance_paths[0]
        declared = ", ".join(path for path, _ in facts.target_decisions)
        return DeliveryContinuationRunner._fail(
            Disposition.Indeterminate,
            "NoMutableProductionTarget",
            f"targets declares only the acceptance oracle ({declared}), so no "
            f"production path is mutable for the crafter and the oracle "
            f"{oracle} never is",
            f"have DESIGN declare in targets at least one production path "
            f"other than the oracle {oracle}; when this run derived before the "
            "bind the value stays unbound and re-running re-elicits DESIGN for "
            "it, but when the authority is ALREADY bound no rerun can, so "
            "delete .nwave/des/handover.json to re-elicit DESIGN for this "
            "Request -- the generated artifacts themselves are never removed",
        )

    def _validate_bound_scopes(
        self, root: Path, stored: StoredHandover
    ) -> DeliveryOutcome | None:
        """Reject equal evidence only across incomparable forward-safe ROOTS.

        ADR-SSOT-002 §4 names two incomparable ready ROOTS, so comparability
        is asked of `batch[0]`, which `_forward_batches` seeds and keeps
        first.  A member orders across a foreign root without saying anything
        about the two roots, so admitting on any member would drop the very
        decomposition error this refuses.  Every member carries one
        `_batch_key` and therefore the root's own scope, so the roots decide
        the whole comparison.  A partial overlap across an ordered dependency
        stays separate, and the forward batch order already runs it in turn.
        """
        bound: list[tuple[str, AuthorityFacts]] = []
        for value in stored.values:
            if value.authority is None:
                continue
            design = self._derive(root, value.authority)
            if isinstance(design, DeliveryOutcome):
                return design
            bound.append((value.observation, design))
        batches = self._forward_batches(stored, bound)
        for index, batch in enumerate(batches):
            locators = {design.locator for _, design in batch}
            scope = {
                path
                for _, design in batch
                for path in (
                    *design.acceptance_paths,
                    *(target for target, _ in design.target_decisions),
                )
            }
            for other in batches[index + 1 :]:
                other_locators = {design.locator for _, design in other}
                other_scope = {
                    path
                    for _, design in other
                    for path in (
                        *design.acceptance_paths,
                        *(target for target, _ in design.target_decisions),
                    )
                }
                if (
                    locators.intersection(other_locators)
                    or scope.intersection(other_scope)
                ) and not self._comparable(stored, batch[0][0], other[0][0]):
                    return self._fail(
                        Disposition.Indeterminate,
                        "ValueAuthorityOverlap",
                        "independent authority batches claim the same locator or acceptance/target path",
                        "bind disjoint durable value authority",
                    )
        return None

    @staticmethod
    def _comparable(stored: StoredHandover, one: str, other: str) -> bool:
        """Whether one graph edge chain already orders these two observations.

        Reachability is read straight off the persisted `dependencies`, which
        `read_handover` admits only in topological order, so the relation is
        acyclic by construction and no cycle can pass for an ordering.
        """
        return DeliveryContinuationRunner._dependency_path(
            stored, one, other
        ) or DeliveryContinuationRunner._dependency_path(stored, other, one)

    @staticmethod
    def _dependency_path(stored: StoredHandover, start: str, target: str) -> bool:
        dependencies = {
            value.observation: value.dependencies for value in stored.values
        }
        pending = list(dependencies.get(start, ()))
        seen: set[str] = set()
        while pending:
            current = pending.pop()
            if current == target:
                return True
            if current not in seen:
                seen.add(current)
                pending.extend(dependencies.get(current, ()))
        return False

    #: The shim the runner writes so a declared bare `des` resolves to the
    #: CANDIDATE.  Pure Python, never a shell script (portability rule): the
    #: interpreter is the runner's own, and the candidate's source directory is
    #: inserted at `sys.path[0]` -- ahead of any editable-install `.pth`, which
    #: is only processed at site-packages time.
    _CANDIDATE_SHIM = (
        "import sys\n"
        "\n"
        "sys.path.insert(0, {source!r})\n"
        "\n"
        "from des.cli.__main__ import main\n"
        "\n"
        "raise SystemExit(main())\n"
    )

    #: The report variable and the module name of the SESSION PROBE: a pytest
    #: plugin the runner writes into a temporary directory, exactly as it writes
    #: the interpreter shims, and reaches through `PYTEST_ADDOPTS` so the
    #: DECLARED ARGV is never rewritten.  A model's declared verification
    #: command is a fact the run records verbatim; editing it to carry a `-p`
    #: would hand every later reader an argv nobody wrote.
    _EXERCISED_REPORT_VAR = "NWAVE_EXERCISED_MODULES_REPORT"
    _EXERCISED_PROBE_MODULE = "nwave_exercised_modules_probe"

    #: Source and not a shipped package file, for the reason `_CANDIDATE_SHIM`
    #: is source too: it must reach a child interpreter that may be the
    #: subject's own `.venv`, where `des` is not importable, and it must not
    #: depend on the distribution whitelist having included one more file.
    #: It reports every loaded file and filters nothing; which of them are the
    #: subject's PRODUCT is measured against the candidate root and the declared
    #: test paths, in one place, by `exercised_modules`.
    _EXERCISED_PROBE = (
        "import os\n"
        "import sys\n"
        "\n"
        "\n"
        "def pytest_sessionfinish(session, exitstatus):\n"
        "    destination = os.environ.get({variable!r})\n"
        "    if not destination:\n"
        "        return\n"
        "    loaded = set()\n"
        "    for module in list(sys.modules.values()):\n"
        "        origin = getattr(module, '__file__', None)\n"
        "        if origin:\n"
        "            loaded.add(os.path.realpath(origin))\n"
        "    with open(destination, 'w', encoding='utf-8') as report:\n"
        "        report.write(chr(10).join(sorted(loaded)))\n"
    )

    #: The shims the runner writes so a declared INTERPRETER name resolves to the
    #: interpreter `_subject_interpreter` resolved.  Pure Python, never a shell
    #: script (portability rule).  ``os.execv`` and not a subprocess: the child
    #: REPLACES the shim, so its exit status and any signal that kills it reach
    #: the runner unchanged, and no wrapper process sits between them.  The
    #: target is ``sys.executable`` by ABSOLUTE path, so a shim can never resolve
    #: through `PATH` to itself.
    _INTERPRETER_SHIM = (
        "import os\n"
        "import sys\n"
        "\n"
        "os.execv({executable!r}, [{executable!r}, *{prefix!r}, *sys.argv[1:]])\n"
    )

    #: Declared name -> the argv prefix the runner's interpreter receives.  A
    #: model declares its test runner in whichever of these spellings is natural
    #: (`python -m pytest`, `python3 -m pytest`, `pytest`); which of them this
    #: box happens to carry is not a fact the model can know, and resolving a
    #: name is enactment (`boundary:software-measures-model-decides`).
    _INTERPRETER_SHIMS: ClassVar[dict[str, tuple[str, ...]]] = {
        "python": (),
        "python3": (),
        "pytest": ("-m", "pytest"),
    }

    #: Where a subject DECLARES its own test environment, in the two spellings
    #: a virtual environment carries.  Only Python is a runtime dependency, so
    #: this reads the filesystem the subject already built and never invokes
    #: `uv` or any other builder.
    _SUBJECT_INTERPRETERS: ClassVar[tuple[tuple[str, ...], ...]] = (
        (".venv", "bin", "python"),
        (".venv", "Scripts", "python.exe"),
    )

    #: The directory name the two spellings above share -- the one thing an
    #: ephemeral candidate worktree is missing when a model declares the
    #: venv-relative form the subject's own briefs use.
    _SUBJECT_VENV = ".venv"

    @staticmethod
    def _subject_interpreter(subject: Path) -> tuple[str, str]:
        """The interpreter the SUBJECT declares, or the runner's own, named.

        MEASURED, run 19 (2026-09-05 07:40): `NATIVE-RUNTIME` reported
        `python=/usr/bin/python3`, because the installed runner
        (`~/.claude/bin/des`) runs under the system interpreter and the shims
        targeted `sys.executable`.  The declared `python -m pytest ...` started,
        collected nothing and exited 4 on `Unknown config option: asyncio_mode`:
        the system interpreter carries none of the subject's test dependencies,
        which live in the `.venv` the subject built at its own root.  The runner
        handed that to the crafter as a finding, the crafter answered
        implementation-correct / verification-inconclusive, and the run ended
        `Indeterminate` -- two paid turns for a defect of FORM, which
        `boundary:software-measures-model-decides` bills to the software.

        The fact this decides over is PRIMITIVE: the path exists and the kernel
        will start it, or it will not.  Not the NAME (GDP-8) -- a `.venv`
        holding an unstartable file is not a declaration, and reading the
        designation would convert a working fallback into a refused spawn.

        Incompleteness degrades LOUD rather than being filled in: a subject that
        declares nothing gets `sys.executable`, and the returned SOURCE is
        printed so an operator can tell the two apart.  That is the entire
        difference between this and run 19, where the interpreter was reported
        and its provenance was not.
        """
        for parts in DeliveryContinuationRunner._SUBJECT_INTERPRETERS:
            declared = subject.joinpath(*parts)
            if declared.is_file() and os.access(declared, os.X_OK):
                return str(declared), "subject-venv"
        return sys.executable, "runner"

    #: What `_link_subject_venv` observed, printed verbatim in the operator
    #: line.  A bool could not carry the three skips apart, and the docstring
    #: claiming the limit "degrades loud" while nothing printed it was the
    #: review finding that forced this.
    _VENV_LINKED = "linked"
    _VENV_CANDIDATE_OWNS = "skipped:candidate-declares-its-own"
    _VENV_SUBJECT_DECLARES_NONE = "skipped:subject-declares-none"
    _VENV_PLATFORM_REFUSED = "skipped:platform-refused"

    @staticmethod
    def _link_subject_venv(subject: Path, candidate: Path) -> str:
        """Carry the subject's declared environment INTO the candidate worktree.

        Two faces of one cause were measured on 2026-09-05.  The venv-relative
        form `.venv/bin/python -m pytest`, which this subject's own briefs and
        ADRs name, was refused because an ephemeral candidate worktree ships no
        `.venv`; the bare form was then admitted and ran under the wrong
        interpreter.  Resolving the shims (`_subject_interpreter`) answers the
        second and leaves the first refused for a path that DOES exist one
        directory up.

        A LINK, not an argv rewrite.  Rewriting would mean pattern-matching the
        model's declared spellings -- `.venv/bin/python`, `./.venv/bin/python`,
        `.venv\\Scripts\\python.exe` -- which is a surrogate for "the model meant
        the subject's environment" and decides over a DESIGNATION.  The link
        makes the candidate's FILESYSTEM carry the subject's declaration, so
        every path under `.venv` resolves, not only the one spelling a rewrite
        was keyed on, and nothing inspects what the model wrote.

        THREE WORLDS leave the link unmade, and they are NOT one condition: a
        candidate that already declares its own environment (nothing to add, and
        overwriting it would replace the operator's environment with another
        one), a subject that declares none (nothing to link), and a platform
        that refuses symlinks -- Windows without the privilege.  Only the third
        is a lost guarantee, and even there the shims still reach the subject's
        interpreter, so what erodes is the literal path and not the
        verification.  The returned WORLD is printed in `NATIVE-RUNTIME` and
        decides the HOW of a refused spawn, so the promise the runner makes to
        the model is a function of what it MEASURED rather than of what this
        method usually manages.
        """
        declared = subject / DeliveryContinuationRunner._SUBJECT_VENV
        linked = candidate / DeliveryContinuationRunner._SUBJECT_VENV
        if linked.exists() or linked.is_symlink():
            return DeliveryContinuationRunner._VENV_CANDIDATE_OWNS
        if not declared.is_dir():
            return DeliveryContinuationRunner._VENV_SUBJECT_DECLARES_NONE
        try:
            linked.symlink_to(declared, target_is_directory=True)
        except OSError:
            return DeliveryContinuationRunner._VENV_PLATFORM_REFUSED
        return DeliveryContinuationRunner._VENV_LINKED

    @staticmethod
    def _unlink_subject_venv(candidate: Path) -> None:
        """Remove the link at the end of the verification that needed it.

        Git unlinks a symlink rather than descending through it, so leaving this
        to `worktree remove` would very probably be safe -- and "very probably"
        is the wrong standard for a mechanism whose failure mode is deleting the
        subject's real environment.  The runner made this link; the runner
        removes it, and Git never meets it.

        Paired with the link inside :meth:`_native`, so the link lives exactly
        as long as the commands that may resolve through it and no cleanup path
        can be reached without passing it (GDP-0).  Removing it a SECOND time in
        the worktree teardown would be a no-op standing in for the guarantee
        rather than providing it.
        """
        linked = candidate / DeliveryContinuationRunner._SUBJECT_VENV
        if linked.is_symlink():
            with contextlib.suppress(OSError):
                linked.unlink()

    #: The directory an ephemeral candidate worktree is missing for the SECOND
    #: class of measurement precondition: the optional structural index the
    #: code-fact composition reads. The public composition has no such index.
    #: The provider owns the name so this runner cannot accidentally link an
    #: unrelated analysis cache.
    _SUBJECT_INDEX = CodeFactChain.optional_index_dir

    #: What `_link_subject_index` observed, printed verbatim in the operator
    #: line.  The LINKED world names WHICH directory, because the name is not
    #: this module's to state and an operator reading `linked` alone could not
    #: tell which precondition was built.
    _INDEX_LINKED_PREFIX = "linked:"
    _INDEX_CANDIDATE_OWNS = "skipped:candidate-declares-its-own"
    _INDEX_ABSENT = "skipped:absent"
    _INDEX_NOT_IGNORED = "skipped:not-ignored"
    _INDEX_IGNORE_UNOBSERVED = "skipped:ignore-unobserved"
    _INDEX_PLATFORM_REFUSED = "skipped:platform-refused"

    def _link_subject_index(self, subject: Path, candidate: Path) -> str:
        """Carry the subject's IGNORED structural index INTO the candidate.

        MEASURED, runs 20 and 27 (2026-09-05/06).  The candidate is an ephemeral
        worktree, so it holds the tracked bytes and nothing else.  Both the
        declared verification argv and the Request stimulus of run 27 were
        `des code-fact query.callers-of resolve_declared_capability --root .`,
        and both answered `provider: textsearch, confidence: noisy` -- not
        because the delivered code was wrong, but because the index that tier
        reads is ignored by Git and therefore did not exist in the tree the
        commands ran in.  The examiner read the noisy answer as "promise not
        observed on the product" and refused candidate `77b9e120c`; the SAME
        candidate, verified by hand in a tree where the index was reachable,
        answered with a resolved provider and the real call sites.  Two runs paid
        for a defect of PRECONDITION, which the
        `boundary:software-measures-model-decides` clause bills to the software.

        Same class as `_link_subject_venv`, and deliberately the same shape: the
        runner CARRIES what the subject already has, and materialises nothing on
        the model's behalf.  It does not regenerate the index, because building
        the index is a decision about what the graph should contain and that is
        the model's; making an existing directory reachable is enactment.

        WHY ONE NAME AND NOT A SURVEY of every ignored top-level directory.  The
        widest criterion that could be written -- ignored, and named by a
        declared argv or by the Request stimulus -- does NOT cover the run this
        repairs: neither of run 27's argv mentions the directory at all, they
        name the `des code-fact` PORT and the port opens the directory itself.
        So the discriminating fact is "the code-fact port reads it", which is a
        constant in the tier that owns it, imported above.  Linking every
        ignored directory instead would carry build outputs and caches nothing
        under verification reads, and would make the candidate's tree a function
        of the operator's leftovers (GDP-10: the narrowest rule that covers the
        measured defect).

        FIVE WORLDS leave the link unmade and they are not one condition.  A
        candidate that ships its own index (linking would shadow the bytes under
        verification with the subject's); a subject that has none (nothing to
        carry); a directory Git TRACKS, which the checkout already placed in the
        candidate at the right revision; an ignore rule Git could not be asked
        about, where the runner claims neither ignored nor tracked (GDP-6 --
        reporting `not-ignored` for a non-answer would assert a property never
        observed); and a platform refusing symlinks.  Each reaches
        `NATIVE-RUNTIME` under its own name, so an operator reading a noisy
        code-fact answer can tell which of them produced it.
        """
        name = DeliveryContinuationRunner._SUBJECT_INDEX
        if name is None:
            return DeliveryContinuationRunner._INDEX_ABSENT
        declared = subject / name
        linked = candidate / name
        if linked.exists() or linked.is_symlink():
            return DeliveryContinuationRunner._INDEX_CANDIDATE_OWNS
        if not declared.is_dir():
            return DeliveryContinuationRunner._INDEX_ABSENT
        observed = self._git(subject, "check-ignore", "-q", "--", name)
        if observed.unanswered is not None or observed.returncode > 1:
            return DeliveryContinuationRunner._INDEX_IGNORE_UNOBSERVED
        if observed.returncode:
            return DeliveryContinuationRunner._INDEX_NOT_IGNORED
        try:
            linked.symlink_to(declared, target_is_directory=True)
        except OSError:
            return DeliveryContinuationRunner._INDEX_PLATFORM_REFUSED
        return f"{DeliveryContinuationRunner._INDEX_LINKED_PREFIX}{name}"

    @staticmethod
    def _unlink_subject_index(candidate: Path) -> None:
        """Remove the link at the end of the verification that needed it.

        The reasoning of :meth:`_unlink_subject_venv` verbatim, on a directory
        whose failure mode is the same: the runner made the link, so the runner
        removes it and no Git command ever meets it.
        """
        if DeliveryContinuationRunner._SUBJECT_INDEX is None:
            return
        linked = candidate / DeliveryContinuationRunner._SUBJECT_INDEX
        if linked.is_symlink():
            with contextlib.suppress(OSError):
                linked.unlink()

    @staticmethod
    def _write_shim(path: Path, body: str, interpreter: str) -> None:
        path.write_text(f"#!{interpreter}\n{body}", encoding="utf-8")
        path.chmod(0o755)

    @staticmethod
    def _arm_interpreter_shims(shims: Path, interpreter: str) -> list[str]:
        """Resolve selected Python command names through the subject interpreter."""
        for name, prefix in DeliveryContinuationRunner._INTERPRETER_SHIMS.items():
            DeliveryContinuationRunner._write_shim(
                shims / name,
                DeliveryContinuationRunner._INTERPRETER_SHIM.format(
                    executable=interpreter, prefix=prefix
                ),
                # The trampoline runs on the RUNNER's interpreter, a real binary,
                # and only its execv reaches the subject's.  With the subject's as
                # the shebang, a target the kernel will not use as an interpreter
                # (a `#!` script on XNU, a non-executable format anywhere) made
                # execve fail with ENOEXEC and subprocess resumed its PATH search:
                # the next `python` on PATH answered, exit 0, while NATIVE-RUNTIME
                # said subject-venv.  From inside the trampoline the same refusal
                # is an OSError and a non-zero exit, never another interpreter.
                sys.executable,
            )
        return list(DeliveryContinuationRunner._INTERPRETER_SHIMS)

    @staticmethod
    def _uses_python(argv: tuple[str, ...]) -> bool:
        name = Path(argv[0]).name.lower()
        return (
            name in {"python", "python3", "python.exe", "python3.exe", "des", "des.exe"}
            or name.startswith("python3.")
            or invokes_pytest(argv)
        )

    @staticmethod
    def _candidate_runtime(
        root: Path,
        shims: Path,
        subject: Path,
        subject_links: str,
        argv: tuple[str, ...],
    ) -> dict[str, str]:
        """Bind the selected runtime to this tree without rewriting declared argv."""
        env = dict(os.environ)
        armed: list[str] = []
        interpreter: str | None = None
        provenance = "not-selected"
        source = root / "src"
        if DeliveryContinuationRunner._uses_python(argv):
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            interpreter, provenance = DeliveryContinuationRunner._subject_interpreter(
                subject
            )
            armed = DeliveryContinuationRunner._arm_interpreter_shims(
                shims, interpreter
            )
            if (source / "des" / "cli" / "__main__.py").is_file():
                inherited = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = os.pathsep.join(
                    [str(source), str(root), *([inherited] if inherited else [])]
                )
                DeliveryContinuationRunner._write_shim(
                    shims / "des",
                    DeliveryContinuationRunner._CANDIDATE_SHIM.format(
                        source=str(source)
                    ),
                    interpreter,
                )
                armed.append("des")
            path = env.get("PATH", "")
            env["PATH"] = os.pathsep.join([str(shims), *([path] if path else [])])
        elif Path(argv[0]).name in {"dune", "dune.exe"}:
            # Dune otherwise discovers the outer subject workspace when a
            # candidate checkout lives beneath it. Native cwd alone is not
            # a workspace-root witness; use Dune's supported root selector.
            env["DUNE_ROOT"] = str(root)
        print(
            f"NATIVE-RUNTIME: candidate={root} cwd={root} "
            f"executor={argv[0]} python={interpreter} python-source={provenance} "
            f"{subject_links} "
            f"shims={','.join(armed)}",
            file=sys.stderr,
        )
        return env

    def _native(
        self,
        root: Path,
        commands: tuple[tuple[str, ...], ...],
        subject: Path,
        extra_env: dict[str, str] | None = None,
        *,
        run: NativeRun = _DECLARED_NATIVE_RUN,
    ) -> tuple[NativeEvidence, ...] | DeliveryOutcome:
        """`root` is the tree under verification; `subject` is the repository.

        `run` carries the three facts that describe the EXECUTION rather than the
        commands: its provenance label, the candidate's changed paths, and
        whether a declared command's partial observation is kept.  Public
        verification executes design-declared vectors: a spawn the kernel will
        not start leaves the run with no verification, so it terminates.  The
        retained metadata does not create a separate Request-authored execution
        path.

        `extra_env` overlays the constructed environment for THIS execution
        only.  It exists for the pre-craft oracle run, which needs a report
        channel the declared argv does not carry; it is deliberately not a way
        to reach into the candidate verification, whose environment is the
        subject's own declaration and nothing else.

        Two parameters and not one, because they are two different facts and the
        ephemeral candidate worktree is exactly where they diverge: the code
        being verified lives in `root`, while the test environment the subject
        DECLARED lives at the subject's own root and is not copied into a
        worktree.  A default collapsing them would resolve `.venv` inside the
        worktree, which is the empty world run 19 measured, so the distinction
        is a required argument rather than an inferable one.
        """
        needs_python = any(self._uses_python(argv) for argv in commands)
        venv_link = (
            self._link_subject_venv(subject, root) if needs_python else "not-selected"
        )
        index_link = (
            self._link_subject_index(subject, root) if needs_python else "not-selected"
        )
        evidence: list[NativeEvidence] = []
        try:
            runtime_workspace = (
                tempfile.TemporaryDirectory(prefix="nwave-native-runtime-")
                if needs_python
                else contextlib.nullcontext(str(root))
            )
            with runtime_workspace as shims:
                for argv in commands:
                    observed = self._native_evidence(
                        root,
                        (argv,),
                        {
                            **self._candidate_runtime(
                                root,
                                Path(shims),
                                subject,
                                f"subject-venv-link={venv_link} "
                                f"subject-index-link={index_link}",
                                argv,
                            ),
                            **(extra_env or {}),
                        },
                        self._subject_test_paths(subject),
                        run,
                    )
                    if isinstance(observed, DeliveryOutcome):
                        return observed
                    evidence.extend(observed)
                    if not self._verification_writers_quiescent:
                        break
                return tuple(evidence)
        except OSError as error:
            failure = FailureDetail(
                "NativeRuntimeSetupUnavailable",
                f"the invocation-owned runtime/probe workspace could not be prepared for cwd {root}: {error}",
                "restore writable isolated temporary/runtime paths and the declared native toolchain; this setup failure does not establish a business defect",
            )
            if run.capture_incomplete and len(evidence) < len(commands):
                argv = commands[len(evidence)]
                evidence.append(
                    self._incomplete_native(
                        argv,
                        stdout="",
                        stderr=str(error),
                        failure=failure,
                        observed=CommandObservation(
                            origin=run.origin,
                            touches_test_paths=touches_test_paths(
                                argv, self._subject_test_paths(subject)
                            ),
                            exercised=self._exercised(
                                argv,
                                None,
                                root,
                                self._subject_test_paths(subject),
                                run.changed,
                            ),
                            cwd=str(root),
                        ),
                    )
                )
                return tuple(evidence)
            return self._fail(
                Disposition.Indeterminate, failure.what, failure.why, failure.how
            )
        finally:
            if venv_link == self._VENV_LINKED:
                self._unlink_subject_venv(root)
            if index_link.startswith(self._INDEX_LINKED_PREFIX):
                self._unlink_subject_index(root)

    def _native_evidence(
        self,
        root: Path,
        commands: tuple[tuple[str, ...], ...],
        env: dict[str, str],
        test_paths: tuple[str, ...] = (),
        run: NativeRun = _DECLARED_NATIVE_RUN,
    ) -> tuple[NativeEvidence, ...] | DeliveryOutcome:
        """The ordered execution itself, over an environment already built.

        Split from :meth:`_native` only so the constructed environment is a
        parameter rather than a hidden effect of the loop -- the shim directory
        lives exactly as long as the commands that may resolve through it.  It
        takes the same `NativeRun` its caller was given, so the two cannot
        disagree about the provenance a record is labelled with.
        """
        probe_workspace = (
            tempfile.TemporaryDirectory(prefix="nwave-exercised-")
            if any(invokes_pytest(argv) for argv in commands)
            else contextlib.nullcontext(None)
        )
        with probe_workspace as probe:
            reports = Path(probe) if probe is not None else None
            if reports is not None:
                (reports / f"{self._EXERCISED_PROBE_MODULE}.py").write_text(
                    self._EXERCISED_PROBE.format(variable=self._EXERCISED_REPORT_VAR),
                    encoding="utf-8",
                )
            evidence: list[NativeEvidence] = []
            observational = run.origin != DECLARED_ORIGIN
            for index, argv in enumerate(commands):
                touches = touches_test_paths(tuple(argv), test_paths)
                report = reports / f"{index}.txt" if reports is not None else None
                command_env = self._probed(argv, env, reports, report)
                cwd, declared_environment = self._native_execution_context(
                    root, command_env
                )
                executable = (
                    str((root / argv[0]).resolve())
                    if not Path(argv[0]).is_absolute() and os.sep in argv[0]
                    else shutil.which(argv[0], path=command_env.get("PATH"))
                )
                started = time.monotonic()
                try:
                    # Group ownership is requested for candidate
                    # verification measurement, but the OBSERVER is
                    # POSIX-only (os.killpg). On platforms without it the
                    # spawn runs plain and quiescence stays UNPROVEN --
                    # never inferred from plain spawn success.
                    requested_group = self._verification_measurement_group
                    effective_group = requested_group and os.name == "posix"
                    completed = spawn(
                        list(argv),
                        cwd=str(root),
                        capture_output=True,
                        text=True,
                        errors="replace",
                        env=command_env,
                        reap_process_group=effective_group,
                        quiesce_process_group=effective_group,
                    )
                    if requested_group and not effective_group:
                        self._verification_writers_quiescent = False
                except SpawnQuiescenceError as unquiescent:
                    self._verification_writers_quiescent = False
                    evidence.append(
                        self._incomplete_native(
                            tuple(argv),
                            stdout=self._stream_text(unquiescent.stdout),
                            stderr=self._stream_text(unquiescent.stderr),
                            failure=FailureDetail(
                                "VerificationWritersUnquiescent",
                                str(unquiescent),
                                "preserve native evidence and establish quiescence before "
                                "recovering the managed workspace; do not run another writer",
                            ),
                            observed=CommandObservation(
                                origin=run.origin,
                                touches_test_paths=touches,
                                exercised=self._exercised(
                                    argv, None, root, test_paths, run.changed
                                ),
                                duration_seconds=time.monotonic() - started,
                                cwd=cwd,
                                declared_environment=declared_environment,
                                executable=executable,
                            ),
                        )
                    )
                    break
                except OSError as refused:
                    duration_seconds = time.monotonic() - started
                    if observational:
                        evidence.append(
                            self._unobserved(
                                tuple(argv),
                                str(refused),
                                CommandObservation(
                                    origin=run.origin,
                                    touches_test_paths=touches,
                                    exercised=self._exercised(
                                        argv, None, root, test_paths, run.changed
                                    ),
                                    duration_seconds=duration_seconds,
                                    cwd=cwd,
                                    declared_environment=declared_environment,
                                    executable=executable,
                                ),
                            )
                        )
                        continue
                    refusal = self._verification_refused(tuple(argv), refused, root)
                    if not run.capture_incomplete:
                        return refusal
                    assert refusal.failure is not None
                    evidence.append(
                        self._incomplete_native(
                            tuple(argv),
                            stdout="",
                            stderr=f"not executed: {refused}",
                            failure=refusal.failure,
                            observed=CommandObservation(
                                origin=run.origin,
                                touches_test_paths=touches,
                                exercised=self._exercised(
                                    argv, None, root, test_paths, run.changed
                                ),
                                duration_seconds=duration_seconds,
                                cwd=cwd,
                                declared_environment=declared_environment,
                                executable=executable,
                            ),
                        )
                    )
                    break
                except subprocess.TimeoutExpired as unbounded:
                    duration_seconds = time.monotonic() - started
                    if observational:
                        evidence.append(
                            self._unobserved(
                                tuple(argv),
                                str(unbounded),
                                CommandObservation(
                                    origin=run.origin,
                                    touches_test_paths=touches,
                                    exercised=self._exercised(
                                        argv, None, root, test_paths, run.changed
                                    ),
                                    duration_seconds=duration_seconds,
                                    cwd=cwd,
                                    declared_environment=declared_environment,
                                    executable=executable,
                                ),
                            )
                        )
                        continue
                    # `SpawnTimeout` subclasses `subprocess.TimeoutExpired`, which is
                    # NOT an `OSError`, so the handler above never saw it and a fired
                    # bound on a declared verification command left the runner as a
                    # traceback.  Named separately because the operator's repair is
                    # the opposite one: not "restore the executable" but "find what
                    # the command is blocked on, or widen its bound".
                    failure = FailureDetail(
                        "VerificationUnbounded",
                        f"the declared verification command did not finish: {unbounded}",
                        "clear what the command is blocked on, or widen "
                        "NWAVE_GATE_RUN_TIMEOUT, then re-run",
                    )
                    if not run.capture_incomplete:
                        return self._fail(
                            Disposition.Indeterminate,
                            failure.what,
                            failure.why,
                            failure.how,
                        )
                    evidence.append(
                        self._incomplete_native(
                            tuple(argv),
                            stdout=self._stream_text(unbounded.output),
                            stderr=self._stream_text(unbounded.stderr),
                            failure=failure,
                            observed=CommandObservation(
                                origin=run.origin,
                                touches_test_paths=touches,
                                exercised=self._exercised(
                                    argv, None, root, test_paths, run.changed
                                ),
                                duration_seconds=duration_seconds,
                                cwd=cwd,
                                declared_environment=declared_environment,
                                executable=executable,
                            ),
                        )
                    )
                    break
                duration_seconds = time.monotonic() - started
                evidence.append(
                    NativeEvidence(
                        tuple(argv),
                        completed.returncode,
                        completed.stdout,
                        completed.stderr,
                        run.origin,
                        touches,
                        self._exercised(
                            argv,
                            self._read_report(report) if report is not None else None,
                            root,
                            test_paths,
                            run.changed,
                        ),
                        duration_seconds=duration_seconds,
                        cwd=cwd,
                        declared_environment=declared_environment,
                        executable=executable,
                    )
                )
            return tuple(evidence)

    @staticmethod
    def _unobserved(
        argv: tuple[str, ...], reason: str, observed: CommandObservation
    ) -> NativeEvidence:
        """A stimulus the runner could not start, recorded rather than dropped.

        Silence would be the worse degrade: a reader who never sees the argv
        cannot tell "the author named no stimulus" from "the author named one
        and it did not run" (GDP-6).
        """
        return NativeEvidence(
            argv,
            None,
            "",
            f"not executed: {reason}",
            observed.origin,
            observed.touches_test_paths,
            observed.exercised,
            duration_seconds=observed.duration_seconds,
            cwd=observed.cwd,
            declared_environment=observed.declared_environment,
            executable=observed.executable,
        )

    @staticmethod
    def _stream_text(value: str | bytes | None) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", "replace")
        return value or ""

    @staticmethod
    def _incomplete_native(
        argv: tuple[str, ...],
        *,
        stdout: str,
        stderr: str,
        failure: FailureDetail,
        observed: CommandObservation,
    ) -> NativeEvidence:
        """Keep a declared command's partial observation with its terminal fact.

        The two channels are keyword-only: both are strings, nothing enforces
        annotations at runtime, and a record whose stdout and stderr are swapped
        reads as a command that answered on the channel it never used.
        """
        return NativeEvidence(
            argv,
            None,
            stdout,
            stderr,
            observed.origin,
            observed.touches_test_paths,
            observed.exercised,
            incomplete=True,
            incomplete_what=failure.what,
            incomplete_why=failure.why,
            incomplete_how=failure.how,
            duration_seconds=observed.duration_seconds,
            cwd=observed.cwd,
            declared_environment=observed.declared_environment,
            executable=observed.executable,
        )

    @staticmethod
    def _native_execution_context(
        root: Path, env: dict[str, str]
    ) -> tuple[str, tuple[tuple[str, str], ...]]:
        """The PUBLIC display subset of the child environment, never its identity.

        A closed list of names cannot be the equality identity of a native child:
        `DOTNET_ROOT`, `NODE_OPTIONS`, `GOFLAGS`, `RUSTFLAGS` and every other
        toolchain selector a stack adds would fall outside it.  Equality is
        `_child_environment_digest`; this projection only shows a reader the
        nonsecret toolchain selections they most often ask about.
        """
        return (
            str(root),
            tuple(
                (name, env[name])
                for name in (
                    "PYTHONPATH",
                    "PYTEST_ADDOPTS",
                    "VIRTUAL_ENV",
                    "OPAM_SWITCH_PREFIX",
                    "DUNE_ROOT",
                    "DUNE_CACHE",
                    "DUNE_CACHE_ROOT",
                    "CC",
                    "CXX",
                    "CARGO_HOME",
                    "RUSTUP_HOME",
                    "JAVA_HOME",
                    "GOCACHE",
                    "GOMODCACHE",
                    "TMPDIR",
                )
                if name in env
            ),
        )

    #: The ONLY names ignored by the environment identity, each because its
    #: value is chosen per invocation and says nothing about what the child
    #: executes: invocation-owned scratch and evidence locations (a managed
    #: launcher makes a fresh directory under `NWAVE_EVIDENCE_DIR` or `TMPDIR`
    #: every run), the runner's own exercised-modules report channel, and the
    #: shell bookkeeping that differs between two hosts launching the same
    #: `des` command.  Any other name, whatever the stack, is identity.
    _VOLATILE_CHILD_ENVIRONMENT = frozenset(
        {
            "NWAVE_EVIDENCE_DIR",
            "TMPDIR",
            "TMP",
            "TEMP",
            _EXERCISED_REPORT_VAR,
            "PWD",
            "OLDPWD",
            "SHLVL",
            "_",
        }
    )

    #: A name that selects a credential.  Substring, case-insensitive: the
    #: identity must never carry a secret, even as a hash a dictionary can invert.
    _SECRET_CHILD_ENVIRONMENT_NAME = re.compile(
        r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH|(?:^|_)PAT(?:_|$)",
        re.IGNORECASE,
    )

    #: A value that looks like a credential whatever its name: well-known vendor
    #: prefixes, a JWT, a PEM private key, an HTTP credential, or a URL carrying
    #: `user:password@`.  Deliberately NOT a generic "long opaque string" rule: a
    #: nonsecret selector (a compiler or SDK name) can be any length, and
    #: dropping it would let a changed toolchain keep the same identity.
    _SECRET_CHILD_ENVIRONMENT_VALUE = re.compile(
        r"^(?:gh[pousr]_[A-Za-z0-9]{20,}"
        r"|github_pat_|glpat-|sk-[A-Za-z0-9_-]{16,}|xox[abprs]-"
        r"|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}"
        r"|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*$"
        r"|(?:Bearer|Basic|Token)\s+\S{8,})"
        r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
        r"|://[^/\s:@]+:[^/\s@]+@"
    )

    @classmethod
    def _child_environment_digest(cls, env: dict[str, str]) -> str:
        """The equality identity of the COMPLETE secret-safe child environment.

        Every name the child inherits participates, sorted, except the named
        per-invocation volatiles and the names or values that look like
        credentials.  So a changed `DOTNET_ROOT`, `NODE_OPTIONS` or `JAVA_HOME`
        changes the identity in any language, while a fresh evidence or scratch
        directory between two phases does not.  The digest is over the ambient
        environment every native child is built from: the runner's own
        per-invocation adaptations (interpreter shim directory, exercised-modules
        probe) are deterministic functions of it, the subject and the argv, and
        the executor path and digest are bound separately.
        """
        visible = sorted(
            (name, value)
            for name, value in env.items()
            if name not in cls._VOLATILE_CHILD_ENVIRONMENT
            and not cls._SECRET_CHILD_ENVIRONMENT_NAME.search(name)
            and not cls._SECRET_CHILD_ENVIRONMENT_VALUE.search(value)
        )
        return hashlib.sha256(
            json.dumps(visible, ensure_ascii=True, separators=(",", ":")).encode()
        ).hexdigest()

    @classmethod
    def _probed(
        cls,
        argv: tuple[str, ...] | list[str],
        env: dict[str, str],
        probe: Path | None,
        report: Path | None,
    ) -> dict[str, str]:
        """This ONE command's environment: the session probe, and where to write.

        ARMED ONLY FOR AN ARGV THAT NAMES PYTEST, and the environment is returned
        byte for byte otherwise.  A command that starts no session would gain a
        `PYTHONPATH` entry and a `PYTEST_ADDOPTS` it never reads, and the
        standing guarantee this class already carries -- a subject shipping no
        `des` leaves with the IMPORT PATH it inherited -- would be false for
        every one of them (GDP-10: no cost on a subject that has nothing to
        measure).

        One report file PER COMMAND, because one per execution would let the last
        pytest session in an ordered vector answer for every earlier one -- the
        same reason `_oracle_red` spends one `_native` call per oracle.

        `PYTEST_ADDOPTS` is APPENDED to, never replaced: the pre-craft oracle run
        already reaches the same variable for its JUnit report, and a subject may
        carry its own.  `PYTHONPATH` is prepended with the probe directory, which
        holds exactly one module, so nothing of the candidate's own import path
        is shadowed.
        """
        if not invokes_pytest(tuple(argv)):
            return env
        assert probe is not None and report is not None
        addopts = env.get("PYTEST_ADDOPTS", "")
        inherited = env.get("PYTHONPATH", "")
        return {
            **env,
            "PYTHONPATH": os.pathsep.join(
                [str(probe), *([inherited] if inherited else [])]
            ),
            "PYTEST_ADDOPTS": " ".join(
                part for part in (addopts, f"-p {cls._EXERCISED_PROBE_MODULE}") if part
            ),
            cls._EXERCISED_REPORT_VAR: str(report),
        }

    @staticmethod
    def _read_report(report: Path) -> str | None:
        """The probe's own bytes, or None when no session wrote any.

        None and not the empty string: an empty report is a session that finished
        having loaded nothing, and no report at all is a session that never
        finished.  Collapsing them would answer "imported nothing" about a run
        that crashed (GDP-6).
        """
        try:
            return report.read_text(encoding="utf-8")
        except OSError:
            return None

    @staticmethod
    def _exercised(
        argv: tuple[str, ...] | list[str],
        report: str | None,
        root: Path,
        test_paths: tuple[str, ...],
        changed: tuple[str, ...],
    ) -> ExercisedModules:
        """The measurement, against the candidate root the child actually ran in.

        `resolve()` and not the raw path, because the probe reports
        `os.path.realpath` of each loaded file: a temporary root reached through
        a symlinked `/tmp` would otherwise sit outside its own candidate and
        every product module would be discarded as another checkout's.
        """
        return exercised_modules(
            tuple(argv), report, str(root.resolve()), test_paths, changed
        )

    #: The only spellings of a test runner the runner GUARANTEES for every
    #: candidate.  Quoted in the HOW of a refused spawn, because a rejection that
    #: names no working form leaves the model to guess again at the next paid
    #: turn (GDP-3, GDP-4).
    _ADMITTED_VERIFICATION_FORM = (
        "declare the command with a name the runner provides for every "
        "candidate: `python`, `python3` and `pytest` all run the interpreter the "
        "subject declares in its own `.venv`, falling back to the runner's, so "
        "`python -m pytest <paths> -q` always resolves. `uv` is NOT a runtime "
        "dependency of DES and is never provided"
    )

    @staticmethod
    def _admitted_verification_form(root: Path) -> str:
        """The working forms, each one MEASURED in the tree it will run in.

        A review finding, closed on sight.  The venv-relative sentence promised
        unconditionally that `.venv/bin/python` resolves "through the link the
        runner places in the candidate worktree", while three measured worlds
        leave that link unmade -- a candidate carrying its own `.venv`, a subject
        declaring none, a platform refusing symlinks.  A HOW that promises a form
        which then fails at `execve` spends the next paid turn on a lie, which is
        the class `role-rejection-how-restates-the-why-and-names-no-action`
        closed from the other direction: not a HOW that says nothing, but one
        that says something untrue.

        Keyed on the PROPERTY and not on the link's outcome (GDP-8, and the
        reason this is not simply the boolean the review pointed at): the
        question is whether a venv-relative interpreter STARTS in this candidate,
        and it does in the `candidate-declares-its-own` world too, where no link
        was made at all.  Reusing `_subject_interpreter` against the CANDIDATE
        asks exactly that and answers it the same way for a linked venv and a
        native one.
        """
        form = DeliveryContinuationRunner._ADMITTED_VERIFICATION_FORM
        _, provenance = DeliveryContinuationRunner._subject_interpreter(root)
        if provenance != "subject-venv":
            return (
                f"{form}, and this candidate carries no `.venv`, so a "
                f"venv-relative interpreter does not resolve in it either"
            )
        return (
            f"{form}. The venv-relative form `.venv/bin/python -m pytest "
            f"<paths> -q` resolves in this candidate too: `NATIVE-RUNTIME` "
            f"reports `subject-venv-link` for how it got there"
        )

    def _verification_refused(
        self, argv: tuple[str, ...], refused: OSError, root: Path
    ) -> DeliveryOutcome:
        """A spawn the kernel would not start is a NON-OUTCOME, never a Retry.

        MEASURED, run 18 (2026-09-05 07:14): a declared `python -m pytest` on a
        box carrying only `python3` came back `Retry` /
        `VerificationUnavailable` with `[Errno 2] No such file or directory:
        'python'` and the HOW `restore verification`.  Both halves were wrong.
        `Retry` asserts that running the same argv again could answer
        differently, and an absent executable is the one world where it provably
        cannot -- the second run fails at `execve` identically.  And `restore
        verification` names no action: it restates the WHAT.

        So every refusal at `execve` is `Indeterminate`, and the three worlds
        `classify_spawn_refusal` separates -- shared with the git seam, which
        learnt the list by being falsified on it -- each get the repair they
        actually ask for.  `Indeterminate` preserves the handover and every WIP
        byte, so an operator who fixes the declaration re-runs and the graph
        resumes; nothing is lost by refusing to promise a retry.

        DECLARED LIMIT: a transient resource refusal (a fork that fails under
        memory pressure) WOULD differ on a second run, and lands here as
        `KernelRefused` whose HOW says so rather than as a `Retry` disposition.
        Splitting a fourth world for it would be a branch with no measured
        incident behind it (GDP-10), and `Indeterminate` already leaves the
        re-run available.
        """
        named = " ".join(argv[:4])
        world = classify_spawn_refusal(refused)
        if world is SpawnRefusal.ExecutableAbsent:
            return self._fail(
                Disposition.Indeterminate,
                "VerificationExecutableAbsent",
                f"the declared verification command `{named}` names "
                f"`{argv[0]}`, which does not resolve to an executable this box "
                f"can start: {refused}. Nothing ran, so no verification "
                f"evidence exists and re-running the same argv would fail "
                f"identically",
                (
                    self._admitted_verification_form(root)
                    if self._uses_python(argv)
                    and Path(argv[0]).name in {"python", "python3", "pytest"}
                    else f"restore the declared native executable `{argv[0]}` in its "
                    "selected project toolchain or PATH, or correct the DESIGN "
                    "verification recipe; retain its native argv and repository cwd"
                ),
            )
        if world is SpawnRefusal.ArgumentListTooLong:
            return self._fail(
                Disposition.Indeterminate,
                "VerificationArgumentListTooLong",
                f"the kernel refused `{named}`: the argument vector is too long "
                f"({sum(len(part) for part in argv)} bytes over {len(argv)} "
                f"arguments)",
                "declare fewer paths in one verification command, or split it "
                "into several commands: the kernel caps a single argument at "
                "131072 bytes and the whole vector near 2 MiB",
            )
        return self._fail(
            Disposition.Indeterminate,
            "VerificationUnavailable",
            f"the kernel refused to start `{named}` with "
            f"{errno.errorcode.get(refused.errno or 0, 'unknown errno')}: "
            f"{refused}",
            "read the errno named above: it is the kernel's own answer about "
            "why the command could not start, and the runner reports it "
            "verbatim rather than guessing the repair. If it names a transient "
            "resource shortage, re-run once the box has resources; the handover "
            "and every work-in-progress byte are preserved",
        )

    @staticmethod
    def _evidence_records(
        evidence: tuple[NativeEvidence, ...],
    ) -> list[dict[str, object]]:
        return [
            {
                "argv": item.argv,
                "exit": item.exit_status,
                "stdout": item.stdout,
                "stderr": item.stderr,
                "origin": item.origin,
                "touches_test_paths": item.touches_test_paths,
                "exercised_measure": item.exercised.measure,
                "exercised_product_modules": item.exercised.paths,
                "exercised_changed_targets": item.exercised.changed_targets,
                "incomplete": item.incomplete,
                "incomplete_what": item.incomplete_what,
                "incomplete_why": item.incomplete_why,
                "incomplete_how": item.incomplete_how,
                "duration_seconds": item.duration_seconds,
                "cwd": item.cwd,
                "declared_environment": (
                    dict(item.declared_environment)
                    if item.declared_environment is not None
                    else None
                ),
                "executable": item.executable,
            }
            for item in evidence
        ]

    @classmethod
    def _retain_native_failure_evidence(
        cls, root: Path, candidate: str, evidence: tuple[NativeEvidence, ...]
    ) -> str | None:
        """Retain a candidate's captured native records at its subject.

        Candidate worktrees are deliberately ephemeral, but their failed native
        observation is not: a refusal after cleanup must still let the author
        read the argv and both streams that actually ran. The subject's
        project-local diagnostic location is the existing durable substrate;
        the record reuses the same serialized form supplied to reviewers, so a
        second, lossy rendering cannot drift from the captured observation.

        ``None`` is deliberately distinct from a locator. A filesystem that
        will not retain the bytes must never cause a terminal to point at a
        record that does not exist.
        """
        directory = root / ".nwave" / "des" / "logs" / "native"
        execution_id = f"{time.time_ns()}-{os.getpid()}"
        payload = json.dumps(
            [
                {**record, "execution_id": execution_id}
                for record in cls._evidence_records(evidence)
            ],
            ensure_ascii=False,
            indent=1,
        ).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        name = (
            f"{candidate}-{digest}-"
            f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-"
            f"{os.getpid()}.json"
        )
        path = directory / name
        try:
            directory.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(
                prefix=f".{name}-", suffix=".tmp", dir=directory
            )
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(payload)
                Path(temporary).replace(path)
            except BaseException:
                with contextlib.suppress(OSError):
                    Path(temporary).unlink()
                raise
            if path.read_bytes() != payload:
                with contextlib.suppress(OSError):
                    path.unlink()
                return None
        except OSError:
            return None
        return path.relative_to(root).as_posix()

    @staticmethod
    def _subject_test_paths(subject: Path) -> tuple[str, ...]:
        """The subject's own declared test paths, read from its `pyproject.toml`."""
        try:
            text: str | None = (subject / "pyproject.toml").read_text(encoding="utf-8")
        except OSError:
            text = None
        return declared_test_paths(text)

    @staticmethod
    def _declared_commit_rule(root: Path) -> CommitMessageRule:
        """The repository's own `.gitlint`, or the documented defaults."""
        try:
            text = (root / ".gitlint").read_text(encoding="utf-8")
        except OSError:
            text = ""
        return CommitMessageRule.declared(text)

    @staticmethod
    def _declared_format_contract(root: Path) -> FormatContract | None:
        """The repository's own formatting declaration, or None when it has none."""

        def text(name: str) -> str | None:
            try:
                return (root / name).read_text(encoding="utf-8")
            except OSError:
                return None

        # `or` would be wrong here: an EMPTY `ruff.toml` is a declaration by
        # existence, and its falsy text must not fall through to the next rung.
        ruff_config = text("ruff.toml")
        if ruff_config is None:
            ruff_config = text(".ruff.toml")
        return declared_format_contract(text("pyproject.toml"), ruff_config)

    @staticmethod
    def _format_executable(contract: FormatContract) -> tuple[str, ...] | None:
        """The declared formatter's argv prefix, or None when it cannot be reached.

        The same two-rung ladder the repository's own quality hook walks: the
        tool on `PATH`, then the project's pinned copy through `uv`. Neither is
        a runtime dependency of DES (`CLAUDE.md`, Portability), so failing to
        resolve either is an answer -- INDETERMINATE at the caller -- and never
        a silent skip.
        """
        if shutil.which(contract.tool):
            return (contract.tool,)
        if shutil.which("uv"):
            return ("uv", "run", "--frozen", contract.tool)
        return None

    def _honour_format_contract(
        self, root: Path, changed: tuple[str, ...]
    ) -> bool | DeliveryOutcome:
        """Normalize the FORM of the bytes this run wrote. True when bytes moved.

        Scoped to `changed` -- the paths the candidate tree ACTUALLY differs
        from its base on -- and never to the authorized `owned` superset. Two
        properties depend on that and on nothing else. A pre-existing owned file
        the run never touched keeps whatever form the repository already carries,
        so the candidate never smuggles unrelated repairs into a delivered value.
        And `_finalize_request` measures foreign state with `owned` excluded, so
        a rewrite confined to changed OWNED paths is invisible to
        `_foreign_status` / `_foreign_bytes` by construction: the formatter can
        never present as drift, because every path it may touch is already
        outside what those two observe.

        The worktree file is rewritten, not a staged copy. The commit and the
        checkout must agree -- an operator whose `git status` is dirty after a
        Success would be told the runner left work behind.

        What is NOT repaired here is as deliberate as what is: a lint finding
        ruff cannot auto-fix, or one outside the FORM family the contract
        admits, is a claim about the code's MEANING. It is left for the
        whole-diff reviewer and CI, and it never becomes an integration
        failure raised by this method.
        """
        contract = self._declared_format_contract(root)
        if contract is None:
            return False
        reachable = tuple(
            path
            for path in contract.reaches(changed)
            if (root / path).is_file() and not (root / path).is_symlink()
        )
        if not reachable:
            return False
        argv = self._format_executable(contract)
        if argv is None:
            return self._fail(
                Disposition.Indeterminate,
                "FormatContractUnreachable",
                f"{contract.declaration} declares {contract.tool} as this "
                f"repository's formatter and the runner writes files it decides "
                f"the form of ({', '.join(reachable)}), but neither "
                f"{contract.tool} nor uv resolves on PATH, so the form of the "
                "candidate cannot be brought to what the repository declares",
                f"install {contract.tool} (uv sync restores the pinned copy this "
                "repository declares) and reissue the Request",
            )
        before = _workspace_bytes(root, reachable)
        # Every declared repair, in the declared order: the auto-repairable FORM
        # rules and then the formatter, because the second reflows what the
        # first reordered.  Honouring only one half integrates a candidate the
        # repository's own quality job rejects, which is the measured defect.
        for repair in contract.repairs:
            try:
                completed = spawn(
                    [*argv, *repair, "--", *reachable],
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
            except OSError as error:
                return self._fail(
                    Disposition.Indeterminate,
                    "FormatContractUnreachable",
                    f"{contract.declaration} declares {contract.tool} as this "
                    f"repository's formatter and it could not be run: {error}",
                    f"install {contract.tool} (uv sync restores the pinned copy "
                    "this repository declares) and reissue the Request",
                )
            if completed.returncode:
                return self._fail(
                    Disposition.Indeterminate,
                    "FormatContractUnhonoured",
                    f"the repair {' '.join(repair)} that {contract.declaration} "
                    f"declares exited {completed.returncode} over "
                    f"{', '.join(reachable)} and the form the repository "
                    "requires is therefore unestablished: "
                    + (completed.stderr or completed.stdout or "no diagnostic"),
                    f"repair the named file so {contract.tool} can read it, then "
                    "reissue the Request",
                )
        return _workspace_bytes(root, reachable) != before

    def _head(self, root: Path) -> str | DeliveryOutcome:
        """The commit every turn record and the one candidate are parented on."""
        observed = self._git(root, "rev-parse", "HEAD")
        if observed.returncode:
            return self._git_failure(
                observed,
                disposition=Disposition.Retry,
                what="GitUnavailable",
                how="restore Git",
            )
        return observed.stdout.strip()

    #: The ref grammar is SSOT in `des.domain.turn_record_ref`; this is the
    #: name every existing call site already reaches it by.
    _turn_ref = staticmethod(turn_ref)

    def _owned_tree(self, root: Path, base: str, paths: tuple[str, ...]) -> str | None:
        """`base`'s tree with the worktree bytes of `paths` overlaid, or None.

        The same plumbing `_candidate` uses and nothing more -- a temporary
        index, `read-tree`, `add`, `write-tree` -- so the real index, HEAD and
        the worktree are all untouched.  The tree is a PRIMITIVE measurement of
        the state those paths are in: equal tree, byte-identical paths.

        It carries `base` deliberately.  A record taken before an integration
        cannot match after one, so a stale record self-invalidates instead of
        authorizing a skip over bytes that have since moved.

        `None` means the measurement did not resolve, and it is the ONLY thing
        this returns for a Git that refused or never answered.  No new terminal
        code is emitted here, and that is a decision, not an omission: the sole
        consumer asks "may I skip work already done", so an unresolved
        measurement degrades to "no", which is what the runner does today.  The
        wrong state -- skipping a turn that is not complete -- stays
        unrepresentable, and a Git genuinely broken says so LOUD a few steps
        later, where `_candidate` builds the one candidate from the same four
        commands and owns the terminal codes for them.
        """
        descriptor, index = tempfile.mkstemp(prefix="nwave-turn-index-")
        os.close(descriptor)
        env = {**declared_child_environment(), "GIT_INDEX_FILE": index}
        try:
            read_tree = self._git(root, "read-tree", base, env=env)
            listed = self._git_bytes(root, "ls-tree", "-z", "--name-only", "-r", base)
            if listed is None:
                return None
            in_base = {
                path
                for path in (self._utf8(raw) for raw in listed.split(b"\0"))
                if path
            }
            present = {path: self._path_present(root / path) for path in paths}
            if any(seen is None for seen in present.values()):
                return None
            stageable = [path for path in paths if present[path] or path in in_base]
            staged = (
                self._git(root, "add", "--", *stageable, env=env)
                if stageable
                else read_tree
            )
            tree = self._git(root, "write-tree", env=env)
            if read_tree.returncode or staged.returncode or tree.returncode:
                return None
            return tree.stdout.strip()
        finally:
            with contextlib.suppress(OSError):
                Path(index).unlink()

    def _paths_tree(self, root: Path, paths: tuple[str, ...]) -> str | None:
        """The tree made by these present paths alone, or ``None``.

        Turn evidence is a fact about its owned paths, not about the repository
        commit it happened beside.  This intentionally starts with an empty
        index: unlike `_owned_tree`, it never carries unrelated base bytes.
        """
        descriptor, index = tempfile.mkstemp(prefix="nwave-turn-paths-index-")
        os.close(descriptor)
        env = {**declared_child_environment(), "GIT_INDEX_FILE": index}
        try:
            present = {path: self._path_present(root / path) for path in paths}
            if any(seen is None for seen in present.values()):
                return None
            stageable = [path for path in paths if present[path]]
            initialized = self._git(root, "read-tree", "--empty", env=env)
            staged = (
                self._git(root, "add", "--", *stageable, env=env)
                if not initialized.returncode and stageable
                else initialized
            )
            tree = self._git(root, "write-tree", env=env)
            if initialized.returncode or staged.returncode or tree.returncode:
                return None
            return tree.stdout.strip()
        finally:
            with contextlib.suppress(OSError):
                Path(index).unlink()

    def cited_design_sections(
        self, root: Path, stored: StoredHandover, value: HandoverValue
    ) -> tuple[tuple[str, str], ...] | None:
        """The unique cited DESIGN section identities for one value.

        Documents remain admitted through `_markdown_text` and exact tracked
        checks.  An empty or non-heading locator is not a citation; a cited
        document or section that cannot be measured makes the answer unknown.
        """
        locators: list[str] = []
        if stored.shared_design is not None:
            locators.append(stored.shared_design.authority_locator)
        authority = value.authority
        locator = (
            authority.authority_locator
            if isinstance(authority, DesignFacts)
            else authority
        )
        if isinstance(locator, str):
            locators.append(locator)
        consumed = []
        by_observation = {item.observation: item for item in stored.values}
        for dependency in value.dependencies:
            prerequisite = by_observation.get(dependency)
            if prerequisite is None or prerequisite.authority is None:
                return None
            if (
                isinstance(prerequisite.authority, DesignFacts)
                and design_facts_defect(prerequisite.authority) is not None
            ):
                return None
            consumed.append(prerequisite)
            bound = prerequisite.authority
            cited = bound.authority_locator if isinstance(bound, DesignFacts) else bound
            if cited:
                locators.append(cited)
        contract_paths: list[str] = []
        mutable = (
            {target.path for target in authority.targets}
            if isinstance(authority, DesignFacts)
            else set()
        )
        bound_facts = [
            item.authority
            for item in (value, *consumed)
            if isinstance(item.authority, DesignFacts)
        ]
        if stored.shared_design is not None:
            bound_facts.append(stored.shared_design.design)
        for facts in bound_facts:
            agreement = facts.agreement_analysis
            if agreement.applicability == "applicable":
                for party in agreement.parties:
                    if "#" in party.locator:
                        locators.append(party.locator)
                    else:
                        path = party.locator.rsplit(":", 1)[0]
                        if (
                            path not in mutable
                            and is_repository_relative_whole_file_locator(path)
                        ):
                            contract_paths.append(path)
        result: list[tuple[str, str]] = [
            (
                f"prerequisite:{item.observation}",
                hashlib.sha256(
                    json.dumps(
                        asdict(item), sort_keys=True, separators=(",", ":")
                    ).encode("utf-8")
                ).hexdigest(),
            )
            for item in consumed
        ]
        if value.design_semantic_sha256 is not None:
            result.append(("value-design-semantic", value.design_semantic_sha256))
        if stored.shared_design is not None:
            result.append(
                ("shared-design-semantic", stored.shared_design.semantic_sha256)
            )
        contracts = _authority_bytes(root, tuple(dict.fromkeys(contract_paths)))
        if contracts is None:
            return None
        result.extend(
            (f"contract:{path}", hashlib.sha256(raw).hexdigest())
            for path, raw in contracts
        )
        for locator in dict.fromkeys(locators):
            document, separator, heading = locator.partition("#")
            if not locator or not separator or not document or not heading:
                continue
            text = _markdown_text(root, document)
            # A DES authority is already admitted from its constructed bytes
            # during an in-progress delivery.  Requiring it to have been
            # committed would turn every pre-integration record into
            # ``uncertain`` and force paid replay before the one eventual
            # integration.  The section digest is the identity here; Git
            # tracking remains an integration concern, not a precondition for
            # measuring this current worktree authority.
            digest = None if text is None else authority_section_sha256(text, locator)
            if digest is None:
                return None
            result.append((locator, digest))
        return tuple(result)

    def _record_identity(
        self,
        root: Path,
        stored: StoredHandover,
        observation: str,
        design: AuthorityFacts,
    ) -> RecordIdentity | None:
        value = next(
            (item for item in stored.values if item.observation == observation), None
        )
        if value is None:
            return None
        return RecordIdentity.of(root, stored, value, design)

    def _record_pairs(
        self,
        root: Path,
        stored: StoredHandover,
        values: tuple[tuple[str, AuthorityFacts], ...],
    ) -> tuple[tuple[str, RecordIdentity], ...] | None:
        pairs = tuple(
            (observation, self._record_identity(root, stored, observation, design))
            for observation, design in values
        )
        if any(identity is None for _, identity in pairs):
            return None
        return tuple(
            (observation, identity)
            for observation, identity in pairs
            if identity is not None
        )

    def _turn_completed(
        self,
        root: Path,
        request: str,
        values: tuple[tuple[str, RecordIdentity], ...],
        role: str,
        paths: tuple[str, ...],
    ) -> bool:
        """Is every one of these values' `role` turn already a recorded fact?

        ``values`` are (observation, selected-revision identity) pairs.  A
        record is current only when its tree equals the owned tree AND its
        message names this value's own revision: the tree alone cannot see a
        selection that changed the criteria but not the bytes.

        Absent record, a workspace that no longer holds what the record
        describes, and a measurement that did not resolve all answer NO: the
        turn is invoked again, exactly as it is today.
        """
        recorded: set[str] = set()
        for observation, identity in values:
            ref = self._turn_ref(request, observation, role)
            observed = self._git(
                root, "rev-parse", "--verify", "--quiet", f"{ref}^{{tree}}"
            )
            if observed.returncode:
                return False
            message = self._git(root, "show", "-s", "--format=%B", ref)
            if message.returncode or message.stdout.strip() != self._turn_message(
                role, identity
            ):
                return False
            recorded.add(observed.stdout.strip())
        current = self._paths_tree(root, paths)
        return current is not None and recorded == {current}

    @staticmethod
    def _turn_message(role: str, identity: RecordIdentity) -> str:
        return (
            f"nwave turn: {role}\n\nselected-revision: {identity.revision}\n"
            f"design-sections: {identity.design_sections}"
        )

    def _turn_recorded(
        self, root: Path, request: str, observation: str, role: str
    ) -> bool:
        """Does a record for this value's `role` turn exist at all?"""
        ref = self._turn_ref(request, observation, role)
        return not self._git(root, "rev-parse", "--verify", "--quiet", ref).returncode

    def _record_turn(
        self, root: Path, target: TurnRecordTarget, *, role: str, tree: str
    ) -> None:
        """Write one turn commit per (observation, identity) and point its ref.

        The commit's job is to be found again and compared: its message names
        the value's selected-revision identity, so a record of another revision
        reads as moved bytes.  It claims to be no delivery commit.

        Recording is best-effort for the same reason reading is: a record that
        is not written costs the NEXT run one re-invoked turn and nothing else.

        `role` and `tree` are keyword-only: both are strings, nothing enforces
        annotations at runtime, and swapping them would commit a tree named by a
        role and key the ref by a tree sha.
        """
        env = declared_child_environment()
        for observation, identity in target.values:
            commit = self._git(
                root,
                "commit-tree",
                tree,
                "-p",
                target.base,
                "-m",
                self._turn_message(role, identity),
                env=env,
            )
            if commit.returncode:
                continue
            self._git(
                root,
                "update-ref",
                self._turn_ref(target.request, observation, role),
                commit.stdout.strip(),
                env=env,
            )

    def _drop_turn_records(
        self, root: Path, request: str, observations: tuple[str, ...], role: str
    ) -> None:
        """Unreference one role's record for these values."""
        for observation in observations:
            self._git(
                root, "update-ref", "-d", self._turn_ref(request, observation, role)
            )

    def _stamp_craft_record(
        self,
        root: Path,
        target: TurnRecordTarget,
        base_tree: str,
        *,
        mutable: tuple[str, ...],
        record_paths: tuple[str, ...],
    ) -> None:
        """Point a craft record at the CURRENT bytes, or drop it when there are none.

        "Wrote nothing" is judged over the ``mutable`` targets alone; the
        record itself is the tree over ``record_paths``.  Both are keyword-only:
        they are two path tuples, nothing enforces annotations at runtime, and
        swapping them would judge emptiness over the wrong set of bytes.

        A record buys back WORK, and a turn that contributed nothing has none to
        buy back.  Recording one would make the empty-owner repair -- "rerun the
        dispatch so the crafter changes its batch's mutable targets" -- reuse
        the same silent turn and refuse again, which is a rejection that lies.

        The same rule decides at the turn AND after the runner's own
        normalization, because normalization can reach that state honestly: a
        turn whose only edit was whitespace the declared formatter undoes wrote
        no bytes, and `_candidate` already says so about its own tree.
        """
        written = self._owned_tree(root, target.base, mutable)
        if written is None:
            return
        if written == base_tree:
            self._drop_turn_records(
                root, target.request, tuple(o for o, _ in target.values), _CRAFT_TURN
            )
            return
        tree = self._paths_tree(root, record_paths)
        if tree is None:
            return
        self._record_turn(root, target, role=_CRAFT_TURN, tree=tree)

    def _pre_candidate_currentness(
        self,
        root: Path,
        stored: StoredHandover,
        prepared: list[tuple[str, AuthorityFacts]],
    ) -> dict[str, tuple[bool, bool]]:
        """Snapshot, per value, whether its oracle/craft record was current.

        Taken BEFORE `_candidate` runs the declared formatter, so an external,
        unreviewed edit -- bytes nobody's oracle/craft turn produced -- reads
        as NOT current here, using the same completed-turn predicates the rest
        of the runner already trusts (`oracle_turn_complete`,
        `craft_turn_complete`).  `_refresh_turn_records` may only re-point a
        record this snapshot already found current: normalization can move
        bytes honestly, but it cannot make a record current that was already
        stale for a reason of its own.
        """
        snapshot: dict[str, tuple[bool, bool]] = {}
        for observation, design in prepared:
            ready = next(
                (item for item in stored.values if item.observation == observation),
                None,
            )
            if ready is None:
                snapshot[observation] = (False, False)
                continue
            snapshot[observation] = (
                self.oracle_turn_complete(root, stored, ready, design),
                self.craft_turn_complete(root, stored, ready, design),
            )
        return snapshot

    def _refresh_turn_records(
        self,
        root: Path,
        base: str,
        stored: StoredHandover,
        prepared: list[tuple[str, AuthorityFacts]],
        was_current: dict[str, tuple[bool, bool]],
    ) -> None:
        """Re-point this Request's records at bytes the RUNNER itself moved.

        `_candidate` honours the repository's declared format contract by
        rewriting the worktree, and it does so after every turn has been
        recorded.  Without this, in a repository that declares a formatter --
        this one does -- every record is stale the moment the first candidate is
        built, and the next resume rebuys the whole prefix although no role and
        no operator touched anything.  Measured on the resume oracle with a
        `ruff.toml` present: the resume re-invoked designer, reviewer and
        crafter over bytes only `ruff format` had changed.

        Only records that ALREADY exist are re-pointed, and only when
        ``was_current`` -- captured BEFORE `_candidate` normalized anything --
        says this value's record was still current at that time.  A record
        that was already stale before normalization (an oracle or craft file
        an operator edited outside `des oracle`/`des craft`) stays historical:
        the formatter moving further bytes is not a native witness that an
        unreviewed edit was ever reviewed.
        """
        observed_base = self._git(root, "rev-parse", f"{base}^{{tree}}")
        if observed_base.returncode:
            return
        base_tree = observed_base.stdout.strip()
        for observation, design in prepared:
            oracle_was_current, craft_was_current = was_current.get(
                observation, (False, False)
            )
            if oracle_was_current and self._turn_recorded(
                root, stored.request, observation, _ORACLE_TURN
            ):
                identity = self._record_identity(root, stored, observation, design)
                tree = self._paths_tree(root, design.acceptance_paths)
                if identity is not None and tree is not None:
                    self._record_turn(
                        root,
                        TurnRecordTarget(
                            base=base,
                            request=stored.request,
                            values=((observation, identity),),
                        ),
                        role=_ORACLE_TURN,
                        tree=tree,
                    )
            if craft_was_current and self._turn_recorded(
                root, stored.request, observation, _CRAFT_TURN
            ):
                pairs = self._record_pairs(root, stored, ((observation, design),))
                if pairs is None:
                    continue
                self._stamp_craft_record(
                    root,
                    TurnRecordTarget(base=base, request=stored.request, values=pairs),
                    base_tree,
                    mutable=self._mutable_targets(design),
                    record_paths=self._craft_record_paths(design),
                )

    def _release_turn_records(self, root: Path, stored: StoredHandover) -> None:
        """Unreference this Request's turn commits once it has integrated.

        No further ceremony is owed: the commits are ordinary objects outside
        the candidate's parent chain, so dropping the refs leaves them for
        `gc` on its own schedule.  A delete that does not answer is
        deliberately NOT terminal -- the Request has already integrated, and a
        surviving record cannot be mistaken for a live one, because every
        recorded tree carries the base it was taken from and integration moved
        that base.
        """
        for value in stored.values:
            for role in VALUE_TURN_ROLES:
                self._drop_turn_records(
                    root, stored.request, (value.observation,), role
                )
        # The verification records go with them, and they are the ones a NEXT
        # Request can actually collide with: they are keyed on the Request text
        # alone, so re-decomposing the same words in this repository used to
        # inherit a candidate belonging to a delivery already integrated.
        for role in (VERIFY_TURN, VERIFY_OUTCOME_TURN):
            self._drop_turn_records(root, stored.request, (stored.request,), role)
        ref = self._verify_upstream(root, stored)
        if ref is not None:
            self._git(root, "update-ref", "-d", ref)

    def _candidate(
        self, root: Path, base: str, owned: tuple[str, ...], facts: IntegrationFacts
    ) -> tuple[str, str] | DeliveryOutcome:
        descriptor, index = tempfile.mkstemp(prefix="nwave-delivery-index-")
        os.close(descriptor)
        # The declared environment plus the ONE variable this builder decides,
        # never `os.environ` plus that variable: the seam strips the
        # repository-selecting names only for callers that pass no `env`, and
        # this caller passes one, so starting from the ambient environment let
        # a parent's `GIT_DIR` or `GIT_WORK_TREE` redirect exactly the four
        # calls that WRITE.  Silent by construction -- no message, no non-zero
        # exit, just a candidate built against another repository.
        env = {**declared_child_environment(), "GIT_INDEX_FILE": index}
        try:
            read_tree = self._git(root, "read-tree", base, env=env)
            # A declared target the crafter never produced exists in neither the
            # worktree nor the base tree.  Staging it would abort the whole
            # candidate on a pathspec error; leaving it out lets the ordered
            # native verification observe the missing output instead.
            listed = self._git_bytes(root, "ls-tree", "-z", "--name-only", "-r", base)
            if listed is None:
                # Unknown base content is not an empty base: treating it as one
                # would silently drop a tracked deletion from the candidate.
                return self._fail(
                    Disposition.Retry,
                    "CandidateUnavailable",
                    f"the tracked content of {base} cannot be observed",
                    "restore Git and re-observe the expected-old tree",
                )
            in_base = {
                path
                for path in (self._utf8(raw) for raw in listed.split(b"\0"))
                if path
            }
            present = {path: self._path_present(root / path) for path in owned}
            if any(seen is None for seen in present.values()):
                # `Path.exists` lets EACCES through, so a directory that stops
                # being searchable mid-turn used to raise here.  Answering
                # "absent" instead would be worse than raising: an owned target
                # silently dropped from `stageable` is a candidate missing a
                # file the value declared, committed as if complete.
                return self._fail(
                    Disposition.Indeterminate,
                    "OwnedScopeUnobservable",
                    "whether every owned path exists cannot be observed on this "
                    "filesystem, so the candidate's scope is unknown",
                    "restore read access to the owned paths, then re-run",
                )
            stageable = [path for path in owned if present[path] or path in in_base]
            # Two passes at most.  The first stages what the roles wrote and
            # names the paths this run actually changed; the declared formatter
            # then normalizes exactly those, and the second pass re-stages the
            # normalized bytes.  A formatter is idempotent, so the second pass
            # is a fixed point and no third is reachable -- the loop is bounded
            # by construction, not by a retry budget.  Where the repository
            # declares no formatter, or none of the changed paths is one it
            # decides the form of, the first pass is the only one.
            tree_sha = ""
            changed_paths: tuple[str, ...] = ()
            for pass_index in range(2):
                staged = (
                    self._git(root, "add", "--", *stageable, env=env)
                    if stageable
                    else read_tree
                )
                if read_tree.returncode or staged.returncode:
                    # Through `_git_failure`, never `_fail`: a Refusal here is a
                    # verdict on the VALUE -- the roles produced a scope that
                    # cannot be staged -- and a git that never answered has said
                    # nothing about the value at all.  Charging an absent tool,
                    # an over-long pathspec or a fired bound to the work as a
                    # refusal is a judgement on a fact the runner never observed,
                    # so those cases come back Indeterminate with the seam's own
                    # reason instead (GDP-8).
                    return self._git_failure(
                        read_tree,
                        staged,
                        disposition=Disposition.Refusal,
                        what="CandidateStagingFailed",
                        how="reconcile owned scope",
                    )
                tree = self._git(root, "write-tree", env=env)
                expected = self._git(root, "rev-parse", f"{base}^{{tree}}")
                if tree.returncode or expected.returncode:
                    return self._git_failure(
                        tree,
                        expected,
                        disposition=Disposition.Retry,
                        what="CandidateUnavailable",
                        how="restore Git",
                    )
                # A staged owned tree equal to expected-old's carries no delta.
                # A commit whose only distinguishing content is that a run
                # happened would be workflow identity in a Git object, so none
                # is written.  Normalization can REACH this state honestly: a
                # turn whose only edit was whitespace the formatter undoes wrote
                # no delta, and saying so is more truthful than committing the
                # round trip.
                if tree.stdout.strip() == expected.stdout.strip():
                    return base, ""
                # The scope is decided on what the tree ACTUALLY changes, never
                # on the authorized `owned` superset a value may not have
                # touched.
                # `-z` is hardening, not a repair of a reachable route: Git
                # QUOTES any path outside the configured encoding, and a quoted
                # path names no scope.  I could not reach that form through any
                # accepted turn -- oracle, support and target paths are ASCII by
                # the locator grammar, and the one owned path that escapes it,
                # the bound authority document, is writable by NO role
                # (`AuthorityDrift` and `CraftScopeDrift` both refuse it).  `-z` costs nothing and removes the encoding
                # dependence outright, so it stays.
                changed = self._git_bytes(
                    root,
                    "diff-tree",
                    "-r",
                    "-z",
                    "--no-commit-id",
                    "--name-only",
                    expected.stdout.strip(),
                    tree.stdout.strip(),
                )
                if changed is None:
                    return self._fail(
                        Disposition.Retry,
                        "CandidateUnavailable",
                        "the candidate tree's changed paths cannot be observed",
                        "restore Git",
                    )
                tree_sha = tree.stdout.strip()
                changed_paths = tuple(
                    path
                    for path in (self._utf8(raw) for raw in changed.split(b"\0"))
                    if path
                )
                if pass_index:
                    break
                honoured = self._honour_format_contract(root, changed_paths)
                if isinstance(honoured, DeliveryOutcome):
                    return honoured
                if not honoured:
                    break
            rule = self._declared_commit_rule(root)
            message = attribute_commit_message(
                root,
                compose_integration_message(facts, base, changed_paths, rule),
            )
            # Composition is the guarantee; this is the honest-no branch for a
            # fact that cannot be made to fit without being falsified.  A commit
            # object is never written for a message CI would reject.  The defect
            # carries its OWN how: a fact is repaired where it is authored, a
            # declared rule is repaired in `.gitlint`, and one shared sentence
            # would have to lie about whichever branch it did not mean.
            nonconforming = rule.defect(message)
            if nonconforming is not None:
                return self._fail(
                    Disposition.Indeterminate,
                    "IntegrationMessageNonConforming",
                    "the composed integrated commit message is rejected by the "
                    f"repository's declared commit rule: {nonconforming.why}",
                    nonconforming.how,
                )
            commit = self._git(
                root,
                "commit-tree",
                tree_sha,
                "-p",
                base,
                "-m",
                message,
                env=env,
            )
            if commit.returncode:
                return self._git_failure(
                    commit,
                    disposition=Disposition.Retry,
                    what="CandidateUnavailable",
                    how="restore Git",
                )
            candidate = commit.stdout.strip()
            diff = self._git(root, "diff", "--binary", base, candidate)
            if diff.returncode:
                return self._git_failure(
                    diff,
                    disposition=Disposition.Retry,
                    what="CandidateUnavailable",
                    how="restore Git",
                )
            return candidate, diff.stdout
        finally:
            try:
                Path(index).unlink()
            except OSError:
                pass

    def _with_candidate_worktree(
        self,
        root: Path,
        candidate: str,
        commands: tuple[tuple[str, ...], ...],
        changed: tuple[str, ...] = (),
    ) -> tuple[str, tuple[NativeEvidence, ...]] | DeliveryOutcome:
        """Measure isolated source inside the project's configured workspace.

        Both isolation modes place real work under the configured workspace
        roots -- reuse in its managed workspace, cold as a registered
        candidate worktree -- never in a tmp/cache directory.
        """
        self._native_evidence_locator = None
        self._native_evidence_sha256 = None
        self._verification_writers_quiescent = True
        try:
            paths = resolve_workspace_paths(root)
            self.workspace_maintenance = maintenance = workspace_maintenance(
                paths, lease_held=self.verification_lease_held
            )
            if maintenance.within_limit is not True:
                # Configured-budget failure refuses ALL new native
                # measurement -- cold growth AND a warm reuse run (which
                # still grows generated caches). A budget that cannot be
                # PROVEN (unknown/protected blockers, unobservable state)
                # refuses exactly like an unmet one. A RECORDED history
                # stays the honestly separate old observation upstream.
                return self._fail(
                    Disposition.Indeterminate,
                    "WorkspaceBudgetExhausted",
                    "workspace budget is not proven within its configured "
                    f"limit and maintenance could not free owned cache: "
                    f"{maintenance.failure or 'budget unmet'}",
                    "remove or adopt the named unknown caches "
                    "(verification.reuse.workspace.adopt_outputs), or raise "
                    "verification.reuse.workspace.cache_limit_bytes",
                )
            if paths.outputs is not None:
                workspace = VerificationWorkspace(paths)
                workspace.acquire(candidate, lease_held=self.verification_lease_held)
                self._reusing_verification_workspace = True
                self._verification_measurement_group = True
                try:
                    result = self._measured_candidate(
                        root, candidate, workspace.directory, commands, changed
                    )
                    if self._verification_writers_quiescent:
                        workspace.finish()
                        # Post-measurement accounting: the workspace is idle,
                        # so automatic cleanup may run and the reported state
                        # is the FINAL usage, never the pre-run claim. The
                        # workspace owns the verification flock after a
                        # successful acquire -- pass that truth, or the post
                        # call would self-block and report a false
                        # "held elsewhere".
                        self.workspace_maintenance = workspace_maintenance(
                            paths, lease_held=True
                        )
                    return result
                finally:
                    self._reusing_verification_workspace = False
                    self._verification_measurement_group = False
                    workspace.release()
        except (OSError, ValueError) as error:
            return self._fail(
                Disposition.Indeterminate,
                "CandidateSourceChanged"
                if isinstance(error, CandidateSourceChanged)
                else "VerificationWorkspaceUnavailable",
                str(error),
                "repair the project verification.reuse declaration or "
                "the named owned workspace; establish quiescence before recovering "
                "interrupted execution. Remove the reuse declaration to select cold isolation",
            )
        try:
            directory = self._cold_candidate_directory(paths, root)
        except (OSError, ValueError) as error:
            return self._fail(
                Disposition.Indeterminate,
                "VerificationWorkspaceUnavailable",
                str(error),
                "place real candidate work inside the repository's configured "
                "workspace; repair verification.reuse.workspace before verifying",
            )
        common: Path | None = None
        try:
            added = self._git(
                root, "worktree", "add", "--detach", str(directory), candidate
            )
            if added.returncode:
                result = self._git_failure(
                    added,
                    disposition=Disposition.Retry,
                    what="CandidateCheckoutUnavailable",
                    how="restore Git worktree support",
                )
            else:
                # Creation is the ownership event: the receipt, not the Git
                # registry location, is what later authorizes maintenance
                # to force-remove this exact checkout. The receipt proves WHO
                # produced it; its phase, written idle only after the same
                # Core observed native quiescence the reuse workspace uses,
                # proves the last native generation finished.
                common = Path(
                    self._git(
                        root,
                        "rev-parse",
                        "--path-format=absolute",
                        "--git-common-dir",
                    ).stdout.strip()
                ).resolve()
                self._write_candidate_receipt(
                    directory, candidate, common, "materializing"
                )
                # Cold isolation owns its process group EXACTLY like the
                # reuse workspace: the measured child is its own session
                # leader, so reaping and observed quiescence apply to the
                # candidate's subtree and never to the caller's group. The
                # reset is a FINALLY over the whole measured region -- every
                # early return, error, and the happy path -- so the flag can
                # never leak into another step's spawns.
                self._verification_measurement_group = True
                try:
                    result = self._measured_candidate(
                        root, candidate, directory, commands, changed
                    )
                    if not self._verification_writers_quiescent:
                        # The receipt stays non-idle and the checkout stays
                        # in place: deleting it now would rmtree a worktree
                        # whose native writers were never proven stopped.
                        return self._candidate_writers_unquiescent(directory)
                    self._write_candidate_receipt(directory, candidate, common, "idle")
                    cleanup = self._remove_candidate_worktree(root, directory)
                    if cleanup is None:
                        # Post-measurement accounting on the now-clean
                        # workspace: the reported state is the FINAL usage,
                        # never the pre-run claim.
                        self.workspace_maintenance = workspace_maintenance(
                            paths, lease_held=self.verification_lease_held
                        )
                    return cleanup or result
                finally:
                    self._verification_measurement_group = False
        except BaseException:
            self._verification_measurement_group = False
            if not self._verification_writers_quiescent:
                return self._candidate_writers_unquiescent(directory)
            cleanup = self._remove_candidate_worktree(root, directory)
            if cleanup is not None:
                return cleanup
            raise
        # The checkout never materialized (add failed): nothing was
        # measured; remove only the known-owned EMPTY allocation.
        cleanup = self._remove_candidate_worktree(root, directory)
        return cleanup or result

    def _write_candidate_receipt(
        self, directory: Path, candidate: str, common: Path, phase: str
    ) -> None:
        """Bind one candidate receipt: who, where, which tree, which phase."""
        (directory / CANDIDATE_RECEIPT).write_text(
            json.dumps(
                {
                    "version": 1,
                    "candidate": candidate,
                    "common_git_dir": str(common),
                    "workspace": str(directory),
                    "phase": phase,
                }
            ),
            encoding="utf-8",
        )

    def _candidate_writers_unquiescent(self, directory: Path) -> DeliveryOutcome:
        return self._fail(
            Disposition.Indeterminate,
            "CandidateWritersUnquiescent",
            f"candidate worktree {directory} is kept: native writers were not "
            "proven quiescent, so its receipt stays non-idle and nothing was "
            "removed",
            f"stop the candidate process group, preserve any native evidence "
            f"under .nwave/des/logs/native, confirm {directory} is quiet, then "
            f"remove only this receipt-marked checkout ({CANDIDATE_RECEIPT} "
            "records the interrupted phase) before verifying again",
        )

    def _cold_candidate_directory(self, paths: WorkspacePaths, root: Path) -> Path:
        """A fresh, uniquely named candidate checkout under the configured root.

        The caller's checkout must share the workspace repository's common
        Git dir BEFORE anything is created: a worktree registered to a
        different repository would pollute the principal's workspace.
        """
        common = Path(
            self._git(
                root, "rev-parse", "--path-format=absolute", "--git-common-dir"
            ).stdout.strip()
        ).resolve()
        principal_common = Path(
            self._git(
                paths.root,
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ).stdout.strip()
        ).resolve()
        if common != principal_common:
            raise ValueError(
                f"configured workspace {paths.candidate} belongs to a different "
                "Git repository than the requesting checkout"
            )
        paths.candidate.mkdir(parents=True, exist_ok=True)
        return Path(
            tempfile.mkdtemp(prefix="nwave-candidate-", dir=paths.candidate)
        ).resolve()

    def _remove_candidate_worktree(
        self, root: Path, directory: Path
    ) -> DeliveryOutcome | None:
        try:
            removed = self._git(root, "worktree", "remove", "--force", str(directory))
            if not removed.returncode:
                return None
            # Checkout creation may have failed before Git registered the
            # directory. Remove only that known-owned EMPTY allocation; never
            # sweep, recursively erase unknown bytes, or prune other worktrees.
            registered = self._git(root, "worktree", "list", "--porcelain", "-z")
            if (
                not registered.returncode
                and f"worktree {directory}" not in registered.stdout.split("\0")
            ):
                try:
                    directory.rmdir()
                except FileNotFoundError:
                    pass
                return None
            detail = removed.stderr or removed.stdout
        except Exception as error:
            detail = f"{type(error).__name__}: {error}"
        return self._fail(
            Disposition.Indeterminate,
            "CleanupUnproven",
            f"candidate worktree {directory} could not be removed: {detail}",
            f"inspect candidate residue at {directory}; preserve any useful "
            "observations before removing this owned checkout",
        )

    @staticmethod
    def _decomposition(stored: StoredHandover) -> list[list[object]]:
        """The already-settled ordered value graph: observation and dependencies.

        The Product Owner decomposed the Request once and software persisted the
        result.  A role that judges ONE assigned value receives this graph so the
        completed decomposition is a fact it READS.  Without it the unit under
        judgement is not representable in the turn, and a model handed the raw
        Request has no way to tell an assigned slice from a bundle it should
        refuse -- the 2026-09-04 measured refusal of a well-formed value.
        """
        return [
            [value.observation, list(value.dependencies)] for value in stored.values
        ]

    @staticmethod
    def _typed_facts(design: AuthorityFacts) -> dict[str, object]:
        """Project the facts that the resolved authority actually declares."""
        facts: dict[str, object] = {
            "authority": design.locator,
            "targets": design.target_decisions,
            "paradigm": design.paradigm,
            "decisions": design.decisions,
            "oracle": design.acceptance_oracle_locator,
            "acceptance_supports": design.acceptance_paths[1:],
            "verification": [list(argv) for argv in design.native_verification_argvs],
            "oracle_verification_index": design.oracle_verification_index,
            "obligations": design.obligations,
            "architectural_tests": AuthorityFacts._decision_wire(
                design.architectural_tests
            ),
            "contract_tests": AuthorityFacts._decision_wire(design.contract_tests),
            "prefactoring": AuthorityFacts._decision_wire(design.prefactoring),
            "agreement_analysis": AuthorityFacts._decision_wire(
                design.agreement_analysis
            ),
            "reuse_analysis": AuthorityFacts._decision_wire(design.reuse_analysis),
            "impact_closure": AuthorityFacts._decision_wire(design.impact_closure),
            "required_verification": design.required_verification_argvs,
        }
        if design.public_oracle is not None:
            facts["public_oracle"] = asdict(design.public_oracle)
        if design.acceptance_obligations:
            facts["acceptance_obligations"] = tuple(
                {"id": item.id, "stimulus": item.stimulus, "expected": item.expected}
                for item in design.acceptance_obligations
            )
        if design.adr is not None:
            facts["adr"] = AuthorityFacts._decision_wire(design.adr)
        return facts

    @staticmethod
    def _shared(stored: StoredHandover) -> dict[str, object]:
        """The one shared feature DESIGN, rendered from the stored binding.

        Never through ``derive_authority`` (same reason as ``_inherited``), and
        empty when unbound so an unbound handover's prompts stay byte-identical.
        """
        bound = stored.shared_design
        if bound is None:
            return {}
        design = bound.design
        return {
            "shared_design": {
                "authority": bound.authority_locator,
                "semantic_sha256": bound.semantic_sha256,
                "targets": [
                    {"path": target.path, "decision": target.decision}
                    for target in design.targets
                ],
                "paradigm": design.paradigm,
                "decisions": list(design.decisions),
                "obligations": list(design.obligations),
                "architectural_tests": AuthorityFacts._decision_wire(
                    design.architectural_tests
                ),
                "contract_tests": AuthorityFacts._decision_wire(design.contract_tests),
                "prefactoring": AuthorityFacts._decision_wire(design.prefactoring),
                "agreement_analysis": AuthorityFacts._decision_wire(
                    design.agreement_analysis
                ),
                "reuse_analysis": AuthorityFacts._decision_wire(design.reuse_analysis),
                "impact_closure": AuthorityFacts._decision_wire(design.impact_closure),
                **(
                    {"public_oracle": asdict(design.public_oracle)}
                    if design.public_oracle is not None
                    else {}
                ),
                **(
                    {"adr": AuthorityFacts._decision_wire(design.adr)}
                    if design.adr is not None
                    else {}
                ),
            }
        }

    @classmethod
    def _shared_of(cls, handover_bytes: bytes) -> dict[str, object]:
        """``_shared`` for a site that holds only the frozen handover bytes."""
        stored = read_handover(handover_bytes)
        return {} if isinstance(stored, Blocked) else cls._shared(stored)

    @staticmethod
    def _prepared_facts(
        prepared: list[tuple[str, AuthorityFacts]],
    ) -> list[dict[str, object]]:
        """For every prepared value, exactly the facts its author received."""
        return [
            {
                "observation": observation,
                **DeliveryContinuationRunner._typed_facts(design),
            }
            for observation, design in prepared
        ]

    @staticmethod
    def _prepared_acceptance_paths(
        prepared: list[tuple[str, AuthorityFacts]],
    ) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                path for _, design in prepared for path in design.acceptance_paths
            )
        )

    #: The only two `pytest` exit statuses that describe a session which RAN to
    #: the end.  Every other one -- 2 interrupted, 3 internal error, 4 usage, 5
    #: nothing collected -- says the run did not get as far as an answer, which
    #: for an oracle IS the answer: it is broken, not red.
    _ORACLE_COMPLETED_EXITS = (0, 1)

    #: Request a report only for a declared Python command. A Python wrapper
    #: can reach pytest without naming it in argv; an unrelated native command
    #: receives no Python preparation. Explicit JUnit output flags are read
    #: separately, without rewriting argv or assigning pytest exit conventions.
    _ORACLE_REPORT_VAR = "PYTEST_ADDOPTS"

    #: The verdicts that REFUSE before one craft turn is paid.
    #:
    #: `broken` alone, and the omission of `green` is MEASURED rather than
    #: cautious.  Both incidents this step exists for -- runs 22 and 23,
    #: 2026-09-05 -- were broken oracles, and arming `broken` breaks nothing:
    #: 168 application unit tests and 67 `dispatch_owns_e2_e4` acceptance tests
    #: stay green.  Arming `green` refused EIGHT of those acceptance tests, and
    #: they are not sloppy fixtures.  They are four designed behaviours in which
    #: an oracle is legitimately green before any craft turn: a resumed run
    #: whose earlier craft bytes survived a failed integration, a value a
    #: sibling already delivered, the no-delta Request that writes no commit and
    #: still swaps, and the silent craft turn on an already-delivered value.
    #: Refusing those would convert the runner's most load-bearing property --
    #: resume -- into a Refusal, to prevent an incident nobody has measured
    #: (GDP-10: name the incident before shipping the restriction).
    #:
    #: The verdict is still COMPUTED, printed on the `ORACLE-RED` line of the
    #: host's terminal, and appended to the value's `oracle-witness` record
    #: (`_record_oracle_witness`), which the reviewer and examiner packets
    #: project: a value whose oracle was never observed RED is VISIBLE to the
    #: independent roles without being refused here.  The incident GDP-10 asked
    #: for is now named (codex retest 2026-10-01, durable-reservations: values
    #: 2-4 were crafted before their DESIGN, so their first oracle records were
    #: green and no RED was ever observed), yet refusing would not have
    #: produced a RED either: in the sibling case a forced remeasure made the
    #: host revert its own fix.  Arming it still needs the discriminator the
    #: four worlds above require -- whether the acceptance BYTES changed in
    #: this run -- which is not built here.
    _ORACLE_REFUSING = ("broken",)

    #: The HOW states only the MOVE, and deliberately claims nothing about what
    #: survived.  It used to end "this outcome preserved the handover and every
    #: WIP byte", which is the exact sentence `des.domain.orchestrator_terminal`
    #: was created to own: measured 2026-09-05 (run 20260905T062139Z-38400) that
    #: promise was FALSE on a path where no handover had ever existed, and a
    #: rejection that lies about the state it leaves behind is worse than a bare
    #: traceback.  Whether a graph survived is measured once, where the run ends,
    #: never asserted from inside it.
    _ORACLE_NOT_RED_HOW = (
        "RUN THE DECLARED ORACLE VECTOR from the repository root; use its "
        "native evidence to distinguish an unmet behavior from a setup, build "
        "or tooling failure. Repair the reported problem within the declared "
        "acceptance paths, then retry the oracle step"
    )

    #: The MOVE for an oracle whose vector asked for a report and produced none.
    #: The oracle's own bytes are not the suspect here -- nothing about them was
    #: observed -- so telling the author to repair assertions would be advice
    #: written for a different incident.  The `argv=` already printed on this
    #: oracle's `ORACLE-RED:` line is what makes the vector runnable by hand.
    _ORACLE_REPORT_ABSENT_HOW = (
        "RUN THE PRINTED VECTOR IN THE WORKSPACE and read its first lines -- the "
        "`argv=` on this oracle's `ORACLE-RED:` line, executed from the "
        "repository root, says why no session completed (measured: `No module "
        "named pytest`); install the runner under that interpreter or declare a "
        "verification vector whose interpreter carries it, then re-run the Request"
    )

    #: The HOW each refusing AXIS names.  Selecting on the axes that actually
    #: refused keeps a set that refused only on assertions emitting today's
    #: single sentence unchanged, and makes a mixed set state BOTH moves rather
    #: than give one of them advice written for the other.
    _ORACLE_REFUSAL_HOWS = {"junit-report-absent": _ORACLE_REPORT_ABSENT_HOW}

    #: The WHY each refusing AXIS adds to its per-oracle sentence.  Only an axis
    #: whose incident the bare diagnosis cannot explain appears here.
    _ORACLE_REFUSAL_WHYS = {
        "junit-report-absent": (
            "the runner asked this vector for a junit report and none was "
            "produced, so pytest did not complete a session under this "
            "interpreter (typically it is not installed there) and nothing "
            "about this oracle's own assertions was observed"
        )
    }

    @staticmethod
    def _junit_counts(report: Path) -> tuple[int, int, int] | None:
        """`tests / errors / failures`, or None when no report was produced.

        PRIMITIVE, not prose: these are attributes pytest writes itself, so the
        split between a test that RAN and failed and one that never ran is read
        rather than inferred from a summary line.  Absence is not zero -- a
        non-pytest runner, a pytest too old for the option, an interrupted
        session -- so it returns None and the caller degrades to the one axis it
        still holds instead of reading silence as success.
        """
        try:
            document = ElementTree.parse(report).getroot()
        except (OSError, ElementTree.ParseError):
            return None
        totals = [0, 0, 0]
        seen = False
        # `iter` yields the root itself when it matches, so both shapes the
        # `junit_family` settings produce -- a `testsuites` wrapper and a bare
        # `testsuite` -- are summed by the same walk.
        for suite in document.iter("testsuite"):
            seen = True
            for index, name in enumerate(("tests", "errors", "failures")):
                try:
                    totals[index] += int(suite.get(name, 0))
                except (TypeError, ValueError):
                    return None
        return (totals[0], totals[1], totals[2]) if seen else None

    #: Per-oracle ceiling on the failure text delivered to the judging roles.
    #: MEASURED against the incident this field exists for: the assertion line
    #: naming two different roots is under 300 bytes, and the longest single
    #: `longrepr` in this repository's own oracles is under 3 KiB, so 4 KiB
    #: carries the whole discriminating fact for every failure observed so far.
    #: It is DECLARED and the cut is MARKED, because a reader who cannot tell a
    #: short failure from a trimmed one has been told something false (GDP-6).
    _ORACLE_FAILURE_BUDGET = 4096

    @staticmethod
    def _junit_failures(report: Path) -> tuple[dict[str, str], ...] | None:
        """WHY each test in the report failed, read off the report's own elements.

        The SAME axis `_junit_counts` already reads, and deliberately no other:
        `message` and the `longrepr` body are attributes pytest writes, so no
        summary prose is parsed here and nothing is inferred from a line's
        shape.  The crash message comes FIRST and the body after it, so the
        one sentence that discriminates "the behaviour is missing" from "this
        oracle cannot pass as written" survives the ceiling.

        `None` is the absence of a readable report, which is not an absence of
        failures: the caller has already degraded its verdict to `exit-status
        -only` in that world and must not read silence as a clean run.
        """
        try:
            document = ElementTree.parse(report).getroot()
        except (OSError, ElementTree.ParseError):
            return None
        spoken: list[dict[str, str]] = []
        budget = DeliveryContinuationRunner._ORACLE_FAILURE_BUDGET
        omitted = 0
        for case in document.iter("testcase"):
            for kind in ("failure", "error"):
                for node in case.findall(kind):
                    if budget <= 0:
                        omitted += 1
                        continue
                    message = "\n".join(
                        part
                        for part in (node.get("message", ""), node.text or "")
                        if part.strip()
                    ).strip()
                    if len(message) > budget:
                        message = message[:budget] + "[...truncated]"
                    budget -= len(message)
                    classname = case.get("classname") or ""
                    name = case.get("name") or ""
                    spoken.append(
                        {
                            "test": f"{classname}::{name}" if classname else name,
                            "kind": kind,
                            "message": message,
                        }
                    )
        if omitted:
            spoken.append(
                {
                    "test": "",
                    "kind": "ceiling",
                    "message": (
                        f"{omitted} further failing tests are omitted at the "
                        f"{DeliveryContinuationRunner._ORACLE_FAILURE_BUDGET}-byte "
                        "per-oracle ceiling; run the oracle to read them all"
                    ),
                }
            )
        return tuple(spoken)

    @staticmethod
    def _oracle_verdict(
        exit_status: int | None,
        counts: tuple[int, int, int] | None,
        report_requested: bool,
        *,
        pytest_exit_status: bool | None = None,
    ) -> tuple[str, str]:
        """Classify evidence without assigning pytest exit semantics to other tools.

        A requested report must exist. Pytest's known completed exits and
        error/failure counts distinguish broken setup from assertion failure.
        Other tools without a report provide only an exit observation: success
        is green; nonzero is indeterminate, with diagnostics for the LLM.
        A native JUnit report can establish errors/failures independently of
        that tool's numeric exit convention. No process exit remains broken.
        """
        if pytest_exit_status is None:
            pytest_exit_status = report_requested
        if exit_status is None:
            return "broken", "exit-status"
        if report_requested and counts is None:
            return "broken", "junit-report-absent"
        if not report_requested and counts is None:
            # Native tools need not use pytest's exit conventions. A nonzero
            # status alone cannot distinguish assertion, build and setup errors.
            return ("green" if not exit_status else "indeterminate"), "exit-status-only"
        if (
            pytest_exit_status
            and exit_status not in DeliveryContinuationRunner._ORACLE_COMPLETED_EXITS
        ):
            return "broken", "exit-status"
        _, errors, failures = counts
        # Read the report's own errors/failures BEFORE trusting a zero exit:
        # a process can exit 0 while its own JUnit report records a failed or
        # errored test case (a native tool's exit convention need not track
        # its report), and a zero exit must never outrank a report that
        # disagrees with it. An error keeps the SAME "broken" designation
        # this method already gives an errored report on the nonzero-exit
        # path; a failure against a clean exit is a genuine two-axis
        # contradiction and earns the same conservative designation the
        # mirror contradiction (nonzero exit, clean report) earns below.
        if errors:
            return "broken", "junit-report"
        if failures:
            if not exit_status:
                return "indeterminate", "junit-report-contradicts-exit-status"
            return "red", "junit-report"
        if not exit_status:
            return "green", "junit-report"
        return "indeterminate", "junit-report-contradicts-exit-status"

    @staticmethod
    def _oracle_diagnosis(item: NativeEvidence) -> str:
        """The tail of every channel that spoke, each named by where it came from.

        Both channels and not one: pytest writes its summary to stdout and
        leaves stderr empty, while a process that died before pytest started
        wrote only stderr.  Reading a fixed channel would report the wrong
        thing for one of those two, and reading the FIRST non-empty one would
        report a stray warning in place of the failure.
        """
        spoken = []
        for channel, text, keep in (
            ("stdout", item.stdout, 3),
            ("stderr", item.stderr, 2),
        ):
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if lines:
                spoken.append(
                    f"{channel}: "
                    + " | ".join(
                        DeliveryContinuationRunner._excerpt(line)
                        for line in lines[-keep:]
                    )
                )
        return "; ".join(spoken) or "the command wrote nothing on either channel"

    #: Per-line ceiling for the operator excerpt.  A test id in this repository
    #: can be a whole paragraph, and three of them unwrapped bury the exit
    #: status the reader came for.  The cut is MARKED and the untruncated output
    #: still travels to the author in the finding, so nothing is silently lost.
    _ORACLE_EXCERPT = 160

    @staticmethod
    def _excerpt(line: str) -> str:
        ceiling = DeliveryContinuationRunner._ORACLE_EXCERPT
        return line if len(line) <= ceiling else f"{line[:ceiling]}[...truncated]"

    @staticmethod
    def _declared_junit_report(root: Path, argv: tuple[str, ...]) -> Path | None:
        """Resolve the command's explicit JUnit destination, never its stdout."""
        destination = None
        for index, word in enumerate(argv):
            if word.startswith(("--junitxml=", "--junit-xml=")):
                destination = word.partition("=")[2]
            elif word in {"--junitxml", "--junit-xml"} and index + 1 < len(argv):
                destination = argv[index + 1]
        return root / destination if destination else None

    @staticmethod
    def _report_stamp(report: Path) -> tuple[int, int, int] | None:
        """An untouched declared output is historical, not this run's report."""
        try:
            observed = report.stat()
        except OSError:
            return None
        return observed.st_ino, observed.st_mtime_ns, observed.st_ctime_ns

    def _executed_oracle_set(
        self, root: Path, prepared: list[tuple[str, AuthorityFacts]]
    ) -> OracleExecution | DeliveryOutcome:
        """Execute every authored oracle in the WORKSPACE, before any craft turn.

        MEASURED TWICE, runs 22 and 23 (2026-09-05).  An oracle that never
        reached its own assertion -- a freshness gate refusing the installed
        `des`, then a support path resolved one directory too high -- was
        APPROVED by the oracle reviewer, implemented by a crafter, refused by
        the native verification, and answered by a correction turn whose finding
        named the ORACLE, which no role downstream of its author may repair.
        Three paid turns per run, and a finding with no route home.

        The two roles that hold the oracle cannot run it: `nw-acceptance-designer`
        declares `Read, Edit` and `nw-acceptance-designer-reviewer` an enforced
        EMPTY tool set.  So "this oracle fails on its assertion and not on its
        scaffolding" is a property the SOFTWARE owns and measures
        (`boundary:software-measures-model-decides`), and observing an execution
        is a fixed floor rather than a rigor knob (GDP-7, ADR-025 RED before
        GREEN).  It runs in the workspace and not in a candidate, because at
        this point no candidate exists: that is the whole point of running here.

        One `_native` call per oracle rather than one for all of them, because
        each needs its OWN report path and `_native_evidence` builds one
        environment for the whole ordered sequence.  The cost is one shim
        directory per value; the alternative is one report per run, in which the
        last oracle's session silently answers for every earlier one.

        EVERY oracle is recorded, not only the refusing ones.  The verdict a
        run 31 or 32b oracle earns is `red`, which is the ADMITTED answer, and
        the defect was inside that admission -- so keeping the measurement only
        where the runner refuses would discard it exactly where it is needed
        (GDP-8: decide on the property, never the designation).
        """
        oracle_bindings = tuple(
            dict.fromkeys(
                (design.acceptance_paths[0], design.oracle_verification_argv)
                for _, design in prepared
            )
        )
        inherited = os.environ.get(self._ORACLE_REPORT_VAR, "")
        records: list[dict[str, object]] = []
        measured: list[dict[str, object]] = []
        refused: list[str] = []
        with tempfile.TemporaryDirectory(prefix="nwave-oracle-red-") as reports:
            for index, (oracle, argv) in enumerate(oracle_bindings):
                declared_report = self._declared_junit_report(root, argv)
                report = declared_report or Path(reports) / f"{index}.xml"
                prior_report = self._report_stamp(report)
                evidence = self._native(
                    root,
                    (argv,),
                    root,
                    (
                        {
                            "PYTHONPATH": os.pathsep.join(
                                [
                                    str(root / "src"),
                                    str(root),
                                    *(
                                        [os.environ["PYTHONPATH"]]
                                        if os.environ.get("PYTHONPATH")
                                        else []
                                    ),
                                ]
                            ),
                            **(
                                {
                                    self._ORACLE_REPORT_VAR: " ".join(
                                        part
                                        for part in (inherited, f"--junitxml={report}")
                                        if part
                                    )
                                }
                                if declared_report is None
                                else {}
                            ),
                        }
                        if self._uses_python(argv)
                        else None
                    ),
                    run=NativeRun(capture_incomplete=True),
                )
                if isinstance(evidence, DeliveryOutcome):
                    return evidence
                item = evidence[0]
                counts = self._junit_counts(report)
                failures = self._junit_failures(report)
                if declared_report is not None and prior_report == self._report_stamp(
                    report
                ):
                    # Never remove or overwrite a caller-selected path ourselves.
                    # Only a report produced by this native command can judge it.
                    counts = None
                    failures = None
                verdict, axis = self._oracle_verdict(
                    item.exit_status,
                    counts,
                    invokes_pytest(argv) or declared_report is not None,
                    pytest_exit_status=invokes_pytest(argv),
                )
                locator = self._retain_native_failure_evidence(root, "oracle", evidence)
                if locator is None:
                    return self._fail(
                        Disposition.Indeterminate,
                        "OracleEvidenceUnretained",
                        "the actual native oracle observation could not be retained",
                        "restore write access to the project-local native evidence directory and remeasure the oracle",
                    )
                measured.append(
                    {
                        "path": oracle,
                        "verdict": verdict,
                        "axis": axis,
                        "counts": counts,
                        "argv": list(item.argv),
                        "exit": item.exit_status,
                        "failures": failures,
                        "diagnostic": self._oracle_diagnosis(item),
                        "native_evidence_locator": locator,
                    }
                )
                if item.incomplete:
                    return OracleExecution(
                        tuple(measured),
                        OracleRedRefusal(
                            json.dumps(self._evidence_records(evidence)),
                            self._fail(
                                Disposition.Indeterminate,
                                item.incomplete_what or "OracleExecutionIncomplete",
                                f"{item.incomplete_why}; actual native observation retained at {locator}",
                                item.incomplete_how
                                or "restore the declared native execution context",
                            ),
                        ),
                    )
                # Operator channel only, exactly like `NATIVE-RUNTIME`. The
                # durable copy of this verdict is the value's witness record,
                # appended once the measurement binds (`_record_oracle_witness`).
                print(
                    f"ORACLE-RED: {oracle} exit={item.exit_status} "
                    f"verdict={verdict} axis={axis} counts={counts} "
                    f"argv={' '.join(argv)}",
                    file=sys.stderr,
                )
                if verdict == "indeterminate" and axis != "exit-status-only":
                    return self._fail(
                        Disposition.Indeterminate,
                        "OracleRedUnobservable",
                        f"{oracle} exited {item.exit_status} while its own report "
                        f"recorded {counts[1] if counts else 0} errors and "
                        f"{counts[2] if counts else 0} failures, so whether it "
                        f"failed on its assertion cannot be established",
                        "run the oracle by hand and read its report, then re-run "
                        "the Request",
                    )
                if verdict not in self._ORACLE_REFUSING:
                    continue
                records.append(
                    {
                        "oracle": oracle,
                        "verdict": verdict,
                        "axis": axis,
                        "argv": item.argv,
                        "exit": item.exit_status,
                        "stdout": item.stdout,
                        "stderr": item.stderr,
                    }
                )
                why = self._ORACLE_REFUSAL_WHYS.get(str(axis), "")
                refused.append(
                    f"{oracle} is {verdict} before any implementation "
                    f"(exit {item.exit_status}, {axis}) -- "
                    + (f"{why} -- " if why else "")
                    + self._oracle_diagnosis(item)
                )
        if not records:
            return OracleExecution(tuple(measured), None)
        return OracleExecution(
            tuple(measured),
            OracleRedRefusal(
                json.dumps(records, ensure_ascii=False),
                self._fail(
                    Disposition.Refusal,
                    "OracleNotRed",
                    "; ".join(refused),
                    "; ".join(
                        dict.fromkeys(
                            self._ORACLE_REFUSAL_HOWS.get(
                                str(record["axis"]), self._ORACLE_NOT_RED_HOW
                            )
                            for record in records
                        )
                    ),
                ),
            ),
        )

    @staticmethod
    def _owned_paths(design: AuthorityFacts) -> tuple[str, ...]:
        """Every path one value's runner-derived facts authorize it to change."""
        return tuple(
            dict.fromkeys(
                (
                    *design.modified_authority_paths,
                    *design.acceptance_paths,
                    *(path for path, _ in design.target_decisions),
                )
            )
        )

    @staticmethod
    def _batch_key(design: AuthorityFacts) -> tuple[object, ...]:
        """Only equal consumed facts may share an author or crafter invocation."""
        return (
            design.locator,
            design.acceptance_oracle_locator,
            design.acceptance_paths,
            design.target_decisions,
            design.paradigm,
            design.public_oracle,
        )

    @staticmethod
    def product_authority_defect(root: Path, stored: StoredHandover) -> Blocked | None:
        """Validate only a product authority actually bound by its constructor."""
        product = stored.product_authority
        if product is None:
            return None
        from des.adapters.driven.config.des_config import DESConfig

        how = (
            "restore the bound product authority or submit complete DISCUSS facts "
            "with `des po --input - --replace-current` and the persisted scope"
        )
        try:
            destination = DESConfig.discuss_document_destination(root, stored.scope)
        except FeatureDocumentsInvalid as error:
            return Blocked(error.what, error.why, error.how, refusal=True)
        if destination != product.locator:
            return Blocked(
                "DiscussAuthorityIdentityMismatch",
                "the configured product destination differs from this Request's constructed authority",
                how,
                refusal=True,
            )
        observed = _authority_bytes(root, (product.locator,))
        if observed is None:
            return Blocked(
                "DiscussAuthorityUnavailable",
                "the bound product authority cannot be read as a repository-local Markdown file",
                how,
            )
        if hashlib.sha256(observed[0][1]).hexdigest() != product.sha256:
            return Blocked(
                "DiscussAuthorityDrift",
                "product authority bytes differ from the DISCUSS constructor's bound identity",
                how,
                refusal=True,
            )
        return None

    @staticmethod
    def _bound_authority_documents(
        root: Path, stored: StoredHandover
    ) -> tuple[str, ...]:
        """Whole-file authority documents the declared commands and handoff derive from."""
        from des.adapters.driven.config.des_config import DESConfig

        paths: list[str] = []
        if stored.product_authority is not None:
            paths.append(stored.product_authority.locator)
        selected = False
        for value in stored.values:
            authority = value.authority
            locator = (
                authority.authority_locator
                if isinstance(authority, DesignFacts)
                else authority
            )
            if isinstance(locator, str) and locator:
                paths.append(locator.partition("#")[0])
            selected = selected or bool(
                value.acceptance or value.acceptance_oracle is not None
            )
        if stored.shared_design is not None:
            paths.append(stored.shared_design.authority_locator.partition("#")[0])
        if selected:
            try:
                paths.append(DESConfig.distill_document_destination(root, stored.scope))
            except FeatureDocumentsInvalid:
                paths.append(".nwave/des/unreadable-distill-authority")
        return tuple(dict.fromkeys(p for p in paths if p))

    def _verify_upstream(self, root: Path, stored: StoredHandover) -> str | None:
        """The verify upstream ref over handover AND authority bytes, or None."""
        documents = _authority_bytes(
            root, self._bound_authority_documents(root, stored)
        )
        if documents is None:
            return None
        upstream = (
            stored.raw
            + b"\0"
            + json.dumps(
                [[p, hashlib.sha256(b).hexdigest()] for p, b in documents],
                separators=(",", ":"),
            ).encode("utf-8")
        )
        return verify_upstream_ref(stored.request, upstream)

    def _owned_with_authority(
        self,
        root: Path,
        stored: StoredHandover,
        prepared: list[tuple[str, AuthorityFacts]],
    ) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                (
                    *self._request_owned_paths(prepared),
                    *self._bound_authority_documents(root, stored),
                )
            )
        )

    @staticmethod
    def _request_owned_paths(
        prepared: list[tuple[str, AuthorityFacts]],
    ) -> tuple[str, ...]:
        """The union of every admitted value's owned paths, first-value order."""
        return tuple(
            dict.fromkeys(
                path
                for _, design in prepared
                for path in DeliveryContinuationRunner._owned_paths(design)
            )
        )

    @staticmethod
    def _craft_record_paths(design: AuthorityFacts) -> tuple[str, ...]:
        """The bytes a craft record is a fact about, uniform for every source.

        The production targets and the acceptance bytes those targets were built
        against: a record measured beside another oracle is not current for this
        one, with no ref deleted.
        """
        mutable = DeliveryContinuationRunner._mutable_targets(design)
        return tuple(dict.fromkeys((*mutable, *design.acceptance_paths)))

    @staticmethod
    def _mutable_targets(design: AuthorityFacts) -> tuple[str, ...]:
        """One value's production targets: what a crafter alone may still change.

        The ORACLE is the only exclusion, and it is the only one ADR-SSOT-002
        §12 asks for: `Author/reviewer separation` keeps the immutable oracle
        out of the crafter's hands, and the immutability windows are stated
        over oracle bytes.  A declared SUPPORT carries no such promise -- it is
        evidence the oracle's reviewer reads, captured before the craft turn
        and surfaced to the whole-diff reviewer as bytes-of-then.

        Subtracting the whole acceptance set instead cost a paid turn on
        2026-09-05, run 15: the architect named one adapter both as the EXTEND
        target and as a support, which is legitimate in meaning -- read this
        file to judge the oracle, change it to deliver -- and the runner
        resolved the two roles silently in favour of immutability.  The crafter
        received `target_decisions` authorizing an EXTEND next to an EMPTY
        `mutable_targets` and answered `indeterminate` on the contradiction.
        The target table is the model's decision about what this delivery
        changes; being read as evidence never withdraws it.
        """
        oracle = design.acceptance_paths[0]
        return tuple(path for path, _ in design.target_decisions if path != oracle)

    @staticmethod
    def _request_argvs(
        prepared: list[tuple[str, AuthorityFacts]],
    ) -> tuple[tuple[str, ...], ...]:
        """Identical native vectors collapse, keeping their first authority order."""
        return tuple(
            dict.fromkeys(
                argv
                for _, design in prepared
                for argv in design.native_verification_argvs
            )
        )

    def _forward_batches(
        self, stored: StoredHandover, values: list[tuple[str, AuthorityFacts]]
    ) -> list[list[tuple[str, AuthorityFacts]]]:
        """Re-derive forward, predecessor-safe batches from bound graph facts."""
        batches: list[list[tuple[str, AuthorityFacts]]] = []
        remaining = dict(values)
        completed: set[str] = set()
        while remaining:
            observation, design = next(iter(remaining.items()))
            selected = {observation}
            changed = True
            while changed:
                changed = False
                for candidate, other in remaining.items():
                    value = next(
                        item for item in stored.values if item.observation == candidate
                    )
                    if (
                        candidate not in selected
                        and self._batch_key(other) == self._batch_key(design)
                        and self._dependency_path(stored, candidate, observation)
                        and set(value.dependencies) <= completed | selected
                    ):
                        selected.add(candidate)
                        changed = True
            batch = [
                (candidate, remaining.pop(candidate))
                for candidate in tuple(remaining)
                if candidate in selected
            ]
            batches.append(batch)
            completed.update(selected)
        return batches

    def _changed_paths(
        self, root: Path, base: str, candidate: str
    ) -> tuple[str, ...] | None:
        """The candidate's own changed paths, or None when Git cannot answer.

        Two readers, one measurement: the correction owners are derived from it,
        and the native evidence intersects it with what each execution imported.
        A second spelling of the same diff would let those two disagree about
        which files the candidate changed.
        """
        changed = self._git_bytes(root, "diff", "--name-only", "-z", base, candidate)
        if changed is None:
            return None
        return tuple(
            path for path in (self._utf8(raw) for raw in changed.split(b"\0")) if path
        )

    def _verified_candidate(
        self,
        root: Path,
        prepared: list[tuple[str, AuthorityFacts]],
        stored: StoredHandover,
        base: str,
    ) -> tuple[str, tuple[NativeEvidence, ...]] | DeliveryOutcome:
        """Construct a candidate, then observe it inside its owned checkout."""
        owned = self._owned_with_authority(root, stored, prepared)
        argvs = self._request_argvs(prepared)
        facts = IntegrationFacts(
            stored.request,
            tuple(observation for observation, _ in prepared),
            tuple(dict.fromkeys(design.locator for _, design in prepared)),
            handover_sha256=hashlib.sha256(stored.raw).hexdigest(),
        )
        # Observe before formatting so an external edit cannot be laundered
        # by refreshing records after the runner's own format contract.
        was_current = self._pre_candidate_currentness(root, stored, prepared)
        created = self._candidate(root, base, owned, facts)
        if isinstance(created, DeliveryOutcome):
            return created
        candidate, _diff = created
        self._refresh_turn_records(root, base, stored, prepared, was_current)
        touched = self._changed_paths(root, base, candidate)
        if touched is None:
            return self._fail(
                Disposition.Retry,
                "GitUnavailable",
                f"the candidate {candidate} diff cannot be observed",
                "restore Git",
            )
        return self._with_candidate_worktree(root, candidate, argvs, touched)

    def _measured_candidate(
        self,
        root: Path,
        candidate: str,
        directory: Path,
        commands: tuple[tuple[str, ...], ...],
        changed: tuple[str, ...],
    ) -> tuple[str, tuple[NativeEvidence, ...]] | DeliveryOutcome:
        evidence = self._native(
            directory,
            commands,
            root,
            run=NativeRun(changed=changed, capture_incomplete=True),
        )
        if isinstance(evidence, DeliveryOutcome):
            return evidence
        # Retain captured streams outside the owned checkout before any later
        # analysis can raise and before that checkout is released.
        evidence_locator = self._retain_native_failure_evidence(
            root, candidate, evidence
        )
        if evidence_locator is not None:
            self._native_evidence_locator = evidence_locator
            try:
                self._native_evidence_sha256 = hashlib.sha256(
                    (root / evidence_locator).read_bytes()
                ).hexdigest()
            except OSError:
                self._native_evidence_locator = None
                self._native_evidence_sha256 = None
        if self._native_evidence_sha256 is None:
            return self._fail(
                Disposition.Indeterminate,
                "NativeEvidenceUnretained",
                f"candidate {candidate} executed but its native observation was not retained",
                "restore writable native evidence storage before verification",
            )
        retained = self._git(
            root,
            "update-ref",
            f"refs/nwave/verification-history/{candidate}/{self._native_evidence_sha256}",
            candidate,
        )
        if retained.returncode:
            return self._git_failure(
                retained,
                disposition=Disposition.Indeterminate,
                what="CandidateHistoryUnretained",
                how="restore writable Git refs to preserve the measured candidate",
            )
        unchanged = self._git(directory, "diff", "--exit-code", candidate, "--")
        if unchanged.returncode:
            return self._fail(
                Disposition.Indeterminate,
                "CandidateSourceChanged",
                f"native execution changed tracked source for candidate {candidate}; "
                f"native evidence: {evidence_locator}",
                "repair the native command to keep candidate source immutable and verify again",
            )
        self._radius = candidate_radius(directory, changed)
        failed = any(
            item.exit_status for item in evidence if item.origin == DECLARED_ORIGIN
        )
        incomplete = next(
            (
                item
                for item in evidence
                if item.origin == DECLARED_ORIGIN and item.incomplete
            ),
            None,
        )
        if not failed:
            if incomplete is not None:
                assert incomplete.incomplete_what is not None
                assert incomplete.incomplete_why is not None
                assert incomplete.incomplete_how is not None
                return self._fail(
                    Disposition.Indeterminate,
                    incomplete.incomplete_what,
                    f"candidate {candidate} has incomplete declared native verification: "
                    f"{incomplete.incomplete_why}"
                    + (
                        f"; native evidence retained at {evidence_locator}"
                        if evidence_locator is not None
                        else "; native evidence could not be retained under "
                        ".nwave/des/logs/native"
                    ),
                    incomplete.incomplete_how,
                )
            return candidate, evidence
        return self._fail(
            Disposition.Refusal,
            "VerificationFailed",
            f"candidate {candidate} failed its ordered native verification"
            + (
                f"; native evidence retained at {evidence_locator}"
                if evidence_locator is not None
                else "; native evidence could not be retained under "
                ".nwave/des/logs/native"
            ),
            "repair the value and explicitly verify the resulting candidate",
        )

    def _integrate(
        self,
        root: Path,
        prepared: list[tuple[str, AuthorityFacts]],
        integration: Integration,
        owned_paths: tuple[str, ...] | None = None,
    ) -> DeliveryOutcome:
        """One compare-and-swap, one owned-index reconciliation, one cleanup.

        A no-delta candidate is expected-old itself, and the swap still runs so
        a concurrently moved ref refuses instead of yielding a Success nobody
        verified against the destination.
        """
        candidate = integration.candidate
        owned = owned_paths or self._request_owned_paths(prepared)
        # The observation, the comparison and the swap live in `HeadAdvance`,
        # which the `des lane integrate` step also calls: one implementation of
        # "the destination is not where you last saw it", so the two cannot
        # drift apart on the one case a green run never exercises.  The seam is
        # INJECTED rather than imported there, so a caller substituting Git for
        # this runner still substitutes it inside the swap.
        refused = HeadAdvance(self._git).swap(root, candidate, integration.base)
        if refused is not None:
            return self._advance_failure(refused)
        reset = self._git(root, "reset", "HEAD", "--", *owned)
        final = self._git(
            root, "status", "--porcelain=v1", "-z", "--untracked-files=all"
        )
        # Named and observed unconditionally: as a trailing `.stdout` inside the
        # disjunction, a non-zero (or unanswered) owned status carrying no
        # output read as PROVEN-clean -- a silent-wrong on the exact question
        # this branch exists to answer.
        owned_status = self._git(root, "status", "--porcelain", "--", *owned)
        if (
            reset.returncode
            or final.returncode
            or owned_status.returncode
            or _foreign_status(final.stdout, owned) != integration.foreign_status
            or _workspace_bytes(root, tuple(integration.foreign_bytes))
            != integration.foreign_bytes
            or owned_status.stdout
        ):
            return self._git_failure(
                reset,
                final,
                owned_status,
                disposition=Disposition.Indeterminate,
                what="CleanupUnproven",
                how="inspect repository state without automatic recovery",
                why=f"{candidate} integrated but cleanup or foreign-state equivalence is unproven",
            )
        return DeliveryOutcome(
            Disposition.Success, integrated_sha=candidate, cleanup_complete=True
        )

    def selected_authority(
        self, root: Path, stored: StoredHandover, position: int
    ) -> AuthorityFacts | DeliveryOutcome:
        """The ONE source of one value's selected acceptance revision.

        ORACLE, CRAFT, VERIFY, prepare-role and ``des state`` all read this and
        nothing else.  A value with no DISTILL selection is judged on its DESIGN
        facts.  A selection is a complete tuple or it is not usable: a persisted
        schema_version 1 selection (legacy partial, wins precedence) is
        ``SelectedRevisionIncomplete``, and a complete one made over another
        DESIGN is ``SelectedRevisionRealignmentNeeded``.  Nothing is borrowed
        from DESIGN and no byte is written.
        """
        value = stored.values[position - 1]
        assert value.authority is not None
        selected = bool(value.acceptance or value.acceptance_oracle is not None)
        design = self._derive(root, value.authority, admit_verification=not selected)
        if isinstance(design, DeliveryOutcome):
            return design
        if stored.shared_design is not None:
            inherited = self._derive(
                root, stored.shared_design.design, admit_verification=False
            )
            if isinstance(inherited, DeliveryOutcome):
                return inherited
            required_commands = tuple(
                dict.fromkeys(
                    (
                        *design.required_verification_argvs,
                        *inherited.required_verification_argvs,
                    )
                )
            )
            required_paths = tuple(
                dict.fromkeys(
                    (
                        *design.required_check_paths,
                        *inherited.required_check_paths,
                    )
                )
            )
            design = replace(
                design,
                required_verification_argvs=required_commands,
                required_check_paths=required_paths,
                native_verification_argvs=(
                    *design.native_verification_argvs,
                    *(
                        argv
                        for argv in required_commands
                        if argv not in design.native_verification_argvs
                    ),
                ),
                acceptance_paths=tuple(
                    dict.fromkeys((*design.acceptance_paths, *required_paths))
                ),
            )
        if not selected:
            return self._admit_verification_executables(root, design) or design
        how = (
            "des distill --repo-root ROOT --replace-current --input - with a "
            "complete schema_version 2 revision (verification and "
            "oracle_verification_index included)"
        )
        if value.acceptance_verification is None:
            return self._fail(
                Disposition.Indeterminate,
                "SelectedRevisionIncomplete",
                f"value {position} holds a schema_version 1 acceptance selection "
                "without verification or oracle_verification_index, so its "
                "complete revision is unknown and is never borrowed from DESIGN",
                how,
            )
        if value.acceptance_design_basis_sha256 != design_basis_sha256(
            stored.shared_design, value
        ):
            return self._fail(
                Disposition.Indeterminate,
                "SelectedRevisionRealignmentNeeded",
                f"value {position}'s selected revision was built over another "
                "DESIGN: the DESIGN changed after the selection, whose bytes are "
                "kept unchanged",
                how + ", or restore the DESIGN with des design --replace-current",
            )
        assert value.acceptance_oracle is not None
        assert value.acceptance_oracle_verification_index is not None
        revision = replace(
            design,
            acceptance_obligations=value.acceptance,
            acceptance_oracle_locator=value.acceptance_oracle,
            acceptance_paths=tuple(
                dict.fromkeys(
                    (
                        value.acceptance_oracle.partition("::")[0],
                        *value.acceptance_supports,
                        *design.required_check_paths,
                    )
                )
            ),
            native_verification_argvs=(
                *value.acceptance_verification,
                *(
                    argv
                    for argv in design.required_verification_argvs
                    if argv not in value.acceptance_verification
                ),
            ),
            oracle_verification_index=value.acceptance_oracle_verification_index,
        )
        return (
            self._admit_verification_executables(root, revision)
            or self._admit_targets(revision)
            or revision
        )

    def derive_authority(
        self, root: Path, locator: str | DesignFacts
    ) -> AuthorityFacts | DeliveryOutcome:
        """Re-derive one value's runner facts from its bound authority.

        Public because a step invoked ALONE starts from the durable graph and
        holds no derived facts from an earlier step; deriving them again from
        the same bytes is the whole reason the authority is durable.
        """
        return self._derive(root, locator)

    def oracle_turn_complete(
        self,
        root: Path,
        stored: StoredHandover,
        ready: HandoverValue,
        design: AuthorityFacts,
    ) -> bool:
        """Is this value's oracle measurement a recorded, current fact?

        Missing records, changed bytes and unresolved measurements answer NO.
        The host decides whether to change the oracle or request remeasurement.
        """
        head = self._head(root)
        if isinstance(head, DeliveryOutcome):
            return False
        identity = RecordIdentity.of(root, stored, ready, design)
        if identity is None:
            return False
        return self._turn_completed(
            root,
            stored.request,
            ((ready.observation, identity),),
            _ORACLE_TURN,
            design.acceptance_paths,
        )

    def invalidate_verification(
        self, root: Path, stored: StoredHandover
    ) -> DeliveryOutcome | None:
        """Withdraw active approval before attempting a fresh measurement."""
        refs = [
            turn_ref(stored.request, stored.request, VERIFY_OUTCOME_TURN),
        ]
        upstream = self._verify_upstream(root, stored)
        if upstream is not None:
            refs.append(upstream)
        for ref in refs:
            removed = self._git(root, "update-ref", "-d", ref)
            if removed.returncode:
                return self._git_failure(
                    removed,
                    disposition=Disposition.Indeterminate,
                    what="VerificationInvalidationFailed",
                    how="restore writable Git refs before requesting fresh verification",
                )
        return None

    def record_verified_candidate(
        self, root: Path, stored: StoredHandover, candidate: str, verdict: str | None
    ) -> None:
        """Record a natively measured candidate, and an optional later verdict.

        Written whatever the judgement was, because the candidate was built and
        verified natively either way and that is a fact about the repository,
        not about the judge's opinion of it. Recording only admissions made the
        absence of a record mean two different things at once, and `des
        integrate` could only read the stricter one.

        Best-effort for the reason every record here is: one that is not written
        costs the next invocation a rebuilt candidate and two paid judgements,
        and a Git that never answered must not turn a judged candidate into a
        refusal.
        """
        head = self._head(root)
        if isinstance(head, DeliveryOutcome):
            return
        observed = self._git(root, "rev-parse", f"{candidate}^{{tree}}")
        if observed.returncode:
            return
        env = declared_child_environment()
        self._git(
            root,
            "update-ref",
            turn_ref(stored.request, stored.request, VERIFY_TURN),
            candidate,
            env=env,
        )
        # The SAME candidate, under the key of the graph it was verified
        # against. Written second and read first, so an interruption between
        # the two leaves a candidate no upstream key covers -- which reads as
        # superseded and costs one rebuild, never as evidence.
        ref = self._verify_upstream(root, stored)
        if ref is None:
            return
        self._git(root, "update-ref", ref, candidate, env=env)
        if verdict is None:
            return
        judged = self._git(
            root,
            "commit-tree",
            observed.stdout.strip(),
            "-p",
            candidate,
            "-m",
            f"{_VERDICT_SUBJECT}{verdict}",
            "-m",
            "",
            env=env,
        )
        if judged.returncode:
            return
        self._git(
            root,
            "update-ref",
            turn_ref(stored.request, stored.request, VERIFY_OUTCOME_TURN),
            judged.stdout.strip(),
            env=env,
        )

    def verification_record(
        self, root: Path, stored: StoredHandover
    ) -> VerificationRecord | None:
        """What the verify record says about this Request, in ONE reading.

        Read by the UPSTREAM KEY, the way every other record in this namespace
        is read against the bytes it was measured over: a candidate verified
        before a wave producer corrected the graph is found under the previous
        key and not under the current one, so it is reported SUPERSEDED rather
        than silently reused. The candidate itself is still returned, because a
        refusal that cannot name the candidate it is refusing is a refusal that
        lies about its own cause.
        """
        observed = self._git(
            root,
            "rev-parse",
            "--verify",
            "--quiet",
            turn_ref(stored.request, stored.request, VERIFY_TURN),
        )
        if observed.returncode:
            return None
        candidate = observed.stdout.strip()
        ref = self._verify_upstream(root, stored)
        if ref is None:
            return VerificationRecord(candidate, False)
        current = self._git(root, "rev-parse", "--verify", "--quiet", ref)
        if not current.returncode:
            # The key names the candidate verified over exactly these bytes, so
            # restoring identical authority bytes finds the earlier record again.
            candidate = current.stdout.strip()
            if self._candidate_covers_current_owned_bytes(root, stored, candidate):
                return VerificationRecord(candidate, True)
        return VerificationRecord(candidate, False)

    def _candidate_covers_current_owned_bytes(
        self, root: Path, stored: StoredHandover, candidate: str
    ) -> bool:
        """Whether a recorded candidate still contains every declared owned byte.

        The upstream key establishes that the handover and bound authorities are
        unchanged.  It cannot establish that a declared production target,
        oracle or support stayed unchanged after verification.  Re-derive the
        same selected facts every consumer reads, then ask Git one question over
        their one existing owned-path union.  A derivation or Git failure is not
        evidence of currentness, so it conservatively makes the record stale.
        """
        prepared: list[tuple[str, AuthorityFacts]] = []
        for position, value in enumerate(stored.values, start=1):
            if value.authority is None:
                return False
            selected = self.selected_authority(root, stored, position)
            if isinstance(selected, DeliveryOutcome):
                return False
            prepared.append((value.observation, selected))
        owned = self._owned_with_authority(root, stored, prepared)
        if not owned:
            return False
        current = _workspace_bytes(root, owned)
        for path in owned:
            observed = current[path]
            if observed == ("absent", ""):
                listed = self._git_bytes(
                    root, "ls-tree", "-z", "--name-only", candidate, "--", path
                )
                if listed is None or listed:
                    return False
                continue
            candidate_bytes = self._git_bytes(root, "show", f"{candidate}:{path}")
            if candidate_bytes is None or observed != ("file", candidate_bytes):
                return False
            entry = self._git_bytes(root, "ls-tree", "-z", candidate, "--", path)
            try:
                mode = b"100755" if (root / path).stat().st_mode & 0o111 else b"100644"
            except OSError:
                return False
            if entry is None or not entry.startswith(mode + b" "):
                return False
        return True

    def verified_candidate(self, root: Path, stored: StoredHandover) -> str | None:
        """The candidate a CURRENT verify record covers, or `None`.

        One predicate, derived from the single reading above: every consumer
        that only asks «may I build on this» gets the same answer the state
        projection and `des integrate` derive theirs from.
        """
        if self.product_authority_defect(root, stored) is not None:
            return None
        record = self.verification_record(root, stored)
        if record is None or not record.covers_current_upstream:
            return None
        head = self._head(root)
        if isinstance(head, DeliveryOutcome):
            return None
        base = self.candidate_base(root, record.candidate)
        if isinstance(base, DeliveryOutcome) or base != head:
            return None
        return record.candidate

    def destination_is(self, root: Path, candidate: str) -> bool:
        """Is the destination already this commit?

        A primitive observation, and the one that separates «this Request was
        never decomposed» from «this Request finished». Both close the graph;
        only the second is what a repeated `des integrate` is looking at.
        """
        head = self._head(root)
        return not isinstance(head, DeliveryOutcome) and head == candidate

    def candidate_base(self, root: Path, candidate: str) -> str | DeliveryOutcome:
        """The commit a candidate is parented on, read from the object itself.

        A step invoked ALONE is handed only the candidate SHA, and the base it
        must compare-and-swap against is IN that object: Section 4a mandates the
        candidate's single parent be the base it was built from. Reading it back
        rather than taking it as a second argument makes a caller that names a
        base the candidate does not have unrepresentable.
        """
        observed = self._git(root, "rev-parse", "--verify", "--quiet", f"{candidate}^")
        if observed.returncode:
            return self._git_failure(
                observed,
                disposition=Disposition.Refusal,
                what="CandidateUnreadable",
                why=f"{candidate} is not a commit with exactly one parent in this "
                "repository, so the base it must be swapped against is unknown",
                how="pass the CANDIDATE line that `des verify` printed, in this "
                "same repository",
            )
        return observed.stdout.strip()

    def verify_request(
        self,
        root: Path,
        stored: StoredHandover,
        prepared: list[tuple[str, AuthorityFacts]],
        *,
        candidate: str | None = None,
    ) -> tuple[str, str, tuple[NativeEvidence, ...]] | DeliveryOutcome:
        """Build the one candidate and persist its declared native observation.

        Native evidence is captured once, persisted candidate-bound, and then
        returned for later host-selected review or examination. This method
        resolves no provider and makes no semantic admission decision.

        Returns the base, the approved candidate SHA and its captured evidence.
        Nothing here moves a ref: the candidate is a commit OUT of the
        destination's history until `integrate_candidate` swaps it in.
        """
        base = self._head(root)
        if isinstance(base, DeliveryOutcome):
            return base
        approved = _authority_bytes(root, self._prepared_acceptance_paths(prepared))
        bound = _authority_bytes(root, self._bound_authority_documents(root, stored))
        if approved is None or bound is None:
            return self._fail(
                Disposition.Indeterminate,
                "AcceptanceEvidenceUnavailable",
                "approved authority, oracle or declared support is unavailable",
                "restore immutable acceptance evidence",
            )
        if candidate is None:
            previous = self.verification_record(root, stored)
            previous_handover = (
                stored_candidate_handover(root, previous.candidate)
                if previous is not None
                else None
            )
            if (
                previous is not None
                and isinstance(previous_handover, StoredHandover)
                and previous_handover.raw == stored.raw
                and self.candidate_base(root, previous.candidate) == base
                and self._candidate_covers_current_owned_bytes(
                    root, stored, previous.candidate
                )
            ):
                candidate = previous.candidate
        if candidate is None:
            verified = self._verified_candidate(root, prepared, stored, base)
        else:
            touched = self._changed_paths(root, base, candidate)
            if touched is None:
                return self._fail(
                    Disposition.Indeterminate,
                    "CandidateUnavailable",
                    "the current candidate diff cannot be observed",
                    "restore Git before fresh verification",
                )
            verified = self._with_candidate_worktree(
                root, candidate, self._request_argvs(prepared), touched
            )
        if isinstance(verified, DeliveryOutcome):
            return verified
        candidate, evidence = verified
        retained = retain_candidate_handover(root, candidate, stored.raw)
        if retained is not None:
            return self._blocked(retained)
        return base, candidate, evidence

    def integrate_candidate(
        self,
        root: Path,
        stored: StoredHandover,
        prepared: list[tuple[str, AuthorityFacts]],
        base: str,
        candidate: str,
    ) -> DeliveryOutcome:
        """Compare-and-swap the candidate in, reconcile, and close the graph.

        The foreign baseline is measured HERE, immediately before the swap,
        rather than inherited from a snapshot an earlier process took.  A step
        invoked alone holds no such snapshot, and inventing one would assert an
        equivalence over a window this process never observed; measuring it now
        proves exactly the window the swap opens, which is the one it can prove.

        Closing the graph is part of integration and not of some later step: a
        handover that outlives its own integrated candidate would make the next
        `des state` name work that is already in the destination.
        """
        owned = self._owned_with_authority(root, stored, prepared)
        observed = self._observed_scope(root)
        if isinstance(observed, DeliveryOutcome):
            return observed
        status, workspace = observed
        integrated = self._integrate(
            root,
            prepared,
            Integration(
                base=base,
                candidate=candidate,
                foreign_status=_foreign_status(status, owned),
                foreign_bytes=_foreign_bytes(workspace, owned),
            ),
            owned,
        )
        if integrated.disposition is not Disposition.Success:
            return integrated
        cleanup = finalize_handover(root, stored.raw)
        if cleanup is not None:
            return self._blocked(cleanup)
        self._release_turn_records(root, stored)
        return integrated

    def _oracle_witness_gap(
        self, root: Path, selected: SelectedValue
    ) -> tuple[str, str]:
        """WHY and HOW for a value whose oracle witness does not cover craft.

        Measured, not generic: which of the three ways the witness can fail to
        cover the current bytes, and for changed bytes WHICH declared acceptance
        paths changed and whether craft owns them.  A generic "restore the
        recorded oracle" sent a host to revert its own production fix twice
        to re-measure RED when the moved path was a craft target the DESIGN had
        also listed as a support (codex retest 2026-10-01, local-bug).
        """
        stored, ready, design = selected.stored, selected.ready, selected.design
        remeasure = (
            "have the acceptance author correct the oracle or its supports if "
            "needed, then remeasure with `des oracle` before craft"
        )
        ref = self._turn_ref(stored.request, ready.observation, _ORACLE_TURN)
        recorded = self._git(
            root, "rev-parse", "--verify", "--quiet", f"{ref}^{{tree}}"
        )
        if recorded.returncode:
            return (
                "no oracle witness is recorded for this value",
                "measure the oracle with `des oracle` before craft",
            )
        identity = RecordIdentity.of(root, stored, ready, design)
        if identity is None:
            return (
                "the selected revision identity of this value could not be "
                "computed, so no witness can be shown to cover it",
                "restore read access to the bound DESIGN and acceptance "
                "authority, then retry",
            )
        message = self._git(root, "show", "-s", "--format=%B", ref)
        if message.returncode or message.stdout.strip() != self._turn_message(
            _ORACLE_TURN, identity
        ):
            return (
                "the oracle witness was recorded over another selected acceptance "
                "revision or DESIGN section identity",
                remeasure,
            )
        current = self._paths_tree(root, design.acceptance_paths)
        changed = (
            None
            if current is None
            else self._git(
                root,
                "diff-tree",
                "-r",
                "-z",
                "--name-only",
                "--no-renames",
                recorded.stdout.strip(),
                current,
            )
        )
        if changed is None or changed.returncode or not changed.stdout.strip("\0"):
            return (
                "no current oracle witness covers the acceptance bytes and no "
                "changed acceptance path could be named",
                "restore the recorded acceptance bytes and Git storage, or "
                + remeasure,
            )
        paths = [path for path in changed.stdout.split("\0") if path]
        targets = {path for path, _ in design.target_decisions}
        crafted = [path for path in paths if path in targets]
        why = (
            "declared acceptance bytes changed since the oracle witness: "
            + ", ".join(paths)
        )
        if crafted:
            return (
                why
                + "; "
                + ", ".join(crafted)
                + " is also a craft target, so the witness cannot cover the "
                "crafted bytes",
                "do not revert production to re-measure RED: correct the DESIGN "
                "(or the DISTILL revision) so no craft target is an acceptance "
                "support, then remeasure with `des oracle` before craft",
            )
        return (why, "restore those acceptance bytes, or " + remeasure)

    def record_craft(
        self, root: Path, selected: SelectedValue
    ) -> DeliveryOutcome | None:
        """Observe GREEN without changing the host's files, then record their identity."""
        stored, ready, design = selected.stored, selected.ready, selected.design
        preservation = self._prefactoring_ready(root, selected)
        if preservation is not None:
            return preservation
        if not self.oracle_turn_complete(root, stored, ready, design):
            why, how = self._oracle_witness_gap(root, selected)
            return self._fail(Disposition.Refusal, "OracleRecordMoved", why, how)
        executed = self._executed_oracle_set(root, [(ready.observation, design)])
        if isinstance(executed, DeliveryOutcome):
            return executed
        if not self._observed_green(executed):
            return self._fail(
                Disposition.Refusal,
                "CraftNotGreen",
                "the host-supplied implementation did not satisfy its recorded public oracle",
                "inspect the native observation and return the finding to its host-selected owner",
            )
        head = self._head(root)
        if isinstance(head, DeliveryOutcome):
            return head
        tree = self._paths_tree(root, self._craft_record_paths(design))
        identity = RecordIdentity.of(root, stored, ready, design)
        if tree is None or identity is None:
            return self._fail(
                Disposition.Indeterminate,
                "CraftRecordUnavailable",
                "the current implementation or authority identity could not be read",
                "restore the declared files and Git storage",
            )
        self._record_turn(
            root,
            TurnRecordTarget(
                base=head,
                request=stored.request,
                values=((ready.observation, identity),),
            ),
            role=_CRAFT_TURN,
            tree=tree,
        )
        if not self.craft_turn_complete(root, stored, ready, design):
            return self._fail(
                Disposition.Indeterminate,
                "CraftRecordUnavailable",
                "the implementation witness was not persisted",
                "restore Git record storage and repeat the measurement",
            )
        return None

    def craft_turn_complete(
        self,
        root: Path,
        stored: StoredHandover,
        ready: HandoverValue,
        design: AuthorityFacts,
    ) -> bool:
        """Is this value's craft turn already a recorded fact over these bytes?"""
        head = self._head(root)
        if isinstance(head, DeliveryOutcome):
            return False
        identity = RecordIdentity.of(root, stored, ready, design)
        if identity is None:
            return False
        return self._turn_completed(
            root,
            stored.request,
            ((ready.observation, identity),),
            _CRAFT_TURN,
            self._craft_record_paths(design),
        )

    @staticmethod
    def _observed_green(executed: OracleExecution | DeliveryOutcome) -> bool:
        """Did the whole executed set come back GREEN, read totally and closed?

        Every one of the four ways this can be anything else answers NO on its
        own branch: a `DeliveryOutcome` (the set could not be executed, or its
        report contradicted its exit status), a refusal (some oracle was `red`
        or `broken`), an EMPTY `measured` tuple (nothing was observed, which is
        not the same as observed green -- GDP-6), and any entry whose verdict is
        not the literal word `green` that `_oracle_verdict` produces.

        Read here rather than at the call site because "green" is a property of
        the EXECUTION, and a caller that re-derived it from exit statuses would
        be the second reading of a verdict this runner already owns.
        """
        if isinstance(executed, DeliveryOutcome):
            return False
        if executed.refusal is not None or not executed.measured:
            return False
        return all(item.get("verdict") == "green" for item in executed.measured)

    def _acceptance_files_available(
        self, root: Path, design: AuthorityFacts
    ) -> DeliveryOutcome | None:
        observed = [
            (path, self._regular_file(root / path)) for path in design.acceptance_paths
        ]
        unavailable = "; ".join(
            f"{'oracle' if index == 0 else 'acceptance support'} {path!r}: "
            + ("unobservable" if seen is None else "missing or not a regular file")
            for index, (path, seen) in enumerate(observed)
            if seen is not True
        )
        if any(seen is None for _, seen in observed):
            return self._fail(
                Disposition.Indeterminate,
                "OracleUnobservable",
                f"acceptance files declared by {design.locator!r} cannot all be "
                f"observed: {unavailable}",
                "restore read access to the named paths and inspect any missing "
                "files against their declaration before re-running the oracle step",
            )
        if unavailable:
            return self._fail(
                Disposition.Indeterminate,
                "OracleUnavailable",
                f"host-authored acceptance files declared by {design.locator!r} "
                f"are unavailable: {unavailable}",
                "restore the named acceptance files or correct their declaration "
                "before re-running the oracle step",
            )
        return None

    def measure_oracle(self, root: Path, selected: SelectedValue) -> MeasuredOracleSet:
        """Measure host-authored acceptance bytes and bind the observed witness."""
        stored, ready, design = selected.stored, selected.ready, selected.design
        preservation = self._prefactoring_ready(root, selected, before_behavior=True)
        if preservation is not None:
            return MeasuredOracleSet((), preservation)
        unavailable = self._acceptance_files_available(root, design)
        if unavailable is not None:
            return MeasuredOracleSet((), unavailable)
        executed = self._executed_oracle_set(root, [(ready.observation, design)])
        if isinstance(executed, DeliveryOutcome):
            return MeasuredOracleSet((), executed)
        if executed.refusal is not None:
            return MeasuredOracleSet(executed.measured, executed.refusal.terminal)
        if not self._record_oracle_turn(
            root, stored, ready.observation, design, executed.measured
        ):
            return MeasuredOracleSet(
                executed.measured,
                self._fail(
                    Disposition.Indeterminate,
                    "OracleRecordUnavailable",
                    "the measured acceptance bytes could not be recorded",
                    "restore Git record storage and repeat the measurement",
                ),
            )
        return MeasuredOracleSet(executed.measured, None)

    def _record_oracle_turn(
        self,
        root: Path,
        stored: StoredHandover,
        observation: str,
        design: AuthorityFacts,
        measured: tuple[dict[str, object], ...],
    ) -> bool:
        """Persist the measured oracle's exact content and authority identity."""
        head = self._head(root)
        if isinstance(head, DeliveryOutcome):
            return False
        tree = self._paths_tree(root, design.acceptance_paths)
        identity = self._record_identity(root, stored, observation, design)
        if tree is None or identity is None:
            return False
        self._record_turn(
            root,
            TurnRecordTarget(
                base=head,
                request=stored.request,
                values=((observation, identity),),
            ),
            role=_ORACLE_TURN,
            tree=tree,
        )
        self._record_oracle_witness(
            root,
            stored.request,
            observation,
            identity=identity,
            tree=tree,
            measured=measured,
        )
        return self.oracle_turn_complete(
            root,
            stored,
            next(value for value in stored.values if value.observation == observation),
            design,
        )

    def _record_oracle_witness(  # noqa: PLR0913 - one record's six coordinates
        self,
        root: Path,
        request: str,
        observation: str,
        *,
        identity: RecordIdentity,
        tree: str,
        measured: tuple[dict[str, object], ...],
    ) -> None:
        """Append this bound measurement's verdicts to the value's witness history.

        One commit per measurement over the measured acceptance tree, parented
        on the previous witness so earlier verdicts stay reachable, and carrying
        the WHOLE history in its body so one read answers "was this value's
        oracle ever observed RED, and against which revision".  Best-effort like
        every turn record: an unwritten witness reads as unmeasured, never as
        green.
        """
        ref = turn_ref(request, observation, ORACLE_WITNESS_TURN)
        previous = self._git(root, "rev-parse", "--verify", "--quiet", ref)
        history = list(self._oracle_witness_history(root, request, observation) or ())
        history.append(
            {
                "revision": identity.revision,
                "design_sections": identity.design_sections,
                "acceptance_tree": tree,
                "oracles": [
                    {
                        "oracle": item.get("path"),
                        "verdict": item.get("verdict"),
                        "axis": item.get("axis"),
                        "exit": item.get("exit"),
                        "counts": item.get("counts"),
                    }
                    for item in measured
                ],
            }
        )
        env = declared_child_environment()
        commit = self._git(
            root,
            "commit-tree",
            tree,
            *(() if previous.returncode else ("-p", previous.stdout.strip())),
            "-m",
            _WITNESS_SUBJECT,
            "-m",
            json.dumps(history, ensure_ascii=False, separators=(",", ":")),
            env=env,
        )
        if commit.returncode:
            return
        self._git(root, "update-ref", ref, commit.stdout.strip(), env=env)

    def oracle_witness(
        self,
        root: Path,
        stored: StoredHandover,
        observation: str,
        design: AuthorityFacts,
    ) -> tuple[dict[str, object], ...] | None:
        """Project history with currentness over the complete authority and bytes.

        Old verdicts remain visible, but a RED over another DESIGN or acceptance
        tree must not be mistaken for a RED over the currently selected oracle.
        Historical records lacking these coordinates are never current.
        """
        history = self._oracle_witness_history(root, stored.request, observation)
        if history is None:
            return None
        identity = self._record_identity(root, stored, observation, design)
        tree = self._paths_tree(root, design.acceptance_paths)
        return tuple(
            {
                **entry,
                "current": identity is not None
                and tree is not None
                and entry.get("revision") == identity.revision
                and entry.get("design_sections") == identity.design_sections
                and entry.get("acceptance_tree") == tree,
            }
            for entry in history
        )

    def _oracle_witness_history(
        self, root: Path, request: str, observation: str
    ) -> tuple[dict[str, object], ...] | None:
        """Every bound oracle measurement of one value, oldest first.

        ``()`` when no measurement was recorded for this value; ``None`` when
        the record exists but cannot be read as a witness history, which a
        packet projects as unmeasured rather than as either verdict.
        """
        ref = turn_ref(request, observation, ORACLE_WITNESS_TURN)
        if self._git(root, "rev-parse", "--verify", "--quiet", ref).returncode:
            return ()
        message = self._git(root, "show", "-s", "--format=%B", ref)
        subject, _, body = message.stdout.partition("\n\n")
        if message.returncode or subject.strip() != _WITNESS_SUBJECT:
            return None
        try:
            history = json.loads(body)
        except ValueError:
            return None
        if not isinstance(history, list) or not all(
            isinstance(entry, dict) for entry in history
        ):
            return None
        return tuple(history)

    def _archive_graph(self, root: Path, stored: StoredHandover) -> str | None:
        """Write the previous graph as a readable Git object, or `None`.

        A commit whose tree holds the handover bytes under a flat name, so
        `git cat-file -p <ref>:handover.json` returns them unchanged. The same
        plumbing `_owned_tree` uses -- a temporary index, `write-tree`,
        `commit-tree` -- so the real index, HEAD and the worktree are untouched.

        `None` when Git did not answer. The archive is EVIDENCE, and one that
        could not be written must never read as one that was: the caller prints
        no `ARCHIVE` row rather than a name pointing at nothing.
        """
        source = handover_path(root)
        blob = self._git(root, "hash-object", "-w", "--", str(source))
        if blob.returncode:
            return None
        descriptor, index = tempfile.mkstemp(prefix="nwave-archive-index-")
        os.close(descriptor)
        env = {**declared_child_environment(), "GIT_INDEX_FILE": index}
        try:
            # An empty FILE is not an empty index: git refuses it as "index file
            # smaller than expected". `read-tree --empty` writes the one the
            # next command can add to, exactly as `_owned_tree` seeds its index
            # from `base` before staging.
            seeded = self._git(root, "read-tree", "--empty", env=env)
            staged = self._git(
                root,
                "update-index",
                "--add",
                "--cacheinfo",
                f"100644,{blob.stdout.strip()},handover.json",
                env=env,
            )
            tree = self._git(root, "write-tree", env=env)
            if seeded.returncode or staged.returncode or tree.returncode:
                return None
        finally:
            with contextlib.suppress(OSError):
                Path(index).unlink()
        commit = self._git(
            root,
            "commit-tree",
            tree.stdout.strip(),
            "-m",
            f"nwave archive: {stored.request}",
            env=declared_child_environment(),
        )
        if commit.returncode:
            return None
        name = archive_ref(
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), stored.request
        )
        if self._git(root, "update-ref", name, commit.stdout.strip()).returncode:
            return None
        return name

    def _rekey_turn_records(
        self, root: Path, old_request: str, new_request: str, kept: tuple[str, ...]
    ) -> None:
        """Point every kept value's records at the new Request's digest.

        Without this every record would be orphaned, because the ref grammar is
        keyed by the Request. New ref first, old ref after, so an interruption
        leaves the record reachable under one key or both, never under none.
        """
        for observation in kept:
            for role in VALUE_TURN_ROLES:
                source = turn_ref(old_request, observation, role)
                observed = self._git(root, "rev-parse", "--verify", "--quiet", source)
                if observed.returncode:
                    continue
                target = turn_ref(new_request, observation, role)
                if self._git(
                    root, "update-ref", target, observed.stdout.strip()
                ).returncode:
                    continue
                self._git(root, "update-ref", "-d", source)

    def _drop_records_for(
        self, root: Path, request: str, observations: tuple[str, ...]
    ) -> None:
        """Drop the records of the values this rewrite archived, and no others.

        NARROWED from the whole-namespace release this runner used to do when a
        brand-new graph was persisted. That release is what made a hand deletion
        cost every paid turn behind it; here only what was NOT re-keyed goes.
        """
        for observation in observations:
            for role in VALUE_TURN_ROLES:
                self._git(
                    root, "update-ref", "-d", turn_ref(request, observation, role)
                )

    @staticmethod
    def _prefactoring_directory(root: Path, selected: SelectedValue) -> Path:
        request = hashlib.sha256(selected.stored.request.encode()).hexdigest()
        value = hashlib.sha256(selected.ready.observation.encode()).hexdigest()
        return root / ".nwave/des/logs/native/prefactoring" / request / value

    def _prefactoring_records(
        self, root: Path, selected: SelectedValue
    ) -> list[tuple[str, dict[str, object]]]:
        records = []
        directory = self._prefactoring_directory(root, selected)
        try:
            paths = list(directory.glob("*.json"))
            for path in paths:
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != path.stem:
                    continue
                record = json.loads(raw)
                if isinstance(record, dict):
                    records.append((path.relative_to(root).as_posix(), record))
        except (OSError, ValueError):
            return []
        return sorted(records, key=lambda item: item[1].get("observed_ns", 0))

    def _prefactoring_context(
        self, root: Path, selection: ApplicablePrefactoring
    ) -> dict[str, object]:
        return {
            "cwd": str(root),
            "executors": [
                self._preservation_executor(root, argv)
                for argv in selection.verification
            ],
            "environment": {"digest": self._child_environment_digest(dict(os.environ))},
        }

    def _preservation_executor(
        self, root: Path, argv: tuple[str, ...]
    ) -> dict[str, str | None]:
        shimmed = argv[0] in {"python", "python3", "pytest"} or (
            argv[0] == "des" and (root / "src/des/cli/__main__.py").is_file()
        )
        path = (
            self._subject_interpreter(root)[0]
            if shimmed
            else resolve_executable(argv[0], cwd=root)
        )
        digest = None
        if path is not None:
            try:
                with Path(path).open("rb") as executable:
                    digest = hashlib.file_digest(executable, "sha256").hexdigest()
            except OSError:
                path = None
        return {"path": path, "sha256": digest}

    def _prefactoring_identity(
        self, root: Path, selected: SelectedValue
    ) -> dict[str, object] | None:
        selection = selected.design.prefactoring
        if not isinstance(selection, ApplicablePrefactoring):
            return None
        identity = RecordIdentity.of(
            root, selected.stored, selected.ready, selected.design
        )
        witness_paths = (
            selection.existing_oracle.partition("::")[0],
            *selection.acceptance_supports,
        )
        if identity is None or any(
            self._regular_file(root / path) is not True for path in witness_paths
        ):
            return None
        witness = self._paths_tree(root, witness_paths)
        production = self._paths_tree(root, self._mutable_targets(selected.design))
        base = self._head(root)
        if witness is None or production is None or isinstance(base, DeliveryOutcome):
            return None
        return {
            "revision": asdict(identity),
            "base": base,
            "witness": witness,
            "production": production,
            "selection": asdict(selection),
            "context": self._prefactoring_context(root, selection),
        }

    def _same_preservation(
        self, root: Path, current: dict[str, object], recorded: dict[str, object]
    ) -> bool:
        # JSON roundtrip gives tuples the same representation as persisted input.
        canonical = json.loads(json.dumps(current))
        if not all(
            canonical[key] == recorded.get(key)
            for key in ("revision", "witness", "selection", "context")
        ):
            return False
        # HEAD is provenance, not witness identity. A preserving-only commit
        # may advance it, but evidence from an unrelated history is not reusable.
        previous, head = recorded.get("base"), current.get("base")
        if not isinstance(previous, str) or not isinstance(head, str):
            return False
        lineage = self._git(root, "merge-base", "--is-ancestor", previous, head)
        return lineage.unanswered is None and lineage.returncode == 0

    def _shared_prefactoring_unassigned(
        self, selected: SelectedValue
    ) -> DeliveryOutcome | None:
        """Refuse a shared applicable move that no value carries and measures.

        Only an applicable `prefactoring` declaration is measured (before-move /
        after-move-before-behavior).  A shared DESIGN that declares an applicable
        move while every value declares none, or a different one, would otherwise
        let delivery reach ORACLE and CRAFT with no preservation witness at all.
        The move is assigned when some value of the graph declares the same
        preservation witness (oracle, argv recipe, supports); that value measures
        it, so a sibling value that touches none of the moved bytes is not forced
        through a before/after pair it can never produce.
        """
        shared = selected.stored.shared_design
        move = None if shared is None else shared.design.prefactoring
        if not isinstance(move, ApplicablePrefactoring):
            return None

        def witness(item: ApplicablePrefactoring) -> tuple[object, ...]:
            return (item.existing_oracle, item.verification, item.acceptance_supports)

        declared = (
            selected.design.prefactoring,
            *(
                getattr(value.authority, "prefactoring", None)
                for value in selected.stored.values
            ),
        )
        if any(
            isinstance(item, ApplicablePrefactoring) and witness(item) == witness(move)
            for item in declared
        ):
            return None
        return self._fail(
            Disposition.Refusal,
            "SharedPrefactoringUnassigned",
            f"the shared DESIGN declares the applicable structural move on "
            f"{move.existing_oracle!r}, but no value declares that same "
            "preservation witness, so no before-move/after-move-before-behavior "
            "pair would ever be measured for it",
            "assign the shared move to one value's applicable `prefactoring` "
            "declaration with the same existing oracle, verification and supports "
            "(des design --value N --replace-current), or make the shared DESIGN's "
            "prefactoring not_applicable, then measure it before ORACLE",
        )

    def _prefactoring_ready(
        self, root: Path, selected: SelectedValue, *, before_behavior: bool = False
    ) -> DeliveryOutcome | None:
        unassigned = self._shared_prefactoring_unassigned(selected)
        if unassigned is not None:
            return unassigned
        if not isinstance(selected.design.prefactoring, ApplicablePrefactoring):
            return None
        current = self._prefactoring_identity(root, selected)
        records = dict(self._prefactoring_records(root, selected))
        for _, after in reversed(tuple(records.items())):
            if (
                current is not None
                and self._same_preservation(root, current, after)
                and after.get("production") == current["production"]
                and after.get("green") is False
            ):
                break
            before = records.get(after.get("before_locator"))
            if (
                current is not None
                and before is not None
                and after.get("phase") == "after-move-before-behavior"
                and after.get("green") is True
                and before.get("green") is True
                and before.get("phase") == "before-move"
                and self._same_preservation(root, current, after)
                and self._same_preservation(root, current, before)
                and self._same_preservation(root, after, before)
                and before.get("production") != after.get("production")
            ):
                if (
                    before_behavior
                    and not self.oracle_turn_complete(
                        root, selected.stored, selected.ready, selected.design
                    )
                    and current["production"] != after.get("production")
                ):
                    break
                return None
        return self._fail(
            Disposition.Refusal,
            "PrefactoringPreservationUnrecorded",
            "the applicable structural move lacks a current before-move/after-move-before-behavior GREEN pair with unchanged oracle, support, selection and execution context",
            "select craft --prefactoring-phase before-move on the existing GREEN state, perform only the declared move, then select craft --prefactoring-phase after-move-before-behavior before measuring the feature oracle",
        )

    def measure_prefactoring(
        self, root: Path, selected: SelectedValue, phase: str
    ) -> tuple[str, tuple[NativeEvidence, ...]] | DeliveryOutcome:
        selection = selected.design.prefactoring
        if phase not in {"before-move", "after-move-before-behavior"}:
            return self._fail(
                Disposition.Refusal,
                "PrefactoringPhaseInvalid",
                f"unsupported preservation phase {phase!r}",
                "select before-move or after-move-before-behavior",
            )
        if not isinstance(selection, ApplicablePrefactoring):
            return self._fail(
                Disposition.Refusal,
                "PrefactoringNotApplicable",
                "the current DESIGN does not select a structural move",
                "use ordinary craft for its declared not_applicable decision",
            )
        # Only a CURRENT record (its bytes and selected revision still match) makes
        # preservation too late; a moved or superseded ref is history, and a
        # replaced DESIGN that now owes a structural move must still be measurable.
        if self.oracle_turn_complete(
            root, selected.stored, selected.ready, selected.design
        ) or self.craft_turn_complete(
            root, selected.stored, selected.ready, selected.design
        ):
            return self._fail(
                Disposition.Refusal,
                "PrefactoringTooLate",
                "a feature oracle or craft is already recorded; post-feature GREEN cannot establish preservation before behavior",
                "retain this history and return the chronology finding to the host-selected architect/crafter",
            )
        current = self._prefactoring_identity(root, selected)
        if current is None:
            return self._fail(
                Disposition.Indeterminate,
                "PrefactoringIdentityUnavailable",
                "the existing oracle/support, production or authority identity is unavailable",
                "restore the declared existing oracle/support and Git access; do not substitute another test",
            )
        before_locator = None
        if phase == "after-move-before-behavior":
            for locator, before in reversed(self._prefactoring_records(root, selected)):
                if before.get("phase") == "before-move" and before.get("green") is True:
                    if self._same_preservation(root, current, before):
                        before_locator = locator
                    break
            if before_locator is None:
                return self._fail(
                    Disposition.Refusal,
                    "PrefactoringWitnessChanged",
                    "no preceding GREEN baseline has the same oracle/support, argv, authority and runtime context",
                    "restore the recorded preservation witness or return the changed selection to its host owner",
                )
            if current["production"] == before.get("production"):
                return self._fail(
                    Disposition.Refusal,
                    "PrefactoringProductionUnchanged",
                    "before and after identify the same production bytes, so no declared move was observed",
                    "perform the declared structural move before selecting the after phase",
                )
        evidence = self._native(
            root, selection.verification, root, run=NativeRun(capture_incomplete=True)
        )
        if isinstance(evidence, DeliveryOutcome):
            return evidence
        unchanged = self._prefactoring_identity(root, selected) == current
        green = (
            bool(evidence)
            and all(item.exit_status == 0 and not item.incomplete for item in evidence)
            and unchanged
        )
        stamp = time.time_ns()
        head = current["base"]
        witness_paths = (
            selection.existing_oracle.partition("::")[0],
            *selection.acceptance_supports,
        )
        snapshot = self._paths_tree(
            root,
            tuple(
                dict.fromkeys(
                    (
                        *self._mutable_targets(selected.design),
                        *witness_paths,
                    )
                )
            ),
        )
        if snapshot is None:
            return self._fail(
                Disposition.Indeterminate,
                "PrefactoringSnapshotUnavailable",
                "the measured production/witness snapshot could not be retained",
                "restore Git storage and repeat the selected measurement",
            )
        identity = RecordIdentity.of(
            root, selected.stored, selected.ready, selected.design
        )
        assert identity is not None
        role = f"prefactoring-{phase}-{stamp}"
        self._record_turn(
            root,
            TurnRecordTarget(
                base=head,
                request=selected.stored.request,
                values=((selected.ready.observation, identity),),
            ),
            role=role,
            tree=snapshot,
        )
        retained = self._git(
            root,
            "rev-parse",
            "--verify",
            self._turn_ref(selected.stored.request, selected.ready.observation, role),
        )
        if retained.returncode:
            return self._fail(
                Disposition.Indeterminate,
                "PrefactoringSnapshotUnavailable",
                "the measured snapshot has no retained Git reference",
                "restore Git storage and repeat the selected measurement",
            )
        record = {
            **current,
            "phase": phase,
            "observed_ns": stamp,
            "before_locator": before_locator,
            "green": green,
            "snapshot": retained.stdout.strip(),
            "evidence": self._evidence_records(evidence),
            # The only observation a preservation command yields is its exit
            # status over unchanged owned bytes: DES never reads an assertion
            # count, so a receipt is a primitive for the host/reviewer to
            # classify, never proof that an assertion ran.
            "observation_basis": "exit-status-only",
            "environment_public": dict(
                self._native_execution_context(root, dict(os.environ))[1]
            ),
        }
        raw = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        directory = self._prefactoring_directory(root, selected)
        path = directory / f"{hashlib.sha256(raw).hexdigest()}.json"
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as output:
                output.write(raw)
        except OSError as error:
            return self._fail(
                Disposition.Indeterminate,
                "PrefactoringEvidenceUnretained",
                str(error),
                "restore write access to the project-local native evidence directory",
            )
        locator = path.relative_to(root).as_posix()
        if not green:
            incomplete = next((item for item in evidence if item.incomplete), None)
            if incomplete is not None:
                return self._fail(
                    Disposition.Indeterminate,
                    incomplete.incomplete_what or "PrefactoringExecutionIncomplete",
                    f"{incomplete.incomplete_why}; retained at {locator}",
                    incomplete.incomplete_how
                    or "restore the selected native execution context",
                )
            if not unchanged:
                return self._fail(
                    Disposition.Refusal,
                    "PrefactoringOwnedDrift",
                    f"the native invocation changed owned production, witness or authority; retained at {locator}",
                    "retain the receipt and restore the declared immutable witness; do not clean unrelated files or bless this execution",
                )
            return self._fail(
                Disposition.Refusal,
                "PrefactoringNotGreen",
                f"{phase} did not observe unchanged preservation GREEN; actual evidence retained at {locator}",
                "read the retained native output, distinguish setup from behavior with its host owner, and repair only the declared structural move or substrate",
            )
        return locator, evidence

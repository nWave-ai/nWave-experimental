"""The resident, outcome-only owner of one whole-Request DES delivery."""

from __future__ import annotations

import contextlib
import errno
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, ClassVar
from xml.etree import ElementTree

from des.adapters.driven.codefact.code_fact_chain import CodeFactChain
from des.adapters.driven.git.git_observation import (
    GitObservation,
    declared_child_environment,
    observe_bytes,
    observe_text,
)
from des.adapters.driven.task_invocation.configured_task_adapter import (
    ModelRuntimeUnavailable,
)
from des.application.candidate_radius import INDETERMINATE, candidate_radius
from des.application.commit_message_attribution import attribute_commit_message
from des.application.design_document_producer import (
    bound_authority_headings,
    publish_design_document,
)
from des.application.handover import (
    Blocked,
    HandoverValue,
    StoredHandover,
    create_handover,
    design_basis_sha256,
    design_facts_defect,
    finalize_handover,
    handover_path,
    handover_unchanged,
    read_handover,
    retain_candidate_handover,
    rewrite_handover,
)
from des.application.head_advance import AdvanceRefusal, HeadAdvance
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
    new_target_acceptance_support_conflict,
)
from des.domain.delivery_disposition import Disposition
from des.domain.design_document import DesignFactsSection
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
from des.domain.model_runtime import ModelRuntimeConfigError, qualify_role_id
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
    VERIFY_OUTCOME_TURN,
    VERIFY_TURN,
    archive_ref,
    decision_ref,
    turn_ref,
    verify_upstream_ref,
)
from des.domain.verification_authority_resolver import (
    ResolvedAuthoritySection,
    authority_section_sha256,
    resolve_authority_section,
)
from des.ports.driven_ports.task_invocation_port import (
    MINIMUM_OBSERVATION_CHARACTERS,
    CraftBlocker,
    DefectOwner,
    DesignFacts,
    MalformedModelEnvelope,
    ModelOutcome,
)
from des.runtime.spawn import (
    SpawnRefusal,
    classify_spawn_refusal,
    resolve_executable,
    spawn,
)


if TYPE_CHECKING:
    from collections.abc import Callable

    from des.application.design_document_producer import PublishedDesignDocument
    from des.domain.distill_document import AcceptanceObligation
    from des.ports.driven_ports.task_invocation_port import (
        ModelRun,
        ProductValue,
        TaskInvocationPort,
    )


#: The ONE repair every inadmissible-design-facts refusal names.  The path it
#: quotes is asserted against :func:`handover_path` in the tests, because a HOW
#: naming a file the software does not actually use is a rejection that lies.
_DESIGN_FACTS_REPAIR = (
    "return typed design facts whose named field carries the shape the "
    "contract requires; when the authority is already bound, delete "
    ".nwave/des/handover.json to re-elicit DESIGN for this Request"
)


#: The turn-record namespace and its two roles now have a SECOND reader -- the
#: read-only state projection -- so the grammar is SSOT in
#: `des.domain.turn_record_ref` and these are its local spellings.
#: The subject grammar of the two judgement records. A constant prefix, so a
#: reader that finds some other commit under the ref answers "unknown" rather
#: than reading an arbitrary subject line as a verdict.
_VERDICT_SUBJECT = "nwave verify: "
_DECISION_SUBJECT = "nwave integrate on orchestrator evidence over verdict: "

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
    model_runs: tuple[ModelRun, ...] = ()


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
    environment is deliberately the closed, nonsecret Python/pytest projection;
    a record made without an invocation retains None for every one of these
    facts, which is unknown rather than a successful context.
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


class CraftSettlement(Enum):
    """How a value's craft turn stands, as ONE closed word the step branches on.

    Three members and no fourth, because the caller has exactly three moves:
    report the turn already recorded over these very bytes, report that an
    observed-green oracle settled a record whose bytes had MOVED, or buy the
    crafter turn.  A pair of booleans would admit a fourth, meaningless state --
    «recorded over current bytes AND settled by a green oracle» -- and would let
    two call sites drift on which one wins; a closed word makes that
    unrepresentable (GDP-0, representation before validation).

    `RecordedOverCurrentBytes` is answered by CALLING `craft_turn_complete` and
    never by a second spelling of tree equality: ADR-DES-003 §5 requires that
    question to be read by ONE predicate, and `des state`'s read-only projection
    is its other reader.

    `Unsettled` is also the answer every UNRESOLVED measurement degrades to -- a
    Git that would not say what HEAD is, an owned tree that did not resolve, an
    oracle that is red, broken or could not be executed at all.  An unresolved
    measurement never authorises a skipped turn, so the only cost of any of them
    is the turn that would have been bought anyway.
    """

    RecordedOverCurrentBytes = "recorded-over-current-bytes"
    SettledByGreenOracle = "settled-by-green-oracle"
    Unsettled = "unsettled"


class OracleSettlement(Enum):
    """How a value's ORACLE turn stands, as ONE closed word the step branches on.

    Three members and no fourth, for the reason `CraftSettlement` states: a pair
    of booleans would admit «recorded over current bytes AND settled by its own
    execution», which means nothing, and would let two call sites drift on which
    one wins.

    A SECOND enum rather than a widened `CraftSettlement`, because the two lanes
    admit DIFFERENT witnesses.  Craft settles only on an all-GREEN oracle -- a
    red one is evidence the work is not done.  The oracle lane settles on any
    RESOLVED verdict, red or green, because what it needs witnessed is that the
    authored oracle still reaches its own assertion, and RED is the admitted
    answer before craft.  `CraftSettlement.SettledByGreenOracle` names the
    stricter witness in its own member name, and renaming it to cover both lanes
    would rewrite the craft lane's vocabulary to say something it does not mean.

    `RecordedOverCurrentBytes` is answered by CALLING `oracle_turn_complete` and
    never by a second spelling of tree equality: ADR-DES-003 §5 requires that
    question to be read by ONE predicate, and `des state`'s read-only projection
    is its other reader.

    `Unsettled` is the answer every UNRESOLVED measurement degrades to -- an
    absent record, a tracked acceptance path that is gone or that the filesystem
    would not answer for, an execution that did not resolve, a Git that would not
    say what HEAD is, an owned tree that did not resolve.  None of them
    authorises a skipped turn, so the only cost of any of them is the
    acceptance-designer turn that would have been bought anyway.
    """

    RecordedOverCurrentBytes = "recorded-over-current-bytes"
    SettledByItsOwnExecution = "settled-by-its-own-execution"
    Unsettled = "unsettled"


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
class RequestRewrite:
    """What a rewritten Request kept, archived and added -- all three, always.

    ADR-DES-003 §7: the terminal shows both lists «so the split can be
    corrected». A rewrite that reported only what it kept would make an
    archived value indistinguishable from one that never existed.
    """

    kept: tuple[str, ...]
    archived: tuple[str, ...]
    fresh: tuple[str, ...]
    archive: str | None


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
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


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

    def __init__(self, invoker: TaskInvocationPort | None = None) -> None:
        self._invoker = invoker
        self._model_runs: list[ModelRun] = []
        self._design_changed: tuple[str, ...] = ()
        self._design_unchanged = False
        self._radius = INDETERMINATE
        # Provider turns whose PROCESS ran, which is not the same set as the
        # turns whose answer survived. A malformed envelope leaves no ModelRun
        # and still costs a turn; counting the process is the only fact that
        # separates "nothing was spent" from "something was spent and its words
        # did not reach us".
        self._turns_bought = 0
        self._last_role: str | None = None
        self._native_evidence_locator: str | None = None
        self._native_evidence_sha256: str | None = None
        # The authority section the last `design_value` PUBLISHED, or `None`
        # when that turn's facts named no configured section.  A measurement,
        # never a decision: the step prints it and nothing branches on it.
        self._published_design: PublishedDesignDocument | None = None

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
    def _prompt(**facts: object) -> str:
        """Every dynamic prompt fact remains exactly one JSON value."""
        return "\n".join(
            f"{key}: {json.dumps(value, ensure_ascii=False)}"
            for key, value in facts.items()
        )

    @classmethod
    def _rooted(cls, root: Path, prompt: str) -> str:
        """The turn's own absolute root, appended by the software that owns it.

        The root is a fact of the RUNNER: it is the very directory this method's
        caller is about to hand the provider as `cwd`, so no role can read it off
        anything it receives, and every path in the facts above is written
        relative to it.  Measured 2026-09-06, run 25: no role prompt named the
        root, and three turns spent six denied Read calls inventing one --
        `/home/user/repo/src/des/...` in the architect's turn, and
        `/tests/des/unit/...` read from the filesystem root in two designer
        turns.  Nothing there was a semantic error; the software simply never
        stated what only it knew (`boundary:software-measures-model-decides`).

        It is appended, never prepended: the first fact a role reads is still the
        unit it was assigned, and it lands HERE rather than at the ten `_prompt`
        call sites because this is the one place that holds the root -- which is
        what makes forgetting it unrepresentable at a new site (GDP-0).
        """
        return "\n".join(
            (
                prompt,
                cls._prompt(
                    repository_root=str(
                        root if root.is_absolute() else Path.cwd() / root
                    ),
                    path_convention=(
                        "Every relative path in this prompt resolves against "
                        "repository_root, which is this turn's working directory."
                    ),
                ),
            )
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

    def resolve_port(self, root: Path) -> TaskInvocationPort | DeliveryOutcome:
        """The provider port one step will spend its single turn on.

        Public because a step invoked ALONE has to resolve the port before it
        takes the lock, and the resolution can itself fail -- an absent
        launcher is a terminal the orchestrator must read, not a traceback.
        """
        return self._port(root)

    @property
    def last_review_owner(self) -> str | None:
        """The owner the last judge named, or `None` when none did.

        The whole-diff reviewer is the oracle's only independent judge now
        (ADR-DES-003 §5), so a finding it charges to the oracle is what sends
        the orchestrator to `des oracle --finding -` rather than to the crafter
        -- the same routing the craft blocker already carries, on the other
        side of the candidate.
        """
        if not self._model_runs:
            return None
        defect = self._model_runs[-1].review_defect
        return None if defect is None else defect.owner.value

    @property
    def last_review_value(self) -> str | None:
        """The value observation the last judge charged, when it named one."""
        if not self._model_runs:
            return None
        defect = self._model_runs[-1].review_defect
        return None if defect is None else defect.value

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

    def persist_native_radius(self, root: Path, candidate: str) -> bool:
        if self._native_evidence_sha256 is None:
            return False
        directory = root / ".nwave" / "des" / "logs" / "radius"
        body = {
            "candidate_sha": candidate,
            "native_evidence_sha256": self._native_evidence_sha256,
            "radius": self._radius,
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
        try:
            records = sorted(directory.glob(f"{candidate}-*.json"))
        except OSError:
            return False
        if len(records) != 1:
            return False
        path = records[0]
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
        ):
            return False
        self._native_evidence_locator = path.relative_to(root).as_posix()
        self._native_evidence_sha256 = actual_digest
        return True

    @property
    def design_unchanged(self) -> bool:
        """Did the last architect correction repeat the facts it was correcting?

        A measurement the terminal prints as `UNCHANGED:`, never a refusal.
        """
        return self._design_unchanged

    @property
    def published_design(self) -> PublishedDesignDocument | None:
        """The authority section this runner's last design turn published.

        `None` means no section was published -- the returned facts named no
        configured document -- so the caller prints no DOCUMENT rows rather
        than a locator pointing at bytes nothing wrote.
        """
        return self._published_design

    @property
    def last_role(self) -> str | None:
        """The last role whose PROCESS ran, or `None` when none did.

        A primitive row (ADR-DES-003 G6) with two named consumers: the derived
        `ORCHESTRATOR` line, which used to guess «the refusing judge» when the
        AUTHOR had rejected, and the census discipline that says to name the
        sender before counting.
        """
        return self._last_role

    @property
    def turns_bought(self) -> int:
        """Provider turns whose PROCESS ran during this runner's life.

        NOT the number of answers received. A malformed envelope costs a turn
        and leaves no `ModelRun`, so counting answers would report zero over
        money that was spent -- which is exactly the claim a terminal must not
        make about its own cause.
        """
        return self._turns_bought

    @property
    def last_blocker(self) -> str | None:
        """The closed word a refusing craft turn named, or `None`.

        Public and READ-ONLY: a step invoked alone forwards it to the
        orchestrator as data, exactly as `DIAGNOSTIC` forwards prose.  Nothing
        outside the composed run's own window may branch on it.
        """
        if not self._model_runs:
            return None
        blocker = self._model_runs[-1].craft_blocker
        return None if blocker is None else blocker.value

    @property
    def last_diagnostic(self) -> str | None:
        """The last role turn's own words, or `None` when no turn ever ran.

        Forwarded VERBATIM and never parsed: Section 4b requires a step's WHY
        to carry the role's own diagnostic, and the whole reason it is opaque
        evidence is that model-authored prose is not a control-plane input.
        """
        return self._model_runs[-1].diagnostic if self._model_runs else None

    def _port(self, root: Path) -> TaskInvocationPort | DeliveryOutcome:
        if self._invoker is not None:
            return self._invoker
        from des.adapters.driven.task_invocation.configured_task_adapter import (
            ConfiguredTaskAdapter,
        )

        return ConfiguredTaskAdapter(root)

    def _invoke(
        self,
        port: TaskInvocationPort,
        root: Path,
        role: str,
        prompt: str,
        handover_bytes: bytes | None,
        handover_root: Path | None = None,
        max_product_values: int | None = None,
        defect_values: tuple[str, ...] = (),
        semantic_task: str | None = None,
    ) -> ModelRun | DeliveryOutcome:
        prompt = self._rooted(root, prompt)
        for attempt in range(2):
            frozen = (
                handover_unchanged(handover_root or root, handover_bytes)
                if handover_bytes is not None
                else None
            )
            if frozen is not None:
                return self._blocked(frozen)
            try:
                invocation = {
                    "role_id": role,
                    "prompt": prompt,
                    "cwd": root,
                    "max_product_values": max_product_values,
                    "defect_values": defect_values,
                }
                if semantic_task is not None:
                    invocation["semantic_task"] = semantic_task
                run = port.invoke(**invocation)
            except (ModelRuntimeUnavailable, ModelRuntimeConfigError) as error:
                return self._fail(
                    Disposition.Retry,
                    "ModelNotIssued",
                    str(error),
                    "repair model_runtime configuration or restore its selected launcher and retry",
                )
            except OSError as error:
                # NOT an envelope defect: the child process was never created,
                # so there is no provider result to observe and the envelope
                # HOW would send the operator to look at nothing.  Measured
                # 2026-09-05, run 12: `[Errno 7] Argument list too long` was
                # reported as `ModelEnvelopeUnavailable`, HOW "observe the
                # provider result" -- a rejection that lies about its own cause.
                return self._fail(
                    Disposition.Indeterminate,
                    "ProviderSpawnFailed",
                    f"the operating system refused to start the provider: {error}",
                    "read the reported errno: no provider process existed, so no "
                    "turn was spent and nothing was written",
                )
            except MalformedModelEnvelope as error:
                # The process RAN and answered unusably, so the turn is spent.
                # Its sibling above is the opposite world and already says so:
                # `ProviderSpawnFailed` states that no provider process existed
                # and no turn was spent. Counting here is what keeps the two
                # distinguishable downstream (2026-09-06: a terminal told its
                # reader "the software refused before buying one" over a turn
                # the provider log shows was bought).
                self._turns_bought += 1
                self._last_role = role
                return self._fail(
                    Disposition.Indeterminate,
                    "ModelEnvelopeUnavailable",
                    str(error),
                    "observe the provider result",
                )
            if not run.issued:
                return self._fail(
                    Disposition.Retry,
                    "ModelNotIssued",
                    run.diagnostic,
                    "repair the selected role runtime or its capability profile and retry",
                )
            self._turns_bought += 1
            self._last_role = role
            self._model_runs.append(run)
            frozen = (
                handover_unchanged(handover_root or root, handover_bytes)
                if handover_bytes is not None
                else None
            )
            if frozen is not None:
                return self._blocked(frozen)
            if not run.exit_status:
                return run
            if not run.retry_safe:
                return self._fail(
                    Disposition.Indeterminate,
                    "IssuedUncertain",
                    run.diagnostic or "provider did not complete cleanly",
                    "observe real effect",
                )
            # A selected-revision recovery is deliberately one paid
            # acceptance-designer turn.  A provider-level failure still reaches
            # the caller as a retryable terminal, but DES must not buy a second
            # turn on its own: the caller chooses whether and when to retry.
            if attempt or semantic_task == "selected-revision-recovery":
                return self._fail(
                    Disposition.Retry,
                    "ProviderRetry",
                    run.diagnostic or "provider did not complete cleanly",
                    "restore provider evidence",
                )
        raise AssertionError("two-attempt provider retry loop exhausted")

    def _accepted(
        self,
        run: ModelRun | DeliveryOutcome,
        *,
        rejected: str,
        indeterminate: str,
        handover: bool,
    ) -> DeliveryOutcome | None:
        """The non-accepting terminal for one turn, or ``None`` when accepted.

        ``handover`` is the caller's own primitive fact: whether a durable graph
        exists for this Request at the moment the turn ended.  It is a required
        keyword, not a default, because the HOW is only true on one side of it
        and a default would silently pick the wrong side at a new call site --
        which is exactly the defect this parameter exists to make
        unrepresentable.  Every caller already holds the fact: the first
        classification runs with no handover by construction, every later turn
        runs with the stored graph in hand.
        """
        if isinstance(run, DeliveryOutcome):
            return run
        if run.outcome is ModelOutcome.Accepted:
            return None
        return self._fail(
            Disposition.Refusal
            if run.outcome is ModelOutcome.Rejected
            else Disposition.Indeterminate,
            rejected if run.outcome is ModelOutcome.Rejected else indeterminate,
            run.diagnostic,
            # The runner cannot name the repair: only the role's own diagnostic,
            # carried verbatim as the WHY, knows what it refused or could not
            # decide, and inventing a remedy here would be advice this run never
            # earned.  What the runner DOES own is the resume, so the HOW names
            # that instead of restating the WHY.  Measured 2026-09-05, run 15:
            # the terminal read "resolve the named uncertainty" and named no
            # action at all.
            #
            # And the resume is not one fact.  Measured 2026-09-05, run
            # 20260905T062139Z-38400: a FIRST classification refused, and the
            # terminal promised "this outcome preserved the handover and every
            # WIP byte" when no handover had ever existed and no byte was WIP.
            # A rejection that lies about the state it leaves behind is worse
            # than a bare traceback, so the HOW branches on the fact and states
            # only the MOVE.  Whether a graph survived is not claimed here at
            # all: `des.domain.orchestrator_terminal` states it once, from a
            # measurement taken where the run ends, and a sentence asserting it
            # from inside the run is exactly the claim that turned out false.
            "act on the finding stated above, then re-run the Request"
            if handover
            else "correct the Request and re-run it: no handover exists yet",
        )

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
        before_status: str,
        before_bytes: dict[str, tuple[str, bytes | str]],
        allowed: tuple[str, ...] = (),
        declared: tuple[str, ...] = (),
        owns: Callable[[str], bool] | None = None,
    ) -> ScopeObservation | DeliveryOutcome:
        """Observe one comparison: outside the role's own paths, and those themselves."""
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
        paths = tuple(dict.fromkeys((*before_bytes, *_status_paths(status.stdout))))
        after_bytes = _workspace_bytes(root, paths)
        return _scope_observation(
            _scope_changes(before_status, before_bytes, status.stdout, after_bytes, ()),
            declared,
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

    def _measured_by_design(self, drift: ScopeObservation) -> None:
        """Keep every byte a design turn moved inside its own substrate.

        The measurement already EXISTS.  `in_scope` is the other half of the
        single comparison that decides whether the turn stayed inside the paths
        it owns, so delivering it costs no second walk of the workspace and
        cannot disagree with the scope refusal about which bytes moved.

        It accumulates across the Request because one aggregate review judges
        the whole set: the authoring turns, and the one correction turn, all
        write into the same substrate the judge is about to be asked about.
        """
        self._design_changed = tuple(
            dict.fromkeys((*self._design_changed, *drift.in_scope))
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
            typed = AuthorityFacts(
                locator.authority_locator or f"typed:{locator.oracle}",
                (),
                tuple((target.path, target.decision) for target in locator.targets),
                locator.paradigm,
                locator.decisions,
                locator.obligations,
                locator.oracle,
                (oracle, *locator.acceptance_supports),
                locator.verification,
                locator.oracle_verification_index,
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
        conflict = new_target_acceptance_support_conflict(
            oracles[0],
            ((row.path, row.decision) for row in targets),
            supports,
        )
        if conflict is not None:
            return DeliveryContinuationRunner._fail(
                Disposition.Indeterminate,
                "TargetAcceptanceSupportConflict",
                "a non-oracle CREATE_NEW target is also a required acceptance "
                f"support: {conflict}",
                "declare that path only as a support, or make its target decision "
                "EXTEND before binding DESIGN",
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
        answered with a resolved provider and the real call sites.  Two runs
        paid for a defect of PRECONDITION, which
        `boundary:software-measures-model-decides` bills to the software.

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
        """Write the interpreter shims.  UNCONDITIONAL, unlike the `des` one.

        TWO CONDITIONS, deliberately separated, because they answer to different
        facts (GDP-10 -- one condition covering both would be wrong in one
        direction or the other):

        * The `des` shim is armed only when the CANDIDATE SHIPS `src/des`.  It
          shadows a name that means something else in a non-DES repository, so
          arming it everywhere would break every non-DES subject to repair a
          defect none of them has.
        * The interpreter shims are armed for EVERY candidate.  `python`,
          `python3` and `pytest` do not name a candidate's own tree at all --
          they name the interpreter that runs its verification, and the runner
          IS an interpreter.  There is no subject for which they mean something
          the runner should defer to.

        MEASURED, run 18 (2026-09-05 07:14): the architect declared
        `python -m pytest ... -q`, the common spelling and the one the standing
        repair for the venv-relative form points at.  This box carries only
        `python3`, so the spawn failed at `execve` before anything ran.  A name
        the box does not carry is not a defect of the model.

        Shadowing rather than deferring is the point.  A `python` that DOES
        resolve on `PATH` need not be the interpreter that carries the
        candidate's `PYTHONPATH`, is not guaranteed to be the version the runner
        runs, and is not the one `NATIVE-RUNTIME` names -- which is exactly the
        silent divergence between two projections of one name that the `des`
        shim exists to close.  One name, one interpreter, printed.
        """
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
    def _candidate_runtime(
        root: Path, shims: Path, subject: Path, venv_link: str, index_link: str
    ) -> dict[str, str]:
        """The child environment in which the CANDIDATE's own code wins.

        A declared verification argv names a PORT -- `des code-fact ...`,
        `python -m pytest ...`.  WHERE that name resolves is enactment, and
        enactment is the runner's (`boundary:software-measures-model-decides`):
        the model cannot know that this box carries three projections of `des`
        and that a bare name picks the installer's shim.  Measured 2026-09-05 in
        an ephemeral candidate worktree: `des` resolved to `~/.claude/bin/des`
        and through it to the recorded active runtime, while `import des` under
        the development venv resolved through an editable `.pth` holding
        ABSOLUTE paths into the main checkout.  Neither is the candidate, both
        answer exit 0 with real output, and the source-blind reviewer cannot
        tell.  That is silent-wrong, not incompleteness.

        ONE measured fact arms the whole construction -- the candidate SHIPS the
        tree a declared name would otherwise reach -- and two halves then close
        it together, so the guarantee and the code have a single condition
        rather than one each:

        * `PYTHONPATH` carries the candidate's own `src` and root FIRST, so
          every interpreter child imports the candidate.  `PYTHONPATH` is
          consulted before site-packages, so an editable `.pth` cannot win.
        * a runner-owned directory carrying a `des` shim goes FIRST on `PATH`,
          because a console script sets its own `sys.path` and `PYTHONPATH`
          alone cannot reach it.

        Both halves are therefore conditional (GDP-10), and the earlier version
        of this docstring claimed that while the `PYTHONPATH` half was in fact
        unconditional: an independent review measured a non-DES subject
        receiving the candidate root on `PYTHONPATH` anyway.  A subject that
        ships no `src/des` is a repository where a declared `des` genuinely
        means the installed analysis tool, and imposing anything there would
        change how every non-DES subject imports to repair a defect none of
        them has.  Such a subject leaves this method with its IMPORT PATH
        untouched.

        The INTERPRETER shims (`_arm_interpreter_shims`) are the third piece and
        carry a DIFFERENT condition -- none.  They name no candidate tree, only
        the interpreter that runs the verification, so the shim directory goes
        on `PATH` for every subject and this method no longer returns the
        inherited environment byte for byte for any of them.  The two conditions
        are separated there, with the measured run that forced it.

        Nothing is stripped from the
        inherited environment: measured on this box, none of `NWAVE_RUNTIME`,
        `NWAVE_AGENTS_HOME`, `CLAUDE_CONFIG_DIR`, `PYTHONPATH` or `VIRTUAL_ENV`
        was set, so a strip list would be precautionary ceremony, and the shim
        reads none of them anyway.

        STATED LIMIT.  The `PATH` half is POSIX-shaped: it relies on a shebang,
        so on Windows a bare `des`, `python` or `pytest` would still reach
        whatever the installer put on `PATH`.  The `PYTHONPATH` half is portable and already covers every
        interpreter child and every console script that imports `des` normally
        -- which is what the installer's own shim, itself a shebang script, is
        the single exception to.  Naming the gap here rather than pretending
        the guarantee is total.
        """
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        source = root / "src"
        interpreter, provenance = DeliveryContinuationRunner._subject_interpreter(
            subject
        )
        armed = DeliveryContinuationRunner._arm_interpreter_shims(shims, interpreter)
        if (source / "des" / "cli" / "__main__.py").is_file():
            inherited = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = os.pathsep.join(
                [str(source), str(root), *([inherited] if inherited else [])]
            )
            DeliveryContinuationRunner._write_shim(
                shims / "des",
                DeliveryContinuationRunner._CANDIDATE_SHIM.format(source=str(source)),
                interpreter,
            )
            armed.append("des")
        path = env.get("PATH", "")
        env["PATH"] = os.pathsep.join([str(shims), *([path] if path else [])])
        # Operator channel only, exactly like the CLI's `DELIVERY-RUNTIME` line
        # and for the identical reason: run 17's false negative was invisible
        # because nothing said WHICH code answered.  Deliberately NOT added to
        # `NativeEvidence`: the reviewer already receives argv, exit status,
        # stdout and stderr, and once the construction above holds there is no
        # verdict it could reach differently by reading a provenance field, so
        # that field would be ceremony (GDP-10).
        print(
            f"NATIVE-RUNTIME: candidate={root} source={source} "
            f"python={interpreter} python-source={provenance} "
            f"subject-venv-link={venv_link} subject-index-link={index_link} "
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
        origin: str = DECLARED_ORIGIN,
        changed: tuple[str, ...] = (),
        capture_incomplete: bool = False,
    ) -> tuple[NativeEvidence, ...] | DeliveryOutcome:
        """`root` is the tree under verification; `subject` is the repository.

        `origin` labels every record this execution produces and determines the
        refusal policy.  Public verification executes design-declared vectors:
        a spawn the kernel will not start leaves the run with no verification,
        so it terminates.  The retained metadata does not create a separate
        Request-authored execution path.

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
        venv_link = self._link_subject_venv(subject, root)
        index_link = self._link_subject_index(subject, root)
        try:
            with tempfile.TemporaryDirectory(prefix="nwave-native-runtime-") as shims:
                return self._native_evidence(
                    root,
                    commands,
                    {
                        **self._candidate_runtime(
                            root, Path(shims), subject, venv_link, index_link
                        ),
                        **(extra_env or {}),
                    },
                    origin,
                    self._subject_test_paths(subject),
                    changed,
                    capture_incomplete,
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
        origin: str = DECLARED_ORIGIN,
        test_paths: tuple[str, ...] = (),
        changed: tuple[str, ...] = (),
        capture_incomplete: bool = False,
    ) -> tuple[NativeEvidence, ...] | DeliveryOutcome:
        """The ordered execution itself, over an environment already built.

        Split from :meth:`_native` only so the constructed environment is a
        parameter rather than a hidden effect of the loop -- the shim directory
        lives exactly as long as the commands that may resolve through it.
        """
        with tempfile.TemporaryDirectory(prefix="nwave-exercised-") as probe:
            reports = Path(probe)
            (reports / f"{self._EXERCISED_PROBE_MODULE}.py").write_text(
                self._EXERCISED_PROBE.format(variable=self._EXERCISED_REPORT_VAR),
                encoding="utf-8",
            )
            evidence: list[NativeEvidence] = []
            observational = origin != DECLARED_ORIGIN
            for index, argv in enumerate(commands):
                touches = touches_test_paths(tuple(argv), test_paths)
                report = reports / f"{index}.txt"
                command_env = self._probed(argv, env, reports, report)
                cwd, declared_environment = self._native_execution_context(
                    root, command_env
                )
                started = time.monotonic()
                try:
                    completed = spawn(
                        list(argv),
                        cwd=str(root),
                        capture_output=True,
                        text=True,
                        errors="replace",
                        env=command_env,
                    )
                except OSError as refused:
                    duration_seconds = time.monotonic() - started
                    if observational:
                        evidence.append(
                            self._unobserved(
                                tuple(argv),
                                str(refused),
                                origin,
                                touches,
                                self._exercised(argv, None, root, test_paths, changed),
                                duration_seconds,
                                cwd,
                                declared_environment,
                            )
                        )
                        continue
                    refusal = self._verification_refused(tuple(argv), refused, root)
                    if not capture_incomplete:
                        return refusal
                    assert refusal.failure is not None
                    evidence.append(
                        self._incomplete_native(
                            tuple(argv),
                            "",
                            f"not executed: {refused}",
                            origin,
                            touches,
                            self._exercised(argv, None, root, test_paths, changed),
                            refusal.failure,
                            duration_seconds,
                            cwd,
                            declared_environment,
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
                                origin,
                                touches,
                                self._exercised(argv, None, root, test_paths, changed),
                                duration_seconds,
                                cwd,
                                declared_environment,
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
                    if not capture_incomplete:
                        return self._fail(
                            Disposition.Indeterminate,
                            failure.what,
                            failure.why,
                            failure.how,
                        )
                    evidence.append(
                        self._incomplete_native(
                            tuple(argv),
                            self._stream_text(unbounded.output),
                            self._stream_text(unbounded.stderr),
                            origin,
                            touches,
                            self._exercised(argv, None, root, test_paths, changed),
                            failure,
                            duration_seconds,
                            cwd,
                            declared_environment,
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
                        origin,
                        touches,
                        self._exercised(
                            argv, self._read_report(report), root, test_paths, changed
                        ),
                        duration_seconds=duration_seconds,
                        cwd=cwd,
                        declared_environment=declared_environment,
                    )
                )
            return tuple(evidence)

    @staticmethod
    def _unobserved(
        argv: tuple[str, ...],
        reason: str,
        origin: str,
        touches: bool,
        exercised: ExercisedModules = UNEXERCISED,
        duration_seconds: float | None = None,
        cwd: str | None = None,
        declared_environment: tuple[tuple[str, str], ...] | None = None,
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
            origin,
            touches,
            exercised,
            duration_seconds=duration_seconds,
            cwd=cwd,
            declared_environment=declared_environment,
        )

    @staticmethod
    def _stream_text(value: str | bytes | None) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", "replace")
        return value or ""

    @staticmethod
    def _incomplete_native(
        argv: tuple[str, ...],
        stdout: str,
        stderr: str,
        origin: str,
        touches: bool,
        exercised: ExercisedModules,
        failure: FailureDetail,
        duration_seconds: float | None = None,
        cwd: str | None = None,
        declared_environment: tuple[tuple[str, str], ...] | None = None,
    ) -> NativeEvidence:
        """Keep a declared command's partial observation with its terminal fact."""
        return NativeEvidence(
            argv,
            None,
            stdout,
            stderr,
            origin,
            touches,
            exercised,
            incomplete=True,
            incomplete_what=failure.what,
            incomplete_why=failure.why,
            incomplete_how=failure.how,
            duration_seconds=duration_seconds,
            cwd=cwd,
            declared_environment=declared_environment,
        )

    @staticmethod
    def _native_execution_context(
        root: Path, env: dict[str, str]
    ) -> tuple[str, tuple[tuple[str, str], ...]]:
        """The nonsecret, command-relevant context captured before its spawn.

        This is the same closed environment projection used by the native hook
        receipt.  In particular, PATH and the ambient process environment are
        intentionally absent: they may expose credentials and are not needed
        to explain the Python/pytest execution declared here.
        """
        return (
            str(root),
            tuple(
                (name, env[name])
                for name in ("PYTHONPATH", "PYTEST_ADDOPTS")
                if name in env
            ),
        )

    @classmethod
    def _probed(
        cls,
        argv: tuple[str, ...] | list[str],
        env: dict[str, str],
        probe: Path,
        report: Path,
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
                self._admitted_verification_form(root),
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
        payload = json.dumps(
            cls._evidence_records(evidence), ensure_ascii=False, indent=1
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
        result: list[tuple[str, str]] = []
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
        self,
        root: Path,
        base: str,
        request: str,
        values: tuple[tuple[str, RecordIdentity], ...],
        role: str,
        tree: str,
    ) -> None:
        """Write one turn commit per (observation, identity) and point its ref.

        The commit's job is to be found again and compared: its message names
        the value's selected-revision identity, so a record of another revision
        reads as moved bytes.  It claims to be no delivery commit.

        Recording is best-effort for the same reason reading is: a record that
        is not written costs the NEXT run one re-invoked turn and nothing else.
        """
        env = declared_child_environment()
        for observation, identity in values:
            commit = self._git(
                root,
                "commit-tree",
                tree,
                "-p",
                base,
                "-m",
                self._turn_message(role, identity),
                env=env,
            )
            if commit.returncode:
                continue
            self._git(
                root,
                "update-ref",
                self._turn_ref(request, observation, role),
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
        base: str,
        base_tree: str,
        request: str,
        values: tuple[tuple[str, RecordIdentity], ...],
        mutable: tuple[str, ...],
        record_paths: tuple[str, ...],
    ) -> None:
        """Point a craft record at the CURRENT bytes, or drop it when there are none.

        "Wrote nothing" is judged over the ``mutable`` targets alone; the
        record itself is the tree over ``record_paths``.

        A record buys back WORK, and a turn that contributed nothing has none to
        buy back.  Recording one would make the empty-owner repair -- "rerun the
        dispatch so the crafter changes its batch's mutable targets" -- reuse
        the same silent turn and refuse again, which is a rejection that lies.

        The same rule decides at the turn AND after the runner's own
        normalization, because normalization can reach that state honestly: a
        turn whose only edit was whitespace the declared formatter undoes wrote
        no bytes, and `_candidate` already says so about its own tree.
        """
        written = self._owned_tree(root, base, mutable)
        if written is None:
            return
        if written == base_tree:
            self._drop_turn_records(
                root, request, tuple(o for o, _ in values), _CRAFT_TURN
            )
            return
        tree = self._paths_tree(root, record_paths)
        if tree is None:
            return
        self._record_turn(root, base, request, values, _CRAFT_TURN, tree)

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
                        base,
                        stored.request,
                        ((observation, identity),),
                        _ORACLE_TURN,
                        tree,
                    )
            if craft_was_current and self._turn_recorded(
                root, stored.request, observation, _CRAFT_TURN
            ):
                pairs = self._record_pairs(root, stored, ((observation, design),))
                if pairs is None:
                    continue
                self._stamp_craft_record(
                    root,
                    base,
                    base_tree,
                    stored.request,
                    pairs,
                    self._mutable_targets(design),
                    self._craft_record_paths(design),
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
            for role in (_ORACLE_TURN, _CRAFT_TURN):
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
    ) -> tuple[Path, tuple[NativeEvidence, ...]] | DeliveryOutcome:
        """Run only the design-declared verification against one candidate."""
        directory = Path(tempfile.mkdtemp(prefix="nwave-candidate-"))
        added = self._git(
            root, "worktree", "add", "--detach", str(directory), candidate
        )
        if added.returncode:
            directory.rmdir()
            return self._git_failure(
                added,
                disposition=Disposition.Retry,
                what="CandidateCheckoutUnavailable",
                how="restore Git worktree support",
            )
        evidence = self._native(
            directory, commands, root, changed=changed, capture_incomplete=True
        )
        if isinstance(evidence, DeliveryOutcome):
            # The capture flag covers declared spawn failures only. Preserve the
            # existing cleanup path for any earlier runtime/setup outcome.
            return self._remove_candidate_worktree(root, directory) or evidence
        return directory, evidence

    def _remove_candidate_worktree(
        self, root: Path, directory: Path
    ) -> DeliveryOutcome | None:
        removed = self._git(root, "worktree", "remove", "--force", str(directory))
        if removed.returncode:
            return self._git_failure(
                removed,
                disposition=Disposition.Indeterminate,
                what="CleanupUnproven",
                how="inspect candidate residue",
            )
        return None

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
    def _inherited(
        root: Path, stored: StoredHandover, ready: HandoverValue
    ) -> list[dict[str, object]]:
        """Every already-bound ANCESTOR of this value, in canonical order.

        THE SET IS THE TRANSITIVE DEPENDENCY ANCESTRY, walked over the same
        `{observation: dependencies}` map `_dependency_path` reads, and never
        "every value at a lower position".  For a Product-Owner graph the two
        coincide -- `_ordered_po_values` gives each value its immediate
        predecessor as its sole dependency, so the persisted DAG is a total
        chain -- and for a graph with real edges the ancestry is the honest one.

        RENDERED FROM THE HANDOVER'S BOUND FACTS, never through
        `derive_authority`: that resolver reads a section out of a DESIGN
        document and can answer `DesignAuthorityUnavailable` or
        `DesignAuthorityUnlocatable`, which would let an unrelated value's
        renamed section turn THIS value's paid turn Indeterminate.  The bound
        `DesignFacts` are already the durable, validated carrier, so "nothing
        inferred" holds by construction.

        EXACTLY THE SIX ENUMERATED FIELDS, plus the optional probe path.
        `decisions` and `obligations` are deliberately absent: a real bound
        authority carries `decisions` entries of many hundreds of characters
        each, and inheriting them would inflate the very prompt this projection
        exists to make cheaper.  A later value that wants a predecessor's
        rationale reads the authority section its locator names.

        A predecessor whose `authority` is a legacy bare locator string rather
        than typed facts CONTRIBUTES NOTHING AND REFUSES NOTHING: the handover
        admits `str | DesignFacts | None`, and a restored older handover must
        not wedge every later design turn.
        """
        dependencies = {
            value.observation: value.dependencies for value in stored.values
        }
        pending = list(dependencies.get(ready.observation, ()))
        ancestry: set[str] = set()
        while pending:
            current = pending.pop()
            if current in ancestry or current == ready.observation:
                continue
            ancestry.add(current)
            pending.extend(dependencies.get(current, ()))
        entries: list[dict[str, object]] = []
        for position, value in enumerate(stored.values, start=1):
            if value.observation not in ancestry:
                continue
            bound = value.authority
            if not isinstance(bound, DesignFacts):
                continue
            entry: dict[str, object] = {
                "observation": value.observation,
                "authority": bound.authority_locator,
                "targets": [
                    {"path": target.path, "decision": target.decision}
                    for target in bound.targets
                ],
                "paradigm": bound.paradigm,
                "acceptance_supports": list(bound.acceptance_supports),
                "oracle": bound.oracle,
                "verification": [list(argv) for argv in bound.verification],
                "oracle_verification_index": bound.oracle_verification_index,
            }
            probe = DeliveryContinuationRunner._probe_evidence(root, position)
            if probe is not None:
                entry["probe_evidence"] = probe
            entries.append(entry)
        return entries

    @staticmethod
    def _probe_evidence(root: Path, position: int) -> str | None:
        """This predecessor's probe directory, reported only when it exists.

        A filesystem that cannot answer means the same as ABSENT.  An optional
        convenience hint must never be able to refuse, or to make Indeterminate
        a step that succeeds today: the totality of `des design` is not traded
        for a path string.

        The directory sits under `_RUNNER_OWNED_PREFIX`, which is already
        excluded from `WorkspaceDriftUnattributed`, so reporting it adds no new
        drift surface.
        """
        relative = f"{_RUNNER_OWNED_PREFIX}probe-value-{position}/"
        try:
            if not (root / relative).is_dir():
                return None
        except OSError:
            return None
        return relative

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
        }
        if design.acceptance_obligations:
            facts["acceptance_obligations"] = tuple(
                {"id": item.id, "stimulus": item.stimulus, "expected": item.expected}
                for item in design.acceptance_obligations
            )
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

    #: How the runner asks for the SECOND axis WITHOUT touching the model's argv.
    #: `PYTEST_ADDOPTS` reaches pytest through every spelling a design may
    #: declare -- `uv run pytest`, `python -m pytest`, `.venv/bin/pytest`, a
    #: wrapper script -- and a runner that is not pytest simply never reads it,
    #: so the variable costs a non-pytest subject nothing.  Rewriting the argv
    #: instead would mean recognising which declared vectors ARE pytest, which
    #: is a decision over a DESIGNATION (GDP-8) and would corrupt a vector like
    #: run 23's `python -c "..."`, where a trailing flag is program input.
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
    #: The verdict is still COMPUTED, printed on the `ORACLE-RED` line and
    #: carried into the turn record, so a vacuous oracle is visible to the
    #: whole-diff reviewer and the examiner without a paid turn being spent on
    #: refusing one.  Arming it is this tuple plus the discriminator the four
    #: worlds above require -- whether the acceptance BYTES changed in this run
    #: -- and that discriminator is unmeasured, so it is not built here.
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
    ) -> tuple[str, str]:
        """Classify evidence without assigning pytest exit semantics to other tools.

        A requested pytest report must exist. Its known completed exits and
        error/failure counts distinguish broken setup from assertion failure.
        Other tools without a report provide only an exit observation: success
        is green; nonzero is indeterminate, with diagnostics for the LLM.
        A native JUnit report can establish errors/failures independently of
        that tool's numeric exit convention. No process exit remains broken.
        """
        if exit_status is None:
            return "broken", "exit-status"
        if report_requested and counts is None:
            return "broken", "junit-report-absent"
        if not report_requested and counts is None:
            # Native tools need not use pytest's exit conventions. A nonzero
            # status alone cannot distinguish assertion, build and setup errors.
            return ("green" if not exit_status else "indeterminate"), "exit-status-only"
        if (
            report_requested
            and exit_status not in DeliveryContinuationRunner._ORACLE_COMPLETED_EXITS
        ):
            return "broken", "exit-status"
        if counts is None:
            return ("green" if not exit_status else "red"), "exit-status-only"
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
                report = Path(reports) / f"{index}.xml"
                evidence = self._native(
                    root,
                    (argv,),
                    root,
                    {
                        self._ORACLE_REPORT_VAR: " ".join(
                            part for part in (inherited, f"--junitxml={report}") if part
                        )
                    },
                )
                if isinstance(evidence, DeliveryOutcome):
                    return evidence
                item = evidence[0]
                counts = self._junit_counts(report)
                failures = self._junit_failures(report)
                verdict, axis = self._oracle_verdict(
                    item.exit_status, counts, invokes_pytest(tuple(argv))
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
                    }
                )
                # Operator channel only, exactly like `NATIVE-RUNTIME`: the
                # turn record carries this line, so a later reader can see the
                # oracle was measured RED before one production byte existed.
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

    def _acceptance_correction(
        self,
        root: Path,
        port: TaskInvocationPort,
        prepared: list[tuple[str, AuthorityFacts]],
        handover_bytes: bytes,
        finding: str,
        oracle_red: tuple[dict[str, object], ...],
    ) -> DeliveryOutcome | None:
        """The ONE correction turn the acceptance author gets for this Request.

        Extracted rather than duplicated when the executed-red step gained a
        second way to reach it: both findings are answered by the same author,
        over the same owned paths, under the same scope and progress
        observation, so a second copy would be two chances to drift apart on
        who owns which byte.  ``None`` means the author corrected something and
        the caller may measure the set again.
        """
        acceptance_paths = self._prepared_acceptance_paths(prepared)
        rejected = _authority_bytes(root, acceptance_paths)
        observed = self._observed_scope(root)
        if isinstance(observed, DeliveryOutcome):
            return observed
        if rejected is None:
            return self._fail(
                Disposition.Indeterminate,
                "AcceptanceEvidenceUnavailable",
                "oracle or declared acceptance support is unavailable",
                "restore immutable acceptance evidence",
            )
        status, before = observed
        correction = self._invoke(
            port,
            root,
            "nw-acceptance-designer",
            self._prompt(
                review_task=(
                    "Revise only the candidate public oracle set and declared supports "
                    "for the values below, in response to the opaque independent review "
                    "finding; do not judge, implement, or execute production."
                ),
                values=self._prepared_facts(prepared),
                **self._shared_of(handover_bytes),
                finding=finding,
                oracle_red=list(oracle_red),
            ),
            handover_bytes,
            root,
        )
        denied = self._accepted(
            correction,
            rejected="AcceptanceCorrectionRejected",
            indeterminate="AcceptanceDesignIndeterminate",
            handover=True,
        )
        # A rejecting author owns no byte; an accepted one owns its test paths,
        # by the SAME rule that governs the turn it is correcting.  Authoring
        # and correcting are one role writing one kind of artefact, so a second
        # scope rule for the second turn was two chances to disagree about the
        # same property, never a second guarantee.
        drift = self._scope_drift(
            root,
            status,
            before,
            (),
            self._request_owned_paths(prepared),
            None if denied is not None else self._designer_owns(root, acceptance_paths),
        )
        if isinstance(drift, DeliveryOutcome):
            return drift
        if drift.attributed:
            if denied is not None:
                return self._fail(
                    Disposition.Refusal,
                    "AcceptanceRejectionMutation",
                    "the aggregate acceptance correction changed declared bytes it "
                    "does not own: " + ", ".join(drift.attributed),
                    "restore the workspace bytes",
                )
            return self._production_scope_drift(
                "the aggregate acceptance correction", drift
            )
        if drift.unattributed:
            return self._unattributed("the aggregate acceptance correction", drift)
        self._measured_by_design(drift)
        if denied is not None:
            return denied
        if _authority_bytes(root, acceptance_paths) == rejected:
            return self._fail(
                Disposition.Refusal,
                "AcceptanceCorrectionNoProgress",
                "acceptance correction repeated previously reviewed evidence",
                "revise the oracle or declared support",
            )
        return None

    def _design_correction(
        self,
        root: Path,
        port: TaskInvocationPort,
        prepared: list[tuple[str, AuthorityFacts]],
        stored: StoredHandover,
        finding: str,
        value: str | None,
    ) -> StoredHandover | DeliveryOutcome:
        """Spend the one correction window on the ARCHITECT of one named value.

        It takes the two facts it USES -- the opaque finding and the value the
        defect is charged to -- rather than a whole `AcceptanceFinding`, because
        two different measurements now reach it: the aggregate oracle review and
        the craft turn.  A craft refusal is not an acceptance finding, and
        building one to satisfy a parameter would make the type claim something
        about the run that is not true.

        The architect is the only role that may rewrite a value's targets,
        obligations and verification: the acceptance designer holds `Read, Edit`
        over the oracle paths alone, so a finding about those facts reaching it
        is a turn that cannot succeed.  The corrected facts replace the bound
        authority atomically, exactly as the existing initial-authoring
        correction edge does, so a resume re-enters on the corrected authority
        and never on the refused one.

        THE ORACLE IS RE-AUTHORED ONLY WHEN IT ACTUALLY MOVED.  The measured
        defect changes a `targets` list and leaves every declared oracle and
        support path where it was, and re-authoring an unchanged artefact would
        buy a paid turn to rewrite bytes the review has already read.  So the
        realignment is gated on the PROPERTY -- did this value's declared
        acceptance path set change? -- and not on the designation "the design
        was corrected".
        """
        if value is None:
            return self._fail(
                Disposition.Indeterminate,
                "ReviewDefectValueMissing",
                "the review charged a defect to the design without naming the "
                "value whose architect owns it",
                "name the value the defect belongs to, then re-run the Request",
            )
        position = next(
            (
                index
                for index, (observation, _) in enumerate(prepared)
                if observation == value
            ),
            None,
        )
        entry = next(
            (item for item in stored.values if item.observation == value),
            None,
        )
        if (
            position is None
            or entry is None
            or not isinstance(entry.authority, DesignFacts)
        ):
            return self._fail(
                Disposition.Indeterminate,
                "ReviewDefectValueUnbound",
                "the review charged a defect to a value that holds no typed "
                f"design facts: {value}",
                "re-run the Request so every value binds its own design",
            )
        design = prepared[position][1]
        before = self._prepared_acceptance_paths(prepared)
        correction = self._invoke(
            port,
            root,
            "nw-solution-architect",
            self._prompt(
                observation=value,
                decomposition=self._decomposition(stored),
                **self._typed_facts(design),
                **self._shared(stored),
                finding=finding,
            ),
            stored.raw,
        )
        denied = self._accepted(
            correction,
            rejected="DesignRejected",
            indeterminate="DesignIndeterminate",
            handover=True,
        )
        if denied is not None:
            if (
                not isinstance(correction, DeliveryOutcome)
                and correction.design_facts is not None
            ):
                return self._fail(
                    Disposition.Indeterminate,
                    "DesignFactsMalformed",
                    "nonaccepting DESIGN correction supplied facts",
                    "return facts only with accepted",
                )
            return denied
        assert not isinstance(correction, DeliveryOutcome)
        replacement = correction.design_facts
        defect = (
            "accepted DESIGN correction supplied no facts at all"
            if replacement is None
            else design_facts_defect(replacement)
        )
        if defect is not None:
            return self._fail(
                Disposition.Indeterminate,
                "DesignFactsMalformed",
                f"accepted DESIGN correction supplied inadmissible facts: {defect}",
                _DESIGN_FACTS_REPAIR,
            )
        assert replacement is not None
        if replacement == entry.authority:
            return self._fail(
                Disposition.Refusal,
                "DesignCorrectionNoProgress",
                "accepted architect correction repeated current typed facts",
                "return distinct typed design facts",
            )
        refreshed = self._derive(root, replacement)
        if isinstance(refreshed, DeliveryOutcome):
            return refreshed
        rebound = self._bind_authority(root, stored, value, replacement)
        if isinstance(rebound, DeliveryOutcome):
            return rebound
        stored = rebound
        prepared[position] = (value, refreshed)
        conflict = self._validate_bound_scopes(root, stored)
        if conflict is not None:
            return conflict
        if self._prepared_acceptance_paths(prepared) == before:
            return stored
        observed = self._observed_scope(root)
        if isinstance(observed, DeliveryOutcome):
            return observed
        status, workspace = observed
        realigned = self._prepare_single(
            root,
            port,
            (value,),
            refreshed,
            stored.raw,
            status,
            workspace,
            self._request_owned_paths(prepared),
        )
        return realigned if realigned is not None else stored

    def _implementation_review(
        self,
        candidate_root: Path,
        root: Path,
        port: TaskInvocationPort,
        prepared: list[tuple[str, AuthorityFacts]],
        handover_bytes: bytes,
        acceptance_evidence: tuple[tuple[str, bytes], ...],
        candidate: str,
        diff: str,
        evidence: tuple[NativeEvidence, ...],
    ) -> DeliveryOutcome | None:
        """One read-only veto over the whole candidate, never a per-value pass."""
        review = self._invoke(
            port,
            candidate_root,
            "nw-software-crafter-reviewer",
            self._prompt(
                candidate_sha=candidate,
                diff=diff,
                values=self._prepared_facts(prepared),
                **self._shared_of(handover_bytes),
                owned_paths=self._request_owned_paths(prepared),
                approved_oracles=[
                    [path, raw.decode("utf-8", errors="replace")]
                    for path, raw in acceptance_evidence
                ],
                native_evidence=self._evidence_records(evidence),
                radius=self._radius,
            ),
            handover_bytes,
            root,
        )
        return self._accepted(
            review,
            rejected="ImplementationReviewRejected",
            indeterminate="ImplementationReviewIndeterminate",
            handover=True,
        )

    def _examine(
        self,
        root: Path,
        port: TaskInvocationPort,
        prepared: list[tuple[str, AuthorityFacts]],
        handover_bytes: bytes,
        candidate: str,
        evidence: tuple[NativeEvidence, ...],
    ) -> DeliveryOutcome | None:
        """The one source-blind pass: ordered observations, SHA, captured evidence.

        It receives no diff, oracle bytes or source, and never re-executes: a
        second execution would judge a different run than the reviewed one.
        """
        examine = self._invoke(
            port,
            root,
            "nw-user-examiner",
            self._prompt(
                outcomes=[observation for observation, _ in prepared],
                candidate_sha=candidate,
                native_evidence=self._evidence_records(evidence),
                radius=self._radius,
            ),
            handover_bytes,
        )
        denied = self._accepted(
            examine,
            rejected="ExamineRejected",
            indeterminate="ExamineIndeterminate",
            handover=True,
        )
        if denied is None or denied.failure is None:
            return denied
        # The diagnostic travels byte-for-byte; the candidate SHA rides in the
        # surrounding WHAT/HOW so it survives the worktree removal.
        return DeliveryOutcome(
            denied.disposition,
            FailureDetail(
                f"{denied.failure.what} on candidate {candidate}",
                denied.failure.why,
                f"inspect candidate {candidate}; the destination ref never moved",
            ),
        )

    def _placeholder(self, values: tuple[ProductValue, ...]) -> DeliveryOutcome | None:
        """The measured incident, refused before anything is written.

        Run 20260906T005839Z-648259 turn 06 answered `accepted` with the single
        value `"a"`.  The runner persisted it and then paid the architect, the
        acceptance designer, its reviewer and a second designer before the
        designer refused the byte -- about $1.2 for one character.

        The provider schema now makes that answer unrepresentable, which is
        where the cost is actually saved (GDP-0, GDP-1).  This is the second
        axis, stated for the same reason the replacement window is re-stated at
        the envelope boundary: an envelope reaches this runner without ever
        having passed the provider's validator whenever it is replayed,
        hand-written or produced by a double.  A turn answering below the floor
        established no semantic result, so it is INDETERMINATE -- never a
        delivery refusal charged to the product -- and the graph is untouched.
        """
        for value in values:
            length = len(value.observation)
            if length >= MINIMUM_OBSERVATION_CHARACTERS:
                continue
            return self._fail(
                Disposition.Indeterminate,
                "ProductValuePlaceholder",
                f"an accepted PO value states {length} character"
                f"{'' if length == 1 else 's'} where a publicly observable "
                f"outcome takes at least {MINIMUM_OBSERVATION_CHARACTERS}: "
                f"{value.observation!r}",
                "re-run the Request: the provider schema declares this floor, "
                "so a turn that answers it cannot carry a placeholder",
            )
        return None

    @staticmethod
    def _ordered_po_values(
        values: tuple[ProductValue, ...], prefix: tuple[HandoverValue, ...]
    ) -> tuple[HandoverValue, ...]:
        """Project ordered PO observations into the persisted continuation DAG."""
        previous = prefix[-1].observation if prefix else None
        projected: list[HandoverValue] = []
        for value in values:
            projected.append(
                HandoverValue(
                    value.observation, () if previous is None else (previous,), None
                )
            )
            previous = value.observation
        return tuple(projected)

    def _bind_authority(
        self,
        root: Path,
        stored: StoredHandover,
        observation: str,
        locator: str | DesignFacts,
    ) -> StoredHandover | DeliveryOutcome:
        """Rebind one value's authority while retaining historical evidence.

        A changed DESIGN is a SEMANTIC decision only the architect makes, and
        a recorded oracle or craft turn was authored/measured/built against
        the OLD typed facts.  `_turn_completed`'s tree-only comparison cannot
        see a changed `decisions` (or any other typed field) that happens to
        leave the same acceptance or mutable bytes on disk, so unchanged
        oracle bytes are not evidence of judgement over the NEW design.  The
        current authority, still readable from `stored` before this rewrite,
        is compared with the replacement by the typed facts' own equality --
        no new storage, gate or comparison is introduced.  An identical
        accepted correction (`current == locator`) changes nothing and keeps
        both the completion claims and the cheap resume they buy.

        Turn records carry the selected revision identity and an owned-byte
        snapshot.  The normal currentness predicate reads both, so records for
        a superseded DESIGN are historical rather than live.  Keeping them is
        what permits an exact restoration to reuse the original proof.
        """
        updated = rewrite_handover(
            root,
            stored.raw,
            stored.request,
            tuple(
                self._rebound(value, locator)
                if value.observation == observation
                else value
                for value in stored.values
            ),
        )
        if isinstance(updated, Blocked):
            return self._blocked(updated)
        return updated

    @staticmethod
    def _rebound(value: HandoverValue, authority: str | DesignFacts) -> HandoverValue:
        """The value bound to ``authority``: identical facts keep the full-input
        identity, different facts (bound without naming their input) clear it."""
        if value.authority == authority:
            return value
        return replace(value, authority=authority, design_semantic_sha256=None)

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

    def _prepare_single(
        self,
        root: Path,
        port: TaskInvocationPort,
        observations: tuple[str, ...],
        design: AuthorityFacts,
        handover_bytes: bytes,
        initial_status: str,
        initial_workspace: dict[str, tuple[str, bytes | str]],
        declared: tuple[str, ...] = (),
        finding: str | None = None,
    ) -> DeliveryOutcome | None:
        """Author one batch's candidate public oracle.  No review or craft.

        ``finding`` travels verbatim into the author's prompt when a caller
        reaches this first-authoring path wearing one -- exactly the state a
        rejected first turn that wrote no oracle byte leaves behind: nothing
        on disk to correct, so the same author call `finding is None` already
        makes is the one this second turn takes too, only with the original
        finding string attached rather than dropped.
        """
        acceptance_paths = design.acceptance_paths
        owns_path = self._designer_owns(root, acceptance_paths)
        approved_authority = _authority_bytes(root, design.modified_authority_paths)
        if approved_authority is None:
            return self._fail(
                Disposition.Indeterminate,
                "AuthorityUnavailable",
                "approved architecture authority cannot be read",
                "restore durable authority",
            )

        def authoring_scope_unchanged() -> DeliveryOutcome | None:
            # AuthorityDrift stays, and its incident is not the designer's
            # convenience: the durable architecture section is the authority the
            # whole run was BOUND to, and a role that rewrites it retroactively
            # changes what every later turn was measured against. It is the one
            # document no role in this Request may write, so unlike the target
            # table it is a property of the artefact, not a designation.
            if (
                _authority_bytes(root, design.modified_authority_paths)
                != approved_authority
            ):
                return self._fail(
                    Disposition.Refusal,
                    "AuthorityDrift",
                    "acceptance design changed the approved architecture authority",
                    "restore authority and rerun from a new Request",
                )
            # This value's OWN facts join the declared set: the runner derived
            # them for the very turn under observation, so a production target
            # it hands the designer is attributable to it -- the third state is
            # for paths no fact in this Request names at all.
            drift = self._scope_drift(
                root,
                initial_status,
                initial_workspace,
                (),
                tuple(dict.fromkeys((*declared, *self._owned_paths(design)))),
                owns_path,
            )
            if isinstance(drift, DeliveryOutcome):
                return drift
            if drift.attributed:
                return self._production_scope_drift("acceptance design", drift)
            if drift.unattributed:
                return self._unattributed("acceptance design", drift)
            self._measured_by_design(drift)
            return None

        acceptance_before = _workspace_bytes(root, acceptance_paths)
        atd = self._invoke(
            port,
            root,
            "nw-acceptance-designer",
            self._prompt(
                **(
                    {"observation": observations[0]}
                    if len(observations) == 1
                    else {"observations": list(observations)}
                ),
                **self._typed_facts(design),
                **self._shared_of(handover_bytes),
                **({} if finding is None else {"finding": finding}),
            ),
            handover_bytes,
            root,
        )
        not_accepted = self._accepted(
            atd,
            rejected="AcceptanceDesignRejected",
            indeterminate="AcceptanceDesignIndeterminate",
            handover=True,
        )
        if not_accepted:
            # A rejecting author owns no byte: its finding travels, its edits do not.
            if _workspace_bytes(root, acceptance_paths) != acceptance_before:
                return self._fail(
                    Disposition.Refusal,
                    "AcceptanceRejectionMutation",
                    "the rejecting acceptance design changed oracle or support bytes",
                    "restore the acceptance bytes",
                )
            return authoring_scope_unchanged() or not_accepted
        observed = [
            (path, self._regular_file(root / path)) for path in acceptance_paths
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
                f"accepted acceptance design left files declared by "
                f"{design.locator!r} unavailable: {unavailable}",
                "restore the named acceptance files or correct their declaration "
                "before re-running the oracle step",
            )
        return authoring_scope_unchanged()

    @staticmethod
    def _batch_key(design: AuthorityFacts) -> tuple[object, ...]:
        """Only equal consumed facts may share an author or crafter invocation."""
        return (
            design.locator,
            design.acceptance_oracle_locator,
            design.acceptance_paths,
            design.target_decisions,
            design.paradigm,
        )

    @staticmethod
    def _bound_authority_documents(
        root: Path, stored: StoredHandover
    ) -> tuple[str, ...]:
        """Whole-file authority documents the declared commands and handoff derive from."""
        from des.adapters.driven.config.des_config import DESConfig

        paths: list[str] = []
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

    def _contribute(
        self,
        root: Path,
        base: str,
        port: TaskInvocationPort,
        prepared: list[tuple[str, AuthorityFacts]],
        handover_bytes: bytes,
        stored: StoredHandover,
        owners: list[tuple[str, AuthorityFacts]] | None = None,
        correction: dict[str, object] | None = None,
        route_blockers: bool = True,
    ) -> DeliveryOutcome | tuple[StoredHandover, tuple[str, ...]]:
        """Every selected value contributes to the one shared private workspace.

        Each crafter owns only its own value's mutable targets: a sibling's
        bytes, the frozen authority, the approved oracles, the handover and
        foreign state are all outside its scope, so one observation covers them.

        That same observation also answers whether an accepted turn produced any
        bytes at all.  A silent turn is not a defect by itself -- a value whose
        target is already delivered is honestly unchanged, and the candidate may
        still verify -- so this returns one sentence per silent batch instead of
        refusing here, and the caller uses them only where a finding proves the
        work was in fact owed.

        A batch whose craft turn is already RECORDED, and whose mutable targets
        still hold exactly what that record describes, is not invoked again: the
        turn happened, its bytes are here, and the first step with no fact behind
        it is the ordered native verification.  A correction pass never reuses a
        record -- a finding was issued, and answering it is the whole point of
        that turn.

        A REFUSING craft turn names WHO can unblock it in a closed word of its
        typed payload.  `route_blockers` decides what happens to that word here:
        the composed run spends one window per value on the role it names, and a
        step invoked ALONE returns it to its caller instead, because Section 4b
        makes choosing which role answers a finding the orchestrator's decision
        and not the software's.  The word is DATA either way.  See
        :meth:`_craft_blocker_window` for the
        measurement; what belongs here is why the pass RESTARTS instead of
        re-invoking the batch in place.  The window's two destinations can both
        change the facts this pass is iterating over -- the architect replaces
        the value's bound typed design, which regroups batches, and the designer
        rewrites oracle bytes -- so continuing over a batch list derived before
        the correction would craft against facts that no longer hold.  Restarting
        re-derives everything from the corrected authority and skips what is
        already done, which is tracked in this call rather than in a record
        because nothing outside it consumes the fact: a resume re-enters the whole
        pass anyway, and a durable field would be a second, driftable spelling of
        a set the loop already holds (GDP-10).

        The handover is returned because a `design` window REBINDS it: every
        later turn is frozen against those bytes, so a caller holding the old
        ones would block itself on the correction it just paid for.
        """
        selected = owners if owners is not None else prepared
        silent: dict[tuple[str, ...], str] = {}
        completed: set[str] = set()
        spent: set[str] = set()
        # A record can only be reused against the tree its base carries, so a
        # base tree the runner cannot read disables reuse outright rather than
        # weakening the comparison.
        observed_base = self._git(root, "rev-parse", f"{base}^{{tree}}")
        base_tree = None if observed_base.returncode else observed_base.stdout.strip()
        while True:
            reopened = False
            for batch in self._forward_batches(stored, selected):
                observations = tuple(observation for observation, _ in batch)
                if set(observations) <= completed:
                    continue
                observation, design = batch[0]
                pairs = self._record_pairs(root, stored, tuple(batch))
                mutable = self._mutable_targets(design)
                agent = (
                    "nw-software-crafter"
                    if design.paradigm == "object_oriented"
                    else "nw-functional-software-crafter"
                )
                if (
                    correction is None
                    and base_tree is not None
                    and pairs is not None
                    and self._turn_completed(
                        root,
                        stored.request,
                        pairs,
                        _CRAFT_TURN,
                        self._craft_record_paths(design),
                    )
                ):
                    completed.update(observations)
                    continue
                observed = self._observed_scope(root)
                if isinstance(observed, DeliveryOutcome):
                    return observed
                status, before = observed
                craft = self._invoke(
                    port,
                    root,
                    agent,
                    self._prompt(
                        **(
                            {"observation": observation}
                            if len(observations) == 1
                            else {"observations": list(observations)}
                        ),
                        **self._typed_facts(design),
                        **self._shared_of(handover_bytes),
                        target_decisions=design.target_decisions,
                        mutable_targets=mutable,
                        **(correction or {}),
                    ),
                    handover_bytes,
                    root,
                )
                not_accepted = self._accepted(
                    craft,
                    rejected="CraftRejected",
                    indeterminate="CraftIndeterminate",
                    handover=True,
                )
                if not_accepted:
                    if (
                        not route_blockers
                        or correction is not None
                        or set(observations) & spent
                    ):
                        return not_accepted
                    routed = self._craft_blocker_window(
                        root, port, prepared, stored, observation, craft, not_accepted
                    )
                    if isinstance(routed, DeliveryOutcome):
                        return routed
                    stored, handover_bytes = routed, routed.raw
                    spent.update(observations)
                    reopened = True
                    break
                drift = self._scope_drift(
                    root,
                    status,
                    before,
                    mutable,
                    self._request_owned_paths(prepared),
                    self._crafter_owns(prepared),
                )
                if isinstance(drift, DeliveryOutcome):
                    return drift
                if drift.attributed:
                    return self._fail(
                        Disposition.Refusal,
                        "CraftScopeDrift",
                        f"the crafter for {observations!r} changed the public oracle "
                        "the RED is measured against: " + ", ".join(drift.attributed),
                        "restore the oracle and let production alone buy the GREEN",
                    )
                if drift.unattributed:
                    return self._unattributed(
                        f"the crafter for {observations!r}", drift
                    )
                if mutable and not set(mutable) & set(drift.in_scope):
                    # An accepted no-op is evidence only that the role said it
                    # had nothing to write.  The value may already be complete,
                    # or it may still be RED.  Execute the declared oracle here,
                    # after the bought turn, and record the turn only in the
                    # former case.  This preserves the retry path for a silent
                    # non-delivery while preventing the state projection from
                    # repeatedly buying the same accepted turn for code already
                    # proved GREEN.
                    if base_tree is not None and self._observed_green(
                        self._executed_oracle_set(root, batch)
                    ):
                        tree = self._paths_tree(root, self._craft_record_paths(design))
                        if pairs is not None and tree is not None:
                            self._record_turn(
                                root,
                                base,
                                stored.request,
                                pairs,
                                _CRAFT_TURN,
                                tree,
                            )
                            if self._turn_completed(
                                root,
                                stored.request,
                                pairs,
                                _CRAFT_TURN,
                                self._craft_record_paths(design),
                            ):
                                silent[observations] = (
                                    f"{agent} accepted {observations!r} without changing "
                                    "any of its batch's mutable targets; its tracked oracle "
                                    "was executed on the current workspace bytes and observed "
                                    "GREEN, so this craft turn was recorded: "
                                    + ", ".join(mutable)
                                )
                            else:
                                silent[observations] = (
                                    f"{agent} accepted {observations!r} without changing any of "
                                    "its batch's mutable targets: " + ", ".join(mutable)
                                )
                        else:
                            silent[observations] = (
                                f"{agent} accepted {observations!r} without changing any of "
                                "its batch's mutable targets: " + ", ".join(mutable)
                            )
                    else:
                        silent[observations] = (
                            f"{agent} accepted {observations!r} without changing any of "
                            "its batch's mutable targets: " + ", ".join(mutable)
                        )
                elif base_tree is not None and pairs is not None:
                    self._stamp_craft_record(
                        root,
                        base,
                        base_tree,
                        stored.request,
                        pairs,
                        mutable,
                        self._craft_record_paths(design),
                    )
                completed.update(observations)
            if not reopened:
                return stored, tuple(silent.values())

    def _craft_blocker_window(
        self,
        root: Path,
        port: TaskInvocationPort,
        prepared: list[tuple[str, AuthorityFacts]],
        stored: StoredHandover,
        observation: str,
        craft: ModelRun | DeliveryOutcome,
        terminal: DeliveryOutcome,
    ) -> StoredHandover | DeliveryOutcome:
        """The ONE correction turn a refusing craft batch gets, on the role it names.

        MEASURED THREE TIMES: runs 31 (`20260906T014933Z-735633`, turn 08), 32b
        (`20260906T032332Z-921671`, turn 04) and 33 (`20260906T032944Z-924463`,
        turns 05-06).  Each crafter implemented its batch, ran the declared
        oracle and found a case still red for a defect of the ORACLE ITSELF --
        two absolute paths compared across different temporary roots, the wrong
        fallback provider, the `file:offset` site format of the text-search
        adapter -- then refused honestly: «cannot be driven green without
        editing the oracle, which is immutable».  Every craft refusal had one
        answer, `CraftRejected`, whose HOW reads «act on the finding, then
        re-run» -- and the resume returns to the same crafter over the same
        oracle.  The only real way out was a NEW Request, paying Product Owner,
        architect and acceptance designer again: three runs and roughly $8 spent
        on findings a single $0.3 designer turn answers.

        WHICH ROLE IS THE CRAFTER'S DECISION, not the runner's.  The word
        arrives in the typed payload, closed by the provider's own schema, and
        the software only routes on it (`boundary:software-measures-model-
        decides`).  Reading it off the diagnostic would be exactly the prose
        parsing this boundary forbids.

        Only a REJECTION opens the window.  An `indeterminate` turn established
        no semantic result, so there is no finding to answer and a paid
        correction would buy a repair for something nobody stated.

        `product` keeps today's behaviour by design: it is the honest "neither
        of the other two roles is at fault", and the Request ends where it
        always did.

        `observation` is the batch's FIRST value, and naming it as the owner of
        a `design` defect is exact rather than a guess: one craft turn is shown
        exactly one design -- that value's -- and every other member of the
        batch is there because `_batch_key` found its locator, oracle,
        acceptance paths, target decisions and paradigm identical.
        """
        if isinstance(craft, DeliveryOutcome):
            return terminal
        if craft.outcome is not ModelOutcome.Rejected:
            return terminal
        blocker = craft.craft_blocker
        if blocker is None:
            # DEGRADE LOUD (GDP-6).  The provider's own schema refuses a
            # non-accepting craft turn that names no blocker, so this is
            # reachable only from an envelope that never met that validator.
            # Guessing a role would be the routing defect this change removes.
            return self._fail(
                Disposition.Indeterminate,
                "CraftBlockerMissing",
                "the craft turn refused its batch without naming what blocks it",
                "observe the provider result: the crafter named no blocker, so no "
                "correction window was opened",
            )
        if blocker is CraftBlocker.Product:
            return terminal
        if blocker is CraftBlocker.Design:
            return self._design_correction(
                root, port, prepared, stored, craft.diagnostic, observation
            )
        # The author owes the same two inputs it gets everywhere else: the
        # opaque finding, and WHY each oracle is red right now.  The set is
        # therefore executed HERE and not inherited from the pre-craft
        # measurement -- production bytes exist by this point, so the earlier
        # observation describes a workspace that no longer exists, and a
        # measured property is never inherited across units.
        executed = self._executed_oracle_set(root, prepared)
        if isinstance(executed, DeliveryOutcome):
            return executed
        denied = self._acceptance_correction(
            root, port, prepared, stored.raw, craft.diagnostic, executed.measured
        )
        if denied is not None:
            return denied
        # The corrected oracle is MEASURED again, exactly as it is after the
        # aggregate review's own correction: a repair that leaves an oracle
        # unable to reach its own assertion is caught before one more paid craft
        # turn.  The aggregate review is NOT re-run -- the corrected bytes travel
        # into the candidate and reach the whole-diff reviewer there, which is
        # Window 1a's own remedy for an oracle that moves before the first
        # approving review.
        remeasured = self._executed_oracle_set(root, prepared)
        if isinstance(remeasured, DeliveryOutcome):
            return remeasured
        if remeasured.refusal is not None:
            return remeasured.refusal.terminal
        return stored

    def _correction_owners(
        self,
        root: Path,
        prepared: list[tuple[str, AuthorityFacts]],
        base: str,
        candidate: str,
    ) -> list[tuple[str, AuthorityFacts]] | DeliveryOutcome:
        """Owners derived from changed target paths, never from the finding text.

        A value whose defect is a missing output changed no target path and stays
        unselected; where a shared path belongs to several values every one of
        them is selected, a conservative over-approximation, not an attribution.
        """
        changed = self._changed_paths(root, base, candidate)
        if changed is None:
            return self._fail(
                Disposition.Retry,
                "GitUnavailable",
                f"the candidate {candidate} diff cannot be observed",
                "restore Git",
            )
        touched = set(changed)
        return [
            (observation, design)
            for observation, design in prepared
            if touched.intersection(self._mutable_targets(design))
        ]

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
        """One candidate and one ordered native execution.

        Returns the candidate SHA and captured evidence, or the terminal native
        verification outcome. It neither invokes a role nor decides a repair.
        """
        owned = self._owned_with_authority(root, stored, prepared)
        argvs = self._request_argvs(prepared)
        facts = IntegrationFacts(
            stored.request,
            tuple(observation for observation, _ in prepared),
            tuple(dict.fromkeys(design.locator for _, design in prepared)),
        )
        while True:
            # Captured BEFORE `_candidate` normalizes anything, so an
            # external, unreviewed edit to an oracle or craft file reads as
            # NOT current here and cannot be laundered by the refresh below.
            was_current = self._pre_candidate_currentness(root, stored, prepared)
            created = self._candidate(root, base, owned, facts)
            if isinstance(created, DeliveryOutcome):
                return created
            candidate, _diff = created
            # The one hand that moves recorded bytes after a turn is the
            # runner's own format contract, honoured inside `_candidate`.
            self._refresh_turn_records(root, base, stored, prepared, was_current)
            touched = self._changed_paths(root, base, candidate)
            if touched is None:
                return self._fail(
                    Disposition.Retry,
                    "GitUnavailable",
                    f"the candidate {candidate} diff cannot be observed",
                    "restore Git",
                )
            checkout = self._with_candidate_worktree(root, candidate, argvs, touched)
            if isinstance(checkout, DeliveryOutcome):
                return checkout
            candidate_root, evidence = checkout
            # Only typed, design-declared vectors execute against the candidate.
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
            # ADR-DES-003 §6: measured here, after the candidate exists and
            # before a judgement is bought, and handed to BOTH judges as data.
            # The software refuses nothing on it -- width is their judgement
            # over a measured fact.
            self._radius = candidate_radius(candidate_root, touched)
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
            cleanup = self._remove_candidate_worktree(root, candidate_root)
            if cleanup is not None:
                return cleanup
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
        base: str,
        candidate: str,
        foreign_baseline: str,
        foreign_bytes: dict[str, tuple[str, bytes | str]],
        owned_paths: tuple[str, ...] | None = None,
    ) -> DeliveryOutcome:
        """One compare-and-swap, one owned-index reconciliation, one cleanup.

        A no-delta candidate is expected-old itself, and the swap still runs so
        a concurrently moved ref refuses instead of yielding a Success nobody
        verified against the destination.
        """
        owned = owned_paths or self._request_owned_paths(prepared)
        # The observation, the comparison and the swap live in `HeadAdvance`,
        # which the `des lane integrate` step also calls: one implementation of
        # "the destination is not where you last saw it", so the two cannot
        # drift apart on the one case a green run never exercises.  The seam is
        # INJECTED rather than imported there, so a caller substituting Git for
        # this runner still substitutes it inside the swap.
        refused = HeadAdvance(self._git).swap(root, candidate, base)
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
            or _foreign_status(final.stdout, owned) != foreign_baseline
            or _workspace_bytes(root, tuple(foreign_bytes)) != foreign_bytes
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

    def design_value(
        self,
        root: Path,
        port: TaskInvocationPort,
        stored: StoredHandover,
        ready: HandoverValue,
        *,
        finding: str | None = None,
        competence: str | None = None,
        destination: str | None = None,
    ) -> tuple[StoredHandover, AuthorityFacts] | DeliveryOutcome:
        """One architect turn for one value, derived and bound, and nothing more.

        ADR-SSOT-002 Section 4b names this step by property: «One role turn
        under a provider-enforced typed contract -- takes the role, the minimum
        facts that role consumes, the private workspace; returns the closed
        outcome, the role's typed output, its diagnostic verbatim.»

        REPEATABLE, and that is what makes it a correction as well as an
        authoring.  A second call over a value that is already bound carries
        `finding` plus the CURRENT typed facts, and the facts it returns REPLACE
        the bound ones.  Which finding goes back to which role, and whether to
        spend a turn on it at all, is the orchestrator's decision; this method
        holds no edge and takes none.

        DERIVE BEFORE BIND.  Binding makes an authority durable, so persisting
        facts the runner then refuses to derive would wedge every later resume
        of this Request behind a handover deletion.  Deriving first keeps
        `authority` unset for a refused value, so the next call re-elicits
        DESIGN for it, which is the HOW the refusal names.

        PUBLISH BEFORE BIND, between that derivation and the bind, and for the
        same reason.  A value's typed facts may name an authority section, and
        a record naming a section no document carries is exactly the
        disagreement the replay arm refuses as `DesignAuthorityUnlocatable` --
        which a role turn used to manufacture on its very first success,
        because nothing ever wrote the section its own record named.  So the
        section is rendered from those typed facts, published through the ONE
        producer the closed-document path uses, and read back with the
        consumer's own resolver; only a resolved read-back reaches the bind.  A
        refusing publication leaves the value UNBOUND, so the next call
        re-elicits DESIGN, which is what the shipped derive-before-bind order
        already promises.

        `destination` is the configured `documents.design.destination`, resolved
        by the caller at the application boundary exactly as the closed-document
        path resolves it.  It is passed in rather than read here so this runner
        gains no configuration dependency.
        """
        self._published_design = None
        current = ready.authority
        facts: dict[str, object] = {
            "observation": ready.observation,
            "decomposition": self._decomposition(stored),
        }
        # ABSENT, never empty: `inherited: []` would move the prompt bytes of
        # every first value, and "nothing to inherit" is represented by the key
        # not being there at all.
        facts.update(self._shared(stored))
        inherited: list[dict[str, object]] = self._inherited(root, stored, ready)
        if inherited:
            facts["inherited"] = inherited
        if finding is not None:
            if current is not None:
                derived_current = self._derive(root, current)
                if isinstance(derived_current, DeliveryOutcome):
                    return derived_current
                facts.update(self._typed_facts(derived_current))
            facts["finding"] = finding
        role_id = qualify_role_id("nw-solution-architect", competence)
        turn = self._invoke(port, root, role_id, self._prompt(**facts), stored.raw)
        denied = self._accepted(
            turn,
            rejected="DesignRejected",
            indeterminate="DesignIndeterminate",
            handover=True,
        )
        if denied is not None:
            if not isinstance(turn, DeliveryOutcome) and turn.design_facts is not None:
                return self._fail(
                    Disposition.Indeterminate,
                    "DesignFactsMalformed",
                    "nonaccepting DESIGN supplied facts",
                    "return facts only with accepted",
                )
            return denied
        assert not isinstance(turn, DeliveryOutcome)
        replacement = turn.design_facts
        defect = (
            "accepted DESIGN supplied no facts at all"
            if replacement is None
            else design_facts_defect(replacement)
        )
        if defect is not None:
            return self._fail(
                Disposition.Indeterminate,
                "DesignFactsMalformed",
                f"accepted DESIGN supplied inadmissible facts: {defect}",
                _DESIGN_FACTS_REPAIR,
            )
        # An accepted correction identical to the bound facts is MEASURED, not
        # refused: ADR-DES-003 §2.5 -- «identity of a model's answer with the
        # previous one is a fact, not a hazard», and the census already ruled
        # «software measures identity; the model decides». The refusal existed
        # to stop a loop the composer ran, and the composer no longer decides.
        self._design_unchanged = finding is not None and replacement == current
        design = self._derive(root, replacement)
        if isinstance(design, DeliveryOutcome):
            return design
        published = self._publish_design_section(
            root, current, replacement, destination, stored
        )
        if isinstance(published, DeliveryOutcome):
            return published
        self._published_design = published
        bound = self._bind_authority(root, stored, ready.observation, replacement)
        if isinstance(bound, DeliveryOutcome):
            if published is not None and published.authority_persisted:
                # BOTH projections, named together.  The section is on disk and
                # the facts carrier is not, and a bare retry would hide half of
                # a mixed durable state from the only reader who can repair it.
                detail = bound.failure
                return self._fail(
                    Disposition.Indeterminate,
                    "DesignProjectionMixed",
                    f"the DESIGN authority section {published.locator} was "
                    "persisted but the handover facts could not be "
                    "compare-and-swap bound"
                    + (f": {detail.why}" if detail is not None else ""),
                    "inspect the authority and handover together before retrying",
                )
            return bound
        return bound, design

    def _publish_design_section(
        self,
        root: Path,
        current: str | DesignFacts | None,
        facts: DesignFacts,
        destination: str | None,
        stored: StoredHandover,
    ) -> PublishedDesignDocument | DeliveryOutcome | None:
        """Publish the section this turn's facts NAME, or say why it cannot be.

        `None` means the facts name no configured section at all -- the
        documented provider-authored-facts value, whose empty locator
        `confirm_recorded_authority` already reads the same way -- so there is
        nothing to render and nothing to refuse.
        """
        locator = facts.authority_locator
        if not locator:
            return None
        if destination is None:
            return self._fail(
                Disposition.Refusal,
                "DesignDestinationMissing",
                f"the architect's facts name the authority section {locator} "
                "while no effective documents.design.destination is configured, "
                "so there is no document this repository owns to publish it into",
                "configure documents.design.destination in repository or global "
                "config, then re-invoke this step",
            )
        document = locator.partition("#")[0]
        section = DesignFactsSection.for_locator(locator, facts)
        if section is None or document != str(destination):
            # The document is fine and the facts are well formed; the two sides
            # simply name different destinations.  That is a role/step CONTRACT
            # GAP, so both sides are named and neither projection moves.
            return self._fail(
                Disposition.Refusal,
                "DesignFactsUnpublishable",
                f"the architect returned authority_locator {locator}, which "
                f"names no section of the configured documents.design.destination "
                f"{destination}, so these typed facts cannot be rendered into "
                "the architecture document this repository owns",
                f"have the role return an authority_locator of the form "
                f"{destination}#<heading>, or set documents.design.destination to "
                "the document the role names; nothing was written and nothing "
                "was bound",
            )
        recorded = (
            current.authority_locator
            if isinstance(current, DesignFacts) and current.authority_locator
            else None
        )
        published = publish_design_document(
            root,
            str(destination),
            section,
            # The same expression the closed-document path uses, so the two
            # publication paths cannot disagree about what a recoverable
            # untracked destination means.
            allow_untracked_recovery=(current is None or current == facts),
            # A correction replaces its OWN section in place; a correction that
            # renames the heading refuses rather than orphaning the section this
            # value already owns.
            replace_current=recorded == locator,
            authority_locator=recorded,
            # The same handover the pre-turn judge read, so the two judgements
            # cannot disagree about which sections this Request published.
            published_headings=bound_authority_headings(stored, str(destination)),
        )
        if isinstance(published, Blocked):
            return self._blocked(published)
        return published

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
        if isinstance(design, DeliveryOutcome) or not selected:
            return design
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
            acceptance_paths=(
                value.acceptance_oracle.partition("::")[0],
                *value.acceptance_supports,
            ),
            native_verification_argvs=value.acceptance_verification,
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

    def confirm_recorded_authority(
        self, root: Path, authority: str | DesignFacts, position: int
    ) -> DeliveryOutcome | None:
        """Does the document on disk still resolve this value's recorded locator?

        The zero-cost replay arm trusts a stored `design=bound` designation.
        MEASURED: after a human renamed the owned H2 out of the configured
        document, that arm still reported Success over a section the file no
        longer carried.  A designation is not evidence, so the record is
        confirmed HERE against the document itself, through the same
        `resolve_authority_section` law that already decides what `<doc>#<heading>`
        names for the post-write and DEVOPS read-backs, and through the same
        property-admitted read (`_markdown_text`) that keeps a symlinked or
        out-of-root file from deciding what a bound record means.

        `None` is agreement: the caller then publishes exactly today's answer.
        An EMPTY recorded locator names no configured section -- it is the
        documented provider-authored facts value -- so it is not a disagreement
        and L1 (ADR-DES-003 §2) stays free for it.
        """
        if not isinstance(authority, DesignFacts):
            return None
        locator = authority.authority_locator
        document, separator, heading = locator.partition("#")
        if not (separator and heading):
            return None
        text = _markdown_text(root, document)
        if text is None:
            # The world did not say no, it did not answer: class C (§2.5).
            return self._fail(
                Disposition.Indeterminate,
                "DesignAuthorityUnavailable",
                f"the stored record says this value's design is bound to "
                f"{locator}, and {document} cannot be read, so whether the "
                "document still carries that section is unknown",
                f"restore a readable repo-local {document} in this repository, "
                f"then re-invoke `des design --repo-root <root> --value "
                f"{position}`",
            )
        resolved = resolve_authority_section(
            text, heading, locator=locator, doc_part=document
        )
        if isinstance(resolved, ResolvedAuthoritySection):
            return None
        return self._fail(
            Disposition.Refusal,
            "DesignAuthorityUnlocatable",
            f"the stored record says this value's design is bound to {locator}, "
            f"while {document} on disk resolves no such section: the record and "
            f"the file disagree ({resolved.reason})",
            f"re-bind this value over the document as it now stands with `des "
            f"design --repo-root <root> --value {position} --finding -`",
        )

    def oracle_turn_complete(
        self,
        root: Path,
        stored: StoredHandover,
        ready: HandoverValue,
        design: AuthorityFacts,
    ) -> bool:
        """Is this value's APPROVED oracle turn already a recorded fact?

        Absent record, a workspace that no longer holds what the record
        describes, and a measurement that did not resolve all answer NO: the
        turn is bought again, exactly as a resume does inside the loop.
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
            self.last_diagnostic or "",
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

    def verified_verdict(self, root: Path, stored: StoredHandover) -> str | None:
        """The word the judge used about the recorded candidate, or `None`.

        `None` where a record predates this half or Git could not answer: the
        caller then holds a candidate whose judgement is unknown, which is not
        the same as an admitted one and must not be read as one.
        """
        observed = self._git(
            root,
            "log",
            "-1",
            "--format=%s",
            turn_ref(stored.request, stored.request, VERIFY_OUTCOME_TURN),
        )
        subject = observed.stdout.strip()
        if observed.returncode or not subject.startswith(_VERDICT_SUBJECT):
            return None
        return subject[len(_VERDICT_SUBJECT) :]

    def record_integration_decision(
        self,
        root: Path,
        stored: StoredHandover,
        candidate: str,
        verdict: str,
        reason: str,
    ) -> DeliveryOutcome | None:
        """Write down that the ORCHESTRATOR decided this integration, or refuse.

        Not best-effort, unlike every other record here: the others cost a
        re-bought turn when they are missing, while this one is the whole
        difference between a decision and a silent overwrite of a judgement. A
        history where the override cannot be read back is exactly the state this
        step exists to prevent, so an unwritable record refuses the step.
        """
        observed = self._git(root, "rev-parse", f"{candidate}^{{tree}}")
        env = declared_child_environment()
        written = (
            observed
            if observed.returncode
            else self._git(
                root,
                "commit-tree",
                observed.stdout.strip(),
                "-p",
                candidate,
                "-m",
                f"{_DECISION_SUBJECT}{verdict}",
                "-m",
                reason,
                env=env,
            )
        )
        if written.returncode:
            return self._git_failure(
                written,
                disposition=Disposition.Indeterminate,
                what="DecisionUnrecordable",
                why=f"the decision to integrate {candidate} over a "
                f"{verdict} judgement could not be written down",
                how="restore Git write access to the repository, then invoke "
                "this step again",
            )
        pointed = self._git(
            root,
            "update-ref",
            decision_ref(stored.request, candidate),
            written.stdout.strip(),
            env=env,
        )
        if pointed.returncode:
            return self._git_failure(
                pointed,
                disposition=Disposition.Indeterminate,
                what="DecisionUnrecordable",
                why=f"the decision record for {candidate} was written but could "
                "not be named, so nothing can find it again",
                how="restore Git write access to the repository, then invoke "
                "this step again",
            )
        return None

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
            candidate_bytes = self._git_bytes(root, "show", f"{candidate}:{path}")
            observed = current[path]
            if candidate_bytes is None or observed != ("file", candidate_bytes):
                return False
        return True

    def verified_candidate(self, root: Path, stored: StoredHandover) -> str | None:
        """The candidate a CURRENT verify record covers, or `None`.

        One predicate, derived from the single reading above: every consumer
        that only asks «may I build on this» gets the same answer the state
        projection and `des integrate` derive theirs from.
        """
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
        port: TaskInvocationPort | None,
        stored: StoredHandover,
        prepared: list[tuple[str, AuthorityFacts]],
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
        verified = self._verified_candidate(root, prepared, stored, base)
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
            base,
            candidate,
            _foreign_status(status, owned),
            _foreign_bytes(workspace, owned),
            owned,
        )
        if integrated.disposition is not Disposition.Success:
            return integrated
        cleanup = finalize_handover(root, stored.raw)
        if cleanup is not None:
            return self._blocked(cleanup)
        self._release_turn_records(root, stored)
        return integrated

    def devops_constraints(
        self,
        root: Path,
        port: TaskInvocationPort,
        request: str,
        authority: str,
        section: str,
    ) -> str | DeliveryOutcome:
        """One platform-architect turn that writes LOCATABLE operational constraints.

        `F-DEVOPS-CONSTRAINTS-INTO-DISTILL` states the shape: DEVOPS is
        optional, and when it is asked for, its product is not an essay -- it is
        CONSTRAINTS the Product Owner decomposes into observable values and the
        acceptance designer turns into execution-observing oracles, examined
        like any other code.  The same row names what was missing, and its item
        (3) is the falsifier this method is built around: verify that the
        authority resolver can read the section DEVOPS writes.

        So the product is resolved through `resolve_authority_section`, the
        SAME function the architect will later cite that section by, and the
        turn is refused when what it left is unreachable or empty.  A constraint
        no locator reaches is exactly the essay the decision forbids, and
        catching it here is GDP-1: before the Request that would consume it is
        ever decomposed.

        NO DEVOPS ROLE ENTERS THIS RUNNER.  This method runs before any
        decomposition exists, writes durable authority, and returns a locator.
        Everything downstream of it is an ordinary value.
        """
        document = _repo_local_markdown(root, authority)
        if document is None:
            return self._fail(
                Disposition.Refusal,
                "AuthorityInadmissible",
                f"{authority} is not a repository-local Markdown file this step "
                "may write: no absolute path, no traversal, no symlink leaving "
                "the root, and the suffix must be .md",
                "pass a repository-relative path to a tracked .md file that "
                "already exists",
            )
        observed = self._observed_scope(root)
        if isinstance(observed, DeliveryOutcome):
            return observed
        status, before = observed
        turn = self._invoke(
            port,
            root,
            "nw-platform-architect",
            self._prompt(
                request=request,
                authority_document=authority,
                authority_section=section,
                constraint_task=(
                    "Write the operational constraints this Request implies into "
                    "the named section of the named document, and nothing else. "
                    "Each constraint must be observable by executing something "
                    "against the running system, because the acceptance designer "
                    "will turn it into an executable oracle."
                ),
            ),
            None,
            root,
        )
        denied = self._accepted(
            turn,
            rejected="ConstraintsRejected",
            indeterminate="ConstraintsIndeterminate",
            handover=False,
        )
        # A rejecting author owns no byte, exactly as at every other authoring
        # boundary in this runner: its finding travels, its edits do not.
        drift = self._scope_drift(
            root,
            status,
            before,
            (authority,) if denied is None else (),
            (authority,),
            None if denied is not None else (lambda path: path == authority),
        )
        if isinstance(drift, DeliveryOutcome):
            return drift
        if drift.attributed or drift.unattributed:
            changed = ", ".join(sorted({*drift.attributed, *drift.unattributed}))
            return self._fail(
                Disposition.Refusal,
                "ConstraintScopeDrift",
                f"the platform architect changed bytes outside the one authority "
                f"document it was given: {changed}",
                f"restore {changed} and re-invoke this step, which writes only "
                f"{authority}",
            )
        if denied is not None:
            return denied
        text = _markdown_text(root, authority)
        if text is None:
            return self._fail(
                Disposition.Indeterminate,
                "AuthorityUnreadable",
                f"{authority} cannot be read back after the turn, so whether the "
                "constraints were written is unknown",
                f"restore read access to {authority}, then re-invoke this step",
            )
        locator = f"{authority}#{section}"
        resolved = resolve_authority_section(
            text, section, locator=locator, doc_part=authority
        )
        if not isinstance(resolved, ResolvedAuthoritySection):
            return self._fail(
                Disposition.Refusal,
                "ConstraintsUnlocatable",
                f"the accepted turn left no section the authority resolver can "
                f"reach at {locator}: {resolved.reason}",
                f"re-invoke this step so the turn writes a heading named "
                f"{section!r} into {authority}; a constraint no locator reaches "
                "is an essay, and the Product Owner cannot consume it",
            )
        body = resolved.text.partition("\n")[2].strip()
        if not body:
            return self._fail(
                Disposition.Refusal,
                "ConstraintsEmpty",
                f"the section at {locator} carries a heading and no constraint "
                "under it",
                f"re-invoke this step so the turn writes at least one observable "
                f"constraint under {section!r} in {authority}",
            )
        return locator

    def craft_value(
        self,
        root: Path,
        port: TaskInvocationPort,
        stored: StoredHandover,
        ready: HandoverValue,
        design: AuthorityFacts,
    ) -> DeliveryOutcome | tuple[str, ...]:
        """One crafter turn for this value's batch, routed to nobody.

        The turn itself is `_contribute` over a one-value selection, with its
        blocker routing switched OFF: a refusing craft turn's closed word comes
        back to the caller as data instead of buying a window.  ADR-SSOT-002
        Section 4b makes choosing which role answers a finding the
        orchestrator's decision, and the software may not take it by reading
        that word.

        Returns the silent-batch sentences on success -- an accepted turn that
        changed none of its mutable targets is honestly reported, never refused
        here, for the reason `_contribute` already states.
        """
        head = self._head(root)
        if isinstance(head, DeliveryOutcome):
            return head
        contributed = self._contribute(
            root,
            head,
            port,
            [(ready.observation, design)],
            stored.raw,
            stored,
            route_blockers=False,
        )
        if isinstance(contributed, DeliveryOutcome):
            return contributed
        _, silent = contributed
        return silent

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

    def craft_settlement(
        self,
        root: Path,
        stored: StoredHandover,
        ready: HandoverValue,
        design: AuthorityFacts,
    ) -> CraftSettlement:
        """Where this value's craft turn stands, and settle it when it may be.

        THE GATE ORDER IS THE DESIGN.  The recorded-over-current-bytes question
        is asked FIRST, so the ordinary resume keeps costing only Git.  Then the
        RECORD must exist: an absent craft record is never settled by a green
        oracle and the oracle is not even executed for it.  That is the
        2026-09-04 guard, where path-existence-as-green skipped craft twice --
        bytes that happen to satisfy an assertion are not evidence that the work
        was ever done, and ADR-DES-003 fixes craft's precondition as the RECORD
        rather than the file.  It is also what bounds the added cost: the first
        craft and the recorded-current resume buy no execution at all.

        THE WITNESS IS THE RUNNER'S EXISTING EXECUTION.  `_executed_oracle_set`
        runs the value's TRACKED oracle in the workspace through the design's own
        declared vector -- the same call, the same `ORACLE-RED:` operator line,
        the same verdict axis the pre-craft step already uses.  Nothing new is
        executed and no second notion of «green» is introduced.

        THE RE-POINT IS DELIBERATELY NOT `_stamp_craft_record`.  That helper
        DROPS the record when the owned tree equals the base, so that a bought
        turn which wrote nothing keeps its "rerun the dispatch" repair honest.
        No turn is bought here, so dropping would instead break this step's own
        promise -- the record re-pointed at the current bytes -- and send the
        next `des state` straight back to `des craft`.
        """
        if self.craft_turn_complete(root, stored, ready, design):
            return CraftSettlement.RecordedOverCurrentBytes
        recorded = self._turn_recorded(
            root, stored.request, ready.observation, _CRAFT_TURN
        )
        if not recorded:
            return CraftSettlement.Unsettled
        if not self._observed_green(
            self._executed_oracle_set(root, [(ready.observation, design)])
        ):
            return CraftSettlement.Unsettled
        head = self._head(root)
        if isinstance(head, DeliveryOutcome):
            return CraftSettlement.Unsettled
        tree = self._paths_tree(root, self._craft_record_paths(design))
        identity = RecordIdentity.of(root, stored, ready, design)
        if tree is None or identity is None:
            return CraftSettlement.Unsettled
        self._record_turn(
            root,
            head,
            stored.request,
            ((ready.observation, identity),),
            _CRAFT_TURN,
            tree,
        )
        return CraftSettlement.SettledByGreenOracle

    def oracle_value(
        self,
        root: Path,
        port: TaskInvocationPort,
        stored: StoredHandover,
        ready: HandoverValue,
        design: AuthorityFacts,
        *,
        finding: str | None = None,
    ) -> MeasuredOracleSet:
        """Author or correct one value's oracle, measure it RED, and judge it.

        TWO THINGS AND ONE STEP, and the third was RETIRED. Between authoring
        and measuring RED the caller has no decision to make. It did have one
        between «measured» and «judged», and the delivered step denied it by
        buying a pre-craft judge -- a FOURTH model boundary, where ADR-SSOT-002
        §4a names exactly three and lists the pre-craft oracle review among the
        mechanisms that lapse (ADR-DES-003 §5). The oracle's independent
        judgement is the whole-diff review at `verify`, which sees oracle and
        implementation together. Run 23's lesson, a judge approving a broken
        oracle in 27.4s, is answered by the RED measurement, which is software
        and free. Craft-time oracle defects still return as `BLOCKED-BY: oracle`
        to `des oracle --finding`. One paid turn fewer per value; the accepted
        risk is §4a's own `Observation fidelity` falsifier, already written: if
        it fires, the separate pre-craft boundary returns.

        AUTHORING OR CORRECTING is decided by `finding` and by nothing inferred.
        Without one this is the first authoring turn.  With one the acceptance
        author is given the CURRENT executed RED beside the finding, measured
        here rather than remembered, because a step invoked alone holds no
        memory of the run that refused -- and a correction reading a second,
        later measurement is exactly the disagreement `AcceptanceFinding`
        carries its own `measured` to prevent.

        The turn record is written only once the set is ADMITTED, for the reason
        `_ORACLE_TURN` already states: recording at authoring time would let a
        resume skip a review that had vetoed.
        """
        prepared = [(ready.observation, design)]
        # A `finding` with NO oracle byte observable on disk is still a FIRST
        # authoring turn wearing one -- a prior rejecting turn owns no byte by
        # construction (`_prepare_single`'s own rule), so "correct the existing
        # evidence" has nothing to read and must not be attempted.  Route it to
        # the same author call `finding is None` already makes, carrying the
        # finding along, rather than answering with a preverification refusal
        # that treats "not authored yet" as "authored and broken".
        no_oracle_byte = (
            finding is not None
            and _authority_bytes(root, design.acceptance_paths) is None
        )
        if finding is None or no_oracle_byte:
            observed = self._observed_scope(root)
            if isinstance(observed, DeliveryOutcome):
                return MeasuredOracleSet((), observed)
            status, workspace = observed
            authored = self._prepare_single(
                root,
                port,
                (ready.observation,),
                design,
                stored.raw,
                status,
                workspace,
                finding=finding,
            )
            if authored is not None:
                return MeasuredOracleSet((), authored)
        else:
            executed = self._executed_oracle_set(root, prepared)
            if isinstance(executed, DeliveryOutcome):
                return MeasuredOracleSet((), executed)
            denied = self._acceptance_correction(
                root, port, prepared, stored.raw, finding, executed.measured
            )
            if denied is not None:
                return MeasuredOracleSet(executed.measured, denied)
        executed = self._executed_oracle_set(root, prepared)
        if isinstance(executed, DeliveryOutcome):
            return MeasuredOracleSet((), executed)
        if executed.refusal is not None:
            # Owned by construction, with no judgement to make: the bytes that
            # failed to reach their own assertion were written by the acceptance
            # designer and by no other role in this Request.
            return MeasuredOracleSet(
                executed.measured,
                AcceptanceFinding(
                    executed.refusal.finding,
                    DefectOwner.Oracle,
                    None,
                    executed.refusal.terminal,
                    executed.measured,
                ),
            )
        self._record_oracle_turn(root, stored, ready.observation, design)
        return MeasuredOracleSet(executed.measured, None)

    def _record_oracle_turn(
        self,
        root: Path,
        stored: StoredHandover,
        observation: str,
        design: AuthorityFacts,
    ) -> bool:
        """Record the approved oracle turn, best-effort, exactly as the loop does.

        Best-effort for the reason recording is everywhere in this runner: a
        record that is not written costs the NEXT invocation one re-authored
        turn and nothing else, and a Git that never answered must not turn an
        approved oracle into a refusal.

        It ANSWERS whether it recorded, because `oracle_settlement` may only
        report a re-pointed record when one was actually written, and the
        alternative was a second spelling of «resolve HEAD, take the owned tree
        over the acceptance paths, record the oracle turn» beside this one.
        `oracle_value` ignores the answer and behaves exactly as before: there
        the unwritten record costs a re-authored turn and nothing else.
        """
        head = self._head(root)
        if isinstance(head, DeliveryOutcome):
            return False
        tree = self._paths_tree(root, design.acceptance_paths)
        identity = self._record_identity(root, stored, observation, design)
        if tree is None or identity is None:
            return False
        self._record_turn(
            root,
            head,
            stored.request,
            ((observation, identity),),
            _ORACLE_TURN,
            tree,
        )
        return True

    @staticmethod
    def _resolved_execution(executed: OracleExecution | DeliveryOutcome) -> bool:
        """Did the executed set reach its own assertion and ANSWER, red or green?

        A different question from `_observed_green`, asked by a different lane,
        and deliberately not a refactor of it: craft settles only on all-GREEN,
        while the oracle lane settles on any RESOLVED verdict because RED is the
        admitted pre-craft answer.  One shared predicate would make the two
        lanes' rules interchangeable in a way neither step means.

        Total and closed.  A `DeliveryOutcome` (the set could not be executed, or
        its report contradicted its exit status -- including the `indeterminate`
        verdict `_executed_oracle_set` turns into an `OracleRedUnobservable`
        terminal), an EMPTY `measured` tuple (nothing was observed, which is not
        the same as observed anything -- GDP-6), and any entry whose verdict is
        not one of the two words `red` and `green` that `_oracle_verdict`
        produces -- `broken` above all -- each answer NO on their own branch.

        `refusal` is deliberately NOT consulted.  It answers «may this set
        proceed to craft», a different question, and `_ORACLE_REFUSING` is
        documented as a set that may later be armed with more verdicts -- which
        must not silently stop a resolved oracle from witnessing its own record.
        Today the two readings coincide; that is exactly why the divergent one is
        written down here rather than assumed.
        """
        if isinstance(executed, DeliveryOutcome):
            return False
        if not executed.measured:
            return False
        return all(
            item.get("verdict") in ("red", "green") for item in executed.measured
        )

    def oracle_settlement(
        self,
        root: Path,
        stored: StoredHandover,
        ready: HandoverValue,
        design: AuthorityFacts,
    ) -> OracleSettlement:
        """Where this value's oracle turn stands, and settle it when it may be.

        THE GATE ORDER IS THE DESIGN, and it is FOUR gates.

        (1) Recorded over the CURRENT bytes is asked first, by calling
        `oracle_turn_complete`, so the ordinary resume keeps costing only Git and
        executes nothing at all.

        (2) The RECORD must then exist.  An absent oracle record is never
        settled, and the oracle is not even executed for it: bytes that happen to
        satisfy an assertion are not evidence that a turn was ever approved,
        which is ADR-SSOT-002's 2026-09-04 class.  It also closes the
        shared-acceptance-bytes hazard the reference model names -- when a
        SIBLING value's authoring wrote the shared oracle file, the value that
        never recorded its own oracle turn still buys it.  This gate is what
        bounds the added cost: the first authoring and the recorded-current
        resume buy no execution.

        (3) Every TRACKED acceptance path must still be present, and this is its
        OWN gate rather than something folded into the verdict, because MEASURED
        they disagree: with a tracked SUPPORT path deleted, the tracked oracle
        still executed green, and `_owned_tree` stages only what is present, so a
        verdict-only reading would have re-pointed a record over a path set that
        had lost a file.  `_path_present`'s third state, `None` for a filesystem
        that refused to say, degrades to `Unsettled` like every other unresolved
        measurement.

        (4) The execution must have RESOLVED.  The witness is the runner's own
        `_executed_oracle_set` -- the same call, the same `ORACLE-RED:` operator
        line, the same verdict axis the pre-craft step already uses.  Nothing new
        is executed and no second notion of a verdict is introduced.

        The re-point REUSES `_record_oracle_turn`, so there is one spelling of
        «record this value's oracle turn» and not two.  It is deliberately not
        the craft lane's `_stamp_craft_record`, which DROPS a record whose tree
        equals base and would break this step's own promise.
        """
        if self.oracle_turn_complete(root, stored, ready, design):
            return OracleSettlement.RecordedOverCurrentBytes
        if not self._turn_recorded(
            root, stored.request, ready.observation, _ORACLE_TURN
        ):
            return OracleSettlement.Unsettled
        for tracked in design.acceptance_paths:
            if self._path_present(root / tracked) is not True:
                return OracleSettlement.Unsettled
        executed = self._executed_oracle_set(root, [(ready.observation, design)])
        if not self._resolved_execution(executed):
            return OracleSettlement.Unsettled
        assert isinstance(executed, OracleExecution)
        if not self._record_oracle_turn(root, stored, ready.observation, design):
            return OracleSettlement.Unsettled
        self._settled_oracle_measured = executed.measured
        return OracleSettlement.SettledByItsOwnExecution

    #: The measurement the last `SettledByItsOwnExecution` stood on.  Empty on a
    #: runner that never settled one, and never read on any other arm.
    _settled_oracle_measured: tuple[dict[str, object], ...] = ()

    @property
    def settled_oracle_measured(self) -> tuple[dict[str, object], ...]:
        """The execution that witnessed the last settled oracle record.

        Carried the way `last_role` and `last_diagnostic` are, because the
        settlement's answer is one closed WORD -- widening it to a pair would put
        the evidence inside the branching type and give the step a second thing
        to branch on.  The step prints these rows so that an examiner can tell
        the red arm from the green arm, rather than reading a success that
        promises evidence it never shows.
        """
        return self._settled_oracle_measured

    def rewrite_request(
        self,
        root: Path,
        port: TaskInvocationPort,
        stored: StoredHandover,
        request: str,
        finding: str | None = None,
    ) -> tuple[StoredHandover, RequestRewrite] | DeliveryOutcome:
        """One Product Owner turn over a CHANGED Request, and the split it implies.

        ADR-DES-003 §7. The repair for a changed mind was deleting the handover
        by hand -- six times in two days -- and each deletion also dropped every
        turn record, so it cost the design, oracle and craft turns of every
        value, kept or not.

        WHO DECIDES WHAT. Which values still hold is a SEMANTIC decision and
        stays with the Product Owner, which is why this buys a turn. The
        software then splits by BYTE IDENTITY of the observation -- a primitive
        it can measure -- and never by similarity, which it cannot: a guessed
        match would silently keep an authority the model did not mean to keep.

        ENACTMENT ORDER IS A LAW. The archive is written, then the kept records
        are re-keyed, then the handover is rewritten by compare-and-swap, and
        only then are the abandoned records dropped. An interruption therefore
        leaves either the old graph whole or the new graph whole -- never a
        graph without its records.
        """
        previous = {value.observation for value in stored.values}
        po = self._invoke(
            port,
            root,
            "nw-product-owner",
            self._prompt(
                rewrite_task=(
                    "Return the whole ordered value sequence for the supplied "
                    "Request, addressing the finding when present and reusing "
                    "a stored observation VERBATIM "
                    "wherever it still holds -- an observation reused byte for "
                    "byte keeps everything already paid for it. Write no "
                    "document, authority or handover."
                ),
                request=request,
                previous_request=stored.request,
                stored_values=[
                    [
                        value.observation,
                        "design bound" if value.authority is not None else "no design",
                    ]
                    for value in stored.values
                ],
                **({} if finding is None else {"finding": finding}),
            ),
            stored.raw,
        )
        denied = self._accepted(
            po,
            rejected="ProductOwnerRejected",
            indeterminate="ProductOwnerIndeterminate",
            handover=True,
        )
        if denied is not None:
            return denied
        assert not isinstance(po, DeliveryOutcome)
        placeholder = self._placeholder(po.product_values)
        if placeholder is not None:
            return placeholder
        proposed = self._ordered_po_values(po.product_values, ())
        if not proposed:
            return self._fail(
                Disposition.Indeterminate,
                "ProductValuesMalformed",
                "accepted PO supplied no values for the rewritten Request",
                "return a nonempty ordered value sequence",
            )
        # THE SPLIT, by byte identity and by nothing else.
        by_observation = {value.observation: value for value in stored.values}
        rewritten = tuple(
            replace(
                by_observation[value.observation],
                dependencies=value.dependencies,
                acceptance=(),
                acceptance_oracle=None,
                acceptance_supports=(),
                acceptance_verification=None,
                acceptance_oracle_verification_index=None,
                acceptance_design_basis_sha256=None,
            )
            if value.observation in by_observation
            else value
            for value in proposed
        )
        kept = tuple(v.observation for v in rewritten if v.observation in previous)
        fresh = tuple(v.observation for v in rewritten if v.observation not in previous)
        archived = tuple(
            observation for observation in previous if observation not in set(kept)
        )
        archive = self._archive_graph(root, stored)
        self._rekey_turn_records(root, stored.request, request, kept)
        updated = rewrite_handover(root, stored.raw, request, rewritten)
        if isinstance(updated, Blocked):
            return self._blocked(updated)
        self._drop_records_for(root, stored.request, archived)
        return updated, RequestRewrite(kept, archived, fresh, archive)

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
            for role in (ORACLE_TURN, CRAFT_TURN):
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
            for role in (ORACLE_TURN, CRAFT_TURN):
                self._git(
                    root, "update-ref", "-d", turn_ref(request, observation, role)
                )

    def decompose(
        self,
        root: Path,
        port: TaskInvocationPort,
        raw_request: str,
        operational_facts: dict[str, object] | None = None,
        *,
        finding: str | None = None,
    ) -> StoredHandover | DeliveryOutcome:
        """One Product Owner turn, and the ordered graph it is recorded as.

        ADR-SSOT-002 Section 4b names this step by property: «Recording an
        accepted decomposition as owned state -- takes the validated ordered
        observations, returns the persisted graph, or the drift that prevented
        the write.»  It is exactly the block `_run_locked` ran inline while the
        runner still owned the sequence, unchanged in what it observes and in
        what it refuses; what moved is that the caller now decides what happens
        next, which is why it RETURNS the graph instead of falling through into
        the design of value one.
        """
        # No durable graph exists while PO reasons.  A PO turn which creates
        # one is an observable protocol violation, not product information.
        before_po = self._path_present(handover_path(root))
        if before_po is None:
            return self._fail(
                Disposition.Indeterminate,
                "HandoverUnobservable",
                "whether a handover exists cannot be observed on this filesystem",
                "restore read access to the handover directory, then re-run",
            )
        if before_po:
            return self._fail(
                Disposition.Indeterminate,
                "HandoverUnexpected",
                "handover appeared before PO",
                "inspect shared checkout",
            )
        product_before = self._snapshot(root, _PRODUCT_ROOT)
        facts: dict[str, object] = {"request": raw_request}
        if finding is not None:
            facts["finding"] = finding
        if operational_facts is not None:
            facts["operational_facts"] = operational_facts
        po = self._invoke(port, root, "nw-product-owner", self._prompt(**facts), None)
        after_po = self._path_present(handover_path(root))
        if after_po is None:
            return self._fail(
                Disposition.Indeterminate,
                "HandoverUnobservable",
                "whether PO created a handover cannot be observed on this filesystem",
                "restore read access to the handover directory, then re-run",
            )
        if after_po:
            return self._fail(
                Disposition.Refusal,
                "HandoverDrift",
                "PO changed the absent handover",
                "inspect shared checkout",
            )
        if self._changed(product_before, self._snapshot(root, _PRODUCT_ROOT)):
            return self._fail(
                Disposition.Indeterminate,
                "ProductAuthorityDrift",
                "PO changed durable product authority",
                "restore product authority",
            )
        denied = self._accepted(
            po,
            rejected="ProductOwnerRejected",
            indeterminate="ProductOwnerIndeterminate",
            # The branch that reaches here has already OBSERVED the absent
            # handover twice -- before the turn and after it -- so this is
            # the runner's own primitive fact, not an assumption.
            handover=False,
        )
        if denied is not None:
            return denied
        assert not isinstance(po, DeliveryOutcome)
        placeholder = self._placeholder(po.product_values)
        if placeholder is not None:
            return placeholder
        values = self._ordered_po_values(po.product_values, ())
        if not values:
            return self._fail(
                Disposition.Indeterminate,
                "ProductValuesMalformed",
                "accepted PO supplied no values",
                "return a nonempty ordered value sequence",
            )
        created = create_handover(
            root, raw_request, values, getattr(self, "feature_id", None)
        )
        if isinstance(created, Blocked):
            return self._blocked(created)
        return created

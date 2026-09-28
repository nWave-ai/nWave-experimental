"""Candidate-bound host role artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.git.git_observation import observe_bytes
from des.adapters.driven.task_invocation.model_envelope import decode_model_run
from des.application.delivery_continuation import DeliveryContinuationRunner
from des.application.delivery_steps import StepOutcome, _prepared
from des.application.handover import (
    _facts_wire,
    _shared_wire,
    design_basis_sha256,
    stored_candidate_handover,
    stored_handover,
)
from des.domain.distill_document import selected_revision_sha256
from des.domain.expectation_charter import (
    ExpectationCharterInvalid,
    member_value,
    namespace_directory,
    parse_canonical,
    source_fingerprint_sha256,
)
from des.domain.public_observations import (
    WITHHELD,
    Defect,
    ObservationPacketRefused,
    read_packet,
)
from des.ports.driven_ports.task_invocation_port import DesignFacts, ModelOutcome


if TYPE_CHECKING:
    from des.ports.driven_ports.task_invocation_port import ModelRun


class ArtifactConflict(ValueError):
    """Existing write-once bytes differ from the requested bytes."""

    def __init__(self, existing: bytes) -> None:
        super().__init__("conflicting bytes for existing role artifact")
        self.digest = hashlib.sha256(existing).hexdigest()


class RoleInputAlreadyPrepared(ValueError):
    """A different role input already exists for this candidate and role."""

    def __init__(self, path: str, digest: str) -> None:
        super().__init__(
            f"role input {path} (sha256 {digest}) already exists and is "
            "write-once; different bytes cannot replace it"
        )
        self.path = path
        self.digest = digest


def _stored_for_candidate(
    root: Path, candidate: str, runner: DeliveryContinuationRunner
):
    """Read active state, or the immutable snapshot of an integrated candidate."""
    active = stored_handover(root)
    if hasattr(active, "request"):
        return active
    archived = stored_candidate_handover(root, candidate)
    if hasattr(archived, "request") and runner.destination_is(root, candidate):
        return archived
    return None


def _candidate_is_admitted(
    root: Path, candidate: str, stored, runner: DeliveryContinuationRunner
) -> bool:
    """A live verify record, or an integrated candidate's retained snapshot."""
    active = stored_handover(root)
    if hasattr(active, "raw") and active.raw == stored.raw:
        return runner.verified_candidate(root, stored) == candidate
    return runner.destination_is(root, candidate)


def _write(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != payload:
        raise ArtifactConflict(path.read_bytes())
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
    try:
        os.link(temporary, path)
    except FileExistsError:
        if path.read_bytes() != payload:
            raise ArtifactConflict(path.read_bytes()) from None
    finally:
        Path(temporary).unlink(missing_ok=True)
    return hashlib.sha256(payload).hexdigest()


#: Known interpreter basenames mapped to the flag(s) THEY use to accept code
#: inline instead of a file path. Scoped narrowly -- only these named
#: interpreters are recognized; an unknown interpreter's flags are never
#: guessed at (see `_examiner_argv` docstring for that limitation).
_INLINE_CODE_FLAGS_BY_INTERPRETER = {
    "sh": frozenset({"-c"}),
    "bash": frozenset({"-c"}),
    "dash": frozenset({"-c"}),
    "zsh": frozenset({"-c"}),
    "ksh": frozenset({"-c"}),
    "node": frozenset({"-e", "--eval"}),
    "nodejs": frozenset({"-e", "--eval"}),
    "ruby": frozenset({"-e"}),
    "perl": frozenset({"-e"}),
    "perl5": frozenset({"-e"}),
}

#: Any `python`, `python2`, `python3`, or versioned `python3.x` basename.
_PYTHON_BASENAME = re.compile(r"^python[23]?(\.\d+)?$")

#: Known interpreter options that consume a separate following argv token
#: (their operand), so that operand must not be mistaken for a script path.
_OPERAND_TAKING_FLAGS_BY_INTERPRETER = {
    "python": frozenset({"-W", "-X"}),
}


def _inline_code_flags_for(executable: str) -> frozenset[str]:
    """The inline-code flag(s) for a recognized interpreter, else empty."""
    name = Path(executable).name
    if _PYTHON_BASENAME.fullmatch(name):
        return frozenset({"-c"})
    return _INLINE_CODE_FLAGS_BY_INTERPRETER.get(name, frozenset())


def _operand_taking_flags_for(executable: str) -> frozenset[str]:
    """Flags of `executable` that take a separate operand token, else empty."""
    name = Path(executable).name
    if _PYTHON_BASENAME.fullmatch(name):
        return _OPERAND_TAKING_FLAGS_BY_INTERPRETER["python"]
    return frozenset()


def _matches_inline_flag(token: str, inline_flags: frozenset[str]) -> bool:
    """Whether `token` invokes an inline-code flag: exact, `--flag=VALUE`,
    a short flag with an attached value (`-cCODE`), or bundled short flags
    ending in it (`-Ic`, `-lc`).
    """
    for flag in inline_flags:
        if token == flag:
            return True
        if flag.startswith("--"):
            if token.startswith(f"{flag}="):
                return True
        elif (
            len(flag) == 2
            and token.startswith("-")
            and not token.startswith("--")
            and len(token) > 1
        ):
            letter = flag[1]
            body = token[1:]
            if body.startswith(letter):
                return True
            if body.endswith(letter) and body[:-1].isalpha():
                return True
    return False


def _interpreter_argv_embeds_inline_code(argv: list[object]) -> bool:
    """Whether `argv` invokes a recognized interpreter with inline code.

    Scans only the interpreter's own option tokens, stopping at the script
    path or at `-m` (the rest of argv becomes the named module's own public
    arguments). A known operand-taking flag (`python -W ignore`) consumes its
    following token without ending the scan. A flag that merely shares a
    letter with an inline-code flag -- `go test -c`, `grep -e PATTERN` --
    never matches because `go` and `grep` are not recognized interpreters.
    """
    if not argv or not isinstance(argv[0], str):
        return False
    inline_flags = _inline_code_flags_for(argv[0])
    if not inline_flags:
        return False
    operand_taking = _operand_taking_flags_for(argv[0])
    skip_next = False
    for token in argv[1:]:
        if not isinstance(token, str):
            continue
        if skip_next:
            skip_next = False
            continue
        if token == "-m":
            return False
        if _matches_inline_flag(token, inline_flags):
            return True
        if token in operand_taking:
            skip_next = True
            continue
        if not token.startswith("-"):
            return False
    return False


def _examiner_argv(argv: object) -> object:
    """Project one native `argv` for the source-blind examiner.

    Most commands project verbatim as the examiner's public stimulus. An
    argv invoking a recognized interpreter's own inline-code flag
    (`python -c`, `sh -c`, `node -e`, ...) carries production/oracle source,
    so it is replaced by an explicit withheld marker naming the reason
    instead. `python -m tool -c ...` stays public: `-m` hands the rest of
    argv to the named tool.

    Limitation: only interpreters named in
    `_INLINE_CODE_FLAGS_BY_INTERPRETER` (plus python) are recognized; an
    unlisted interpreter's inline-code flag is not detected.
    """
    if not isinstance(argv, list) or not _interpreter_argv_embeds_inline_code(argv):
        return argv
    return {
        "withheld": True,
        "reason": (
            "argv invokes a recognized interpreter with its inline-code "
            "flag (such as python -c, sh -c, node -e); the source-blind "
            "examiner is not shown production or oracle source text, so "
            "this command is named as withheld rather than silently "
            "omitted"
        ),
    }


def _examiner_native_evidence(
    native: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Source-safe bounded projection of candidate-bound native evidence.

    Reuses the same candidate-bound records the reviewer receives (loaded by
    the caller from the sealed native evidence file); this function only
    narrows which of their keys reach the examiner. `argv` and `cwd` are
    included: they are the public stimulus DES actually ran, needed to join a
    captured command with its captured output. `declared_environment` stays
    withheld -- it is native metadata about the run, not the command or its
    observation, and native metadata projection already bounds it elsewhere.
    A key absent from a historical record projects as `None` (unknown
    metadata), which is distinct from a key present with an empty value
    (`""`, `[]`) -- both survive `dict.get` unchanged.
    """
    return [
        {
            **{
                k: item.get(k)
                for k in (
                    "exit",
                    "stdout",
                    "stderr",
                    "origin",
                    "incomplete",
                    "incomplete_what",
                    "incomplete_why",
                    "incomplete_how",
                    "duration_seconds",
                )
            },
            "argv": WITHHELD,
            "stdout": WITHHELD,
            "stderr": WITHHELD,
            "cwd": WITHHELD,
        }
        for item in native
    ]


class LocatorBearingCriterionId(ValueError):
    """A selected acceptance criterion id carries a known repository locator."""

    def __init__(self, criterion_id: str) -> None:
        super().__init__(criterion_id)
        self.criterion_id = criterion_id


_LOCATOR_TRAILING_SELECTOR = r"(::[\w.]+)?"


def _redact_repository_locators(
    text: str, owned_paths: tuple[str, ...]
) -> tuple[str, bool]:
    """Replace known repository locators and return whether any were withheld."""
    redacted = False
    for path in owned_paths:
        if not path:
            continue
        pattern = re.compile(re.escape(path) + _LOCATOR_TRAILING_SELECTOR)
        text, count = pattern.subn("[withheld repository locator]", text)
        if count:
            redacted = True
    return text, redacted


def _projected_selected_acceptance(
    prepared: list[tuple[int, object]], owned_paths: tuple[str, ...]
) -> list[dict[str, object]]:
    """Project selected acceptance criteria for the source-blind examiner."""
    projected: list[dict[str, object]] = []
    for position, (_observation, design) in enumerate(prepared, start=1):
        obligations = design.acceptance_obligations
        criteria: list[dict[str, object]] | None = None
        if obligations:
            criteria = []
            for obligation in obligations:
                if any(path and path in obligation.id for path in owned_paths):
                    raise LocatorBearingCriterionId(obligation.id)
                stimulus, stimulus_redacted = _redact_repository_locators(
                    obligation.stimulus, owned_paths
                )
                expected, expected_redacted = _redact_repository_locators(
                    obligation.expected, owned_paths
                )
                criteria.append(
                    {
                        "id": obligation.id,
                        "stimulus": stimulus,
                        "expected": expected,
                        "redacted_fields": [
                            *(("stimulus",) if stimulus_redacted else ()),
                            *(("expected",) if expected_redacted else ()),
                        ],
                    }
                )
        projected.append(
            {
                "value": position,
                "source": "DISTILL" if obligations else "DESIGN",
                "revision_sha256": design.selected_revision_sha256,
                "criteria": criteria,
            }
        )
    return projected


def _candidate_expectation_charters(
    root: Path, stored, tree_sha: str, runner: DeliveryContinuationRunner
) -> list[dict[str, object]]:
    """Every validated charter bound to THIS candidate's own tree, ordered.

    Enumerate the complete assigned namespace in the candidate tree. A bad
    entry refuses the packet instead of disappearing from the projection.
    """
    namespace = namespace_directory(stored.scope)
    parent = ""
    for part in Path(namespace).parts:
        parent = f"{parent}/{part}" if parent else part
        observed_parent = runner._git(root, "ls-tree", tree_sha, "--", parent)
        if observed_parent.returncode:
            raise ValueError(
                f"candidate charter namespace {parent} cannot be inspected"
            )
        if observed_parent.stdout.strip():
            rows = [
                row
                for row in observed_parent.stdout.splitlines()
                if row.endswith("\t" + parent)
            ]
            if not rows or not rows[0].startswith("040000 tree "):
                raise ValueError(
                    f"candidate charter namespace parent {parent} is not a directory"
                )
    listing = observe_bytes(root, "ls-tree", "-rz", tree_sha, "--", namespace)
    if listing.returncode:
        raise ValueError("candidate charter namespace cannot be enumerated")
    entries: list[dict[str, object]] = []
    seen: set[int] = set()
    for record in filter(None, listing.stdout.split(b"\0")):
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, kind, _sha = metadata.decode("ascii").split(" ", 2)
            path = raw_path.decode("utf-8")
        except (ValueError, UnicodeError):
            raise ValueError(
                "candidate charter namespace has malformed tree entry"
            ) from None
        if not path.startswith(namespace + "/") or "/" in path[len(namespace) + 1 :]:
            raise ValueError(f"candidate charter namespace has nested entry {path}")
        position = member_value(Path(path).name)
        if mode not in ("100644", "100755") or kind != "blob" or position is None:
            raise ValueError(
                f"candidate charter namespace has noncanonical entry {path}"
            )
        if position in seen or position > len(stored.values):
            raise ValueError(
                f"candidate charter namespace has invalid value position {path}"
            )
        seen.add(position)
        observed = observe_bytes(root, "show", f"{tree_sha}:{path}")
        if observed.returncode:
            raise ValueError(f"candidate charter {path} cannot be read")
        data = observed.stdout
        try:
            charter = parse_canonical(data)
        except ExpectationCharterInvalid as error:
            raise ValueError(
                f"candidate charter {path} is malformed: {error}"
            ) from None
        if charter.value != position:
            raise ValueError(f"candidate charter {path} has a different value position")
        expected_source = source_fingerprint_sha256(
            stored.values[position - 1].observation, stored.scope, position
        )
        if charter.source_sha256 != expected_source:
            raise ValueError(f"candidate charter {path} has a stale source binding")
        entries.append(
            {
                "value": position,
                "path": path,
                "content_sha256": hashlib.sha256(data).hexdigest(),
                "source_sha256": charter.source_sha256,
                "intent": charter.intent,
                "public_start_recipe": charter.public_start_recipe,
                "exploration": charter.exploration,
                "positive_observations": list(charter.positive_observations),
                "negative_observation": charter.negative_observation,
            }
        )
    return sorted(entries, key=lambda item: item["value"])


def _sealed(payload: dict[str, object], kind: str) -> bytes:
    """Canonical artifact bytes with a digest of the payload excluding itself."""
    payload = {**payload, "kind": kind}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return json.dumps(
        {**payload, "payload_sha256": hashlib.sha256(canonical).hexdigest()},
        sort_keys=True,
        ensure_ascii=False,
    ).encode()


def _load_and_bind(
    root: Path, role: str, candidate: str, path: Path
) -> tuple[Path, dict[str, object], bytes]:
    """Load one sealed input at PATH and rebind it to current authority."""
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("prepared role input is unavailable") from error
    digest = payload.pop("payload_sha256", None)
    if payload.get("kind") != "role_input" or payload.get("role") != role:
        raise ValueError("prepared role input kind or role differs")
    if (
        not isinstance(digest, str)
        or hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        != digest
    ):
        raise ValueError("prepared role input digest differs")
    runner = DeliveryContinuationRunner()
    stored = _stored_for_candidate(root, candidate, runner)
    tree = runner._git(root, "rev-parse", f"{candidate}^{{tree}}")
    if (
        stored is None
        or not hasattr(stored, "raw")
        or not _candidate_is_admitted(root, candidate, stored, runner)
        or not runner.load_native_evidence_identity(root, candidate)
        or payload.get("candidate_sha") != candidate
        or payload.get("request_digest") != hashlib.sha256(stored.raw).hexdigest()
        or payload.get("request") != stored.request
        or tree.returncode
        or payload.get("candidate_tree_sha") != tree.stdout.strip()
        or payload.get("native_evidence_sha256") != runner.native_evidence_sha256
    ):
        raise ValueError("prepared role input authority binding differs")
    observed = payload.get("public_observations")
    if observed is not None and (
        not isinstance(observed, dict)
        or observed.get("candidate_sha") != payload.get("candidate_sha")
        or observed.get("candidate_tree_sha") != payload.get("candidate_tree_sha")
    ):
        raise ValueError("prepared role input observations binding differs")
    if role == "examiner":
        charters = payload.get("expectation_charters")
        if not isinstance(
            charters, list
        ) or charters != _candidate_expectation_charters(
            root, stored, tree.stdout.strip(), runner
        ):
            raise ValueError(
                "prepared expectation charter projection differs from the candidate's own tree"
            )
    payload["payload_sha256"] = digest
    return path, payload, raw


def load_prepared(
    root: Path, role: str, candidate: str
) -> tuple[Path, dict[str, object], bytes]:
    """Load the legacy fixed-name sealed input and rebind current authority."""
    path = root / ".nwave/des/logs/roles" / f"{candidate}-{role}-input.json"
    return _load_and_bind(root, role, candidate, path)


_CONTENT_ADDRESSED_INPUT = re.compile(
    r"^(?P<candidate>[0-9a-f]{40})-(?P<role>reviewer|examiner)-"
    r"(?P<digest>[0-9a-f]{64})-input\.json$"
)


def load_prepared_at(
    root: Path, role: str, candidate: str, path: Path
) -> tuple[Path, dict[str, object], bytes]:
    """Load one explicitly selected examiner input, content-addressed or legacy."""
    roles_dir = (root / ".nwave/des/logs/roles").resolve()
    try:
        # `des prepare-role` prints an INPUT relative to --repo-root. Resolve
        # that public form at the repository boundary, never against the
        # process cwd; absolute callers retain their explicit path.
        resolved = (path if path.is_absolute() else root / path).resolve()
    except OSError as error:
        raise ValueError("prepared role input is unavailable") from error
    try:
        resolved.relative_to(roles_dir)
    except ValueError:
        raise ValueError(
            "prepared role input must be inside the owned roles directory"
        ) from None
    legacy_name = f"{candidate}-{role}-input.json"
    match = _CONTENT_ADDRESSED_INPUT.fullmatch(resolved.name)
    if match is not None:
        if match.group("candidate") != candidate or match.group("role") != role:
            raise ValueError("prepared role input candidate or role differs")
    elif resolved.name != legacy_name:
        raise ValueError("prepared role input is not a recognized artifact name")
    result = _load_and_bind(root, role, candidate, resolved)
    if match is not None:
        if hashlib.sha256(result[2]).hexdigest() != match.group("digest"):
            raise ValueError(
                "prepared role input content digest differs from its filename"
            )
    return result


class SelectedRevisionUnavailable(ValueError):
    """The one selected acceptance revision cannot be read for a value.

    Carries the reader's own WHAT/WHY/HOW and disposition, so preparation
    reports the recoverable owner instead of a generic unavailability.
    """

    def __init__(self, outcome: StepOutcome) -> None:
        super().__init__(outcome.failure.why if outcome.failure else "")
        self.outcome = outcome


class RecoveryInputAlreadyPrepared(ValueError):
    """A recovery input is sealed; different current facts need a fresh value."""

    def __init__(self, path: str, digest: str) -> None:
        super().__init__(f"recovery input {path} already exists with sha256 {digest}")
        self.path = path
        self.digest = digest


def _recovery_binding_sha256(payload: dict[str, object]) -> str:
    """Return the immutable authority binding, excluding caller prose."""
    binding = {key: item for key, item in payload.items() if key != "finding"}
    return hashlib.sha256(
        json.dumps(binding, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def _recovery_path(root: Path, value: int, path_sha256: str | None = None) -> Path:
    """Locate a recovery input by its content-addressed path, retaining legacy history."""
    suffix = "" if path_sha256 is None else f"-{path_sha256}"
    return (
        root
        / ".nwave/des/logs/roles"
        / f"value-{value}-acceptance-designer-selected-revision-recovery{suffix}-input.json"
    )


def _recovery_facts(root: Path, value: int, finding: str) -> dict[str, object]:
    """Measure the exact stale selection and current design a recovery may read."""
    stored = stored_handover(root)
    if stored is None or not hasattr(stored, "raw"):
        raise ValueError("handover unavailable")
    if value < 1 or value > len(stored.values):
        raise ValueError(f"value {value} is outside the stored Request")
    selected = stored.values[value - 1]
    if not isinstance(selected.authority, DesignFacts):
        raise ValueError(f"value {value} has no complete bound value DESIGN facts")
    if (
        selected.design_semantic_sha256 is not None
        and selected.authority.public_oracle is None
    ):
        raise ValueError(
            "bound value DESIGN facts predate the public-oracle projection; "
            "re-run des design --repo-root ROOT --value N --input - with the bound "
            "manifest (unchanged section bytes: only the handover projection is re-bound, "
            "the selection basis is unchanged), then des prepare-role again"
        )
    if (
        stored.shared_design is not None
        and stored.shared_design.semantic_sha256 is not None
        and stored.shared_design.design.public_oracle is None
    ):
        raise ValueError(
            "bound shared DESIGN facts predate the public-oracle projection; "
            "re-run des design --repo-root ROOT --shared --input - with the bound "
            "manifest (unchanged section bytes: only the handover projection is re-bound, "
            "the selection basis is unchanged), then des prepare-role again"
        )
    if not finding.strip():
        raise ValueError("finding must be non-empty")
    if (
        selected.acceptance is None
        or selected.acceptance_oracle is None
        or selected.acceptance_supports is None
        or selected.acceptance_verification is None
        or selected.acceptance_oracle_verification_index is None
        or selected.acceptance_design_basis_sha256 is None
    ):
        raise ValueError(f"value {value} has no complete selected revision")
    current_basis = design_basis_sha256(stored.shared_design, selected)
    if selected.acceptance_design_basis_sha256 == current_basis:
        raise ValueError(f"value {value} selected revision is already aligned")
    revision = {
        "observation": selected.observation,
        "acceptance_obligations": [
            {"id": item.id, "stimulus": item.stimulus, "expected": item.expected}
            for item in selected.acceptance
        ],
        "oracle": selected.acceptance_oracle,
        "acceptance_supports": list(selected.acceptance_supports),
        "verification": [list(argv) for argv in selected.acceptance_verification],
        "oracle_verification_index": selected.acceptance_oracle_verification_index,
    }
    payload = {
        "schema_version": 1,
        "role": "acceptance-designer",
        "task": "selected-revision-recovery",
        "value": value,
        "request": stored.request,
        "request_digest": hashlib.sha256(stored.raw).hexdigest(),
        "observation": selected.observation,
        "selected_revision": revision,
        "selected_revision_identity": selected_revision_sha256(
            selected.acceptance,
            selected.acceptance_oracle,
            selected.acceptance_supports,
            selected.acceptance_verification,
            selected.acceptance_oracle_verification_index,
        ),
        "selected_design_basis_sha256": selected.acceptance_design_basis_sha256,
        "current_design_basis_sha256": current_basis,
        # Keep both semantic identities explicit as well as inside the basis.
        # A future basis representation must not silently weaken recovery input
        # freshness, and absent legacy identities remain an observable null.
        "value_design_semantic_sha256": selected.design_semantic_sha256,
        "shared_design_semantic_sha256": (
            None
            if stored.shared_design is None
            else stored.shared_design.semantic_sha256
        ),
        # The identities above make later changes stale; these complete facts
        # are the immutable semantic material the acceptance designer may use
        # for this one recovery.  Reuse the handover's canonical wire rather
        # than independently re-encoding DESIGN fields here.
        "current_value_design": _facts_wire(selected.authority),
        "current_shared_design": (
            None if stored.shared_design is None else _shared_wire(stored.shared_design)
        ),
        "finding": finding,
    }
    payload["recovery_binding_sha256"] = _recovery_binding_sha256(payload)
    return payload


def prepare_selected_revision_recovery(
    root: Path, value: int, finding: str
) -> tuple[str, str]:
    """Seal the one caller-selected ATD recovery input, without a model turn.

    The path is content-addressed by the sha256 of the exact sealed bytes --
    the same identity `_write` returns and `des prepare-role` prints as
    INPUT-SHA256 -- so a corrected finding (part of those sealed bytes)
    necessarily seals its own distinct immutable input, while an identical
    finding for an unchanged authority binding reuses the same path.
    """
    payload = _recovery_facts(root, value, finding)
    raw = _sealed(payload, "role_input")
    input_sha256 = hashlib.sha256(raw).hexdigest()
    path = _recovery_path(root, value, input_sha256)
    relative = path.relative_to(root).as_posix()
    try:
        return relative, _write(path, raw)
    except ArtifactConflict as conflict:
        raise RecoveryInputAlreadyPrepared(relative, conflict.digest) from None


def load_selected_revision_recovery(
    root: Path, value: int, path: Path
) -> tuple[Path, dict[str, object], bytes]:
    """Load one sealed input only while its exact authority binding is current."""
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("prepared recovery input is unavailable") from error
    digest = payload.pop("payload_sha256", None)
    if (
        payload.get("kind") != "role_input"
        or payload.get("role") != "acceptance-designer"
        or payload.get("task") != "selected-revision-recovery"
        or payload.get("value") != value
        or not isinstance(digest, str)
        or hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        != digest
    ):
        raise ValueError("prepared recovery input kind, binding, or digest differs")
    finding = payload.get("finding")
    if not isinstance(finding, str):
        raise ValueError("prepared recovery finding is unavailable")
    current = _recovery_facts(root, value, finding)
    bound_payload = {key: item for key, item in payload.items() if key != "kind"}
    if current != bound_payload:
        raise ValueError("prepared recovery input authority binding differs")
    binding_sha256 = payload.get("recovery_binding_sha256")
    if not isinstance(
        binding_sha256, str
    ) or binding_sha256 != _recovery_binding_sha256(
        {
            key: item
            for key, item in payload.items()
            if key not in {"kind", "recovery_binding_sha256"}
        }
    ):
        raise ValueError("prepared recovery input binding identity differs")
    expected = _recovery_path(root, value, hashlib.sha256(raw).hexdigest())
    # Legacy paths sealed before content-identity addressing: bare (very
    # first recovery shape) and binding-only (one input per authority
    # binding, before a corrected finding needed its own distinct input).
    legacy = _recovery_path(root, value)
    legacy_binding_only = _recovery_path(root, value, binding_sha256)
    if path not in {expected, legacy, legacy_binding_only}:
        raise ValueError("prepared recovery input path differs from its binding")
    payload["payload_sha256"] = digest
    return path, payload, raw


def prepare(
    root: Path, role: str, candidate: str, observations: Path | None = None
) -> tuple[str, str]:
    if observations is not None and role != "examiner":
        raise ObservationPacketRefused(
            [
                Defect(
                    "",
                    "role_not_examiner",
                    "observations are accepted only for examiner",
                )
            ]
        )
    runner = DeliveryContinuationRunner()
    stored = _stored_for_candidate(root, candidate, runner)
    if stored is None or not hasattr(stored, "request"):
        raise ValueError("handover unavailable")
    # The selected revision is judged FIRST: an incomplete or misaligned one
    # must name its own recovery, whatever else about the candidate is true.
    prepared = _prepared(runner, root, stored)
    if not isinstance(prepared, list):
        raise SelectedRevisionUnavailable(prepared)
    if not _candidate_is_admitted(
        root, candidate, stored, runner
    ) or not runner.load_native_evidence_identity(root, candidate):
        raise ValueError("candidate has no bound native evidence")
    native_path = root / runner.native_evidence_locator
    native = json.loads(native_path.read_bytes())
    request_digest = hashlib.sha256(stored.raw).hexdigest()
    tree = runner._git(root, "rev-parse", f"{candidate}^{{tree}}")
    if tree.returncode:
        raise ValueError("candidate tree is unavailable")
    common = {
        "schema_version": 1,
        "role": role,
        "request": stored.request,
        "request_digest": request_digest,
        "candidate_sha": candidate,
        "candidate_tree_sha": tree.stdout.strip(),
        "native_evidence_sha256": runner.native_evidence_sha256,
    }
    changed = runner._changed_paths(root, f"{candidate}^", candidate)
    if changed is None:
        raise ValueError("candidate changed paths are unavailable")
    try:
        radius_record = json.loads(
            (root / ".nwave/des/logs/radius" / f"{candidate}.json").read_bytes()
        )
        if not isinstance(radius_record, dict):
            raise ValueError("radius record is not an object")
        seal = radius_record.pop("payload_sha256", None)
        if (
            seal
            != hashlib.sha256(
                json.dumps(radius_record, sort_keys=True).encode()
            ).hexdigest()
        ):
            raise ValueError("radius seal differs")
        if (
            radius_record.get("candidate_sha") != candidate
            or radius_record.get("native_evidence_sha256")
            != runner.native_evidence_sha256
            or not isinstance(radius_record.get("radius"), str)
        ):
            raise ValueError("radius binding differs")
        radius = radius_record["radius"]
    except (OSError, json.JSONDecodeError, ValueError):
        raise ValueError("candidate-bound native radius is unavailable")
    if role == "examiner":
        owned_paths = runner._request_owned_paths(prepared)
        selected_acceptance = _projected_selected_acceptance(prepared, owned_paths)
        public_observations = None
        provenance = None
        if observations is not None:
            public_observations, provenance = read_packet(
                observations,
                candidate,
                tree.stdout.strip(),
                owned_paths,
            )
        projected = _examiner_native_evidence(native)
        payload = {
            **common,
            "outcomes": [value for value, _ in prepared],
            "selected_acceptance": selected_acceptance,
            "native_evidence": projected,
            "radius": WITHHELD,
            "public_observations": public_observations,
            "observations_provenance": provenance,
            "expectation_charters": _candidate_expectation_charters(
                root, stored, tree.stdout.strip(), runner
            ),
        }
    elif role == "reviewer":
        diff = runner._git(
            root,
            "diff",
            "--no-color",
            f"{candidate}^",
            candidate,
            "--",
            ".",
            # DES-written authority documents are inputs, not the role's work.
            *(
                f":(exclude){path}"
                for path in runner._bound_authority_documents(root, stored)
            ),
        ).stdout
        approved = []
        for _, design in prepared:
            for path in design.acceptance_paths:
                observed = runner._git(root, "show", f"{candidate}:{path}")
                if observed.returncode:
                    raise ValueError(f"candidate oracle {path} is unavailable")
                approved.append([path, observed.stdout])
        payload = {
            **common,
            "diff": diff,
            "values": runner._prepared_facts(prepared),
            **runner._shared(stored),
            "owned_paths": runner._request_owned_paths(prepared),
            "approved_oracles": approved,
            "native_evidence": native,
            "radius": radius,
        }
    else:
        raise ValueError("role must be reviewer or examiner")
    raw = _sealed(payload, "role_input")
    if role == "examiner":
        digest = hashlib.sha256(raw).hexdigest()
        path = (
            root / ".nwave/des/logs/roles" / f"{candidate}-{role}-{digest}-input.json"
        )
    else:
        path = root / ".nwave/des/logs/roles" / f"{candidate}-{role}-input.json"
    relative = path.relative_to(root).as_posix()
    try:
        return relative, _write(path, raw)
    except ArtifactConflict as conflict:
        raise RoleInputAlreadyPrepared(relative, conflict.digest) from None


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordedRoleTurn:
    """WHICH role turn a recorded result belongs to, and WHO answered it.

    Keyword-only, and load-bearing: `role`, `candidate`, `provider`, `model` and
    `session` are all strings or None, so a positional permutation records a turn
    against the wrong role, the wrong candidate or an invented model, and nothing
    raises. Nothing in this repository would catch it: `typecheck` covers
    `src/des/` but is executed by no workflow.
    """

    role: str
    candidate: str
    provider: str
    model: str | None
    session: str | None


def record(
    root: Path,
    turn: RecordedRoleTurn,
    raw: bytes,
    prepared_input: Path | None = None,
) -> tuple[str, str, str]:
    role = turn.role
    candidate = turn.candidate
    provider = turn.provider
    model = turn.model
    session = turn.session
    if prepared_input is not None:
        if role != "examiner":
            raise ValueError("--prepared-input applies only to examiner revisions")
        _input_path, prepared, input_raw = load_prepared_at(
            root, role, candidate, prepared_input
        )
    elif role == "examiner":
        try:
            _input_path, prepared, input_raw = load_prepared(root, role, candidate)
        except ValueError as error:
            raise ValueError(
                "no legacy fixed-name examiner input is available; select the "
                "exact revision with --prepared-input PATH, using the INPUT "
                "returned by des prepare-role"
            ) from error
    else:
        _input_path, prepared, input_raw = load_prepared(root, role, candidate)
    structured = json.loads(raw)["structured_output"]
    decode_model_run(
        structured,
        role_id="nw-software-crafter-reviewer"
        if role == "reviewer"
        else "nw-user-examiner",
    )
    outcome = structured["outcome"]
    payload = {
        "schema_version": 1,
        "role": role,
        "candidate_sha": candidate,
        "candidate_tree_sha": prepared.get("candidate_tree_sha"),
        "request_digest": prepared.get("request_digest"),
        "native_evidence_sha256": prepared.get("native_evidence_sha256"),
        "input_sha256": hashlib.sha256(input_raw).hexdigest(),
        "declared_provider": provider,
        "result": structured,
    }
    if model is not None:
        payload["declared_model"] = model
    if session is not None:
        payload["declared_session_id"] = session
    encoded = _sealed(payload, "role_result")
    identity = (
        hashlib.sha256(encoded).hexdigest()
        if role == "examiner"
        else hashlib.sha256((session or "adapter").encode()).hexdigest()
    )
    path = root / ".nwave/des/logs/roles" / f"{candidate}-{role}-{identity}-result.json"
    return outcome, path.relative_to(root).as_posix(), _write(path, encoded)


@dataclass(frozen=True)
class ModelInvocation:
    """The provider, model, and run to record for one completed role invocation."""

    provider: str
    model: str
    run: ModelRun


def record_model(
    root: Path,
    role: str,
    candidate: str,
    invocation: ModelInvocation,
    input_path: Path | None = None,
) -> tuple[str, str, str]:
    """Persist the adapter's typed result without reconstructing an envelope."""
    provider, model, run = invocation.provider, invocation.model, invocation.run
    if input_path is not None:
        _input_path, prepared, input_raw = _load_and_bind(
            root, role, candidate, input_path
        )
    else:
        _input_path, prepared, input_raw = load_prepared(root, role, candidate)
    payload = {
        "schema_version": 1,
        "role": role,
        "candidate_sha": candidate,
        "input_sha256": hashlib.sha256(input_raw).hexdigest(),
        "candidate_tree_sha": prepared.get("candidate_tree_sha"),
        "request_digest": prepared.get("request_digest"),
        "native_evidence_sha256": prepared.get("native_evidence_sha256"),
        "actual_provider": provider,
        "actual_model": model,
        "outcome": run.outcome.value,
        "diagnostic": run.diagnostic,
        "issued": run.issued,
        "exit_status": run.exit_status,
        "retry_safe": run.retry_safe,
    }
    if run.accounting is not None:
        payload["accounting"] = {
            "total_cost_usd": run.accounting.total_cost_usd,
            "num_turns": run.accounting.num_turns,
            "input_tokens": run.accounting.input_tokens,
            "output_tokens": run.accounting.output_tokens,
            "cache_creation_input_tokens": run.accounting.cache_creation_input_tokens,
            "cache_read_input_tokens": run.accounting.cache_read_input_tokens,
            "session_id": run.accounting.session_id,
        }
    if run.review_defect is not None:
        payload["review_defect"] = {
            "owner": run.review_defect.owner.value,
            "value": run.review_defect.value,
        }
    raw = _sealed(payload, "role_result")
    identity = hashlib.sha256(raw).hexdigest()
    path = root / ".nwave/des/logs/roles" / f"{candidate}-{role}-{identity}-result.json"
    return run.outcome.value, path.relative_to(root).as_posix(), _write(path, raw)


def record_selected_revision_recovery(
    root: Path,
    value: int,
    invocation: ModelInvocation,
    input_path: Path,
) -> tuple[str, str, str, str | None, str | None]:
    """Persist one ATD recovery outcome and its accepted document verbatim.

    The document is canonicalized by its domain owner once, written separately
    from result metadata, and never reconstructed by the CLI.  Rejections and
    indeterminate outcomes intentionally have no document path.  ``input_path``
    mirrors :func:`record_model`'s own optional parameter: when the caller
    supplies the exact prepared-input path it already validated, that binding
    is honored rather than silently re-derived.
    """
    provider, model, run = invocation.provider, invocation.model, invocation.run
    _path, prepared, input_raw = load_selected_revision_recovery(
        root, value, input_path
    )
    document_path: Path | None = None
    document_digest: str | None = None
    if run.outcome is ModelOutcome.Accepted:
        if run.distill_document is None:
            raise ValueError(
                "accepted acceptance-designer result has no DISTILL document"
            )
        document_raw = run.distill_document.canonical_json().encode("utf-8")
        document_identity = hashlib.sha256(document_raw).hexdigest()
        document_path = (
            root
            / ".nwave/des/logs/roles"
            / (
                f"value-{value}-acceptance-designer-selected-revision-recovery-"
                f"{document_identity}-document.json"
            )
        )
        document_digest = _write(document_path, document_raw)
    elif run.distill_document is not None:
        raise ValueError(
            "non-accepting acceptance-designer result carried a DISTILL document"
        )
    payload = {
        "schema_version": 1,
        "role": "acceptance-designer",
        "task": "selected-revision-recovery",
        "value": value,
        "request_digest": prepared["request_digest"],
        "input_sha256": hashlib.sha256(input_raw).hexdigest(),
        "actual_provider": provider,
        "actual_model": model,
        "outcome": run.outcome.value,
        "diagnostic": run.diagnostic,
        "issued": run.issued,
        "exit_status": run.exit_status,
        "retry_safe": run.retry_safe,
        "distill_document": (
            None
            if document_path is None
            else {
                "path": document_path.relative_to(root).as_posix(),
                "sha256": document_digest,
            }
        ),
    }
    raw = _sealed(payload, "role_result")
    identity = hashlib.sha256(raw).hexdigest()
    result_path = (
        root
        / ".nwave/des/logs/roles"
        / f"value-{value}-acceptance-designer-selected-revision-recovery-{identity}-result.json"
    )
    result_digest = _write(result_path, raw)
    return (
        run.outcome.value,
        result_path.relative_to(root).as_posix(),
        result_digest,
        None if document_path is None else document_path.relative_to(root).as_posix(),
        document_digest,
    )

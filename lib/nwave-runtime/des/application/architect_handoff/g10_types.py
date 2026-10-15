"""Typed architect handoff grammar: closed, tagged, frozen records.

Representation first (GDP-0): every wrong state that a SHAPE can exclude is excluded here
(closed vocabularies, required fields, non-blank strings, non-empty lists, tagged sums, one record
per atom kind). What a shape cannot express (cross-field, cross-section, against the typed
`targets`) is in g10_rules.py. Each closed vocabulary names the repository text it comes from.
"""

from __future__ import annotations

import dataclasses as dc
import hashlib
import re
import typing as t
from typing import Literal

from des.ports.driven_ports.task_invocation_port import (
    FactRef,  # noqa: TC001 - runtime schema uses get_type_hints
)


# --------------------------------------------------------------------------- vocabularies
# nWave/skills/nw-pbt-fundamentals/SKILL.md:23-32 (the repository's own property taxonomy)
LawKind = Literal[
    "invariant",
    "idempotence",
    "roundtrip",
    "oracle",
    "metamorphic",
    "commutativity",
    "inductive",
    "verify_solution",
]
# hexagonal layers named by the algebraic-design protocol decisions ("ALGEBRA, <layer> layer")
Layer = Literal["domain", "application", "adapter", "infrastructure"]
# nWave/skills/nw-certainty-by-construction/SKILL.md:95-101 (calibration table, 5 rows)
Strength = Literal[
    "proof", "strong_static", "gradual_checker", "centralised", "runtime_boundary"
]
# nWave/skills/nw-design/SKILL.md:403-404 (DESIGN axis, runtime axis)
Design = Literal["PASS", "BLOCKED"]
Runtime = Literal["OBSERVED", "DESIGNED_NOT_BUILT", "INDETERMINATE"]
# nw-solution-architect-formal-verification/SKILL.md:17-23 and nw-design/SKILL.md:463-466: the PROOF of a
# formal claim is its own state. An unexecuted checker leaves only that proof INDETERMINATE; "tool absence
# never blocks DESIGN". A refuted proof is a counterexample: the DESIGN axis is then BLOCKED.
Proof = Literal["passed", "indeterminate", "refuted"]
# E-G10-79: triage of a conditionally true theorem
Cause = Literal["carrier", "law_scope", "boundary"]
Language = Literal["quint", "tla", "agda"]
Tool = Literal[
    "probe",
    "quint_typecheck",
    "quint_run",
    "quint_verify",
    "tlc",
    "apalache",
    "agda",
    "test",
    "code_fact",
    "script",
]
Target = Literal["environment", "model", "prototype", "implementation"]
ResultClass = Literal["ok", "violation", "error", "timeout"]
ArtifactRole = Literal["output", "trace"]
# counterexample: the DESIGN model fails; mutant: a deliberately broken variant fails (what the bug does);
# example: a normal behavior of the model (an ok run, or a witness of reachability)
ScenarioKind = Literal["counterexample", "mutant", "example"]
# nw-po-scenario-exploration/SKILL.md:66-67
Judgment = Literal["correct", "incorrect", "depends", "unclear", "correction"]
Kind = Literal["laws", "construction", "model", "closure", "scenarios"]
KINDS: tuple[str, ...] = t.get_args(Kind)
VERIFIERS = frozenset(
    {"quint_verify", "tlc", "apalache", "agda"}
)  # a passing simulation is not verification
MODEL_TOOLS = frozenset(
    {"quint_run", "quint_verify", "tlc", "apalache"}
)  # tools whose runs can carry traces
SEQUENCE_FIELDS = frozenset({"argv"})  # ordered; every other tuple is a set

# --------------------------------------------------------------------------- string shapes (the type, not a gate)
ID = t.NewType("ID", str)  # citable token
Locator = t.NewType("Locator", str)  # code reference, never prose (E-V2-D-17)
RelPath = t.NewType(
    "RelPath", str
)  # a file kept beside the sidecar; never absolute, never `..`
Sha = t.NewType("Sha", str)  # lowercase sha256 hex
_PATH = r"[\w./@+-]+"
_SYMBOL = r"[\w$#.:<>@-]+"
ID_RE = r"[A-Za-z][A-Za-z0-9_-]{0,63}"
LOCATOR_RE = (
    rf"(?:CREATE_NEW:)?({_PATH})(?::[0-9]+(?:-[0-9]+)?(?::[0-9]+)?|::{_SYMBOL})?"
)
RELPATH_RE = _PATH
SHA_RE = r"[0-9a-f]{64}"
SCOPE_RE = r"shared|value:[1-9][0-9]*"
VARIANT_RE = r"base|fairness|no_fairness|fixed|unfixed|witness|mutant:[A-Za-z][A-Za-z0-9_-]{0,63}"
PATTERNS: dict[str, str] = {
    "ID": ID_RE,
    "FactId": ID_RE,
    "Locator": LOCATOR_RE,
    "RelPath": RELPATH_RE,
    "Sha": SHA_RE,
}


def _safe_path(p: str) -> bool:
    return not p.startswith("/") and ".." not in p.split("/")


def valid(shape: str, v: str) -> bool:
    """A value has the shape when the WHOLE string matches (a trailing newline never does)."""
    m = re.fullmatch(PATTERNS[shape], v)
    if m is None:
        return False
    if shape == "Locator":
        return _safe_path(m.group(1))
    if shape == "RelPath":
        return _safe_path(v)
    return True


def locator_path(loc: str) -> str:
    """The file part of a locator; a string that is not a locator is returned unchanged."""
    m = re.fullmatch(LOCATOR_RE, loc)
    return m.group(1) if m else loc


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode("utf-8"))


def trace_of(run: Run) -> Artifact | None:
    """The kept trace of a run; if a document lists several, the smallest (path, sha256), so that the choice never depends on list order."""
    traces = sorted(
        (a for a in run.artifacts if a.role == "trace"),
        key=lambda a: (a.path, a.sha256),
    )
    return traces[0] if traces else None


def rec(cls):
    return dc.dataclass(frozen=True, kw_only=True)(cls)


def ne(**kw):  # non-empty collection
    return dc.field(metadata={"nonempty": True}, **kw)


def pos(**kw):  # strictly positive integer
    return dc.field(metadata={"positive": True}, **kw)


# --------------------------------------------------------------------------- laws
@rec
class Observation:
    id: ID
    description: FactRef
    result_type: str  # E-G05-56
    cannot_distinguish: FactRef


@rec
class Equality:
    under: tuple[ID, ...] = (
        ne()
    )  # observation ids: x ~ y iff they agree under all of these
    definition: FactRef


@rec
class Constructor:
    id: ID
    signature: str


@rec
class Generator:  # declared once in Laws.generators, cited by id from every broad law that uses it
    id: ID
    domain: FactRef
    size_bound: int = pos()
    seed_policy: FactRef
    must_include: tuple[FactRef, ...] = dc.field(
        metadata={"nonempty": True, "unique_refs": True}
    )
    depth_bound: int | None = None


@rec
class Falsifier:
    description: FactRef


@rec
class Broad:
    generator: ID
    independent_observation: FactRef
    falsifier: Falsifier
    tag: Literal["broad"] = "broad"


@rec
class Finite:
    cases: tuple[FactRef, ...] = dc.field(
        metadata={"nonempty": True, "unique_refs": True}
    )
    reason: FactRef
    tag: Literal["finite"] = "finite"


@rec
class NoTreatment:
    reason: FactRef
    tag: Literal["none"] = "none"


Treatment = Broad | Finite | NoTreatment


@rec
class ToRun:
    tag: Literal["to_run"] = "to_run"


@rec
class Executed:
    receipts: tuple[ID, ...] = ne()
    tag: Literal["executed"] = "executed"


Evidence = ToRun | Executed


@rec
class Law:
    id: ID
    statement: FactRef
    kind: LawKind
    layer: Layer
    owner: Locator
    uses: tuple[ID, ...] = ne()  # observations and constructors the law relates
    treatment: Treatment
    evidence: Evidence


@rec
class RefutedLaw:
    id: ID
    statement: FactRef
    cause: Cause
    counterexample: FactRef
    run: ID | None = None  # E-G08-79: the receipt kept beside the counterexample


@rec
class Laws:
    observations: tuple[Observation, ...] = ne()
    equality: Equality
    constructors: tuple[Constructor, ...] = ne()
    generators: tuple[Generator, ...]  # may be empty: a design with no broad law
    laws: tuple[Law, ...] = ne()
    refuted: tuple[RefutedLaw, ...]


# --------------------------------------------------------------------------- construction
@rec
class Unknown:  # E-V2-E-32: an unknown state always names who carries its risk
    state: FactRef
    risk_owner: FactRef


@rec
class ExclusionClaim:
    id: ID
    proposition: FactRef
    harm: FactRef
    owner: Locator
    admitted_input: FactRef
    constructor: Locator
    consumer: Locator
    public_observation: FactRef
    bypass: tuple[FactRef, ...] = dc.field(metadata={"unique_refs": True})
    strength: Strength


@rec
class Construction:
    claims: tuple[ExclusionClaim, ...] = ne()
    admitted: tuple[FactRef, ...] = dc.field(
        metadata={"nonempty": True, "unique_refs": True}
    )
    excluded: tuple[FactRef, ...] = dc.field(
        metadata={"nonempty": True, "unique_refs": True}
    )
    unknown: tuple[Unknown, ...]  # may be empty: stated, not omitted


# --------------------------------------------------------------------------- model
@rec
class Located:
    at: Locator
    tag: Literal["located"] = "located"


@rec
class ModelOnly:
    reason: FactRef
    tag: Literal["model_only"] = "model_only"


Site = Located | ModelOnly


@rec
class Atomicity:  # E-V2-D-17: the real code mechanism, as a code reference and never prose
    at: Locator
    note: FactRef


@rec
class StateAtom:
    name: str
    symbol: str  # the runtime symbol or expression the atom stands for (nw-design:414)
    site: Site
    tag: Literal["state"] = "state"


@rec
class ActionAtom:  # every model step names its domain sentence and its atomicity mechanism
    name: str
    symbol: str
    site: Site
    template: FactRef
    atomicity: Atomicity
    tag: Literal["action"] = "action"


@rec
class PropertyAtom:
    name: str
    symbol: str
    site: Site
    statement: FactRef
    tag: Literal["property"] = "property"


@rec
class ConstantAtom:
    name: str
    symbol: str
    site: Site
    tag: Literal["constant"] = "constant"


Atom = StateAtom | ActionAtom | PropertyAtom | ConstantAtom


@rec
class Kill:
    property: str
    run: ID


@rec
class Mutant:
    id: ID
    description: FactRef
    kills: tuple[Kill, ...] = ne()


@rec
class ModelSource:
    path: RelPath
    sha256: Sha


@rec
class Model:
    id: ID
    language: Language
    path: Locator
    source: ModelSource
    atoms: tuple[Atom, ...] = ne()
    exclusions: tuple[FactRef, ...] = dc.field(metadata={"unique_refs": True})
    assumptions: tuple[FactRef, ...] = dc.field(metadata={"unique_refs": True})
    mutants: tuple[Mutant, ...]

    @property
    def sha256(self) -> str:
        return self.source.sha256


@rec
class Models:
    models: tuple[Model, ...] = ne()


# --------------------------------------------------------------------------- closure
@rec
class Checked:  # a formal run backs it (rules CL3 and CL4)
    model_id: ID
    properties: tuple[str, ...] = ne()  # names the runs check (Run.checks)
    proof: Proof
    proof_note: FactRef | None = None
    fairness: FactRef | None = None
    tag: Literal["checked"] = "checked"


@rec
class Constructed:  # excluded by construction: ids of ExclusionClaim in the `construction` section
    claims: tuple[ID, ...] = ne()
    tag: Literal["constructed"] = "constructed"


@rec
class Argued:  # prose argument; a PASS on it must state its assumptions (ADR wording: "PASS under ...")
    argument: tuple[FactRef, ...] = ne()
    tag: Literal["argued"] = "argued"


@rec
class Route:  # admitted input -> producer -> consumer -> public observation (nw-certainty-by-construction:49-52)
    admitted_input: FactRef
    producer: Locator
    consumer: Locator
    public_observation: FactRef
    bootstrap: FactRef | None = None
    tag: Literal["path"] = "path"


Basis = Checked | Constructed | Argued | Route


@rec
class Claim:
    statement: FactRef
    design: Design
    design_note: FactRef | None = None
    runtime: Runtime
    runtime_note: FactRef | None = None
    assumptions: tuple[FactRef, ...] = dc.field(metadata={"unique_refs": True})
    runs: tuple[ID, ...]  # evidence receipts
    laws: tuple[ID, ...]  # laws that refine this claim at runtime
    basis: Basis
    tag: Literal["claim"] = "claim"


@rec
class NotApplicableClaim:  # only `liveness` may take it (nw-design:405-406)
    reason: FactRef
    tag: Literal["not_applicable"] = "not_applicable"


@rec
class Inherited:  # only `liveness` at value scope: the claim of the same subject at shared scope applies
    tag: Literal["inherited"] = "inherited"


LivenessEntry = Claim | NotApplicableClaim | Inherited


@rec
class Closure:  # nw-design:399-406: for every public value, exactly these four, each on both axes
    subject: FactRef
    safety: Claim
    inhabitation: Claim
    public_reachability: Claim
    liveness: LivenessEntry


@rec
class ClosureSet:
    closures: tuple[Closure, ...] = ne()


# --------------------------------------------------------------------------- receipts
@rec
class Measure:
    kind: Literal["states", "cases", "samples"]
    value: int = pos()


@rec
class Artifact:  # a file kept beside the sidecar; `trace` = the raw ITF trace (E-G08-18, E-V2-A-70)
    role: ArtifactRole
    path: RelPath
    sha256: Sha


# Shared by the runtime decoder and positional provider-schema projection.
ARGV_DATA_RE = r"^[^\x00\ud800-\udfff]*$"
ARGV_EXECUTABLE_RE = r"^(?=[\s\S]*\S)[^\x00\ud800-\udfff]*$"


@rec
class Run:
    id: ID
    tool: Tool
    tool_version: str  # E-V2-A-70
    target: Target
    model_id: ID | None = None
    model_sha256: Sha | None = (
        None  # the text the run actually used (a stale receipt is not evidence)
    )
    variant: str = dc.field(
        metadata={
            "pattern": VARIANT_RE,
            "display": "base|fairness|no_fairness|fixed|unfixed|witness|mutant:<id>",
        }
    )
    # Executable is nonblank; later literal data arguments may be empty.
    argv: tuple[str, ...] = dc.field(metadata={"nonempty": True, "literal_argv": True})
    exit_status: int
    result_class: ResultClass
    checks: tuple[str, ...]  # property names or law ids this run checks
    measure: Measure | None = None
    seed: str | None = None
    duration_s: float | None = dc.field(default=None, metadata={"nonneg": True})
    artifacts: tuple[
        Artifact, ...
    ] = ()  # empty = authored claim; `g10 run` always keeps the output


@rec
class Receipts:
    runs: tuple[Run, ...] = ne()


# --------------------------------------------------------------------------- scenarios
@rec
class Pending:
    tag: Literal["pending"] = "pending"


@rec
class Judged:
    by: str
    judgment: Judgment
    model_identity: Sha  # sha256 of the model text the human judged (E-G09-06)
    trace_identity: (
        Sha  # sha256 of the trace the human read: the exact scenario (E-G09-06)
    )
    note: FactRef | None = None
    tag: Literal["judged"] = "judged"


Review = Pending | Judged


@rec
class Scenario:  # never authored: the steps are read from the raw trace of `source_run`
    id: ID
    title: FactRef
    source_run: ID
    kind: ScenarioKind
    review: Review


@rec
class Scenarios:
    scenarios: tuple[Scenario, ...] = ne()


# --------------------------------------------------------------------------- sections
@rec
class Applicable:
    payload: t.Any
    tag: Literal["applicable"] = "applicable"


@rec
class NotApplicable:
    reason: FactRef
    tag: Literal["not_applicable"] = "not_applicable"


@rec
class Entry:
    kind: Kind
    scope: str
    status: Applicable | NotApplicable


PAYLOAD: dict[str, type] = {
    "laws": Laws,
    "construction": Construction,
    "model": Models,
    "closure": ClosureSet,
    "scenarios": Scenarios,
}
Handoff = dict  # {(kind, scope): Entry}
REQUIRED_SHARED = (
    "laws",
    "model",
    "closure",
    "scenarios",
)  # construction: projected only

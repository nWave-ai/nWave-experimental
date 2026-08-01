"""The feature-delta read seam -- one reader, three DISTINGUISHED outcomes.

WHY-NEW-FILE: src/des/domain/feature_delta_source.py
  CLOSEST-EXISTING: src/des/adapters/driven/filesystem/feature_delta_filesystem_reader.py
  EXTENSION-COST: that adapter implements the `FeatureDeltaReader` DRIVEN PORT
    whose contract is `str | None` -- the very collapse this module exists to
    undo. Widening it to a discriminated outcome changes an abstract port and
    breaks every in-memory double implementing it tree-wide.
  PARALLEL-RATIONALE: incompatible return contract on a published port
    (`str | None` vs a three-outcome record) plus a different consumer set --
    the port serves `DiscussGateOut.evaluate`, which only needs
    content-or-INDETERMINATE, while a GATE must tell the operator WHICH of
    three causes fired because each one routes to a DIFFERENT action.

Three causes, three operator actions -- and today's readiness gate collapsed
the first two into the second, reporting an ABSENT file as one that "could not
be read as UTF-8 text":

  * ABSENT       -> create it (or the path/tree is wrong); the HOW invokes the
                    PRODUCING TOOL (`des feature-delta-schema inject`,
                    `des feature-delta-doctor`), never advice about encodings.
  * UNDECODABLE  -> re-encode it as UTF-8. Nothing is missing; the bytes are.
  * PRESENT      -> the content is in hand; a failing invariant from here on is
                    a MISSING SECTION, and the action is to write that section.

The path layout `{repo_root}/docs/feature/{feature_id}/feature-delta.md` is the
same DESIGN-PINNED location the driven adapter reads (git-free, stdlib only).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.domain.repo_path_resolver import feature_delta_path


if TYPE_CHECKING:
    from pathlib import Path


#: `ADR-<PREFIX>-<NNN>`-shaped id token, e.g. `ADR-DFR-001` / `adr-flow-006`.
#: Case-insensitive: the repo carries both `ADR-DFR-001-*.md` (upper) and
#: `adr-029-*.md` (lower) casing conventions (Technology Choices row 1).
_ADR_ID_RE = re.compile(r"ADR-[A-Z0-9]+(?:-[A-Z0-9]+)*", re.IGNORECASE)


#: Cause tokens carried on a gate's per-invariant record so a DOWNSTREAM
#: reader (e.g. the hook's refusal formatter) can branch on WHICH of the three
#: states fired instead of re-parsing prose.
FEATURE_DELTA_ABSENT = "feature-delta-absent"
FEATURE_DELTA_UNDECODABLE = "feature-delta-undecodable"
#: The delta WAS read; an invariant then found its own section missing.
FEATURE_DELTA_SECTION_MISSING = "feature-delta-section-missing"


@dataclass(frozen=True)
class FeatureDeltaRead:
    """The outcome of one feature-delta read.

    ``content`` is non-None exactly when the read succeeded; ``cause`` and
    ``detail`` are empty exactly then. The two are never both meaningful --
    a reader that answers "here is the text" and "here is why there is no
    text" at once is the collapse this record exists to prevent.
    """

    path: Path
    content: str | None
    cause: str
    detail: str

    @property
    def is_present(self) -> bool:
        return self.content is not None


@dataclass(frozen=True)
class AdrRefDereference:
    """The outcome of resolving one declared `adr-refs` id token (DD-8, D6).

    Exactly two states: PRESENT (`resolved_path` names the real file) or
    ABSENT (`resolved_path` is None). The 4th-state locus resolver
    (`LOCUS_UNRESOLVED`) is explicitly OUT of scope for this feature
    (feature-delta.md Section 11 row 1, RIDIMENSIONA).
    """

    adr_id: str
    resolved_path: Path | None


def extract_adr_ref_ids(section_body: str) -> tuple[str, ...]:
    """Every `ADR-<PREFIX>-<NNN>`-shaped id token declared in `section_body`,
    first-seen order, de-duplicated. Pure, never raises."""
    seen: dict[str, None] = {}
    for match in _ADR_ID_RE.finditer(section_body):
        seen.setdefault(match.group(0), None)
    return tuple(seen)


def adr_ref_roots(repo_root: Path, feature_id: str) -> tuple[Path, ...]:
    """The declared, closed, ordered ADR root tuple (Technology Choices row 2)."""
    return (
        repo_root / "docs" / "product" / "architecture",
        repo_root / "docs" / "feature" / feature_id / "design" / "adrs",
        repo_root / "docs" / "architecture" / "adrs",
        repo_root / "docs" / "adrs",
    )


def any_adr_ref_root_exists(repo_root: Path) -> bool:
    """Whether `repo_root` holds AT LEAST ONE of the 4 declared ADR root
    directories -- checked WITHOUT a feature_id (the feature-specific root is
    matched via a wildcard over `docs/feature/*/design/adrs`, since a
    feature-agnostic caller -- the doctor's could-not-verify leg (DD-9) -- has
    no single feature in scope). Used to distinguish "the tree itself cannot
    be checked" from "this one id is dangling"; reporting zero gaps when NO
    declared root exists would be a GDP-6 silent-wrong."""
    if (repo_root / "docs" / "product" / "architecture").is_dir():
        return True
    if (repo_root / "docs" / "architecture" / "adrs").is_dir():
        return True
    if (repo_root / "docs" / "adrs").is_dir():
        return True
    feature_dir = repo_root / "docs" / "feature"
    if feature_dir.is_dir():
        for child in feature_dir.iterdir():
            if (child / "design" / "adrs").is_dir():
                return True
    return False


def _resolve_adr_id(adr_id: str, roots: tuple[Path, ...]) -> Path | None:
    """Case-insensitive resolve of one ADR id against the declared roots,
    first-match-wins in root order. `Path.glob` is case-SENSITIVE on Linux,
    so matching is done by lower-casing both sides rather than globbing."""
    needle = f"{adr_id.lower()}-"
    for root in roots:
        try:
            if not root.is_dir():
                continue
            candidates = sorted(root.iterdir())
        except OSError:
            continue
        for candidate in candidates:
            if candidate.is_file() and candidate.name.lower().startswith(needle):
                return candidate
    return None


def dereference_adr_refs(
    section_body: str, *, repo_root: Path, feature_id: str
) -> tuple[AdrRefDereference, ...]:
    """Resolve every declared `adr-refs` id token in `section_body` against
    the declared, closed, ordered ADR root tuple (DD-8, D6).

    Pure, read-only, never raises -- a malformed token simply never matches
    the id pattern and is not extracted at all. Matching is case-insensitive
    on the id prefix against the 4 declared roots.
    """
    roots = adr_ref_roots(repo_root, feature_id)
    return tuple(
        AdrRefDereference(adr_id=adr_id, resolved_path=_resolve_adr_id(adr_id, roots))
        for adr_id in extract_adr_ref_ids(section_body)
    )


# --- D76: internal `per <ID>` decision-citation resolution -----------------
#
# D33 closed the ADR-refs half of "a citation resolves to something real, or
# is named dangling, never silence" (dereference_adr_refs, above). Its own
# closure note declared the residue verbatim: "Nessun controllo che una
# citazione interna <<per DD-N>> risolva a una riga esistente -- solo il
# caso ADR-refs e' presidiato." This section closes the rest of the SAME
# defect class -- any `<PREFIX>-<N>` decision id (DD-N is the convention
# `nw-design` SKILL.md names; empirically the shipped corpus also carries
# D-N, DDD-N, AC-N, and others, all authored the same way: a table row /
# heading / checklist item DECLARES the id, other prose CITES it via
# `per <ID>`) -- never a second, differently-shaped checker for the ADR
# family, which stays entirely out of scope here.

#: One `<PREFIX>-<N>` id token, e.g. `DD-3`, `D-12`, `DDD-8`, `AC-5`,
#: `AC-5.b` (a lettered sub-item). 1-4 letters, 1-3 digits, optional
#: `.<suffix>`.
_DECISION_ID_TOKEN = r"[A-Za-z]{1,4}-[0-9]{1,3}(?:\.[a-z0-9]+)?"

#: A CITATION: `per <ID>`, optionally backticked/bolded. This is the exact
#: citation form the residue names ("per DD-N") and the convention teaches
#: ("cites it (`per DD-N`)", `nw-design` SKILL.md Decision-once).
_DECISION_CITE_RE = re.compile(
    rf"\bper\s+`?\*{{0,2}}({_DECISION_ID_TOKEN})\*{{0,2}}`?", re.IGNORECASE
)

#: A DECLARATION: the id token OPENS a table row, a heading, or a checklist
#: item -- i.e. it is being DEFINED, not merely mentioned in running prose.
#: A bare in-paragraph mention (`... per DD-2 earlier ...`) never matches
#: this -- only `_DECISION_CITE_RE` reads prose mentions, deliberately, so
#: a citation can never satisfy itself by being its own "declaration".
_DECISION_DECL_RE = re.compile(
    r"^(?:\|\s*|[-*]\s*(?:\[[ xX]\]\s*)?|#{2,4}\s*)"
    rf"\*{{0,2}}({_DECISION_ID_TOKEN})\*{{0,2}}"
    r"\s*(?:[|:]|—|--|-\s|$)"
)

#: The ADR family already has its own dedicated, wired checker
#: (`dereference_adr_refs` / `feature_delta_doctor._dangling_adr_ref_gaps`,
#: D33/D6) -- excluded here so this module never duplicates it a second,
#: differently-shaped way.
_ADR_FAMILY = "ADR"

#: The GDP family is a closed, external, repo-wide enumeration (CLAUDE.md
#: Gate Design Principles; canonical clause `nw-cross-cutting-invariants`
#: SKILL.md `gate:design-principles-gdp-1-8`) -- fixed at GDP-1..GDP-8,
#: never per-document.
_GDP_CLOSED_SET = frozenset(f"GDP-{n}" for n in range(1, 9))

#: The AD family (`ARCH_TECH_DEBT.md` items) is a repo-global registry
#: declared in exactly ONE file, not per-feature-delta.
_ARCH_TECH_DEBT_RELPATH = "ARCH_TECH_DEBT.md"

_DECISION_STATE_RESOLVED_LOCAL = "resolved-local"
_DECISION_STATE_RESOLVED_EXTERNAL = "resolved-external"
_DECISION_STATE_DANGLING = "dangling"
_DECISION_STATE_COULD_NOT_VERIFY = "could-not-verify"


@dataclass(frozen=True)
class DecisionCitation:
    """One `per <ID>` decision citation found in a document.

    ``context`` is the whole source line, for self-explaining gap reporting.
    """

    id: str
    line: int
    context: str


@dataclass(frozen=True)
class DecisionCitationResolution:
    """The outcome of resolving one `DecisionCitation` -- one of the four
    states above. ``detail`` names WHERE resolution was attempted (or why it
    could not be), for the gap-rendering layer to build WHAT/WHY/HOW from
    without re-deriving it."""

    citation: DecisionCitation
    state: str
    detail: str


def extract_decision_declarations(document_text: str) -> frozenset[str]:
    """Every decision id DECLARED (table row / heading / checklist item) in
    `document_text`, upper-cased, first-seen order collapsed to a set. Pure,
    never raises."""
    declared: set[str] = set()
    for line in document_text.splitlines():
        match = _DECISION_DECL_RE.match(line)
        if match:
            declared.add(match.group(1).upper())
    return frozenset(declared)


def extract_decision_citations(document_text: str) -> tuple[DecisionCitation, ...]:
    """Every `per <ID>` citation in `document_text`, in document order.

    The ADR family is excluded at extraction time (not resolution time) --
    it is out of this module's scope entirely, not merely "always resolved".
    Pure, never raises."""
    citations: list[DecisionCitation] = []
    for lineno, line in enumerate(document_text.splitlines(), start=1):
        for match in _DECISION_CITE_RE.finditer(line):
            cid = match.group(1).upper()
            family = re.match(r"[A-Za-z]+", cid)
            if family is not None and family.group(0).upper() == _ADR_FAMILY:
                continue
            citations.append(
                DecisionCitation(id=cid, line=lineno, context=line.strip())
            )
    return tuple(citations)


def _decision_family(decision_id: str) -> str:
    match = re.match(r"[A-Za-z]+", decision_id)
    return match.group(0).upper() if match is not None else ""


def _load_arch_tech_debt_ids(repo_root: Path) -> frozenset[str] | None:
    """The AD-N ids declared in `ARCH_TECH_DEBT.md`, or None when that file
    is absent/unreadable at `repo_root` (the could-not-verify leg)."""
    path = repo_root / _ARCH_TECH_DEBT_RELPATH
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return extract_decision_declarations(text)


def resolve_decision_citations(
    document_text: str, *, repo_root: Path | None
) -> tuple[DecisionCitationResolution, ...]:
    """Resolve every non-ADR `per <ID>` citation in `document_text` to one of
    the four states (module section docstring above).

    Pure, read-only, never raises. `repo_root` is used ONLY to resolve the
    AD-N external registry (`ARCH_TECH_DEBT.md`); every other family
    resolves against `document_text` alone or the closed GDP-1..8 set.
    """
    local_ids = extract_decision_declarations(document_text)
    citations = extract_decision_citations(document_text)
    if not citations:
        return ()

    arch_tech_debt_ids: frozenset[str] | None = None
    arch_tech_debt_loaded = False

    results: list[DecisionCitationResolution] = []
    for citation in citations:
        base_id = citation.id.split(".")[0]
        if citation.id in local_ids or base_id in local_ids:
            results.append(
                DecisionCitationResolution(
                    citation=citation,
                    state=_DECISION_STATE_RESOLVED_LOCAL,
                    detail=f"declared in this same document as `{citation.id}`",
                )
            )
            continue

        family = _decision_family(citation.id)

        if family == "GDP":
            if base_id in _GDP_CLOSED_SET:
                results.append(
                    DecisionCitationResolution(
                        citation=citation,
                        state=_DECISION_STATE_RESOLVED_EXTERNAL,
                        detail="member of the closed GDP-1..GDP-8 enumeration",
                    )
                )
            else:
                results.append(
                    DecisionCitationResolution(
                        citation=citation,
                        state=_DECISION_STATE_DANGLING,
                        detail="not a member of the closed GDP-1..GDP-8 enumeration",
                    )
                )
            continue

        if family == "AD":
            if not arch_tech_debt_loaded:
                arch_tech_debt_ids = (
                    _load_arch_tech_debt_ids(repo_root)
                    if repo_root is not None
                    else None
                )
                arch_tech_debt_loaded = True
            if arch_tech_debt_ids is None:
                results.append(
                    DecisionCitationResolution(
                        citation=citation,
                        state=_DECISION_STATE_COULD_NOT_VERIFY,
                        detail=(
                            f"{_ARCH_TECH_DEBT_RELPATH} is absent or unreadable "
                            f"at repo_root={repo_root}"
                        ),
                    )
                )
            elif base_id in arch_tech_debt_ids:
                results.append(
                    DecisionCitationResolution(
                        citation=citation,
                        state=_DECISION_STATE_RESOLVED_EXTERNAL,
                        detail=f"declared in {_ARCH_TECH_DEBT_RELPATH}",
                    )
                )
            else:
                results.append(
                    DecisionCitationResolution(
                        citation=citation,
                        state=_DECISION_STATE_DANGLING,
                        detail=f"not declared in {_ARCH_TECH_DEBT_RELPATH}",
                    )
                )
            continue

        results.append(
            DecisionCitationResolution(
                citation=citation,
                state=_DECISION_STATE_DANGLING,
                detail="not declared in this document, and its prefix names no known external registry",
            )
        )

    return tuple(results)


def _absent_detail(path: Path, repo_root: Path) -> str:
    return (
        f"what: no feature-delta.md exists at {path} / "
        f"why: the file is ABSENT (this is not an encoding problem -- nothing "
        f"was there to decode); the tree this gate read is {repo_root} / "
        f"how: if that tree is the wrong one, re-dispatch declaring the right "
        f"project root (`des dispatch --repo-root <project-root>`, which stamps "
        f"the DES-PROJECT-ROOT marker the gate resolves against). If the tree is "
        f"right, GENERATE the document, do not retype it: `des "
        f"feature-delta-schema inject --wave <wave>` emits the canonical "
        f"headings, then `des feature-delta-doctor {path}` names every remaining "
        f"structural gap in one pass"
    )


def _undecodable_detail(path: Path) -> str:
    return (
        f"what: the feature-delta at {path} EXISTS but its bytes are not valid "
        f"UTF-8 / why: an encoding fault -- no section is missing, the file "
        f"cannot be decoded at all / how: re-encode the file as UTF-8 (e.g. "
        f"`iconv -f <source-encoding> -t UTF-8`) and re-run this gate; do NOT "
        f"regenerate the document, its content is not in question"
    )


def read_feature_delta(repo_root: Path, feature_id: str) -> FeatureDeltaRead:
    """Read the feature-delta, distinguishing ABSENT from UNDECODABLE.

    Never raises: an unreadable artefact degrades LOUD into a record naming the
    cause + the remediation for THAT cause, so a gate can refuse with an
    actionable WHAT/WHY/HOW instead of a single mis-attributing sentence.
    """
    path = feature_delta_path(repo_root, feature_id)
    if not path.is_file():
        return FeatureDeltaRead(
            path=path,
            content=None,
            cause=FEATURE_DELTA_ABSENT,
            detail=_absent_detail(path, repo_root),
        )
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return FeatureDeltaRead(
            path=path,
            content=None,
            cause=FEATURE_DELTA_UNDECODABLE,
            detail=_undecodable_detail(path),
        )
    except OSError as exc:
        # Present-but-unopenable (permissions, a broken symlink target, an I/O
        # error). Neither "absent" nor "bad encoding" -- say what actually
        # happened rather than borrowing one of the other two causes.
        return FeatureDeltaRead(
            path=path,
            content=None,
            cause=FEATURE_DELTA_UNDECODABLE,
            detail=(
                f"what: the feature-delta at {path} exists but could not be "
                f"opened ({exc.strerror or exc}) / why: a filesystem-level read "
                f"error, not a missing document and not an encoding fault / "
                f"how: fix the file's permissions or the broken link at that "
                f"path, then re-run this gate"
            ),
        )
    return FeatureDeltaRead(path=path, content=content, cause="", detail="")

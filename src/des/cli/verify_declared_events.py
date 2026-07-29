"""des verify-declared-events -- prose claims a ledger/event exists; does code emit it?

Charter: docs/mikado/codex-parity-and-performance-delivery.mikado.md
         (the "declared-vs-emitted" defect class, F-DECLARED-VS-EMITTED).

Recurring defect class this gate closes: shipped prose (a skill, an agent
spec, a command definition, CLAUDE.md, or a permanent ADR) names an event or
ledger record as if the system produces it -- present tense, no caveat -- and
NO code path actually writes it. The reader designs on top of a name that
does not exist. Confirmed instances found by manual audit before this gate
existed: ``FeatureEnd`` (CLAUDE.md's own DONE-definition names a ledger
record with zero producers), ``FeatureEndCycleComplete`` /
``FeatureEndCycleRefused`` / ``FeatureEndCycleIndeterminate`` (a design doc
assumed these were ledger events; `des feature-end`'s `_emit()` only prints
them to stdout -- see ``src/des/cli/feature_end.py``, never a ledger write),
``FeatureEndCheckpoint`` (four shipped skill/task files describe it as a
firing resume-signal; the SAME repo's own
``docs/feature/des-next-loop-projection/feature-delta.md`` admits it was
"never implemented"), and ``DocumentationDensityEvent`` (eleven citation
sites across seven skill files claim "every expansion choice emits" one;
``DocumentationDensityEvent(`` has zero constructor call sites anywhere in
``src/des``).

GDP-8 (decide on the PROPERTY, never the DESIGNATION): this gate does not
trust a name's presence in the codebase in general -- it verifies the
specific property "this string is passed to a real ledger/audit WRITE call",
mechanically, by regex over ``src/des/**/*.py`` (GDP-7: filesystem + regex
only, no import, so an arbitrary ``--repo-root`` never executes untrusted
code). The claim side is symmetric: a PascalCase name in backticks, ending in
a suffix this codebase's own event vocabulary already uses (``Event``,
``Verified``, ``Verdict``, ... -- see ``_EVENT_SUFFIX_RE``), inside a window
that also carries a production-claiming trigger word ("emit(s)", "writes",
"records", "ledger event", ...) is a CLAIM. A claim whose window ALSO carries
an explicit non-claim marker ("not yet", "DESIGNED-NOT-BUILT", "e.g.", ...)
is self-exempt -- the author already told the reader this name is aspirational
or illustrative, which is the opposite of this defect class. A claim neither
self-exempt nor matched by a producer is either a real gap (fix the prose or
build the producer) or a mechanical false positive (register it in
``nWave/data/declared-event-exemptions.json`` with a reason -- reviewable,
never silent).

KNOWN BLIND SPOT (documented per GDP-6, never silently): some producer names
are f-string TEMPLATES, not literal strings -- e.g. ``WaveReviewSpec.event``
is ``f"{self.wave_camel}ReviewVerdict"``. This gate resolves exactly that one
templated family (every ``WaveReviewSpec(wave="...")`` instantiation
mechanically yields ``"<Wave>ReviewVerdict"``, so a fourth wave is covered
automatically) because it is the one confirmed to appear in shipped prose
claims (``DiscussReviewVerdict`` / ``DesignReviewVerdict`` /
``DevopsReviewVerdict``). Other dynamic families in the tree
(``WorkExhaustedWindow*``, ``PipelineStage{Started,Completed,Failed}``,
``health.gate.*``) are NOT resolved -- none of them are currently claimed in
shipped prose, so leaving them unresolved cannot cause a false PASS; it can
only ever cause a false FAIL requiring a reviewed exemption entry, the safe
failure direction (never silent-wrong).

Filesystem + regex only (GDP-7 agnostic), stdlib-only (no ``import yaml`` /
``import re2`` -- see ``verify_catalog_coherence.py`` for the same DES-bundle
constraint this module inherits). Degrades LOUD (GDP-6), never a silent pass,
on two surfaces: no Python source under ``<repo_root>/src/des`` (not an
nWave-dev checkout), or no shipped prose corpus found at all (same cause).
Both raise ``DeclaredEventsInputUnavailableError``, rendered as an
INDETERMINATE verdict with a non-zero exit -- never treated as "zero claims,
PASS".
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from des.cli._repo_root_arg import add_repo_root_argument
from des.domain.gate_outcome import _EXIT_BY_VERDICT, GateVerdict


class DeclaredEventsInputUnavailableError(Exception):
    """An input this gate needs is missing -- ``--repo-root`` is not an
    nWave-dev checkout (no ``src/des`` Python source, or no shipped prose
    corpus at all). Rendered as INDETERMINATE, never a silent PASS."""


# --- producer side: what does the code actually write? ---------------------

_PRODUCER_ROOT = "src/des"

# `_EVENT = "Foo"`, `EBATCH_REFACTOR_COMPLETED = "EBatchRefactorCompleted"` --
# a module/class-level constant assigned a string literal. Deliberately NOT
# narrowed to identifiers containing "EVENT": the real vocabulary hub
# (`at_completion_ledger.py`) names most of its ~40 constants after the
# record family instead (`EBATCH_REFACTOR_COMPLETED`, `SLICE_COMMIT_VERIFIED`,
# `FULL_SUITE_LEG_RAN`, ...), so an EVENT-only filter missed the majority of
# real producers on first calibration against the live corpus. Over-broad on
# purpose (GDP-6 bias: a stray non-event string constant here can only ever
# soften a real defect into a required exemption, never mask one, because the
# claim side independently requires a suffix from the event vocabulary).
_CONST_ASSIGN_RE = re.compile(
    r'^[ \t]*[A-Za-z_][A-Za-z0-9_]*\s*(?::\s*[\w\[\], ]+\s*)?=\s*"([A-Za-z][\w.\-]*)"',
    re.MULTILINE,
)
# `.append_gate_event("Foo", ...)`, `_emit_carpaccio_gate_event("Bar", ...)` --
# a literal event name passed as the first positional argument to an
# append/emit-named call. Deliberately does NOT match a dict/brace literal
# as the first argument (`_emit({"event": "Foo", ...})`) -- that shape is
# `feature_end.py`'s `_emit()`, which only `print()`s a JSON line to CLI
# stdout, never a ledger write (the exact FeatureEndCycleComplete /
# FeatureEndCycleRefused / FeatureEndCycleIndeterminate confirmed defect this
# gate exists to catch -- a blanket `"event": "X"` dict-literal scan would
# have silently absorbed these as "producers" and missed the very case that
# motivated this gate).
_CALL_LITERAL_RE = re.compile(r'\w*(?:append|emit)\w*\(\s*"([^"]+)"')
# `event="Foo"` -- literal keyword argument (e.g. a ledger-write call site
# built with `event=` instead of a positional arg).
_KWARG_EVENT_RE = re.compile(r'\bevent\s*=\s*"([^"]+)"')
# `WaveReviewSpec(wave="discuss", ...)` -- the one resolved template family
# (module docstring KNOWN BLIND SPOT paragraph).
_WAVE_REVIEW_SPEC_RE = re.compile(r'WaveReviewSpec\(\s*\n?\s*wave="([a-z]+)"')
# `"event": "Foo"` -- dict-literal payload shape. Real, but NOT ledger-tier
# evidence on its own: this is also the exact shape of a CLI-stdout-only
# `_emit()`/`print(json.dumps(...))` payload (`feature_end.py`'s
# `FeatureEndCycleComplete`/`Refused`/`Indeterminate`), so a name found ONLY
# here is a real code-emitted string but not proof of a DURABLE (ledger)
# write. Feeds the BROAD tier only (see `ProducerNames` below); a claim whose
# own prose invokes "ledger" must clear the STRICT tier instead.
_DICT_LITERAL_EVENT_RE = re.compile(r'"event"\s*:\s*"([^"]+)"')


@dataclass(frozen=True)
class ProducerNames:
    """Two tiers of producer evidence, mirroring the two claim strengths a
    prose asset can make (module docstring: durability, GDP-8 property not
    designation).

    ``strict`` -- this string is passed to a durable ledger/audit WRITE
    (a named constant in the vocabulary hub, a literal arg to an
    append/emit-named call, an `event=` kwarg, or the resolved
    `WaveReviewSpec` template). A claim whose own text invokes "ledger"
    (durability) must be found here.

    ``broad`` -- ``strict`` PLUS any name found in a bare `"event": "X"`
    dict literal -- a real code-emitted string, but not proof of durability
    (it may be CLI-stdout-only, like `feature_end.py`'s `_emit()`). A claim
    that does NOT invoke "ledger" -- e.g. a bare "the gate records `Foo`" --
    only needs to clear this weaker bar: the name corresponds to SOMETHING
    the code actually does, not nothing."""

    strict: frozenset[str]
    broad: frozenset[str]


def extract_producer_names(python_source: str) -> ProducerNames:
    """Every event/record name this ONE source file's text plausibly writes,
    split into the ``strict`` (durable) / ``broad`` (any real emission)
    tiers.

    Pure function, no filesystem -- callers pass the already-read text so
    this stays independently testable against a fixture string."""
    strict: set[str] = set(_CONST_ASSIGN_RE.findall(python_source))
    strict.update(_CALL_LITERAL_RE.findall(python_source))
    strict.update(_KWARG_EVENT_RE.findall(python_source))
    for wave in _WAVE_REVIEW_SPEC_RE.findall(python_source):
        strict.add(f"{wave.capitalize()}ReviewVerdict")
    broad = strict | set(_DICT_LITERAL_EVENT_RE.findall(python_source))
    return ProducerNames(strict=frozenset(strict), broad=frozenset(broad))


def _iter_python_files(repo_root: Path) -> list[Path]:
    base = repo_root / _PRODUCER_ROOT
    if not base.is_dir():
        return []
    return sorted(base.rglob("*.py"))


def compute_producer_registry(repo_root: Path) -> ProducerNames:
    """Every event/record name mechanically found across ``src/des``.

    Raises ``DeclaredEventsInputUnavailableError`` when no Python source is
    found at all -- the common case being ``repo_root`` is not an nWave-dev
    checkout."""
    py_files = _iter_python_files(repo_root)
    if not py_files:
        raise DeclaredEventsInputUnavailableError(
            f"no Python source found under {repo_root / _PRODUCER_ROOT} -- "
            "this repo_root does not look like an nWave-dev checkout"
        )
    strict: set[str] = set()
    broad: set[str] = set()
    for path in py_files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        names = extract_producer_names(text)
        strict.update(names.strict)
        broad.update(names.broad)
    return ProducerNames(strict=frozenset(strict), broad=frozenset(broad))


# --- claim side: what does shipped prose say the code writes? --------------

_PROSE_DIR_ROOTS = ("nWave/skills", "nWave/agents", "nWave/tasks/nw")
_PROSE_SINGLE_FILES = ("CLAUDE.md",)
_ADR_ROOT = "docs/product/architecture"

# The event-name vocabulary this codebase actually uses, as a required
# SUFFIX -- narrows backtick-quoted PascalCase matches to plausible
# event/record names instead of firing on every capitalized code identifier
# (`Read`, `Write`, tool names, class names, ...) mentioned near a trigger
# word. A name with no suffix from this list, like the confirmed ``FeatureEnd``
# case, is NOT caught by this heuristic -- documented gap, see the module
# docstring; the fix for that one instance is the prose correction, not a
# broader (and much noisier) heuristic.
_EVENT_SUFFIX = (
    "Event|Verified|Completed|Complete|Refused|Recorded|Pending|Attested|"
    "Signed|Drained|Escalated|Projected|Checkpoint|Indeterminate|Cleared|"
    "Rejected|Bypassed|Blocked|Sealed|Observed|Verdict|NotApplicable"
)
_CLAIM_NAME_RE = re.compile(rf"`([A-Z][a-zA-Z]*(?:{_EVENT_SUFFIX}))`")
_TRIGGER_RE = re.compile(
    r"\b(emit|emits|emitted|writes?|written|records?|recorded|appends?|"
    r"appended|ledger record|ledger event)\b",
    re.IGNORECASE,
)
_SELF_EXEMPT_RE = re.compile(
    r"\b(not yet|not built|never implemented|not implemented|"
    r"designed-not-built|not emitted|no producer|no emitter|zero producer|"
    r"no ledger record|hypothetical|illustrative|does not build|"
    r"doesn't build)\b|e\.g\.|for example",
    re.IGNORECASE,
)
# A claim that invokes "ledger" is claiming DURABILITY -- a name a reader can
# expect to read BACK later (`des next`, a done-gate, a resume cue). That
# claim must clear the STRICT producer tier; a bare "the gate records `Foo`"
# with no "ledger" only needs the weaker BROAD tier (module docstring,
# `ProducerNames`).
_DURABILITY_RE = re.compile(r"\bledger\b", re.IGNORECASE)

_WINDOW_RADIUS_CHARS = 160


@dataclass(frozen=True)
class Claim:
    """One (name, location) a prose asset claims is produced.

    ``context`` -- the tight character-radius window used to decide whether
    this is a claim at all (trigger-word proximity, see ``extract_claims``).
    ``full_line`` -- the WHOLE source line, used only for the self-exempt
    check: an author fixing a claim by appending a "NOT YET WIRED" caveat at
    the END of an already-long paragraph-per-line ADR sentence should not
    have to hand-place the caveat within an arbitrary character radius of the
    backtick name to be believed. Self-exemption only ever turns a FAIL into
    a visible, reported EXEMPT (never a silent pass), so this broader search
    is one-directional-safe in a way widening the TRIGGER search was not
    (that caused the GateVerdict false-positive this module's docstring
    describes)."""

    name: str
    file: str
    line: int
    context: str
    full_line: str


@dataclass(frozen=True)
class Exemption:
    file: str
    name: str
    reason: str


def extract_claims(markdown_source: str, file_label: str) -> tuple[Claim, ...]:
    """Every claimed event/record name in ONE prose asset's text.

    A backtick-quoted, suffix-matching PascalCase name counts as a claim only
    when a production-claiming trigger word appears within a character
    radius of the SAME line (not the whole line, not neighboring lines): ADR
    prose in this repo ships one paragraph per line, so a whole-line or
    cross-line window degrades to "same paragraph", which false-positived on
    TYPE names (e.g. `GateVerdict`, `FullSuiteLegIndeterminate` -- Python
    dataclasses discussed in an architecture paragraph that also happens to
    mention "ledger append" somewhere else in the same paragraph, never
    claiming those specific names are themselves ledger-written strings) on
    first calibration against the live corpus. Pure function, no filesystem,
    independently testable against a fixture string."""
    claims: list[Claim] = []
    for lineno, line in enumerate(markdown_source.splitlines(), start=1):
        for match in _CLAIM_NAME_RE.finditer(line):
            start = max(0, match.start() - _WINDOW_RADIUS_CHARS)
            end = min(len(line), match.end() + _WINDOW_RADIUS_CHARS)
            local = line[start:end]
            if not _TRIGGER_RE.search(local):
                continue
            claims.append(
                Claim(
                    name=match.group(1),
                    file=file_label,
                    line=lineno,
                    context=local.strip(),
                    full_line=line,
                )
            )
    return tuple(claims)


def _is_self_exempt(claim: Claim) -> bool:
    return bool(_SELF_EXEMPT_RE.search(claim.full_line))


def _iter_prose_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for root in _PROSE_DIR_ROOTS:
        base = repo_root / root
        if base.is_dir():
            files.extend(sorted(base.rglob("*.md")))
    for name in _PROSE_SINGLE_FILES:
        single = repo_root / name
        if single.is_file():
            files.append(single)
    adr_base = repo_root / _ADR_ROOT
    if adr_base.is_dir():
        files.extend(sorted(adr_base.glob("*.md")))
    return files


_DEFAULT_EXEMPTIONS_RELPATH = ("nWave", "data", "declared-event-exemptions.json")


def _load_exemptions(repo_root: Path) -> tuple[Exemption, ...]:
    path = repo_root.joinpath(*_DEFAULT_EXEMPTIONS_RELPATH)
    if not path.is_file():
        return ()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    return tuple(
        Exemption(file=e["file"], name=e["name"], reason=e["reason"])
        for e in raw.get("exemptions", ())
    )


def _is_registered_exempt(claim: Claim, exemptions: tuple[Exemption, ...]) -> bool:
    return any(e.file == claim.file and e.name in (claim.name, "*") for e in exemptions)


@dataclass(frozen=True)
class DeclaredEventsResult:
    """The closed comparison: every claim, split into matched / self-exempt /
    registered-exempt / undeclared (the defect this gate exists to catch)."""

    producers: ProducerNames
    claims: tuple[Claim, ...]
    undeclared: tuple[Claim, ...]
    exempted: tuple[Claim, ...]

    @property
    def clean(self) -> bool:
        return not self.undeclared


def compute_declared_events(repo_root: Path) -> DeclaredEventsResult:
    """Scan the producer + prose corpora under ``repo_root``; classify every
    claim. Raises ``DeclaredEventsInputUnavailableError`` when either corpus
    is entirely absent (repo_root is not an nWave-dev checkout)."""
    producers = compute_producer_registry(repo_root)
    prose_files = _iter_prose_files(repo_root)
    if not prose_files:
        raise DeclaredEventsInputUnavailableError(
            "no shipped prose corpus found under nWave/skills, nWave/agents, "
            "nWave/tasks/nw, CLAUDE.md, or docs/product/architecture -- this "
            "repo_root does not look like an nWave-dev checkout"
        )
    exemptions = _load_exemptions(repo_root)

    all_claims: list[Claim] = []
    undeclared: list[Claim] = []
    exempted: list[Claim] = []
    for path in prose_files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        label = str(path.relative_to(repo_root)).replace("\\", "/")
        for claim in extract_claims(text, label):
            all_claims.append(claim)
            required = (
                producers.strict
                if _DURABILITY_RE.search(claim.context)
                else producers.broad
            )
            if claim.name in required:
                continue
            if _is_self_exempt(claim) or _is_registered_exempt(claim, exemptions):
                exempted.append(claim)
                continue
            undeclared.append(claim)

    return DeclaredEventsResult(
        producers=producers,
        claims=tuple(all_claims),
        undeclared=tuple(undeclared),
        exempted=tuple(exempted),
    )


def _render_how(claim: Claim) -> str:
    return (
        f"{claim.file}:{claim.line} claims `{claim.name}` is produced, but no "
        f"write call in src/des passes that literal string to a ledger/audit "
        f"write. WHY: a reader designs on top of a name that does not exist. "
        f"HOW: either (1) build the missing producer and wire it to a real "
        f"ledger/audit write, (2) correct the prose to the real event name "
        f"that already carries this claim's intent, (3) add an explicit "
        f"caveat in the same sentence ('not yet built' / 'DESIGNED-NOT-BUILT') "
        f"if this is a stated future intent, or (4) if this is a mechanical "
        f"false positive (a pedagogical example unrelated to the DES ledger), "
        f"register it in nWave/data/declared-event-exemptions.json with a "
        f"reason."
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des verify-declared-events",
        description=(
            "Every event/record name shipped prose claims is produced must "
            "have a real write call in src/des, or an explicit caveat, or a "
            "reviewed exemption."
        ),
    )
    add_repo_root_argument(
        parser,
        "--repo-root",
        type=str,
        default=".",
        help="Repo root holding src/des and the shipped prose corpus (default: cwd).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()

    try:
        result = compute_declared_events(repo_root)
    except DeclaredEventsInputUnavailableError as exc:
        how = (
            "point --repo-root at a real nWave-dev checkout (it must hold "
            "src/des/**/*.py and at least one of nWave/skills, nWave/agents, "
            "nWave/tasks/nw, CLAUDE.md, or docs/product/architecture)."
        )
        print(f"verify-declared-events: {exc} -- {how}", file=sys.stderr)
        verdict = {
            "event": "DeclaredEventsChecked",
            "verdict": GateVerdict.INDETERMINATE.value,
            "reason": str(exc),
            "how": [how],
            "undeclared": [],
        }
        print(json.dumps(verdict))
        return _EXIT_BY_VERDICT[GateVerdict.INDETERMINATE]

    if result.clean:
        verdict = {
            "event": "DeclaredEventsChecked",
            "verdict": GateVerdict.PASS.value,
            "reason": (
                f"{len(result.claims)} claim(s) checked against "
                f"{len(result.producers.broad)} known producer(s) "
                f"({len(result.producers.strict)} ledger-tier): 0 undeclared "
                f"({len(result.exempted)} exempt)."
            ),
            "how": [],
            "undeclared": [],
        }
        print(json.dumps(verdict))
        return _EXIT_BY_VERDICT[GateVerdict.PASS]

    verdict = {
        "event": "DeclaredEventsChecked",
        "verdict": GateVerdict.FAIL.value,
        "reason": (
            f"{len(result.undeclared)} claimed event(s) with no matching "
            "producer and no exemption."
        ),
        "how": [_render_how(c) for c in result.undeclared],
        "undeclared": [
            {"name": c.name, "file": c.file, "line": c.line} for c in result.undeclared
        ],
    }
    print(json.dumps(verdict))
    return _EXIT_BY_VERDICT[GateVerdict.FAIL]


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

"""Execute one declared agreement: build ONE artifact, hand it to EVERY consumer.

THE CROSSING EXECUTES BOTH PARTIES. No verdict here is ever derived from reading
source, an import graph or a syntax tree. The artifact exists ONLY because the
declared producer really ran and really wrote it, and acceptance IS the declared
consumer's own process exit code -- with its stderr tail carried verbatim as
what it rejects. That is the whole difference between an executable agreement
and a claim about one.

WHY A FILE AND NOT A PIPE. The artifact crosses through a CHECKER-OWNED,
run-scoped file path substituted for the literal ``{artifact}`` token in BOTH
argvs. Measured reason, not preference: this repository's real producer
``des verify-test-runner`` writes 80 bytes of RUNNER output to stdout
(``.  [100%]`` -- not JSON) while writing a clean ``nwave.test_result.v1``
artifact to its ``--out`` path. A stdout-to-stdin pipe would therefore corrupt
the artifact with the runner's own chatter. The file path also keeps the crossing
independent of either party's language: the token is substituted into an argv,
and argv is what every toolchain already has.

THE PRODUCER RUNS EXACTLY ONCE PER CROSSING and the SAME artifact bytes reach
every declared consumer, so the crossing reports ONE ``artifact_bytes`` and ONE
``artifact_sha256`` for the whole run. Measured reason, not economy: re-running
the producer per consumer would let two consumers see different bytes under a
single verdict, which would make the claim "every declared consumer was reached
by the producer's artifact" unverifiable rather than merely redundant.

NO SHORT-CIRCUIT. Every declared consumer is reached, in declaration order, EVEN
AFTER one refuses, and the outcome reports EVERY declared consumer with its own
exit code and its own substituted argv. Stopping at the first refusal would
leave the remaining consumers unmeasured while reporting a complete run, and an
operator who fixed the named consumer would meet the next disagreement only on
the following run.

THREE VERDICTS, AND INDETERMINATE IS NEVER GREEN:

* ``AgreementCrossed`` (0) -- every declared consumer was REACHED and every one
  of them exited 0. Names the contract, the producer, the producer argv ACTUALLY
  EXECUTED, the artifact's length and sha256, and the full ``consumers`` array,
  so a crossing that carried nothing cannot report a green.
* ``AgreementRefused`` (1) -- every declared consumer was reached and at least
  one exited non-zero. The payload carries the full ``consumers`` array PLUS a
  ``refused`` array naming WHICH consumers refused, each with its exit code and
  the verbatim reject reason it wrote (stderr tail, falling back to stdout tail).
  The human line names the same consumer and the same reason, so the two halves
  of the terminal cannot disagree.
* ``AgreementIndeterminate`` (2) -- nothing decisive was learnt: an unreadable or
  invalid declaration, a producer that failed, an artifact absent or empty after
  the producer exited, a declared executable that is absent, or a fired
  wall-clock bound.

PRECEDENCE, STATED RATHER THAN LEFT TO WHICHEVER BRANCH RUNS FIRST. If ANY
declared consumer could not be REACHED AT ALL -- its declared executable is
absent, or its wall-clock bound fired -- the whole outcome is INDETERMINATE even
when another consumer really refused. The sentence "every declared consumer was
reached" is then false, and a red that implied a complete traversal would be a
lie. The payload still carries every per-consumer result actually observed, and
the reason names the unreached consumer and why.

EVERY VERDICT NAMES THE RUNTIME THAT PRODUCED IT. Each party's ``argv[0]`` is
RESOLVED to an absolute executable BEFORE the spawn and is then EXECUTED BY THAT
RESOLVED PATH, so the reported ``runtime`` is the program that really ran by
CONSTRUCTION rather than a re-derivation that can drift from it. ``runtime`` and
``argv[0]`` are ONE derived value projected twice, so the terminal cannot carry
two disagreeing claims about what executed; ``runtime`` exists so the claim is
readable without positional knowledge of argv.

A RUNTIME IS NEVER A LANGUAGE NAME. The outcome reports the executable, and
never maps it to "python" or "shell": inferring a language from a path is exactly
the single-language reading this checker exists to refuse, and a wrong inference
would declare verified a population nobody looked at. ``consumer_runtimes`` --
sorted and de-duplicated -- summarises the CONSUMER verdicts ONLY, because the
population claim is about who CONSUMED the contract; folding the producer's own
runtime in would make a single-runtime consumer population read as two. The
producer reports its runtime on its own line, so the producer side is equally
language-free.

AN UNRESOLVABLE ``argv[0]`` IS NEVER GREEN. Resolution failure is reported
exactly as an absent executable already is: the producer makes the crossing
INDETERMINATE, and a consumer becomes UNREACHED, which the precedence above turns
into an indeterminate outcome even when another consumer really refused.

LOUD UNVERIFIED CENSUS: EVERY DECLARED CONSUMER IS ACCOUNTED FOR IN ONE TERMINAL.
Each terminal carries ``declared_consumers``, ``verified_consumers`` and an
``unverified`` census -- one entry per structural fact the checker NEEDED and
could not resolve, naming the ``subject`` (a declared party's name, or
``declaration`` / ``artifact`` / ``repository-root``), the ``fact`` it needed to
know, and the verbatim ``detail``. The invariant of EVERY verdict is
``verified_consumers + (consumer entries in the census) == declared_consumers``:
a population nobody ever counted is exactly how a partial list passes for a
complete one. The human half names the same counts and the same misses, so the
two halves cannot drift.

THE GREEN IS ONE STRUCTURAL GATE, not an emergent property of whichever branch
runs first: exit 0 REQUIRES an empty census AND
``verified_consumers == declared_consumers`` AND nobody refused. That is what
makes "no missed verification can be green" checkable ON THE GREEN ITSELF.

``cross_agreement`` IS TOTAL. Every escape -- an unreadable artifact, a party
whose output cannot be decoded, any other unforeseen fault -- becomes an
``AgreementIndeterminate`` terminal naming the subject whose structural fact
could not be resolved. A contained fault is INDETERMINATE (2) and NEVER REFUSED
(1): exit 1 is the colour of a declared consumer that really ran and really said
no, and lending it to a crash would record a verdict the checker never reached.

A PARTY'S OUTPUT IS CAPTURED AS BYTES AND DECODED HERE WITH ``errors="replace"``.
Measured reason, not taste: ``text=True`` decodes STRICTLY inside subprocess, so
a declared consumer writing latin-1 on stderr would destroy the whole run before
any verdict existed -- making the promise to reach parties whose language the
checker shares nothing with false for every party not emitting UTF-8. Acceptance
IS the exit code, which no decoding choice can touch, so a party whose output
merely decoded lossily was genuinely VERIFIED and does not enter the census; the
U+FFFD characters carried into the reported reason are their own visible marker.

EVERY TERMINAL STATES THE POPULATION IT SPEAKS FOR. Green, red and indeterminate
alike carry a closed ``scope`` object -- ``declaration``, ``contract``,
``measured``, ``out_of_reach`` and ``widen_by`` -- and the human half states the
same limit behind the fixed, greppable lead-in ``SPEAKS ONLY FOR``. It is on the
GREEN above all: a limit that only appeared when something went wrong could not
qualify the verdict an operator actually trusts, and the green is the one that
would otherwise read as a claim about the CONTRACT rather than about a LIST.
There is no flag and no opt-in: an operator who has to ASK for the limit of a
measurement reads a universal claim by default.

``scope`` IS DERIVED FROM THE RUN, never a constant banner: the declaration path
the operator passed VERBATIM, the declared contract (or the literal ``UNKNOWN``),
and a ``measured`` clause naming the COUNT, the CONTRACT and the FILE that
decided the population. A scope whose bytes do not change between a one- and a
three-consumer declaration is indistinguishable from boilerplate nobody reads.

``out_of_reach`` STATES THE BOUNDARY BY ENUMERATING ITS INSIDE. ``rule`` is the
predicate itself, so a machine reader can APPLY the boundary instead of parsing
prose; ``in_reach`` is the DECLARED consumer names in declaration order and
nothing else; ``count`` is the literal string ``UNKNOWN`` and is NEVER a number
and never ``0``. Absence of a count is what forbids reading the field as "nobody
else consumes this" -- a claim strictly stronger than an executable crossing can
ever make.

``widen_by`` TURNS A STATED LIMIT INTO AN ACT: the action, the file to edit (the
SAME path ``scope.declaration`` names, because that file is the only thing that
decides the population) and the exact argv that re-runs THIS crossing. A boundary
an operator cannot widen is a disclaimer rather than an instruction.

THE BOUNDARY IS DECLARED, NEVER MEASURED BY READING THE TREE. No scan for other
readers of the contract, not now and not later: a source scan is exactly the
single-language reading this checker refuses, and a scan that found nothing would
read as "nobody else consumes this". THE UNDECLARED POPULATION IS ALSO NEVER
FOLDED INTO THE COUNTS -- ``declared_consumers``, ``verified_consumers`` and
``unverified`` keep exactly their meaning, because the census lists structural
facts the checker NEEDED and could not resolve while an undeclared party is one
it was never asked about. The boundary is a QUALIFIER stated beside the counts,
not a term inside them.

COVERING UNDECLARED CONSUMERS IS OUT OF SCOPE BY CONSTRUCTION, not a later value:
the crossing can only execute parties somebody declared, so the honest move is to
say so on every terminal rather than promise a future that would require the
source reading this checker refuses.
"""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from des.domain.agreement_declaration import (
    AgreementDeclaration,
    InvalidDeclaration,
    declaration_from_bytes,
    substitute_artifact,
)
from des.runtime.spawn import (
    SpawnTimeout,
    classify_spawn_refusal,
    resolve_executable,
    spawn,
)


CROSSED = "AgreementCrossed"
REFUSED = "AgreementRefused"
INDETERMINATE = "AgreementIndeterminate"

AGREEMENT_TIMEOUT_ENV = "NWAVE_AGREEMENT_TIMEOUT"
"""Operator-facing override quoted in the HOW of a fired crossing bound."""

_BOUND_SECONDS = 900.0
"""Wall-clock ceiling for ONE declared party. Generous but explicit: a real
producer may run a test suite, while a party still running after fifteen minutes
is stuck rather than working. Every child gets this bound -- an omitted bound is
how a checker hangs a gate forever instead of reporting an indeterminate."""

_TAIL_CHARACTERS = 2000
"""How much of a party's stderr is carried verbatim into the terminal."""

UNKNOWN = "UNKNOWN"
"""The literal stated where a fact is genuinely not known.

Used for ``scope.contract`` when no declaration could be read, and for
``scope.out_of_reach.count`` ALWAYS. It is a string and never a number: ``0``
would assert that nobody else reads the contract, which is strictly stronger than
anything an executable crossing can establish."""

OUT_OF_REACH_RULE = (
    "a reader of this contract whose name is not listed in in_reach was NOT "
    "executed by this run"
)
"""The PREDICATE itself, so a machine reader can APPLY the boundary rather than
parse prose about it."""

WIDEN_ACTION = (
    "declare that reader as a consumer in this declaration and re-run the crossing"
)
"""The act that WIDENS the boundary. A boundary an operator cannot widen is a
disclaimer rather than an instruction."""

BOUNDARY_LEAD_IN = "SPEAKS ONLY FOR"
"""The FIXED lead-in of the human half's boundary clause, so an examiner who sees
no source can grep the stated limit off any terminal."""


@dataclass(frozen=True)
class _Execution:
    """One party that REALLY RAN: the program, the vector, and what it returned.

    ``runtime`` and ``argv[0]`` are the SAME resolved value -- the vector is
    built from the runtime, not beside it -- so the two can never be reported as
    two disagreeing facts about what executed.
    """

    runtime: str
    argv: tuple[str, ...]
    completed: subprocess.CompletedProcess[bytes]


@dataclass(frozen=True)
class CrossingOutcome:
    """One terminal: its process exit code, its machine line and its human line."""

    exit_code: int
    payload: dict[str, object]
    human: str


@dataclass(frozen=True, kw_only=True)
class _CrossingScope:
    """The population ONE terminal speaks for, carried as a single value.

    ``repo_root`` is the root AS THE OPERATOR GAVE IT, because
    ``scope.widen_by.rerun`` must be a command they can paste back; ``declaration``
    is the path they named; and ``declared`` is the DECLARATION ITSELF rather than
    a bare count, which is what keeps "the contract is known while the population
    is UNKNOWN" -- and its reverse -- unrepresentable rather than merely avoided by
    each branch remembering. ``declared`` has no default and may be ``None``: a
    terminal reached BEFORE any declaration was read genuinely does not know what
    it was asked to measure, and says exactly that.

    Keyword-only because ``repo_root`` and ``declaration`` are both ``str``:
    nothing checks annotations at runtime here, so a positional transposition
    would quietly report the declaration path as the repository root on every
    terminal, and both fields reach the operator verbatim.
    """

    repo_root: str
    declaration: str
    declared: AgreementDeclaration | None


@dataclass(frozen=True, kw_only=True)
class _CrossingCensus:
    """What ONE terminal verified, and every structural fact it could not.

    The invariant of every verdict -- ``verified_consumers`` plus the consumer
    entries in ``unverified`` equals ``declared_consumers`` -- is a statement
    about these two together, which is why they travel as one value.
    ``unverified`` carries no default: an indeterminate whose machine surface
    named nothing it could not verify is exactly the silence the census exists to
    end, and a default would let a new branch reintroduce it.

    ``verified_consumers`` carries no default EITHER, and the incident that a
    default would license is specific: a new ``_terminal`` branch omitting it emits
    ``VERIFIED 0 of N declared consumer(s)`` on a verdict that DID verify some,
    understating its own result with every assertion still passing. The
    EIGHT indeterminate constructions state ``verified_consumers=0`` outright, which is
    the fact each of them means rather than a value inherited from a declaration.

    Keyword-only so every construction names which half it is giving.
    """

    unverified: list[dict[str, str]]
    verified_consumers: int


def cross_agreement(repo_root: Path, declaration_path: str) -> CrossingOutcome:
    """Execute the agreement declared at ``declaration_path`` under ``repo_root``.

    Returns a terminal rather than raising: every world -- accepted, refused and
    "nothing was learnt" -- is a reportable outcome, and a traceback would turn
    the third into an unreadable second class of failure. THAT PROMISE IS TOTAL:
    any unforeseen fault is caught here, at the APPLICATION boundary that owns
    it, so every caller -- the CLI and the in-process drivers alike -- inherits
    it rather than each having to re-implement a catch of its own.
    """
    # The repository root AS THE OPERATOR GAVE IT, because `scope.widen_by.rerun`
    # must be a command the operator can paste back -- not a resolution of it.
    given_root = str(repo_root)
    try:
        return _cross_agreement(repo_root, declaration_path)
    except Exception as escaped:  # broad on purpose -- totality is the promise here
        return _indeterminate(
            f"the crossing could not be carried to a verdict: {escaped!r}",
            census=_CrossingCensus(
                unverified=[
                    _census_entry(
                        "declaration",
                        "whether the declared agreement could be executed to a verdict",
                        f"{type(escaped).__name__}: {escaped}",
                    )
                ],
                # STATED LIMIT: the one site where this zero is not a fact.  Every
                # other `verified_consumers=0` has run no consumer yet, so zero is
                # what happened.  Here the count is UNREACHABLE -- `reached` died
                # with the unwound frame -- so a fault raised after some consumers
                # accepted would report 0 and understate them.  Left as 0 because
                # carrying a partial count out means widening a totality catch to
                # hold state, in the one branch whose verdict is "nothing learnt".
                verified_consumers=0,
            ),
            scope=_CrossingScope(
                repo_root=given_root, declaration=declaration_path, declared=None
            ),
        )


def _cross_agreement(repo_root: Path, declaration_path: str) -> CrossingOutcome:
    given_root = str(repo_root)
    # Every terminal below this point is reached BEFORE a declaration was read,
    # so all three speak for the same honestly unknown population.
    unread = _CrossingScope(
        repo_root=given_root, declaration=declaration_path, declared=None
    )
    root = Path(repo_root).resolve()
    if not root.is_dir():
        return _indeterminate(
            f"the repository root is not a directory: {root}",
            census=_CrossingCensus(
                unverified=[
                    _census_entry(
                        "repository-root",
                        "whether the repository root is a directory",
                        f"{root} is not a directory",
                    )
                ],
                verified_consumers=0,
            ),
            scope=unread,
        )

    declaration_file = root / declaration_path
    try:
        raw = declaration_file.read_bytes()
    except OSError as unreadable:
        return _indeterminate(
            f"the declaration could not be read: {unreadable}",
            census=_CrossingCensus(
                unverified=[
                    _census_entry(
                        "declaration",
                        "whether the declaration could be read",
                        str(unreadable),
                    )
                ],
                verified_consumers=0,
            ),
            scope=unread,
        )

    try:
        declared = declaration_from_bytes(raw)
    except InvalidDeclaration as invalid:
        return _indeterminate(
            f"the declaration is invalid: {invalid}",
            census=_CrossingCensus(
                unverified=[
                    _census_entry(
                        "declaration",
                        "whether the declaration names an executable agreement",
                        str(invalid),
                    )
                ],
                verified_consumers=0,
            ),
            scope=unread,
        )

    # Run-scoped and CHECKER-OWNED: neither party chooses where the artifact
    # lands, so neither can hand the other a stale file from a previous run.
    with tempfile.TemporaryDirectory(prefix="nwave-agreement-") as scratch:
        artifact = Path(scratch) / "artifact"
        return _cross(
            declared,
            root=root,
            artifact=artifact,
            given_root=given_root,
            declaration_path=declaration_path,
        )


def _cross(
    declared: AgreementDeclaration,
    *,
    root: Path,
    artifact: Path,
    given_root: str,
    declaration_path: str,
) -> CrossingOutcome:
    # The declared population is known from here on, so every terminal below can
    # count itself against it rather than reporting whoever happened to be reached.
    # It travels as the DECLARATION ITSELF rather than as a bare count, so a
    # terminal cannot know how many parties it speaks for without knowing WHO.
    total_declared = len(declared.consumers)
    scope = _CrossingScope(
        repo_root=given_root, declaration=declaration_path, declared=declared
    )

    declared_producer_argv = substitute_artifact(declared.producer.argv, str(artifact))
    produced = _execute(declared_producer_argv, root)
    if isinstance(produced, str):
        return _indeterminate(
            f"the declared producer could not run: {produced}",
            scope=scope,
            census=_CrossingCensus(
                unverified=[
                    _census_entry(
                        declared.producer.name,
                        "whether the declared producer could be run at all",
                        produced,
                    ),
                    *_unbuilt_consumers(declared, "the producer never ran"),
                ],
                verified_consumers=0,
            ),
        )
    producer_argv = produced.argv
    if produced.completed.returncode != 0:
        return _indeterminate(
            f"the declared producer {declared.producer.name!r} exited "
            f"{produced.completed.returncode}; nothing can be concluded about the "
            f"agreement. stderr tail: {_tail(produced.completed.stderr)}",
            scope=scope,
            census=_CrossingCensus(
                unverified=[
                    _census_entry(
                        declared.producer.name,
                        "whether the declared producer could build the artifact",
                        f"exited {produced.completed.returncode}. stderr tail: "
                        f"{_tail(produced.completed.stderr)}",
                    ),
                    *_unbuilt_consumers(declared, "no artifact was ever built"),
                ],
                verified_consumers=0,
            ),
        )

    if not artifact.is_file():
        return _indeterminate(
            f"the declared producer {declared.producer.name!r} exited 0 but wrote "
            f"no artifact at the substituted path",
            scope=scope,
            census=_CrossingCensus(
                unverified=[
                    _census_entry(
                        "artifact",
                        "whether the producer wrote an artifact at the substituted path",
                        f"{declared.producer.name} exited 0 but no regular file exists "
                        f"at the substituted path",
                    ),
                    *_unbuilt_consumers(declared, "no artifact was ever built"),
                ],
                verified_consumers=0,
            ),
        )
    payload_bytes = artifact.read_bytes()
    if not payload_bytes:
        return _indeterminate(
            f"the declared producer {declared.producer.name!r} exited 0 but the "
            f"artifact is empty; an empty artifact crosses nothing",
            scope=scope,
            census=_CrossingCensus(
                unverified=[
                    _census_entry(
                        "artifact",
                        "whether the artifact carries any bytes to cross",
                        f"{declared.producer.name} exited 0 but the artifact is empty",
                    ),
                    *_unbuilt_consumers(declared, "the artifact was empty"),
                ],
                verified_consumers=0,
            ),
        )
    digest = hashlib.sha256(payload_bytes).hexdigest()

    # EVERY declared consumer is reached from the ONE artifact just produced,
    # in declaration order, WITHOUT short-circuiting on a refusal. `unreached`
    # records parties the checker could not even start, because those decide the
    # verdict's precedence below.
    reached: list[dict[str, object]] = []
    refused: list[dict[str, object]] = []
    unreached: list[str] = []
    unverified: list[dict[str, str]] = []

    for consumer in declared.consumers:
        consumed = _execute(substitute_artifact(consumer.argv, str(artifact)), root)
        if isinstance(consumed, str):
            unreached.append(
                f"the declared consumer {consumer.name!r} could not be reached: "
                f"{consumed}"
            )
            unverified.append(
                _census_entry(
                    consumer.name,
                    "whether the declared consumer accepts the artifact",
                    consumed,
                )
            )
            continue

        reached.append(
            {
                "name": consumer.name,
                "runtime": consumed.runtime,
                "argv": list(consumed.argv),
                "exit_code": consumed.completed.returncode,
            }
        )
        if consumed.completed.returncode != 0:
            refused.append(
                {
                    "name": consumer.name,
                    "exit_code": consumed.completed.returncode,
                    "reject_reason": (
                        _tail(consumed.completed.stderr)
                        or _tail(consumed.completed.stdout)
                    ),
                }
            )

    # THE CONSUMER VERDICTS ONLY, sorted and de-duplicated. The population claim
    # this value carries is about who CONSUMED the contract, so the producer's
    # own runtime stays on the producer line: folding it in would inflate a
    # genuinely single-runtime consumer population into a false two.
    consumer_runtimes = sorted({str(entry["runtime"]) for entry in reached})

    producer_line = {
        "name": declared.producer.name,
        "runtime": produced.runtime,
        "argv": list(producer_argv),
    }
    common: dict[str, object] = {
        "contract": declared.contract,
        "producer": producer_line,
        "consumers": reached,
        "consumer_runtimes": consumer_runtimes,
        "artifact_bytes": len(payload_bytes),
        "artifact_sha256": digest,
    }

    # THE GATE, STATED ONCE AND STRUCTURALLY. A green is permitted ONLY when the
    # census is empty AND every declared consumer was verified AND nobody
    # refused. Stating it here -- rather than letting it emerge from whichever
    # branch happens to run first -- is what makes "no missed verification can be
    # green" checkable on the green itself.
    if unverified or len(reached) != total_declared:
        # PRECEDENCE: a consumer that was never reached makes "every declared
        # consumer was reached" false, so neither a green nor a red may be
        # claimed -- even when another consumer really did refuse.
        return _indeterminate(
            f"{declared.contract}: not every declared consumer could be reached, "
            f"so nothing can be concluded about the agreement. " + "; ".join(unreached),
            observed=common,
            census=_CrossingCensus(
                unverified=unverified, verified_consumers=len(reached)
            ),
            scope=scope,
        )

    if refused:
        named = ", ".join(
            f"{entry['name']} (exit {entry['exit_code']}): {entry['reject_reason']}"
            for entry in refused
        )
        return _terminal(
            exit_code=1,
            payload={"verdict": REFUSED, **common, "refused": refused},
            human=(
                f"{declared.contract}: {len(reached)} declared consumer(s) were "
                f"reached by the {len(payload_bytes)} bytes (sha256 {digest}) "
                f"built by {declared.producer.name}, and "
                f"{len(refused)} REFUSED them -- {named}. "
                + _runtime_clause(consumer_runtimes)
            ),
            census=_CrossingCensus(
                unverified=unverified, verified_consumers=len(reached)
            ),
            scope=scope,
        )

    return _terminal(
        exit_code=0,
        payload={"verdict": CROSSED, **common},
        human=(
            f"{declared.contract}: {declared.producer.name} built "
            f"{len(payload_bytes)} bytes (sha256 {digest}) and all "
            f"{len(reached)} declared consumer(s) ACCEPTED them: "
            + ", ".join(str(entry["name"]) for entry in reached)
            + ". "
            + _runtime_clause(consumer_runtimes)
        ),
        census=_CrossingCensus(unverified=unverified, verified_consumers=len(reached)),
        scope=scope,
    )


def _census_entry(subject: str, fact: str, detail: str) -> dict[str, str]:
    """One structural fact the checker NEEDED and could not resolve.

    ``subject`` names WHO or WHAT went unverified, ``fact`` names WHAT the
    checker needed to know about it, and ``detail`` carries the verbatim
    evidence. No field may be empty: an entry naming nothing would leave the
    operator exactly where a prose-only reason already leaves them.
    """
    return {
        "subject": subject.strip() or "unnamed subject",
        "fact": " ".join(fact.split()) or "an unnamed structural fact",
        "detail": " ".join(detail.split()) or "(no detail was captured)",
    }


def _unbuilt_consumers(
    declared: AgreementDeclaration, why: str
) -> list[dict[str, str]]:
    """Every declared consumer, unverified, because the crossing never reached them.

    Without these entries a terminal that failed BEFORE the traversal would
    report a declared population it silently never looked at -- the precise way a
    partial list passes for a complete one. The invariant
    ``verified + consumer entries == declared`` holds in these worlds too, with
    ``verified`` honestly zero.
    """
    return [
        _census_entry(
            consumer.name,
            "whether the declared consumer accepts the artifact",
            f"the consumer was never reached: {why}",
        )
        for consumer in declared.consumers
    ]


def _scope(
    *, repo_root: str, declaration: str, declared: AgreementDeclaration | None
) -> dict[str, object]:
    """The CLOSED statement of the population this run speaks for.

    Everything here is derived from THIS run -- the operator's own declaration
    path, the declared contract and the declared names -- so the object cannot
    degenerate into a constant banner that reads the same whatever was measured.
    Nothing here reads the tree: the boundary is DECLARED, and a scan that found
    no other reader would license the far stronger claim "nobody else consumes
    this contract".
    """
    in_reach = [] if declared is None else [party.name for party in declared.consumers]
    contract = UNKNOWN if declared is None else declared.contract
    measured = (
        f"{UNKNOWN}: the declared population could not be read from {declaration}"
        if declared is None
        else f"{len(in_reach)} declared consumer(s) of {contract}, "
        f"listed in {declaration}"
    )
    return {
        "declaration": declaration,
        "contract": contract,
        "measured": measured,
        "out_of_reach": {
            "rule": OUT_OF_REACH_RULE,
            "in_reach": in_reach,
            # NEVER a number, and `0` least of all -- see UNKNOWN above.
            "count": UNKNOWN,
        },
        "widen_by": {
            "action": WIDEN_ACTION,
            # The SAME path scope.declaration names: one file decides the
            # population, so a second path here could only disagree with it.
            "edit": declaration,
            "rerun": [
                "des",
                "verify-agreement",
                "--repo-root",
                repo_root,
                "--declaration",
                declaration,
            ],
        },
    }


def _boundary_clause(*, declaration: str, declared: AgreementDeclaration | None) -> str:
    """The human half's statement of the SAME limit the machine half carries.

    Two forms and no more, both behind the fixed ``SPEAKS ONLY FOR`` lead-in so
    the limit is greppable off any terminal by an examiner who sees no source.
    The second form exists so this projection never has to render a count or a
    contract name it does not have: inventing either to fill the sentence is the
    fabrication this checker exists to prevent.
    """
    if declared is None:
        return (
            f"{BOUNDARY_LEAD_IN} the consumer(s) declared in {declaration}, and that "
            f"population is {UNKNOWN} because the declaration could not be read; "
            f"this run executed no reader of any contract and counts none in any "
            f"field of this outcome."
        )
    return (
        f"{BOUNDARY_LEAD_IN} {len(declared.consumers)} consumer(s) declared in "
        f"{declaration}; any other reader of {declared.contract} was NOT executed "
        f"and is counted in no field of this outcome."
    )


def _terminal(
    *,
    exit_code: int,
    payload: dict[str, object],
    human: str,
    census: _CrossingCensus,
    scope: _CrossingScope,
) -> CrossingOutcome:
    """Project ONE terminal whose two halves account for the same population.

    The census fields AND the boundary are on EVERY verdict, green included -- a
    census or a limit that only appeared when something went wrong could not be
    the thing a green is gated on, nor qualify the verdict an operator actually
    trusts. The human half states the same counts, names the same misses and
    states the same limit, so the two halves cannot drift, and it is collapsed to
    a SINGLE line because the machine half is the one single-line JSON object on
    stdout: a captured tail containing a newline and a brace must never read as a
    second outcome.

    ``scope`` is REQUIRED and carries the DECLARATION ITSELF rather than a bare
    count, which makes "the contract is known while the population is UNKNOWN" --
    and its reverse -- unrepresentable rather than merely avoided by each branch
    remembering. Required rather than defaulted, exactly as the census is: a
    default would let a new branch emit a terminal with no boundary on it.
    """
    declared = scope.declared
    declared_consumers = 0 if declared is None else len(declared.consumers)
    verified_consumers = census.verified_consumers
    clauses = [
        human,
        f"VERIFIED {verified_consumers} of {declared_consumers} declared consumer(s).",
        _boundary_clause(declaration=scope.declaration, declared=declared),
    ]
    clauses.extend(
        f"COULD NOT VERIFY: {entry['subject']} -- {entry['fact']}: {entry['detail']}"
        for entry in census.unverified
    )
    return CrossingOutcome(
        exit_code=exit_code,
        payload={
            **payload,
            "declared_consumers": declared_consumers,
            "verified_consumers": verified_consumers,
            "unverified": list(census.unverified),
            "scope": _scope(
                repo_root=scope.repo_root,
                declaration=scope.declaration,
                declared=declared,
            ),
        },
        human=" ".join(" ".join(clause.split()) for clause in clauses),
    )


def _runtime_clause(consumer_runtimes: list[str]) -> str:
    """What the consumer verdicts REST ON, stated in the green and the red alike.

    The human half of the terminal states the same count and NAMES the same
    programs as ``consumer_runtimes`` on the machine half, so the two cannot
    drift into disagreeing about which real executables spoke -- the same
    discipline the contract, the refuser and the reject reason already hold. It
    is stated on a refusal too: a red whose breadth were invisible would leave an
    operator unable to tell a narrow population from a broad one.
    """
    named = ", ".join(consumer_runtimes)
    return (
        f"Those consumer verdicts rest on {len(consumer_runtimes)} distinct "
        f"runtime(s): {named}."
    )


def _execute(argv: tuple[str, ...], root: Path) -> _Execution | str:
    """Run one declared party, or DESCRIBE why it could not be run.

    ``argv[0]`` is RESOLVED FIRST and the party is then executed BY THE RESOLVED
    ABSOLUTE PATH, so the ``runtime`` reported for its verdict is the program
    that really ran rather than a second lookup that could answer differently.
    Resolution never follows symlinks, so a multi-call binary that dispatches on
    ``argv[0]`` still runs the program the declaration names. No shell is
    interposed, so the crossing stays independent of any party's language.
    ``stdin`` is ``DEVNULL`` and ``cwd`` is the resolved repository root, so a
    party can neither inherit the checker's stdin nor depend on where the
    operator happened to stand.

    A party that resolves to nothing is reported exactly as an absent executable
    is -- as a DESCRIPTION rather than a runtime nobody can vouch for -- because
    naming a runtime that never ran is the fabrication this checker exists to
    prevent.
    """
    runtime = resolve_executable(argv[0], cwd=root)
    if runtime is None:
        return (
            f"ExecutableAbsent: the declared executable {argv[0]!r} resolves to "
            f"no executable program on PATH or under {root}"
        )
    executed = (runtime, *argv[1:])
    try:
        completed = spawn(
            list(executed),
            cwd=str(root),
            stdin=subprocess.DEVNULL,
            # BYTES, NOT TEXT. `text=True` decodes STRICTLY inside subprocess,
            # so a party emitting anything but UTF-8 would kill the run before a
            # verdict existed. The crossing decodes in `_tail` with
            # errors="replace" instead.
            capture_output=True,
            timeout=_BOUND_SECONDS,
            timeout_env=AGREEMENT_TIMEOUT_ENV,
        )
    except SpawnTimeout as fired:
        return f"its {_BOUND_SECONDS:g}s wall-clock bound fired.\n{fired}"
    except OSError as refused:
        return (
            f"{classify_spawn_refusal(refused).value}: the declared executable "
            f"{argv[0]!r} could not be spawned as {runtime!r} ({refused})"
        )
    return _Execution(runtime=runtime, argv=executed, completed=completed)


def _indeterminate(
    reason: str,
    observed: dict[str, object] | None = None,
    *,
    census: _CrossingCensus,
    scope: _CrossingScope,
) -> CrossingOutcome:
    """Nothing decisive was learnt. Never green, never a refusal.

    ``observed`` carries whatever the crossing DID measure before it lost the
    ability to speak for the whole traversal -- the producer argv, the one
    artifact, and the per-consumer results actually obtained. Reporting them
    costs nothing and spares the operator a blind re-run, while the verdict
    still refuses to claim a complete traversal that never happened.

    ``census`` is REQUIRED rather than defaulted, and so is its own
    ``unverified``: an indeterminate whose machine surface named nothing it could
    not verify is exactly the silence that value exists to end, and a default
    would let a new branch reintroduce it.

    ``scope`` is REQUIRED for the same reason, and its ``declared`` may be
    ``None``: an indeterminate reached BEFORE any declaration was read genuinely
    does not know what it was asked to measure, and says exactly that rather than
    reporting a population of zero -- which reads as "there was nothing to
    measure".
    """
    return _terminal(
        exit_code=2,
        payload={"verdict": INDETERMINATE, "reason": reason, **(observed or {})},
        human=f"{INDETERMINATE}: {reason}",
        census=census,
        scope=scope,
    )


def _tail(captured: str | bytes | None) -> str:
    """The verbatim tail of a party's output, decoded LOSSILY on purpose.

    A declared party owes this checker no encoding: decoding strictly would let a
    latin-1 byte on a consumer's stderr destroy a whole run that had already
    produced a verdict. The U+FFFD characters a lossy decode leaves behind ARE
    the visible marker that a byte was not understood, and acceptance IS the
    exit code, which no decoding choice can touch.
    """
    if not captured:
        return ""
    if isinstance(captured, bytes):
        captured = captured.decode("utf-8", errors="replace")
    return captured.strip()[-_TAIL_CHARACTERS:]


__all__ = [
    "AGREEMENT_TIMEOUT_ENV",
    "BOUNDARY_LEAD_IN",
    "CROSSED",
    "INDETERMINATE",
    "OUT_OF_REACH_RULE",
    "REFUSED",
    "UNKNOWN",
    "WIDEN_ACTION",
    "CrossingOutcome",
    "cross_agreement",
]

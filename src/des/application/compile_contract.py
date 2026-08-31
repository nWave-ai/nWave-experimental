"""Compile one DeliveryContract SKELETON from a DESIGN architecture brief's
own citations (ADR-SSOT-002 Section 4/4b item 1): ``des compile-contract``'s
pure core.

DISTILL "compiles value and architecture authority into a contract" (ADR
Section 4 preamble); today ATD hand-transcribes every mechanically-derivable
fact (target candidate/decision/declared-imports, verification-scope
commands, the acceptance locator, the schema-closed obligation vocabulary a
brief already bold-labels) and six ``des dispatch`` validators exist
specifically to catch ATD's transcription mistakes AFTER the fact. This
module removes the cause: every fact a validator already knows how to CHECK,
this module DERIVES the same way, by calling the identical resolver in
GENERATION mode instead of VALIDATION mode -- so a compiled skeleton passes
those validators by construction, not by luck.

Row 13 (K4 run 18) adds ``cited-skills``: every ``nw-*`` skill name the brief
cites by name (backtick-quoted, grounded against the installed skill
registry -- ``skill_citations_for_repo``) becomes a mechanical field ATD
reads, instead of a text mention that never became a carried fact. This
compiler still never loads a skill or judges whether its guidance was
followed -- it only makes the CITATION itself impossible to silently lose
between DESIGN's brief and ATD's authoring turn.

Row 13 follow-up (Ale, 2026-08-20: "nw-pbt-python e' troppo python-centric
... nWave e' language agnostic") adds ``pbt-adapter``: when ``cited-skills``
names the PBT family skill or any specific ``nw-pbt-<lang>`` variant, this
compiler mechanically resolves which of the eight shipped variants THIS
contract's own targets imply, from their file extensions
(``resolve_pbt_adapter``) -- never from the citation's own claimed
language, never a silent Python default. A target-language mismatch
against a specifically-cited variant is a ``"discrepancy"`` (the target-
derived variant wins). No installed language-specific adapter applies (no
target extension maps to any shipped variant, targets span more than one,
or the one target-derived variant is not actually installed in this
repository) degrades to the generic, language-agnostic family skill itself
(``"family-fallback"``) -- never a bare refusal: language specificity is
an upgrade when available, never a requirement (Ale, 2026-08-20
follow-up). Only the doubly-degenerate case, where even the family skill
is not installed, is a LOUD ``"unresolved"`` with a ``reason``.

What remains a ``PLACEHOLDER`` (see
``des.domain.contract_placeholder_resolver``) is exactly the set of fields
ADR-SSOT-002 Section 4's field-ownership table assigns to a SEMANTIC/
value-side authority this compiler is never given access to: ``outcome``
(value-side identity), each target's ``justification`` prose and its
``boundary.*`` sub-fields (DESIGN's own judgment, not a fact the brief's
citations alone determine). ``paradigm`` is transcribed from DESIGN's
canonical declaration by the CLI. ``contract-shape`` is the one remaining
schema-closed enum that cannot represent an unfilled placeholder; it takes
the conservative default documented at its own call site below.

The acceptance-oracle locator (``acceptance-tests.locator``) is a
CONVENTION this compiler decides, not an external input: root cannot obtain
that judgment call from ATD before ATD ever runs (ATD holds no ``Bash``,
and this producer runs before ATD's own dispatch), so the locator is
derived deterministically instead (``des.domain.oracle_locator_resolver``)
from the primary EXTEND target's own test-directory convention plus the
``delivery-id``. ATD then WRITES the oracle at that path -- it fills, it
never chooses. No discoverable test-directory convention is a construction
refusal (``Blocked``), never an invented directory.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from des._internal.delivery_contract_schema import (
    LEGACY_SCHEMA_VERSION,
    delivery_contract_schema_version,
)
from des.adapters.driven.codefact.code_fact_chain import CodeFactChain
from des.domain.architecture_brief_resolver import (
    DroppedCitation,
    TargetTableProblems,
    declared_imports_for_target,
    extract_acceptance_support_locators,
    extract_declared_oracle_locator_candidates,
    extract_declared_target_locators,
    extract_declared_target_table,
    extract_declared_verification_authority_locators,
    extract_declared_verification_commands,
    extract_obligations,
    extract_oracle_citations,
    extract_target_citations_with_drops,
    first_unparsed_obligation_candidate,
    is_code_target_citation,
    is_repository_relative_whole_file_locator,
    malformed_acceptance_support_locator_lines,
    resolve_pbt_adapter,
    skill_citations_for_repo,
)
from des.domain.base_revision_resolver import observed_base_revision
from des.domain.contract_placeholder_resolver import PLACEHOLDER
from des.domain.oracle_locator_resolver import (
    is_test_shaped_path,
    oracle_citation_file_part,
    resolve_cited_oracle_locator,
    resolve_existing_oracle_locator,
    resolve_oracle_locator,
)
from des.domain.verification_authority_resolver import (
    AmbiguousAuthorityReference,
    UnresolvedAuthorityReference,
    resolve_verification_authority,
)
from des.domain.workspace_test_command_resolver import declared_whole_suite_command
from des.ports.code_fact_port import (
    CAPABILITY_ATOMS_IN_FILE,
    Answered,
    CapabilityDescriptor,
    CodeFactResult,
    Confidence,
)


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from des.domain.architecture_brief_resolver import DeclaredTargetTableRow
    from des.ports.code_fact_port import Resolution


#: DESIGN owns ``targetPlan.contract-shape`` semantically, but the schema
#: constrains it to a closed enum -- an unfilled placeholder cannot validate
#: there the way ``justification``/``boundary.*`` (free ``nonEmptyText``)
#: can. ``bounded-change`` is the safe generic default for an EXTEND target
#: touching existing code; ATD corrects it per-target when a target is
#: actually ``pure-function`` or ``unbounded-preservation``.
DEFAULT_CONTRACT_SHAPE = "bounded-change"


@dataclass(frozen=True, slots=True)
class CompileContractInputs:
    """Every fact ``compile_delivery_contract`` needs, already resolved by
    its CLI caller (argv parsing, brief file reading) -- this dataclass
    itself performs no I/O."""

    repo_root: Path
    delivery_id: str
    brief_text: str
    delivery_route: str
    paradigm: str
    examine: bool
    budget_token_limit: int
    budget_wall_clock_minutes: int
    #: `applicability.independent-review` is a Seeded/orchestration fact
    #: (ADR-SSOT-002 Section 4c), not purely mechanical -- when the caller
    #: already holds the authoritative closed-rule value (root, before
    #: `des prepare-ordinary-request`), it MUST pass it here rather than
    #: let this compiler's own citation-only proxy (`ARCHITECTURE_BOUNDARY_
    #: CHANGE` in obligations) silently disagree with it. `None` (the
    #: default, for standalone/manual invocations with no better source)
    #: falls back to that proxy.
    independent_review: bool | None = None
    #: The exact immutable VALUE-SEED piped on stdin for an `auto-`
    #: `delivery_id` (`des.application.ordinary_request.
    #: read_value_seed_text`). When present, it lands verbatim in
    #: `contract["outcome"]` instead of the `<ATD: fill>` placeholder --
    #: an auto contract's outcome is compiled, never ATD-authored. `None`
    #: (the default, for a manual/non-auto compile) preserves the existing
    #: placeholder behavior.
    value_seed: str | None = None


@dataclass(frozen=True, slots=True)
class Compiled:
    """A schema-shaped skeleton, ready to be serialized verbatim.

    ``oracle_reused`` is True when the acceptance-oracle locator was
    carried over from the EXISTING contract (recompile-contract only)."""

    contract: dict
    oracle_reused: bool = False


@dataclass(frozen=True, slots=True)
class UnrunCheck:
    """One authority check this pass could NOT execute, because it is
    decided FROM the outcome of a check that failed (the oracle's language
    cannot be judged when the declared target set is unknown).

    A dependent check stays sequential -- but it is DECLARED here, never
    silently omitted: GDP-6, the third state ``could-not-verify`` reaches
    the aggregate. Silence would read as "checked, fine", which is exactly
    the silent-wrong a validator exists to prevent."""

    check: str
    because: str


@dataclass(frozen=True, slots=True)
class Blocked:
    """The compiler could not derive enough from the brief to proceed.

    ``kind`` is the optional machine-readable refusal class (e.g.
    ``"unresolved-authority-reference"``) a caller can key on; the
    WHAT/WHY/HOW prose stays the human contract either way.

    Reject-all-at-once (Ale, 2026-08-22): one compile pass runs EVERY
    INDEPENDENT authority check and reports every problem it found -- the
    head problem in ``what``/``why``/``how``/``kind`` (so a single-problem
    refusal is byte-for-byte the one it has always been), the rest in
    ``also``. Stopping at the first charged the caller one full
    architect->compile round-trip per defect: three sequential refusals on
    ADR-AUM-001 (2026-08-22), four on ADR-CFG-001 (2026-08-21)."""

    what: str
    why: str
    how: str
    kind: str | None = None
    #: The FURTHER independent problems the same pass found, in report
    #: order. Empty for a single-problem refusal.
    also: tuple[Blocked, ...] = ()
    #: The dependent checks this pass could not execute (GDP-6).
    not_run: tuple[UnrunCheck, ...] = ()

    @property
    def problems(self) -> tuple[Blocked, ...]:
        """Every problem of this refusal, head first -- each one a
        standalone WHAT/WHY/HOW carrying no aggregate state of its own."""
        return (replace(self, also=(), not_run=()), *self.also)


def _one_refusal(problems: list[Blocked], unrun: list[UnrunCheck]) -> Blocked:
    """The single ``Blocked`` carrying every problem found in one pass."""
    head, *rest = problems
    return replace(head, also=tuple(rest), not_run=tuple(unrun))


#: The same descriptor shape `blast_radius_measurement` already binds for
#: this capability -- one file, one atom set, through the composed chain.
_ATOMS_DESCRIPTOR = CapabilityDescriptor(
    id=CAPABILITY_ATOMS_IN_FILE,
    stability="stable",
    contract_version="1.0.0",
    io_schema="atoms",
    providing_adapter="code-fact-chain",
)


def binding_resolved_atoms(resolution: Resolution) -> frozenset[str]:
    """The atom set ONLY when the envelope's provenance is trustworthy.

    Q-90/Q-91 acceptance law (agreed with SF, 2026-08-21): the decision is
    on the resolution ENVELOPE -- confidence/provider -- never on the
    payload's shape alone. An ``Answered`` at ``binding-resolved`` (e.g.
    provider ``graphify``) yields its atoms; an ``Answered`` at any lower
    confidence (``approx``, ``noisy`` -- the textual floor rediscovers
    comment/string occurrences, the exact class the falsified whole-word
    text scan admitted), a ``Failed`` and an ``Unsupported`` all yield the
    empty set: honest absence, never a textual admission."""
    if not isinstance(resolution, Answered):
        return frozenset()
    if resolution.confidence != Confidence.BINDING_RESOLVED.value:
        return frozenset()
    envelope = resolution.payload
    payload = envelope.payload if isinstance(envelope, CodeFactResult) else None
    if not isinstance(payload, dict) or payload.get("unparseable"):
        return frozenset()
    atoms = payload.get("atoms")
    if not isinstance(atoms, list):
        return frozenset()
    return frozenset(atom for atom in atoms if isinstance(atom, str) and atom)


def target_atoms_resolver(repo_root: Path) -> Callable[[str], frozenset[str]]:
    """Compose the CodeFact port for `declared_imports_for_target`.

    The domain resolver never does this I/O itself (hexagonal boundary):
    it receives this callable and the application resolves each target
    file's atoms through the composed chain
    (`query.atoms-in-file`), gating admission on `binding_resolved_atoms`'s
    envelope decision. A missing target file resolves to the empty set --
    a symbol cannot pre-exist in a file that does not."""

    def resolve_atoms(target_candidate: str) -> frozenset[str]:
        target_file = repo_root / target_candidate
        if not target_file.is_file():
            return frozenset()
        chain = CodeFactChain(root=target_file)
        return binding_resolved_atoms(chain.resolve(_ATOMS_DESCRIPTOR, {}))

    return resolve_atoms


def _build_target_plan(
    repo_root: Path,
    target_path: str,
    citations: list[str],
    brief_text: str,
    *,
    declared_decision: str | None = None,
    regrounding_exempt: bool = False,
) -> dict | Blocked:
    # A typed declaration's own decision wins over the existence inference
    # (declaration beats inference, never the other way -- ADR-CFG-001
    # reproduction, 2026-08-20) -- but a declaration is GROUNDED against
    # the base tree before it is trusted (reviewer counterexample
    # 2026-08-20: EXTEND on a nonexistent path and CREATE_NEW on an
    # existing one both compiled unchecked, re-opening the ungrounded
    # class the deleted EXTEND-citation validator guarded "by
    # construction"). A contradiction blocks loud, pre-write.
    #
    # ``regrounding_exempt`` marks a row whose path+decision the EXISTING
    # contract already declares: it was grounded at the original compile,
    # and the contract itself is the record that the file is this very
    # delivery's own product -- re-checking it against a worktree that now
    # carries the delivery's in-flight work would let the delivery poison
    # its own recompilation.
    exists = (repo_root / target_path).is_file()
    if not regrounding_exempt and declared_decision == "EXTEND" and not exists:
        return Blocked(
            what=f"declared EXTEND target {target_path!r} does not exist "
            "in the base tree",
            why="EXTEND is a declaration about an EXISTING file; trusting "
            "it against a path the base tree does not carry would compile "
            "an ungrounded contract",
            how="correct the ADR/decision: declare CREATE_NEW if "
            f"{target_path!r} is genuinely new, or fix the declared path "
            "to the real existing file",
        )
    if not regrounding_exempt and declared_decision == "CREATE_NEW" and exists:
        return Blocked(
            what=f"declared CREATE_NEW target {target_path!r} already "
            "exists in the base tree",
            why="CREATE_NEW declares a file that does not exist yet; "
            "trusting it against an existing file would compile an "
            "ungrounded contract",
            how="correct the ADR/decision: declare EXTEND if "
            f"{target_path!r} is being modified, or pick a path the base "
            "tree does not already carry",
        )
    decision = declared_decision or ("EXTEND" if exists else "CREATE_NEW")
    return {
        "candidate": target_path,
        # `overlap` is the exact field `des dispatch`'s EXTEND-citation
        # validator searches -- every citation the brief carries for this
        # file is independently useful evidence, so all are kept.
        "overlap": "; ".join(citations),
        "decision": decision,
        "justification": PLACEHOLDER,
        "declared-imports": declared_imports_for_target(
            repo_root,
            target_path,
            brief_text,
            target_atoms=target_atoms_resolver(repo_root),
        ),
        "contract-shape": DEFAULT_CONTRACT_SHAPE,
        "boundary": {
            "failure-behavior": PLACEHOLDER,
            "substrate-lie": PLACEHOLDER,
            "substrate-probe": PLACEHOLDER,
            "double-blind-spot": PLACEHOLDER,
        },
    }


def _oracle_dotted_label(oracle_locator: str) -> str:
    """The Python dotted-module label ``pytest``/``python -m pytest`` scope
    a run to (``pkg/tests/test_x.py`` -> ``pkg.tests.test_x``) -- a Python-
    only convention. A non-``.py`` oracle (SF friction report 2026-08-20,
    item 2c: a Go oracle previously got this SAME dot-join, producing a
    ``pkg.tests.test_x`` token no ``go test`` invocation accepts) is never
    dot-joined -- its own raw repository-relative path is returned instead,
    the one projection every toolchain unambiguously understands as a real,
    already-cited file, never a guessed module-path shape."""
    if not oracle_locator.endswith(".py"):
        return oracle_locator
    stem = oracle_locator[:-3]
    return stem.replace("/", ".")


def _executable_for(repo_root: Path, head: str) -> dict:
    """A ``repository`` executable when ``head`` resolves under
    ``repo_root`` (a vendored venv interpreter, ``k4-fixture-venv/bin/
    python``, ...), else a ``toolchain`` executable resolved through the
    consumer's own ``PATH`` -- mirrors the same repository-vs-toolchain
    distinction ADR-SSOT-002 Section 4 already draws for
    ``verification-scope.commands``."""
    if (repo_root / head).is_file():
        return {"kind": "repository", "path": head}
    return {"kind": "toolchain", "name": head}


def _replace_last_non_flag_token(tokens: list[str], replacement: str) -> list[str]:
    """``tokens`` with its last non-``-``-prefixed entry swapped for
    ``replacement`` -- an index-based replacement (never value-equality
    based), so a coincidental duplicate earlier token is never mis-swapped."""
    for index in range(len(tokens) - 1, -1, -1):
        if not tokens[index].startswith("-"):
            return [*tokens[:index], replacement, *tokens[index + 1 :]]
    return [*tokens, replacement]


def _oracle_command_scope(oracle_locator: str) -> str:
    """The token that scopes a verification command to the oracle. A
    selector-less locator keeps the historic projection
    (``_oracle_dotted_label``). A ``path::Selector`` locator: pytest
    accepts the whole citation verbatim for a Python oracle; for any other
    language the FILE PART alone is the one shape every toolchain accepts
    as a real path (SF friction report 2026-08-20 -- the selector stays in
    ``acceptance-tests.locator`` as oracle identity; per-language selector
    syntax, e.g. ``go test -run``, is a language-adapter concern this
    compiler does not guess at)."""
    if "::" not in oracle_locator:
        return _oracle_dotted_label(oracle_locator)
    file_part = oracle_citation_file_part(oracle_locator)
    if file_part.endswith(".py"):
        return oracle_locator
    return file_part


def _verification_delegation(repo_root: Path, brief_text: str) -> dict | Blocked | None:
    """The declared-DELEGATION form of ``verification-scope``, or ``None``
    when the brief declares no delegation at all.

    Split out from the argv-shaped fallback (``_verification_commands``)
    because the two have DIFFERENT dependencies: a delegation is decided
    from the brief alone, so it is checkable in the same pass as every
    other brief-only check even when the acceptance oracle could not be
    resolved -- while the fallback commands are SCOPED to that oracle and
    therefore genuinely dependent on it.

    Precedence 0 (outranks everything) -- a declared DELEGATION
    (``Verification authority locator: `<repo-relative-doc>#<heading-
    anchor>```, SF friction 2026-08-21): the cited authority document owns
    the LITERAL verification order as a fenced script block (assignments,
    command substitution, ``!`` negations, pipes -- never argv-splittable),
    so the contract carries it BY-REFERENCE (``literal-script-block``:
    locator + content digest + verbatim lines). This compiler never
    interprets the lines; faithful execution belongs to the consumer, which
    verifies the digest against the owning document. A declared delegation
    that cannot be resolved (document absent / outside the repository /
    heading absent / fence absent) is a typed
    ``unresolved-authority-reference`` refusal BEFORE any write -- never a
    fallback to the label/CLAUDE.md forms: falling back would silently
    substitute a narrower scope for the one the authority explicitly owns.

    With no delegation declared this returns ``None`` and the argv-shaped
    forms apply unchanged (``_verification_commands``): the ``Verification
    command:`` label, then the subject CLAUDE.md whole-suite convention,
    then the Python-only pytest fallback or a refusal."""
    declared_locators = extract_declared_verification_authority_locators(brief_text)
    if len(declared_locators) > 1:
        listed = ", ".join(repr(locator) for locator in declared_locators)
        return Blocked(
            kind="unresolved-authority-reference",
            what="the brief declares more than one verification authority "
            f"locator ({listed}) but the contract carries exactly one "
            "literal-script-block",
            why="two delegations cannot both own the literal verification "
            "order; picking one silently would drop the other authority's "
            "declared scope",
            how="keep exactly one 'Verification authority locator: "
            "`<repo-relative-doc>#<heading-anchor>`' line in the cited "
            "authority (fold the order into one document section), then "
            "re-run des compile-contract",
        )
    if declared_locators:
        resolution = resolve_verification_authority(repo_root, declared_locators[0])
        if isinstance(resolution, UnresolvedAuthorityReference):
            return Blocked(
                kind="unresolved-authority-reference",
                what="the declared verification authority reference "
                f"{resolution.locator!r} cannot be resolved: "
                f"{resolution.reason}",
                why="a declared delegation names the one authority that "
                "owns the literal verification order; falling back to the "
                "subject's CLAUDE.md or a synthesized command would "
                "silently substitute a different scope for the declared "
                "one",
                how="fix the 'Verification authority locator: "
                "`<repo-relative-doc>#<heading-anchor>`' line so the "
                "document exists under the repository root and the heading "
                "is followed by one fenced block carrying the literal "
                "order (marker sentence 'The exact ... verification order "
                "is:'), then re-run des compile-contract",
            )
        if isinstance(resolution, AmbiguousAuthorityReference):
            listed = ", ".join(repr(c) for c in resolution.candidates)
            return Blocked(
                kind="ambiguous-authority-reference",
                what="the declared verification authority reference "
                f"{resolution.locator!r} is ambiguous: {resolution.reason}",
                why="distinct headings can normalize to the same anchor "
                "key; binding the first match silently could carry a "
                "DIFFERENT authority's literal order than the one the "
                "brief meant",
                how="rename one of the colliding headings "
                f"({listed}) so the anchor names exactly one section, or "
                "point the 'Verification authority locator:' line at an "
                "anchor only one heading normalizes to, then re-run des "
                "compile-contract",
            )
        return {
            "literal-script-block": {
                "locator": resolution.locator,
                "content-digest": resolution.content_digest,
                # `lines` is a display-only, NON-authoritative projection
                # for the human/agent reader. Every executor and verifier
                # binds EXCLUSIVELY to the content re-resolved from the
                # owning document (digest-checked against
                # `content-digest`); `des dispatch` refuses LOUDLY when
                # this carried copy drifts from the resolved block.
                "lines": list(resolution.lines),
            }
        }
    return None


def _verification_commands(
    repo_root: Path, oracle_locator: str, brief_text: str
) -> list[dict] | Blocked:
    """Precedence 1 -- the cited authority's own typed declarations
    (``Verification command: `<argv...>```, one per line,
    ``extract_declared_verification_commands``): the authority that
    already states the subject's exact native argv OWNS them, so they are
    carried VERBATIM -- never re-scoped, never duplicated into the
    subject's CLAUDE.md first (SF friction 2026-08-20, verification-scope
    ownership: ``des compile-contract`` demanded a ``go test ./...``
    declaration in the subject CLAUDE.md while the cited Slice 1 brief
    already declared the exact Go and Rust argv -- prose duplicated in
    the wrong place). Same declaration-outranks-inference principle as
    the typed ``Oracle target locator:`` above.

    Precedence 2 (fallback) -- one command scoped to the oracle, plus the
    workspace's own declared whole-suite command when one exists
    (``workspace_test_command_resolver``) -- together they construct the
    preservation scope without relying on a later omission gate.
    Precedence 3 -- a workspace with no declared whole-suite convention
    and a PYTHON oracle falls back to a direct pytest invocation of the
    oracle locator, using a bare ``python`` toolchain name (PATH-resolved)
    -- never a guessed repository-relative ``.venv/bin/python`` path, which
    a fresh/scratch workspace with no real venv at that exact spot would
    silently mis-resolve as a broken toolchain name containing a slash (the
    identical interpreter-resolution class of defect fixed in the shared
    DeliveryContract test fixture, `docs/delivery-contracts/
    fix-language-agnostic-contract-paths.json`, 2026-08-19: `uv run`
    already prepends a real venv's own ``bin/`` to ``PATH`` for every
    child process, so a bare name resolves correctly with no repo-relative
    guess needed). The pytest fallback is PYTHON-ONLY: for a non-Python
    oracle with no declared whole-suite command this compiler REFUSES
    (SF friction report 2026-08-20, sister reproduction, item c: a
    ``python -m pytest`` invocation was invented for a Go subject) --
    verification commands are language-native or absent, never a
    wrong-language guess."""
    declared_by_authority = extract_declared_verification_commands(brief_text)
    if declared_by_authority:
        return [
            {
                "executable": _executable_for(repo_root, head),
                "arguments": list(rest),
            }
            for head, *rest in declared_by_authority
        ]
    declared = declared_whole_suite_command(repo_root)
    if not declared:
        if not oracle_citation_file_part(oracle_locator).endswith(".py"):
            return Blocked(
                what="the subject declares no whole-suite test command, "
                f"and the oracle {oracle_locator!r} is not Python -- no "
                "language-native verification command can be derived",
                why="verification commands must be language-native; the "
                "only convention this compiler may fall back to (a direct "
                "python -m pytest invocation) is Python-only, and "
                "inventing it for another language was the SF friction "
                "2026-08-20 defect",
                how="declare the scope in the cited authority: either a "
                "delegation line 'Verification authority locator: "
                "`<repo-relative-doc>#<heading-anchor>`' when an authority "
                "document owns the literal order, or per-line "
                'declarations, e.g. "Verification command: '
                '`go test ./...`" (one line per command); or declare the '
                "subject's own whole-suite command in its root CLAUDE.md "
                "in the labeled shape, e.g. \"- Run the subject's own "
                'tests: `go test ./...`"; then re-run des compile-contract',
            )
        return [
            {
                "executable": _executable_for(repo_root, "python"),
                "arguments": ["-m", "pytest", "-q", oracle_locator],
            }
        ]
    head, *rest = declared
    executable = _executable_for(repo_root, head)
    whole_suite_command = {"executable": executable, "arguments": list(rest)}
    oracle_command = {
        "executable": executable,
        "arguments": _replace_last_non_flag_token(
            rest, _oracle_command_scope(oracle_locator)
        ),
    }
    return [oracle_command, whole_suite_command]


def _unadmitted_oracle_reason(candidate: str) -> str:
    """Why one declared ``Oracle target locator:`` path is not an oracle --
    the SAME two shape rules ``extract_oracle_citations`` applies, restated
    as a cause the reader can act on rather than a silent drop."""
    file_part = oracle_citation_file_part(candidate)
    if not is_code_target_citation(file_part):
        return "a documentary/formal-proof file is never an oracle"
    if not is_test_shaped_path(file_part):
        return (
            "its filename is not test/spec-shaped by any convention this "
            "compiler knows for that extension"
        )
    return "unrecognized citation shape"  # pragma: no cover -- admitted above


def compile_delivery_contract(
    inputs: CompileContractInputs,
    *,
    declared_in_existing_contract: Mapping[str, str] | None = None,
    existing_oracle_locator: str | None = None,
    existing_verification_scope: dict | None = None,
    admitted_base_revision: str | None = None,
) -> Compiled | Blocked:
    """Derive a schema-shaped DeliveryContract skeleton from ``inputs``.

    ``Blocked`` only when a fact this compiler could never safely guess is
    genuinely absent (no observable HEAD, no file:line citation, no
    schema-closed obligation token) -- never a partial or best-effort
    contract in that case.

    ``declared_in_existing_contract`` (recompile-contract ONLY) maps each
    target path the EXISTING contract already declares to its declared
    decision: a brief row matching path+decision is exempt from
    re-grounding, because it was grounded at the original compile and the
    file on disk may be this very delivery's own in-flight product. New
    rows and decision-changed rows are grounded fresh, as at compile.

    ``existing_oracle_locator`` / ``existing_verification_scope``
    (recompile-contract ONLY): the EXISTING contract is the record of the
    original oracle judgment, so when the brief as it stands NOW yields no
    test-shaped citation the locator (and, if the fresh fallback
    derivation cannot produce one, its verification-scope) is reused
    instead of refused. compile-contract never passes these, so its
    refusal is unchanged.

    ``admitted_base_revision`` is supplied only when recompile-contract has
    reconstructed a reviewed closure at HEAD. That closure owns original B;
    observing HEAD here would rewrite B to C and destroy delivery identity.
    Initial compilation/recompilation leaves it ``None``.
    """
    base_revision = admitted_base_revision or observed_base_revision(inputs.repo_root)
    if base_revision is None:
        return Blocked(
            what=f"HEAD could not be observed at {inputs.repo_root}",
            why="repository.base-revision must be the exact observed "
            "candidate SHA, never guessed",
            how="run from a repository with at least one commit checked out",
        )

    # Reject-all-at-once (Ale, 2026-08-22): from here to the contract
    # build, every INDEPENDENT check runs and every problem it found is
    # ACCUMULATED -- one pass, one refusal listing all of them. Returning
    # at the first charged the architect one full consult->compile
    # round-trip per defect (three on ADR-AUM-001, four on ADR-CFG-001).
    # A check that genuinely DEPENDS on a failed one stays sequential and
    # is recorded in ``unrun``, never silently skipped (GDP-6).
    problems: list[Blocked] = []
    unrun: list[UnrunCheck] = []

    already_declared = declared_in_existing_contract or {}
    citations, dropped_citations = extract_target_citations_with_drops(
        inputs.brief_text
    )
    declared_table = extract_declared_target_table(inputs.brief_text)
    table_rows: list[DeclaredTargetTableRow] | None = None
    #: False when the authority's declared target set could not be read in
    #: full -- every check DECIDED FROM that set is then undecidable, and
    #: says so rather than running on a set it knows is partial.
    target_set_complete = True
    if isinstance(declared_table, TargetTableProblems):
        problems.extend(
            Blocked(
                what=problem.what,
                why=problem.why,
                how=problem.how,
                kind="target-declaration-table",
            )
            for problem in declared_table.problems
        )
        target_set_complete = False
        # The rows that DID transcribe are still grounded below: a
        # readable row is independent of an unreadable sibling, so this
        # pass reports its problems too instead of hiding them behind the
        # table refusal.
        table_rows = list(declared_table.rows)
        unrun.append(
            UnrunCheck(
                check="target grounding for the rows this pass could not read",
                because="the authority's declared target set could not be "
                "transcribed in full, so those rows' declarations were "
                "never grounded against the base tree",
            )
        )
    elif declared_table is not None:
        table_rows = list(declared_table)

    declared_locators = extract_declared_target_locators(inputs.brief_text)
    targets: dict[str, dict] = {}
    #: EVERY path the authority declared, whether or not its plan grounded
    #: -- the language/route decisions below are made from the DECLARED
    #: set, so a row that failed grounding must not silently shrink it.
    target_paths: list[str] = []

    def _plan_or_problem(
        path: str,
        evidence: list[str],
        *,
        declared_decision: str | None,
        regrounding_exempt: bool,
    ) -> None:
        """Ground one declared row, recording its problem instead of
        aborting the pass -- rows are independent of one another."""
        target_paths.append(path)
        plan = _build_target_plan(
            inputs.repo_root,
            path,
            evidence,
            inputs.brief_text,
            declared_decision=declared_decision,
            regrounding_exempt=regrounding_exempt,
        )
        if isinstance(plan, Blocked):
            problems.append(plan)
            unrun.append(
                UnrunCheck(
                    check=f"target-plan derivation for {path!r} "
                    "(declared-imports, contract-shape, boundary)",
                    because="the row's own declaration did not ground "
                    "against the base tree, so this pass has no plan to "
                    "derive them from",
                )
            )
            return
        targets[path] = plan

    if table_rows is not None:
        # The table is the authority's OWN explicit, complete target set
        # (GDP-0: the architect declares, this compiler transcribes) -- it
        # outranks EVERY inferred source, including a per-line typed
        # locator declaration (ADR-CFG-001 third same-producer incident,
        # 2026-08-21: a stale slice-1 typed line and citation inference
        # each produced a wrong set while the amendment's table declared
        # the right one). Citations/locators for a tabled path survive as
        # overlap evidence; anything outside the declared set surfaces in
        # `dropped-citations`, never silently (GDP-6).
        declared_paths = {row.path for row in table_rows}
        dropped_citations = (
            dropped_citations
            + [
                DroppedCitation(
                    citation=citation,
                    reason="prose citation outside the declared target "
                    "table -- the authority's '| Target | Decision |' "
                    "table outranks citation inference",
                )
                for target_path, citation_list in citations.items()
                if target_path not in declared_paths
                for citation in citation_list
            ]
            + [
                DroppedCitation(
                    citation=locator.citation,
                    reason="typed target declaration outside the declared "
                    "target table -- the table is the complete declared "
                    "set",
                )
                for locator in declared_locators
                if locator.path not in declared_paths
            ]
        )
        locator_citations = {
            locator.path: locator.citation
            for locator in declared_locators
            if locator.path in declared_paths
        }
        for row in table_rows:
            evidence = [
                citation
                for citation in [locator_citations.get(row.path)]
                if citation is not None
            ] + citations.get(row.path, [])
            _plan_or_problem(
                row.path,
                # `overlap` is nonEmptyText in the schema: a declared row
                # with zero citations of its own still names its source.
                evidence or ["declared in the authority's target table"],
                declared_decision=row.decision,
                regrounding_exempt=row.decision is not None
                and already_declared.get(row.path) == row.decision,
            )
    elif declared_locators:
        # A typed declaration is DESIGN's own explicit statement of the
        # target set: declaration wins over prose inference, never the
        # other way (ADR-CFG-001 reproduction, 2026-08-20: two files the
        # brief textually excluded from scope were promoted to EXTEND
        # while the one declared CREATE_NEW target was dropped). Prose
        # citations survive only as extra overlap evidence for a declared
        # target, never as autonomous targets of their own -- and the
        # ones for files OUTSIDE the declared set are surfaced in
        # `dropped-citations`, never silently discarded (GDP-6).
        declared_paths = {locator.path for locator in declared_locators}
        dropped_citations = dropped_citations + [
            DroppedCitation(
                citation=citation,
                reason="prose citation outside the declared target set -- "
                "a typed 'Oracle target locator' declaration outranks "
                "prose inference",
            )
            for target_path, citation_list in citations.items()
            if target_path not in declared_paths
            for citation in citation_list
        ]
        for locator in declared_locators:
            _plan_or_problem(
                locator.path,
                [locator.citation, *citations.get(locator.path, [])],
                declared_decision=locator.decision,
                regrounding_exempt=locator.decision is not None
                and already_declared.get(locator.path) == locator.decision,
            )
    elif not citations:
        if dropped_citations:
            # The brief DID carry citations -- every one collapsed to
            # nothing this parser can ground. Say exactly that (a WHAT
            # claiming "no citation" would be a lying rejection).
            collapsed = "; ".join(
                f"{entry.citation} ({entry.reason})" for entry in dropped_citations
            )
            problems.append(
                Blocked(
                    what="every file:line citation in the architecture brief "
                    f"collapsed to zero groundable targets: {collapsed}",
                    why="targets are derived exclusively from DESIGN's own "
                    "cited insertion points; a citation this compiler cannot "
                    "ground is never promoted to a guessed file",
                    how="qualify each citation with its repository-relative "
                    "path (e.g. 'src/pkg/module.py:12', never a bare "
                    "'module.py:12' naming no cited file), or author the "
                    "contract's targets by hand",
                )
            )
        else:
            problems.append(
                Blocked(
                    what="the architecture brief carries no file:line citation",
                    why="targets are derived exclusively from DESIGN's own cited "
                    "insertion points; a brief with none gives this compiler "
                    "nothing to build a target from",
                    how="cite at least one exact file:line insertion point in the "
                    "architecture brief, or author the contract's targets by hand "
                    "for a brief this compiler cannot parse",
                )
            )
    else:
        for target_path, citation_list in citations.items():
            _plan_or_problem(
                target_path,
                citation_list,
                declared_decision=None,
                regrounding_exempt=False,
            )

    # The primary EXTEND target is the first declaration/citation the brief
    # makes -- both extractors preserve first-appearance order.
    primary_target = target_paths[0] if target_paths else None

    # The acceptance oracle's route/language/convention are all decided
    # FROM the declared target set. With that set unknown (unreadable or
    # partial table) or empty, this whole block is genuinely undecidable:
    # it is DECLARED unrun rather than run against a set this pass knows
    # is not the architect's (GDP-6, the third state reaches the
    # aggregate).
    oracle_pass_decidable = bool(target_paths) and target_set_complete
    oracle_locator: str | None = None
    oracle_reused = False
    if not oracle_pass_decidable:
        unrun.append(
            UnrunCheck(
                check="acceptance-oracle resolution (route/language/convention)",
                because="it is decided from the complete declared target "
                "set, which this pass could not resolve",
            )
        )
    else:
        assert primary_target is not None
        # A test/spec-shaped citation is an oracle-binding candidate, never
        # a target (SF friction report 2026-08-20, sister reproduction,
        # item a).
        oracle_citations = extract_oracle_citations(inputs.brief_text)

        # GREEN_TO_GREEN binds an ALREADY-EXISTING, already-committed
        # oracle -- authoring one fresh is RED_TO_GREEN's job, a different
        # route. Never project a possibly wrong-language, possibly
        # nonexistent path here (SF friction report 2026-08-20, item 2a).
        if inputs.delivery_route == "GREEN_TO_GREEN":
            oracle_locator = resolve_existing_oracle_locator(
                inputs.repo_root, oracle_citations
            )
            if oracle_locator is None:
                problems.append(
                    Blocked(
                        what="GREEN_TO_GREEN but the brief cites no existing, "
                        "already-committed test/spec file",
                        why="GREEN_TO_GREEN binds an oracle that already exists -- "
                        "projecting an unauthored path (as RED_TO_GREEN does) would "
                        "be a contradiction by construction",
                        how="cite the exact file:line of the real, already-"
                        f"committed oracle that already covers {primary_target!r} "
                        "in the architecture brief, or use RED_TO_GREEN if the "
                        "oracle is not yet written",
                    )
                )
        else:
            # RED_TO_GREEN: an explicitly cited oracle (with or without a
            # ::Selector) IS the locator -- the brief already made the
            # judgment call. Only a Python subject with NO cited oracle may
            # fall back to the Python-only tests/test_<slug>.py convention;
            # a non-Python subject with no cited oracle is a refusal, never
            # a wrong-language pytest path (SF friction report 2026-08-20,
            # sister reproduction, item b).
            oracle_locator = resolve_cited_oracle_locator(oracle_citations)
            if oracle_locator is None and existing_oracle_locator is not None:
                oracle_locator = existing_oracle_locator
                oracle_reused = True
            if oracle_locator is None and not all(
                target_path.endswith(".py") for target_path in target_paths
            ):
                # GDP-3: name WHICH targets made the subject non-Python,
                # and -- when the brief DID declare an oracle -- which
                # declaration was refused and why. "the brief cites no
                # test/spec oracle" is a lying rejection when a
                # declaration sits right there in the text (ADR-AUM-001
                # reproduction, 2026-08-22). The declared set, never the
                # grounded one: a row that failed grounding must not
                # silently shrink the language decision.
                non_python = [
                    target_path
                    for target_path in target_paths
                    if not target_path.endswith(".py")
                ]
                unadmitted = [
                    f"{candidate} ({_unadmitted_oracle_reason(candidate)})"
                    for candidate in extract_declared_oracle_locator_candidates(
                        inputs.brief_text
                    )
                    if candidate not in oracle_citations
                ]
                detail = (
                    "the brief's own 'Oracle target locator:' declaration was "
                    "NOT admitted as an oracle: " + "; ".join(unadmitted)
                    if unadmitted
                    else "the brief carries no 'Oracle target locator:' "
                    "declaration and no test/spec-shaped file:line or "
                    "path::TestName citation"
                )
                problems.append(
                    Blocked(
                        what=f"{inputs.delivery_route} on a non-Python subject "
                        f"(non-Python targets: {', '.join(non_python)}) and no "
                        f"test/spec oracle could be bound -- {detail}",
                        why="the tests/test_<slug>.py synthesis is a Python-only "
                        "convention; projecting it for a non-Python subject "
                        "invents a wrong-language, nonexistent oracle (SF "
                        "friction report 2026-08-20, sister reproduction)",
                        how="declare the oracle in the architecture brief next to "
                        "the targets it covers, in a shape this compiler admits: "
                        'an "Oracle target locator: `<repo-relative test/spec-'
                        'shaped path>`" line (the path need NOT exist yet on '
                        "RED_TO_GREEN -- ATD authors it there), a file:line "
                        "citation of a test/spec-shaped file, or a path::TestName "
                        f"selector binding (e.g. {primary_target!r}'s own sibling "
                        "*_test file)",
                    )
                )
            elif oracle_locator is None:
                oracle_locator = resolve_oracle_locator(
                    inputs.repo_root, primary_target, inputs.delivery_id
                )
                if oracle_locator is None:
                    problems.append(
                        Blocked(
                            what="no test-directory convention is discoverable for "
                            f"{primary_target!r} (no sibling tests/ and no repository-"
                            "root tests/)",
                            why="the acceptance-oracle locator is a convention this "
                            "compiler decides, never a guessed or invented directory",
                            how="create the project's test directory (a sibling tests/ "
                            f"next to {primary_target!r}, or a top-level tests/), or "
                            "declare the project's test-directory convention in the "
                            "workspace fragment",
                        )
                    )

    # Brief-only, therefore always decidable -- it depends on no target
    # and no oracle, so a failed target set never hides a missing
    # obligation behind an earlier refusal.
    schema_unreadable = False
    try:
        obligations = extract_obligations(inputs.brief_text)
    except RuntimeError as exc:
        obligations = []
        schema_unreadable = True
        problems.append(
            Blocked(
                kind="contract-schema-unreadable",
                what=str(exc),
                why="the compiler cannot derive the closed obligation vocabulary",
                how="reinstall nWave with its schemas, then re-run compile-contract",
            )
        )
    if not obligations and not schema_unreadable:
        offending_line = first_unparsed_obligation_candidate(inputs.brief_text)
        problems.append(
            Blocked(
                what="the architecture brief bold-labels no schema-closed "
                "obligation token"
                + (
                    f" -- closest candidate line: {offending_line!r}"
                    if offending_line
                    else ""
                ),
                why="obligations select the algebra/certainty/PBT/reuse/"
                "architecture-drift lenses downstream; this compiler only ever "
                "copies a token the brief already states, never invents one",
                how="have DESIGN label each numbered obligation with its exact "
                "schema token, in EITHER accepted shape -- 'N. **TOKEN**' or "
                "'**N. TOKEN**' (an optional trailing ':' inside the bold span "
                "is also tolerated, e.g. '**REUSE_CANDIDATE:**') -- or author "
                "'obligations' by hand",
            )
        )

    # Test dependencies are durable authority, never an inferred list of
    # whatever files happen to sit beside the primary oracle. The producer
    # preserves declaration order and rejects every spelling that would
    # otherwise require downstream normalisation.
    support_locators = extract_acceptance_support_locators(inputs.brief_text)
    malformed_support = malformed_acceptance_support_locator_lines(inputs.brief_text)
    invalid_support = [
        locator
        for locator in support_locators
        if not is_repository_relative_whole_file_locator(locator)
    ]
    duplicate_support = sorted(
        {locator for locator in support_locators if support_locators.count(locator) > 1}
    )
    if malformed_support:
        problems.append(
            Blocked(
                what="malformed Test dependency locator declaration(s): "
                + "; ".join(repr(line) for line in malformed_support),
                why="test-dependency identity must be an explicit backticked durable locator",
                how="write one 'Test dependency locator: `<repository-relative-file>`' line per private test dependency",
            )
        )
    if invalid_support:
        problems.append(
            Blocked(
                what="test dependency locator is not a repository-relative whole-file identity: "
                + ", ".join(repr(locator) for locator in invalid_support),
                why="selectors, traversal and absolute paths cannot be stable support identities",
                how="declare repository-relative whole-file locators without selectors",
            )
        )
    if duplicate_support:
        problems.append(
            Blocked(
                what="duplicate test dependency locator(s): "
                + ", ".join(repr(locator) for locator in duplicate_support),
                why="one support identity may enter the ordered closure exactly once",
                how="remove duplicate Test dependency locator lines",
            )
        )
    if support_locators != sorted(support_locators):
        problems.append(
            Blocked(
                what="test dependency locators are not lexicographically ordered",
                why="closure identity must not depend on incidental producer iteration order",
                how="sort Test dependency locator lines by locator bytes and recompile",
            )
        )

    # ADR-SSOT-002 Section 4c closed rule: independent review resolves true
    # when obligations include an architecture-boundary change -- used only
    # when the caller has no already-resolved Seeded value of its own.
    independent_review = (
        inputs.independent_review
        if inputs.independent_review is not None
        else "ARCHITECTURE_BOUNDARY_CHANGE" in obligations
    )

    # A declared DELEGATION is decided from the brief ALONE (precedence 0),
    # so it is checkable in the same pass as every other brief-only check
    # even when the oracle could not be resolved. The argv-shaped fallback
    # commands are SCOPED to the oracle and therefore genuinely dependent.
    verification_scope: dict | None = None
    delegation = _verification_delegation(inputs.repo_root, inputs.brief_text)
    if isinstance(delegation, Blocked):
        problems.append(delegation)
    elif delegation is not None:
        verification_scope = delegation
    elif oracle_locator is not None:
        commands = _verification_commands(
            inputs.repo_root, oracle_locator, inputs.brief_text
        )
        if isinstance(commands, Blocked):
            # The fallback derivation coming up empty -- for a REUSED
            # oracle the existing contract already records the matching
            # scope. (Typed authority-reference refusals never reach here:
            # a declared delegation is current authority and stays loud.)
            if oracle_reused and existing_verification_scope is not None:
                verification_scope = existing_verification_scope
            else:
                problems.append(commands)
        else:
            verification_scope = {"commands": commands}
    elif not oracle_pass_decidable:
        unrun.append(
            UnrunCheck(
                check="verification-scope commands",
                because="they are scoped to the acceptance oracle, whose "
                "own resolution this pass could not run",
            )
        )

    if problems:
        return _one_refusal(problems, unrun)

    # Every branch that leaves these unresolved appended a problem above,
    # so reaching here with either unset is unrepresentable by
    # construction -- asserted rather than defaulted, because a silent
    # default here would write a contract with a guessed oracle.
    assert oracle_locator is not None
    assert verification_scope is not None

    cited_skills = skill_citations_for_repo(inputs.repo_root, inputs.brief_text)
    pbt_adapter = resolve_pbt_adapter(inputs.repo_root, cited_skills, targets.keys())

    contract = {
        "schema-version": (
            delivery_contract_schema_version()
            if support_locators
            else LEGACY_SCHEMA_VERSION
        ),
        "delivery-id": inputs.delivery_id,
        "repository": {"worktree": ".", "base-revision": base_revision},
        "outcome": inputs.value_seed if inputs.value_seed is not None else PLACEHOLDER,
        "targets": targets,
        "paradigm": inputs.paradigm,
        "delivery-route": inputs.delivery_route,
        "obligations": obligations,
        "cited-skills": cited_skills,
        # GDP-6: a citation this compiler dropped stays VISIBLE to
        # ATD/human review. Optional additive field (same pattern as
        # cited-skills), absent when nothing was dropped.
        **(
            {
                "dropped-citations": [
                    {"citation": entry.citation, "reason": entry.reason}
                    for entry in dropped_citations
                ]
            }
            if dropped_citations
            else {}
        ),
        **({"pbt-adapter": pbt_adapter} if pbt_adapter is not None else {}),
        "acceptance-tests": {
            "locator": oracle_locator,
            **({"supporting-locators": support_locators} if support_locators else {}),
        },
        "verification-scope": verification_scope,
        "applicability": {
            "independent-review": independent_review,
            "examine": inputs.examine,
        },
        "budget": {
            "token-limit": inputs.budget_token_limit,
            "wall-clock-minutes": inputs.budget_wall_clock_minutes,
        },
    }
    return Compiled(contract=contract, oracle_reused=oracle_reused)

"""Compile one DeliveryContract SKELETON from a DESIGN architecture brief.

``des compile-contract`` mechanically derives every fact a ``des dispatch``
validator already knows how to CHECK (target candidate/decision/declared-
imports, verification-scope commands, the acceptance locator by convention,
the schema-closed obligation vocabulary) by calling the same resolver in
GENERATION mode. What remains is written as the literal ``<ATD: fill>``
placeholder (``des.domain.contract_placeholder_resolver``) for ATD to
author -- never a guess. See ``des.application.compile_contract`` module
docstring for the full rationale (ADR-SSOT-002 Section 4/4b item 1).
"""

from __future__ import annotations

import argparse
import json
import re
import stat
import sys
from pathlib import Path

from des._internal.delivery_contract_schema import (
    SchemaUnreadable,
    SchemaViolation,
    delivery_contract_schema_violation,
)
from des.application.compile_contract import (
    Blocked,
    CompileContractInputs,
    Compiled,
    compile_delivery_contract,
)
from des.application.ordinary_request import (
    ARCH_HEADER_PREFIXES,
    BUDGET_TABLE,
    DELIVERY_ID_PREFIX,
    compute_delivery_id,
    contract_locator_for,
    is_valid_arch_header_line,
    read_value_seed_text,
)
from des.domain.architecture_brief_resolver import (
    canonical_paradigm,
    extract_declared_paradigms,
)
from des.domain.verification_authority_resolver import (
    AmbiguousAuthorityReference,
    UnresolvedAuthorityReference,
    resolve_authority_section,
)


_EXIT_BLOCKED = 2
_DELIVERY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _blocked(*, what: str, why: str, how: str) -> int:
    print(f"WHAT: {what} WHY: {why} HOW: {how}", file=sys.stderr)
    return _EXIT_BLOCKED


def _problem_line(problem: Blocked) -> str:
    """One problem's own complete WHAT/WHY/HOW. A typed refusal leads with
    its machine-readable class token (e.g.
    ``unresolved-authority-reference``) so a caller can key on it without
    parsing prose."""
    what = f"{problem.kind}: {problem.what}" if problem.kind else problem.what
    return f"WHAT: {what} WHY: {problem.why} HOW: {problem.how}"


def _blocked_from(result: Blocked) -> int:
    """Render ONE refusal carrying every problem the compile pass found --
    the single renderer BOTH ``des compile-contract`` and ``des recompile-
    contract`` call (the same rendering, never a copy).

    Reject-all-at-once (Ale, 2026-08-22): a validator that stops at the
    first problem charges the caller one full producer round-trip per
    defect. A single-problem refusal stays byte-for-byte the one line it
    has always been -- no reader pays for the multi-problem affordance.
    More than one problem (or any check that could not run) leads with HOW
    MANY, then one numbered block per problem, each independently
    actionable, then every check this pass could NOT run and why (GDP-6:
    the third state reaches the aggregate; silence would read as
    "checked, fine")."""
    problems = result.problems
    if len(problems) == 1 and not result.not_run:
        print(_problem_line(problems[0]), file=sys.stderr)
        return _EXIT_BLOCKED
    total = len(problems)
    noun = "problem" if total == 1 else "problems"
    lines = [
        f"BLOCKED: {total} {noun} found in one pass -- each is "
        "independent; fix them all, then re-run.",
        *(
            f"({index}/{total}) {_problem_line(problem)}"
            for index, problem in enumerate(problems, start=1)
        ),
        *(f"NOT CHECKED: {entry.check} -- {entry.because}" for entry in result.not_run),
    ]
    print("\n".join(lines), file=sys.stderr)
    return _EXIT_BLOCKED


#: Where each contract node this compiler emits COMES FROM in the
#: architecture authority. A schema violation is never a JSON typo -- the
#: compiler transcribes; so the HOW must name the CELL whose text produced
#: the invalid value, not merely report that the JSON does not validate
#: (GDP-3/GDP-4: the repair is made at the producing authority, and the
#: reader must not have to guess which line of the ADR to correct).
_AUTHORITY_ORIGIN: dict[str, str] = {
    "targets": "the target-declaration table (the pipe table whose header "
    "names both a Target and a Decision column)",
    "acceptance-tests": "the 'Oracle target locator: `<path>`' citation "
    "(or the test/spec-shaped file:line citation the oracle was bound from)",
    "verification-scope": "the 'Verification command: `<argv>`' label lines "
    "(or the 'Verification authority locator:' delegation)",
    "obligations": "the 'Delivery obligations' list",
    "cited-skills": "the brief's own nw-* skill citations",
    "dropped-citations": "the brief's own nw-* skill citations",
    "pbt-adapter": "the brief's own nw-* skill citations",
    "delivery-id": "the --delivery-id argument",
    "repository": "the observed repository HEAD",
}


def _authority_cell(path: tuple[str | int, ...]) -> str:
    """The authority cell that produced the contract node at ``path``."""
    if not path:
        return "the architecture authority as a whole"
    head = str(path[0])
    origin = _AUTHORITY_ORIGIN.get(head)
    if head != "targets":
        return origin or f"whatever the authority declares for {head!r}"
    if len(path) < 2:
        return f"a Target cell of {origin}"
    declared = str(path[1])
    column = {"candidate": "Target", "decision": "Decision"}.get(
        str(path[2]) if len(path) > 2 else "", ""
    )
    if column:
        return f"the {column} cell of the row declaring {declared!r} in {origin}"
    return f"the row declaring {declared!r} in {origin}"


def refuse_schema_invalid_skeleton(
    contract: dict,
    *,
    architecture_authority: str,
    producer: str,
) -> int | None:
    """Refuse BEFORE the write when the compiled contract does not satisfy
    the installed thin-delivery-contract schema; ``None`` when it does.

    GDP-0, third occurrence of the class (Ale, 2026-08-22): this compiler
    used to write its skeleton unvalidated and leave the check to the
    downstream consumer (``des dispatch`` / ``des validate-delivery-
    contract``), so a Target cell naming a DIRECTORY where the schema
    admits only a FILE was transcribed verbatim into a contract no version
    of the schema has ever accepted -- it reached the trunk, went red in
    CI, and blocked the slice. The grounding check did not stop it because
    ``is_file`` is False for EVERY non-file, directories included: it does
    not discriminate a file from a non-file. The producer now makes the
    invalid state unrepresentable on disk; the check runs through the SAME
    seam ``des validate-delivery-contract`` runs downstream (``des.
    _internal.delivery_contract_schema``), never a rewired copy.
    """
    finding = delivery_contract_schema_violation(contract)
    if finding is None:
        return None
    if isinstance(finding, SchemaUnreadable):
        return _blocked_from(
            Blocked(
                kind="contract-schema-unreadable",
                what="the DeliveryContract schema cannot be read at "
                f"{finding.schema_path} ({finding.error})",
                why="a skeleton whose validity could not be established is "
                "not written: an unchecked contract is exactly the state "
                "this producer exists to make unrepresentable (GDP-6 -- "
                "could-not-verify is never a pass)",
                how=f"reinstall nWave with its schemas, then re-run {producer}",
            )
        )
    assert isinstance(finding, SchemaViolation)
    prefix = next(
        (p for p in ARCH_HEADER_PREFIXES if architecture_authority.startswith(p)),
        "",
    )
    reference = architecture_authority[len(prefix) :]
    return _blocked_from(
        Blocked(
            kind="schema-invalid-skeleton",
            what=f"the compiled skeleton fails the thin-delivery-contract "
            f"schema at {finding.pointer} ({finding.message})",
            why="this compiler TRANSCRIBES the authority -- an invalid "
            "value in the contract is an invalid value in the authority, "
            "and writing it would hand a contract downstream that no "
            "version of the schema has ever accepted (GDP-0: the producer "
            "makes the wrong state unrepresentable; nothing was written)",
            how=f"correct {_authority_cell(finding.path)} in {reference} so "
            f"the value satisfies nWave/schemas/{finding.schema_path.name} "
            f"at {finding.pointer}, then re-run {producer} -- editing the "
            "JSON by hand is not a fix, the next compile transcribes the "
            "same cell again",
        )
    )


class _RefusingArgumentParser(argparse.ArgumentParser):
    """Fail-closed argv parsing: one concise WHAT/WHY/HOW line on stderr,
    nonzero exit -- mirrors ``des prepare-ordinary-request``'s own parser."""

    def error(self, message: str) -> None:
        print(
            f"WHAT: {message} "
            "WHY: every argv fact must be an explicit, well-formed fixed "
            "token -- a missing or malformed flag cannot be silently "
            "defaulted or guessed. "
            "HOW: pass every required --flag; see "
            f"`{self.prog} --help`.",
            file=sys.stderr,
        )
        raise SystemExit(_EXIT_BLOCKED)


def build_parser(prog: str, description: str) -> argparse.ArgumentParser:
    """The one shared argv surface for ``des compile-contract`` AND ``des
    recompile-contract`` -- the recompiler takes the exact same input facts
    (ADR-SSOT-002 Section 4/4b), so the flag set is defined once here."""
    parser = _RefusingArgumentParser(prog=prog, description=description)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--delivery-id", required=True)
    parser.add_argument(
        "--architecture-authority",
        required=True,
        help="The exact 'ARCHITECTURE-COVERED: <path>.md#<anchor>' line -- "
        "the SAME shape/value des prepare-ordinary-request already "
        "validates and ATD's own envelope carries.",
    )
    parser.add_argument(
        "--route",
        dest="delivery_route",
        default="RED_TO_GREEN",
        choices=("RED_TO_GREEN", "GREEN_TO_GREEN"),
    )
    parser.add_argument(
        "--paradigm",
        default=None,
        choices=("functional", "object_oriented"),
        help="Optional compatibility assertion. Normally the compiler derives "
        "DESIGN's 'Paradigm:' declaration "
        "from --architecture-authority; a conflict is refused.",
    )
    parser.add_argument("--examine", default="true", choices=("true", "false"))
    parser.add_argument(
        "--independent-review",
        default=None,
        choices=("true", "false"),
        help="The caller's own already-resolved Seeded value (ADR-SSOT-002 "
        "Section 4c) -- omit only for a standalone/manual run with no "
        "better source, which falls back to this compiler's own "
        "obligations-based proxy.",
    )
    parser.add_argument("--size", default="M", choices=("M", "L"))
    parser.add_argument("--budget-token-limit", type=int, default=None)
    parser.add_argument("--budget-wall-clock-minutes", type=int, default=None)
    return parser


def _parser() -> argparse.ArgumentParser:
    return build_parser(
        prog="des compile-contract",
        description=(
            "Compile one DeliveryContract SKELETON from a DESIGN architecture "
            "brief's own citations; leaves every semantic field as an "
            "explicit <ATD: fill> placeholder for the acceptance designer "
            "to author. verification-scope precedence: (1) a 'Verification "
            "authority locator: `<repo-relative-doc>#<heading-anchor>`' "
            "delegation carries the authority's literal script block "
            "by-reference; (2) 'Verification command: `<argv>`' label "
            "lines; (3) the subject CLAUDE.md whole-suite convention; "
            "(4) the Python-only pytest fallback, else a typed refusal. "
            "An unresolvable declared delegation is a typed "
            "'unresolved-authority-reference' refusal, never a fallback."
        ),
    )


def resolve_inputs(args: argparse.Namespace) -> CompileContractInputs | int:
    """Validate the shared argv facts and read the brief -- the one input
    resolution both ``des compile-contract`` and ``des recompile-contract``
    run (the same derivation, never a copy). Returns the ready
    ``CompileContractInputs``, or the already-printed blocked exit code."""
    repo_root: Path = args.repo_root
    try:
        root_stat = repo_root.lstat()
    except OSError as exc:
        return _blocked(
            what=f"--repo-root cannot be read ({exc})",
            why="contract compilation requires a real repository root",
            how="pass an existing absolute repository directory",
        )
    if (
        not repo_root.is_absolute()
        or not stat.S_ISDIR(root_stat.st_mode)
        or repo_root.is_symlink()
    ):
        return _blocked(
            what="--repo-root is not an absolute real directory",
            why="contract identity must not depend on the invoking cwd, and "
            "a symlink root makes it ambiguous",
            how="pass the absolute physical repository directory",
        )

    if not _DELIVERY_ID_RE.match(args.delivery_id):
        return _blocked(
            what=f"--delivery-id {args.delivery_id!r} is not schema-shaped",
            why="delivery-id must match thin-delivery-contract.schema.json's "
            "$defs/id pattern",
            how="pass a lowercase-kebab id starting with a letter or digit",
        )

    if not is_valid_arch_header_line(args.architecture_authority):
        return _blocked(
            what=(
                f"--architecture-authority {args.architecture_authority!r} "
                "is not a well-formed ARCHITECTURE-COVERED <path>.md#<anchor> "
                "line"
            ),
            why="the architecture authority is a citation, not free text -- "
            "the same shape des prepare-ordinary-request already requires",
            how="pass the architect's exact 'ARCHITECTURE-COVERED: "
            "<repo-relative-path>.md#<anchor>' line verbatim",
        )
    prefix = next(
        p for p in ARCH_HEADER_PREFIXES if args.architecture_authority.startswith(p)
    )
    reference = args.architecture_authority[len(prefix) :]
    brief_relative_path, _separator, anchor = reference.partition("#")
    brief_path = repo_root / brief_relative_path
    try:
        resolved_root = repo_root.resolve(strict=True)
        resolved_brief = brief_path.resolve(strict=True)
    except OSError as exc:
        return _blocked(
            what=f"the architecture brief cannot be read or resolved at {brief_path} ({exc})",
            why="compile-contract reads only an authority physically contained by --repo-root",
            how="pass a readable repository-contained architecture authority",
        )
    if not resolved_brief.is_relative_to(resolved_root):
        return _blocked(
            what=f"the architecture brief at {brief_relative_path!r} resolves outside --repo-root",
            why="a symlink authority would make the cited repository-relative authority false",
            how="replace it with a real authority file physically contained by --repo-root",
        )
    try:
        whole_document_text = brief_path.read_text(encoding="utf-8")
    except OSError as exc:
        return _blocked(
            what=f"the architecture brief cannot be read at {brief_path} ({exc})",
            why="compile-contract derives every fact from the brief's own citations",
            how="pass an --architecture-authority path readable under --repo-root",
        )

    # The anchor is a CITATION to one section, not decoration: every fact
    # below is derived from `brief_text` alone, so it must be the CITED
    # SECTION, never the whole document (F-COMPILE-CONTRACT-IGNORES-
    # AUTHORITY-ANCHOR, docs/product/backlog.md) -- reuses the SAME
    # anchor-matching/ambiguity law `resolve_verification_authority` already
    # applies to a sibling `<doc>#<anchor>` citation shape, never a second
    # resolver.
    section = resolve_authority_section(
        whole_document_text,
        anchor,
        locator=args.architecture_authority,
        doc_part=brief_relative_path,
    )
    if isinstance(section, UnresolvedAuthorityReference):
        return _blocked(
            what="the --architecture-authority anchor cannot be resolved: "
            f"{section.reason}",
            why="compile-contract derives every fact from the CITED SECTION "
            "alone -- an anchor naming no real heading would otherwise "
            "silently fall back to reading the whole document",
            how="point --architecture-authority at a real "
            "'<path>.md#<heading-anchor>' heading that exists in the "
            "document, or add that heading to the document",
        )
    if isinstance(section, AmbiguousAuthorityReference):
        listed = ", ".join(repr(candidate) for candidate in section.candidates)
        return _blocked(
            what=f"the --architecture-authority anchor is ambiguous: {section.reason}",
            why="distinct headings can normalize to the same anchor key; "
            "binding the first match would derive every fact from a "
            "DIFFERENT section than the one cited",
            how=f"rename one of the colliding headings ({listed}) so the "
            "anchor names exactly one section",
        )
    brief_text = section.text

    declared_paradigms = extract_declared_paradigms(brief_text)
    normalized = [canonical_paradigm(value) for value in declared_paradigms]
    recognized = [value for value in normalized if value is not None]
    distinct = list(dict.fromkeys(recognized))
    if len(distinct) > 1:
        return _blocked(
            what=f"the architecture authority declares conflicting paradigms {distinct}",
            why="paradigm is one DESIGN-owned decision; selecting either value "
            "would silently contradict the other",
            how="retain one exact 'Paradigm: functional' or 'Paradigm: "
            "object_oriented' declaration in the cited section",
        )
    if declared_paradigms and None in normalized:
        malformed = declared_paradigms[normalized.index(None)]
        return _blocked(
            what=f"the architecture authority declares unsupported paradigm {malformed!r}",
            why="the DeliveryContract schema admits only functional or "
            "object_oriented; this spelling does not identify either "
            "unambiguously",
            how="declare functional/FP or object-oriented/OO/OOP on the "
            "Paradigm: line in the cited section",
        )
    if len(declared_paradigms) > 1:
        return _blocked(
            what="the architecture authority declares the paradigm more than once",
            why="paradigm is one DESIGN-owned decision; equivalent aliases are "
            "still duplicate authorities that may drift independently",
            how="retain exactly one 'Paradigm: functional' or 'Paradigm: "
            "object_oriented' declaration in the cited section",
        )
    authority_paradigm = distinct[0] if distinct else None
    if authority_paradigm is None:
        return _blocked(
            what="the architecture authority does not declare a paradigm",
            why="paradigm belongs to DESIGN and cannot be silently defaulted "
            "or supplied by root",
            how="add a 'Paradigm:' line selecting functional/FP or "
            "object-oriented/OO/OOP to the cited section, then re-run "
            "compile-contract",
        )
    if (
        authority_paradigm is not None
        and args.paradigm is not None
        and authority_paradigm != args.paradigm
    ):
        return _blocked(
            what=f"--paradigm {args.paradigm!r} contradicts the architecture "
            f"authority's {authority_paradigm!r} decision",
            why="an argv compatibility assertion cannot override DESIGN authority",
            how="drop --paradigm or pass the authority's exact value",
        )
    table_tokens, table_minutes = BUDGET_TABLE[args.size]
    budget_token_limit = (
        args.budget_token_limit if args.budget_token_limit is not None else table_tokens
    )
    budget_wall_clock_minutes = (
        args.budget_wall_clock_minutes
        if args.budget_wall_clock_minutes is not None
        else table_minutes
    )

    value_seed: str | None = None
    if args.delivery_id.startswith(DELIVERY_ID_PREFIX):
        value_seed = read_value_seed_text()
        if value_seed is None:
            return _blocked(
                what=f"--delivery-id {args.delivery_id!r} requires the exact "
                "immutable VALUE-SEED piped on stdin, but stdin was empty or "
                "not valid UTF-8",
                why="an auto delivery-id's outcome IS the piped VALUE-SEED -- "
                "compile-contract must read the same raw bytes the id was "
                "computed from, never an argv or environment carrier",
                how="pipe the exact VALUE-SEED text as raw UTF-8 stdin to "
                "des compile-contract",
            )
        if compute_delivery_id(value_seed) != args.delivery_id:
            return _blocked(
                what=f"the piped VALUE-SEED does not hash to --delivery-id "
                f"{args.delivery_id!r} ({compute_delivery_id(value_seed)!r} "
                "computed instead)",
                why="an auto delivery-id is a deterministic function of its "
                "own VALUE-SEED -- a mismatch means the wrong seed, or the "
                "wrong id, was passed",
                how="pass the exact VALUE-SEED that produced this "
                "delivery-id, or recompute the delivery-id from the seed "
                "actually being piped",
            )

    return CompileContractInputs(
        repo_root=repo_root,
        delivery_id=args.delivery_id,
        brief_text=brief_text,
        delivery_route=args.delivery_route,
        paradigm=authority_paradigm,
        examine=args.examine == "true",
        budget_token_limit=budget_token_limit,
        budget_wall_clock_minutes=budget_wall_clock_minutes,
        independent_review=(
            None
            if args.independent_review is None
            else args.independent_review == "true"
        ),
        value_seed=value_seed,
    )


def _atomic_write_contract(destination: Path, contract: dict) -> None:
    """Publish one complete contract or leave the prior bytes untouched."""
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(contract, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exit_signal:
        code = exit_signal.code
        return code if isinstance(code, int) else _EXIT_BLOCKED

    inputs = resolve_inputs(args)
    if isinstance(inputs, int):
        return inputs
    result = compile_delivery_contract(inputs)
    if isinstance(result, Blocked):
        return _blocked_from(result)
    assert isinstance(result, Compiled)
    refusal = refuse_schema_invalid_skeleton(
        result.contract,
        architecture_authority=args.architecture_authority,
        producer="des compile-contract",
    )
    if refusal is not None:
        return refusal

    contract_locator = contract_locator_for(inputs.delivery_id)
    destination = inputs.repo_root / contract_locator
    if destination.is_file():
        return _blocked_from(
            Blocked(
                kind="existing-contract",
                what=f"a contract already exists at {contract_locator}",
                why="one contract is written once; compiling over an existing "
                "skeleton would silently discard ATD's in-progress fills",
                how="run des recompile-contract with the same flags to "
                "re-derive it in place while preserving ATD's fills, or delete "
                "the existing file first if truly starting over",
            )
        )
    if destination.exists():
        return _blocked_from(
            Blocked(
                kind="existing-non-file",
                what=f"the contract destination {contract_locator} exists but is not a file",
                why="a directory or other non-file collision cannot be treated as an existing DeliveryContract",
                how="remove or rename the colliding non-file path, then re-run des compile-contract",
            )
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_contract(destination, result.contract)
    print(f"DELIVERY-CONTRACT-SKELETON: {contract_locator}")
    print(f"ORACLE-LOCATOR: {result.contract['acceptance-tests']['locator']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

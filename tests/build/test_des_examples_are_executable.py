"""Executable-example guard (GDP-1): every fenced `des <subcommand> ...`
example across `nWave/skills/**/SKILL.md` and `nWave/agents/*.md` must be
argparse-acceptable.

Run 6 evidence: root copied nw-auto/SKILL.md's documented `des code-fact`
verification command, hit "unrecognized arguments" 3x (a positional
`subject` token trailing after an already-consumed `--root VALUE` flag is
a genuine argparse ordering trap -- reproduced live: `des code-fact
query.callers-of --root . SYMBOL` fails, `des code-fact query.callers-of
SYMBOL --root .` and `--root . query.callers-of SYMBOL` both work), then
fell back to 19 direct source Reads -- the exact behaviour the "root never
Reads source" rule exists to prevent. An example nobody can execute is
worse than no example: it sends the reader into the exact failure mode
the guidance was written to close off.

Run 9 correction: the original implementation dry-ran every example as a
real `python -m des ...` SUBPROCESS, which failed nondeterministically
under box load (~1 in 3 combined-suite runs -- many `des` spawns
contending for the same box, not order-dependence: the hermetic env fix
already ruled that out). Parses IN-PROCESS instead: each subcommand's own
`argparse.ArgumentParser` factory (`_parser`/`_build_parser`, resolved via
`des.cli.__main__`'s own subcommand registry -- never a second hand-typed
module-path mapping) is called directly and its `.parse_known_args(argv)`
is exercised with no subprocess, no env, no timeout, nothing left for a
loaded box to contend over.

Placeholders are substituted with dummy values of the right SHAPE (a real
existing file/dir in this checkout, a plain identifier, an enum member --
never a value chosen to make a borderline case pass) and the real
argparse instance parses the result. A downstream WHAT/WHY/HOW application
refusal (a nonexistent delivery-contract, an unresolved symbol) never
happens here at all now -- IN-PROCESS parsing stops at argv acceptance,
never reaching application logic -- so only argparse's own fixed error
vocabulary ("unrecognized arguments", "invalid choice", "the following
arguments are required", "expected ... argument") counts as a
documentation defect here.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import re
import shlex
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
_PREFLIGHT_DIR = REPO_ROOT / "scripts" / "analysis" / "k4"
if str(_PREFLIGHT_DIR) not in sys.path:
    sys.path.insert(0, str(_PREFLIGHT_DIR))

from preflight import des_fenced_lines


_ARGPARSE_ERROR_MARKERS = (
    "unrecognized arguments",
    "invalid choice",
    "the following arguments are required",
    "expected one argument",
    "expected at least one argument",
)

# Real, small, always-present targets -- shape-appropriate dummy values,
# never chosen to coincidentally satisfy a specific example's semantics.
_DUMMY_DIR = str(REPO_ROOT)
_DUMMY_FILE = "pyproject.toml"

_ANGLE_PLACEHOLDER_RE = re.compile(r"<[^>]+>")
_BRACKETED_OPTIONAL_RE = re.compile(r"\[[^\]]*\]")
_BARE_UPPER_TOKEN_RE = re.compile(r"[A-Z][A-Z_]*")


def _dummy_for(name: str) -> str:
    """One dummy value shaped for what a placeholder NAME claims to hold --
    never a value hand-picked to make one specific example pass."""
    lowered = name.lower()
    if "|" in name:
        # `<true|false>`, `<RED_TO_GREEN|GREEN_TO_GREEN>`, `<M|L>` -- any
        # one member is a syntactically valid enum choice.
        return name.split("|", 1)[0].strip()
    if "root" in lowered:
        return _DUMMY_DIR
    if "file" in lowered or "path" in lowered:
        return _DUMMY_FILE
    if "symbol" in lowered:
        return "dummy_symbol"
    if "anchor" in lowered:
        return "decision"
    if any(word in lowered for word in ("limit", "minutes", "count")):
        return "1"
    if "id" in lowered:
        return "auto-0000000000000000"
    if "locator" in lowered or "contract" in lowered:
        return "docs/delivery-contracts/dummy.json"
    return "dummy-value"


def _collapse_angle_span_whitespace(match: re.Match[str]) -> str:
    """`<absolute physical root>` -> `<absolute_physical_root>` so the span
    shlex-splits as ONE token below -- the underscore is undone again in
    `_substitute_token`, this only survives long enough to cross the split."""
    return "<" + re.sub(r"\s+", "_", match.group(0)[1:-1]) + ">"


def _substitute_token(token: str) -> str:
    """One dummy value per ORIGINAL (pre-substitution) token -- applied
    exactly once, so an already-substituted enum member (`RED_TO_GREEN`,
    `M`) is never mistaken for a second, bare-uppercase placeholder and
    re-substituted into a generic dummy on a following pass. `_dummy_for`'s
    checks are substring-based, so the collapsed `_`-joined placeholder
    name (`absolute_physical_root`) still matches "root" without needing
    the underscores undone -- undoing them would also corrupt a REAL
    underscored enum member like `RED_TO_GREEN`, which was never
    whitespace to begin with."""
    if len(token) > 2 and token.startswith("<") and token.endswith(">"):
        return _dummy_for(token[1:-1])
    if _BARE_UPPER_TOKEN_RE.fullmatch(token):
        return _dummy_for(token)
    return token


def _tokenize(command_line: str) -> list[str] | None:
    """Substituted argv for one `des_fenced_lines` entry, or `None` if it
    does not shlex-tokenize after the substitutions below."""
    # A trailing shell heredoc redirect (`<<'DELIM'` and its body) is never
    # real argv -- the shell strips it before argparse ever sees it.
    head = command_line.split("<<", 1)[0]
    # `[optional clause]` is prose describing an omittable extra flag, not
    # literal syntax to copy -- drop it for a minimal valid invocation.
    head = _BRACKETED_OPTIONAL_RE.sub("", head)
    # `<...>` may itself contain spaces (`<absolute physical root>`) -- a
    # single regex pass over the raw string keeps it one placeholder,
    # never several stray tokens after shlex splits on the inner spaces.
    head = _ANGLE_PLACEHOLDER_RE.sub(_collapse_angle_span_whitespace, head).strip()
    try:
        tokens = shlex.split(head)
    except ValueError:
        return None
    return [_substitute_token(token) for token in tokens]


def _all_des_example_argv() -> list[tuple[str, list[str]]]:
    """`(source-relative-path, substituted argv)` for every fenced `des`
    example across the two documented globs."""
    paths = sorted(REPO_ROOT.glob("nWave/skills/**/SKILL.md")) + sorted(
        REPO_ROOT.glob("nWave/agents/*.md")
    )
    examples: list[tuple[str, list[str]]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for line in des_fenced_lines(text):
            tokens = _tokenize(line)
            if not tokens or tokens[0] != "des":
                continue
            examples.append((str(path.relative_to(REPO_ROOT)), tokens))
    return examples


# The parser-factory function names actually used across `src/des/cli/*`
# today -- `dispatch.py`/`resolve_charters.py` use `_build_parser`,
# `code_fact.py`/`prepare_ordinary_request.py`/`charter_scaffold.py`/
# `validate_delivery_contract.py` use `_parser`. Either is a zero-arg
# callable returning one fresh `argparse.ArgumentParser` -- never invoked
# module `main()`, so no application logic (file I/O, network, mutation)
# ever runs for this guard.
_PARSER_FACTORY_NAMES = ("_parser", "_build_parser")


def _resolve_parser_factory(subcommand: str):
    """The zero-arg `argparse.ArgumentParser` factory for a registered
    `des` subcommand, resolved via `des.cli.__main__`'s OWN subcommand
    registry -- never a second, hand-typed subcommand-to-module mapping
    that could independently drift from the real dispatcher. `None` when
    the subcommand is not registered, or its module exposes neither known
    factory name (a real documentation-vs-CLI gap, not swallowed here)."""
    from des.cli.__main__ import _REGISTRY

    row = next((entry for entry in _REGISTRY if entry.name == subcommand), None)
    if row is None:
        return None
    module = importlib.import_module(row.module_path)
    for name in _PARSER_FACTORY_NAMES:
        factory = getattr(module, name, None)
        if callable(factory):
            return factory
    return None


def _in_process_argparse_error_text(parser_factory, argv: list[str]) -> str:
    """Attempt `parser_factory().parse_known_args(argv)` IN-PROCESS (no
    subprocess) and return whatever argparse-generated error text
    resulted, or `""` on a clean parse. Standard `argparse.ArgumentParser`
    prints its message to stderr then raises `SystemExit` (`self.exit()`)
    -- captured via a redirected `stderr`. Some modules override `error()`
    to raise a different, module-private exception carrying the SAME
    argparse-generated message text instead of exiting (`des
    resolve-charters`'s `_RefusingArgumentParser`, `des prepare-ordinary-
    request`'s own refusing parser) -- that exception's own `str()` is
    appended too, so either path's message text reaches the caller."""
    stderr_capture = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr_capture):
            parser_factory().parse_known_args(argv)
    except SystemExit:
        pass
    except Exception as exc:
        return stderr_capture.getvalue() + str(exc)
    return stderr_capture.getvalue()


def test_extraction_finds_a_known_nonempty_baseline() -> None:
    """Non-vacuity pin: a parser/glob mistake that finds nothing can never
    fail the executability check below -- a silent, undiscriminating
    pass."""
    examples = _all_des_example_argv()
    sources = {source for source, _ in examples}
    assert "nWave/skills/nw-code-analysis-port/SKILL.md" in sources
    assert "nWave/skills/nw-auto/SKILL.md" in sources
    assert len(examples) >= 5


def test_every_documented_des_example_parses_without_an_argparse_error() -> None:
    problems: list[str] = []
    unresolved_subcommands: set[str] = set()
    for source, argv in _all_des_example_argv():
        subcommand = argv[1] if len(argv) > 1 else ""
        parser_factory = _resolve_parser_factory(subcommand)
        if parser_factory is None:
            unresolved_subcommands.add(subcommand)
            continue
        error_text = _in_process_argparse_error_text(parser_factory, argv[2:])
        hit = next(
            (marker for marker in _ARGPARSE_ERROR_MARKERS if marker in error_text),
            None,
        )
        if hit is not None:
            problems.append(
                f"{source}: `{' '.join(argv)}` -> argparse error ({hit!r}): "
                f"{error_text.strip()}"
            )
    assert not unresolved_subcommands, (
        "no argparse-factory could be resolved for "
        f"{sorted(unresolved_subcommands)} via des.cli.__main__'s registry "
        f"-- expose one of {_PARSER_FACTORY_NAMES} on that subcommand's "
        "module, or this guard cannot verify its documented examples at all"
    )
    assert not problems, "\n\n".join(problems)


def _documented_heredoc_subcommands() -> set[str]:
    """The `des <subcommand>` name of every fenced example across
    `nWave/skills/**/SKILL.md` that ends in the quoted seed-heredoc
    redirect."""
    documented: set[str] = set()
    for path in sorted(REPO_ROOT.glob("nWave/skills/**/SKILL.md")):
        for line in des_fenced_lines(path.read_text(encoding="utf-8")):
            if not (line.endswith("<<'NW_SEED'") or line.endswith('<<"NW_SEED"')):
                continue
            head = line.split("<<", 1)[0]
            try:
                tokens = shlex.split(head)
            except ValueError:
                continue
            if len(tokens) >= 2 and tokens[0] == "des":
                documented.add(tokens[1])
    return documented


def test_skill_heredoc_examples_match_hook_allowed_commands_exactly() -> None:
    """Run 7 evidence: nw-auto/SKILL.md mandated piping the VALUE-SEED
    heredoc into `des resolve-charters` once it started building the PO
    envelope; the Auto-root Bash hook's carve-out only ever recognized
    `prepare-ordinary-request` as heredoc-eligible, so root's own
    documented next command was denied -- the drift class this repo's own
    guards exist to kill. THE one place naming the heredoc-eligible
    subcommand set is `pre_tool_use_handler._VALUE_SEED_HEREDOC_ALLOWED_
    COMMANDS`; this test asserts BOTH directions against it, imported
    directly rather than re-declared, so the two can never independently
    drift again: every fenced example ending in the heredoc redirect must
    name a subcommand the hook allows, and every subcommand the hook
    allows must be demonstrated by at least one fenced example."""
    from des.adapters.drivers.hooks import pre_tool_use_handler

    allowed = set(pre_tool_use_handler._VALUE_SEED_HEREDOC_ALLOWED_COMMANDS)
    documented = _documented_heredoc_subcommands()

    # Non-vacuity: an extraction bug that finds nothing can never fail
    # either coverage assertion below -- a silent, undiscriminating pass.
    assert documented, "no fenced seed-heredoc example found at all"
    assert allowed, "the hook's heredoc-eligible command set is empty"

    missing_from_docs = allowed - documented
    assert not missing_from_docs, (
        f"the hook allows the seed heredoc for {sorted(missing_from_docs)} but "
        "no fenced nw-auto/SKILL.md example demonstrates it"
    )
    undocumented_in_hook = documented - allowed
    assert not undocumented_in_hook, (
        "a fenced nw-auto/SKILL.md example pipes the seed heredoc into "
        f"{sorted(undocumented_in_hook)}, which the hook does not allow"
    )

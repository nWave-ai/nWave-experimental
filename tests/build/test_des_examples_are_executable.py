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

Placeholders are substituted with dummy values of the right SHAPE (a real
existing file/dir in this checkout, a plain identifier, an enum member --
never a value chosen to make a borderline case pass) and the real `des`
CLI parses the result. A downstream WHAT/WHY/HOW application refusal (a
nonexistent delivery-contract, an unresolved symbol) is expected and fine;
only argparse's own fixed error vocabulary ("unrecognized arguments",
"invalid choice", "the following arguments are required", "expected ...
argument") counts as a documentation defect here.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
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


def _hermetic_subprocess_env(home: Path) -> dict[str, str]:
    """A minimal, deliberately clean subprocess environment -- verified
    live to produce byte-identical CLI output with and without the
    ambient session's environment: this CLI needs only `PATH` (interpreter/
    shared-library resolution) and a real `HOME`. Every other ambient var
    -- `CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `NWAVE_AGENTS_HOME`,
    `DES_PROJECT_DIR`, `GIT_*` overrides, anything a sibling test's
    `monkeypatch.setenv` or a session-scoped autouse fixture set earlier in
    THIS pytest session -- is deliberately absent. `subprocess.run` with no
    `env=` inherits the CALLING process's full `os.environ`, so without
    this the dry-run silently tests "the CLI plus whatever this pytest
    session happened to touch first," not the CLI's own argparse grammar
    in isolation -- an order-dependent pass/fail unrelated to whether the
    documented example is actually well-formed."""
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home)}


def test_extraction_finds_a_known_nonempty_baseline() -> None:
    """Non-vacuity pin: a parser/glob mistake that finds nothing can never
    fail the executability check below -- a silent, undiscriminating
    pass."""
    examples = _all_des_example_argv()
    sources = {source for source, _ in examples}
    assert "nWave/skills/nw-code-analysis-port/SKILL.md" in sources
    assert "nWave/skills/nw-auto/SKILL.md" in sources
    assert len(examples) >= 5


def test_every_documented_des_example_parses_without_an_argparse_error(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = _hermetic_subprocess_env(home)

    problems: list[str] = []
    for source, argv in _all_des_example_argv():
        result = subprocess.run(
            [sys.executable, "-m", "des", *argv[1:]],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        hit = next(
            (marker for marker in _ARGPARSE_ERROR_MARKERS if marker in result.stderr),
            None,
        )
        if hit is not None:
            problems.append(
                f"{source}: `{' '.join(argv)}` -> argparse error ({hit!r}), "
                f"full stderr:\n{result.stderr.strip()}"
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

"""Classify a verification-scope command's BASE execution output (K4 Run 13).

Run 13 debrief: 4 crafter dispatches, 3 of them wasted -- each burned 4-9
minutes implementing against the oracle, then failed on a defect IN THE
ORACLE ITSELF. The root's own debrief: "have ATD actually execute the
oracle... before CONTRACT_READY". ATD holds no `Bash` by design; the
deterministic place is `des dispatch`, the one boundary between
`CONTRACT_READY` and the first crafter dispatch.

ONE language-agnostic classification (roadmap: "language agnostic is an
outcome constraint, not authorization to build or retain a universal
language-adapter framework" -- an earlier revision built a Python-AST
structure checker plus an `OracleCheckPort`/adapter-per-language pair,
both deleted; "removal before refactoring"). No Python-specific parsing
survives (`SyntaxError`/`SystemCheckError`/`ERROR:`-block regex, all
vocabulary that could never generalize honestly to Go/TS/Rust output): a
nonzero exit whose output already names one of the contract's own
declared symbols is the missing-feature reason (RED, acceptable, any
language, a plain token match). A nonzero exit matching the small,
extensible, language-NEUTRAL build/compile-broken marker table below is
`UNACCEPTABLE_BUILD` -- the ONE refusal beyond `ALREADY_GREEN` this
classifier still makes, quoting the real tool's own output rather than
diagnosing it (never claiming "SyntaxError" against output that was never
Python's -- the K4 sister defect's lying-refusal shape, one language
over). Every other nonzero exit is `INDETERMINATE` -- informational only,
never a refusal. The crafter's own BASELINE remains the one real test.

This module is pure text/dict classification -- no subprocess, no `Bash`.
Two callers feed it a captured `(returncode, output)` pair: `des dispatch`'s
BASE red-reason probe (`des.cli._oracle_red_reason_refusal`, reusing
`des.runtime.test_execution.run_pytest_reaped`, a general bounded-Popen
helper despite its name) and the oracle-write PostToolUse classifier
(`des.domain.oracle_write_classifier`) -- ONE classification function, no
duplicate algorithm between the two call sites.
"""

from __future__ import annotations

import re


_DECLARED_SYMBOL_RE = re.compile(r"\b[A-Z][A-Za-z0-9]{2,}\b")

#: A language-neutral build/compile-broken signal -- present regardless of
#: which specific toolchain produced it. Small and extensible by design:
#: add a row, never a language-specific branch. None of these claim WHICH
#: language failed or diagnose the exact cause; they only decide whether
#: the real tool's own output gets quoted as a refusal instead of filed
#: informational.
_BUILD_BROKEN_MARKERS: tuple[str, ...] = (
    "SyntaxError",  # Python
    "syntax error",  # Go's own compiler wording (lowercase, distinct token)
    "# command-line-arguments",  # go build/vet's compile-error preamble
    "cannot find package",  # go
    "error TS",  # tsc
    "error[E",  # rustc
    "could not compile",  # cargo
)

#: One-per-command classification. `GREEN`/`RED` are correct-shaped
#: outcomes (whether a defect at all depends on route and oracle-linkage,
#: decided by the caller); `UNACCEPTABLE_BUILD` is always a defect;
#: `INDETERMINATE` means this classifier cannot name the failure reason --
#: informational only, never a defect.
GREEN = "GREEN"
RED = "RED"
UNACCEPTABLE_BUILD = "UNACCEPTABLE_BUILD"
INDETERMINATE = "INDETERMINATE"


def declared_symbol_candidates(contract: dict) -> set[str]:
    """Every CamelCase-shaped identifier the contract's own targets already
    name as new substrate, read from `justification`/`overlap` -- the
    symbols a nonzero exit is allowed to fail on and still count as the
    missing-feature reason, not an oracle defect. A plain token match,
    language-agnostic: a symbol name is just a substring, whatever
    language actually printed it."""
    found: set[str] = set()
    for target in contract.get("targets", {}).values():
        for field in ("justification", "overlap"):
            found.update(_DECLARED_SYMBOL_RE.findall(str(target.get(field, ""))))
    return found


def classify_probe_output(
    *, returncode: int, output: str, declared_symbols: set[str]
) -> str:
    """Classify one command's BASE execution outcome: `GREEN` (exit 0);
    `RED` (nonzero, output names a declared symbol -- the acceptable
    missing-feature reason, checked first so a real declared-symbol match
    always wins over an incidental marker substring); `UNACCEPTABLE_BUILD`
    (nonzero, no declared symbol, output matches a build/compile-broken
    marker -- a real defect, any language); or `INDETERMINATE` (nonzero,
    neither -- this classifier does not know why, so it makes no claim;
    the caller reports it informationally, never as a refusal)."""
    if returncode == 0:
        return GREEN
    if any(symbol in output for symbol in declared_symbols):
        return RED
    if any(marker in output for marker in _BUILD_BROKEN_MARKERS):
        return UNACCEPTABLE_BUILD
    return INDETERMINATE


def reason_line(output: str) -> str:
    """The most informative single line of `output` to quote in a finding
    or a note: the last non-empty line naming an error-shaped token
    (`Error`/`error`/`clashes`/`FAIL`/`ERROR`), or, failing that, the last
    non-empty line overall. Shared by both callers (see module docstring)
    so the quoted evidence is identical regardless of which one asks."""
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(
            token in stripped
            for token in ("Error", "error", "clashes", "FAIL", "ERROR")
        ):
            return stripped[:200]
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1][:200] if lines else ""

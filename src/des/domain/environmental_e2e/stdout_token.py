"""L1.4 stdout-token domain — pure formatter, no I/O.

The cross-tree-frozen one-line stdout token every `--mode` of
`verify_environmental_e2e` emits. Nine fields, no JSON, no free prose:

    environmental_e2e mode=<m> feature=<id> authored=<bool> genuine=<bool>
      collected=<N> verdict=<pass|fail|flaky|broken|misscoped|xpass-stale>
      verdict_input_digest=<digest|-> fresh=<bool|-> xfail_present=<bool|->

Closed enums for `verdict` and exit codes — both byte-locked by L1.4.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GateVerdict(str, Enum):
    """L1.4 closed enum for the stdout `verdict` field."""

    PASS = "pass"
    FAIL = "fail"
    FLAKY = "flaky"
    BROKEN = "broken"
    MISSCOPED = "misscoped"
    XPASS_STALE = "xpass-stale"


class GateExit(int, Enum):
    """L1.4 four-value exit-code grid, uniform across modes."""

    PASS = 0
    CHECK_FAILED = 1
    PARSE_IO = 2
    MISSCOPED = 3


@dataclass(frozen=True)
class StdoutToken:
    """L1.4 stdout-token value object — nine fields, immutable."""

    mode: str
    feature: str
    authored: bool
    genuine: bool
    collected: int
    verdict: GateVerdict
    verdict_input_digest: str | None
    fresh: bool | None
    xfail_present: bool | None


def _render_bool(value: bool | None) -> str:
    """Render a bool|None field using the L1.4 placeholder ('-') for None."""
    if value is None:
        return "-"
    return "true" if value else "false"


def _render_digest(value: str | None) -> str:
    """Render the digest field using the L1.4 placeholder ('-') for None."""
    return value if value is not None else "-"


def format_stdout_token(token: StdoutToken) -> str:
    """Render the nine-field L1.4 stdout token as one machine-readable line."""
    return (
        f"environmental_e2e mode={token.mode} feature={token.feature} "
        f"authored={_render_bool(token.authored)} "
        f"genuine={_render_bool(token.genuine)} "
        f"collected={token.collected} "
        f"verdict={token.verdict.value} "
        f"verdict_input_digest={_render_digest(token.verdict_input_digest)} "
        f"fresh={_render_bool(token.fresh)} "
        f"xfail_present={_render_bool(token.xfail_present)}"
    )


__all__ = [
    "GateExit",
    "GateVerdict",
    "StdoutToken",
    "format_stdout_token",
]

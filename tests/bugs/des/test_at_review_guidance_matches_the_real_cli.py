"""Guidance that tells an operator how to record an AT-review must actually run.

The readiness gate's HOW printed a `des record-at-review-verdict` line that the
real CLI rejects -- it omitted the required `--reviewer-agent-id` -- so an
operator following the instruction hit argparse errors and finished the job by
trial and error. A HOW that does not execute is not a HOW.

The test drives the operator's real path: pull the command out of the guidance
text, substitute the placeholders, and hand it to the REAL parser.
"""

from __future__ import annotations

import re
import shlex

import pytest

from des.cli import at_review_verdict
from des.cli.verify_readiness_pre_dispatch import _INV_AT_VERDICT, _REMEDIATIONS


AT_VERDICT_GUIDANCE = _REMEDIATIONS[_INV_AT_VERDICT]


_COMMAND_RE = re.compile(r"`des record-at-review-verdict([^`]*)`")
_PLACEHOLDER_RE = re.compile(r"<[^>]+>")


def _documented_invocations(guidance: str) -> list[list[str]]:
    """Every runnable `des record-at-review-verdict ...` line in the guidance."""
    found = []
    for tail in _COMMAND_RE.findall(guidance):
        # A prose reference that elides its flags ("... --verdict APPROVED") is
        # not an instruction to copy, so it is not held to the parser.
        if "..." in tail:
            continue
        found.append(shlex.split(_PLACEHOLDER_RE.sub("placeholder", tail)))
    return found


def test_the_guidance_actually_documents_a_command() -> None:
    """Guards the extraction: a silent zero-match would make the suite vacuous."""
    assert _documented_invocations(AT_VERDICT_GUIDANCE)


@pytest.mark.parametrize("guidance", [AT_VERDICT_GUIDANCE], ids=["readiness-invariant"])
def test_documented_invocation_parses_against_the_real_cli(guidance: str) -> None:
    for argv in _documented_invocations(guidance):
        # SystemExit is argparse refusing the operator's copy-paste.
        at_review_verdict._parse_args(argv)


def test_the_real_cli_still_requires_the_flags_the_guidance_names() -> None:
    """If a required flag is ever dropped, the guidance above is stale, not wrong."""
    with pytest.raises(SystemExit):
        at_review_verdict._parse_args(
            ["--feature-id", "f", "--slice-id", "slice-01", "--verdict", "APPROVED"]
        )

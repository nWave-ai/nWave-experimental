"""Regression: `des dispatch` must name the CORRECT agent per phase in the
generated `AGENT_IDENTITY` section, not hardcode the crafter for every phase.

DEFECT (GDP-5, the producing-tool must derive the correct agent per phase):
`_section_body` in `src/des/cli/dispatch.py` (~line 126) hardcodes

    "AGENT_IDENTITY": "Agent: nw-software-crafter\\n",

for EVERY phase, including `D_DISTILL` -- the phase whose job is AUTHORING
the slice's acceptance test. But nWave's test/fix authorship split (ADR-025)
reserves AT authorship to `nw-acceptance-designer`; the crafter is SLIM and
NEVER authors tests. So a `des dispatch --phase D_DISTILL ...` invocation
generates a dispatch prompt naming the WRONG agent (`nw-software-crafter`)
for AT authoring.

The fix (crafter's job, NOT implemented by this AT): `_section_body`'s
`AGENT_IDENTITY` entry becomes phase-aware -- a phase-to-agent map routing
`D_DISTILL` to `nw-acceptance-designer` while implementation phases
(`A_GREEN`, `D_REFACTOR_COMMIT`, ...) keep `nw-software-crafter`.

Driving surface (Mandate 16 -- driving-port-only, default IN-PROCESS): the
REAL `des dispatch` CLI, driven in-process via
`tests/common/in_process_cli.run_cli_in_process` (the in-process analogue of
`python -m des.cli.__main__ dispatch ...`) against THIS checkout's real
`nWave/dispatch/atdd_pure.yaml` + `vendors.yaml` SSOT -- no mocking of the
prompt builder.

RED-for-right-reason: the positive assertion below reads the captured stdout
for a `--phase D_DISTILL` dispatch and asserts the `AGENT_IDENTITY` section
names `nw-acceptance-designer` and NOT `nw-software-crafter` -- this FAILS
today with a clear semantic `AssertionError` (the section renders
`Agent: nw-software-crafter` for D_DISTILL), never a crash/import/collection
error.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.common.in_process_cli import run_cli_in_process


_REPO_ROOT = Path(__file__).resolve().parents[3]


def _run_dispatch(argv: list[str]) -> tuple[int, str, str]:
    """Drive the REAL `des dispatch` CLI in-process (Layer-2 default)."""
    return run_cli_in_process(["dispatch", *argv], cwd=_REPO_ROOT)


def _base_argv(*, phase: str, slice_id: str = "slice-01") -> list[str]:
    return [
        "--mode",
        "atdd_pure",
        "--project-id",
        "probe-x",
        "--slice",
        slice_id,
        "--phase",
        phase,
        "--intent",
        "author the slice's acceptance test",
        "--repo-root",
        str(_REPO_ROOT),
    ]


def _agent_identity_line(stdout: str) -> str:
    """Extract the `Agent: ...` line following the `# AGENT_IDENTITY` header."""
    lines = stdout.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "# AGENT_IDENTITY":
            for following in lines[index + 1 :]:
                if following.startswith("Agent:"):
                    return following
            return ""
    return ""


def test_dispatch_d_distill_names_acceptance_designer_not_crafter() -> None:
    """POSITIVE (the bug, active-RED today): a `--phase D_DISTILL` dispatch's
    `AGENT_IDENTITY` section must name `nw-acceptance-designer` -- the agent
    that authors acceptance tests -- and must NOT name `nw-software-crafter`,
    which never authors tests (ADR-025 test/fix authorship split).
    """
    exit_code, stdout, stderr = _run_dispatch(
        _base_argv(phase="D_DISTILL", slice_id="feature-end")
    )

    assert exit_code == 0, (
        f"expected `des dispatch --phase D_DISTILL` to succeed -- got "
        f"exit_code={exit_code}, stderr={stderr!r}"
    )

    agent_identity_line = _agent_identity_line(stdout)

    assert "nw-acceptance-designer" in agent_identity_line, (
        "expected the D_DISTILL dispatch's AGENT_IDENTITY section to name "
        "'nw-acceptance-designer' (the AT-authoring agent per ADR-025) -- "
        f"got AGENT_IDENTITY line={agent_identity_line!r} from full "
        f"stdout={stdout!r} (exit_code={exit_code}, stderr={stderr!r}). "
        "`_section_body`'s AGENT_IDENTITY entry in "
        "src/des/cli/dispatch.py hardcodes 'nw-software-crafter' for every "
        "phase -- see this test module's docstring for the fix direction."
    )
    assert "nw-software-crafter" not in agent_identity_line, (
        "the D_DISTILL dispatch's AGENT_IDENTITY section must NOT name "
        "'nw-software-crafter' -- the crafter is SLIM and never authors "
        f"tests (ADR-025) -- got AGENT_IDENTITY line={agent_identity_line!r}"
    )


@pytest.mark.negative_at
def test_dispatch_a_green_still_names_the_crafter() -> None:
    """NEGATIVE AT (no-overcorrection control -- must stay GREEN before AND
    after the fix): a `--phase A_GREEN` dispatch (an implementation phase)
    must STILL name `nw-software-crafter` in its `AGENT_IDENTITY` section.
    The fix routes ONLY the AT-authoring phase (`D_DISTILL`) to
    `nw-acceptance-designer` -- it must not misroute implementation phases.
    """
    exit_code, stdout, stderr = _run_dispatch(_base_argv(phase="A_GREEN"))

    assert exit_code == 0, (
        f"expected `des dispatch --phase A_GREEN` to succeed -- got "
        f"exit_code={exit_code}, stderr={stderr!r}"
    )

    agent_identity_line = _agent_identity_line(stdout)

    assert "nw-software-crafter" in agent_identity_line, (
        "expected the A_GREEN dispatch's AGENT_IDENTITY section to still "
        "name 'nw-software-crafter' (an implementation phase, unaffected "
        f"by the D_DISTILL fix) -- got AGENT_IDENTITY "
        f"line={agent_identity_line!r} from full stdout={stdout!r} "
        f"(exit_code={exit_code}, stderr={stderr!r})."
    )
    assert "nw-acceptance-designer" not in agent_identity_line, (
        "the A_GREEN dispatch's AGENT_IDENTITY section must NOT name "
        "'nw-acceptance-designer' -- that agent is scoped to AT-authoring "
        f"phases only -- got AGENT_IDENTITY line={agent_identity_line!r}"
    )

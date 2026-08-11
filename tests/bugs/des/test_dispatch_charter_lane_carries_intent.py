"""Regression AT -- a charter-lane dispatch silently discards ``--intent``.

Closes two duplicate pile entries naming one defect:
``dispatch-charter-lane-silently-drops-intent`` and
``des-dispatch-charter-lane-drops-intent``.

RCA (complete, confirmed empirically -- do NOT re-investigate).
``_section_body`` (``src/des/cli/dispatch.py``) renders ``TASK_CONTEXT`` as a
conditional expression whose intent append binds to the ``else`` arm ONLY::

    "TASK_CONTEXT": (
        f"Slice {slice_id} of feature {feature_id}.\\n"
        if runs_tests
        else f"Wave {wave} for feature {feature_id} (scope: {slice_id}).\\n"
        + (f"{intent}\\n" if intent else "")
    ),

so a ``runs_tests=True`` dispatch gets NO intent in ``TASK_CONTEXT``.  The
other intent-carrying body, ``ATDD_PURE_PHASES``, is not in the charter lane's
section set at all: charter is a PHASELESS lane
(``des.domain.lane_profile.PHASELESS_LANES``), non-code-facing, and declares no
``DES-PHASE``.  Its ``runs_tests`` nonetheless resolves True -- visible in the
rendered ``BOUNDARY_RULES`` ("Stay within slice <id>'s value statement", the
``runs_tests=True`` wording).  Net effect: NO section of a charter envelope
carries the operator's intent text, and nothing says so.  Reproduced live::

    des dispatch --mode atdd_pure --project-id probe --slice slice-01 \\
        --lane charter --intent "PROBE_TOKEN_XYZ"

-> the emitted envelope contains no ``PROBE_TOKEN_XYZ`` anywhere.  The intent
is the ONLY channel by which the spine tells a charter author WHAT to charter;
dropping it silently is a GDP-6 silent-wrong, not a cosmetic gap.

Driving surface: the production CLI EDGE ``des.cli.__main__`` driven through
``run_module_in_process`` -- the SAME boundary
``tests/des/unit/cli/test_des_dispatch_generator.py`` already establishes for
``des dispatch``.  No production module is imported for its internals, so a
failure here is a semantic ``AssertionError`` about observable CLI output,
never an import/collection error (RED-not-BROKEN).

Author-only regression test: no production code is touched by this file.

covers: des-dispatch-charter-lane-drops-intent
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.common.in_process_cli import run_module_in_process


# tests/bugs/des/<this file> -> parents[3] is the checkout root.
_REPO_ROOT = Path(__file__).resolve().parents[3]

_PROJECT_ID = "probe"
_SLICE_ID = "slice-01"


def _dispatch_env() -> dict[str, str]:
    """Env with `src` importable and the freshness gate silenced.

    Without ``NWAVE_FRESHNESS=skip`` the CLI prints a
    ``des.runtime.freshness.*`` JSON line ahead of the envelope -- an unrelated
    cross-cutting concern that would confound the stdout assertions here.
    """
    env = dict(os.environ)
    src = str(_REPO_ROOT / "src")
    env["PYTHONPATH"] = (
        f"{src}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else src
    )
    env["NWAVE_FRESHNESS"] = "skip"
    return env


def _run_charter_dispatch(*extra: str) -> tuple[int, str, str]:
    return run_module_in_process(
        "des.cli.__main__",
        "dispatch",
        "--mode",
        "atdd_pure",
        "--project-id",
        _PROJECT_ID,
        "--slice",
        _SLICE_ID,
        "--lane",
        "charter",
        *extra,
        cwd=_REPO_ROOT,
        env=_dispatch_env(),
    )


def _section_body(envelope: str, section_id: str) -> str:
    """Return the body text under ``# <section_id>``, up to the next header.

    Parses the rendered envelope the way a reading agent does -- by its
    ``# SECTION`` headers -- rather than reaching into the generator's private
    body map, so the assertion keys on the OBSERVABLE artifact.
    """
    lines = envelope.splitlines()
    header = f"# {section_id}"
    try:
        start = lines.index(header) + 1
    except ValueError:  # pragma: no cover - guarded by an assertion at call site
        raise AssertionError(
            f"section header {header!r} absent from the rendered envelope:\n{envelope}"
        ) from None
    body: list[str] = []
    for line in lines[start:]:
        if line.startswith("# ") and line[2:].strip().isupper():
            break
        body.append(line)
    return "\n".join(body)


# ---------------------------------------------------------------------------
# AT-1 (positive) -- the intent text SURVIVES into the charter envelope
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "intent",
    [
        "PROBE_TOKEN_XYZ",
        "Charter the token-billing expectation for the drain lane",
        'observable: "des dispatch" drops --intent (quotes, colons & dashes)',
    ],
    ids=["marker-token", "prose", "punctuation-heavy"],
)
def test_charter_lane_envelope_carries_the_intent_text(intent: str) -> None:
    """``des dispatch --lane charter --intent "<text>"`` must render that text
    VERBATIM inside the envelope -- the intent is the only channel carrying the
    operator's instruction to a phaseless, non-code-facing charter author.

    FAILS TODAY: no section of a charter envelope carries the intent
    (``TASK_CONTEXT``'s ``runs_tests=True`` arm omits it; ``ATDD_PURE_PHASES``,
    the other intent-bearing body, is not in the charter section set).
    """
    exit_code, envelope, stderr = _run_charter_dispatch("--intent", intent)

    assert exit_code == 0, (
        f"charter dispatch must succeed; got exit {exit_code}. "
        f"stdout={envelope!r} stderr={stderr!r}"
    )
    assert intent in envelope, (
        f"the --intent text {intent!r} is ABSENT from the rendered charter "
        "envelope -- the operator's instruction was silently discarded, so the "
        "charter author is dispatched with no statement of what to charter.\n"
        f"envelope=\n{envelope}"
    )


def test_charter_lane_task_context_is_where_the_intent_lands() -> None:
    """The intent must reach ``TASK_CONTEXT`` specifically -- the section whose
    declared job is stating the task, and the one a charter author reads for it.

    A charter envelope has no ``ATDD_PURE_PHASES`` section (phaseless lane), so
    ``TASK_CONTEXT`` is the only body that can carry the instruction; asserting
    the section, not merely the envelope, keeps a fix from parking the text in
    an unrelated header where the reader will not look for it.
    """
    intent = "PROBE_TOKEN_TASK_CONTEXT"
    exit_code, envelope, stderr = _run_charter_dispatch("--intent", intent)

    assert exit_code == 0, f"exit {exit_code}; stderr={stderr!r}"
    assert "# TASK_CONTEXT" in envelope, (
        f"TASK_CONTEXT header missing from the charter envelope:\n{envelope}"
    )

    body = _section_body(envelope, "TASK_CONTEXT")
    assert intent in body, (
        f"the --intent text {intent!r} did not reach TASK_CONTEXT. "
        f"TASK_CONTEXT body was:\n{body!r}\nfull envelope=\n{envelope}"
    )


# ---------------------------------------------------------------------------
# AT-2 (negative oracle) -- an ABSENT intent renders NO artifact
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_charter_lane_without_intent_never_renders_a_placeholder_artifact() -> None:
    """A charter dispatch with NO ``--intent`` must render a clean
    ``TASK_CONTEXT`` -- no literal ``None``, no ``''``, no orphan blank-slot
    line.

    This is the negative oracle for AT-1: an unconditional
    ``+ f"{intent}\\n"`` would satisfy AT-1 while leaking a placeholder into
    every intent-less charter dispatch.  It PASSES today and must keep passing
    after the fix -- a fix that trades one silent-wrong for a visible-wrong is
    not a fix.
    """
    exit_code, envelope, stderr = _run_charter_dispatch()

    assert exit_code == 0, f"exit {exit_code}; stderr={stderr!r}"
    body = _section_body(envelope, "TASK_CONTEXT")

    for artifact in ("None", "''", '""'):
        assert artifact not in body, (
            f"intent-less charter TASK_CONTEXT leaked the placeholder "
            f"{artifact!r} -- an absent intent must render nothing at all, not "
            f"a stringified empty value. body=\n{body!r}"
        )

    substantive = [line for line in body.splitlines() if line.strip()]
    # charter is a PHASELESS lane (runs_tests=False), so TASK_CONTEXT renders
    # the wave/scope statement, never the runs_tests=True "Slice ... of
    # feature ..." wording -- `--wave` defaults to "deliver" when unset.
    assert substantive == [
        f"Wave deliver for feature {_PROJECT_ID} (scope: {_SLICE_ID})."
    ], (
        "intent-less charter TASK_CONTEXT must carry exactly the wave/scope "
        f"statement and nothing else; got {substantive!r}"
    )

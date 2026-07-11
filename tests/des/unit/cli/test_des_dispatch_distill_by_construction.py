"""Regression ATs -- friction #79 (`des dispatch` violates its own BY-
CONSTRUCTION promise). Sister-repro'd + hit 3x in one session as hand-refined
DESIGN_CONTEXT rejections.

``des dispatch``'s module docstring (`src/des/cli/dispatch.py`) claims the
rendered prompt "PASSES the dispatch gates BY CONSTRUCTION -- the system
produces the checked artifact". Two ways that promise is broken today:

(A) ``--phase D_DISTILL --slice slice-01`` EMITS (exit 0) a prompt carrying
    ``DES-SLICE : slice-01``. ``D_DISTILL`` is in `FEATURE_END_PHASES`
    (`des.domain.atdd_pure_phases`) -- its ONLY coherent scope is the
    `feature-end` literal (ADR-028 D6, Option A). The REAL production guard
    the runtime applies -- `classify_atdd_pure_dispatch(DesMarkerParser().
    parse(prompt))` (`des.domain.des_marker_parser`), consumed by
    `PreToolUseService.validate` / `_validate_atdd_pure_dispatch` to emit
    `ATDD_PURE_DISPATCH_DEFECTIVE` -- classifies this exact combination
    'defective'. Confirmed empirically (2026-07-11):

        markers = DesMarkerParser().parse(prompt)
        classify_atdd_pure_dispatch(markers)  # -> 'defective'

    `des dispatch` should either REFUSE (self-explaining, non-zero exit) or
    AUTO-CORRECT `--slice` to `feature-end` when `--phase D_DISTILL` (or any
    other `FEATURE_END_PHASES` member) -- never silently hand the operator a
    prompt the runtime guard is guaranteed to reject.

(B) A generator-rendered `DESIGN_CONTEXT` body must itself satisfy
    `design_context_carries_architecture` (`des.domain.
    design_context_content_check`) -- pinned here as a REGRESSION INVARIANT
    so a future edit to `_section_body`'s `DESIGN_CONTEXT` template cannot
    silently drift it back into a citation-free / templated-placeholder body
    (the class of defect that caused 3 hand-refined-dispatch rejections in
    one session today).

Driving surface: mirrors `test_des_dispatch_generator.py` exactly (P1-P4
in-process active-RED pattern) -- the STABLE `des.cli.__main__` entry driven
via subprocess (`python -m des.cli.__main__ dispatch ...`), never an internal
import of the generator module. The guard-classification assertions then
apply the REAL production predicates (`classify_atdd_pure_dispatch`,
`design_context_carries_architecture`) to the subprocess's stdout -- the
same functions the runtime hook applies, not a re-invented check.

CONTRACT_SHAPE: bounded-change (closed-world rendering + a closed-world
guard-classification predicate; no unbounded input space -> example-based,
no PBT).

covers: friction #79 (dispatch violates by-construction)
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from des.domain.atdd_pure_phases import FEATURE_END_PHASES
from des.domain.des_marker_parser import DesMarkerParser, classify_atdd_pure_dispatch
from des.domain.design_context_content_check import design_context_carries_architecture


_REPO_ROOT = Path(__file__).resolve().parents[4]

_DES_SLICE_PATTERN = re.compile(r"<!--\s*DES-SLICE\s*:\s*(\S+)\s*-->")
_PER_SLICE_SCOPE_SHAPE = re.compile(r"slice-\d+[a-z]?")

# The DESIGN_CONTEXT section body -- everything after its header line, up to
# the next `# SECTION` header (or end of string if it were the last section).
_DESIGN_CONTEXT_BODY_PATTERN = re.compile(
    r"# DESIGN_CONTEXT\n(.*?)(?:\n# [A-Z_]+\n|\Z)", re.DOTALL
)


# ---------------------------------------------------------------------------
# Driving-port helpers (subprocess boundary -- mirrors test_des_dispatch_
# generator.py's `_dispatch_argv` / `_dispatch_env` / `_run_dispatch` exactly)
# ---------------------------------------------------------------------------


def _dispatch_argv(*args: str) -> list[str]:
    return [sys.executable, "-m", "des.cli.__main__", "dispatch", *args]


def _dispatch_env() -> dict[str, str]:
    env = dict(os.environ)
    src = str(_REPO_ROOT / "src")
    env["PYTHONPATH"] = (
        f"{src}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else src
    )
    env["NWAVE_FRESHNESS"] = "skip"
    return env


def _run_dispatch(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _dispatch_argv(*args),
        capture_output=True,
        text=True,
        timeout=30,
        env=_dispatch_env(),
    )


def _design_context_body(prompt: str) -> str:
    match = _DESIGN_CONTEXT_BODY_PATTERN.search(prompt)
    assert match is not None, (
        f"no # DESIGN_CONTEXT section found in the generated prompt:\n{prompt}"
    )
    return match.group(1)


# ---------------------------------------------------------------------------
# AT-1 -- POSITIVE: a D_DISTILL + slice-01 dispatch can NEVER carry a
# guard-rejected combination (defect A, the sister repro)
# ---------------------------------------------------------------------------


def test_distill_phase_dispatch_never_carries_a_guard_rejected_combination() -> None:
    """`des dispatch --phase D_DISTILL --slice slice-01` must either (a) REFUSE
    with a self-explaining non-zero exit naming the fix (use `feature-end`),
    OR (b) emit a prompt whose rendered `DES-SLICE` is `feature-end` (auto-
    corrected) -- the emitted-or-refused OUTCOME can never be a prompt the
    real runtime guard (`classify_atdd_pure_dispatch`) classifies
    'defective'.

    FAILS TODAY: exit 0, and the rendered prompt echoes `DES-SLICE :
    slice-01` verbatim -- `classify_atdd_pure_dispatch` on the parsed markers
    returns 'defective' (confirmed empirically 2026-07-11), reproducing the
    sister's repro one Task dispatch later, at the runtime hook.
    """
    result = _run_dispatch(
        "--mode",
        "atdd_pure",
        "--project-id",
        "demo",
        "--slice",
        "slice-01",
        "--phase",
        "D_DISTILL",
    )

    if result.returncode != 0:
        combined = result.stdout + result.stderr
        assert "Traceback" not in combined, (
            "a D_DISTILL + slice-01 refusal must be a clean, self-explaining "
            f"error, never a Python traceback. combined={combined!r}"
        )
        assert "feature-end" in combined, (
            "a refused D_DISTILL + slice-01 dispatch must NAME the fix (use "
            f"the feature-end scope). combined={combined!r}"
        )
        return

    prompt = result.stdout
    markers = DesMarkerParser().parse(prompt)
    classification = classify_atdd_pure_dispatch(markers)
    assert classification != "defective", (
        "des dispatch emitted (exit 0) a D_DISTILL + slice-01 prompt that "
        "the REAL production guard (classify_atdd_pure_dispatch, the exact "
        "predicate PreToolUseService.validate applies) classifies "
        "'defective' -- the by-construction promise "
        "(src/des/cli/dispatch.py module docstring) is broken: the operator "
        "gets a prompt that WILL be rejected one Task-dispatch later at the "
        "runtime hook. Fix: refuse when --phase is a FEATURE_END_PHASES "
        "member and --slice is not 'feature-end', or auto-correct --slice "
        "to 'feature-end'. "
        f"rendered DES-SLICE={markers.slice_id!r} prompt=\n{prompt}"
    )


# ---------------------------------------------------------------------------
# AT-2 -- INVARIANT (regression pin): a generated DESIGN_CONTEXT body always
# satisfies the real content-presence predicate (defect B)
# ---------------------------------------------------------------------------


def test_generated_design_context_satisfies_the_real_architecture_predicate() -> None:
    """A generated A_GREEN dispatch's `# DESIGN_CONTEXT` body must satisfy the
    REAL production predicate `design_context_carries_architecture` -- the
    exact check `AtddPurePromptValidator` / the dispatch-gate hand-refinement
    path applies (the class of defect that caused 3 hand-refined-dispatch
    rejections in one session today, per
    `des.domain.design_context_content_check`).

    Pins the invariant so a future edit to `_section_body`'s DESIGN_CONTEXT
    template (`src/des/cli/dispatch.py`) cannot silently drift it back into a
    citation-free / templated-placeholder body without this test going RED.

    Passes today -- a regression pin, not a repro of an open defect.
    """
    result = _run_dispatch(
        "--mode",
        "atdd_pure",
        "--project-id",
        "demo",
        "--slice",
        "slice-01",
        "--phase",
        "A_GREEN",
    )
    assert result.returncode == 0, (
        f"expected exit 0; got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )

    body = _design_context_body(result.stdout)
    assert design_context_carries_architecture(body), (
        "the generator's own rendered # DESIGN_CONTEXT body does NOT satisfy "
        "design_context_carries_architecture -- the SAME predicate the "
        "dispatch gates apply to a hand-refined dispatch. A generator that "
        "cannot pass its own checked predicate is not gate-valid BY "
        f"CONSTRUCTION. body={body!r}"
    )


# ---------------------------------------------------------------------------
# AT-3 -- NEGATIVE, universal (`_never_`): no FEATURE_END_PHASES dispatch may
# render a per-slice DES-SLICE scope, across every FEATURE_END_PHASES member
# and every --slice input
# ---------------------------------------------------------------------------


def test_feature_end_phase_dispatch_never_renders_a_per_slice_des_slice_marker() -> (
    None
):
    """A generated dispatch prompt for ANY `FEATURE_END_PHASES` member (today:
    `D_DISTILL`) must NEVER carry a per-slice-shaped `DES-SLICE` marker
    (`slice-\\d+[a-z]?`) -- regardless of the `--slice` value supplied on the
    command line. `FEATURE_END_PHASES` membership means the phase's ONLY
    coherent scope is the `feature-end` literal (ADR-028 D6, Option A); a
    per-slice `DES-SLICE` on such a phase is unconditionally incoherent.

    FAILS TODAY, for every probed `--slice` value: the generator's
    `_build_prompt` echoes `args.slice_id` verbatim with no phase-aware
    correction -- the same defect AT-1 reproduces once, restated here as the
    universal claim across `FEATURE_END_PHASES` x several slice inputs.
    """
    assert "D_DISTILL" in FEATURE_END_PHASES, (
        "fixture assumption: D_DISTILL is a FEATURE_END_PHASES member -- "
        "update this test if the phase-identity SSOT changes."
    )

    for phase in sorted(FEATURE_END_PHASES):
        for slice_value in ("slice-01", "slice-02", "slice-05"):
            result = _run_dispatch(
                "--mode",
                "atdd_pure",
                "--project-id",
                "demo",
                "--slice",
                slice_value,
                "--phase",
                phase,
            )
            if result.returncode != 0:
                # A refusal is an acceptable resolution of defect A (AT-1) --
                # it trivially satisfies "never renders a per-slice scope"
                # since nothing was rendered.
                continue

            slice_match = _DES_SLICE_PATTERN.search(result.stdout)
            assert slice_match is not None, (
                f"phase={phase} slice={slice_value}: exit 0 but no DES-SLICE "
                f"marker found in output:\n{result.stdout}"
            )
            rendered_scope = slice_match.group(1)
            assert not _PER_SLICE_SCOPE_SHAPE.fullmatch(rendered_scope), (
                f"des dispatch --phase {phase} --slice {slice_value} rendered "
                f"a per-slice DES-SLICE scope ({rendered_scope!r}) for a "
                "FEATURE_END_PHASES member -- its only coherent scope is the "
                "'feature-end' literal (ADR-028 D6, Option A). This prompt is "
                "guaranteed to be classified 'defective' by "
                f"classify_atdd_pure_dispatch. prompt=\n{result.stdout}"
            )

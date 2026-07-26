"""Acceptance contract for the DESIGN dispatch ownership envelope.

The tests drive the public ``des`` CLI only.  They pin the artifact that an
orchestrator receives from ``des dispatch`` and the policy boundary that
receives a hand-authored prompt before a DESIGN owner can run.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[5]
FEATURE_ID = "design-dispatch-ownership-envelope"


def _des(*args: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    """Invoke the checkout's ``des`` dispatcher through its public CLI."""
    environment = os.environ.copy()
    source_path = str(REPO_ROOT / "src")
    environment["PYTHONPATH"] = f"{source_path}{os.pathsep}{REPO_ROOT}" + (
        f"{os.pathsep}{environment['PYTHONPATH']}"
        if environment.get("PYTHONPATH")
        else ""
    )
    return subprocess.run(
        [sys.executable, "-m", "des", *args],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _render_design_dispatch(workspace: Path) -> subprocess.CompletedProcess[str]:
    return _des(
        "dispatch",
        "--mode",
        "atdd_pure",
        "--project-id",
        FEATURE_ID,
        "--slice",
        "feature-end",
        "--wave",
        "design",
        "--repo-root",
        str(REPO_ROOT),
        cwd=workspace,
    )


def _verify_design_owner_prompt(
    prompt_path: Path, *, repo_root: Path
) -> subprocess.CompletedProcess[str]:
    return _des(
        "verify-wave-dispatch",
        "--subagent-type",
        "nw-solution-architect",
        "--prompt-path",
        str(prompt_path),
        "--repo-root",
        str(repo_root),
        "--session-id",
        "design-ownership-envelope-at",
        cwd=repo_root,
    )


def test_des_dispatch_design_prompt_owns_canonical_sections_and_runs_readiness(
    tmp_path: Path,
) -> None:
    """A generated DESIGN prompt must carry the non-substitutable ownership contract."""
    (tmp_path / ".git").mkdir()
    rendered = _render_design_dispatch(tmp_path)

    assert rendered.returncode == 0, (
        "WHAT: `des dispatch --wave design` did not render a prompt; "
        "WHY: the system must produce the DESIGN handoff artifact by construction; "
        "HOW: make `des dispatch` render the DESIGN envelope successfully.\n"
        f"stdout={rendered.stdout}\nstderr={rendered.stderr}"
    )
    prompt = rendered.stdout
    expected_envelope = (
        f"nw-solution-architect owns docs/feature/{FEATURE_ID}/feature-delta.md "
        "canonical DESIGN sections `## Reuse Analysis` and "
        "`## Prefactoring Assessment`."
    )
    assert expected_envelope in prompt, (
        "WHAT: the generated DESIGN prompt omits its canonical-section ownership "
        "envelope; WHY: ownership of Reuse Analysis and Prefactoring Assessment "
        "must be unambiguous in feature-delta.md; HOW: have `des dispatch` emit "
        "the nw-solution-architect ownership sentence verbatim."
    )
    assert "Standalone design documents never substitute" in prompt, (
        "WHAT: the generated DESIGN prompt permits an implicit standalone-document "
        "substitute; WHY: feature-delta.md is the canonical DESIGN surface; HOW: "
        "make `des dispatch` state that standalone design documents never substitute."
    )
    assert "Before handoff, run `des verify-readiness-pre-dispatch`" in prompt, (
        "WHAT: the generated DESIGN prompt has no pre-handoff readiness execution "
        "mandate; WHY: ownership is not complete until readiness is observed; HOW: "
        "make `des dispatch` require `des verify-readiness-pre-dispatch` before handoff."
    )


@pytest.mark.negative_at
def test_wave_dispatch_guard_rejects_marked_design_prompt_without_ownership_envelope(
    tmp_path: Path,
) -> None:
    """A marker-valid but envelope-invalid hand-authored DESIGN prompt is refused."""
    (tmp_path / ".git").mkdir()
    prompt_path = tmp_path / "hand-authored-design-prompt.md"
    prompt_path.write_text(
        "\n".join(
            (
                "<!-- DES-VALIDATION : required -->",
                f"<!-- DES-PROJECT-ID : {FEATURE_ID} -->",
                "<!-- DES-MODE : atdd_pure -->",
                "<!-- DES-SLICE : feature-end -->",
                "<!-- DES-WAVE : design -->",
                "# AGENT_IDENTITY",
                "Agent: nw-solution-architect",
                "# TASK_CONTEXT",
                "Author DESIGN output.",
            )
        ),
        encoding="utf-8",
    )

    guarded = _verify_design_owner_prompt(prompt_path, repo_root=tmp_path)

    assert guarded.returncode == 1, (
        "WHAT: the wave-dispatch guard allowed a hand-authored DESIGN prompt that "
        "carries DES markers but lacks the ownership envelope; WHY: marker validity "
        "alone cannot protect canonical feature-delta ownership; HOW: make the guard "
        "reject it and name `des dispatch` as the producing remedy.\n"
        f"stdout={guarded.stdout}\nstderr={guarded.stderr}"
    )
    refusal = f"{guarded.stdout}\n{guarded.stderr}"
    assert "des dispatch" in refusal, (
        "WHAT: the ownership-envelope refusal omits its producing remedy; WHY: an "
        "operator needs a safe correction rather than a hand-authored workaround; "
        "HOW: state WHAT/WHY/HOW and name `des dispatch` in the refusal.\n"
        f"output={refusal}"
    )


@pytest.mark.parametrize(
    ("wave", "agent"),
    (("design", "nw-solution-architect"), ("discuss", "nw-product-owner")),
)
def test_valid_design_and_non_design_dispatches_remain_allowed(
    tmp_path: Path, wave: str, agent: str
) -> None:
    """Valid generated DESIGN and non-DESIGN dispatches retain their on-spine path."""
    (tmp_path / ".git").mkdir()
    rendered = _des(
        "dispatch",
        "--mode",
        "atdd_pure",
        "--project-id",
        FEATURE_ID,
        "--slice",
        "feature-end",
        "--wave",
        wave,
        "--repo-root",
        str(REPO_ROOT),
        cwd=tmp_path,
    )
    assert rendered.returncode == 0, (
        f"WHAT: `des dispatch --wave {wave}` failed to render; WHY: a valid "
        "on-spine wave must remain dispatchable; HOW: preserve the existing "
        f"{wave} generation path.\nstdout={rendered.stdout}\nstderr={rendered.stderr}"
    )
    prompt_path = tmp_path / f"{wave}-generated-prompt.md"
    prompt_path.write_text(rendered.stdout, encoding="utf-8")
    guarded = _des(
        "verify-wave-dispatch",
        "--subagent-type",
        agent,
        "--prompt-path",
        str(prompt_path),
        "--repo-root",
        str(tmp_path),
        "--session-id",
        "design-ownership-envelope-regression",
        cwd=tmp_path,
    )
    assert guarded.returncode == 0, (
        f"WHAT: the guard rejected a valid generated {wave} dispatch; WHY: the "
        "ownership envelope must harden malformed DESIGN prompts without regressing "
        f"valid {wave} work; HOW: preserve the matching DES-WAVE allow path.\n"
        f"stdout={guarded.stdout}\nstderr={guarded.stderr}"
    )

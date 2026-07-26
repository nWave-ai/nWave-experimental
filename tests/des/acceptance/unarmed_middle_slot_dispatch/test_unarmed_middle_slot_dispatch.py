"""Acceptance contract for the charter-armed C_REVIEWER_AUDIT dispatch slot.

The public ``des dispatch`` CLI must choose the middle-slot recipient from a
slice-matching expectation charter, not from the phase name alone.  These
tests deliberately drive the real CLI in a temporary project tree; they do
not import the dispatcher or inspect its implementation.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[5]
FEATURE_ID = "unarmed-middle-slot-dispatch"
SLICE_ID = "slice-00"


def _dispatch_environment() -> dict[str, str]:
    """Run the checkout's public CLI without unrelated freshness output."""
    environment = os.environ.copy()
    source_path = str(REPO_ROOT / "src")
    environment["PYTHONPATH"] = f"{source_path}{os.pathsep}{REPO_ROOT}" + (
        f"{os.pathsep}{environment['PYTHONPATH']}"
        if environment.get("PYTHONPATH")
        else ""
    )
    environment["NWAVE_FRESHNESS"] = "skip"
    return environment


def _project_tree(tmp_path: Path) -> Path:
    """Create a disposable project whose shipped dispatch assets stay real."""
    project = tmp_path / "project"
    project.mkdir()
    (project / ".git").mkdir()
    (project / "nWave").symlink_to(REPO_ROOT / "nWave", target_is_directory=True)
    return project


def _write_charter(project: Path, name: str, spec_rows: str) -> Path:
    charter = project / "docs" / "product" / "expectations" / FEATURE_ID / f"{name}.md"
    charter.parent.mkdir(parents=True, exist_ok=True)
    charter.write_text(
        "\n".join(
            (
                f"# {name}",
                "",
                "## Intent",
                "A user can observe the promised outcome through the real surface.",
                "",
                f"Spec rows: {spec_rows}",
            )
        ),
        encoding="utf-8",
    )
    return charter


def _dispatch(project: Path) -> subprocess.CompletedProcess[str]:
    """Render the C_REVIEWER_AUDIT envelope through the public ``des`` CLI."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "des",
            "dispatch",
            "--mode",
            "atdd_pure",
            "--project-id",
            FEATURE_ID,
            "--slice",
            SLICE_ID,
            "--wave",
            "deliver",
            "--phase",
            "C_REVIEWER_AUDIT",
            "--repo-root",
            str(project),
        ],
        cwd=project,
        env=_dispatch_environment(),
        capture_output=True,
        text=True,
        check=False,
    )


def test_charters_written_but_this_slice_unmapped_is_refused_never_substituted(
    tmp_path: Path,
) -> None:
    """Charters exist for this feature and this slice is not in one: an OMISSION.

    The refusal is the contract.  Handing the slot to the technical reviewer
    instead would return an AT-completeness audit to an operator who asked for
    an examine -- the two answer different questions (one reads the code, the
    other refuses to by construction), and nothing in the envelope would say
    which one had run.  Refusing NAMES what is missing; substituting HIDES it.

    Note this is the UNMAPPED case, distinct from a feature with no charter
    directory at all (the practice simply is not adopted there): only the
    omission is refused, so adopting charters never becomes a trap for repos
    that have not.
    """
    project = _project_tree(tmp_path)
    _write_charter(project, "other-slice", "slice-99")

    rendered = _dispatch(project)

    assert rendered.returncode != 0, (
        "WHAT: a C_REVIEWER_AUDIT dispatch rendered an envelope although no "
        f"charter maps {SLICE_ID} while OTHER slices are chartered; "
        "WHY: silently substituting a role turns a missing charter into a "
        "different kind of verdict the operator never asked for; "
        "HOW: refuse and name the missing charter.\n"
        f"stdout={rendered.stdout}\nstderr={rendered.stderr}"
    )
    assert "nw-acceptance-designer-reviewer" not in rendered.stdout, (
        "WHAT: the refusal still emitted a technical-reviewer envelope; "
        "WHY: a refusal that also renders the substitute is the substitution "
        "it claims to refuse; "
        "HOW: return before any prompt is emitted.\n"
        f"stdout={rendered.stdout}"
    )
    for token in ("WHAT:", "WHY:", "HOW:", SLICE_ID):
        assert token in rendered.stderr, (
            f"WHAT: the refusal does not carry {token!r}; "
            "WHY: a refusal that does not say what is missing, why it matters, "
            "and how to produce it forces the operator to investigate; "
            "HOW: state the triad and name the unmapped slice.\n"
            f"stderr={rendered.stderr}"
        )


def test_matching_charter_routes_only_vera_to_the_real_surface(tmp_path: Path) -> None:
    """A unique matching charter arms the non-code-facing EXAMINE envelope."""
    project = _project_tree(tmp_path)
    charter = _write_charter(project, "observable-outcome", SLICE_ID)

    rendered = _dispatch(project)

    assert rendered.returncode == 0, (
        "WHAT: a charter-armed C_REVIEWER_AUDIT dispatch did not render; "
        "WHY: a matching expectation charter must activate EXAMINE; "
        "HOW: resolve the unique charter mapping before producing the dispatch.\n"
        f"stdout={rendered.stdout}\nstderr={rendered.stderr}"
    )
    prompt = rendered.stdout
    assert "Agent: nw-user-examiner" in prompt, (
        "WHAT: a matching charter did not select Vera; WHY: the armed middle slot is "
        "execution-observation, not code review; HOW: route a unique matching charter to "
        "nw-user-examiner.\n"
        f"prompt=\n{prompt}"
    )
    assert str(charter.relative_to(project)) in prompt, (
        "WHAT: the armed envelope does not name its charter; WHY: Vera may receive only the "
        "charter as her specification; HOW: include the matching charter path.\n"
        f"prompt=\n{prompt}"
    )
    assert "walk the promised outcome through the real surface" in prompt.lower(), (
        "WHAT: the armed envelope lacks the real-surface action; WHY: EXAMINE certifies what "
        "a user can observe; HOW: instruct Vera to walk the charter through the real surface.\n"
        f"prompt=\n{prompt}"
    )
    forbidden_technical_material = ("feature-delta.md", "acceptance-test", "15-item")
    assert not any(
        material in prompt.lower() for material in forbidden_technical_material
    ), (
        "WHAT: the charter-only EXAMINE envelope leaked technical review material; WHY: Vera's "
        "independence depends on not receiving design/code/AT context; HOW: emit only the charter "
        "and real-surface action for an armed slot.\n"
        f"prompt=\n{prompt}"
    )


@pytest.mark.parametrize("armed", (False, True), ids=("unarmed", "armed"))
def test_generated_middle_slot_prompt_never_claims_no_code_access_while_auditing_code(
    tmp_path: Path, armed: bool
) -> None:
    """Role wording and work instructions must describe the same evidence mode."""
    project = _project_tree(tmp_path)
    if armed:
        _write_charter(project, "observable-outcome", SLICE_ID)

    prompt = _dispatch(project).stdout.lower()
    claims_no_code_access = "no code access" in prompt or "no source access" in prompt
    audits_technical_material = (
        "audit source" in prompt or "audit acceptance tests" in prompt
    )

    assert not (claims_no_code_access and audits_technical_material), (
        "WHAT: the generated middle-slot prompt contradicts its own access boundary; WHY: an "
        "examiner cannot truthfully be denied code access while asked to audit source/ATs; HOW: "
        "make the armed prompt charter-only or use the technical reviewer envelope.\n"
        f"prompt=\n{prompt}"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("charters", "diagnostic"),
    (
        ((("malformed", "not-a-slice"),), "malformed"),
        ((("first", SLICE_ID), ("second", SLICE_ID)), "ambiguous"),
    ),
    ids=("malformed-mapping", "ambiguous-mapping"),
)
def test_middle_slot_refuses_malformed_or_ambiguous_charter_mapping(
    tmp_path: Path,
    charters: tuple[tuple[str, str], ...],
    diagnostic: str,
) -> None:
    """Negative AT: malformed or non-unique mapping must degrade loud, never guess."""
    project = _project_tree(tmp_path)
    for name, spec_rows in charters:
        _write_charter(project, name, spec_rows)

    rendered = _dispatch(project)
    output = f"{rendered.stdout}\n{rendered.stderr}"

    assert rendered.returncode != 0, (
        "WHAT: des dispatch chose a middle-slot role from a malformed or ambiguous charter map; "
        "WHY: an arbitrary reviewer/examiner choice corrupts the gate's evidence mode; HOW: stop "
        "with an INDETERMINATE diagnostic that names the mapping problem.\n"
        f"case={diagnostic}\noutput=\n{output}"
    )
    assert "INDETERMINATE" in output and diagnostic in output.lower(), (
        "WHAT: the charter-map refusal is not a loud, actionable degradation; WHY: operators must "
        "be able to repair the charter map before dispatch; HOW: emit INDETERMINATE and name whether "
        "the mapping is malformed or ambiguous.\n"
        f"case={diagnostic}\noutput=\n{output}"
    )
    assert "Agent:" not in rendered.stdout, (
        "WHAT: dispatch rendered an agent after an indeterminate charter map; WHY: a role selected "
        "after ambiguity is arbitrary; HOW: refuse before producing an AGENT_IDENTITY envelope.\n"
        f"case={diagnostic}\noutput=\n{output}"
    )

"""Public oracle: `des project --html`, the layer the human reads.

`docs/architecture/adr-ssot-document-model.md`, «Feature Brief — The Human
Layer»: «The SSOT files serve agents. The delta files serve the delivery
pipeline. Neither is designed for human consumption.»  The handover and the
typed design facts are exactly that -- machine-first -- and the human who has to
choose between an interactive and an autonomous session reads neither happily.

`docs/product/architecture/ADR-BOARD-001-shared-slice-state-projection.md` fixes
what such a page may be: «The shared slice-state model is a projection function,
never a fourth persisted store», recomputed on every read. So this step reads
the two owned facts, writes ONE html file and nothing else, and holds no state
of its own. Run it twice over an unchanged repository and the page is the same.

It carries NO new content. Every line of the page is either a label the step
terminals already use or a value read verbatim from the owned state, and the
renderer is the one that already exists -- `des.adapters.driven.rendering.
nwave_document`, with the nWave palette and its dark mode. A second renderer or
a second stylesheet would be a second answer to "what does an nWave document
look like".
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    asked,
    block,
    git,
    nexts,
    observation,
)


REQUEST = "one Request whose state a human reads before choosing how to run it"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
TARGET = "product_value.py"
HANDOVER = Path(".nwave") / "des" / "handover.json"


def design_facts() -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "bound the value to its typed design facts",
            "design_facts": {
                "targets": [{"path": TARGET, "decision": "CREATE_NEW"}],
                "paradigm": "object_oriented",
                "decisions": ["one opaque semantic decision"],
                "oracle": ORACLE,
                "acceptance_supports": [SUPPORT],
                "verification": [["python", "-m", "pytest", ORACLE]],
            },
        }
    }


def bound(root: Path, step) -> None:
    assert (
        step(
            "po",
            "--repo-root",
            str(root),
            answers=[accepted_values("A", "B")],
            stdin=REQUEST,
        )[0]
        == 0
    )
    assert (
        step(
            "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
        )[0]
        == 0
    )


def test_the_page_carries_the_request_the_values_and_the_typed_facts(
    root: Path, step, tmp_path: Path, turns: Path
) -> None:
    bound(root, step)
    out = tmp_path / "projection.html"
    code, stdout, stderr = step("project", "--repo-root", str(root), "--html", str(out))
    assert code == 0, stdout + stderr
    lines = block(stdout, stderr)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert lines["HTML"] == str(out)
    page = out.read_text()
    assert REQUEST in page
    assert observation("A") in page
    assert observation("B") in page
    assert ORACLE in page
    assert TARGET in page
    assert "object_oriented" in page
    assert "python -m pytest" in page
    # Rendered through the ONE nWave renderer: its palette and its provenance
    # banner, never a second stylesheet invented here.
    assert "--paper" in page
    assert "Projection, not source" in page
    assert str(HANDOVER) in page
    assert asked(turns) == ["nw-product-owner", "nw-solution-architect"]


def test_the_projection_writes_only_the_page_and_never_a_store(
    root: Path, step, tmp_path: Path
) -> None:
    """ADR-BOARD-001: a visualization is a projection, never a fourth store."""
    bound(root, step)
    before = (root / HANDOVER).read_bytes()
    refs_before = git(root, "for-each-ref", "--format=%(refname)")
    head_before = git(root, "rev-parse", "HEAD")
    status_before = git(root, "status", "--porcelain")

    out = tmp_path / "projection.html"
    assert step("project", "--repo-root", str(root), "--html", str(out))[0] == 0

    assert (root / HANDOVER).read_bytes() == before
    assert git(root, "for-each-ref", "--format=%(refname)") == refs_before
    assert git(root, "rev-parse", "HEAD") == head_before
    assert git(root, "status", "--porcelain") == status_before


def test_the_same_state_renders_the_same_page(root: Path, step, tmp_path: Path) -> None:
    """Recomputed on every read, so it cannot drift from what it projects."""
    bound(root, step)
    first, second = tmp_path / "a.html", tmp_path / "b.html"
    assert step("project", "--repo-root", str(root), "--html", str(first))[0] == 0
    assert step("project", "--repo-root", str(root), "--html", str(second))[0] == 0
    assert first.read_text() == second.read_text()


def test_the_page_says_what_each_value_already_carries(
    root: Path, step, tmp_path: Path
) -> None:
    bound(root, step)
    out = tmp_path / "projection.html"
    step("project", "--repo-root", str(root), "--html", str(out))
    page = out.read_text()
    text = re.sub(r"<[^>]+>", " ", page)
    assert "bound" in text
    assert "absent" in text


def test_an_undecomposed_repository_refuses_and_names_the_step_that_starts_one(
    root: Path, step, tmp_path: Path
) -> None:
    out = tmp_path / "projection.html"
    code, stdout, stderr = step("project", "--repo-root", str(root), "--html", str(out))
    assert code == 1
    assert block(stdout, stderr)["WHAT"] == "HandoverAbsent"
    assert not out.exists()
    assert any(item.startswith(f"des po --repo-root {root}") for item in nexts(stdout))

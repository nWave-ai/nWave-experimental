"""Public observations for the provider-free DISCUSS constructor."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance.design_document_construction.test_design_document_construction import (
    MANIFEST,
)
from tests.des.acceptance.steps_for_the_orchestrator.conftest import base_repository

from des.application import handover
from des.application.delivery_steps import DeliverySteps
from des.application.handover import HandoverValue, read_handover
from des.domain.delivery_disposition import Disposition


def payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "request": "Let a user choose a widget color.",
        "outcomes": ["A user can choose and verify a widget color."],
        "scope": {
            "in_scope": ["Widget color selection."],
            "out_of_scope": {
                "applicability": "not_applicable",
                "reason": "No exclusions are needed for this brief.",
                "items": [],
            },
        },
        "decisions": ["Keep color selection in the Widget boundary."],
        "values": [
            {"observation": "A user can select a widget color.", "dependencies": []},
            {
                "observation": "A user sees the selected widget color.",
                "dependencies": ["A user can select a widget color."],
            },
        ],
    }


def call(root: Path, raw: str) -> tuple[int, str, str]:
    return run_cli_in_process(
        ["discuss", "--repo-root", str(root), "--input", "-"],
        cwd=root,
        stdin_text=raw,
        catch_all=True,
    )


def test_public_discuss_constructs_ordered_document_and_handover_without_provider(
    tmp_path: Path,
) -> None:
    root = base_repository(tmp_path / "repository")
    raw = json.dumps(payload())
    code, out, err = call(root, raw)
    document = root / "docs/product/brief.md"
    handover = root / ".nwave/des/handover.json"
    assert code == 0 and "NEXT: des design --repo-root <root> --value 1" in out + err
    assert all(
        section in document.read_text()
        for section in (
            "## Request",
            "## Outcomes",
            "## Scope",
            "### In scope",
            "### Out of scope",
            "## Observations",
            "## Decisions",
            "## Values",
        )
    )
    stored = read_handover(handover.read_bytes())
    assert not hasattr(stored, "what")
    assert [value.observation for value in stored.values] == [
        item["observation"] for item in payload()["values"]
    ]
    before = (document.read_bytes(), handover.read_bytes())
    assert call(root, raw)[0] == 0 and before == (
        document.read_bytes(),
        handover.read_bytes(),
    )


def test_public_discuss_configuration_and_malformed_input_refuse_before_writing(
    tmp_path: Path, monkeypatch
) -> None:
    root, home = base_repository(tmp_path / "repository"), tmp_path / "home"
    (home / ".nwave").mkdir(parents=True)
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(home))
    (home / ".nwave/config.json").write_text(
        json.dumps({"documents": {"discuss": {"destination": "docs/global.md"}}})
    )
    (root / ".nwave").mkdir()
    (root / ".nwave/config.json").write_text(
        json.dumps({"documents": {"discuss": {"destination": "docs/project.md"}}})
    )
    malformed = payload()
    malformed["values"] = []
    code, out, err = call(root, json.dumps(malformed))
    assert code != 0 and "InvalidDiscussDocument" in out + err
    assert not (root / "docs/project.md").exists()
    assert not (root / ".nwave/des/handover.json").exists()
    assert call(root, json.dumps(payload()))[0] == 0
    assert (root / "docs/project.md").is_file() and not (
        root / "docs/global.md"
    ).exists()


def test_public_design_binds_discuss_graph_and_replay_retains_facts(
    tmp_path: Path,
) -> None:
    root = base_repository(tmp_path / "repository")
    raw = json.dumps(payload())
    assert call(root, raw)[0] == 0
    code, out, err = run_cli_in_process(
        ["design", "--repo-root", str(root), "--value", "1", "--input", "-"],
        cwd=root,
        stdin_text=json.dumps(MANIFEST),
        catch_all=True,
    )
    assert code == 0, out + err
    handover = root / ".nwave/des/handover.json"
    bound = handover.read_bytes()
    assert call(root, raw)[0] == 0 and handover.read_bytes() == bound


def test_public_discuss_preserves_ordered_multi_dependencies_through_design_and_refuses_reverse(
    tmp_path: Path,
) -> None:
    root = base_repository(tmp_path / "repository")
    supplied = payload()
    values = supplied["values"]
    assert isinstance(values, list)
    first, second = values
    values.append(
        {
            "observation": "A user can verify the selected widget color.",
            "dependencies": [first["observation"], second["observation"]],
        }
    )
    raw = json.dumps(supplied)
    assert call(root, raw)[0] == 0
    code, out, err = run_cli_in_process(
        ["design", "--repo-root", str(root), "--value", "3", "--input", "-"],
        cwd=root,
        stdin_text=json.dumps(MANIFEST),
        catch_all=True,
    )
    assert code == 0, out + err
    document = root / "docs/product/brief.md"
    handover = root / ".nwave/des/handover.json"
    before = (document.read_bytes(), handover.read_bytes())
    reversed_dependencies = payload()
    reversed_values = reversed_dependencies["values"]
    assert isinstance(reversed_values, list)
    a, b = reversed_values
    reversed_values.append(
        {
            "observation": "A user can verify the selected widget color.",
            "dependencies": [b["observation"], a["observation"]],
        }
    )
    code, out, err = call(root, json.dumps(reversed_dependencies))
    assert code != 0
    assert "values[2].dependencies must be ordered preceding observations" in out + err
    assert before == (document.read_bytes(), handover.read_bytes())


def test_discuss_markdown_keeps_multiline_semantic_text_out_of_heading_and_table_control(
    tmp_path: Path,
) -> None:
    root = base_repository(tmp_path / "repository")
    supplied = payload()
    supplied["request"] = "Request prose\n## Impostor request section"
    supplied["outcomes"] = ["Outcome prose\n## Impostor outcomes section"]
    scope = supplied["scope"]
    assert isinstance(scope, dict)
    scope["in_scope"] = ["Scope prose\n### Impostor scope section"]
    out_of_scope = scope["out_of_scope"]
    assert isinstance(out_of_scope, dict)
    out_of_scope["applicability"] = "applicable"
    out_of_scope["reason"] = "Reason prose\n## Impostor reason section"
    out_of_scope["items"] = ["Out prose\n### Impostor out section"]
    supplied["decisions"] = ["Decision prose\n## Impostor decision section"]
    values = supplied["values"]
    assert isinstance(values, list)
    values[0]["observation"] = "First | observation\n## Impostor value section"
    values[1]["dependencies"] = [values[0]["observation"]]
    assert call(root, json.dumps(supplied))[0] == 0
    rendered = (root / "docs/product/brief.md").read_text()
    headings = [line for line in rendered.splitlines() if line.startswith("#")]
    assert headings == [
        "# Product brief",
        "## Request",
        "## Outcomes",
        "## Scope",
        "### In scope",
        "### Out of scope",
        "## Observations",
        "## Decisions",
        "## Values",
    ]
    assert "    ## Impostor request section" in rendered
    assert "First \\| observation<br>## Impostor value section" in rendered


def test_discuss_race_reports_indeterminate_with_authority_and_untouched_winner(
    tmp_path: Path, monkeypatch
) -> None:
    root = base_repository(tmp_path / "repository")
    winner_values = (HandoverValue("External winner observation.", (), None),)
    winner_raw = handover._canonical_bytes(
        "Let a user choose a widget color.", winner_values
    )
    original_create = handover._create_if_absent

    def external_creator(path: Path, raw: bytes) -> bool | handover.Blocked:
        assert path == handover.handover_path(root)
        assert original_create(path, winner_raw) is True
        return False

    monkeypatch.setattr(handover, "_create_if_absent", external_creator)
    outcome = DeliverySteps().discuss_document(root, json.dumps(payload()))
    document = root / "docs/product/brief.md"
    stored = root / ".nwave/des/handover.json"
    assert outcome.disposition is Disposition.Indeterminate
    assert (
        outcome.failure is not None and outcome.failure.what == "HandoverGraphMismatch"
    )
    assert outcome.facts == (
        "DOCUMENT: docs/product/brief.md",
        f"DOCUMENT-SHA256: {hashlib.sha256(document.read_bytes()).hexdigest()}",
    )
    assert stored.read_bytes() == winner_raw

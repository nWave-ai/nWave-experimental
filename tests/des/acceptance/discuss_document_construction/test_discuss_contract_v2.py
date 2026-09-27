"""DISCUSS schema_version 2: every section explicit, help contract really runs."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance.discuss_document_construction.test_discuss_document_construction import (
    call,
    payload,
)
from tests.des.acceptance.steps_for_the_orchestrator.conftest import base_repository

from des.adapters.driven.rendering.nwave_document import render
from des.domain.discuss_contract import (
    CURRENT_VERSION,
    DESCRIBE_FLAG,
    EXAMPLE_MARKER,
    MINIMAL_EXAMPLE,
)


def v2() -> dict[str, object]:
    return copy.deepcopy(MINIMAL_EXAMPLE)


def brief(root: Path) -> str:
    return (root / "docs/product/brief.md").read_text()


def nothing_written(root: Path) -> bool:
    return (
        not (root / "docs/product/brief.md").exists()
        and not (root / ".nwave/des/handover.json").exists()
    )


def describe() -> tuple[int, str, str]:
    return run_cli_in_process(
        ["discuss", "--describe-input"], cwd=Path.cwd(), catch_all=True
    )


def test_described_example_runs_through_the_public_cli(tmp_path: Path) -> None:
    code, out, err = describe()
    assert code == 0, err
    assert f"schema_version {CURRENT_VERSION} (current)" in out
    assert "not_explored" in out and "generated" in out and "legacy" in out.lower()
    example = out.split(EXAMPLE_MARKER, 1)[1]
    assert json.loads(example) == MINIMAL_EXAMPLE
    root = base_repository(tmp_path / "repository")
    code, out, err = call(root, example)
    assert code == 0, out + err
    text = brief(root)
    assert text.count("_Not explored._") == 4 and "_Not run" in text


def test_help_states_version_required_fields_and_points_to_the_schema() -> None:
    code, out, err = run_cli_in_process(
        ["discuss", "--help"], cwd=Path.cwd(), catch_all=True
    )
    text = out + err
    assert code == 0
    assert "schema_version 2" in text and "quint_scenarios" in text
    assert "not_explored" in text and DESCRIBE_FLAG in text


@pytest.mark.parametrize("key", ["jtbd", "journey", "gherkin", "quint_scenarios"])
def test_v2_refuses_an_omitted_section_without_mutation(
    tmp_path: Path, key: str
) -> None:
    root = base_repository(tmp_path / "repository")
    document = v2()
    del document[key]
    code, out, err = call(root, json.dumps(document))
    assert code != 0 and "InvalidDiscussDocument" in out + err
    assert key in out + err and DESCRIBE_FLAG in out + err
    assert nothing_written(root)


def test_v2_explicit_unexpanded_sections_are_accepted_and_shown(
    tmp_path: Path,
) -> None:
    root = base_repository(tmp_path / "repository")
    assert call(root, json.dumps(v2()))[0] == 0
    text = brief(root)
    for heading in ("## Jobs to be done", "## User journey", "## Gherkin scenarios"):
        assert heading in text
    assert "Not explored" in render(text) and "Not run" in render(text)


def test_v2_provided_sections_render_their_fields(tmp_path: Path) -> None:
    root = base_repository(tmp_path / "repository")
    document = v2()
    document["jtbd"] = {
        "status": "provided",
        "human": [{"job": "Pick a color fast", "status": "confirmed"}],
    }
    document["journey"] = {
        "status": "provided",
        "steps": [
            {"step": "Open palette", "human_emotion": "curious", "status": "open"}
        ],
    }
    document["gherkin"] = {
        "status": "provided",
        "scenarios": [
            {
                "scenario": "Pick",
                "steps": ["Given a widget", "Then it is red"],
                "status": "proposed",
            }
        ],
    }
    document["quint_scenarios"] = {
        "status": "generated",
        "model": {"path": "m.qnt", "identity": "sha256:1"},
        "tool": {
            "name": "quint",
            "version": "0.25.0",
            "command": "quint run m.qnt --seed 7",
        },
        "trace": {"path": "t.itf.json"},
        "scenarios": [
            {"title": "T", "events": [{"trace_index": 0, "text": "User picks red"}]}
        ],
    }
    code, out, err = call(root, json.dumps(document))
    assert code == 0, out + err
    text = brief(root)
    html = render(text)
    for needle in (
        "Pick a color fast",
        "curious",
        "Then it is red",
        "--seed 7",
        "User picks red",
    ):
        assert needle in text and needle in html
    assert "_Not explored._" in text.split("### LLM")[1].split("## User journey")[0]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(jtbd={"status": "provided"}),
        lambda d: d.update(jtbd={"status": "not_explored", "human": []}),
        lambda d: d.update(jtbd={"human": [{"job": "x", "status": "open"}]}),
        lambda d: d.update(journey={"status": "provided", "steps": []}),
        lambda d: d.update(journey={"status": "not_explored", "steps": [1]}),
        lambda d: d.update(journey=[{"step": "s", "status": "open"}]),
        lambda d: d.update(gherkin={"status": "provided", "scenarios": "x"}),
        lambda d: d.update(gherkin={"status": ["provided"]}),
        lambda d: d.update(quint_scenarios={"status": "generated"}),
        lambda d: d.update(
            quint_scenarios={"status": "not_run", "trace": {"path": "t"}}
        ),
        lambda d: d.update(schema_version=3),
        lambda d: d.update(extra=1),
    ],
)
def test_v2_illegal_state_combinations_refuse_before_writing(
    tmp_path: Path, mutate
) -> None:
    root = base_repository(tmp_path / "repository")
    document = v2()
    mutate(document)
    code, out, err = call(root, json.dumps(document))
    assert code != 0 and "InvalidDiscussDocument" in out + err
    assert nothing_written(root)


def test_legacy_v1_input_still_passes(tmp_path: Path) -> None:
    root = base_repository(tmp_path / "repository")
    assert payload()["schema_version"] == 1
    assert call(root, json.dumps(payload()))[0] == 0
    assert brief(root).count("_Not explored._") == 4

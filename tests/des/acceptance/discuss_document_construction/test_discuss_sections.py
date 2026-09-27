"""DISCUSS always shows JTBD, journey, Gherkin and Quint sections, honestly."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.des.acceptance.discuss_document_construction.test_discuss_document_construction import (
    bind_design,
    call,
    call_replacing,
    payload,
    stored_values,
)
from tests.des.acceptance.steps_for_the_orchestrator.conftest import base_repository

from des.adapters.driven.rendering.nwave_document import render


def full() -> dict[str, object]:
    document = payload()
    document["jtbd"] = {
        "human": [{"job": "Pick a color I like | fast", "status": "confirmed"}],
        "llm": [{"job": "Receive the color as a closed enum", "status": "proposed"}],
    }
    document["journey"] = [
        {"step": "Open the palette", "human_emotion": "curious", "status": "proposed"},
        {"step": "Confirm the color", "status": "open"},
    ]
    document["gherkin"] = [
        {
            "scenario": "Choose a color",
            "steps": ["Given a widget", "When I pick red", "Then the widget is red"],
            "status": "confirmed",
        }
    ]
    document["quint_scenarios"] = {
        "status": "generated",
        "model": {"path": "models/color.qnt", "identity": "sha256:abc"},
        "tool": {
            "name": "quint",
            "version": "0.25.0",
            "command": "quint run color.qnt",
        },
        "trace": {"path": "traces/color.itf.json"},
        "scenarios": [
            {
                "title": "Pick then confirm",
                "events": [
                    {"trace_index": 0, "text": "The user picks red"},
                    {"trace_index": 1, "text": "The widget shows red"},
                ],
            }
        ],
    }
    return document


def brief(root: Path) -> str:
    return (root / "docs/product/brief.md").read_text()


def test_omitted_sections_are_still_visible_with_honest_placeholders(
    tmp_path: Path,
) -> None:
    root = base_repository(tmp_path / "repository")
    assert call(root, json.dumps(payload()))[0] == 0
    text = brief(root)
    for heading in (
        "## Jobs to be done",
        "### Human",
        "### LLM",
        "## User journey",
        "## Gherkin scenarios",
        "## Quint scenarios",
    ):
        assert heading in text
    assert text.count("_Not explored._") == 4
    assert "_Not run" in text
    html = render(text)
    assert "Not explored" in html and "Not run" in html


def test_populated_sections_survive_markdown_and_html(tmp_path: Path) -> None:
    root = base_repository(tmp_path / "repository")
    code, out, err = call(root, json.dumps(full()))
    assert code == 0, out + err
    text = brief(root)
    assert "- [confirmed] Pick a color I like | fast" in text
    assert "| Open the palette | curious | proposed |" in text
    assert "| Confirm the color | not explored | open |" in text
    assert "Then the widget is red" in text and "```gherkin" in text
    assert "[trace 1] The widget shows red" in text
    assert "models/color.qnt" in text and "not verified by DES" in text
    assert "_Not run" not in text
    html = render(text)
    for needle in (
        "Pick a color I like | fast",
        "curious",
        "Then the widget is red",
        "traces/color.itf.json",
        "The user picks red",
    ):
        assert needle in html


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(jtbd={}),
        lambda d: d.update(jtbd={"human": [{"job": "x", "status": "agreed"}]}),
        lambda d: d.update(journey=[]),
        lambda d: d.update(journey=[{"step": "s", "status": "open", "emotion": "x"}]),
        lambda d: d.update(gherkin=[{"scenario": "s", "steps": [], "status": "open"}]),
        lambda d: d.update(
            gherkin=[{"scenario": "s", "steps": ["a\n```"], "status": "open"}]
        ),
        lambda d: d.update(quint_scenarios={"status": "not_run", "model": {}}),
        lambda d: d.update(quint_scenarios={"status": "generated"}),
        lambda d: d["quint_scenarios"]["scenarios"][0]["events"][0].update(
            trace_index=-1
        ),
        lambda d: d.update(
            gherkin=[
                {
                    "scenario": "s",
                    "steps": ["Given x", "```", "## Quint scenarios"],
                    "status": "open",
                }
            ]
        ),
        lambda d: d.update(
            gherkin=[{"scenario": "s", "steps": ["~~~"], "status": "open"}]
        ),
        lambda d: d.update(quint_scenarios={"status": ["generated"]}),
        lambda d: d.update(quint_scenarios={"status": {"not_run": 1}}),
        lambda d: d.update(unknown=1),
    ],
)
def test_malformed_sections_refuse_before_any_write(tmp_path: Path, mutate) -> None:
    root = base_repository(tmp_path / "repository")
    document = full()
    mutate(document)
    code, out, err = call(root, json.dumps(document))
    assert code != 0 and "InvalidDiscussDocument" in out + err
    assert not (root / "docs/product/brief.md").exists()
    assert not (root / ".nwave/des/handover.json").exists()


def test_quint_not_run_needs_no_evidence_and_replace_current_preserves_graph(
    tmp_path: Path,
) -> None:
    root = base_repository(tmp_path / "repository")
    assert call(root, json.dumps(payload()))[0] == 0
    bind_design(root, 1)
    bind_design(root, 2)
    before = [value["authority"] for value in stored_values(root)]
    corrected = full()
    corrected["quint_scenarios"] = {"status": "not_run"}
    code, out, err = call_replacing(root, json.dumps(corrected))
    assert code == 0, out + err
    text = brief(root)
    assert "Pick a color I like" in text and "_Not run" in text
    assert [value["authority"] for value in stored_values(root)] == before


def test_carriage_return_stays_inside_its_table_cell(tmp_path: Path) -> None:
    root = base_repository(tmp_path / "repository")
    document = payload()
    document["journey"] = [
        {"step": "Open\r## Forged\rpalette", "status": "open"},
    ]
    assert call(root, json.dumps(document))[0] == 0
    text = brief(root)
    assert "\r" not in text
    assert [line for line in text.splitlines() if line.startswith("## Forged")] == []


def test_journey_renders_qualitative_arc_without_invented_intensity(
    tmp_path: Path,
) -> None:
    root = base_repository(tmp_path / "repository")
    document = full()
    document["journey"].append(
        {
            "step": "Evil ``` <b>x</b>",
            "human_emotion": "<i>uneasy</i>",
            "status": "confirmed",
        }
    )
    code, out, err = call(root, json.dumps(document))
    assert code == 0, out + err
    text = brief(root)
    assert "Qualitative journey arc (stated emotions; NOT measured intensity)" in text
    assert "[proposed] 1. Open the palette" in text
    assert "emotion: curious" in text
    assert "[open] 2. Confirm the color" in text
    assert "emotion: UNKNOWN (not explored)" in text
    assert "[confirmed] 3." in text
    assert sum(line.startswith("```") for line in text.splitlines()) % 2 == 0
    html = render(text)
    assert "&lt;b&gt;x&lt;/b&gt;" in html and "<b>x</b>" not in html


def test_unexplored_journey_shows_unknown_arc_status(tmp_path: Path) -> None:
    root = base_repository(tmp_path / "repository")
    assert call(root, json.dumps(payload()))[0] == 0
    assert "Journey arc: UNKNOWN (journey not explored)" in brief(root)

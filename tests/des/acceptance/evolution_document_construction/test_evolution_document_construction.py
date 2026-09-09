"""Public observations for the provider-free feature-evolution constructor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance.steps_for_the_orchestrator.conftest import base_repository


DEFAULT = Path("docs/evolution/2026-09-09-widget-release.md")


def value() -> dict[str, object]:
    return {
        "schema_version": 1,
        "date": "2026-09-09",
        "feature_id": "widget-release",
        "purpose": "First line\n## Content, not an injected heading",
        "key_decisions": ["Keep evidence before cleanup."],
        "delivered_work": ["Released the Widget feature."],
        "verification_results": ["Focused native tests passed."],
        "problems": {
            "applicability": "not_applicable",
            "reason": "No delivery problem was observed.",
            "items": [],
        },
        "lessons": {
            "applicability": "applicable",
            "reason": "The delivery produced a reusable lesson.",
            "items": ["Keep durable evidence before cleanup."],
        },
        "durable_artifacts": [
            {"label": "CI evidence", "path": "https://example.invalid/runs/1"}
        ],
    }


def call(root: Path, raw: str) -> tuple[int, str, str]:
    return run_cli_in_process(
        ["evolution", "--repo-root", str(root), "--input", "-"],
        cwd=root,
        stdin_text=raw,
        catch_all=True,
    )


def terminal(out: str, err: str) -> dict[str, str]:
    return {
        key: item
        for line in (out + "\n" + err).splitlines()
        for key, sep, item in [line.partition(": ")]
        if sep
    }


def test_public_evolution_uses_default_global_and_project_destinations_and_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home / ".claude"))
    monkeypatch.setenv("CODEX_HOME", str(home / ".codex"))
    global_root, project_root, default_root = (
        base_repository(tmp_path / name) for name in ("global", "project", "default")
    )
    (home / ".nwave").mkdir()
    (home / ".nwave/config.json").write_text(
        json.dumps({"documents": {"evolution": {"destination": "docs/global.md"}}})
    )
    (project_root / ".nwave").mkdir()
    (project_root / ".nwave/config.json").write_text(
        json.dumps({"documents": {"evolution": {"destination": "docs/project.md"}}})
    )
    raw = json.dumps(value())
    for root, destination in (
        (global_root, Path("docs/global.md")),
        (project_root, Path("docs/project.md")),
    ):
        code, out, err = call(root, raw)
        assert (
            code == 0
            and terminal(out, err)["DELIVERY-OUTCOME"] == "Success"
            and (root / destination).is_file()
        )
        before = (root / destination).read_bytes()
        retry = call(root, raw)
        assert retry[0] == 0 and (root / destination).read_bytes() == before
    (home / ".nwave/config.json").unlink()
    code, out, err = call(default_root, raw)
    assert code == 0 and terminal(out, err)["DELIVERY-OUTCOME"] == "Success"
    before = (default_root / DEFAULT).read_bytes()
    assert (
        call(default_root, raw)[0] == 0
        and (default_root / DEFAULT).read_bytes() == before
    )
    text = (default_root / DEFAULT).read_text()
    assert (
        "    ## Content, not an injected heading" in text
        and "TURNS-BOUGHT: 0" in call(default_root, raw)[1]
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda item: item.update({"schema_version": 1.0}),
        lambda item: item.update({"date": "2026-02-30"}),
        lambda item: item.update(
            {
                "durable_artifacts": [
                    {"label": "bad]\\n## injected", "path": "ftp://invalid"}
                ]
            }
        ),
    ],
)
def test_invalid_public_evolution_input_refuses_before_writing(
    tmp_path: Path, mutate
) -> None:
    root = base_repository(tmp_path / "invalid")
    invalid = value()
    mutate(invalid)
    raw = json.dumps(invalid)
    code, out, err = call(root, raw)
    assert (
        code != 0
        and terminal(out, err)["DELIVERY-OUTCOME"] == "Refusal"
        and "Traceback" not in out + err
    )
    assert not (root / DEFAULT).exists()

"""AT -- `des charter-scaffold --seed-mode direct-value` (K4 route fix).

Adds the honest direct-value seed mode for ordinary Auto M/L work driven by
a user directive: no feature-delta/Slice Plan is read, exactly ONE charter
scaffold is produced, and the immutable `--value` text is copied into Intent
VERBATIM -- same skeleton/idempotency contract as bug-observable /
brownfield-discovery. `--feature-id` is OPTIONAL: when omitted, it is
derived mechanically (never by LLM convention) from the same `--value` seed,
and reported in the existing JSON payload's `feature_id` field.

Driving surface: `des.cli.charter_scaffold.main(argv) -> int` invoked
IN-PROCESS against a `tmp_path` fixture repo (composition-root driving
port -- Mandate 16, driving-port-only boundary). No subprocess fork.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


VALUE_TEXT = "Operator sees last night's backup succeeded before relying on it"

TEMPLATE_SKELETON = """# <intent, as a human sentence>
ID: EXP-<feature>-<n> · Spec rows: <R…> · Persona: <who>

## Intent
<the value statement: what the user accomplishes, why it matters>

## Preconditions
<start recipe: how to run the system from a clean state, seed state>

## Charter
Explore <area> via <surface: browser/CLI/API> to verify <intent>.

## Expected observations (oracle)
- <observable outcome, user language>
- <negative: what must NOT happen>

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
"""


def _seed_repo(repo_root: Path) -> None:
    template_dir = repo_root / "nWave" / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "expectation-charter.md").write_text(
        TEMPLATE_SKELETON, encoding="utf-8"
    )


def _intent_section(content: str) -> str:
    lines = content.splitlines()
    try:
        start = lines.index("## Intent") + 1
    except ValueError:
        return ""
    body: list[str] = []
    for line in lines[start:]:
        if line.startswith("##"):
            break
        body.append(line)
    return "\n".join(body)


def _invoke(
    repo_root: Path,
    capsys,
    *,
    feature_id: str | None,
    value: str | None,
) -> tuple[int, dict]:
    from des.cli.charter_scaffold import main

    argv = ["--seed-mode", "direct-value"]
    if feature_id is not None:
        argv += ["--feature-id", feature_id]
    if value is not None:
        argv += ["--value", value]
    argv += ["--repo-root", str(repo_root), "--format", "json"]

    exit_code = main(argv)
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


def test_direct_value_with_omitted_feature_id_derives_it_deterministically_and_fills_intent_verbatim(
    tmp_path: Path, capsys
) -> None:
    """Happy path: no --feature-id supplied -- the CLI derives one
    mechanically from --value (deterministic, same on every run), creates
    exactly ONE scaffold, and the Intent carries --value VERBATIM."""
    _seed_repo(tmp_path)

    exit_code, payload = _invoke(tmp_path, capsys, feature_id=None, value=VALUE_TEXT)

    assert exit_code == 0
    derived_feature_id = payload["feature_id"]
    assert derived_feature_id  # non-empty, derived mechanically
    assert len(payload["created"]) == 1

    expectations_dir = (
        tmp_path / "docs" / "product" / "expectations" / derived_feature_id
    )
    created_files = sorted(p.name for p in expectations_dir.glob("*.md"))
    assert created_files == payload["created"]

    content = (expectations_dir / created_files[0]).read_text(encoding="utf-8")
    intent_body = _intent_section(content)
    assert intent_body.strip("\n") == VALUE_TEXT

    # Deterministic: a second, independent invocation derives the SAME
    # feature id from the same --value (no run-varying disambiguator).
    tmp_path_2 = tmp_path.parent / (tmp_path.name + "-rederive")
    tmp_path_2.mkdir()
    _seed_repo(tmp_path_2)
    _, payload_2 = _invoke(tmp_path_2, capsys, feature_id=None, value=VALUE_TEXT)
    assert payload_2["feature_id"] == derived_feature_id


def test_direct_value_second_run_is_idempotent(tmp_path: Path, capsys) -> None:
    """Idempotent re-run: running twice does not overwrite/re-create the
    scaffold; a fresh-PO edit made between runs survives untouched."""
    _seed_repo(tmp_path)
    feature_id = "reads-last-nights-backup-status"

    first_exit, first_payload = _invoke(
        tmp_path, capsys, feature_id=feature_id, value=VALUE_TEXT
    )
    assert first_exit == 0
    assert len(first_payload["created"]) == 1

    expectations_dir = tmp_path / "docs" / "product" / "expectations" / feature_id
    scaffold_path = next(expectations_dir.glob("*.md"))
    sentinel = "SENTINEL: fresh-PO-authored oracle, must survive re-run\n"
    scaffold_path.write_text(sentinel, encoding="utf-8")

    second_exit, second_payload = _invoke(
        tmp_path, capsys, feature_id=feature_id, value=VALUE_TEXT
    )

    assert second_exit == 0
    assert second_payload["created"] == []
    assert len(second_payload["skipped"]) == 1
    assert scaffold_path.read_text(encoding="utf-8") == sentinel


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(None, id="value_flag_omitted"),
        pytest.param("", id="value_blank_string"),
        pytest.param("   ", id="value_whitespace_only"),
    ],
)
def test_direct_value_missing_value_degrades_loud(
    tmp_path: Path, capsys, value: str | None
) -> None:
    """Blank input LOUD: a missing/blank --value must never produce a `.md`
    garbage file -- a LOUD non-zero reject naming 'value', never a silent
    no-op."""
    _seed_repo(tmp_path)

    exit_code, payload = _invoke(
        tmp_path, capsys, feature_id="whatever-feature", value=value
    )

    assert exit_code != 0
    assert payload["verdict"] == "missing-value"
    assert "value" in payload["detail"].lower()
    assert payload["created"] == []


@pytest.mark.parametrize(
    "hostile_value",
    [
        pytest.param("???", id="symbols_only"),
        pytest.param("日本語のみのテキストです", id="non_latin_only"),
    ],
)
def test_direct_value_hostile_value_with_omitted_feature_id_degrades_loud(
    tmp_path: Path, capsys, hostile_value: str
) -> None:
    """Hostile input LOUD: with --feature-id omitted (the common Auto path),
    a symbol-only/non-Latin --value has nothing mechanical to derive a
    feature id FROM -- this must degrade LOUD, never silently proceed with a
    degenerate feature id, and never write a scaffold anywhere."""
    _seed_repo(tmp_path)

    exit_code, payload = _invoke(tmp_path, capsys, feature_id=None, value=hostile_value)

    assert exit_code != 0
    assert payload["verdict"] == "undeterminable-feature-id"
    assert payload["created"] == []
    expectations_root = tmp_path / "docs" / "product" / "expectations"
    assert not expectations_root.is_dir() or not any(expectations_root.iterdir())

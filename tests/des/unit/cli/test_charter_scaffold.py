"""Executable contract for the single DeliveryContract charter producer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli import charter_scaffold


VALUE = "Operator sees the backup result before relying on it"
DELIVERY_ID = "backup-status"


def _invoke(root: Path, capsys, *extra: str) -> tuple[int, dict[str, object]]:
    code = charter_scaffold.main(
        [
            "--delivery-id",
            DELIVERY_ID,
            "--value",
            VALUE,
            "--repo-root",
            str(root),
            *extra,
        ]
    )
    return code, json.loads(capsys.readouterr().out)


def test_scaffold_creates_one_direct_member_and_is_idempotent(
    tmp_path: Path, capsys
) -> None:
    first_code, first = _invoke(tmp_path, capsys)
    second_code, second = _invoke(tmp_path, capsys)

    expected = (
        "docs/product/expectations/backup-status/"
        "operator-sees-the-backup-result-before-relying-on-it.md"
    )
    assert (first_code, first["created"], first["skipped"]) == (0, [expected], [])
    assert (second_code, second["created"], second["skipped"]) == (
        0,
        [],
        [expected],
    )
    content = (tmp_path / expected).read_text(encoding="utf-8")
    assert f"ID: {DELIVERY_ID}" in content
    assert f"## Intent\n{VALUE}" in content
    assert "<PublicStartRecipe:" in content


@pytest.mark.parametrize(
    ("delivery_id", "value", "verdict"),
    [
        ("../escape", VALUE, charter_scaffold.VERDICT_INVALID_DELIVERY_ID),
        ("UPPER", VALUE, charter_scaffold.VERDICT_INVALID_DELIVERY_ID),
        (DELIVERY_ID, "   ", charter_scaffold.VERDICT_MISSING_VALUE),
        (DELIVERY_ID, "--- !!!", charter_scaffold.VERDICT_UNSAFE_VALUE),
    ],
)
def test_invalid_identity_or_value_refuses_without_writing(
    tmp_path: Path,
    capsys,
    delivery_id: str,
    value: str,
    verdict: str,
) -> None:
    code = charter_scaffold.main(
        [
            "--delivery-id",
            delivery_id,
            "--value",
            value,
            "--repo-root",
            str(tmp_path),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code != 0
    assert payload["verdict"] == verdict
    assert not (tmp_path / "docs/product/expectations").exists()


def test_divergent_checkout_and_installed_templates_refuse_loudly(
    tmp_path: Path, capsys
) -> None:
    (tmp_path / ".git").mkdir()
    template = tmp_path / "nWave/templates/expectation-charter.md"
    template.parent.mkdir(parents=True)
    template.write_text(
        "## Template\n```markdown\n# divergent\n```\n", encoding="utf-8"
    )

    code, payload = _invoke(tmp_path, capsys)

    assert code != 0
    assert payload["verdict"] == charter_scaffold.VERDICT_AMBIGUOUS_CHARTER_TEMPLATE
    assert str(template) in str(payload["detail"])
    assert not (tmp_path / "docs/product/expectations").exists()


def test_legacy_seed_and_feature_flags_are_not_cli_vocabulary(
    tmp_path: Path, capsys
) -> None:
    with pytest.raises(SystemExit):
        charter_scaffold.main(
            [
                "--seed-mode",
                "direct-value",
                "--feature-id",
                DELIVERY_ID,
                "--value",
                VALUE,
                "--repo-root",
                str(tmp_path),
            ]
        )
    assert not (tmp_path / "docs/product/expectations").exists()

"""Regression (vacuous PASS via producer/checker drift): `des
verify-charter-filled` must refuse the RAW output of `des charter-scaffold`.

Bug: `verify_charter_filled` hardcoded three scaffold placeholder tokens
(`<start recipe: ...>`, `<observable outcome, user language>`,
`<negative: what must NOT happen>`) that drifted away from the placeholders
the REAL template `nWave/templates/expectation-charter.md` actually emits
(`<PublicStartRecipe: ...>`, `<positive observable outcome in user or
operator language>`, `Negative: <what must not happen>`). Consequence:
scaffolding a charter and immediately verifying it -- zero fields filled --
returned `"filled": true` / PASS. The gate checked nothing, while the PO
spec promised "A charter failing that gate never reaches dispatch".

Fix direction pinned here: the checker DERIVES its placeholder tokens from
the same template SSOT the scaffolder reads (one resolution, one parser --
`charter_scaffold._extract_template_skeleton`), so this drift class is
unrepresentable (GDP-0).

Driving surface (Mandate-13 driving-port-only, IN-PROCESS): the REAL
`charter_scaffold.main(argv)` produces the charter, then the REAL
`verify_charter_filled.main(argv)` judges it -- no fixture charter body that
could itself drift from the producer.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.charter_scaffold import main as scaffold_main
from des.cli.verify_charter_filled import main as verify_main


def test_raw_scaffold_output_is_refused_naming_the_unfilled_sections(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scaffold_code = scaffold_main(
        [
            "--delivery-id",
            "backup-status",
            "--value",
            "Operator sees the backup result before relying on it",
            "--repo-root",
            str(tmp_path),
        ]
    )
    scaffold_payload = json.loads(capsys.readouterr().out)
    assert scaffold_code == 0, scaffold_payload
    assert scaffold_payload["created"], scaffold_payload
    charter_path = tmp_path / scaffold_payload["created"][0]

    verify_code = verify_main(["--charter", str(charter_path), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    # The reviewer's falsifier: a raw, zero-fields-filled scaffold must
    # NEVER be reported FILLED -- and the refusal names BOTH judgment
    # sections still carrying template placeholders.
    assert verify_code != 0, payload
    assert payload["filled"] is False, payload
    assert payload["verdict"] == "FAIL", payload
    joined_missing = " ".join(payload["missing_sections"])
    assert "oracle" in joined_missing, payload
    assert "start-recipe" in joined_missing, payload

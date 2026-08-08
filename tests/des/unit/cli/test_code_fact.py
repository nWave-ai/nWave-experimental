"""Executable contract for the public vendor-neutral ``des code-fact`` query.

The target baseline deliberately has neither Graphify nor Tsunami.  These tests
drive the installed-runtime composition boundary in process: the CLI must expose
the already-shipped CodeFactChain and report which bundled tier answered.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _invoke(argv: list[str], capsys: pytest.CaptureFixture) -> tuple[int, dict]:
    from des.cli.code_fact import main

    exit_code = main(argv)
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


def test_python_target_uses_bundled_ast_and_reports_loud_paid_tier_skip(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    (tmp_path / "subject.py").write_text(
        "def target():\n    return 1\n\ndef caller():\n    return target()\n",
        encoding="utf-8",
    )

    exit_code, result = _invoke(
        ["query.callers-of", "target", "--root", str(tmp_path)], capsys
    )

    assert exit_code == 0
    assert result["provider"] == "ast"
    assert result["confidence"] == "approx"
    assert result["reason_code"] == "live-non-callable"
    assert result["payload"]["sites"]
    assert "health.gate.code-fact.tsunami-absent" in result["health_events"]


def test_non_python_target_degrades_to_bundled_text_floor_not_python_ast(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    (tmp_path / "subject.ts").write_text(
        "function target() { return 1; }\nfunction caller() { return target(); }\n",
        encoding="utf-8",
    )

    exit_code, result = _invoke(
        ["query.callers-of", "target", "--root", str(tmp_path)], capsys
    )

    assert exit_code == 0
    assert result["provider"] == "textsearch"
    assert result["confidence"] == "noisy"
    assert result["payload"]["sites"]
    assert "health.gate.code-fact.tsunami-absent" in result["health_events"]


@pytest.mark.parametrize("root_kind", ["mixed_tree", "single_typescript_file"])
def test_python_ast_never_masks_a_non_python_subject(
    root_kind: str, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    typescript = tmp_path / "subject.ts"
    typescript.write_text(
        "function target() { return 1; }\nfunction caller() { return target(); }\n",
        encoding="utf-8",
    )
    if root_kind == "mixed_tree":
        (tmp_path / "unrelated.py").write_text(
            "def unrelated():\n    return 1\n", encoding="utf-8"
        )
        root = tmp_path
    else:
        root = typescript

    exit_code, result = _invoke(
        ["query.callers-of", "target", "--root", str(root)], capsys
    )

    assert exit_code == 0
    assert result["provider"] == "textsearch"
    assert result["confidence"] == "noisy"
    assert result["payload"]["sites"]


@pytest.mark.parametrize("root_kind", ["mixed_tree", "single_typescript_file"])
def test_text_floor_reports_non_python_atoms_instead_of_a_false_empty_result(
    root_kind: str, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    typescript = tmp_path / "subject.ts"
    typescript.write_text(
        "export class Existing {}\nfunction helper() { return 1; }\n",
        encoding="utf-8",
    )
    if root_kind == "mixed_tree":
        (tmp_path / "unrelated.py").write_text(
            "def unrelated():\n    return 1\n", encoding="utf-8"
        )
        root = tmp_path
    else:
        root = typescript

    exit_code, result = _invoke(["query.atoms-in-file", "--root", str(root)], capsys)

    assert exit_code == 0
    assert result["provider"] == "textsearch"
    assert result["confidence"] == "noisy"
    assert {"Existing", "helper"} <= set(result["payload"]["atoms"])


@pytest.mark.parametrize(
    "capability",
    [
        "query.callers-of",
        "query.reads-of",
        "query.never-wired",
        "query.adr-section",
    ],
)
def test_symbol_shaped_capabilities_require_a_subject(
    capability: str, capsys: pytest.CaptureFixture
) -> None:
    from des.cli.code_fact import main

    with pytest.raises(SystemExit) as exc_info:
        main([capability])

    assert exc_info.value.code == 2
    assert "subject" in capsys.readouterr().err


def test_atoms_query_needs_no_dummy_subject_and_defaults_root_to_cwd(
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "subject.py").write_text(
        "class Existing:\n    pass\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    exit_code, result = _invoke(["query.atoms-in-file"], capsys)

    assert exit_code == 0
    assert result["provider"] == "ast"
    assert "Existing" in result["payload"]["atoms"]


def test_unknown_capability_is_an_argparse_usage_error(
    capsys: pytest.CaptureFixture,
) -> None:
    from des.cli.code_fact import main

    with pytest.raises(SystemExit) as exc_info:
        main(["query.not-real", "value"])

    assert exc_info.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_dispatcher_reaches_code_fact_without_a_parallel_entrypoint(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    from des.cli.__main__ import main

    (tmp_path / "subject.py").write_text(
        "def existing():\n    return 1\n", encoding="utf-8"
    )

    exit_code = main(
        ["code-fact", "query.never-wired", "existing", "--root", str(tmp_path)]
    )

    assert exit_code == 0
    result = json.loads(capsys.readouterr().out)
    assert set(result) == {
        "provider",
        "confidence",
        "reason_code",
        "payload",
        "health_events",
    }

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


def test_python_target_uses_bundled_ast_and_answers_with_a_conserved_trace(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """ADR-LA-001 D9 slice (b): the retired ``health_events`` paid-tier-absent
    skip is gone; the provider-neutral ``Resolution`` trace is the honest
    observation surface -- one clean ``answered`` entry naming the same
    provider that answered, with zero faults (LA1-L9)."""
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
    assert result["payload"]["sites"]
    answering_entries = [
        entry for entry in result["trace"] if entry["event"] == "answered"
    ]
    assert len(answering_entries) == 1
    assert answering_entries[0]["provider_id"] == "ast"
    assert answering_entries[0]["fault_count"] == 0
    assert answering_entries[0]["scope"] in {"complete", "filtered", "unfiltered"}


def test_non_python_target_degrades_to_bundled_text_floor_with_a_conserved_trace(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """ADR-LA-001 D9 slice (b): same trace-conservation proof as the AST case,
    over the TextSearch floor -- provider/scope/fault facts, never the retired
    ``health_events`` skip channel."""
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
    answering_entries = [
        entry for entry in result["trace"] if entry["event"] == "answered"
    ]
    assert len(answering_entries) == 1
    assert answering_entries[0]["provider_id"] == "textsearch"
    assert answering_entries[0]["fault_count"] == 0
    assert answering_entries[0]["scope"] in {"complete", "filtered", "unfiltered"}


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


@pytest.mark.parametrize(
    ("file_name", "file_source", "expected_provider"),
    [
        pytest.param(
            "subject.py",
            "def target():\n"
            "    return 1\n\n"
            "def observer():\n"
            "    observed = target\n"
            "    return observed\n",
            "ast",
            id="python_ast_scope",
        ),
        pytest.param(
            "subject.ts",
            "function target() { return 1; }\n"
            "function observer() {\n"
            "  const observed = target;\n"
            "  return observed;\n"
            "}\n",
            "textsearch",
            id="non_python_textsearch_floor",
        ),
    ],
)
def test_reads_of_reports_a_non_call_reference_while_callers_of_stays_absent(
    file_name: str,
    file_source: str,
    expected_provider: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    (tmp_path / file_name).write_text(file_source, encoding="utf-8")

    reads_exit_code, reads_result = _invoke(
        ["query.reads-of", "target", "--root", str(tmp_path)], capsys
    )
    callers_exit_code, callers_result = _invoke(
        ["query.callers-of", "target", "--root", str(tmp_path)], capsys
    )

    assert reads_exit_code == 0
    assert callers_exit_code == 0
    assert reads_result["provider"] == expected_provider
    assert callers_result["provider"] == expected_provider
    assert reads_result["payload"]["sites"]
    assert not callers_result["payload"]["sites"]


def test_recursive_call_is_reported_by_callers_of_not_hidden_by_the_definition(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    (tmp_path / "subject.py").write_text(
        "def target():\n    return target()\n", encoding="utf-8"
    )

    callers_exit_code, callers_result = _invoke(
        ["query.callers-of", "target", "--root", str(tmp_path)], capsys
    )
    reads_exit_code, reads_result = _invoke(
        ["query.reads-of", "target", "--root", str(tmp_path)], capsys
    )
    never_wired_exit_code, never_wired_result = _invoke(
        ["query.never-wired", "target", "--root", str(tmp_path)], capsys
    )

    assert callers_exit_code == 0
    assert reads_exit_code == 0
    assert never_wired_exit_code == 0
    assert callers_result["payload"]["sites"]
    assert not reads_result["payload"]["sites"]
    assert never_wired_result["payload"]["never_wired"] is False


def test_dispatcher_reaches_code_fact_without_a_parallel_entrypoint(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    from des.cli.__main__ import main
    from des.ports.code_fact_port import TRACE_DETAIL_MAX_CHARS, TRACE_EXEMPLARS_MAX

    (tmp_path / "subject.py").write_text(
        "def existing():\n    return 1\n", encoding="utf-8"
    )

    exit_code = main(
        ["code-fact", "query.never-wired", "existing", "--root", str(tmp_path)]
    )

    assert exit_code == 0
    result = json.loads(capsys.readouterr().out)
    # ADR-LA-001 D6-R1/R5, D9 slice (b): the retired mutable ``health_events``
    # side channel is gone from the public envelope. D9 slice (c), D6-R3: the
    # envelope-level ``reason_code`` is gone too -- the disambiguating signal
    # now lives in the capability's own payload schema (e.g. ``never-wired``'s
    # ``never_wired`` bool) -- the bounded ``Resolution`` trace is the only
    # journey observation left at the envelope level.
    assert set(result) == {
        "provider",
        "confidence",
        "payload",
        "trace",
    }
    assert result["trace"], "Answered query must expose its bounded resolution trace"
    answering_entries = [
        entry for entry in result["trace"] if entry["event"] == "answered"
    ]
    assert len(answering_entries) == 1
    assert answering_entries[0]["provider_id"] == result["provider"]
    assert answering_entries[0]["fault_count"] == 0
    for entry in result["trace"]:
        assert set(entry) == {
            "provider_id",
            "event",
            "scope",
            "fault_count",
            "exemplars",
            "detail",
        }
        assert entry["provider_id"]
        assert entry["scope"] in {"complete", "filtered", "unfiltered"}
        assert len(entry["exemplars"]) <= TRACE_EXEMPLARS_MAX
        assert len(entry["detail"]) <= TRACE_DETAIL_MAX_CHARS

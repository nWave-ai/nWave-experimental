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


def test_non_python_substring_does_not_hide_a_python_identifier(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """A config word containing ``a`` is not a non-Python reference to ``a``."""
    (tmp_path / "subject.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    config_dir = tmp_path / ".nwave"
    config_dir.mkdir()
    (config_dir / "des-config.json").write_text(
        '{"blast_radius": {}}', encoding="utf-8"
    )

    exit_code, result = _invoke(
        ["query.callers-of", "a", "--root", str(tmp_path)], capsys
    )

    assert exit_code == 0
    assert result["provider"] == "ast"
    assert result["payload"]["sites"] == []


def test_dotted_subject_degrades_when_non_python_uses_realized_callable(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    (tmp_path / "subject.py").write_text(
        "class Owner:\n    def method(self):\n        return 1\n", encoding="utf-8"
    )
    (tmp_path / "caller.ts").write_text("x.method();\n", encoding="utf-8")

    exit_code, result = _invoke(
        ["query.callers-of", "Owner.method", "--root", str(tmp_path)], capsys
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


def test_unrecognized_arguments_carries_a_how_line_with_a_working_example(
    capsys: pytest.CaptureFixture,
) -> None:
    """Run 6 evidence: root mis-ordered `subject` after an already-consumed
    `--root VALUE` (`query.callers-of --root . SYMBOL`), hit a bare
    "unrecognized arguments" message with no example 3x, then fell back to
    19 direct source Reads. Argparse's own fixed error text is preserved
    (a caller/guard can still recognize the failure class), with one HOW
    line appended naming the actual working order.

    CI correction: the mis-ordered-positional trigger itself
    (`query.callers-of --root . target`) is NOT a portable way to force
    this error -- CI's Python 3.12.13 parses it cleanly where local 3.12.3
    does not (argparse's handling of a positional trailing an
    already-satisfied optional differs across CPython 3.12.x patch
    releases). A trailing genuinely-unknown flag is unrecognized on every
    Python version argparse has ever shipped -- use that instead to force
    the SAME error path/message this test actually verifies."""
    from des.cli.code_fact import main

    with pytest.raises(SystemExit) as exc_info:
        main(["query.callers-of", "target", "--root", ".", "--bogus-flag"])

    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "unrecognized arguments" in err
    assert "--bogus-flag" in err
    assert "HOW:" in err
    assert "query.callers-of SYMBOL --root ROOT" in err


@pytest.mark.parametrize(
    ("file_name", "file_source", "expected_provider", "callers_answers_absence"),
    [
        pytest.param(
            "subject.py",
            "def target():\n"
            "    return 1\n\n"
            "def observer():\n"
            "    observed = target\n"
            "    return observed\n",
            "ast",
            True,
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
            True,
            id="non_python_textsearch_floor",
        ),
    ],
)
def test_reads_of_reports_a_non_call_reference_while_callers_of_stays_absent(
    file_name: str,
    file_source: str,
    expected_provider: str,
    callers_answers_absence: bool,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    """reads-of and callers-of stay disjoint. Both tiers represent bare and
    dotted trailing identifiers, so their empty callers result is an honest
    structural/noisy absence rather than hidden dotted-reference blindness."""
    (tmp_path / file_name).write_text(file_source, encoding="utf-8")

    reads_exit_code, reads_result = _invoke(
        ["query.reads-of", "target", "--root", str(tmp_path)], capsys
    )
    callers_exit_code, callers_result = _invoke(
        ["query.callers-of", "target", "--root", str(tmp_path)], capsys
    )

    assert reads_exit_code == 0
    assert reads_result["provider"] == expected_provider
    assert reads_result["payload"]["sites"]

    assert callers_answers_absence
    assert callers_exit_code == 0
    assert callers_result["provider"] == expected_provider
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


def test_textsearch_sites_are_reported_as_file_line_not_character_offset(
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mixed tree containing a non-Python file forces the textsearch
    provider for the whole query.  Every reported site must be a 1-based
    ``file:line`` locator -- never a raw character offset -- for both the
    Python and the non-Python match."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "m.py").write_text(
        "def target():\n"
        "    return 1\n"
        "\n"
        "def caller():\n"
        "    x = 1\n"
        "    return target()\n",
        encoding="utf-8",
    )
    (pkg / "x.ts").write_text("const value = target();\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code, result = _invoke(["query.callers-of", "target", "--root", "."], capsys)

    assert exit_code == 0
    assert result["provider"] == "textsearch"
    assert result["confidence"] == "noisy"
    assert result["payload"]["sites"] == [
        "pkg/m.py:6",
        "pkg/x.ts:1",
    ]


def test_textsearch_site_on_final_unterminated_line_still_reports_correct_line(
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The newline-counting locator must not depend on a trailing terminator:
    a sole match on a file's last line, where that file has no trailing
    newline, still reports the correct 1-based line number."""
    (tmp_path / "subject.ts").write_text(
        "function unrelated() { return 1; }\nfunction caller() { return target(); }",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    exit_code, result = _invoke(["query.callers-of", "target", "--root", "."], capsys)

    assert exit_code == 0
    assert result["provider"] == "textsearch"
    assert result["confidence"] == "noisy"
    assert result["payload"]["sites"] == ["subject.ts:2"]


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

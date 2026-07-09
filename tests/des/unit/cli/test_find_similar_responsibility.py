"""AT -- `des find-similar-responsibility` (codefact-similar-responsibility, slice-01).

Charter: docs/product/expectations/codefact-similar-responsibility/
         des-find-similar-responsibility---name-symbol---scope-path-shows-an-operator-the-ranked-existing.md
Feature-delta: docs/feature/codefact-similar-responsibility/feature-delta.md

A NEW thin observable CLI (`src/des/cli/find_similar_responsibility.py`,
`main(argv) -> int`) that invokes a NEW additive `CodeFactPort` capability
(`query.similar-responsibility`, AST-tier, dispatched in
`AstAdapter.query()` mirroring the shipped `_step_shape_corpus` pattern) so
an operator about to author a new symbol sees the RANKED existing symbols
whose structural fingerprint (name-token Jaccard + arity) overlaps the
proposed name -- before writing a parallel implementation.

Advisory, GDP-6-safe (never blocks): the tool always exits 0 -- it informs,
it never gates (charter, "Expected observations" bullet 4). The signal that
distinguishes "I looked and found nothing" from "I could not look" is the
`reason_code` field on the JSON payload, mirroring the LOCKED
`CodeFactResult.reason_code` vocabulary (`ReasonCode`, `code_fact_port.py`):
`"live-non-callable"` -- a real, parseable scope was searched (whether or
not it yielded candidates) -- vs `"absent"` -- the scope could not be
searched at all (nonexistent path / empty directory / nothing parseable) --
mirroring `AstAdapter._step_shape_corpus`'s own absent-vs-live split. An
`"absent"` reason_code with a fabricated `"candidates": []` that looks
identical to a genuine empty search is exactly the silent-wrong failure the
design (GDP-6) and the charter's two NEGATIVE oracle bullets forbid.

covers: slice-01 of docs/feature/codefact-similar-responsibility/feature-delta.md

RED reason (P1-P4 in-process active-RED, `nw-distill-red-scaffolding`):
neither `src/des/cli/find_similar_responsibility.py` nor the
`query.similar-responsibility` capability constant/dispatch exist yet.
Module-level imports name ONLY stdlib + pytest (P1) -- NEVER the absent SUT
module. `_invoke()` lazily imports `main` from
`des.cli.find_similar_responsibility` INSIDE its body (P3); the resulting
`ModuleNotFoundError` is a runtime exception raised WITHIN each test's own
call stack, not a collection-time error -- collection stays green, and each
test fails for a semantic reason once the module ships (P4).

Driving surface: `des.cli.find_similar_responsibility.main(argv) -> int`
invoked IN-PROCESS against a `tmp_path` scope directory (composition-root
driving port -- Mandate 16, driving-port-only boundary). No subprocess fork.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


#: Two module-level defs of DIFFERENT structural closeness to a queried
#: "parse_feature_delta_v2" -- `parse_feature_delta` is a near-miss (3/4
#: name-token overlap); `parse_feature_document` is a weaker cousin (2/5).
#: Line numbers are pinned by this exact literal (`parse_feature_delta` at
#: line 1) so the AT can assert `{file, line}` precisely, per the charter's
#: "enough file and line detail that the operator can go open it" oracle.
MULTI_SYMBOL_MODULE = (
    "def parse_feature_delta(path):\n"
    "    return path\n"
    "\n"
    "\n"
    "def parse_feature_document(path):\n"
    "    return path\n"
)

#: Several similarly-shaped `validate_*` symbols -- the charter's "generic
#: name against a scope likely to contain several plausible candidates" walk.
GENERIC_NAME_MODULE = (
    "def validate_input(data):\n"
    "    return data\n"
    "\n"
    "\n"
    "def validate_output(data):\n"
    "    return data\n"
    "\n"
    "\n"
    "def validate_schema(data):\n"
    "    return data\n"
)

#: Syntactically invalid Python -- the "directory with nothing parseable"
#: degrade-LOUD case (an unparseable .py MUST NOT be silently skipped into a
#: fabricated empty result).
UNPARSEABLE_MODULE = "def not_valid_python(:\n    pass\n"

_REASON_ABSENT = "absent"
_REASON_LIVE = "live-non-callable"


def _write_module(scope_dir: Path, relative_path: str, source: str) -> Path:
    file_path = scope_dir / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(source, encoding="utf-8")
    return file_path


def _invoke(name: str, scope: Path, capsys) -> tuple[int, dict]:
    """The driving call every test uses: in-process `main()` (P2), stdout
    captured and parsed as the `--format json` contract token."""
    from des.cli.find_similar_responsibility import main

    exit_code = main(
        [
            "--name",
            name,
            "--scope",
            str(scope),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


def test_ranks_the_existing_lookalike_symbol_first_with_file_and_line(
    tmp_path: Path, capsys
) -> None:
    _write_module(tmp_path, "feature_delta.py", MULTI_SYMBOL_MODULE)

    exit_code, payload = _invoke("parse_feature_delta_v2", tmp_path, capsys)

    assert exit_code == 0
    assert payload["reason_code"] == _REASON_LIVE
    candidates = payload["candidates"]
    assert candidates, "expected >=1 candidate for a near-miss name"
    top = candidates[0]
    assert top["symbol"] == "parse_feature_delta"
    assert top["file"].endswith("feature_delta.py")
    assert top["line"] == 1
    if len(candidates) > 1:
        # Closest match leads the list -- ranked by overlap, non-increasing.
        assert candidates[0]["overlap"] >= candidates[1]["overlap"]


def test_unrelated_symbol_is_never_returned_as_a_candidate(
    tmp_path: Path, capsys
) -> None:
    _write_module(tmp_path, "feature_delta.py", MULTI_SYMBOL_MODULE)

    # design's own witnessed RED AT: a request for an unrelated `send_email`
    # -- shares zero name-tokens with either existing symbol.
    exit_code, payload = _invoke("send_email", tmp_path, capsys)

    assert exit_code == 0
    # A real, parseable scope WAS searched -- distinguishes this genuine
    # empty result from the degrade-LOUD "could not look" cases below.
    assert payload["reason_code"] == _REASON_LIVE
    ranked_symbols = [candidate["symbol"] for candidate in payload["candidates"]]
    assert "parse_feature_delta" not in ranked_symbols
    assert "parse_feature_document" not in ranked_symbols


def _nonexistent_scope(tmp_path: Path) -> Path:
    return tmp_path / "does-not-exist"


def _empty_scope(tmp_path: Path) -> Path:
    return tmp_path


def _unparseable_scope(tmp_path: Path) -> Path:
    _write_module(tmp_path, "broken.py", UNPARSEABLE_MODULE)
    return tmp_path


@pytest.mark.parametrize(
    "make_scope",
    [
        pytest.param(_nonexistent_scope, id="nonexistent_scope_path"),
        pytest.param(_empty_scope, id="empty_scope_directory"),
        pytest.param(_unparseable_scope, id="scope_with_nothing_parseable"),
    ],
)
def test_scope_that_cannot_be_read_degrades_loud_never_fabricates_an_empty_candidate_list(
    tmp_path: Path, capsys, make_scope
) -> None:
    scope = make_scope(tmp_path)

    exit_code, payload = _invoke("anything", scope, capsys)

    # Advisory (charter bullet 4): even the degrade-LOUD path never exits
    # non-zero to block the operator -- the loud signal lives in the payload.
    assert exit_code == 0
    assert payload["reason_code"] == _REASON_ABSENT
    assert payload["reason_code"] != _REASON_LIVE, (
        "an unreadable/unparseable/nonexistent scope must read differently "
        "from a genuine 'I looked and found nothing' answer"
    )
    assert payload["candidates"] == []
    assert payload["detail"], "the LOUD 'could not look' signal must be self-explaining"


def test_command_is_advisory_never_blocks_even_with_multiple_ranked_candidates(
    tmp_path: Path, capsys
) -> None:
    _write_module(tmp_path, "validators.py", GENERIC_NAME_MODULE)

    exit_code, payload = _invoke("validate", tmp_path, capsys)

    # Never blocks/refuses/gates -- exits 0 regardless of how many
    # candidates a generic name surfaces (charter bullet 4).
    assert exit_code == 0
    assert payload["reason_code"] == _REASON_LIVE
    assert len(payload["candidates"]) >= 2
    overlaps = [candidate["overlap"] for candidate in payload["candidates"]]
    assert overlaps == sorted(overlaps, reverse=True), "candidates must be ranked"

"""Regression: `des find-similar-responsibility` must DECLARE the coverage
gap when a candidate file cannot be parsed, never silently drop it
(F-fix-find-similar-declares-unparseable-coverage, sister "sixth floor"
Q-155/Q-160 in its minor per-file form).

Charter: `docs/feature/fix-find-similar-declares-unparseable-coverage/
feature-delta.md`.

RCA (feature-delta `[REF] Value`): `AstAdapter._similar_responsibility`
(`src/des/adapters/driven/codefact/ast_code_fact_adapter.py:281-339`) calls
`self._parse(source_file)` for every candidate file and, when parsing fails
(`_parse` returns `None` on `ast.parse` `SyntaxError`), silently `continue`s
-- the file never contributes a candidate and NOTHING says it was skipped.
`des find-similar-responsibility` (`src/des/cli/find_similar_responsibility.py`)
renders only `{candidates, reason_code, detail}` -- there is no field naming
how many candidate files could not be read/parsed. An operator asking "did
you search everything?" gets a clean-looking empty/short candidate list
indistinguishable from "I searched everything and found nothing" -- the
coverage-gap-reports-as-completeness class this feature-delta names.

Fix direction (feature-delta `[REF] Design reference`, NOT implemented
here): thread the ALREADY-COMPUTED parse-failure signal (the same `_parse
is None` check the ranking loop already makes -- no second parse pass) up
through the payload to one new declared field. This AT's own oracle fixes
the field's name and shape, since the feature-delta only specifies "a field
naming how many files were unreadable/unparsed": the CLI JSON payload gains
an integer key `unparsed_count` alongside the existing `candidates`,
`reason_code`, `detail` keys -- the count of candidate `.py` files under
`--scope` whose `_parse` returned `None` during the SAME ranking pass.

Three-oracle contract (mirrors the feature-delta's coverage-gap framing):
  1. UNPARSEABLE-PRESENT: a corpus with >=1 unparseable file declares a
     nonzero `unparsed_count` alongside its (possibly nonempty) ranking.
     ACTIVE-RED today (`unparsed_count` does not exist in the payload).
  2. FULLY-PARSEABLE: a corpus where every file parses reports
     `unparsed_count == 0` and its ranking output is UNCHANGED --
     byte-identical to the pre-fix `candidates`/`reason_code`/`detail`
     contract already covered by
     `tests/des/unit/cli/test_find_similar_responsibility.py`. Control pin,
     GREEN today (the field is simply absent) AND after (the field reports
     zero, everything else untouched).
  3. ANTI-OVERSHOOT (the trap that ruins the fix, sister Q-160): the
     discriminant MUST be the PARSE-FAILURE signal (`_parse` returned
     `None`), NEVER "this file contributed zero module-level symbols". A
     genuinely-empty-but-PARSEABLE file (docstring-only / import-only /
     zero-byte) is NOT unparseable -- it parsed fine, it is just empty --
     and must NOT be counted toward `unparsed_count`. An implementation
     that deduces "unparsed" from "zero symbols contributed" would wrongly
     flag this file; this pin rejects that implementation. Negative AT
     (`@pytest.mark.negative_at`), GREEN today (the field does not exist,
     so it cannot be wrongly populated) AND after (the fix must keep it
     green).

@contract-shape:bounded-change (oracle 1, oracle 3): a corpus containing an
unparseable file moves the payload from "no unparsed signal at all" (today)
to "a correct, bounded `unparsed_count`" (the fix); the anti-overshoot pin
bounds which files may contribute to that count.

@contract-shape:unbounded-preservation (oracle 2): the fully-parseable
ranking path (`candidates`, `reason_code`, `detail`) must never regress
under the fix.

Driving surface: `des.cli.find_similar_responsibility.main(argv) -> int`
invoked IN-PROCESS against a `tmp_path` scope directory (composition-root
driving port -- Mandate 16, driving-port-only boundary; mirrors the shipped
`tests/des/unit/cli/test_find_similar_responsibility.py` harness idiom, no
subprocess fork, no second parse pass authored by this AT).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


#: The shipped near-miss fixture (unchanged, sourced from
#: `tests/des/unit/cli/test_find_similar_responsibility.py
#: MULTI_SYMBOL_MODULE`) -- a fully-parseable module with a real ranked
#: candidate, used as the "something to find" half of every mixed corpus.
PARSEABLE_MODULE_WITH_CANDIDATE = (
    "def parse_feature_delta(path):\n"
    "    return path\n"
    "\n"
    "\n"
    "def parse_feature_document(path):\n"
    "    return path\n"
)

#: Several distinct real `SyntaxError` shapes -- `ast.parse` raises a
#: DIFFERENT concrete exception for each, all caught by `AstAdapter._parse`
#: and returning `None`. Parametrizing over shapes proves the fix counts
#: PARSE FAILURE generically, never one specific error string.
UNPARSEABLE_MODULE_SHAPES: dict[str, str] = {
    "invalid_syntax": "def not_valid_python(:\n    pass\n",
    "unmatched_paren": "def missing_paren(\n    pass\n",
    "unexpected_indent": "    def indented_at_module_level():\n        pass\n",
    "unterminated_expression": "x = (1, 2\n",
}

#: Genuinely-empty-but-PARSEABLE shapes -- `ast.parse` succeeds and yields
#: ZERO module-level `def`/`class`/assignment symbols. The anti-overshoot
#: pin: none of these may ever be counted as unparsed.
EMPTY_BUT_PARSEABLE_MODULE_SHAPES: dict[str, str] = {
    "zero_byte_file": "",
    "import_only": "import os\n",
    "docstring_only": '"""Nothing but a module docstring."""\n',
}

_REASON_ABSENT = "absent"
_REASON_LIVE = "live-non-callable"


def _write_module(scope_dir: Path, relative_path: str, source: str) -> Path:
    file_path = scope_dir / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(source, encoding="utf-8")
    return file_path


def _invoke(name: str, scope: Path, capsys) -> tuple[int, dict]:
    """The driving call every test uses: in-process `main()`, stdout
    captured and parsed as the `--format json` contract token (mirrors
    `tests/des/unit/cli/test_find_similar_responsibility.py::_invoke`)."""
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


# ---------------------------------------------------------------------------
# Oracle 1 -- UNPARSEABLE-PRESENT: a corpus with >=1 unparseable file must
# declare a nonzero `unparsed_count`. ACTIVE-RED today.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "unparseable_shape_ids",
    [
        pytest.param(["invalid_syntax"], id="one_unparseable_file"),
        pytest.param(["invalid_syntax", "unmatched_paren"], id="two_unparseable_files"),
        pytest.param(
            sorted(UNPARSEABLE_MODULE_SHAPES),
            id="every_known_syntax_error_shape",
        ),
    ],
)
def test_unparseable_files_are_declared_in_the_coverage_count(
    tmp_path: Path, capsys, unparseable_shape_ids: list[str]
) -> None:
    """A corpus with N unparseable `.py` files (alongside one parseable file
    with a real candidate) declares `unparsed_count == N` -- the coverage
    signal an operator needs to tell "searched everything, found nothing"
    apart from "searched what parsed". ACTIVE-RED today: `AstAdapter
    ._similar_responsibility` silently `continue`s past each unparseable
    file (`ast_code_fact_adapter.py:304-306`) and the CLI payload has no
    `unparsed_count` key at all -- `payload.get("unparsed_count")` is
    `None`, never the expected integer.
    """
    _write_module(tmp_path, "feature_delta.py", PARSEABLE_MODULE_WITH_CANDIDATE)
    for shape_id in unparseable_shape_ids:
        _write_module(
            tmp_path,
            f"broken_{shape_id}.py",
            UNPARSEABLE_MODULE_SHAPES[shape_id],
        )

    exit_code, payload = _invoke("parse_feature_delta_v2", tmp_path, capsys)

    assert exit_code == 0, (
        "the coverage declaration must stay advisory (GDP-6) -- it must "
        f"never flip the command non-zero; got exit_code={exit_code}"
    )
    assert payload.get("unparsed_count") == len(unparseable_shape_ids), (
        f"expected the declared unparsed-file count to equal the "
        f"{len(unparseable_shape_ids)} genuinely unparseable file(s) "
        f"({unparseable_shape_ids}) planted alongside the one parseable "
        f"candidate file; got unparsed_count="
        f"{payload.get('unparsed_count')!r} (the field is absent from the "
        f"payload today -- the fix threads the adapter's already-computed "
        f"`_parse is None` signal to this one new CLI field, feature-delta "
        f"[REF] Design reference)"
    )
    # The parseable file's own candidate must still be found -- the
    # unparseable siblings must not poison the ranking loop.
    assert payload.get("reason_code") == _REASON_LIVE, (
        "a corpus that still has a real parseable candidate file must stay "
        f"a genuine live search; got reason_code={payload.get('reason_code')!r}"
    )
    ranked_symbols = [c["symbol"] for c in payload.get("candidates", [])]
    assert "parse_feature_delta" in ranked_symbols, (
        "the unparseable siblings must not suppress the real candidate "
        f"from the still-parseable file; got candidates={ranked_symbols!r}"
    )


def test_corpus_with_only_unparseable_files_declares_full_unparsed_count(
    tmp_path: Path, capsys
) -> None:
    """A corpus where EVERY candidate file is unparseable (no parseable file
    at all) stays `absent` (mirrors the shipped degrade-LOUD contract) but
    ALSO declares `unparsed_count` equal to the total file count -- so
    "nothing parseable" and "nothing SIMILAR" never collapse into the same
    reading. ACTIVE-RED today: no `unparsed_count` key at all.
    """
    _write_module(
        tmp_path, "broken_one.py", UNPARSEABLE_MODULE_SHAPES["invalid_syntax"]
    )
    _write_module(
        tmp_path, "broken_two.py", UNPARSEABLE_MODULE_SHAPES["unmatched_paren"]
    )

    exit_code, payload = _invoke("anything", tmp_path, capsys)

    assert exit_code == 0
    assert payload.get("reason_code") == _REASON_ABSENT, (
        "a scope where nothing parses stays the shipped degrade-LOUD "
        f"'absent' answer; got reason_code={payload.get('reason_code')!r}"
    )
    assert payload.get("candidates") == [], (
        "an all-unparseable scope must still never fabricate a candidate"
    )
    assert payload.get("unparsed_count") == 2, (
        "both planted files are genuinely unparseable and must both be "
        f"counted; got unparsed_count={payload.get('unparsed_count')!r} "
        "(field absent today)"
    )


# ---------------------------------------------------------------------------
# Oracle 2 -- FULLY-PARSEABLE: unaffected ranking output, `unparsed_count
# == 0`. Control pin -- GREEN today (field absent) and after (field zero).
# ---------------------------------------------------------------------------


def test_fully_parseable_corpus_reports_zero_unparsed_and_unchanged_ranking(
    tmp_path: Path, capsys
) -> None:
    """A corpus where every file parses reports `unparsed_count == 0` and
    its ranking output is byte-identical to the shipped fully-parseable
    contract (`tests/des/unit/cli/test_find_similar_responsibility.py
    ::test_ranks_the_existing_lookalike_symbol_first_with_file_and_line`).
    No new noise on the fully-covered path.
    """
    _write_module(tmp_path, "feature_delta.py", PARSEABLE_MODULE_WITH_CANDIDATE)

    exit_code, payload = _invoke("parse_feature_delta_v2", tmp_path, capsys)

    assert exit_code == 0
    assert payload.get("reason_code") == _REASON_LIVE
    candidates = payload.get("candidates", [])
    assert candidates, "expected >=1 candidate for a near-miss name"
    top = candidates[0]
    assert top["symbol"] == "parse_feature_delta"
    assert top["file"].endswith("feature_delta.py")
    assert top["line"] == 1
    assert payload.get("unparsed_count", 0) == 0, (
        "a fully-parseable corpus must declare zero unparsed files; got "
        f"unparsed_count={payload.get('unparsed_count')!r} (today the key "
        "is simply absent, which this pin also accepts via the `0` "
        "default -- it must never become nonzero)"
    )


# ---------------------------------------------------------------------------
# Oracle 3 -- ANTI-OVERSHOOT (sister Q-160 trap): a genuinely-empty-but-
# parseable file must NEVER be counted as unparsed. Negative AT.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize("empty_shape_id", sorted(EMPTY_BUT_PARSEABLE_MODULE_SHAPES))
def test_genuinely_empty_parseable_file_is_not_counted_as_unparsed(
    tmp_path: Path, capsys, empty_shape_id: str
) -> None:
    """A file that PARSES successfully but contributes zero module-level
    `def`/`class`/assignment symbols must NOT be counted toward
    `unparsed_count` -- it is empty, not unparseable. Kills any
    implementation that discriminates "unparsed" by "this file's parse
    loop iteration contributed zero candidates" instead of the real `_parse
    is None` signal. GREEN today (the field does not exist, so it cannot
    be wrongly nonzero) AND must stay GREEN after the fix.
    """
    _write_module(tmp_path, "feature_delta.py", PARSEABLE_MODULE_WITH_CANDIDATE)
    _write_module(
        tmp_path,
        "empty_module.py",
        EMPTY_BUT_PARSEABLE_MODULE_SHAPES[empty_shape_id],
    )

    exit_code, payload = _invoke("parse_feature_delta_v2", tmp_path, capsys)

    assert exit_code == 0
    assert payload.get("unparsed_count", 0) == 0, (
        f"'{empty_shape_id}' parses fine and simply defines nothing -- it "
        f"must never be counted as unparsed; got unparsed_count="
        f"{payload.get('unparsed_count')!r} (a wrong implementation that "
        "infers 'unparsed' from 'zero symbols contributed' would wrongly "
        "flag this file -- this pin rejects that implementation)"
    )
    # The real candidate from the sibling parseable file must still surface
    # -- the empty file must not poison the ranking either.
    ranked_symbols = [c["symbol"] for c in payload.get("candidates", [])]
    assert "parse_feature_delta" in ranked_symbols

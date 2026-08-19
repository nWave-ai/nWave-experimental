"""Unit tests for the architecture-brief citation parser
(`des compile-contract`'s parsing half).

Covers the line-wrap regression a real ADR-SSOT-002 brief (K4 run-13,
maintenance-windows) exposed: markdown word-wraps a long inline-code
citation with no space marker at the wrap point, and a naive regex over the
raw text mistook the fragment after the break for its own, wrong, file
citation (`hc/api/management/commands/sendalerts.py:24-55` split at the
`commands/` line boundary produced a spurious `sendalerts.py` target).
"""

from __future__ import annotations

from pathlib import Path

from des.domain.architecture_brief_resolver import (
    declared_imports_for_target,
    extract_declared_import_candidates,
    extract_obligations,
    extract_target_citations,
)


def test_extracts_one_citation_per_file() -> None:
    # Mirrors `des.cli.dispatch._FILE_LINE_CITATION_RE`'s own shape exactly
    # (reused, not reinvented): it captures the FIRST line number of a
    # `file:line-range` citation, never the trailing `-30` -- the same
    # substring `des dispatch`'s own EXTEND-citation validator searches for.
    brief = "See `pkg/mod.py:10` and `pkg/mod.py:20-30` and `pkg/other.py:5`."
    citations = extract_target_citations(brief)
    assert citations == {
        "pkg/mod.py": ["pkg/mod.py:10", "pkg/mod.py:20"],
        "pkg/other.py": ["pkg/other.py:5"],
    }


def test_citation_split_across_a_markdown_line_wrap_is_joined() -> None:
    # Reproduces the exact K4 run-13 shape: a long inline-code span wrapped
    # mid-path at 80 columns, with no space at the break.
    brief = (
        "Observation point: `hc/api/management/commands/\n"
        "sendalerts.py:24-55`, the sole driving entry."
    )
    citations = extract_target_citations(brief)
    assert citations == {
        "hc/api/management/commands/sendalerts.py": [
            "hc/api/management/commands/sendalerts.py:24"
        ]
    }
    # The regression: no spurious short-fragment target.
    assert "sendalerts.py" not in citations


def test_no_citation_yields_empty_mapping() -> None:
    assert extract_target_citations("no file references here at all") == {}


def test_extracts_schema_closed_obligation_tokens_in_order() -> None:
    brief = (
        "1. **REUSE_CANDIDATE** -- law: reuse the validator.\n"
        "2. **INVALID_STATE** -- law: reject negative duration.\n"
        "3. **REUSE_CANDIDATE** -- repeated, must not duplicate.\n"
    )
    assert extract_obligations(brief) == ["REUSE_CANDIDATE", "INVALID_STATE"]


def test_non_schema_bold_token_is_ignored() -> None:
    brief = "### Reuse survey (decision: **EXTEND**, not CREATE_NEW)"
    assert extract_obligations(brief) == []


def test_extracts_backtick_symbol_candidates_deduplicated() -> None:
    brief = "Reuse `Check.get_grace_start` and `CronSim`, again `CronSim`."
    assert extract_declared_import_candidates(brief) == [
        "Check.get_grace_start",
        "CronSim",
    ]


def test_backtick_symbol_split_across_a_line_wrap_is_joined() -> None:
    brief = "Reuse `hc.api.views.\nguess_kind` for validation."
    assert extract_declared_import_candidates(brief) == ["hc.api.views.guess_kind"]


_MODULE_WITH_IMPORT_AND_CLASS = """
from cronsim import CronSim


class Check:
    def get_grace_start(self):
        return None
"""


def _seed(tmp_path: Path, relative: str, source: str) -> None:
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")


def test_declared_imports_admits_bare_name_bound_in_target_file(
    tmp_path: Path,
) -> None:
    _seed(tmp_path, "pkg/mod.py", _MODULE_WITH_IMPORT_AND_CLASS)
    brief = "Reuse `CronSim` and `Check` here."
    assert declared_imports_for_target(tmp_path, "pkg/mod.py", brief) == [
        "CronSim",
        "Check",
    ]


def test_declared_imports_drops_dotted_class_attribute_chain(
    tmp_path: Path,
) -> None:
    # `Check.get_grace_start` is neither a bare bound name nor a resolvable
    # dotted MODULE path (`Check` is a class, not a module file) -- the
    # existing `des dispatch` declared-import validator cannot verify this
    # shape either, so emitting it would fail "passes by construction".
    _seed(tmp_path, "pkg/mod.py", _MODULE_WITH_IMPORT_AND_CLASS)
    brief = "Reuse `Check.get_grace_start` for occurrence computation."
    assert declared_imports_for_target(tmp_path, "pkg/mod.py", brief) == []


def test_declared_imports_admits_resolvable_dotted_module_path(
    tmp_path: Path,
) -> None:
    _seed(tmp_path, "pkg/helpers.py", "def guess_kind(x):\n    return x\n")
    _seed(tmp_path, "pkg/mod.py", "class Check:\n    pass\n")
    brief = "Reuse `pkg.helpers.guess_kind` for validation."
    assert declared_imports_for_target(tmp_path, "pkg/mod.py", brief) == [
        "pkg.helpers.guess_kind"
    ]


def test_declared_imports_drops_unverifiable_invented_symbol(
    tmp_path: Path,
) -> None:
    _seed(tmp_path, "pkg/mod.py", "class Check:\n    pass\n")
    brief = "Reuse `TotallyInventedHelper` which does not exist anywhere."
    assert declared_imports_for_target(tmp_path, "pkg/mod.py", brief) == []

"""P3.2 spec-coverage gate — the observed proofs, pinned as regression.

These tests ARE the evolution-plan P3.2 done-currency, made permanent: the
gate was proven by execution against a planted defect of its target class
(a checklist with an uncovered identity/security requirement — the eval's
silent-absence class where UI/security/validation requirements shipped with
no AT and nothing flagged them), a compliant case, the Gherkin-tag arm, and
the degrade-LOUD cases. Deleting the gate's logic turns these RED.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.verify_spec_coverage import main


# fix-coverage-claim-names-a-feature: attribution is now a DECLARED BINDING
# (a checklist's line-anchored '@feature-<id>' declaration + a matching AT
# head-tag), not a bare marker anywhere under --at-dir. Every fixture below
# declares the SAME feature id and tags its own AT file(s) with it so the
# ORIGINAL test intent (a marker on THIS file covers THIS checklist's row)
# still holds under the new attribution contract -- each test is hermetic
# (its own tmp_path), so sharing one id across fixtures is safe.
_FIXTURE_FEATURE_ID = "spec-coverage-fixture"


def _tag_at_source(name: str, source: str) -> str:
    """Prepend the fixture's '@feature-<id>' attribution tag -- a leading
    '# @feature-<id>' comment for pytest files, '// @feature-<id>' for
    TS/JS, or a leading Gherkin tag line for '.feature' files."""
    if name.endswith(".feature"):
        return f"@feature-{_FIXTURE_FEATURE_ID}\n{source}"
    if name.endswith((".ts", ".tsx", ".js", ".jsx")):
        return f"// @feature-{_FIXTURE_FEATURE_ID}\n{source}"
    return f"# @feature-{_FIXTURE_FEATURE_ID}\n{source}"


_CHECKLIST_TABLE = f"""\
# Requirements

@feature-{_FIXTURE_FEATURE_ID}

| ID | Requirement | Category |
|----|-------------|----------|
| R1 | a booking produces a confirmation | functional |
| R2 | client-supplied identity must be rejected | security |
"""

_AT_COVERS_R1_ONLY = """\
import pytest


@pytest.mark.covers("R1")
def test_booking_produces_confirmation():
    assert {"confirmation": "abc"}["confirmation"]
"""

_AT_COVERS_R2_BODY_COMMENT = """\

def test_server_derives_identity_and_rejects_client_supplied():
    # covers: R2
    assert True
"""


def _first_event(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    out: dict[str, object] = json.loads(capsys.readouterr().out.splitlines()[0])
    return out


def _write_corpus(tmp_path: Path, at_source: str) -> tuple[str, str]:
    """Write checklist + AT corpus; return (checklist, at_dir) paths."""
    checklist = tmp_path / "checklist.md"
    checklist.write_text(_CHECKLIST_TABLE)
    at_dir = tmp_path / "ats"
    at_dir.mkdir()
    (at_dir / "test_booking.py").write_text(
        _tag_at_source("test_booking.py", at_source)
    )
    return str(checklist), str(at_dir)


def test_uncovered_security_requirement_is_refused_naming_the_row(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE proof: R1 covered, R2 (security) uncovered -> exit 1.

    The eval's silent-absence class: an identity/security requirement with
    no AT. The gate must exit 1, name R2 as a visible red row with its
    category, and call out the mandatory category explicitly.
    """
    checklist, at_dir = _write_corpus(tmp_path, _AT_COVERS_R1_ONLY)

    assert (
        main(["--checklist", checklist, "--at-dir", at_dir, "--repo", str(tmp_path)])
        == 1
    )
    event = _first_event(capsys)
    assert event["event"] == "SpecCoverageRefused"
    assert all(k in event for k in ("what", "why", "how"))
    uncovered = event["uncovered"]
    assert isinstance(uncovered, list) and len(uncovered) == 1
    assert uncovered[0]["id"] == "R2"
    assert uncovered[0]["category"] == "security"
    assert "client-supplied identity" in str(uncovered[0]["text"])
    assert event["mandatory_categories_uncovered"] == ["security"]


def test_body_comment_marker_covers_the_requirement(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """POSITIVE proof: adding an AT with '# covers: R2' -> exit 0 + counts."""
    checklist, at_dir = _write_corpus(
        tmp_path, _AT_COVERS_R1_ONLY + _AT_COVERS_R2_BODY_COMMENT
    )

    assert (
        main(["--checklist", checklist, "--at-dir", at_dir, "--repo", str(tmp_path)])
        == 0
    )
    event = _first_event(capsys)
    assert event["event"] == "SpecCoverageVerified"
    assert event["counts"] == {
        "functional": {"covered": 1, "total": 1},
        "security": {"covered": 1, "total": 1},
    }


def test_missing_checklist_degrades_loud_indeterminate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """DEGRADE proof: no checklist -> exit 2 with what/why/how, never a pass.

    A feature without a checklist cannot claim coverage.
    """
    at_dir = tmp_path / "ats"
    at_dir.mkdir()
    (at_dir / "test_x.py").write_text("def test_x():\n    assert True\n")

    assert (
        main(
            [
                "--checklist",
                str(tmp_path / "nope.md"),
                "--at-dir",
                str(at_dir),
                "--repo",
                str(tmp_path),
            ]
        )
        == 2
    )
    event = _first_event(capsys)
    assert event["event"] == "SpecCoverageIndeterminate"
    assert all(k in event for k in ("what", "why", "how"))


def test_gherkin_covers_tag_satisfies_the_requirement(tmp_path: Path) -> None:
    """Gherkin arm: a @covers-R2 tag covers the security row -> exit 0."""
    checklist = tmp_path / "checklist.md"
    checklist.write_text(_CHECKLIST_TABLE)
    at_dir = tmp_path / "ats"
    at_dir.mkdir()
    (at_dir / "test_booking.py").write_text(
        _tag_at_source("test_booking.py", _AT_COVERS_R1_ONLY)
    )
    (at_dir / "identity.feature").write_text(
        _tag_at_source(
            "identity.feature",
            "Feature: Identity\n\n"
            "  @covers-R2\n"
            "  Scenario: Client-supplied identity is rejected\n"
            "    Given a request carrying a client-supplied identity\n"
            "    When it reaches the API\n"
            "    Then it is rejected\n",
        )
    )

    assert (
        main(
            [
                "--checklist",
                str(checklist),
                "--at-dir",
                str(at_dir),
                "--repo",
                str(tmp_path),
            ]
        )
        == 0
    )


def test_docstring_marker_covers_the_requirement(tmp_path: Path) -> None:
    """Docstring arm: the R-id token in the test docstring counts."""
    checklist, at_dir = _write_corpus(
        tmp_path,
        _AT_COVERS_R1_ONLY
        + '\n\ndef test_identity_rejection():\n    """Covers R2."""\n'
        "    assert True\n",
    )

    assert (
        main(["--checklist", checklist, "--at-dir", at_dir, "--repo", str(tmp_path)])
        == 0
    )


def test_list_row_grammar_is_parsed(tmp_path: Path) -> None:
    """List-row arm: '- R<n> [category] text' rows form the denominator."""
    checklist = tmp_path / "checklist.md"
    checklist.write_text(
        f"@feature-{_FIXTURE_FEATURE_ID}\n\n"
        "- R1 [functional] a booking produces a confirmation\n"
        "- R2 [security] client-supplied identity must be rejected\n"
    )
    at_dir = tmp_path / "ats"
    at_dir.mkdir()
    (at_dir / "test_booking.py").write_text(
        _tag_at_source("test_booking.py", _AT_COVERS_R1_ONLY)
    )

    assert (
        main(
            [
                "--checklist",
                str(checklist),
                "--at-dir",
                str(at_dir),
                "--repo",
                str(tmp_path),
            ]
        )
        == 1
    )


def test_empty_at_corpus_degrades_loud_indeterminate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """DEGRADE proof: checklist present but zero AT files -> exit 2."""
    checklist = tmp_path / "checklist.md"
    checklist.write_text(_CHECKLIST_TABLE)
    at_dir = tmp_path / "ats"
    at_dir.mkdir()

    assert (
        main(
            [
                "--checklist",
                str(checklist),
                "--at-dir",
                str(at_dir),
                "--repo",
                str(tmp_path),
            ]
        )
        == 2
    )
    assert _first_event(capsys)["event"] == "SpecCoverageIndeterminate"


def test_malformed_row_with_id_but_no_category_degrades_loud(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """DEGRADE proof: an R-id row without a closed-set category -> exit 2.

    A half-parsed checklist must never silently shrink the denominator.
    """
    checklist = tmp_path / "checklist.md"
    checklist.write_text("| R1 | a requirement with no category cell |\n")
    at_dir = tmp_path / "ats"
    at_dir.mkdir()
    (at_dir / "test_x.py").write_text("def test_x():\n    assert True\n")

    assert (
        main(
            [
                "--checklist",
                str(checklist),
                "--at-dir",
                str(at_dir),
                "--repo",
                str(tmp_path),
            ]
        )
        == 2
    )
    event = _first_event(capsys)
    assert event["event"] == "SpecCoverageIndeterminate"
    assert "R1" in str(event["what"])


def test_duplicate_requirement_id_degrades_loud(tmp_path: Path) -> None:
    """DEGRADE proof: duplicate R-ids are an ambiguous denominator -> exit 2."""
    checklist = tmp_path / "checklist.md"
    checklist.write_text("- R1 [functional] first\n- R1 [security] duplicate id\n")
    at_dir = tmp_path / "ats"
    at_dir.mkdir()
    (at_dir / "test_x.py").write_text("def test_x():\n    assert True\n")

    assert (
        main(
            [
                "--checklist",
                str(checklist),
                "--at-dir",
                str(at_dir),
                "--repo",
                str(tmp_path),
            ]
        )
        == 2
    )


def test_ts_test_file_with_slash_comment_covers(tmp_path):
    """Language-generality: a `.test.ts` with `// covers: R2` counts (dogfood
    friction from the event-seat-reservation TS/Vitest rebuild, 2026-07-03)."""
    from des.cli.verify_spec_coverage import main

    checklist = tmp_path / "cl.md"
    checklist.write_text(
        f"@feature-{_FIXTURE_FEATURE_ID}\n\n"
        "| R1 | booking works | functional |\n| R2 | identity rejected | security |\n"
    )
    at = tmp_path / "ats"
    at.mkdir()
    (at / "booking.test.ts").write_text(
        _tag_at_source(
            "booking.test.ts",
            "test('books a seat', () => {\n"
            "  // covers: R1\n"
            "  // covers: R2\n"
            "  expect(true).toBe(true);\n"
            "});\n",
        )
    )
    assert (
        main(
            [
                "--checklist",
                str(checklist),
                "--at-dir",
                str(at),
                "--repo",
                str(tmp_path),
            ]
        )
        == 0
    )


def test_ts_uncovered_still_refused(tmp_path):
    """A TS corpus that covers R1 but not R2(security) is still refused."""
    from des.cli.verify_spec_coverage import main

    checklist = tmp_path / "cl.md"
    checklist.write_text(
        f"@feature-{_FIXTURE_FEATURE_ID}\n\n"
        "| R1 | booking works | functional |\n| R2 | identity rejected | security |\n"
    )
    at = tmp_path / "ats"
    at.mkdir()
    (at / "booking.spec.ts").write_text(
        _tag_at_source(
            "booking.spec.ts",
            "test('books', () => {\n  // covers: R1\n  expect(1).toBe(1);\n});\n",
        )
    )
    assert (
        main(
            [
                "--checklist",
                str(checklist),
                "--at-dir",
                str(at),
                "--repo",
                str(tmp_path),
            ]
        )
        == 1
    )


# --- regression: comment-marker scanner must not count STRING-LITERAL data ---
#
# Root cause (confirmed): `_covers_ids_from_body_comments` (Python arm) and
# `_covered_ids_in_source_text` (TS/JS/other arm) both apply the comment regex
# to RAW source lines with no string-literal awareness. A test body that
# WRITES fixture text containing the marker syntax -- e.g.
# `checklist.write_text("# covers: R1")` -- has that exact substring on its
# raw source line, so the scanner counts it as a genuine marker even though
# it is DATA, not a comment. Empirically triggered by this gate's own
# meta-test `tests/des/unit/application/test_distill_spec_coverage_advisory.py`
# (`test_full_coverage_is_a_silent_pass`, line ~64), whose fixture string
# `"def test_b():\n    # covers: R1\n    # covers: R2\n    ..."` falsely
# satisfies an unrelated feature's R1/R2 checklist rows when both files land
# under a shared `--at-dir`.

_AT_STRING_LITERAL_FALSE_POSITIVE_PY = """\
def test_writes_a_checklist_fixture(tmp_path):
    # This test's PURPOSE is writing fixture data -- the marker text below
    # is STRING CONTENT the test produces, not a real coverage marker for
    # THIS test.
    (tmp_path / "checklist.md").write_text("# covers: R1")
    assert True
"""

_AT_STRING_LITERAL_FALSE_POSITIVE_TS = (
    "test('writes a fixture', () => {\n"
    '  const marker = "// covers: R1";\n'
    "  expect(marker).toContain('covers');\n"
    "});\n"
)


def test_string_literal_marker_is_not_real_coverage_python(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE (the bug), Python arm: '# covers: R1' as STRING DATA inside
    a test body (e.g. an argument to `.write_text(...)`) must NOT count as
    covering R1 -- only a genuine `# covers: R1` comment counts. On the
    current (unfixed) scanner this assertion FAILS: the string-literal
    substring is wrongly counted, so the gate wrongly reports exit 0
    (SpecCoverageVerified) instead of exit 1 (SpecCoverageRefused)."""
    checklist = tmp_path / "checklist.md"
    checklist.write_text(
        f"@feature-{_FIXTURE_FEATURE_ID}\n\n"
        "| R1 | a booking produces a confirmation | functional |\n"
    )
    at_dir = tmp_path / "ats"
    at_dir.mkdir()
    (at_dir / "test_fixture_writer.py").write_text(
        _tag_at_source("test_fixture_writer.py", _AT_STRING_LITERAL_FALSE_POSITIVE_PY)
    )

    result = main(
        [
            "--checklist",
            str(checklist),
            "--at-dir",
            str(at_dir),
            "--repo",
            str(tmp_path),
        ]
    )

    assert result == 1, (
        "BUG: string-literal '# covers: R1' DATA was wrongly counted as a "
        f"real marker -- gate returned exit {result} "
        f"({'SpecCoverageVerified -- WRONG' if result == 0 else result}), "
        "expected exit 1 (SpecCoverageRefused, R1 uncovered)"
    )
    event = _first_event(capsys)
    assert event["event"] == "SpecCoverageRefused"
    uncovered = event["uncovered"]
    assert isinstance(uncovered, list) and len(uncovered) == 1
    assert uncovered[0]["id"] == "R1"


def test_string_literal_marker_is_not_real_coverage_typescript(
    tmp_path: Path,
) -> None:
    """NEGATIVE (the bug), TS arm: '// covers: R1' as a JS/TS string literal
    must NOT count -- only a genuine `// covers: R1` comment line counts.
    On the current (unfixed) scanner this assertion FAILS."""
    checklist = tmp_path / "cl.md"
    checklist.write_text(
        f"@feature-{_FIXTURE_FEATURE_ID}\n\n| R1 | booking works | functional |\n"
    )
    at_dir = tmp_path / "ats"
    at_dir.mkdir()
    (at_dir / "fixture.test.ts").write_text(
        _tag_at_source("fixture.test.ts", _AT_STRING_LITERAL_FALSE_POSITIVE_TS)
    )

    result = main(
        [
            "--checklist",
            str(checklist),
            "--at-dir",
            str(at_dir),
            "--repo",
            str(tmp_path),
        ]
    )

    assert result == 1, (
        "BUG: TS string-literal '// covers: R1' was wrongly counted as a "
        f"real marker -- gate returned exit {result}, expected exit 1 "
        "(SpecCoverageRefused, R1 uncovered)"
    )


def test_string_literal_decoy_does_not_mask_a_real_marker_elsewhere(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Combined proof (anti-over-correction): a string-literal decoy for R1
    living ALONGSIDE a REAL '# covers: R2' comment marker in another file --
    R1 must stay uncovered (decoy ignored) while R2 is covered (real marker
    still honored). Guards against a fix that over-corrects and stops
    recognizing genuine markers."""
    checklist = tmp_path / "checklist.md"
    checklist.write_text(_CHECKLIST_TABLE)
    at_dir = tmp_path / "ats"
    at_dir.mkdir()
    (at_dir / "test_fixture_writer.py").write_text(
        _tag_at_source("test_fixture_writer.py", _AT_STRING_LITERAL_FALSE_POSITIVE_PY)
    )
    (at_dir / "test_identity.py").write_text(
        _tag_at_source("test_identity.py", _AT_COVERS_R2_BODY_COMMENT)
    )

    assert (
        main(
            [
                "--checklist",
                str(checklist),
                "--at-dir",
                str(at_dir),
                "--repo",
                str(tmp_path),
            ]
        )
        == 1
    )
    event = _first_event(capsys)
    assert event["event"] == "SpecCoverageRefused"
    uncovered = event["uncovered"]
    assert isinstance(uncovered, list) and len(uncovered) == 1
    assert uncovered[0]["id"] == "R1"


# --- regression: hierarchical requirement identifiers are exact contracts ---
#
# RCA: every grammar in `verify_spec_coverage` accepts only the legacy
# `R\\d+` shape. A legitimate vertically sliced requirement such as
# `R-S01-03` is therefore omitted from the checklist denominator and the
# gate returns SpecCoverageIndeterminate before its Python and Gherkin marker
# readers have a chance to recognize the exact identifier.

_HIERARCHICAL_REQUIREMENT_ID = "R-S01-03"
_HIERARCHICAL_CHECKLIST = (
    f"@feature-{_FIXTURE_FEATURE_ID}\n\n"
    "| ID | Requirement | Category |\n"
    "|----|-------------|----------|\n"
    f"| {_HIERARCHICAL_REQUIREMENT_ID} | installed Codex host starts the slice | functional |\n"
)


def _write_hierarchical_coverage_corpus(
    tmp_path: Path, *at_files: tuple[str, str]
) -> tuple[str, str]:
    """Write one hierarchical checklist and a non-empty AT corpus."""
    checklist = tmp_path / "checklist.md"
    checklist.write_text(_HIERARCHICAL_CHECKLIST)
    at_dir = tmp_path / "ats"
    at_dir.mkdir()
    for name, source in at_files:
        (at_dir / name).write_text(_tag_at_source(name, source))
    return str(checklist), str(at_dir)


def test_python_marker_covers_exact_hierarchical_requirement_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Positive: an exact Python marker covers `R-S01-03` end-to-end.

    This drives the public CLI rather than a reader helper: the requirement
    must be parsed into the denominator *and* the Python marker must be
    attributed to the exact same identity.
    """
    checklist, at_dir = _write_hierarchical_coverage_corpus(
        tmp_path,
        (
            "test_hierarchical.py",
            '@pytest.mark.covers("R-S01-03")\n'
            "def test_installed_codex_host_starts_slice():\n"
            "    assert True\n",
        ),
    )

    assert (
        main(["--checklist", checklist, "--at-dir", at_dir, "--repo", str(tmp_path)])
        == 0
    ), (
        "BUG: an exact Python coverage marker for R-S01-03 must verify the "
        "hierarchical checklist row rather than degrading INDETERMINATE"
    )
    assert _first_event(capsys)["event"] == "SpecCoverageVerified"


def test_gherkin_tag_covers_exact_hierarchical_requirement_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Positive: an exact Gherkin tag covers `R-S01-03` end-to-end."""
    checklist, at_dir = _write_hierarchical_coverage_corpus(
        tmp_path,
        (
            "installed-host.feature",
            "@covers-R-S01-03\n"
            "Feature: Installed Codex host\n\n"
            "  Scenario: Start an installed slice\n"
            "    Given an installed Codex host\n"
            "    When it starts a slice\n"
            "    Then the slice starts\n",
        ),
    )

    assert (
        main(["--checklist", checklist, "--at-dir", at_dir, "--repo", str(tmp_path)])
        == 0
    ), (
        "BUG: an exact Gherkin @covers-R-S01-03 tag must verify the "
        "hierarchical checklist row rather than degrading INDETERMINATE"
    )
    assert _first_event(capsys)["event"] == "SpecCoverageVerified"


def test_uncovered_hierarchical_requirement_is_refused_not_indeterminate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE: a valid but uncovered hierarchy row is a visible refusal.

    This distinguishes a genuine uncovered requirement (exit 1) from an
    unsupported identifier grammar (exit 2). A non-empty unrelated corpus
    proves the result is not the empty-corpus degrade path.
    """
    checklist, at_dir = _write_hierarchical_coverage_corpus(
        tmp_path,
        ("test_unrelated.py", "def test_unrelated():\n    assert True\n"),
    )

    assert (
        main(["--checklist", checklist, "--at-dir", at_dir, "--repo", str(tmp_path)])
        == 1
    ), (
        "BUG: R-S01-03 is a valid requirement identity; without an exact "
        "AT it must be REFUSED (1), never treated as malformed/INDETERMINATE (2)"
    )
    event = _first_event(capsys)
    assert event["event"] == "SpecCoverageRefused"
    uncovered = event["uncovered"]
    assert isinstance(uncovered, list) and [row["id"] for row in uncovered] == [
        _HIERARCHICAL_REQUIREMENT_ID
    ]


def test_legacy_numeric_requirement_id_remains_supported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Compatibility: the existing `R1` grammar remains a valid exact ID."""
    checklist = tmp_path / "checklist.md"
    checklist.write_text(
        f"@feature-{_FIXTURE_FEATURE_ID}\n\n| R1 | legacy booking works | functional |\n"
    )
    at_dir = tmp_path / "ats"
    at_dir.mkdir()
    (at_dir / "test_legacy.py").write_text(
        _tag_at_source(
            "test_legacy.py",
            '@pytest.mark.covers("R1")\ndef test_legacy_booking():\n    assert True\n',
        )
    )

    assert (
        main(
            [
                "--checklist",
                str(checklist),
                "--at-dir",
                str(at_dir),
                "--repo",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert _first_event(capsys)["event"] == "SpecCoverageVerified"


@pytest.mark.parametrize(
    "lookalike",
    [
        "R-S1-03",  # missing zero in the slice segment
        "R-S01-3",  # missing zero in the requirement segment
        "prefix-R-S01-03",  # prefix partial must not cover the exact ID
        "R-S01-03-suffix",  # suffix partial must not cover the exact ID
    ],
)
def test_hierarchical_marker_lookalikes_do_not_cover_exact_requirement(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], lookalike: str
) -> None:
    """Negative precision proof: near IDs cannot cover `R-S01-03`.

    The parser must admit the valid canonical identity without weakening its
    equality relation into prefix/suffix or zero-insensitive matching.
    """
    checklist, at_dir = _write_hierarchical_coverage_corpus(
        tmp_path,
        (
            "test_lookalike.py",
            f'@pytest.mark.covers("{lookalike}")\n'
            "def test_lookalike_marker():\n"
            "    assert True\n",
        ),
    )

    assert (
        main(["--checklist", checklist, "--at-dir", at_dir, "--repo", str(tmp_path)])
        == 1
    ), (
        f"BUG: marker {lookalike!r} is not the exact canonical ID "
        f"{_HIERARCHICAL_REQUIREMENT_ID!r}; it must leave that row REFUSED"
    )
    event = _first_event(capsys)
    assert event["event"] == "SpecCoverageRefused"
    uncovered = event["uncovered"]
    assert isinstance(uncovered, list) and [row["id"] for row in uncovered] == [
        _HIERARCHICAL_REQUIREMENT_ID
    ]

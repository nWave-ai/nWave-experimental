"""Acceptance tests -- `validate_language_adapter_catalog` degrades LOUD on
an unreadable catalog path (regression, Vera examine finding #77, GDP-3/6).

Contract under test (EXISTING code, genuine BEHAVIORAL defect -- not
MISSING_FUNCTIONALITY): `scripts/cli/validate_language_adapter_catalog.py`
`main(argv)` / `validate_catalog(catalog_path)`.

FACTUAL CORRECTION established by reading the CLI before authoring (mirrors
the `test_check_port_realization_cli.py` precedent of pinning a factual
correction inline): the dispatch describing this defect names it as the
`--check-conformance` mode. Reading `main()` (line 465-470) shows
`--check-conformance` takes ZERO catalog-path argument at all -- it always
resolve-and-probes the LIVE `nwave.lang.adapter` registry
(`run_conformance_gate()`, no `args[1:]` consumed) and its OWN unresolvable-
input path already degrades cleanly today (verified empirically: a
`DiscoveryResolutionError` -> exit 3, structured, no traceback -- the SAME
clean shape the dispatch attributes to the `--check-port-realization`
sibling). So a literal `--check-conformance <nonexistent-path>` invocation
does NOT reproduce the reported symptom (confirmed via a one-shot repro: exit
1, zero traceback, the live-registry gap lane -- the path is silently
ignored, a DIFFERENT and separately-trackable defect, not this one).

The reported symptom -- a raw Python traceback + an incomplete diagnostic on
an unreadable catalog path -- reproduces on the CLI's BASE mode instead: `python
-m scripts.cli.validate_language_adapter_catalog <path>` (no flag), which IS
the CLI's literal "catalog conformance check" in plain-English terms (the
module docstring calls it validating the catalog against the schema +
grounding its `witnesses:`). `validate_catalog()` (line 125-144) calls
`catalog_path.read_text(encoding="utf-8")` (line 127) with ZERO exception
handling -- confirmed via three one-shot repros, each producing a raw
`Traceback (most recent call last)` block on stderr + exit 1 (colliding with
the unrelated witness-not-found gap lane):

  * nonexistent path             -> uncaught `FileNotFoundError`
  * a directory passed as catalog -> uncaught `IsADirectoryError`
  * unparseable YAML content      -> uncaught `yaml.parser.ParserError`

None of the three malformed-input classes is caught; all three leak the
interpreter's raw traceback text to the user and all three exit 1 (the
"malformed" lane is documented as exit 2, so even the exit code is wrong).
Compare the sibling `--check-port-realization` mode's OWN unresolvable-input
handling (`run_port_realization_gate`, line 421-433): a `try/except` around
resolution, ONE clear diagnostic line naming the target, exit 3
(`PORT_REALIZATION_GATE_INDETERMINATE`) -- verified empirically clean
(`--plugin does.not.exist:Nope` -> exit 3, single line, no traceback). That
is the shape `validate_catalog` must adopt (GDP-6: degrade LOUD, never
silent-wrong, never a raw traceback; GDP-3: WHAT the path is / WHY it could
not be read / a controlled, documented exit lane).

Today's incomplete FAIL-LOUD names 2 of 4 expected diagnostic elements: (1)
the offending path IS present in the exception text, (2) an exception CLASS
name is present -- but (3) there is NO HOW-to-fix guidance and (4) the output
is NOT a single clean block (it is an interpreter stack trace), so this AT
targets exit lane 3 (INDETERMINATE, reusing the SAME lane the sibling modes
already use for "the input is unresolvable" -- never silently colliding
with the existing witness-gap lane 1 or the schema-malformed lane 2).

Driving surface (Mandate-13 driving-port-only, Layer 3 composition, IN-
PROCESS default): the real `scripts.cli.validate_language_adapter_catalog`
CLI driver (`main(argv)`), captured via `capsys` -- no subprocess fork
(mirrors `tests/des/acceptance/test_check_contract_shape_declarations.py`
Scenario 5's identical in-process degrade-LOUD pattern for the same defect
class). `main()` is called directly (not `sys.exit(main(...))`), so an
uncaught exception propagates as a normal Python exception into the test
body -- caught here via `try/except` and turned into a semantic
`pytest.fail`, never a collection-time BROKEN failure (RED-for-right-reason,
ADR-025 / Mandate-7).

CONTRACT_SHAPE: unbounded-preservation for every scenario -- the CLI is a
read-only inspection (no state mutation); the exit code + printed diagnostic
are the port-exposed observables.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.cli.validate_language_adapter_catalog import main


# ---------------------------------------------------------------------------
# Shared driving-port helper
# ---------------------------------------------------------------------------


def _run_main(
    capsys: pytest.CaptureFixture[str], catalog_path: Path
) -> tuple[int | None, str, Exception | None]:
    """Drive `main([str(catalog_path)])` in-process; never let a raised
    exception escape uncaptured -- return it instead so callers can assert
    on it directly (RED-for-right-reason: a genuine behavioral defect, not
    a pytest collection/BROKEN failure)."""
    exit_code: int | None = None
    raised: Exception | None = None
    try:
        exit_code = main([str(catalog_path)])
    except Exception as exc:
        raised = exc
    captured = capsys.readouterr()
    return exit_code, captured.out + captured.err, raised


# ---------------------------------------------------------------------------
# Scenario 1 -- POSITIVE: a nonexistent catalog path degrades to
# INDETERMINATE (exit 3), one clear diagnostic naming the path, no traceback.
# CONTRACT_SHAPE: unbounded-preservation
# ---------------------------------------------------------------------------


def test_main_degrades_to_indeterminate_on_a_nonexistent_catalog_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: Vera examine finding #77; GDP-3 (WHAT/WHY/HOW,
    self-explaining) + GDP-6 (degrade LOUD, never silent-wrong).

    Today `validate_catalog` lets an uncaught `FileNotFoundError` from
    `catalog_path.read_text()` escape all the way to the interpreter,
    producing a raw traceback on stderr and exit 1 (colliding with the
    unrelated witness-not-found lane). The fix must catch this and degrade
    to the SAME structured INDETERMINATE shape the sibling
    `--check-port-realization` mode already uses for an unresolvable input:
    exit 3, a single clear diagnostic naming the missing path, never a raw
    Python traceback.
    """
    missing_catalog = tmp_path / "does-not-exist" / "language-adapter-ports.yaml"

    exit_code, combined_output, raised = _run_main(capsys, missing_catalog)

    if raised is not None:
        pytest.fail(
            "degrade-LOUD violation (GDP-6): a nonexistent catalog path must "
            f"return exit 3 (INDETERMINATE) with a diagnostic, not raise "
            f"{type(raised).__name__}: {raised}"
        )

    assert exit_code == 3, (
        f"expected the INDETERMINATE lane (an unreadable catalog path) -- "
        f"got exit {exit_code}. output={combined_output!r}"
    )
    assert exit_code not in (0, 1, 2), (
        "must never collide with the existing 0 conformant / 1 witness-gap / "
        f"2 malformed-schema lanes; got exit {exit_code}"
    )
    assert "Traceback (most recent call last)" not in combined_output, (
        f"must degrade LOUD with a diagnostic, never a raw Python traceback: "
        f"{combined_output!r}"
    )
    assert str(missing_catalog) in combined_output, (
        f"diagnostic must name the unreadable path {missing_catalog!s}: "
        f"{combined_output!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 2 -- NEGATIVE AT: the WRONG outcome (a raw Python traceback
# reaching the user) is NOT produced for ANY malformed-catalog-path case.
# CONTRACT_SHAPE: unbounded-preservation
# ---------------------------------------------------------------------------


def _malformed_directory_as_catalog(tmp_path: Path) -> Path:
    """A directory passed where a catalog FILE is expected."""
    directory = tmp_path / "a-directory-not-a-file"
    directory.mkdir()
    return directory


def _malformed_unparseable_yaml(tmp_path: Path) -> Path:
    """A catalog file whose content is not parseable YAML."""
    bad_yaml = tmp_path / "unparseable-catalog.yaml"
    bad_yaml.write_text("not: [valid\n", encoding="utf-8")
    return bad_yaml


def _malformed_nonexistent_path(tmp_path: Path) -> Path:
    return tmp_path / "still-does-not-exist" / "language-adapter-ports.yaml"


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "build_malformed_catalog_path",
    [
        _malformed_nonexistent_path,
        _malformed_directory_as_catalog,
        _malformed_unparseable_yaml,
    ],
    ids=[
        "nonexistent_path",
        "directory_as_catalog",
        "unparseable_yaml_content",
    ],
)
def test_main_never_lets_a_raw_traceback_reach_the_user_on_a_malformed_catalog_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    build_malformed_catalog_path,
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: Vera examine finding #77; GDP-6 (no silent-wrong, no
    raw traceback -- across the WHOLE malformed-input class, not only the
    nonexistent-path instance Scenario 1 pins).

    Whatever malformed shape the catalog PATH takes (missing entirely, a
    directory, or unparseable content once read), the WRONG outcome -- a raw
    `Traceback (most recent call last)` block reaching the user's stderr --
    must never be produced. `main` must always return a controlled exit
    code with a structured diagnostic instead.
    """
    malformed_catalog_path = build_malformed_catalog_path(tmp_path)

    exit_code, combined_output, raised = _run_main(capsys, malformed_catalog_path)

    if raised is not None:
        pytest.fail(
            "degrade-LOUD violation (GDP-6): a malformed catalog path "
            f"({malformed_catalog_path!s}) must return a controlled exit "
            f"code with a diagnostic, not raise {type(raised).__name__}: "
            f"{raised}"
        )

    assert "Traceback (most recent call last)" not in combined_output, (
        "WRONG outcome produced: a raw Python traceback reached the user for "
        f"malformed catalog path {malformed_catalog_path!s}: {combined_output!r}"
    )
    assert exit_code != 0, (
        "must never silently report a malformed/unreadable catalog path as "
        f"clean (exit 0); got exit {exit_code} for {malformed_catalog_path!s}"
    )

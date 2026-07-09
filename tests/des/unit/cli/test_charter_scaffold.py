"""AT -- `des charter-scaffold` (charter-scaffold feature, slice-01).

The producing tool that makes charter authoring system-paid (GDP-5) and early
(GDP-1): it reads a feature's `## Wave: DISCUSS / [REF] Slice Plan` table and,
for each OBSERVABLE-value slice (Annotation NOT `@infrastructure` /
`@prefactoring`), generates a charter SCAFFOLD at
`docs/product/expectations/<feature-id>/<intent-name>.md` using
`nWave/templates/expectation-charter.md` as the skeleton, Intent pre-filled
from the slice's Value statement VERBATIM. Idempotent (never overwrites);
degrades LOUD (GDP-6) on a missing/malformed feature-delta or absent Slice
Plan.

covers: slice-01 of docs/feature/charter-scaffold/feature-delta.md

RED reason (P1-P4 in-process active-RED, `nw-distill-red-scaffolding`):
`src/des/cli/charter_scaffold.py` does not exist yet. Module-level imports
name ONLY stable, already-shipped entries (`des.cli.validate_feature_delta`'s
verdict constants) -- NEVER the absent SUT module (P1). Each test lazily
imports `main` from `des.cli.charter_scaffold` INSIDE its body (P3); the
resulting `ModuleNotFoundError` is a runtime exception raised WITHIN the
test's own call stack, not a collection-time error -- collection stays
green, and each test fails for a semantic reason once the module ships (P4).

Driving surface: `des.cli.charter_scaffold.main(argv) -> int` invoked
IN-PROCESS against a `tmp_path` fixture repo (composition-root driving
port -- Mandate 16, driving-port-only boundary). No subprocess fork.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.validate_feature_delta import VERDICT_MISSING_SLICE_PLAN


FEATURE_ID = "seat-booking"

#: The real `nWave/templates/expectation-charter.md` "Template" skeleton
#: (verbatim), seeded into the fixture repo at the repo-root-relative path the
#: tool reads it from. Kept byte-faithful to the shipped template so a future
#: template edit that breaks this shape is caught here too.
TEMPLATE_SKELETON = """# <intent, as a human sentence>
ID: EXP-<feature>-<n> · Spec rows: <R…> · Persona: <who>

## Intent
<the value statement: what the user accomplishes, why it matters>

## Preconditions
<start recipe: how to run the system from a clean state, seed state>

## Charter
Explore <area> via <surface: browser/CLI/API> to verify <intent>.

## Expected observations (oracle)
- <observable outcome, user language>
- <negative: what must NOT happen>

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
"""

#: Two observable slices (no `@infrastructure`/`@prefactoring` Annotation) +
#: one @infrastructure slice that must be skipped. Value statements are plain
#: prose (no `|`, no punctuation beyond spaces) so their kebab slug is
#: unambiguous: lowercase words joined by single hyphens.
VALUE_STATEMENT_1 = "A visitor books two seats and sees a countdown"
VALUE_STATEMENT_2 = "A visitor cancels a held seat before payment"
INFRA_VALUE_STATEMENT = "Wire the seat hold repository migration"

SLICE_PLAN_FEATURE_DELTA = f"""# Feature-delta -- seat-booking

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | {VALUE_STATEMENT_1} | pending |  | first observable slice |
| slice-02 | {INFRA_VALUE_STATEMENT} | pending | @infrastructure | plumbing, no user value |
| slice-03 | {VALUE_STATEMENT_2} | pending |  | second observable slice |
"""

#: A feature-delta with a title but no Slice Plan section at all -- the
#: "absent Slice Plan" degrade-LOUD case.
NO_SLICE_PLAN_FEATURE_DELTA = (
    "# Feature-delta -- seat-booking\n\nJust a summary, no plan.\n"
)

#: Dogfood finding (real feature-delta): a Value statement is a full user
#: sentence, not a short label -- 262 chars, well past the 255-byte NAME_MAX
#: most filesystems enforce per path component. A slug derived from the
#: ENTIRE sentence + ".md" crashes the scaffold write with `OSError: File
#: name too long`.
LONG_VALUE_STATEMENT = (
    "A visitor who has been comparing several upcoming community theatre "
    "performances over the past few weeks finally decides during a quiet "
    "evening at home to hold two adjacent seats for the spring gala night "
    "show while checking with their partner about the schedule"
)

#: A filesystem-safe cap on the generated `<intent-name>.md` basename,
#: INCLUDING the `.md` suffix. Comfortably under the 255-byte NAME_MAX most
#: filesystems enforce, and short enough to stay a legible slug (per your
#: ~80-100 char guidance).
MAX_SCAFFOLD_FILENAME_LENGTH = 100

LONG_VALUE_FEATURE_DELTA = f"""# Feature-delta -- seat-booking

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | {LONG_VALUE_STATEMENT} | pending |  | single observable slice |
"""

#: Regression fixture (Vera-found defect, GDP-6 silent-wrong): slice-01 is a
#: well-formed observable row; slice-02's Value statement cell is BLANK. The
#: current implementation's `_kebab_slug("")` returns `""`, so `_scaffold_slice`
#: writes a literal `.md` file (empty kebab-slug stem) and counts it in
#: `created` -- a broken scaffold silently reported as a success.
BLANK_VALUE_STATEMENT_FEATURE_DELTA = f"""# Feature-delta -- seat-booking

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | {VALUE_STATEMENT_1} | pending |  | well-formed observable slice |
| slice-02 |  | pending |  | blank Value statement -- malformed row |
"""


def _seed_repo(repo_root: Path) -> None:
    """Seed the one repo-root-relative asset the tool reads regardless of
    scenario: the expectation-charter template."""
    template_dir = repo_root / "nWave" / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "expectation-charter.md").write_text(
        TEMPLATE_SKELETON, encoding="utf-8"
    )


def _write_feature_delta(repo_root: Path, feature_id: str, content: str) -> Path:
    delta_dir = repo_root / "docs" / "feature" / feature_id
    delta_dir.mkdir(parents=True, exist_ok=True)
    path = delta_dir / "feature-delta.md"
    path.write_text(content, encoding="utf-8")
    return path


def _expectations_dir(repo_root: Path, feature_id: str) -> Path:
    return repo_root / "docs" / "product" / "expectations" / feature_id


def _intent_section(content: str) -> str:
    """Test-local helper (not production code): the body of the `## Intent`
    section, up to the next `##` heading."""
    lines = content.splitlines()
    try:
        start = lines.index("## Intent") + 1
    except ValueError:
        return ""
    body: list[str] = []
    for line in lines[start:]:
        if line.startswith("##"):
            break
        body.append(line)
    return "\n".join(body)


def _invoke(repo_root: Path, capsys, feature_id: str = FEATURE_ID) -> tuple[int, dict]:
    """The driving call every test uses: in-process `main()` (P2), stdout
    captured and parsed as the `--format json` contract token."""
    from des.cli.charter_scaffold import main

    exit_code = main(
        [
            "--feature-id",
            feature_id,
            "--repo-root",
            str(repo_root),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


def test_generates_a_scaffold_for_each_observable_slice(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    _write_feature_delta(tmp_path, FEATURE_ID, SLICE_PLAN_FEATURE_DELTA)

    exit_code, payload = _invoke(tmp_path, capsys)

    expectations_dir = _expectations_dir(tmp_path, FEATURE_ID)
    created_files = (
        sorted(p.name for p in expectations_dir.glob("*.md"))
        if expectations_dir.is_dir()
        else []
    )

    assert exit_code == 0
    assert payload["feature_id"] == FEATURE_ID
    assert payload["observable_slices"] == 2
    assert len(created_files) == 2
    assert "a-visitor-books-two-seats-and-sees-a-countdown.md" in created_files
    assert "a-visitor-cancels-a-held-seat-before-payment.md" in created_files
    assert len(payload["created"]) == 2


def test_generated_scaffold_intent_contains_the_value_statement_verbatim(
    tmp_path: Path, capsys
) -> None:
    _seed_repo(tmp_path)
    _write_feature_delta(tmp_path, FEATURE_ID, SLICE_PLAN_FEATURE_DELTA)

    _invoke(tmp_path, capsys)

    scaffold_path = (
        _expectations_dir(tmp_path, FEATURE_ID)
        / "a-visitor-books-two-seats-and-sees-a-countdown.md"
    )
    content = scaffold_path.read_text(encoding="utf-8")
    intent_body = _intent_section(content)

    assert VALUE_STATEMENT_1 in intent_body
    # Uncontaminated by construction: the tool only ever saw the Value
    # statement column, never design/impl vocabulary.
    assert "src/des" not in content
    assert "class " not in content
    assert "def " not in content


def test_does_not_generate_a_charter_for_the_infrastructure_slice(
    tmp_path: Path, capsys
) -> None:
    _seed_repo(tmp_path)
    _write_feature_delta(tmp_path, FEATURE_ID, SLICE_PLAN_FEATURE_DELTA)

    exit_code, payload = _invoke(tmp_path, capsys)

    expectations_dir = _expectations_dir(tmp_path, FEATURE_ID)
    created_files = (
        sorted(p.name for p in expectations_dir.glob("*.md"))
        if expectations_dir.is_dir()
        else []
    )

    assert exit_code == 0
    assert not any("seat-hold-repository-migration" in name for name in created_files)
    assert len(created_files) == 2  # only the 2 observable slices, never slice-02
    assert payload["observable_slices"] == 2  # slice-02 excluded from the count


def test_does_not_overwrite_an_existing_charter(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    _write_feature_delta(tmp_path, FEATURE_ID, SLICE_PLAN_FEATURE_DELTA)

    # First run creates the scaffolds.
    first_exit, first_payload = _invoke(tmp_path, capsys)
    assert first_exit == 0
    assert len(first_payload["created"]) == 2

    # A fresh PO has since filled in judgment -- seed a sentinel marking their
    # work so a second run must leave it untouched.
    scaffold_path = (
        _expectations_dir(tmp_path, FEATURE_ID)
        / "a-visitor-books-two-seats-and-sees-a-countdown.md"
    )
    sentinel = "SENTINEL: fresh-PO-authored oracle, must survive re-run\n"
    scaffold_path.write_text(sentinel, encoding="utf-8")

    second_exit, second_payload = _invoke(tmp_path, capsys)

    assert second_exit == 0
    # Idempotent: nothing NEW created on the 2nd run -- both existing
    # scaffolds are reported skipped.
    assert second_payload["created"] == []
    assert len(second_payload["skipped"]) == 2
    # The negative assertion this test exists for: the sentinel content is
    # NOT clobbered by the 2nd run.
    assert scaffold_path.read_text(encoding="utf-8") == sentinel


@pytest.mark.parametrize(
    "seed_feature_delta,expected_verdict,expected_detail_substring",
    [
        pytest.param(
            None,
            "missing-feature-delta",
            FEATURE_ID,
            id="feature_delta_file_absent",
        ),
        pytest.param(
            NO_SLICE_PLAN_FEATURE_DELTA,
            VERDICT_MISSING_SLICE_PLAN,
            "Slice Plan",
            id="slice_plan_section_absent",
        ),
    ],
)
def test_degrades_loud_on_malformed_or_missing_feature_delta(
    tmp_path: Path,
    capsys,
    seed_feature_delta: str | None,
    expected_verdict: str,
    expected_detail_substring: str,
) -> None:
    _seed_repo(tmp_path)
    if seed_feature_delta is not None:
        _write_feature_delta(tmp_path, FEATURE_ID, seed_feature_delta)

    exit_code, payload = _invoke(tmp_path, capsys)

    # Degrade-LOUD (GDP-6): never a silent success, never a partial scaffold
    # that looks complete.
    assert exit_code != 0
    assert payload["verdict"] == expected_verdict
    assert expected_detail_substring in payload["detail"]
    expectations_dir = _expectations_dir(tmp_path, FEATURE_ID)
    assert not expectations_dir.is_dir() or not list(expectations_dir.glob("*.md"))


def test_generated_scaffold_filename_is_length_bounded_for_a_long_value_statement(
    tmp_path: Path, capsys
) -> None:
    """Dogfood regression: a real Value statement is a full sentence (262
    chars here). The `<intent-name>.md` basename must be TRUNCATED to a
    filesystem-safe length, not derived from the whole sentence -- driving
    through `main()` (the composition-root port), never `_kebab_slug`
    directly (Mandate 16, driving-port-only boundary).

    The current implementation (`_scaffold_slice` -> `_kebab_slug`) has no
    length bound, so this reproduces the dogfood crash end-to-end through the
    real driving port; the crash is caught and turned into a clean
    `AssertionError` (fail-for-right-reason) rather than surfacing as an
    unhandled `OSError` ERROR.
    """
    _seed_repo(tmp_path)
    _write_feature_delta(tmp_path, FEATURE_ID, LONG_VALUE_FEATURE_DELTA)

    try:
        exit_code, payload = _invoke(tmp_path, capsys)
    except OSError as exc:
        pytest.fail(
            "des charter-scaffold crashed with OSError while writing the "
            f"scaffold for a long Value statement ({exc!r}); the intent-name "
            "slug must be length-bounded (truncated), never derived from the "
            "entire Value-statement sentence"
        )

    expectations_dir = _expectations_dir(tmp_path, FEATURE_ID)
    created_files = (
        list(expectations_dir.glob("*.md")) if expectations_dir.is_dir() else []
    )

    assert exit_code == 0
    assert payload["created"] == [created_files[0].name]
    assert len(created_files) == 1
    filename = created_files[0].name

    # Bounded: filesystem-safe length, well under NAME_MAX.
    assert len(filename) <= MAX_SCAFFOLD_FILENAME_LENGTH

    # Still meaningful: a non-empty kebab slug derived from the START of the
    # Value statement (truncation, not silent emptying).
    slug = filename.removesuffix(".md")
    assert slug
    first_word = LONG_VALUE_STATEMENT.split(maxsplit=1)[0].lower()
    assert slug.startswith(first_word)

    # Deterministic: re-running against the SAME long Value statement resolves
    # back to the SAME (now-existing) filename -- idempotent skip, no new file.
    second_exit, second_payload = _invoke(tmp_path, capsys)
    assert second_exit == 0
    assert second_payload["created"] == []
    assert second_payload["skipped"] == [filename]


def test_blank_value_statement_row_is_skipped_not_scaffolded_as_garbage_file(
    tmp_path: Path, capsys
) -> None:
    """Regression (Vera-found defect, GDP-6 silent-wrong):
    `docs/product/expectations/<feature-id>/.md` (empty kebab-slug stem) must
    never be produced for a blank Value statement row, and that row must
    never be silently counted in `created`. It is either reported in
    `skipped` (with a reason) OR the whole run is a LOUD non-zero reject
    naming the offending slice ('slice-02'). The well-formed row alongside
    it (slice-01) must still scaffold correctly -- the tool still works for
    good input.
    """
    _seed_repo(tmp_path)
    _write_feature_delta(tmp_path, FEATURE_ID, BLANK_VALUE_STATEMENT_FEATURE_DELTA)

    exit_code, payload = _invoke(tmp_path, capsys)

    expectations_dir = _expectations_dir(tmp_path, FEATURE_ID)
    all_files = (
        sorted(p.name for p in expectations_dir.glob("*.md"))
        if expectations_dir.is_dir()
        else []
    )

    # (a) never a `.md` garbage file (empty kebab-slug stem) on disk, no
    # matter which remediation path (skip-and-report vs loud-reject) is taken.
    assert ".md" not in all_files, (
        "blank Value statement row produced a garbage '.md' scaffold "
        f"(empty kebab-slug stem); files on disk: {all_files}"
    )

    well_formed_slug = "a-visitor-books-two-seats-and-sees-a-countdown.md"

    if exit_code == 0:
        # (b) the blank row is never silently counted as `created`.
        assert ".md" not in payload["created"], (
            "blank Value statement row's garbage '.md' scaffold was counted "
            f"in 'created': {payload['created']}"
        )
        assert ".md" in payload.get("skipped", []) or any(
            "slice-02" in entry for entry in payload.get("skipped", [])
        ), (
            "blank Value statement row was accepted (exit 0) but neither "
            f"rejected nor reported in 'skipped'; payload: {payload}"
        )
        # the tool still works for good input alongside the blank row.
        assert well_formed_slug in all_files
        assert well_formed_slug in payload["created"]
    else:
        # (b, alternative) a LOUD non-zero reject naming the offending slice.
        assert "slice-02" in payload["detail"], (
            "run rejected but detail does not name the offending slice "
            f"'slice-02': {payload['detail']!r}"
        )


def test_blank_value_statement_never_creates_a_dotmd_garbage_file(
    tmp_path: Path, capsys
) -> None:
    """Negative regression (Vera-found defect): a blank Value statement must
    NEVER emit a scaffold literally named `.md` (empty kebab-slug stem), and
    it must NEVER appear in the `created` list -- the exact GDP-6
    silent-wrong defect: a broken file counted as a successful scaffold.
    """
    _seed_repo(tmp_path)
    _write_feature_delta(tmp_path, FEATURE_ID, BLANK_VALUE_STATEMENT_FEATURE_DELTA)

    exit_code, payload = _invoke(tmp_path, capsys)

    expectations_dir = _expectations_dir(tmp_path, FEATURE_ID)
    garbage_path = expectations_dir / ".md"

    assert not garbage_path.exists(), (
        "des charter-scaffold created a literal '.md' garbage scaffold "
        "(empty kebab-slug stem) for a blank Value statement row"
    )
    assert ".md" not in payload.get("created", []), (
        "blank Value statement row's garbage '.md' scaffold was silently "
        f"counted as created: {payload['created']}"
    )

"""AT -- `des charter-scaffold --seed-mode bug-observable` (slice-03).

slice-03 EXTENDS the shipped slice-01 producing tool
(`src/des/cli/charter_scaffold.py`) with a `--seed-mode
{slice-plan,bug-observable}` selector (default `slice-plan`, byte-identical
for every existing caller) + `--observable <text>`.

`--seed-mode bug-observable` generates ONE uncontaminated charter scaffold
straight from a bug's observable behaviour: NO Slice Plan is read (there is
none for a raw bugfix), the Intent is PRE-FILLED from the `--observable` text
VERBATIM (user-side), the judgment sections (oracle / start-recipe) are left
as the template's fresh-PO-fill TODO placeholders -- the SAME skeleton the
slice-01 slice-plan path emits. Idempotent (never overwrites); degrades LOUD
(GDP-6) on a missing/blank `--observable`, never a `.md` garbage file.

covers: slice-03 of docs/feature/charter-scaffold/feature-delta.md

RED reason (P1-P4 in-process active-RED, `nw-distill-red-scaffolding`):
`des.cli.charter_scaffold.main` exists (slice-01) but its argparse has NO
`--seed-mode` / `--observable` flags yet. Module-level imports name ONLY the
stable shipped `main` (P1). Each test drives it IN-PROCESS (P2); the absent
flags surface as an argparse `SystemExit(2)` reached WITHIN the test body's
own call (P3), caught and re-raised as a clear `AssertionError`
(fail-for-right-reason, P4). Collection stays green; each test fails for a
semantic reason and goes GREEN once slice-03 ships the flags.

Placement: a NEW file (not appended to `test_charter_scaffold.py`) so the
carpaccio slice-gate counts ONLY slice-03's ATs against the ceiling -- the
slice-01/02 tests in the sibling file are a separate, already-shipped slice.
Same imports/fixtures/pattern as `test_charter_scaffold.py`.

Driving surface: `des.cli.charter_scaffold.main(argv) -> int` invoked
IN-PROCESS against a `tmp_path` fixture repo (composition-root driving
port -- Mandate 16, driving-port-only boundary). No subprocess fork.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


#: A plain bug-behaviour sentence (user-side, no design/impl vocabulary) --
#: the `--observable` text a `/nw-bugfix` caller supplies verbatim.
BUG_OBSERVABLE_TEXT = (
    "Clicking Save twice creates two duplicate invoices instead of one"
)

#: The NEW degrade-LOUD verdict token slice-03 adds for `--seed-mode
#: bug-observable` with a missing/blank `--observable`. Mirrors the shipped
#: `missing-feature-delta` / `missing-charter-template` naming convention in
#: `des.cli.charter_scaffold` -- defined LOCALLY here (not imported) because
#: it does not exist in the shipped module yet: this is the DISTILL-authored
#: contract the crafter implements verbatim to reach GREEN.
VERDICT_MISSING_OBSERVABLE = "missing-observable"

#: The real `nWave/templates/expectation-charter.md` "Template" skeleton
#: (byte-faithful, seeded into the fixture repo at the repo-root-relative path
#: the tool reads it from) -- same skeleton the slice-01 AT uses.
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


def _seed_repo(repo_root: Path) -> None:
    """Seed the one repo-root-relative asset the tool reads regardless of
    scenario: the expectation-charter template."""
    template_dir = repo_root / "nWave" / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "expectation-charter.md").write_text(
        TEMPLATE_SKELETON, encoding="utf-8"
    )


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


def _invoke_bug_observable(
    repo_root: Path,
    capsys,
    feature_id: str,
    observable: str | None,
) -> tuple[int, dict]:
    """The slice-03 driving call: in-process `main()` (P2) with `--seed-mode
    bug-observable` -- a flag the current shipped CLI does not recognise yet.

    Wraps the call so argparse rejecting the not-yet-existing `--seed-mode` /
    `--observable` flags surfaces as a clear `AssertionError` (fail-for-
    right-reason, P4) instead of an unhandled `SystemExit` propagating out of
    the test body. `observable=None` omits the `--observable` flag entirely
    (the "flag never supplied" case).
    """
    from des.cli.charter_scaffold import main

    argv = ["--seed-mode", "bug-observable", "--feature-id", feature_id]
    if observable is not None:
        argv += ["--observable", observable]
    argv += ["--repo-root", str(repo_root), "--format", "json"]

    try:
        exit_code = main(argv)
    except SystemExit as exc:
        pytest.fail(
            "des charter-scaffold --seed-mode bug-observable was rejected "
            f"by argparse (SystemExit code={exc.code}) -- the '--seed-mode' "
            "/ '--observable' flags do not exist yet on the shipped CLI; "
            "implement them per feature-delta.md slice-03 to make this pass"
        )
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


def test_bug_observable_generates_one_scaffold_with_observable_verbatim_in_intent(
    tmp_path: Path, capsys
) -> None:
    """Happy path: exactly ONE charter scaffold is created under
    docs/product/expectations/<feature-id>/, its Intent section reads the
    --observable text VERBATIM, and the judgment sections (Preconditions /
    Charter / Expected observations) are left as the template's fresh-PO-fill
    TODO placeholders -- the tool lifts only the observable text, it never
    invents judgment (same contract as the slice-01 Value-statement path).
    """
    _seed_repo(tmp_path)
    feature_id = "fix-duplicate-invoice"

    exit_code, payload = _invoke_bug_observable(
        tmp_path, capsys, feature_id, BUG_OBSERVABLE_TEXT
    )

    expectations_dir = _expectations_dir(tmp_path, feature_id)
    created_files = (
        sorted(p.name for p in expectations_dir.glob("*.md"))
        if expectations_dir.is_dir()
        else []
    )

    assert exit_code == 0
    assert payload["feature_id"] == feature_id
    assert len(created_files) == 1
    assert payload["created"] == [created_files[0]]

    # Meaningful, not arbitrary: the slug derives from the observable text.
    first_word = BUG_OBSERVABLE_TEXT.split(maxsplit=1)[0].lower()
    assert created_files[0].startswith(first_word)

    content = (expectations_dir / created_files[0]).read_text(encoding="utf-8")
    intent_body = _intent_section(content)
    assert BUG_OBSERVABLE_TEXT in intent_body
    # Uncontaminated by construction: only the observable text was seen.
    assert "src/des" not in content
    assert "class " not in content
    assert "def " not in content

    # Judgment sections untouched -- still the template's TODO placeholders.
    assert (
        "<start recipe: how to run the system from a clean state, seed state>"
        in content
    )
    assert "<observable outcome, user language>" in content
    assert "<negative: what must NOT happen>" in content


def test_bug_observable_second_run_is_idempotent_and_reports_skipped(
    tmp_path: Path, capsys
) -> None:
    """Idempotent re-run: running twice does NOT overwrite / re-create the
    scaffold; the second run reports it in `skipped`, and a fresh-PO edit
    made between runs survives untouched.
    """
    _seed_repo(tmp_path)
    feature_id = "fix-duplicate-invoice-idempotent"

    first_exit, first_payload = _invoke_bug_observable(
        tmp_path, capsys, feature_id, BUG_OBSERVABLE_TEXT
    )
    assert first_exit == 0
    assert len(first_payload["created"]) == 1

    expectations_dir = _expectations_dir(tmp_path, feature_id)
    scaffold_path = next(expectations_dir.glob("*.md"))
    sentinel = "SENTINEL: fresh-PO-authored oracle, must survive re-run\n"
    scaffold_path.write_text(sentinel, encoding="utf-8")

    second_exit, second_payload = _invoke_bug_observable(
        tmp_path, capsys, feature_id, BUG_OBSERVABLE_TEXT
    )

    assert second_exit == 0
    assert second_payload["created"] == []
    assert len(second_payload["skipped"]) == 1
    assert scaffold_path.read_text(encoding="utf-8") == sentinel


@pytest.mark.parametrize(
    "observable",
    [
        pytest.param(None, id="observable_flag_omitted"),
        pytest.param("", id="observable_blank_string"),
        pytest.param("   ", id="observable_whitespace_only"),
    ],
)
def test_bug_observable_missing_observable_never_creates_a_garbage_scaffold(
    tmp_path: Path, capsys, observable: str | None
) -> None:
    """Negative (GDP-6 degrade-LOUD, the slice-01 blank-Value lesson applies
    here too): a missing OR blank --observable with --seed-mode
    bug-observable must NEVER produce a `.md` garbage file / empty-Intent
    scaffold. Instead: a LOUD non-zero reject with a clear message naming
    'observable' -- never a silent no-op.
    """
    _seed_repo(tmp_path)
    feature_id = "fix-missing-observable"

    exit_code, payload = _invoke_bug_observable(
        tmp_path, capsys, feature_id, observable
    )

    expectations_dir = _expectations_dir(tmp_path, feature_id)

    assert exit_code != 0
    assert payload["verdict"] == VERDICT_MISSING_OBSERVABLE
    assert "observable" in payload["detail"].lower()
    assert payload["created"] == []
    assert not expectations_dir.is_dir() or not list(expectations_dir.glob("*.md"))


def test_explicit_seed_mode_slice_plan_matches_default_behaviour(
    tmp_path: Path, capsys
) -> None:
    """Default seed-mode regression: an existing slice-plan feature-delta
    still scaffolds its observable slices when `--seed-mode slice-plan` is
    passed EXPLICITLY -- byte-identical to the pre-slice-03 shipped default
    (feature-delta.md slice-03: 'slice-plan stays the default seed-mode ...
    byte-identical for existing callers'). Proves the new flag's default path
    is the unchanged slice-01 behaviour.
    """
    feature_id = "seat-booking"
    value_statement_1 = "A visitor books two seats and sees a countdown"
    infra_value_statement = "Wire the seat hold repository migration"
    value_statement_2 = "A visitor cancels a held seat before payment"
    slice_plan_feature_delta = f"""# Feature-delta -- seat-booking

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | {value_statement_1} | pending |  | first observable slice |
| slice-02 | {infra_value_statement} | pending | @infrastructure | plumbing, no user value |
| slice-03 | {value_statement_2} | pending |  | second observable slice |
"""

    _seed_repo(tmp_path)
    delta_dir = tmp_path / "docs" / "feature" / feature_id
    delta_dir.mkdir(parents=True, exist_ok=True)
    (delta_dir / "feature-delta.md").write_text(
        slice_plan_feature_delta, encoding="utf-8"
    )

    from des.cli.charter_scaffold import main

    argv = [
        "--seed-mode",
        "slice-plan",
        "--feature-id",
        feature_id,
        "--repo-root",
        str(tmp_path),
        "--format",
        "json",
    ]
    try:
        exit_code = main(argv)
    except SystemExit as exc:
        pytest.fail(
            "des charter-scaffold --seed-mode slice-plan was rejected by "
            f"argparse (SystemExit code={exc.code}) -- the '--seed-mode' "
            "flag does not exist yet on the shipped CLI; implement it per "
            "feature-delta.md slice-03 (default 'slice-plan', byte-identical "
            "to the existing behaviour) to make this pass"
        )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    expectations_dir = _expectations_dir(tmp_path, feature_id)
    created_files = (
        sorted(p.name for p in expectations_dir.glob("*.md"))
        if expectations_dir.is_dir()
        else []
    )

    assert exit_code == 0
    assert payload["observable_slices"] == 2
    assert len(created_files) == 2
    assert "a-visitor-books-two-seats-and-sees-a-countdown.md" in created_files
    assert "a-visitor-cancels-a-held-seat-before-payment.md" in created_files
    assert len(payload["created"]) == 2

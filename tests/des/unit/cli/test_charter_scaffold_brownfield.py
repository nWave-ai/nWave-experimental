"""AT -- `des charter-scaffold --seed-mode brownfield-discovery` (slice-04).

slice-04 EXTENDS the shipped `src/des/cli/charter_scaffold.py` (slice-01
slice-plan, slice-03 bug-observable) with a THIRD `--seed-mode
{slice-plan,bug-observable,brownfield-discovery}` choice + `--area <text>`.

`--seed-mode brownfield-discovery` generates ONE discovery-framed charter
scaffold for retrofitting expectations onto an EXISTING undocumented system
area: NO Slice Plan is read, the Intent INVERTS the normal derivation --
instead of lifting a Value statement verbatim, it invites the examiner to
DISCOVER and document what `--area` is supposed to do for the user by
exploring the running system. Judgment sections (Preconditions / Charter /
Expected observations) are left as the template's fresh-PO-fill TODO
placeholders -- same skeleton every other seed-mode emits. Idempotent (never
overwrites); degrades LOUD (GDP-6) on a missing/blank `--area`, never a `.md`
garbage / empty-Intent file.

covers: slice-04 of docs/feature/charter-scaffold/feature-delta.md

RED reason (P1-P4 in-process active-RED, `nw-distill-red-scaffolding`):
`des.cli.charter_scaffold.main` exists (slice-01/02/03 shipped) but its
argparse `--seed-mode` choice set is `("slice-plan", "bug-observable")` --
`"brownfield-discovery"` is NOT yet a recognised choice, and `--area` is not
yet a recognised flag. Module-level imports name ONLY the stable shipped
`main` (P1), imported lazily inside each helper/test (P2, mirrors the
slice-03 sibling file). Each test drives it IN-PROCESS; the unrecognised
`--seed-mode` value surfaces as an argparse `SystemExit(2)` reached WITHIN
the test body's own call (P3), caught and re-raised as a clear
`AssertionError` via `pytest.fail` (fail-for-right-reason, P4). Collection
stays green; each new-behaviour test fails for a semantic reason and goes
GREEN once slice-04 ships the choice + flag. The regression test (existing
seed-modes unchanged) does NOT touch the new flag -- it is a real behaviour
assertion against already-shipped code and is expected to PASS today,
serving as the additive-only safety net slice-04 must not break.

Placement: a NEW file (not appended to `test_charter_scaffold.py` or
`test_charter_scaffold_bug_observable.py`) so the carpaccio slice-gate
counts ONLY slice-04's ATs against the ceiling -- the slice-01/02/03 tests
in the sibling files are separate, already-shipped slices.

Driving surface: `des.cli.charter_scaffold.main(argv) -> int` invoked
IN-PROCESS against a `tmp_path` fixture repo (composition-root driving
port -- Mandate 16, driving-port-only boundary). No subprocess fork.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


#: A plain, real-sounding description of an existing, undocumented system
#: area -- the `--area` text an operator retrofitting a charter would supply
#: verbatim. User-side language only, no implementation vocabulary.
AREA_TEXT = "the settings page where a user changes their notification preferences"

#: A second, distinct area used to prove per-area scaffolds don't merge.
AREA_TEXT_2 = "the background job that reconciles daily payment totals"

#: Verbs the discovery-framed Intent must read as an INVITATION with --
#: "explore the running system", "discover what X does" -- never a finished
#: description of the area's behaviour (the design contract's inversion:
#: charter FROM the system, not the system from the charter).
_DISCOVERY_VERBS = ("explore", "discover", "document")

#: The NEW degrade-LOUD verdict token slice-04 adds for `--seed-mode
#: brownfield-discovery` with a missing/blank `--area`. Mirrors the shipped
#: `missing-feature-delta` / `missing-charter-template` / `missing-observable`
#: naming convention in `des.cli.charter_scaffold` -- defined LOCALLY here
#: (not imported) because it does not exist in the shipped module yet: this
#: is the DISTILL-authored contract the crafter implements verbatim to reach
#: GREEN.
VERDICT_MISSING_AREA = "missing-area"

#: The real `nWave/templates/expectation-charter.md` "Template" skeleton
#: (byte-faithful, seeded into the fixture repo at the repo-root-relative
#: path the tool reads it from) -- same skeleton the slice-01/03 ATs use.
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


def _invoke_brownfield_discovery(
    repo_root: Path,
    capsys,
    feature_id: str,
    area: str | None,
) -> tuple[int, dict]:
    """The slice-04 driving call: in-process `main()` (P2) with `--seed-mode
    brownfield-discovery` -- a choice the current shipped CLI does not
    recognise yet.

    Wraps the call so argparse rejecting the not-yet-existing
    `brownfield-discovery` choice / `--area` flag surfaces as a clear
    `AssertionError` (fail-for-right-reason, P4) instead of an unhandled
    `SystemExit` propagating out of the test body. `area=None` omits the
    `--area` flag entirely (the "flag never supplied" case).
    """
    from des.cli.charter_scaffold import main

    argv = ["--seed-mode", "brownfield-discovery", "--feature-id", feature_id]
    if area is not None:
        argv += ["--area", area]
    argv += ["--repo-root", str(repo_root), "--format", "json"]

    try:
        exit_code = main(argv)
    except SystemExit as exc:
        pytest.fail(
            "des charter-scaffold --seed-mode brownfield-discovery was "
            f"rejected by argparse (SystemExit code={exc.code}) -- the "
            "'brownfield-discovery' seed-mode / '--area' flag do not exist "
            "yet on the shipped CLI; implement them per feature-delta.md "
            "slice-04 to make this pass"
        )
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


def test_brownfield_discovery_generates_one_scaffold_with_discovery_framed_intent(
    tmp_path: Path, capsys
) -> None:
    """Happy path: exactly ONE charter scaffold is created under
    docs/product/expectations/<feature-id>/, its Intent section NAMES the
    --area text and reads as an invitation to explore/discover -- not a
    finished description of the area's behaviour -- and the judgment
    sections (Preconditions / Charter / Expected observations) are left as
    the template's fresh-PO-fill TODO placeholders (same contract as the
    slice-01/03 seed-modes: this tool lifts, it never invents judgment).
    """
    _seed_repo(tmp_path)
    feature_id = "legacy-notifications"

    exit_code, payload = _invoke_brownfield_discovery(
        tmp_path, capsys, feature_id, AREA_TEXT
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

    content = (expectations_dir / created_files[0]).read_text(encoding="utf-8")
    intent_body = _intent_section(content)

    # Names the area, in recognizably the caller's own words.
    assert AREA_TEXT in intent_body
    # Reads as an invitation to discover -- not a finished description a
    # reader could use to infer what the area actually does.
    assert any(verb in intent_body.lower() for verb in _DISCOVERY_VERBS)

    # Uncontaminated by construction: only the --area text was seen.
    assert "src/des" not in content
    assert "class " not in content
    assert "def " not in content

    # Judgment sections untouched -- still the template's TODO placeholders,
    # never silently pre-filled with assumed/guessed behaviour.
    assert (
        "<start recipe: how to run the system from a clean state, seed state>"
        in content
    )
    assert "<observable outcome, user language>" in content
    assert "<negative: what must NOT happen>" in content


def test_brownfield_discovery_second_run_is_idempotent_and_reports_skipped(
    tmp_path: Path, capsys
) -> None:
    """Idempotent re-run: running the same --area twice does NOT overwrite /
    re-create the scaffold; the second run reports it in `skipped`, and a
    fresh-PO discovery edit made between runs survives untouched (clobbering
    a PO's discovery notes is a data-loss defect, not a convenience).
    """
    _seed_repo(tmp_path)
    feature_id = "legacy-notifications-idempotent"

    first_exit, first_payload = _invoke_brownfield_discovery(
        tmp_path, capsys, feature_id, AREA_TEXT
    )
    assert first_exit == 0
    assert len(first_payload["created"]) == 1

    expectations_dir = _expectations_dir(tmp_path, feature_id)
    scaffold_path = next(expectations_dir.glob("*.md"))
    sentinel = "SENTINEL: fresh-PO discovery notes, must survive re-run\n"
    scaffold_path.write_text(sentinel, encoding="utf-8")

    second_exit, second_payload = _invoke_brownfield_discovery(
        tmp_path, capsys, feature_id, AREA_TEXT
    )

    assert second_exit == 0
    assert second_payload["created"] == []
    assert len(second_payload["skipped"]) == 1
    assert scaffold_path.read_text(encoding="utf-8") == sentinel


@pytest.mark.parametrize(
    "area",
    [
        pytest.param(None, id="area_flag_omitted"),
        pytest.param("", id="area_blank_string"),
        pytest.param("   ", id="area_whitespace_only"),
    ],
)
def test_brownfield_discovery_missing_area_never_creates_a_garbage_scaffold(
    tmp_path: Path, capsys, area: str | None
) -> None:
    """Negative (GDP-6 degrade-LOUD, the slice-01/03 blank-input lesson
    applies here too): a missing OR blank --area with --seed-mode
    brownfield-discovery must NEVER produce a `.md` garbage file / empty-
    Intent scaffold. Instead: a LOUD non-zero reject, verdict `missing-area`,
    with a clear message naming 'area' -- never a silent no-op.
    """
    _seed_repo(tmp_path)
    feature_id = "legacy-missing-area"

    exit_code, payload = _invoke_brownfield_discovery(
        tmp_path, capsys, feature_id, area
    )

    expectations_dir = _expectations_dir(tmp_path, feature_id)

    assert exit_code != 0
    assert payload["verdict"] == VERDICT_MISSING_AREA
    assert "area" in payload["detail"].lower()
    assert payload["created"] == []
    assert not expectations_dir.is_dir() or not list(expectations_dir.glob("*.md"))


def test_brownfield_discovery_different_area_same_feature_creates_a_separate_scaffold(
    tmp_path: Path, capsys
) -> None:
    """A different --area in the same --feature-id produces its OWN separate
    scaffold, not a merge or overwrite of the first -- a team retrofitting
    charters onto several legacy areas grows a suite, one file per area.
    """
    _seed_repo(tmp_path)
    feature_id = "legacy-multi-area"

    first_exit, first_payload = _invoke_brownfield_discovery(
        tmp_path, capsys, feature_id, AREA_TEXT
    )
    assert first_exit == 0
    assert len(first_payload["created"]) == 1

    second_exit, second_payload = _invoke_brownfield_discovery(
        tmp_path, capsys, feature_id, AREA_TEXT_2
    )
    assert second_exit == 0
    assert len(second_payload["created"]) == 1

    expectations_dir = _expectations_dir(tmp_path, feature_id)
    created_files = sorted(p.name for p in expectations_dir.glob("*.md"))
    contents = [
        (expectations_dir / name).read_text(encoding="utf-8") for name in created_files
    ]

    # Both scaffolds coexist -- neither run clobbered the other.
    assert len(created_files) == 2
    assert any(AREA_TEXT in _intent_section(c) for c in contents)
    assert any(AREA_TEXT_2 in _intent_section(c) for c in contents)


def test_existing_seed_modes_unchanged_when_brownfield_discovery_is_added(
    tmp_path: Path, capsys
) -> None:
    """Regression: default slice-plan mode (no --seed-mode) AND the explicit
    --seed-mode bug-observable path both still work unchanged once the
    brownfield-discovery choice/flag exist -- proves the new seed-mode is
    purely additive (feature-delta.md slice-04: 'slice-plan default +
    bug-observable paths unchanged'). This test drives already-shipped
    behaviour, not the new flag -- it is expected to PASS today and must
    keep passing after slice-04 lands.
    """
    from des.cli.charter_scaffold import main

    _seed_repo(tmp_path)

    # -- slice-plan (default, no --seed-mode passed at all) --
    slice_plan_feature_id = "legacy-regression-slice-plan"
    value_statement = "A visitor books two seats and sees a countdown"
    slice_plan_feature_delta = f"""# Feature-delta -- {slice_plan_feature_id}

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | {value_statement} | pending |  | first observable slice |
"""
    delta_dir = tmp_path / "docs" / "feature" / slice_plan_feature_id
    delta_dir.mkdir(parents=True, exist_ok=True)
    (delta_dir / "feature-delta.md").write_text(
        slice_plan_feature_delta, encoding="utf-8"
    )

    slice_plan_argv = [
        "--feature-id",
        slice_plan_feature_id,
        "--repo-root",
        str(tmp_path),
        "--format",
        "json",
    ]
    slice_plan_exit = main(slice_plan_argv)
    slice_plan_payload = json.loads(capsys.readouterr().out)

    assert slice_plan_exit == 0
    assert slice_plan_payload["observable_slices"] == 1
    assert len(slice_plan_payload["created"]) == 1

    # -- bug-observable (explicit --seed-mode) --
    bug_feature_id = "legacy-regression-bug-observable"
    observable = "Clicking Save twice creates two duplicate invoices instead of one"
    bug_observable_argv = [
        "--seed-mode",
        "bug-observable",
        "--feature-id",
        bug_feature_id,
        "--observable",
        observable,
        "--repo-root",
        str(tmp_path),
        "--format",
        "json",
    ]
    bug_observable_exit = main(bug_observable_argv)
    bug_observable_payload = json.loads(capsys.readouterr().out)

    assert bug_observable_exit == 0
    assert len(bug_observable_payload["created"]) == 1

"""AT -- `des charter-scaffold --seed-mode brownfield-discovery`.

`--seed-mode brownfield-discovery` generates ONE discovery-framed charter
scaffold for retrofitting expectations onto an EXISTING undocumented system
area: the Intent invites the examiner to DISCOVER and document what `--area`
is supposed to do for the user by exploring the running system. Judgment
sections (Preconditions / Charter / Expected observations) are left as the
template's fresh-PO-fill TODO placeholders -- same skeleton every other
seed-mode emits. Idempotent (never overwrites); degrades LOUD (GDP-6) on a
missing/blank `--area`, never a `.md` garbage / empty-Intent file.

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
    """Drive the in-process `main()` with `--seed-mode brownfield-discovery`.

    Wraps the call so argparse errors surface as clear `AssertionError`
    instead of unhandled `SystemExit`. `area=None` omits the `--area` flag
    entirely.
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
            "on the CLI"
        )
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


def test_brownfield_discovery_generates_one_scaffold_with_discovery_framed_intent(
    charter_template_seeded_repo: Path, capsys
) -> None:
    """Happy path: exactly ONE charter scaffold is created under
    docs/product/expectations/<feature-id>/, its Intent section NAMES the
    --area text and reads as an invitation to explore/discover -- not a
    finished description of the area's behaviour -- and the judgment
    sections (Preconditions / Charter / Expected observations) are left as
    the template's fresh-PO-fill TODO placeholders (same contract as the
    slice-01/03 seed-modes: this tool lifts, it never invents judgment).
    """
    tmp_path = charter_template_seeded_repo
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

    # Names the area.
    assert AREA_TEXT in intent_body
    # Reads as an invitation to discover/explore.
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
    charter_template_seeded_repo: Path, capsys
) -> None:
    """Idempotent re-run: running the same --area twice does NOT overwrite /
    re-create the scaffold; the second run reports it in `skipped`, and a
    fresh-PO discovery edit made between runs survives untouched (clobbering
    a PO's discovery notes is a data-loss defect, not a convenience).
    """
    tmp_path = charter_template_seeded_repo
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
    charter_template_seeded_repo: Path, capsys, area: str | None
) -> None:
    """Negative (GDP-6 degrade-LOUD, the slice-01/03 blank-input lesson
    applies here too): a missing OR blank --area with --seed-mode
    brownfield-discovery must NEVER produce a `.md` garbage file / empty-
    Intent scaffold. Instead: a LOUD non-zero reject, verdict `missing-area`,
    with a clear message naming 'area' -- never a silent no-op.
    """
    tmp_path = charter_template_seeded_repo
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
    charter_template_seeded_repo: Path, capsys
) -> None:
    """A different --area in the same --feature-id produces its OWN separate
    scaffold, not a merge or overwrite of the first -- a team retrofitting
    charters onto several legacy areas grows a suite, one file per area.
    """
    tmp_path = charter_template_seeded_repo
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
    charter_template_seeded_repo: Path, capsys
) -> None:
    """Regression: the --seed-mode bug-observable and --seed-mode
    direct-value paths both still work unchanged once brownfield-discovery
    is added.
    """
    from des.cli.charter_scaffold import main

    tmp_path = charter_template_seeded_repo

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

    # -- direct-value (explicit --seed-mode) --
    direct_value_feature_id = "legacy-regression-direct-value"
    direct_value_argv = [
        "--seed-mode",
        "direct-value",
        "--feature-id",
        direct_value_feature_id,
        "--value",
        "Operator sees last night's backup succeeded",
        "--repo-root",
        str(tmp_path),
        "--format",
        "json",
    ]
    direct_value_exit = main(direct_value_argv)
    direct_value_payload = json.loads(capsys.readouterr().out)

    assert direct_value_exit == 0
    assert len(direct_value_payload["created"]) == 1

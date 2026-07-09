"""RED regression ATs -- two BLOCKER defects found by the feature-end deep
review of the shipped `des charter-scaffold` tool
(`src/des/cli/charter_scaffold.py`, slice-01/02/03/04, all seed-modes
already on `main`).

D1 (silent-wrong on hostile input, a variant of the already-fixed blank-
input bug): every degrade-LOUD guard in the tool checks `not input.strip()`
(blank BEFORE normalisation) but `_scaffold_slice` derives the on-disk
filename via `_kebab_slug`, which strips every character outside
`[A-Za-z0-9\\s-]`. A symbol-only or purely non-Latin input (e.g. "???",
"@#$%", or a CJK-only sentence) is NON-blank pre-slug, so it sails past
every guard, then normalises to an EMPTY slug -- `_scaffold_slice` writes a
literal `.md` file (empty/degenerate stem) and counts it in `created`. This
is the exact GDP-6 silent-wrong shape the blank-input tests in
`test_charter_scaffold.py` / `_bug_observable.py` / `_brownfield.py` guard
against -- it leaks straight through normalisation because none of them
re-check the POST-slug result. Reproduced across all three `--seed-mode`
values (`slice-plan` Value statement, `bug-observable` `--observable`,
`brownfield-discovery` `--area`) because all three funnel through the same
`_scaffold_slice` -> `_kebab_slug` call.

D2 (AT-completeness ZERO-obligation gap, surfaced as a real silent-wrong):
`_classify_slice_cohesion` (the MECC that emits `VERDICT_REJECTED_INFRA_ONLY`)
vetoes ONLY the case where every data row's Annotation normalises to the
LITERAL token `"infrastructure"` -- a Slice Plan whose rows are `@infrastructure`
MIXED WITH `@prefactoring` (or entirely `@prefactoring`) fails that narrow
check on the first non-"infrastructure" row and returns `None` (no veto).
`_run_slice_plan` therefore proceeds past `validate_slice_plan_content` with
`VERDICT_ACCEPTED`; `_observable_slice_rows` then correctly filters out BOTH
annotation kinds (`_is_observable` already excludes prefactoring too),
leaving zero observable rows -- so the tool exits 0 with `created: []`,
`skipped: []`, `observable_slices: 0`, `verdict: "accepted"`: a silent
empty "success" instead of the LOUD `rejected-infra-only` reject a
zero-observable-slice plan deserves. No existing test drives an
all-`@infrastructure`/`@prefactoring` Slice Plan, so this gap shipped
unexercised.

covers: feature-end deep review D1 + D2, `des charter-scaffold`
(`src/des/cli/charter_scaffold.py`)

RED reason (P1-P4 in-process active-RED, `nw-distill-red-scaffolding`):
NOT a missing-module/missing-flag RED (the tool + every flag exercised here
are already shipped) -- these are BEHAVIOURAL REDs. Each test drives the
real, already-shipped `des.cli.charter_scaffold.main(argv)` IN-PROCESS
against a `tmp_path` fixture repo and asserts the DESIRED (not-yet-true)
outcome; the CURRENT implementation's actual outcome (a garbage scaffold
silently created / a silent empty-success exit) makes the assertion raise a
plain `AssertionError` -- fail-for-the-right-reason, never a collection or
import error.

Driving surface: `des.cli.charter_scaffold.main(argv) -> int` invoked
IN-PROCESS against a `tmp_path` fixture repo (composition-root driving
port -- Mandate 16, driving-port-only boundary). No subprocess fork.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.validate_feature_delta import VERDICT_REJECTED_INFRA_ONLY


#: The one repo-root-relative asset every seed-mode reads regardless of
#: scenario: the expectation-charter template skeleton (byte-faithful to the
#: real shipped `nWave/templates/expectation-charter.md`).
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
    template_dir = repo_root / "nWave" / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "expectation-charter.md").write_text(
        TEMPLATE_SKELETON, encoding="utf-8"
    )


def _expectations_dir(repo_root: Path, feature_id: str) -> Path:
    return repo_root / "docs" / "product" / "expectations" / feature_id


def _invoke_seed_mode(
    repo_root: Path,
    capsys,
    feature_id: str,
    seed_mode: str,
    hostile_text: str,
) -> tuple[int, dict]:
    """Drive the already-shipped `main()` (P2) for one of the three
    `--seed-mode` values, feeding `hostile_text` as that mode's user-supplied
    text (`slice-plan` Value statement / `bug-observable` `--observable` /
    `brownfield-discovery` `--area`). No SystemExit handling needed -- all
    three seed-modes and their flags already exist on `main`'s argparse."""
    from des.cli.charter_scaffold import main

    if seed_mode == "slice-plan":
        feature_delta = f"""# Feature-delta -- {feature_id}

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | {hostile_text} | pending |  | hostile Value statement (D1 regression) |
"""
        delta_dir = repo_root / "docs" / "feature" / feature_id
        delta_dir.mkdir(parents=True, exist_ok=True)
        (delta_dir / "feature-delta.md").write_text(feature_delta, encoding="utf-8")
        argv = [
            "--feature-id",
            feature_id,
            "--repo-root",
            str(repo_root),
            "--format",
            "json",
        ]
    elif seed_mode == "bug-observable":
        argv = [
            "--seed-mode",
            "bug-observable",
            "--feature-id",
            feature_id,
            "--observable",
            hostile_text,
            "--repo-root",
            str(repo_root),
            "--format",
            "json",
        ]
    else:
        assert seed_mode == "brownfield-discovery"
        argv = [
            "--seed-mode",
            "brownfield-discovery",
            "--feature-id",
            feature_id,
            "--area",
            hostile_text,
            "--repo-root",
            str(repo_root),
            "--format",
            "json",
        ]

    exit_code = main(argv)
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


@pytest.mark.parametrize(
    "seed_mode,hostile_text",
    [
        pytest.param("slice-plan", "???", id="slice_plan_symbols_only"),
        pytest.param(
            "slice-plan", "日本語のみのテキストです", id="slice_plan_non_latin"
        ),
        pytest.param("bug-observable", "###", id="bug_observable_symbols_only"),
        pytest.param(
            "bug-observable", "只有中文字符没有别的", id="bug_observable_non_latin"
        ),
        pytest.param(
            "brownfield-discovery", "!!!", id="brownfield_discovery_symbols_only"
        ),
        pytest.param(
            "brownfield-discovery",
            "@#$%",
            id="brownfield_discovery_symbols_only_2",
        ),
    ],
)
def test_hostile_input_normalizing_to_an_empty_slug_never_creates_a_garbage_scaffold(
    tmp_path: Path, capsys, seed_mode: str, hostile_text: str
) -> None:
    """D1 (BLOCKER): a symbol-only or non-Latin input is non-blank BEFORE
    kebab-slug normalisation (so it sails past every `not input.strip()`
    guard) but normalises to an EMPTY slug -- the tool must never write a
    `.md` file with an empty/degenerate stem for it, and must never count
    such a file in `created`. Currently (D1, unfixed) it does both: exit 0,
    a literal `.md` scaffold on disk, counted in `created`.
    """
    _seed_repo(tmp_path)
    feature_id = f"hostile-{seed_mode}"

    exit_code, payload = _invoke_seed_mode(
        tmp_path, capsys, feature_id, seed_mode, hostile_text
    )

    expectations_dir = _expectations_dir(tmp_path, feature_id)
    all_files = (
        sorted(p.name for p in expectations_dir.glob("*.md"))
        if expectations_dir.is_dir()
        else []
    )
    degenerate_files = [name for name in all_files if not name.removesuffix(".md")]

    assert not degenerate_files, (
        f"hostile input {hostile_text!r} via --seed-mode {seed_mode} "
        f"normalized to an empty kebab-slug and was scaffolded as a garbage "
        f"file: {degenerate_files} (files on disk: {all_files})"
    )
    assert not any(name in payload.get("created", []) for name in degenerate_files), (
        "a degenerate/empty-stem scaffold was silently counted in "
        f"'created': {payload.get('created')}"
    )
    if exit_code == 0:
        # accepted-but-skipped path: the hostile input must be reported LOUD
        # in `skipped` -- never a silent no-op that creates nothing and says
        # nothing.
        assert payload.get("skipped"), (
            "hostile input degraded to exit 0 with nothing created AND "
            f"nothing reported in 'skipped' -- silent no-op: {payload}"
        )


@pytest.mark.parametrize(
    "annotations",
    [
        pytest.param(
            ("infrastructure", "prefactoring"),
            id="mixed_infrastructure_and_prefactoring",
        ),
        pytest.param(("prefactoring", "prefactoring"), id="all_prefactoring"),
    ],
)
def test_slice_plan_with_zero_observable_rows_never_silently_exits_zero(
    tmp_path: Path, capsys, annotations: tuple[str, str]
) -> None:
    """D2 (BLOCKER, AT-completeness ZERO-obligation gap): a Slice Plan whose
    rows are ALL `@infrastructure`/`@prefactoring` (zero observable slices)
    must degrade LOUD with `rejected-infra-only` (or equivalent), never a
    silent `accepted` exit-0 with `observable_slices: 0`.

    `_classify_slice_cohesion`'s MECC vetoes only the literal
    all-`"infrastructure"` case -- a plan mixing `@infrastructure` with
    `@prefactoring` (or entirely `@prefactoring`) slips past it, then
    `_observable_slice_rows` correctly filters every row out, yielding a
    silent empty "success": exit 0, `created: []`, `verdict: "accepted"`.
    """
    _seed_repo(tmp_path)
    feature_id = "zero-observable-" + "-".join(annotations)

    rows = "\n".join(
        f"| slice-{i + 1:02d} | Some internal plumbing step {i + 1} | "
        f"pending | @{annotation} | no user value |"
        for i, annotation in enumerate(annotations)
    )
    feature_delta = f"""# Feature-delta -- {feature_id}

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
{rows}
"""
    delta_dir = tmp_path / "docs" / "feature" / feature_id
    delta_dir.mkdir(parents=True, exist_ok=True)
    (delta_dir / "feature-delta.md").write_text(feature_delta, encoding="utf-8")

    from des.cli.charter_scaffold import main

    exit_code = main(
        [
            "--feature-id",
            feature_id,
            "--repo-root",
            str(tmp_path),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code != 0, (
        "a Slice Plan with ZERO observable rows (annotations="
        f"{annotations}) exited 0 -- silent empty success (payload="
        f"{payload}) instead of a LOUD reject"
    )
    assert payload["verdict"] == VERDICT_REJECTED_INFRA_ONLY, (
        f"expected verdict {VERDICT_REJECTED_INFRA_ONLY!r} for a "
        f"zero-observable-slice Slice Plan, got {payload['verdict']!r} "
        f"(payload={payload})"
    )
    assert payload["created"] == []

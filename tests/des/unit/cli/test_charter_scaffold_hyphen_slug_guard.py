"""RED regression AT -- bugfix #59 LOW-2, the hyphen-only variant of the
already-fixed D1 empty-slug guard (`src/des/cli/charter_scaffold.py`).

THE DEFECT: `_kebab_slug` strips every character outside `[A-Za-z0-9\\s-]` and
lower-cases the rest, but a HYPHEN-only (or whitespace+hyphen) input has no
character outside that allowed set to strip -- `_kebab_slug("---")` returns
`"---"` verbatim, NOT `""`. Every existing `if not _kebab_slug(...)` empty-slug
guard site (`_scaffold_slice`, `_emit_single_scaffold_result`) therefore treats
a hyphen-only input as a NON-empty, sluggable value: it sails past the guard
and `_scaffold_slice` writes a literal `---.md` garbage file -- the exact
#52-class defect the D1 fix closed, for the hyphen-only variant D1 missed (a
slug with NO alphanumeric content is as meaningless a filename as an empty
one).

THE FIX (crafter, NOT authored here): `_kebab_slug` returns `""` when its
normalised result carries NO alphanumeric character, so every existing
`not _kebab_slug(...)` guard site catches hyphen-only for free and reuses
`_empty_slug_skip_label` verbatim -- no new guard/message.

covers: bugfix #59 LOW-2, `des charter-scaffold`
(`src/des/cli/charter_scaffold.py`)

RED reason: These are BEHAVIOURAL REDs. Each test drives the real,
already-shipped seam (`_kebab_slug` directly, or `des.cli.charter_scaffold.main`
IN-PROCESS) and asserts the DESIRED outcome; the CURRENT implementation's
actual outcome (a hyphens-preserved slug / garbage `---.md` scaffold) makes
the assertion raise a plain `AssertionError`.

Driving surface: `_kebab_slug(value_statement) -> str` (pure function, direct
call) for scenario 1; `des.cli.charter_scaffold.main(argv) -> int` invoked
IN-PROCESS against a `tmp_path` fixture repo (composition-root driving port --
Mandate 16, driving-port-only boundary) for scenarios 2-3. No subprocess fork.

Test Reuse & Consolidation: reuses the D1 hostile-input fixture pattern
(`_seed_repo` / `_expectations_dir` / `_invoke_seed_mode`) from
`tests.des.unit.cli.test_charter_scaffold_hostile_input`. `bug-observable`
and `brownfield-discovery` route through a LOCAL `--flag=value` argv builder
(`_invoke_seed_mode_equals_form` below) instead of the shared helper's
`--flag value` two-token form: argparse rejects a bare `---`/`-` TOKEN
following `--observable`/`--area` as ambiguous (`error: argument --area:
expected one argument`) -- a genuine argparse quirk, not the `_kebab_slug`
defect under test. The `--flag=value` single-token form sidesteps that
without touching production code.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.charter_scaffold import _kebab_slug
from tests.des.unit.cli.test_charter_scaffold_hostile_input import (
    _expectations_dir,
    _invoke_seed_mode,
    _seed_repo,
)


def _invoke_seed_mode_equals_form(
    repo_root: Path,
    capsys,
    feature_id: str,
    seed_mode: str,
    hostile_text: str,
) -> tuple[int, dict]:
    """Variant that passes the hostile text via `--flag=value` (single token)
    instead of `--flag value` (two tokens) for hyphen-only inputs."""
    from des.cli.charter_scaffold import main

    flag = "--observable" if seed_mode == "bug-observable" else "--area"
    argv = [
        "--seed-mode",
        seed_mode,
        "--feature-id",
        feature_id,
        f"{flag}={hostile_text}",
        "--repo-root",
        str(repo_root),
        "--format",
        "json",
    ]
    exit_code = main(argv)
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


@pytest.mark.parametrize(
    "hyphen_only_input",
    [
        pytest.param("---", id="triple_hyphen"),
        pytest.param("- - -", id="space_separated_hyphens"),
        pytest.param("  --  ", id="whitespace_padded_double_hyphen"),
        pytest.param("-", id="single_hyphen"),
    ],
)
def test_kebab_slug_reduces_no_alphanumeric_input_to_empty(
    hyphen_only_input: str,
) -> None:
    """A hyphen-only / whitespace-only input has NO alphanumeric content --
    `_kebab_slug` must reduce it to `""`, the SAME empty-slug signal every
    `not _kebab_slug(...)` guard site already checks for.

    Currently (unfixed) `_kebab_slug` returns the hyphens verbatim
    (e.g. `"---"` stays `"---"`), sailing past every guard site.
    """
    # covers: bugfix #59 LOW-2
    slug = _kebab_slug(hyphen_only_input)

    assert slug == "", (
        f"_kebab_slug({hyphen_only_input!r}) returned {slug!r} -- a "
        "hyphen-only/whitespace-only input carries NO alphanumeric content "
        "and must normalise to an empty slug, matching every "
        "`not _kebab_slug(...)` empty-slug guard site's contract"
    )


@pytest.mark.parametrize(
    "seed_mode",
    [
        pytest.param("direct-value", id="direct_value"),
        pytest.param("bug-observable", id="bug_observable"),
        pytest.param("brownfield-discovery", id="brownfield_discovery"),
    ],
)
def test_hyphen_only_input_is_skipped_and_writes_no_charter_file(
    tmp_path: Path, capsys, seed_mode: str
) -> None:
    """A hyphen-only value/observable/area passed to `des charter-scaffold`
    (any `--seed-mode`) must be SKIPPED with the existing self-explaining
    empty-slug label and must write NO `---.md` (or any) charter file --
    closing the #52 garbage-`.md` class for the hyphen-only variant.

    Currently (unfixed) `_kebab_slug("---")` is truthy, so the tool writes a
    literal `---.md` scaffold and counts it in `created`.
    """
    # covers: bugfix #59 LOW-2
    _seed_repo(tmp_path)
    feature_id = f"hyphen-only-{seed_mode}"
    hostile_text = "---"

    invoke = _invoke_seed_mode_equals_form
    exit_code, payload = invoke(tmp_path, capsys, feature_id, seed_mode, hostile_text)

    expectations_dir = _expectations_dir(tmp_path, feature_id)
    all_files = (
        sorted(p.name for p in expectations_dir.glob("*.md"))
        if expectations_dir.is_dir()
        else []
    )

    assert "---.md" not in all_files, (
        f"hyphen-only input {hostile_text!r} via --seed-mode {seed_mode} "
        f"was scaffolded as a garbage '---.md' file (files on disk: "
        f"{all_files})"
    )
    assert "---.md" not in payload.get("created", []), (
        f"'---.md' was silently counted in 'created': {payload.get('created')}"
    )
    if exit_code == 0:
        assert payload.get("skipped"), (
            "hyphen-only input degraded to exit 0 with nothing created AND "
            f"nothing reported in 'skipped' -- silent no-op: {payload}"
        )


def test_normal_alphanumeric_input_is_not_skipped_still_writes_charter() -> None:
    """Non-regression: a NORMAL alphanumeric input must still slug correctly
    and the guard must NOT over-trigger on it -- the no-alphanumeric-content
    reduction only fires when there is truly nothing sluggable left.
    """
    # covers: bugfix #59 LOW-2
    slug = _kebab_slug("Fix the thing")

    assert slug == "fix-the-thing", (
        f"_kebab_slug('Fix the thing') returned {slug!r} -- a normal "
        "alphanumeric input must slug unchanged; the no-alphanumeric-content "
        "empty-slug guard must not over-trigger on real content"
    )


def test_normal_alphanumeric_input_end_to_end_writes_its_charter(
    tmp_path: Path, capsys
) -> None:
    """Non-regression, end-to-end: a normal alphanumeric value
    still gets its charter written (not skipped) through the real
    `des charter-scaffold` direct-value entry -- the hyphen-only guard must not
    over-trigger on ordinary user-authored content.
    """
    # covers: bugfix #59 LOW-2
    _seed_repo(tmp_path)
    feature_id = "normal-input-non-regression"

    exit_code, payload = _invoke_seed_mode(
        tmp_path, capsys, feature_id, "direct-value", "Fix the thing"
    )

    expectations_dir = _expectations_dir(tmp_path, feature_id)
    all_files = (
        sorted(p.name for p in expectations_dir.glob("*.md"))
        if expectations_dir.is_dir()
        else []
    )

    assert exit_code == 0, f"expected exit 0 for a normal input, got payload={payload}"
    assert "fix-the-thing.md" in all_files, (
        "a normal alphanumeric Value statement did not produce its expected "
        f"charter file (files on disk: {all_files}, payload={payload})"
    )
    assert "fix-the-thing.md" in payload.get("created", []), (
        f"'fix-the-thing.md' was not reported in 'created': {payload}"
    )

"""AT -- `des feature-end-preconditions-scaffold`
(feature-end-certifies-real-consumers, slice-01, walking skeleton).

The producing tool that GENERATES, from a feature's feature-delta, the two
feature-end preconditions the real gates already consume:

- `## Environmental E2E` block (`docs/feature/<id>/feature-delta.md`) --
  consumed by `des verify-environmental-e2e --mode run`
  (`src/des/cli/verify_environmental_e2e.py:516`, presence-checked via
  `has_environmental_e2e_block`).
- `.nwave/demo-recipe.json` -- consumed by `des verify-fresh-clone`
  (`src/des/cli/verify_fresh_clone.py:50`, schema `RECIPE_RELPATH` +
  `{"steps": [{"name", "cmd": [...]}], "timeout_seconds"}`).

Mirrors `charter_scaffold.py`'s shape verbatim (DESIGN §New components #1):
pure parse/render core + thin argparse shell, idempotent (never overwrites),
degrade-LOUD JSON verdict on every failure class. Two `--target` modes:

- `--target environmental-e2e --feature-id <id> --e2e-test <path>
  [--repo-root .]` -- appends `## Environmental E2E\\n- test: <path>\\n` when
  absent (idempotent no-op otherwise); degrades LOUD on a missing
  feature-delta or an `--e2e-test` path that is not an existing file.
- `--target demo-recipe [--repo-root .]` -- CONSERVATIVE detection only
  (Earned Trust / GDP-6: a guessed-wrong recipe is worse than none, because
  `verify-fresh-clone` would then degrade LOUD against the WRONG steps).
  Writes `.nwave/demo-recipe.json` ONLY when exactly one confident
  install/build/test convention is detected; otherwise degrades LOUD with a
  HOW telling the operator to hand-author (mirrors
  `verify_fresh_clone._indeterminate`'s what/why/how shape).

covers: slice-01 of
docs/feature/feature-end-certifies-real-consumers/feature-delta.md

RED reason (P1-P4 in-process active-RED, `nw-distill-red-scaffolding`):
`src/des/cli/feature_end_preconditions_scaffold.py` does not exist yet.
Module-level imports name ONLY stable, already-shipped entries
(`des.cli.verify_fresh_clone.RECIPE_RELPATH`,
`des.domain.environmental_e2e.has_environmental_e2e_block`,
`des.cli.validate_feature_delta.VERDICT_ACCEPTED`) -- NEVER the absent SUT
module (P1). Each test lazily imports `main` from
`des.cli.feature_end_preconditions_scaffold` INSIDE `_invoke` (P3); the
resulting `ModuleNotFoundError` is a runtime exception raised WITHIN the
test's own call stack, not a collection-time error -- collection stays
green, and each test fails for a semantic reason once the module ships (P4).

Driving surface: `des.cli.feature_end_preconditions_scaffold.main(argv) ->
int` invoked IN-PROCESS against a `tmp_path` fixture repo (composition-root
driving port -- Mandate 16, driving-port-only boundary). No subprocess fork.

Contract this AT pins (owned by DISTILL -- nothing exists yet to reverse
engineer): stdout is one JSON object `{target, written, verdict, detail}` per
invocation. `written` is `True` only when this run put NEW content on disk;
`verdict == "accepted"` (imported from `des.cli.validate_feature_delta`, the
SAME acceptance-verdict vocabulary `charter_scaffold`/`validate_feature_delta`
already share) covers BOTH a real write and an idempotent no-op (exit 0
either way); any other verdict is a degrade-LOUD reject (exit non-zero,
`written` never `True`). Negative assertions below deliberately check
`verdict != VERDICT_ACCEPTED` + a `detail` substring rather than pinning an
exact degrade-token spelling -- strong enough to prove degrade-LOUD without
over-coupling to a token the crafter has not chosen yet.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.validate_feature_delta import VERDICT_ACCEPTED
from des.cli.verify_fresh_clone import RECIPE_RELPATH
from des.domain.environmental_e2e import has_environmental_e2e_block


FEATURE_ID = "checkout-flow"

E2E_TEST_RELPATH = "tests/e2e/test_checkout_flow.py"
ALT_E2E_TEST_RELPATH = "tests/e2e/test_alt_checkout_flow.py"

NO_E2E_BLOCK_FEATURE_DELTA = f"""# Feature-delta -- {FEATURE_ID}

## Wave: DISCUSS / [REF] Value

A shopper checks out and receives an order confirmation.
"""

#: A feature-delta that ALREADY carries a well-formed block naming a
#: different (legacy) e2e test -- the never-overwrite fixture.
EXISTING_E2E_BLOCK_FEATURE_DELTA = f"""# Feature-delta -- {FEATURE_ID}

## Wave: DISCUSS / [REF] Value

A shopper checks out and receives an order confirmation.

## Environmental E2E
- test: tests/e2e/test_legacy_checkout.py
"""


def _write_feature_delta(repo_root: Path, feature_id: str, content: str) -> Path:
    delta_dir = repo_root / "docs" / "feature" / feature_id
    delta_dir.mkdir(parents=True, exist_ok=True)
    path = delta_dir / "feature-delta.md"
    path.write_text(content, encoding="utf-8")
    return path


def _feature_delta_path(repo_root: Path, feature_id: str) -> Path:
    return repo_root / "docs" / "feature" / feature_id / "feature-delta.md"


def _seed_e2e_test_file(repo_root: Path, relpath: str) -> Path:
    path = repo_root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "def test_checkout_flow_e2e():\n    assert True\n", encoding="utf-8"
    )
    return path


def _seed_confidently_detectable_layout(repo_root: Path) -> None:
    """A layout + declared-task convention `resolve_layout` (EXTEND) can BOTH
    confidently resolve: `src/` + `tests/` dirs present, plus a
    `pyproject.toml [tool.poe.tasks]` declaring install/build/test -- the
    ONE-confident-convention case `--target demo-recipe` must write for."""
    (repo_root / "src").mkdir(parents=True, exist_ok=True)
    (repo_root / "tests").mkdir(parents=True, exist_ok=True)
    (repo_root / "pyproject.toml").write_text(
        '[tool.poe.tasks]\ninstall = "uv sync"\nbuild = "uv build"\ntest = "pytest"\n',
        encoding="utf-8",
    )


def _recipe_path(repo_root: Path) -> Path:
    return repo_root / RECIPE_RELPATH


def _invoke(repo_root: Path, argv: list[str], capsys) -> tuple[int, dict]:
    """The driving call every test uses: in-process `main()` (P2), stdout
    captured and parsed as the `--format json`-equivalent contract token."""
    from des.cli.feature_end_preconditions_scaffold import main

    exit_code = main([*argv, "--repo-root", str(repo_root)])
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


# --- --target environmental-e2e -----------------------------------------


def test_environmental_e2e_scaffold_appends_a_well_formed_block_when_absent(
    tmp_path: Path, capsys
) -> None:
    _write_feature_delta(tmp_path, FEATURE_ID, NO_E2E_BLOCK_FEATURE_DELTA)
    _seed_e2e_test_file(tmp_path, E2E_TEST_RELPATH)

    exit_code, payload = _invoke(
        tmp_path,
        [
            "--target",
            "environmental-e2e",
            "--feature-id",
            FEATURE_ID,
            "--e2e-test",
            E2E_TEST_RELPATH,
        ],
        capsys,
    )

    delta_content = _feature_delta_path(tmp_path, FEATURE_ID).read_text(
        encoding="utf-8"
    )

    assert exit_code == 0
    assert payload["verdict"] == VERDICT_ACCEPTED
    assert payload["written"] is True
    # A CERTIFICATION-usable block, not placeholder text: the SAME predicate
    # the real gate consults (`verify_environmental_e2e.py`) must see it.
    assert has_environmental_e2e_block(delta_content) is True
    assert f"- test: {E2E_TEST_RELPATH}" in delta_content


@pytest.mark.parametrize(
    "e2e_test_relpath",
    [E2E_TEST_RELPATH, ALT_E2E_TEST_RELPATH],
    ids=["primary_e2e_path", "alternate_e2e_path"],
)
def test_environmental_e2e_block_content_traces_to_the_declared_e2e_test_path(
    tmp_path: Path, capsys, e2e_test_relpath: str
) -> None:
    # A different fixture (`--e2e-test` value) must produce a VISIBLY
    # different block -- the generated block traces back to what was
    # declared, it is never boilerplate independent of the input.
    #
    # NOTE: deliberately no function docstring -- pytest-pspec renders the
    # JUnit <testcase name> from the docstring verbatim, WITHOUT the
    # parametrize id, so a shared docstring across parametrize cases
    # collapses them into one duplicate testcase name (observed: two
    # `test_scaffold_never_...` cases folded into one id by
    # `des verify-red-green`'s RedGreenDuplicateIdCollapse). Comment instead.
    _write_feature_delta(tmp_path, FEATURE_ID, NO_E2E_BLOCK_FEATURE_DELTA)
    _seed_e2e_test_file(tmp_path, e2e_test_relpath)

    _invoke(
        tmp_path,
        [
            "--target",
            "environmental-e2e",
            "--feature-id",
            FEATURE_ID,
            "--e2e-test",
            e2e_test_relpath,
        ],
        capsys,
    )

    delta_content = _feature_delta_path(tmp_path, FEATURE_ID).read_text(
        encoding="utf-8"
    )
    assert f"- test: {e2e_test_relpath}" in delta_content
    other_relpath = (
        ALT_E2E_TEST_RELPATH
        if e2e_test_relpath == E2E_TEST_RELPATH
        else E2E_TEST_RELPATH
    )
    assert f"- test: {other_relpath}" not in delta_content


def test_environmental_e2e_scaffold_never_overwrites_an_existing_block(
    tmp_path: Path, capsys
) -> None:
    """A pre-existing `## Environmental E2E` block (e.g. hand-authored, or
    from a prior run) must survive untouched -- the tool must SAY it is
    leaving it alone (idempotent no-op), never silently clobber it with a
    NEW `--e2e-test` value."""
    _write_feature_delta(tmp_path, FEATURE_ID, EXISTING_E2E_BLOCK_FEATURE_DELTA)
    _seed_e2e_test_file(tmp_path, E2E_TEST_RELPATH)
    before = _feature_delta_path(tmp_path, FEATURE_ID).read_text(encoding="utf-8")

    exit_code, payload = _invoke(
        tmp_path,
        [
            "--target",
            "environmental-e2e",
            "--feature-id",
            FEATURE_ID,
            "--e2e-test",
            E2E_TEST_RELPATH,
        ],
        capsys,
    )

    after = _feature_delta_path(tmp_path, FEATURE_ID).read_text(encoding="utf-8")

    assert exit_code == 0
    assert after == before, (
        "the pre-existing block (naming 'test_legacy_checkout.py') was "
        "clobbered by a re-run with a different --e2e-test value"
    )
    assert payload["written"] is False
    assert payload["verdict"] == VERDICT_ACCEPTED
    # Self-explaining (GDP-3): the payload SAYS it is a no-op, not silent.
    assert (
        "test_legacy_checkout.py" in payload["detail"]
        or "already" in payload["detail"].lower()
    )


def test_environmental_e2e_scaffold_rejects_e2e_test_path_that_does_not_exist(
    tmp_path: Path, capsys
) -> None:
    _write_feature_delta(tmp_path, FEATURE_ID, NO_E2E_BLOCK_FEATURE_DELTA)
    # Deliberately NOT seeding the e2e test file at this path.

    exit_code, payload = _invoke(
        tmp_path,
        [
            "--target",
            "environmental-e2e",
            "--feature-id",
            FEATURE_ID,
            "--e2e-test",
            E2E_TEST_RELPATH,
        ],
        capsys,
    )

    delta_content = _feature_delta_path(tmp_path, FEATURE_ID).read_text(
        encoding="utf-8"
    )

    assert exit_code != 0
    assert payload["verdict"] != VERDICT_ACCEPTED
    assert E2E_TEST_RELPATH in payload["detail"]
    assert has_environmental_e2e_block(delta_content) is False, (
        "a block was appended even though the declared --e2e-test path does "
        "not exist on disk -- the tool must refuse, not write a block "
        "pointing at nothing"
    )


def test_environmental_e2e_scaffold_rejects_missing_feature_delta(
    tmp_path: Path, capsys
) -> None:
    # Deliberately NOT writing docs/feature/<id>/feature-delta.md at all.
    _seed_e2e_test_file(tmp_path, E2E_TEST_RELPATH)

    exit_code, payload = _invoke(
        tmp_path,
        [
            "--target",
            "environmental-e2e",
            "--feature-id",
            FEATURE_ID,
            "--e2e-test",
            E2E_TEST_RELPATH,
        ],
        capsys,
    )

    assert exit_code != 0
    assert payload["verdict"] != VERDICT_ACCEPTED
    assert FEATURE_ID in payload["detail"]
    assert not _feature_delta_path(tmp_path, FEATURE_ID).exists()


def test_environmental_e2e_scaffold_second_run_is_byte_identical_noop(
    tmp_path: Path, capsys
) -> None:
    """Idempotency law (DESIGN §Contract-test suggestions): running
    `--target environmental-e2e` twice against the SAME inputs produces
    byte-identical output the second time."""
    _write_feature_delta(tmp_path, FEATURE_ID, NO_E2E_BLOCK_FEATURE_DELTA)
    _seed_e2e_test_file(tmp_path, E2E_TEST_RELPATH)
    argv = [
        "--target",
        "environmental-e2e",
        "--feature-id",
        FEATURE_ID,
        "--e2e-test",
        E2E_TEST_RELPATH,
    ]

    first_exit, first_payload = _invoke(tmp_path, argv, capsys)
    after_first = _feature_delta_path(tmp_path, FEATURE_ID).read_text(encoding="utf-8")

    second_exit, second_payload = _invoke(tmp_path, argv, capsys)
    after_second = _feature_delta_path(tmp_path, FEATURE_ID).read_text(encoding="utf-8")

    assert first_exit == 0
    assert first_payload["written"] is True
    assert second_exit == 0
    assert second_payload["written"] is False
    assert after_second == after_first


# --- --target demo-recipe -------------------------------------------------


def test_demo_recipe_scaffold_writes_a_consumable_recipe_when_confidently_detected(
    tmp_path: Path, capsys
) -> None:
    _seed_confidently_detectable_layout(tmp_path)

    exit_code, payload = _invoke(tmp_path, ["--target", "demo-recipe"], capsys)

    recipe_path = _recipe_path(tmp_path)
    assert exit_code == 0
    assert payload["verdict"] == VERDICT_ACCEPTED
    assert payload["written"] is True
    assert recipe_path.is_file()

    # Consumable by `des verify-fresh-clone` (RECIPE_RELPATH's own schema):
    # {"steps": [{"name": str, "cmd": [str, ...]}], ...} -- not placeholder.
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    assert isinstance(recipe.get("steps"), list)
    assert len(recipe["steps"]) >= 1
    for step in recipe["steps"]:
        assert isinstance(step.get("name"), str) and step["name"]
        assert isinstance(step.get("cmd"), list) and step["cmd"]
        assert all(isinstance(token, str) for token in step["cmd"])


def test_demo_recipe_scaffold_rejects_guessing_when_layout_cannot_be_confidently_detected(
    tmp_path: Path, capsys
) -> None:
    """Negative (Earned Trust / GDP-6): a bare repo -- no pyproject, no
    src/tests convention -- gives the tool NOTHING confident to detect. It
    must declare it cannot infer (degrade LOUD, naming the recipe path an
    operator would hand-author), never fabricate a plausible-looking-but-
    wrong recipe."""
    # Deliberately bare: no pyproject.toml, no src/ or tests/ dirs.

    exit_code, payload = _invoke(tmp_path, ["--target", "demo-recipe"], capsys)

    assert exit_code != 0
    assert payload["verdict"] != VERDICT_ACCEPTED
    assert payload["written"] is False
    assert not _recipe_path(tmp_path).exists()
    # Self-explaining (GDP-3): names the artifact an operator would
    # hand-author -- distinguishes "I have no information" from silence.
    assert (
        str(RECIPE_RELPATH) in payload["detail"]
        or RECIPE_RELPATH.name in payload["detail"]
    )


def test_demo_recipe_scaffold_never_overwrites_an_existing_recipe_without_saying_so(
    tmp_path: Path, capsys
) -> None:
    _seed_confidently_detectable_layout(tmp_path)
    recipe_path = _recipe_path(tmp_path)
    recipe_path.parent.mkdir(parents=True, exist_ok=True)
    sentinel = json.dumps({"steps": [{"name": "hand-authored", "cmd": ["true"]}]})
    recipe_path.write_text(sentinel, encoding="utf-8")

    exit_code, payload = _invoke(tmp_path, ["--target", "demo-recipe"], capsys)

    assert exit_code == 0
    assert payload["written"] is False
    assert payload["verdict"] == VERDICT_ACCEPTED
    assert recipe_path.read_text(encoding="utf-8") == sentinel, (
        "a pre-existing hand-authored .nwave/demo-recipe.json was clobbered "
        "instead of being left untouched and reported as a no-op"
    )


def test_demo_recipe_scaffold_second_run_is_byte_identical_noop(
    tmp_path: Path, capsys
) -> None:
    """Idempotency law (DESIGN §Contract-test suggestions): running
    `--target demo-recipe` twice against the SAME confidently-detectable
    layout produces byte-identical output the second time."""
    _seed_confidently_detectable_layout(tmp_path)

    first_exit, first_payload = _invoke(tmp_path, ["--target", "demo-recipe"], capsys)
    after_first = _recipe_path(tmp_path).read_text(encoding="utf-8")

    second_exit, second_payload = _invoke(tmp_path, ["--target", "demo-recipe"], capsys)
    after_second = _recipe_path(tmp_path).read_text(encoding="utf-8")

    assert first_exit == 0
    assert first_payload["written"] is True
    assert second_exit == 0
    assert second_payload["written"] is False
    assert after_second == after_first


# --- cross-target: never claim success while writing nothing --------------


@pytest.mark.parametrize(
    "case",
    [
        "environmental_e2e_missing_feature_delta",
        "environmental_e2e_e2e_test_not_found",
        "demo_recipe_ambiguous_layout",
    ],
)
def test_scaffold_never_reports_success_when_nothing_was_written(
    tmp_path: Path, capsys, case: str
) -> None:
    # Cross-cutting negative (both `--target` verbs): the command must NOT
    # report success (`verdict == accepted` / `written: true`) in any run
    # where it actually wrote nothing to disk -- the exact GDP-6
    # silent-wrong shape backlog #126 already named for the sibling
    # feature-end certifier.
    #
    # NOTE: deliberately no function docstring here -- see the sibling
    # note on `test_environmental_e2e_block_content_traces_to_the_declared_
    # e2e_test_path` (pytest-pspec docstring-as-JUnit-name collision across
    # parametrize cases).
    if case == "environmental_e2e_missing_feature_delta":
        # No feature-delta written at all.
        argv = [
            "--target",
            "environmental-e2e",
            "--feature-id",
            FEATURE_ID,
            "--e2e-test",
            E2E_TEST_RELPATH,
        ]
    elif case == "environmental_e2e_e2e_test_not_found":
        _write_feature_delta(tmp_path, FEATURE_ID, NO_E2E_BLOCK_FEATURE_DELTA)
        argv = [
            "--target",
            "environmental-e2e",
            "--feature-id",
            FEATURE_ID,
            "--e2e-test",
            E2E_TEST_RELPATH,
        ]
    else:
        # demo_recipe_ambiguous_layout: bare repo, nothing seeded.
        argv = ["--target", "demo-recipe"]

    exit_code, payload = _invoke(tmp_path, argv, capsys)

    assert exit_code != 0
    assert payload["verdict"] != VERDICT_ACCEPTED
    assert payload.get("written") is not True, (
        f"case={case!r} reported written=True alongside a non-accepted "
        f"verdict {payload.get('verdict')!r} -- success must never be "
        "claimed when nothing was actually written to disk"
    )

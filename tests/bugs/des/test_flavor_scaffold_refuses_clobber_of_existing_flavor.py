"""Regression (Vera examine 2026-07-09, DESTRUCTIVE): `des flavor-scaffold`
silently overwrites an EXISTING flavor file.

Bug: `des flavor-scaffold --flavor-id <id>` writes a fresh TODO-template
scaffold to `nWave/flavors/<id>.yaml` unconditionally -- with no
`target_path.exists()` check before `target_path.write_text(...)`
(``src/des/cli/flavor_scaffold.py:160``, preceded only by
``target_dir.mkdir(parents=True, exist_ok=True)`` at line 159). When `<id>`
names a flavor that already exists, the tool clobbers it: exit 0, no
warning, no refusal. Vera ran `des flavor-scaffold --flavor-id atdd_pure`
against this very repo and it overwrote the real production
`nWave/flavors/atdd_pure.yaml` with a placeholder skeleton.

RCA (tsunami-confirmed, `atoms_in_file` on `src/des/cli/flavor_scaffold.py`):
the `main()` member's only write-site is line 160
(`target_path.write_text(yaml_text, encoding="utf-8")`); no read/`exists()`
call on `target_path` appears anywhere in the module before that write.

Fix (crafter's job, NOT this test's): `flavor-scaffold` must refuse
(non-zero exit) with a clear message when the target flavor file already
exists, and must leave that file BYTE-UNCHANGED -- unless the operator
opts in to overwrite (e.g. `--force`). Scaffolding a NEW (non-existing)
flavor-id must keep working exactly as before.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition,
IN-PROCESS default): the REAL `des.cli.__main__.main()` dispatcher,
captured via `capsys` -- the same convention as the sibling regression AT
`tests/bugs/des/test_flavor_scaffold_produces_valid_flavor.py`. `--repo`
points at a `tmp_path` this test controls; the real
`nWave/flavors/` tree is never touched.

RED mechanism (semantic, not a collection/import error): today the
dispatcher DOES resolve `flavor-scaffold` (it is a registered subcommand)
and `main()` returns an ordinary `int` -- so `_invoke_dispatcher` never
raises. The negative AT's assertions on "pre-existing file bytes unchanged"
and "exit code non-zero" fail with a plain `AssertionError` because the
current implementation overwrites the file and exits 0.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.cli.__main__ import main as dispatcher_main


def _invoke_dispatcher(argv: list[str], capsys: pytest.CaptureFixture[str]):
    """Drive the REAL `des` dispatcher (`des.cli.__main__.main`) in-process.

    Normalizes both control-flow shapes the dispatcher can produce for a
    given argv into one `(exit_code, stdout, stderr)` tuple -- mirrors the
    sibling regression AT's helper of the same name so both tests read the
    same way. `flavor-scaffold` is a registered subcommand today, so
    `main()` is expected to return an ordinary `int`; the `SystemExit`
    branch is kept only for parity with argparse usage-error paths
    (e.g. a missing required `--flavor-id`).
    """
    try:
        exit_code = dispatcher_main(list(argv))
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


def _seed_existing_flavor(repo_root: Path, flavor_id: str, body: str) -> Path:
    """Create a pre-existing flavor file under a tmp_path-scoped repo, mimicking
    a real production flavor the scaffold must never clobber."""
    flavors_dir = repo_root / "nWave" / "flavors"
    flavors_dir.mkdir(parents=True, exist_ok=True)
    flavor_path = flavors_dir / f"{flavor_id}.yaml"
    flavor_path.write_text(body, encoding="utf-8")
    return flavor_path


def test_flavor_scaffold_creates_a_new_flavor_that_does_not_exist_yet(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """POSITIVE (control -- must stay green): scaffolding a flavor-id with NO
    pre-existing file still works, exactly as before the fix."""
    argv = [
        "flavor-scaffold",
        "--flavor-id",
        "brand_new_flavor",
        "--repo",
        str(tmp_path),
    ]
    exit_code, stdout, stderr = _invoke_dispatcher(argv, capsys)

    assert exit_code == 0, (
        "expected scaffolding a brand-new flavor-id to succeed (exit 0), "
        f"got exit_code={exit_code} stdout={stdout!r} stderr={stderr!r}"
    )

    written_path = tmp_path / "nWave" / "flavors" / "brand_new_flavor.yaml"
    assert written_path.exists(), (
        f"expected {written_path} to be created for a non-existing flavor-id, "
        f"but it was not written: stdout={stdout!r} stderr={stderr!r}"
    )
    assert "flavor_id: brand_new_flavor" in written_path.read_text(encoding="utf-8"), (
        "expected the newly-created file to carry the requested flavor_id"
    )


@pytest.mark.negative_at
def test_flavor_scaffold_never_silently_overwrites_an_existing_flavor(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """NEGATIVE AT (the bug): scaffolding an EXISTING flavor-id must NOT
    silently clobber it. The pre-existing file's bytes must be UNCHANGED
    after the command, the command must exit NON-ZERO, and the diagnostic
    must name the existing flavor and how to proceed.

    RED today: `flavor-scaffold` has no existence check before its write
    (`src/des/cli/flavor_scaffold.py:160`) -- it overwrites the file and
    exits 0, so every assertion below fails for a genuine business-logic
    reason (AssertionError), not a collection/import error.
    """
    original_body = (
        "flavor_id: atdd_pure\n"
        "display_name: ATDD Pure\n"
        "description: |\n"
        "  Production flavor content that must survive untouched.\n"
        "default: true\n"
        "selection: deterministic-config\n"
        "skill_load_set:\n"
        "  nw-software-crafter:\n"
        "    conditional: []\n"
    )
    flavor_path = _seed_existing_flavor(tmp_path, "atdd_pure", original_body)

    argv = [
        "flavor-scaffold",
        "--flavor-id",
        "atdd_pure",
        "--repo",
        str(tmp_path),
    ]
    exit_code, stdout, stderr = _invoke_dispatcher(argv, capsys)

    assert flavor_path.read_bytes() == original_body.encode("utf-8"), (
        "expected the pre-existing nWave/flavors/atdd_pure.yaml to be left "
        "BYTE-UNCHANGED when --flavor-id names a flavor that already "
        "exists -- the tool clobbered it instead. "
        f"stdout={stdout!r} stderr={stderr!r}"
    )

    assert exit_code != 0, (
        "expected `des flavor-scaffold --flavor-id atdd_pure` to REFUSE "
        "(non-zero exit) when the target flavor already exists, got "
        f"exit_code=0. stdout={stdout!r} stderr={stderr!r}"
    )

    diagnostic = stdout + stderr
    assert "atdd_pure" in diagnostic, (
        "expected the refusal diagnostic to name the existing flavor-id "
        f"('atdd_pure'), got stdout={stdout!r} stderr={stderr!r}"
    )

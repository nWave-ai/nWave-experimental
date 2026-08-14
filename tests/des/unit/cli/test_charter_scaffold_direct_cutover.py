"""AT -- `des charter-scaffold` direct cutover: closed seed-mode domain.

After direct cutover, `charter-scaffold` MUST:
- Remove `slice-plan` completely (never accept it as a choice)
- Make `--seed-mode` required and closed to exactly `direct-value`,
  `bug-observable`, `brownfield-discovery`
- Refuse any default or feature-delta access

Each scenario below verifies these constraints are enforced.

Driving surface: `des.cli.charter_scaffold.main(argv) -> int` invoked
IN-PROCESS against a `tmp_path` fixture repo (composition-root driving port).
No subprocess fork.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


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

FEATURE_ID = "seat-booking"

#: Each legal post-cutover seed-mode paired with the CLI flags that satisfy
#: ITS OWN required input, and a predicate confirming a scaffold landed.
_LEGAL_SEED_MODE_INPUT = {
    "direct-value": ["--value", "Operator sees last night's backup succeeded"],
    "bug-observable": ["--observable", "Clicking Save twice creates two invoices"],
    "brownfield-discovery": ["--area", "the legacy export pipeline"],
}


def _seed_repo(repo_root: Path) -> None:
    template_dir = repo_root / "nWave" / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "expectation-charter.md").write_text(
        TEMPLATE_SKELETON, encoding="utf-8"
    )


def _expectations_root(repo_root: Path) -> Path:
    return repo_root / "docs" / "product" / "expectations"


def _invoke(repo_root: Path, capsys, argv: list[str]) -> tuple[int, dict]:
    from des.cli import charter_scaffold

    exit_code = charter_scaffold.main(
        [*argv, "--repo-root", str(repo_root), "--format", "json"]
    )
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


@pytest.mark.parametrize(
    "seed_mode,own_flags",
    list(_LEGAL_SEED_MODE_INPUT.items()),
    ids=list(_LEGAL_SEED_MODE_INPUT),
)
def test_each_legal_seed_mode_is_accepted_with_its_own_required_input(
    tmp_path: Path, capsys, seed_mode: str, own_flags: list[str]
) -> None:
    _seed_repo(tmp_path)

    exit_code, payload = _invoke(
        tmp_path,
        capsys,
        ["--seed-mode", seed_mode, "--feature-id", FEATURE_ID, *own_flags],
    )

    assert exit_code == 0
    assert len(payload["created"]) == 1
    created_files = sorted(
        p.name for p in _expectations_root(tmp_path).glob(f"{FEATURE_ID}/*.md")
    )
    assert created_files == payload["created"]


@pytest.mark.parametrize(
    "seed_mode,own_flags",
    list(_LEGAL_SEED_MODE_INPUT.items()),
    ids=list(_LEGAL_SEED_MODE_INPUT),
)
def test_each_legal_seed_mode_never_reads_or_requires_a_feature_delta(
    tmp_path: Path, capsys, monkeypatch, seed_mode: str, own_flags: list[str]
) -> None:
    """No feature-delta access from charter-scaffold at all: even with NO
    feature-delta.md anywhere on disk, and with `Path.read_text` instrumented
    to fail loudly if ever consulted for feature-delta.md, every legal
    seed-mode still succeeds -- proving the production path never reaches for
    a feature-delta, not merely that none happened to exist."""
    _seed_repo(tmp_path)

    original_read_text = Path.read_text

    def _guard_read_text(self, *args, **kwargs):
        if self.name == "feature-delta.md":
            raise AssertionError(
                "charter-scaffold consulted feature-delta.md -- no legal "
                "post-cutover seed-mode may access a feature-delta"
            )
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _guard_read_text)

    exit_code, payload = _invoke(
        tmp_path,
        capsys,
        ["--seed-mode", seed_mode, "--feature-id", FEATURE_ID, *own_flags],
    )

    assert exit_code == 0
    assert len(payload["created"]) == 1


def test_omitted_seed_mode_refuses(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)

    from des.cli import charter_scaffold

    with pytest.raises(SystemExit) as excinfo:
        charter_scaffold.main(
            [
                "--feature-id",
                FEATURE_ID,
                "--value",
                "whatever",
                "--repo-root",
                str(tmp_path),
                "--format",
                "json",
            ]
        )
    assert excinfo.value.code != 0
    assert not _expectations_root(tmp_path).is_dir() or not any(
        _expectations_root(tmp_path).rglob("*.md")
    )


def test_explicit_slice_plan_seed_mode_refuses(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)

    from des.cli import charter_scaffold

    with pytest.raises(SystemExit) as excinfo:
        charter_scaffold.main(
            [
                "--seed-mode",
                "slice-plan",
                "--feature-id",
                FEATURE_ID,
                "--repo-root",
                str(tmp_path),
                "--format",
                "json",
            ]
        )
    assert excinfo.value.code != 0
    assert not _expectations_root(tmp_path).is_dir() or not any(
        _expectations_root(tmp_path).rglob("*.md")
    )


def test_unknown_seed_mode_token_refuses(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)

    from des.cli import charter_scaffold

    with pytest.raises(SystemExit) as excinfo:
        charter_scaffold.main(
            [
                "--seed-mode",
                "epic-mode",
                "--feature-id",
                FEATURE_ID,
                "--repo-root",
                str(tmp_path),
                "--format",
                "json",
            ]
        )
    assert excinfo.value.code != 0
    assert not _expectations_root(tmp_path).is_dir() or not any(
        _expectations_root(tmp_path).rglob("*.md")
    )

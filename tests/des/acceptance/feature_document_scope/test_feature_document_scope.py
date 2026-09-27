"""Public observations for distinct project and feature DES document scopes."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import nwave_ai.cli
import pytest

from des.application.handover import read_handover
from des.domain.feature_documents import merge_feature_destinations
from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance.design_document_construction.test_design_document_construction import (
    MANIFEST,
)
from tests.des.acceptance.devops_document_construction.test_devops_document_construction import (
    INPUT as DEVOPS_INPUT,
)
from tests.des.acceptance.distill_document_construction.test_distill_document_construction import (
    _discuss_payload,
    _distill_payload,
)
from tests.des.acceptance.steps_for_the_orchestrator.conftest import base_repository


HANDOVER = Path(".nwave/des/handover.json")
PRODUCT = {
    "docs/product/brief.md": b"# PRODUCT brief\n",
    "docs/product/architecture/brief.md": b"# PRODUCT architecture\n",
    "docs/product/acceptance/brief.md": b"# PRODUCT acceptance\n",
    "docs/product/operations/brief.md": b"# PRODUCT operations\n",
}


def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = base_repository(tmp_path / "repository")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("NWAVE_AGENTS_HOME", raising=False)
    monkeypatch.chdir(root)
    for name, content in PRODUCT.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return root


def _des(root: Path, *argv: str, stdin: str | None = None) -> tuple[int, str]:
    code, out, err = run_cli_in_process(
        list(argv), cwd=root, stdin_text=stdin, catch_all=True
    )
    return code, out + err


def _nwave(root: Path, *argv: str) -> tuple[int, str]:
    code, out, err = run_cli_in_process(
        list(argv), cwd=root, main=nwave_ai.cli.main_with_argv, catch_all=True
    )
    return code, out + err


def _tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git" not in p.parts and p.suffix != ".lock"
    }


def _flow(root: Path, feature: str) -> None:
    code, text = _des(
        root,
        "discuss",
        "--repo-root",
        str(root),
        "--feature",
        feature,
        "--input",
        "-",
        stdin=json.dumps(_discuss_payload()),
    )
    assert code == 0, text
    # Scope is durable: later steps carry no --feature flag; the handover binds it.
    for step, payload in (
        (("design", "--value", "1"), MANIFEST),
        (("distill",), _distill_payload()),
    ):
        code, text = _des(
            root,
            step[0],
            "--repo-root",
            str(root),
            *step[1:],
            "--input",
            "-",
            stdin=json.dumps(payload),
        )
        assert code == 0, text
    code, text = _des(
        root,
        "devops",
        "--repo-root",
        str(root),
        "--feature",
        feature,
        "--input",
        "-",
        stdin=json.dumps(DEVOPS_INPUT),
    )
    assert code == 0, text


def test_feature_scopes_are_distinct_and_never_touch_product_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path, monkeypatch)
    code, text = _nwave(
        root,
        "project",
        "feature-document",
        "feature-a",
        "design",
        "docs/feature/feature-a/design/a-design.md",
    )
    assert code == 0, text
    _flow(root, "feature-a")
    stored = read_handover((root / HANDOVER).read_bytes())
    assert stored.feature_id == "feature-a"
    (root / HANDOVER).unlink()
    _flow(root, "feature-b")
    for name, content in PRODUCT.items():
        assert (root / name).read_bytes() == content
    a = {
        "docs/feature/feature-a/brief.md",
        "docs/feature/feature-a/design/a-design.md",
        "docs/feature/feature-a/acceptance/brief.md",
        "docs/feature/feature-a/operations/brief.md",
    }
    b = {
        "docs/feature/feature-b/brief.md",
        "docs/feature/feature-b/architecture/brief.md",
        "docs/feature/feature-b/acceptance/brief.md",
        "docs/feature/feature-b/operations/brief.md",
    }
    assert all((root / name).is_file() for name in a | b)
    assert not (root / "docs/feature/feature-a/architecture/brief.md").exists()
    assert not (root / "docs/feature/feature-b/x").exists()


def test_bad_scope_config_and_mismatch_refuse_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path, monkeypatch)
    discuss = ["discuss", "--repo-root", str(root), "--input", "-"]
    raw = json.dumps(_discuss_payload())
    before = _tree(root)
    for bad in ("Bad_ID", "../x", "-a", ""):
        code, _ = _des(root, *discuss, "--feature", bad, stdin=raw)
        assert code != 0 and _tree(root) == before, bad
    for bad_config in (
        "{not json",
        json.dumps({"documents": {"design": {"destination": "../out.md"}}}),
        json.dumps(
            {"documents": {"discuss": {"destination": "docs/feature/other/brief.md"}}}
        ),
    ):
        cfg = root / ".nwave/features/feature-a/config.json"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(bad_config)
        before = _tree(root)
        code, _ = _des(root, *discuss, "--feature", "feature-a", stdin=raw)
        assert code != 0 and _tree(root) == before
    cfg.unlink()
    assert _des(root, *discuss, "--feature", "feature-a", stdin=raw)[0] == 0
    before = _tree(root)
    code, _ = _des(
        root,
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        "--feature",
        "feature-b",
        "--input",
        "-",
        stdin=json.dumps(MANIFEST),
    )
    assert code != 0 and _tree(root) == before


def test_merge_law_resolves_each_wave_independently_and_ignores_flat_paths() -> None:
    merged = merge_feature_destinations(
        "f1",
        global_documents={
            "design": {"destination": "docs/flat.md"},
            "feature": {"discuss": {"destination": "g/{feature}.md"}},
        },
        project_documents={"feature": {"distill": {"destination": "p/{feature}/a.md"}}},
        feature_documents={"design": {"destination": "g/mine.md"}},
    )
    assert merged == {
        "discuss": "g/f1.md",
        "design": "g/mine.md",
        "distill": "p/f1/a.md",
        "devops": "docs/feature/f1/operations/brief.md",
    }


def test_bound_scope_survives_a_real_new_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path, monkeypatch)
    code, text = _des(
        root,
        "discuss",
        "--repo-root",
        str(root),
        "--feature",
        "feature-a",
        "--input",
        "-",
        stdin=json.dumps(_discuss_payload()),
    )
    assert code == 0, text
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "des",
            "design",
            "--repo-root",
            str(root),
            "--value",
            "1",
            "--input",
            "-",
        ],
        input=json.dumps(MANIFEST),
        text=True,
        capture_output=True,
        cwd=root,
        env={**__import__("os").environ, "HOME": str(tmp_path / "home")},
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert (root / "docs/feature/feature-a/architecture/brief.md").is_file()
    assert (root / "docs/product/architecture/brief.md").read_bytes() == PRODUCT[
        "docs/product/architecture/brief.md"
    ]


def test_feature_config_writer_uses_the_readers_root_in_linked_worktree_and_subdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    main = _repo(tmp_path, monkeypatch)
    worktree = tmp_path / "linked"
    subprocess.run(
        ["git", "-C", str(main), "worktree", "add", "--detach", str(worktree)],
        check=True,
        capture_output=True,
    )
    nested = worktree / "src" / "deep"
    nested.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(nested)
    code, text = _nwave(
        nested,
        "project",
        "feature-document",
        "feature-a",
        "design",
        "docs/feature/feature-a/custom/d.md",
    )
    assert code == 0, text
    assert (main / ".nwave/features/feature-a/config.json").is_file()
    assert not (worktree / ".nwave/features").exists()
    assert not (nested / ".nwave").exists()
    from des.adapters.driven.config.des_config import DESConfig

    assert DESConfig.feature_document_destinations(worktree, "feature-a")["design"] == (
        "docs/feature/feature-a/custom/d.md"
    )
    code, text = _nwave(
        nested,
        "project",
        "feature-template",
        "design",
        "docs/feature/{feature}/arch/b.md",
    )
    assert code == 0, text
    assert not (worktree / ".nwave/config.json").exists()
    assert "arch/b.md" in (main / ".nwave/config.json").read_text()


@pytest.mark.parametrize(
    "flags,scope,path",
    [
        (["--project"], {"kind": "project"}, "docs/product/brief.md"),
        (
            ["--epic", "checkout"],
            {"kind": "epic", "epic_id": "checkout"},
            "docs/epic/checkout/brief.md",
        ),
        (
            ["--feature", "checkout"],
            {"kind": "feature", "feature_id": "checkout"},
            "docs/feature/checkout/brief.md",
        ),
        (
            ["--slice", "checkout", "slice-01"],
            {"kind": "slice", "feature_id": "checkout", "slice_id": "slice-01"},
            "docs/feature/checkout/brief.md",
        ),
    ],
)
def test_explicit_scope_survives_design_and_discuss_rewrite(
    tmp_path, flags, scope, path
):
    root = base_repository(tmp_path / "scope")
    raw = json.dumps(_discuss_payload())
    code, text = _des(
        root, "discuss", "--repo-root", str(root), *flags, "--input", "-", stdin=raw
    )
    assert code == 0, text
    assert (root / path).exists()
    assert json.loads((root / HANDOVER).read_bytes())["scope"] == scope
    code, text = _des(
        root,
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        "--input",
        "-",
        stdin=json.dumps(MANIFEST),
    )
    assert code == 0, text
    code, text = _des(
        root,
        "discuss",
        "--repo-root",
        str(root),
        *flags,
        "--replace-current",
        "--input",
        "-",
        stdin=raw,
    )
    assert code == 0, text
    assert json.loads((root / HANDOVER).read_bytes())["scope"] == scope


@pytest.mark.parametrize("command", ["discuss", "po", "devops"])
def test_root_document_commands_require_explicit_scope_before_writing(
    tmp_path, command
):
    root = base_repository(tmp_path / "missing-scope")
    before = _tree(root)
    code, _text = _des(root, command, "--repo-root", str(root), stdin="{}")
    assert code != 0
    assert _tree(root) == before


def test_epic_configuration_is_separate_and_malformed_config_writes_nothing(
    tmp_path, monkeypatch
):
    root = _repo(tmp_path, monkeypatch)
    config = root / ".nwave/config.json"
    config.parent.mkdir(exist_ok=True)
    config.write_text(
        json.dumps(
            {
                "documents": {
                    "epic": {"discuss": {"destination": "docs/epic/{epic}/product.md"}}
                }
            }
        )
    )
    args = ["discuss", "--repo-root", str(root), "--epic", "orders", "--input", "-"]
    raw = json.dumps(_discuss_payload())
    assert _des(root, *args, stdin=raw)[0] == 0
    assert (root / "docs/epic/orders/product.md").exists()
    for path, content in PRODUCT.items():
        assert (root / path).read_bytes() == content
    override = root / ".nwave/epics/orders/config.json"
    override.parent.mkdir(parents=True)
    override.write_text("{broken")
    before = _tree(root)
    code, _text = _des(root, *args, "--replace-current", stdin=raw)
    assert code != 0
    assert _tree(root) == before


@pytest.mark.parametrize(
    "scope",
    [
        None,
        {},
        {"kind": "slice", "slice_id": "slice-01"},
        {"kind": "epic"},
        {"kind": "project", "feature_id": "x"},
    ],
)
def test_malformed_persisted_scope_is_never_project(scope):
    from des.application.handover import Blocked

    raw = json.dumps(
        {
            "request": "x",
            "scope": scope,
            "values": [{"observation": "A", "dependencies": [], "authority": None}],
        }
    ).encode()
    assert isinstance(read_handover(raw), Blocked)

"""Argv/JSON proof for `des resolve-charters` (ADR-SSOT-002 §4b projection).

Drives `main()` against a real temporary filesystem tree -- never a mocked
Discover/Resolve algebra -- asserting the exact one-JSON-line contract, no
writes, and byte-identical tree state before/after every invocation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from des.cli import resolve_charters


_FILLED_CHARTER = """# Expectation charter

## Preconditions

Start a clean checkout and run `make demo`.

## Expected observations (oracle)

- Positive: the demo prints "ready".
- Negative: the demo does NOT print a stack trace.
"""


def _run(capsys, argv: list[str]) -> tuple[int, dict]:
    exit_code = resolve_charters.main(argv)
    captured = capsys.readouterr()
    assert captured.out.count("\n") == 1
    assert captured.err == ""
    return exit_code, json.loads(captured.out)


def _tree_digest(root: Path) -> str:
    hasher = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        hasher.update(str(path.relative_to(root)).encode("utf-8"))
        hasher.update(b"\0")
        if path.is_symlink():
            hasher.update(b"symlink:" + str(path.readlink()).encode("utf-8"))
        elif path.is_file():
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


def _base_argv(repo_root: Path, delivery_id: str, examine: str) -> list[str]:
    return [
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        delivery_id,
        "--examine",
        examine,
    ]


def test_examine_false_returns_skip_without_namespace_io(tmp_path, capsys):
    exit_code, payload = _run(capsys, _base_argv(tmp_path, "some-id", "false"))
    assert exit_code == 0
    assert payload == {"status": "SKIP"}
    assert not (tmp_path / "docs").exists()


def test_examine_false_skips_with_hostile_namespace_untouched(tmp_path, capsys):
    namespace_parent = tmp_path / "docs" / "product" / "expectations"
    namespace_parent.mkdir(parents=True)
    real = tmp_path / "elsewhere"
    real.mkdir()
    (namespace_parent / "hostile-id").symlink_to(real, target_is_directory=True)

    exit_code, payload = _run(capsys, _base_argv(tmp_path, "hostile-id", "false"))

    assert exit_code == 0
    assert payload == {"status": "SKIP"}
    assert (namespace_parent / "hostile-id").is_symlink()


def test_missing_namespace_returns_author(tmp_path, capsys):
    exit_code, payload = _run(capsys, _base_argv(tmp_path, "missing-id", "true"))
    assert exit_code == 0
    assert payload == {
        "status": "AUTHOR",
        "namespace": "docs/product/expectations/missing-id",
    }


def test_empty_namespace_returns_author(tmp_path, capsys):
    namespace = tmp_path / "docs" / "product" / "expectations" / "empty-id"
    namespace.mkdir(parents=True)
    exit_code, payload = _run(capsys, _base_argv(tmp_path, "empty-id", "true"))
    assert exit_code == 0
    assert payload == {
        "status": "AUTHOR",
        "namespace": "docs/product/expectations/empty-id",
    }


def test_deterministic_multi_valid_returns_ordered_repo_relative_reuse(
    tmp_path, capsys
):
    namespace = tmp_path / "docs" / "product" / "expectations" / "multi-id"
    namespace.mkdir(parents=True)
    (namespace / "b-charter.md").write_text(_FILLED_CHARTER, encoding="utf-8")
    (namespace / "a-charter.md").write_text(_FILLED_CHARTER, encoding="utf-8")

    exit_code, payload = _run(capsys, _base_argv(tmp_path, "multi-id", "true"))

    assert exit_code == 0
    assert payload == {
        "status": "REUSE",
        "charter-paths": [
            "docs/product/expectations/multi-id/a-charter.md",
            "docs/product/expectations/multi-id/b-charter.md",
        ],
    }


def test_namespace_symlink_blocks(tmp_path, capsys):
    real = tmp_path / "elsewhere"
    real.mkdir()
    namespace_parent = tmp_path / "docs" / "product" / "expectations"
    namespace_parent.mkdir(parents=True)
    (namespace_parent / "linked-id").symlink_to(real, target_is_directory=True)

    exit_code, payload = _run(capsys, _base_argv(tmp_path, "linked-id", "true"))

    assert exit_code == resolve_charters._EXIT_USAGE_ERROR
    assert payload["status"] == "BLOCK"
    assert "symlink" in payload["what"]


def test_member_symlink_blocks(tmp_path, capsys):
    namespace = tmp_path / "docs" / "product" / "expectations" / "member-symlink-id"
    namespace.mkdir(parents=True)
    real = tmp_path / "outside.md"
    real.write_text(_FILLED_CHARTER, encoding="utf-8")
    (namespace / "linked.md").symlink_to(real)

    exit_code, payload = _run(capsys, _base_argv(tmp_path, "member-symlink-id", "true"))

    assert exit_code == resolve_charters._EXIT_USAGE_ERROR
    assert payload["status"] == "BLOCK"
    assert "symlink" in payload["what"]


def test_nested_directory_member_blocks(tmp_path, capsys):
    namespace = tmp_path / "docs" / "product" / "expectations" / "nested-dir-id"
    (namespace / "sub").mkdir(parents=True)

    exit_code, payload = _run(capsys, _base_argv(tmp_path, "nested-dir-id", "true"))

    assert exit_code == resolve_charters._EXIT_USAGE_ERROR
    assert payload["status"] == "BLOCK"
    assert "directory" in payload["what"]


def test_non_markdown_member_blocks(tmp_path, capsys):
    namespace = tmp_path / "docs" / "product" / "expectations" / "non-md-id"
    namespace.mkdir(parents=True)
    (namespace / "notes.txt").write_text("x", encoding="utf-8")

    exit_code, payload = _run(capsys, _base_argv(tmp_path, "non-md-id", "true"))

    assert exit_code == resolve_charters._EXIT_USAGE_ERROR
    assert payload["status"] == "BLOCK"
    assert "Markdown" in payload["what"]


def test_unfilled_member_blocks(tmp_path, capsys):
    namespace = tmp_path / "docs" / "product" / "expectations" / "unfilled-id"
    namespace.mkdir(parents=True)
    (namespace / "draft.md").write_text("# Title\n", encoding="utf-8")

    exit_code, payload = _run(capsys, _base_argv(tmp_path, "unfilled-id", "true"))

    assert exit_code == resolve_charters._EXIT_USAGE_ERROR
    assert payload["status"] == "BLOCK"
    assert "unfilled" in payload["what"]


@pytest.mark.parametrize(
    "delivery_id",
    ["../escape", "UPPER", "-leading-dash", "trailing/slash", "has space", ""],
)
def test_invalid_delivery_id_blocks(tmp_path, capsys, delivery_id):
    exit_code, payload = _run(capsys, _base_argv(tmp_path, delivery_id, "true"))
    assert exit_code == resolve_charters._EXIT_USAGE_ERROR
    assert payload["status"] == "BLOCK"


def test_delivery_id_validation_is_derived_from_shipped_schema(
    tmp_path, capsys, monkeypatch
):
    schema_path = tmp_path / "contract.schema.json"
    schema_path.write_text(
        json.dumps({"$defs": {"id": {"type": "string", "const": "only-id"}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        resolve_charters, "resolve_delivery_contract_schema_path", lambda: schema_path
    )

    accepted_code, accepted = _run(capsys, _base_argv(tmp_path, "only-id", "false"))
    refused_code, refused = _run(capsys, _base_argv(tmp_path, "some-id", "false"))

    assert accepted_code == 0
    assert accepted == {"status": "SKIP"}
    assert refused_code == resolve_charters._EXIT_USAGE_ERROR
    assert refused["status"] == "BLOCK"


def test_missing_delivery_id_schema_blocks_before_namespace_io(
    tmp_path, capsys, monkeypatch
):
    missing_schema = tmp_path / "missing.schema.json"
    monkeypatch.setattr(
        resolve_charters,
        "resolve_delivery_contract_schema_path",
        lambda: missing_schema,
    )

    exit_code, payload = _run(capsys, _base_argv(tmp_path, "some-id", "false"))

    assert exit_code == resolve_charters._EXIT_USAGE_ERROR
    assert payload["status"] == "BLOCK"
    assert not (tmp_path / "docs").exists()


@pytest.mark.parametrize(
    "argv",
    [
        ["--repo-root", "/tmp", "--delivery-id", "id", "--examine", "maybe"],
        ["--repo-root", "/tmp", "--delivery-id", "id"],
    ],
)
def test_malformed_argv_blocks_as_one_json_line(capsys, argv):
    exit_code, payload = _run(capsys, argv)
    assert exit_code == resolve_charters._EXIT_USAGE_ERROR
    assert payload["status"] == "BLOCK"


def test_relative_repo_root_blocks(capsys):
    exit_code, payload = _run(
        capsys, ["--repo-root", "relative", "--delivery-id", "id", "--examine", "true"]
    )
    assert exit_code == resolve_charters._EXIT_USAGE_ERROR
    assert payload["status"] == "BLOCK"


def test_symlink_repo_root_blocks(tmp_path, capsys):
    real = tmp_path / "real-root"
    real.mkdir()
    linked = tmp_path / "linked-root"
    linked.symlink_to(real, target_is_directory=True)

    exit_code, payload = _run(capsys, _base_argv(linked, "id", "true"))

    assert exit_code == resolve_charters._EXIT_USAGE_ERROR
    assert payload["status"] == "BLOCK"


def test_byte_identical_tree_digest_no_mutation(tmp_path, capsys):
    namespace = tmp_path / "docs" / "product" / "expectations" / "digest-id"
    namespace.mkdir(parents=True)
    (namespace / "a.md").write_text(_FILLED_CHARTER, encoding="utf-8")
    before = _tree_digest(tmp_path)

    _run(capsys, _base_argv(tmp_path, "digest-id", "true"))

    after = _tree_digest(tmp_path)
    assert before == after

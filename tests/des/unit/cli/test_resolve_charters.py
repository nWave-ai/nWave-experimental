"""Argv/JSON proof for `des resolve-charters` (ADR-SSOT-002 §4b projection).

Drives `main()` against a real temporary filesystem tree -- never a mocked
Discover/Resolve algebra -- asserting the exact one-JSON-line contract, no
writes, and byte-identical tree state before/after every invocation.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

import pytest

from des.application.ordinary_request import build_po_envelope, compute_delivery_id
from des.cli import resolve_charters


_FILLED_CHARTER = """# Expectation charter

## Preconditions

Start a clean checkout and run `make demo`.

## Expected observations (oracle)

- Positive: the demo prints "ready".
- Negative: the demo does NOT print a stack trace.
"""


class _FakeStdin:
    """A genuine byte stream on `.buffer`, matching `sys.stdin`'s shape."""

    def __init__(self, seed_bytes: bytes) -> None:
        self.buffer = io.BytesIO(seed_bytes)


def _run(
    capsys, argv: list[str], *, monkeypatch=None, seed_bytes: bytes | None = None
) -> tuple[int, dict]:
    if monkeypatch is not None:
        monkeypatch.setattr(sys, "stdin", _FakeStdin(seed_bytes or b""))
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


def test_missing_namespace_returns_author(tmp_path, capsys, monkeypatch):
    seed = "Ship the widget end to end."
    delivery_id = compute_delivery_id(seed)
    exit_code, payload = _run(
        capsys,
        _base_argv(tmp_path, delivery_id, "true"),
        monkeypatch=monkeypatch,
        seed_bytes=seed.encode("utf-8"),
    )
    assert exit_code == 0
    namespace = f"docs/product/expectations/{delivery_id}"
    assert payload == {
        "status": "AUTHOR",
        "namespace": namespace,
        "envelope": build_po_envelope(
            delivery_id=delivery_id,
            namespace=namespace,
            root=str(tmp_path.resolve()),
            value_seed=seed,
        ),
    }


def test_empty_namespace_returns_author(tmp_path, capsys, monkeypatch):
    seed = "Ship a different widget."
    delivery_id = compute_delivery_id(seed)
    namespace_dir = tmp_path / "docs" / "product" / "expectations" / delivery_id
    namespace_dir.mkdir(parents=True)
    exit_code, payload = _run(
        capsys,
        _base_argv(tmp_path, delivery_id, "true"),
        monkeypatch=monkeypatch,
        seed_bytes=seed.encode("utf-8"),
    )
    assert exit_code == 0
    namespace = f"docs/product/expectations/{delivery_id}"
    assert payload == {
        "status": "AUTHOR",
        "namespace": namespace,
        "envelope": build_po_envelope(
            delivery_id=delivery_id,
            namespace=namespace,
            root=str(tmp_path.resolve()),
            value_seed=seed,
        ),
    }


def test_author_without_stdin_seed_blocks(tmp_path, capsys, monkeypatch):
    """The producer never persists VALUE-SEED anywhere -- `AUTHOR` without a
    piped seed must refuse, never emit an envelope with a missing/invented
    VALUE-SEED."""
    exit_code, payload = _run(
        capsys,
        _base_argv(tmp_path, "missing-id", "true"),
        monkeypatch=monkeypatch,
        seed_bytes=b"",
    )
    assert exit_code != 0
    assert payload["status"] == "BLOCK"
    assert "value seed" in payload["what"]


def test_author_with_mismatched_seed_blocks(tmp_path, capsys, monkeypatch):
    """A piped VALUE-SEED that does not hash to the given --delivery-id
    must refuse -- never silently embed a mismatched seed in the envelope."""
    exit_code, payload = _run(
        capsys,
        _base_argv(tmp_path, "missing-id", "true"),
        monkeypatch=monkeypatch,
        seed_bytes=b"This seed does not hash to missing-id.",
    )
    assert exit_code != 0
    assert payload["status"] == "BLOCK"
    assert "missing-id" in payload["what"]


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


class TestPoEnvelopeIsPrintedVerbatimAndAcceptedByTheRealHook:
    """K4 Run 6 evidence: the root hand-authored the PO dispatch envelope,
    was rejected by the hook twice (malformed header), then forwarded the
    architecture anchor into PO's own context (`CHARTER-AUTHOR-DISQUALIFIED`
    -- a matrix row 10 regression), ~8 minutes lost. `des resolve-charters`
    must print the exact ready-to-paste envelope on `AUTHOR` -- sourced from
    a REAL `des prepare-ordinary-request` run, never a hand-built fixture --
    and that printed envelope must be accepted by the real hook gate, while
    a hand-authored variant carrying an architecture anchor is denied."""

    @staticmethod
    def _init_repo(tmp_path) -> Path:
        import subprocess

        root = tmp_path / "repo"
        root.mkdir()
        env = {
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t.example",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t.example",
        }
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        (root / "README.md").write_text("x", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "init"], cwd=root, check=True, env=env
        )
        return root

    def test_envelope_from_a_real_prepared_request_is_allowed_by_the_hook(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        from des.adapters.drivers.hooks.pre_tool_use_handler import (
            _evaluate_auto_root_po_envelope,
        )
        from des.cli import prepare_ordinary_request

        root = self._init_repo(tmp_path)
        seed = "FEATURE -- maintenance windows end to end."

        monkeypatch.setattr(sys, "stdin", _FakeStdin(seed.encode("utf-8")))
        prep_exit = prepare_ordinary_request.main(
            [
                "--size",
                "M",
                "--repo-root",
                str(root),
                "--architecture-authority",
                "ARCHITECTURE-COVERED: docs/architecture/adrs/adr-1.md#decision",
                "--delivery-route",
                "RED_TO_GREEN",
                "--examine",
                "true",
                "--independent-review",
                "false",
            ]
        )
        atd_body = capsys.readouterr().out
        assert prep_exit == 0
        delivery_id = compute_delivery_id(seed)
        assert f"DELIVERY-ID: {delivery_id}" in atd_body

        exit_code, payload = _run(
            capsys,
            _base_argv(root, delivery_id, "true"),
            monkeypatch=monkeypatch,
            seed_bytes=seed.encode("utf-8"),
        )
        assert exit_code == 0
        assert payload["status"] == "AUTHOR"
        envelope = payload["envelope"]

        # PO-side check: the printed envelope never carries the
        # architecture-authority anchor -- PO disqualifies itself as
        # charter author the instant its context carries one.
        assert "ARCHITECTURE-COVERED" not in envelope
        assert f"DELIVERY-ID: {delivery_id}" in envelope

        # The real hook gate allows this envelope verbatim.
        assert _evaluate_auto_root_po_envelope(envelope) is None

    def test_hand_authored_variant_with_an_architecture_anchor_is_denied(
        self, tmp_path
    ) -> None:
        from des.adapters.drivers.hooks.pre_tool_use_handler import (
            _evaluate_auto_root_po_envelope,
        )

        delivery_id = compute_delivery_id("Ship it.")
        envelope = build_po_envelope(
            delivery_id=delivery_id,
            namespace=f"docs/product/expectations/{delivery_id}",
            root=str(tmp_path.resolve()),
            value_seed="Ship it.",
        )
        hand_variant = (
            "ARCHITECTURE-COVERED: docs/architecture/adrs/adr-1.md#decision\n\n"
            + envelope
        )

        assert _evaluate_auto_root_po_envelope(hand_variant) is not None

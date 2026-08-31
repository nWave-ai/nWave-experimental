"""Executable contract for provider-neutral DeliveryContract validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des._internal.delivery_contract_schema import (
    resolve_delivery_contract_schema_path,
)
from des.cli import dispatch as dispatch_cli
from des.cli.__main__ import _REGISTRY
from des.cli.validate_delivery_contract import main
from tests.common.delivery_contract_fixture import seed_referenced_oracle


ROOT = Path(__file__).resolve().parents[4]
EXAMPLE = ROOT / "docs/delivery-contracts/fix-language-agnostic-contract-paths.json"
SCHEMA = ROOT / "nWave/schemas/thin-delivery-contract.schema.json"


def test_valid_contract_returns_installed_schema_identity(
    tmp_path: Path, capsys
) -> None:
    contract = tmp_path / "delivery.json"
    contract.write_bytes(EXAMPLE.read_bytes())
    seed_referenced_oracle(tmp_path, json.loads(EXAMPLE.read_text(encoding="utf-8")))

    exit_code = main(
        [
            "--repo-root",
            str(tmp_path),
            "--delivery-contract",
            "delivery.json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["verdict"] == "VALID"
    assert payload["contract"] == "delivery.json"
    assert payload["digest"].startswith("sha256:")


def test_schema_invalid_contract_refuses_loudly(tmp_path: Path, capsys) -> None:
    (tmp_path / "delivery.json").write_text("{}", encoding="utf-8")

    exit_code = main(
        [
            "--repo-root",
            str(tmp_path),
            "--delivery-contract",
            "delivery.json",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "fails the thin-delivery-contract schema" in captured.err
    assert "WHAT:" in captured.err
    assert "WHY:" in captured.err
    assert "HOW:" in captured.err


def test_validator_and_dispatch_share_one_closure_digest(
    tmp_path: Path, capsys
) -> None:
    contract = tmp_path / "delivery.json"
    contract.write_bytes(EXAMPLE.read_bytes())
    seed_referenced_oracle(tmp_path, json.loads(EXAMPLE.read_text(encoding="utf-8")))
    args = ["--repo-root", str(tmp_path), "--delivery-contract", "delivery.json"]

    validate_exit = main(args)
    validate_digest = json.loads(capsys.readouterr().out)["digest"]

    dispatch_exit = dispatch_cli.main(args)
    dispatch_out = capsys.readouterr().out

    assert validate_exit == 0
    assert dispatch_exit == 0
    dispatch_digest = next(
        line.removeprefix("THIN-DELIVERY-CONTRACT-DIGEST: ")
        for line in dispatch_out.splitlines()
        if line.startswith("THIN-DELIVERY-CONTRACT-DIGEST: ")
    )
    assert validate_digest == dispatch_digest


def _seed_supporting_contract(tmp_path: Path) -> tuple[Path, list[Path]]:
    contract_dict = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    contract_dict["schema-version"] = "1.4"
    locators = ["spec/law.tla", "tests/support/widget.json"]
    contract_dict["acceptance-tests"]["supporting-locators"] = locators
    contract_path = tmp_path / "delivery.json"
    contract_path.write_text(json.dumps(contract_dict), encoding="utf-8")
    seed_referenced_oracle(tmp_path, contract_dict)
    paths = [tmp_path / locator for locator in locators]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"support:{path.name}\n", encoding="utf-8")
    return contract_path, paths


def _point_of_use_consumer_verdict(
    frozen_digest: str, validator_payload: dict[str, str]
) -> str:
    """Executable projection of the crafter's mandated equality decision."""
    if (
        validator_payload.get("verdict") != "VALID"
        or validator_payload.get("digest") != frozen_digest
    ):
        return "INDETERMINATE"
    return "VALID"


def test_frozen_dispatch_digest_detects_support_mutation_at_consumer_boundary(
    tmp_path: Path, capsys
) -> None:
    contract, support_paths = _seed_supporting_contract(tmp_path)
    args = ["--repo-root", str(tmp_path), "--delivery-contract", contract.name]

    assert dispatch_cli.main(args) == 0
    frozen = next(
        line.removeprefix("THIN-DELIVERY-CONTRACT-DIGEST: ")
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("THIN-DELIVERY-CONTRACT-DIGEST: ")
    )

    support_paths[1].write_bytes(support_paths[1].read_bytes() + b"mutated\n")
    assert main(args) == 0
    current = json.loads(capsys.readouterr().out)

    assert current["digest"] != frozen
    assert _point_of_use_consumer_verdict(frozen, current) == "INDETERMINATE"


def test_delivery_closure_digest_vectors_pin_v1_compatibility_and_v2_framing() -> None:
    assert dispatch_cli.closure_digest(b"contract", b"oracle") == (
        "48cd745ce7d714b4b42347ff758c8a79c59e06c97404b69bbf780ad866be5b80"
    )
    v2_digest = dispatch_cli.closure_digest(
        b"contract",
        b"oracle",
        oracle_locator="tests/test_x.py::test_x",
        supporting_files=(
            ("spec/Law.tla", b"tla"),
            ("tests/data.json", b"json"),
        ),
    )
    assert v2_digest == (
        "c85b9d6d93135bf25d850571ffb740286b524c647b906a3dfbe6022649a5613a"
    )
    assert v2_digest != dispatch_cli.closure_digest(
        b"contract",
        b"oracle",
        oracle_locator="tests/test_x.py::other_test",
        supporting_files=(
            ("spec/Law.tla", b"tla"),
            ("tests/data.json", b"json"),
        ),
    )
    assert v2_digest != dispatch_cli.closure_digest(
        b"contract",
        b"oracle",
        oracle_locator="tests/test_x.py::test_x",
        supporting_files=(
            ("spec/Other.tla", b"tla"),
            ("tests/data.json", b"json"),
        ),
    )


@pytest.mark.parametrize("consumer", [main, dispatch_cli.main])
def test_unreadable_support_refuses_before_handoff(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch, consumer
) -> None:
    contract_path, support_paths = _seed_supporting_contract(tmp_path)
    unreadable = support_paths[0]
    original_open = dispatch_cli.os.open

    def fail_one_support(path, flags, *args):
        if Path(path) == unreadable:
            raise PermissionError("injected unreadable support")
        return original_open(path, flags, *args)

    monkeypatch.setattr(dispatch_cli.os, "open", fail_one_support)

    exit_code = consumer(
        ["--repo-root", str(tmp_path), "--delivery-contract", contract_path.name]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "cannot be opened" in captured.err
    assert "WHAT:" in captured.err
    assert "WHY:" in captured.err
    assert "HOW:" in captured.err


@pytest.mark.parametrize("consumer", [main, dispatch_cli.main])
def test_support_swapped_to_symlink_between_check_and_open_refuses(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch, consumer
) -> None:
    contract_path, support_paths = _seed_supporting_contract(tmp_path)
    victim, target = support_paths
    original_open = dispatch_cli.os.open
    swapped = False

    def swap_before_open(path, flags, *args):
        nonlocal swapped
        if Path(path) == victim and not swapped:
            swapped = True
            victim.unlink()
            victim.symlink_to(target)
        return original_open(path, flags, *args)

    monkeypatch.setattr(dispatch_cli.os, "open", swap_before_open)

    exit_code = consumer(
        ["--repo-root", str(tmp_path), "--delivery-contract", contract_path.name]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "without following links" in captured.err
    assert "WHAT:" in captured.err
    assert "WHY:" in captured.err
    assert "HOW:" in captured.err


class _NonDiscriminatingStat:
    """One stat observation from a filesystem whose tick cannot discriminate.

    The reviewer reproduced same-size writes whose mtime was restored and
    whose ctime did not advance within the observable filesystem tick.  This
    projects that environment at the OS boundary the consumer really observes:
    identity, mode and every byte-relevant metadata field stay equal across
    the mutation, so only the bytes themselves can discriminate it.
    """

    def __init__(self, observed, ctime_ns: int) -> None:
        self._observed = observed
        self.st_ctime_ns = ctime_ns

    def __getattr__(self, name: str):
        return getattr(self._observed, name)


@pytest.mark.parametrize("consumer", [main, dispatch_cli.main])
@pytest.mark.parametrize("mutation_hook", ["after_fd_read", "before_final_lstat"])
def test_support_same_inode_same_metadata_byte_mutation_refuses(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
    consumer,
    mutation_hook: str,
) -> None:
    contract_path, support_paths = _seed_supporting_contract(tmp_path)
    victim = support_paths[0]
    victim_identity = victim.lstat()
    original_fdopen = dispatch_cli.os.fdopen
    original_fstat = dispatch_cli.os.fstat
    original_lstat = Path.lstat
    mutated = False
    victim_read = False

    def without_tick_discrimination(observed):
        if (observed.st_dev, observed.st_ino) == (
            victim_identity.st_dev,
            victim_identity.st_ino,
        ):
            return _NonDiscriminatingStat(observed, victim_identity.st_ctime_ns)
        return observed

    def mutate_same_size() -> None:
        nonlocal mutated
        victim.write_bytes(b"B" * victim_identity.st_size)
        dispatch_cli.os.utime(
            victim,
            ns=(victim_identity.st_atime_ns, victim_identity.st_mtime_ns),
        )
        mutated = True

    class MutatingStream:
        def __init__(self, stream) -> None:
            self._stream = stream

        def __enter__(self):
            self._stream.__enter__()
            return self

        def __exit__(self, *args):
            return self._stream.__exit__(*args)

        def read(self) -> bytes:
            nonlocal victim_read
            content = self._stream.read()
            victim_read = True
            if mutation_hook == "after_fd_read" and not mutated:
                mutate_same_size()
            return content

        def fileno(self) -> int:
            return self._stream.fileno()

        def seek(self, *args):
            return self._stream.seek(*args)

    def mutate_victim_after_read(descriptor, *args, **kwargs):
        stream = original_fdopen(descriptor, *args, **kwargs)
        opened = dispatch_cli.os.fstat(descriptor)
        if (
            opened.st_dev == victim_identity.st_dev
            and opened.st_ino == victim_identity.st_ino
        ):
            return MutatingStream(stream)
        return stream

    def mutate_before_final_lstat(path: Path):
        if (
            path == victim
            and victim_read
            and mutation_hook == "before_final_lstat"
            and not mutated
        ):
            mutate_same_size()
        return without_tick_discrimination(original_lstat(path))

    def stat_without_tick_discrimination(descriptor):
        return without_tick_discrimination(original_fstat(descriptor))

    monkeypatch.setattr(dispatch_cli.os, "fdopen", mutate_victim_after_read)
    monkeypatch.setattr(dispatch_cli.os, "fstat", stat_without_tick_discrimination)
    monkeypatch.setattr(Path, "lstat", mutate_before_final_lstat)

    exit_code = consumer(
        ["--repo-root", str(tmp_path), "--delivery-contract", contract_path.name]
    )

    captured = capsys.readouterr()
    assert mutated
    assert exit_code == 2
    assert captured.out == ""
    assert "bytes changed while it was read" in captured.err
    assert "WHAT:" in captured.err
    assert "WHY:" in captured.err
    assert "HOW:" in captured.err


def test_dispatch_digest_uses_validated_snapshot_after_regular_replacement(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The published digest binds the bytes dispatch validated, not a reread.

    A legitimate writer -- a formatter or hook -- replaces one already
    acquired support file while `des dispatch` is still loading later closure
    members.  That replacement is admissible: the support snapshot was
    already validated and read from its own no-follow descriptor.  The
    closure identity therefore must remain the identity of the acquired
    bytes.  Observed only through public argv and stdout.
    """
    contract_path, support_paths = _seed_supporting_contract(tmp_path)
    contract_dict = json.loads(contract_path.read_text(encoding="utf-8"))
    oracle_locator = str(contract_dict["acceptance-tests"]["locator"])
    oracle_path = tmp_path / oracle_locator.split("::", 1)[0]
    victim = support_paths[1]
    acquired_digest = "sha256:" + dispatch_cli.closure_digest(
        contract_path.read_bytes(),
        oracle_path.read_bytes(),
        oracle_locator=oracle_locator,
        supporting_files=tuple(
            (locator, (tmp_path / locator).read_bytes())
            for locator in contract_dict["acceptance-tests"]["supporting-locators"]
        ),
    )
    oracle_identity = oracle_path.lstat()
    original_fdopen = dispatch_cli.os.fdopen
    replaced = False

    def replace_victim_once_a_later_member_opens(descriptor, *args, **kwargs):
        # Every support snapshot is complete before the oracle is opened, so
        # this is the admissible post-acquisition window, not a mutation of a
        # file dispatch is still reading.
        nonlocal replaced
        opened = dispatch_cli.os.fstat(descriptor)
        if not replaced and (opened.st_dev, opened.st_ino) == (
            oracle_identity.st_dev,
            oracle_identity.st_ino,
        ):
            victim.write_bytes(b"replaced by a legitimate writer\n")
            replaced = True
        return original_fdopen(descriptor, *args, **kwargs)

    monkeypatch.setattr(
        dispatch_cli.os, "fdopen", replace_victim_once_a_later_member_opens
    )

    exit_code = dispatch_cli.main(
        ["--repo-root", str(tmp_path), "--delivery-contract", contract_path.name]
    )

    captured = capsys.readouterr()
    published = next(
        line.removeprefix("THIN-DELIVERY-CONTRACT-DIGEST: ")
        for line in captured.out.splitlines()
        if line.startswith("THIN-DELIVERY-CONTRACT-DIGEST: ")
    )
    assert replaced
    assert exit_code == 0
    assert published == acquired_digest


def test_absent_no_follow_capability_refuses_before_any_ordinary_open(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a no-follow open capability, closure acquisition refuses.

    No-follow is a capability, not a flag that silently degrades to `0`: an
    ordinary open cannot bind the validated path to the opened file, so no
    closure member may be opened at all.
    """
    contract_path, support_paths = _seed_supporting_contract(tmp_path)
    contract_dict = json.loads(contract_path.read_text(encoding="utf-8"))
    members = {
        contract_path,
        tmp_path / str(contract_dict["acceptance-tests"]["locator"]).split("::", 1)[0],
        *support_paths,
    }
    opened: list[Path] = []
    ordinary_open = dispatch_cli.os.open

    def record_open(path, flags, *args):
        opened.append(Path(path))
        return ordinary_open(path, flags, *args)

    monkeypatch.delattr(dispatch_cli.os, "O_NOFOLLOW", raising=False)
    monkeypatch.setattr(dispatch_cli.os, "open", record_open)

    exit_code = dispatch_cli.main(
        ["--repo-root", str(tmp_path), "--delivery-contract", contract_path.name]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "WHAT:" in captured.err
    assert "WHY:" in captured.err
    assert "HOW:" in captured.err
    assert not members.intersection(opened)


@pytest.mark.parametrize("consumer", [main, dispatch_cli.main])
@pytest.mark.parametrize("defect", ["missing", "symlink", "reordered"])
def test_support_defects_refuse_before_handoff(
    tmp_path: Path, capsys, consumer, defect: str
) -> None:
    contract_path, support_paths = _seed_supporting_contract(tmp_path)
    if defect == "missing":
        support_paths[0].unlink()
    elif defect == "symlink":
        support_paths[0].unlink()
        support_paths[0].symlink_to(support_paths[1])
    else:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["acceptance-tests"]["supporting-locators"].reverse()
        contract_path.write_text(json.dumps(contract), encoding="utf-8")

    exit_code = consumer(
        ["--repo-root", str(tmp_path), "--delivery-contract", contract_path.name]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "WHAT:" in captured.err
    assert "WHY:" in captured.err
    assert "HOW:" in captured.err


@pytest.mark.parametrize("mutate", ["contract", "oracle"])
def test_digest_changes_when_contract_or_oracle_bytes_mutate(
    tmp_path: Path, capsys, mutate: str
) -> None:
    contract_path = tmp_path / "delivery.json"
    contract_dict = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    contract_path.write_text(json.dumps(contract_dict), encoding="utf-8")
    oracle_path = seed_referenced_oracle(tmp_path, contract_dict)
    args = ["--repo-root", str(tmp_path), "--delivery-contract", "delivery.json"]

    main(args)
    original_digest = json.loads(capsys.readouterr().out)["digest"]

    if mutate == "contract":
        contract_dict["outcome"] = contract_dict["outcome"] + " mutated."
        contract_path.write_text(json.dumps(contract_dict), encoding="utf-8")
    else:
        oracle_path.write_bytes(oracle_path.read_bytes() + b"\n# mutated\n")

    mutated_exit = main(args)
    mutated_digest = json.loads(capsys.readouterr().out)["digest"]

    assert mutated_exit == 0
    assert original_digest != mutated_digest


def test_validator_is_a_public_des_subcommand() -> None:
    row = next(row for row in _REGISTRY if row.name == "validate-delivery-contract")

    assert row.module_path == "des.cli.validate_delivery_contract"


def test_declared_whole_suite_command_is_not_a_read_only_validation_carrier(
    tmp_path: Path, capsys
) -> None:
    """Preservation resolves CLAUDE bytes at construction, never as a CLI claim."""
    contract = tmp_path / "delivery.json"
    contract.write_bytes(EXAMPLE.read_bytes())
    seed_referenced_oracle(tmp_path, json.loads(EXAMPLE.read_text(encoding="utf-8")))
    (tmp_path / "CLAUDE.md").write_text(
        "- Run the subject's own tests: "
        "`k4-fixture-venv/bin/python manage.py test hc.api --noinput`\n",
        encoding="utf-8",
    )

    exit_code = main(
        ["--repo-root", str(tmp_path), "--delivery-contract", "delivery.json"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""


def _fake_installed_runtime(claude_dir: Path, schema: dict) -> Path:
    """A Claude-install layout carrying exactly one packaged contract schema."""
    installed = claude_dir / "lib" / "nWave" / "schemas" / SCHEMA.name
    installed.parent.mkdir(parents=True)
    installed.write_text(json.dumps(schema), encoding="utf-8")
    return installed


def test_resolver_prefers_the_installed_runtime_schema_over_the_checkout_copy(
    tmp_path: Path, monkeypatch
) -> None:
    """Version-skew incident 2026-08-20: a worktree venv's editable `des`
    validated an installed-runtime-compiled contract against the worktree's
    STALE checkout schema. The checkout copy is a build source, never the
    runtime validation source: when an installed runtime carries the schema,
    every layout must resolve THAT copy."""
    installed = _fake_installed_runtime(
        tmp_path / "claude", json.loads(SCHEMA.read_text(encoding="utf-8"))
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))

    assert resolve_delivery_contract_schema_path() == installed


def test_resolver_falls_back_to_the_checkout_schema_without_an_installed_runtime(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "no-install-here"))

    assert resolve_delivery_contract_schema_path() == SCHEMA


def test_checkout_runtime_validates_with_the_installed_schema_not_its_own(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """The discriminating direction of the same skew: the installed schema
    (here deliberately WITHOUT `dropped-citations`) must be the one that
    speaks, even though this checkout's own schema admits the property."""
    stale = json.loads(SCHEMA.read_text(encoding="utf-8"))
    del stale["properties"]["dropped-citations"]
    del stale["$defs"]["droppedCitations"]
    _fake_installed_runtime(tmp_path / "claude", stale)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))

    repo = tmp_path / "repo"
    repo.mkdir()
    contract_dict = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    contract_dict["dropped-citations"] = [
        {"citation": "orphan_symbol", "reason": "no grounded target"}
    ]
    (repo / "delivery.json").write_text(json.dumps(contract_dict), encoding="utf-8")
    seed_referenced_oracle(repo, contract_dict)

    exit_code = main(["--repo-root", str(repo), "--delivery-contract", "delivery.json"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "fails the thin-delivery-contract schema" in captured.err
    assert "dropped-citations" in captured.err

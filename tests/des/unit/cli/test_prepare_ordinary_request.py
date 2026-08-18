"""Raw-input proof for `des prepare-ordinary-request` (ADR-SSOT-002 §4d).

Drives `main()` from a genuine byte stdin stream against a real temporary
git repository that starts with no `DeliveryContract`, no oracle and no
`docs/delivery-contracts/` directory at all -- never a hand-built 14-line
fixture asserted as proof of constructor totality. Also proves the producer's
stdout is accepted by the real hook gate, and that a tampered copy is not.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys

import pytest

from des.adapters.drivers.hooks.pre_tool_use_handler import (
    _evaluate_auto_root_atd_body,
)
from des.cli import prepare_ordinary_request


_ARCH_AUTHORITY = "ARCHITECTURE-COVERED: docs/architecture/adrs/adr-1.md#decision"


def _init_repo(tmp_path) -> str:
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
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True, env=env)
    return str(root)


class _FakeStdin:
    """A genuine byte stream on `.buffer`, matching `sys.stdin`'s shape."""

    def __init__(self, seed_bytes: bytes) -> None:
        self.buffer = io.BytesIO(seed_bytes)


def _run(
    monkeypatch, capsys, *, seed_bytes: bytes, argv: list[str]
) -> tuple[int, str, str]:
    monkeypatch.setattr(sys, "stdin", _FakeStdin(seed_bytes))
    exit_code = prepare_ordinary_request.main(argv)
    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


def _base_argv(repo_root: str, **overrides: str) -> list[str]:
    argv = {
        "--size": "M",
        "--repo-root": repo_root,
        "--architecture-authority": _ARCH_AUTHORITY,
        "--delivery-route": "RED_TO_GREEN",
        "--examine": "true",
        "--independent-review": "false",
    }
    argv.update(overrides)
    result: list[str] = []
    for flag, value in argv.items():
        result += [flag, value]
    return result


class TestRawInputProducesADeterministicPreparedEnvelope:
    def test_no_contract_oracle_or_artifact_exists_before_or_after(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        root = _init_repo(tmp_path)
        contracts_dir = tmp_path / "repo" / "docs" / "delivery-contracts"
        assert not contracts_dir.exists()

        exit_code, out, _err = _run(
            monkeypatch, capsys, seed_bytes=b"Ship it.", argv=_base_argv(root)
        )

        assert exit_code == 0
        assert out.count("\n") == 13  # 14 lines, no trailing newline
        assert not contracts_dir.exists()
        top_level_entries = {entry.name for entry in (tmp_path / "repo").iterdir()}
        assert top_level_entries == {"README.md", ".git"}

    def test_same_seed_same_id_different_seed_different_id(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        root = _init_repo(tmp_path)
        _exit_a, out_a, _ = _run(
            monkeypatch, capsys, seed_bytes=b"Same seed.", argv=_base_argv(root)
        )
        _exit_b, out_b, _ = _run(
            monkeypatch, capsys, seed_bytes=b"Same seed.", argv=_base_argv(root)
        )
        _exit_c, out_c, _ = _run(
            monkeypatch, capsys, seed_bytes=b"Different seed.", argv=_base_argv(root)
        )
        assert out_a == out_b
        assert out_a != out_c

        def _delivery_id(body: str) -> str:
            for line in body.splitlines():
                if line.startswith("DELIVERY-ID: "):
                    return line
            raise AssertionError("no DELIVERY-ID line")

        assert _delivery_id(out_a) == _delivery_id(out_b)
        assert _delivery_id(out_a) != _delivery_id(out_c)

    def test_hostile_multiline_unicode_seed_roundtrips_with_no_shell_execution(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        root = _init_repo(tmp_path)
        hostile_seed = (
            'Ship "the" widget.\nSecond line with `backticks`.\n'
            "$(touch pwned) && rm -rf / ; echo *glob* — 日本語 done."
        )
        exit_code, out, _err = _run(
            monkeypatch,
            capsys,
            seed_bytes=hostile_seed.encode("utf-8"),
            argv=_base_argv(root),
        )
        assert exit_code == 0
        assert not (tmp_path / "repo" / "pwned").exists()
        lines = out.split("\n")
        assert len(lines) == 14
        outcome_value = json.loads(lines[5][len("OUTCOME: ") :])
        value_seed_value = json.loads(lines[13][len("VALUE-SEED: ") :])
        assert outcome_value == hostile_seed
        assert value_seed_value == hostile_seed
        # The JSON string literal itself carries no raw newline.
        assert "\n" not in lines[5]
        assert "\n" not in lines[13]


class TestFailClosedNeverInventsAFact:
    def test_missing_installed_schema_fails_closed(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        root = _init_repo(tmp_path)
        missing_schema = tmp_path / "missing-schema.json"
        monkeypatch.setattr(
            prepare_ordinary_request,
            "resolve_delivery_contract_schema_path",
            lambda: missing_schema,
        )

        exit_code, out, err = _run(
            monkeypatch, capsys, seed_bytes=b"seed", argv=_base_argv(root)
        )

        assert exit_code != 0
        assert out == ""
        assert "installed DeliveryContract schema is unavailable" in err
        assert "WHAT:" in err and "WHY:" in err and "HOW:" in err

    def test_mismatched_repo_root_fails_closed(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        _init_repo(tmp_path)
        subdir = tmp_path / "repo" / "sub"
        subdir.mkdir()
        exit_code, out, err = _run(
            monkeypatch,
            capsys,
            seed_bytes=b"seed",
            argv=_base_argv(str(subdir)),
        )
        assert exit_code != 0
        assert out == ""
        assert "WHAT:" in err and "WHY:" in err and "HOW:" in err

    def test_non_repo_root_fails_closed(self, tmp_path, monkeypatch, capsys) -> None:
        not_a_repo = tmp_path / "plain"
        not_a_repo.mkdir()
        exit_code, out, err = _run(
            monkeypatch,
            capsys,
            seed_bytes=b"seed",
            argv=_base_argv(str(not_a_repo)),
        )
        assert exit_code != 0
        assert out == ""
        assert "WHAT:" in err

    def test_empty_stdin_fails_closed(self, tmp_path, monkeypatch, capsys) -> None:
        root = _init_repo(tmp_path)
        exit_code, out, err = _run(
            monkeypatch, capsys, seed_bytes=b"", argv=_base_argv(root)
        )
        assert exit_code != 0
        assert out == ""
        assert "UTF-8" in err

    def test_invalid_utf8_stdin_fails_closed(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        root = _init_repo(tmp_path)
        exit_code, out, err = _run(
            monkeypatch, capsys, seed_bytes=b"\xff\xfe", argv=_base_argv(root)
        )
        assert exit_code != 0
        assert out == ""
        assert "UTF-8" in err

    @pytest.mark.parametrize(
        "override",
        [
            {"--delivery-route": "SIDEWAYS"},
            {"--examine": "yes"},
            {"--independent-review": "maybe"},
            {"--size": "S"},
            {
                "--architecture-authority": "ARCHITECTURE-NO-IMPACT: docs/architecture/adrs/adr-1.md#decision"
            },
        ],
    )
    def test_invalid_enum_flag_fails_closed(
        self, tmp_path, monkeypatch, capsys, override
    ) -> None:
        root = _init_repo(tmp_path)
        exit_code, out, err = _run(
            monkeypatch,
            capsys,
            seed_bytes=b"seed",
            argv=_base_argv(root, **override),
        )
        assert exit_code != 0
        assert out == ""
        assert err.strip() != ""

    @pytest.mark.parametrize(
        "flag", ["--budget-token-limit", "--budget-wall-clock-minutes"]
    )
    @pytest.mark.parametrize("bad_value", ["0", "-5"])
    def test_non_positive_budget_override_fails_closed(
        self, tmp_path, monkeypatch, capsys, flag, bad_value
    ) -> None:
        root = _init_repo(tmp_path)
        exit_code, out, err = _run(
            monkeypatch,
            capsys,
            seed_bytes=b"seed",
            argv=_base_argv(root) + [flag, bad_value],
        )
        assert exit_code != 0
        assert out == ""
        assert "positive" in err


class TestProducerOutputIsAcceptedByTheRealHook:
    def test_producer_stdout_is_accepted_verbatim(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        root = _init_repo(tmp_path)
        exit_code, out, _err = _run(
            monkeypatch,
            capsys,
            seed_bytes=b"Ship the real thing.",
            argv=_base_argv(root),
        )
        assert exit_code == 0
        assert _evaluate_auto_root_atd_body(out) is None

    @pytest.mark.parametrize(
        "mutate",
        [
            lambda lines: [
                line.replace("DELIVERY-ID: ", "DELIVERY-ID: auto-0000000000000000")
                if line.startswith("DELIVERY-ID: ")
                else line
                for line in lines
            ],
            lambda lines: [
                line.replace(
                    "CONTRACT-LOCATOR: ",
                    "CONTRACT-LOCATOR: docs/delivery-contracts/auto-tampered.json",
                )
                if line.startswith("CONTRACT-LOCATOR: ")
                else line
                for line in lines
            ],
            lambda lines: [
                line.replace('"Ship the real thing."', '"A different outcome."')
                if line.startswith("OUTCOME: ")
                else line
                for line in lines
            ],
            lambda lines: [
                line.replace('"Ship the real thing."', '"A different seed."')
                if line.startswith("VALUE-SEED: ")
                else line
                for line in lines
            ],
        ],
        ids=["tampered_id", "tampered_locator", "tampered_outcome", "tampered_seed"],
    )
    def test_tampered_producer_stdout_is_rejected_by_the_hook(
        self, tmp_path, monkeypatch, capsys, mutate
    ) -> None:
        root = _init_repo(tmp_path)
        exit_code, out, _err = _run(
            monkeypatch,
            capsys,
            seed_bytes=b"Ship the real thing.",
            argv=_base_argv(root),
        )
        assert exit_code == 0
        tampered = "\n".join(mutate(out.split("\n")))
        assert _evaluate_auto_root_atd_body(tampered) is not None


class TestExactlyOnceProducerPerDeliveryId:
    """Run 4 evidence: root re-ran the entire producer->crafter cycle on
    EVERY crafter INDETERMINATE, burning the producer 4x for one DeliveryId.
    ADR-SSOT-002 SS4c/4d: one DeliveryContract is written exactly once by
    ATD for a given (deterministic) DeliveryId. Enforced here, at the
    cheapest possible point, by refusing a second producer run once that
    contract exists on disk -- never by tracking a call count."""

    @staticmethod
    def _locator_from(body: str) -> str:
        for line in body.splitlines():
            if line.startswith("CONTRACT-LOCATOR: "):
                return line[len("CONTRACT-LOCATOR: ") :]
        raise AssertionError("no CONTRACT-LOCATOR line")

    def test_second_run_for_same_seed_after_contract_exists_is_blocked(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        root = _init_repo(tmp_path)
        _exit_a, out_a, _err_a = _run(
            monkeypatch, capsys, seed_bytes=b"Ship it.", argv=_base_argv(root)
        )
        assert _exit_a == 0
        locator = self._locator_from(out_a)
        contract_path = tmp_path / "repo" / locator
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        contract_path.write_text("{}", encoding="utf-8")

        exit_code, out, err = _run(
            monkeypatch, capsys, seed_bytes=b"Ship it.", argv=_base_argv(root)
        )

        assert exit_code == 2
        assert out == ""
        assert "WHAT:" in err and "WHY:" in err and "HOW:" in err
        assert locator in err
        assert "REVISE-CONTRACT" in err
        assert "CITATION" in err

    def test_a_different_seed_is_unaffected_by_an_unrelated_existing_contract(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        root = _init_repo(tmp_path)
        _exit_a, out_a, _err_a = _run(
            monkeypatch, capsys, seed_bytes=b"Ship it.", argv=_base_argv(root)
        )
        locator = self._locator_from(out_a)
        contract_path = tmp_path / "repo" / locator
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        contract_path.write_text("{}", encoding="utf-8")

        exit_code, out, _err = _run(
            monkeypatch,
            capsys,
            seed_bytes=b"A wholly different request.",
            argv=_base_argv(root),
        )

        assert exit_code == 0
        assert out != ""
        assert self._locator_from(out) != locator

    def test_a_non_file_at_the_contract_locator_still_blocks(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        """Fails closed on ANY pre-existing thing at that path -- a
        directory left behind by a crashed run is not proof of absence."""
        root = _init_repo(tmp_path)
        _exit_a, out_a, _err_a = _run(
            monkeypatch, capsys, seed_bytes=b"Ship it.", argv=_base_argv(root)
        )
        locator = self._locator_from(out_a)
        contract_path = tmp_path / "repo" / locator
        contract_path.mkdir(parents=True)

        exit_code, _out, err = _run(
            monkeypatch, capsys, seed_bytes=b"Ship it.", argv=_base_argv(root)
        )

        assert exit_code == 2
        assert "WHAT:" in err


class TestInvocationIsHostNeutral:
    @pytest.mark.parametrize(
        "env_overrides",
        [
            {},
            {"CLAUDE_CONFIG_DIR": "/fake/claude"},
            {"CODEX_HOME": "/fake/codex"},
        ],
    )
    def test_output_is_unaffected_by_host_specific_environment(
        self, tmp_path, monkeypatch, capsys, env_overrides
    ) -> None:
        root = _init_repo(tmp_path)
        for key, value in env_overrides.items():
            monkeypatch.setenv(key, value)
        exit_code, out, _err = _run(
            monkeypatch, capsys, seed_bytes=b"Host neutral seed.", argv=_base_argv(root)
        )
        assert exit_code == 0
        assert "DELIVERY-ID: " in out

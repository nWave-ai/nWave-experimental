"""Regression tests for the public ``nwave-ai`` discovery surface."""

from __future__ import annotations

import json
import os
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from nwave_ai.cli import main


def _invoke(args: list[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    with (
        patch("sys.argv", ["nwave-ai", *args]),
        patch("sys.stdout", out),
        patch("sys.stderr", err),
    ):
        code = main()
    return code, out.getvalue(), err.getvalue()


def test_help_text_omits_retired_feature_delta_commands() -> None:
    """The direct cutover must not advertise the retired carrier family."""
    code, stdout, _ = _invoke(["--help"])
    assert code == 0
    for command in (
        "sync",
        "validate-feature-delta",
        "extract-gherkin",
        "migrate-feature",
    ):
        assert command not in stdout


@pytest.mark.parametrize(
    "command",
    ["sync", "validate-feature-delta", "extract-gherkin", "migrate-feature"],
)
def test_retired_feature_delta_commands_are_not_dispatched(command: str) -> None:
    code, _, stderr = _invoke([command])
    assert code == 1
    assert f"Unknown command: {command}" in stderr


@pytest.mark.parametrize(
    ("argv", "expect_zero"),
    [
        (["project", "enable", "--help"], True),
        (["project", "enable", "-h"], True),
        (["project", "disable", "--help"], True),
        (["project", "disable", "-h"], True),
        (["project", "--help"], True),
        (["project", "-h"], True),
        (["project"], False),
        (["project", "bogus"], False),
        (["project", "enable", "--bogus"], False),
        (["project", "enable", "extra"], False),
        (["project", "disable", "extra"], False),
        (["project", "enable", "--yes", "extra"], False),
    ],
)
def test_project_help_and_malformed_args_never_mutate_cwd(
    argv: list[str], expect_zero: bool, tmp_path, monkeypatch
) -> None:
    """`project enable|disable --help`/`-h` and any unknown option or extra
    positional must print usage and never create `.nwave/` or `.gitignore`
    in cwd -- only an exact `enable`/`disable` action (with optional
    `--yes`) may write, and it must never silently swallow trailing args."""
    monkeypatch.chdir(tmp_path)
    code, stdout, stderr = _invoke(argv)
    if expect_zero:
        assert code == 0
        assert "Usage: nwave-ai project" in stdout
    else:
        assert code != 0
        assert "Usage: nwave-ai project" in stderr
    assert not (tmp_path / ".nwave").exists()
    assert not (tmp_path / ".gitignore").exists()


_JSON_LEAF = st.none() | st.booleans() | st.integers() | st.text(max_size=24)
_JSON_VALUE = st.recursive(
    _JSON_LEAF,
    lambda children: (
        st.lists(children, max_size=3)
        | st.dictionaries(st.text(min_size=1, max_size=12), children, max_size=3)
    ),
    max_leaves=12,
)
_UNRELATED_JSON_MEMBERS = st.dictionaries(
    st.text(min_size=1, max_size=12).filter(lambda key: key != "enabled"),
    _JSON_VALUE,
    max_size=5,
)


def _assert_refusal_preserves_previous_bytes(
    argv: list[str], canonical_config: Path, legacy_marker: Path
) -> None:
    previous_canonical_bytes = canonical_config.read_bytes()
    previous_legacy_bytes = legacy_marker.read_bytes()
    code, stdout, stderr = _invoke(argv)
    assert code != 0
    assert stdout == ""
    for part in ("WHAT", "WHY", "HOW"):
        assert part in stderr
    assert canonical_config.read_bytes() == previous_canonical_bytes
    assert legacy_marker.read_bytes() == previous_legacy_bytes


@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(unrelated_members=_UNRELATED_JSON_MEMBERS)
def test_project_activation_writer_is_canonical_atomic_and_status_observed(
    tmp_path, monkeypatch, unrelated_members: dict[str, object]
) -> None:
    """Explicit consent has one atomic writer with a public status proof."""
    case_root = tmp_path / os.urandom(8).hex()
    case_root.mkdir()

    for action, expected_enabled, status_word in (
        (["project", "enable", "--yes"], True, "active"),
        (["project", "disable"], False, "inactive"),
    ):
        action_name = "enable" if expected_enabled else "disable"
        absent_root = case_root / f"absent-{action_name}-canonical-config"
        absent_root.mkdir()
        monkeypatch.chdir(absent_root)
        absent_code, _, _ = _invoke(action)
        absent_config = absent_root / ".nwave" / "config.json"
        assert absent_code == 0
        assert json.loads(absent_config.read_text(encoding="utf-8")) == {
            "enabled": expected_enabled
        }
        assert not (absent_root / ".nwave" / "local-config.json").exists()
        status_code, status_stdout, _ = _invoke(["status"])
        assert status_code == 0
        assert f"This project is {status_word}." in status_stdout

        project_root = case_root / f"preserved-members-{action_name}"
        nwave_directory = project_root / ".nwave"
        nwave_directory.mkdir(parents=True)
        canonical_config = nwave_directory / "config.json"
        canonical_config.write_text(json.dumps(unrelated_members), encoding="utf-8")
        legacy_marker = nwave_directory / "local-config.json"
        legacy_bytes = b'{"enabled_for_repo": true, "legacy": "preserve"}\n'
        legacy_marker.write_bytes(legacy_bytes)
        monkeypatch.chdir(project_root)

        original_replace = os.replace
        with patch("os.replace", wraps=original_replace) as replace:
            action_code, _, _ = _invoke(action)
        assert action_code == 0
        canonical_replacements = [
            call.args
            for call in replace.call_args_list
            if len(call.args) >= 2 and Path(call.args[1]) == canonical_config
        ]
        assert len(canonical_replacements) == 1
        temporary_path, replaced_path = canonical_replacements[0]
        assert Path(temporary_path).parent == canonical_config.parent
        assert Path(temporary_path) != canonical_config
        assert Path(replaced_path) == canonical_config
        assert json.loads(canonical_config.read_text(encoding="utf-8")) == {
            **unrelated_members,
            "enabled": expected_enabled,
        }
        assert legacy_marker.read_bytes() == legacy_bytes
        status_code, status_stdout, _ = _invoke(["status"])
        assert status_code == 0
        assert f"This project is {status_word}." in status_stdout

        canonical_config.write_bytes(b'{"enabled":')
        _assert_refusal_preserves_previous_bytes(
            action, canonical_config, legacy_marker
        )

        canonical_config.write_text(json.dumps(unrelated_members), encoding="utf-8")
        original_write_text = Path.write_text

        def fail_temporary_write(
            path: Path,
            *args,
            _canonical_config=canonical_config,
            _original_write_text=original_write_text,
            **kwargs,
        ):
            if path.parent == _canonical_config.parent and path != _canonical_config:
                raise PermissionError("temporary write permission denied")
            return _original_write_text(path, *args, **kwargs)

        with patch.object(Path, "write_text", new=fail_temporary_write):
            _assert_refusal_preserves_previous_bytes(
                action, canonical_config, legacy_marker
            )

        original_read_text = Path.read_text

        def fail_temporary_read(
            path: Path,
            *args,
            _canonical_config=canonical_config,
            _original_read_text=original_read_text,
            **kwargs,
        ):
            if path.parent == _canonical_config.parent and path != _canonical_config:
                raise OSError("temporary read failure")
            return _original_read_text(path, *args, **kwargs)

        with patch.object(Path, "read_text", new=fail_temporary_read):
            _assert_refusal_preserves_previous_bytes(
                action, canonical_config, legacy_marker
            )

        with patch("os.replace", side_effect=OSError("replace failure")):
            _assert_refusal_preserves_previous_bytes(
                action, canonical_config, legacy_marker
            )

        with patch("os.replace", side_effect=InterruptedError("before replace")):
            _assert_refusal_preserves_previous_bytes(
                action, canonical_config, legacy_marker
            )

        completed_document = json.dumps(
            {**unrelated_members, "enabled": expected_enabled}
        ).encode("utf-8")

        def replace_then_interrupt(
            source, destination, _original_replace=original_replace
        ) -> None:
            _original_replace(source, destination)
            raise InterruptedError("after replace")

        with patch("os.replace", side_effect=replace_then_interrupt):
            interrupted_code, interrupted_stdout, interrupted_stderr = _invoke(action)
        assert interrupted_code != 0
        assert interrupted_stdout == ""
        for part in ("WHAT", "WHY", "HOW"):
            assert part in interrupted_stderr
        assert canonical_config.read_bytes() == completed_document
        assert legacy_marker.read_bytes() == legacy_bytes
        status_code, status_stdout, _ = _invoke(["status"])
        assert status_code == 0
        assert f"This project is {status_word}." in status_stdout

        externally_replaced_config = json.dumps(
            {
                **unrelated_members,
                "enabled": not expected_enabled,
                "external": "race",
            }
        ).encode("utf-8")

        def replace_then_externally_change_state(
            source,
            destination,
            _original_replace=original_replace,
            _externally_replaced_config=externally_replaced_config,
        ) -> None:
            _original_replace(source, destination)
            Path(destination).write_bytes(_externally_replaced_config)

        with patch("os.replace", side_effect=replace_then_externally_change_state):
            mismatch_code, mismatch_stdout, mismatch_stderr = _invoke(action)
        assert mismatch_code != 0
        assert mismatch_stdout == ""
        for part in ("WHAT", "WHY", "HOW"):
            assert part in mismatch_stderr
        assert canonical_config.read_bytes() == externally_replaced_config
        assert legacy_marker.read_bytes() == legacy_bytes

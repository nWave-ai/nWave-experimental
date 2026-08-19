"""Unit tests for `missing_verification_paths` (K4 Run 9 admission).

Run 9 repro: a `manage.py test` command citing the wrong Django app-label
prefix (`api.tests.test_x` instead of the real `hc.api.tests.test_x`) must
be caught statically; the SAME command citing the contract's own oracle
locator, or a real existing test module, must not.
"""

from __future__ import annotations

from pathlib import Path

from des.domain.verification_command_resolver import (
    missing_verification_paths,
    resolve_existing_oracle_files,
)


def _seed_test_module(root: Path, relative: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# test module\n", encoding="utf-8")


def _contract(commands: list[dict], oracle_locator: str = "") -> dict:
    return {
        "acceptance-tests": {"locator": oracle_locator},
        "verification-scope": {"commands": commands},
    }


def _django_command(*labels: str) -> dict:
    return {
        "executable": {"kind": "repository", "path": "manage.py"},
        "arguments": ["test", *labels],
    }


def test_wrong_app_label_prefix_is_reported_missing(tmp_path: Path) -> None:
    """Run 9 repro: `api.tests.test_update_check` -- missing the real `hc.`
    app-label prefix -- must be caught even though `hc/api/tests/
    test_update_check.py` exists on disk under the CORRECT dotted path."""
    _seed_test_module(tmp_path, "hc/api/tests/test_update_check.py")
    contract = _contract([_django_command("api.tests.test_update_check")])

    assert missing_verification_paths(tmp_path, contract) == [
        "api.tests.test_update_check"
    ]


def test_correct_dotted_label_resolving_to_a_real_file_is_accepted(
    tmp_path: Path,
) -> None:
    _seed_test_module(tmp_path, "hc/api/tests/test_update_check.py")
    contract = _contract([_django_command("hc.api.tests.test_update_check")])

    assert missing_verification_paths(tmp_path, contract) == []


def test_multiple_labels_in_one_command_report_only_the_missing_ones(
    tmp_path: Path,
) -> None:
    _seed_test_module(tmp_path, "hc/api/tests/test_update_check.py")
    _seed_test_module(tmp_path, "hc/api/tests/test_create_check.py")
    contract = _contract(
        [
            _django_command(
                "hc.api.tests.test_update_check",
                "hc.api.tests.test_create_check",
                "api.tests.test_flip_model",
            )
        ]
    )

    assert missing_verification_paths(tmp_path, contract) == [
        "api.tests.test_flip_model"
    ]


def test_label_matching_the_contracts_own_oracle_locator_is_never_missing(
    tmp_path: Path,
) -> None:
    """A verification command may cite the SAME oracle file this contract's
    ATD authored -- it is not "missing" merely because no test module
    existed before this delivery. No file is seeded on disk here."""
    contract = _contract(
        [_django_command("hc.api.tests.test_maintenance_windows")],
        oracle_locator="hc/api/tests/test_maintenance_windows.py",
    )

    assert missing_verification_paths(tmp_path, contract) == []


def test_pytest_style_path_is_checked_the_same_way(tmp_path: Path) -> None:
    _seed_test_module(tmp_path, "tests/api/test_update_check.py")
    contract = _contract(
        [
            {
                "executable": {"kind": "toolchain", "name": "pytest"},
                "arguments": [
                    "tests/api/test_update_check.py",
                    "tests/api/test_missing.py",
                ],
            }
        ]
    )

    assert missing_verification_paths(tmp_path, contract) == [
        "tests/api/test_missing.py"
    ]


def test_python_dash_m_pytest_shape_is_recognized(tmp_path: Path) -> None:
    """This repo's own checked-in contracts run pytest as `<python> -m
    pytest ...`, never a standalone `pytest` executable."""
    _seed_test_module(tmp_path, "tests/build/test_thin_delivery_contract_schema.py")
    contract = _contract(
        [
            {
                "executable": {"kind": "repository", "path": ".venv/bin/python"},
                "arguments": [
                    "-m",
                    "pytest",
                    "-q",
                    "tests/build/test_thin_delivery_contract_schema.py",
                    "tests/build/test_missing_module.py",
                ],
            }
        ]
    )

    assert missing_verification_paths(tmp_path, contract) == [
        "tests/build/test_missing_module.py"
    ]


def test_pytest_node_id_suffix_checks_only_the_file_part(tmp_path: Path) -> None:
    _seed_test_module(tmp_path, "tests/api/test_update_check.py")
    contract = _contract(
        [
            {
                "executable": {"kind": "toolchain", "name": "pytest"},
                "arguments": ["tests/api/test_update_check.py::TestCase::test_it"],
            }
        ]
    )

    assert missing_verification_paths(tmp_path, contract) == []


def test_non_test_command_is_never_flagged(tmp_path: Path) -> None:
    contract = _contract(
        [
            {
                "executable": {"kind": "repository", "path": ".venv/bin/ruff"},
                "arguments": ["check", "."],
            }
        ]
    )

    assert missing_verification_paths(tmp_path, contract) == []


def test_resolve_existing_oracle_files_includes_locator_and_verification_labels(
    tmp_path: Path,
) -> None:
    _seed_test_module(tmp_path, "hc/api/tests/test_update_check.py")
    _seed_test_module(tmp_path, "hc/api/tests/test_create_check.py")
    contract = _contract(
        [
            _django_command(
                "hc.api.tests.test_update_check", "hc.api.tests.test_create_check"
            )
        ],
        oracle_locator="hc/api/tests/test_update_check.py",
    )

    resolved = {p.as_posix() for p in resolve_existing_oracle_files(tmp_path, contract)}

    assert resolved == {
        (tmp_path / "hc/api/tests/test_update_check.py").as_posix(),
        (tmp_path / "hc/api/tests/test_create_check.py").as_posix(),
    }


def test_resolve_existing_oracle_files_skips_a_missing_path(tmp_path: Path) -> None:
    contract = _contract(
        [_django_command("hc.api.tests.test_missing")],
        oracle_locator="hc/api/tests/test_missing_oracle.py",
    )

    assert resolve_existing_oracle_files(tmp_path, contract) == []

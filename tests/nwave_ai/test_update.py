"""Public acceptance oracle for ``nwave-ai update --check``.

The CLI is the driving port.  PyPI is the only nondeterministic external
dependency and is substituted at the stdlib HTTP boundary; the installed
version still travels through the product's existing lazy identity projection.
"""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from nwave_ai.cli import main

from scripts.shared.version import ProductVersion


class _PyPIResponse:
    """Minimal context-managed response carrying a controlled PyPI document."""

    def __init__(self, document: object) -> None:
        self._body = json.dumps(document).encode("utf-8")

    def __enter__(self) -> _PyPIResponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def _invoke_check(
    monkeypatch,
    tmp_path: Path,
    *,
    urlopen,
) -> tuple[int, str, str, list[Path]]:
    """Drive the public command and retain its observable working-tree delta."""
    monkeypatch.chdir(tmp_path)
    before = sorted(tmp_path.rglob("*"))
    current_version = ProductVersion.from_text("1.4.0")

    with (
        patch(
            "scripts.shared.version.resolve_product_version",
            return_value=current_version,
        ) as resolve_product_version,
        patch("urllib.request.urlopen", side_effect=urlopen),
        patch(
            "nwave_ai.cli._resolve_installer",
            side_effect=AssertionError("--check must not select a package manager"),
        ),
        patch(
            "nwave_ai.cli._run_script",
            side_effect=AssertionError("--check must not run an installer script"),
        ),
        patch(
            "subprocess.run",
            side_effect=AssertionError("--check must not replace packages"),
        ),
        patch("sys.argv", ["nwave-ai", "update", "--check"]),
        patch("sys.stdout", new_callable=io.StringIO) as stdout,
        patch("sys.stderr", new_callable=io.StringIO) as stderr,
    ):
        exit_code = main()

    assert resolve_product_version.call_count == 1, (
        "WHAT: update checking did not resolve the installed version through the "
        "existing product-identity projection exactly once. "
        "WHY: current-version ownership must stay centralized and unambiguous. "
        "HOW: obtain the current version only via `nwave_ai.__version__`."
    )
    return exit_code, stdout.getvalue(), stderr.getvalue(), before


def test_update_check_reports_the_greatest_eligible_stable_public_release(
    monkeypatch, tmp_path: Path
) -> None:
    """A user sees the installed version and the greatest eligible PyPI release."""
    observed_requests: list[tuple[str, float]] = []

    def pypi(url: str, *, timeout: float) -> _PyPIResponse:
        observed_requests.append((url, timeout))
        return _PyPIResponse(
            {
                "releases": {
                    "2.8.0": [{"yanked": False}],
                    "2.8.1+local": [{"yanked": False}],
                    "2.8.2rc1": [{"yanked": False}],
                    "2.8.3.dev1": [{"yanked": False}],
                    "2.9.0": [{"yanked": True}],
                    "3.0.0": [],
                    "not-a-version": [{"yanked": False}],
                }
            }
        )

    exit_code, stdout, stderr, before = _invoke_check(
        monkeypatch, tmp_path, urlopen=pypi
    )

    assert exit_code == 0, (
        "WHAT: update checking did not complete successfully. "
        "WHY: a user cannot learn the latest stable public release. "
        "HOW: make `nwave-ai update --check` report a discovered eligible release."
    )
    assert "1.4.0" in stdout and "2.8.0" in stdout, (
        "WHAT: the check did not report both installed and latest eligible versions. "
        "WHY: the update decision needs the current exactly-one-owner projection "
        "and the greatest stable public PyPI release. "
        "HOW: report 1.4.0 and select 2.8.0 after excluding local, prerelease, "
        "development, yanked, fileless, and malformed candidates."
    )
    assert "update-available" in stdout, (
        "WHAT: the check did not show that an update is available. "
        "WHY: a user must be able to distinguish an available newer public release "
        "from a version-only report. "
        "HOW: emit the `update-available` state when the eligible discovered release "
        "exceeds the installed version."
    )
    assert stderr == "", (
        "WHAT: a successful update check wrote a refusal. "
        "WHY: an eligible public release was available. "
        "HOW: reserve stderr and exit 1 for discovery refusals."
    )
    assert observed_requests == [("https://pypi.org/pypi/nwave-ai/json", 5.0)], (
        "WHAT: release discovery did not make exactly the bounded PyPI request. "
        "WHY: the public check has a fixed five-second stdlib HTTP contract. "
        "HOW: request the nwave-ai PyPI JSON endpoint once with timeout_seconds=5.0."
    )
    assert sorted(tmp_path.rglob("*")) == before, (
        "WHAT: update checking changed the working tree. "
        "WHY: `--check` is observation-only and must not write artifacts. "
        "HOW: keep replacement, synchronization, migration, and artifact writes "
        "outside the check dispatch path."
    )


def test_update_check_refuses_when_release_metadata_cannot_yield_a_release(
    monkeypatch, tmp_path: Path
) -> None:
    """Unavailable, malformed, and all-ineligible discovery each fail loudly."""
    cases = (
        OSError("network unavailable"),
        _PyPIResponse({"releases": []}),
        _PyPIResponse(
            {
                "releases": {
                    "3.0.0rc1": [{"yanked": False}],
                    "3.0.0+local": [{"yanked": False}],
                    "3.0.0": [{"yanked": True}],
                    "unparseable": [{"yanked": False}],
                }
            }
        ),
    )

    for response in cases:

        def pypi(_url: str, *, timeout: float, result=response) -> _PyPIResponse:
            assert timeout == 5.0
            if isinstance(result, OSError):
                raise result
            return result

        exit_code, stdout, stderr, before = _invoke_check(
            monkeypatch, tmp_path, urlopen=pypi
        )

        assert exit_code == 1, (
            "WHAT: undiscoverable release metadata did not refuse with exit 1. "
            "WHY: the command must never invent a latest release. "
            "HOW: translate unavailable, malformed, and all-ineligible metadata "
            "into the discovery refusal."
        )
        assert stdout == "", (
            "WHAT: a failed update discovery reported a release. "
            "WHY: no eligible latest stable public release was established. "
            "HOW: emit the WHAT/WHY/HOW refusal only on discovery failure."
        )
        assert all(marker in stderr for marker in ("WHAT:", "WHY:", "HOW:")), (
            "WHAT: discovery failure was not explained as a WHAT/WHY/HOW refusal. "
            "WHY: users need an actionable reason instead of a crash or silence. "
            "HOW: render the existing discovery refusal on stderr."
        )
        assert sorted(tmp_path.rglob("*")) == before, (
            "WHAT: a failed update check changed the working tree. "
            "WHY: refusal is also read-only. "
            "HOW: do not reach any write, migration, synchronization, or package "
            "replacement path while checking."
        )


def _newer_release() -> _PyPIResponse:
    """Return one controlled public release newer than the installed owner."""
    return _PyPIResponse({"releases": {"2.0.0": [{"yanked": False}]}})


def _owned_console(tmp_path: Path) -> Path:
    """Create the owned interpreter and its public console sibling fixture."""
    interpreter = tmp_path / "owned-environment" / "bin" / "python"
    executable = interpreter.with_name("nwave-ai")
    interpreter.parent.mkdir(parents=True, exist_ok=True)
    interpreter.write_text("", encoding="utf-8")
    executable.write_text("", encoding="utf-8")
    executable.chmod(0o755)
    return interpreter


def _drive_apply(
    monkeypatch,
    tmp_path: Path,
    *,
    process_results: list[subprocess.CompletedProcess[str]],
    release: _PyPIResponse | None = None,
) -> tuple[int, str, str, list[list[str]], Path, Path]:
    """Drive the public apply command and retain every real process argv."""
    root = tmp_path / "migration-root"
    root.mkdir(exist_ok=True)
    interpreter = _owned_console(tmp_path)
    observed_argv: list[list[str]] = []
    results = iter(process_results)

    def pypi(_url: str, *, timeout: float) -> _PyPIResponse:
        assert timeout == 5.0
        return release if release is not None else _newer_release()

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        observed_argv.append(argv)
        return next(results)

    # The established explicit override is ownership evidence; it avoids any
    # PATH choice and keeps this public CLI test independent of host tooling.
    monkeypatch.setenv("NWAVE_INSTALLER", "uv")
    with (
        patch("sys.executable", str(interpreter)),
        patch(
            "scripts.shared.version.resolve_product_version",
            return_value=ProductVersion.from_text("1.4.0"),
        ),
        patch("urllib.request.urlopen", side_effect=pypi),
        patch("subprocess.run", side_effect=run),
        patch("sys.argv", ["nwave-ai", "update", "--yes", "--root", str(root)]),
        patch("sys.stdout", new_callable=io.StringIO) as stdout,
        patch("sys.stderr", new_callable=io.StringIO) as stderr,
    ):
        exit_code = main()

    return (
        exit_code,
        stdout.getvalue(),
        stderr.getvalue(),
        observed_argv,
        root,
        interpreter,
    )


def test_update_apply_treats_a_non_newer_release_as_a_noop(
    monkeypatch, tmp_path: Path
) -> None:
    """A known owner does not replace when discovery is not newer than current."""
    exit_code, stdout, stderr, observed_argv, _root, _interpreter = _drive_apply(
        monkeypatch,
        tmp_path,
        process_results=[],
        release=_PyPIResponse({"releases": {"1.4.0": [{"yanked": False}]}}),
    )

    assert exit_code == 0 and "up-to-date" in stdout and stderr == "", (
        "WHAT: a discovered release equal to the installed version was not a clean no-op. "
        "WHY: replacement is authorized only for a strictly newer stable public release. "
        "HOW: report up-to-date and return success without entering the mutation stages."
    )
    assert observed_argv == [], (
        "WHAT: a non-newer release launched an update process. "
        "WHY: no replacement, proof, synchronization, or migration is needed for an up-to-date owner. "
        "HOW: stop after parsed version comparison when latest is less than or equal to current."
    )


def test_update_apply_replaces_proves_synchronizes_then_migrates_through_public_cli(
    monkeypatch, tmp_path: Path
) -> None:
    """A newer owned release completes the public replacement-to-migration journey."""
    exit_code, stdout, stderr, observed_argv, root, interpreter = _drive_apply(
        monkeypatch,
        tmp_path,
        process_results=[
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="nwave-ai 2.0.0\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        ],
    )

    owned_console = interpreter.with_name("nwave-ai")
    assert exit_code == 0, (
        "WHAT: the owned newer release did not complete the update journey. "
        "WHY: replacement, proof, framework synchronization, and artifact migration "
        "are one operator-requested value. "
        "HOW: complete every named stage after proving the owned executable is 2.0.0."
    )
    assert all(
        stage in stdout
        for stage in (
            "replace-package",
            "verify-executable",
            "synchronize-framework",
            "migrate-artifacts",
        )
    ), (
        "WHAT: successful update output omitted one or more completed stages. "
        "WHY: operators need the ordered public record of the work performed. "
        "HOW: render each successful stage name in the completion result."
    )
    assert "2.0.0" in stdout and stderr == "", (
        "WHAT: the successful update did not report the exact discovered version cleanly. "
        "WHY: a generic success cannot establish which release was installed. "
        "HOW: render version 2.0.0 on stdout and reserve stderr for refusals."
    )
    assert observed_argv == [
        ["uv", "tool", "install", "--reinstall", "nwave-ai==2.0.0"],
        [str(owned_console), "--version"],
        [str(owned_console), "install", "--yes"],
        ["des", "update", "--apply", "--root", str(root)],
    ], (
        "WHAT: update stages did not use the owner-bound commands in their required order. "
        "WHY: PATH or stale-import execution can prove and synchronize a different install, "
        "and the migration root must not leak into framework synchronization. "
        "HOW: replace via uv, prove and synchronize with the owned nwave-ai sibling, "
        "then invoke des update --apply with root only on that final argv."
    )


def test_update_apply_stops_at_the_first_failed_named_stage(
    monkeypatch, tmp_path: Path
) -> None:
    """Each process-stage refusal suppresses every later public side effect."""
    cases = (
        (
            "replace-package",
            [
                subprocess.CompletedProcess(
                    [], 9, stdout="", stderr="replacement failed"
                )
            ],
            "exit 9",
        ),
        (
            "verify-executable",
            [
                subprocess.CompletedProcess([], 0, stdout="", stderr=""),
                subprocess.CompletedProcess([], 7, stdout="", stderr="proof failed"),
            ],
            "exit 7",
        ),
        (
            "verify-executable",
            [
                subprocess.CompletedProcess([], 0, stdout="", stderr=""),
                subprocess.CompletedProcess(
                    [], 0, stdout="nwave-ai 2.0.1\n", stderr=""
                ),
            ],
            "2.0.1",
        ),
        (
            "synchronize-framework",
            [
                subprocess.CompletedProcess([], 0, stdout="", stderr=""),
                subprocess.CompletedProcess(
                    [], 0, stdout="nwave-ai 2.0.0\n", stderr=""
                ),
                subprocess.CompletedProcess([], 4, stdout="", stderr="sync failed"),
            ],
            "exit 4",
        ),
        (
            "migrate-artifacts",
            [
                subprocess.CompletedProcess([], 0, stdout="", stderr=""),
                subprocess.CompletedProcess(
                    [], 0, stdout="nwave-ai 2.0.0\n", stderr=""
                ),
                subprocess.CompletedProcess([], 0, stdout="", stderr=""),
                subprocess.CompletedProcess(
                    [], 5, stdout="", stderr="migration failed"
                ),
            ],
            "exit 5",
        ),
    )

    for stage, results, expected_cause in cases:
        exit_code, stdout, stderr, observed_argv, root, interpreter = _drive_apply(
            monkeypatch, tmp_path, process_results=results
        )
        failure_text = stdout + stderr
        owned_console = interpreter.with_name("nwave-ai")
        replacement = ["uv", "tool", "install", "--reinstall", "nwave-ai==2.0.0"]
        proof = [str(owned_console), "--version"]
        synchronization = [str(owned_console), "install", "--yes"]
        migration = ["des", "update", "--apply", "--root", str(root)]
        expected_argv_prefix = (
            [replacement]
            if stage == "replace-package"
            else [replacement, proof]
            if stage == "verify-executable"
            else [replacement, proof, synchronization]
            if stage == "synchronize-framework"
            else [replacement, proof, synchronization, migration]
        )
        command = expected_argv_prefix[-1]

        assert exit_code != 0 and stage in failure_text, (
            "WHAT: a failed update stage did not produce a non-success, stage-named refusal. "
            "WHY: an operator must know the exact stopping point and cannot treat partial "
            "replacement as a completed update. "
            f"HOW: translate this failure to a `{stage}` refusal with its argv owner and cause."
        )
        assert " ".join(command) in failure_text and expected_cause in failure_text, (
            "WHAT: a failed update stage did not bind its actionable command and cause "
            "to the public refusal. "
            "WHY: the operator needs both the exact owner-bound command and the observed "
            "failure to repair a partial update safely. "
            f"HOW: include `{' '.join(command)}` and `{expected_cause}` in the "
            f"`{stage}` refusal."
        )
        assert observed_argv == expected_argv_prefix, (
            "WHAT: update process argv did not stop at the exact failed-stage prefix. "
            "WHY: synchronization and migration are unsafe without the preceding proof and "
            "their effects must never be claimed after a refusal. "
            "HOW: retain the owner-bound argv through the first non-zero or version-mismatch "
            "result and run no later stage."
        )
        if stage != "migrate-artifacts":
            assert [
                "des",
                "update",
                "--apply",
                "--root",
                str(root),
            ] not in observed_argv, (
                "WHAT: artifact migration ran despite an earlier update-stage failure. "
                "WHY: the migration root may change only after replacement, exact proof, and "
                "framework synchronization have succeeded. "
                "HOW: do not construct or execute the des migration argv after a refusal."
            )


def test_update_apply_refuses_unknown_owner_and_non_newer_release_before_processes(
    monkeypatch, tmp_path: Path
) -> None:
    """Ownership and version preconditions cannot trigger a mutating stage."""
    interpreter = _owned_console(tmp_path)
    root = tmp_path / "migration-root"
    root.mkdir()
    observed_argv: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        observed_argv.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.delenv("NWAVE_INSTALLER", raising=False)
    with (
        patch("sys.executable", str(interpreter)),
        patch(
            "scripts.shared.version.resolve_product_version",
            return_value=ProductVersion.from_text("1.4.0"),
        ),
        patch("urllib.request.urlopen", return_value=_newer_release()),
        patch("subprocess.run", side_effect=run),
        patch("sys.argv", ["nwave-ai", "update", "--yes", "--root", str(root)]),
        patch("sys.stdout", new_callable=io.StringIO) as stdout,
        patch("sys.stderr", new_callable=io.StringIO) as stderr,
    ):
        exit_code = main()

    assert (
        exit_code != 0 and "owner" in (stdout.getvalue() + stderr.getvalue()).lower()
    ), (
        "WHAT: unknown installation ownership was not refused explicitly. "
        "WHY: choosing an installer from PATH could replace a package other than the running one. "
        "HOW: refuse before replacement unless the running interpreter has a detected owner."
    )
    assert observed_argv == [], (
        "WHAT: unknown ownership launched an update process. "
        "WHY: ownership is a precondition for every mutating stage. "
        "HOW: return the ownership refusal before constructing replacement, proof, sync, or migration argv."
    )


def test_update_apply_refuses_invalid_discovery_before_package_replacement(
    monkeypatch, tmp_path: Path
) -> None:
    """Malformed public-release metadata cannot enter the mutating workflow."""
    interpreter = _owned_console(tmp_path)
    root = tmp_path / "migration-root"
    root.mkdir()
    observed_argv: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        observed_argv.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setenv("NWAVE_INSTALLER", "uv")
    with (
        patch("sys.executable", str(interpreter)),
        patch(
            "scripts.shared.version.resolve_product_version",
            return_value=ProductVersion.from_text("1.4.0"),
        ),
        patch("urllib.request.urlopen", return_value=_PyPIResponse({"releases": []})),
        patch("subprocess.run", side_effect=run),
        patch("sys.argv", ["nwave-ai", "update", "--yes", "--root", str(root)]),
        patch("sys.stdout", new_callable=io.StringIO) as stdout,
        patch("sys.stderr", new_callable=io.StringIO) as stderr,
    ):
        exit_code = main()

    assert exit_code != 0 and all(
        marker in (stdout.getvalue() + stderr.getvalue())
        for marker in ("WHAT:", "WHY:", "HOW:")
    ), (
        "WHAT: invalid release metadata did not become an explicit discovery refusal. "
        "WHY: no parsed stable version exists to authorize exact package replacement. "
        "HOW: render the discovery WHAT/WHY/HOW refusal before selecting or running an owner command."
    )
    assert observed_argv == [], (
        "WHAT: invalid discovery started package replacement or a later stage. "
        "WHY: all mutation depends on a valid newer public version. "
        "HOW: terminate before the first process when discovery cannot yield an eligible release."
    )


def test_update_mutation_requires_exact_yes_and_root_shape(
    monkeypatch, tmp_path: Path
) -> None:
    """Only the explicit apply argv shape can reach a mutation-capable stage."""
    root = tmp_path / "migration-root"
    root.mkdir()
    malformed_argv = (
        ["nwave-ai", "update"],
        ["nwave-ai", "update", "--yes"],
        ["nwave-ai", "update", "--root", str(root)],
        ["nwave-ai", "update", "--yes", "--root", str(root), "--check"],
    )

    for argv in malformed_argv:
        with (
            patch(
                "subprocess.run",
                side_effect=AssertionError(
                    "a malformed update invocation must not run a process"
                ),
            ),
            patch("sys.argv", argv),
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main()

        assert exit_code != 0 and "Usage:" in (stdout.getvalue() + stderr.getvalue()), (
            "WHAT: an incomplete or mixed update invocation was not rejected as usage. "
            "WHY: mutations require the operator's explicit --yes acknowledgement and named root. "
            "HOW: accept mutation only for `update --yes --root PATH` and keep `--check` separate."
        )

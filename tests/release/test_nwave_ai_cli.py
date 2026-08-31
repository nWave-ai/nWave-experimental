"""Tests for nwave_ai/cli.py

Thin CLI wrapper that dispatches install/uninstall/version commands
to the appropriate scripts under scripts/install/.

BDD scenario mapping:
  - Version derivation (P2-V1): ``nwave-ai --version``, ``nwave-ai version``
    and ``nwave_ai.__version__`` share one installed-metadata-or-source-derived
    projection; missing/malformed/ambiguous identity refuses without printing
    a version
  - Project root: resolves to repo root from cli.py location
  - Run script: subprocess dispatch with missing-script guard
  - Main dispatch: routes commands to correct handlers
  - Usage: prints formatted help text
  - Unresolved build identity retirement (P2-V2a): every live producer either
    constructs a real identity or refuses with the typed identity error; lazy
    consumers resolve only at use and preserve loud WHAT/WHY/HOW failure
  - Release literal-stamp retirement: every release workflow and its private
    test dependencies retire the obsolete module-literal stamp/parse/count
    machinery, retaining only the pyproject-patch producer and the installed
    observations
"""

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from nwave_ai.cli import (
    _get_project_root,
    _print_usage,
    _run_script,
    main,
)

import nwave_ai


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
NWAVE_AI_PKG = REPO_ROOT / "nwave_ai"
SCRIPTS_DIR = REPO_ROOT / "scripts"
SRC_DIR = REPO_ROOT / "src"

# The obsolete sed/re.subn pattern every release workflow and private test
# dependency used to independently write into ``nwave_ai/__init__.py``.
_STAMP_REGEX_LITERAL = '__version__ = ".*"'


def _clean_env() -> dict[str, str]:
    """A minimal environment: no PYTHONPATH/PYTHONHOME or other ambient
    interpreter override that could reintroduce the leakage ``-S`` (below)
    is meant to remove.
    """
    return {"PATH": os.environ.get("PATH", "")}


def _build_checkout(
    tmp_path: Path, *, pyproject: dict[str, object] | str | None
) -> Path:
    """One isolated checkout: the real ``nwave_ai``/``scripts`` sources, with
    only ``nwave_ai/__init__.py`` physically copied so its own
    ``__file__``-relative root resolves to *this* checkout, never the real
    repository root; an optional synthetic ``pyproject.toml`` supplies the
    source project identity under test.
    """
    checkout = tmp_path / "checkout"
    nwave_ai_dir = checkout / "nwave_ai"
    nwave_ai_dir.mkdir(parents=True)
    for entry in NWAVE_AI_PKG.iterdir():
        if entry.name == "__pycache__":
            continue
        target = nwave_ai_dir / entry.name
        if entry.name == "__init__.py":
            shutil.copy2(entry, target)
        else:
            target.symlink_to(entry, target_is_directory=entry.is_dir())
    (checkout / "scripts").symlink_to(SCRIPTS_DIR, target_is_directory=True)
    (checkout / "src").symlink_to(SRC_DIR, target_is_directory=True)
    if pyproject is not None:
        if isinstance(pyproject, str):
            project_text = pyproject
        else:
            project_lines = ["[project]"]
            for field in ("name", "version"):
                if field not in pyproject:
                    continue
                value = pyproject[field]
                literal = f'"{value}"' if isinstance(value, str) else str(value)
                project_lines.append(f"{field} = {literal}")
            project_text = "\n".join(project_lines) + "\n"
        (checkout / "pyproject.toml").write_text(
            project_text,
            encoding="utf-8",
        )
    return checkout


def _write_dist_info(
    checkout: Path,
    *,
    dist_name: str,
    version: str | None,
    owned_package: str,
    include_metadata: bool = True,
    include_top_level: bool = True,
) -> None:
    """One ephemeral ``*.dist-info`` directory naming *owned_package* through
    either optional ``top_level.txt`` or wheel-standard ``RECORD`` evidence,
    the two shapes ``importlib.metadata.packages_distributions()`` infers.
    """
    dist_info = checkout / f"{dist_name}-{version or 'unknown'}.dist-info"
    dist_info.mkdir()
    if include_metadata:
        metadata = f"Metadata-Version: 2.1\nName: {dist_name}\n"
        if version is not None:
            metadata += f"Version: {version}\n"
        (dist_info / "METADATA").write_text(metadata, encoding="utf-8")
    if include_top_level:
        (dist_info / "top_level.txt").write_text(f"{owned_package}\n", encoding="utf-8")
    else:
        (dist_info / "WHEEL").write_text(
            "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
            encoding="utf-8",
        )
        (dist_info / "RECORD").write_text(
            f"{owned_package}/__init__.py,,\n"
            f"{dist_info.name}/METADATA,,\n"
            f"{dist_info.name}/WHEEL,,\n"
            f"{dist_info.name}/RECORD,,\n",
            encoding="utf-8",
        )


def _run_cli(checkout: Path, argv: list[str]) -> subprocess.CompletedProcess:
    """Drive ``nwave_ai.cli.main()`` in a fresh, site-isolated subprocess that
    imports only *checkout*, proving each real version argv without
    module-cache, ambient site-package, or operator-environment leakage.
    """
    code = (
        "import sys; "
        "sys.path.insert(0, sys.argv[1]); "
        "sys.path.insert(0, sys.argv[1] + '/src'); "
        "sys.argv = ['nwave-ai', *sys.argv[2:]]; "
        "from nwave_ai.cli import main; sys.exit(main())"
    )
    return subprocess.run(
        [sys.executable, "-S", "-c", code, str(checkout), *argv],
        cwd=str(checkout),
        capture_output=True,
        text=True,
        timeout=30,
        env=_clean_env(),
    )


def _run_get_version(checkout: Path) -> subprocess.CompletedProcess:
    """Call the legacy source-only compatibility port in the same isolated
    checkout used by the public version surfaces.
    """
    code = (
        "import sys; from pathlib import Path; "
        "sys.path.insert(0, sys.argv[1]); "
        "from scripts.shared.version import get_version, VersionResolutionError; "
        "\ntry:\n"
        "    print(get_version(Path(sys.argv[1])))\n"
        "except VersionResolutionError as exc:\n"
        "    print(str(exc), file=sys.stderr)\n"
        "    sys.exit(3)\n"
    )
    return subprocess.run(
        [sys.executable, "-S", "-c", code, str(checkout)],
        cwd=str(checkout),
        capture_output=True,
        text=True,
        timeout=30,
        env=_clean_env(),
    )


def _assert_cli_refuses(checkout: Path, argv_cases: tuple[tuple[str, ...], ...]):
    for argv in argv_cases:
        result = _run_cli(checkout, list(argv))
        assert result.returncode != 0
        assert result.stdout == ""
        assert "WHAT:" in result.stderr
        assert "WHY:" in result.stderr
        assert "HOW:" in result.stderr
        assert "Traceback" not in result.stderr


class TestVersionDerivation:
    """``resolve_product_version`` end to end through the real CLI/module
    surface: installed-metadata precedence, source-derived fallback, and
    refusal on ambiguous/missing/malformed identity (P2-V1).
    """

    @pytest.mark.parametrize(
        "include_top_level", [True, False], ids=["top-level", "wheel-record"]
    )
    def test_installed_metadata_owner_wins_without_hardcoding_the_name(
        self, tmp_path, include_top_level
    ):
        """The dynamically discovered owner wins over the adjacent source
        identity even though it is never named "nwave-ai" literally -- no
        hard-coded ``version("nwave-ai")`` branch could produce this result.
        Wheel-standard RECORD evidence remains sufficient when the optional
        top-level declaration is absent.
        """
        checkout = _build_checkout(
            tmp_path, pyproject={"name": "nwave", "version": "1.1.1"}
        )
        _write_dist_info(
            checkout,
            dist_name="nwave-ai-fork",
            version="7.7.7",
            owned_package="nwave_ai",
            include_top_level=include_top_level,
        )

        for argv in (("--version",), ("version",)):
            result = _run_cli(checkout, list(argv))
            assert result.returncode == 0
            assert result.stdout.strip() == "nwave-ai 7.7.7"
            assert result.stderr == ""

    def test_source_derived_version_without_installed_owner(self, tmp_path):
        checkout = _build_checkout(
            tmp_path, pyproject={"name": "nwave", "version": "9.9.9"}
        )

        for argv in (("--version",), ("version",)):
            result = _run_cli(checkout, list(argv))
            assert result.returncode == 0
            assert result.stdout.strip() == "nwave-ai 9.9.9"
            assert result.stderr == ""

    @pytest.mark.parametrize(
        "pyproject",
        [
            pytest.param(None, id="no-pyproject"),
            pytest.param({"version": "1.0.0"}, id="missing-name"),
            pytest.param({"name": "", "version": "1.0.0"}, id="empty-name"),
            pytest.param({"name": 7, "version": "1.0.0"}, id="nonstring-name"),
            pytest.param({"name": "nwave"}, id="missing-version"),
            pytest.param({"name": "nwave", "version": ""}, id="empty-version"),
            pytest.param({"name": "nwave", "version": 7}, id="nonstring-version"),
            pytest.param('[project\nname = "nwave"\n', id="malformed-toml"),
            pytest.param({"name": "nwave", "version": "0.0.0"}, id="sentinel-version"),
        ],
    )
    def test_source_identity_refuses_without_printing(self, tmp_path, pyproject):
        checkout = _build_checkout(tmp_path, pyproject=pyproject)

        _assert_cli_refuses(checkout, (("--version",), ("version",)))

    @pytest.mark.parametrize(
        ("versions", "include_metadata"),
        [
            pytest.param(("1.0.0", "2.0.0"), True, id="ambiguous-owner"),
            pytest.param((None,), True, id="missing-owner-version"),
            pytest.param((None,), False, id="missing-owner-metadata"),
            pytest.param(("0.0.0",), True, id="sentinel-version"),
        ],
    )
    def test_installed_identity_refuses_without_printing(
        self, tmp_path, versions, include_metadata
    ):
        checkout = _build_checkout(
            tmp_path, pyproject={"name": "nwave", "version": "1.0.0"}
        )
        for index, version in enumerate(versions):
            _write_dist_info(
                checkout,
                dist_name=f"nwave-ai-owner-{index}",
                version=version,
                owned_package="nwave_ai",
                include_metadata=include_metadata,
                include_top_level=include_metadata,
            )

        _assert_cli_refuses(checkout, (("--version",), ("version",)))

    def test_product_version_from_text_is_version_only_immutable_and_non_sentinel(
        self,
    ):
        """The value object has one stored fact -- version text. Distribution
        name remains selection provenance, and the compatibility sentinel can
        never inhabit the strict P2-V1 value.
        """
        from scripts.shared.version import ProductVersion, VersionResolutionError

        product_version = ProductVersion.from_text("4.0.1")

        assert product_version.version == "4.0.1"
        assert not hasattr(product_version, "name")
        assert not hasattr(product_version, "distribution_name")
        for attribute, value in (
            ("version", "9.9.9"),
            ("name", "nwave-ai"),
            ("distribution_name", "nwave-ai"),
        ):
            with pytest.raises(AttributeError):
                setattr(product_version, attribute, value)
        with pytest.raises(VersionResolutionError):
            ProductVersion.from_text("0.0.0")

    def test_product_version_refuses_every_direct_construction_shape(self):
        from scripts.shared.version import ProductVersion

        for direct_args in ((), ("4.0.1",), ("4.0.1", "nwave-ai-fork")):
            with pytest.raises(TypeError):
                ProductVersion(*direct_args)
        with pytest.raises(TypeError):
            ProductVersion(version="4.0.1")

    def test_legacy_get_version_delegates_valid_source_identity(self, tmp_path):
        checkout = _build_checkout(
            tmp_path, pyproject={"name": "nwave", "version": "4.0.1"}
        )

        result = _run_get_version(checkout)

        assert result.returncode == 0
        assert result.stdout.strip() == "4.0.1"
        assert result.stderr == ""

    def test_legacy_get_version_refuses_unresolved_identity_loudly(self, tmp_path):
        checkout = _build_checkout(tmp_path, pyproject={"version": "4.0.1"})

        result = _run_get_version(checkout)

        assert result.returncode == 3
        assert result.stdout == ""
        assert "WHAT:" in result.stderr
        assert "WHY:" in result.stderr
        assert "HOW:" in result.stderr
        assert "0.0.0" not in result.stdout

    @pytest.mark.parametrize("argv", [[], ["--help"]])
    def test_help_refuses_when_product_identity_is_unavailable(self, tmp_path, argv):
        checkout = _build_checkout(tmp_path, pyproject=None)

        result = _run_cli(checkout, argv)

        assert result.returncode != 0
        assert result.stdout == ""
        assert "WHAT:" in result.stderr
        assert "WHY:" in result.stderr
        assert "HOW:" in result.stderr
        assert "Traceback" not in result.stderr

    def test_lazy_import_defers_resolution_then_direct_access_raises_typed_error(
        self, tmp_path
    ):
        """Importing ``nwave_ai`` alone performs no resolution; only a direct
        ``__version__`` access resolves and may raise the typed error.
        """
        checkout = _build_checkout(tmp_path, pyproject=None)
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]); "
            "import nwave_ai\n"
            "print('IMPORTED', flush=True)\n"
            "try:\n"
            "    nwave_ai.unknown_product_attribute\n"
            "except AttributeError:\n"
            "    print('UNKNOWN-ATTRIBUTE', flush=True)\n"
            "else:\n"
            "    sys.exit(2)\n"
            "try:\n"
            "    nwave_ai.__version__\n"
            "except Exception as exc:\n"
            "    print(f'RAISED:{type(exc).__module__}.{type(exc).__name__}')\n"
            "    sys.exit(3)\n"
            "print('NOT-RAISED')\n"
            "sys.exit(0)\n"
        )
        result = subprocess.run(
            [sys.executable, "-S", "-c", code, str(checkout)],
            cwd=str(checkout),
            capture_output=True,
            text=True,
            timeout=30,
            env=_clean_env(),
        )

        assert "IMPORTED" in result.stdout
        assert "UNKNOWN-ATTRIBUTE" in result.stdout
        assert result.returncode == 3
        assert "RAISED:scripts.shared.version.VersionResolutionError" in result.stdout


class TestBuildIdentityConstruction:
    """Finite P2-V2a construction law over the six DESIGN-owned producers.

    This is deliberately bounded to the closed target set.  It is not a
    repository-wide source-shape gate: the property is that a version producer
    cannot return either compatibility sentinel through any of the four
    authority-censused escape shapes.
    """

    PRODUCERS = (
        "scripts/shared/version.py",
        "scripts/build_dist.py",
        "scripts/install/install_nwave.py",
        "scripts/framework/create_github_tarballs.py",
        "scripts/install/plugins/des_plugin.py",
        "scripts/install/plugins/opencode_des_plugin.py",
    )
    SENTINELS = {"0.0.0", "dev"}

    @classmethod
    def _sentinel_escapes(cls, source: str) -> list[tuple[int, str]]:
        tree = ast.parse(source)
        escapes: list[tuple[int, str]] = []
        for function in (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and "version" in node.name.lower()
        ):
            for node in ast.walk(function):
                if isinstance(node, ast.Return) and (
                    node.value is None
                    or (
                        isinstance(node.value, ast.Constant)
                        and node.value.value in cls.SENTINELS
                    )
                ):
                    escapes.append((node.lineno, "return"))
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and len(node.args) >= 2
                    and isinstance(node.args[1], ast.Constant)
                    and node.args[1].value in cls.SENTINELS
                ):
                    escapes.append((node.lineno, "dict.get-default"))
                if isinstance(node, ast.IfExp):
                    for branch in (node.body, node.orelse):
                        if (
                            isinstance(branch, ast.Constant)
                            and branch.value in cls.SENTINELS
                        ):
                            escapes.append((node.lineno, "conditional"))
        return escapes

    @pytest.mark.parametrize("producer", PRODUCERS)
    def test_unresolved_identity_is_not_a_producer_result(self, producer):
        source = (REPO_ROOT / producer).read_text(encoding="utf-8")

        assert self._sentinel_escapes(source) == [], producer
        assert "VersionResolutionError" in source, producer

    def test_valid_source_and_installed_seeds_still_reach_the_public_cli(
        self, tmp_path
    ):
        source_checkout = _build_checkout(
            tmp_path / "source", pyproject={"name": "nwave", "version": "4.0.1"}
        )
        installed_checkout = _build_checkout(
            tmp_path / "installed",
            pyproject={"name": "nwave", "version": "4.0.0"},
        )
        _write_dist_info(
            installed_checkout,
            dist_name="nwave-ai",
            version="4.0.1+candidate",
            owned_package="nwave_ai",
        )

        source_result = _run_cli(source_checkout, ["version"])
        installed_result = _run_cli(installed_checkout, ["version"])

        assert source_result.returncode == 0
        assert source_result.stdout.strip() == "nwave-ai 4.0.1"
        assert source_result.stderr == ""
        assert installed_result.returncode == 0
        assert installed_result.stdout.strip() == "nwave-ai 4.0.1+candidate"
        assert installed_result.stderr == ""


class TestReleaseLiteralStampRetirement:
    """The obsolete module-literal stamp/parse/count machinery is retired
    from every release workflow and its private test dependencies; each
    surviving route keeps its own pyproject-patch producer and installed
    observations. One finite one-writer removal assertion over real bytes,
    never a nested pytest run or a general source-shape gate.
    """

    @pytest.mark.parametrize(
        "workflow",
        [
            ".github/workflows/release-github.yml",
            ".github/workflows/release-prod.yml",
            ".github/workflows/release-rc.yml",
        ],
    )
    def test_workflow_module_literal_stamp_step_is_absent(self, workflow):
        text = (REPO_ROOT / workflow).read_text(encoding="utf-8")
        assert "Stamp nwave_ai version" not in text
        assert _STAMP_REGEX_LITERAL not in text
        assert "Patch pyproject.toml for nwave-ai" in text

    def test_release_rc_retains_installed_lazy_attribute_smokes(self):
        text = (REPO_ROOT / ".github/workflows/release-rc.yml").read_text(
            encoding="utf-8"
        )
        assert text.count("nwave_ai.__version__") >= 2

    @pytest.mark.parametrize(
        "support_file",
        [
            "tests/acceptance/certified_capture/test_clean_install_evidence_bundle.py",
            "tests/e2e/conftest.py",
            "tests/release/test_release_staging_ssot.py",
        ],
    )
    def test_support_file_module_literal_stamp_write_is_absent(self, support_file):
        text = (REPO_ROOT / support_file).read_text(encoding="utf-8")
        assert _STAMP_REGEX_LITERAL not in text
        assert "module version assignments" not in text

    def test_release_staging_ssot_stamp_parser_and_count_helpers_are_absent(self):
        text = (REPO_ROOT / "tests/release/test_release_staging_ssot.py").read_text(
            encoding="utf-8"
        )
        assert "_stamp_module_version" not in text
        assert "_sed_replacement" not in text
        assert "_stamp_version_value" not in text
        assert "_module_version(" not in text
        assert '"stamp":' not in text


class TestProjectRoot:
    """_get_project_root() returns the repo root."""

    def test_returns_parent_of_nwave_ai_package(self):
        """Given cli.py lives in nwave_ai/,
        when _get_project_root() is called,
        then it returns nwave_ai's parent (the repo root).
        """
        root = _get_project_root()
        assert root == Path(__file__).parent.parent.parent
        assert (root / "nwave_ai" / "cli.py").exists()


class TestRunScript:
    """_run_script() subprocess dispatch."""

    def test_calls_subprocess_with_correct_args(self, tmp_path):
        """Given a valid script path,
        when _run_script() is called,
        then it invokes subprocess.run with the right command.
        """
        mock_result = MagicMock(returncode=0)
        with (
            patch("nwave_ai.cli._get_project_root", return_value=tmp_path),
            patch("nwave_ai.cli.subprocess.run", return_value=mock_result) as mock_run,
        ):
            script_dir = tmp_path / "scripts" / "install"
            script_dir.mkdir(parents=True)
            (script_dir / "install_nwave.py").touch()

            code = _run_script("install_nwave.py", ["--dry-run"])

        assert code == 0
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd[1].endswith("install_nwave.py")
        assert "--dry-run" in cmd
        assert call_args[1]["cwd"] == str(tmp_path)

    def test_returns_1_when_script_missing(self, tmp_path, capsys):
        """Given the script file does not exist,
        when _run_script() is called,
        then it prints an error and returns 1.
        """
        with patch("nwave_ai.cli._get_project_root", return_value=tmp_path):
            code = _run_script("missing.py", [])

        assert code == 1
        err = capsys.readouterr().err
        assert "missing.py not found" in err

    def test_propagates_subprocess_return_code(self, tmp_path):
        """Given the subprocess exits with code 42,
        when _run_script() is called,
        then it returns 42.
        """
        mock_result = MagicMock(returncode=42)
        with (
            patch("nwave_ai.cli._get_project_root", return_value=tmp_path),
            patch("nwave_ai.cli.subprocess.run", return_value=mock_result),
        ):
            script_dir = tmp_path / "scripts" / "install"
            script_dir.mkdir(parents=True)
            (script_dir / "install_nwave.py").touch()

            code = _run_script("install_nwave.py", [])

        assert code == 42


class TestMainDispatch:
    """main() routes commands to the correct handlers."""

    def test_install_routes_to_run_script(self):
        """Given argv=['nwave-ai', 'install', '--dry-run'],
        when main() is called,
        then it dispatches to _run_script('install_nwave.py', ['--dry-run']).
        """

        class VersionAccessForbidden:
            @property
            def __version__(self):
                raise AssertionError("install command resolved product identity")

        with (
            patch("nwave_ai.cli.sys.argv", ["nwave-ai", "install", "--dry-run"]),
            patch("nwave_ai.cli._run_script", return_value=0) as mock_rs,
            patch("nwave_ai.cli.nwave_ai", VersionAccessForbidden()),
        ):
            code = main()

        assert code == 0
        mock_rs.assert_called_once_with("install_nwave.py", ["--dry-run"])

    def test_uninstall_routes_to_run_script(self):
        """Given argv=['nwave-ai', 'uninstall'],
        when main() is called,
        then it dispatches to _run_script('uninstall_nwave.py', []).
        """
        with (
            patch("nwave_ai.cli.sys.argv", ["nwave-ai", "uninstall"]),
            patch("nwave_ai.cli._run_script", return_value=0) as mock_rs,
        ):
            code = main()

        assert code == 0
        mock_rs.assert_called_once_with("uninstall_nwave.py", [])

    def test_version_prints_version(self, capsys):
        """Given argv=['nwave-ai', 'version'],
        when main() is called,
        then it prints the version string and returns 0.
        """
        with (
            patch("nwave_ai.cli.sys.argv", ["nwave-ai", "version"]),
            patch.object(nwave_ai, "__version__", "3.4.5"),
        ):
            code = main()

        assert code == 0
        assert "3.4.5" in capsys.readouterr().out

    def test_help_flag_prints_usage(self, capsys):
        """Given argv=['nwave-ai', '--help'],
        when main() is called,
        then it prints usage and returns 0.
        """
        with (
            patch("nwave_ai.cli.sys.argv", ["nwave-ai", "--help"]),
            patch.object(nwave_ai, "__version__", "1.0.0"),
        ):
            code = main()

        assert code == 0
        out = capsys.readouterr().out
        assert "Usage:" in out

    def test_no_args_prints_usage(self, capsys):
        """Given argv=['nwave-ai'] (no command),
        when main() is called,
        then it prints usage and returns 0.
        """
        with (
            patch("nwave_ai.cli.sys.argv", ["nwave-ai"]),
            patch.object(nwave_ai, "__version__", "1.0.0"),
        ):
            code = main()

        assert code == 0
        assert "Usage:" in capsys.readouterr().out

    def test_unknown_command_returns_1(self, capsys):
        """Given argv=['nwave-ai', 'bogus'],
        when main() is called,
        then it prints an error and returns 1.
        """
        with patch("nwave_ai.cli.sys.argv", ["nwave-ai", "bogus"]):
            code = main()

        assert code == 1
        err = capsys.readouterr().err
        assert "Unknown command: bogus" in err


class TestUsage:
    """_print_usage(version) output format."""

    def test_includes_version_and_commands(self, capsys):
        """Given a version string,
        when _print_usage() is called,
        then it prints version header, commands, and options.
        """
        code = _print_usage("9.8.7")

        assert code == 0
        out = capsys.readouterr().out
        assert "nwave-ai 9.8.7" in out
        assert "install" in out
        assert "uninstall" in out
        assert "version" in out
        assert "--dry-run" in out

    def test_returns_zero(self):
        """_print_usage() always returns 0."""
        assert _print_usage("0.0.0") == 0

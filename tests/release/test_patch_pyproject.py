"""Tests for scripts/release/patch_pyproject.py

Computes pyproject.toml patches for public repo distribution:
rename package, set version, update authors, rewrite build targets,
remove dev-only sections.

BDD scenario mapping:
  - journey-stable-release.feature: "pyproject.toml is patched: name 'nwave-ai', version '1.1.22'" (Scenario 1)
  - journey-stable-release.feature: Dry run shows patch diff (Scenario 2)
  - US-RTR-003: Stable release pipeline, pyproject patching step.
"""

import posixpath
import shutil
from pathlib import Path

import pytest
import tomllib

from scripts.release.patch_pyproject import _patch_wheel_packages, patch_pyproject


class TestPackageNameSwap:
    """Rename 'nwave' to 'nwave-ai' in the public distribution."""

    def test_project_name_changed_to_nwave_ai(self, sample_pyproject_path, tmp_path):
        """Given source pyproject.toml has name='nwave',
        when patching with --target-name 'nwave-ai',
        then the output has name='nwave-ai'.
        """
        output_path = str(tmp_path / "out.toml")
        result = patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )
        content = (tmp_path / "out.toml").read_text()
        assert 'name = "nwave-ai"' in content
        assert result["patched"] is True
        assert any("name" in c for c in result["changes"])

    def test_name_swap_is_exact_not_substring(self, sample_pyproject_path, tmp_path):
        """The name swap should not affect other occurrences of 'nwave'
        in non-name fields (e.g., description or URLs).
        """
        output_path = str(tmp_path / "out.toml")
        patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )
        content = (tmp_path / "out.toml").read_text()
        # Description still says "nWave Framework", not "nwave-ai Framework"
        assert "nWave Framework" in content


class TestVersionSetting:
    """Set the target version in the patched pyproject.toml."""

    def test_version_set_to_target(self, sample_pyproject_path, tmp_path):
        """Given source version is '1.1.21',
        when patching with --target-version '1.1.22',
        then the output has version='1.1.22'.
        """
        output_path = str(tmp_path / "out.toml")
        result = patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )
        content = (tmp_path / "out.toml").read_text()
        assert 'version = "1.1.22"' in content
        assert any("version" in c for c in result["changes"])

    def test_version_format_is_pep440(self, sample_pyproject_path, tmp_path):
        """The patched version must be valid PEP 440."""
        output_path = str(tmp_path / "out.toml")
        from packaging.version import Version

        patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )
        content = (tmp_path / "out.toml").read_text()
        # Extract the version line
        for line in content.splitlines():
            if line.startswith("version"):
                version_str = line.split("=")[1].strip().strip('"')
                Version(version_str)  # Raises InvalidVersion if not PEP 440
                break


class TestBuildTargetRewrite:
    """Rewrite build targets for public distribution."""

    def test_wheel_packages_rewritten(self, sample_pyproject_path, tmp_path):
        """Given source has packages=['nWave'],
        when patching for nwave-ai,
        then packages are rewritten for the public package structure.
        """
        output_path = str(tmp_path / "out.toml")
        patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )
        content = (tmp_path / "out.toml").read_text()
        # The old nWave package reference should be replaced
        assert 'packages = ["nWave"]' not in content
        assert 'packages = ["nwave_ai"]' in content

    def test_force_include_added(self, sample_pyproject_path, tmp_path):
        """Given source has simple wheel config,
        when patching for nwave-ai,
        then selective force-include entries are added.

        Regression guard (fix-wheel-leaks-des-config-p0 01-02): the force-include
        map must NOT contain broad ``"scripts"`` or ``"src/des"`` entries, which
        ship dev-only tooling and closed-source runtime respectively.  Only the
        narrow subset actually consumed by nwave_ai/ at runtime may be included.
        """
        output_path = str(tmp_path / "out.toml")
        patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )
        content = (tmp_path / "out.toml").read_text()
        assert "[tool.hatch.build.targets.wheel.force-include]" in content
        # nWave/ subtree (public framework content)
        assert '"nWave/agents" = "nWave/agents"' in content
        assert '"nWave/skills" = "nWave/skills"' in content
        assert '"nWave/tasks/nw" = "nWave/tasks/nw"' in content
        # Narrow scripts includes: only the subset nwave_ai/ actually imports
        assert '"scripts/install" = "scripts/install"' in content
        assert '"scripts/shared" = "scripts/shared"' in content
        # Pre-built DES module (produced by scripts/build_dist.py into dist/lib/
        # and staged to repo root ./lib before `python -m build --wheel`).
        # Hatch force-include semantics: LHS=source, RHS=destination.  The
        # Distinct staged sources are mandatory: Hatch normalizes a trailing
        # slash and would otherwise retain only one destination.  The public
        # entry point needs top-level des, while the installer needs its nested
        # runtime asset copy.
        assert '"lib/python/des" = "des"' in content
        assert '"lib/nwave-runtime/des" = "nWave/lib/python/des"' in content
        # Should NOT include nWave/ as a whole (avoids broken symlinks)
        lines = content.splitlines()
        assert not any(line.strip() == '"nWave" = "nWave"' for line in lines)

    @pytest.mark.negative_at
    def test_capture_contract_package_is_projected_to_its_public_wheel_destination(
        self,
    ):
        """The release patch keeps both public Python package projections.

        CONTRACT_SHAPE: pure-function
        """
        # covers: R1
        patched_text, _ = _patch_wheel_packages(
            '[tool.hatch.build.targets.wheel]\npackages = ["nWave"]\n',
            "nwave_ai",
        )
        force_include = tomllib.loads(patched_text)["tool"]["hatch"]["build"][
            "targets"
        ]["wheel"]["force-include"]

        assert {
            "lib/python/des": "des",
            "src/nwave_capture": "nwave_capture",
        }.items() <= force_include.items(), (
            "WHAT: the release wheel omits a public Python package projection. "
            "WHY: installed users need both the des command and the independent "
            "nwave_capture study contract. HOW: add both source-to-destination "
            "entries to _patch_wheel_packages."
        )

    @pytest.mark.negative_at
    def test_development_and_rc_wheel_projects_capture_with_existing_packages(self):
        """The repository wheel includes capture without dropping current packages.

        CONTRACT_SHAPE: pure-function
        """
        # covers: R1
        repository_root = Path(__file__).resolve().parents[2]
        project = tomllib.loads((repository_root / "pyproject.toml").read_text())
        packages = set(
            project["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
        )

        assert {"src/des", "nwave_ai", "src/nwave_capture"} <= packages, (
            "WHAT: the development/RC wheel package list omits an existing public "
            "package or the neutral capture contract. WHY: non-PyPI candidates must "
            "ship des, nwave_ai, and nwave_capture together. HOW: add "
            "src/nwave_capture to [tool.hatch.build.targets.wheel].packages without "
            f"removing current entries; observed={sorted(packages)}"
        )

    def test_public_catalog_never_has_single_destination_or_broad_include(self):
        """The public catalog ships at both consumer-visible wheel locations.

        Each destination needs a distinct normalized source key: syntactically
        different aliases that normalize to the same path collide in Hatch.
        """
        patched_text, _ = _patch_wheel_packages(
            '[tool.hatch.build.targets.wheel]\npackages = ["nWave"]\n',
            "nwave_ai",
        )
        patched = tomllib.loads(patched_text)
        force_include = patched["tool"]["hatch"]["build"]["targets"]["wheel"][
            "force-include"
        ]

        catalog_entries = [
            (posixpath.normpath(source), destination)
            for source, destination in force_include.items()
            if posixpath.basename(destination) == "framework-catalog.yaml"
        ]
        required_destinations = {
            "nWave/framework-catalog.yaml",
            "nWave/nWave/framework-catalog.yaml",
        }

        # Witness: both consumer-visible destinations are present, with no extras.
        assert {destination for _, destination in catalog_entries} == (
            required_destinations
        )
        # Mutation pair: normalized-source collision or broad fallback must fail.
        assert len({source for source, _ in catalog_entries}) == 2
        assert "nWave" not in {posixpath.normpath(source) for source in force_include}

    def test_public_templates_never_share_normalized_source_or_use_broad_include(
        self,
    ):
        """Both template consumers require collision-free force-includes.

        Each destination needs a distinct normalized source key: syntactically
        different aliases that normalize to the same path collide in Hatch.
        """
        patched_text, _ = _patch_wheel_packages(
            '[tool.hatch.build.targets.wheel]\npackages = ["nWave"]\n',
            "nwave_ai",
        )
        patched = tomllib.loads(patched_text)
        force_include = patched["tool"]["hatch"]["build"]["targets"]["wheel"][
            "force-include"
        ]

        required_destinations = {
            "nWave/templates",
            "nWave/nWave/templates",
        }
        template_entries = [
            (posixpath.normpath(source), destination)
            for source, destination in force_include.items()
            if posixpath.basename(destination) == "templates"
        ]

        # Witness: both consumer-visible destinations are present, with no extras.
        assert {destination for _, destination in template_entries} == (
            required_destinations
        )
        # Mutation pair: normalized-source collision or broad fallback must fail.
        assert len({source for source, _ in template_entries}) == 2
        assert "nWave" not in {posixpath.normpath(source) for source in force_include}

    def test_public_data_never_has_one_destination_shared_source_or_broad_include(
        self,
    ):
        """Data ships to both consumers from collision-free, narrow sources."""
        patched_text, _ = _patch_wheel_packages(
            '[tool.hatch.build.targets.wheel]\npackages = ["nWave"]\n',
            "nwave_ai",
        )
        patched = tomllib.loads(patched_text)
        force_include = patched["tool"]["hatch"]["build"]["targets"]["wheel"][
            "force-include"
        ]

        required_destinations = {
            "nWave/data",
            "nWave/nWave/data",
        }
        data_entries = [
            (posixpath.normpath(source), destination)
            for source, destination in force_include.items()
            if posixpath.basename(destination) == "data"
        ]

        assert {destination for _, destination in data_entries} == (
            required_destinations
        )
        assert len({source for source, _ in data_entries}) == 2
        assert "nWave" not in {posixpath.normpath(source) for source in force_include}

    def test_force_include_excludes_broad_scripts(
        self, sample_pyproject_path, tmp_path
    ):
        """Regression guard: the broad ``"scripts" = "scripts"`` force-include
        shipped 136 files of dev-only tooling (release/, hooks/, framework/,
        validation/) to the 3.11.0 public wheel.  The patched output must NOT
        contain this entry.
        """
        output_path = str(tmp_path / "out.toml")
        patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )
        content = (tmp_path / "out.toml").read_text()
        lines = content.splitlines()
        assert not any(line.strip() == '"scripts" = "scripts"' for line in lines), (
            "broad 'scripts' force-include is present — dev-only tooling will "
            "ship publicly (regression of fix-wheel-leaks-des-config-p0)"
        )

    def test_force_include_excludes_raw_src_des(self, sample_pyproject_path, tmp_path):
        """Regression guard: the ``"src/des" = "src/des"`` force-include shipped
        149 files of closed-source DES runtime to the 3.11.0 public wheel.
        The patched output must NOT contain this entry — use the pre-built
        ``lib/python/des`` (import-rewritten) instead.
        """
        output_path = str(tmp_path / "out.toml")
        patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )
        content = (tmp_path / "out.toml").read_text()
        lines = content.splitlines()
        assert not any(line.strip() == '"src/des" = "src/des"' for line in lines), (
            "raw 'src/des' force-include is present — closed-source DES runtime "
            "will ship publicly (regression of fix-wheel-leaks-des-config-p0)"
        )


class TestCliEntryPoint:
    """Add CLI entry point for pipx install support."""

    def test_project_scripts_added(self, sample_pyproject_path, tmp_path):
        """Given source has no [project.scripts],
        when patching for nwave-ai,
        then [project.scripts] is added with the CLI entry point.
        """
        output_path = str(tmp_path / "out.toml")
        patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )
        content = (tmp_path / "out.toml").read_text()
        assert "[project.scripts]" in content
        assert 'nwave-ai = "nwave_ai.cli:main"' in content

    def test_existing_scripts_not_duplicated(self, tmp_path):
        """Given source already has [project.scripts],
        when patching,
        then no duplicate section is added.
        """
        toml_with_scripts = (
            '[project]\nname = "nwave"\nversion = "1.0.0"\n\n'
            '[project.urls]\nHomepage = "https://example.com"\n\n'
            '[project.scripts]\nnwave = "nwave.cli:main"\n\n'
            '[tool.hatch.build.targets.wheel]\npackages = ["nWave"]\n'
        )
        src = tmp_path / "src.toml"
        src.write_text(toml_with_scripts)
        output_path = str(tmp_path / "out.toml")
        patch_pyproject(
            input_path=str(src),
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )
        content = (tmp_path / "out.toml").read_text()
        assert content.count("[project.scripts]") == 1

    def test_patched_output_contains_nwave_ai_entry(self, tmp_path):
        """Given source already has [project.scripts] with foreign entries
        (no nwave-ai), when patching, then the patched output MUST contain
        the nwave-ai console script entry.

        Postcondition assertion absent from test_existing_scripts_not_duplicated
        (which only asserted dedupe count). Codifies issue #41 RCA Branch D:
        the existing test is satisfied by the bug, this one falsifies it.
        """
        toml_with_scripts = (
            '[project]\nname = "nwave"\nversion = "1.0.0"\n\n'
            '[project.urls]\nHomepage = "https://example.com"\n\n'
            '[project.scripts]\nnwave = "nwave.cli:main"\n\n'
            '[tool.hatch.build.targets.wheel]\npackages = ["nWave"]\n'
        )
        src = tmp_path / "src.toml"
        src.write_text(toml_with_scripts)
        output_path = str(tmp_path / "out.toml")
        patch_pyproject(
            input_path=str(src),
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )
        content = (tmp_path / "out.toml").read_text()
        assert 'nwave-ai = "nwave_ai.cli:main"' in content

    def test_existing_des_entry_point_is_preserved_with_importable_destination(
        self, tmp_path
    ):
        """The public DES script keeps its import target and top-level package.

        The release patcher deliberately keeps the nested prebuilt copy used
        by the installer while also force-including the same package at
        ``site-packages/des``.  Without the latter, an installed ``des``
        script fails before its CLI can start.
        """
        toml_with_des = (
            '[project]\nname = "nwave"\nversion = "1.0.0"\n\n'
            '[project.scripts]\ndes = "des.cli.__main__:main"\n\n'
            '[tool.hatch.build.targets.wheel]\npackages = ["nWave"]\n'
        )
        src = tmp_path / "src.toml"
        src.write_text(toml_with_des)
        output_path = str(tmp_path / "out.toml")

        patch_pyproject(
            input_path=str(src),
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )

        content = (tmp_path / "out.toml").read_text()
        assert 'des = "des.cli.__main__:main"' in content
        assert '"lib/python/des" = "des"' in content
        assert '"lib/nwave-runtime/des" = "nWave/lib/python/des"' in content


class TestDevSectionRemoval:
    """Remove dev-only sections from the public pyproject.toml."""

    def test_tool_nwave_section_removed(self, sample_pyproject_path, tmp_path):
        """Given source contains [tool.nwave] section,
        when patching for public distribution,
        then [tool.nwave] is completely removed.
        """
        output_path = str(tmp_path / "out.toml")
        patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )
        content = (tmp_path / "out.toml").read_text()
        assert "[tool.nwave]" not in content
        assert "public_version_floor" not in content

    def test_semantic_release_section_removed(self, sample_pyproject_path, tmp_path):
        """Given source contains [tool.semantic_release] section,
        when patching for public distribution,
        then [tool.semantic_release] is completely removed.
        """
        output_path = str(tmp_path / "out.toml")
        patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )
        content = (tmp_path / "out.toml").read_text()
        assert "[tool.semantic_release]" not in content
        assert "version_variable" not in content

    def test_pytest_section_preserved(self, sample_pyproject_path, tmp_path):
        """Given source contains [tool.pytest.ini_options],
        when patching for public distribution,
        then [tool.pytest.ini_options] is preserved (it is not dev-only).
        """
        output_path = str(tmp_path / "out.toml")
        patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )
        content = (tmp_path / "out.toml").read_text()
        assert "[tool.pytest.ini_options]" in content
        assert 'testpaths = ["tests"]' in content


class TestDryRunMode:
    """Dry run outputs a JSON diff instead of writing a file."""

    def test_dry_run_outputs_json_diff(self, sample_pyproject_path, tmp_path):
        """Given --dry-run flag,
        when running patch_pyproject,
        then result contains changes showing before/after for each field.

        Maps to: Stable dry run "the patch shows name 'nwave-ai', version '1.1.22'".
        """
        output_path = str(tmp_path / "out.toml")
        result = patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
            dry_run=True,
        )
        assert result["patched"] is True
        assert len(result["changes"]) > 0
        # Changes describe name and version swaps
        changes_str = " ".join(result["changes"])
        assert "nwave-ai" in changes_str
        assert "1.1.22" in changes_str

    def test_dry_run_does_not_write_output_file(self, sample_pyproject_path, tmp_path):
        """Given --dry-run flag and --output /some/path,
        when running patch_pyproject,
        then no file is written to the output path.
        """
        output_path = str(tmp_path / "out.toml")
        patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
            dry_run=True,
        )
        assert not (tmp_path / "out.toml").exists()


class TestIdempotency:
    """Patching the same file twice yields identical results."""

    def test_repeated_patch_never_retains_staged_data_alias_after_source_deletion(
        self, sample_pyproject_path, tmp_path
    ):
        """A repeated patch removes a data alias whose source was deleted."""
        source = tmp_path / "nWave" / "data"
        source.mkdir(parents=True)
        (source / "orchestrator-affordance").mkdir()
        (source / "orchestrator-affordance" / "standing-loops.md").write_text(
            "keep the loop standing\n",
            encoding="utf-8",
        )
        staged = tmp_path / ".nwave-wheel-assets" / "data"
        output_path = str(tmp_path / "out.toml")

        patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )

        # Model a staged copy left by an earlier successful patch. The repeated
        # patch owns cleanup even when the current source has disappeared.
        if not staged.exists():
            shutil.copytree(source, staged)
        shutil.rmtree(source)

        patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )

        assert not staged.exists()

    def test_repeated_patch_removes_staged_template_alias_when_source_is_deleted(
        self, sample_pyproject_path, tmp_path
    ):
        """A repeated patch cannot retain templates deleted from the source.

        CONTRACT_SHAPE: bounded-change
        Outcome anchor: EXP-fix-codex-bootstrap-spine-1 (Expected observations).
        """
        source = tmp_path / "nWave" / "templates"
        source.mkdir(parents=True)
        (source / "role.md").write_text("portable role\n", encoding="utf-8")
        staged = tmp_path / ".nwave-wheel-assets" / "templates"
        output_path = str(tmp_path / "out.toml")

        patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )
        assert (staged / "role.md").is_file()

        (source / "role.md").unlink()
        source.rmdir()
        patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )

        assert not staged.exists()

    def test_repeated_patch_removes_staged_catalog_alias_when_source_is_deleted(
        self, sample_pyproject_path, tmp_path
    ):
        """A repeated patch cannot retain a catalog deleted from the source.

        CONTRACT_SHAPE: bounded-change
        Outcome anchor: EXP-fix-codex-bootstrap-spine-1 (Expected observations).
        """
        source = tmp_path / "nWave" / "framework-catalog.yaml"
        source.parent.mkdir(parents=True)
        source.write_text("name: public\n", encoding="utf-8")
        staged = tmp_path / ".nwave-wheel-assets" / "framework-catalog.yaml"
        output_path = str(tmp_path / "out.toml")

        patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )
        assert staged.is_file()

        source.unlink()
        patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_path,
            target_name="nwave-ai",
            target_version="1.1.22",
        )

        assert not staged.exists()

    def test_double_patch_is_idempotent(self, sample_pyproject_path, tmp_path):
        """Given a source pyproject.toml is patched once to output_a,
        when output_a is patched again with the same parameters to output_b,
        then output_a and output_b are identical.
        """
        output_a = str(tmp_path / "a.toml")
        output_b = str(tmp_path / "b.toml")

        patch_pyproject(
            input_path=sample_pyproject_path,
            output_path=output_a,
            target_name="nwave-ai",
            target_version="1.1.22",
        )
        patch_pyproject(
            input_path=output_a,
            output_path=output_b,
            target_name="nwave-ai",
            target_version="1.1.22",
        )
        content_a = (tmp_path / "a.toml").read_text()
        content_b = (tmp_path / "b.toml").read_text()
        assert content_a == content_b


class TestErrorHandling:
    """Malformed input and parse error handling."""

    def test_missing_source_file_returns_error(self, tmp_path):
        """Given --source-pyproject points to a non-existent file,
        then exit code is 1 and message indicates file not found.
        """
        from scripts.release.patch_pyproject import PatchError

        with pytest.raises(PatchError, match="not found"):
            patch_pyproject(
                input_path=str(tmp_path / "nonexistent.toml"),
                output_path=str(tmp_path / "out.toml"),
                target_name="nwave-ai",
                target_version="1.1.22",
            )

    def test_malformed_toml_returns_parse_error(self, tmp_path):
        """Given --source-pyproject points to a file with invalid TOML,
        then exit code is 1 and message indicates parse error.
        """
        from scripts.release.patch_pyproject import PatchError

        bad_toml = tmp_path / "bad.toml"
        bad_toml.write_text("[project\nname = broken")
        with pytest.raises(PatchError, match="parse"):
            patch_pyproject(
                input_path=str(bad_toml),
                output_path=str(tmp_path / "out.toml"),
                target_name="nwave-ai",
                target_version="1.1.22",
            )

    def test_missing_project_name_returns_error(self, tmp_path):
        """Given pyproject.toml has no [project] name field,
        then exit code is 1 and message indicates missing field.
        """
        from scripts.release.patch_pyproject import PatchError

        no_name = tmp_path / "noname.toml"
        no_name.write_text('[project]\nversion = "1.0.0"\n')
        with pytest.raises(PatchError, match="missing.*name"):
            patch_pyproject(
                input_path=str(no_name),
                output_path=str(tmp_path / "out.toml"),
                target_name="nwave-ai",
                target_version="1.1.22",
            )

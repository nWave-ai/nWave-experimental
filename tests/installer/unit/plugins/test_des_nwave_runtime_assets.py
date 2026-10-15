"""Regression: DES install ships nWave runtime assets to <claude_dir>/lib/nWave/.

F-DES-INSTALL-SHIPS-NWAVE-RUNTIME-ASSETS — the installed des package resolves
config siblings of lib/python at runtime (Path(__file__).parents[N] / "nWave" /
...): installed readers consume nWave/data/, nWave/templates/ and
nWave/framework-catalog.yaml. These tests pin that exact
live asset set without preserving retired workflow registries.
"""

from pathlib import Path
from unittest.mock import MagicMock

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.des_plugin import DESPlugin


def _context_with_nwave(base: Path) -> tuple[InstallContext, Path]:
    """Build an InstallContext whose project_root/nWave carries runtime assets."""
    project_root = base / "project"
    nwave = project_root / "nWave"
    (nwave / "data").mkdir(parents=True)
    (nwave / "data" / "doctor.json").write_text("{}\n")
    (nwave / "templates").mkdir(parents=True)
    (nwave / "templates" / "AGENT_TEMPLATE.md").write_text("# template\n")
    (nwave / "framework-catalog.yaml").write_text("agents: []\n")

    claude_dir = base / ".claude"
    claude_dir.mkdir(parents=True)
    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=base / "scripts",
        templates_dir=nwave / "templates",
        logger=MagicMock(),
        project_root=project_root,
        framework_source=None,
    )
    return context, claude_dir


def test_runtime_assets_shipped_to_lib_nwave(tmp_path: Path) -> None:
    """The live data, template dirs + catalog land under lib/nWave/."""
    context, claude_dir = _context_with_nwave(tmp_path)

    DESPlugin()._install_nwave_runtime_assets(context=context, using_prebuilt=False)

    lib_nwave = claude_dir / "lib" / "nWave"
    assert (lib_nwave / "data" / "doctor.json").is_file()
    assert (lib_nwave / "templates" / "AGENT_TEMPLATE.md").is_file()
    assert (lib_nwave / "framework-catalog.yaml").is_file()
    assert not (lib_nwave / "flavors").exists()
    assert not (lib_nwave / "hooks").exists()


def test_missing_nwave_source_skips_without_crash(tmp_path: Path) -> None:
    """A pre-built tree without a co-located nWave/ is a logged skip, not a crash.

    Named residue: the dist/PyPI path does not yet carry these assets beside its
    des package; the installer must degrade gracefully there, not raise.
    """
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=tmp_path / "scripts",
        templates_dir=tmp_path / "templates",
        logger=MagicMock(),
        project_root=tmp_path / "absent-project",  # no nWave/ here
        framework_source=None,
    )

    # Must not raise.
    DESPlugin()._install_nwave_runtime_assets(context=context, using_prebuilt=False)

    assert not (claude_dir / "lib" / "nWave").exists()


def test_dry_run_ships_nothing(tmp_path: Path) -> None:
    """Dry-run reports intent without writing assets."""
    context, claude_dir = _context_with_nwave(tmp_path)
    context.dry_run = True

    DESPlugin()._install_nwave_runtime_assets(context=context, using_prebuilt=False)

    assert not (claude_dir / "lib" / "nWave").exists()


def test_nested_wheel_runtime_uses_flat_des_templates_when_required(
    tmp_path: Path,
) -> None:
    """A public wheel keeps DES prerequisites and runtime templates coherent.

    Hatch normalizes two force-include keys differing only by a trailing slash
    to one source path.  The wheel must therefore carry templates flat for the
    DES prerequisite, while the nested runtime tier falls back to that same
    canonical source when it populates ``lib/nWave/templates``.
    """
    framework_source = tmp_path / "site-packages" / "nWave"
    nested = framework_source / "nWave"
    (nested / "data").mkdir(parents=True)
    (nested / "data" / "doctor.json").write_text("{}\n")
    (nested / "framework-catalog.yaml").write_text("agents: []\n")
    (framework_source / "templates").mkdir(parents=True)
    (framework_source / "templates" / ".pre-commit-config-nwave.yaml").write_text(
        "repos: []\n"
    )

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=tmp_path / "scripts",
        templates_dir=framework_source / "templates",
        logger=MagicMock(),
        project_root=None,
        framework_source=framework_source,
    )

    DESPlugin()._install_nwave_runtime_assets(context=context, using_prebuilt=True)

    expected = (
        claude_dir / "lib" / "nWave" / "templates" / ".pre-commit-config-nwave.yaml"
    )
    assert expected.is_file(), (
        f"WHAT  {expected} was not created.\n"
        "WHY   Hatch normalizes the two force-include keys "
        "('nWave/templates' and its build alias) to the SAME source "
        "path, so `_install_nwave_runtime_assets` must fall back to the "
        "flat `framework_source / 'templates'` tree when populating "
        "`lib/nWave/templates` for a nested wheel runtime -- that "
        "fallback did not fire (or fired against the wrong source).\n"
        "HOW   Inspect `DESPlugin._install_nwave_runtime_assets` "
        "(scripts/install/plugins/des_plugin.py) for the branch that "
        "populates `lib/nWave/templates` under `using_prebuilt=True`; "
        "confirm it reads from `context.templates_dir` "
        "(here: framework_source/templates), not from the nested "
        "`framework_source/nWave/...` tree that only carries `data` and "
        "`framework-catalog.yaml` in this fixture."
    )


def test_public_wheel_data_tier_installs_without_a_development_checkout(
    tmp_path: Path,
) -> None:
    """The packaged data tier serves an all-target install from its wheel alone."""
    framework_source = tmp_path / "site-packages" / "nWave"
    packaged_data = framework_source / "nWave" / "data"
    packaged_data.mkdir(parents=True)
    (packaged_data / "orchestrator-affordance.yaml").write_text("entries: []\n")
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=tmp_path / "scripts",
        templates_dir=framework_source / "templates",
        logger=MagicMock(),
        project_root=None,
        framework_source=framework_source,
    )

    result = DESPlugin()._install_des_data(context)

    assert result.success is True, result.message
    assert (claude_dir / "data" / "orchestrator-affordance.yaml").is_file()


def _runtime_message(what: str, how: str) -> str:
    return (
        f"WHAT: {what}. WHY: runtime role families must be public-only in every "
        f"channel, independently of host dev_mode. HOW: {how}."
    )


def _family_snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def _synthetic_runtime_tier(base: Path, channel: str, selection: str):
    """Synthetic private sentinels avoid freezing any real private source."""
    import logging

    import yaml

    project = base / "source"
    framework = project / "nWave" if channel == "checkout" else base / channel
    tier = framework / "nWave" if channel == "wheel" else framework
    agents = framework / "agents" / "nw" if channel == "dist" else framework / "agents"
    skills = framework / "skills"
    agents.mkdir(parents=True)
    skills.mkdir(parents=True)
    (tier / "data").mkdir(parents=True)
    (tier / "data" / "probe.json").write_text("{}\n")
    (framework / "templates").mkdir(parents=True)
    (framework / "templates" / "probe.tmpl").write_text("public template\n")
    catalog = {
        "agents": (
            {}
            if selection == "empty"
            else {
                "public-probe": {"public": selection == "public"},
                "PRIVATE-runtime-probe": {"public": False},
            }
        ),
        "skills": {"nw-PRIVATE-runtime-skill": {"public": False}},
    }
    (tier / "framework-catalog.yaml").write_text(yaml.safe_dump(catalog))
    # Family catalog lookup uses the canonical framework tier, even when the
    # wheel runtime's data/hooks reside under its nested nWave child.
    if tier != framework:
        (framework / "framework-catalog.yaml").write_text(yaml.safe_dump(catalog))
        (tier / "hooks").mkdir()
        (tier / "hooks" / "old-hook.py").write_text("# wheel hooks\n")
    for name, owned_skills in (
        ("nw-public-probe", ["nw-public-probe-skill", "nw-PRIVATE-runtime-skill"]),
        ("nw-PRIVATE-runtime-probe", ["nw-PRIVATE-runtime-skill"]),
        ("nw-uncatalogued-probe", ["nw-uncatalogued-probe-skill"]),
    ):
        metadata = {
            "name": name,
            "description": "synthetic role",
            "skills": owned_skills,
        }
        (agents / f"{name}.md").write_text(
            "---\n"
            + yaml.safe_dump(metadata, sort_keys=False)
            + "---\nPublic probe body.\n"
        )
    for name in (
        "nw-public-probe-skill",
        "nw-PRIVATE-runtime-skill",
        "nw-uncatalogued-probe-skill",
        "nw-command-probe",
    ):
        directory = skills / name
        directory.mkdir()
        metadata = {
            "name": name,
            "description": "synthetic skill",
            "user-invocable": False,
        }
        if name != "nw-command-probe":
            metadata["disable-model-invocation"] = True
        (directory / "SKILL.md").write_text(
            "---\n" + yaml.safe_dump(metadata) + "---\nPublic probe knowledge.\n"
        )
    module = (
        project / "src" / "des"
        if channel == "checkout"
        else framework / "lib" / "python" / "des"
    )
    module.mkdir(parents=True)
    (module / "__init__.py").write_text('"""Synthetic copy-boundary input."""\n')
    home = base / "home"
    home.mkdir()
    context = InstallContext(
        claude_dir=home / ".claude",
        scripts_dir=project / "scripts",
        templates_dir=framework / "templates",
        logger=logging.getLogger("runtime-public-family-observation"),
        project_root=project if channel == "checkout" else None,
        framework_source=framework,
    )
    return context, framework, tier, agents, skills, home


def _expected_public_families(tier: Path, agents: Path, skills: Path):
    from scripts.shared.agent_catalog import (
        build_ownership_map,
        detect_command_skills,
        is_public_agent,
        load_private_skills,
        load_public_agents,
    )
    from scripts.shared.skill_distribution import enumerate_skills, filter_public_skills

    public = load_public_agents(tier)
    if not public:
        return set(), set()
    return (
        {
            path.name
            for path in agents.glob("*.md")
            if is_public_agent(path.name, public)
        },
        {
            entry.name
            for entry in filter_public_skills(
                enumerate_skills(skills),
                public,
                build_ownership_map(agents),
                detect_command_skills(skills),
                load_private_skills(tier),
            )
        },
    )


def _assert_public_runtime_families(root: Path, expected):
    import yaml

    expected_agents, expected_skills = expected
    actual_agents = {path.name for path in (root / "agents").glob("*.md")}
    actual_skills = (
        {path.name for path in (root / "skills").iterdir() if path.is_dir()}
        if (root / "skills").is_dir()
        else set()
    )
    assert (actual_agents, actual_skills) == expected, _runtime_message(
        f"emitted agent/skill populations differ: actual={(actual_agents, actual_skills)}, "
        f"expected={(expected_agents, expected_skills)}",
        "copy only the explicitly catalog-selected canonical source families; "
        "treat an empty public set as empty at the emitter, not at include-all helpers",
    )
    for name in actual_agents:
        text = (root / "agents" / name).read_text()
        frontmatter = yaml.safe_load(text.split("---", 2)[1])
        assert "nw-PRIVATE-runtime-skill" not in frontmatter.get("skills", []), (
            _runtime_message(
                f"{name} still declares a removed private skill",
                "scrub removed skill references only in the runtime destination copy",
            )
        )
    if expected_agents:
        assert (root / "agents" / "nw-public-probe.md").is_file(), _runtime_message(
            "the public role was not shipped",
            "do not obtain privacy by dropping the public family",
        )


def test_runtime_family_emission_is_public_and_source_preserving_in_each_channel(
    tmp_path: Path, monkeypatch
) -> None:
    """Closed channel/visibility controls use the real filesystem emitter."""
    import itertools

    cases = itertools.product(
        ("checkout", "wheel", "dist"),
        (False, True),
        ("public", "empty", "private-only"),
    )
    for channel, dev_mode, selection in cases:
        case = tmp_path / f"{channel}-{dev_mode}-{selection}"
        case.mkdir()
        context, framework, tier, agents, skills, home = _synthetic_runtime_tier(
            case, channel, selection
        )
        context.dev_mode = dev_mode
        expected = _expected_public_families(tier, agents, skills)
        before = _family_snapshot(framework)
        with monkeypatch.context() as environment:
            environment.setenv("HOME", str(home))
            environment.setenv("NWAVE_AGENTS_HOME", str(home))
            context.target_platforms = {"omp"}
            shipped = DESPlugin()._install_nwave_runtime_assets(
                context=context, using_prebuilt=channel != "checkout"
            )
        assert shipped == home / ".nwave" / "nWave", _runtime_message(
            f"{channel} emitter did not return its observed runtime root: {shipped}",
            "emit the admitted tier beside the host-neutral des package",
        )
        _assert_public_runtime_families(shipped, expected)
        assert _family_snapshot(framework) == before, _runtime_message(
            f"{channel} source tier changed after runtime emission",
            "apply filtering and reference scrubbing to the destination only",
        )


def test_mixed_target_mirrors_the_same_public_runtime_families(
    tmp_path: Path, monkeypatch
) -> None:
    for dev_mode in (False, True):
        case = tmp_path / str(dev_mode)
        case.mkdir()
        context, framework, tier, agents, skills, home = _synthetic_runtime_tier(
            case, "checkout", "public"
        )
        context.dev_mode = dev_mode
        context.target_platforms = {"claude_code", "codex", "omp"}
        before = _family_snapshot(framework)
        expected = _expected_public_families(tier, agents, skills)
        with monkeypatch.context() as environment:
            environment.setenv("HOME", str(home))
            environment.setenv("NWAVE_AGENTS_HOME", str(home))
            result = DESPlugin()._install_des_module(context)
        assert result.success, _runtime_message(
            f"mixed runtime install refused: {result.message}",
            "retain the real module install and its runtime asset mirror",
        )
        primary = home / ".claude" / "lib" / "nWave"
        mirror = home / ".nwave" / "nWave"
        _assert_public_runtime_families(primary, expected)
        _assert_public_runtime_families(mirror, expected)
        assert _family_snapshot(primary) == _family_snapshot(mirror), _runtime_message(
            "mixed target runtime asset bytes differ between primary and mirror",
            "mirror the already-filtered runtime asset tree without widening visibility",
        )
        assert _family_snapshot(framework) == before, _runtime_message(
            "mixed install scrubbed or rewrote its source role families",
            "never mutate the source tier while preparing runtime copies",
        )


def test_empty_public_catalog_is_not_an_unavailable_catalog(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    import logging
    import re

    import pytest

    from scripts.shared.agent_catalog import CatalogParseError, load_public_agents

    context, framework, tier, _, _, home = _synthetic_runtime_tier(
        tmp_path, "checkout", "empty"
    )
    context.target_platforms = {"omp"}
    catalog = tier / "framework-catalog.yaml"
    legal_bytes = catalog.read_bytes()
    installer = DESPlugin()
    installed_root = home / ".nwave" / "nWave"
    with monkeypatch.context() as environment:
        environment.setenv("HOME", str(home))
        environment.setenv("NWAVE_AGENTS_HOME", str(home))
        assert load_public_agents(tier) == set(), _runtime_message(
            "valid empty public catalog was not observed as empty",
            "retain strict catalog loading and handle its valid empty result at the emitter",
        )
        before = _family_snapshot(framework)
        legal = installer._install_des_module(context)
        assert legal.success and installed_root.is_dir(), _runtime_message(
            f"capable legal-empty module installer refused: {legal.message}",
            "establish the admitted control through the same module-install "
            "surface used by unavailable and unparseable catalog observations",
        )
        _assert_public_runtime_families(installed_root, (set(), set()))
        assert _family_snapshot(framework) == before, _runtime_message(
            "legal-empty module install changed its source tier",
            "filter only the runtime destination copy",
        )

        try:
            catalog.unlink()
            before_missing = _family_snapshot(framework)
            caplog.clear()
            with caplog.at_level(logging.WARNING, logger=context.logger.name):
                unavailable = installer._install_des_module(context)
            warnings = [
                record.getMessage()
                for record in caplog.records
                if record.name == context.logger.name
                and record.levelno >= logging.WARNING
            ]
            catalog_unavailable = any(
                str(tier) in warning
                and catalog.name in warning
                and "N/A" in warning
                and "not" in warning.lower()
                and "tier" in warning.lower()
                for warning in warnings
            )
            assert unavailable.success and catalog_unavailable, _runtime_message(
                "missing catalog did not produce the existing source-tier "
                "unavailability diagnostic on the capable module-install surface",
                "retain the warning naming this tier and framework-catalog.yaml "
                "as unavailable/not applicable; do not accept unrelated warnings",
            )
            _assert_public_runtime_families(installed_root, (set(), set()))
            assert _family_snapshot(framework) == before_missing, _runtime_message(
                "unavailable-catalog module install changed the source tier",
                "observe missing input without repairing or rewriting source files",
            )

            catalog.write_text("agents: [unterminated")
            # Establish the specific malformed-input cause independently at
            # the existing strict catalog port, not from any installer error.
            with pytest.raises(CatalogParseError) as parse_failure:
                load_public_agents(tier)
            assert str(catalog) in str(parse_failure.value), _runtime_message(
                "strict catalog parse failure does not identify the challenged file",
                "preserve the concrete catalog locator in the existing diagnostic",
            )
            before_broken = _family_snapshot(framework)
            caplog.clear()
            broken = installer._install_des_module(context)
            catalog_parse_failure = (
                not broken.success
                and str(catalog) in broken.message
                and bool(
                    re.search(
                        r"\b(?:parse|parsing|yaml|CatalogParseError)\b",
                        broken.message,
                        re.IGNORECASE,
                    )
                )
            )
            assert catalog_parse_failure, _runtime_message(
                "malformed catalog did not produce a failure naming the exact "
                "catalog file and its parse/YAML cause",
                "propagate the strict catalog-observation cause through the "
                "same previously capable module installer; an unrelated "
                "nonempty refusal message is not this observation",
            )
            _assert_public_runtime_families(installed_root, (set(), set()))
            assert _family_snapshot(framework) == before_broken, _runtime_message(
                "malformed-catalog module install changed the source tier",
                "leave malformed source input untouched on refusal",
            )
        finally:
            catalog.write_bytes(legal_bytes)

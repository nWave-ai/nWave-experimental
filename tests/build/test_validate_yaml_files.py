"""The YAML hook validates authored project files, not generated run state."""

from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "validation" / "validate_yaml_files.py"


def _load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_yaml_files", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_project_yaml_is_validated_while_generated_trees_are_pruned(tmp_path):
    """A real malformed YAML file still fails; retained run fixtures do not."""
    validator_module = _load_validator_module()
    root = tmp_path / "project"
    source_yaml = root / "new-project-file.yaml"
    generated_yamls = [
        root / ".nwave" / "recovery" / "captured-fixture.yaml",
        root / ".nwave" / "worktrees" / "lane" / "fixture.yml",
        root / ".venv" / "generated.yml",
    ]
    source_yaml.parent.mkdir(parents=True)
    source_yaml.write_text("project: [\n", encoding="utf-8")
    for generated_yaml in generated_yamls:
        generated_yaml.parent.mkdir(parents=True, exist_ok=True)
        generated_yaml.write_text("fixture: [\n", encoding="utf-8")

    validator = validator_module.YAMLValidator(root)

    assert validator.find_yaml_files() == [source_yaml]
    assert validator.validate_all() is False
    assert [path for path, _error in validator.errors] == [
        Path("new-project-file.yaml")
    ]

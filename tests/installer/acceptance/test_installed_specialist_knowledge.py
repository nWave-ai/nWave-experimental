"""Installed native specialists carry mandatory knowledge once, never on-demand knowledge.

Drives AgentsPlugin.install (Claude) and CodexAgentsPlugin.install (Codex)
through isolated InstallContext; no real HOME, no provider invocation.
"""

import hashlib
import json
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import tomllib

from scripts.install.plugins.agents_plugin import AgentsPlugin
from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.codex_agents_plugin import CodexAgentsPlugin
from scripts.install.plugins.codex_des_plugin import _build_hook_entry
from scripts.install.plugins.opencode_common import parse_frontmatter


SKILL_TEXT = "---\nname: nw-alpha\ndescription: test\n---\nALPHA MANDATORY KNOWLEDGE\n"
CONDITIONAL_TEXT = (
    "---\nname: nw-conditional\ndescription: t\n---\nCONDITIONAL SECRET\n"
)
ROLE = (
    "---\nname: nw-foo\ndescription: Some agent\ntools: Read\n"
    "skills:\n  - nw-alpha\n  - nw-alpha\n---\n# Role\n"
    "Invoke Skill(nw-conditional) only when the named condition holds.\n"
)
ROLE_MISSING = ROLE.replace(
    "  - nw-alpha\n  - nw-alpha\n", "  - nw-alpha\n  - nw-missing\n"
)


class _Env:
    def __init__(self, provider, layout, tmp_path, monkeypatch):
        self.provider, self.layout = provider, layout
        project = tmp_path / "project"
        (project / "nWave").mkdir(parents=True)
        (project / "nWave" / "framework-catalog.yaml").write_text("agents: {}\n")
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        dist = tmp_path / "dist"
        if layout == "source":
            self.agents = project / "nWave" / "agents"
            self.skills = project / "nWave" / "skills"
            framework = tmp_path / "framework"
        else:
            self.agents = dist / "agents" / "nw"
            self.skills = dist / "skills"
            framework = dist
        self.agents.mkdir(parents=True)
        for name, text in (
            ("nw-alpha", SKILL_TEXT),
            ("nw-conditional", CONDITIONAL_TEXT),
        ):
            (self.skills / name).mkdir(parents=True)
            (self.skills / name / "SKILL.md").write_text(text, encoding="utf-8")
        self.context = InstallContext(
            claude_dir=claude_dir,
            scripts_dir=tmp_path / "scripts",
            templates_dir=tmp_path / "templates",
            logger=MagicMock(),
            project_root=project,
            framework_source=framework,
            dev_mode=True,
        )
        codex = tmp_path / "home" / ".codex" / "agents"
        codex.parent.mkdir(parents=True)
        base = "scripts.install.plugins.codex_agents_plugin."
        monkeypatch.setattr(base + "_codex_agents_dir", lambda: codex)
        monkeypatch.setattr(base + "_codex_config_dir", lambda: codex.parent)
        self.codex = codex
        self.installed_dir = (
            claude_dir / "agents" / "nw" if provider == "claude" else codex
        )
        self.installed = self.installed_dir / (
            "nw-foo.md" if provider == "claude" else "nw-foo.toml"
        )

    def write_role(self, text, name="nw-foo"):
        text = text.replace("name: nw-foo", f"name: {name}")
        (self.agents / f"{name}.md").write_text(text, encoding="utf-8")
        return (self.agents / f"{name}.md").read_bytes()

    def snapshot(self):
        """Every installed byte under the provider's agent directory, manifest included."""
        return {
            str(path.relative_to(self.installed_dir)): path.read_bytes()
            for path in sorted(self.installed_dir.rglob("*"))
            if path.is_file()
        }

    def install(self):
        plugin = AgentsPlugin() if self.provider == "claude" else CodexAgentsPlugin()
        return plugin.install(self.context)

    def body(self):
        raw = self.installed.read_text(encoding="utf-8")
        if self.provider == "codex":
            return tomllib.loads(raw)["developer_instructions"]
        return raw


@pytest.fixture(params=["claude", "codex"])
def provider(request):
    return request.param


@pytest.fixture(params=["source", "distribution"])
def env(request, provider, tmp_path, monkeypatch):
    return _Env(provider, request.param, tmp_path, monkeypatch)


def test_installed_role_preloads_mandatory_knowledge_once_and_keeps_conditional_on_demand(
    env,
):
    source_before = env.write_role(ROLE)

    result = env.install()

    assert result.success is True, f"install must succeed: {result.message}"
    body = env.body()
    assert (
        body.count(SKILL_TEXT) == 1 or body.count("ALPHA MANDATORY KNOWLEDGE") == 1
    ), (
        "Mandatory skill (declared twice) must be materialized exactly once; "
        "WHY: doubled knowledge wastes paid context; HOW: dedupe declarations in the loader."
    )
    assert body.count("ALPHA MANDATORY KNOWLEDGE") == 1
    assert "CONDITIONAL SECRET" not in body, "conditional skill must stay on-demand"
    assert "nw-conditional" in body, "conditional read instruction must survive"
    deployed_skills = (
        str(env.context.claude_dir / "skills")
        if env.provider == "claude"
        else "~/.agents/skills"
    )
    assert f"{deployed_skills}/nw-conditional/SKILL.md" in body
    for leak in (str(env.skills), str(env.agents), str(env.context.project_root)):
        assert leak not in body, f"installed role leaks build path {leak}"
    assert (env.agents / "nw-foo.md").read_bytes() == source_before, (
        "source bytes must be unchanged"
    )

    if env.provider == "claude":
        frontmatter, _ = parse_frontmatter(body)
        assert "skills" not in frontmatter, (
            "installed Claude frontmatter must not ask the host to reload materialized skills"
        )
        assert str(frontmatter["tools"]).strip() == "Read", (
            "tools boundary must be unchanged"
        )
    else:
        assert "Declared tools: Read" in body, "tools boundary must be unchanged"
        assert "Write/Edit ->" not in body

    # Idempotent reinstall must not double preloaded knowledge.
    assert env.install().success is True
    assert env.body().count("ALPHA MANDATORY KNOWLEDGE") == 1


def test_missing_mandatory_skill_fails_install_and_preserves_existing_role(env):
    env.write_role(ROLE)
    env.write_role(ROLE, name="nw-zeta")
    assert env.install().success is True
    installed_before = env.snapshot()
    assert len(installed_before) >= 2, "both valid roles must be installed first"

    # The LATER sorted role loses a mandatory skill; the earlier one stays valid.
    source_before = env.write_role(ROLE_MISSING, name="nw-zeta")
    result = env.install()

    assert result.success is False, (
        "missing mandatory skill must fail installation before any paid turn"
    )
    assert "nw-missing" in result.message, (
        "failure must name the missing skill so the maintainer can add it"
    )
    assert env.snapshot() == installed_before, (
        "the whole installed agent directory, manifest included, must be "
        "preserved when a later role fails to render"
    )
    assert (env.agents / "nw-zeta.md").read_bytes() == source_before


def test_legacy_alias_render_failure_preserves_installed_codex_agents(env):
    if env.provider != "codex":
        pytest.skip("legacy aliases exist only for Codex")
    # Only alias rendering can fail: the catalog excludes the canonical source.
    (env.context.project_root / "nWave" / "framework-catalog.yaml").write_text(
        "agents:\n  foo:\n    public: true\n", encoding="utf-8"
    )
    env.context.dev_mode = False
    env.write_role(ROLE)
    env.write_role(ROLE_MISSING, name="nw-software-crafter")

    # Exact pre-manifest DES ownership witness for the legacy alias bootstrap.
    python_path, pythonpath = "/legacy/bin/python", "/legacy/src"
    config_dir = env.codex.parent
    hooks_path = config_dir / "hooks.json"
    command = _build_hook_entry(python_path, pythonpath)["hooks"][0]["command"]
    hooks_path.write_text(
        json.dumps({"hooks": {"PreToolUse": [{"hooks": [{"command": command}]}]}}),
        encoding="utf-8",
    )
    (config_dir / ".nwave-des-manifest.json").write_text(
        json.dumps(
            {
                "hooks_file": str(hooks_path),
                "python_path": python_path,
                "pythonpath": pythonpath,
            }
        ),
        encoding="utf-8",
    )
    env.codex.mkdir(exist_ok=True)
    (env.codex / "nw-crafter.toml").write_text("legacy = true\n", encoding="utf-8")
    before = env.snapshot()

    result = env.install()

    assert result.success is False, "legacy alias render failure must fail install"
    assert "nw-missing" in result.message, "failure must name the missing skill"
    assert env.snapshot() == before, (
        "failed alias render must leave the codex agents directory untouched"
    )


@pytest.mark.parametrize("shared", [False, True])
def test_recovery_packet_seals_current_design_and_preserves_immutable_content_identity(
    tmp_path: Path, shared: bool
):
    from tests.des.acceptance.distill_document_construction.test_distill_document_construction import (
        _call,
        _shared_manifest,
        _Subject,
        _value_manifest,
    )
    from tests.des.acceptance.steps_for_the_orchestrator.conftest import block

    subject = _Subject(tmp_path, None, shared=shared).designed()
    expected_shared_semantic_sha256 = None
    if shared:
        code, out, err = _call(
            subject.root, "design", json.dumps(_shared_manifest()), shared=True
        )
        assert code == 0, out + err
        identities = block(out, err)
        expected_shared_semantic_sha256 = identities["SEMANTIC-SHA256"]
    subject.select("blue")
    subject.select("green", replace=True)
    finding = "Realign selected acceptance with current DESIGN."

    def prepare():
        return subject.step(
            "prepare-role",
            "--repo-root",
            str(subject.root),
            "--role",
            "acceptance-designer",
            "--task",
            "selected-revision-recovery",
            "--value",
            "1",
            "--finding",
            "-",
            stdin=finding,
        )

    sealed = []
    for color in ("green", "amber"):
        expected_observation = f"stdout is {color} and exit is zero."
        code, out, err = _call(
            subject.root,
            "design",
            json.dumps(_value_manifest(expected=expected_observation)),
            value=1,
            replace_current=True,
        )
        assert code == 0, out + err
        current_design_semantic_sha256 = block(out, err)["SEMANTIC-SHA256"]
        code, out, err = prepare()
        assert code == 0, out + err
        lines = block(out, err)
        path = subject.root / lines["INPUT"]
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert lines["INPUT-SHA256"] == digest
        assert re.findall(r"[0-9a-f]{64}", path.name) == [digest]
        packet = json.loads(raw)
        assert packet["finding"] == finding
        assert packet["value_design_semantic_sha256"] == current_design_semantic_sha256
        assert (
            packet["shared_design_semantic_sha256"] == expected_shared_semantic_sha256
        )
        for earlier_path, earlier_raw, earlier_packet in sealed:
            assert earlier_path.read_bytes() == earlier_raw
            assert (
                packet["value_design_semantic_sha256"]
                != (earlier_packet["value_design_semantic_sha256"])
            )
        sealed.append((path, raw, packet))

        # Repreparing unchanged authority/finding reuses the same sealed bytes.
        code, out, err = prepare()
        assert code == 0, out + err
        repeated = block(out, err)
        assert subject.root / repeated["INPUT"] == path
        assert repeated["INPUT-SHA256"] == digest
        assert path.read_bytes() == raw

    # A corrupt existing packet is neither silently replaced nor accepted.
    path, raw, _ = sealed[-1]
    tampered = raw.replace(finding.encode(), b"A different unsealed finding.")
    path.write_bytes(tampered)
    code, out, err = prepare()
    assert code != 0
    assert block(out, err)["WHAT"] == "RoleInputAlreadyPrepared"
    assert path.read_bytes() == tampered


def test_selected_revision_recovery_refuses_legacy_semantic_bound_facts_without_public_oracle(
    tmp_path: Path,
):
    """Legacy semantic-bound value DESIGN facts predate the public-oracle projection.

    When a value was bound with the closed DESIGN constructor before this
    correction existed, its authority has no public_oracle field. If later
    re-submitted unchanged, the handover projection gains public_oracle and the
    selection basis remains stable (step 4 of the correction: design_basis_sha256
    excludes public_oracle). Recovery must refuse such a state to prevent
    silently sealing an input that hides the current expected observation.
    """
    from tests.common.in_process_cli import run_cli_in_process
    from tests.des.acceptance.distill_document_construction.test_distill_document_construction import (
        _call,
        _Subject,
        _value_manifest,
    )

    subject = _Subject(tmp_path, None, shared=False).designed()
    subject.select("blue")
    subject.select("green", replace=True)

    # Design change after selection
    code, out, err = _call(
        subject.root,
        "design",
        json.dumps(_value_manifest(expected="stdout is green and exit is zero.")),
        value=1,
        replace_current=True,
    )
    assert code == 0, out + err

    # Strip public_oracle from the bound authority to simulate legacy state
    handover_path = subject.root / ".nwave/des/handover.json"
    payload = json.loads(handover_path.read_text())
    del payload["values"][0]["authority"]["public_oracle"]
    payload["values"][0]["design_semantic_sha256"] = (
        payload["values"][0].get("design_semantic_sha256") or "non_null"
    )  # Ensure it's non-None to trigger the check
    handover_path.write_text(json.dumps(payload, separators=(",", ":")))

    finding = (
        "DESIGN for value 1 changed after DISTILL B; des oracle --value 1 ended "
        "Indeterminate with SelectedRevisionRealignmentNeeded. Realign the "
        "selected acceptance revision."
    )
    code, out, err = run_cli_in_process(
        [
            "prepare-role",
            "--repo-root",
            str(subject.root),
            "--role",
            "acceptance-designer",
            "--task",
            "selected-revision-recovery",
            "--value",
            "1",
            "--finding",
            "-",
        ],
        cwd=subject.root,
        stdin_text=finding,
        catch_all=True,
    )
    assert code != 0, (
        "WHAT: prepare-role accepted legacy semantic-bound facts without public_oracle. "
        "WHY: such facts predate the projection and would hide the current expected. "
        "HOW: prepare-role must refuse with a Refusal naming the re-bind HOW."
    )
    assert "public-oracle projection" in (out + err), (
        "refusal must name the root cause: the facts predate the projection"
    )
    assert "des design --repo-root ROOT --value N --input -" in (out + err), (
        "refusal must name the re-bind HOW"
    )


def test_selected_revision_recovery_refuses_legacy_semantic_bound_shared_design_facts_without_public_oracle(
    tmp_path: Path,
):
    """Legacy semantic-bound shared DESIGN facts predate the public-oracle projection.

    When a value was bound with the closed DESIGN constructor before this
    correction existed, shared authority has no public_oracle field. If later
    re-submitted unchanged, the handover projection gains public_oracle and the
    selection basis remains stable. Recovery must refuse such a state to prevent
    silently sealing an input that hides the current shared expected observation.

    This test complements the value-only variant: it ensures that shared DESIGN
    facts lacking public_oracle are detected separately from value DESIGN facts.
    """
    from tests.common.in_process_cli import run_cli_in_process
    from tests.des.acceptance.distill_document_construction.test_distill_document_construction import (
        _call,
        _Subject,
        _value_manifest,
    )

    subject = _Subject(tmp_path, None, shared=True).designed()
    subject.select("blue")
    subject.select("green", replace=True)

    # Design change after selection
    code, out, err = _call(
        subject.root,
        "design",
        json.dumps(_value_manifest(expected="stdout is green and exit is zero.")),
        value=1,
        replace_current=True,
    )
    assert code == 0, out + err

    # Strip public_oracle from the shared design to simulate legacy state,
    # while keeping value authority intact to test independent detection
    handover_path = subject.root / ".nwave/des/handover.json"
    payload = json.loads(handover_path.read_text())
    # Verify shared_design exists and has semantic_sha256
    assert payload.get("shared_design") is not None, "test requires shared_design"
    assert payload["shared_design"].get("semantic_sha256") is not None, (
        "test requires shared_design to have semantic_sha256"
    )
    # Delete public_oracle from shared_design's design (DesignFacts)
    if "design" in payload["shared_design"]:
        if "public_oracle" in payload["shared_design"]["design"]:
            del payload["shared_design"]["design"]["public_oracle"]
    # Ensure value authority still has public_oracle (to test independent detection)
    assert payload["values"][0]["authority"].get("public_oracle") is not None, (
        "test requires value authority to keep public_oracle"
    )
    handover_path.write_text(json.dumps(payload, separators=(",", ":")))

    finding = (
        "DESIGN for value 1 changed after DISTILL B; des oracle --value 1 ended "
        "Indeterminate with SelectedRevisionRealignmentNeeded. Realign the "
        "selected acceptance revision."
    )
    code, out, err = run_cli_in_process(
        [
            "prepare-role",
            "--repo-root",
            str(subject.root),
            "--role",
            "acceptance-designer",
            "--task",
            "selected-revision-recovery",
            "--value",
            "1",
            "--finding",
            "-",
        ],
        cwd=subject.root,
        stdin_text=finding,
        catch_all=True,
    )
    assert code != 0, (
        "WHAT: prepare-role accepted legacy semantic-bound shared facts without public_oracle. "
        "WHY: such facts predate the projection and would hide the current expected observation. "
        "HOW: prepare-role must refuse with a Refusal naming the re-bind HOW."
    )
    assert "public-oracle projection" in (out + err), (
        "refusal must name the root cause: the facts predate the projection"
    )
    assert "des design --repo-root ROOT --shared --input -" in (out + err), (
        "refusal must name the re-bind HOW with --shared flag"
    )

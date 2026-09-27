"""Installed native specialists carry mandatory knowledge once, never on-demand knowledge.

Drives AgentsPlugin.install (Claude) and CodexAgentsPlugin.install (Codex)
through isolated InstallContext; no real HOME, no provider invocation.
"""

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import tomllib

from scripts.install.plugins.agents_plugin import AgentsPlugin
from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.codex_agents_plugin import CodexAgentsPlugin
from scripts.install.plugins.codex_des_plugin import _build_hook_entry
from scripts.install.plugins.codex_skills_plugin import CodexSkillsPlugin
from scripts.install.plugins.opencode_common import parse_frontmatter
from scripts.install.plugins.skills_plugin import SkillsPlugin
from tests.common.in_process_cli import run_cli_in_process


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


# --- Installed recovery guidance agrees with DES terminals (Claude and Codex) ---

# Discriminator runs point the same oracle at an isolated copy of the installable
# sources via NWAVE_INSTALL_FIXTURE_SOURCE; default is this repository.
_REPO = Path(
    os.environ.get("NWAVE_INSTALL_FIXTURE_SOURCE")
    or Path(__file__).resolve().parents[3]
)
_RULE_MARKER = "a slice is not ready until the shared decisions it depends on"
_TABLE_HEAD = "**Recovery owners (sole table; other files reference it)."
_PRELOAD = re.compile(
    r"<!-- PRELOADED SKILL START: (?P<name>[\w-]+);.*?<!-- PRELOADED SKILL END: (?P=name)"
    r"[^>]*-->",
    re.S,
)
_CLASSES = (
    "incomplete contract",
    "stale contract",
    "broken substrate",
    "missing product",
)
# terminal closed word -> (class, owner command tokens the row must carry,
# command tokens it must NOT carry). Closed terminal -> owner operation map.
_TERMINALS = {
    "SelectedRevisionIncomplete": (
        "incomplete contract",
        ["des distill --replace-current"],
        ["des craft"],
    ),
    "SelectedRevisionRealignmentNeeded": (
        "stale contract",
        ["preserve", "DISTILL"],
        ["des craft"],
    ),
    "OracleNotRed": ("broken substrate", ["des oracle"], ["des craft"]),
    "OracleRed": ("missing product", ["des craft --value N"], ["des distill"]),
}
# Named owner commands the installed guidance must state (step, exact option token).
_REQUIRED_OPTIONS = {
    ("design", "--shared"),
    ("design", "--feature"),
    ("design", "--value"),
    ("distill", "--replace-current"),
    ("craft", "--value"),
    ("oracle", "--value"),
}
_OPTION = re.compile(r"(?<![\w-])(--[a-z][a-z-]*)(?![\w-])")
_SPAN = re.compile(r"`([^`\n]+)`")
_FENCE = re.compile(r"```.*?```", re.S)


def _install_real_guidance(provider, tmp_path, monkeypatch):
    """Install the repository's real skills and agents into a clean provider home."""
    claude = tmp_path / ".claude"
    claude.mkdir()
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    base = "scripts.install.plugins.codex_agents_plugin."
    monkeypatch.setattr(base + "_codex_agents_dir", lambda: home / ".codex" / "agents")
    monkeypatch.setattr(base + "_codex_config_dir", lambda: home / ".codex")
    sbase = "scripts.install.plugins.codex_skills_plugin."
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(home))
    monkeypatch.setattr(sbase + "_codex_config_dir", lambda: home / ".codex")
    context = InstallContext(
        claude_dir=claude,
        scripts_dir=tmp_path / "scripts",
        templates_dir=tmp_path / "templates",
        logger=MagicMock(),
        project_root=_REPO,
        framework_source=tmp_path / "no-dist",
        dev_mode=True,
    )
    plugins = (
        (SkillsPlugin(), AgentsPlugin())
        if provider == "claude"
        else (CodexSkillsPlugin(), CodexAgentsPlugin())
    )
    for plugin in plugins:
        result = plugin.install(context)
        assert result.success, f"{provider} install failed: {result.message}"
    skills = claude / "skills" if provider == "claude" else home / ".agents" / "skills"
    agents = (
        claude / "agents" / "nw" if provider == "claude" else home / ".codex" / "agents"
    )
    return skills, agents


def _agent_text(agents, name, provider):
    raw = (
        agents / (f"{name}.md" if provider == "claude" else f"{name}.toml")
    ).read_text(encoding="utf-8")
    return tomllib.loads(raw)["developer_instructions"] if provider == "codex" else raw


def _table_rows(auto_text):
    assert _TABLE_HEAD in auto_text, (
        "installed nw-auto lacks the sole recovery table; WHY: the LLM has no owner "
        "map for terminals; HOW: keep the table in nWave/skills/nw-auto/SKILL.md."
    )
    section = auto_text.split(_TABLE_HEAD, 1)[1].split("\n## ", 1)[0]
    return [
        ln
        for ln in section.splitlines()
        if ln.startswith("| ") and not ln.startswith(("| Observed", "|---"))
    ]


def _named_commands(text):
    """(step, options) for every inline code span that names a `des <step>` command."""
    found = []
    for span in _SPAN.findall(_FENCE.sub("", text)):
        match = re.match(r"des ([a-z][a-z-]*)\b(.*)", span.strip(), re.S)
        if match:
            found.append((match.group(1), sorted(set(_OPTION.findall(match.group(2))))))
    return found


def _strip_preloads(body):
    return _PRELOAD.sub("", body)


def test_installed_recovery_guidance_agrees_with_des_terminals_on_claude_and_codex(
    tmp_path, monkeypatch
):
    # Scope: guidance as installed by the real Claude/Codex plugins versus the
    # in-process SOURCE-tree `des <step> --help`. Not a wheel-installed `des` or
    # runtime proof; that belongs to the separate real-host eval.
    seen = {}
    for provider in ("claude", "codex"):
        sub = tmp_path / provider
        sub.mkdir()
        skills, agents = _install_real_guidance(provider, sub, monkeypatch)
        texts = {
            n: (skills / n / "SKILL.md").read_text(encoding="utf-8")
            for n in ("nw-auto", "nw-design", "nw-distill")
        }
        seen[provider] = (texts, skills, agents)

    (tc, _, _), (tx, _, _) = seen["claude"], seen["codex"]
    auto_c, design_c = tc["nw-auto"], tc["nw-design"]
    assert _table_rows(auto_c) == _table_rows(tx["nw-auto"]), (
        "recovery table differs between Claude and Codex installs"
    )
    assert _RULE_MARKER in design_c and _RULE_MARKER in tx["nw-design"], (
        "installed nw-design must own the feature-design rule on both hosts"
    )
    paragraphs = [
        next(x for x in t["nw-design"].split("\n\n") if _RULE_MARKER in x)
        for t in (tc, tx)
    ]
    assert paragraphs[0] == paragraphs[1], (
        "the nw-design rule paragraph differs between hosts"
    )

    # Terminal -> class -> owner mapping, one row each, one class per row.
    rows = _table_rows(auto_c)
    for word, (klass, tokens, forbidden) in _TERMINALS.items():
        matching = [
            r for r in rows if word in r or (word == "OracleRed" and "oracle RED" in r)
        ]
        assert len(matching) == 1, (
            f"{word}: expected exactly one recovery row, found {len(matching)}; "
            "HOW: add or dedupe the row in the nw-auto table"
        )
        row = matching[0]
        assert [c for c in _CLASSES if c in row] == [klass], (
            f"{word} must map to exactly class '{klass}': {row}"
        )
        for token in tokens:
            assert token in row, f"{word} owner cell must name {token!r}: {row}"
        for token in forbidden:
            assert token not in row, f"{word} owner cell must not name {token!r}: {row}"

    # Every named command code span parses under `des <step> --help`, option by exact token.
    named = []
    for provider, (texts, _, _) in seen.items():
        for source in ("nw-auto", "nw-design", "nw-distill"):
            named += _named_commands(texts[source])
    stated = {(step, opt) for step, options in named for opt in options}
    assert stated >= _REQUIRED_OPTIONS, (
        f"installed guidance omits owner commands {sorted(_REQUIRED_OPTIONS - stated)}"
    )
    helps = {}
    for step in sorted({step for step, _ in named}):
        code, out, err = run_cli_in_process([step, "--help"], cwd=tmp_path)
        assert code == 0, f"`des {step} --help` rejected (exit {code}): {err[:200]}"
        helps[step] = set(_OPTION.findall(out))
    for step, options in named:
        for option in options:
            assert option in helps[step], (
                f"installed guidance names {option} for `des {step}` but its --help "
                "does not; HOW: align the guidance with the constructor"
            )

    # The rule has one owner: no other installed skill restates it, and each role
    # reaches nw-design/nw-auto by a real deployed path (or mandatory preload).
    for provider, (texts, skills, agents) in seen.items():
        deployed = str(skills) if provider == "claude" else "~/.agents/skills"
        for path in skills.glob("*/SKILL.md"):
            if path.parent.name == "nw-design":
                continue
            assert _RULE_MARKER not in path.read_text(encoding="utf-8"), (
                f"{provider}: rule restated outside nw-design in {path.name}"
            )
        assert (skills / "nw-design" / "SKILL.md").is_file()
        assert (skills / "nw-auto" / "SKILL.md").is_file()
        skill_home = "~/.claude/skills" if provider == "claude" else "~/.agents/skills"
        assert f"{skill_home}/nw-auto/SKILL.md" in texts["nw-distill"], (
            f"{provider}: nw-distill must reference the nw-auto recovery table by path"
        )
        for name, mandatory in (
            ("nw-solution-architect", True),
            ("nw-solution-architect-reviewer", False),
            ("nw-acceptance-designer", False),
        ):
            body = _agent_text(agents, name, provider)
            resident = _strip_preloads(body)
            assert _RULE_MARKER not in resident, (
                f"{provider}: {name} restates the rule outside preloaded nw-design"
            )
            preloaded = [m.group("name") for m in _PRELOAD.finditer(body)]
            if mandatory:
                assert "nw-design" in preloaded, (
                    f"{provider}: {name} must preload nw-design"
                )
            else:
                assert "nw-design" not in preloaded
                assert f"{deployed}/nw-design/SKILL.md" in resident, (
                    f"{provider}: {name} must reference {deployed}/nw-design/SKILL.md"
                )

    # Limited textual guard only (one phrasing family); real scope efficacy is a
    # separate model eval. The single-value exemption is not observed here.
    for text in (design_c, auto_c):
        assert not re.search(
            r"(?:every|each|all) (?:value|delta|slice)s?\b[^.\n]*"
            r"(?:requires?|needs?|must (?:bind|have)) (?:a )?shared|"
            r"always bind shared first",
            text,
            re.I,
        )


# --- Selected-revision-recovery: acceptance-designer prepare/invoke boundary ---


@pytest.mark.parametrize("shared", [False, True])
def test_selected_revision_recovery_prepares_and_invokes_acceptance_designer_to_yield_a_replayable_v2_document(
    tmp_path: Path, shared: bool
):
    """The declared Value-3 recovery boundary, now deployed.

    Closed design (brief.md, "Installed recovery guidance for Claude and
    Codex"): once `des oracle` is mechanically blocked by
    SelectedRevisionRealignmentNeeded, the one recovery route is
    `des prepare-role --role acceptance-designer --task selected-revision-recovery`
    followed by `des invoke-role`, yielding one typed v2 DistillDocument whose
    exact persisted bytes the caller submits unchanged to
    `des distill --replace-current --input -`. No implicit route or test
    execution occurs. `prepare-role` accepts that role and that task and seals
    the recovery input (`src/des/cli/prepare_role.py`, and
    `role_artifacts.prepare_selected_revision_recovery`), so this observation is
    GREEN: a failure here is a regression, never a missing capability.
    """
    from tests.common.in_process_cli import run_cli_in_process
    from tests.des.acceptance import fake_provider
    from tests.des.acceptance.distill_document_construction.test_distill_document_construction import (
        _call,
        _declared_revision,
        _Subject,
        _value_manifest,
    )
    from tests.des.acceptance.steps_for_the_orchestrator.conftest import block

    subject = _Subject(tmp_path, None, shared=shared).designed()
    subject.select("blue")
    subject.select("green", replace=True)

    # Real DESIGN change after B: the exact realignment-needed condition the
    # brief names as the trigger for this recovery capability.
    code, out, err = _call(
        subject.root,
        "design",
        json.dumps(_value_manifest(expected="stdout is green and exit is zero.")),
        value=1,
        replace_current=True,
    )
    assert code == 0, out + err

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
    assert code == 0, (
        "WHAT: `des prepare-role --role acceptance-designer --task "
        "selected-revision-recovery` is refused. WHY: the closed design "
        "(docs/feature/atomic-selected-acceptance/architecture/brief.md, "
        "'Installed recovery guidance for Claude and Codex') declares this as "
        "the one route that repairs a SelectedRevisionRealignmentNeeded "
        "selection: it binds the kept selected revision, current DESIGN facts "
        "and the finding into one sealed input, without a verified candidate "
        "or native-evidence record, and never runs a native command. HOW: "
        "keep src/des/cli/prepare_role.py accepting --role acceptance-designer "
        "with --task selected-revision-recovery and --finding, and keep "
        "role_artifacts.prepare_selected_revision_recovery sealing that input; "
        "run the argv above against a subject repository to see the block.\n"
        f"stdout={out!r} stderr={err!r}"
    )
    lines = block(out, err)
    input_path = lines["INPUT"]
    prepared = json.loads((subject.root / input_path).read_text())
    assert "value_design_semantic_sha256" in prepared
    assert "shared_design_semantic_sha256" in prepared
    assert prepared["current_value_design"] == {
        "targets": [{"path": "src/widget.py", "decision": "EXTEND"}],
        "paradigm": "object_oriented",
        "decisions": ["Value one keeps color validation at construction."],
        "oracle": "tests/acceptance/test_design_default.py::test_design_default",
        "acceptance_supports": [],
        "verification": [["pytest", "-q", "tests/acceptance/test_design_default.py"]],
        "oracle_verification_index": 0,
        "obligations": ["Preserve existing callers."],
        "authority_locator": (
            "docs/feature/atomic-selected-acceptance/architecture/brief.md"
            "#Selected widget color"
        ),
        "public_oracle": {
            "observation": "CLI prints the selected color.",
            "stimulus": "Run widget show --color red.",
            "expected": "stdout is green and exit is zero.",
            "falsifier": "Any other stdout or non-zero exit.",
        },
    }, (
        "WHAT: recovery input omitted or changed current value DESIGN facts. "
        "WHY: the acceptance designer must realign B against the exact current "
        "authority. HOW: prepare-role must seal the canonical value DESIGN wire."
    )
    expected_shared = (
        {
            "authority_locator": (
                "docs/feature/atomic-selected-acceptance/architecture/brief.md"
                "#Selected acceptance feature design"
            ),
            # The shared DESIGN binding records sha256 of the manifest's
            # rendered Markdown (delivery_steps.SharedDesign), so any change to
            # the DESIGN renderer moves this literal. It last moved when the
            # lint-clean section rendering reached this branch.
            "section_sha256": "83b4c2185445e2d44a3dfe0f430cfdf26b7e95659633f4882ec9d493c9b8cba5",
            "semantic_sha256": "9ae5c2d1cd7abb0db8293f8d0f25466d6cb64ebadf5530ee626a880f9e992b0f",
            "design": {
                "targets": [{"path": "src/widget.py", "decision": "EXTEND"}],
                "paradigm": "object_oriented",
                "decisions": [
                    "Every consumer reads one complete selected acceptance revision."
                ],
                "oracle": "tests/test_shared.py::test_shared",
                "acceptance_supports": [],
                "verification": [["pytest", "-q", "tests/test_shared.py"]],
                "oracle_verification_index": 0,
                "obligations": ["Value sections carry only deltas."],
                "authority_locator": (
                    "docs/feature/atomic-selected-acceptance/architecture/brief.md"
                    "#Selected acceptance feature design"
                ),
                "public_oracle": {
                    "observation": "CLI prints the selected color.",
                    "stimulus": "Run widget show --color red.",
                    "expected": "stdout is red and exit is zero.",
                    "falsifier": "Any other stdout or non-zero exit.",
                },
            },
        }
        if shared
        else None
    )
    assert prepared["current_shared_design"] == expected_shared, (
        "WHAT: recovery input omitted or changed current shared DESIGN facts. "
        "WHY: shared authority changes which B criteria remain valid. HOW: "
        "prepare-role must seal the canonical shared DESIGN wire or explicit null."
    )
    assert prepared["finding"] == finding
    first_input_path = input_path
    first_prepared_bytes = (subject.root / first_input_path).read_bytes()

    # A second DESIGN correction makes the first input stale. The first bytes
    # remain history; a new binding receives one new immutable input.
    code, out, err = _call(
        subject.root,
        "design",
        json.dumps(_value_manifest(expected="stdout is amber and exit is zero.")),
        value=1,
        replace_current=True,
    )
    assert code == 0, out + err
    second_finding = (
        "DESIGN for value 1 changed again after the first recovery input; "
        "realign the selected acceptance revision to current authority."
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
        stdin_text=second_finding,
        catch_all=True,
    )
    assert code == 0, out + err
    input_path = block(out, err)["INPUT"]
    assert input_path != first_input_path
    assert (subject.root / first_input_path).read_bytes() == first_prepared_bytes
    second_prepared = json.loads((subject.root / input_path).read_text())
    assert second_prepared["finding"] == second_finding
    # A NEW authority binding yields a NEW input: under content-identity
    # addressing that is a payload-digest and path claim, not a file-name
    # substring claim -- the binding differs, so the sealed payload bytes
    # differ, so the content-addressed path differs. Assert the identity LAW
    # itself, not merely that the two paths differ: each path's sole 64-hex
    # suffix must equal the sha256 of that exact input's own sealed bytes --
    # the same digest `des prepare-role` prints as INPUT-SHA256.
    assert (
        second_prepared["recovery_binding_sha256"]
        != prepared["recovery_binding_sha256"]
    )
    single_hash = re.compile(
        r"^value-1-acceptance-designer-selected-revision-recovery-"
        r"(?P<digest>[0-9a-f]{64})-input\.json$"
    )
    first_match = single_hash.match(Path(first_input_path).name)
    second_match = single_hash.match(Path(input_path).name)
    assert first_match is not None and second_match is not None, (
        "WHAT: a recovery input path is not named by a single 64-hex-char "
        "content digest. WHY: DESIGN requires the recovery INPUT path to "
        "equal the sha256 of the sealed input's own bytes, never a binding "
        "or a binding+finding composite. HOW: name the prepared input "
        "value-N-acceptance-designer-selected-revision-recovery-"
        "<sha256 of its own sealed bytes>-input.json.\n"
        f"first={first_input_path!r} second={input_path!r}"
    )
    assert (
        first_match.group("digest") == hashlib.sha256(first_prepared_bytes).hexdigest()
    ), (
        "WHAT: the first recovery input's path digest does not equal the "
        "sha256 of its own sealed bytes. WHY: the path IS the content "
        "identity of the sealed input, not an arbitrary or binding-derived "
        "token. HOW: derive the path from the digest of the exact bytes "
        "`_write` persists."
    )
    second_prepared_bytes = (subject.root / input_path).read_bytes()
    assert (
        second_match.group("digest")
        == hashlib.sha256(second_prepared_bytes).hexdigest()
    ), (
        "WHAT: the second recovery input's path digest does not equal the "
        "sha256 of its own sealed bytes. WHY: same content-identity law as "
        "the first input -- a corrected finding is a different payload, "
        "hence a different digest and path. HOW: derive the path from the "
        "digest of the exact bytes `_write` persists."
    )
    assert second_prepared_bytes != first_prepared_bytes
    assert second_prepared["current_value_design"]["public_oracle"]["expected"] == (
        "stdout is amber and exit is zero."
    ), (
        "WHAT: the second prepared input has the old expected. "
        "WHY: the public oracle should reflect the current DESIGN. "
        "HOW: current_value_design must carry public_oracle with the latest expected."
    )

    # One issued turn, one identity, against the same fake provider the rest
    # of the acceptance corpus drives -- no real credential, no real host.
    workspace = tmp_path / "recovery-workspace"
    workspace.mkdir()
    native = subject.root / ".nwave/des/logs/native"
    native_before = set(native.iterdir()) if native.exists() else set()
    b = _declared_revision("green", None)
    document = {
        "schema_version": 2,
        "values": [
            {
                "observation": b["observation"],
                "acceptance_obligations": b["acceptance_obligations"],
                "oracle": b["oracle"],
                "acceptance_supports": b["acceptance_supports"],
                "verification": b["verification"],
                "oracle_verification_index": b["oracle_verification_index"],
            }
        ],
    }
    results = workspace / "results.json"
    log = workspace / "log.json"
    results.write_text(
        json.dumps(
            [
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "realigned the selected revision",
                        "distill_document": document,
                    }
                }
            ]
        )
    )
    # The real recovery entry owns a per-user disposable role context.  Declare
    # that external location explicitly so this public CLI observation neither
    # borrows the developer's home nor mistakes an unwritable host home for a
    # recovery failure.
    recovery_home = workspace / "home"
    recovery_home.mkdir()
    environment = fake_provider.environment(
        subject.root,
        launcher_dir=workspace / "bin",
        results=results,
        log=log,
    ) | {"HOME": str(recovery_home), "CLAUDE_CONFIG_DIR": str(workspace / "claude")}
    code, out, err = run_cli_in_process(
        [
            "invoke-role",
            "--repo-root",
            str(subject.root),
            "--role",
            "acceptance-designer",
            "--task",
            "selected-revision-recovery",
            "--provider",
            "claude",
            "--input",
            input_path,
        ],
        cwd=subject.root,
        env=environment,
        catch_all=True,
    )
    assert code == 0, (
        f"WHAT: des invoke-role refused the recovery turn. stdout={out!r} "
        f"stderr={err!r}"
    )
    turns = json.loads(log.read_text()) if log.exists() else []
    assert len(turns) == 1, (
        f"WHAT: expected exactly one issued role turn, observed "
        f"{len(turns)}. WHY: recovery buys one synchronous "
        "provider turn, never more. HOW: invoke-role must call the port once."
    )
    assert turns[-1]["agent"] == "nw-acceptance-designer", (
        f"WHAT: issued turn identity was {turns[-1]['agent']!r}, expected "
        "nw-acceptance-designer. HOW: role_id(role='acceptance-designer') must "
        "resolve the installed acceptance-designer role."
    )

    invoke_lines = block(out, err)
    document_path = subject.root / invoke_lines["DISTILL-DOCUMENT"]
    persisted = document_path.read_bytes()
    parsed = json.loads(persisted)
    assert parsed["schema_version"] == 2, (
        "WHAT: persisted artifact is not a complete schema_version 2 DistillDocument."
    )
    assert parsed["values"][0]["oracle"] == b["oracle"]

    # No native test command ran during prepare or invoke: the turn log holds
    # exactly the one recovery row, and no native-evidence file appeared.
    native_after = set(native.iterdir()) if native.exists() else set()
    assert native_after == native_before, (
        "WHAT: a native command ran during recovery preparation/invocation. "
        "WHY: recovery only reads and returns a document; it never executes "
        "the oracle or any declared verification argv. HOW: prepare-role and "
        "invoke-role must not call the native-argv runner for this task."
    )

    # The caller replays the exact persisted bytes, unchanged, to the owning
    # DES constructor -- and only that constructor writes the selection.
    subject_turns_before_distill = len(subject.rows())
    code, out, err = _call(subject.root, "distill", persisted.decode("utf-8"))
    assert code != 0, (
        "WHAT: replaying the recovered document without --replace-current "
        "must still refuse (a misaligned selection is never silently "
        "overwritten by a bare distill)."
    )
    code, out, err = _call(
        subject.root, "distill", persisted.decode("utf-8"), replace_current=True
    )
    assert code == 0, (
        f"WHAT: des distill --replace-current refused the exact "
        f"recovered bytes unchanged. stdout={out!r} stderr={err!r}"
    )
    assert len(subject.rows()) == subject_turns_before_distill, (
        "caller-directed DISTILL must construct the selection without invoking a role"
    )

    code, out, err, _ = subject.oracle("green")
    assert "SelectedRevisionRealignmentNeeded" not in (out + err), (
        "WHAT: the selection is still reported misaligned after replaying the "
        "recovered document. WHY: a complete v2 replacement is the only thing "
        "that realigns. HOW: the recovered document's basis must match the "
        "current DESIGN facts."
    )


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


def test_selected_revision_recovery_invokes_the_acceptance_designer_in_a_readable_checkout(
    tmp_path: Path,
):
    """RED for the public defect: recovery invocation spawns the role in an

    empty scratch directory, so the declared oracle target and acceptance
    supports it must read to review or extend (GREEN_TO_GREEN reuse) or to
    author missing declared supports do not exist there.

    Evidence: `.nwave/des/logs/roles/value-3-acceptance-designer-
    selected-revision-recovery-*-result.json` records `outcome: rejected`
    with a diagnostic naming `repository_root` empty and every declared
    acceptance_supports path plus the oracle target unreadable via
    `FileNotFoundError`, for a real turn issued by the installed
    acceptance-designer role.

    The closed design (brief.md, "Installed recovery guidance for Claude and
    Codex") binds recovery to the sealed B revision, current DESIGN facts and
    the finding -- reading declared assets to realign against them is the
    whole point of the recovery turn, so the execution cwd must contain what
    the sealed revision names, whether that is the live working tree or an
    equivalent checked-out candidate snapshot. This observation drives the
    real `des prepare-role` / `des invoke-role` public CLI end to end and
    inspects the fake provider's own recorded `cwd` -- never invented, never
    a private field the port does not expose.
    """
    from tests.common.in_process_cli import run_cli_in_process
    from tests.des.acceptance import fake_provider
    from tests.des.acceptance.distill_document_construction.test_distill_document_construction import (
        _call,
        _declared_revision,
        _Subject,
        _value_manifest,
    )
    from tests.des.acceptance.steps_for_the_orchestrator.conftest import block

    subject = _Subject(tmp_path, None, shared=False).designed()
    subject.select("blue")
    b = _declared_revision("green", None)
    subject.select("green", replace=True)

    # The sealed B revision names these declared assets; the real recovery
    # role must be able to read them from its execution cwd to realign B or
    # to author a declared-but-missing support -- exactly the reuse/RED
    # boundary GREEN_TO_GREEN and RED_TO_GREEN both depend on.
    oracle_target = subject.root / str(b["oracle"]).split("::", 1)[0]
    oracle_target.parent.mkdir(parents=True, exist_ok=True)
    oracle_target.write_text("def test_selects_green():\n    assert True\n")
    for support in b["acceptance_supports"]:
        support_path = subject.root / str(support)
        support_path.parent.mkdir(parents=True, exist_ok=True)
        support_path.write_text("MARKER = 1\n")

    code, out, err = _call(
        subject.root,
        "design",
        json.dumps(_value_manifest(expected="stdout is green and exit is zero.")),
        value=1,
        replace_current=True,
    )
    assert code == 0, out + err

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
    assert code == 0, out + err
    input_path = block(out, err)["INPUT"]

    workspace = tmp_path / "recovery-workspace"
    workspace.mkdir()
    results = workspace / "results.json"
    log = workspace / "log.json"
    results.write_text(
        json.dumps(
            [
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "realigned the selected revision",
                        "distill_document": {
                            "schema_version": 2,
                            "values": [
                                {
                                    "observation": b["observation"],
                                    "acceptance_obligations": b[
                                        "acceptance_obligations"
                                    ],
                                    "oracle": b["oracle"],
                                    "acceptance_supports": b["acceptance_supports"],
                                    "verification": b["verification"],
                                    "oracle_verification_index": b[
                                        "oracle_verification_index"
                                    ],
                                }
                            ],
                        },
                    }
                }
            ]
        )
    )
    recovery_home = workspace / "home"
    recovery_home.mkdir()
    oracle_target = str(b["oracle"]).split("::", 1)[0]
    declared_paths = [oracle_target, *(str(s) for s in b["acceptance_supports"])]
    environment = fake_provider.environment(
        subject.root,
        launcher_dir=workspace / "bin",
        results=results,
        log=log,
        check_paths=declared_paths,
    ) | {"HOME": str(recovery_home), "CLAUDE_CONFIG_DIR": str(workspace / "claude")}
    code, out, err = run_cli_in_process(
        [
            "invoke-role",
            "--repo-root",
            str(subject.root),
            "--role",
            "acceptance-designer",
            "--task",
            "selected-revision-recovery",
            "--provider",
            "claude",
            "--input",
            input_path,
        ],
        cwd=subject.root,
        env=environment,
        catch_all=True,
    )
    assert code == 0, (
        f"WHAT: des invoke-role refused the recovery turn. stdout={out!r} "
        f"stderr={err!r}"
    )

    turns = json.loads(log.read_text()) if log.exists() else []
    assert len(turns) == 1, (
        f"WHAT: expected exactly one issued role turn, observed {len(turns)}. "
        "WHY: recovery buys one synchronous provider turn, never more. HOW: "
        "invoke-role must call the port once."
    )
    # Recorded by the launcher itself, INSIDE its execution cwd, at the moment
    # of invocation -- before invoke_role.py's `finally` block can remove an
    # isolated checkout or scratch tempdir. Asserting on this recorded fact
    # (rather than re-probing the filesystem after invoke-role has returned)
    # keeps the observation honest for a CORRECT fix too: a fix that checks
    # out a candidate snapshot and then cleans it up on return must not read
    # as a false RED here.
    readable = set(turns[-1]["readable_paths"])
    assert oracle_target in readable, (
        f"WHAT: at the moment of invocation the recovery role's execution cwd "
        f"did not contain the sealed revision's declared oracle target "
        f"{b['oracle']!r} (recorded readable_paths={sorted(readable)!r}, "
        f"cwd={turns[-1]['cwd']!r}). WHY: the acceptance-designer role "
        "reviews or extends the existing oracle (GREEN_TO_GREEN reuse) or "
        "authors a declared-but-missing support against the real repository "
        "state, and an execution cwd without those declared assets makes the "
        "role reject with 'repository_root is empty' instead of reading "
        "them -- the exact public defect .nwave/des/logs/roles/value-3-"
        "acceptance-designer-selected-revision-recovery-*-result.json "
        "records. HOW: src/des/cli/invoke_role.py must give the "
        "acceptance-designer selected-revision-recovery turn an execution "
        "cwd that contains the declared assets -- the live working tree or "
        "an equivalent checked-out candidate snapshot, exactly as the "
        "reviewer role already checks out its candidate -- while keeping the "
        "candidate-isolation guarantee and never running the declared oracle "
        "or verification argv itself."
    )
    for support in b["acceptance_supports"]:
        assert str(support) in readable, (
            f"WHAT: at the moment of invocation the recovery role's execution "
            f"cwd did not contain the sealed revision's declared acceptance "
            f"support {support!r} (recorded readable_paths="
            f"{sorted(readable)!r}, cwd={turns[-1]['cwd']!r}). WHY: reading "
            "every declared acceptance support is part of the same "
            "constructive chain as reading the oracle target. HOW: give the "
            "recovery turn's execution cwd the declared acceptance supports "
            "too."
        )
    # The isolation and no-extra-execution guarantees the closed design
    # demands stay observed exactly as before: no native command ran, and the
    # exact provider argv/turn count is unaffected by recording readable_paths.
    document_path = subject.root / block(out, err)["DISTILL-DOCUMENT"]
    assert json.loads(document_path.read_bytes())["schema_version"] == 2

    # A readable execution cwd is necessary but not sufficient: a role that
    # declares Edit/Bash could still get write/execute access while every
    # assertion above stays green. The projected `--tools`/`--allowedTools`
    # ceiling is the fact that rules that out, recorded from the real argv
    # the real ClaudeCodeTaskAdapter spawned the launcher with -- never
    # reconstructed from a copy of the projection rule.
    argv = turns[-1]["argv"]
    tools = set(argv[argv.index("--tools") + 1].split(","))
    allowed_tools = set(argv[argv.index("--allowedTools") + 1].split(","))
    assert tools == {"Read", "StructuredOutput"}, (
        f"WHAT: recovery's `--tools` argv entry was {tools!r}, not exactly "
        "{'Read', 'StructuredOutput'}. WHY: the closed design binds recovery "
        "to a read-only turn that only realigns the sealed revision against "
        "current DESIGN facts; a role that keeps Edit/Bash could write to or "
        "execute inside the repository it is only supposed to read. HOW: "
        "src/des/adapters/driven/task_invocation/claude_code_task_adapter.py "
        "must project declared_tools down to Read (plus the synthetic "
        "StructuredOutput answer channel) for semantic_task="
        "'selected-revision-recovery', never leaving Edit or Bash in "
        "`--tools`."
    )
    assert allowed_tools == {"Read", "StructuredOutput"}, (
        f"WHAT: recovery's `--allowedTools` argv entry was {allowed_tools!r}, "
        "not exactly {'Read', 'StructuredOutput'}. WHY: `--allowedTools` is "
        "what the spawned Claude session is actually permitted to invoke; "
        "granting Edit or Bash there reopens write/exec access even if "
        "`--tools` is capped. HOW: project the same capped tuple onto "
        "`--allowedTools`."
    )

    # Nearest public Codex recovery case for the same law: drive the real
    # `des invoke-role --provider codex` boundary end to end, through a
    # deterministic fake `codex` executable that records its own spawned argv
    # and execution cwd -- never the private `_sandbox_for` projection
    # function directly. The fake speaks Codex's real transport (role travels
    # in `-c developer_instructions=...`, the answer lands in the
    # provider-enforced `--output-last-message` terminal file, never stdout),
    # so this observation is a public-boundary repeat of the same sandbox law,
    # not a copy of the projection code that computes it.
    codex_workspace = tmp_path / "recovery-workspace-codex"
    codex_workspace.mkdir()
    codex_results = codex_workspace / "results.json"
    codex_log = codex_workspace / "log.json"
    codex_results.write_text(
        json.dumps(
            [
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "realigned the selected revision",
                        "distill_document": {
                            "schema_version": 2,
                            "values": [
                                {
                                    "observation": b["observation"],
                                    "acceptance_obligations": b[
                                        "acceptance_obligations"
                                    ],
                                    "oracle": b["oracle"],
                                    "acceptance_supports": b["acceptance_supports"],
                                    "verification": b["verification"],
                                    "oracle_verification_index": b[
                                        "oracle_verification_index"
                                    ],
                                }
                            ],
                        },
                    }
                }
            ]
        )
    )
    codex_home = codex_workspace / "home"
    codex_home.mkdir()
    (subject.root / ".nwave" / "config.json").write_text(
        json.dumps(
            {
                "model_runtime": {
                    "default": {"provider": "codex", "model": "gpt-5-codex"}
                }
            }
        ),
        encoding="utf-8",
    )
    codex_environment = fake_provider.environment(
        subject.root,
        launcher_dir=codex_workspace / "bin",
        results=codex_results,
        log=codex_log,
        check_paths=declared_paths,
    ) | {"HOME": str(codex_home)}
    codex_native = subject.root / ".nwave/des/logs/native"
    native_before_codex = (
        set(codex_native.iterdir()) if codex_native.exists() else set()
    )
    code, out, err = run_cli_in_process(
        [
            "invoke-role",
            "--repo-root",
            str(subject.root),
            "--role",
            "acceptance-designer",
            "--task",
            "selected-revision-recovery",
            "--provider",
            "codex",
            "--input",
            input_path,
        ],
        cwd=subject.root,
        env=codex_environment,
        catch_all=True,
    )
    assert code == 0, (
        f"WHAT: des invoke-role --provider codex refused the recovery turn. "
        f"stdout={out!r} stderr={err!r}"
    )

    codex_turns = json.loads(codex_log.read_text()) if codex_log.exists() else []
    assert len(codex_turns) == 1, (
        f"WHAT: expected exactly one issued Codex role turn, observed "
        f"{len(codex_turns)}. WHY: recovery buys one synchronous provider "
        "turn, never more. HOW: invoke-role must call the port once."
    )
    codex_turn = codex_turns[-1]
    assert codex_turn["agent"] == "nw-acceptance-designer", (
        f"WHAT: issued Codex turn identity was {codex_turn['agent']!r}, "
        "expected nw-acceptance-designer."
    )
    codex_readable = set(codex_turn["readable_paths"])
    assert oracle_target in codex_readable, (
        f"WHAT: at the moment of invocation the Codex recovery role's "
        f"execution cwd did not contain the sealed revision's declared "
        f"oracle target {b['oracle']!r} (readable_paths="
        f"{sorted(codex_readable)!r}, cwd={codex_turn['cwd']!r}). HOW: give "
        "the Codex recovery turn's execution cwd the declared oracle target."
    )
    for support in b["acceptance_supports"]:
        assert str(support) in codex_readable, (
            f"WHAT: at the moment of invocation the Codex recovery role's "
            f"execution cwd did not contain the sealed revision's declared "
            f"acceptance support {support!r} (readable_paths="
            f"{sorted(codex_readable)!r}). HOW: give the Codex recovery "
            "turn's execution cwd the declared acceptance supports too."
        )

    codex_argv = codex_turn["argv"]
    assert "--sandbox" in codex_argv, (
        f"WHAT: the real Codex invocation argv carried no --sandbox flag: "
        f"{codex_argv!r}. WHY: the closed design binds recovery to a "
        "read-only turn. HOW: CodexTaskAdapter.argv_for must always pass "
        "--sandbox."
    )
    codex_sandbox = codex_argv[codex_argv.index("--sandbox") + 1]
    assert codex_sandbox == "read-only", (
        f"WHAT: the real Codex --sandbox argv value was {codex_sandbox!r}, "
        "not 'read-only'. WHY: the closed design requires the recovery turn "
        "to run read-only on Codex too -- StructuredOutput is Claude-only "
        "synthetic metadata that must never widen the sandbox, and Read "
        "alone must never project to 'workspace-write'. HOW: "
        "src/des/adapters/driven/task_invocation/codex_task_adapter.py's "
        "_sandbox_for must keep excluding StructuredOutput from the "
        "write-capability check and must keep mapping a Read-only real-tool "
        "set to 'read-only', and _run_turn must pass that projection through "
        "unchanged."
    )
    native_after_codex = set(codex_native.iterdir()) if codex_native.exists() else set()
    assert native_after_codex == native_before_codex, (
        "WHAT: a native command ran during the Codex recovery turn. WHY: "
        "recovery only reads and returns a document; it never executes the "
        "oracle or any declared verification argv. HOW: invoke-role must not "
        "call the native-argv runner for this task under any provider."
    )
    codex_document_path = subject.root / block(out, err)["DISTILL-DOCUMENT"]
    assert json.loads(codex_document_path.read_bytes())["schema_version"] == 2


@dataclass(frozen=True)
class _RecoveryContext:
    """Where a recovery cycle runs: the designed subject and its scratch space.

    ``subject`` is the ``_Subject`` a caller has already ``designed()``. It is
    typed ``object`` rather than by name because ``_Subject`` lives in another
    acceptance module that this file imports INSIDE its functions, deliberately,
    so importing it at module scope to satisfy an annotation would execute that
    module on every collection of this one. The original function was unannotated,
    so nothing is lost here.
    """

    subject: object
    tmp_path: Path
    workspace_name: str


@dataclass(frozen=True)
class _RecoveryCase:
    """What a recovery cycle recovers: the value, its finding, and the
    accepted revision the fake provider hands back."""

    value: int
    expected: str
    declared_revision: dict
    finding: str


def _recovery_cycle(context: _RecoveryContext, case: _RecoveryCase):
    """One real prepare-role / invoke-role recovery cycle for `case.value`.

    Drives the public boundary only; returns (input_path, document_path,
    stdout, stderr, exit_code) so the caller decides what a second cycle
    must preserve.
    """
    from tests.common.in_process_cli import run_cli_in_process
    from tests.des.acceptance import fake_provider
    from tests.des.acceptance.distill_document_construction.test_distill_document_construction import (
        _call,
        _value_manifest,
    )
    from tests.des.acceptance.steps_for_the_orchestrator.conftest import block

    subject = context.subject
    code, out, err = _call(
        subject.root,
        "design",
        json.dumps(_value_manifest(expected=case.expected)),
        value=case.value,
        replace_current=True,
    )
    assert code == 0, out + err

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
            str(case.value),
            "--finding",
            "-",
        ],
        cwd=subject.root,
        stdin_text=case.finding,
        catch_all=True,
    )
    assert code == 0, out + err
    input_path = block(out, err)["INPUT"]

    workspace = context.tmp_path / context.workspace_name
    workspace.mkdir()
    results = workspace / "results.json"
    log = workspace / "log.json"
    b = case.declared_revision
    document = {
        "schema_version": 2,
        "values": [
            {
                "observation": b["observation"],
                "acceptance_obligations": b["acceptance_obligations"],
                "oracle": b["oracle"],
                "acceptance_supports": b["acceptance_supports"],
                "verification": b["verification"],
                "oracle_verification_index": b["oracle_verification_index"],
            }
        ],
    }
    results.write_text(
        json.dumps(
            [
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "realigned the selected revision",
                        "distill_document": document,
                    }
                }
            ]
        )
    )
    home = workspace / "home"
    home.mkdir()
    environment = fake_provider.environment(
        subject.root,
        launcher_dir=workspace / "bin",
        results=results,
        log=log,
    ) | {"HOME": str(home), "CLAUDE_CONFIG_DIR": str(workspace / "claude")}
    code, out, err = run_cli_in_process(
        [
            "invoke-role",
            "--repo-root",
            str(subject.root),
            "--role",
            "acceptance-designer",
            "--task",
            "selected-revision-recovery",
            "--provider",
            "claude",
            "--input",
            input_path,
        ],
        cwd=subject.root,
        env=environment,
        catch_all=True,
    )
    return input_path, code, out, err


def test_second_accepted_selected_revision_recovery_retains_both_documents(
    tmp_path: Path,
):
    """RED: a prior accepted selected-revision-recovery document must not

    block a second, genuinely different, accepted recovery for the same
    value after a further DESIGN change. The public defect:
    `record_selected_revision_recovery` writes the document under a
    value-only fixed locator (no revision/input digest), so `_write`'s
    write-once guard treats the second accepted document's different bytes
    as `ArtifactConflict`, and `des invoke-role` returns the bought turn as
    `RoleResultUnrecordable` instead of retaining both historical documents
    under distinct locators -- exactly the loss `.nwave/des/logs/roles/
    value-3-acceptance-designer-selected-revision-recovery-document.json`
    exhibits for value 3.
    """
    from tests.des.acceptance.distill_document_construction.test_distill_document_construction import (
        _declared_revision,
        _Subject,
    )
    from tests.des.acceptance.steps_for_the_orchestrator.conftest import block

    subject = _Subject(tmp_path, None, shared=False).designed()
    subject.select("blue")

    finding = (
        "DESIGN for value 1 changed after DISTILL B; des oracle --value 1 ended "
        "Indeterminate with SelectedRevisionRealignmentNeeded. Realign the "
        "selected acceptance revision."
    )
    b_first = _declared_revision("green", None)
    subject.select("green", replace=True)
    input_path_1, code, out, err = _recovery_cycle(
        _RecoveryContext(
            subject=subject, tmp_path=tmp_path, workspace_name="recovery-workspace-1"
        ),
        _RecoveryCase(
            value=1,
            expected="stdout is green and exit is zero.",
            declared_revision=b_first,
            finding=finding,
        ),
    )
    assert code == 0, f"first recovery turn must succeed: stdout={out!r} stderr={err!r}"
    document_path_1 = block(out, err)["DISTILL-DOCUMENT"]

    b_second = _declared_revision("amber", None)
    subject.select("amber", replace=True)
    second_finding = (
        "DESIGN for value 1 changed again after the first recovery; realign "
        "the selected acceptance revision to current authority."
    )
    input_path_2, code, out, err = _recovery_cycle(
        _RecoveryContext(
            subject=subject, tmp_path=tmp_path, workspace_name="recovery-workspace-2"
        ),
        _RecoveryCase(
            value=1,
            expected="stdout is amber and exit is zero.",
            declared_revision=b_second,
            finding=second_finding,
        ),
    )
    assert code == 0, (
        "WHAT: the second accepted selected-revision-recovery turn for value "
        f"1 was refused after it bought a real provider turn. stdout={out!r} "
        f"stderr={err!r}. WHY: a value-only fixed document locator collides "
        "across two distinct accepted revisions and loses the paid turn. "
        "HOW: name the recovery document locator by the recovery binding (as "
        "the input and result locators already are) so distinct accepted "
        "documents for the same value coexist."
    )
    assert "RoleResultUnrecordable" not in (out + err)
    assert input_path_1 != input_path_2

    document_path_2 = block(out, err)["DISTILL-DOCUMENT"]
    assert document_path_2 != document_path_1, (
        "the second accepted document must have its own distinct locator"
    )
    assert (subject.root / document_path_1).exists(), (
        "the first accepted recovery document must remain readable after the "
        "second accepted recovery"
    )
    first_document = json.loads((subject.root / document_path_1).read_bytes())
    second_document = json.loads((subject.root / document_path_2).read_bytes())
    assert first_document["values"][0]["oracle"] == b_first["oracle"]
    assert second_document["values"][0]["oracle"] == b_second["oracle"]


def test_a_corrected_finding_seals_a_distinct_recovery_input_on_claude_and_codex(
    tmp_path: Path,
):
    """A corrected finding at one authority binding seals its own immutable input.

    Law: a recovery INPUT path's sole 64-hex suffix is the sha256 of that
    input's exact sealed bytes. F1 and F2 at one binding therefore seal two
    distinct inputs; repeating F1 reuses its path; corrupted bytes refuse
    before a turn; legacy bare and binding-only names stay loadable; after a
    further DESIGN change F1 refuses before a turn. F1 runs on the Claude fake
    provider and F2 on the Codex fake provider, and F2's accepted document
    realigns the selection through `des distill --replace-current`. Driven only
    through the public `des` CLI.
    """
    from tests.des.acceptance import fake_provider
    from tests.des.acceptance.distill_document_construction.test_distill_document_construction import (
        _call,
        _declared_revision,
        _Subject,
        _value_manifest,
    )
    from tests.des.acceptance.steps_for_the_orchestrator.conftest import block

    subject = _Subject(tmp_path, None, shared=False).designed()
    subject.select("blue")
    subject.select("green", replace=True)
    code, out, err = _call(
        subject.root,
        "design",
        json.dumps(_value_manifest(expected="stdout is green and exit is zero.")),
        value=1,
        replace_current=True,
    )
    assert code == 0, out + err

    def prepare(finding: str) -> tuple[int, str, str]:
        return run_cli_in_process(
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

    finding_1 = "F1: realign the selected acceptance revision to current DESIGN."
    finding_2 = "F2: a corrected finding at the SAME authority binding as F1."
    prepared = {}
    for name, finding in (("F1", finding_1), ("F2", finding_2)):
        code, out, err = prepare(finding)
        assert code == 0, (
            f"WHAT: preparing {name} refused. WHY: a corrected finding at an "
            "unchanged binding is a distinct immutable input, not a conflict. "
            f"HOW: name each input by its own content digest. out={out!r} err={err!r}"
        )
        lines = block(out, err)
        prepared[name] = (lines["INPUT"], lines["INPUT-SHA256"])
    (path_1, digest_1), (path_2, digest_2) = prepared["F1"], prepared["F2"]
    raw_1 = (subject.root / path_1).read_bytes()
    raw_2 = (subject.root / path_2).read_bytes()
    single_hash = re.compile(
        r"^value-1-acceptance-designer-selected-revision-recovery-"
        r"(?P<digest>[0-9a-f]{64})-input\.json$"
    )
    for path, raw, digest in ((path_1, raw_1, digest_1), (path_2, raw_2, digest_2)):
        match = single_hash.match(Path(path).name)
        assert match is not None and match.group("digest") == digest == (
            hashlib.sha256(raw).hexdigest()
        ), (
            f"WHAT: {path!r} is not named by the sha256 of its own sealed bytes "
            f"(INPUT-SHA256={digest!r}). WHY: the path is the content identity "
            "of the exact input; a binding-only or binding-plus-finding name "
            "collides or composes two identities. HOW: name the input "
            "value-N-acceptance-designer-selected-revision-recovery-<sha256 of "
            "its bytes>-input.json."
        )
    assert path_1 != path_2 and raw_1 != raw_2
    payload_1, payload_2 = json.loads(raw_1), json.loads(raw_2)
    binding = payload_1["recovery_binding_sha256"]
    assert payload_2["recovery_binding_sha256"] == binding, (
        "F1 and F2 must share one recovery_binding_sha256"
    )
    assert (payload_1["finding"], payload_2["finding"]) == (finding_1, finding_2)

    code, out, err = prepare(finding_1)
    assert code == 0 and (
        block(out, err)["INPUT"],
        block(out, err)["INPUT-SHA256"],
    ) == (path_1, digest_1), "repeating F1 verbatim must reuse its path and digest"

    corrupted = subject.root / path_1
    corrupted.write_bytes(raw_1.replace(b'"F1', b'"XX'))
    code, out, err = prepare(finding_1)
    assert code != 0 and "WHAT: RoleInputAlreadyPrepared" in out + err, (
        "WHAT: re-preparing F1 over altered sealed bytes did not refuse with "
        "the public RoleInputAlreadyPrepared terminal. WHY: an immutable input "
        "is never silently rewritten. HOW: keep the write-once guard on the path."
    )
    assert corrupted.read_bytes() != raw_1, "the refusal must not rewrite the artifact"
    corrupted.write_bytes(raw_1)

    roles = subject.root / ".nwave/des/logs/roles"
    legacy_names = (
        "value-1-acceptance-designer-selected-revision-recovery-input.json",
        f"value-1-acceptance-designer-selected-revision-recovery-{binding}-input.json",
    )
    for legacy in legacy_names:
        (roles / legacy).write_bytes(raw_1)

    def invoke(input_path: str, provider: str, workspace_name: str, color: str):
        workspace = tmp_path / workspace_name
        workspace.mkdir()
        results, log, home = (
            workspace / "results.json",
            workspace / "log.json",
            workspace / "home",
        )
        home.mkdir()
        config = subject.root / ".nwave" / "config.json"
        if provider == "codex":
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                json.dumps(
                    {
                        "model_runtime": {
                            "default": {"provider": "codex", "model": "gpt-5-codex"}
                        }
                    }
                ),
                encoding="utf-8",
            )
        else:
            config.unlink(missing_ok=True)
        b = _declared_revision(color, None)
        document = {
            "schema_version": 2,
            "values": [
                {
                    key: b[key]
                    for key in (
                        "observation",
                        "acceptance_obligations",
                        "oracle",
                        "acceptance_supports",
                        "verification",
                        "oracle_verification_index",
                    )
                }
            ],
        }
        results.write_text(
            json.dumps(
                [
                    {
                        "structured_output": {
                            "outcome": "accepted",
                            "diagnostic": "realigned the selected revision",
                            "distill_document": document,
                        }
                    }
                ]
            )
        )
        environment = fake_provider.environment(
            subject.root, launcher_dir=workspace / "bin", results=results, log=log
        ) | {"HOME": str(home), "CLAUDE_CONFIG_DIR": str(workspace / "claude")}
        code, out, err = run_cli_in_process(
            [
                "invoke-role",
                "--repo-root",
                str(subject.root),
                "--role",
                "acceptance-designer",
                "--task",
                "selected-revision-recovery",
                "--provider",
                provider,
                "--input",
                input_path,
            ],
            cwd=subject.root,
            env=environment,
            catch_all=True,
        )
        issued = json.loads(log.read_text(encoding="utf-8")) if log.is_file() else []
        return code, out, err, issued

    documents = {}
    for name, path, provider, color in (
        ("F1", path_1, "claude", "green"),
        ("F2", path_2, "codex", "amber"),
    ):
        code, out, err, issued = invoke(path, provider, f"recovery-{name}", color)
        assert code == 0, (
            f"WHAT: invoke-role {name} via {provider} refused. out={out!r} err={err!r}"
        )
        assert [turn.get("agent") for turn in issued] == ["nw-acceptance-designer"], (
            f"WHAT: {name} via {provider} issued {issued!r}. WHY: each recovery "
            "buys exactly one acceptance-designer turn on its own provider. HOW: "
            "invoke only the selected role once for the exact INPUT."
        )
        documents[name] = block(out, err)["DISTILL-DOCUMENT"]
    assert documents["F1"] != documents["F2"], (
        "accepted documents need distinct locators"
    )

    for index, legacy in enumerate(legacy_names):
        code, out, err, issued = invoke(
            f".nwave/des/logs/roles/{legacy}", "claude", f"legacy-{index}", "green"
        )
        assert code == 0 and len(issued) == 1, (
            f"WHAT: legacy recovery input {legacy} is not loadable. WHY: earlier "
            "artifacts remain readable history. HOW: accept bare and binding-only "
            f"names under their seal and binding checks. out={out!r} err={err!r}"
        )

    persisted = (subject.root / documents["F2"]).read_text(encoding="utf-8")
    code, out, err = _call(subject.root, "distill", persisted, replace_current=True)
    assert code == 0, (
        f"des distill --replace-current refused F2's bytes: {out!r} {err!r}"
    )
    assert (subject.root / documents["F1"]).is_file() and (
        subject.root / documents["F2"]
    ).is_file(), "both accepted documents must survive the replacement"
    code, out, err, _ = subject.oracle("amber")
    assert "SelectedRevisionRealignmentNeeded" not in out + err, (
        "WHAT: des oracle still reports misalignment after F2's replacement. "
        "WHY: a complete v2 replacement realigns the selection. HOW: accept "
        "the recovered document unchanged as the selected revision."
    )

    code, out, err = _call(
        subject.root,
        "design",
        json.dumps(_value_manifest(expected="stdout is amber and exit is zero.")),
        value=1,
        replace_current=True,
    )
    assert code == 0, out + err
    code, out, err, issued = invoke(path_1, "claude", "stale-F1", "green")
    assert code != 0 and issued == [], (
        "WHAT: re-loading F1 after a further DESIGN change did not refuse "
        "before any turn. WHY: a stale binding never buys a recovery turn. "
        f"HOW: refuse on binding mismatch before invocation. out={out!r} issued={issued!r}"
    )


_ALIGNMENT_PHRASES = {
    "nw-role-invocation": (
        "invoke the installed `nw-user-examiner` natively with an explicit "
        "preimplementation assessment task",
        "the same selected behavioral contract bytes supplied to ATD",
        "Return its independent expectations to the existing ATD reviewer",
        "reuse it without another preimplementation assessment or ATD review",
        "Current DES examiner preparation requires a verified candidate",
        "use the native installed examiner for that task",
    ),
    "nw-distill": (
        "supply both outputs to the existing ATD reviewer",
        "Reuse a prior adequate alignment when the original value, selected "
        "contract, and findings are unchanged",
    ),
}
_NOT_DES_SURFACES = (
    "preimplementation-assessment",
    "preimplementation-alignment",
    "--examiner-result",
    "--role acceptance-reviewer",
)


def test_installed_before_code_alignment_uses_the_native_examiner_on_claude_and_codex(
    tmp_path, monkeypatch
):
    """Installed guidance routes before-code alignment to the native examiner.

    Law: on both installed hosts, the guidance sends the same selected
    behavioral contract bytes given to ATD to a native `nw-user-examiner`
    preimplementation assessment, returns both outputs to the existing ATD
    reviewer before craft, reuses an unchanged adequate alignment, and states
    that DES examiner preparation needs a verified candidate -- naming no
    candidate-free DES task, flag or role. The public `des prepare-role --role
    examiner` without a verified candidate refuses and writes no input.
    """

    def flat(text: str) -> str:
        return " ".join(text.split())

    per_host = {}
    for provider in ("claude", "codex"):
        sub = tmp_path / provider
        sub.mkdir()
        skills, agents = _install_real_guidance(provider, sub, monkeypatch)
        texts = {
            name: flat((skills / name / "SKILL.md").read_text(encoding="utf-8"))
            for name in _ALIGNMENT_PHRASES
        }
        examiner = flat(_agent_text(agents, "nw-user-examiner", provider))
        for name, phrases in _ALIGNMENT_PHRASES.items():
            for phrase in phrases:
                assert phrase in texts[name], (
                    f"WHAT: installed {provider} {name} lacks {phrase!r}. WHY: "
                    "the LLM follows installed guidance to align ATD, the native "
                    "examiner and the ATD reviewer on one selected revision before "
                    f"craft. HOW: keep that rule in nWave/skills/{name}/SKILL.md."
                )
        assert "When explicitly tasked during DISTILL before craft" in examiner, (
            f"WHAT: installed {provider} nw-user-examiner lacks its "
            "preimplementation assessment task. WHY: the native route needs a "
            "role that accepts it. HOW: keep the section in the agent definition."
        )
        installed = [
            (path.parent.name, path.read_text(encoding="utf-8"))
            for path in skills.glob("*/SKILL.md")
        ]
        for name, text in installed:
            for surface in _NOT_DES_SURFACES:
                assert surface not in text, (
                    f"WHAT: installed {provider} {name} names {surface!r}. WHY: "
                    "before-code alignment uses the native examiner; no "
                    "candidate-free DES task, flag or public role exists. HOW: "
                    "route the assessment to native nw-user-examiner."
                )
        per_host[provider] = texts
    assert sorted(per_host) == ["claude", "codex"], "both hosts must be observed"

    code, out, _ = run_cli_in_process(["prepare-role", "--help"], cwd=tmp_path)
    assert code == 0 and "acceptance-reviewer" not in out, (
        "des prepare-role must expose no public acceptance-reviewer role"
    )

    from tests.des.acceptance.distill_document_construction.test_distill_document_construction import (
        _Subject,
    )

    subject = _Subject(tmp_path / "subject", None).designed()
    subject.select("blue")
    roles = subject.root / ".nwave" / "des" / "logs" / "roles"
    before = sorted(p.name for p in roles.glob("*")) if roles.is_dir() else []
    code, out, err = run_cli_in_process(
        ["prepare-role", "--repo-root", str(subject.root), "--role", "examiner"],
        cwd=subject.root,
        catch_all=True,
    )
    after = sorted(p.name for p in roles.glob("*")) if roles.is_dir() else []
    assert code != 0 and "DELIVERY-OUTCOME: Refusal" in out + err, (
        "WHAT: des prepare-role --role examiner succeeded without a verified "
        "candidate. WHY: DES examiner input is candidate-bound final-EXAMINE "
        "input and cannot serve a preimplementation assessment. HOW: refuse "
        f"with WHAT/WHY/HOW before any write. out={out!r} err={err!r}"
    )
    assert after == before, f"no role input may be written: {before!r} -> {after!r}"

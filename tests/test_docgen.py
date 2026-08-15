"""Tests for nwave-docgen: deterministic documentation generator."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest
from nwave_ai.state_delta import assert_state_delta, set_to, unchanged

from scripts.docgen import (
    DocgenError,
    _infer_wave,
    _role_skill_loading_body,
    check_links,
    check_pages,
    check_registry_runtime_agreement,
    enrich,
    extract_agent,
    extract_all,
    extract_command,
    extract_skill,
    extract_template,
    parse_front_matter,
    render,
    run_pipeline,
    write_pages,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def nwave_tree(tmp_path: Path) -> Path:
    """Create a minimal nWave file tree for integration tests."""
    nw = tmp_path / "nWave"

    # Agent
    agents = nw / "agents"
    agents.mkdir(parents=True)
    (agents / "nw-crafter.md").write_text(
        textwrap.dedent("""\
        ---
        name: nw-crafter
        description: A test crafter agent
        model: sonnet
        tools: Read, Write, Edit
        maxTurns: 30
        skills:
          - tdd
          - refactoring
        ---
        # Body content
    """)
    )

    # Command
    cmds = nw / "tasks" / "nw"
    cmds.mkdir(parents=True)
    (cmds / "deliver.md").write_text(
        textwrap.dedent("""\
        ---
        description: "Execute the DELIVER wave"
        argument-hint: '[feature] - Example: "Add auth"'
        ---
        # Body
        Use nw-crafter to implement.
    """)
    )

    # Skills
    skill_dir = nw / "skills" / "crafter"
    skill_dir.mkdir(parents=True)
    (skill_dir / "tdd.md").write_text(
        textwrap.dedent("""\
        ---
        name: tdd
        description: TDD methodology knowledge
        ---
        # TDD
    """)
    )
    (skill_dir / "refactoring.md").write_text(
        textwrap.dedent("""\
        ---
        name: refactoring
        description: Progressive refactoring patterns
        ---
        # Refactoring
    """)
    )

    # Template
    templates = nw / "templates"
    templates.mkdir(parents=True)
    (templates / "deliver-tdd.yaml").write_text(
        textwrap.dedent("""\
        ---
        template_type: "deliver-tdd"
        description: "TDD template for DELIVER wave"
        version: "1.0.0"
        ---
    """)
    )

    return tmp_path


# ---------------------------------------------------------------------------
# parse_front_matter
# ---------------------------------------------------------------------------
class TestParseFrontMatter:
    def test_scalar_values(self, tmp_path: Path):
        f = tmp_path / "test.md"
        f.write_text("---\nname: foo\ndescription: bar baz\n---\n# Body")
        result = parse_front_matter(f)
        assert result == {"name": "foo", "description": "bar baz"}

    def test_list_values(self, tmp_path: Path):
        f = tmp_path / "test.md"
        f.write_text("---\nname: agent\nskills:\n  - alpha\n  - beta\n---\n")
        result = parse_front_matter(f)
        assert result["skills"] == ["alpha", "beta"]

    def test_quoted_values(self, tmp_path: Path):
        f = tmp_path / "test.md"
        f.write_text('---\ndescription: "A quoted value"\n---\n')
        result = parse_front_matter(f)
        assert result["description"] == "A quoted value"

    def test_missing_front_matter_raises(self, tmp_path: Path):
        f = tmp_path / "test.md"
        f.write_text("# No front matter here")
        with pytest.raises(DocgenError, match="Missing YAML front-matter"):
            parse_front_matter(f)


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------
class TestExtract:
    def test_extract_agent(self, nwave_tree: Path):
        path = nwave_tree / "nWave" / "agents" / "nw-crafter.md"
        agent = extract_agent(path)
        assert agent["name"] == "nw-crafter"
        assert agent["model"] == "sonnet"
        assert agent["tools"] == ["Read", "Write", "Edit"]
        assert agent["max_turns"] == 30
        assert agent["skills"] == ["tdd", "refactoring"]

    def test_extract_command(self, nwave_tree: Path):
        path = nwave_tree / "nWave" / "tasks" / "nw" / "deliver.md"
        cmd = extract_command(path)
        assert cmd["name"] == "deliver"
        assert "DELIVER" in cmd["description"]

    def test_extract_skill(self, nwave_tree: Path):
        path = nwave_tree / "nWave" / "skills" / "crafter" / "tdd.md"
        skill = extract_skill(path)
        assert skill["name"] == "tdd"
        assert skill["agent_dir"] == "crafter"

    def test_extract_template(self, nwave_tree: Path):
        path = nwave_tree / "nWave" / "templates" / "deliver-tdd.yaml"
        tmpl = extract_template(path)
        assert tmpl["name"] == "deliver-tdd"
        assert tmpl["type"] == "deliver-tdd"
        assert tmpl["version"] == "1.0.0"

    def test_missing_required_field_raises(self, tmp_path: Path):
        f = tmp_path / "bad.md"
        f.write_text("---\nfoo: bar\n---\n")
        with pytest.raises(DocgenError, match="Missing required fields"):
            extract_agent(f)


# ---------------------------------------------------------------------------
# Enrich
# ---------------------------------------------------------------------------
class TestEnrich:
    def test_valid_cross_refs(self, nwave_tree: Path):
        paths = {
            "agents": list((nwave_tree / "nWave" / "agents").glob("*.md")),
            "commands": list((nwave_tree / "nWave" / "tasks" / "nw").glob("*.md")),
            "skills": list((nwave_tree / "nWave" / "skills").rglob("*.md")),
            "templates": list((nwave_tree / "nWave" / "templates").glob("*.yaml")),
        }
        data = extract_all(paths)
        enriched = enrich(data)
        assert len(enriched["agents"]) == 1

    def test_broken_agent_skill_ref_raises(self):
        data = {
            "agents": [
                {
                    "name": "nw-test",
                    "skills": ["nonexistent"],
                    "tools": [],
                    "description": "",
                    "model": "",
                    "max_turns": 0,
                    "source_path": "",
                }
            ],
            "commands": [],
            "skills": [],
            "templates": [],
        }
        with pytest.raises(DocgenError, match="references skill 'nonexistent'"):
            enrich(data)

    def test_orphan_skill_raises(self):
        data = {
            "agents": [
                {
                    "name": "nw-test",
                    "skills": [],
                    "tools": [],
                    "description": "",
                    "model": "",
                    "max_turns": 0,
                    "source_path": "",
                }
            ],
            "commands": [],
            "skills": [
                {
                    "name": "orphan",
                    "description": "",
                    "agent_dir": "no-such-agent",
                    "source_path": "",
                }
            ],
            "templates": [],
        }
        with pytest.raises(DocgenError, match="no matching agent"):
            enrich(data)


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
class TestRender:
    def test_render_produces_all_pages(self, nwave_tree: Path):
        paths = {
            "agents": list((nwave_tree / "nWave" / "agents").glob("*.md")),
            "commands": list((nwave_tree / "nWave" / "tasks" / "nw").glob("*.md")),
            "skills": list((nwave_tree / "nWave" / "skills").rglob("*.md")),
            "templates": list((nwave_tree / "nWave" / "templates").glob("*.yaml")),
        }
        data = enrich(extract_all(paths))
        pages = render(data)

        assert "index.md" in pages
        assert "agents/index.md" in pages
        assert "commands/index.md" in pages
        assert "skills/index.md" in pages
        assert "templates/index.md" in pages
        assert "agents/nw-crafter.md" in pages

    def test_master_index_has_counts(self, nwave_tree: Path):
        paths = {
            "agents": list((nwave_tree / "nWave" / "agents").glob("*.md")),
            "commands": list((nwave_tree / "nWave" / "tasks" / "nw").glob("*.md")),
            "skills": list((nwave_tree / "nWave" / "skills").rglob("*.md")),
            "templates": list((nwave_tree / "nWave" / "templates").glob("*.yaml")),
        }
        data = enrich(extract_all(paths))
        index = render(data)["index.md"]
        assert "1 agents" in index
        assert "1 commands" in index
        assert "2 skills" in index

    def test_agent_detail_lists_skills(self, nwave_tree: Path):
        paths = {
            "agents": list((nwave_tree / "nWave" / "agents").glob("*.md")),
            "commands": list((nwave_tree / "nWave" / "tasks" / "nw").glob("*.md")),
            "skills": list((nwave_tree / "nWave" / "skills").rglob("*.md")),
            "templates": list((nwave_tree / "nWave" / "templates").glob("*.yaml")),
        }
        data = enrich(extract_all(paths))
        page = render(data)["agents/nw-crafter.md"]
        assert "tdd" in page
        assert "refactoring" in page


# ---------------------------------------------------------------------------
# Write + Check
# ---------------------------------------------------------------------------
class TestWriteAndCheck:
    def test_write_then_check_passes(self, nwave_tree: Path, tmp_path: Path):
        output_dir = tmp_path / "output"
        pages = run_pipeline(nwave_tree, output_dir)
        write_pages(pages, output_dir)
        assert check_pages(pages, output_dir) == []

    def test_check_detects_missing(self, tmp_path: Path):
        pages = {"missing.md": "content"}
        stale = check_pages(pages, tmp_path)
        assert len(stale) == 1
        assert "missing" in stale[0]

    def test_check_detects_stale(self, tmp_path: Path):
        out = tmp_path / "file.md"
        out.write_text("old content")
        stale = check_pages({"file.md": "new content"}, tmp_path)
        assert len(stale) == 1
        assert "stale" in stale[0]


# ---------------------------------------------------------------------------
# Fix 1: Skill links in agent detail
# ---------------------------------------------------------------------------
class TestSkillLinks:
    def test_agent_detail_links_skills_to_source(self, nwave_tree: Path):
        paths = {
            "agents": list((nwave_tree / "nWave" / "agents").glob("*.md")),
            "commands": list((nwave_tree / "nWave" / "tasks" / "nw").glob("*.md")),
            "skills": list((nwave_tree / "nWave" / "skills").rglob("*.md")),
            "templates": list((nwave_tree / "nWave" / "templates").glob("*.yaml")),
        }
        data = enrich(extract_all(paths))
        pages = render(data)
        page = pages["agents/nw-crafter.md"]
        # Skills link to the in-site reference page (stays inside the doc root,
        # so it resolves on the published site instead of escaping to GitHub).
        assert "[tdd](../skills/crafter-tdd.md)" in page
        assert "[refactoring](../skills/crafter-refactoring.md)" in page
        # The per-skill pages exist and (no catalog → all released) link source.
        assert "skills/crafter-tdd.md" in pages
        assert "github.com/nWave-ai/nWave/blob/main" in pages["skills/crafter-tdd.md"]

    def test_no_generated_md_link_escapes_doc_root(self, nwave_tree: Path):
        """Invariant: no generated relative .md link escapes docs/reference/.

        This is the regression guard for the nw-documentarist-reviewer class of
        bug — generated pages must not link out of the published doc root.
        """
        import posixpath
        import re

        link_re = re.compile(r"\]\(([^)]+)\)")
        paths = {
            "agents": list((nwave_tree / "nWave" / "agents").glob("*.md")),
            "commands": list((nwave_tree / "nWave" / "tasks" / "nw").glob("*.md")),
            "skills": list((nwave_tree / "nWave" / "skills").rglob("*.md")),
            "templates": list((nwave_tree / "nWave" / "templates").glob("*.yaml")),
        }
        pages = render(enrich(extract_all(paths)))
        for relpath, content in pages.items():
            base = (Path("docs/reference") / relpath).parent.as_posix()
            for url in link_re.findall(content):
                if url.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                target = posixpath.normpath(posixpath.join(base, url.split("#")[0]))
                assert target.startswith("docs/reference"), (
                    f"{relpath}: link escapes doc root -> {url} ({target})"
                )

    def test_public_skill_page_omits_private_agents(self, tmp_path: Path):
        """A released skill page must not name a private agent in 'Used by'.

        Released skill pages ship to the public repo; naming a private agent
        there leaks it and links to a stripped agent page. Uses a real catalog
        fixture (the synthetic nwave_tree has none, so it can't catch this).
        """
        nw = tmp_path / "nWave"
        (nw / "agents").mkdir(parents=True)
        (nw / "skills" / "nw-shared").mkdir(parents=True)
        (nw / "framework-catalog.yaml").write_text(
            "wave_phases:\n- DISCUSS\nagents:\n"
            "  pub:\n    public: true\n  priv:\n    public: false\n",
            encoding="utf-8",
        )
        for name in ("pub", "priv"):
            (nw / "agents" / f"nw-{name}.md").write_text(
                f"---\nname: nw-{name}\ndescription: A {name} agent\n"
                "skills:\n  - nw-shared\n---\n# body\n",
                encoding="utf-8",
            )
        (nw / "skills" / "nw-shared" / "SKILL.md").write_text(
            "---\nname: nw-shared\ndescription: shared skill\n---\n# body\n",
            encoding="utf-8",
        )
        pages = run_pipeline(tmp_path, tmp_path / "docs" / "reference")
        page = pages["skills/nw-shared.md"]  # released (owned by public 'pub')
        assert "nw-pub" in page  # public user is listed
        assert "nw-priv" not in page  # private user must be filtered out

    def test_agent_index_and_detail_label_preloaded_skills(self, nwave_tree: Path):
        """Eager preload (frontmatter-only) is labeled distinctly from
        conditional use so readers don't conflate the two channels."""
        paths = {
            "agents": list((nwave_tree / "nWave" / "agents").glob("*.md")),
            "commands": list((nwave_tree / "nWave" / "tasks" / "nw").glob("*.md")),
            "skills": list((nwave_tree / "nWave" / "skills").rglob("*.md")),
            "templates": list((nwave_tree / "nWave" / "templates").glob("*.yaml")),
        }
        pages = render(enrich(extract_all(paths)))
        assert "| Preloaded skills |" in pages["agents/index.md"]
        assert "| Skills |" not in pages["agents/index.md"]
        detail = pages["agents/nw-crafter.md"]
        assert "## Preloaded skills" in detail
        assert "## Skills\n" not in detail

    def test_real_tree_lists_conditional_owner_in_skill_used_by(self):
        """On the real tree, nw-acceptance-designer owns nw-property-based-testing
        via role-skill-loading.yaml's phase field, not its frontmatter — the
        generated skill page's 'Used by' must still surface it."""
        from scripts.docgen import scan

        root = Path(__file__).resolve().parents[1]
        pages = render(enrich(extract_all(scan(root))), root=root)
        page = pages["skills/nw-property-based-testing.md"]
        assert "nw-acceptance-designer" in page
        agent_frontmatter = (
            root / "nWave" / "agents" / "nw-acceptance-designer.md"
        ).read_text(encoding="utf-8")
        front, _, _ = agent_frontmatter.partition("\n---\n")
        assert "property-based-testing" not in front


class TestWaveGrouping:
    @pytest.mark.parametrize(
        "description,expected_wave",
        [
            ("Handles DISCOVER wave tasks", "DISCOVER"),
            ("Use for DISCUSS wave planning", "DISCUSS"),
            ("Runs before DESIGN wave", "DESIGN"),
            ("DISTILL wave acceptance tests", "DISTILL"),
            ("DELIVER wave implementation", "DELIVER"),
            ("DEVOPS wave deployment", "DEVOPS"),
            ("A utility agent", "Other"),
        ],
    )
    def test_infer_wave(self, description: str, expected_wave: str):
        assert _infer_wave(description) == expected_wave

    def test_agents_index_has_wave_sections(self, nwave_tree: Path):
        paths = {
            "agents": list((nwave_tree / "nWave" / "agents").glob("*.md")),
            "commands": list((nwave_tree / "nWave" / "tasks" / "nw").glob("*.md")),
            "skills": list((nwave_tree / "nWave" / "skills").rglob("*.md")),
            "templates": list((nwave_tree / "nWave" / "templates").glob("*.yaml")),
        }
        data = enrich(extract_all(paths))
        page = render(data)["agents/index.md"]
        # nw-crafter has no wave keyword -> Other
        assert "## Other" in page
        assert "## All Agents" in page

    def test_agent_detail_shows_wave(self, nwave_tree: Path):
        paths = {
            "agents": list((nwave_tree / "nWave" / "agents").glob("*.md")),
            "commands": list((nwave_tree / "nWave" / "tasks" / "nw").glob("*.md")),
            "skills": list((nwave_tree / "nWave" / "skills").rglob("*.md")),
            "templates": list((nwave_tree / "nWave" / "templates").glob("*.yaml")),
        }
        data = enrich(extract_all(paths))
        page = render(data)["agents/nw-crafter.md"]
        assert "**Wave:** Other" in page


# ---------------------------------------------------------------------------
# Fix 3: Bidirectional command<->agent cross-references
# ---------------------------------------------------------------------------
class TestCommandAgentCrossRefs:
    def test_extract_command_finds_agent_refs(self, nwave_tree: Path):
        path = nwave_tree / "nWave" / "tasks" / "nw" / "deliver.md"
        cmd = extract_command(path)
        assert "nw-crafter" in cmd["agents"]

    def test_enrich_populates_agent_commands(self, nwave_tree: Path):
        paths = {
            "agents": list((nwave_tree / "nWave" / "agents").glob("*.md")),
            "commands": list((nwave_tree / "nWave" / "tasks" / "nw").glob("*.md")),
            "skills": list((nwave_tree / "nWave" / "skills").rglob("*.md")),
            "templates": list((nwave_tree / "nWave" / "templates").glob("*.yaml")),
        }
        data = enrich(extract_all(paths))
        agent = data["agents"][0]
        assert "deliver" in agent["commands"]

    def test_commands_index_has_agents_column(self, nwave_tree: Path):
        paths = {
            "agents": list((nwave_tree / "nWave" / "agents").glob("*.md")),
            "commands": list((nwave_tree / "nWave" / "tasks" / "nw").glob("*.md")),
            "skills": list((nwave_tree / "nWave" / "skills").rglob("*.md")),
            "templates": list((nwave_tree / "nWave" / "templates").glob("*.yaml")),
        }
        data = enrich(extract_all(paths))
        page = render(data)["commands/index.md"]
        assert "Agents" in page
        assert "[nw-crafter](../agents/nw-crafter.md)" in page

    def test_agent_detail_has_commands_section(self, nwave_tree: Path):
        paths = {
            "agents": list((nwave_tree / "nWave" / "agents").glob("*.md")),
            "commands": list((nwave_tree / "nWave" / "tasks" / "nw").glob("*.md")),
            "skills": list((nwave_tree / "nWave" / "skills").rglob("*.md")),
            "templates": list((nwave_tree / "nWave" / "templates").glob("*.yaml")),
        }
        data = enrich(extract_all(paths))
        page = render(data)["agents/nw-crafter.md"]
        assert "## Commands" in page
        assert "`/nw-deliver`" in page


# ---------------------------------------------------------------------------
# Integration: full pipeline on real nWave tree
# ---------------------------------------------------------------------------
class TestIntegration:
    """Run against the actual nWave directory if available."""

    @pytest.fixture
    def real_root(self) -> Path:
        root = Path(__file__).resolve().parent.parent
        if not (root / "nWave" / "agents").exists():
            pytest.skip("nWave directory not found")
        return root

    def test_full_pipeline_succeeds(self, real_root: Path):
        pages = run_pipeline(real_root, real_root / "docs" / "generated")
        assert len(pages) > 5

    def test_standalone_entrypoint_uses_worktree_public_skill_projection(
        self, real_root: Path, tmp_path: Path
    ) -> None:
        """Direct script execution resolves this worktree's shared catalog.

        CONTRACT_SHAPE: bounded-change
        """
        expected_public_shared = {
            "nw-auto",
            "nw-pbt-dotnet",
            "nw-pbt-erlang-elixir",
            "nw-pbt-go",
            "nw-pbt-haskell",
            "nw-pbt-jvm",
            "nw-pbt-python",
            "nw-pbt-rust",
            "nw-pbt-typescript",
        }
        output_dir = tmp_path / "reference"

        result = subprocess.run(
            [
                sys.executable,
                str(real_root / "scripts" / "docgen.py"),
                "--root",
                str(real_root),
                "--output-dir",
                str(output_dir),
            ],
            cwd=real_root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, result.stderr
        generated = {path.stem for path in (output_dir / "skills").glob("*.md")}
        assert expected_public_shared <= generated

    def test_artifact_counts_match_source(self, real_root: Path):
        from scripts.docgen import scan

        paths = scan(real_root)
        pages = run_pipeline(real_root, real_root / "docs" / "generated")
        index = pages["index.md"]
        assert f"{len(paths['agents'])} agents" in index
        assert f"{len(paths['commands'])} commands" in index
        assert f"{len(paths['skills'])} skills" in index

    def test_all_agents_have_detail_pages(self, real_root: Path):
        from scripts.docgen import scan

        paths = scan(real_root)
        pages = run_pipeline(real_root, real_root / "docs" / "generated")
        agent_pages = [
            k for k in pages if k.startswith("agents/") and k != "agents/index.md"
        ]
        assert len(agent_pages) == len(paths["agents"])

    def test_cross_links_valid(self, real_root: Path):
        """Pipeline completes without DocgenError means all cross-refs are valid."""
        pages = run_pipeline(real_root, real_root / "docs" / "generated")
        assert pages  # No DocgenError raised

    def test_check_passes_against_real_repo(self, real_root: Path):
        """`docgen --check` must accept the live repo as-is.

        Nothing wires `docgen --check` into pre-commit/CI today (mikado D28a
        finding, 2026-07-29) -- a des-command-catalog GENERATED region or a
        catalog-authored command-guide front-matter value can drift silently
        (e.g. a new `_SubcommandRow` landing in the registry without a
        docgen re-run) and nothing red-flags it until someone happens to run
        docgen by hand. This test is that flag: it re-runs the SAME checks
        `docgen --check` runs and fails naming every stale asset, so this
        drift class is caught by the ordinary test suite instead of going
        unnoticed indefinitely.
        """
        from scripts.docgen import (
            check_command_front_matter,
            check_generated_regions,
            project_command_front_matter,
            project_generated_regions,
            scan,
        )

        asset_paths = scan(real_root)
        region_projections = project_generated_regions(real_root, asset_paths)
        front_matter_projections = project_command_front_matter(real_root)
        stale = check_generated_regions(
            real_root, region_projections
        ) + check_command_front_matter(real_root, front_matter_projections)
        assert not stale, (
            "docgen --check would refuse the live repo -- regenerate with "
            "`uv run python scripts/docgen.py` and commit the diff:\n"
            + "\n".join(stale)
        )


# ---------------------------------------------------------------------------
# Link validation
# ---------------------------------------------------------------------------
class TestCheckLinks:
    def test_valid_links_pass(self, tmp_path: Path):
        """Valid relative links between files produce no errors."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "target.md").write_text("# Target")
        (tmp_path / "docs" / "source.md").write_text("[link](target.md)")
        assert check_links(tmp_path, ["docs"]) == []

    def test_broken_relative_link_detected(self, tmp_path: Path):
        """Broken relative link is reported with file:line format."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "source.md").write_text("[broken](nonexistent.md)")
        broken = check_links(tmp_path, ["docs"])
        assert len(broken) == 1
        assert "source.md:1" in broken[0]
        assert "nonexistent.md" in broken[0]

    def test_external_urls_skipped(self, tmp_path: Path):
        """External URLs (https://) are not validated."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "source.md").write_text(
            "[ext](https://example.com)\n[mail](mailto:a@b.com)"
        )
        assert check_links(tmp_path, ["docs"]) == []

    def test_anchor_links_file_verified(self, tmp_path: Path):
        """file.md#section passes when file.md exists (anchor not validated)."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "target.md").write_text("# Section")
        (tmp_path / "docs" / "source.md").write_text("[link](target.md#section)")
        assert check_links(tmp_path, ["docs"]) == []

    def test_anchor_only_links_skipped(self, tmp_path: Path):
        """Anchor-only links (#section) are skipped."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "source.md").write_text("[link](#section)")
        assert check_links(tmp_path, ["docs"]) == []

    def test_single_file_target(self, tmp_path: Path):
        """Can check a single file (not just directories)."""
        readme = tmp_path / "README.md"
        readme.write_text("[link](nonexistent.md)")
        broken = check_links(tmp_path, ["README.md"])
        assert len(broken) == 1

    def test_integration_real_tree(self):
        """Run check_links on actual repo docs — validates our own docs."""
        root = Path(__file__).resolve().parent.parent
        if not (root / "docs" / "guides").exists():
            pytest.skip("docs/guides not found")
        broken = check_links(root, ["README.md", "docs/guides", "docs/reference"])
        assert broken == [], "Broken links in repo:\n" + "\n".join(broken)


# ---------------------------------------------------------------------------
# Regression: write_pages MUST NOT delete foreign (hand-authored) files
# ---------------------------------------------------------------------------
def _snapshot_dir(output_dir: Path) -> dict[str, str]:
    """Snapshot every file under output_dir as {relative_path: content}."""
    snapshot: dict[str, str] = {}
    if not output_dir.exists():
        return snapshot
    for path in output_dir.rglob("*"):
        if path.is_file():
            rel = path.relative_to(output_dir).as_posix()
            snapshot[rel] = path.read_text(encoding="utf-8")
    return snapshot


class TestPreservesUserAuthoredDocs:
    """write_pages MUST perform surgical writes — never delete foreign files.

    Regression for RCA `docs/analysis/rca-pre-push-hook-untracked-deletion-2026-05-06.md`.
    Predicate: delta(output_dir) ⊆ pages.keys(). Foreign files (hand-authored,
    untracked, or tracked-but-not-in-page-set) are preserved untouched.
    """

    def test_foreign_files_preserved_via_state_delta(self, tmp_path: Path):
        """State-delta predicate: only files in pages.keys() may change."""
        output_dir = tmp_path / "reference"
        output_dir.mkdir()

        # Foreign top-level file (hand-authored, not in pages)
        foreign_top = output_dir / "user-doc.md"
        foreign_top.write_text("hand-authored top-level\n", encoding="utf-8")

        # Foreign nested file
        nested_dir = output_dir / "subdir"
        nested_dir.mkdir()
        foreign_nested = nested_dir / "user-deep.md"
        foreign_nested.write_text("hand-authored deep\n", encoding="utf-8")

        # Pages the renderer owns
        pages = {
            "index.md": "# generated index\n",
            "agents/nw-foo.md": "# generated agent doc\n",
        }

        before = _snapshot_dir(output_dir)
        write_pages(pages, output_dir)
        after = _snapshot_dir(output_dir)

        # Universe = (every slot present before) UNION (every page key)
        universe = set(before.keys()) | set(pages.keys())

        # Expected per-slot:
        #   foreign files (in `before` but not in `pages`)  -> unchanged()
        #   page files (in `pages`)                          -> set_to(content)
        expected = {}
        for slot in universe:
            if slot in pages:
                expected[slot] = set_to(pages[slot])
            else:
                expected[slot] = unchanged()

        assert_state_delta(
            before=before,
            after=after,
            universe=universe,
            expected=expected,
            strict=True,
        )

        # Concrete preservation assertions (defense in depth)
        assert foreign_top.exists(), "foreign top-level file deleted by write_pages"
        assert foreign_top.read_text(encoding="utf-8") == "hand-authored top-level\n"
        assert foreign_nested.exists(), "foreign nested file deleted by write_pages"
        assert foreign_nested.read_text(encoding="utf-8") == "hand-authored deep\n"

        # Pages were written
        assert (output_dir / "index.md").read_text(encoding="utf-8") == pages[
            "index.md"
        ]
        assert (output_dir / "agents" / "nw-foo.md").read_text(
            encoding="utf-8"
        ) == pages["agents/nw-foo.md"]

    def test_creates_output_dir_if_missing(self, tmp_path: Path):
        """write_pages MUST create output_dir when it does not yet exist."""
        output_dir = tmp_path / "fresh" / "reference"
        assert not output_dir.exists()

        pages = {"index.md": "# fresh\n"}
        write_pages(pages, output_dir)

        assert output_dir.is_dir()
        assert (output_dir / "index.md").read_text(encoding="utf-8") == "# fresh\n"


# ---------------------------------------------------------------------------
# Registry <-> runtime phase-vocabulary agreement
# (F-DOCGEN-PHASE-VOCAB-COMPARATOR-ALIAS-BLIND regression coverage)
# ---------------------------------------------------------------------------
class TestRegistryRuntimePhaseVocabAgreement:
    """`check_registry_runtime_agreement` must normalize display-vocabulary
    phase tokens (EXAMINE/COMMIT) through the enum's own alias map
    (`normalize_phase_token`) before comparing against `CANONICAL_PHASES`.

    A literal, alias-blind string compare false-fails on every velocity-v2
    EXAMINE/COMMIT display token -- this reddened 8 of the ~10 real
    `mode_registry` acceptance tests on trunk (commits `58feae54b` +
    `a91bf4f6b` renamed the display vocabulary; the enum's own value-alias
    shielded Python call-sites but not this comparator).
    """

    def test_docgen_check_recognizes_examine_commit_aliases(self):
        """The real, shipped default flavor's `deliver_phase_shape` speaks the
        EXAMINE/COMMIT display vocabulary -- the comparator must normalize
        both aliases and agree with `CANONICAL_PHASES`: zero disagreements on
        the live repo tree. This is `docgen --check`'s own registry-agreement
        leg, run directly (not just observed via CLI exit code)."""
        root = Path(__file__).resolve().parent.parent
        if not (root / "nWave" / "flavors").exists():
            pytest.skip("nWave/flavors directory not found")

        disagreements = check_registry_runtime_agreement(root)

        assert disagreements == [], (
            "docgen --check must recognize EXAMINE/COMMIT as display-vocab "
            f"aliases of the canonical phase slots -- got: {disagreements}"
        )

    def test_normalize_phase_token_resolves_examine_and_commit_from_the_enum(self):
        """DRY SSOT pin: the alias resolution is DERIVED from
        `ATDDPurePhase` -- EXAMINE resolves to the enum's own
        `C_REVIEWER_AUDIT`-sharing value, COMMIT resolves to
        `D_REFACTOR_COMMIT`'s value. No second hand-authored alias table."""
        from des.domain.atdd_pure_phases import ATDDPurePhase, normalize_phase_token

        assert normalize_phase_token("EXAMINE") == ATDDPurePhase["EXAMINE"].value
        assert normalize_phase_token("COMMIT") == ATDDPurePhase.D_REFACTOR_COMMIT.value

    def test_unrecognized_phase_token_is_still_reported_as_disagreement(
        self, tmp_path: Path
    ):
        """Negative oracle: a genuinely INCORRECT phase token (neither the
        canonical name nor a recognized display-vocab alias) must still be
        caught -- alias-awareness must not become a blanket pass-anything."""
        from des.application.workflow_mode import resolve_workflow_mode

        with tempfile.TemporaryDirectory() as empty:
            # `.effective_mode`: the resolver now returns a decision OBJECT
            # (outcome + mode + reason), not a bare mode string. This site
            # uses the value as a flavor id and a filename, so the object's
            # repr would silently become the filename -- the fixture would
            # build a differently-named flavor and this negative oracle
            # would report the wrong disagreement instead of the planted one.
            resolver_default = resolve_workflow_mode(Path(empty)).effective_mode

        flavors_dir = tmp_path / "nWave" / "flavors"
        flavors_dir.mkdir(parents=True)
        (flavors_dir / f"{resolver_default}.yaml").write_text(
            textwrap.dedent(f"""\
                flavor_id: {resolver_default}
                default: true
                deliver_phase_shape: "A_GREEN -> TOTALLY_BOGUS_PHASE -> COMMIT"
            """),
            encoding="utf-8",
        )

        disagreements = check_registry_runtime_agreement(tmp_path)

        assert disagreements, (
            "an incorrect (non-canonical, non-alias) phase token must still "
            "produce a disagreement, never be silently accepted"
        )
        assert any("TOTALLY_BOGUS_PHASE" in entry for entry in disagreements), (
            f"the disagreement must name the unrecognized token. got: {disagreements}"
        )


# ---------------------------------------------------------------------------
# role-skill-loading.yaml: build-time-only universal-lens registry
# ---------------------------------------------------------------------------
_ROLE_SKILL_TARGETS = [
    "nw-acceptance-designer-reviewer",
    "nw-acceptance-designer",
    "nw-ddd-architect-reviewer",
    "nw-ddd-architect",
    "nw-functional-software-crafter",
    "nw-platform-architect-reviewer",
    "nw-platform-architect",
    "nw-software-crafter-reviewer",
    "nw-software-crafter",
    "nw-solution-architect-reviewer",
    "nw-solution-architect",
    "nw-system-designer-reviewer",
    "nw-system-designer",
]
_CRAFTER_ROLES = ["nw-software-crafter", "nw-functional-software-crafter"]
# {authoring role: single-owner reviewer} — every design-lens architect that
# projects native algebra + certainty on_demand, paired with its reviewer.
_ARCHITECT_REVIEWER_PAIRS = [
    ("nw-solution-architect", "nw-solution-architect-reviewer"),
    ("nw-ddd-architect", "nw-ddd-architect-reviewer"),
    ("nw-system-designer", "nw-system-designer-reviewer"),
    ("nw-platform-architect", "nw-platform-architect-reviewer"),
]


class TestRoleSkillLoadingRegistry:
    """`role-skill-loading.yaml` is parsed ONLY at docgen (build) time -- there
    is no runtime resolver -- so its guarantees are enforced here, once, on
    the registry + its rendering into every targeted agent's installed spec.
    """

    @pytest.fixture(scope="class")
    def root(self) -> Path:
        root = Path(__file__).resolve().parent.parent
        if not (root / "nWave" / "data" / "role-skill-loading.yaml").exists():
            pytest.skip("role-skill-loading.yaml not found")
        return root

    @pytest.fixture(scope="class")
    def roles(self, root: Path) -> dict:
        import yaml

        return yaml.safe_load(
            (root / "nWave" / "data" / "role-skill-loading.yaml").read_text()
        )["roles"]

    def test_registry_matches_its_own_closed_schema(self, root: Path, roles: dict):
        import jsonschema
        import yaml

        schema = yaml.safe_load(
            (root / "nWave" / "data" / "role-skill-loading.schema.yaml").read_text()
        )
        registry = yaml.safe_load(
            (root / "nWave" / "data" / "role-skill-loading.yaml").read_text()
        )
        jsonschema.validate(registry, schema)

    def test_schema_accepts_valid_catalog_only(self, root: Path):
        import jsonschema
        import yaml

        schema = yaml.safe_load(
            (root / "nWave" / "data" / "role-skill-loading.schema.yaml").read_text()
        )
        registry = {
            "version": 1,
            "roles": {
                "nw-example": {"catalog_only": ["nw-a", "nw-b"]},
            },
        }
        jsonschema.validate(registry, schema)

    @pytest.mark.parametrize(
        "catalog_only",
        [
            [],
            ["nw-a", "nw-a"],
            ["not-nw-prefixed"],
            [123],
        ],
        ids=["empty", "duplicate", "bad-pattern", "wrong-type"],
    )
    def test_schema_rejects_invalid_catalog_only(self, root: Path, catalog_only):
        import jsonschema
        import yaml

        schema = yaml.safe_load(
            (root / "nWave" / "data" / "role-skill-loading.schema.yaml").read_text()
        )
        registry = {
            "version": 1,
            "roles": {"nw-example": {"catalog_only": catalog_only}},
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(registry, schema)

    def test_schema_rejects_unknown_role_field(self, root: Path):
        import jsonschema
        import yaml

        schema = yaml.safe_load(
            (root / "nWave" / "data" / "role-skill-loading.schema.yaml").read_text()
        )
        registry = {
            "version": 1,
            "roles": {"nw-example": {"catalog_only": ["nw-a"], "bogus": True}},
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(registry, schema)

    def test_real_atd_frontmatter_has_no_skills_field(self, root: Path):
        text = (root / "nWave" / "agents" / "nw-acceptance-designer.md").read_text()
        import yaml

        fm = yaml.safe_load(text.split("---")[1])
        assert "skills" not in fm, (
            "nw-acceptance-designer.md frontmatter must not eagerly preload -- "
            f"found skills: {fm.get('skills')}"
        )

    def test_atd_generated_body_excludes_catalog_only_and_includes_code_analysis(
        self, root: Path, roles: dict
    ):
        body = _role_skill_loading_body("nw-acceptance-designer", root)
        atd_entry = roles["nw-acceptance-designer"]
        for skill in atd_entry.get("catalog_only", []):
            assert f"Skill({skill})" not in body, (
                f"catalog_only skill {skill} must not render in the generated body"
            )
        assert "Invoke Skill(nw-code-analysis-port) ON-TRIGGER" in body, (
            "nw-code-analysis-port must render ON-TRIGGER"
        )
        assert "F — code/test fact query" in body

    @pytest.mark.parametrize("agent_id", _ROLE_SKILL_TARGETS)
    def test_installed_spec_has_exactly_one_generated_region(
        self, root: Path, agent_id: str
    ):
        body = (root / "nWave" / "agents" / f"{agent_id}.md").read_text()
        assert body.count("GENERATED:role-skill-loading START") == 1

    @pytest.mark.parametrize("agent_id", _ROLE_SKILL_TARGETS)
    def test_every_trigger_is_lazy_never_an_eager_always_preload(
        self, root: Path, roles: dict, agent_id: str
    ):
        """Every phase and on_demand skill appears as ON-TRIGGER, never NOW."""
        entry = roles[agent_id]
        for field in ("on_demand", "phase"):
            for trigger in entry.get(field, {}).values():
                assert not trigger.lower().startswith("always"), (
                    f"{agent_id}.{field} trigger {trigger!r} is eager, not "
                    "lazy -- role-skill-loading rows load on a fired trigger, "
                    "never unconditionally"
                )
        # Verify rendered body emits only ON-TRIGGER, never NOW for phase skills
        body = _role_skill_loading_body(agent_id, root)
        phase_skills = entry.get("phase", {})
        for skill in phase_skills:
            assert f"Invoke Skill({skill}) ON-TRIGGER" in body, (
                f"{agent_id}: phase skill {skill} must render as ON-TRIGGER, never NOW"
            )
            assert f"Invoke Skill({skill}) NOW" not in body, (
                f"{agent_id}: phase skill {skill} must not render as NOW"
            )

    def test_reviewers_mirror_only_on_demand_lenses_never_authoring_phase_rows(
        self, roles: dict
    ):
        for agent_id, entry in roles.items():
            reviewed = entry.get("reviewer_of")
            if not reviewed or len(reviewed) != 1:
                continue
            reviewed_entry = roles[reviewed[0]]
            assert set(entry.get("on_demand", {})).isdisjoint(
                reviewed_entry.get("phase", {})
            ), f"{agent_id} must not author the reviewed role's phase-owned skills"

    @pytest.mark.parametrize("author,reviewer", _ARCHITECT_REVIEWER_PAIRS)
    def test_architect_projects_algebra_certainty_reviewer_mirrors_lens_only(
        self, root: Path, roles: dict, author: str, reviewer: str
    ):
        """Cross-layer projection law (ADR-SSOT-002 6a, 2026-08-13): solution
        architect, DDD architect, system designer and platform architect each
        project native algebra + certainty + stress-analysis on_demand; each
        single-owner reviewer mirrors exactly those on-demand lenses and
        never the author's own phase- or paradigm-owned rows. One dense
        parametrized law replaces four near-duplicate per-role test bodies."""
        author_entry = roles[author]
        for lens in (
            "nw-algebraic-design-protocol",
            "nw-certainty-by-construction",
            "nw-stress-analysis",
        ):
            assert lens in author_entry.get("on_demand", {}), (
                f"{author} must project native {lens} on_demand"
            )

        author_body = _role_skill_loading_body(author, root)
        reviewer_body = _role_skill_loading_body(reviewer, root)
        for lens in (
            "nw-algebraic-design-protocol",
            "nw-certainty-by-construction",
            "nw-stress-analysis",
        ):
            assert f"Invoke Skill({lens}) ON-TRIGGER" in author_body
            assert f"Invoke Skill({lens}) ON-TRIGGER" in reviewer_body

        reviewer_entry = roles[reviewer]
        assert reviewer_entry.get("reviewer_of") == [author]
        for target in author_entry.get("paradigm", {}).values():
            assert f"Skill({target})" not in reviewer_body, (
                f"{reviewer} must not inherit {author}'s paradigm-owned {target}"
            )
        for skill in author_entry.get("phase", {}):
            assert f"Skill({skill})" not in reviewer_body, (
                f"{reviewer} must not inherit {author}'s phase-owned {skill}"
            )

    def test_stress_analysis_owned_only_by_architects_never_atd_crafters_examiner(
        self, root: Path, roles: dict
    ):
        """`nw-stress-analysis` is lazy on_demand exclusively on the four
        architect roles (mirrored by their single-owner reviewers). ATD, both
        crafters, the crafter reviewer and the examiner must neither declare
        nor render it."""
        architects = [author for author, _ in _ARCHITECT_REVIEWER_PAIRS]
        for role in architects:
            assert "nw-stress-analysis" in roles[role].get("on_demand", {})

        excluded = [
            "nw-acceptance-designer",
            "nw-acceptance-designer-reviewer",
            "nw-software-crafter",
            "nw-functional-software-crafter",
            "nw-software-crafter-reviewer",
            "nw-user-examiner",
        ]
        for role in excluded:
            entry = roles.get(role, {})
            for field in ("on_demand", "phase", "catalog_only"):
                values = entry.get(field, {})
                names = values if isinstance(values, list) else values.keys()
                assert "nw-stress-analysis" not in names, (
                    f"{role} must not own nw-stress-analysis via {field}"
                )
            body = _role_skill_loading_body(role, root)
            assert "nw-stress-analysis" not in body, (
                f"{role} must not render nw-stress-analysis"
            )

    def test_stress_analysis_skill_is_native_invocable_not_disabled(self, root: Path):
        """`nw-stress-analysis` is rendered as a native `Invoke Skill(...)
        ON-TRIGGER` row -- `disable-model-invocation: true` would mechanically
        contradict that (see test_atd_native_trigger_spatial_first.py's
        established law). It stays non-user-invocable (loaded only via the
        registry trigger, never a direct user command)."""
        text = (
            root / "nWave" / "skills" / "nw-stress-analysis" / "SKILL.md"
        ).read_text(encoding="utf-8")
        front = text.split("---")[1]
        assert "user-invocable: false" in front
        assert "disable-model-invocation" not in front

    def test_residuality_flag_is_force_on_not_sole_authoritative_trigger(
        self, root: Path
    ):
        """`--residuality` remains the explicit force-on path into
        `nw-stress-analysis`'s semantic trigger, but no hand-authored
        normative prose may claim it is the ONLY trigger -- that phrasing
        contradicts the registry-driven semantic-trigger set."""
        targets = [
            root / "nWave" / "agents" / "nw-solution-architect.md",
            root / "nWave" / "skills" / "nw-design" / "SKILL.md",
            root / "nWave" / "skills" / "nw-design-discovery-flow" / "SKILL.md",
            root / "nWave" / "skills" / "nw-stress-analysis" / "SKILL.md",
        ]
        stale_phrases = (
            "Only with --residuality",
            "flag only",
            "--residuality flag only",
        )
        for path in targets:
            text = path.read_text(encoding="utf-8")
            for phrase in stale_phrases:
                assert phrase not in text, (
                    f"{path.name} still carries stale sole-trigger phrasing: {phrase!r}"
                )
        stress_text = (
            root / "nWave" / "skills" / "nw-stress-analysis" / "SKILL.md"
        ).read_text(encoding="utf-8")
        assert "force-on" in stress_text

    def test_no_crafter_role_authors_a_language_pbt_lens(self, roles: dict):
        for agent_id in _CRAFTER_ROLES:
            assert "language_pbt" not in roles[agent_id], (
                f"{agent_id} carries language_pbt -- PBT authoring is owned "
                "exclusively by nw-acceptance-designer, never a crafter"
            )

    def test_atd_auto_route_projects_author_skills_and_lenses_on_trigger(
        self, root: Path, roles: dict
    ):
        """ATD's author lenses and eight language PBT deep dives render
        ON-TRIGGER with zero NOW rows; generic PBT is phase-owned (author
        only, never on_demand); the reviewer mirrors on_demand lenses only,
        never the phase-owned generic PBT skill."""
        body = _role_skill_loading_body("nw-acceptance-designer", root)
        assert "NOW" not in body, f"ATD rendered body must have zero NOW rows: {body}"

        for lens in (
            "nw-test-design-mandates",
            "nw-property-based-testing",
            "nw-algebraic-design-protocol",
            "nw-certainty-by-construction",
        ):
            assert f"Invoke Skill({lens}) ON-TRIGGER" in body, (
                f"{lens} must render as ON-TRIGGER"
            )

        pbt_rows = [
            line for line in body.splitlines() if "Invoke ONE Skill(nw-pbt-" in line
        ]
        assert len(pbt_rows) == 8, f"expected 8 language PBT rows, got {pbt_rows}"

        atd_entry = roles["nw-acceptance-designer"]
        assert "nw-property-based-testing" in atd_entry.get("phase", {}), (
            "nw-property-based-testing must be in ATD phase (author-only)"
        )
        assert "nw-property-based-testing" not in atd_entry.get("on_demand", {}), (
            "nw-property-based-testing must not be in ATD on_demand"
        )

        reviewer_body = _role_skill_loading_body(
            "nw-acceptance-designer-reviewer", root
        )
        assert "nw-property-based-testing" not in reviewer_body, (
            "reviewer must not include phase-owned nw-property-based-testing"
        )
        assert "nw-algebraic-design-protocol" in reviewer_body, (
            "reviewer must mirror on_demand algebra lens"
        )
        assert "nw-certainty-by-construction" in reviewer_body, (
            "reviewer must mirror on_demand certainty lens"
        )

        pbt_trigger = roles["nw-acceptance-designer"]["phase"][
            "nw-property-based-testing"
        ]
        assert "BROAD_INPUT_DOMAIN" in pbt_trigger
        assert "BROAD_INPUT_DOMAIN" in body
        assert "BROAD_INPUT_DOMAIN" not in reviewer_body, (
            "the reviewer must not inherit the ATD-only PBT authoring obligation"
        )

    def test_atd_route_contract_paragraph_mandates_native_skill_and_obligation_order(
        self, root: Path
    ):
        """K4 (2026-08-13): the hand-authored paragraph wrapping the generated
        Skill rows must never call them "Read rows" or send Claude to the Read
        tool -- that exact language let a real ATD run skip algebra/certainty/
        PBT before authoring while still emitting BROAD_INPUT_DOMAIN. It must
        derive obligation tokens before authoring, invoke every fired row's
        Skill(...) natively, and bind BROAD_INPUT_DOMAIN to both the generic
        and language-matched PBT rows."""
        text = (root / "nWave" / "agents" / "nw-acceptance-designer.md").read_text()
        start = text.index("**Thin Auto M/L route")
        end = text.index("<!-- GENERATED:role-skill-loading START")
        paragraph = " ".join(text[start:end].split())

        for forbidden in ("Read row", "Read directive", "with the Read tool"):
            assert forbidden not in paragraph, (
                f"ATD route-contract paragraph must not say {forbidden!r} -- "
                "the generated rows are native Skill invocations, never Read targets"
            )

        for token in (
            "Skill directive",
            "derive the applicable obligation tokens",
            "before authoring",
            "invoke each generated row's `Skill(...)` natively",
            "never a manual SKILL.md read",
            "`BROAD_INPUT_DOMAIN` fires two rows together",
            "the language-matched `nw-pbt-{lang}` row",
        ):
            assert token in paragraph, f"ATD route-contract paragraph missing: {token}"

        assert paragraph.index(
            "derive the applicable obligation tokens"
        ) < paragraph.index("invoke each generated row's `Skill(...)` natively"), (
            "obligation-token derivation must precede Skill invocation in reading order"
        )

    def test_atd_broad_input_domain_dependency_completeness_is_atd_owned(
        self, root: Path
    ):
        """ATD consumes the named PBT substrate fact and repairs only its owner.

        A runtime-missing library never excuses downgrading BROAD_INPUT_DOMAIN
        to enumerated examples, shipping an undeclared import, or reinstalling
        an unrelated dependency manifest.
        """
        text = (root / "nWave" / "agents" / "nw-acceptance-designer.md").read_text()
        start = text.index("`BROAD_INPUT_DOMAIN` is this agent's")
        end = text.index("**Spatial-first materialization (HARD):**")
        # Markdown wraps compound words after ``-``; normalize that layout so
        # this assertion protects the semantic phrase rather than line width.
        paragraph = " ".join(text[start:end].split()).replace("- ", "-")
        for token in (
            "never delegated to a crafter",
            "named substrate fact consumed from the brief",
            "dependency is declared but runtime-missing",
            "edits only the named manifest owner",
            "named direct dependency-delta install argv",
            "never a whole test-dependency-manifest reinstall",
            "Downgrading to examples",
            "an undeclared import",
            "never discharges the obligation",
        ):
            assert token in paragraph, f"BROAD_INPUT_DOMAIN paragraph missing: {token}"

    def test_atd_semantic_pbt_carveout_preserves_one_observation_across_projections(
        self, root: Path
    ):
        """A test layer cannot silently erase a declared semantic law.

        The ATD and its three mandate projections must agree on one compact
        property: representative real-port examples prove wiring, while any
        cheap generative seam proves the same promised observation through an
        explicit preservation map. Missing that map is an EVIDENCE_GAP, never
        permission to downgrade a broad law to examples.
        """
        relative_paths = (
            "nWave/agents/nw-acceptance-designer.md",
            "nWave/skills/nw-test-design-mandates/SKILL.md",
            "nWave/skills/nw-test-design-mandates-layered-mechanics/SKILL.md",
            "nWave/skills/nw-ad-distill-dod/SKILL.md",
        )
        projections = {
            path: " ".join((root / path).read_text(encoding="utf-8").split()).lower()
            for path in relative_paths
        }

        for path, projection in projections.items():
            for required in (
                "broad-input/state/failure law",
                "same promised observation",
                "preservation map",
                "evidence_gap",
                "example-only",
            ):
                assert required in projection, f"{path} omits {required!r}"

        combined = "\n".join(projections.values())
        for retired_blanket_ban in (
            "pbt decorators (`@given`, `rulebasedstatemachine`) appear only on layer 1-2 tests",
            "layers 3+ use example-only — sad paths enumerated explicitly",
            "no pbt machinery imported at those layers",
        ):
            assert retired_blanket_ban not in combined

    @pytest.mark.parametrize("agent_id", _ROLE_SKILL_TARGETS)
    def test_frontmatter_disjoint_from_effective_conditional_skills(
        self, root: Path, roles: dict, agent_id: str
    ):
        """Frontmatter skills must be disjoint from effective conditional skills.

        Effective conditional skills are: own on_demand/phase KEYS, own paradigm/
        language_pbt VALUES, and union of reviewer_of owners' on_demand KEYS.

        catalog_only must also be disjoint from that same effective set --
        it is build-time ownership only, never an eager preload or an
        ON-TRIGGER row, so it must not shadow a role's own on_demand/phase/
        paradigm/language_pbt authority.
        """
        path = root / "nWave" / "agents" / f"{agent_id}.md"
        if agent_id not in roles or not path.exists():
            pytest.skip(f"{agent_id} unavailable")

        # Compute effective conditional skills
        entry = roles[agent_id]
        effective = set()
        for field in ("on_demand", "phase"):
            effective.update(entry.get(field, {}).keys())
        for field in ("paradigm", "language_pbt"):
            effective.update(entry.get(field, {}).values())
        for owner in entry.get("reviewer_of", []):
            effective.update(roles.get(owner, {}).get("on_demand", {}).keys())

        # Load frontmatter skills
        text = path.read_text(encoding="utf-8")
        import yaml

        fm = yaml.safe_load(text.split("---")[1])
        frontmatter_skills = set(fm.get("skills") or [])

        # Assert disjointness
        overlap = effective & frontmatter_skills
        assert not overlap, f"{agent_id} frontmatter still owns {overlap}"

        # catalog_only must not shadow the role's own effective conditional skills
        catalog_only = set(entry.get("catalog_only") or [])
        catalog_overlap = catalog_only & effective
        assert not catalog_overlap, (
            f"{agent_id} catalog_only shadows effective conditional skills: "
            f"{catalog_overlap}"
        )

        # ATD-specific compact assertions
        if agent_id == "nw-acceptance-designer":
            banned = {
                "nw-property-based-testing",
                "nw-test-design-mandates",
                "nw-algebraic-design-protocol",
                "nw-certainty-by-construction",
            }
            assert not (frontmatter_skills & banned), frontmatter_skills & banned
        elif agent_id == "nw-acceptance-designer-reviewer":
            banned = {
                "nw-property-based-testing",
                "nw-algebraic-design-protocol",
                "nw-certainty-by-construction",
                "nw-ad-critique-dimensions",
                "nw-at-completeness-check",
            }
            assert not (frontmatter_skills & banned), frontmatter_skills & banned

    def test_atd_auto_route_directive_is_reachable_from_auto_terminal_branch(
        self, root: Path
    ):
        """The generated block must sit inside the Auto-reachable Route
        contract paragraph, before the Human-only branch marker -- placing it
        after `## Workflow` (as the pre-fix location did) is unreachable
        because Auto stops before that heading."""
        text = (root / "nWave" / "agents" / "nw-acceptance-designer.md").read_text()
        route_idx = text.index("## Route contract")
        human_idx = text.index("**Human route:**")
        marker_idx = text.index("GENERATED:role-skill-loading START")
        assert route_idx < marker_idx < human_idx, (
            "role-skill-loading directive must render between the Auto Route "
            "contract heading and the Human-route marker"
        )
        assert text.count("Invoke Skill(nw-algebraic-design-protocol)") == 1, (
            "the algebra directive must not be duplicated as stale hand-authored prose"
        )

    def test_oo_and_fp_crafters_read_lens_at_point_of_need_without_test_authoring(
        self, root: Path
    ):
        for agent_id, design_skill in (
            ("nw-software-crafter", "nw-code-design-oo"),
            ("nw-functional-software-crafter", "nw-code-design-fp"),
        ):
            body = _role_skill_loading_body(agent_id, root)
            assert f"Invoke Skill({design_skill})" in body, body
            assert "Invoke Skill(nw-algebraic-design-protocol)" in body, body
            assert "Invoke Skill(nw-certainty-by-construction)" in body, body
            for banned in ("nw-property-based-testing", "nw-test-design-mandates"):
                assert banned not in body, (
                    f"{agent_id} must never load a test-authoring skill -- SLIM "
                    f"scope forbids it, found {banned!r} in {body!r}"
                )

            for token in (
                "CONTESTED_LAW",
                "REPRESENTATION_CHANGE",
                "INVALID_STATE",
                "PRESERVATION",
            ):
                assert token in body, (
                    f"{agent_id}: DeliveryContract obligation {token} must "
                    "deterministically appear in the generated trigger projection"
                )

            text = (root / "nWave" / "agents" / f"{agent_id}.md").read_text()
            assert "REUSE_CANDIDATE" in text
            assert "ARCHITECTURE_BOUNDARY_CHANGE" in text
            assert "authoring or editing a test" in text

    def test_crafters_directive_is_reachable_from_dispatch_authority(self, root: Path):
        for agent_id in _CRAFTER_ROLES:
            text = (root / "nWave" / "agents" / f"{agent_id}.md").read_text()
            dispatch_idx = text.index("## Dispatch authority")
            workflow_idx = text.index("## Workflow")
            marker_idx = text.index("GENERATED:role-skill-loading START")
            assert dispatch_idx < marker_idx < workflow_idx, (
                f"{agent_id}: role-skill-loading directive must render inside "
                "Dispatch authority, the section the thin/Auto path executes"
            )
            assert text.count("Invoke Skill(nw-algebraic-design-protocol)") == 1, (
                f"{agent_id}: the algebra directive must not be duplicated as "
                "stale hand-authored prose"
            )

    @pytest.mark.parametrize("agent_id", _ROLE_SKILL_TARGETS)
    def test_frontmatter_tools_declares_skill(self, root: Path, agent_id: str):
        text = (root / "nWave" / "agents" / f"{agent_id}.md").read_text()
        tools_line = next(
            line for line in text.splitlines() if line.startswith("tools:")
        )
        tools = [tool.strip() for tool in tools_line.removeprefix("tools:").split(",")]
        assert "Skill" in tools, f"{agent_id}: frontmatter tools must declare Skill"
        assert tools.count("Skill") == 1, f"{agent_id}: Skill declared more than once"

    @pytest.mark.parametrize("agent_id", _ROLE_SKILL_TARGETS)
    def test_generated_region_invokes_skill_natively_never_reads_a_path(
        self, root: Path, agent_id: str
    ):
        text = (root / "nWave" / "agents" / f"{agent_id}.md").read_text()
        start = text.index("GENERATED:role-skill-loading START")
        end = text.index("GENERATED:role-skill-loading END")
        region = text[start:end]
        assert "Invoke" in region and "Skill(" in region, (
            f"{agent_id}: generated region must render native Skill invocations"
        )
        assert "~/.claude/skills" not in region, (
            f"{agent_id}: generated region must never render a Read path"
        )
        assert "Read `" not in region, (
            f"{agent_id}: generated region must never render a Read directive"
        )

    @pytest.mark.parametrize("agent_id", _ROLE_SKILL_TARGETS)
    def test_every_registered_role_still_projects_a_nonempty_body(
        self, root: Path, agent_id: str
    ):
        body = _role_skill_loading_body(agent_id, root)
        assert body.strip(), f"{agent_id} projected an empty role-skill-loading body"

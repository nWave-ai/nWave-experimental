"""Tests for nwave-docgen: deterministic documentation generator."""

from __future__ import annotations

import subprocess
import sys
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

    def test_real_tree_omits_atd_as_owner_of_removed_pbt_skill(self):
        """nw-property-based-testing was removed from ATD's role-skill-loading
        entry and was never in its catalog_only — the generated skill page's
        'Used by' must not list nw-acceptance-designer as a runtime owner."""
        from scripts.docgen import scan

        root = Path(__file__).resolve().parents[1]
        pages = render(enrich(extract_all(scan(root))), root=root)
        page = pages["skills/nw-property-based-testing.md"]
        assert "nw-acceptance-designer" not in page
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
            "nw-adversarial-refutation",
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
                "--public-only",
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
# role-skill-loading.yaml: build-time-only universal-lens registry
# ---------------------------------------------------------------------------
_ROLE_SKILL_TARGETS = [
    "nw-acceptance-designer-reviewer",
    "nw-acceptance-designer",
    "nw-ddd-architect-reviewer",
    "nw-ddd-architect",
    "nw-platform-architect-reviewer",
    "nw-platform-architect",
    "nw-software-crafter-reviewer",
    "nw-solution-architect-reviewer",
    "nw-solution-architect",
    "nw-system-designer-reviewer",
    "nw-system-designer",
]
_CRAFTER_ROLES = ["nw-software-crafter", "nw-functional-software-crafter"]
# ATD compiles at build time and must not invoke runtime Skill/CodeFact --
# excluded from assertions that require every targeted role to declare/
# invoke Skill; those assertions still apply to every other runtime role.
_RUNTIME_SKILL_TARGETS = [
    role for role in _ROLE_SKILL_TARGETS if role != "nw-acceptance-designer"
]
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

    @pytest.mark.parametrize("role", _CRAFTER_ROLES)
    def test_crafter_eager_preload_is_only_the_compact_kernel(
        self, root: Path, role: str
    ):
        import yaml

        text = (root / "nWave" / "agents" / f"{role}.md").read_text()
        fm = yaml.safe_load(text.split("---")[1])
        assert fm["skills"] == ["nw-crafter-discipline-delivery-contract"]
        assert "nw-cross-cutting-invariants" not in fm["skills"]

    def test_crafter_kernel_is_preloadable_but_not_user_invocable(self, root: Path):
        text = (
            root
            / "nWave"
            / "skills"
            / "nw-crafter-discipline-delivery-contract"
            / "SKILL.md"
        ).read_text()
        front = text.split("---")[1]
        assert "user-invocable: false" in front
        assert "disable-model-invocation" not in front

    @pytest.mark.parametrize("role", _CRAFTER_ROLES)
    def test_every_crafter_lazy_lens_is_model_invocable(
        self, root: Path, roles: dict, role: str
    ):
        entry = roles[role]
        names = set(entry.get("catalog_only", []))
        assert names
        for name in names:
            text = (root / "nWave" / "skills" / name / "SKILL.md").read_text(
                encoding="utf-8"
            )
            front = text.split("---")[1]
            assert "disable-model-invocation" not in front, (
                f"{role} renders Skill({name}) ON-TRIGGER but {name} is disabled"
            )

    @pytest.mark.parametrize("role", _CRAFTER_ROLES)
    def test_crafter_resolves_matching_lazy_lenses_before_baseline(
        self, root: Path, role: str
    ):
        agent = (root / "nWave" / "agents" / f"{role}.md").read_text()
        discipline = (
            root
            / "nWave"
            / "skills"
            / "nw-crafter-discipline-delivery-contract"
            / "SKILL.md"
        ).read_text()
        resolve = agent.split("**RESOLVE LENSES**", 1)[1].split("**BASELINE**", 1)[0]
        assert '"Mandatory lens resolution"' in " ".join(resolve.split())
        assert "sole normative routing authority" in agent
        assert "before BASELINE" in discipline
        assert "No matched row is optional" in discipline
        assert "first-mutation bound" in discipline

    def test_atd_generated_body_excludes_catalog_only_and_design_owned_code_analysis(
        self, root: Path, roles: dict
    ):
        body = _role_skill_loading_body("nw-acceptance-designer", root)
        atd_entry = roles["nw-acceptance-designer"]
        for skill in atd_entry.get("catalog_only", []):
            assert f"Skill({skill})" not in body, (
                f"catalog_only skill {skill} must not render in the generated body"
            )
        assert "Skill(nw-code-analysis-port)" not in body, (
            "DESIGN owns code-fact resolution; projecting it into ATD would "
            "reintroduce duplicate repository discovery during DISTILL"
        )

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

    def test_atd_auto_route_projects_zero_runtime_rows_and_preserves_catalog_only(
        self, root: Path, roles: dict
    ):
        """DESIGN owns proof-protocol selection; ATD compiles and must not
        invoke runtime Skill/CodeFact -- its generated region is a static
        catalog-only placeholder with zero ON-TRIGGER/NOW rows, while its
        catalog_only ownership (e.g. nw-bdd-methodology) is preserved."""
        body = _role_skill_loading_body("nw-acceptance-designer", root)
        assert "Skill(" not in body, f"ATD rendered body must invoke no Skill: {body}"
        assert "NOW" not in body, f"ATD rendered body must have zero NOW rows: {body}"
        assert "ON-TRIGGER" not in body, (
            f"ATD rendered body must have zero ON-TRIGGER rows: {body}"
        )
        assert "(no universal lens applies to this role)" in body

        atd_entry = roles["nw-acceptance-designer"]
        for field in ("on_demand", "phase", "language_pbt"):
            assert field not in atd_entry, f"ATD must not carry {field}"
        catalog_only = atd_entry.get("catalog_only") or []
        assert catalog_only, "ATD must keep a nonempty catalog_only"
        assert "nw-bdd-methodology" in catalog_only
        assert "nw-at-completeness-check" in catalog_only

        reviewer_body = _role_skill_loading_body(
            "nw-acceptance-designer-reviewer", root
        )
        assert "nw-property-based-testing" not in reviewer_body, (
            "reviewer must not include catalog_only nw-property-based-testing"
        )

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
            "nWave/skills/nw-at-completeness-check/SKILL.md",
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

    def test_oo_and_fp_crafters_read_lens_at_point_of_need_without_test_authoring(
        self, root: Path, roles: dict
    ):
        discipline = (
            root
            / "nWave"
            / "skills"
            / "nw-crafter-discipline-delivery-contract"
            / "SKILL.md"
        ).read_text()
        for agent_id, design_skill in (
            ("nw-software-crafter", "nw-code-design-oo"),
            ("nw-functional-software-crafter", "nw-code-design-fp"),
        ):
            catalog = roles[agent_id]["catalog_only"]
            assert design_skill in catalog
            assert design_skill in discipline
            assert "nw-algebraic-design-protocol" in discipline
            assert "nw-certainty-by-construction" in discipline
            for banned in ("nw-property-based-testing", "nw-test-design-mandates"):
                assert banned not in discipline, (
                    f"{agent_id} must never load a test-authoring skill -- SLIM "
                    f"scope forbids it, found {banned!r} in the compact discipline"
                )

            for token in (
                "CONTESTED_LAW",
                "REPRESENTATION_CHANGE",
                "INVALID_STATE",
                "PRESERVATION",
            ):
                assert token in discipline, (
                    f"{agent_id}: DeliveryContract obligation {token} must "
                    "appear in the sole normative routing table"
                )

            text = (root / "nWave" / "agents" / f"{agent_id}.md").read_text()
            assert '"Mandatory lens resolution"' in " ".join(text.split())
            assert "REUSE_CANDIDATE" in discipline
            assert "ARCHITECTURE_BOUNDARY_CHANGE" in discipline
            assert "Do not author" in text

    @pytest.mark.parametrize("agent_id", _RUNTIME_SKILL_TARGETS)
    def test_frontmatter_tools_declares_skill(self, root: Path, agent_id: str):
        text = (root / "nWave" / "agents" / f"{agent_id}.md").read_text()
        tools_line = next(
            line for line in text.splitlines() if line.startswith("tools:")
        )
        tools = [tool.strip() for tool in tools_line.removeprefix("tools:").split(",")]
        assert "Skill" in tools, f"{agent_id}: frontmatter tools must declare Skill"
        assert tools.count("Skill") == 1, f"{agent_id}: Skill declared more than once"

    def test_atd_frontmatter_tools_excludes_skill(self, root: Path):
        """ATD compiles and must not invoke runtime Skill -- its tools are
        the compiler-boundary set Read/Write/Edit, plus (Ale's
        construction-over-file correction, 2026-08-20, c05215bd7) `Bash`
        -- but ONLY as the sole route to `des fill-contract`, never a
        general shell. That allowlist is enforced by the installed
        PreToolUse hook `_evaluate_atd_fill_contract_bash_command`
        (`src/des/adapters/drivers/hooks/pre_tool_use_handler.py`, gated
        on `_ATD_ROLE_NAME == "nw-acceptance-designer"`); pure-function
        and end-to-end coverage of that lockdown already lives in
        `tests/des/unit/adapters/drivers/hooks/
        test_atd_fill_contract_bash_lockdown.py` and the tools-set
        projection is separately pinned in
        `tests/plugins/unit/test_atd_native_trigger_spatial_first.py`.
        The property is re-asserted directly here too -- a non-fill-
        contract Bash command must still be blocked -- so this file's
        own pin can never silently drift back to "any Bash is fine"
        without an assertion in THIS suite catching it."""
        text = (root / "nWave" / "agents" / "nw-acceptance-designer.md").read_text()
        tools_line = next(
            line for line in text.splitlines() if line.startswith("tools:")
        )
        tools = [tool.strip() for tool in tools_line.removeprefix("tools:").split(",")]
        assert "Skill" not in tools
        assert set(tools) == {"Read", "Write", "Edit", "Bash"}

        from des.adapters.drivers.hooks import pre_tool_use_handler

        assert (
            pre_tool_use_handler._evaluate_atd_fill_contract_bash_command("rm -rf /")
            is not None
        ), "a non-fill-contract Bash command must still be blocked for ATD"
        assert (
            pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(
                "des fill-contract --repo-root /repo --delivery-id w --status"
            )
            is None
        ), "the ONE allowlisted shape (des fill-contract) must still be permitted"

    @pytest.mark.parametrize("agent_id", _RUNTIME_SKILL_TARGETS)
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

    def test_atd_generated_region_forbids_skill_and_codefact_invocation(
        self, root: Path
    ):
        """DESIGN owns proof-protocol selection; the compiled ATD region must
        not invoke a runtime Skill or CodeFact."""
        text = (root / "nWave" / "agents" / "nw-acceptance-designer.md").read_text()
        start = text.index("GENERATED:role-skill-loading START")
        end = text.index("GENERATED:role-skill-loading END")
        region = text[start:end]
        assert "Skill(" not in region
        assert "CodeFact" not in region

    @pytest.mark.parametrize("agent_id", _ROLE_SKILL_TARGETS)
    def test_every_registered_role_still_projects_a_nonempty_body(
        self, root: Path, agent_id: str
    ):
        body = _role_skill_loading_body(agent_id, root)
        assert body.strip(), f"{agent_id} projected an empty role-skill-loading body"

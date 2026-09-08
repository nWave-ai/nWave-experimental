"""Every production visibility decision must consult the private-skill declaration.

``is_public_skill`` takes ``private_skills`` as an OPTIONAL argument so the
existing four-argument callers keep working. Optional means a new call site
can omit it and silently ship a skill the catalog declares private -- the
exact leak class this module family exists to prevent (nwave_ai-3.15.1).

This test pins that every call site in ``scripts/`` supplies it, and proves
on a witness that the detector can actually tell a four-argument call apart
from a five-argument one.
"""

import ast
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Call sites that hold an nWave tree and therefore MUST pass the declaration.
CALL_SITE_MODULES = [
    "scripts/check_docs_links.py",
    "scripts/docgen.py",
    "scripts/release/strip_private_agents.py",
    "scripts/release/verify_plugin_privacy.py",
    "scripts/release/verify_wheel_privacy.py",
    "scripts/validation/validate_skill_references.py",
]

# Call sites that hold no tree: they take private_skills from their own
# caller and forward it. TestDistributionFilterForwards proves the forwarding.
TREELESS_CALL_SITE_MODULES = [
    "scripts/shared/skill_distribution.py",
]

# The definition itself.
DEFINITION_MODULE = "scripts/shared/agent_catalog.py"


def _offending_calls(source: str) -> list[int]:
    """Line numbers of ``is_public_skill`` calls that omit the declaration."""
    offenders: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (
            func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        )
        if name != "is_public_skill":
            continue
        passes_positionally = len(node.args) >= 5
        passes_by_keyword = any(kw.arg == "private_skills" for kw in node.keywords)
        if not (passes_positionally or passes_by_keyword):
            offenders.append(node.lineno)
    return offenders


class TestDetector:
    """Witness: the check is not vacuous."""

    def test_flags_a_four_argument_call(self):
        src = "is_public_skill(name, public_agents, ownership, command_skills)\n"
        assert _offending_calls(src) == [1]

    @pytest.mark.parametrize(
        "src",
        [
            "is_public_skill(n, p, o, c, private)\n",
            "is_public_skill(n, p, ownership_map=o, command_skills=c, private_skills=s)\n",
        ],
    )
    def test_accepts_a_call_that_passes_the_declaration(self, src):
        assert _offending_calls(src) == []


class TestProductionCallSites:
    @pytest.mark.parametrize("module", CALL_SITE_MODULES)
    def test_call_site_passes_private_skills(self, module):
        path = PROJECT_ROOT / module
        offenders = _offending_calls(path.read_text(encoding="utf-8"))
        assert offenders == [], (
            f"WHAT: {module} calls is_public_skill without private_skills at "
            f"line(s) {offenders}. WHY: the call would derive visibility from "
            f"owning agents alone and ship a skill the catalog declares "
            f"public: false. HOW: load it once with "
            f"load_private_skills(<nwave_dir>) and pass it as the fifth "
            f"argument."
        )

    def test_every_call_site_is_accounted_for(self):
        """A new call site must be classified, never silently unclassified."""
        found = {
            str(p.relative_to(PROJECT_ROOT))
            for p in (PROJECT_ROOT / "scripts").rglob("*.py")
            if "is_public_skill(" in p.read_text(encoding="utf-8")
        }
        known = (
            set(CALL_SITE_MODULES)
            | set(TREELESS_CALL_SITE_MODULES)
            | {DEFINITION_MODULE}
        )
        assert found == known, (
            f"WHAT: the is_public_skill call-site population drifted: "
            f"{found ^ known}. WHY: an unclassified call site decides "
            f"distribution without being checked against the catalog's "
            f"private-skill declaration. HOW: pass private_skills at the new "
            f"call site and add it to CALL_SITE_MODULES, or, when it holds no "
            f"nWave tree, add it to TREELESS_CALL_SITE_MODULES."
        )


class TestDistributionFilterForwards:
    """The treeless filter forwards the declaration instead of ignoring it."""

    def _entries(self, tmp_path):
        from scripts.shared.skill_distribution import SkillEntry

        return [
            SkillEntry(name="nw-secret-lens", source_path=tmp_path / "a.md"),
            SkillEntry(name="nw-open-lens", source_path=tmp_path / "b.md"),
        ]

    def test_declared_private_skill_is_dropped(self, tmp_path):
        from scripts.shared.skill_distribution import filter_public_skills

        kept = filter_public_skills(
            self._entries(tmp_path),
            {"widget-maker"},
            {"nw-secret-lens": {"widget-maker"}, "nw-open-lens": {"widget-maker"}},
            None,
            {"nw-secret-lens"},
        )
        assert [e.name for e in kept] == ["nw-open-lens"]

    def test_without_a_declaration_both_survive(self, tmp_path):
        from scripts.shared.skill_distribution import filter_public_skills

        kept = filter_public_skills(
            self._entries(tmp_path),
            {"widget-maker"},
            {"nw-secret-lens": {"widget-maker"}, "nw-open-lens": {"widget-maker"}},
        )
        assert [e.name for e in kept] == ["nw-secret-lens", "nw-open-lens"]

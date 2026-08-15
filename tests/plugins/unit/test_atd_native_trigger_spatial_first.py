"""K4 ATD-economics regression (2026-08-13).

Confirmed defect: the ATD route's generated Skill-Loading block and
nWave/data/role-skill-loading.yaml both require native `Invoke Skill(...)
ON-TRIGGER` for nw-test-design-mandates / nw-property-based-testing /
nw-pbt-python, but all three skill frontmatters carried
`disable-model-invocation: true` -- contradicting the registry and silently
blocking the native trigger the agent body promises. The one skill that DID
load (nw-certainty-by-construction) never carried that line. Separately, the
route synthesized the whole acceptance-test portfolio in one long silent
inference after the last triggered skill returned, instead of materializing
the first acceptance-test file immediately.

Three independently useful projections:
1. The three registry-required knowledge skills are model-invocable
   (no `disable-model-invocation: true`) while staying `user-invocable: false`
   -- native trigger without broadening public command UX.
2. The registry's ON-TRIGGER skill names line up with the agent body's
   generated `Invoke Skill(...) ON-TRIGGER` rows -- no drift between the
   registry (SSOT) and its rendered projection.
3. The thin Auto route requires the very next tool call after the schema
   read and the last triggered skill to be the `Write` of the single
   acceptance-test file, carrying a spatial skeleton, refined only by `Edit`
   on that same file -- never a separate design/proof document.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from scripts.shared.frontmatter import parse_frontmatter_file


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NWAVE_DIR = PROJECT_ROOT / "nWave"
AGENTS_DIR = NWAVE_DIR / "agents"
SKILLS_DIR = NWAVE_DIR / "skills"
REGISTRY_PATH = NWAVE_DIR / "data" / "role-skill-loading.yaml"

REGISTRY_REQUIRED_NATIVE_TRIGGER_SKILLS = [
    "nw-test-design-mandates",
    "nw-property-based-testing",
    "nw-pbt-python",
]

AGENT_BODY = (AGENTS_DIR / "nw-acceptance-designer.md").read_text(encoding="utf-8")
REGISTRY = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))


class TestRegistryRequiredSkillsAreNativelyModelInvocable:
    """Fix: drop the contradictory disable-model-invocation: true frontmatter line."""

    def test_frontmatter_stays_user_invocable_false_but_model_invocable(self):
        contradictions = []
        for skill in REGISTRY_REQUIRED_NATIVE_TRIGGER_SKILLS:
            metadata, _ = parse_frontmatter_file(SKILLS_DIR / skill / "SKILL.md")
            assert metadata is not None, (
                f"{skill}/SKILL.md has no parseable frontmatter"
            )
            if metadata.get("user-invocable") is not False:
                contradictions.append(
                    (skill, "user-invocable", metadata.get("user-invocable"))
                )
            if metadata.get("disable-model-invocation"):
                contradictions.append(
                    (
                        skill,
                        "disable-model-invocation",
                        metadata.get("disable-model-invocation"),
                    )
                )
        assert contradictions == [], (
            f"registry-required native-trigger skills still contradict the "
            f"registry: {contradictions}"
        )

    def test_certainty_by_construction_baseline_stays_unset(self):
        """The one skill that DID load natively is the control: it never
        carried disable-model-invocation, and this fix must not add it."""
        metadata, _ = parse_frontmatter_file(
            SKILLS_DIR / "nw-certainty-by-construction" / "SKILL.md"
        )
        assert metadata is not None
        assert not metadata.get("disable-model-invocation")


class TestRegistryAndAgentBodyNativeNamesStayAligned:
    """No drift between role-skill-loading.yaml (SSOT) and the rendered agent body."""

    def test_registry_phase_skills_all_emit_a_native_invoke_row(self):
        role = REGISTRY["roles"]["nw-acceptance-designer"]
        registry_names = set(role.get("phase", {})) | set(role.get("on_demand", {}))
        missing = [
            name
            for name in registry_names
            if f"Invoke Skill({name}) ON-TRIGGER" not in AGENT_BODY
        ]
        assert missing == [], (
            f"role-skill-loading.yaml names {missing} for nw-acceptance-designer "
            f"but the generated agent body emits no matching native Invoke row"
        )

    def test_agent_body_native_rows_all_resolve_to_an_installed_skill_dir(self):
        for skill in REGISTRY_REQUIRED_NATIVE_TRIGGER_SKILLS:
            expected_row = (
                f"Invoke ONE Skill({skill}) ON-TRIGGER"
                if skill == "nw-pbt-python"
                else f"Invoke Skill({skill}) ON-TRIGGER"
            )
            assert expected_row in AGENT_BODY, (
                f"{skill} missing its native ON-TRIGGER row in nw-acceptance-designer.md"
            )
            assert (SKILLS_DIR / skill / "SKILL.md").is_file(), (
                f"{skill} has a native trigger row but no installed skill directory"
            )


class TestThinRouteRequiresImmediateSpatialMaterialization:
    """After the schema read + last triggered skill, the next tool is the AT Write."""

    def test_spatial_first_mandate_is_present_and_hard(self):
        assert "Spatial-first materialization (HARD)" in AGENT_BODY

    def test_mandate_orders_write_immediately_after_schema_and_last_trigger(self):
        start = AGENT_BODY.index("**Spatial-first materialization (HARD):**")
        end = AGENT_BODY.index("### GREEN_TO_GREEN branch")
        section = " ".join(AGENT_BODY[start:end].split())
        for token in (
            "after the schema read and last",
            "ON-TRIGGER `Skill(...)` return",
            "the next tool call is the `Write`",
            "no extra Read/Grep/Glob/Bash",
            "no silent synthesis first",
            "no git query",
            "dependency probe",
            "`nw-distill-red-scaffolding`/other Skill call may",
            "intervene between the last triggered row and that `Write`",
        ):
            assert token in section, f"Missing ordering token: {token!r}"

    def test_mandate_requires_spatial_skeleton_not_prose_planning(self):
        start = AGENT_BODY.index("**Spatial-first materialization (HARD):**")
        end = AGENT_BODY.index("### GREEN_TO_GREEN branch")
        section = " ".join(AGENT_BODY[start:end].split())
        for token in (
            "states, failure modes, observables, properties",
            "test/docstring structure",
            "never prose planning",
        ):
            assert token in section

    def test_refinement_stays_in_the_same_file_no_new_artifact_type(self):
        start = AGENT_BODY.index("**Spatial-first materialization (HARD):**")
        end = AGENT_BODY.index("### GREEN_TO_GREEN branch")
        section = " ".join(AGENT_BODY[start:end].split())
        assert "refine only via `Edit` on this same file" in section
        assert "never a separate design document" in section

    def test_only_one_acceptance_test_artifact_file_is_named(self):
        start = AGENT_BODY.index("**Spatial-first materialization (HARD):**")
        end = AGENT_BODY.index("### GREEN_TO_GREEN branch")
        section = " ".join(AGENT_BODY[start:end].split())
        assert "the `Write` of exactly ONE consolidated" in section
        assert "acceptance-test artifact FILE" in section


class TestClosureOnlyPhaseAndFinalResponse:
    """K4 corrective, collapsed to 3 dense assertions.

    Defect: after the spatial-first Write, ATD ran 51 more tool calls of
    unbounded product discovery/refinement (171247 subagent tokens, 815348
    ms) and ended at max-turn with incomplete prose -- no DeliveryContract,
    no two-line handoff. Fix: bound post-Write work to a closed
    operation/artifact set that still permits the one dependency the K4
    clean-environment failure needed (an undeclared PBT library), keep a
    terminal EVIDENCE_GAP/BROKEN silent on the THIN header, and make
    RedConfirmed's final response exactly the two header lines."""

    def _closure_section(self):
        start = AGENT_BODY.index("**Closure-only phase (HARD):**")
        end = AGENT_BODY.index("### GREEN_TO_GREEN branch")
        return " ".join(AGENT_BODY[start:end].split())

    def _pre_authoring_section(self):
        start = AGENT_BODY.index("### RED_TO_GREEN branch")
        end = AGENT_BODY.index("**Spatial-first materialization (HARD):**")
        return " ".join(AGENT_BODY[start:end].split())

    def _final_response_section(self):
        start = AGENT_BODY.index("### Both branches — final response")
        end = AGENT_BODY.index("You own the acceptance tests")
        return " ".join(AGENT_BODY[start:end].split())

    def test_closed_operation_and_artifact_set(self):
        """Named manifest declaration edit, explicit runtime-missing, exact
        named direct dependency-delta install argv, never whole manifest
        reinstall. Post-Write: permitted is same-test Edit, that preidentified
        delta, the hash, the one contract Write, the verification command.
        Forbidden: renewed discovery/Skill/Task/Bash and any extra file."""
        pre = self._pre_authoring_section()
        for token in (
            "dependency-manifest topology",
            "split runtime/test-dependency manifests",
            "select the repo-native one that owns TEST dependencies",
            "never the runtime-only manifest",
            "this Read never targets a second manifest",
            "this step confirms the repository-native one",
            "settled by the end of this step, never claimed from step 3 alone",
            "ambiguous after steps 2-4 is `EVIDENCE_GAP`",
        ):
            assert token in pre, f"Missing pre-authoring token: {token!r}"

        section = " ".join(self._closure_section().split())
        for allowed in (
            "same-test-file `Edit`",
            "named manifest owner's declaration edit",
            "iff `BROAD_INPUT_DOMAIN` fired and the substrate facts state the dependency runtime-missing",
            "named direct dependency-delta install argv",
            "never an invented tool",
            "the test file's SHA-256 hash",
            "one `DeliveryContract` JSON Write and schema validation",
            "already-selected `verification-scope.commands`",
        ):
            assert allowed in section, f"Missing permitted-operation token: {allowed!r}"
        for forbidden in (
            "No further product-source Read/Grep/Glob",
            "`nw-code-analysis-port`/CodeFact query",
            "no `Skill(...)` or `Task` call",
            "no exploratory or diagnostic Bash",
            "no other file",
            "whole test dependency manifest",
        ):
            assert forbidden in section, f"Missing prohibition token: {forbidden!r}"
        # Fix must not accidentally forbid the required contract Write.
        assert "exactly two files" not in section
        assert "second `Write`" not in section
        assert "refused outright" not in section

    def test_terminal_blocker_is_silent_only_redconfirmed_earns_the_header(self):
        section = self._closure_section()
        for token in (
            "terminal `EVIDENCE_GAP`",
            "or `BROKEN`",
            "never investigated",
            "never retried",
            "never narrowed to a substitute command or reduced scope",
            "never patched by authoring an additional test",
            "return only the concise blocker itself and stop",
            "never the two-line header",
            "Only `RedConfirmed` earns the header",
            "the two-line header below is the IMMEDIATE next output",
        ):
            assert token in section, f"Missing token: {token!r}"

    def test_final_response_is_exactly_two_lines_root_owns_forwarding(self):
        section = self._final_response_section()
        assert "then exactly one blank line" not in section
        assert "concise optional evidence" not in section
        for token in (
            "and nothing else",
            "No greeting",
            "summary heading",
            "code fence",
            "absolute path",
            "JSON paste",
            "duplicate header",
            "root-computed hash",
            "may precede, follow, or replace these two lines",
            "Root may append its own crafter context",
            "never emits this header",
        ):
            assert token in section, f"Missing token: {token!r}"

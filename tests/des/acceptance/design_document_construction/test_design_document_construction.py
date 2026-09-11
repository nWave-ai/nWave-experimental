"""Public oracle for the deterministic DESIGN-document producer.

The law is that one closed semantic input has two matching public projections:
the configured Markdown authority section and the handover facts.  The real
``des`` dispatcher is the only production surface driven here.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import stat
import sys
import tempfile
from pathlib import Path

import pytest
from tests.common.in_process_cli import run_cli_in_process
from tests.common.state_delta import assert_state_delta, set_to, unchanged
from tests.des.acceptance import fake_provider
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    PACKAGE_PARENT,
    accepted_values,
    base_repository,
    git,
    hermetic_environment,
)

from des.application.handover import Blocked
from scripts import docgen


GLOBAL_DESTINATION = Path("docs/global-design.md")
REPOSITORY_DESTINATION = Path("docs/product/architecture/brief.md")
HANDOVER = Path(".nwave/des/handover.json")

INPUT_DESCRIPTION_ASSETS = (
    Path("nWave/skills/nw-design/SKILL.md"),
    Path("nWave/agents/nw-solution-architect.md"),
    Path("docs/product/architecture/ADR-DES-003-step-surface-algebra.md"),
)

_GENERATED_INPUT_DESCRIPTION = re.compile(
    r"<!-- GENERATED:design-document-input START[^>]*-->\n"
    r"(?P<body>.*?)"
    r"<!-- GENERATED:design-document-input END -->",
    re.DOTALL,
)

MANIFEST = {
    "schema_version": 1,
    "authority": {"heading": "Widget color"},
    "purpose": "Expose the selected widget color.",
    "constraints": ["Preserve existing callers."],
    "targets": [
        {
            "path": "src/widget.py",
            "decision": "EXTEND",
            "reason": "Widget already owns color.",
        }
    ],
    "paradigm": "object_oriented",
    "decisions": ["Keep color validation at Widget construction."],
    "reuse_analysis": {
        "candidates": [
            {
                "symbol": "Widget",
                "locator": "src/widget.py:10",
                "decision": "EXTEND",
                "reason": "Existing public owner.",
            }
        ]
    },
    "prefactoring": {
        "applicability": "applicable",
        "existing_oracle": "tests/test_widget.py::test_default_color",
        "move": "Extract the current default lookup without changing output.",
        "preserved_observation": "A default widget remains blue.",
    },
    "agreement_analysis": {
        "applicability": "not_applicable",
        "reason": "The widget color extension touches no shared release or "
        "interchange schema.",
    },
    "boundaries": {
        "applicability": "not_applicable",
        "reason": "No port or dependency boundary changes.",
    },
    "public_oracle": {
        "observation": "CLI prints the selected color.",
        "stimulus": "Run widget show --color red.",
        "expected": "stdout is red and exit is zero.",
        "falsifier": "Any other stdout or non-zero exit.",
    },
    "oracle": "tests/test_widget.py::test_selected_color",
    "acceptance_supports": [],
    "verification": [["pytest", "-q", "tests/test_widget.py"]],
}

EXPECTED_SECTION = """## Widget color

### Purpose
Expose the selected widget color.

### Constraints
- Preserve existing callers.

### Targets
| Path | Decision | Reason |
|---|---|---|
| `src/widget.py` | EXTEND | Widget already owns color. |

### Paradigm
object_oriented

### Decisions
- Keep color validation at Widget construction.

### Reuse analysis
| Symbol | Locator | Decision | Reason |
|---|---|---|---|
| Widget | `src/widget.py:10` | EXTEND | Existing public owner. |

### Prefactoring
Existing oracle: `tests/test_widget.py::test_default_color`

Move: Extract the current default lookup without changing output.

Preserved observation: A default widget remains blue.

### Agreement analysis
Not applicable: The widget color extension touches no shared release or interchange schema.

### Boundaries
Not applicable: No port or dependency boundary changes.

### Public oracle
Observation: CLI prints the selected color.

Stimulus: Run widget show --color red.

Expected: stdout is red and exit is zero.

Falsifier: Any other stdout or non-zero exit.

### Oracle and verification
Oracle target locator: `tests/test_widget.py::test_selected_color`

Verification command: `pytest -q tests/test_widget.py`
"""

EXPECTED_FACTS = {
    "targets": [{"path": "src/widget.py", "decision": "EXTEND"}],
    "paradigm": "object_oriented",
    "decisions": ["Keep color validation at Widget construction."],
    "oracle": "tests/test_widget.py::test_selected_color",
    "acceptance_supports": [],
    "verification": [["pytest", "-q", "tests/test_widget.py"]],
    "obligations": ["Preserve existing callers."],
    "authority_locator": "docs/product/architecture/brief.md#Widget color",
}

APPLICABLE_BOUNDARIES = {
    "applicability": "applicable",
    "driving_port": "des design",
    "driven_ports": ["architecture authority", "bound handover"],
    "dependency_direction": "The CLI depends inward on the document producer.",
    "failures": [
        {
            "condition": "The handover compare-and-swap cannot replace its file.",
            "outcome": "Indeterminate",
            "observation": "The terminal identifies the completed authority and retryable handover.",
        }
    ],
}

APPLICABLE_ACCEPTANCE_SUPPORTS = [
    "tests/des/acceptance/steps_for_the_orchestrator/conftest.py"
]

EXPECTED_APPLICABLE_FACTS = {
    **EXPECTED_FACTS,
    "acceptance_supports": APPLICABLE_ACCEPTANCE_SUPPORTS,
}

UNRELATED_AUTHORITY_PREFIX = (
    b"# Architecture authority\n\n"
    b"This human introduction is outside DESIGN ownership.\n\n"
    b"## Existing architecture\n\n"
    b"This H2 belongs to a different value and must remain byte-identical.\n\n"
)

UNRELATED_AUTHORITY_SUFFIX = (
    b"\n\n## Human appendix\n\n"
    b"This suffix is outside DESIGN ownership and must remain byte-identical.\n"
)


def _terminal(stdout: str, stderr: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in (stdout + "\n" + stderr).splitlines():
        label, separator, value = line.partition(": ")
        if separator:
            rows.setdefault(label, value)
    return rows


@pytest.fixture
def design_repository(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """A tracked checkout, with global A overridden by repository B."""
    root = base_repository(tmp_path / "repository")
    home = tmp_path / "home"
    (home / ".nwave").mkdir(parents=True)
    (home / ".nwave" / "config.json").write_text(
        json.dumps({"documents": {"design": {"destination": str(GLOBAL_DESTINATION)}}})
    )
    (root / ".nwave").mkdir()
    (root / ".nwave" / "config.json").write_text(
        json.dumps(
            {"documents": {"design": {"destination": str(REPOSITORY_DESTINATION)}}}
        )
    )
    return root, {**os.environ, "HOME": str(home)}


def _bootstrap_value(
    root: Path,
    environment: dict[str, str],
    tmp_path: Path,
    *labels: str,
) -> None:
    """Create DESIGN's declared prerequisite through the real public PO step."""
    results, turns, counter = (
        tmp_path / "answers.json",
        tmp_path / "turns.json",
        tmp_path / "counter",
    )
    results.write_text(json.dumps([accepted_values(*(labels or ("widget color",)))]))
    provider_environment = fake_provider.environment(
        root,
        launcher_dir=tmp_path / "bin",
        results=results,
        log=turns,
        counter=counter,
        package_parent=PACKAGE_PARENT,
    )
    code, out, err = run_cli_in_process(
        ["po", "--repo-root", str(root)],
        cwd=root,
        env=hermetic_environment(
            provider_environment | {"HOME": environment["HOME"]},
            tmp_path / "claude-config",
        ),
        stdin_text="Produce one architecture value for the Widget command.",
        catch_all=True,
    )
    assert code == 0, (
        "the public PO prerequisite did not create the stored value; DESIGN must "
        f"start from a real handover (stdout={out!r}, stderr={err!r})"
    )


def _design(
    root: Path,
    environment: dict[str, str],
    manifest: dict,
    *,
    replace_current: bool = False,
    value: int = 1,
) -> tuple[int, str, str]:
    arguments = ["design", "--repo-root", str(root), "--value", str(value)]
    if replace_current:
        arguments.append("--replace-current")
    arguments += ["--input", "-"]
    return run_cli_in_process(
        arguments,
        cwd=root,
        env=environment,
        stdin_text=json.dumps(manifest),
        catch_all=True,
    )


def _words(value: str) -> str:
    """Compare rendered guidance across CLI wrapping and Markdown layout."""
    return " ".join(value.split())


def test_design_input_help_and_author_guidance_share_one_generated_contract(
    tmp_path: Path,
) -> None:
    """Authors can obtain the accepted manifest language from every public input surface."""
    code, help_text, stderr = run_cli_in_process(
        ["design", "--help"], cwd=tmp_path, catch_all=True
    )

    assert code == 0, (
        "`des design --help` must remain a readable, successful public entry for "
        f"constructor-input authors (stdout={help_text!r}, stderr={stderr!r})"
    )
    for semantic_term in (
        "schema_version",
        "acceptance_supports",
        "functional",
        "object_oriented",
    ):
        assert semantic_term in help_text, (
            "`des design --help` must describe the accepted closed v1 manifest "
            f"language, including {semantic_term!r}; otherwise a host cannot form "
            "constructor input without copying a second contract"
        )

    repository = Path(__file__).resolve().parents[4]
    bodies: list[str] = []
    for relative_path in INPUT_DESCRIPTION_ASSETS:
        source = (repository / relative_path).read_text(encoding="utf-8")
        match = _GENERATED_INPUT_DESCRIPTION.search(source)
        assert match is not None, (
            f"{relative_path} must carry the generated DESIGN input-description "
            "block so source guidance cannot drift from the public constructor"
        )
        bodies.append(match.group("body"))

    assert len({_words(body) for body in bodies}) == 1, (
        "the skill, agent, and ADR must publish one shared DESIGN input description; "
        "independently edited manifest prose leaves different authors with different "
        "accepted input languages"
    )
    assert _words(bodies[0]) in _words(help_text), (
        "the public help must expose the same generated input description shipped "
        "to DESIGN authors; a CLI-only or documentation-only description is not a "
        "usable shared constructor contract"
    )

    projections = docgen.project_generated_regions(repository, docgen.scan(repository))
    projected = {
        projection.path.relative_to(repository): projection
        for projection in projections
    }
    missing = set(INPUT_DESCRIPTION_ASSETS) - set(projected)
    assert not missing, (
        "docgen must own every source asset that publishes the DESIGN input "
        f"description; missing projections={sorted(map(str, missing))}"
    )
    stale = docgen.check_generated_regions(
        repository, [projected[path] for path in INPUT_DESCRIPTION_ASSETS]
    )
    assert not stale, (
        "the checked source guidance must already equal docgen's projection of the "
        f"shared constructor description; stale assets={stale}"
    )


def _craft_prompt(
    root: Path, environment: dict[str, str], tmp_path: Path
) -> tuple[int, str, str, str]:
    """Run the real craft consumer and retain its controlled-provider input."""
    results, turns, counter = (
        tmp_path / "craft-answers.json",
        tmp_path / "craft-turns.json",
        tmp_path / "craft-counter",
    )
    results.write_text(
        json.dumps(
            [
                {
                    "structured_output": {
                        "outcome": "rejected",
                        "diagnostic": "captured corrected facts at craft boundary",
                        "blocked_by": "design",
                    }
                }
            ]
        )
    )
    provider_environment = fake_provider.environment(
        root,
        launcher_dir=tmp_path / "craft-bin",
        results=results,
        log=turns,
        counter=counter,
        package_parent=PACKAGE_PARENT,
    )
    code, out, err = run_cli_in_process(
        ["craft", "--repo-root", str(root), "--value", "1"],
        cwd=root,
        env=hermetic_environment(
            provider_environment | {"HOME": environment["HOME"]},
            tmp_path / "craft-claude-config",
        ),
        catch_all=True,
    )
    return code, out, err, json.loads(turns.read_text())[0]["prompt"]


def _design_state(root: Path, environment: dict[str, str]) -> str:
    code, out, err = run_cli_in_process(
        ["state", "--repo-root", str(root)], cwd=root, env=environment, catch_all=True
    )
    assert code == 0, (
        "the public state projection must be readable before and after DESIGN so "
        f"the binding transition is observable (stdout={out!r}, stderr={err!r})"
    )
    return out


def _oracle_prompt(
    root: Path, environment: dict[str, str], tmp_path: Path
) -> tuple[int, str, str, str]:
    """Run the real oracle step and return its captured authoring prompt."""
    results, turns, counter = (
        tmp_path / "oracle-answers.json",
        tmp_path / "oracle-turns.json",
        tmp_path / "oracle-counter",
    )
    results.write_text(
        json.dumps(
            [
                {
                    "structured_output": {
                        "outcome": "rejected",
                        "diagnostic": "captured the authoring boundary",
                    },
                }
            ]
        )
    )
    provider_environment = fake_provider.environment(
        root,
        launcher_dir=tmp_path / "oracle-bin",
        results=results,
        log=turns,
        counter=counter,
        package_parent=PACKAGE_PARENT,
    )
    code, out, err = run_cli_in_process(
        ["oracle", "--repo-root", str(root), "--value", "1"],
        cwd=root,
        env=hermetic_environment(
            provider_environment | {"HOME": environment["HOME"]},
            tmp_path / "oracle-claude-config",
        ),
        catch_all=True,
    )
    return code, out, err, json.loads(turns.read_text())[0]["prompt"]


def _track_authority(root: Path, contents: bytes) -> Path:
    """Seed a real, tracked human authority outside the producer's ownership."""
    authority = root / REPOSITORY_DESTINATION
    authority.parent.mkdir(parents=True)
    authority.write_bytes(contents)
    git(root, "add", str(REPOSITORY_DESTINATION))
    git(root, "commit", "-qm", "tracked human architecture authority")
    return authority


def _assert_refusal_without_projection_mutation(
    root: Path,
    environment: dict[str, str],
    manifest: dict,
) -> None:
    """The public construction boundary rejects before either durable projection."""
    authority = root / REPOSITORY_DESTINATION
    authority_before = authority.read_bytes() if authority.exists() else None
    global_authority = root / GLOBAL_DESTINATION
    global_before = global_authority.read_bytes() if global_authority.exists() else None
    handover_before = (root / HANDOVER).read_bytes()

    code, out, err = _design(root, environment, manifest)
    rows = _terminal(out, err)

    assert code != 0 and rows.get("DELIVERY-OUTCOME") == "Refusal", (
        "a value outside closed v1 input construction must refuse at the public "
        f"terminal (stdout={out!r}, stderr={err!r})"
    )
    assert (
        authority.read_bytes() if authority.exists() else None
    ) == authority_before and (
        global_authority.read_bytes() if global_authority.exists() else None
    ) == global_before, (
        "a construction refusal must leave both possible authority destinations "
        "byte-identical; validation precedes every durable write"
    )
    assert (root / HANDOVER).read_bytes() == handover_before, (
        "a construction refusal must leave the existing handover byte-identical; "
        "facts bind only after a whole valid manifest exists"
    )


def test_design_document_is_the_configured_authority_and_matching_bound_facts(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    _track_authority(root, UNRELATED_AUTHORITY_PREFIX)
    before_state = _design_state(root, environment)

    code, out, err = _design(root, environment, MANIFEST)
    rows = _terminal(out, err)
    authority = root / REPOSITORY_DESTINATION
    after_state = _design_state(root, environment)

    assert code == 0, (
        "valid closed v1 DESIGN input must succeed through `des design`; the "
        f"terminal instead reported stdout={out!r}, stderr={err!r}"
    )
    assert rows.get("DELIVERY-OUTCOME") == "Success", (
        "the terminal must classify the completed two-projection construction as "
        f"Success, not {rows.get('DELIVERY-OUTCOME')!r}"
    )
    assert rows.get("SCHEMA-VERSION") == "1"
    assert not (root / GLOBAL_DESTINATION).exists(), (
        "repository documents.design.destination must override global configuration; "
        "the global authority was written despite the repository declaration"
    )
    assert (
        authority.read_bytes() == UNRELATED_AUTHORITY_PREFIX + EXPECTED_SECTION.encode()
    ), (
        "inserting DESIGN's owned H2 must preserve every byte of the tracked "
        "human prefix and unrelated H2 sections, then append only the canonical "
        "owned section"
    )
    facts_json = rows.get("DESIGN-FACTS")
    assert facts_json is not None, (
        "a successful DESIGN terminal must publish DESIGN-FACTS so callers can "
        "compare the bound typed projection without parsing Markdown"
    )
    assert json.loads(facts_json) == EXPECTED_FACTS, (
        "DESIGN-FACTS must expose exactly the DesignFacts projection of the same "
        "normalized manifest; do not derive facts separately from Markdown"
    )
    assert facts_json == json.dumps(
        EXPECTED_FACTS, ensure_ascii=False, separators=(",", ":")
    ), (
        "DESIGN-FACTS must be canonical JSON so callers can compare the public "
        "facts exactly"
    )
    assert_state_delta(
        before={
            "configured_authority": False,
            "global_authority": False,
            "design_state": "design=bound" in before_state,
        },
        after={
            "configured_authority": authority.exists(),
            "global_authority": (root / GLOBAL_DESTINATION).exists(),
            "design_state": "design=bound" in after_state,
        },
        universe={"configured_authority", "global_authority", "design_state"},
        expected={
            "configured_authority": set_to(True),
            "global_authority": unchanged(),
            "design_state": set_to(True),
        },
    )


def test_design_document_projects_applicable_boundaries_and_acceptance_supports(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    """Applicable semantic boundaries remain readable in the human authority."""
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    manifest = json.loads(json.dumps(MANIFEST))
    manifest["boundaries"] = APPLICABLE_BOUNDARIES
    manifest["acceptance_supports"] = APPLICABLE_ACCEPTANCE_SUPPORTS

    code, out, err = _design(root, environment, manifest)
    rows = _terminal(out, err)
    authority = (root / REPOSITORY_DESTINATION).read_text()
    missing_authority_observations = {
        observation
        for observation in (
            APPLICABLE_BOUNDARIES["driving_port"],
            *APPLICABLE_BOUNDARIES["driven_ports"],
            APPLICABLE_BOUNDARIES["dependency_direction"],
            *(
                value
                for failure in APPLICABLE_BOUNDARIES["failures"]
                for value in (
                    failure["condition"],
                    failure["outcome"],
                    failure["observation"],
                )
            ),
            *APPLICABLE_ACCEPTANCE_SUPPORTS,
        )
        if observation not in authority
    }

    assert code == 0 and rows.get("DELIVERY-OUTCOME") == "Success", (
        "a complete applicable-boundaries manifest must construct through `des "
        f"design` (stdout={out!r}, stderr={err!r})"
    )
    assert not missing_authority_observations, (
        "the configured human DESIGN authority must retain every applicable "
        "boundary and acceptance-support semantic fact; render the missing "
        f"fixture observations: {sorted(missing_authority_observations)!r}"
    )
    assert rows.get("DESIGN-FACTS") == json.dumps(
        EXPECTED_APPLICABLE_FACTS, ensure_ascii=False, separators=(",", ":")
    ), (
        "the public terminal facts must bind the same nonempty acceptance "
        "supports as the accepted semantic manifest; project them from "
        "DesignFacts rather than deriving a separate terminal payload"
    )


def test_constraints_survive_the_bound_handover_into_the_actual_oracle_prompt(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    """Closed input constraints reach the acceptance designer as typed facts."""
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    manifest = json.loads(json.dumps(MANIFEST))
    manifest["constraints"] = [
        "The new public form is exactly des devops --repo-root ROOT --input -, reading one strict UTF-8 OperationalDocumentInput JSON object from stdin. It invokes no provider or role.",
        "OperationalDocumentInput v1 has exactly schema_version, authority, purpose, environment, deployment, recovery, and observability. schema_version is integer 1; authority is exactly {heading: non-empty single-line string}; purpose is a non-empty string.",
        "Each of environment, deployment, recovery, and observability is exactly {applicability, reason, obligations}. applicability is applicable or not_applicable; reason is a non-empty string; obligations is an array with no duplicate id.",
    ]

    code, out, err = _design(root, environment, manifest)
    assert code == 0, out + err
    bound = json.loads((root / HANDOVER).read_text())["values"][0]["authority"]
    assert bound["obligations"] == manifest["constraints"], (
        "the handover must persist normalized constraints as typed obligations "
        "before the oracle step reads its authority"
    )
    assert bound["decisions"] == manifest["decisions"], (
        "constraints are an added projection; they must not overwrite the "
        "separate design decisions"
    )

    oracle_code, oracle_out, oracle_err, prompt = _oracle_prompt(
        root, environment, tmp_path
    )
    assert oracle_code == 1, oracle_out + oracle_err
    assert (
        _terminal(oracle_out, oracle_err).get("WHAT") == "AcceptanceDesignRejected"
    ), (
        "the controlled provider intentionally rejects after capture; no oracle "
        "authoring or measurement is part of this prompt-boundary regression"
    )
    prompt_facts = {
        key: json.loads(value)
        for line in prompt.splitlines()
        for key, separator, value in [line.partition(": ")]
        if separator
    }
    assert prompt_facts["obligations"] == manifest["constraints"], (
        "the real nw-acceptance-designer invocation must receive the closed "
        "input constraints from its typed authority facts"
    )
    assert prompt_facts["decisions"] == manifest["decisions"], (
        "the acceptance prompt must retain decisions separately from obligations"
    )


def test_identical_normalized_input_preserves_owned_section_and_all_observations(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    """A lost successful terminal can be retried without changing either projection."""
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    authority = _track_authority(
        root,
        UNRELATED_AUTHORITY_PREFIX
        + EXPECTED_SECTION.encode()
        + UNRELATED_AUTHORITY_SUFFIX,
    )

    first_code, first_out, first_err = _design(root, environment, MANIFEST)
    first_rows = _terminal(first_out, first_err)
    authority_after_first = authority.read_bytes()
    handover_after_first = (root / HANDOVER).read_bytes()

    second_code, second_out, second_err = _design(root, environment, MANIFEST)
    second_rows = _terminal(second_out, second_err)

    assert first_code == 0 and second_code == 0, (
        "an identical normalized DESIGN input must succeed both initially and on "
        "retry through the public command"
    )
    assert authority_after_first == (
        UNRELATED_AUTHORITY_PREFIX
        + EXPECTED_SECTION.encode()
        + UNRELATED_AUTHORITY_SUFFIX
    ), (
        "an already-owned identical H2 must preserve the unrelated prefix and "
        "suffix byte-for-byte"
    )
    assert authority.read_bytes() == authority_after_first, (
        "the idempotent retry must leave all authority bytes unchanged, including "
        "the unrelated sections on both sides of the owned H2"
    )
    assert (root / HANDOVER).read_bytes() == handover_after_first, (
        "the idempotent retry must leave the bound handover bytes unchanged"
    )
    expected_locator = f"{REPOSITORY_DESTINATION}#Widget color"
    expected_digest = hashlib.sha256(authority_after_first).hexdigest()
    for rows in (first_rows, second_rows):
        assert rows.get("DELIVERY-OUTCOME") == "Success", (
            "both identical invocations must publicly report Success"
        )
        assert rows.get("DOCUMENT") == expected_locator, (
            "the public document locator must identify the configured authority "
            "section exactly"
        )
        assert rows.get("DOCUMENT-SHA256") == expected_digest, (
            "the public document digest must be the SHA-256 of the unchanged "
            "authority bytes"
        )
        assert rows.get("DESIGN-FACTS") == json.dumps(
            EXPECTED_FACTS, ensure_ascii=False, separators=(",", ":")
        ), "each invocation must publish the same canonical bound facts"
        assert rows.get("SCHEMA-VERSION") == "1"
    assert {
        label: second_rows.get(label)
        for label in ("DOCUMENT", "DOCUMENT-SHA256", "DESIGN-FACTS")
    } == {
        label: first_rows.get(label)
        for label in ("DOCUMENT", "DOCUMENT-SHA256", "DESIGN-FACTS")
    }, (
        "an identical normalized retry must return the same DOCUMENT locator, "
        "DOCUMENT-SHA256, and DESIGN-FACTS observations"
    )


def test_replace_current_rebinds_only_the_selected_section_and_craft_reads_v2(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    """The public correction changes one durable pair, then reaches craft."""
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path, "widget color", "unrelated value")
    authority = _track_authority(
        root,
        UNRELATED_AUTHORITY_PREFIX
        + EXPECTED_SECTION.encode()
        + UNRELATED_AUTHORITY_SUFFIX,
    )
    first_code, first_out, first_err = _design(root, environment, MANIFEST)
    assert first_code == 0, first_out + first_err
    authority_v1 = authority.read_bytes()
    handover_v1 = (root / HANDOVER).read_bytes()
    unrelated_v1 = json.loads(handover_v1)["values"][1]

    corrected = json.loads(json.dumps(MANIFEST))
    corrected["purpose"] = "Expose the corrected selected widget color."
    corrected["decisions"] = ["Keep corrected color validation at Widget construction."]
    expected_v2_facts = {
        "targets": [{"path": "src/widget.py", "decision": "EXTEND"}],
        "paradigm": "object_oriented",
        "decisions": ["Keep corrected color validation at Widget construction."],
        "oracle": "tests/test_widget.py::test_selected_color",
        "acceptance_supports": [],
        "verification": [["pytest", "-q", "tests/test_widget.py"]],
        "obligations": ["Preserve existing callers."],
        "authority_locator": "docs/product/architecture/brief.md#Widget color",
    }

    refused_code, refused_out, refused_err = _design(root, environment, corrected)
    refused = _terminal(refused_out, refused_err)
    assert refused_code != 0 and refused.get("WHAT") == "DesignAuthorityDrift"
    assert authority.read_bytes() == authority_v1
    assert (root / HANDOVER).read_bytes() == handover_v1

    code, out, err = _design(root, environment, corrected, replace_current=True)
    rows = _terminal(out, err)
    authority_v2 = authority.read_bytes()
    handover_v2 = (root / HANDOVER).read_bytes()
    assert code == 0 and rows.get("DELIVERY-OUTCOME") == "Success", out + err
    assert rows.get("SCHEMA-VERSION") == "1"
    assert json.loads(rows["DESIGN-FACTS"]) == expected_v2_facts
    assert authority_v2.startswith(UNRELATED_AUTHORITY_PREFIX)
    assert authority_v2.endswith(UNRELATED_AUTHORITY_SUFFIX)
    assert authority_v2 != authority_v1
    assert json.loads(handover_v2)["values"][0]["authority"] == expected_v2_facts
    assert json.loads(handover_v2)["values"][1] == unrelated_v1

    craft_code, craft_out, craft_err, craft_prompt = _craft_prompt(
        root, environment, tmp_path
    )
    craft_rows = _terminal(craft_out, craft_err)
    assert craft_code != 0 and craft_rows.get("WHAT") == "CraftRejected"
    prompt_facts = {
        key: json.loads(value)
        for line in craft_prompt.splitlines()
        for key, separator, value in [line.partition(": ")]
        if separator
    }
    assert prompt_facts["authority"] == expected_v2_facts["authority_locator"]
    assert prompt_facts["decisions"] == expected_v2_facts["decisions"]
    assert prompt_facts["targets"] == [["src/widget.py", "EXTEND"]]

    retry_code, retry_out, retry_err = _design(
        root, environment, corrected, replace_current=True
    )
    retry = _terminal(retry_out, retry_err)
    assert retry_code == 0, retry_out + retry_err
    assert authority.read_bytes() == authority_v2
    assert (root / HANDOVER).read_bytes() == handover_v2
    assert {
        label: retry.get(label)
        for label in ("SCHEMA-VERSION", "DOCUMENT-SHA256", "DESIGN-FACTS")
    } == {
        label: rows.get(label)
        for label in ("SCHEMA-VERSION", "DOCUMENT-SHA256", "DESIGN-FACTS")
    }


def test_replace_current_directory_sync_failure_reports_whole_authority_as_indeterminate(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path, monkeypatch
) -> None:
    """The public terminal is honest when rename succeeded but durability is unknown."""
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    authority = _track_authority(root, UNRELATED_AUTHORITY_PREFIX)
    assert _design(root, environment, MANIFEST)[0] == 0
    handover_before = (root / HANDOVER).read_bytes()
    corrected = json.loads(json.dumps(MANIFEST))
    corrected["purpose"] = "Expose a corrected selected widget color."

    monkeypatch.setattr(
        "des.application.handover._fsync_directory",
        lambda _path, **_kwargs: Blocked(
            "DesignAuthorityUnavailable", "simulated directory sync failure", "repair"
        ),
    )
    code, out, err = _design(root, environment, corrected, replace_current=True)
    rows = _terminal(out, err)

    assert code != 0 and rows.get("DELIVERY-OUTCOME") == "Indeterminate"
    assert rows.get("WHAT") == "DesignAuthorityUnavailable"
    assert b"Expose a corrected selected widget color." in authority.read_bytes()
    assert (root / HANDOVER).read_bytes() == handover_before


def test_conflicting_bound_design_facts_refuse_before_authority_or_handover_mutation(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    """A known bound-facts conflict is refused before either public projection moves."""
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    authority = _track_authority(root, UNRELATED_AUTHORITY_PREFIX)

    bound_code, bound_out, bound_err = _design(root, environment, MANIFEST)
    bound_rows = _terminal(bound_out, bound_err)
    assert bound_code == 0 and bound_rows.get("DELIVERY-OUTCOME") == "Success", (
        "the public fixture must first create this value's tracked authority and "
        "bound DesignFacts so the later valid submission reaches the facts conflict "
        f"(stdout={bound_out!r}, stderr={bound_err!r})"
    )
    assert "design=bound" in _design_state(root, environment), (
        "the fixture's successful public DESIGN invocation must leave the value "
        "bound before the conflicting submission is evaluated"
    )
    authority_before = authority.read_bytes()
    handover_before = (root / HANDOVER).read_bytes()
    conflicting_manifest = json.loads(json.dumps(MANIFEST))
    conflicting_manifest["decisions"] = [
        "Keep color validation at the command boundary instead."
    ]

    code, out, err = _design(root, environment, conflicting_manifest)
    rows = _terminal(out, err)

    assert code != 0 and rows.get("DELIVERY-OUTCOME") == "Refusal", (
        "a valid manifest whose same-heading authority bytes diverge must "
        f"refuse through the public terminal (stdout={out!r}, stderr={err!r})"
    )
    assert rows.get("WHAT") == "DesignAuthorityDrift", (
        "the document publisher must refuse same-heading divergent authority "
        f"bytes before the facts carrier can change (stdout={out!r}, stderr={err!r})"
    )
    assert authority.read_bytes() == authority_before, (
        "a same-heading divergent document must not replace the existing owned "
        "authority section"
    )
    assert (root / HANDOVER).read_bytes() == handover_before, (
        "a same-heading authority refusal must precede every handover rewrite"
    )


def test_legacy_six_field_facts_are_repaired_by_the_same_closed_input(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    """An exact historical carrier upgrades only after its authority is re-proven."""
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    authority = _track_authority(root, UNRELATED_AUTHORITY_PREFIX)
    first_code, first_out, first_err = _design(root, environment, MANIFEST)
    assert first_code == 0, first_out + first_err
    authority_before = authority.read_bytes()

    legacy_payload = json.loads((root / HANDOVER).read_text())
    del legacy_payload["values"][0]["authority"]["obligations"]
    legacy_raw = json.dumps(
        legacy_payload, ensure_ascii=False, separators=(",", ":")
    ).encode()
    (root / HANDOVER).write_bytes(legacy_raw)

    repair_code, repair_out, repair_err = _design(root, environment, MANIFEST)
    assert repair_code == 0, repair_out + repair_err
    repaired_raw = (root / HANDOVER).read_bytes()
    repaired = json.loads(repaired_raw)
    assert authority.read_bytes() == authority_before, (
        "the same owned authority bytes must be re-proven, never reconstructed "
        "from the historical facts carrier"
    )
    assert repaired_raw != legacy_raw
    assert repaired["values"][0]["authority"]["obligations"] == MANIFEST["constraints"]
    assert repaired["values"][0]["authority"]["decisions"] == MANIFEST["decisions"]


def test_changed_heading_refuses_without_guessing_a_new_section_identity(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    authority = _track_authority(root, UNRELATED_AUTHORITY_PREFIX)
    first_code, first_out, first_err = _design(root, environment, MANIFEST)
    assert first_code == 0, first_out + first_err
    authority_before = authority.read_bytes()
    handover_before = (root / HANDOVER).read_bytes()

    next_manifest = json.loads(json.dumps(MANIFEST))
    next_manifest["authority"]["heading"] = "Widget color accessibility"
    next_manifest["decisions"] = ["Keep color validation at the command boundary."]
    next_code, next_out, next_err = _design(
        root, environment, next_manifest, replace_current=True
    )
    rows = _terminal(next_out, next_err)

    assert next_code != 0 and rows.get("WHAT") == "DesignAuthorityIdentityMismatch"
    assert authority.read_bytes() == authority_before
    assert (root / HANDOVER).read_bytes() == handover_before


def test_invalid_design_input_refuses_before_authority_or_handover_mutation(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    handover_before = (root / HANDOVER).read_bytes()
    invalid = {key: value for key, value in MANIFEST.items() if key != "reuse_analysis"}

    code, out, err = _design(root, environment, invalid)
    rows = _terminal(out, err)

    assert code != 0 and rows.get("DELIVERY-OUTCOME") == "Refusal", (
        "an incomplete closed v1 manifest must refuse at the public terminal; "
        f"got code={code}, stdout={out!r}, stderr={err!r}"
    )
    assert (
        not (root / GLOBAL_DESTINATION).exists()
        and not (root / REPOSITORY_DESTINATION).exists()
    ), (
        "validation must complete before either durable write; invalid input must "
        "not create the global or configured authority destination"
    )
    assert (root / HANDOVER).read_bytes() == handover_before, (
        "validation refusal must leave the handover byte-identical; bind facts only "
        "after the whole manifest has normalized successfully"
    )


@pytest.mark.skipif(
    sys.platform != "linux",
    reason="the public nonregular-destination regression uses a Linux Unix socket",
)
def test_existing_unix_socket_design_destination_refuses_without_projection_mutation(
    tmp_path: Path,
) -> None:
    """An existing nonregular authority destination is unsafe before either write."""
    # Linux limits Unix-socket paths to 108 bytes.  Keep only this disposable
    # real repository short; the command still receives its configured path.
    with tempfile.TemporaryDirectory(prefix="des-socket-", dir="/tmp") as workspace:
        root = base_repository(Path(workspace) / "repository")
        home = Path(workspace) / "home"
        (home / ".nwave").mkdir(parents=True)
        (home / ".nwave" / "config.json").write_text(
            json.dumps(
                {"documents": {"design": {"destination": str(REPOSITORY_DESTINATION)}}}
            )
        )
        environment = {**os.environ, "HOME": str(home)}
        _bootstrap_value(root, environment, tmp_path)
        authority = root / REPOSITORY_DESTINATION
        authority.parent.mkdir(parents=True)
        handover_before = (root / HANDOVER).read_bytes()

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as destination_socket:
            try:
                destination_socket.bind(str(authority))
            except OSError as error:
                pytest.skip(
                    "the Linux runner does not permit Unix-domain socket fixtures: "
                    f"{error}"
                )
            destination_before = authority.lstat()
            code, out, err = _design(root, environment, MANIFEST)
            rows = _terminal(out, err)
            destination_after = authority.lstat()

        assert code != 0 and rows.get("DELIVERY-OUTCOME") == "Refusal", (
            "an existing Unix-socket DESIGN destination must refuse through `des design` "
            "before any persistence; classify it as unsafe rather than reporting a "
            f"retryable storage interruption (stdout={out!r}, stderr={err!r})"
        )
        assert rows.get("WHAT") == "UnsafeDesignDestination", (
            "the public refusal must identify the nonregular configured destination as "
            f"unsafe, not expose it as {rows.get('WHAT')!r}; reject it before reading "
            "or publishing authority bytes"
        )
        assert (
            stat.S_ISSOCK(destination_before.st_mode)
            and stat.S_ISSOCK(destination_after.st_mode)
            and (
                destination_after.st_dev,
                destination_after.st_ino,
            )
            == (
                destination_before.st_dev,
                destination_before.st_ino,
            )
        ), (
            "the nonregular configured destination must remain the same Unix socket; "
            "refusal cannot replace or otherwise mutate an unsafe authority target"
        )
        assert (root / HANDOVER).read_bytes() == handover_before, (
            "an unsafe existing destination must refuse before binding DesignFacts; "
            "the handover projection must remain byte-identical"
        )


def _replace(manifest: dict, location: tuple[str | int, ...], value: object) -> None:
    current: object = manifest
    for key in location[:-1]:
        current = current[key]  # type: ignore[index]
    current[location[-1]] = value  # type: ignore[index]


@pytest.mark.parametrize(
    ("case", "location", "value"),
    [
        ("boolean schema version", ("schema_version",), True),
        ("floating-point schema version", ("schema_version",), 1.0),
        ("Markdown-prefixed heading", ("authority", "heading"), "# Widget color"),
        ("multiline heading", ("authority", "heading"), "Widget\ncolor"),
        ("trimmed-empty purpose", ("purpose",), " \t "),
        ("duplicate constraints", ("constraints",), ["same", "same"]),
        ("duplicate targets", ("targets",), [MANIFEST["targets"][0]] * 2),
        ("duplicate decisions", ("decisions",), ["same", "same"]),
        (
            "duplicate reuse candidates",
            ("reuse_analysis", "candidates"),
            [MANIFEST["reuse_analysis"]["candidates"][0]] * 2,
        ),
        (
            "duplicate supports",
            ("acceptance_supports",),
            ["tests/design_support.py", "tests/design_support.py"],
        ),
        (
            "duplicate verification argv",
            ("verification",),
            [["pytest", "-q", "tests/test_widget.py"]] * 2,
        ),
        ("absolute target path", ("targets", 0, "path"), "/tmp/widget.py"),
        ("traversing target path", ("targets", 0, "path"), "../widget.py"),
        (
            "malformed candidate locator",
            ("reuse_analysis", "candidates", 0, "locator"),
            "src/widget.py:0",
        ),
        (
            "absolute oracle locator",
            ("oracle",),
            "/tmp/test_widget.py::test_selected_color",
        ),
        (
            "traversing oracle locator",
            ("oracle",),
            "../test_widget.py::test_selected_color",
        ),
        ("traversing support path", ("acceptance_supports",), ["../support.py"]),
        ("empty verification argv", ("verification",), [[]]),
        ("empty verification argument", ("verification",), [["pytest", ""]]),
        (
            "unknown boundaries applicability",
            ("boundaries", "applicability"),
            "sometimes",
        ),
    ],
)
def test_closed_v1_construction_refuses_invalid_text_collections_and_locators(
    design_repository: tuple[Path, dict[str, str]],
    tmp_path: Path,
    case: str,
    location: tuple[str | int, ...],
    value: object,
) -> None:
    """Each closed-language violation is refused through the real CLI before I/O."""
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    manifest = json.loads(json.dumps(MANIFEST))
    _replace(manifest, location, value)

    _assert_refusal_without_projection_mutation(root, environment, manifest)


@pytest.mark.parametrize(
    ("case", "field", "value"),
    [
        ("duplicate driven ports", "driven_ports", ["handover", "handover"]),
        (
            "duplicate failure descriptions",
            "failures",
            [
                {
                    "condition": "write fails",
                    "outcome": "Indeterminate",
                    "observation": "The terminal reports mixed projections.",
                }
            ]
            * 2,
        ),
    ],
)
def test_applicable_boundaries_reject_duplicate_required_entries(
    design_repository: tuple[Path, dict[str, str]],
    tmp_path: Path,
    case: str,
    field: str,
    value: object,
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    manifest = json.loads(json.dumps(MANIFEST))
    manifest["boundaries"] = {
        "applicability": "applicable",
        "driving_port": "des design",
        "driven_ports": ["authority", "handover"],
        "dependency_direction": "CLI depends inward on the producer.",
        "failures": [
            {
                "condition": "write fails",
                "outcome": "Indeterminate",
                "observation": "The terminal reports mixed projections.",
            }
        ],
    }
    manifest["boundaries"][field] = value

    _assert_refusal_without_projection_mutation(root, environment, manifest)


def test_trimmed_heading_normalizes_to_the_public_document_locator(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    manifest = json.loads(json.dumps(MANIFEST))
    manifest["authority"]["heading"] = "  Widget color  "

    code, out, err = _design(root, environment, manifest)
    rows = _terminal(out, err)

    assert code == 0 and rows.get("DELIVERY-OUTCOME") == "Success", (
        "a heading with surrounding whitespace must normalize as closed v1 text, "
        f"not be treated as a distinct authority (stdout={out!r}, stderr={err!r})"
    )
    assert rows.get("DOCUMENT") == f"{REPOSITORY_DESTINATION}#Widget color", (
        "the public locator must use the trimmed heading so retries and H2 ownership "
        "refer to one normalized section"
    )


@pytest.mark.parametrize(
    ("case", "prefactoring", "boundaries"),
    [
        (
            "not-applicable prefactoring",
            {"applicability": "not_applicable", "reason": "No safe move is needed."},
            MANIFEST["boundaries"],
        ),
        (
            "applicable boundaries",
            MANIFEST["prefactoring"],
            {
                "applicability": "applicable",
                "driving_port": "des design",
                "driven_ports": ["architecture authority", "handover"],
                "dependency_direction": "CLI depends inward on the producer.",
                "failures": [
                    {
                        "condition": "authority write fails",
                        "outcome": "Indeterminate",
                        "observation": "The terminal reports mixed projections.",
                    }
                ],
            },
        ),
    ],
)
def test_closed_v1_optional_prefactoring_and_boundaries_forms_are_constructible(
    design_repository: tuple[Path, dict[str, str]],
    tmp_path: Path,
    case: str,
    prefactoring: dict,
    boundaries: dict,
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    manifest = json.loads(json.dumps(MANIFEST))
    manifest["prefactoring"] = prefactoring
    manifest["boundaries"] = boundaries

    code, out, err = _design(root, environment, manifest)
    rows = _terminal(out, err)

    assert code == 0 and rows.get("DELIVERY-OUTCOME") == "Success", (
        f"the closed v1 {case} form must construct through `des design` "
        f"(stdout={out!r}, stderr={err!r})"
    )
    assert (root / REPOSITORY_DESTINATION).exists() and (root / HANDOVER).exists(), (
        "an accepted optional form must reach the same two public durable "
        "projections as the complete semantic manifest"
    )


def test_design_document_requires_agreement_analysis_before_authority_or_handover_mutation(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    """A manifest silent on shared-contract consumers is refused, not assumed safe.

    This is the observed regression class: commit 11352c52a migrated four of
    five release-channel consumers of the same schema and forgot the fifth
    because nothing forced the author to name every producer/consumer pair.
    """
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    missing_field = {
        key: value for key, value in MANIFEST.items() if key != "agreement_analysis"
    }

    _assert_refusal_without_projection_mutation(root, environment, missing_field)


def test_design_document_requires_a_reason_for_not_applicable_agreement_analysis(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    """Declaring the not-applicable case still requires the closed reason field."""
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    manifest = json.loads(json.dumps(MANIFEST))
    manifest["agreement_analysis"] = {"applicability": "not_applicable"}

    authority = root / REPOSITORY_DESTINATION
    handover_before = (root / HANDOVER).read_bytes()

    code, out, err = _design(root, environment, manifest)
    rows = _terminal(out, err)

    assert code != 0 and rows.get("DELIVERY-OUTCOME") == "Refusal", (
        "a not_applicable agreement_analysis missing its reason must refuse at "
        f"the public terminal (stdout={out!r}, stderr={err!r})"
    )
    assert "agreement_analysis" in (out + err), (
        "the refusal must identify agreement_analysis by name so the author "
        f"knows which closed field is incomplete (stdout={out!r}, stderr={err!r})"
    )
    assert not authority.exists(), (
        "validation must precede every durable authority write"
    )
    assert (root / HANDOVER).read_bytes() == handover_before, (
        "validation refusal must leave the existing handover byte-identical"
    )


APPLICABLE_AGREEMENT_ANALYSIS = {
    "applicability": "applicable",
    "parties": [
        {
            "contract": "release migration decision schema",
            "role": "producer",
            "locator": "scripts/release/release_migration_decision.py:47",
            "decision": "MIGRATED",
            "reason": "Emits schema v4 for every release channel.",
        },
        {
            "contract": "release migration decision schema",
            "role": "consumer",
            "locator": "scripts/release/experimental_migration_decision.py:20",
            "decision": "MIGRATED",
            "reason": "Reads schema v4 like every other release channel.",
        },
    ],
}


def test_applicable_agreement_analysis_renders_every_declared_party(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    """Each declared producer/consumer pair is readable in the rendered authority."""
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    manifest = json.loads(json.dumps(MANIFEST))
    manifest["agreement_analysis"] = APPLICABLE_AGREEMENT_ANALYSIS

    code, out, err = _design(root, environment, manifest)
    rows = _terminal(out, err)
    authority = (root / REPOSITORY_DESTINATION).read_text()

    assert code == 0 and rows.get("DELIVERY-OUTCOME") == "Success", (
        "a complete applicable agreement_analysis manifest must construct "
        f"through `des design` (stdout={out!r}, stderr={err!r})"
    )
    missing_authority_observations = {
        observation
        for party in APPLICABLE_AGREEMENT_ANALYSIS["parties"]
        for observation in (
            party["contract"],
            party["role"],
            party["locator"],
            party["decision"],
            party["reason"],
        )
        if observation not in authority
    }
    assert not missing_authority_observations, (
        "the rendered authority must retain every declared party's contract, "
        "role, locator, decision, and reason; render the missing fixture "
        f"observations: {sorted(missing_authority_observations)!r}"
    )
    assert "### Agreement analysis" in authority, (
        "the rendered authority must carry a distinct Agreement analysis "
        "section, not fold parties into an unrelated section"
    )


@pytest.mark.parametrize(
    ("case", "agreement_analysis"),
    [
        (
            "duplicate declared parties",
            {
                "applicability": "applicable",
                "parties": [APPLICABLE_AGREEMENT_ANALYSIS["parties"][0]] * 2,
            },
        ),
        (
            "empty declared parties",
            {"applicability": "applicable", "parties": []},
        ),
        (
            "unknown decision literal",
            {
                "applicability": "applicable",
                "parties": [
                    {
                        **APPLICABLE_AGREEMENT_ANALYSIS["parties"][0],
                        "decision": "FORGOTTEN",
                    }
                ],
            },
        ),
    ],
)
def test_applicable_agreement_analysis_rejects_malformed_parties(
    design_repository: tuple[Path, dict[str, str]],
    tmp_path: Path,
    case: str,
    agreement_analysis: dict,
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    manifest = json.loads(json.dumps(MANIFEST))
    manifest["agreement_analysis"] = agreement_analysis

    _assert_refusal_without_projection_mutation(root, environment, manifest)


def test_default_repository_relative_design_destination_is_used_without_config(
    tmp_path: Path,
) -> None:
    root = base_repository(tmp_path / "repository")
    home = tmp_path / "home"
    environment = {**os.environ, "HOME": str(home)}
    _bootstrap_value(root, environment, tmp_path)

    code, out, err = _design(root, environment, MANIFEST)
    rows = _terminal(out, err)

    assert code == 0 and rows.get("DELIVERY-OUTCOME") == "Success", (
        "without either configuration tier, DESIGN must use its declared repository "
        f"default destination (stdout={out!r}, stderr={err!r})"
    )
    assert (root / REPOSITORY_DESTINATION).exists(), (
        "the default documents.design.destination must be the repository-relative "
        "docs/product/architecture/brief.md authority"
    )


def test_design_uses_nwave_agents_home_global_destination_before_repository_override(
    tmp_path: Path,
) -> None:
    """The public producer reads the same selected global authority as G1."""
    root = base_repository(tmp_path / "repository")
    home = tmp_path / "unselected-home"
    agents_home = tmp_path / "selected-agents-home"
    (agents_home / ".nwave").mkdir(parents=True)
    (agents_home / ".nwave" / "config.json").write_text(
        json.dumps({"documents": {"design": {"destination": str(GLOBAL_DESTINATION)}}})
    )
    environment = {
        **os.environ,
        "HOME": str(home),
        "NWAVE_AGENTS_HOME": str(agents_home),
    }
    _bootstrap_value(root, environment, tmp_path)

    code, out, err = _design(root, environment, MANIFEST)
    rows = _terminal(out, err)

    assert code == 0 and rows.get("DELIVERY-OUTCOME") == "Success", (
        "the selected NWAVE_AGENTS_HOME global config must drive the public "
        f"DESIGN destination (stdout={out!r}, stderr={err!r})"
    )
    assert (root / GLOBAL_DESTINATION).exists() and not (
        root / REPOSITORY_DESTINATION
    ).exists(), (
        "when the repository declares no documents.destination, DESIGN must use "
        "the G1-selected global config rather than the unrelated HOME or default"
    )


def test_handover_io_failure_is_indeterminate_and_exact_projection_retryable(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    handover_before = (root / HANDOVER).read_bytes()
    handover_directory = (root / HANDOVER).parent
    before_state = _design_state(root, environment)

    # PO has already created the cooperative lock, so this denies only the
    # handover replacement's temporary write, after the authority can ship.
    handover_directory.chmod(0o555)
    try:
        code, out, err = _design(root, environment, MANIFEST)
    finally:
        handover_directory.chmod(0o755)

    rows = _terminal(out, err)
    authority = root / REPOSITORY_DESTINATION
    assert code != 0 and rows.get("DELIVERY-OUTCOME") == "Indeterminate", (
        "a filesystem failure after the authority write must be publicly "
        f"indeterminate, never a claimed rollback (stdout={out!r}, stderr={err!r})"
    )
    assert authority.read_text() == EXPECTED_SECTION, (
        "the indeterminate result must truthfully retain the already-written "
        "authority section rather than claim it was rolled back"
    )
    assert (root / HANDOVER).read_bytes() == handover_before, (
        "the failed handover compare-and-swap must leave its old bytes intact so "
        "the exact authority-plus-old-handover combination is identifiable"
    )

    retry_code, retry_out, retry_err = _design(root, environment, MANIFEST)
    after_state = _design_state(root, environment)
    assert (
        retry_code == 0
        and _terminal(retry_out, retry_err).get("DELIVERY-OUTCOME") == "Success"
    ), (
        "after filesystem repair, the declared exact section plus old handover "
        "combination must complete the handover CAS on retry"
    )
    assert_state_delta(
        before={
            "configured_authority": False,
            "global_authority": False,
            "design_state": "design=bound" in before_state,
        },
        after={
            "configured_authority": authority.exists(),
            "global_authority": (root / GLOBAL_DESTINATION).exists(),
            "design_state": "design=bound" in after_state,
        },
        universe={"configured_authority", "global_authority", "design_state"},
        expected={
            "configured_authority": set_to(True),
            "global_authority": unchanged(),
            "design_state": set_to(True),
        },
    )


def test_exact_untracked_authority_with_the_admissible_old_handover_binds_only_facts(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    """The authority-first interruption is retryable without adopting other bytes."""
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    authority = root / REPOSITORY_DESTINATION
    authority.parent.mkdir(parents=True)
    authority.write_bytes(EXPECTED_SECTION.encode())
    handover_before = (root / HANDOVER).read_bytes()

    code, out, err = _design(root, environment, MANIFEST)
    rows = _terminal(out, err)

    assert code == 0 and rows.get("DELIVERY-OUTCOME") == "Success", (
        "the exact untracked single-section authority left by an authority-first "
        "interruption, paired with this value's old handover, must resume only "
        f"the handover binding (stdout={out!r}, stderr={err!r})"
    )
    assert authority.read_bytes() == EXPECTED_SECTION.encode(), (
        "the narrow untracked retry exception must not rewrite even one authority "
        "byte; only the admissible old handover may be advanced"
    )
    assert (root / HANDOVER).read_bytes() != handover_before, (
        "resuming an exact authority plus the old handover must bind facts rather "
        "than falsely report an idempotent success with the value still unbound"
    )
    assert "design=bound" in _design_state(root, environment), (
        "the public state projection must show the value bound after the narrow "
        "authority-first recovery completes"
    )


@pytest.mark.parametrize(
    ("case", "contents"),
    [
        (
            "prefix",
            b"Human preface outside DESIGN ownership.\n\n" + EXPECTED_SECTION.encode(),
        ),
        (
            "suffix",
            EXPECTED_SECTION.encode() + b"\nHuman appendix outside DESIGN ownership.\n",
        ),
        (
            "other-h2",
            EXPECTED_SECTION.encode() + b"\n## Another authority\n\nHuman text.\n",
        ),
        (
            "divergent-owned-section",
            EXPECTED_SECTION.replace(
                "Expose the selected widget color.", "Hide the selected widget color."
            ).encode(),
        ),
        ("duplicate-matching-h2", EXPECTED_SECTION.encode() * 2),
    ],
)
def test_untracked_authority_outside_the_exact_retry_shape_refuses_unchanged(
    design_repository: tuple[Path, dict[str, str]],
    tmp_path: Path,
    case: str,
    contents: bytes,
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    authority = root / REPOSITORY_DESTINATION
    authority.parent.mkdir(parents=True)
    authority.write_bytes(contents)
    handover_before = (root / HANDOVER).read_bytes()

    code, out, err = _design(root, environment, MANIFEST)
    rows = _terminal(out, err)

    assert code != 0 and rows.get("DELIVERY-OUTCOME") == "Refusal", (
        f"an untracked authority with a {case} must refuse explicit recovery, "
        f"never be adopted by the retry exception (stdout={out!r}, stderr={err!r})"
    )
    assert authority.read_bytes() == contents, (
        f"the {case} untracked authority must remain byte-identical on refusal; "
        "DESIGN may resume only the exact canonical single-section interruption"
    )
    assert (root / HANDOVER).read_bytes() == handover_before, (
        f"the {case} untracked authority must not bind facts while its authority "
        "ownership remains unsafe"
    )


def test_only_a_complete_h2_line_owns_a_section(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    prose_with_heading_bytes = (
        b"# Architecture authority\n\n"
        b"This prose quotes ## Widget color but owns no DESIGN section.\n\n"
    )
    authority = _track_authority(root, prose_with_heading_bytes)

    code, out, err = _design(root, environment, MANIFEST)
    rows = _terminal(out, err)

    assert code == 0 and rows.get("DELIVERY-OUTCOME") == "Success", (
        "only a line whose complete content is the owned H2 may claim DESIGN "
        f"ownership; heading bytes inside prose must not block insertion (stdout={out!r}, stderr={err!r})"
    )
    assert (
        authority.read_bytes() == prose_with_heading_bytes + EXPECTED_SECTION.encode()
    ), (
        "a prose occurrence of the heading must remain byte-identical and the "
        "canonical section must append after it"
    )


def test_duplicate_matching_h2_lines_refuse_before_any_projection_changes(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    duplicate_sections = EXPECTED_SECTION.encode() * 2
    authority = _track_authority(root, duplicate_sections)
    handover_before = (root / HANDOVER).read_bytes()

    code, out, err = _design(root, environment, MANIFEST)
    rows = _terminal(out, err)

    assert code != 0 and rows.get("DELIVERY-OUTCOME") == "Refusal", (
        "two matching complete H2 lines are ambiguous even when both bodies are "
        f"canonical, so the public command must refuse (stdout={out!r}, stderr={err!r})"
    )
    assert authority.read_bytes() == duplicate_sections, (
        "duplicate matching H2 ambiguity must be detected before authority mutation"
    )
    assert (root / HANDOVER).read_bytes() == handover_before, (
        "duplicate matching H2 ambiguity must be detected before facts are bound"
    )


def test_authority_prewrite_drift_refuses_without_stale_overwrite(
    design_repository: tuple[Path, dict[str, str]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    original_authority = UNRELATED_AUTHORITY_PREFIX
    authority = _track_authority(root, original_authority)
    handover_before = (root / HANDOVER).read_bytes()
    concurrent_authority = original_authority + b"Concurrent human edit.\n"
    read_bytes = Path.read_bytes
    write_bytes = Path.write_bytes
    authority_reads = 0

    def drift_before_authority_cas(path: Path) -> bytes:
        nonlocal authority_reads
        if path == authority:
            authority_reads += 1
            if authority_reads == 2:
                write_bytes(path, concurrent_authority)
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", drift_before_authority_cas)
    code, out, err = _design(root, environment, MANIFEST)
    rows = _terminal(out, err)

    assert code != 0 and rows.get("DELIVERY-OUTCOME") == "Refusal", (
        "authority bytes changed after snapshot but before replacement must refuse "
        f"rather than overwrite a concurrent edit (stdout={out!r}, stderr={err!r})"
    )
    assert authority.read_bytes() == concurrent_authority, (
        "the authority prewrite CAS must preserve the concurrent bytes instead of "
        "writing a section rendered from a stale snapshot"
    )
    assert (root / HANDOVER).read_bytes() == handover_before, (
        "authority prewrite drift must prevent the later handover binding as well"
    )


def test_post_authority_handover_drift_is_indeterminate_and_never_stale_overwrites(
    design_repository: tuple[Path, dict[str, str]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    handover_before = (root / HANDOVER).read_bytes()
    concurrent_handover = handover_before + b"\n"
    read_bytes = Path.read_bytes
    write_bytes = Path.write_bytes
    handover_reads = 0

    def drift_before_handover_cas(path: Path) -> bytes:
        nonlocal handover_reads
        if path == root / HANDOVER:
            handover_reads += 1
            if handover_reads == 2:
                write_bytes(path, concurrent_handover)
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", drift_before_handover_cas)
    code, out, err = _design(root, environment, MANIFEST)
    rows = _terminal(out, err)

    assert code != 0 and rows.get("DELIVERY-OUTCOME") == "Indeterminate", (
        "handover drift discovered after authority persistence is a mixed durable "
        f"state and must report Indeterminate (stdout={out!r}, stderr={err!r})"
    )
    assert (root / REPOSITORY_DESTINATION).read_bytes() == EXPECTED_SECTION.encode(), (
        "the authority-first protocol must truthfully retain the completed "
        "canonical authority section after later handover drift"
    )
    assert (root / HANDOVER).read_bytes() == concurrent_handover, (
        "the handover CAS must preserve concurrent bytes instead of overwriting "
        "them with facts derived from its stale snapshot"
    )

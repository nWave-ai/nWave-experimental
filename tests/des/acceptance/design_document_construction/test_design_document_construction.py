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
    observation,
)

from des.application.handover import Blocked
from des.domain.design_document import DesignDocument
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
    "oracle_verification_index": 0,
}

EXPECTED_SECTION = """## Widget color

### Purpose (Widget color)

Expose the selected widget color.

### Constraints (Widget color)

- Preserve existing callers.

### Targets (Widget color)

| Path | Decision | Reason |
|---|---|---|
| `src/widget.py` | EXTEND | Widget already owns color. |

### Paradigm (Widget color)

object_oriented

### Decisions (Widget color)

- Keep color validation at Widget construction.

### Reuse analysis (Widget color)

| Symbol | Locator | Decision | Reason |
|---|---|---|---|
| Widget | `src/widget.py:10` | EXTEND | Existing public owner. |

### Prefactoring (Widget color)

Existing oracle: `tests/test_widget.py::test_default_color`

Move: Extract the current default lookup without changing output.

Preserved observation: A default widget remains blue.

### Agreement analysis (Widget color)

Not applicable: The widget color extension touches no shared release or
interchange schema.

### Boundaries (Widget color)

Not applicable: No port or dependency boundary changes.

### Public oracle (Widget color)

Observation: CLI prints the selected color.

Stimulus: Run widget show --color red.

Expected: stdout is red and exit is zero.

Falsifier: Any other stdout or non-zero exit.

### Oracle and verification (Widget color)

Oracle target locator: `tests/test_widget.py::test_selected_color`
Oracle verification command index: `0`

Verification command:

```sh
pytest -q tests/test_widget.py
```
"""

EXPECTED_FACTS = {
    "targets": [{"path": "src/widget.py", "decision": "EXTEND"}],
    "paradigm": "object_oriented",
    "decisions": ["Keep color validation at Widget construction."],
    "oracle": "tests/test_widget.py::test_selected_color",
    "acceptance_supports": [],
    "verification": [["pytest", "-q", "tests/test_widget.py"]],
    "oracle_verification_index": 0,
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
    scope_flags: tuple[str, ...] = ("--project",),
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
        ["po", "--repo-root", str(root), *scope_flags],
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
    migrate_legacy_rendering: bool = False,
    replace_unbound: bool = False,
    value: int = 1,
) -> tuple[int, str, str]:
    arguments = ["design", "--repo-root", str(root), "--value", str(value)]
    if replace_current:
        arguments.append("--replace-current")
    if migrate_legacy_rendering:
        arguments.append("--migrate-legacy-rendering")
    if replace_unbound:
        arguments.append("--replace-unbound")
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
    # Prose is hard-wrapped at 80 columns, so an observation is readable in the
    # authority once its line breaks are read as the spaces they render as.
    authority = " ".join((root / REPOSITORY_DESTINATION).read_text().split())
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
        "oracle_verification_index": 0,
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
    assert json.loads(handover_v2)["values"][0]["authority"] == {
        **expected_v2_facts,
        "public_oracle": corrected["public_oracle"],
    }
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


def test_explicit_legacy_rendering_migration_binds_only_an_exact_historical_section(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    """A renderer-only upgrade restores an interrupted tracked value deterministically."""
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    document = DesignDocument.from_json(json.dumps(MANIFEST))
    authority = _track_authority(
        root,
        UNRELATED_AUTHORITY_PREFIX
        + document.legacy_markdown_v1().encode()
        + UNRELATED_AUTHORITY_SUFFIX,
    )
    before = authority.read_bytes()
    handover_before = (root / HANDOVER).read_bytes()

    refused_code, refused_out, refused_err = _design(root, environment, MANIFEST)
    assert refused_code != 0 and _terminal(refused_out, refused_err).get("WHAT") == (
        "DesignAuthorityDrift"
    )
    assert authority.read_bytes() == before
    assert (root / HANDOVER).read_bytes() == handover_before

    code, out, err = _design(root, environment, MANIFEST, migrate_legacy_rendering=True)
    rows = _terminal(out, err)
    assert code == 0 and rows.get("DELIVERY-OUTCOME") == "Success", out + err
    assert document.markdown().encode() in authority.read_bytes()
    assert document.legacy_markdown_v1().encode() not in authority.read_bytes()
    assert authority.read_bytes().startswith(UNRELATED_AUTHORITY_PREFIX)
    assert authority.read_bytes().endswith(UNRELATED_AUTHORITY_SUFFIX)
    assert json.loads((root / HANDOVER).read_text())["values"][0]["authority"] == {
        **EXPECTED_FACTS,
        "public_oracle": MANIFEST["public_oracle"],
    }


def test_explicit_unbound_recovery_replaces_only_the_named_tracked_section(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    """A complete manifest can explicitly repair a pre-binding authority gap."""
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    authority = _track_authority(
        root,
        UNRELATED_AUTHORITY_PREFIX
        + b"## Widget color\n\nPartial historical authority.\n"
        + UNRELATED_AUTHORITY_SUFFIX,
    )
    before = authority.read_bytes()
    handover_before = (root / HANDOVER).read_bytes()

    refused_code, refused_out, refused_err = _design(root, environment, MANIFEST)
    assert refused_code != 0 and _terminal(refused_out, refused_err).get("WHAT") == (
        "DesignAuthorityDrift"
    )
    assert authority.read_bytes() == before
    assert (root / HANDOVER).read_bytes() == handover_before

    code, out, err = _design(root, environment, MANIFEST, replace_unbound=True)
    rows = _terminal(out, err)
    assert code == 0 and rows.get("DELIVERY-OUTCOME") == "Success", out + err
    assert authority.read_bytes().startswith(UNRELATED_AUTHORITY_PREFIX)
    assert authority.read_bytes().endswith(UNRELATED_AUTHORITY_SUFFIX)
    assert EXPECTED_SECTION.encode() in authority.read_bytes()
    assert b"Partial historical authority." not in authority.read_bytes()
    assert json.loads((root / HANDOVER).read_text())["values"][0]["authority"] == {
        **EXPECTED_FACTS,
        "public_oracle": MANIFEST["public_oracle"],
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


@pytest.mark.parametrize("removed_member", ["obligations", "public_oracle"])
def test_legacy_six_field_facts_are_repaired_by_the_same_closed_input(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path, removed_member: str
) -> None:
    """An exact historical carrier upgrades only after its authority is re-proven."""
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    authority = _track_authority(root, UNRELATED_AUTHORITY_PREFIX)
    first_code, first_out, first_err = _design(root, environment, MANIFEST)
    assert first_code == 0, first_out + first_err
    authority_before = authority.read_bytes()

    legacy_payload = json.loads((root / HANDOVER).read_text())
    del legacy_payload["values"][0]["authority"][removed_member]
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
    if removed_member == "obligations":
        assert (
            repaired["values"][0]["authority"]["obligations"] == MANIFEST["constraints"]
        )
        assert repaired["values"][0]["authority"]["decisions"] == MANIFEST["decisions"]
    elif removed_member == "public_oracle":
        assert (
            repaired["values"][0]["authority"]["public_oracle"]
            == MANIFEST["public_oracle"]
        )
        assert repaired["values"][0]["authority"].get("public_oracle") is not None


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
        ("NUL verification token", ("verification",), [["pytest", "a\x00b"]]),
        (
            "out-of-range oracle verification command index",
            ("oracle_verification_index",),
            1,
        ),
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


def test_public_construction_refuses_a_new_target_required_as_acceptance_support(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    """The public constructor refuses the cross-field contradiction pre-write."""
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    manifest = json.loads(json.dumps(MANIFEST))
    manifest["targets"] = [
        {"path": "tests/design_support.py", "decision": "CREATE_NEW"}
    ]
    manifest["acceptance_supports"] = ["tests/design_support.py"]

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
    write_bytes = Path.write_bytes
    from des.application import handover as handover_module

    replace_exact_bytes = handover_module.replace_exact_bytes

    def drift_before_handover_cas(path: Path, *args, **kwargs):
        # Land the concurrent edit immediately before the handover CAS read,
        # independent of how many other reads precede it.
        if path == root / HANDOVER:
            write_bytes(path, concurrent_handover)
        return replace_exact_bytes(path, *args, **kwargs)

    monkeypatch.setattr(
        handover_module, "replace_exact_bytes", drift_before_handover_cas
    )
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


# A tracked human authority whose last content line carries no terminator.  The
# producer appends its owned section verbatim and never inserts a separator, so
# the declared H2 lands glued to the end of that line and no longer begins a
# line of its own -- the document on disk resolves ZERO sections for the very
# heading this invocation claims to have written.
UNTERMINATED_AUTHORITY_PREFIX = (
    b"# Architecture authority\n\nThis human introduction is outside DESIGN ownership."
)


def test_design_inserts_a_separator_before_an_owned_section(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    """A final human line without a terminator still yields a resolvable section.

    DESIGN retains every human byte, adds only the two newline bytes needed for
    its owned H2 to start on its own line, then binds facts to the read-back
    document it actually wrote.
    """
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    authority = _track_authority(root, UNTERMINATED_AUTHORITY_PREFIX)
    handover_before = (root / HANDOVER).read_bytes()

    code, out, err = _design(root, environment, MANIFEST)
    rows = _terminal(out, err)
    authority_on_disk = authority.read_bytes()
    state = _design_state(root, environment)
    expected_locator = f"{REPOSITORY_DESTINATION}#Widget color"

    assert code == 0 and rows.get("DELIVERY-OUTCOME") == "Success", out + err
    assert authority_on_disk == (
        UNTERMINATED_AUTHORITY_PREFIX + b"\n\n" + EXPECTED_SECTION.encode()
    ), "DES must preserve human bytes and add only the required H2 separator"
    assert rows.get("DOCUMENT") == expected_locator
    assert rows.get("DOCUMENT-SHA256") == hashlib.sha256(authority_on_disk).hexdigest()
    assert "design=bound" in state
    assert (root / HANDOVER).read_bytes() != handover_before


def _replay_design(
    root: Path,
    environment: dict[str, str],
    tmp_path: Path,
    *,
    label: str,
    value: int = 1,
) -> tuple[int, str, str, Path]:
    """Run `des design --value N` with NO input and NO finding: the replay arm.

    The step resolves its provider port before this branch runs even though it
    buys no turn, so the invocation carries a controlled provider.  The returned
    log path is the falsifier for "zero turns": it must never come into
    existence, because a replay that bought an architect turn is not a replay.
    """
    results, turns, counter = (
        tmp_path / f"{label}-answers.json",
        tmp_path / f"{label}-turns.json",
        tmp_path / f"{label}-counter",
    )
    results.write_text(json.dumps([]))
    provider_environment = fake_provider.environment(
        root,
        launcher_dir=tmp_path / f"{label}-bin",
        results=results,
        log=turns,
        counter=counter,
        package_parent=PACKAGE_PARENT,
    )
    code, out, err = run_cli_in_process(
        ["design", "--repo-root", str(root), "--value", str(value)],
        cwd=root,
        env=hermetic_environment(
            provider_environment | {"HOME": environment["HOME"]},
            tmp_path / f"{label}-claude-config",
        ),
        catch_all=True,
    )
    return code, out, err, turns


def test_design_replay_reports_a_binding_only_while_the_document_resolves_it(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    """A stored `design=bound` record is confirmed only by the document on disk.

    One value is bound through the real public constructor, then replayed twice
    through `des design --value 1` -- the zero-cost arm that today trusts the
    stored designation without ever opening a document.  The two replays differ
    only in whether the value's own recorded authority locator still resolves in
    the configured document:

    * while the section resolves, the replay is exactly today's answer -- the
      same Success, the same VALUE/PARADIGM/ORACLE/TARGETS/RECORDED facts, zero
      turns bought and not one byte written;
    * once a human renames that H2 out of the document, the record and the file
      disagree.  The replay must then refuse rather than confirm a binding the
      document no longer carries, naming the unresolved locator, saying that the
      record and the file disagree, and naming `--finding -` as the way forward.
    """
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    authority = _track_authority(root, UNRELATED_AUTHORITY_PREFIX)
    bind_code, bind_out, bind_err = _design(root, environment, MANIFEST)
    assert bind_code == 0, (
        "the public constructor must first bind this value's typed design facts "
        f"to a resolving document section (stdout={bind_out!r}, stderr={bind_err!r})"
    )
    assert "design=bound" in _design_state(root, environment), (
        "the fixture must reach the recorded state whose agreement with the "
        "document this scenario is about"
    )
    expected_locator = f"{REPOSITORY_DESTINATION}#Widget color"
    authority_bound = authority.read_bytes()
    handover_bound = (root / HANDOVER).read_bytes()

    agreeing_code, agreeing_out, agreeing_err, agreeing_turns = _replay_design(
        root, environment, tmp_path, label="agreeing"
    )
    agreeing_rows = _terminal(agreeing_out, agreeing_err)
    agreeing_transcript = _words(agreeing_out + "\n" + agreeing_err)

    assert agreeing_code == 0 and agreeing_rows.get("DELIVERY-OUTCOME") == "Success", (
        "while the recorded locator still resolves, the replay must remain the "
        "zero-cost Success it is today; reading the document back may not turn a "
        f"true binding into a failure (stdout={agreeing_out!r}, stderr={agreeing_err!r})"
    )
    assert agreeing_rows.get("TURNS-BOUGHT") == "0", (
        "confirming an agreeing record must stay free; the replay reads a "
        f"document, it does not buy an architect turn (rows={agreeing_rows!r})"
    )
    assert not agreeing_turns.exists(), (
        "the agreeing replay must invoke no provider at all; a bought turn over "
        "an already-bound value is the paid overwrite L1 exists to prevent"
    )
    assert {
        label: agreeing_rows.get(label)
        for label in ("VALUE-1", "PARADIGM", "ORACLE", "TARGETS")
    } == {
        "VALUE-1": json.dumps(observation("widget color"), ensure_ascii=False),
        "PARADIGM": EXPECTED_FACTS["paradigm"],
        "ORACLE": EXPECTED_FACTS["oracle"],
        "TARGETS": "src/widget.py (EXTEND)",
    }, (
        "the agreeing replay must publish exactly the same typed facts as today; "
        "the read-back decides whether these rows may be published, it does not "
        f"change one of them (rows={agreeing_rows!r})"
    )
    assert "RECORDED:" in agreeing_out + agreeing_err, (
        "the agreeing replay must keep publishing its RECORDED row so a caller "
        "still learns that the facts were already bound and nothing was rebought"
    )
    assert (
        _words(
            "this value's typed design facts are already bound over these bytes, "
            "so no turn was bought; re-bind with `des design --repo-root <root> "
            "--value 1 --finding -`"
        )
        in agreeing_transcript
    ), (
        "the RECORDED row must remain its current sentence, including the "
        f"`--finding -` re-bind: the agreeing arm changes no byte "
        f"(stdout={agreeing_out!r}, stderr={agreeing_err!r})"
    )
    assert (
        authority.read_bytes() == authority_bound
        and (root / HANDOVER).read_bytes() == handover_bound
    ), (
        "the agreeing replay must leave both durable projections byte-identical; "
        "it reads the document to decide, it never writes one"
    )

    stale_document = authority_bound.replace(
        b"\n## Widget color\n", b"\n## Widget colour\n"
    )
    assert stale_document != authority_bound, (
        "the fixture must actually rename the owned H2 out of the document; "
        "otherwise the stale-record world is never entered"
    )
    authority.write_bytes(stale_document)
    git(root, "commit", "-qam", "human renames the owned architecture heading")
    handover_before_stale = (root / HANDOVER).read_bytes()

    stale_code, stale_out, stale_err, stale_turns = _replay_design(
        root, environment, tmp_path, label="stale"
    )
    stale_rows = _terminal(stale_out, stale_err)
    stale_transcript = _words(stale_out + "\n" + stale_err)
    stale_state = _design_state(root, environment)

    assert stale_code != 0 and stale_rows.get("DELIVERY-OUTCOME") == "Refusal", (
        "a recorded binding whose locator resolves no section in the document on "
        "disk must refuse; reporting Success here confirms a binding the file "
        f"does not carry (stdout={stale_out!r}, stderr={stale_err!r})"
    )
    assert stale_rows.get("WHAT") == "DesignAuthorityUnlocatable", (
        "the stale record must reuse the name that already owns 'the declared "
        f"DESIGN authority section does not resolve on disk', not {stale_rows.get('WHAT')!r}; "
        "a document that answered and simply does not resolve the heading is a "
        "refusal, never a retryable substrate failure"
    )
    assert not stale_turns.exists(), (
        "the refusal must intercept before any role is bought; a disagreement "
        "between the record and the file costs the caller nothing"
    )
    missing_refusal_observations = {
        observation
        for observation in (
            expected_locator,
            "record",
            "disagree",
            "--finding -",
        )
        if observation not in stale_transcript
    }
    assert not missing_refusal_observations, (
        "the public refusal must name the unresolved locator verbatim as "
        "'<document>#<heading>', say that the stored record and the document "
        "disagree, and name the producing re-bind `des design ... --finding -` "
        f"as the way forward; the terminal omitted {sorted(missing_refusal_observations)!r} "
        f"(stdout={stale_out!r}, stderr={stale_err!r})"
    )
    assert "ORACLE:" not in stale_out + stale_err, (
        "a refusal must not also publish the bound facts rows; the step either "
        "confirms the binding or refuses it, never both"
    )
    assert authority.read_bytes() == stale_document, (
        "the refusal must leave the human-owned document byte-identical; the "
        "step reads it to decide and never repairs it on the author's behalf"
    )
    assert (root / HANDOVER).read_bytes() == handover_before_stale, (
        "the refusal must write nothing: the stored record stays exactly as the "
        "author left it so `--finding -` can re-bind it deliberately"
    )
    assert "design=bound" in stale_state, (
        "refusing must not silently unbind the value; the record is unchanged "
        f"and only the report about it is honest (state={stale_state!r})"
    )


#: The typed facts ONE architect turn returns, in the exact provider-neutral
#: shape `nw-solution-architect` answers under.  `authority_locator` is already
#: part of that declared payload; the value below names the section the role
#: says its record is about, which is the section the step must publish.
ROLE_TURN_FACTS = {
    "targets": [{"path": "src/widget.py", "decision": "EXTEND"}],
    "paradigm": "object_oriented",
    "decisions": ["Keep color validation at Widget construction."],
    "oracle": "tests/test_widget.py::test_selected_color",
    "acceptance_supports": [],
    "verification": [["pytest", "-q", "tests/test_widget.py"]],
    "oracle_verification_index": 0,
    "authority_locator": f"{REPOSITORY_DESTINATION}#Widget color",
}

ROLE_TURN_FINDING = (
    "the previously bound facts named no architecture authority section, so "
    "re-author them for this value"
)


def _design_turn(
    root: Path,
    environment: dict[str, str],
    tmp_path: Path,
    facts: dict | None,
    *,
    label: str,
    value: int = 1,
) -> tuple[int, str, str, Path]:
    """One REAL architect turn through `des design --value N --finding -`.

    The controlled provider answers the closed typed-facts envelope the solution
    architect's own schema declares -- never a Markdown document and never the
    closed v1 manifest -- because the section this scenario is about must be
    derivable from those typed facts alone.  The returned log path lets a caller
    prove a turn was, or was not, bought.
    """
    results, turns, counter = (
        tmp_path / f"{label}-answers.json",
        tmp_path / f"{label}-turns.json",
        tmp_path / f"{label}-counter",
    )
    counter.unlink(missing_ok=True)
    results.write_text(
        json.dumps(
            [
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": (
                            "resolved this value's consumed design facts from the "
                            "existing architecture and code"
                        ),
                        "design_facts": facts,
                    }
                }
            ]
        )
    )
    provider_environment = fake_provider.environment(
        root,
        launcher_dir=tmp_path / f"{label}-bin",
        results=results,
        log=turns,
        counter=counter,
        package_parent=PACKAGE_PARENT,
    )
    code, out, err = run_cli_in_process(
        ["design", "--repo-root", str(root), "--value", str(value), "--finding", "-"],
        cwd=root,
        env=hermetic_environment(
            provider_environment | {"HOME": environment["HOME"]},
            tmp_path / f"{label}-claude-config",
        ),
        stdin_text=ROLE_TURN_FINDING,
        catch_all=True,
    )
    return code, out, err, turns


def _mismatched_repository(
    tmp_path: Path, environment: dict[str, str]
) -> tuple[Path, Path]:
    """A second real checkout whose configured destination the role disagrees with."""
    root = base_repository(tmp_path / "contract-gap")
    (root / ".nwave").mkdir()
    (root / ".nwave" / "config.json").write_text(
        json.dumps(
            {"documents": {"design": {"destination": str(REPOSITORY_DESTINATION)}}}
        )
    )
    workspace = tmp_path / "contract-gap-work"
    workspace.mkdir()
    _bootstrap_value(root, environment, workspace)
    return root, workspace


def test_the_design_turn_publishes_the_section_its_record_names(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    """A role turn binds `design=bound` only over a section it actually published.

    The closed-document path already produces two matching projections.  The
    ROLE-TURN path -- `des design --value N --finding -`, the one the
    orchestrator uses to author or correct a value's facts from a real architect
    turn -- binds typed facts whose `authority_locator` names a section, while
    nothing has ever written that section.  The record therefore names a
    document that does not carry it, which is exactly the disagreement the
    replay arm above refuses as `DesignAuthorityUnlocatable`: today a role turn
    manufactures that stale state on its very first success.

    So this scenario measures the whole constructive chain through the real
    public driving port:

    * the named document gains the declared heading and a `git status` diff, so
      the bytes a human reads really moved;
    * the Success terminal carries the same DOCUMENT / DOCUMENT-SHA256 rows the
      closed-document path prints, measured against the bytes on disk;
    * an immediately following `des design --value N` confirms the record
      instead of refusing `DesignAuthorityUnlocatable`, which is the falsifier
      for "a value was bound over a section nobody wrote";
    * and when the returned facts cannot be rendered into the configured
      document -- the role names one destination, the step is configured with
      another -- the command REFUSES, naming both sides of that role/step
      contract gap, binds nothing and writes nothing.
    """
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    authority = _track_authority(root, UNRELATED_AUTHORITY_PREFIX)
    before_state = _design_state(root, environment)
    expected_locator = f"{REPOSITORY_DESTINATION}#Widget color"

    code, out, err, turns = _design_turn(
        root, environment, tmp_path, ROLE_TURN_FACTS, label="role"
    )
    rows = _terminal(out, err)
    published = authority.read_bytes()
    status = git(root, "status", "--porcelain")
    after_state = _design_state(root, environment)

    assert code == 0 and rows.get("DELIVERY-OUTCOME") == "Success", (
        "an accepted architect turn whose typed facts name a configured section "
        "must complete through `des design --value 1 --finding -` "
        f"(stdout={out!r}, stderr={err!r})"
    )
    assert turns.exists(), (
        "the scenario must measure a REAL role turn; a run that bought none is "
        "not the authoring path this observation is about"
    )
    assert b"\n## Widget color\n" in b"\n" + published, (
        "the configured document must now carry the H2 the role's own "
        "authority_locator names, each on its own line; a value may not bind to "
        f"a heading no document begins (document={published!r})"
    )
    assert published.startswith(UNRELATED_AUTHORITY_PREFIX), (
        "publishing the role's section must preserve every byte of the tracked "
        "human prefix; the document is human-owned outside this one H2"
    )
    missing_rendered_facts = {
        fact
        for fact in (
            ROLE_TURN_FACTS["paradigm"],
            ROLE_TURN_FACTS["decisions"][0],
            ROLE_TURN_FACTS["oracle"],
            ROLE_TURN_FACTS["targets"][0]["path"],
            ROLE_TURN_FACTS["targets"][0]["decision"],
            " ".join(ROLE_TURN_FACTS["verification"][0]),
        )
        if fact not in published.decode()
    }
    assert not missing_rendered_facts, (
        "the published section must be rendered from the returned typed facts "
        "and must retain every one of them, so the human authority and the "
        "bound facts are two projections of one turn; the document omitted "
        f"{sorted(missing_rendered_facts)!r}"
    )
    assert str(REPOSITORY_DESTINATION) in status, (
        "the named document must show a diff in `git status`; a publication no "
        f"version-control observation can see is not a durable one (status={status!r})"
    )
    assert rows.get("DOCUMENT") == expected_locator, (
        "the Success terminal must name the section this turn published, in the "
        "same `<document>#<heading>` form the closed-document path prints, not "
        f"{rows.get('DOCUMENT')!r}"
    )
    assert rows.get("DOCUMENT-SHA256") == hashlib.sha256(published).hexdigest(), (
        "DOCUMENT-SHA256 must measure the bytes now on disk, so a caller can "
        "read from the terminal alone that this turn produced document bytes"
    )
    assert_state_delta(
        before={
            "configured_authority": False,
            "design_state": "design=bound" in before_state,
        },
        after={
            "configured_authority": b"## Widget color" in published,
            "design_state": "design=bound" in after_state,
        },
        universe={"configured_authority", "design_state"},
        expected={
            "configured_authority": set_to(True),
            "design_state": set_to(True),
        },
    )

    replay_code, replay_out, replay_err, replay_turns = _replay_design(
        root, environment, tmp_path, label="after-role-turn"
    )
    replay_rows = _terminal(replay_out, replay_err)

    assert replay_rows.get("WHAT") != "DesignAuthorityUnlocatable", (
        "the value must not have been bound over a section nobody wrote; a role "
        "turn that leaves the very next replay refusing its own record has "
        f"recorded a binding the document does not carry (stdout={replay_out!r}, "
        f"stderr={replay_err!r})"
    )
    assert replay_code == 0 and replay_rows.get("DELIVERY-OUTCOME") == "Success", (
        "the immediately following `des design --value 1` must confirm the "
        "record the previous turn published, at zero cost "
        f"(stdout={replay_out!r}, stderr={replay_err!r})"
    )
    assert not replay_turns.exists(), (
        "confirming a record the document resolves must buy no architect turn"
    )

    gap_root, gap_workspace = _mismatched_repository(tmp_path, environment)
    gap_handover_before = (gap_root / HANDOVER).read_bytes()
    gap_facts = {
        **ROLE_TURN_FACTS,
        "authority_locator": "docs/product/architecture/somewhere-else.md#Widget color",
    }

    gap_code, gap_out, gap_err, _gap_turns = _design_turn(
        gap_root, environment, gap_workspace, gap_facts, label="gap"
    )
    gap_rows = _terminal(gap_out, gap_err)
    gap_transcript = _words(gap_out + "\n" + gap_err)
    gap_state = _design_state(gap_root, environment)

    assert gap_code != 0 and gap_rows.get("DELIVERY-OUTCOME") == "Refusal", (
        "facts that cannot be rendered into the configured document must refuse "
        "through the public terminal, never bind "
        f"(stdout={gap_out!r}, stderr={gap_err!r})"
    )
    assert gap_rows.get("WHAT") == "DesignFactsUnpublishable", (
        "the refusal must name the role/step contract gap under its own word, "
        f"not {gap_rows.get('WHAT')!r}; the document is fine and the facts are "
        "well-formed -- the two sides simply name different destinations"
    )
    missing_gap_observations = {
        observation
        for observation in (
            gap_facts["authority_locator"],
            str(REPOSITORY_DESTINATION),
            "documents.design.destination",
        )
        if observation not in gap_transcript
    }
    assert not missing_gap_observations, (
        "the refusal must name the locator the role declared, the configured "
        "documents.design.destination it disagrees with, and the repair; the "
        f"terminal omitted {sorted(missing_gap_observations)!r} "
        f"(stdout={gap_out!r}, stderr={gap_err!r})"
    )
    assert not (gap_root / REPOSITORY_DESTINATION).exists(), (
        "a contract-gap refusal must write no authority bytes at all"
    )
    assert (gap_root / HANDOVER).read_bytes() == gap_handover_before, (
        "a contract-gap refusal must leave the handover byte-identical, so the "
        "next call re-elicits DESIGN instead of resuming an unpublished binding"
    )
    assert "design=bound" not in gap_state, (
        "a value whose section was never published must stay unbound "
        f"(state={gap_state!r})"
    )


# --- shared feature DESIGN: one section per Request beside the value sections ---

SHARED_MANIFEST = {
    **json.loads(json.dumps(MANIFEST)),
    "authority": {"heading": "Shared feature DESIGN constructor"},
    "purpose": "Persist the design shared by every value of one Request once.",
    "constraints": ["Value sections carry only deltas."],
    "oracle": "tests/test_shared.py::test_shared_design",
    "verification": [["pytest", "-q", "tests/test_shared.py"]],
}
SHARED_HEADING = SHARED_MANIFEST["authority"]["heading"]
FEATURE_FLAGS = ("--feature", "shared-widget")


def _shared(
    root: Path,
    environment: dict[str, str],
    manifest: dict,
    *extra: str,
    stdin: str | None = None,
) -> tuple[int, str, str]:
    return run_cli_in_process(
        ["design", "--repo-root", str(root), "--shared", *extra, "--input", "-"],
        cwd=root,
        env=environment,
        stdin_text=json.dumps(manifest) if stdin is None else stdin,
        catch_all=True,
    )


def _section(document: str, heading: str) -> str:
    start = document.index(f"## {heading}\n")
    following = document.find("\n## ", start + 1)
    return document[start : None if following < 0 else following]


def _bound_value_locator(root: Path) -> str | None:
    """The persisted locator of value 1's bound DESIGN section, if any."""
    values = json.loads((root / HANDOVER).read_text()).get("values", [])
    authority = values[0].get("authority") if values else None
    return authority.get("authority_locator") if authority else None


def _bound_document(root: Path) -> Path | None:
    """The document the handover actually binds (scope-resolved, not assumed)."""
    locator = _bound_value_locator(root)
    return None if locator is None else root / locator.partition("#")[0]


def _bytes_of(root: Path) -> dict[str, bytes | None]:
    authority = _bound_document(root)
    return {
        "document": (
            authority.read_bytes()
            if authority is not None and authority.exists()
            else None
        ),
        "handover": (root / HANDOVER).read_bytes(),
    }


def _feature_repository(design_repository, tmp_path: Path):
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path, scope_flags=FEATURE_FLAGS)
    code, out, err = _design(root, environment, MANIFEST)
    assert code == 0, f"value 1 must bind first (stdout={out!r}, stderr={err!r})"
    return root, environment


def test_shared_feature_design_is_constructed_once_and_its_change_is_visible(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    root, environment = _feature_repository(design_repository, tmp_path)
    document_path = _bound_document(root)
    assert document_path is not None and document_path.exists(), (
        "value 1's bound locator must name the scope-resolved document"
    )
    value_section = _section(document_path.read_text(), "Widget color")
    raw_before = (root / HANDOVER).read_bytes()

    code, out, err = _shared(root, environment, SHARED_MANIFEST)
    rows = _terminal(out, err)
    assert code == 0 and rows.get("SHARED") == "bound", (
        "`des design --shared --input -` must bind the shared section on a "
        f"feature-scoped handover (code={code}, stdout={out!r}, stderr={err!r})"
    )
    expected_locator = (
        f"{_bound_value_locator(root).partition('#')[0]}#{SHARED_HEADING}"
    )
    assert rows.get("AUTHORITY") == expected_locator
    document = document_path.read_text()
    shared_section = _section(document, SHARED_HEADING)
    assert (
        "Persist the design shared by every value of one Request once."
        in (shared_section)
        and "- Value sections carry only deltas." in shared_section
    ), "the generated shared section must render the manifest fields"
    assert (
        rows.get("SECTION-SHA256")
        == hashlib.sha256(shared_section.encode()).hexdigest()
    ), "SECTION-SHA256 must digest the section bytes in the document"
    assert _section(document, "Widget color") == value_section, (
        "the value section must be preserved byte-for-byte beside the shared one"
    )
    bound = json.loads((root / HANDOVER).read_text())
    assert bound["shared_design"]["authority_locator"] == expected_locator
    assert bound["shared_design"]["section_sha256"] == rows["SECTION-SHA256"]
    assert (root / HANDOVER).read_bytes() != raw_before

    # identical rebind: stable no-op
    settled = _bytes_of(root)
    code, out, err = _shared(root, environment, SHARED_MANIFEST)
    rows_again = _terminal(out, err)
    assert code == 0 and rows_again.get("SHARED") == "unchanged", out + err
    assert _bytes_of(root) == settled, "an identical rebind must change no byte"

    # divergent without explicit replacement refuses
    changed = json.loads(json.dumps(SHARED_MANIFEST))
    changed["constraints"] = ["Value sections carry only deltas.", "Changed."]
    code, out, err = _shared(root, environment, changed)
    assert code != 0 and _terminal(out, err).get("WHAT") == "DesignAuthorityDrift"
    assert _bytes_of(root) == settled

    # explicit replacement makes the change visible in the handover raw bytes
    code, out, err = _shared(root, environment, changed, "--replace-current")
    rows_new = _terminal(out, err)
    assert code == 0 and rows_new.get("SHARED") == "replaced", out + err
    assert rows_new["SECTION-SHA256"] != rows["SECTION-SHA256"]
    after = _bytes_of(root)
    assert after["handover"] != settled["handover"], (
        "a semantic change must change handover bytes so old evidence is historical"
    )
    new_document = document_path.read_text()
    assert "- Changed." in _section(new_document, SHARED_HEADING)
    assert _section(new_document, "Widget color") == value_section


@pytest.mark.parametrize(
    ("case", "arguments"),
    [
        ("intent missing", ["--input", "-"]),
        ("both intents", ["--value", "1", "--shared", "--input", "-"]),
        ("shared with finding", ["--shared", "--input", "-", "--finding", "x"]),
        ("shared with competence", ["--shared", "--input", "-", "--competence", "x"]),
        ("shared without input", ["--shared"]),
    ],
)
def test_shared_intent_must_be_explicit_and_exclusive_without_mutation(
    design_repository, tmp_path: Path, case: str, arguments: list[str]
) -> None:
    root, environment = _feature_repository(design_repository, tmp_path)
    before = _bytes_of(root)
    code, out, err = run_cli_in_process(
        ["design", "--repo-root", str(root), *arguments],
        cwd=root,
        env=environment,
        stdin_text=json.dumps(SHARED_MANIFEST),
        catch_all=True,
    )
    assert code != 0, f"{case}: invalid invocation must fail (out={out!r}, err={err!r})"
    assert _bytes_of(root) == before, f"{case}: refusal must not mutate"


def test_shared_and_value_headings_can_never_collide_in_either_direction(
    design_repository, tmp_path: Path
) -> None:
    root, environment = _feature_repository(design_repository, tmp_path)
    before = _bytes_of(root)
    owned = json.loads(json.dumps(SHARED_MANIFEST))
    owned["authority"]["heading"] = "Widget color"
    code, out, err = _shared(root, environment, owned)
    assert (
        code != 0 and _terminal(out, err).get("WHAT") == "DesignAuthorityHeadingOwned"
    )
    assert _bytes_of(root) == before

    assert _shared(root, environment, SHARED_MANIFEST)[0] == 0
    bound = _bytes_of(root)
    stolen = json.loads(json.dumps(MANIFEST))
    stolen["authority"]["heading"] = SHARED_HEADING
    code, out, err = _design(root, environment, stolen, value=1, replace_current=True)
    assert (
        code != 0 and _terminal(out, err).get("WHAT") == "DesignAuthorityHeadingOwned"
    )
    assert _bytes_of(root) == bound


def test_malformed_shared_input_refuses_without_mutation(
    design_repository, tmp_path: Path
) -> None:
    root, environment = _feature_repository(design_repository, tmp_path)
    before = _bytes_of(root)
    incomplete = {k: v for k, v in SHARED_MANIFEST.items() if k != "reuse_analysis"}
    for stdin in (json.dumps(incomplete), "{not json"):
        code, out, err = _shared(root, environment, {}, stdin=stdin)
        assert code != 0 and _terminal(out, err).get("DELIVERY-OUTCOME") == "Refusal"
        assert _bytes_of(root) == before


def test_shared_design_on_scopeless_legacy_handover_never_falls_back_to_project(
    design_repository, tmp_path: Path
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path, scope_flags=FEATURE_FLAGS)
    payload = json.loads((root / HANDOVER).read_text())
    del payload["scope"]
    (root / HANDOVER).write_bytes(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    )
    before = _bytes_of(root)
    code, out, err = _shared(root, environment, SHARED_MANIFEST)
    assert (
        code != 0 and _terminal(out, err).get("WHAT") == "SharedDesignScopeImplicit"
    ), f"a scope-less handover must refuse, not default (out={out!r}, err={err!r})"
    assert _bytes_of(root) == before
    assert not (root / GLOBAL_DESTINATION).exists()


# --- shared binding: boundary controls (preservation, malformed, legacy, currentness) ---

SECOND_MANIFEST = {
    **json.loads(json.dumps(MANIFEST)),
    "authority": {"heading": "Widget size"},
    "purpose": "Expose the selected widget size.",
}


def _shared_binding(root: Path) -> object:
    return json.loads((root / HANDOVER).read_text()).get("shared_design")


def _distill_all(root: Path, environment: dict[str, str], labels: tuple[str, ...]):
    """The currently supported complete DISTILL input, one entry per value."""
    payload = {
        "schema_version": 2,
        "values": [
            {
                "observation": observation(label),
                "acceptance_obligations": [
                    {
                        "id": f"observe-{index}",
                        "stimulus": "Run the public widget command.",
                        "expected": "The selected value is reported.",
                    }
                ],
                "oracle": f"tests/acceptance/test_widget.py::test_value_{index}",
                "acceptance_supports": [],
                "verification": [
                    [
                        "pytest",
                        "-q",
                        f"tests/acceptance/test_widget.py::test_value_{index}",
                    ]
                ],
                "oracle_verification_index": 0,
            }
            for index, label in enumerate(labels)
        ],
    }
    return run_cli_in_process(
        ["distill", "--repo-root", str(root), "--input", "-"],
        cwd=root,
        env=environment,
        stdin_text=json.dumps(payload),
        catch_all=True,
    )


def test_shared_binding_survives_ordinary_design_and_distill_writes_unchanged(
    design_repository, tmp_path: Path
) -> None:
    root, environment = design_repository
    _bootstrap_value(
        root,
        environment,
        tmp_path,
        "widget color",
        "widget size",
        scope_flags=FEATURE_FLAGS,
    )
    assert _design(root, environment, MANIFEST)[0] == 0
    code, out, err = _shared(root, environment, SHARED_MANIFEST)
    assert code == 0 and _terminal(out, err).get("SHARED") == "bound", out + err
    bound = _shared_binding(root)
    assert bound is not None, "the shared binding must be persisted before writes"

    code, out, err = _design(root, environment, SECOND_MANIFEST, value=2)
    assert code == 0, f"ordinary value DESIGN must still succeed: {out}{err}"
    assert _shared_binding(root) == bound, (
        "an ordinary value DESIGN write must carry shared_design forward unchanged"
    )

    code, out, err = _distill_all(root, environment, ("widget color", "widget size"))
    assert code == 0, f"ordinary DISTILL write must still succeed: {out}{err}"
    assert _shared_binding(root) == bound, (
        "a DISTILL acceptance write must carry shared_design forward unchanged"
    )
    state_code, state_out, state_err = run_cli_in_process(
        ["state", "--repo-root", str(root)], cwd=root, env=environment, catch_all=True
    )
    settled = (root / HANDOVER).read_bytes()
    assert state_code == 0, state_out + state_err
    assert (root / HANDOVER).read_bytes() == settled
    assert _shared_binding(root) == bound, "a round-trip read must retain the binding"


def _corrupt_shared(payload: dict, case: str) -> None:
    document = payload["values"][0]["authority"]["authority_locator"].partition("#")[0]
    shared = payload["shared_design"]
    if case == "missing scope":
        del payload["scope"]
    elif case == "extra key":
        shared["extra"] = 1
    elif case == "missing key":
        del shared["section_sha256"]
    elif case == "missing semantic digest":
        del shared["semantic_sha256"]
    elif case == "non-hex semantic digest":
        shared["semantic_sha256"] = "z" * 64
    elif case == "short semantic digest":
        shared["semantic_sha256"] = "ab"
    elif case == "non-hex digest":
        shared["section_sha256"] = "z" * 64
    elif case == "short digest":
        shared["section_sha256"] = "ab"
    elif case == "invalid locator":
        shared["authority_locator"] = "no-hash-separator"
        shared["design"]["authority_locator"] = "no-hash-separator"
    elif case == "top locator differs from design locator":
        shared["authority_locator"] = f"{document}#Other heading"
    elif case == "locator equals bound value locator":
        value_locator = payload["values"][0]["authority"]["authority_locator"]
        shared["authority_locator"] = value_locator
        shared["design"]["authority_locator"] = value_locator
    elif case == "design projection invalid":
        del shared["design"]["oracle"]
    elif case == "not an object":
        payload["shared_design"] = "bound"
    elif case == "feature_id instead of scope":
        payload["feature_id"] = "shared-widget"
        del payload["scope"]
    else:  # pragma: no cover
        raise AssertionError(case)


@pytest.mark.parametrize(
    "case",
    [
        "missing scope",
        "extra key",
        "missing key",
        "non-hex digest",
        "short digest",
        "missing semantic digest",
        "non-hex semantic digest",
        "short semantic digest",
        "invalid locator",
        "top locator differs from design locator",
        "locator equals bound value locator",
        "design projection invalid",
        "not an object",
        "feature_id instead of scope",
    ],
)
def test_malformed_persisted_shared_binding_is_refused_without_authoritative_change(
    design_repository, tmp_path: Path, case: str
) -> None:
    root, environment = _feature_repository(design_repository, tmp_path)
    code, out, err = _shared(root, environment, SHARED_MANIFEST)
    assert code == 0 and _terminal(out, err).get("SHARED") == "bound", (
        f"a constructor-produced artifact is required for fault injection: {out}{err}"
    )
    payload = json.loads((root / HANDOVER).read_text())
    _corrupt_shared(payload, case)
    (root / HANDOVER).write_bytes(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    )
    before = _bytes_of(root)

    for arguments in (["state", "--repo-root", str(root)],):
        code, out, err = run_cli_in_process(
            arguments, cwd=root, env=environment, catch_all=True
        )
        assert code != 0 and _terminal(out, err).get("WHAT") == "HandoverMalformed", (
            f"{case}: persisted shared data must be HandoverMalformed "
            f"(out={out!r}, err={err!r})"
        )
    code, out, err = _shared(root, environment, SHARED_MANIFEST, *FEATURE_FLAGS)
    assert code != 0 and _terminal(out, err).get("WHAT") == "HandoverMalformed", (
        f"{case}: a rebind over malformed data must refuse (out={out!r}, err={err!r})"
    )
    assert _bytes_of(root) == before, f"{case}: no authoritative byte may change"


def _reordered(value: object) -> object:
    if isinstance(value, dict):
        return {key: _reordered(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [_reordered(item) for item in value]
    return value


def test_different_argv_boundaries_are_never_silently_ignored_by_shared_binding(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    root, environment = _feature_repository(design_repository, tmp_path)
    first = json.loads(json.dumps(SHARED_MANIFEST))
    first["verification"] = [["/usr/bin/printf", "%s %s", "A", "B"]]
    second = json.loads(json.dumps(first))
    second["verification"] = [["/usr/bin/printf", "%s", "%s A", "B"]]

    code, out, err = _shared(root, environment, first)
    rows_a = _terminal(out, err)
    assert code == 0 and rows_a.get("SHARED") == "bound", out + err
    semantic_a = rows_a.get("SEMANTIC-SHA256", "")
    assert re.fullmatch(r"[0-9a-f]{64}", semantic_a), (
        "the terminal must expose SEMANTIC-SHA256 as 64 lowercase hex "
        f"(got {semantic_a!r}); it identifies the complete constructor input"
    )
    bound = json.loads((root / HANDOVER).read_text())["shared_design"]
    assert set(bound) == {
        "authority_locator",
        "section_sha256",
        "semantic_sha256",
        "design",
    }, f"exact shared metadata keys required, got {sorted(bound)}"
    assert bound["semantic_sha256"] == semantic_a
    settled = _bytes_of(root)

    # JSON key order and insignificant whitespace normalize away: no-op.
    noisy = json.dumps(_reordered(first), indent=4, ensure_ascii=False)
    code, out, err = _shared(root, environment, first, stdin=noisy)
    rows_same = _terminal(out, err)
    assert code == 0 and rows_same.get("SHARED") == "unchanged", out + err
    assert rows_same.get("SEMANTIC-SHA256") == semantic_a
    assert _bytes_of(root) == settled, "an equivalent manifest must change no byte"

    # Different argv boundaries: different semantics -> refuse.
    code, out, err = _shared(root, environment, second)
    assert code != 0 and _terminal(out, err).get("WHAT") == "DesignAuthorityDrift", (
        "a manifest whose argv boundaries differ must not be treated as a no-op "
        f"regardless of the Markdown projection (out={out!r}, err={err!r}); "
        "compare semantic_sha256, never section equality alone"
    )
    assert _bytes_of(root) == settled

    code, out, err = _shared(root, environment, second, "--replace-current")
    rows_b = _terminal(out, err)
    assert code == 0 and rows_b.get("SHARED") == "replaced", out + err
    assert rows_b["SEMANTIC-SHA256"] != semantic_a
    assert rows_b["SECTION-SHA256"] != rows_a["SECTION-SHA256"], (
        "the fenced shell rendering must preserve the distinct argv boundaries "
        "for human readers as well as semantic_sha256 preserving them mechanically"
    )
    after = _bytes_of(root)
    assert after["document"] != settled["document"], (
        "a replacement must update the fenced argv rendering with the new boundaries"
    )
    assert after["handover"] != settled["handover"], (
        "semantic replacement must change handover raw so old evidence is historical"
    )
    assert (
        json.loads(after["handover"])["shared_design"]["semantic_sha256"]
        == (rows_b["SEMANTIC-SHA256"])
    )


@pytest.mark.parametrize("scoped", [True, False])
def test_legacy_handover_without_shared_data_reads_with_exact_bytes(
    design_repository, tmp_path: Path, scoped: bool
) -> None:
    root, environment = _feature_repository(design_repository, tmp_path)
    payload = json.loads((root / HANDOVER).read_text())
    assert "shared_design" not in payload, "no-shared bytes must omit the key"
    if not scoped:
        del payload["scope"]
        (root / HANDOVER).write_bytes(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        )
    before = _bytes_of(root)
    code, out, err = run_cli_in_process(
        ["state", "--repo-root", str(root)], cwd=root, env=environment, catch_all=True
    )
    assert code == 0, f"legacy reads keep their behavior: {out}{err}"
    assert _bytes_of(root) == before, "reading legacy must never rewrite it"
    if not scoped:
        code, out, err = _shared(root, environment, SHARED_MANIFEST)
        assert code != 0 and _terminal(out, err).get("WHAT") == (
            "SharedDesignScopeImplicit"
        )
        assert _bytes_of(root) == before


def test_previous_proof_is_historical_after_shared_change_and_current_after_identical_rebind(
    tmp_path: Path,
) -> None:
    from tests.des.acceptance.steps_for_the_orchestrator import conftest as orchestrator
    from tests.des.acceptance.steps_for_the_orchestrator.test_verify_and_integrate_close_the_request import (
        ORACLE,
        RED_ORACLE,
        REQUEST,
        SUPPORT,
        TARGET,
        design_facts,
        verdict,
    )

    root = base_repository(tmp_path / "root")
    turns = tmp_path / "model-log.json"
    step = orchestrator.stepper(root, tmp_path, turns)
    environment = {**os.environ}

    def state() -> dict[str, str]:
        code, out, err = step("state", "--repo-root", str(root))
        assert code == 0, out + err
        return orchestrator.block(out, err)

    assert (
        step(
            "po",
            "--feature",
            "shared-widget",
            "--repo-root",
            str(root),
            answers=[accepted_values("A")],
            stdin=REQUEST,
        )[0]
        == 0
    )
    assert (
        step(
            "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
        )[0]
        == 0
    )
    code, out, err = step(
        "oracle",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[
            {
                "structured_output": {"outcome": "accepted", "diagnostic": "oracle"},
                "writes": {ORACLE: RED_ORACLE, SUPPORT: "MARKER = 1\n"},
            },
            verdict("the oracle set is admissible"),
        ],
    )
    assert code == 0, out + err
    code, out, err = step(
        "craft",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[
            {
                "structured_output": {"outcome": "accepted", "diagnostic": "crafted"},
                "writes": {TARGET: "VALUE = 1\n"},
            }
        ],
    )
    assert code == 0, out + err
    code, out, err = step("verify", "--repo-root", str(root), answers=[])
    assert code == 0, out + err
    candidate = orchestrator.block(out, err)["CANDIDATE"]

    code, out, err = _shared(root, environment, SHARED_MANIFEST)
    assert code == 0 and _terminal(out, err).get("SHARED") == "bound", out + err
    # the first shared bind is itself a semantic change of the graph
    assert state()["CANDIDATE"] == f"{candidate} bytes moved"

    code, out, err = step("verify", "--repo-root", str(root), answers=[])
    assert code == 0, out + err
    candidate = orchestrator.block(out, err)["CANDIDATE"]
    assert state()["CANDIDATE"] == f"{candidate} recorded"

    code, out, err = _shared(root, environment, SHARED_MANIFEST)
    assert code == 0 and _terminal(out, err).get("SHARED") == "unchanged", out + err
    assert state()["CANDIDATE"] == f"{candidate} recorded", (
        "an identical shared rebind must leave the proof current"
    )

    changed = json.loads(json.dumps(SHARED_MANIFEST))
    changed["constraints"] = ["Value sections carry only deltas.", "Changed."]
    code, out, err = _shared(root, environment, changed, "--replace-current")
    assert code == 0 and _terminal(out, err).get("SHARED") == "replaced", out + err
    assert state()["CANDIDATE"] == f"{candidate} bytes moved", (
        "a changed shared contract must make the earlier proof historical"
    )


# --- shared constructor: explicit scope, preservation, wrong-target replace, no provider ---


def _provider_watched(root: Path, environment: dict[str, str], tmp_path: Path):
    """An environment whose provider launcher logs every turn it is asked to buy."""
    results, turns = tmp_path / "watch-answers.json", tmp_path / "watch-turns.json"
    results.write_text("[]")
    provider_environment = fake_provider.environment(
        root,
        launcher_dir=tmp_path / "watch-bin",
        results=results,
        log=turns,
        counter=tmp_path / "watch-counter",
        package_parent=PACKAGE_PARENT,
    )
    watched = hermetic_environment(
        provider_environment | {"HOME": environment["HOME"]},
        tmp_path / "watch-claude-config",
    )
    return watched, turns


def _payload(root: Path) -> dict:
    return json.loads((root / HANDOVER).read_text())


def test_explicit_feature_constructs_scope_on_a_legacy_graph_and_changes_only_shared_and_scope(
    design_repository, tmp_path: Path
) -> None:
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path, scope_flags=FEATURE_FLAGS)
    assert _design(root, environment, MANIFEST)[0] == 0
    legacy = _payload(root)
    del legacy["scope"]
    (root / HANDOVER).write_bytes(
        json.dumps(legacy, ensure_ascii=False, separators=(",", ":")).encode()
    )
    watched, turns = _provider_watched(root, environment, tmp_path)

    code, out, err = _shared(root, watched, SHARED_MANIFEST, *FEATURE_FLAGS)
    rows = _terminal(out, err)
    assert code == 0 and rows.get("SHARED") == "bound", (
        "an explicit --feature must construct the scope key on a scope-less "
        f"legacy handover in the same write (stdout={out!r}, stderr={err!r})"
    )
    after = _payload(root)
    assert after.get("scope") is not None and "shared-widget" in json.dumps(
        after["scope"]
    ), "the constructed scope key must name the explicit feature"
    assert "shared_design" in after
    assert {k: v for k, v in after.items() if k not in ("scope", "shared_design")} == (
        legacy
    ), (
        "a shared bind may change only scope and shared_design; values, design "
        "facts, acceptance and selections must stay identical"
    )
    assert not turns.exists() or json.loads(turns.read_text()) == [], (
        "--shared must buy no provider turn; the turn log recorded one"
    )

    settled = _bytes_of(root)
    code, out, err = _shared(
        root, environment, SHARED_MANIFEST, "--feature", "other-feature"
    )
    assert code != 0 and _terminal(out, err).get("WHAT") == "FeatureScopeMismatch", (
        f"a different --feature must refuse (stdout={out!r}, stderr={err!r})"
    )
    assert _bytes_of(root) == settled, "a scope mismatch must change no byte"


def test_first_shared_bind_preserves_every_other_top_level_field(
    design_repository, tmp_path: Path
) -> None:
    root, environment = _feature_repository(design_repository, tmp_path)
    before = _payload(root)
    code, out, err = _shared(root, environment, SHARED_MANIFEST)
    assert code == 0, out + err
    after = _payload(root)
    assert {k: v for k, v in after.items() if k != "shared_design"} == before, (
        "the first bind must leave every top-level field except shared_design "
        "identical; only the shared writer may change it"
    )
    assert "shared_design" not in before and "shared_design" in after


def test_replace_current_without_a_binding_or_on_another_heading_preserves_bytes(
    design_repository, tmp_path: Path
) -> None:
    root, environment = _feature_repository(design_repository, tmp_path)
    before = _bytes_of(root)
    code, out, err = _shared(root, environment, SHARED_MANIFEST, "--replace-current")
    assert code != 0 and _terminal(out, err).get("DELIVERY-OUTCOME") == "Refusal", (
        "--replace-current requires a bound shared design; refuse, never bind "
        f"(stdout={out!r}, stderr={err!r})"
    )
    assert _bytes_of(root) == before, "an unbound replace must change no byte"

    assert _shared(root, environment, SHARED_MANIFEST)[0] == 0
    bound = _bytes_of(root)
    other = json.loads(json.dumps(SHARED_MANIFEST))
    other["authority"]["heading"] = "Another shared heading"
    for extra in (("--replace-current",), ()):
        code, out, err = _shared(root, environment, other, *extra)
        assert code != 0 and (
            _terminal(out, err).get("WHAT") == "DesignAuthorityIdentityMismatch"
        ), f"a different shared heading must refuse {extra} (out={out!r}, err={err!r})"
        assert _bytes_of(root) == bound, "a wrong-heading call must change no byte"


def test_shared_construction_buys_no_provider_turn(
    design_repository, tmp_path: Path
) -> None:
    root, environment = _feature_repository(design_repository, tmp_path)
    watched, turns = _provider_watched(root, environment, tmp_path)
    changed = json.loads(json.dumps(SHARED_MANIFEST))
    changed["constraints"] = ["Value sections carry only deltas.", "Changed."]
    for manifest, extra in (
        (SHARED_MANIFEST, ()),
        (SHARED_MANIFEST, ()),
        (changed, ("--replace-current",)),
    ):
        code, out, err = _shared(root, watched, manifest, *extra)
        assert code == 0, out + err
    assert not turns.exists() or json.loads(turns.read_text()) == [], (
        "--shared must never invoke a provider; the turn log is not empty"
    )


# --- shared boundary regressions: legacy encoding and self-contradicting oracle ---


def test_shared_bearing_handover_rejects_a_value_with_the_legacy_locator_encoding(
    design_repository, tmp_path: Path
) -> None:
    """A bound shared design admits only the current encoding: moving value 1's
    locator to the shared design must not be readable as a legacy variant."""
    root, environment = _feature_repository(design_repository, tmp_path)
    code, out, err = _shared(root, environment, SHARED_MANIFEST)
    assert code == 0 and _terminal(out, err).get("SHARED") == "bound", (
        f"a constructor-produced artifact is required: {out}{err}"
    )
    payload = json.loads((root / HANDOVER).read_text())
    locator = payload["values"][0]["authority"].pop("authority_locator")
    payload["shared_design"]["authority_locator"] = locator
    payload["shared_design"]["design"]["authority_locator"] = locator
    (root / HANDOVER).write_bytes(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    )
    before = (root / HANDOVER).read_bytes()
    document = root / locator.partition("#")[0]
    document_before = document.read_bytes()

    code, out, err = run_cli_in_process(
        ["state", "--repo-root", str(root)], cwd=root, env=environment, catch_all=True
    )
    assert code != 0 and _terminal(out, err).get("WHAT") == "HandoverMalformed", (
        f"legacy value encoding beside a shared design must be HandoverMalformed "
        f"(out={out!r}, err={err!r}); read shared-bearing bytes only in the current encoding"
    )
    code, out, err = _shared(root, environment, SHARED_MANIFEST, *FEATURE_FLAGS)
    assert code != 0 and _terminal(out, err).get("WHAT") == "HandoverMalformed", (
        f"a rebind over the legacy encoding must refuse (out={out!r}, err={err!r})"
    )
    assert (root / HANDOVER).read_bytes() == before, "no handover byte may change"
    assert document.read_bytes() == document_before, "no document byte may change"


@pytest.mark.parametrize("path", ["shared", "value"])
def test_design_manifest_whose_support_is_its_oracle_file_refuses_before_any_write(
    design_repository, tmp_path: Path, path: str
) -> None:
    """An acceptance support equal to the oracle's file is self-contradictory and
    must be refused before any document or handover byte is written."""
    root, environment = design_repository
    if path == "shared":
        root, environment = _feature_repository(design_repository, tmp_path)
        manifest = json.loads(json.dumps(SHARED_MANIFEST))
    else:
        _bootstrap_value(root, environment, tmp_path)
        manifest = json.loads(json.dumps(MANIFEST))
    manifest["oracle"] = "tests/x.py::t"
    manifest["acceptance_supports"] = ["tests/x.py"]
    handover_before = (root / HANDOVER).read_bytes()
    documents = {
        p: p.read_bytes() if p.exists() else None
        for p in (
            root / REPOSITORY_DESTINATION,
            root / GLOBAL_DESTINATION,
            *([_bound_document(root)] if _bound_document(root) else []),
        )
    }

    if path == "shared":
        code, out, err = _shared(root, environment, manifest)
    else:
        code, out, err = _design(root, environment, manifest)
    rows = _terminal(out, err)

    assert code != 0 and rows.get("DELIVERY-OUTCOME") == "Refusal", (
        f"{path}: an oracle file listed as its own support must refuse, not publish "
        f"then report a mixed projection (stdout={out!r}, stderr={err!r})"
    )
    assert (root / HANDOVER).read_bytes() == handover_before, "handover must not change"
    assert documents == {
        p: p.read_bytes() if p.exists() else None for p in documents
    }, "no design document may be written before validation completes"


def test_design_admits_repeated_argv_tokens_and_keeps_them(
    design_repository: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    """A token may repeat inside one argv; only a whole repeated argv is refused."""
    root, environment = design_repository
    _bootstrap_value(root, environment, tmp_path)
    manifest = json.loads(json.dumps(MANIFEST))
    manifest["verification"] = [["pytest", "-q", "-q", "tests/test_widget.py"]]

    code, out, err = _design(root, environment, manifest)

    assert code == 0, out + err
    stored = json.loads((root / HANDOVER).read_text())["values"][0]
    assert stored["authority"]["verification"] == manifest["verification"]

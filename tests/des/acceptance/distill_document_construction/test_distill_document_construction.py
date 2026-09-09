"""Public oracle for the provider-free DISTILL acceptance authority."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance.design_document_construction.test_design_document_construction import (
    MANIFEST,
)
from tests.des.acceptance.steps_for_the_orchestrator.conftest import base_repository

from des.application import handover
from des.application.delivery_steps import DeliverySteps
from des.application.handover import (
    AcceptanceObligation,
    bind_design_facts,
    read_handover,
)
from des.domain.delivery_disposition import Disposition
from des.ports.driven_ports.task_invocation_port import (
    DesignFacts,
    DesignTarget,
    ModelOutcome,
    ModelRun,
    TaskInvocationPort,
)


HANDOVER = Path(".nwave/des/handover.json")


def _discuss_payload() -> dict[str, object]:
    first = "A user selects a widget color."
    return {
        "schema_version": 1,
        "request": "Let a user choose a widget color.",
        "outcomes": ["A user can choose and verify a widget color."],
        "scope": {
            "in_scope": ["Widget color selection."],
            "out_of_scope": {
                "applicability": "not_applicable",
                "reason": "No exclusions are needed.",
                "items": [],
            },
        },
        "decisions": ["Keep selection in the Widget boundary."],
        "values": [
            {"observation": first, "dependencies": []},
            {
                "observation": "A user sees the selected widget color.",
                "dependencies": [first],
            },
        ],
    }


def _distill_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "values": [
            {
                "observation": "A user selects a widget color.",
                "acceptance_obligations": [
                    {
                        "id": "select-color",
                        "stimulus": "Choose blue in the public widget control.",
                        "expected": "The selected color is blue.",
                    }
                ],
                "oracle": "tests/acceptance/test_widget.py::test_selects_blue",
                "acceptance_supports": ["tests/support/widget_driver.py"],
            },
            {
                "observation": "A user sees the selected widget color.",
                "acceptance_obligations": [
                    {
                        "id": "see-color",
                        "stimulus": "Open the widget after choosing blue.",
                        "expected": "The visible widget color is blue.",
                    }
                ],
                "oracle": "tests/acceptance/test_widget.py::test_visible_color",
                "acceptance_supports": [],
            },
        ],
    }


def _call(
    root: Path,
    command: str,
    raw: str,
    *,
    value: int | None = None,
    **kwargs: object,
) -> tuple[int, str, str]:
    arguments = [command, "--repo-root", str(root)]
    if value is not None:
        arguments.extend(("--value", str(value)))
    arguments.extend(("--input", "-"))
    return run_cli_in_process(
        arguments,
        cwd=root,
        stdin_text=raw,
        catch_all=True,
        **kwargs,
    )


def _prepare(root: Path) -> dict[str, object]:
    code, out, err = _call(root, "discuss", json.dumps(_discuss_payload()))
    assert code == 0, out + err
    return _distill_payload()


def _stored(root: Path):
    value = read_handover((root / HANDOVER).read_bytes())
    assert not isinstance(value, handover.Blocked), value
    return value


def _headings(markdown: str) -> list[tuple[int, str]]:
    """Parse the public Markdown structure, normalizing heading content only."""
    headings = []
    for line in markdown.splitlines():
        match = re.fullmatch(r"(#{1,6})[ \t]+(.*)", line)
        if match is not None:
            headings.append((len(match.group(1)), " ".join(match.group(2).split())))
    return headings


def _prompt_json_value(prompt: str, key: str) -> object:
    """Read one machine-produced ``key: JSON-value`` line at the public boundary."""
    prefix = f"{key}: "
    values = [
        line.removeprefix(prefix)
        for line in prompt.splitlines()
        if line.startswith(prefix)
    ]
    assert len(values) == 1, f"expected exactly one {key!r} fact in craft prompt"
    return json.loads(values[0])


def test_public_distill_constructs_one_escaped_document_and_typed_handover_without_provider(
    tmp_path: Path,
) -> None:
    root = base_repository(tmp_path / "repository")
    supplied = _prepare(root)
    supplied["values"][0]["acceptance_obligations"][0]["stimulus"] = (  # type: ignore[index]
        "Choose | blue\n## injected heading"
    )
    code, out, err = _call(root, "distill", json.dumps(supplied), env={"PATH": ""})
    document = root / "docs/product/acceptance/brief.md"
    assert code == 0, out + err
    assert "NEXT: des craft --repo-root <root> --value 1" in out
    assert not (root / ".nwave/des/turns").exists(), "DISTILL must buy no provider turn"
    headings = _headings(document.read_text())
    assert headings == [
        (1, "Acceptance brief"),
        (2, "Request"),
        (2, "Value Observations"),
        (3, "A user selects a widget color."),
        (2, "Acceptance Obligations"),
        (2, "Oracle"),
        (2, "Supports"),
        (3, "A user sees the selected widget color."),
        (2, "Acceptance Obligations"),
        (2, "Oracle"),
        (2, "Supports"),
    ]
    assert (2, "injected heading") not in headings
    rendered = document.read_text()
    assert "Choose \\| blue<br>## injected heading" in rendered
    stored = _stored(root)
    assert stored.values[0].acceptance == (
        AcceptanceObligation(
            "select-color",
            "Choose | blue\n## injected heading",
            "The selected color is blue.",
        ),
    )
    assert (
        stored.values[0].acceptance_oracle
        == "tests/acceptance/test_widget.py::test_selects_blue"
    )
    assert stored.values[0].acceptance_supports == ("tests/support/widget_driver.py",)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        json.dumps({"schema_version": True, "values": []}),
        json.dumps({"schema_version": 1.0, "values": []}),
        json.dumps({"schema_version": 1, "values": [], "unknown": 1}),
        '{"schema_version":1,"values":[{"observation":"\\ud800","acceptance_obligations":[{"id":"x","stimulus":"x","expected":"x"}],"oracle":"tests/x.py","acceptance_supports":[]}]}',
    ],
)
def test_public_distill_refuses_closed_schema_empty_and_non_utf8_semantics_before_mutation(
    tmp_path: Path, raw: str
) -> None:
    root = base_repository(tmp_path / "repository")
    _prepare(root)
    before = (root / HANDOVER).read_bytes()
    code, out, err = _call(root, "distill", raw)
    assert code != 0 and "InvalidDistillDocument" in out + err
    assert (root / HANDOVER).read_bytes() == before
    assert not (root / "docs/product/acceptance/brief.md").exists()


def test_public_distill_empty_input_leaves_a_fresh_repository_without_artifacts(
    tmp_path: Path,
) -> None:
    root = base_repository(tmp_path / "repository")
    code, out, err = _call(root, "distill", "")
    assert code != 0 and "InvalidDistillDocument" in out + err
    assert not (root / HANDOVER).exists()
    assert not (root / "docs/product/acceptance/brief.md").exists()


def test_public_distill_honors_project_then_global_then_default_destination(
    tmp_path: Path, monkeypatch
) -> None:
    root = base_repository(tmp_path / "repository")
    _prepare(root)
    home = tmp_path / "home"
    (home / ".nwave").mkdir(parents=True)
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(home))
    (home / ".nwave/config.json").write_text(
        json.dumps({"documents": {"distill": {"destination": "docs/global.md"}}})
    )
    (root / ".nwave").mkdir(exist_ok=True)
    (root / ".nwave/config.json").write_text(
        json.dumps({"documents": {"distill": {"destination": "docs/project.md"}}})
    )
    assert _call(root, "distill", json.dumps(_distill_payload()))[0] == 0
    assert (root / "docs/project.md").is_file() and not (
        root / "docs/global.md"
    ).exists()
    other = base_repository(tmp_path / "global-only")
    _prepare(other)
    assert _call(other, "distill", json.dumps(_distill_payload()))[0] == 0
    assert (other / "docs/global.md").is_file()
    monkeypatch.delenv("NWAVE_AGENTS_HOME")
    default = base_repository(tmp_path / "default")
    _prepare(default)
    assert _call(default, "distill", json.dumps(_distill_payload()))[0] == 0
    assert (default / "docs/product/acceptance/brief.md").is_file()


def test_public_distill_retry_after_real_design_is_byte_identical_and_preserves_design_facts(
    tmp_path: Path,
) -> None:
    root = base_repository(tmp_path / "repository")
    raw = json.dumps(_prepare(root))
    assert _call(root, "distill", raw)[0] == 0
    code, out, err = _call(root, "design", json.dumps(MANIFEST), value=1)
    assert code == 0, out + err
    before = (
        (root / HANDOVER).read_bytes(),
        (root / "docs/product/acceptance/brief.md").read_bytes(),
    )
    assert _call(root, "distill", raw)[0] == 0
    assert before == (
        (root / HANDOVER).read_bytes(),
        (root / "docs/product/acceptance/brief.md").read_bytes(),
    )
    stored = _stored(root)
    assert isinstance(stored.values[0].authority, DesignFacts)
    assert stored.values[1].authority is None
    assert stored.values[0].acceptance[0].id == "select-color"


def test_distill_accepts_selected_graph_values_and_preserves_unselected_graph_and_authority(
    tmp_path: Path,
) -> None:
    """DISTILL selects known values; it never admits a rule that every value is required."""
    root = base_repository(tmp_path / "repository")
    supplied = _prepare(root)
    before = _stored(root)
    expected_graph = tuple(
        (value.observation, value.dependencies) for value in before.values
    )
    unselected_authority = DesignFacts(
        (DesignTarget("README.md", "EXTEND"),),
        "object_oriented",
        ("Keep the public behavior.",),
        "tests/des/acceptance/test_widget.py::test_design_default",
        (),
        (("true",),),
    )
    assert not isinstance(
        bind_design_facts(root, before, 2, unselected_authority), handover.Blocked
    )
    values = supplied["values"]
    assert isinstance(values, list)
    supplied["values"] = values[:1]
    assert _call(root, "distill", json.dumps(supplied))[0] == 0

    stored = _stored(root)
    assert (
        tuple((value.observation, value.dependencies) for value in stored.values)
        == expected_graph
    )
    assert stored.values[0].acceptance
    assert stored.values[1].acceptance == ()
    assert stored.values[1].authority == unselected_authority
    rendered = (root / "docs/product/acceptance/brief.md").read_text()
    assert "A user selects a widget color." in rendered
    assert "A user sees the selected widget color." not in rendered


def test_distill_refuses_unknown_graph_corrupt_handover_and_external_symlink_before_mutation(
    tmp_path: Path,
) -> None:
    root = base_repository(tmp_path / "repository")
    raw = json.dumps(_prepare(root))
    valid_handover = (root / HANDOVER).read_bytes()
    bad = _distill_payload()
    values = bad["values"]
    assert isinstance(values, list)
    values[0]["observation"] = "An observation outside the stored graph."
    code, out, err = _call(root, "distill", json.dumps(bad))
    assert code != 0 and "DistillHandoverConflict" in out + err
    assert not (root / "docs/product/acceptance/brief.md").exists()
    (root / HANDOVER).write_bytes(b"not json")
    code, out, err = _call(root, "distill", raw)
    assert code != 0 and "HandoverMalformed" in out + err
    assert (root / HANDOVER).read_bytes() == b"not json"
    # Restore a valid graph so this next refusal exercises the document publisher,
    # rather than merely repeating the corrupt-handover refusal above.
    (root / HANDOVER).write_bytes(valid_handover)
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n")
    destination = root / "docs/product/acceptance/brief.md"
    destination.parent.mkdir(parents=True)
    destination.symlink_to(outside)
    before_symlink_handover = (root / HANDOVER).read_bytes()
    code, out, err = _call(root, "distill", raw)
    assert code != 0 and "UnsafeDistillDestination" in out + err
    assert outside.read_text() == "outside\n"
    assert (root / HANDOVER).read_bytes() == before_symlink_handover


def test_distill_refuses_divergent_existing_document_without_rewriting_handover(
    tmp_path: Path,
) -> None:
    root = base_repository(tmp_path / "repository")
    raw = json.dumps(_prepare(root))
    assert _call(root, "distill", raw)[0] == 0
    document = root / "docs/product/acceptance/brief.md"
    document.write_text("conflicting human authority\n")
    before = (document.read_bytes(), (root / HANDOVER).read_bytes())
    code, out, err = _call(root, "distill", raw)
    assert code != 0 and "DistillAuthorityDrift" in out + err
    assert before == (document.read_bytes(), (root / HANDOVER).read_bytes())


def test_distill_refuses_conflicting_oracle_or_support_facts_before_document_mutation(
    tmp_path: Path,
) -> None:
    root = base_repository(tmp_path / "repository")
    supplied = _prepare(root)
    assert _call(root, "distill", json.dumps(supplied))[0] == 0
    values = supplied["values"]
    assert isinstance(values, list)
    values[0]["oracle"] = "tests/acceptance/test_widget.py::test_other_oracle"
    document = root / "docs/product/acceptance/brief.md"
    before = (document.read_bytes(), (root / HANDOVER).read_bytes())
    code, out, err = _call(root, "distill", json.dumps(supplied))
    assert code != 0 and "DistillHandoverConflict" in out + err
    assert before == (document.read_bytes(), (root / HANDOVER).read_bytes())


@pytest.mark.parametrize(
    "unsafe_oracle",
    (
        "/tmp/widget.test.ts::selectsBlue",
        "C:\\workspace\\widget.test.ts::selectsBlue",
        "../tests/widget.test.ts::selectsBlue",
        "tests/\x00widget.test.ts::selectsBlue",
    ),
)
def test_public_distill_locator_boundaries_are_contract_not_implementation_mirrors(
    tmp_path: Path, unsafe_oracle: str
) -> None:
    """The public CLI admits only safe repository-relative oracle locators."""
    root = base_repository(tmp_path / "repository")
    supplied = _prepare(root)
    values = supplied["values"]
    assert isinstance(values, list)
    values[0]["oracle"] = unsafe_oracle
    before = (root / HANDOVER).read_bytes()
    code, out, err = _call(root, "distill", json.dumps(supplied))
    assert code != 0 and "InvalidDistillDocument" in out + err
    assert (root / HANDOVER).read_bytes() == before
    assert not (root / "docs/product/acceptance/brief.md").exists()


def test_public_distill_accepts_safe_typescript_oracle_and_support_locators(
    tmp_path: Path,
) -> None:
    """Public CLI contract boundary: TypeScript locators need no Python-only exception."""
    root = base_repository(tmp_path / "repository")
    supplied = _prepare(root)
    values = supplied["values"]
    assert isinstance(values, list)
    values[0]["oracle"] = "web/src/test/acceptance/value.test.ts::selectsBlue"
    values[0]["acceptance_supports"] = ["web/src/test/support/widget_driver.ts"]
    code, out, err = _call(root, "distill", json.dumps(supplied))
    assert code == 0, out + err
    stored = _stored(root)
    assert (
        stored.values[0].acceptance_oracle
        == "web/src/test/acceptance/value.test.ts::selectsBlue"
    )
    assert stored.values[0].acceptance_supports == (
        "web/src/test/support/widget_driver.ts",
    )


def test_old_handover_reader_accepts_pre_distill_canonical_bytes() -> None:
    legacy = json.dumps(
        {
            "request": "Existing Request.",
            "values": [
                {
                    "observation": "Existing observation.",
                    "dependencies": [],
                    "authority": None,
                }
            ],
        },
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode()
    restored = read_handover(legacy)
    assert not isinstance(restored, handover.Blocked), restored
    assert restored.values[0].acceptance == ()


def test_public_distill_cas_loss_after_document_publication_is_indeterminate_and_preserves_winner(
    tmp_path: Path, monkeypatch
) -> None:
    root = base_repository(tmp_path / "repository")
    raw = json.dumps(_prepare(root))
    winner = (root / HANDOVER).read_bytes()

    def lose_after_publication(*_args: object, **_kwargs: object) -> handover.Blocked:
        return handover.Blocked(
            "HandoverDrift", "external winner", "inspect winner", refusal=True
        )

    monkeypatch.setattr(handover, "rewrite_handover", lose_after_publication)
    outcome = DeliverySteps().distill_document(root, raw)
    document = root / "docs/product/acceptance/brief.md"
    assert outcome.disposition is Disposition.Indeterminate
    assert outcome.failure is not None and outcome.failure.what == "HandoverDrift"
    assert outcome.facts == (
        "DOCUMENT: docs/product/acceptance/brief.md",
        f"DOCUMENT-SHA256: {hashlib.sha256(document.read_bytes()).hexdigest()}",
    )
    assert (root / HANDOVER).read_bytes() == winner


class _CapturingCraftPort(TaskInvocationPort):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def invoke(
        self, *, role_id: str, prompt: str, cwd: Path, **_kwargs: object
    ) -> ModelRun:
        self.calls.append((role_id, prompt))
        return ModelRun(ModelOutcome.Rejected, "captured boundary", 0, True)


@pytest.mark.parametrize(
    ("position", "expected_oracle", "expected_supports", "expected_obligations"),
    (
        (
            1,
            "tests/acceptance/test_widget.py::test_selects_blue",
            ["tests/support/widget_driver.py"],
            [
                {
                    "id": "select-color",
                    "stimulus": "Choose blue in the public widget control.",
                    "expected": "The selected color is blue.",
                }
            ],
        ),
        (
            2,
            "tests/acceptance/test_widget.py::test_visible_color",
            [],
            [
                {
                    "id": "see-color",
                    "stimulus": "Open the widget after choosing blue.",
                    "expected": "The visible widget color is blue.",
                }
            ],
        ),
    ),
)
def test_delivery_steps_craft_consumes_distill_typed_stimulus_expected_oracle_and_supports(
    tmp_path: Path,
    position: int,
    expected_oracle: str,
    expected_supports: list[str],
    expected_obligations: list[dict[str, str]],
) -> None:
    """Boundary capture proves provider input, including explicit empty supports."""
    root = base_repository(tmp_path / "repository")
    raw = json.dumps(_prepare(root))
    assert _call(root, "distill", raw)[0] == 0
    stored = _stored(root)
    facts = DesignFacts(
        (DesignTarget("README.md", "EXTEND"),),
        "object_oriented",
        ("Keep the public behavior.",),
        "tests/des/acceptance/test_widget.py::test_design_default",
        ("tests/support/design_default.py",),
        (("true",),),
    )
    assert not isinstance(
        bind_design_facts(root, stored, position, facts), handover.Blocked
    )
    port = _CapturingCraftPort()
    outcome = DeliverySteps(invoker=port).craft(root, position)
    assert outcome.disposition is Disposition.Refusal
    role, prompt = port.calls[-1]
    assert role == "nw-software-crafter"
    assert _prompt_json_value(prompt, "oracle") == expected_oracle
    assert _prompt_json_value(prompt, "acceptance_supports") == expected_supports
    assert _prompt_json_value(prompt, "acceptance_obligations") == expected_obligations

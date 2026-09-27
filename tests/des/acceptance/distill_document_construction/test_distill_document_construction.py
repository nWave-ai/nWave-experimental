"""Public oracle for the provider-free DISTILL acceptance authority."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance import fake_provider
from tests.des.acceptance.design_document_construction.test_design_document_construction import (
    MANIFEST,
)
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    PACKAGE_PARENT,
    base_repository,
    block,
    hermetic_environment,
    stepper,
)

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


def _declared(oracle: str) -> dict[str, object]:
    """The complete native verification a schema_version 2 value must declare."""
    path = oracle.split("::", maxsplit=1)[0]
    return {
        "verification": [[sys.executable, "-m", "pytest", path]],
        "oracle_verification_index": 0,
    }


def _distill_payload() -> dict[str, object]:
    return {
        "schema_version": 2,
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
                **_declared("tests/acceptance/test_widget.py::test_selects_blue"),
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
                **_declared("tests/acceptance/test_widget.py::test_visible_color"),
            },
        ],
    }


def _call(
    root: Path,
    command: str,
    raw: str,
    *,
    value: int | None = None,
    project: bool = False,
    replace_current: bool = False,
    shared: bool = False,
    scope: tuple[str, ...] = (),
    **kwargs: object,
) -> tuple[int, str, str]:
    arguments = [command, "--repo-root", str(root), *scope]
    if project:
        arguments.append("--project")
    if shared:
        arguments.append("--shared")
    if value is not None:
        arguments.extend(("--value", str(value)))
    if replace_current:
        arguments.append("--replace-current")
    arguments.extend(("--input", "-"))
    return run_cli_in_process(
        arguments,
        cwd=root,
        stdin_text=raw,
        catch_all=True,
        **kwargs,
    )


def _prepare(root: Path) -> dict[str, object]:
    code, out, err = _call(
        root, "discuss", json.dumps(_discuss_payload()), project=True
    )
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


def _v1_input() -> str:
    """The retired grammar, spelled as the historical NEW-input v1 shape."""
    value = {
        k: v
        for k, v in _distill_payload()["values"][0].items()  # type: ignore[index]
        if k not in ("verification", "oracle_verification_index")
    }
    return json.dumps({"schema_version": 1, "values": [value]})


def _v2_with(**changes: object) -> str:
    value = json.loads(json.dumps(_distill_payload()["values"][0]))  # type: ignore[index]
    for key, replacement in changes.items():
        if replacement is _MISSING:
            del value[key]
        else:
            value[key] = replacement
    return json.dumps({"schema_version": 2, "values": [value]})


_MISSING = object()
_PYTEST_ARGV = [sys.executable, "-m", "pytest", "tests/acceptance/test_widget.py"]


@pytest.mark.parametrize(
    "raw",
    [
        "",
        json.dumps({"schema_version": True, "values": []}),
        json.dumps({"schema_version": 2.0, "values": []}),
        json.dumps({"schema_version": 2, "values": [], "unknown": 1}),
        json.dumps({"schema_version": 3, "values": []}),
        '{"schema_version":2,"values":[{"observation":"\\ud800","acceptance_obligations":[{"id":"x","stimulus":"x","expected":"x"}],"oracle":"tests/x.py","acceptance_supports":[],"verification":[["x"]],"oracle_verification_index":0}]}',
        _v1_input(),
        _v2_with(verification=_MISSING),
        _v2_with(oracle_verification_index=_MISSING),
        _v2_with(verification=[]),
        _v2_with(verification=[[]]),
        _v2_with(verification=[[""]]),
        _v2_with(verification=[["a\x00b"]]),
        _v2_with(verification=[[1]]),
        _v2_with(verification="pytest"),
        _v2_with(verification=[_PYTEST_ARGV, _PYTEST_ARGV]),
        _v2_with(oracle_verification_index=1),
        _v2_with(oracle_verification_index=-1),
        _v2_with(oracle_verification_index=True),
        _v2_with(oracle_verification_index=0.0),
        _v2_with(oracle_verification_index="0"),
        _v2_with(extra_member=1),
    ],
)
def test_public_distill_refuses_closed_schema_empty_and_non_utf8_semantics_before_mutation(
    tmp_path: Path, raw: str
) -> None:
    """v1 input, an incomplete or misindexed v2 member and every closed-schema
    defect refuse with the v2 HOW before any artifact or handover byte changes."""
    root = base_repository(tmp_path / "repository")
    _prepare(root)
    before = (root / HANDOVER).read_bytes()
    code, out, err = _call(root, "distill", raw)
    assert code != 0 and "InvalidDistillDocument" in out + err, (
        "WHAT: input was not refused as InvalidDistillDocument. WHY: only a "
        "complete schema_version 2 revision may select acceptance. HOW: refuse "
        "before writing, naming the member and the v2 contract."
    )
    assert (root / HANDOVER).read_bytes() == before
    assert not (root / "docs/product/acceptance/brief.md").exists()


def test_public_distill_refusal_of_v1_input_names_the_v2_how(tmp_path: Path) -> None:
    root = base_repository(tmp_path / "repository")
    _prepare(root)
    code, out, err = _call(root, "distill", _v1_input())
    assert code != 0
    assert "schema_version 2" in out + err and "verification" in out + err, (
        "WHAT: the v1 refusal does not teach v2. WHY: the caller cannot repair "
        "input it cannot see. HOW: name schema_version 2 and its verification members."
    )


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
    # The DESIGN identity is established BEFORE the selection: a DESIGN that
    # arrives after a selection deliberately makes it need realignment, which
    # its own scenario below observes.
    code, out, err = _call(root, "design", json.dumps(MANIFEST), value=1)
    assert code == 0, out + err
    assert _call(root, "distill", raw)[0] == 0
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
        0,
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


def test_public_distill_adds_acceptance_to_the_existing_document_in_graph_order(
    tmp_path: Path,
) -> None:
    root = base_repository(tmp_path / "repository")
    supplied = _prepare(root)
    values = supplied["values"]
    assert isinstance(values, list)
    value_one, value_two = values

    assert (
        _call(
            root,
            "distill",
            json.dumps({"schema_version": 2, "values": [value_one]}),
        )[0]
        == 0
    )
    document = root / "docs/product/acceptance/brief.md"
    first_bytes = document.read_bytes()

    code, out, err = _call(
        root, "distill", json.dumps({"schema_version": 2, "values": [value_two]})
    )
    assert code == 0, out + err
    rendered = document.read_text()
    assert rendered.index(value_one["observation"]) < rendered.index(
        value_two["observation"]
    )
    stored = _stored(root)
    assert [value.acceptance[0].id for value in stored.values] == [
        "select-color",
        "see-color",
    ]

    before_retry = (
        document.read_bytes(),
        hashlib.sha256(document.read_bytes()).hexdigest(),
    )
    code, out, err = _call(root, "distill", json.dumps(supplied))
    assert code == 0, out + err
    assert (
        document.read_bytes(),
        hashlib.sha256(document.read_bytes()).hexdigest(),
    ) == before_retry
    assert document.read_bytes() != first_bytes


def test_public_distill_refuses_missing_prior_authority_without_rewriting_handover(
    tmp_path: Path,
) -> None:
    root = base_repository(tmp_path / "repository")
    supplied = _prepare(root)
    values = supplied["values"]
    assert isinstance(values, list)
    assert (
        _call(
            root,
            "distill",
            json.dumps({"schema_version": 2, "values": values[:1]}),
        )[0]
        == 0
    )
    document = root / "docs/product/acceptance/brief.md"
    document.unlink()
    before_handover = (root / HANDOVER).read_bytes()

    code, out, err = _call(
        root, "distill", json.dumps({"schema_version": 2, "values": values[1:]})
    )
    assert code != 0 and "DistillAuthorityDrift" in out + err
    assert not document.exists()
    assert (root / HANDOVER).read_bytes() == before_handover


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


def test_public_distill_replace_current_replaces_one_value_only_and_craft_receives_it(
    tmp_path: Path,
) -> None:
    """A correction changes one acceptance projection and stops before its NEXT."""
    root = base_repository(tmp_path / "repository")
    supplied = _prepare(root)
    initial = json.dumps(supplied)
    assert _call(root, "distill", initial, env={"PATH": ""})[0] == 0
    for position in (1, 2):
        code, out, err = _call(root, "design", json.dumps(MANIFEST), value=position)
        assert code == 0, out + err

    document = root / "docs/product/acceptance/brief.md"
    before_handover = json.loads((root / HANDOVER).read_text())
    before_graph = [
        (value["observation"], value["dependencies"])
        for value in before_handover["values"]
    ]
    before_value_two = json.dumps(
        before_handover["values"][1], ensure_ascii=False, separators=(",", ":")
    ).encode()
    before_value_one_authority = before_handover["values"][0]["authority"]
    before = (document.read_bytes(), (root / HANDOVER).read_bytes())

    values = supplied["values"]
    assert isinstance(values, list)
    corrected = json.loads(json.dumps(values[0]))
    corrected["acceptance_obligations"] = [
        {
            "id": "select-green",
            "stimulus": "Choose green in the public widget control.",
            "expected": "The selected color is green.",
        }
    ]
    corrected["oracle"] = "tests/acceptance/test_widget.py::test_selects_green"
    corrected["acceptance_supports"] = ["tests/support/green_widget_driver.py"]
    corrected |= _declared(corrected["oracle"])
    correction = json.dumps({"schema_version": 2, "values": [corrected]})

    refused_code, refused_out, refused_err = _call(root, "distill", correction)
    assert refused_code != 0 and "DistillHandoverConflict" in refused_out + refused_err
    assert before == (document.read_bytes(), (root / HANDOVER).read_bytes())

    code, out, err = _call(
        root, "distill", correction, replace_current=True, env={"PATH": ""}
    )
    assert code == 0, out + err
    assert "NEXT: des craft --repo-root <root> --value 1" in out
    assert not (root / ".nwave/des/turns").exists(), "DISTILL must not execute NEXT"

    after_handover = json.loads((root / HANDOVER).read_text())
    assert [
        (value["observation"], value["dependencies"])
        for value in after_handover["values"]
    ] == before_graph
    assert after_handover["values"][0]["authority"] == before_value_one_authority
    assert (
        json.dumps(
            after_handover["values"][1], ensure_ascii=False, separators=(",", ":")
        ).encode()
        == before_value_two
    )
    rendered = document.read_text()
    assert rendered.count("A user selects a widget color.") == 1
    assert "test_selects_green" in rendered
    assert "test_selects_blue" not in rendered

    results, turns, counter = (
        tmp_path / "answers.json",
        tmp_path / "turns.json",
        tmp_path / "counter",
    )
    results.write_text(
        json.dumps(
            [
                {
                    "structured_output": {
                        "outcome": "rejected",
                        "diagnostic": "captured corrected craft input",
                        "blocked_by": "product",
                    }
                }
            ]
        )
    )
    environment = hermetic_environment(
        fake_provider.environment(
            root,
            launcher_dir=tmp_path / "bin",
            results=results,
            log=turns,
            counter=counter,
            package_parent=PACKAGE_PARENT,
        ),
        tmp_path / "claude-config",
    )
    craft_code, craft_out, craft_err = run_cli_in_process(
        ["craft", "--repo-root", str(root), "--value", "1"],
        cwd=root,
        env=environment,
        catch_all=True,
    )
    assert craft_code != 0 and "CraftRejected" in craft_out + craft_err
    calls = json.loads(turns.read_text())
    assert len(calls) == 1 and calls[0]["agent"] == "nw-software-crafter"
    assert _prompt_json_value(calls[0]["prompt"], "oracle") == corrected["oracle"]
    assert (
        _prompt_json_value(calls[0]["prompt"], "acceptance_supports")
        == corrected["acceptance_supports"]
    )
    assert (
        _prompt_json_value(calls[0]["prompt"], "acceptance_obligations")
        == corrected["acceptance_obligations"]
    )


def test_public_distill_replace_current_reports_cas_loss_then_retries_without_duplication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A published correction with a lost fact CAS is indeterminate, then retryable."""
    root = base_repository(tmp_path / "repository")
    supplied = _prepare(root)
    assert _call(root, "distill", json.dumps(supplied))[0] == 0
    values = supplied["values"]
    assert isinstance(values, list)
    corrected = json.loads(json.dumps(values[0]))
    corrected["acceptance_obligations"][0]["expected"] = "The selected color is teal."
    correction = json.dumps({"schema_version": 2, "values": [corrected]})
    winner = (root / HANDOVER).read_bytes()

    def lose_after_publication(*_args: object, **_kwargs: object) -> handover.Blocked:
        return handover.Blocked(
            "HandoverDrift", "external winner", "inspect winner", refusal=True
        )

    with monkeypatch.context() as patch:
        patch.setattr(handover, "rewrite_handover", lose_after_publication)
        code, out, err = _call(root, "distill", correction, replace_current=True)
    document = root / "docs/product/acceptance/brief.md"
    assert code != 0 and "Indeterminate" in out + err
    assert "HandoverDrift" in out + err
    assert "The selected color is teal." in document.read_text()
    assert (root / HANDOVER).read_bytes() == winner

    retry_code, retry_out, retry_err = _call(
        root, "distill", correction, replace_current=True
    )
    assert retry_code == 0, retry_out + retry_err
    assert document.read_text().count("The selected color is teal.") == 1
    assert (
        _stored(root).values[0].acceptance[0].expected == "The selected color is teal."
    )


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
    rewrite_handover = handover.rewrite_handover

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
    monkeypatch.setattr(handover, "rewrite_handover", rewrite_handover)
    code, out, err = _call(root, "distill", raw)
    assert code == 0, out + err
    assert _stored(root).values[0].acceptance[0].id == "select-color"


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
    # DESIGN exists BEFORE the selection so DISTILL is aligned to its basis.
    for design_position in (1, 2):
        code, out, err = _call(
            root, "design", json.dumps(MANIFEST), value=design_position
        )
        assert code == 0, out + err
    assert _call(root, "distill", raw)[0] == 0
    stored = _stored(root)
    # Bind the DESIGN's own published facts: an exact no-op that keeps the
    # selection aligned to its basis (no differing DESIGN, no realignment).
    facts = stored.values[position - 1].authority
    assert isinstance(facts, DesignFacts)
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


# ---------------------------------------------------------------------------
# Atomic selected acceptance revision: the feature walking skeleton and the
# value 1 (one complete revision) and value 2 (currentness) observations.
# Every step below is the real ``des`` CLI; only the provider is a fake that
# captures the inputs it is given.  Native argv really executes.
# ---------------------------------------------------------------------------

FEATURE = ("--feature", "atomic-selected-acceptance")
WITNESS = "tests/acceptance/witness_b.mjs"
WITNESS_SOURCE = 'console.log("SELECTED-B-NODE");\n'
FIRST_VALUE = "A user selects a widget color."
SHARED_DECISION = "Every consumer reads one complete selected acceptance revision."
SECOND_ORACLE = "tests/acceptance/test_visible_color.py::test_visible_color"
DESIGN_ORACLE = "tests/acceptance/test_design_default.py::test_design_default"


def _declared_revision(color: str, node: str | None) -> dict[str, object]:
    """One complete selected revision: A (blue, pytest only) or B (green, +Node)."""
    oracle_path = f"tests/acceptance/test_selected_{color}.py"
    argvs: list[list[str]] = [[sys.executable, "-m", "pytest", oracle_path]]
    if node is not None:
        argvs.append([node, WITNESS])
    return {
        "observation": FIRST_VALUE,
        "acceptance_obligations": [
            {
                "id": f"select-{color}",
                "stimulus": f"Choose {color} in the public widget control.",
                "expected": f"The selected color is {color}.",
            }
        ],
        "oracle": f"{oracle_path}::test_selects_{color}",
        "acceptance_supports": [f"tests/support/{color}_driver.py"],
        "verification": argvs,
        "oracle_verification_index": 0,
    }


def _v2_input(value: dict[str, object]) -> str:
    return json.dumps({"schema_version": 2, "values": [value]})


def _value_manifest(
    *, expected: str = "stdout is red and exit is zero.", reordered: bool = False
) -> dict:
    manifest = json.loads(json.dumps(MANIFEST))
    manifest["authority"] = {"heading": "Selected widget color"}
    manifest["decisions"] = ["Value one keeps color validation at construction."]
    manifest["public_oracle"]["expected"] = expected
    manifest["oracle"] = DESIGN_ORACLE
    manifest["verification"] = [
        ["pytest", "-q", DESIGN_ORACLE.split("::", maxsplit=1)[0]]
    ]
    if reordered:
        manifest = dict(reversed(list(manifest.items())))
    return manifest


def _shared_manifest(*, constraint: str = "Value sections carry only deltas.") -> dict:
    manifest = json.loads(json.dumps(MANIFEST))
    manifest["authority"] = {"heading": "Selected acceptance feature design"}
    manifest["purpose"] = "Hold the decisions every value of the feature shares."
    manifest["constraints"] = [constraint]
    manifest["decisions"] = [SHARED_DECISION]
    manifest["oracle"] = "tests/test_shared.py::test_shared"
    manifest["verification"] = [["pytest", "-q", "tests/test_shared.py"]]
    return manifest


@pytest.fixture(scope="session")
def node_executable() -> str:
    """Node is a declared test substrate: resolved once, absolute, never skipped."""
    found = shutil.which("node")
    assert found is not None, (
        "WHAT: Node is not on PATH. WHY: selected revision B declares a Node "
        "witness that des verify must really execute; a skip or a Python "
        "substitute would falsify that. HOW: install Node (actions/setup-node in "
        "CI, or prepend its bin to PATH locally) and rerun."
    )
    absolute = str(Path(found).absolute())
    ran = subprocess.run([absolute, "--version"], capture_output=True, text=True)
    assert ran.returncode == 0, f"WHAT: {absolute} does not run: {ran.stderr}"
    return absolute


def _acceptance_keys(root: Path, position: int = 0) -> dict[str, str]:
    """The persisted selection of one value, byte-canonical per key."""
    value = json.loads((root / HANDOVER).read_text())["values"][position]
    return {
        key: json.dumps(item, sort_keys=True, ensure_ascii=False)
        for key, item in value.items()
        if key == "acceptance" or key.startswith("acceptance_")
    }


def _shared_lines(prompt: str) -> list[str]:
    return [line for line in prompt.splitlines() if line.startswith("shared_design: ")]


def _text_around(page: str, needle: str, radius: int = 400) -> str:
    """Plain words near one fact on the human page (tags removed)."""
    text = " ".join(re.sub(r"<[^>]+>", " ", page).split())
    assert needle in text, (
        f"WHAT: the page does not show {needle!r}. WHY: the human cannot judge "
        "a fact that is not rendered. HOW: project it with its label."
    )
    at = text.index(needle)
    return text[max(0, at - radius) : at + len(needle) + radius].lower()


_ROW_TAGS = frozenset({"tr", "li", "article"})
_STATE_TOKENS = re.compile(r"(?<!not )\b(current|historical|uncertain)\b")


class _RowCollector(HTMLParser):
    """Collect the plain text of every semantic row/card/list item, nesting kept."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.open: list[list[str]] = []
        self.rows: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _ROW_TAGS:
            self.open.append([])

    def handle_endtag(self, tag: str) -> None:
        if tag in _ROW_TAGS and self.open:
            self.rows.append(" ".join(" ".join(self.open.pop()).split()))

    def handle_data(self, data: str) -> None:
        for row in self.open:
            row.append(data)


def _row_of(page: str, needle: str) -> str:
    """The smallest semantic row (tr/li/article) whose text shows the locator."""
    collector = _RowCollector()
    collector.feed(page)
    collector.close()
    holding = [row for row in collector.rows if needle in row]
    assert holding, (
        f"WHAT: no row/card/list item shows {needle!r}. WHY: the human cannot "
        "judge a record that is not a row with its own state label. HOW: render "
        "each record as one row (tr, li or article) carrying locator and state."
    )
    return min(holding, key=len)


def _labels(page: str, needle: str) -> set[str]:
    """The exact state labels inside the one smallest row of a locator."""
    return set(_STATE_TOKENS.findall(_row_of(page, needle).lower()))


def test_row_label_reader_is_not_satisfied_by_a_neighbouring_or_negated_label() -> None:
    """Non-vacuity of the label reader itself, on tiny adversarial HTML."""
    page = (
        "<ul><li>rec-A.json current</li>"
        "<li>rec-B.json is not current, kept as historical</li>"
        "<li>rec-C.json</li></ul>"
    )
    assert _labels(page, "rec-A.json") == {"current"}
    assert _labels(page, "rec-B.json") == {"historical"}, "negated 'not current'"
    assert _labels(page, "rec-C.json") == set(), "neighbour label leaked into a row"
    with pytest.raises(AssertionError):
        _labels("<p>rec-A.json current</p>", "rec-A.json")  # not a row


def _assert_label(page: str, needle: str, label: str) -> None:
    found = _labels(page, needle)
    assert found == {label}, (
        f"WHAT: {needle!r} is labelled {sorted(found)}, expected exactly "
        f"{label!r}. WHY: a human must tell current from historical evidence "
        "per record. HOW: render one state label on each record row."
    )


class _Subject:
    """One real subject repository driven only through the public CLI."""

    def __init__(self, tmp_path: Path, node: str | None, *, shared: bool = True):
        self.tmp, self.node, self.shared = tmp_path, node, shared
        self.root = base_repository(tmp_path / "repository")
        self.turns = tmp_path / "workspace" / "turns.json"
        (tmp_path / "workspace").mkdir()
        self.step = stepper(self.root, tmp_path / "workspace", self.turns)
        native = tmp_path / "native-bin"
        native.mkdir()
        (native / "git").symlink_to(shutil.which("git"))  # type: ignore[arg-type]
        self.native = {"PATH": str(native), "PYTHONPATH": str(PACKAGE_PARENT)}
        if node is not None:
            witness = self.root / WITNESS
            witness.parent.mkdir(parents=True, exist_ok=True)
            witness.write_text(WITNESS_SOURCE)
            subprocess.run(["git", "-C", str(self.root), "add", WITNESS], check=True)
            subprocess.run(
                ["git", "-C", str(self.root), "commit", "-qm", "owned Node witness"],
                check=True,
            )

    # -- constructors -------------------------------------------------------
    def designed(self) -> _Subject:
        code, out, err = _call(
            self.root, "discuss", json.dumps(_discuss_payload()), scope=FEATURE
        )
        assert code == 0, out + err
        if self.shared:
            code, out, err = _call(
                self.root, "design", json.dumps(_shared_manifest()), shared=True
            )
            assert code == 0, out + err
        code, out, err = _call(
            self.root, "design", json.dumps(_value_manifest()), value=1
        )
        assert code == 0, out + err
        self.second_done = False
        return self

    def _second_payload(self) -> dict[str, object]:
        return {
            "schema_version": 2,
            "values": [
                {
                    "observation": "A user sees the selected widget color.",
                    "acceptance_obligations": [
                        {
                            "id": "see-color",
                            "stimulus": "Open the widget after choosing a color.",
                            "expected": "The visible widget color is shown.",
                        }
                    ],
                    "oracle": SECOND_ORACLE,
                    "acceptance_supports": ["tests/support/visible_driver.py"],
                    **_declared(SECOND_ORACLE),
                }
            ],
        }

    def complete_second_value(self) -> None:
        """Give the visible-color value its own closed design, oracle and craft.

        Global verify checks the whole request, so value 2 must be complete
        through the same public constructors; it owns its own files and never
        touches value 1's product or oracle.
        """
        if getattr(self, "second_done", True):
            return
        self.second_done = True
        manifest = _value_manifest()
        manifest["authority"] = {"heading": "Visible widget color"}
        manifest["decisions"] = ["Value two reads the selection back."]
        manifest["oracle"] = SECOND_ORACLE
        manifest["verification"] = [
            ["pytest", "-q", SECOND_ORACLE.split("::", maxsplit=1)[0]]
        ]
        code, out, err = _call(self.root, "design", json.dumps(manifest), value=2)
        assert code == 0, out + err
        payload = self._second_payload()
        code, out, err = _call(self.root, "distill", json.dumps(payload))
        assert code == 0, out + err
        code, out, err = self.step(
            "oracle",
            "--repo-root",
            str(self.root),
            "--value",
            "2",
            answers=[
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "authored a red acceptance oracle",
                    },
                    "writes": {
                        "tests/acceptance/test_visible_color.py": (
                            "from pathlib import Path\n\n\n"
                            "def test_visible_color():\n"
                            "    root = Path(__file__).resolve().parents[2]\n"
                            "    product = root / 'src' / 'widget.py'\n"
                            "    text = product.read_text() if product.exists() else ''\n"
                            "    assert 'VISIBLE = 1' in text, 'the widget shows no color'\n"
                        ),
                        "tests/support/visible_driver.py": "MARKER = 1\n",
                    },
                },
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "the oracle set is admissible",
                    }
                },
            ],
        )
        assert code == 0, out + err
        code, out, err = self.step(
            "craft",
            "--repo-root",
            str(self.root),
            "--value",
            "2",
            answers=[
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "implemented the value behind its oracle",
                    },
                    "writes": {
                        "src/widget.py": (self.root / "src/widget.py").read_text()
                        + "VISIBLE = 1\n"
                    },
                }
            ],
        )
        assert code == 0, out + err

    def select(self, color: str, *, replace: bool = False) -> None:
        node = self.node if color == "green" else None
        code, out, err = _call(
            self.root,
            "distill",
            _v2_input(_declared_revision(color, node)),
            replace_current=replace,
        )
        assert code == 0, out + err
        if replace and getattr(self, "second_done", False):
            # complete realignment: the visible-color value is re-declared too
            code, out, err = _call(
                self.root,
                "distill",
                json.dumps(self._second_payload()),
                replace_current=True,
            )
            assert code == 0, out + err

    # -- consumers ----------------------------------------------------------
    def rows(self) -> list[dict]:
        return json.loads(self.turns.read_text()) if self.turns.exists() else []

    def oracle(self, color: str) -> tuple[int, str, str, list[dict]]:
        seen = len(self.rows())
        code, out, err = self.step(
            "oracle",
            "--repo-root",
            str(self.root),
            "--value",
            "1",
            answers=[
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "authored a red acceptance oracle",
                    },
                    "writes": {
                        f"tests/acceptance/test_selected_{color}.py": (
                            "from pathlib import Path\n\n\n"
                            f"def test_selects_{color}():\n"
                            "    root = Path(__file__).resolve().parents[2]\n"
                            "    product = root / 'src' / 'widget.py'\n"
                            "    text = product.read_text() if product.exists() else ''\n"
                            f"    assert '{color.upper()} = 1' in text, "
                            f"'the widget does not report {color}'\n"
                        ),
                        f"tests/support/{color}_driver.py": "MARKER = 1\n",
                    },
                },
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "the oracle set is admissible",
                    }
                },
            ],
        )
        return code, out, err, self.rows()[seen:]

    def craft(self, color: str) -> tuple[int, str, str, list[dict]]:
        seen = len(self.rows())
        product = "BLUE = 1\n" + ("GREEN = 1\n" if color == "green" else "")
        if getattr(self, "second_done", False):
            product += "VISIBLE = 1\n"  # value 2's completed behaviour is kept
        code, out, err = self.step(
            "craft",
            "--repo-root",
            str(self.root),
            "--value",
            "1",
            answers=[
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "implemented the value behind its oracle",
                    },
                    "writes": {"src/widget.py": product},
                }
            ],
        )
        return code, out, err, self.rows()[seen:]

    def verify(self) -> dict[str, str]:
        self.complete_second_value()
        code, out, err = run_cli_in_process(
            ["verify", "--repo-root", str(self.root)],
            cwd=self.root,
            env=self.native,
            catch_all=True,
        )
        assert code == 0, out + err
        return block(out, err)

    def evidence(self, lines: dict[str, str]) -> tuple[Path, list[dict]]:
        path = self.root / lines["NATIVE-EVIDENCE"]
        return path, json.loads(path.read_text(encoding="utf-8"))

    def through(self, color: str) -> dict[str, str]:
        assert self.oracle(color)[0] == 0
        assert self.craft(color)[0] == 0
        return self.verify()

    def page(self, name: str = "page") -> str:
        out_file = self.tmp / f"{name}.html"
        code, out, err = self.step(
            "project", "--repo-root", str(self.root), "--html", str(out_file)
        )
        assert code == 0, out + err
        return out_file.read_text(encoding="utf-8")

    def state(self) -> str:
        code, out, err = self.step("state", "--repo-root", str(self.root))
        assert code == 0, out + err
        return out

    def prepared(self, role: str, candidate: str) -> tuple[dict, str]:
        code, out, err = self.step(
            "prepare-role",
            "--repo-root",
            str(self.root),
            "--role",
            role,
            "--candidate",
            candidate,
        )
        assert code == 0, out + err
        raw = (self.root / block(out, err)["INPUT"]).read_text(encoding="utf-8")
        return json.loads(raw), raw

    def bytes(self) -> bytes:
        return (self.root / HANDOVER).read_bytes()


def _assert_shared_once(prompt: str, subject: _Subject, who: str) -> None:
    binding = _stored(subject.root).shared_design
    assert binding is not None
    lines = _shared_lines(prompt)
    assert len(lines) == 1, (
        f"WHAT: {who} received {len(lines)} top-level shared_design facts, "
        "expected exactly one. WHY: shared authority repeated or absent lets "
        "roles judge different decisions. HOW: project _shared(stored) once."
    )
    shared = json.loads(lines[0].removeprefix("shared_design: "))
    assert shared["authority"] == binding.authority_locator
    assert shared["semantic_sha256"] == binding.semantic_sha256
    assert set(shared) == {
        "authority",
        "semantic_sha256",
        "targets",
        "paradigm",
        "decisions",
        "obligations",
    }
    assert shared["decisions"] == [SHARED_DECISION]
    assert prompt.count(SHARED_DECISION) == 1, (
        f"WHAT: {who} carries the shared decision more than once (per-value copy)."
    )


def _assert_revision_b(rows: list[dict], subject: _Subject, who: str) -> None:
    assert rows, f"WHAT: {who} bought no provider turn to capture."
    b = _declared_revision("green", subject.node)
    for row in rows:
        prompt = row["prompt"]
        assert b["oracle"] in prompt, f"{who} did not receive revision B"
        assert DESIGN_ORACLE not in prompt, (
            f"WHAT: {who} received the DESIGN oracle beside B. WHY: a mixed tuple "
            "lets roles judge different criteria. HOW: read only B's tuple."
        )
        for key, want in (
            ("oracle", b["oracle"]),
            ("acceptance_supports", b["acceptance_supports"]),
            ("acceptance_obligations", b["acceptance_obligations"]),
            ("verification", b["verification"]),
            ("oracle_verification_index", b["oracle_verification_index"]),
        ):
            assert _prompt_json_value(prompt, key) == want, (
                f"WHAT: {who} {key} differs from B's. WHY: one complete tuple. "
                "HOW: project B through a single accessor."
            )
        _assert_shared_once(prompt, subject, who)


def _members_of(node: object, observation: str) -> list[dict]:
    """Every object of a structured input that is the per-value member of one value."""
    found: list[dict] = []
    if isinstance(node, dict):
        if node.get("observation") == observation and "oracle" in node:
            found.append(node)
        for item in node.values():
            found += _members_of(item, observation)
    elif isinstance(node, list):
        for item in node:
            found += _members_of(item, observation)
    return found


def _assert_reviewer_member_is_b(reviewer: dict, node: str) -> None:
    b = _declared_revision("green", node)
    members = _members_of(reviewer, FIRST_VALUE)
    assert len(members) == 1, (
        f"WHAT: reviewer input has {len(members)} per-value members for the "
        "selected value, expected one. WHY: one value, one selected tuple. HOW: "
        "project the value once with its complete selected revision."
    )
    member = members[0]
    for key in (
        "oracle",
        "acceptance_supports",
        "acceptance_obligations",
        "verification",
        "oracle_verification_index",
    ):
        assert member.get(key) == b[key], (
            f"WHAT: reviewer per-value {key} is {member.get(key)!r}, expected B's "
            f"{b[key]!r}. WHY: the reviewer must judge the same complete tuple the "
            "oracle, crafter and verify used. HOW: project B's complete selected "
            "revision, including ordered argv and index, into the value member."
        )


def _assert_persisted_b(subject: _Subject, node: str) -> None:
    persisted, b = _acceptance_keys(subject.root), _declared_revision("green", node)
    assert json.loads(persisted["acceptance_verification"]) == b["verification"]
    assert json.loads(persisted["acceptance_oracle_verification_index"]) == 0
    assert json.loads(persisted["acceptance"]) == b["acceptance_obligations"]
    assert json.loads(persisted["acceptance_oracle"]) == b["oracle"]
    assert json.loads(persisted["acceptance_supports"]) == b["acceptance_supports"]


def _assert_b_native_evidence(records: list[dict], node: str) -> None:
    # value 2 (visible color) contributes its own record; B's are value 1's
    records = [
        r for r in records if not r["argv"][-1].endswith("test_visible_color.py")
    ]
    assert len(records) == 2, (
        f"WHAT: native evidence holds {len(records)} records, expected B's two. "
        "WHY: B declares a pytest oracle and a Node witness. HOW: execute every "
        "declared argv in order."
    )
    declared = _declared_revision("green", node)["verification"]
    assert [record["argv"] for record in records] == declared, (
        "WHAT: executed argv differ from B's ordered declared argv. WHY: verify "
        "must run exactly the selected tuple, in order. HOW: execute B's list."
    )
    assert [record["exit"] for record in records] == [0, 0], (
        "WHAT: a declared native command did not exit zero. WHY: green evidence "
        "means every declared argv succeeded. HOW: retain each native exit."
    )
    assert Path(records[1]["argv"][0]).is_absolute()
    assert "SELECTED-B-NODE" in records[1]["stdout"]
    assert "test_selected_blue" not in json.dumps(records), "A leaked into B evidence"


def test_one_complete_selected_revision_reaches_oracle_craft_and_verify(
    tmp_path: Path, node_executable: str
) -> None:
    """A changed acceptance criterion is ONE revision for every downstream role.

    WHAT: after A is replaced by B, ORACLE, CRAFT, VERIFY and the reviewer all
    receive B's complete tuple (oracle, supports, obligations, ordered native
    argv, index) with the shared authority exactly once, and the source-blind
    examiner receives none of it. WHY: a partial overlay lets the oracle
    author, crafter and verification judge different criteria. HOW: persist and
    read one complete revision through a single accessor.
    """
    subject = _Subject(tmp_path, node_executable).designed()
    subject.select("blue")
    a_lines = subject.through("blue")
    subject.select("green", replace=True)

    persisted = _acceptance_keys(subject.root)
    b = _declared_revision("green", node_executable)
    assert json.loads(persisted["acceptance_verification"]) == b["verification"]
    assert json.loads(persisted["acceptance_oracle_verification_index"]) == 0
    assert json.loads(persisted["acceptance"]) == b["acceptance_obligations"]
    assert re.fullmatch(r'"[0-9a-f]{64}"', persisted["acceptance_design_basis_sha256"])

    code, out, err, oracle_rows = subject.oracle("green")
    assert code == 0, out + err
    _assert_revision_b(oracle_rows, subject, "ORACLE")
    code, out, err, craft_rows = subject.craft("green")
    assert code == 0, out + err
    _assert_revision_b(craft_rows, subject, "CRAFT")
    prompt = craft_rows[0]["prompt"]
    assert _prompt_json_value(prompt, "oracle") == b["oracle"]
    assert _prompt_json_value(prompt, "acceptance_supports") == b["acceptance_supports"]
    assert (
        _prompt_json_value(prompt, "acceptance_obligations")
        == b["acceptance_obligations"]
    )

    lines = subject.verify()
    _, records = subject.evidence(lines)
    _assert_b_native_evidence(records, node_executable)
    assert lines["NATIVE-EVIDENCE"] != a_lines["NATIVE-EVIDENCE"]

    candidate = lines["CANDIDATE"]
    reviewer, reviewer_raw = subject.prepared("reviewer", candidate)
    binding = _stored(subject.root).shared_design
    assert binding is not None
    assert reviewer["shared_design"]["authority"] == binding.authority_locator
    assert reviewer["shared_design"]["semantic_sha256"] == binding.semantic_sha256
    assert reviewer["shared_design"]["decisions"] == [SHARED_DECISION]
    _assert_reviewer_member_is_b(reviewer, node_executable)
    assert reviewer_raw.count(SHARED_DECISION) == 1, "shared authority not once"
    examiner, examiner_raw = subject.prepared("examiner", candidate)
    assert "shared_design" not in examiner and "targets" not in examiner
    for forbidden in (SHARED_DECISION, binding.authority_locator, b["oracle"]):
        assert forbidden not in examiner_raw, (
            f"WHAT: the source-blind examiner input carries {forbidden!r}."
        )
    _assert_authority_bytes_bind_candidate(subject, lines)


def test_feature_revision_reaches_every_consumer_keeps_history_and_replays_nothing(
    tmp_path: Path, node_executable: str
) -> None:
    """The ONE feature walking skeleton: design -> A -> B -> oracle -> craft ->
    verify -> project -> prepare-role. Values extend it; none adds a second."""
    subject = _Subject(tmp_path, node_executable).designed()
    subject.select("blue")
    a_lines = subject.through("blue")
    a_path, _a_records = subject.evidence(a_lines)
    a_bytes = a_path.read_bytes()
    subject.select("green", replace=True)
    b_lines = subject.through("green")
    _, b_records = subject.evidence(b_lines)
    _assert_b_native_evidence(b_records, node_executable)
    assert a_path.read_bytes() == a_bytes, "A evidence was rewritten"
    page = subject.page()
    _assert_label(page, a_lines["NATIVE-EVIDENCE"], "historical")
    assert a_lines["NATIVE-EVIDENCE-SHA256"] in " ".join(page.split())
    _assert_label(page, b_lines["NATIVE-EVIDENCE"], "current")
    native = subject.root / ".nwave/des/logs/native"
    before = {p.name: p.read_bytes() for p in native.iterdir()}
    for role in ("reviewer", "examiner"):
        subject.prepared(role, b_lines["CANDIDATE"])
    assert {p.name: p.read_bytes() for p in native.iterdir()} == before, (
        "WHAT: preparing review or EXAMINE changed the kept native evidence. "
        "WHY: preparation reads collected evidence and replays nothing (the "
        "declared-counter oracle of value 4 measures the argv itself). HOW: "
        "prepare-role must only read."
    )


@pytest.mark.parametrize("change", ("value", "shared"))
def test_design_change_keeps_selected_revision_and_needs_explicit_complete_realignment(
    tmp_path: Path, node_executable: str, change: str
) -> None:
    """(c)/(s) an actual DESIGN change keeps B's bytes but reports realignment;
    only a complete DISTILL replacement (r) restores alignment."""
    subject = _Subject(tmp_path, node_executable).designed()
    subject.select("blue")
    subject.select("green", replace=True)
    b_lines = subject.through("green")
    b_path, _ = subject.evidence(b_lines)
    b_bytes = b_path.read_bytes()
    _assert_label(subject.page("before"), b_lines["NATIVE-EVIDENCE"], "current")
    kept, before = _acceptance_keys(subject.root), subject.bytes()

    if change == "value":
        code, out, err = _call(
            subject.root,
            "design",
            json.dumps(_value_manifest(expected="stdout is green and exit is zero.")),
            value=1,
            replace_current=True,
        )
    else:
        code, out, err = _call(
            subject.root,
            "design",
            json.dumps(_shared_manifest(constraint="Roles never see a mixed tuple.")),
            shared=True,
            replace_current=True,
        )
    assert code == 0, out + err
    assert subject.bytes() != before, "the DESIGN identity change was not recorded"
    assert b_path.read_bytes() == b_bytes
    _assert_label(subject.page("changed"), b_lines["NATIVE-EVIDENCE"], "historical")
    assert _acceptance_keys(subject.root) == kept, (
        "WHAT: a DESIGN change rewrote the selected revision. WHY: the human "
        "decided B is kept until explicitly realigned. HOW: bind_design_facts "
        "and bind_shared_design never modify acceptance keys."
    )

    seen = len(subject.rows())
    code, out, err, _ = subject.oracle("green")
    text = out + err
    assert code != 0 and "Indeterminate" in text
    assert "SelectedRevisionRealignmentNeeded" in text
    assert "des distill" in text and "--replace-current" in text
    assert "schema_version 2" in text, "the HOW must name the complete v2 input"
    assert len(subject.rows()) == seen, "a misaligned selection bought a turn"

    state = subject.state()
    assert "oracle=uncertain craft=uncertain" in state, state
    assert "SelectedRevisionRealignmentNeeded" in state, (
        "WHAT: state hid the selected revision's realignment condition. "
        "WHY: an orchestrator must distinguish a missing oracle from a preserved "
        "selection made over another DESIGN. HOW: project the reader's specific "
        "recovery in state."
    )
    assert (
        f"NEXT: des distill --repo-root {subject.root} --replace-current --input -"
        in state
    ), (
        "WHAT: state named des oracle for an unrealigned selected revision. "
        "WHY: that command can only refuse before buying a turn, so it causes a "
        "useless attempt. HOW: suggest the complete DISTILL replacement and let "
        "the orchestrator obtain its manifest from the acceptance designer."
    )

    misaligned = subject.bytes()
    code, out, err = _call(
        subject.root, "distill", _v2_input(_declared_revision("green", node_executable))
    )
    assert code != 0 and "DistillHandoverConflict" in out + err
    assert "--replace-current" in out + err
    assert subject.bytes() == misaligned

    subject.select("green", replace=True)  # (r) complete explicit replacement
    assert len(subject.rows()) == seen, "realignment bought a provider turn"
    assert "oracle=uncertain craft=uncertain" not in subject.state()
    _assert_persisted_b(subject, node_executable)
    assert b_path.read_bytes() == b_bytes, "prior evidence was rewritten"
    _assert_label(subject.page("realigned"), b_lines["NATIVE-EVIDENCE"], "historical")


def test_reordered_design_manifest_is_a_no_op_that_keeps_b_current(
    tmp_path: Path, node_executable: str
) -> None:
    """(n) the same normalized DESIGN input, reordered, changes no byte."""
    subject = _Subject(tmp_path, node_executable).designed()
    subject.select("blue")
    subject.select("green", replace=True)
    b_lines = subject.through("green")
    b_path, _ = subject.evidence(b_lines)
    b_bytes = b_path.read_bytes()
    before = subject.bytes()
    code, out, err = _call(
        subject.root,
        "design",
        json.dumps(_value_manifest(reordered=True), indent=2),
        value=1,
    )
    assert code == 0, out + err
    assert subject.bytes() == before, (
        "WHAT: an identical normalized DESIGN rewrote the handover. WHY: a "
        "known-identity no-op must keep B and its evidence current. HOW: compare "
        "DesignFacts and design_semantic_sha256, then return stored unchanged."
    )
    _assert_label(subject.page("noop"), b_lines["NATIVE-EVIDENCE"], "current")
    assert b_path.read_bytes() == b_bytes
    _assert_persisted_b(subject, node_executable)
    assert "oracle=uncertain craft=uncertain" not in subject.state()


def _seed_legacy_design_identity(subject: _Subject) -> None:
    """Historical canonical bytes: a DESIGN bound before full-input identity."""
    payload = json.loads(subject.bytes())
    for item in payload["values"]:
        item.pop("design_semantic_sha256", None)
    (subject.root / HANDOVER).write_bytes(
        json.dumps(
            payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode()
    )


def test_unknown_legacy_design_identity_bootstrap_misaligns_b_until_replacement(
    tmp_path: Path, node_executable: str
) -> None:
    subject = _Subject(tmp_path, node_executable, shared=False).designed()
    _seed_legacy_design_identity(subject)
    subject.select("green")
    b_lines = subject.through("green")
    b_path, _ = subject.evidence(b_lines)
    b_bytes = b_path.read_bytes()
    kept, selected = _acceptance_keys(subject.root), subject.bytes()

    code, out, err = _call(
        subject.root, "design", json.dumps(_value_manifest()), value=1
    )
    assert code == 0, out + err
    assert subject.bytes() != selected, "identity bootstrap must change the handover"
    assert b_path.read_bytes() == b_bytes
    _assert_label(subject.page("boot"), b_lines["NATIVE-EVIDENCE"], "historical")
    assert "design_semantic_sha256" in json.loads(subject.bytes())["values"][0]
    assert _acceptance_keys(subject.root) == kept
    seen = len(subject.rows())
    code, out, err, _ = subject.oracle("green")
    assert code != 0 and "SelectedRevisionRealignmentNeeded" in out + err
    assert len(subject.rows()) == seen

    subject.select("green", replace=True)
    assert len(subject.rows()) == seen, "replacement bought a provider turn"
    assert "oracle=uncertain craft=uncertain" not in subject.state()
    _assert_persisted_b(subject, node_executable)
    identified = subject.bytes()
    code, out, err = _call(
        subject.root, "design", json.dumps(_value_manifest()), value=1
    )
    assert code == 0 and subject.bytes() == identified, (
        "a later identical normalized rebind must be an exact no-op"
    )


def _seed_persisted_v1_selection(root: Path, oracle: str) -> None:
    """Historical v1 trio bytes; the v1-refusing constructor cannot author them."""
    payload = json.loads((root / HANDOVER).read_bytes())
    item = payload["values"][0]
    item["acceptance"] = [
        {"id": "select-blue", "stimulus": "Choose blue.", "expected": "It is blue."}
    ]
    item["acceptance_oracle"] = oracle
    item["acceptance_supports"] = []
    (root / HANDOVER).write_bytes(
        json.dumps(
            payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode()
    )


def test_persisted_v1_trio_is_incomplete_everywhere_even_when_its_oracle_equals_design(
    tmp_path: Path,
) -> None:
    subject = _Subject(tmp_path, None, shared=False).designed()
    _seed_persisted_v1_selection(subject.root, DESIGN_ORACLE)
    before, seen = subject.bytes(), len(subject.rows())
    candidate = subprocess.run(
        ["git", "-C", str(subject.root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    commands = (
        ("oracle", "--value", "1"),
        ("craft", "--value", "1"),
        ("verify",),
        ("prepare-role", "--role", "reviewer", "--candidate", candidate),
    )
    for command, *rest in commands:
        code, out, err = subject.step(command, "--repo-root", str(subject.root), *rest)
        text = out + err
        assert code != 0, command
        assert "SelectedRevisionIncomplete" in text, command
        assert "--replace-current" in text and "schema_version 2" in text, command
    assert subject.bytes() == before and len(subject.rows()) == seen
    assert "oracle=uncertain craft=uncertain" in subject.state()
    page = subject.page()
    assert "uncertain" in _text_around(page, "--replace-current", 200)


def test_handover_without_shared_design_gives_prompts_no_shared_design(
    tmp_path: Path,
) -> None:
    subject = _Subject(tmp_path, None, shared=False).designed()
    subject.select("blue")
    code, out, err, rows = subject.oracle("blue")
    assert code == 0, out + err
    assert rows and all(not _shared_lines(row["prompt"]) for row in rows)
    assert all("test_selects_blue" in row["prompt"] for row in rows)


def test_revision_keeps_evidence_and_projects_current_historical_uncertain(
    tmp_path: Path, node_executable: str
) -> None:
    """After A -> B: B current, A historical and kept; misaligned B uncertain
    with its explicit HOW; a complete replacement never rewrites old evidence."""
    subject = _Subject(tmp_path, node_executable).designed()
    subject.select("blue")
    a_lines = subject.through("blue")
    a_path, _ = subject.evidence(a_lines)
    a_bytes = a_path.read_bytes()
    a_loc = a_lines["NATIVE-EVIDENCE"]

    subject.select("blue", replace=True)  # unchanged-selection control
    _assert_label(subject.page("unchanged"), a_loc, "current")

    subject.select("green", replace=True)
    page = subject.page("selected-b")
    _assert_label(page, a_loc, "historical")
    assert "current" not in _labels(page, "test_selects_green"), (
        "WHAT: B is claimed current with no current verification record. WHY: "
        "only A was verified. HOW: show B verified only after its own record."
    )
    assert a_lines["NATIVE-EVIDENCE-SHA256"] in " ".join(page.split())
    assert "witness_b.mjs" in page and "test_selects_blue" not in _text_around(
        page, "test_selects_green", 60
    )
    b_lines = subject.through("green")
    b_loc = b_lines["NATIVE-EVIDENCE"]
    page = subject.page("verified-b")
    _assert_label(page, b_loc, "current")
    _assert_label(page, a_loc, "historical")
    assert a_path.read_bytes() == a_bytes, "A evidence was rewritten"

    b_path, _ = subject.evidence(b_lines)
    b_bytes, kept = b_path.read_bytes(), _acceptance_keys(subject.root)
    code, out, err = _call(
        subject.root,
        "design",
        json.dumps(_value_manifest(expected="stdout is green and exit is zero.")),
        value=1,
        replace_current=True,
    )
    assert code == 0, out + err
    assert "oracle=uncertain craft=uncertain" in subject.state()
    page = subject.page("misaligned")
    assert "--replace-current" in page
    assert "current" not in _labels(page, "test_selects_green")
    assert _acceptance_keys(subject.root) == kept and b_path.read_bytes() == b_bytes

    subject.select("green", replace=True)
    page = subject.page("realigned")
    assert _labels(page, b_loc) == {"historical"}, (
        "WHAT: pre-realignment B evidence is shown as current. WHY: its bytes "
        "were measured against other handover bytes. HOW: label it historical "
        "and keep it until a new verify records a current one."
    )
    assert b_path.read_bytes() == b_bytes and a_path.read_bytes() == a_bytes

    # A MOVED record (code moved after verification) is neither absent nor current.
    (subject.root / "moved_marker.txt").write_text("moved\n")
    for cmd in (["add", "-A"], ["commit", "-q", "-m", "move code"]):
        subprocess.run(
            [
                "git",
                "-C",
                str(subject.root),
                "-c",
                "user.name=t",
                "-c",
                "user.email=t@t",
                *cmd,
            ],
            check=True,
            capture_output=True,
        )
    page = subject.page("moved")
    found = _labels(page, a_loc)
    assert found and "current" not in found, (
        f"WHAT: a MOVED record is labelled {sorted(found)}. WHY: it must be "
        "neither absent nor current. HOW: label it historical or uncertain."
    )
    assert a_path.read_bytes() == a_bytes


def test_verified_record_stays_kept_but_is_no_longer_current_after_a_code_move(
    tmp_path: Path, node_executable: str
) -> None:
    """Same record, handover unchanged: current before a code-only commit, kept
    byte-identical and not current after it."""
    subject = _Subject(tmp_path, node_executable).designed()
    subject.select("blue")
    lines = subject.through("blue")
    path, _ = subject.evidence(lines)
    loc, kept = lines["NATIVE-EVIDENCE"], path.read_bytes()
    handover = subject.bytes()
    before = subject.page("before-move")
    _assert_label(before, loc, "current")

    (subject.root / "moved_marker.txt").write_text("moved\n")
    for cmd in (["add", "-A"], ["commit", "-q", "-m", "move code only"]):
        subprocess.run(
            [
                "git",
                "-C",
                str(subject.root),
                "-c",
                "user.name=t",
                "-c",
                "user.email=t@t",
                *cmd,
            ],
            check=True,
            capture_output=True,
        )
    assert subject.bytes() == handover, "handover must stay unchanged"
    after = _labels(subject.page("after-move"), loc)
    assert after and "current" not in after and after != _labels(before, loc), (
        f"WHAT: after a code-only move the same record is labelled {sorted(after)}. "
        "WHY: it was measured against other code, so it is not proof now. "
        "HOW: keep it visible, labelled historical or uncertain, never current."
    )
    assert path.read_bytes() == kept, "evidence bytes must stay unchanged"


_ARGV = st.lists(
    st.text(alphabet=st.characters(categories=("Ll", "Nd")), min_size=1, max_size=8),
    min_size=1,
    max_size=3,
)


def _property_repository(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = base_repository(tmp_path_factory.mktemp("property") / "repository")
    _prepare(root)
    return root


def _seed_once(root: Path) -> None:
    """Plain complete v2 write before any --replace-current (idempotent)."""
    if _acceptance_keys(root).get("acceptance", "[]") != "[]":
        return
    seed = json.dumps(
        {"schema_version": 2, "values": [_distill_payload()["values"][0]]}  # type: ignore[index]
    )
    code, out, err = _call(root, "distill", seed)
    assert code == 0, out + err


@pytest.fixture(scope="module")
def property_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _property_repository(tmp_path_factory)


@settings(
    max_examples=12,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    argvs=st.lists(_ARGV, min_size=1, max_size=3, unique_by=tuple),
    data=st.data(),
)
def test_any_complete_ordered_v2_verification_is_kept_in_declared_order(
    property_root: Path, argvs: list[list[str]], data: st.DataObject
) -> None:
    """Law: a value with distinct ordered argvs and an in-range index is stored
    exactly, order and index preserved, whatever their shape."""
    _seed_once(property_root)
    index = data.draw(st.integers(0, len(argvs) - 1))
    value = json.loads(json.dumps(_distill_payload()["values"][0]))  # type: ignore[index]
    value["verification"], value["oracle_verification_index"] = argvs, index
    code, out, err = _call(
        property_root,
        "distill",
        json.dumps({"schema_version": 2, "values": [value]}),
        replace_current=True,
    )
    assert code == 0, out + err
    kept = _acceptance_keys(property_root)
    assert json.loads(kept["acceptance_verification"]) == argvs
    assert json.loads(kept["acceptance_oracle_verification_index"]) == index


@settings(
    max_examples=12,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    argvs=st.lists(_ARGV, min_size=1, max_size=3, unique_by=tuple),
    misindex=st.one_of(st.integers(-5, -1), st.integers(0, 5)),
    duplicated=st.booleans(),
)
def test_any_duplicate_or_out_of_range_v2_verification_is_refused_without_mutation(
    property_root: Path, argvs: list[list[str]], misindex: int, duplicated: bool
) -> None:
    """Law: a duplicate argv, or an index outside the argv list, is refused
    naming the member, and no byte of the handover changes."""
    _seed_once(property_root)
    if duplicated:
        argvs = [*argvs, argvs[0]]
        index = 0
    else:
        index = misindex if not 0 <= misindex < len(argvs) else len(argvs)
    value = json.loads(json.dumps(_distill_payload()["values"][0]))  # type: ignore[index]
    value["verification"], value["oracle_verification_index"] = argvs, index
    before = (property_root / HANDOVER).read_bytes()
    code, out, err = _call(
        property_root,
        "distill",
        json.dumps({"schema_version": 2, "values": [value]}),
        replace_current=True,
    )
    assert code != 0 and "InvalidDistillDocument" in out + err
    assert (property_root / HANDOVER).read_bytes() == before


# -- revision identity: selected criteria, provider DESIGN, argv grammar -----


def _labels_of(state: str, position: int = 1) -> dict[str, str]:
    """The oracle= and craft= currentness labels of one VALUE line of `des state`."""
    line = next(
        row for row in state.splitlines() if row.startswith(f"VALUE-{position}:")
    )
    return {
        name: re.search(rf"{name}=(.+?)(?= \w+=|$)", line).group(1)  # type: ignore[union-attr]
        for name in ("oracle", "craft")
    }


def _blue_design(subject: _Subject) -> None:
    """DESIGN declares the very oracle and argv that DISTILL will select."""
    path = "tests/acceptance/test_selected_blue.py"
    manifest = _value_manifest()
    manifest["oracle"] = f"{path}::test_selects_blue"
    manifest["acceptance_supports"] = ["tests/support/blue_driver.py"]
    manifest["verification"] = [[sys.executable, "-m", "pytest", path]]
    code, out, err = _call(
        subject.root, "design", json.dumps(manifest), value=1, replace_current=True
    )
    assert code == 0, out + err


def _blue_with(**changes: object) -> dict[str, object]:
    value = _declared_revision("blue", None)
    value.update(changes)
    return value


def _assert_selection_made_oracle_and_craft_stale(subject: _Subject) -> None:
    labels = _labels_of(subject.state())
    assert labels["oracle"] != "recorded" and labels["craft"] != "recorded", (
        "WHAT: a changed selected revision left "
        f"oracle={labels['oracle']} craft={labels['craft']} current. WHY: the "
        "recorded oracle and craft were produced for other acceptance criteria "
        "or other declared commands, although no code byte moved. HOW: key "
        "every turn record to the selected revision identity and judge "
        "currentness against it."
    )


def test_first_selection_with_other_obligations_makes_oracle_and_craft_stale(
    tmp_path: Path,
) -> None:
    """(I) DESIGN's own oracle, supports and argv, but explicit new obligations."""
    subject = _Subject(tmp_path, None, shared=False).designed()
    _blue_design(subject)
    assert subject.oracle("blue")[0] == 0 and subject.craft("blue")[0] == 0
    assert _labels_of(subject.state()) == {"oracle": "recorded", "craft": "recorded"}

    changed = _blue_with()
    changed["acceptance_obligations"][0]["expected"] = "Blue is shown, exactly."  # type: ignore[index]
    code, out, err = _call(subject.root, "distill", _v2_input(changed))
    assert code == 0, out + err
    _assert_selection_made_oracle_and_craft_stale(subject)


@pytest.mark.parametrize("change", ("obligations", "added-argv"))
def test_replacing_a_selection_without_moving_code_makes_oracle_and_craft_stale(
    tmp_path: Path, change: str
) -> None:
    """(II) same oracle bytes and supports; only criteria or commands differ."""
    subject = _Subject(tmp_path, None, shared=False).designed()
    _blue_design(subject)
    subject.select("blue")
    assert subject.oracle("blue")[0] == 0 and subject.craft("blue")[0] == 0
    assert _labels_of(subject.state()) == {"oracle": "recorded", "craft": "recorded"}

    if change == "obligations":
        revision = _blue_with(
            acceptance_obligations=[
                {
                    "id": "select-blue",
                    "stimulus": "Choose blue with the keyboard.",
                    "expected": "The selected color is blue, unmistakably.",
                }
            ]
        )
    else:
        argvs = _blue_with()["verification"]
        revision = _blue_with(
            verification=[*argvs, [sys.executable, "-c", "print('extra')"]]  # type: ignore[misc]
        )
    code, out, err = _call(
        subject.root, "distill", _v2_input(revision), replace_current=True
    )
    assert code == 0, out + err
    _assert_selection_made_oracle_and_craft_stale(subject)


def test_an_unrelated_value_revision_keeps_this_value_evidence_current(
    tmp_path: Path,
) -> None:
    """A value's record belongs to its cited DESIGN sections, not to HEAD.

    Value 2 changes its own cited section after value 1 has recorded both
    turns.  The public state projection must keep value 1 current and must
    not buy another oracle or craft turn: its owned bytes, selected revision,
    own cited section, and shared cited section are all unchanged.
    """
    subject = _Subject(tmp_path, None).designed()
    _blue_design(subject)
    authority = "docs/feature/atomic-selected-acceptance/architecture/brief.md"
    subprocess.run(["git", "-C", str(subject.root), "add", authority], check=True)
    subprocess.run(
        ["git", "-C", str(subject.root), "commit", "-qm", "bind value designs"],
        check=True,
    )
    subject.select("blue")
    assert subject.oracle("blue")[0] == 0
    assert subject.craft("blue")[0] == 0
    subject.complete_second_value()
    subprocess.run(["git", "-C", str(subject.root), "add", authority], check=True)
    subprocess.run(
        ["git", "-C", str(subject.root), "commit", "-qm", "add value two design"],
        check=True,
    )
    # Completing value 2 establishes its DESIGN section.  B is then explicitly
    # realigned against the complete two-value design before its evidence is
    # recorded for this observation.
    subject.select("blue", replace=True)
    assert subject.oracle("blue")[0] == 0
    assert subject.craft("blue")[0] == 0
    assert _labels_of(subject.state()) == {"oracle": "recorded", "craft": "recorded"}
    turns_before = len(subject.rows())

    visible = _value_manifest()
    visible["authority"] = {"heading": "Visible widget color"}
    visible["decisions"] = ["Value two reads the selection back after revision."]
    visible["oracle"] = SECOND_ORACLE
    visible["verification"] = [
        ["pytest", "-q", SECOND_ORACLE.split("::", maxsplit=1)[0]]
    ]
    code, out, err = _call(
        subject.root,
        "design",
        json.dumps(visible),
        value=2,
        replace_current=True,
    )
    assert code == 0, out + err
    subprocess.run(["git", "-C", str(subject.root), "add", authority], check=True)
    subprocess.run(
        ["git", "-C", str(subject.root), "commit", "-qm", "revise value two design"],
        check=True,
    )

    assert _labels_of(subject.state()) == {"oracle": "recorded", "craft": "recorded"}, (
        "WHAT: value 1 reads other than recorded after only value 2's cited "
        "DESIGN section changed. WHY: an unrelated authority revision must not "
        "invalidate byte-identical value-1 evidence. HOW: compare each turn's "
        "owned-path tree and selected revision with only value 1's own and "
        "shared cited DESIGN-section identities."
    )
    assert len(subject.rows()) == turns_before, (
        "WHAT: changing value 2 replayed a value-1 provider turn. WHY: value "
        "1 evidence remains current and must be reused. HOW: keep unrelated "
        "section identity out of value 1's turn-currentness record."
    )


def _provider_facts(decision: str) -> dict[str, object]:
    """Typed facts a provider returns for value 1 of the standard subject."""
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "typed facts",
            "design_facts": {
                "targets": [
                    {
                        "path": "src/widget.py",
                        "decision": "EXTEND",
                        "reason": "Widget already owns color.",
                    }
                ],
                "paradigm": "object_oriented",
                "decisions": [decision],
                "oracle": DESIGN_ORACLE,
                "acceptance_supports": [],
                "verification": [
                    ["pytest", "-q", DESIGN_ORACLE.split("::", maxsplit=1)[0]]
                ],
                "oracle_verification_index": 0,
            },
        }
    }


def _provider_design(subject: _Subject, facts: dict[str, object]):
    return subject.step(
        "design",
        "--repo-root",
        str(subject.root),
        "--value",
        "1",
        "--finding",
        "-",
        answers=[facts],
        stdin="a downstream finding",
    )


@pytest.mark.parametrize(
    ("identity", "decision"),
    (
        ("known", "CHANGED decision: validate at the boundary."),
        # the same typed projection is still not a full semantic no-op
        ("known", "Value one keeps color validation at construction."),
        ("historical-null", "CHANGED decision: validate at the boundary."),
    ),
)
def test_provider_design_change_keeps_b_and_needs_explicit_realignment(
    tmp_path: Path, node_executable: str, identity: str, decision: str
) -> None:
    subject = _Subject(tmp_path, node_executable, shared=False).designed()
    if identity == "historical-null":
        _seed_legacy_design_identity(subject)
    subject.select("green")
    kept = _acceptance_keys(subject.root)

    code, out, err = _provider_design(subject, _provider_facts(decision))
    assert code == 0, (
        "WHAT: a provider DESIGN over a selected revision was refused or lost. "
        f"WHY: provider facts carry no full-input identity. HOW: bind them, "
        f"clear the identity and keep B for explicit realignment ({out + err})"
    )
    value = json.loads(subject.bytes())["values"][0]
    assert "design_semantic_sha256" not in value
    assert _acceptance_keys(subject.root) == kept, "B's bytes must be preserved"

    seen = len(subject.rows())
    code, out, err, _ = subject.oracle("green")
    assert code != 0 and "SelectedRevisionRealignmentNeeded" in out + err
    assert "--replace-current" in out + err and "schema_version 2" in out + err
    assert len(subject.rows()) == seen, "a misaligned selection bought a turn"


@pytest.mark.parametrize(
    "verification",
    (
        [["pytest", "-q", DESIGN_ORACLE.split("::", maxsplit=1)[0], "\x00"]],
        [["pytest", "-q", "tests/x.py"], ["pytest", "-q", "tests/x.py"]],
    ),
    ids=("NUL-token", "duplicate-whole-argv"),
)
def test_provider_design_with_invalid_argv_is_refused_without_a_write(
    tmp_path: Path, verification: list[list[str]]
) -> None:
    subject = _Subject(tmp_path, None, shared=False).designed()
    before = subject.bytes()
    facts = _provider_facts("Value one keeps color validation at construction.")
    facts["structured_output"]["design_facts"]["verification"] = verification  # type: ignore[index]
    code, out, err = _provider_design(subject, facts)
    assert code != 0 and "DesignFactsMalformed" in out + err, (
        "WHAT: provider facts with a NUL token or a repeated whole argv were "
        "not refused as DesignFactsMalformed. WHY: they are not native argv. "
        "HOW: apply native_verification_defect to provider facts."
    )
    assert subject.bytes() == before


def test_distill_accepts_repeated_argv_tokens_and_keeps_them(tmp_path: Path) -> None:
    root = base_repository(tmp_path / "repository")
    _prepare(root)
    argv = [sys.executable, "-m", "pytest", "-q", "-q", "tests/acceptance/x.py"]
    code, out, err = _call(root, "distill", _v2_with(verification=[argv]))
    assert code == 0, out + err
    kept = json.loads(_acceptance_keys(root)["acceptance_verification"])
    assert kept == [argv]


def test_verified_candidate_binds_every_authority_byte_and_refuses_unreadable_authority(
    tmp_path: Path, node_executable: str
) -> None:
    """A single changed authority byte (prose no fact projects) makes the record
    not current and builds a NEW candidate containing it; identical bytes keep
    the record; an unreadable authority never reuses one."""
    subject = _Subject(tmp_path, node_executable).designed()
    subject.select("green")
    _assert_authority_bytes_bind_candidate(subject, subject.through("green"))


def _assert_authority_bytes_bind_candidate(subject: _Subject, first: dict) -> None:
    path, _ = subject.evidence(first)
    kept = path.read_bytes()
    DOC = "docs/feature/atomic-selected-acceptance/acceptance/brief.md"
    document = subject.root / DOC
    original = document.read_bytes()

    def verify_text() -> tuple[int, str, str]:
        return run_cli_in_process(
            ["verify", "--repo-root", str(subject.root)],
            cwd=subject.root,
            env=subject.native,
            catch_all=True,
        )

    code, out, err = verify_text()
    assert code == 0 and "RECORDED" in out + err, (
        "WHAT: byte-identical authorities did not reuse the record. WHY: the key "
        "is bound to authority bytes only. HOW: print RECORDED and run no command."
    )
    assert block(out, err)["CANDIDATE"] == first["CANDIDATE"]

    document.write_bytes(original + b"\nProse no fact projects.\n")
    code, out, err = verify_text()
    assert code == 0 and "RECORDED" not in out + err, (
        "WHAT: a changed authority byte reused the earlier record. WHY: the "
        "authority determines declared commands and handoff. HOW: key the "
        "upstream ref on the bound authority bytes."
    )
    second = block(out, err)
    assert second["CANDIDATE"] != first["CANDIDATE"]
    assert second["NATIVE-EVIDENCE"] != first["NATIVE-EVIDENCE"]
    shown = subprocess.run(
        ["git", "-C", str(subject.root), "show", f"{second['CANDIDATE']}:{DOC}"],
        capture_output=True,
    )
    assert shown.stdout == document.read_bytes(), (
        "WHAT: the new candidate lacks the changed authority bytes. WHY: an "
        "authority-only delta must not collapse to the bare base. HOW: stage "
        "the bound authority documents into the candidate."
    )
    assert path.read_bytes() == kept, "earlier native evidence was rewritten"
    assert "current" not in _labels(subject.page("old"), first["NATIVE-EVIDENCE"])

    document.write_bytes(original)
    code, out, err = verify_text()
    assert (code == 0 and block(out, err)["CANDIDATE"] == first["CANDIDATE"]) or (
        code == 0 and "RECORDED" in out + err
    ), "restoring identical authority bytes must reuse evidence"

    document.unlink()
    document.symlink_to(subject.root / "src" / "widget.py")
    code, out, err = verify_text()
    assert code != 0 and "AcceptanceEvidenceUnavailable" in out + err
    assert "restore immutable acceptance evidence" in out + err
    assert path.read_bytes() == kept


def test_uncommitted_des_authority_keeps_evidence_measurable(tmp_path: Path) -> None:
    """A DES-authored authority stays measurable before it is ever committed.

    Law: record currentness depends on the confined, readable cited section,
    never on Git tracking. Drives `des discuss`/`des design` (never git-added),
    `des oracle`, `des craft` and `des state` through the public CLI; then
    renames the cited heading away in the still-uncommitted document and reads
    the same `des state`, proving the negative direction from one stimulus.
    """
    subject = _Subject(tmp_path, None).designed()
    value = _stored(subject.root).values[0]
    locator = value.authority.authority_locator
    assert locator is not None and "#" in locator, (
        "WHAT: the designed value carries no `<document>#<heading>` locator. "
        "WHY: this oracle measures a cited DESIGN section. HOW: bind the value "
        "through `des design` before measuring it."
    )
    document_path, _, heading = locator.partition("#")
    document = subject.root / document_path

    def tracked() -> bool:
        return (
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(subject.root),
                    "ls-files",
                    "--error-unmatch",
                    document_path,
                ],
                capture_output=True,
                text=True,
            ).returncode
            == 0
        )

    assert document.is_file() and not tracked(), (
        "WHAT: the authority `des design` published is missing or already "
        "git-tracked. WHY: the law concerns an uncommitted DES-constructed "
        "authority. HOW: keep the document on disk without git add/commit."
    )

    oracle_path, _, oracle_function = value.authority.oracle.partition("::")
    code, out, err = subject.step(
        "oracle",
        "--repo-root",
        str(subject.root),
        "--value",
        "1",
        answers=[
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "authored a red acceptance oracle",
                },
                "writes": {
                    oracle_path: (
                        "from pathlib import Path\n\n\n"
                        f"def {oracle_function}():\n"
                        "    root = Path(__file__).resolve().parents[2]\n"
                        "    product = root / 'src' / 'widget.py'\n"
                        "    text = product.read_text() if product.exists() else ''\n"
                        "    assert 'BLUE = 1' in text, 'the widget does not report blue'\n"
                    )
                },
            },
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "the oracle set is admissible",
                }
            },
        ],
    )
    assert code == 0, out + err
    code, out, err = subject.step(
        "craft",
        "--repo-root",
        str(subject.root),
        "--value",
        "1",
        answers=[
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "implemented the value behind its oracle",
                },
                "writes": {"src/widget.py": "BLUE = 1\n"},
            }
        ],
    )
    assert code == 0, out + err
    assert not tracked(), "the authority must stay uncommitted through oracle/craft"

    recorded = subject.state()
    assert "oracle=recorded craft=recorded" in recorded, (
        f"WHAT: `des state` reported {recorded!r}, not 'oracle=recorded "
        "craft=recorded', for an untracked readable authority. WHY: evidence "
        "must be measurable before the authority is integrated. HOW: resolve "
        "the cited section from confined worktree text, never from git tracking."
    )
    readable = document.read_text(encoding="utf-8")
    assert f"## {heading}" in readable, "the cited heading must resolve"

    document.write_text(
        readable.replace(f"## {heading}", f"## {heading} renamed"), encoding="utf-8"
    )
    assert not tracked(), "the document stays uncommitted after the rename"
    moved = subject.state()
    assert "oracle=uncertain craft=uncertain" in moved, (
        f"WHAT: `des state` reported {moved!r} after the cited heading was "
        "renamed away, not 'oracle=uncertain craft=uncertain'. WHY: an "
        "unresolvable cited section is unmeasurable, never current or "
        "historical. HOW: answer None for the whole cited set and label both "
        "records uncertain."
    )

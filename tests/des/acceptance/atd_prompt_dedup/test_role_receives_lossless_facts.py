"""Receiving roles retain facts once, rather than receiving duplicate snapshots.

Driving port: des.cli.__main__:main / python -m des handoff prompt.
@contract-shape: real-io. No production helper supplies expected facts.

Preservation map: generated cases call the same dispatcher, read the same native
snapshot format, use the same renderer/composer, and decode the same captured
stdout as the process journey. Only the interpreter fork is omitted. The
independent oracle is the acceptance-owned input and its explicitly declared
raw/effective/projected meaning, not a second prompt renderer.

Dependencies and discovery belong to pyproject.toml and uv.lock: pytest and
Hypothesis in the existing dev group, src on pythonpath, native des entry point.
Generation bounds (30 examples, depth 3, 5 children, 80-character leaves) are
verification bounds, not product restrictions. Hypothesis supplies shrinking,
replay and failure blobs; execution and a demonstrated shrink remain the
verification owner's responsibility.

The frozen run5 observation is a separate real-boundary refusal observation.
It retains the original bytes and never substitutes a normalized fixture.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import pytest
from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st
from tests.des._helpers.host_facts import design_manifest
from tests.des.architect_handoff.tests.test_g10 import fixture_context

from des.cli.__main__ import main
from des.domain.design_document import DesignDocument


CHECKOUT = Path(__file__).resolve().parents[4]
FIXTURE = Path(__file__).resolve().with_name("fixture")
TEMPLATES = CHECKOUT / "nWave/templates/architect-handoff"
SKILLS = CHECKOUT / "nWave/skills"
STATE = Path(".nwave/des/handover.json")
PACKET_MARKER = "=== [C] orchestrator ===\nnative_input: "
UNASSESSED_SECTION = {
    "UNASSESSED": "this handoff has no such section; do not read this as not applicable"
}
ABSENT_PUBLIC_ORACLE = "UNASSESSED: no public oracle supplied"
ABSENT_OPERATIONS = "UNASSESSED: no operational authority supplied to this prompt; root must supply any applicable operational input"
SHARED_COMMAND = ["env", "-u", "CI", "python3", "-m", "des", "handoff", "describe"]
RUN5 = FIXTURE / "run5"
RUN5_ROOT = RUN5 / "root.txt"


class Role(StrEnum):
    ARCHITECT = "nw-solution-architect"
    DESIGNER = "nw-acceptance-designer"
    CRAFTER = "nw-software-crafter"
    REVIEWER = "nw-software-crafter-reviewer"
    EXAMINER = "nw-user-examiner"


class MissingInput(StrEnum):
    SNAPSHOT = "missing snapshot"
    MALFORMED_SNAPSHOT = "malformed snapshot"
    ROOT = "missing caller input"
    BLANK_ROOT = "blank caller input"
    TEMPLATE = "missing explicit template"
    TEMPLATE_SHAPE = "inconsistent strict template shape"
    DESIGN = "unbound selected design"


@dataclass(frozen=True)
class NativeOutput:
    exit: int
    stdout: bytes
    stderr: bytes

    def successful_text(self) -> str:
        assert self.exit == 0, (
            f"WHAT: admitted native prompt exited {self.exit}, stderr={self.stderr!r}. "
            "WHY: an input/runner failure is not the intended ownership RED. "
            "HOW: restore the admitted native fixture and declared runtime before measuring the semantic assertion."
        )
        return self.stdout.decode("utf-8")


@dataclass(frozen=True)
class FactContent:
    tree: object

    @property
    def text(self) -> str:
        return json.dumps(
            self.tree, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )


@dataclass(frozen=True)
class CallerText:
    text: str


@dataclass(frozen=True)
class PromptInput:
    repository: Path
    role: Role
    position: int | None = None
    extra: tuple[str, ...] = ()
    root_context: Path = Path("root.txt")

    def argv(self) -> list[str]:
        args = [
            "handoff",
            "prompt",
            "--repo-root",
            str(self.repository),
            "--role",
            self.role.value,
            "--root-context",
            str(self.root_context),
            "--template-dir",
            str(TEMPLATES),
            "--skills-dir",
            str(SKILLS),
        ]
        if self.position is not None:
            args += ["--value", str(self.position)]
        return [*args, *self.extra]


def _environment() -> dict[str, str]:
    # Retain the root conftest's Git isolation, but never inherit CI or a foreign
    # Python import path. Child imports come from their selected checkout.
    environment = dict(os.environ)
    environment.pop("CI", None)
    environment.pop("PYTEST_ADDOPTS", None)
    environment["PYTHONPATH"] = "src"
    return environment


def _native(args: list[str], *, process: bool = False) -> NativeOutput:
    if process:
        result = subprocess.run(
            [sys.executable, "-m", "des", *args],
            cwd=CHECKOUT,
            env=_environment(),
            capture_output=True,
            check=False,
        )
        return NativeOutput(result.returncode, result.stdout, result.stderr)
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_status = main(args)
    return NativeOutput(
        exit_status,
        stdout.getvalue().encode("utf-8"),
        stderr.getvalue().encode("utf-8"),
    )


def _message(what: str, why: str, how: str) -> str:
    return f"WHAT: {what}. WHY: {why}. HOW: {how}."


def _write_snapshot(root: Path, snapshot: dict) -> None:
    path = root / STATE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def _snapshot(root: Path) -> dict:
    return json.loads((root / STATE).read_bytes())


def _leaves(value: object):
    if isinstance(value, dict):
        for child in value.values():
            yield from _leaves(child)
    elif isinstance(value, list):
        for child in value:
            yield from _leaves(child)
    else:
        yield value


def _reference_ids(value: object):
    if isinstance(value, dict):
        if set(value) == {"ref"}:
            yield value["ref"]
        else:
            for child in value.values():
                yield from _reference_ids(child)
    elif isinstance(value, list):
        for child in value:
            yield from _reference_ids(child)


def _raw_population(snapshot: dict, position: int | None) -> dict:
    """Product identity remains distinct from the one selected fact carrier."""
    population = copy.deepcopy(snapshot)
    population.pop("architect_receipts", None)
    population["values"] = [
        {
            name: value.get(name)
            for name in ("observation", "dependencies", "design_semantic_sha256")
        }
        for value in population["values"]
    ]
    if "shared_design" in population:
        population["shared_design"].pop("design")
    if position is not None:
        population["values"] = [population["values"][position - 1]]
    return population


def _projection_population(
    snapshot: dict, role: Role, position: int | None
) -> list[dict]:
    # These fixtures deliberately declare only not_applicable sections. Their
    # expected content is the authored reason; an omitted consumed kind has the
    # separately specified UNASSESSED observation. No model/view algorithm is
    # copied, and no production projection function is imported.
    views = {
        Role.ARCHITECT: dict.fromkeys(
            ("laws", "construction", "model", "closure", "scenarios"),
            "full",
        ),
        Role.DESIGNER: {
            "laws": "full",
            "construction": "full",
            "model": "falsifiers",
            "closure": "axes",
        },
        Role.CRAFTER: {"laws": "owned", "construction": "owned", "model": "interface"},
        Role.REVIEWER: {
            "laws": "full",
            "construction": "full",
            "model": "interface",
            "closure": "axes",
        },
    }[role]
    sections = []
    if "shared_design" in snapshot and position is None:
        sections += (
            snapshot["shared_design"]["design"]
            .get("architect_handoff", {})
            .get("sections", [])
        )
    for value in snapshot["values"]:
        sections += value["authority"].get("architect_handoff", {}).get("sections", [])
    expected = {}
    for section in sections:
        kind, scope = section["kind"], section["scope"]
        if kind not in views or (
            position is not None and scope not in ("shared", f"value:{position}")
        ):
            continue
        content = {"not_applicable": section["status"]["reason"]}
        digest = hashlib.sha256(
            json.dumps(
                content, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        expected[(kind, scope)] = {
            "kind": kind,
            "scope": scope,
            "view": views[kind],
            "sha256": digest,
            "content": content,
        }
    for kind, view in views.items():
        expected.setdefault(
            (kind, "shared"),
            {
                "kind": kind,
                "scope": "shared",
                "view": view,
                "sha256": "-",
                "content": dict(UNASSESSED_SECTION),
            },
        )
    return [expected[key] for key in sorted(expected)]


def _effective_population(snapshot: dict, position: int) -> dict:
    """Own references and the explicitly selected shared command stay separate."""
    declaration = snapshot["values"][position - 1]["authority"]
    expected = copy.deepcopy(declaration)
    expected.pop("facts")
    expected.pop("architect_handoff")
    inherited = bool(declaration["inherits"])
    expected.update(
        authority=declaration["authority_locator"],
        acceptance_supports=["root.txt"]
        if inherited
        else declaration["acceptance_supports"],
        verification=[
            *declaration["verification"],
            *([SHARED_COMMAND] if inherited else []),
        ],
        required_verification=[SHARED_COMMAND] if inherited else [],
    )
    return expected


def _literal_free(prompt: str, root: str, opaque: str | None = None) -> str:
    # Only the observer excludes known caller-owned literal segments. The SUT
    # must preserve them, even if they look like packet or projection syntax.
    for label, literal in (("ROOT", root), ("opaque instructions", opaque)):
        if literal is None:
            continue
        occurrences = [
            match.start() for match in re.finditer(re.escape(literal), prompt)
        ]
        assert len(occurrences) == 1, _message(
            f"the supplied {label} segment has carrier positions {occurrences}, expected one",
            "literal inputs must survive exactly once without stripping or substitution",
            "route ROOT from actual substitution ownership and preserve opaque instruction bytes",
        )
        prompt = prompt.replace(literal, "", 1)
    return prompt


def _packet_and_other_text(
    prompt: str, root: str, opaque: str | None = None
) -> tuple[dict, str]:
    visible = _literal_free(prompt, root, opaque)
    carriers = [
        match.start() for match in re.finditer(re.escape(PACKET_MARKER), visible)
    ]
    assert len(carriers) == 1, _message(
        f"native_input carrier population is {carriers}, expected exactly one",
        "the receiving role requires one canonical software-generated fact packet",
        "emit one JSON packet in the native caller block",
    )
    start = carriers[0] + len(PACKET_MARKER)
    try:
        packet, length = json.JSONDecoder().raw_decode(visible[start:])
    except ValueError as error:
        pytest.fail(
            _message(
                f"native_input is not decodable JSON: {error}",
                "missing future behavior must fail a public observation, not an import or setup",
                "serialize the complete path-addressed packet at the declared public carrier",
            )
        )
    assert isinstance(packet, dict), _message(
        f"native_input has type {type(packet).__name__}, expected an object",
        "semantic paths must remain addressable",
        "emit the declared structured packet rather than prose or a truncated payload",
    )
    return packet, visible[:start] + visible[start + length :]


def _assert_sole_carrier(other_text: str) -> None:
    duplicate_objects = []
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", other_text):
        try:
            value, _ = decoder.raw_decode(other_text[match.start() :])
        except ValueError:
            continue
        if isinstance(value, dict) and set(value).intersection(
            {
                "request",
                "scope",
                "values",
                "shared_design",
                "product_authority",
                "architect_projection",
                "selected_authority",
            }
        ):
            duplicate_objects.append(sorted(value))
    projected_carriers = re.findall(r"^=== \[H\] .*$", other_text, flags=re.MULTILINE)
    assert not duplicate_objects and not projected_carriers, _message(
        f"outside native_input, fact-object carriers={duplicate_objects}, projection carriers={projected_carriers}",
        "FROM DES/native_input/projected displays must not carry the same software-owned facts repeatedly",
        "keep all facts in native_input, substitute navigation references in named templates, and emit no separate projection rows",
    )


def _assert_facts(
    prompt: str, subject: PromptInput, snapshot: dict, *, opaque: str | None = None
) -> dict:
    root = (subject.repository / subject.root_context).read_bytes().decode("utf-8")
    packet, other_text = _packet_and_other_text(prompt, root, opaque)
    # This is the primary defect assertion. It deliberately precedes checks for
    # the future selected_authority field, so old successful product output dies
    # to duplicated carriers, not to a missing import/interface or fixture error.
    _assert_sole_carrier(other_text)
    raw = _raw_population(snapshot, subject.position)
    received_raw = {name: packet.get(name) for name in raw}
    assert received_raw == raw, _message(
        f"scoped raw population differs: expected={raw!r}, actual={received_raw!r}",
        "raw declarations, dependencies, equal independent values and provenance are independent semantic facts",
        "preserve every admitted raw path, removing only the declared raw handoff/receipt presentations",
    )
    expected_projection = _projection_population(
        snapshot, subject.role, subject.position
    )
    assert packet.get("architect_projection") == expected_projection, _message(
        f"projection population differs: expected={expected_projection!r}, actual={packet.get('architect_projection')!r}",
        "consumed content, ordered identities, full hashes, reasons and explicit missing-section markers must survive",
        "retain the complete existing consumer projection in the canonical packet without broadening role views",
    )
    if subject.position is not None:
        expected_effective = _effective_population(snapshot, subject.position)
        assert packet.get("selected_authority") == expected_effective, _message(
            f"effective population differs: expected={expected_effective!r}, actual={packet.get('selected_authority')!r}",
            "the receiving role needs the resolved selection as well as the distinct raw declarations",
            "retain effective supports/required commands, all typed selection fields, and explicit absence semantics",
        )
        inherited = bool(
            snapshot["values"][subject.position - 1]["authority"]["inherits"]
        )
        expected_records = (
            {
                record["id"]: record
                for record in snapshot["shared_design"]["design"][
                    "architectural_tests"
                ]["obligations"]
            }
            if inherited
            else {}
        )
        assert packet["inherited_records"] == expected_records, _message(
            f"inherited records differ: expected={expected_records!r}, actual={packet['inherited_records']!r}",
            "L-resolve-retains preserves every selected shared record without copying unrelated records",
            "resolve the selected inherits ids and emit their complete records once",
        )
        expected_shared_verification = {"0": SHARED_COMMAND} if inherited else {}
        assert packet["shared_verification"] == expected_shared_verification, _message(
            f"shared verification differs: expected={expected_shared_verification!r}, actual={packet['shared_verification']!r}",
            "inherited indexes select the shared argv, not the value's own verification list",
            "retain the selected shared indexes and their original commands",
        )
        invocation = packet.get("invocation")
        invocation_values = (
            list(_leaves(invocation)) if isinstance(invocation, dict) else []
        )
        assert str(subject.repository.resolve()) in invocation_values and (
            subject.position in invocation_values
            or str(subject.position) in invocation_values
        ), _message(
            f"invocation lacks the original repository/one-based position: {invocation!r}",
            "a scoped packet must not silently renumber a later selected value",
            "retain the original invocation parameters independently of the scoped values array",
        )
    declarations = [
        *(value["authority"] for value in snapshot["values"]),
        *([snapshot["shared_design"]["design"]] if "shared_design" in snapshot else []),
    ]
    definitions = {
        record["id"]: record["text"]
        for declaration in declarations
        for record in declaration["facts"]
    }
    record_ids = {
        record["id"]
        for declaration in declarations
        for kind, member in (
            ("architectural_tests", "obligations"),
            ("contract_tests", "obligations"),
            ("agreement_analysis", "parties"),
        )
        for record in declaration[kind].get(member, [])
    }
    for declaration in declarations:
        for section in declaration["architect_handoff"]["sections"]:
            payload = section["status"].get("payload", {})
            for member in ("laws", "refuted", "claims", "models"):
                record_ids.update(record["id"] for record in payload.get(member, []))
            record_ids.update(
                record["subject"]["ref"] for record in payload.get("closures", [])
            )
    roots = {
        name: packet.get(name, {})
        for name in (
            "selected_authority",
            "inherited_records",
            "shared_verification",
            "architect_projection",
        )
    }
    expected_catalog = {}
    for identifier in _reference_ids(roots):
        assert identifier in definitions or identifier in record_ids, _message(
            f"the receiving-role packet references undeclared id {identifier}",
            "an unresolved fact is not an inherited record or assessed absence",
            "retain a reference to an independently declared fact or record",
        )
        if identifier in definitions:
            expected_catalog[identifier] = definitions[identifier]
    assert packet["facts"] == expected_catalog, _message(
        f"reachable catalog differs: expected={expected_catalog!r}, actual={packet['facts']!r}",
        "L-catalog-once requires exactly the facts reachable through the four declared roots",
        "retain every reachable definition and exclude unselected definitions",
    )
    assert all(
        text not in list(_leaves(roots)) for text in expected_catalog.values()
    ), _message(
        f"catalog text escaped into reference roots: roots={roots!r}, catalog={expected_catalog!r}",
        "selected authority and inherited/projected records carry references, not parallel prose definitions",
        "replace duplicated root text with the corresponding FactRef",
    )
    return packet


def _assert_repeat(first: NativeOutput, second: NativeOutput) -> None:
    second.successful_text()
    assert first.stdout == second.stdout, _message(
        f"paired stdout differs: lengths={len(first.stdout)}/{len(second.stdout)}, hashes="
        f"{hashlib.sha256(first.stdout).hexdigest()}/{hashlib.sha256(second.stdout).hexdigest()}",
        "unchanged explicit inputs must produce byte-identical complete prompts",
        "make packet construction, references, projection order and assembly deterministic without truncation",
    )


def _assert_instruction_contract(
    prompt: str, subject: PromptInput, template_name: str, phase: str | None = None
) -> None:
    supplied = (TEMPLATES / f"{template_name}.tmpl").read_text(encoding="utf-8")
    heading = "## SUBMIT" if subject.role is Role.ARCHITECT else "## TASK (template)"
    instructions = supplied[supplied.index(heading) :].split("## FROM THE ROOT", 1)[0]
    if subject.role is Role.ARCHITECT:
        commands = [
            [
                "des",
                "design",
                "--repo-root",
                str(subject.repository.resolve()),
                "--shared",
                "--input",
                "-",
            ]
        ]
        commands += [
            [
                "des",
                "design",
                "--repo-root",
                str(subject.repository.resolve()),
                "--value",
                str(position),
                "--input",
                "-",
            ]
            for position in range(1, len(_snapshot(subject.repository)["values"]) + 1)
        ]
        instructions = instructions.replace(
            "{{submit_steps|bullets}}",
            "\n".join("- " + shlex.join(command) for command in commands),
        )
    instructions = instructions.replace(
        "{{repo_root}}", str(subject.repository.resolve())
    )
    instructions = instructions.replace("{{value}}", str(subject.position))
    if phase is not None:
        instructions = instructions.replace("{{phase}}", phase)
    assert instructions in prompt, _message(
        "the supplied task/return or host-submission instruction segment changed",
        "fact deduplication must not alter role permissions, return schemas or actual invocation instructions",
        "leave instruction inputs intact and replace only authority-bearing template slots with references",
    )


class ReceivingRoleJourney:
    def __init__(self, temporary_root: Path):
        self.temporary_root = temporary_root

    def _current_fixture(self, root: Path) -> dict:
        """Build this fixture's declared current scopes; frozen files stay untouched."""
        snapshot = _snapshot(root)
        declarations = [(None, snapshot["shared_design"]["design"])]
        declarations += [
            (index, value["authority"])
            for index, value in enumerate(snapshot["values"], 1)
        ]
        for position, source in declarations:
            declaration = copy.deepcopy(source)
            label = "SHARED" if position is None else f"VALUE_{position}"
            handoff, catalog, _retired = fixture_context(
                declaration["architect_handoff"]
            )
            declaration["architect_handoff"] = handoff
            declaration["facts"] = [
                {"id": record.id, "text": record.text} for record in catalog.records
            ]
            declaration["constraints"] = declaration.pop("obligations")
            declaration["purpose"] = f"{label}_PURPOSE_FACT"
            declaration["boundaries"] = {
                "applicability": "not_applicable",
                "reason": f"{label}_BOUNDARY_FACT",
            }
            for target in declaration["targets"]:
                target["reason"] = f"{label}_TARGET_FACT"
            declaration["public_oracle"] = {
                "observation": f"{label}_PUBLIC_FACT",
                "stimulus": f"{label}_STIMULUS_FACT",
                "expected": f"{label}_EXPECTED_FACT",
                "falsifier": f"{label}_FALSIFIER_FACT",
            }
            if position is not None:
                declaration["architectural_tests"] = {
                    "applicability": "applicable",
                    "obligations": [],
                }
                declaration["inherits"] = [{"ref": "V0-architectural_tests-1"}]
            manifest = design_manifest(
                declaration, declaration["purpose"], position or 0
            )
            document = DesignDocument.from_json(
                json.dumps(manifest), value=position or 1, shared=position is None
            )
            locator = "docs/design.md#" + document.heading
            current = json.loads(document.facts_json(document.facts_at(locator)))
            if position is None:
                snapshot["shared_design"].update(
                    authority_locator=locator,
                    semantic_sha256=document.semantic_sha256,
                    section_sha256=hashlib.sha256(
                        document.markdown().encode()
                    ).hexdigest(),
                    design=current,
                )
            else:
                snapshot["values"][position - 1]["authority"] = current
                snapshot["values"][position - 1]["design_semantic_sha256"] = (
                    document.semantic_sha256
                )
        _write_snapshot(root, snapshot)
        return snapshot

    def _copy_input(self, destination: Path) -> None:
        shutil.copytree(FIXTURE, destination)
        # Keep tracked text fixtures whitespace-clean; restore their deliberate
        # trailing-space inputs only in each disposable runtime fixture.
        for name in ("root.txt", "instructions.txt"):
            path = destination / name
            content = path.read_bytes()
            boundary = len(content.rstrip(b"\n"))
            path.write_bytes(content[:boundary] + b"  " + content[boundary:])
        self._current_fixture(destination)

    def defaults_receive_complete_facts_once(self) -> None:
        root = self.temporary_root / "current-input"
        self._copy_input(root)
        snapshot = _snapshot(root)
        for role, position, template in (
            (Role.DESIGNER, 1, "oracle.atd-v3"),
            (Role.ARCHITECT, None, "design.architect-v9"),
        ):
            subject = PromptInput(root.resolve(), role, position)
            before = (root / STATE).read_bytes()
            first = _native(subject.argv(), process=True)
            text = first.successful_text()
            _assert_facts(text, subject, snapshot)
            _assert_instruction_contract(text, subject, template)
            _assert_repeat(first, _native(subject.argv(), process=True))
            assert (root / STATE).read_bytes() == before, _message(
                "prompt rendering changed its supplied snapshot",
                "rendering is an observation, not an authority or lifecycle mutation",
                "keep prompt construction read-only",
            )

    def generated_facts_remain_independently_addressable(
        self, content: FactContent
    ) -> None:
        # Every finite disposition is constructed on every broad content sample;
        # no branch depends on random discovery of a rare absence or equality.
        for inherited, public_present in (
            (True, True),
            (True, False),
            (False, True),
            (False, False),
        ):
            with tempfile.TemporaryDirectory(dir=self.temporary_root) as directory:
                root = Path(directory) / "input"
                self._copy_input(root)
                snapshot = _snapshot(root)
                predecessor = snapshot["values"][0]
                predecessor["observation"] = "PREDECESSOR_FACT"
                selected = copy.deepcopy(predecessor)
                definitions = selected["authority"]["facts"]
                identifiers = {
                    record["id"]: "V2-" + record["id"] for record in definitions
                }

                def selected_references(value, *, identifiers=identifiers):
                    if isinstance(value, dict):
                        if set(value) == {"ref"} and value["ref"] in identifiers:
                            value["ref"] = identifiers[value["ref"]]
                        else:
                            for child in value.values():
                                selected_references(child)
                    elif isinstance(value, list):
                        for child in value:
                            selected_references(child)

                selected_references(selected["authority"])
                for record in definitions:
                    record["id"] = identifiers[record["id"]]
                    record["text"] = "SELECTED_FACT:" + record["text"]
                marker = "INDEPENDENT_EQUAL_FACT:" + content.text
                snapshot["request"] = marker
                selected["observation"] = marker
                selected["dependencies"] = [predecessor["observation"]]
                selected["authority"]["authority_locator"] = "docs/design.md#Value 2"
                selected["authority"]["decisions"] = [{"ref": "V2-generated"}]
                selected["authority"]["facts"].append(
                    {
                        "id": "V2-generated",
                        "text": "CATALOG_DECISION_FACT:" + content.text,
                    }
                )
                selected["authority"]["architect_handoff"]["sections"][0]["scope"] = (
                    "value:2"
                )
                selected["authority"]["architect_handoff"]["sections"][0]["status"][
                    "reason"
                ] = {"ref": "V2-projection"}
                selected["authority"]["facts"].append(
                    {"id": "V2-projection", "text": "PROJECTED_FACT:" + content.text}
                )
                if public_present:
                    selected["authority"]["public_oracle"] = {
                        "observation": {"ref": "V2-public"},
                        "stimulus": selected["authority"]["public_oracle"]["stimulus"],
                        "expected": {"ref": "V2-generated"},
                        "falsifier": selected["authority"]["public_oracle"][
                            "falsifier"
                        ],
                    }
                    selected["authority"]["facts"].append(
                        {"id": "V2-public", "text": "PUBLIC_FACT:" + content.text}
                    )
                snapshot["values"].append(selected)
                if not inherited:
                    snapshot["scope"] = {"kind": "project"}
                    snapshot.pop("shared_design")
                    predecessor["authority"]["inherits"] = []
                    predecessor["authority"]["architectural_tests"] = {
                        "applicability": "not_applicable",
                        "reason": {"ref": "V1-architecture"},
                    }
                    predecessor["authority"]["facts"].append(
                        {
                            "id": "V1-architecture",
                            "text": "No predecessor architecture check.",
                        }
                    )
                    selected["authority"]["inherits"] = []
                    selected["authority"]["architectural_tests"] = {
                        "applicability": "not_applicable",
                        "reason": {"ref": "V2-architecture"},
                    }
                    selected["authority"]["facts"].append(
                        {
                            "id": "V2-architecture",
                            "text": "No inherited architecture check.",
                        }
                    )
                # Materialize valid typed authorities through the public producer,
                # including its optional-field shape and canonical field order.
                for position, value in enumerate(snapshot["values"], 1):
                    authority = value["authority"]
                    locator = authority["authority_locator"]
                    manifest = {
                        name: field
                        for name, field in authority.items()
                        if name != "authority_locator" and field is not None
                    }
                    document = DesignDocument.from_json(
                        json.dumps(manifest, ensure_ascii=False),
                        value=position,
                    )
                    materialized = json.loads(
                        document.facts_json(document.facts_at(locator))
                    )
                    assert materialized == authority, _message(
                        "canonical materialization changed a generated authority fact",
                        "field ordering must not replace or coalesce independent input paths",
                        "preserve the complete authored fact/reference population",
                    )
                    value["authority"] = materialized
                    value["design_semantic_sha256"] = document.semantic_sha256
                if not public_present:
                    snapshot["values"][1]["authority"]["public_oracle"] = None
                _write_snapshot(root, snapshot)
                subject = PromptInput(
                    root,
                    Role.DESIGNER,
                    2,
                    (
                        "--template-name",
                        "custom",
                        "--template-dir",
                        str(root / "templates"),
                    ),
                )
                rendered = _native(subject.argv())
                if not public_present:
                    assert (
                        rendered.exit != 0
                        and PACKET_MARKER.encode() not in rendered.stdout
                    ), _message(
                        f"absent public oracle yielded exit={rendered.exit}, stdout={rendered.stdout!r}, stderr={rendered.stderr!r}",
                        "missing public authority must refuse rather than emit a successful partial packet",
                        "refuse the malformed handover before producing native_input",
                    )
                    diagnostic = rendered.stdout + rendered.stderr
                    assert b"HandoverMalformed" in diagnostic, _message(
                        f"absent public oracle lacks HandoverMalformed: {diagnostic!r}",
                        "an incidental runner failure cannot establish the declared malformed-input refusal",
                        "report the native handover refusal identifying its unavailable public oracle",
                    )
                    assert b"public_oracle" in diagnostic, _message(
                        f"malformed-input refusal does not identify public_oracle: {diagnostic!r}",
                        "the refusal must distinguish this missing contract from unrelated setup failure",
                        "name the missing public_oracle in the native diagnostic",
                    )
                    continue
                text = rendered.successful_text()
                _assert_facts(text, subject, snapshot)
                for label in ("CUSTOM_REQUEST_FIRST", "CUSTOM_REQUEST_SECOND"):
                    line = next(
                        line
                        for line in text.splitlines()
                        if line.startswith(label + "=")
                    )
                    assert "native_input.request" in line and marker not in line, (
                        _message(
                            f"custom request binding is not a non-owning navigation reference: {line!r}",
                            "repeated partial slots must retain fact access without generating another scalar carrier",
                            "bind each request slot to the canonical request path",
                        )
                    )
                public_line = next(
                    line
                    for line in text.splitlines()
                    if line.startswith("CUSTOM_PUBLIC=")
                )
                assert "selected_authority.public_oracle" in public_line, _message(
                    f"custom public-oracle binding does not navigate to its effective fact: {public_line!r}",
                    "a custom template must retain the declared fact even when it omits the full state slot",
                    "substitute a reference to native_input.selected_authority.public_oracle",
                )
                event(f"shared={inherited};public={public_present};selected-position=2")

    def caller_inputs_survive_actual_template_consumption(
        self, caller: CallerText
    ) -> None:
        with tempfile.TemporaryDirectory(dir=self.temporary_root) as directory:
            root = Path(directory) / "input"
            self._copy_input(root)
            literal = (
                "\n  CALLER_BEGIN\n"
                + caller.text
                + "\n{{request}} native_input [H]\nCALLER_END  \n\n"
            )
            (root / "root.txt").write_bytes(literal.encode("utf-8"))
            original = (root / "templates/custom.tmpl").read_bytes()
            spec = (root / "templates/custom.spec.json").read_bytes()
            for consumed in (False, True):
                name = (
                    "arbitrary-consumer-with-root"
                    if consumed
                    else "arbitrary-consumer-without-root"
                )
                (root / "templates" / f"{name}.tmpl").write_bytes(
                    original + (b"\n{{root_input}}\n" if consumed else b"")
                )
                (root / "templates" / f"{name}.spec.json").write_bytes(spec)
                subject = PromptInput(
                    root,
                    Role.DESIGNER,
                    1,
                    (
                        "--template-name",
                        name,
                        "--template-dir",
                        str(root / "templates"),
                    ),
                )
                first = _native(subject.argv())
                _literal_free(first.successful_text(), literal)
                _assert_repeat(first, _native(subject.argv()))
                event(f"actual-root-slot={consumed}")
            opaque = (root / "instructions.txt").read_bytes().decode("utf-8")
            subject = PromptInput(
                root, Role.DESIGNER, 1, ("--template", "instructions.txt")
            )
            first = _native(subject.argv())
            _assert_facts(
                first.successful_text(), subject, _snapshot(root), opaque=opaque
            )
            _assert_repeat(first, _native(subject.argv()))

    def phase_and_operational_absence_remain_explicit(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.temporary_root) as directory:
            root = Path(directory) / "input"
            self._copy_input(root)
            snapshot = _snapshot(root)
            declaration = snapshot["values"][0]["authority"]
            declaration["facts"].extend(
                [
                    {"id": "V1-move", "text": "PRESERVATION_MOVE_FACT"},
                    {"id": "V1-preserved", "text": "PRESERVED_OBSERVATION_FACT"},
                ]
            )
            declaration["prefactoring"] = {
                "existing_oracle": "root.txt",
                "move": {"ref": "V1-move"},
                "preserved_observation": {"ref": "V1-preserved"},
                "verification": [SHARED_COMMAND],
                "acceptance_supports": [],
                "applicability": "applicable",
            }
            _write_snapshot(root, snapshot)
            subject = PromptInput(
                root,
                Role.CRAFTER,
                1,
                (
                    "--phase",
                    "before",
                    "--targets",
                    "src/role.py",
                ),
            )
            first = _native(subject.argv())
            text = first.successful_text()
            packet = _assert_facts(text, subject, snapshot)
            assert ABSENT_OPERATIONS in list(_leaves(packet)), _message(
                "the canonical packet lost the explicit operational UNASSESSED input",
                "no supplied operational authority must not be mistaken for an assessed absence",
                "retain that instruction-only absence fact in the packet, rather than dropping it with the summary",
            )
            invocation_values = list(_leaves(packet.get("invocation")))
            assert (
                "before" in invocation_values and "src/role.py" in invocation_values
            ), _message(
                f"phase/target invocation facts are missing: {packet.get('invocation')!r}",
                "fact ownership does not authorize changing the caller's phase or target restriction",
                "retain these original invocation parameters and keep them in command instructions",
            )
            _assert_instruction_contract(text, subject, "craft.prefactor-v3", "before")
            _assert_repeat(first, _native(subject.argv()))

    def unavailable_inputs_receive_refusals(self, missing: MissingInput) -> None:
        with tempfile.TemporaryDirectory(dir=self.temporary_root) as directory:
            root = Path(directory) / "input"
            self._copy_input(root)
            snapshot = _snapshot(root)
            extra = ()
            if missing is MissingInput.SNAPSHOT:
                (root / STATE).unlink()
            elif missing is MissingInput.MALFORMED_SNAPSHOT:
                (root / STATE).write_bytes(b"{")
            elif missing is MissingInput.ROOT:
                (root / "root.txt").unlink()
            elif missing is MissingInput.BLANK_ROOT:
                (root / "root.txt").write_bytes(b" \n\t")
            elif missing is MissingInput.TEMPLATE:
                extra = (
                    "--template-name",
                    "unavailable",
                    "--template-dir",
                    str(root / "templates"),
                )
            elif missing is MissingInput.TEMPLATE_SHAPE:
                spec = json.loads((root / "templates/custom.spec.json").read_bytes())
                spec["required"]["root_input"] = "list"
                (root / "templates/custom.spec.json").write_text(
                    json.dumps(spec), encoding="utf-8"
                )
                extra = (
                    "--template-name",
                    "custom",
                    "--template-dir",
                    str(root / "templates"),
                )
            elif missing is MissingInput.DESIGN:
                snapshot["values"][0]["authority"] = None
                snapshot["values"][0].pop("design_semantic_sha256", None)
                _write_snapshot(root, snapshot)
            output = _native(PromptInput(root, Role.DESIGNER, 1, extra).argv())
            stderr = output.stderr.decode("utf-8")
            assert output.exit != 0 and all(
                label in stderr for label in ("WHAT:", "WHY:", "HOW:")
            ), _message(
                f"{missing.value} returned exit={output.exit}, stderr={stderr!r}",
                "incapable input must remain distinguishable from a successfully emitted packet with honest absence markers",
                "preserve the native non-success WHAT/WHY/HOW boundary",
            )
            assert PACKET_MARKER.encode() not in output.stdout, _message(
                f"{missing.value} emitted a successful-looking partial packet",
                "a smaller or empty partial prompt is not a lossless refusal",
                "complete admission before emitting successful prompt stdout",
            )

    def prepared_roles_receive_only_their_sealed_scope(self) -> None:
        # A real native verify builds one candidate and creates its own evidence.
        # No receipt, radius, seal, candidate ref or prepared packet is authored
        # by the test. The verified vector is a real prompt process against the
        # copied native source and compact input, not an execution stand-in.
        root = self.temporary_root / "prepared-subject"
        root.mkdir()
        shutil.copytree(
            CHECKOUT / "src",
            root / "src",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        shutil.copytree(
            CHECKOUT / "nWave",
            root / "nWave",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        shutil.copy2(CHECKOUT / "pyproject.toml", root / "pyproject.toml")
        shutil.copy2(CHECKOUT / "uv.lock", root / "uv.lock")
        self._copy_input(root / "input")
        (root / ".gitignore").write_text("/.nwave/\n__pycache__/\n", encoding="utf-8")
        self._git(root, "init", "-q")
        self._git(root, "config", "user.email", "native-prompt-fixture@example.test")
        self._git(root, "config", "user.name", "Native Prompt Fixture")
        self._git(root, "add", ".")
        self._git(root, "commit", "-qm", "Existing native prompt inputs")
        from tests.des._helpers.host_facts import design_manifest, product_manifest

        def construct(argv: list[str], manifest: dict) -> str:
            # Stdin is the public constructor input boundary. Only its stream
            # is supplied here; native publication, hashing and binding are real.
            previous_stdin = sys.stdin
            try:
                sys.stdin = io.StringIO(json.dumps(manifest, ensure_ascii=False))
                output = _native(argv)
            finally:
                sys.stdin = previous_stdin
            assert output.exit == 0, _message(
                f"native {argv[0]} fixture construction failed: stdout={output.stdout!r}, stderr={output.stderr!r}",
                "prepared-role admission requires genuine published authority and its native identity binding",
                "restore the admitted constructor inputs; do not blank locators or manufacture identity hashes",
            )
            return output.stdout.decode("utf-8")

        observation = (
            "The receiving role retains its complete sealed permitted fact population."
        )
        construct(
            [
                "po",
                "--repo-root",
                str(root),
                "--feature",
                "sealed-role-prompt",
                "--input",
                "-",
            ],
            product_manifest(
                "Receive complete sealed facts through the native role prompt.",
                [observation],
            ),
        )
        # Reuse the compact fixture's semantic declarations, not its synthetic
        # stored identity. The native DESIGN constructor publishes and binds the
        # actual preparation authority below. Its original heading stays named.
        declaration = copy.deepcopy(_snapshot(FIXTURE)["values"][0]["authority"])
        declaration["targets"] = [
            {"path": "src/des/cli/handoff.py", "decision": "EXTEND"}
        ]
        declaration["decisions"] = ["PRIVATE_DESIGN_FACT_FOR_REVIEWER"]
        declaration["oracle"] = "input/instructions.txt"
        declaration["acceptance_supports"] = [
            "input/root.txt",
            "input/templates/custom.tmpl",
            "input/templates/custom.spec.json",
            "input/.nwave/des/handover.json",
        ]
        # Resolve the input at execution time inside the isolated candidate,
        # then invoke the real dispatcher. Do not bind the recipe to this
        # preparation directory or to an implementation checkout.
        command = [
            "env",
            "-u",
            "CI",
            "PYTHONPATH=src",
            sys.executable,
            "-c",
            "from pathlib import Path; from des.cli.__main__ import main; "
            "raise SystemExit(main(['handoff', 'prompt', '--repo-root', "
            "str((Path.cwd() / 'input').resolve()), '--role', "
            f"{Role.DESIGNER.value!r}, '--value', '1', '--root-context', 'root.txt', "
            "'--template-dir', '../nWave/templates/architect-handoff', "
            "'--skills-dir', '../nWave/skills']))",
        ]
        declaration["verification"] = [command]
        normalized_handoff, typed_catalog, _driven = fixture_context(
            declaration["architect_handoff"]
        )
        declaration["architect_handoff"] = normalized_handoff
        declaration["facts"] = [
            {"id": record.id, "text": record.text} for record in typed_catalog.records
        ]
        declaration["public_oracle"] = {
            "observation": observation,
            "stimulus": "Prepare and render the native role's sealed permitted facts.",
            "expected": observation,
            "falsifier": "A permitted fact is lost or repeated, or another role's private fact is disclosed.",
        }
        manifest = design_manifest(declaration, observation, 1)
        publication = construct(
            ["design", "--repo-root", str(root), "--value", "1", "--input", "-"],
            manifest,
        )
        active = _snapshot(root)
        semantic_identities = re.findall(
            r"^SEMANTIC-SHA256: ([0-9a-f]{64})$", publication, re.MULTILINE
        )
        bound_value = active["values"][0]
        assert len(semantic_identities) == 1 and (
            bound_value.get("design_semantic_sha256") == semantic_identities[0]
            and bound_value["authority"]["authority_locator"]
        ), _message(
            f"published DESIGN identity population={semantic_identities!r}, bound identity={bound_value.get('design_semantic_sha256')!r}, locator={bound_value['authority']['authority_locator']!r}",
            "the later native verify/prepare chain must consume the constructor's actual bound identity",
            "retain the native published locator and semantic identity rather than hand-mutating the stored authority",
        )
        # An acceptance-owned caller-input change provides a genuine candidate
        # delta. It is not a fake implementation or a fabricated execution.
        context = (root / "input/root.txt").read_bytes() + b"PREPARED_CALLER_CONTEXT\n"
        (root / "input/root.txt").write_bytes(context)
        verified = _native(["verify", "--repo-root", str(root)])
        verification_text = verified.successful_text()
        candidates = re.findall(
            r"^CANDIDATE: ([0-9a-f]{40})$", verification_text, re.MULTILINE
        )
        assert len(candidates) == 1, _message(
            f"native verify returned candidate population {candidates}",
            "prepared-role tests need the real candidate/evidence chain, not caller-authored receipts",
            "restore native candidate construction and capture its public candidate identity",
        )
        candidate = candidates[0]
        active_before = (root / STATE).read_bytes()
        for role, preparation_role in (
            (Role.REVIEWER, "reviewer"),
            (Role.EXAMINER, "examiner"),
        ):
            prepared_output = _native(
                [
                    "prepare-role",
                    "--repo-root",
                    str(root),
                    "--role",
                    preparation_role,
                    "--candidate",
                    candidate,
                ]
            )
            prepared_text = prepared_output.successful_text()
            paths = re.findall(r"^INPUT: (.+)$", prepared_text, re.MULTILINE)
            assert len(paths) == 1, _message(
                f"public preparation returned input population {paths}",
                "the prompt must consume the actual sealed prepared input",
                "use the single native prepare-role INPUT rather than constructing a replacement packet",
            )
            prepared_path = root / paths[0]
            prepared_bytes = prepared_path.read_bytes()
            prepared = json.loads(prepared_bytes)
            if role is Role.REVIEWER:
                selected = prepared["selected_authority"]["1"]
                assert selected == _effective_population(active, 1), _message(
                    "the reviewer lost its permitted selected design population",
                    "normalization changes carriers, not the reviewer's allowed meaning",
                    "retain the complete selected references and actual verification context",
                )
                assert selected["decisions"] == manifest["decisions"], _message(
                    f"prepared decisions differ: expected={manifest['decisions']!r}, actual={selected['decisions']!r}",
                    "L-resolve-retains preserves the selected decision references and their order",
                    "carry the bound manifest's decision references into the sealed reviewer input unchanged",
                )
                assert [
                    prepared["facts"][reference["ref"]]
                    for reference in selected["decisions"]
                ] == ["PRIVATE_DESIGN_FACT_FOR_REVIEWER"], _message(
                    "the reviewer lost its permitted design facts during preparation",
                    "the selected references must resolve to the original allowed facts",
                    "retain reviewer DESIGN and evidence without duplicate prose displays",
                )
                permitted_roots = {
                    name: prepared[name]
                    for name in (
                        "selected_authority",
                        "inherited_records",
                        "shared_verification",
                        "architect_projection",
                    )
                }
                definitions = {
                    record["id"]: record["text"] for record in manifest["facts"]
                }
                expected_prepared_catalog = {
                    identifier: definitions[identifier]
                    for identifier in _reference_ids(permitted_roots)
                }
                assert prepared["facts"] == expected_prepared_catalog, _message(
                    f"prepared catalog differs: expected={expected_prepared_catalog!r}, actual={prepared['facts']!r}",
                    "the reviewer receives exactly its reachable permitted catalog under L-catalog-once",
                    "resolve the sealed role roots without dropping selected or adding unrelated definitions",
                )
                assert (
                    list(_leaves(prepared)).count("PRIVATE_DESIGN_FACT_FOR_REVIEWER")
                    == 1
                ), _message(
                    f"reviewer design fact occurs {list(_leaves(prepared)).count('PRIVATE_DESIGN_FACT_FOR_REVIEWER')} times, expected one",
                    "the sealed reviewer retains its permitted decision once rather than repeating prose",
                    "keep the decision text solely in the prepared facts catalog",
                )
                assert prepared["architect_projection"] == {
                    "1": _projection_population(active, Role.REVIEWER, 1)
                }, _message(
                    "the prepared reviewer projection differs from its independent declared population",
                    "prepared projection metadata is already owned by the sealed packet",
                    "reuse the complete sealed reviewer projection without another projection implementation",
                )
                assert prepared["native_evidence"][0]["argv"] == command, _message(
                    "the candidate's native evidence does not identify the real prompt vector",
                    "a stand-in execution cannot establish prepared-input lineage",
                    "verify the actual copied native prompt through its declared process vector",
                )
            else:
                assert prepared["outcomes"] == [active["values"][0]["observation"]], (
                    _message(
                        "the examiner lost the public outcome population",
                        "source blindness must preserve public value rather than supply an empty packet",
                        "retain the sealed public outcomes and selected public criteria",
                    )
                )
                assert "PRIVATE_DESIGN_FACT_FOR_REVIEWER" not in json.dumps(
                    prepared
                ) and not {
                    "architect_projection",
                    "selected_authority",
                    "shared_design",
                    "values",
                    "invocation",
                }.intersection(prepared), _message(
                    "the prepared examiner input contains private design or live invocation enrichment",
                    "the examiner is source-blind and consumes the sealed public population only",
                    "do not rebuild examiner facts from the live handover",
                )
            instructions = CHECKOUT / "nWave/agents" / f"{role.value}.md"
            subject = PromptInput(
                root,
                role,
                None,
                (
                    "--candidate",
                    candidate,
                    "--role-input",
                    paths[0],
                    "--template",
                    str(instructions),
                ),
                Path("input/root.txt"),
            )
            first = _native(subject.argv())
            packet, other_text = _packet_and_other_text(
                first.successful_text(), context.decode("utf-8")
            )
            assert packet == prepared, _message(
                "emitted prepared facts differ from the public preparation's sealed input",
                "prompt construction must preserve the complete role-specific producer/consumer agreement",
                "emit the existing prepared packet exactly, with no loss or private enrichment",
            )
            assert not re.findall(r"^=== \[H\] .*$", other_text, re.MULTILINE), (
                _message(
                    "the prepared prompt generated separate projected fact carriers",
                    "the sealed reviewer projection already belongs to native_input, and the examiner consumes none",
                    "emit no second projection display",
                )
            )
            _assert_repeat(first, _native(subject.argv()))
            assert (
                prepared_path.read_bytes() == prepared_bytes
                and (root / STATE).read_bytes() == active_before
            ), _message(
                "prompt construction mutated its prepared input or active snapshot",
                "sealing and native scope boundaries are not part of this correction",
                "keep prepared loaders and prompt construction read-only",
            )
            # A bad seal must differ from a successfully source-blind packet.
            damaged = dict(prepared, payload_sha256="0" * 64)
            prepared_path.write_text(json.dumps(damaged), encoding="utf-8")
            refused = _native(subject.argv())
            assert (
                refused.exit != 0
                and PACKET_MARKER.encode() not in refused.stdout
                and all(
                    label.encode() in refused.stderr
                    for label in ("WHAT:", "WHY:", "HOW:")
                )
            ), _message(
                "a damaged prepared seal did not produce a distinguishable native refusal",
                "empty/source-blind facts must not camouflage inability to authenticate the input",
                "retain the existing prepared-input seal check and non-success boundary",
            )

    @staticmethod
    def _git(root: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            env=_environment(),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, _message(
            f"native fixture Git operation failed: {result.stderr}",
            "candidate preparation requires real isolated Git, not simulated receipts",
            "restore Git support for this temporary fixture before measuring prompt behavior",
        )
        return result.stdout.strip()

    def supplied_prompt_fits_attestation_and_repeats(self) -> None:
        # Frozen pre-normalized authorities are refusal-only inputs. The exact
        # original bytes and paired public process observations remain pinned.
        assert (RUN5 / STATE).is_file() and RUN5_ROOT.is_file(), _message(
            "the declared read-only run5 input or literal caller context is unavailable",
            "the refusal observation applies to that actual frozen fixture only",
            "provide the named unchanged measurement inputs; do not substitute the compact oracle fixture",
        )
        before = ((RUN5 / STATE).read_bytes(), RUN5_ROOT.read_bytes())
        assert len(before[0]) == 529073 and hashlib.sha256(before[0]).hexdigest() == (
            "833ef043034cdc4e8c2e0dcf3db3fc29ae33b487ae4210c8120f23724d3f65be"
        ), _message(
            "the frozen run5 handover differs from its original byte identity",
            "the attestation requires the exact original handover, not a normalized or reduced input",
            "restore the versioned frozen handover from the authorized original using a binary copy",
        )
        assert len(before[1]) == 98 and hashlib.sha256(before[1]).hexdigest() == (
            "2298035414b878c5d77dfbe6bec6d254248ed96b6343243c61ea78b477563aba"
        ), _message(
            "the frozen ROOT caller context differs from its original byte identity",
            "the attestation requires the exact original caller context",
            "restore the versioned frozen root.txt from the authorized original using a binary copy",
        )

        for role, position in (
            (Role.DESIGNER, 1),
            (Role.DESIGNER, 2),
            (Role.DESIGNER, 3),
            (Role.ARCHITECT, None),
        ):
            subject = PromptInput(RUN5, role, position, root_context=RUN5_ROOT)
            first = _native(subject.argv(), process=True)
            assert first.exit != 0, _message(
                "a frozen pre-normalized authority was executed",
                "only schema-2 catalog authorities are executable",
                "rebind the selected scope with des design --replace-current",
            )
            diagnostic = first.stdout + first.stderr
            assert b"DesignFactsPreNormalized" in diagnostic, _message(
                f"frozen {role.value} value={position} refusal lacks DesignFactsPreNormalized: {diagnostic!r}",
                "L-retired-forms forbids executing historical authority; an unrelated failure is not its refusal",
                "report the pre-normalized authority refusal at the native consumer boundary",
            )
            assert b"des design" in diagnostic and b"--replace-current" in diagnostic, (
                _message(
                    f"pre-normalized refusal lacks constructor remediation: {diagnostic!r}",
                    "the refusal-only cutover must teach how to construct the current authority",
                    "direct the caller to des design --replace-current for the selected scope",
                )
            )
            assert PACKET_MARKER.encode() not in first.stdout, _message(
                f"frozen {role.value} value={position} emitted native_input: {first.stdout!r}",
                "retired authority cannot yield a successful-looking partial fact packet",
                "complete schema-2 admission before emitting native_input",
            )
            second = _native(subject.argv(), process=True)
            assert (second.exit, second.stdout, second.stderr) == (
                first.exit,
                first.stdout,
                first.stderr,
            ), _message(
                f"paired frozen refusals differ: first={(first.exit, first.stdout, first.stderr)!r}, second={(second.exit, second.stdout, second.stderr)!r}",
                "unchanged historical inputs must produce the same complete refusal on every fresh process",
                "make retired-authority admission and remediation deterministic without mutating the inputs",
            )
        assert ((RUN5 / STATE).read_bytes(), RUN5_ROOT.read_bytes()) == before, (
            _message(
                "the run5 snapshot or caller context changed during measurement",
                "unchanged-input comparisons and the read-only fixture boundary must remain authentic",
                "restore the immutable measurement inputs and repeat the actual corrected-source renders",
            )
        )


def _fact_tree(depth: int):
    leaf = st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-100000, max_value=100000),
        st.text(st.characters(blacklist_categories=("Cs",)), max_size=80),
    )
    if depth == 0:
        return leaf
    child = _fact_tree(depth - 1)
    return st.one_of(
        leaf,
        st.lists(child, max_size=5),
        st.dictionaries(
            st.text(st.characters(blacklist_categories=("Cs",)), max_size=80),
            child,
            max_size=5,
        ),
    )


PROPERTY_SETTINGS = settings(
    max_examples=30,
    deadline=None,
    derandomize=True,
    database=None,
    print_blob=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@pytest.mark.acceptance
@pytest.mark.walking_skeleton
def test_role_receives_complete_facts_once_through_the_native_process(tmp_path):
    """ownership, rawPreserved, effectivePreserved, projectionPreserved; duplicate mutant."""
    journey = ReceivingRoleJourney(tmp_path)
    journey.defaults_receive_complete_facts_once()


@pytest.mark.acceptance
@PROPERTY_SETTINGS
@given(content=st.builds(FactContent, _fact_tree(3)))
def test_role_preserves_independent_fact_paths_and_partial_template_access(
    tmp_path, content
):
    """rawPreserved/effectivePreserved/projectionPreserved; raw_second_loss/value_coalescing."""
    journey = ReceivingRoleJourney(tmp_path)
    journey.generated_facts_remain_independently_addressable(content)


@pytest.mark.acceptance
@PROPERTY_SETTINGS
@given(
    caller=st.builds(
        CallerText, st.text(st.characters(blacklist_categories=("Cs",)), max_size=80)
    )
)
def test_caller_text_survives_named_and_opaque_instructions_byte_for_byte(
    tmp_path, caller
):
    """rootPreserved/taskPreserved; context_loss; actual omitted-ROOT routing; repeat-byte equality."""
    journey = ReceivingRoleJourney(tmp_path)
    journey.caller_inputs_survive_actual_template_consumption(caller)


@pytest.mark.acceptance
def test_role_retains_phase_target_and_operational_absence_facts(tmp_path):
    """Invocation parameters and operational UNASSESSED input retain their own meaning."""
    journey = ReceivingRoleJourney(tmp_path)
    journey.phase_and_operational_absence_remain_explicit()


@pytest.mark.acceptance
@pytest.mark.parametrize("missing", list(MissingInput), ids=lambda item: item.value)
def test_role_receives_a_refusal_instead_of_a_partial_fact_packet(tmp_path, missing):
    """Unavailable/inconsistent native inputs differ from assessed absence."""
    journey = ReceivingRoleJourney(tmp_path)
    journey.unavailable_inputs_receive_refusals(missing)


@pytest.mark.acceptance
@pytest.mark.integration
def test_prepared_reviewer_and_examiner_retain_their_sealed_fact_scope(tmp_path):
    """prepared-role-input-scope; source-blind examiner boundary; genuine native preparation."""
    journey = ReceivingRoleJourney(tmp_path)
    journey.prepared_roles_receive_only_their_sealed_scope()


@pytest.mark.acceptance
@pytest.mark.integration
def test_supplied_prompt_fits_attestation_and_repeats_without_manual_removal(tmp_path):
    """Exact run5 byte identities; paired explicit refusals for ATD1-3 and architect."""
    journey = ReceivingRoleJourney(tmp_path)
    journey.supplied_prompt_fits_attestation_and_repeats()

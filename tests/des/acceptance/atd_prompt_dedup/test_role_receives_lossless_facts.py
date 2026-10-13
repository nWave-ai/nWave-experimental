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

The supplied run5 observation is a separate real-boundary observation. It reads
the original fixture, never substitutes the compact fixture for its size bound.
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

from des.cli.__main__ import main


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
    SUPPORT = "missing declared support"
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


def _raw_population(snapshot: dict, position: int | None) -> dict:
    # This is the declared raw population, not a call to the production scope
    # or projection implementation. All retained input members participate.
    population = copy.deepcopy(snapshot)
    population.pop("architect_receipts", None)
    for value in population["values"]:
        value["authority"].pop("architect_handoff", None)
    if "shared_design" in population:
        population["shared_design"]["design"].pop("architect_handoff", None)
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
            ("laws", "construction", "model", "closure", "receipts", "scenarios"),
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
    if "shared_design" in snapshot:
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
    # The concrete acceptance cases specify this effective result independently:
    # the selected declaration plus the one shared required command/root support.
    # They do not ask a runner to calculate their own expected answer.
    declaration = snapshot["values"][position - 1]["authority"]
    inherited = "shared_design" in snapshot
    expected = {
        "authority": declaration["authority_locator"]
        or f"typed:{declaration['oracle']}",
        "targets": [
            [item["path"], item["decision"]] for item in declaration["targets"]
        ],
        "paradigm": declaration["paradigm"],
        "decisions": declaration["decisions"],
        "oracle": declaration["oracle"],
        "acceptance_supports": ["root.txt"] if inherited else [],
        "verification": [
            *declaration["verification"],
            *([SHARED_COMMAND] if inherited else []),
        ],
        "oracle_verification_index": declaration["oracle_verification_index"],
        "obligations": declaration["obligations"],
        "architectural_tests": declaration["architectural_tests"],
        "contract_tests": declaration["contract_tests"],
        "prefactoring": declaration["prefactoring"],
        "agreement_analysis": declaration["agreement_analysis"],
        "reuse_analysis": declaration["reuse_analysis"],
        "impact_closure": declaration["impact_closure"],
        "required_verification": [SHARED_COMMAND] if inherited else [],
        "public_oracle": declaration.get("public_oracle", ABSENT_PUBLIC_ORACLE),
    }
    if "adr" in declaration:
        expected["adr"] = declaration["adr"]
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

    def _copy_input(self, destination: Path) -> None:
        shutil.copytree(FIXTURE, destination)
        # Keep tracked text fixtures whitespace-clean; restore their deliberate
        # trailing-space inputs only in each disposable runtime fixture.
        for name in ("root.txt", "instructions.txt"):
            path = destination / name
            content = path.read_bytes()
            boundary = len(content.rstrip(b"\n"))
            path.write_bytes(content[:boundary] + b"  " + content[boundary:])

    def defaults_receive_complete_facts_once(self) -> None:
        snapshot = _snapshot(FIXTURE)
        for role, position, template in (
            (Role.DESIGNER, 1, "oracle.atd-v3"),
            (Role.ARCHITECT, None, "design.architect-v9"),
        ):
            subject = PromptInput(FIXTURE.resolve(), role, position)
            before = (FIXTURE / STATE).read_bytes()
            first = _native(subject.argv(), process=True)
            text = first.successful_text()
            _assert_facts(text, subject, snapshot)
            _assert_instruction_contract(text, subject, template)
            _assert_repeat(first, _native(subject.argv(), process=True))
            assert (FIXTURE / STATE).read_bytes() == before, _message(
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
                marker = "INDEPENDENT_EQUAL_FACT:" + content.text
                snapshot["request"] = marker
                selected["observation"] = marker
                selected["dependencies"] = [predecessor["observation"]]
                selected["authority"]["authority_locator"] = (
                    "docs/design.md#Selected after predecessor"
                )
                selected["authority"]["decisions"] = [marker]
                selected["authority"]["architect_handoff"]["sections"][0]["scope"] = (
                    "value:2"
                )
                selected["authority"]["architect_handoff"]["sections"][0]["status"][
                    "reason"
                ] = "PROJECTED_FACT:" + content.text
                if public_present:
                    selected["authority"]["public_oracle"] = {
                        "observation": "PUBLIC_FACT:" + content.text,
                        "stimulus": "Receive the selected facts",
                        "expected": marker,
                        "falsifier": "An independent fact is lost or repeated",
                    }
                snapshot["values"].append(selected)
                if not inherited:
                    snapshot["scope"] = {"kind": "project"}
                    snapshot.pop("shared_design")
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
                text = _native(subject.argv()).successful_text()
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
            snapshot["values"][0]["authority"]["prefactoring"] = {
                "existing_oracle": "root.txt",
                "move": "PRESERVATION_MOVE_FACT",
                "preserved_observation": "PRESERVED_OBSERVATION_FACT",
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
            elif missing is MissingInput.SUPPORT:
                snapshot["values"][0]["authority"]["acceptance_supports"] = [
                    "templates/custom.spec.json"
                ]
                _write_snapshot(root, snapshot)
                (root / "templates/custom.spec.json").unlink()
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
        declaration = copy.deepcopy(_snapshot(root / "input")["values"][0]["authority"])
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
        manifest = design_manifest(declaration, observation, 1)
        manifest["architect_handoff"] = declaration["architect_handoff"]
        manifest["public_oracle"] = {
            "observation": observation,
            "stimulus": "Prepare and render the native role's sealed permitted facts.",
            "expected": observation,
            "falsifier": "A permitted fact is lost or repeated, or another role's private fact is disclosed.",
        }
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
                assert prepared["values"][0]["decisions"] == [
                    "PRIVATE_DESIGN_FACT_FOR_REVIEWER"
                ], _message(
                    "the reviewer lost its permitted design facts during preparation",
                    "a scope-preserving prompt must retain the reviewer's actual allowed population",
                    "retain reviewer DESIGN and evidence while excluding their duplicate displays",
                )
                assert prepared["architect_projection"] == _projection_population(
                    active, Role.REVIEWER, None
                ), _message(
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

    def _run5_execution_copy(self) -> Path:
        """Adapt only the environment of a disposable copy, never frozen evidence.

        Live verification uses PATH python3; historical receipts, semantic facts
        and locators remain the original observations, not rewritten history.
        """
        root = self.temporary_root / "run5-execution"
        shutil.copytree(RUN5, root)
        # Native support admission needs real Git ignore queries in this copy,
        # independently of the enclosing checkout that admits the frozen input.
        self._git(root, "init", "-q")
        original = _snapshot(root)
        execution = copy.deepcopy(original)
        legacy_python = "/home/parajao/Projects/nWave-dev/.venv/bin/python"
        substitutions = set()
        declarations = [
            (("values", index, "authority", "verification"), value["authority"])
            for index, value in enumerate(execution["values"])
        ]
        if "shared_design" in execution:
            declarations.append(
                (
                    ("shared_design", "design", "verification"),
                    execution["shared_design"]["design"],
                )
            )
        for prefix, authority in declarations:
            for index, argv in enumerate(authority.get("verification", [])):
                if argv and argv[0] == legacy_python:
                    argv[0] = "python3"
                    substitutions.add((*prefix, index, 0))
        expected = {
            ("values", value, "authority", "verification", command, 0)
            for value in range(3)
            for command in range(2)
        } | {
            ("shared_design", "design", "verification", command, 0)
            for command in range(2)
        }
        assert substitutions == expected, _message(
            f"run5 live executable substitutions differ: {substitutions!r}",
            "this frozen observation declares exactly six value and two shared live executable slots",
            "restore the original frozen input and adapt only its declared live verification executables",
        )
        restored = copy.deepcopy(execution)
        for path in substitutions:
            argv = restored
            for component in path[:-1]:
                argv = argv[component]
            argv[path[-1]] = legacy_python
        assert restored == original, _message(
            "the execution copy changed facts beyond live verification argv[0]",
            "historical receipts, locators and all other facts must retain exact equality",
            "limit the temporary-copy adaptation to the eight declared executable slots",
        )
        _write_snapshot(root, execution)
        assert (root / "root.txt").read_bytes() == RUN5_ROOT.read_bytes(), _message(
            "the execution copy changed literal caller bytes",
            "environment-only adaptation must preserve the original root context",
            "copy root.txt as binary without normalization",
        )
        return root

    def supplied_prompt_fits_attestation_and_repeats(self) -> None:
        # This integration input is explicitly named by DESIGN. No compact-size
        # proxy, reference-probe result, skip or fallback can satisfy its bound.
        assert (RUN5 / STATE).is_file() and RUN5_ROOT.is_file(), _message(
            "the declared read-only run5 input or literal caller context is unavailable",
            "the supplied attestation threshold applies to that actual fixture only",
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
        execution_root = self._run5_execution_copy()
        first_designer_size = None
        for role, position in (
            (Role.DESIGNER, 1),
            (Role.DESIGNER, 2),
            (Role.DESIGNER, 3),
            (Role.ARCHITECT, None),
        ):
            subject = PromptInput(
                execution_root, role, position, root_context=execution_root / "root.txt"
            )
            first = _native(subject.argv(), process=True)
            first.successful_text()
            _assert_repeat(first, _native(subject.argv(), process=True))
            if role is Role.DESIGNER and position == 1:
                first_designer_size = len(first.stdout)
        assert ((RUN5 / STATE).read_bytes(), RUN5_ROOT.read_bytes()) == before, (
            _message(
                "the run5 snapshot or caller context changed during measurement",
                "unchanged-input comparisons and the read-only fixture boundary must remain authentic",
                "restore the immutable measurement inputs and repeat the actual corrected-source renders",
            )
        )
        assert first_designer_size is not None and first_designer_size < 490000, (
            _message(
                f"actual run5 acceptance-designer first prompt is {first_designer_size} UTF-8 bytes, expected strictly below 490000",
                "the role turn must fit the supplied attestation limit without manual fact removal",
                "remove duplicate software-owned carriers losslessly; do not truncate or substitute another fixture",
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
    """Actual run5 ATD1 <490000 bytes; paired whole stdout for ATD1-3 and architect."""
    journey = ReceivingRoleJourney(tmp_path)
    journey.supplied_prompt_fits_attestation_and_repeats()

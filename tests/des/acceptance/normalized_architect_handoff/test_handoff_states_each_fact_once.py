"""Current design facts reach the next role once, without losing shared obligations.

@contract-shape: real-io. All behavior enters des.cli.__main__.main, or the
package subprocess in the single walking skeleton. Real temporary repository,
CAS handover, configured document publisher and native templates are retained.
The in-process preservation map omits only the interpreter fork: arguments,
stdin, stored bytes, publishers and prompt consumer are the same production
composition. Behavioral observations use the real public command. The two
explicit DESIGN architecture observations additionally inspect the declared
construction boundary and resolved typed-record graph, never production AST.
Hypothesis bounds are sampling bounds, never production limits; native shrinking
and database replay are retained. Host owns RED/GREEN and isolated execution.
"""

from __future__ import annotations

import base64
import copy
import dataclasses as dc
import gzip
import hashlib
import html
import importlib
import io
import json
import os
import re
import string
import subprocess
import sys
import tempfile
import types
import typing as t
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

from des.cli.__main__ import main


CHECKOUT = Path(__file__).resolve().parents[4]
FIXTURE = Path(__file__).with_name("fixture") / "doctor_version_sync"
STATE = Path(".nwave/des/handover.json")
MARKER = "=== [C] orchestrator ===\nnative_input: "
PBT = settings(max_examples=20, derandomize=True, deadline=None, print_blob=True)


def message(what, why, how):
    return f"WHAT: {what}. WHY: {why}. HOW: {how}."


#: The interpreter the run11 architect recorded on the author's machine. The
#: fixture keeps it verbatim as provenance. Only at the execution boundary,
#: where the journey hands a document to des, does this test host substitute
#: its own interpreter for that one recorded argv0; nothing else is rewritten.
FROZEN_INTERPRETER = "/home/parajao/Projects/nWave-dev/.venv/bin/python"


def runnable(recipes):
    """The frozen native recipes with this host's interpreter as argv0."""
    return [
        [sys.executable, *argv[1:]] if argv[:1] == [FROZEN_INTERPRETER] else argv
        for argv in recipes
    ]


def executable_body(body):
    """The document des receives: every recorded recipe made runnable here."""
    if isinstance(body, dict):
        return {
            key: runnable(child) if key == "verification" else executable_body(child)
            for key, child in body.items()
        }
    if isinstance(body, list):
        return [executable_body(child) for child in body]
    return body


def load(name):
    return json.loads((FIXTURE / name).read_text())


def frozen_bytes(mapping, name):
    """Decode independent immutable source bytes from the declared repo support."""
    assert mapping["immutable_inputs"]["encoding"] == "gzip+base64", message(
        "frozen source encoding is unsupported",
        "expected source bytes must be available without an author-home dependency",
        "retain the declared compressed immutable input snapshots in the repository fixture",
    )
    return gzip.decompress(
        base64.b64decode(mapping["immutable_inputs"]["bytes"][name], validate=True)
    )


def walk(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, path + (index,))
    else:
        yield path, value


def at(value, path):
    for part in path:
        value = value[part]
    return value


def set_at(value, path, replacement):
    at(value, path[:-1])[path[-1]] = replacement


def records(document, kind):
    key = "parties" if kind == "agreement_analysis" else "obligations"
    return document[kind].get(key, [])


def catalog(*documents):
    return {
        item["id"]: item["text"] for document in documents for item in document["facts"]
    }


def semantic_hash(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class Response:
    code: int
    stdout: str
    stderr: str

    def admitted(self, action):
        assert self.code == 0, message(
            f"public {action} did not admit the declared current form: exit={self.code}, stdout={self.stdout}, stderr={self.stderr}",
            "schema-2 current facts and references are promised producer behavior, not an optional mode",
            "implement the declared normalized constructor/consumer; distinguish a reported product refusal from environment startup failure",
        )
        return self


class HandoffJourney:
    def __init__(self, directory, *, fork=False, count=3):
        self.root = Path(directory)
        self.fork = fork
        self.count = count
        self.bindings = []
        self.root.mkdir(parents=True, exist_ok=True)
        home = self.root / ".oracle-home"
        for path in (
            home,
            home / ".config",
            home / ".cache",
            home / ".local/share",
            home / ".local/state",
        ):
            path.mkdir(parents=True, exist_ok=True)
        # Git and both dispatcher modes receive the same declared inputs, never
        # the host's destination selectors, global config or provider environment.
        self.environment = {
            "HOME": str(home),
            "NWAVE_AGENTS_HOME": str(home),
            "NWAVE_PROJECT_ROOT": str(self.root),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "XDG_DATA_HOME": str(home / ".local/share"),
            "XDG_STATE_HOME": str(home / ".local/state"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "PATH": os.pathsep.join(
                (str(Path(sys.executable).parent), "/usr/bin", "/bin")
            ),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONUTF8": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": str(CHECKOUT / "src"),
            "NO_COLOR": "1",
        }
        result = subprocess.run(
            ["git", "init", "-q", str(self.root)],
            capture_output=True,
            text=True,
            check=False,
            cwd=self.root,
            env=self.environment,
        )
        assert result.returncode == 0, message(
            "isolated repository creation failed: " + result.stderr,
            "no product observation occurred",
            "restore the declared Git runtime before observing RED",
        )
        (self.root / "root-context.md").write_bytes(
            (FIXTURE / "root-context.md").read_bytes()
        )
        self.po = load("po.json")
        self.po["values"] = self.po["values"][:count]
        self.po["outcomes"] = [value["observation"] for value in self.po["values"]]
        self.po["scope"]["in_scope"] = self.po["outcomes"]
        self.invoke(
            "po", "--feature", "doctor-version-sync", "--input", "-", body=self.po
        ).admitted("product decomposition")

    def invoke(self, *args, body=None, fork=None):
        argv = [args[0], "--repo-root", str(self.root), *args[1:]]
        text = (
            ""
            if body is None
            else body
            if isinstance(body, str)
            else json.dumps(executable_body(body), ensure_ascii=False)
        )
        environment = self.environment
        if self.fork if fork is None else fork:
            result = subprocess.run(
                [sys.executable, "-m", "des", *argv],
                input=text,
                text=True,
                capture_output=True,
                cwd=CHECKOUT,
                env=environment,
                check=False,
            )
            return Response(result.returncode, result.stdout, result.stderr)
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch.dict(os.environ, environment, clear=True),
            patch("sys.stdin", io.StringIO(text)),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            try:
                code = main(argv)
            except SystemExit as exit:
                # The dispatcher exposes argparse's actual process termination.
                # Preserve Python process semantics, not product exceptions.
                code = (
                    0
                    if exit.code is None
                    else exit.code
                    if isinstance(exit.code, int)
                    else 1
                )
                if exit.code is not None and not isinstance(exit.code, int):
                    stderr.write(str(exit.code) + "\n")
        return Response(code, stdout.getvalue(), stderr.getvalue())

    def bind(self, document, position=None, *, replace=False, handoff_file=None):
        selection = ["--shared"] if position is None else ["--value", str(position)]
        models = [
            model
            for section in document.get("architect_handoff", {}).get("sections", [])
            if section["kind"] == "model"
            for model in section["status"].get("payload", {}).get("models", [])
            if "source" in model
        ]
        if models:
            mapping = load("run11-fact-map.json")
            frozen_models = {}
            for name in mapping["source_revision"]["current_normative_sources"]:
                original = json.loads(frozen_bytes(mapping, name))
                for section in original.get("architect_handoff", {}).get(
                    "sections", []
                ):
                    if section["kind"] == "model":
                        for model in (
                            section["status"].get("payload", {}).get("models", [])
                        ):
                            frozen_models[model["path"]] = model["text"].encode()
            for model in models:
                source = model["source"]
                raw = frozen_models[source["path"]]
                assert hashlib.sha256(raw).hexdigest() == source["sha256"], message(
                    "external model fixture identity differs",
                    "real model locators must not depend on the author's machine",
                    "stage exact independently frozen bytes outside the handoff",
                )
                path = self.root / source["path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
        result = self.invoke(
            "design",
            *selection,
            *(["--replace-current"] if replace else []),
            *(["--architect-handoff", handoff_file] if handoff_file else []),
            "--input",
            "-",
            body=document,
        )
        if result.code == 0:
            self.bindings.append((position, result))
        return result

    def current(self, shared, values):
        self.bind(shared).admitted("shared design")
        for position, document in enumerate(values, 1):
            self.bind(document, position).admitted("value design")
        return self

    def bytes(self):
        return (self.root / STATE).read_bytes()

    def prompt(self, position, role="nw-acceptance-designer", *, fork=None):
        result = self.invoke(
            "handoff",
            "prompt",
            "--role",
            role,
            "--value",
            str(position),
            "--root-context",
            "root-context.md",
            "--template-dir",
            str(CHECKOUT / "nWave/templates/architect-handoff"),
            "--skills-dir",
            str(CHECKOUT / "nWave/skills"),
            fork=fork,
        )
        result.admitted("receiving-role prompt")
        assert MARKER in result.stdout, message(
            "canonical public packet is absent",
            "the next role cannot resolve current facts",
            "emit native_input through the declared real prompt",
        )
        packet, _ = json.JSONDecoder().raw_decode(result.stdout.split(MARKER, 1)[1])
        return packet, result

    # Keep native selection and expected refusal explicit at this public adapter.
    def refused(  # noqa: PLR0913
        self,
        document,
        position,
        what,
        tokens,
        *,
        replace=False,
        ids=(),
        handoff_file=None,
    ):
        before = self.bytes()
        result = self.bind(
            document, position, replace=replace, handoff_file=handoff_file
        )
        report = result.stdout + result.stderr
        assert (
            result.code == 1
            and "DELIVERY-OUTCOME: Refusal" in report
            and f"WHAT: {what}" in report
        ), message(
            f"invalid current input produced exit={result.code}, report={report}",
            "a forbidden definition must not be accepted or mistaken for startup failure",
            "refuse through the public constructor with the declared WHAT and WHY diagnostics",
        )
        for token in tokens:
            assert re.search(
                r"(?m)^\s*(?:WHY:\s*)?(?:[-*]\s*)?" + re.escape(token) + r"\b", report
            ), message(
                f"refusal omitted a token-led defect line for {token}: {report}",
                "each independent defect needs its own distinguishable public diagnostic",
                "report every applicable token at the start of its own defect line",
            )
        assert not any(
            retired in report
            for retired in (
                "DesignSharedFactCopied",
                "DesignInheritedFactMissing",
                "ArchitectHandoffDecisionProse",
            )
        ), message(
            "a retired defect alias was emitted",
            "clean cutover has one diagnostic identity per declared defect",
            "emit only the normalized refusal vocabulary",
        )
        if what == "InvalidDesignDocument":
            assert (
                "UNRUN: bound-state reference checks (manifest did not decode)"
                in report
            ), message(
                "manifest refusal omitted its unrun bound-state checks",
                "absence of bound-state diagnostics must not pretend those checks ran",
                "emit the declared UNRUN discriminator after every manifest-only defect refusal",
            )
        assert "WHY:" in report and "HOW:" in report and "des design" in report, (
            message(
                "refusal lacks a producing-tool correction",
                "a refusal must explain the defect and how to construct valid current input",
                "emit WHAT/WHY/HOW with the public producer remediation",
            )
        )
        for identity in ids:
            assert identity in report, message(
                f"refusal omitted affected identity {identity}: {report}",
                "the operator must locate each missing reference/dependent",
                "name every offending id and affected value",
            )
            if position is not None and "DesignFactUnresolved" in tokens:
                defect_lines = [
                    line
                    for line in report.splitlines()
                    if re.match(
                        r"^\s*(?:WHY:\s*)?(?:[-*]\s*)?DesignFactUnresolved\b",
                        line,
                    )
                ]
                assert any(
                    re.search(
                        r"(?<![A-Za-z0-9_-])"
                        + re.escape(identity)
                        + r"(?![A-Za-z0-9_-])",
                        line,
                    )
                    and re.search(
                        r"\bvalues?\s*[:=-]?\s*(?:\[\s*)?" + str(position) + r"\b",
                        line,
                        re.IGNORECASE,
                    )
                    for line in defect_lines
                ), message(
                    f"unresolved id {identity} is not paired with dependent value {position} on its defect line: {report}",
                    "separate mentions cannot tell the operator which value needs each missing reference",
                    "name each missing id and its dependent value together on a token-led unresolved-reference line",
                )
        assert self.bytes() == before, message(
            "refused input changed bound handover bytes",
            "refusal must preserve the previously accepted authority",
            "validate all defects before binding or publishing replacement state",
        )
        return result

    def document(self):
        # The configured public authority locator is produced by des, not guessed.
        stored = json.loads(self.bytes())
        locator = stored["shared_design"]["authority_locator"]
        return (self.root / locator.split("#", 1)[0]).read_text()

    def recovery(self, shared, value):
        selected = {
            "observation": self.po["values"][0]["observation"],
            "acceptance_obligations": [
                {
                    "id": "current_facts",
                    "stimulus": "Receive current facts",
                    "expected": "Every selected fact and obligation remains available once",
                }
            ],
            "oracle": value["oracle"],
            "acceptance_supports": value["acceptance_supports"],
            "verification": value["verification"],
            "oracle_verification_index": value["oracle_verification_index"],
        }
        self.invoke(
            "distill", "--input", "-", body={"schema_version": 2, "values": [selected]}
        ).admitted("selected contract")
        changed = copy.deepcopy(shared)
        changed["facts"][0]["text"] += " Current revision."
        self.bind(changed, replace=True).admitted("shared currentness replacement")
        result = self.invoke(
            "prepare-role",
            "--role",
            "acceptance-designer",
            "--task",
            "selected-revision-recovery",
            "--value",
            "1",
            "--finding",
            "-",
            body="The shared fact changed; recover the same selected obligations without duplication.",
        ).admitted("recovery preparation")
        line = next(
            (line for line in result.stdout.splitlines() if line.startswith("INPUT: ")),
            None,
        )
        assert line is not None, message(
            "public recovery omitted its produced input locator",
            "the next role needs the actual sealed consumer artifact",
            "return the written recovery INPUT locator",
        )
        return json.loads(
            (self.root / line.removeprefix("INPUT: ")).read_text()
        ), changed


def reference_ids(value):
    return {leaf for path, leaf in walk(value) if path and path[-1] == "ref"}


def inherited_records(shared, value):
    selected = {item["ref"] for item in value.get("inherits", [])}
    return {
        record["id"]: record
        for kind in ("architectural_tests", "contract_tests", "agreement_analysis")
        for record in records(shared, kind)
        if record["id"] in selected
    }


def typed_contents(shared, value):
    """Select the declared dependency graph, without calling product projection."""
    selected = {item["ref"] for item in value.get("inherits", [])}
    own = value.get("architect_handoff", {}).get("sections", [])
    inherited_subjects = {
        item["subject"]["ref"]
        for section in own
        if section["kind"] == "closure"
        for item in section["status"].get("payload", {}).get("closures", [])
        if item["liveness"]["tag"] == "inherited"
    }
    result = {}
    for document, is_shared in ((shared, True), (value, False)):
        for section in document.get("architect_handoff", {}).get("sections", []):
            kind, scope, status = section["kind"], section["scope"], section["status"]
            if kind not in ("laws", "construction", "model", "closure"):
                continue
            if status["tag"] != "applicable":
                if not is_shared:
                    result[(kind, scope)] = {"not_applicable": status["reason"]}
                continue
            payload = copy.deepcopy(status["payload"])
            if is_shared:
                if kind == "laws":
                    payload["laws"] = [
                        record for record in payload["laws"] if record["id"] in selected
                    ]
                    payload["refuted"] = [
                        record
                        for record in payload["refuted"]
                        if record["id"] in selected
                    ]
                    used = {
                        identity
                        for record in payload["laws"]
                        for identity in record["uses"]
                    } | selected
                    generators = {
                        record["treatment"]["generator"]
                        for record in payload["laws"]
                        if record["treatment"]["tag"] == "broad"
                    } | selected
                    for field in ("observations", "constructors"):
                        payload[field] = [
                            record for record in payload[field] if record["id"] in used
                        ]
                    payload["generators"] = [
                        record
                        for record in payload["generators"]
                        if record["id"] in generators
                    ]
                    if not any(
                        payload[field]
                        for field in (
                            "laws",
                            "refuted",
                            "observations",
                            "constructors",
                            "generators",
                        )
                    ):
                        continue
                elif kind == "construction":
                    payload["claims"] = [
                        record
                        for record in payload["claims"]
                        if record["id"] in selected
                    ]
                    if not payload["claims"]:
                        continue
                elif kind == "model":
                    payload["models"] = [
                        record
                        for record in payload["models"]
                        if record["id"] in selected
                    ]
                    if not payload["models"]:
                        continue
                else:
                    payload["closures"] = [
                        record
                        for record in payload["closures"]
                        if record["subject"]["ref"] in selected | inherited_subjects
                    ]
                    if not payload["closures"]:
                        continue
            # The existing ATD role views are full/full/falsifiers/axes.
            if kind == "model":
                projected = []
                for model in payload["models"]:
                    atom_fields = {
                        "state": ("tag", "name", "symbol", "site"),
                        "constant": ("tag", "name", "symbol", "site"),
                        "property": ("tag", "name", "symbol", "site"),
                        "action": ("tag", "name", "symbol", "site", "atomicity"),
                    }
                    projected.append(
                        {
                            "id": model["id"],
                            "language": model["language"],
                            "path": model["path"],
                            "sha256": model["source"]["sha256"],
                            "atoms": [
                                {
                                    key: child
                                    for key, child in atom.items()
                                    if key in atom_fields[atom["tag"]]
                                }
                                for atom in model["atoms"]
                            ],
                            "assumptions": model["assumptions"],
                            "exclusions": model["exclusions"],
                            "mutants": [
                                {
                                    "id": mutant["id"],
                                    "description": mutant["description"],
                                    "kills": sorted(
                                        {kill["property"] for kill in mutant["kills"]}
                                    ),
                                }
                                for mutant in model["mutants"]
                            ],
                        }
                    )
                payload = {"models": projected}
            elif kind == "closure":
                projected = []
                for closure in payload["closures"]:
                    row = {"subject": closure["subject"]}
                    for axis in (
                        "safety",
                        "inhabitation",
                        "public_reachability",
                        "liveness",
                    ):
                        claim = closure[axis]
                        row[axis] = (
                            {
                                key: child
                                for key, child in claim.items()
                                if key
                                in (
                                    "statement",
                                    "design",
                                    "runtime",
                                    "design_note",
                                    "runtime_note",
                                )
                            }
                            if claim["tag"] == "claim"
                            else claim
                        )
                    projected.append(row)
                payload = {"closures": projected}
            result[(kind, scope)] = payload
    return result


def unordered_records(value):
    """Role projection sorts sets; submitted manifest reference order stays exact."""
    if isinstance(value, dict):
        return {key: unordered_records(child) for key, child in value.items()}
    if isinstance(value, list):
        return sorted(
            (unordered_records(child) for child in value),
            key=lambda child: json.dumps(child, sort_keys=True, ensure_ascii=False),
        )
    return value


def assert_typed(packet, shared, value):
    expected = typed_contents(shared, value)
    entries = packet.get("architect_projection", [])
    assert isinstance(entries, list), message(
        "typed operational projection is absent",
        "laws, models, construction and closure are next-role facts too",
        "retain the declared fourth reachability root",
    )
    actual = {
        (entry["kind"], entry["scope"]): entry["content"]
        for entry in entries
        if not (
            isinstance(entry.get("content"), dict) and "UNASSESSED" in entry["content"]
        )
    }
    assert len(actual) == sum(
        1
        for entry in entries
        if not (
            isinstance(entry.get("content"), dict) and "UNASSESSED" in entry["content"]
        )
    ), message(
        "a typed scope was projected twice",
        "duplicate typed records create parallel operational definitions",
        "emit each selected typed scope once",
    )
    assert unordered_records(actual) == unordered_records(expected), message(
        f"selected typed metadata differs: expected={expected}, actual={actual}",
        "identity-only shared design must not erase needed operational typed facts or leak unselected records",
        "retain own typed sections and selected shared records with their declared dependencies and unchanged role view",
    )


def reachable_catalog(shared, value):
    # Four roots: own semantic slots, selected manifest records, their shared
    # commands (no FactRefs), and selected typed metadata in the ATD role view.
    definitions = catalog(shared, value)
    inherited = inherited_records(shared, value)
    direct = reference_ids(
        {
            key: item
            for key, item in value.items()
            if key not in ("facts", "inherits", "architect_handoff")
        }
    )
    direct.update(reference_ids(inherited))
    direct.update(reference_ids(list(typed_contents(shared, value).values())))
    return {
        identity: definitions[identity]
        for identity in direct
        if identity in definitions
    }


def record_population(value):
    """Record identities/fields, independent of list-versus-map presentation."""
    found = []
    if isinstance(value, dict):
        if "id" in value and ("obligation" in value or "role" in value):
            found.append(value)
        for child in value.values():
            found.extend(record_population(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(record_population(child))
    return found


def assert_selected_references(selected, value):
    """Compare submitted semantic structure, independently of resolved prose."""
    for field in (
        "purpose",
        "constraints",
        "decisions",
        "inherits",
        "targets",
        "reuse_analysis",
        "prefactoring",
        "agreement_analysis",
        "architectural_tests",
        "contract_tests",
        "impact_closure",
        "boundaries",
        "public_oracle",
        "adr",
    ):
        if field in value:
            assert field in selected and selected[field] == value[field], message(
                f"selected {field} changed: expected={value[field]}, actual={selected.get(field)}",
                "semantic slots must keep the submitted own and shared references, not expanded or prefixed prose or copied inherited records",
                "retain exact FactRef objects and their own structured context; keep shared definitions in the catalog and selected shared records in inherited_records",
            )


def assert_packet(packet, shared, value):
    expected = reachable_catalog(shared, value)
    actual = packet.get("facts")
    assert actual == expected, message(
        f"reachable catalog differs: expected={expected}, actual={actual}",
        "the next role needs every selected current fact and no unrelated or unused declaration",
        "project precisely the submitted value references and explicitly inherited record references, each once",
    )
    assert_selected_references(packet["selected_authority"], value)
    assert_typed(packet, shared, value)
    population = Counter(text for _, text in walk(packet) if isinstance(text, str))
    for identity, text in expected.items():
        assert population[text] == 1, message(
            f"reachable fact {identity} occurs {population[text]} times",
            "one authoritative prose definition must serve every reference",
            "emit text only in the receiving-role facts map",
        )
    for identity, text in catalog(shared, value).items():
        if identity not in expected:
            assert population[text] == 0, message(
                f"unselected fact {identity} leaked into the packet",
                "once-only output is still wrong when an unrelated fact reaches this role",
                "exclude all facts unreachable from this value and its selected shared records",
            )
    for document in packet.get("values", []):
        assert "authority" not in document, message(
            "a value repeats an authority body",
            "value identities must not introduce a second authority snapshot",
            "retain observation, dependencies and identities only",
        )
    shared_identity = packet.get("shared_design", {})
    assert (
        isinstance(shared_identity, dict)
        and set(shared_identity)
        <= {"authority_locator", "section_sha256", "semantic_sha256"}
        and "authority_locator" in shared_identity
    ), message(
        f"shared projection is not identity-only: {shared_identity}",
        "shared declarations outside selected references leak unrelated authority",
        "emit only the three declared shared identity fields",
    )
    excluded = {
        "architect_receipts",
        "history",
        "provenance",
        "receipts",
        "supersedes",
        "supersession",
        "trace",
        "model_text",
    }
    assert not excluded.intersection(packet), message(
        f"excluded packet-envelope carriers: {sorted(excluded.intersection(packet))}",
        "history is forbidden at the envelope as well as in nested operational records",
        "retain only current operational metadata and external evidence locators",
    )

    def inspect_operational(node, path=()):
        if isinstance(node, dict):
            for key, child in node.items():
                assert key not in excluded, message(
                    f"excluded carrier at {path + (key,)}",
                    "nested evidence bodies are still operational history carriers",
                    "retain external locators and current structured metadata only",
                )
                assert not (key == "text" and path and path[0] != "facts"), message(
                    f"parallel text carrier at {path}",
                    "only the facts map owns current semantic text",
                    "retain FactRefs in every operational record",
                )
                inspect_operational(child, path + (key,))
        elif isinstance(node, list):
            for index, child in enumerate(node):
                inspect_operational(child, path + (index,))

    for root in (
        "selected_authority",
        "inherited_records",
        "shared_verification",
        "architect_projection",
        "shared_design",
        "values",
    ):
        inspect_operational(packet.get(root, {}), (root,))


def assert_inherited(packet, shared, value):
    selected = packet["selected_authority"]
    assert_selected_references(selected, value)
    # Decisions and constraints are first-class retained obligations, not just
    # prose indirectly covered by test/party records.
    for field in ("decisions", "constraints", "inherits"):
        assert selected.get(field, []) == value.get(field, []), message(
            f"selected {field} changed: {selected.get(field)} != {value.get(field)}",
            "dropping a selected decision or constraint is as lossy as dropping a test",
            "preserve the submitted own and shared FactRef order without inheriting unrelated shared slots",
        )
    for kind in ("architectural_tests", "contract_tests", "agreement_analysis"):
        assert records(selected, kind) == records(value, kind), message(
            f"value-local {kind} expanded or lost records",
            "the selected authority must contain the value delta, not copied inherited definitions",
            "retain own records here and selected shared records only in inherited_records",
        )
    expected_records = inherited_records(shared, value)
    actual_records = record_population(packet.get("inherited_records", {}))
    assert Counter(record["id"] for record in actual_records) == Counter(
        expected_records.keys()
    ), message(
        f"inherited record population differs: {actual_records}",
        "each explicitly selected shared test/party must be present exactly once",
        "project only selected shared record identities without duplicates",
    )
    assert {record["id"]: record for record in actual_records} == expected_records, (
        message(
            "inherited record fields lost their submitted meaning",
            "record identity alone cannot preserve obligations",
            "retain the original structured record and FactRef fields",
        )
    )
    indexes = {
        record["verification_index"]
        for record in expected_records.values()
        if "verification_index" in record
    }
    executed = runnable(shared["verification"])
    expected_argv = {str(index): executed[index] for index in indexes}
    assert packet.get("shared_verification") == expected_argv, message(
        f"inherited command map differs: {packet.get('shared_verification')} != {expected_argv}",
        "an inherited index belongs to the shared list, never the different value list",
        "project exactly the selected shared indexes and their original argv",
    )


def decoded_markdown_text(text, *, submitted=False):
    """Decode published prose while keeping code contents literal.

    Submitted definitions supply raw prose, not the publisher's Markdown
    escapes or entities. Only their explicit code spans have inline syntax.
    """
    escaped_punctuation = r"\\([" + re.escape(string.punctuation) + r"])"

    def prose(fragment):
        if not submitted:
            fragment = html.unescape(re.sub(escaped_punctuation, r"\1", fragment))
        return re.sub(r"\s+", " ", fragment)

    fragments = []
    cursor = 0
    # An escaped backtick cannot open code. Once code starts, backslashes are
    # literal and only a backtick run of exactly the opening length closes it.
    for opening in re.finditer(escaped_punctuation + r"|`+", text):
        if opening.start() < cursor or opening.group().startswith("\\"):
            continue
        closing = next(
            (
                run
                for run in re.finditer(r"`+", text[opening.end() :])
                if run.group() == opening.group()
            ),
            None,
        )
        if closing is None:
            continue
        fragments.append(prose(text[cursor : opening.start()]))
        content = text[opening.end() : opening.end() + closing.start()]
        content = re.sub(r"\r\n?|\n", " ", content)
        if content.startswith(" ") and content.endswith(" ") and content.strip(" "):
            content = content[1:-1]
        # Canonical delimiters ignore incidental fence length without losing
        # literal backslashes, entity-looking text or spaces inside code.
        fence = "`" * (
            1 + max((len(run) for run in re.findall(r"`+", content)), default=0)
        )
        fragments.append(fence + content + fence)
        cursor = opening.end() + closing.end()
    fragments.append(prose(text[cursor:]))
    return "".join(fragments).strip()


def assert_document(text, documents):
    expected = {
        identity: decoded_markdown_text(prose, submitted=True)
        for identity, prose in catalog(*documents).items()
    }
    sections = re.split(r"(?m)^(#{1,6})\s+([^\n]+)\n", text)
    definitions = []
    other_blocks = [
        decoded_markdown_text(block)
        for block in re.split(r"\n\s*\n", sections[0])
        if block.strip()
    ]
    facts_regions = 0
    for i in range(1, len(sections), 3):
        title, body = sections[i + 1], sections[i + 2]
        other_blocks.append(decoded_markdown_text(title))
        if not re.match(r"Facts\b", title):
            other_blocks.extend(
                decoded_markdown_text(block)
                for block in re.split(r"\n\s*\n", body)
                if block.strip()
            )
            continue
        facts_regions += 1
        current = None
        fragments = []
        other_lines = []

        def finish_other(lines):
            if lines:
                other_blocks.append(decoded_markdown_text(" ".join(lines)))
                lines.clear()

        def finish_item(identity, parts):
            if identity is not None:
                definitions.append((identity, decoded_markdown_text(" ".join(parts))))

        for line in body.splitlines():
            item = re.match(r"^- ([A-Za-z][A-Za-z0-9_-]{0,63}):[ \t]*(.*)$", line)
            if item:
                finish_other(other_lines)
                finish_item(current, fragments)
                current, first = item.groups()
                fragments = [first]
            elif current is not None and line.startswith("  ") and line.strip():
                fragments.append(line.strip())
            else:
                finish_item(current, fragments)
                current, fragments = None, []
                if line.strip():
                    other_lines.append(line)
                else:
                    finish_other(other_lines)
        finish_item(current, fragments)
        finish_other(other_lines)
    assert facts_regions, message(
        "published authority has no Facts section",
        "the one catalog must be readable in the actual durable document",
        "render catalog definitions in Facts lists and references elsewhere",
    )
    actual_ids = Counter(identity for identity, _ in definitions)
    assert actual_ids == Counter(dict.fromkeys(expected, 1)), message(
        f"decoded fact identity population differs: {actual_ids}",
        "wrapping must not hide a missing, additional or duplicated definition",
        "retain each bound fact id as exactly one logical Facts-list item",
    )
    actual_texts = Counter(prose for _, prose in definitions)
    for identity, prose in expected.items():
        actual = [body for found, body in definitions if found == identity]
        assert actual == [prose] and actual_texts[prose] == 1, message(
            f"decoded fact {identity} differs or is defined more than once: {actual}",
            "one semantic definition survives wrapping and Markdown safety escaping, not necessarily a contiguous byte substring",
            "keep the independently decoded id/text pair once in its owning Facts item",
        )
        assert not any(prose in block for block in other_blocks), message(
            f"decoded fact {identity} occurs outside its Facts item",
            "a copy in another subsection remains a duplicate even when safely wrapped or escaped",
            "emit ids and structured scalars in all non-Facts blocks",
        )


def test_document_keeps_literal_code_and_decodes_only_surrounding_prose():
    """L-document-once; local observer controls, not production observations."""
    submitted = (
        r"# Current `\*` and `&amp;` stay exact; "
        "outside * markers & signs wrap safely."
    )
    documents = [{"facts": [{"id": "F-Literal", "text": submitted}]}]
    published = (
        "## Shared design\n\n### Facts (Shared design)\n\n"
        r"- F-Literal: \# Current `\*` and `&amp;` stay exact; outside \*"
        "\n  markers &amp; signs wrap safely.\n"
    )
    assert decoded_markdown_text(submitted, submitted=True) == submitted, message(
        "submitted literal meaning was changed by the expected-value decoder",
        "the source definition, not the publisher's escaping, supplies the independent meaning",
        "preserve submitted prose and literal code contents",
    )
    assert decoded_markdown_text(published.split("- F-Literal: ", 1)[1]) == submitted, (
        message(
            "valid wrapping or prose escaping changed the decoded meaning",
            "a capable document observer must accept safe publication while keeping code literal",
            "decode escapes and entities only outside code spans and join wrapped prose",
        )
    )
    assert_document(published, documents)
    for corrupted in (
        published.replace(r"`\*`", "`*`"),
        published.replace("`&amp;`", "`&`"),
    ):
        with pytest.raises(AssertionError, match="decoded fact F-Literal differs"):
            assert_document(corrupted, documents)


def assert_compiled_headings(journey, shared, values):
    """L-compiled-heading: independently derive scope labels, not author titles."""
    stored = json.loads(journey.bytes())
    expected = [(None, "Shared design", stored["shared_design"]["authority_locator"])]
    expected.extend(
        (position, f"Value {position}", record["authority"]["authority_locator"])
        for position, record in enumerate(stored["values"], 1)
    )
    bindings = dict(journey.bindings)
    for position, title, locator in expected:
        assert locator.split("#", 1)[1] == title, message(
            "bound locator has an author-controlled heading",
            "normalized scope identity determines the section title",
            "compile the shared or numbered value heading",
        )
        marker = "AUTHORITY" if position is None else "DOCUMENT"
        assert f"{marker}: {locator}" in bindings[position].stdout, message(
            "public bind output omitted its compiled locator",
            "operators need the actual normalized authority identity through the existing scope marker",
            f"print the bound compiled locator through {marker}, without an alias",
        )
        if position is not None:
            assert f"AUTHORITY: {locator}" not in bindings[position].stdout, message(
                "value binding introduced an alias locator marker",
                "the existing value contract has the sole DOCUMENT marker",
                "preserve DOCUMENT for value publication and retry",
            )
        titles = re.findall(
            r"(?m)^#{1,6}\s+([^\n]+)$",
            (journey.root / locator.split("#", 1)[0]).read_text(),
        )
        assert titles.count(title) == 1, message(
            "compiled scope heading is absent or duplicated",
            "changing a locator alone does not establish the published identity",
            "publish each compiled scope heading once",
        )
    assert_document(journey.document(), [shared, *values])


def assert_provenance(shared, values):
    mapping = load("run11-fact-map.json")
    full_catalog = catalog(shared, *values)
    sources = {entry["name"]: entry for entry in mapping["sources"]}
    population = mapping["population"]
    originals = {}
    assert set(sources) == {
        "shared-manifest.json",
        "value-1-manifest.json",
        "value-2-manifest.json",
        "value-3-manifest.json",
        "run11-packet-1",
        "run11-packet-2",
        "run11-packet-3",
    }, message(
        "source population was narrowed",
        "full current compact and historical provenance must be accounted for",
        "enumerate every supplied source, not a tiny demonstration",
    )
    for name, source in sources.items():
        locator = source["locator"]
        raw = frozen_bytes(mapping, name)
        assert hashlib.sha256(raw).hexdigest() == source["sha256"], message(
            f"frozen source {name} changed",
            "independent source meaning must match its unchanged external identity",
            "restore the exact source snapshot inside the declared repository fixture",
        )
        source_value = (
            json.loads(raw)
            if name.endswith(".json")
            else json.JSONDecoder().raw_decode(raw.decode().split(MARKER, 1)[1])[0]
        )
        originals[name] = source_value
        expected_paths = {
            "/" + "/".join(str(x).replace("~", "~0").replace("/", "~1") for x in path)
            for path, _ in walk(source_value)
        }
        observed_paths = {
            entry["pointer"] for entry in population if entry["source"] == name
        }
        assert expected_paths <= observed_paths, message(
            f"source {name} omitted paths {expected_paths - observed_paths}",
            "all source entries need a retained current fact or external evidence locator",
            "map the complete source population without silently dropping facts",
        )
        for entry in (entry for entry in population if entry["source"] == name):
            parts = [
                part.replace("~1", "/").replace("~0", "~")
                for part in entry["pointer"].split("/")[1:]
            ]
            observed = source_value
            for part in parts:
                observed = (
                    observed[int(part)]
                    if isinstance(observed, list)
                    else observed[part]
                )
            assert semantic_hash(observed) == entry["sha256"], message(
                f"source entry digest changed at {entry['pointer']}",
                "a locator alone cannot prove current semantic provenance",
                "bind the exact unchanged source entry",
            )
            if "fact_id" in entry:
                assert entry["fact_id"] in full_catalog, message(
                    "mapped current fact is absent",
                    "provenance cannot disguise dropped operational facts",
                    "retain the mapped catalog id",
                )
                identity = entry["fact_id"]
                expected_text = mapping.get("label_derivations", {}).get(
                    identity, observed
                )
                assert (
                    isinstance(expected_text, str)
                    and " ".join(full_catalog[identity].split()).casefold()
                    == " ".join(expected_text.split()).casefold()
                ), message(
                    f"mapped source meaning changed for {identity}",
                    "a source hash cannot justify an unrelated fixture fact",
                    "retain the unchanged source text or its explicitly recorded property-label derivation",
                )
            else:
                assert entry["evidence_locator"] == locator + "#" + entry["pointer"], (
                    message(
                        "external evidence metadata does not identify its original source",
                        "the original locator stays provenance metadata, never a runtime dependency",
                        "retain the unchanged source locator and entry pointer alongside its frozen bytes",
                    )
                )
    for index, value in enumerate(values, 1):
        assert (
            value["verification"]
            == originals[f"value-{index}-manifest.json"]["verification"]
        ), message(
            "value verification argv changed during transcription",
            "representation change must preserve the independently frozen native recipe",
            "copy ordered argv and index unchanged",
        )
    assert (
        shared["verification"] == originals["shared-manifest.json"]["verification"]
    ), message(
        "shared verification argv changed",
        "inherited obligations select these independently frozen actual commands",
        "retain every shared argv unchanged",
    )
    source = originals["shared-manifest.json"]
    source_entries = {
        (entry["source"], entry["pointer"]): entry for entry in population
    }
    for document, name in zip(
        [shared, *values],
        [
            "shared-manifest.json",
            "value-1-manifest.json",
            "value-2-manifest.json",
            "value-3-manifest.json",
        ],
        strict=True,
    ):
        source = originals[name]
        for field in ("oracle", "acceptance_supports", "oracle_verification_index"):
            assert document[field] == source[field], message(
                f"{name}:{field} changed during transcription",
                "a normalized handoff must not silently change existing executable obligations",
                "preserve the independently frozen locator, supports and selected command index",
            )
        for kind, field in (
            ("targets", None),
            ("impact_closure", "items"),
            ("architectural_tests", "obligations"),
            ("contract_tests", "obligations"),
            ("agreement_analysis", "parties"),
        ):
            record_source_name = (
                "shared-manifest.json"
                if name != "shared-manifest.json"
                and kind in mapping["selection_rules"]["structured_fields_from_shared"]
                else name
            )
            record_source = originals[record_source_name]
            expected_records = (
                record_source[kind]
                if field is None
                else record_source[kind].get(field, [])
            )
            actual_records = (
                document[kind] if field is None else document[kind].get(field, [])
            )
            # Shared obligations are deliberately selected by id, not copied.
            if (
                name != "shared-manifest.json"
                and field in ("obligations", "parties")
                and not actual_records
            ):
                assert {record["id"] for record in records(shared, kind)} <= {
                    item["ref"] for item in document["inherits"]
                }, message(
                    "a transcribed shared obligation was not selected",
                    "empty local lists are valid only when their shared meaning remains reachable",
                    "select all applicable shared record identities",
                )
                continue
            assert len(actual_records) == len(expected_records), message(
                f"{name}:{kind} population changed",
                "the full doctor design retains every test, party, target and impact",
                "transcribe the complete current record population",
            )
            for index, (expected_record, actual_record) in enumerate(
                zip(expected_records, actual_records, strict=True)
            ):
                for key, expected_value in expected_record.items():
                    actual_value = actual_record[key]
                    if isinstance(actual_value, dict) and set(actual_value) == {"ref"}:
                        pointer = (
                            f"/{kind}/"
                            + (f"{field}/" if field else "")
                            + f"{index}/{key}"
                        )
                        mapped = source_entries[(record_source_name, pointer)][
                            "fact_id"
                        ]
                        assert actual_value["ref"] == mapped, message(
                            f"{name}:{pointer} changed source identity",
                            "a fixture must not choose its own convenient expected meaning",
                            "use the independently source-mapped stable fact id",
                        )
                        expected_value = mapping.get("label_derivations", {}).get(
                            mapped, expected_value
                        )
                        actual_value = full_catalog[mapped]
                    assert actual_value == expected_value, message(
                        f"{name}:{kind} field {key} lost current meaning",
                        "normalization changes representation, never substantive doctor obligations",
                        "retain the unchanged source scalar or explicit reviewed source-frame derivation",
                    )

        # Independent v6 sources determine actual operational selections, not
        # catalog presence alone. An unreferenced retained text does not pass.
        def source_ref(source_name, pointer):
            return {"ref": source_entries[(source_name, pointer)]["fact_id"]}

        def unique_refs(refs):
            return list({ref["ref"]: ref for ref in refs}.values())

        if name == "shared-manifest.json":
            for field in ("decisions", "constraints"):
                expected_refs = [
                    source_ref(name, f"/{field}/{index}")
                    for index in range(len(source[field]))
                ]
                assert document[field] == expected_refs, message(
                    f"shared {field} source selections changed",
                    "keeping catalog text without its decision/constraint selection loses meaning",
                    "retain every independently frozen current selection",
                )
        else:
            rules = mapping["selection_rules"]
            expected_decisions = [
                source_ref("shared-manifest.json", f"/decisions/{index}")
                for index in range(len(originals["shared-manifest.json"]["decisions"]))
            ]
            expected_decisions += [
                source_ref(name, f"/decisions/{index}")
                for index in rules["own_decision_source_indexes"]
            ]
            expected_decisions += [
                source_ref(name, f"/public_oracle/{field}")
                for field in rules["own_public_oracle_fields"]
            ]

            def source_structure(node, path):
                pointer = "/" + "/".join(map(str, path))
                entry = source_entries.get(("shared-manifest.json", pointer), {})
                if "fact_id" in entry:
                    return {"ref": entry["fact_id"]}
                if isinstance(node, dict):
                    return {
                        key: source_structure(child, path + (key,))
                        for key, child in node.items()
                    }
                if isinstance(node, list):
                    return [
                        source_structure(child, path + (index,))
                        for index, child in enumerate(node)
                    ]
                return node

            for field in rules["structured_fields_from_shared"]:
                expected_structure = source_structure(
                    originals["shared-manifest.json"][field], (field,)
                )
                assert document[field] == expected_structure, message(
                    f"{name} current structured {field} lost its source relationship",
                    "a reason-only constraint does not retain paths, dispositions or failure outcomes",
                    "carry the applicable value-own structured dependency with its scalar fields and shared FactRefs",
                )
            expected_constraints = [
                source_ref("shared-manifest.json", f"/constraints/{index}")
                for index in range(
                    len(originals["shared-manifest.json"]["constraints"])
                )
            ]
            expected_constraints += [
                source_ref(name, f"/constraints/{index}")
                for index in range(len(source.get("constraints", [])))
            ]
            assert document["decisions"] == unique_refs(
                expected_decisions
            ) and document["constraints"] == unique_refs(expected_constraints), message(
                f"{name} source decision/constraint selection differs",
                "full original operational meaning requires actual selected references, not a parked catalog",
                "retain source-derived decisions and common operational constraints in their prescribed order",
            )
            selected_ids = reference_ids(document["inherits"])
            typed_ids = {
                record["subject"]["ref"] if field == "closures" else record["id"]
                for section in shared["architect_handoff"]["sections"]
                for field in ("laws", "refuted", "claims", "models", "closures")
                for record in section["status"].get("payload", {}).get(field, [])
            }
            manifest_ids = {
                record["id"]
                for kind in (
                    "architectural_tests",
                    "contract_tests",
                    "agreement_analysis",
                )
                for record in records(shared, kind)
            }
            assert selected_ids == typed_ids | manifest_ids, message(
                "full doctor shared selections changed",
                "all source-selected tests, parties and typed relations must reach each current role",
                "retain the complete independent v6 selection inventory",
            )
        # Every retained typed source leaf has a frozen-source identity above;
        # require complete operational typed record population, not a reduced
        # targets/tests/parties-only account.
        original_sections = {
            section["kind"]: section
            for section in source.get("architect_handoff", {}).get("sections", [])
            if section["kind"] != "receipts"
        }
        current_sections = {
            section["kind"]: section
            for section in document.get("architect_handoff", {}).get("sections", [])
        }
        assert set(current_sections) == set(original_sections), message(
            "current typed section population changed",
            "only evidence-body sections retire; operative law/model/closure/construction metadata remains",
            "retain every current typed kind from the independent source",
        )
        for kind, section in original_sections.items():
            original_payload = section["status"].get("payload", {})
            current_payload = current_sections[kind]["status"].get("payload", {})
            for field in (
                "laws",
                "refuted",
                "claims",
                "models",
                "closures",
                "observations",
                "constructors",
                "generators",
            ):
                if field in original_payload:
                    assert len(current_payload[field]) == len(
                        original_payload[field]
                    ), message(
                        f"{name}:{kind}/{field} was reduced",
                        "retained typed relations must not silently disappear",
                        "preserve the full current typed record population",
                    )
            for path, expected_value in walk(section):
                if path[-1] == "text" and kind == "model":
                    continue
                current_value = at(current_sections[kind], path)
                if isinstance(current_value, dict) and set(current_value) == {"ref"}:
                    pointer = (
                        "/architect_handoff/sections/"
                        + str(source["architect_handoff"]["sections"].index(section))
                        + "/"
                        + "/".join(map(str, path))
                    )
                    identity = source_entries[(name, pointer)]["fact_id"]
                    assert current_value["ref"] == identity and full_catalog[
                        identity
                    ] == mapping.get("label_derivations", {}).get(
                        identity, expected_value
                    ), message(
                        "typed semantic source relation changed",
                        "retained metadata must refer to its independently mapped current meaning",
                        "preserve its source identity and explicit source-frame derivation",
                    )
                else:
                    assert current_value == expected_value, message(
                        "typed scalar source relation changed",
                        "counts alone do not conserve law vocabulary, ownership, model symbols or closure relations",
                        "retain every operational structured scalar from the frozen source",
                    )
            if kind == "model":
                for old_model, new_model in zip(
                    original_payload["models"], current_payload["models"], strict=True
                ):
                    assert new_model["source"] == {
                        "path": old_model["path"],
                        "sha256": hashlib.sha256(
                            old_model["text"].encode()
                        ).hexdigest(),
                    }, message(
                        "external model evidence identity changed",
                        "model bytes retire from the handoff but their declared locator and identity remain",
                        "cite the independently frozen model bytes by locator and digest only",
                    )
    baseline = mapping["authoritative_run11"]
    original_raw = frozen_bytes(mapping, baseline["immutable_input"])
    assert (
        hashlib.sha256(original_raw).hexdigest()
        == baseline["sha256"]
        == "19091412673937fedf974303f015e392e2d761c014e21f058baea7a6019565b8"
    ), message(
        "authoritative run11 source identity changed",
        "current compact reconciliation must remain tied to the original unchanged doctor authority",
        "retain the independently frozen source bytes and original external locator",
    )
    original = json.loads(original_raw)
    authorities = {
        "shared": original["shared_design"]["design"],
        **{
            f"value-{index}": record["authority"]
            for index, record in enumerate(original["values"], 1)
        },
    }
    expected_members = set()
    for scope, authority in authorities.items():
        for field in (
            "decisions",
            "constraints",
            "targets",
            "architectural_tests",
            "contract_tests",
            "agreement_analysis",
            "impact_closure",
            "verification",
        ):
            field_value = authority.get(field, [])
            members = (
                field_value.get(
                    "parties",
                    field_value.get("obligations", field_value.get("items", [])),
                )
                if isinstance(field_value, dict)
                else field_value
            )
            expected_members.update(
                (scope, field, index) for index in range(len(members))
            )
    assert {
        (entry["scope"], entry["field"], entry["index"])
        for entry in baseline["population"]
    } == expected_members, message(
        "authoritative source population was narrowed",
        "all current/source obligations need a retained fact or explicit external evidence disposition",
        "account for every original decision, constraint, test, party, target, impact and actual command",
    )
    for entry in baseline["population"]:
        population_value = authorities[entry["scope"]][entry["field"]]
        members = (
            population_value.get(
                "parties",
                population_value.get("obligations", population_value.get("items", [])),
            )
            if isinstance(population_value, dict)
            else population_value
        )
        assert semantic_hash(members[entry["index"]]) == entry["sha256"], message(
            "authoritative source member lost its external identity",
            "unmatched historical/source evidence must stay external rather than silently vanish",
            "retain its exact source digest and locator in the declared provenance support",
        )
        relation = entry["current_relationship"]
        scope_index = (
            0 if entry["scope"] == "shared" else int(entry["scope"].split("-")[1])
        )
        document = [shared, *values][scope_index]
        if relation["tag"] == "evidence_only":
            assert (
                relation["basis"] and relation["locator"] == entry["evidence_locator"]
            ), message(
                "original evidence disposition lacks a reviewed basis",
                "historical evidence must not be silently relabeled as current semantics",
                "retain its explicit evidence-only disposition and locator",
            )
        elif relation["tag"] == "verification":
            assert (
                document["verification"][relation["index"]] == members[entry["index"]]
            ), message(
                "native original recipe relationship changed",
                "v6 source authorization does not invent a substitute verification",
                "retain original ordered argv",
            )
        else:
            expected_ids = set(relation.get("fact_ids", []))
            assert expected_ids <= full_catalog.keys(), message(
                "original operational relationship has absent current facts",
                "a source accounting locator alone does not conserve operative meaning",
                "retain the explicitly related current facts",
            )
            if scope_index:
                reachable = reachable_catalog(shared, document)
                assert expected_ids <= reachable.keys(), message(
                    f"original operative relationship lost from {entry['scope']}: {relation}",
                    "parked text is not current role retention",
                    "select every current related fact through the declared public reference slots",
                )
                if relation["tag"] in (
                    "own_decision",
                    "shared_decision",
                    "shared_selection",
                ):
                    assert expected_ids <= reference_ids(document["decisions"]), (
                        message(
                            "original decision has no selected current decision",
                            "text-only catalog conservation is insufficient",
                            "retain the source-driven operational decision references",
                        )
                    )
                if "record_id" in relation:
                    assert relation["record_id"] in reference_ids(
                        document["inherits"]
                    ), message(
                        "original law was not selected",
                        "typed operational relations cannot be evidence-only",
                        "select the current law and dependencies",
                    )


@dataclass(frozen=True)
class CurrentFacts:
    shared_texts: tuple[str, ...]
    own_texts: tuple[str, ...]
    values: int
    suffix: str


@st.composite
def current_facts(draw):
    # Nonempty shared catalog supplies required semantic slots; empty own catalogs
    # and removal to the empty catalog are constructed in separate refusal arms.
    printable = st.characters(
        categories=(
            "Lu",
            "Ll",
            "Lt",
            "Lm",
            "Lo",
            "Nd",
            "Nl",
            "No",
            "Pc",
            "Pd",
            "Ps",
            "Pe",
            "Pi",
            "Pf",
            "Po",
            "Sm",
            "Sc",
            "Sk",
            "So",
            "Zs",
        )
    )
    shared = tuple(
        "Generated " + text
        for text in draw(
            st.lists(
                st.text(printable, min_size=1, max_size=30), min_size=1, max_size=3
            )
        )
    )
    own = tuple(
        "Generated " + text
        for text in draw(
            st.lists(
                st.text(printable, min_size=1, max_size=30), min_size=0, max_size=3
            )
        )
    )
    return CurrentFacts(
        shared,
        own,
        draw(st.integers(1, 3)),
        draw(
            st.text(
                "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
                min_size=0,
                max_size=3,
            )
        ),
    )


def small_designs(case):
    facts = [
        {"id": f"S{i}{case.suffix}", "text": f"Shared-{i}: {text} |"}
        for i, text in enumerate(case.shared_texts)
    ]
    ref = {"ref": facts[0]["id"]}
    shared = {
        "schema_version": 2,
        "facts": facts,
        "purpose": ref,
        "constraints": [ref],
        "decisions": [ref],
        "targets": [
            {"path": "nwave_ai/doctor/runner.py", "decision": "EXTEND", "reason": ref}
        ],
        "paradigm": "object_oriented",
        "reuse_analysis": {"candidates": []},
        "prefactoring": {"applicability": "not_applicable", "reason": ref},
        "agreement_analysis": {
            "applicability": "applicable",
            "parties": [
                {
                    "id": "AP1",
                    "contract": "doctor-current-record",
                    "role": "producer",
                    "locator": "nwave_ai/doctor/runner.py:1",
                    "decision": "MIGRATED",
                    "reason": ref,
                },
                {
                    "id": "AP2",
                    "contract": "doctor-current-record",
                    "role": "consumer",
                    "locator": "nwave_ai/cli.py:1",
                    "decision": "MIGRATED",
                    "reason": ref,
                },
            ],
        },
        "architectural_tests": {"applicability": "not_applicable", "reason": ref},
        "contract_tests": {
            "applicability": "applicable",
            "obligations": [
                {
                    "id": "CT1",
                    "obligation": ref,
                    "contract": "doctor-current-record",
                    "producer": "nwave_ai/doctor/runner.py:1",
                    "consumer": "nwave_ai/cli.py:1",
                    "observation": ref,
                    "oracle": "tests/nwave_ai/doctor/test_saved_readings.py",
                    "verification_index": 0,
                }
            ],
        },
        "impact_closure": {
            "applicability": "applicable",
            "items": [
                {
                    "kind": "runtime",
                    "locator": "nwave_ai/doctor/runner.py",
                    "decision": "CHANGED",
                    "reason": ref,
                },
                {
                    "kind": "consumer",
                    "locator": "nwave_ai/cli.py:1",
                    "decision": "MIGRATED",
                    "reason": ref,
                },
            ],
        },
        "boundaries": {"applicability": "not_applicable", "reason": ref},
        "public_oracle": dict.fromkeys(
            ("observation", "stimulus", "expected", "falsifier"), ref
        ),
        "oracle": "tests/nwave_ai/doctor/test_saved_readings.py",
        "acceptance_supports": [],
        "verification": [
            [
                "python3",
                "-m",
                "pytest",
                "-q",
                "tests/nwave_ai/doctor/test_saved_readings.py",
            ]
        ],
        "oracle_verification_index": 0,
    }
    shared["architectural_tests"] = {
        "applicability": "applicable",
        "obligations": [
            {
                "id": "AR1",
                "obligation": ref,
                "oracle": shared["oracle"],
                "verification_index": 0,
            }
        ],
    }
    unused_decision = {
        "id": "UnusedD",
        "text": "A current decision for an unrelated outcome",
    }
    unused_constraint = {
        "id": "UnusedC",
        "text": "A current constraint for an unrelated outcome",
    }
    shared["facts"].extend((unused_decision, unused_constraint))
    shared["decisions"].append({"ref": "UnusedD"})
    shared["constraints"].append({"ref": "UnusedC"})
    shared["facts"].append(
        {"id": "UTyped", "text": "An operational law for an unrelated outcome"}
    )
    law = {
        "id": "LCurrent",
        "statement": ref,
        "kind": "invariant",
        "layer": "adapter",
        "owner": "nwave_ai/doctor/runner.py",
        "uses": ["OCurrent", "CCurrent"],
        "treatment": {
            "tag": "broad",
            "generator": "GCurrent",
            "independent_observation": ref,
            "falsifier": {"description": ref},
        },
        "evidence": {"tag": "to_run"},
    }
    unselected_law = copy.deepcopy(law)
    unselected_law.update(id="LOther", statement={"ref": "UTyped"})
    shared["architect_handoff"] = {
        "sections": [
            {
                "kind": "laws",
                "scope": "shared",
                "status": {
                    "tag": "applicable",
                    "payload": {
                        "observations": [
                            {
                                "id": "OCurrent",
                                "description": ref,
                                "result_type": "dict",
                                "cannot_distinguish": ref,
                            }
                        ],
                        "constructors": [
                            {"id": "CCurrent", "signature": "run(context) -> report"}
                        ],
                        "equality": {"under": ["OCurrent"], "definition": ref},
                        "generators": [
                            {
                                "id": "GCurrent",
                                "domain": ref,
                                "size_bound": 6,
                                "seed_policy": ref,
                                "must_include": [ref],
                                "depth_bound": 1,
                            }
                        ],
                        "laws": [law, unselected_law],
                        "refuted": [],
                    },
                },
            }
        ]
    }
    values = []
    for position in range(1, case.values + 1):
        value = copy.deepcopy(shared)
        value["constraints"] = [ref]
        value["facts"] = [
            {
                "id": f"V{position}{i}{case.suffix}",
                "text": f"Own-{position}-{i}: {text} |",
            }
            for i, text in enumerate(case.own_texts)
        ]
        value["decisions"] = [ref, *({"ref": item["id"]} for item in value["facts"])]
        value["inherits"] = [
            {"ref": "CT1"},
            {"ref": "AP1"},
            {"ref": "AP2"},
            {"ref": "AR1"},
        ]
        value["inherits"].append({"ref": "LCurrent"})
        value.pop("architect_handoff")
        value["agreement_analysis"]["parties"] = []
        value["contract_tests"]["obligations"] = []
        value["architectural_tests"]["obligations"] = []
        value["impact_closure"]["items"] = value["impact_closure"]["items"][:1]
        value["verification"] = [
            [
                "python3",
                "-m",
                "pytest",
                "-q",
                "tests/nwave_ai/test_truthful_comparisons.py",
            ]
        ]
        value["oracle"] = "tests/nwave_ai/test_truthful_comparisons.py"
        if value["facts"]:
            own_ref = {"ref": value["facts"][0]["id"]}
            value["constraints"].append(own_ref)
            own_contract = copy.deepcopy(shared["contract_tests"]["obligations"][0])
            own_contract.update(
                id=f"OC{position}",
                obligation=own_ref,
                observation=own_ref,
                oracle=value["oracle"],
            )
            value["contract_tests"]["obligations"].append(own_contract)
            own_party = copy.deepcopy(shared["agreement_analysis"]["parties"][0])
            own_party.update(id=f"OP{position}", reason=own_ref)
            value["agreement_analysis"]["parties"].append(own_party)
        values.append(value)
    return shared, values


def test_current_purpose_cannot_be_replaced_by_expanded_prose():
    """L-catalog-once; m-expand observer control, not a production observation."""
    shared, values = small_designs(
        CurrentFacts(("Current shared comparison",), ("Current own comparison",), 1, "")
    )
    value = values[0]
    selected = copy.deepcopy(value)
    assert_selected_references(selected, value)
    selected["purpose"] = (
        "Current purpose: " + catalog(shared, value)[value["purpose"]["ref"]]
    )
    with pytest.raises(AssertionError, match="selected purpose changed"):
        assert_selected_references(selected, value)


@pytest.mark.walking_skeleton
def test_current_doctor_facts_reach_each_receiving_role_once():
    """L-doctor-complete; current facts, parties, tests and impacts survive."""
    shared = load("shared.json")
    values = [load(f"value-{position}.json") for position in (1, 2, 3)]
    assert_provenance(shared, values)
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, fork=True).current(shared, values)
        before = journey.bytes()
        for position, value in enumerate(values, 1):
            packet, first = journey.prompt(position)
            again, second = journey.prompt(position)
            assert_packet(packet, shared, value)
            assert_inherited(packet, shared, value)
            assert packet == again and first.stdout == second.stdout, message(
                "unchanged render inputs produced different packets/prompts",
                "the host needs repeatable current facts",
                "make real rendering deterministic without remeasuring or expanding evidence",
            )
        assert_compiled_headings(journey, shared, values)
        assert journey.bytes() == before, message(
            "prompt consumption mutated authority",
            "rendering observes accepted state",
            "keep prompt generation read-only",
        )


@pytest.mark.parametrize("carrier", ("authority", "heading"))
def test_author_titles_cannot_copy_a_current_definition(carrier):
    """L-compiled-heading; titles are not a second author prose slot."""
    shared = load("shared.json")
    candidate = copy.deepcopy(shared)
    text = shared["facts"][0]["text"]
    candidate[carrier] = {"heading": text} if carrier == "authority" else text
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, count=1)
        journey.refused(
            candidate, None, "InvalidDesignDocument", ["DesignKeyNotInGrammar"]
        )


def write_detached(journey, shared, value, *, context=True):
    """Real manifest files and byte-bound catalog locators, never a fake catalog."""
    entries = []
    for name, document in (
        ("catalog-shared.json", shared),
        ("catalog-value.json", value),
    ):
        raw = json.dumps(document, ensure_ascii=False).encode()
        (journey.root / name).write_bytes(raw)
        entries.append({"path": name, "sha256": hashlib.sha256(raw).hexdigest()})
    document = {
        "sections": copy.deepcopy(
            shared["architect_handoff"]["sections"]
            + value["architect_handoff"]["sections"]
        )
    }
    if context:
        document["catalog"] = entries
    (journey.root / "typed-current.json").write_text(
        json.dumps(document, ensure_ascii=False)
    )
    return document


def inspect_handoff(journey, command, *, detached):
    args = ["handoff", command]
    if detached:
        args += ["typed-current.json", "--dir", "."]
    if command == "prompt":
        args += [
            "--role",
            "nw-acceptance-designer",
            "--value",
            "1",
            "--root-context",
            "root-context.md",
            "--template-dir",
            str(CHECKOUT / "nWave/templates/architect-handoff"),
            "--skills-dir",
            str(CHECKOUT / "nWave/skills"),
        ]
    return journey.invoke(*args)


@pytest.mark.parametrize("command", ("render", "summary", "prompt", "check"))
def test_detached_references_require_their_declared_catalog(command):
    """Reference context: structural checks must distinguish UNRUN from PASS."""
    shared, value = load("shared.json"), load("value-1.json")
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, count=1).current(shared, [value])
        write_detached(journey, shared, value, context=False)
        before = journey.bytes()
        result = inspect_handoff(journey, command, detached=True)
        report = result.stdout + result.stderr
        assert result.code != 0 and "ArchitectHandoffCatalogUnavailable" in report, (
            message(
                "detached references silently used absent or implicit context: "
                + report,
                "a bound graph is not a fallback for missing detached catalog ownership",
                "refuse unresolved detached context with the declared catalog-unavailable diagnostic",
            )
        )
        if command == "check":
            assert "UNRUN" in report, message(
                "text-dependent rules were reported without their unavailable context",
                "structural checking does not establish reference/template/trace rules",
                "retain structural results and aggregate context-dependent rules as UNRUN",
            )
            assert "M2" in report and "S3" in report, message(
                "the aggregate omitted a declared text-dependent rule",
                "template and trace rendering must not be implicitly reported as passed without reference context",
                "name both unavailable rule families in the UNRUN aggregate",
            )
        else:
            assert (
                "HOW:" in report and "catalog" in report and "--repo-root" in report
            ), message(
                "catalog refusal omitted the two declared producing remedies",
                "operators need to choose explicit detached context or native scope",
                "name catalog locators and the native repository route",
            )
        assert journey.bytes() == before, message(
            "detached context refusal mutated bound authority",
            "inspection is not an implicit context repair",
            "preserve bound state",
        )


@pytest.mark.parametrize(
    "detached", (False, True), ids=("native-bound-graph", "detached-manifest-locators")
)
def test_catalog_context_retains_rendered_and_aggregate_meaning(detached):
    """Reference context: native and detached real consumers retain current facts."""
    shared, value = load("shared.json"), load("value-1.json")
    definitions = catalog(shared, value)
    law_section = next(
        section
        for section in shared["architect_handoff"]["sections"]
        if section["kind"] == "laws"
    )
    statement = definitions[
        law_section["status"]["payload"]["laws"][0]["statement"]["ref"]
    ]
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, count=1).current(shared, [value])
        write_detached(journey, shared, value)
        rendered = inspect_handoff(journey, "render", detached=detached).admitted(
            "current contextual render"
        )
        assert statement in rendered.stdout, message(
            "rendered law retained a reference object instead of its current meaning",
            "human rendering requires the catalog, not object stringification",
            "resolve rendered semantic references through the explicit current catalog",
        )
        summary = json.loads(
            inspect_handoff(journey, "summary", detached=detached)
            .admitted("current contextual summary")
            .stdout
        )
        expected_claims = Counter(
            {"PASS": 0, "BLOCKED": 0, "NOT_APPLICABLE": 0, "INHERITED": 0}
        )
        expected_subjects = set()
        for document in (shared, value):
            for section in document["architect_handoff"]["sections"]:
                if section["kind"] != "closure":
                    continue
                for closure in section["status"]["payload"]["closures"]:
                    expected_subjects.add(
                        section["scope"] + "/" + definitions[closure["subject"]["ref"]]
                    )
                    for axis in (
                        "safety",
                        "inhabitation",
                        "public_reachability",
                        "liveness",
                    ):
                        entry = closure[axis]
                        expected_claims[
                            entry["design"]
                            if entry["tag"] == "claim"
                            else "NOT_APPLICABLE"
                            if entry["tag"] == "not_applicable"
                            else "INHERITED"
                        ] += 1
        assert (
            summary["claims"] == dict(expected_claims)
            and set(summary["closure"]) == expected_subjects
        ), message(
            "summary lost contextual closure identities or axis counts",
            "aggregate counts must retain the independently declared current subject population",
            "resolve subject labels and preserve every current closure axis",
        )
        prompt = inspect_handoff(journey, "prompt", detached=detached).admitted(
            "current contextual prompt"
        )
        assert MARKER in prompt.stdout, message(
            "contextual prompt lacks its real role payload",
            "an id substring is not a typed observation",
            "emit the declared current public role handover",
        )
        packet = json.JSONDecoder().raw_decode(prompt.stdout.split(MARKER, 1)[1])[0]
        assert_packet(packet, shared, value)
        assert_inherited(packet, shared, value)
        valid = inspect_handoff(journey, "check", detached=detached)
        report = valid.stdout + valid.stderr
        assert valid.code in (0, 1, 3) and re.search(
            r"(?m)^\d+ defects?(?:\(s\))?\.", report
        ), message(
            "valid-context check did not produce its actual aggregate: " + report,
            "usage, decoding or environment failure is not a valid template control",
            "run the declared checker and retain its complete defect/unrun aggregate",
        )
        assert "decoding failed" not in report.lower(), message(
            "valid-context control never reached contextual rules: " + report,
            "a decoder-only aggregate cannot establish M2 execution",
            "decode the complete current typed fixture and run its contextual rule family",
        )
        assert "ArchitectHandoffCatalogUnavailable" not in report, message(
            "valid context remained unavailable",
            "a valid catalog must actually enable contextual rules",
            "resolve through its digest-bound current catalog",
        )
        assert "[M2]" not in report and not re.search(
            r"(?:UNRUN|Not run:)[^\n]*\bM2\b", report, re.IGNORECASE
        ), message(
            "valid current templates fail or skip M2: " + report,
            "an always-failing checker cannot establish the negative placeholder observation",
            "run M2 against resolved valid current templates and preserve unrelated structural results honestly",
        )


@pytest.mark.parametrize("defect", ("digest", "id", "text"))
def test_detached_catalog_sources_refuse_identity_and_content_conflicts(defect):
    """Reference context: digest and smart-constructor merge defects are public refusals."""
    shared, value = load("shared.json"), load("value-1.json")
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, count=1).current(shared, [value])
        document = write_detached(journey, shared, value)
        if defect == "digest":
            document["catalog"][0]["sha256"] = "0" * 64
        else:
            clone = copy.deepcopy(shared)
            aliases = {record["id"]: "Q" + record["id"] for record in clone["facts"]}
            if defect == "id":
                aliases[clone["facts"][0]["id"]] = clone["facts"][0]["id"]
            for path, identity in list(walk(clone)):
                if path and path[-1] == "ref":
                    set_at(clone, path, aliases.get(identity, identity))
            for index, record in enumerate(clone["facts"]):
                record["id"] = aliases[record["id"]]
                if defect != "text" or index != 0:
                    record["text"] = "Detached current definition: " + record["text"]
            raw = json.dumps(clone, ensure_ascii=False).encode()
            (journey.root / "catalog-conflict.json").write_bytes(raw)
            document["catalog"].append(
                {
                    "path": "catalog-conflict.json",
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
        (journey.root / "typed-current.json").write_text(
            json.dumps(document, ensure_ascii=False)
        )
        before = journey.bytes()
        result = inspect_handoff(journey, "summary", detached=True)
        report = result.stdout + result.stderr
        assert result.code != 0, message(
            "invalid detached catalog was admitted",
            "locator digests and unique catalog definitions are context authority",
            "refuse digest or smart-constructor merge conflicts",
        )
        if defect != "digest":
            token = "DesignFactIdClash" if defect == "id" else "DesignFactTextRepeated"
            assert token in report, message(
                "context merge lost its declared catalog defect: " + report,
                "catalog construction has the same one owner and refusal vocabulary",
                "preserve the smart constructor diagnostic through the public inspection port",
            )
        assert journey.bytes() == before, message(
            "catalog conflict changed native binding",
            "external inspection cannot partially replace current authority",
            "leave bound graph unchanged",
        )


@pytest.mark.parametrize("atom_tag", ("action", "property"))
def test_placeholder_rules_resolve_current_catalog_text_before_checking(atom_tag):
    """M2: invalid placeholders in referenced text cannot escape text-dependent rules."""
    shared, value = load("shared.json"), load("value-1.json")
    model_section = next(
        section
        for section in shared["architect_handoff"]["sections"]
        if section["kind"] == "model"
    )
    atom = next(
        atom
        for atom in model_section["status"]["payload"]["models"][0]["atoms"]
        if atom["tag"] == atom_tag
    )
    identity = atom["template" if atom_tag == "action" else "statement"]["ref"]
    next(record for record in shared["facts"] if record["id"] == identity)["text"] = (
        "Current observation {catalog_context_absent}"
    )
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, count=1).current(
            load("shared.json"), [value]
        )
        write_detached(journey, shared, value)
        result = inspect_handoff(journey, "check", detached=True)
        report = result.stdout + result.stderr
        assert (
            result.code != 0 and "M2" in report and "catalog_context_absent" in report
        ), message(
            "placeholder rule did not inspect referenced current text: " + report,
            "checking the reference object bypasses the declared text rule",
            "resolve action templates and property statements before validating their state placeholders",
        )


def test_inline_handoff_files_cannot_override_the_producer_catalog():
    """Reference context: producer FILE input is not a detached context override."""
    shared, value = load("shared.json"), load("value-1.json")
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, count=1)
        document = write_detached(journey, shared, value)
        document["sections"] = copy.deepcopy(shared["architect_handoff"]["sections"])
        (journey.root / "typed-current.json").write_text(
            json.dumps(document, ensure_ascii=False)
        )
        candidate = copy.deepcopy(shared)
        candidate.pop("architect_handoff")
        journey.refused(
            candidate,
            None,
            "InvalidDesignDocument",
            ["DesignKeyNotInGrammar"],
            handoff_file="typed-current.json",
        )


@pytest.mark.parametrize(
    "kind,field",
    (
        ("laws", "laws"),
        ("laws", "refuted"),
        ("construction", "claims"),
        ("model", "models"),
        ("closure", "closures"),
        ("closure", "inherited"),
    ),
)
def test_unselected_typed_records_do_not_reach_the_current_role(kind, field):
    """L-catalog-once/L-resolve-retains; typed selectors and closure dependency."""
    shared, value = load("shared.json"), load("value-1.json")
    section = next(
        section
        for section in shared["architect_handoff"]["sections"]
        if section["kind"] == kind
    )
    record = section["status"]["payload"][
        "closures" if field == "inherited" else field
    ][0]
    identity = record["subject"]["ref"] if kind == "closure" else record["id"]
    value["inherits"] = [ref for ref in value["inherits"] if ref["ref"] != identity]
    if field == "inherited":
        own = next(
            section
            for section in value["architect_handoff"]["sections"]
            if section["kind"] == "closure"
        )
        own["status"]["payload"]["closures"][0]["liveness"] = {"tag": "inherited"}
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, count=1).current(shared, [value])
        packet, _ = journey.prompt(1)
        assert_packet(packet, shared, value)
        assert_inherited(packet, shared, value)


@PBT
@given(current_facts())
def test_generated_current_facts_have_one_packet_definition(case):
    """L-catalog-once; m-expand is the falsifier."""
    shared, values = small_designs(case)
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, count=case.values).current(shared, values)
        for position, value in enumerate(values, 1):
            packet, _ = journey.prompt(position)
            assert_packet(packet, shared, value)


@PBT
@given(current_facts())
def test_generated_current_facts_have_one_document_definition(case):
    """L-document-once; reference expansion outside Facts is the falsifier."""
    shared, values = small_designs(case)
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, count=case.values).current(shared, values)
        text = journey.document()
        assert_document(text, [shared, *values])


@PBT
@given(current_facts())
def test_generated_inherited_obligations_keep_their_original_commands(case):
    """L-resolve-retains; m-dropinherit and wrong-scope indexes falsify it."""
    shared, values = small_designs(case)
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, count=case.values).current(shared, values)
        for position, value in enumerate(values, 1):
            packet, _ = journey.prompt(position)
            assert_inherited(packet, shared, value)


def test_value_owned_laws_require_explicit_shared_vocabulary():
    """L-resolve-retains/L-unresolved-refused; no automatic vocabulary promotion."""
    shared, values = small_designs(
        CurrentFacts(("Current shared vocabulary",), ("Current own law",), 1, "")
    )
    value = values[0]
    shared_section = shared["architect_handoff"]["sections"][0]
    vocabulary = shared_section["status"]["payload"]
    own_ref = value["purpose"] = {"ref": value["facts"][0]["id"]}
    own_observation = copy.deepcopy(vocabulary["observations"][0])
    own_observation.update(
        id="OwnObservation", description=own_ref, cannot_distinguish=own_ref
    )
    own_constructor = copy.deepcopy(vocabulary["constructors"][0])
    own_constructor["id"] = "OwnConstructor"
    own_law = copy.deepcopy(vocabulary["laws"][0])
    own_law.update(
        id="OwnLaw",
        statement=own_ref,
        uses=["OwnObservation", "OwnConstructor", "OCurrent", "CCurrent"],
    )
    own_law["treatment"]["independent_observation"] = own_ref
    own_law["treatment"]["falsifier"]["description"] = own_ref
    own_payload = {
        "observations": [own_observation],
        "constructors": [own_constructor],
        "generators": [],
        "equality": {"under": ["OwnObservation", "OCurrent"], "definition": own_ref},
        "laws": [own_law],
        "refuted": [],
    }
    value["architect_handoff"] = {
        "sections": [
            {
                "kind": "laws",
                "scope": "value:1",
                "status": {"tag": "applicable", "payload": own_payload},
            }
        ]
    }
    vocabulary_ids = ("OCurrent", "CCurrent", "GCurrent")
    value["inherits"] = [
        ref for ref in value["inherits"] if ref["ref"] != "LCurrent"
    ] + [{"ref": identity} for identity in vocabulary_ids]
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, count=1).current(shared, [value])
        packet, _ = journey.prompt(1)
        assert_packet(packet, shared, value)
        assert_inherited(packet, shared, value)
        for identity in vocabulary_ids:
            missing = copy.deepcopy(value)
            missing["inherits"] = [
                ref for ref in missing["inherits"] if ref["ref"] != identity
            ]
            result = journey.refused(
                missing,
                1,
                "DesignInheritanceRefused",
                ["DesignFactUnresolved"],
                replace=True,
                ids=[identity],
            )
            assert re.search(
                r"\bvalues?(?:\s*[:=-]?\s*)1\b",
                result.stdout + result.stderr,
                re.IGNORECASE,
            ), message(
                f"missing vocabulary {identity} omitted dependent value1",
                "a shared id is not enough to locate its own-law consumer",
                "name the missing id and affected value in the same refusal",
            )


@PBT
@given(current_facts())
def test_generated_catalogs_and_reference_order_survive_restoration(case):
    """L-roundtrip; dropped ids, references or ordering falsify it."""
    shared, values = small_designs(case)
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, count=case.values).current(shared, values)
        journey.invoke("state", fork=True).admitted(
            "fresh process stored-state restoration"
        )
        restored = json.loads(journey.bytes())
        actual = [
            restored["shared_design"]["design"],
            *(item["authority"] for item in restored["values"]),
        ]
        for expected, observed in zip([shared, *values], actual, strict=True):
            for field in (
                "facts",
                "decisions",
                "constraints",
                "inherits",
                "agreement_analysis",
                "contract_tests",
                "public_oracle",
                "architect_handoff",
            ):
                assert observed.get(field, []) == expected.get(field, []), message(
                    f"restored {field} changed: {observed.get(field)} != {expected.get(field)}",
                    "the persistent carrier must retain ordered definitions/references and structured obligations",
                    "preserve the submitted normalized meaning in write/restore",
                )
        for position, value in enumerate(values, 1):
            packet, _ = journey.prompt(position, fork=True)
            assert (
                packet["selected_authority"]["decisions"] == value["decisions"]
                and packet["selected_authority"]["constraints"] == value["constraints"]
                and packet["selected_authority"].get("inherits", [])
                == value.get("inherits", [])
            ), message(
                "fresh public reader changed submitted reference order",
                "raw storage shape is not enough if the receiving consumer loses references",
                "retain ordered decisions, constraints and record selection in the real reader projection",
            )
            assert_packet(packet, shared, value)
            assert_inherited(packet, shared, value)
        with tempfile.TemporaryDirectory() as recovery_directory:
            recovery_journey = HandoffJourney(recovery_directory, count=1).current(
                shared, values[:1]
            )
            recovered, changed = recovery_journey.recovery(shared, values[0])
            current, _ = recovery_journey.prompt(1, fork=True)
            expected_current = reachable_catalog(changed, values[0])
            assert recovered.get("facts") == current.get("facts") == expected_current, (
                message(
                    "shared replacement was stale in public round-trip consumers",
                    "restoration/recovery must observe current shared text, not copied prior prose",
                    "use current resolved reachable facts in both produced packets",
                )
            )


@PBT
@given(current_facts())
def test_generated_repeated_definitions_are_refused_without_binding(case):
    """L-repeat-refused; m-copy, m-idclash and m-crossvalue falsify it."""
    shared, values = small_designs(case)
    # Every branch is constructed, never left to probabilistic reachability.
    for origin in ("within", "shared", "sibling"):
        for defect in ("id", "exact", "case_whitespace", "id_and_text"):
            with tempfile.TemporaryDirectory() as directory:
                journey = HandoffJourney(directory, count=max(2, case.values))
                journey.bind(shared).admitted("shared design")
                candidate = copy.deepcopy(values[0])
                source = shared["facts"][0]
                if origin == "sibling":
                    sibling = copy.deepcopy(values[0])
                    sibling["facts"].append(
                        {"id": "Sibling", "text": "Sibling: " + case.shared_texts[0]}
                    )
                    sibling["decisions"].append({"ref": "Sibling"})
                    journey.bind(sibling, 1).admitted("first sibling")
                    source = sibling["facts"][-1]
                    candidate = copy.deepcopy(
                        small_designs(
                            CurrentFacts(
                                case.shared_texts, case.own_texts, 2, case.suffix
                            )
                        )[1][1]
                    )
                if origin == "within":
                    candidate["facts"].append(
                        {"id": "Local", "text": "Local: " + case.shared_texts[0]}
                    )
                    source = candidate["facts"][-1]
                variant = (source["text"][0].swapcase() + source["text"][1:]).replace(
                    " ", "  "
                )
                item = {
                    "id": source["id"] if defect in ("id", "id_and_text") else "Fresh",
                    "text": "A different current fact"
                    if defect == "id"
                    else source["text"]
                    if defect != "case_whitespace"
                    else "  " + variant + "  ",
                }
                candidate["facts"].append(item)
                tokens = (
                    ["DesignFactIdClash"]
                    if defect == "id"
                    else ["DesignFactTextRepeated"]
                    if defect != "id_and_text"
                    else ["DesignFactIdClash", "DesignFactTextRepeated"]
                )
                journey.refused(
                    candidate,
                    2 if origin == "sibling" else 1,
                    "InvalidDesignDocument"
                    if origin == "within"
                    else "DesignInheritanceRefused",
                    tokens,
                )
                event(f"origin={origin};defect={defect}")


@PBT
@given(current_facts())
def test_generated_missing_references_cannot_discard_shared_obligations(case):
    """L-unresolved-refused; m-dangling is the falsifier."""
    shared, values = small_designs(case)
    for defect in (
        "fact",
        "record",
        "without_shared",
        "remove_fact",
        "remove_record",
        "two_missing",
    ):
        with tempfile.TemporaryDirectory() as directory:
            journey = HandoffJourney(directory, count=case.values)
            if defect != "without_shared":
                journey.bind(shared).admitted("shared design")
            candidate = copy.deepcopy(values[0])
            token = "DesignFactUnresolved"
            ids = []
            if defect in ("remove_fact", "remove_record"):
                for position, value in enumerate(values, 1):
                    journey.bind(value, position).admitted("dependent value")
                candidate = copy.deepcopy(shared)
                if defect == "remove_fact":
                    missing = candidate["facts"].pop(0)["id"]
                else:
                    missing = candidate["contract_tests"]["obligations"][0]["id"]
                    candidate["contract_tests"] = {
                        "applicability": "not_applicable",
                        "reason": shared["purpose"],
                    }
                ids = [missing]
                report = journey.refused(
                    candidate,
                    None,
                    "DesignInheritanceRefused",
                    [token],
                    replace=True,
                    ids=ids,
                )
                for position in range(1, case.values + 1):
                    assert re.search(
                        r"value(?:s)?[^\n]*\b" + str(position) + r"\b",
                        report.stdout + report.stderr,
                        re.IGNORECASE,
                    ), message(
                        f"removal refusal omitted dependent outcome {position}",
                        "all dependent values need correction",
                        "name every bound dependent in the same public refusal",
                    )
            else:
                if defect == "fact":
                    candidate["purpose"] = {"ref": "AbsentFact"}
                    ids = ["AbsentFact"]
                elif defect in ("record", "two_missing"):
                    candidate["inherits"].append({"ref": "AbsentRecord"})
                    ids = ["AbsentRecord"]
                    if defect == "two_missing":
                        candidate["purpose"] = {"ref": "AbsentFact"}
                        ids.append("AbsentFact")
                else:
                    token = "DesignInheritanceWithoutShared"
                journey.refused(
                    candidate, 1, "DesignInheritanceRefused", [token], ids=ids
                )
                event(f"missing={defect}")


def legacy_form(document, shared=None):
    definitions = catalog(*([shared] if shared else []), document)

    def expand(value):
        if isinstance(value, dict):
            if set(value) == {"ref"}:
                return definitions[value["ref"]]
            return {
                key: expand(child)
                for key, child in value.items()
                if key not in ("facts", "inherits")
            }
        if isinstance(value, list):
            return [expand(child) for child in value]
        return value

    result = expand(document)
    result["schema_version"] = 1
    result["authority"] = {"heading": "Legacy current doctor authority"}
    for kind in ("architectural_tests", "contract_tests", "agreement_analysis"):
        if (
            shared
            and not records(result, kind)
            and result[kind]["applicability"] == "applicable"
        ):
            result[kind] = expand(shared[kind])
        for record in records(result, kind):
            record.pop("id", None)
    return result


RETIRED = (
    ("old_schema", "DesignManifestSchemaRetired"),
    ("prose_reference", "DesignFactRefExpected"),
    ("history", "DesignKeyNotInGrammar"),
    ("provenance", "DesignKeyNotInGrammar"),
    ("supersedes", "DesignKeyNotInGrammar"),
    ("receipts", "ArchitectHandoffSectionRetired"),
    ("model_text", "ArchitectHandoffModelTextRetired"),
    ("superseded", "DesignAdrStatusRetired"),
    ("deprecated", "DesignAdrStatusRetired"),
    ("persisted_old", "DesignFactsPreNormalized"),
    ("locator_string", "DesignFactsPreNormalized"),
    ("legacy_option", "unknown"),
)


@pytest.mark.parametrize("form,token", RETIRED, ids=[item[0] for item in RETIRED])
def test_excluded_forms_do_not_become_accepted_current_handoffs(form, token):
    """L-retired-forms; the entire exact variant population is owned here."""
    shared, _ = small_designs(CurrentFacts(("Finite current contract",), (), 1, ""))
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, count=1)
        if form == "legacy_option":
            before = journey.bytes()
            result = journey.invoke(
                "design",
                "--shared",
                "--migrate-legacy-rendering",
                "--input",
                "-",
                body=legacy_form(shared),
            )
            report = result.stdout + result.stderr
            assert (
                result.code != 0
                and "--migrate-legacy-rendering" in report
                and re.search(r"unknown|unrecognized", report, re.IGNORECASE)
            ), message(
                f"retired alternate producer was still available: {report}",
                "an optional legacy renderer defeats clean cutover",
                "remove the flag from the public constructor grammar",
            )
            assert journey.bytes() == before, message(
                "retired option changed bound state",
                "a removed producer cannot publish facts",
                "refuse the unknown option before mutation",
            )
            return
        if form == "old_schema":
            # On unchanged product this actual public input is accepted. RED is
            # its missing promised refusal, independent of future schema admission.
            journey.refused(legacy_form(shared), None, "InvalidDesignDocument", [token])
            return
        if form in ("persisted_old", "locator_string"):
            # Future grammar rejects these, so stage the unchanged historical
            # wire fixture only for the explicitly declared pre-normalized reader.
            mapping = load("run11-fact-map.json")
            source = mapping["persisted_fixture"]
            raw = frozen_bytes(mapping, "persisted_handover")
            assert hashlib.sha256(raw).hexdigest() == source["sha256"], message(
                "frozen persisted input changed",
                "the reader observation must consume genuine original bytes independently of normalized fixture output",
                "restore the exact persisted snapshot in the declared repository support",
            )
            document_raw = frozen_bytes(mapping, "persisted_document")
            assert (
                hashlib.sha256(document_raw).hexdigest() == source["document_sha256"]
            ), message(
                "frozen authority input changed",
                "same-locator rebind must consume the independently frozen original authority",
                "restore the exact authority snapshot in the declared repository support",
            )
            persisted = json.loads(raw)
            for authority in [
                persisted["shared_design"]["authority_locator"],
                *(
                    item["authority"]["authority_locator"]
                    for item in persisted["values"]
                ),
            ]:
                destination = journey.root / authority.split("#", 1)[0]
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(document_raw)
            if form == "locator_string":
                # This is the declared old opaque-identity carrier, not a new
                # producer operation or execution shim.
                persisted["values"][0]["authority"] = persisted["values"][0][
                    "authority"
                ]["authority_locator"]
                raw = json.dumps(
                    persisted,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                ).encode()
            (journey.root / STATE).write_bytes(raw)
            before = journey.bytes()
            result = journey.invoke(
                "handoff",
                "prompt",
                "--role",
                "nw-acceptance-designer",
                "--value",
                "1",
                "--root-context",
                "root-context.md",
                "--template-dir",
                str(CHECKOUT / "nWave/templates/architect-handoff"),
                "--skills-dir",
                str(CHECKOUT / "nWave/skills"),
            )
            report = result.stdout + result.stderr
            assert (
                result.code != 0
                and token in report
                and "des design" in report
                and "--replace-current" in report
            ), message(
                f"old persisted facts were not explicitly refused: {report}",
                "consumers must require deliberate same-authority rebind, not a legacy shim",
                "return the pre-normalized refusal and replace-current HOW",
            )
            for args, body in (
                (
                    (
                        "prepare-role",
                        "--role",
                        "acceptance-designer",
                        "--task",
                        "selected-revision-recovery",
                        "--value",
                        "1",
                        "--finding",
                        "-",
                    ),
                    "Recover this selected current value without executing pre-normalized facts.",
                ),
                (
                    ("oracle", "--value", "1", "--input", "-"),
                    {
                        "outcome": "accepted",
                        "diagnostic": "Current public oracle candidate.",
                    },
                ),
                (
                    ("craft", "--value", "1", "--input", "-"),
                    {
                        "outcome": "accepted",
                        "diagnostic": "Current implementation report.",
                    },
                ),
                (("verify",), None),
            ):
                refused = journey.invoke(*args, body=body)
                report = refused.stdout + refused.stderr
                assert (
                    refused.code != 0
                    and token in report
                    and "des design" in report
                    and "--replace-current" in report
                ), message(
                    f"{args[0]} consumed an old opaque authority: {report}",
                    "every declared consumer requires an explicit normalized same-locator repair",
                    "refuse pre-normalized facts before report admission, task preparation or verification",
                )
                assert journey.bytes() == before, message(
                    f"{args[0]} rewrote old facts",
                    "refusal-only carriers are not an implicit migration mechanism",
                    "preserve the bound raw source until explicit replacement",
                )
            assert journey.bytes() == before, message(
                "old-reader refusal changed input",
                "reading is not migration",
                "leave frozen persisted facts untouched",
            )
            current_shared = load("shared.json")
            current_values = [load(f"value-{position}.json") for position in (1, 2, 3)]
            journey.bind(current_shared, replace=True).admitted(
                "same-locator shared rebind"
            )
            repaired_shared = json.loads(journey.bytes())["shared_design"][
                "authority_locator"
            ]
            old_shared = persisted["shared_design"]["authority_locator"]
            assert repaired_shared == old_shared.split("#", 1)[0] + "#Shared design", (
                message(
                    "shared repair did not compile its new locator",
                    "old author headings must not survive normalized replacement",
                    "keep the destination document and replace the old scope section with its compiled heading",
                )
            )
            remaining = json.loads(journey.bytes())
            assert [record["authority"] for record in remaining["values"]] == [
                record["authority"] for record in persisted["values"]
            ], message(
                "shared replacement altered still-old opaque authorities",
                "same-owner sequential repair must preserve not-yet-replaced raw JSON or locator identities",
                "serialize every untouched old authority unchanged and refuse its execution",
            )
            for position, current_value in enumerate(current_values, 1):
                journey.bind(current_value, position, replace=True).admitted(
                    "same-locator value rebind"
                )
                rebound = json.loads(journey.bytes())["values"][position - 1][
                    "authority"
                ]["authority_locator"]
                old = persisted["values"][position - 1]["authority"]
                old_locator = old if isinstance(old, str) else old["authority_locator"]
                assert rebound == old_locator.split("#", 1)[0] + f"#Value {position}", (
                    message(
                        "value repair retained an author heading or changed its destination",
                        "scope position and document define normalized identity",
                        "bind the compiled value locator in the same destination",
                    )
                )
                headings = re.findall(
                    r"(?m)^#{1,6}\s+([^\n]+)$",
                    (journey.root / old_locator.split("#", 1)[0]).read_text(),
                )
                assert (
                    old_locator.split("#", 1)[1] not in headings
                    and f"Value {position}" in headings
                ), message(
                    "old author heading survived explicit repair",
                    "renaming only the stored locator leaves duplicate author prose in the durable document",
                    "replace the original section heading in the actual published document",
                )
                remaining = json.loads(journey.bytes())
                assert [
                    record["authority"] for record in remaining["values"][position:]
                ] == [
                    record["authority"] for record in persisted["values"][position:]
                ], message(
                    "sequential replacement discarded another old authority",
                    "repairing one value cannot silently migrate or erase its siblings",
                    "preserve untouched opaque authority objects exactly until individually rebound",
                )
            packet, _ = journey.prompt(1)
            assert_packet(packet, current_shared, current_values[0])
            assert_inherited(packet, current_shared, current_values[0])
            return
        candidate = copy.deepcopy(shared)
        if form == "prose_reference":
            candidate["purpose"] = candidate["facts"][0]["text"]
        elif form in ("history", "provenance", "supersedes"):
            candidate[form] = "Prior evidence that must stay external"
        elif form == "receipts":
            candidate["architect_handoff"] = {
                "sections": [
                    {
                        "kind": "receipts",
                        "scope": "shared",
                        "status": {"tag": "applicable", "payload": {"runs": []}},
                    }
                ]
            }
        elif form == "model_text":
            model_section = copy.deepcopy(
                next(
                    section
                    for section in load("shared.json")["architect_handoff"]["sections"]
                    if section["kind"] == "model"
                )
            )
            model_section["status"]["payload"]["models"][0]["text"] = (
                "module old_model {}"
            )
            candidate["architect_handoff"] = {"sections": [model_section]}
        else:
            ref = candidate["purpose"]
            candidate["adr"] = {
                "applicability": "applicable",
                "context": ref,
                "decision": ref,
                "alternatives": [ref],
                "consequences": [ref],
                "status": form,
            }
        journey.refused(candidate, None, "InvalidDesignDocument", [token])


@pytest.mark.parametrize("status", ("proposed", "accepted"))
def test_current_decision_statuses_and_full_length_identifiers_are_admitted(status):
    """Proposed/accepted current decisions admit the declared identifier boundary."""
    shared, values = small_designs(
        CurrentFacts(("Current doctor comparison contract",), (), 1, "")
    )
    ref = shared["purpose"]
    shared["adr"] = {
        "applicability": "applicable",
        "context": ref,
        "decision": ref,
        "alternatives": [ref],
        "consequences": [ref],
        "status": status,
    }
    longest_id = "A" + "z" * 63
    original_id = shared["facts"][0]["id"]
    shared["facts"][0]["id"] = longest_id
    for document in (shared, *values):
        for path, identity in list(walk(document)):
            if path and path[-1] == "ref" and identity == original_id:
                set_at(document, path, longest_id)
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, count=1).current(shared, values)
        packet, _ = journey.prompt(1)
        assert packet["facts"] == reachable_catalog(shared, values[0]), message(
            "current control lost its declared facts",
            "valid current author input must remain usable at the full identifier boundary",
            "admit both current statuses without narrowing the declared id domain",
        )


@pytest.mark.parametrize(
    "defect",
    (
        "empty_without_inherits",
        "empty_architectural",
        "empty_agreement",
        "not_applicable_with_inherits",
        "not_applicable_architectural",
        "not_applicable_agreement",
        "shared_inherits",
        "id_empty",
        "id_overlong",
        "id_digit",
        "id_underscore",
        "id_hyphen",
        "id_unicode",
        "id_space",
        "id_punctuation",
        "record_clash",
        "two_manifest_defects",
        "ref_with_text",
        "null_ref",
        "numeric_ref",
        "null_ref_value",
        "numeric_ref_value",
        "missing_ref_key",
        "trace_key",
        "receipt_key",
    ),
)
def test_construction_restrictions_explain_each_illegal_input(defect):
    shared, values = small_designs(
        CurrentFacts(("A distinct finite admission control",), (), 1, "")
    )
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, count=1)
        candidate = copy.deepcopy(values[0])
        position = 1
        tokens = ["DesignInheritanceContradiction"]
        if defect == "shared_inherits":
            candidate = copy.deepcopy(shared)
            candidate["inherits"] = [{"ref": "CT1"}]
            position = None
            tokens = ["DesignInheritsOnShared"]
        else:
            journey.bind(shared).admitted("admitted shared control")
            if defect in (
                "empty_without_inherits",
                "empty_architectural",
                "empty_agreement",
            ):
                removed = {
                    "empty_without_inherits": {"CT1"},
                    "empty_architectural": {"AR1"},
                    "empty_agreement": {"AP1", "AP2"},
                }[defect]
                candidate["inherits"] = [
                    item for item in candidate["inherits"] if item["ref"] not in removed
                ]
            elif defect in (
                "not_applicable_with_inherits",
                "not_applicable_architectural",
                "not_applicable_agreement",
            ):
                kind = {
                    "not_applicable_with_inherits": "contract_tests",
                    "not_applicable_architectural": "architectural_tests",
                    "not_applicable_agreement": "agreement_analysis",
                }[defect]
                candidate[kind] = {
                    "applicability": "not_applicable",
                    "reason": shared["purpose"],
                }
            elif defect.startswith("id_"):
                identities = {
                    "id_empty": "",
                    "id_overlong": "A" + "z" * 64,
                    "id_digit": "1-illegal",
                    "id_underscore": "_illegal",
                    "id_hyphen": "-illegal",
                    "id_unicode": "éclair",
                    "id_space": "A space",
                    "id_punctuation": "A?",
                }
                candidate["facts"] = [
                    {"id": identities[defect], "text": "Finite malformed identifier"}
                ]
                tokens = ["DesignFactIdShape"]
            elif defect in (
                "ref_with_text",
                "null_ref",
                "numeric_ref",
                "null_ref_value",
                "numeric_ref_value",
                "missing_ref_key",
            ):
                malformed = {
                    "ref_with_text": {
                        "ref": shared["purpose"]["ref"],
                        "text": shared["facts"][0]["text"],
                    },
                    "null_ref": None,
                    "numeric_ref": 7,
                    "null_ref_value": {"ref": None},
                    "numeric_ref_value": {"ref": 7},
                    "missing_ref_key": {},
                }
                candidate["purpose"] = malformed[defect]
                tokens = ["DesignFactRefExpected"]
            elif defect in ("trace_key", "receipt_key"):
                candidate["trace" if defect == "trace_key" else "receipts"] = (
                    "External evidence cannot be an operational slot"
                )
                tokens = ["DesignKeyNotInGrammar"]
            elif defect == "record_clash":
                candidate["facts"] = [
                    {"id": "CT1", "text": "Finite record namespace clash"}
                ]
                tokens = ["DesignFactIdClash"]
                journey.refused(candidate, position, "DesignInheritanceRefused", tokens)
                return
            else:
                candidate["purpose"] = "A copied semantic statement"
                candidate["history"] = "An excluded container"
                tokens = ["DesignFactRefExpected", "DesignKeyNotInGrammar"]
        journey.refused(candidate, position, "InvalidDesignDocument", tokens)


def reference_slots(document):
    # One public raw-prose challenge per distinct declared semantic field/context.
    owned = {}
    for path, value in walk(document):
        if path and path[-1] == "ref":
            slot = path[:-1]
            signature = tuple(part for part in slot if not isinstance(part, int))
            owned.setdefault(signature, slot)
    return tuple(owned.values())


MALFORMED_REFERENCES = (
    "raw",
    "null",
    "numeric",
    "empty",
    "ref-plus-text",
    "null-id",
    "numeric-id",
)
NULLABLE_REFERENCE_FIELDS = {
    "proof_note",
    "fairness",
    "bootstrap",
    "design_note",
    "runtime_note",
    "note",
}


def reference_document(name):
    source_name, _, shape = name.partition("@")
    document = load(source_name)
    if not shape:
        return document
    ref = document["purpose"]
    if shape == "prefactoring":
        document["prefactoring"] = {
            "applicability": "applicable",
            "existing_oracle": document["oracle"],
            "move": ref,
            "preserved_observation": ref,
            "verification": document["verification"],
            "acceptance_supports": document["acceptance_supports"],
        }
    elif shape == "adr":
        document["adr"] = {
            "applicability": "applicable",
            "context": ref,
            "decision": ref,
            "alternatives": [ref],
            "consequences": [ref],
            "status": "proposed",
        }
    elif shape in ("finite", "none"):
        law = next(
            section
            for section in document["architect_handoff"]["sections"]
            if section["kind"] == "laws"
        )["status"]["payload"]["laws"][0]
        law["treatment"] = (
            {"tag": "finite", "cases": [ref], "reason": ref}
            if shape == "finite"
            else {"tag": "none", "reason": ref}
        )
    elif shape in ("argued", "optional"):
        closures = next(
            section
            for section in document["architect_handoff"]["sections"]
            if section["kind"] == "closure"
        )["status"]["payload"]["closures"]
        for closure in closures:
            for axis in ("safety", "inhabitation", "public_reachability", "liveness"):
                claim = closure[axis]
                if claim["tag"] != "claim":
                    continue
                claim["design_note"] = ref
                claim["runtime_note"] = ref
                basis = claim["basis"]
                if shape == "argued":
                    claim["basis"] = {"tag": "argued", "argument": [ref]}
                elif basis["tag"] == "checked":
                    basis["proof_note"] = ref
                    basis["fairness"] = ref
                elif basis["tag"] == "path":
                    basis["bootstrap"] = ref
    elif shape == "section-na":
        document["architect_handoff"]["sections"][0]["status"] = {
            "tag": "not_applicable",
            "reason": ref,
        }
    elif shape == "scenario":
        model = next(
            section
            for section in document["architect_handoff"]["sections"]
            if section["kind"] == "model"
        )["status"]["payload"]["models"][0]
        run_id = model["mutants"][0]["kills"][0]["run"]
        # Negative grammar input only: trace identity is intentionally unresolved.
        # No trace, human judgment or receipt is fabricated as an admitted fact.
        document["architect_handoff"]["sections"].append(
            {
                "kind": "scenarios",
                "scope": "shared",
                "status": {
                    "tag": "applicable",
                    "payload": {
                        "scenarios": [
                            {
                                "id": "NegativeReferenceContext",
                                "title": ref,
                                "source_run": run_id,
                                "kind": "mutant",
                                "review": {
                                    "tag": "judged",
                                    "by": "negative-reference-input",
                                    "judgment": "unclear",
                                    "model_identity": model["source"]["sha256"],
                                    "trace_identity": "0" * 64,
                                    "note": ref,
                                },
                            }
                        ]
                    },
                },
            }
        )
    else:
        raise AssertionError("Undeclared reference shape: " + shape)
    return document


def reference_contexts():
    contexts = {}
    names = (
        "shared.json",
        "value-1.json",
        "value-2.json",
        "value-3.json",
        *(
            "shared.json@" + shape
            for shape in (
                "prefactoring",
                "adr",
                "finite",
                "none",
                "argued",
                "optional",
                "section-na",
                "scenario",
            )
        ),
    )
    for name in names:
        document = reference_document(name)
        for slot in reference_slots(document):
            signature = tuple(part for part in slot if not isinstance(part, int))
            parents = [at(document, slot[:length]) for length in range(len(slot))]
            discriminators = tuple(
                (parent.get("tag"), parent.get("kind") if "status" in parent else None)
                for parent in parents
                if isinstance(parent, dict)
                and ("tag" in parent or ("status" in parent and "kind" in parent))
            )
            contexts.setdefault((signature, discriminators), (name, slot))
    return tuple(contexts.values())


@pytest.mark.parametrize(
    "context,variant",
    [
        (context, variant)
        for context in reference_contexts()
        for variant in MALFORMED_REFERENCES
        if variant != "null" or context[1][-1] not in NULLABLE_REFERENCE_FIELDS
    ],
    ids=str,
)
def test_every_semantic_field_refuses_a_parallel_prose_carrier(context, variant):
    """Every malformed alternative; null in optional FactRef slots is not malformed."""
    name, slot = context
    shared = load("shared.json")
    document = reference_document(name)
    illegal = copy.deepcopy(document)
    original = at(document, slot)
    definitions = catalog(shared, document)
    if slot[0] == "inherits":
        # Inheritance selects a structured record, not a catalog definition.
        record = inherited_records(shared, document)[original["ref"]]
        raw = record["id"]
        prose = definitions[record["obligation"]["ref"]]
    else:
        prose = definitions[original["ref"]]
        raw = prose
    malformed = {
        "raw": raw,
        "null": None,
        "numeric": 7,
        "empty": {},
        "ref-plus-text": {**original, "text": prose},
        "null-id": {"ref": None},
        "numeric-id": {"ref": 7},
    }
    set_at(illegal, slot, malformed[variant])
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory)
        source_name = name.partition("@")[0]
        position = (
            None
            if source_name == "shared.json"
            else int(source_name.removeprefix("value-").removesuffix(".json"))
        )
        if position is not None:
            journey.bind(shared).admitted("complete shared context")
        result = journey.refused(
            illegal, position, "InvalidDesignDocument", ["DesignFactRefExpected"]
        )
        report = result.stdout + result.stderr
        pointer = "/" + "/".join(map(str, slot))
        dotted = ".".join(
            str(part) if isinstance(part, str) else f"[{part}]" for part in slot
        ).replace(".[", "[")
        assert pointer in report or dotted in report, message(
            f"refusal omitted the full illegal slot {slot}: {report}",
            "a repeated leaf name cannot identify the offending context",
            "name the complete source field path including record indexes",
        )


UNIQUE_REFERENCE_LISTS = (
    pytest.param("shared.json", None, ("constraints",), id="constraints"),
    pytest.param("shared.json", None, ("decisions",), id="decisions"),
    pytest.param(
        "shared.json", None, ("boundaries", "driven_ports"), id="driven-dependencies"
    ),
    pytest.param(
        "shared.json@adr", None, ("adr", "alternatives"), id="decision-alternatives"
    ),
    pytest.param(
        "shared.json@adr", None, ("adr", "consequences"), id="decision-consequences"
    ),
    pytest.param(
        "shared.json",
        "laws",
        ("generators", 0, "must_include"),
        id="required-generated-cases",
    ),
    pytest.param(
        "shared.json@finite",
        "laws",
        ("laws", 0, "treatment", "cases"),
        id="finite-cases",
    ),
    pytest.param(
        "shared.json",
        "construction",
        ("claims", 0, "bypass"),
        id="construction-bypasses",
    ),
    pytest.param("shared.json", "construction", ("admitted",), id="admitted-inputs"),
    pytest.param("shared.json", "construction", ("excluded",), id="excluded-inputs"),
    pytest.param(
        "shared.json", "model", ("models", 0, "exclusions"), id="model-exclusions"
    ),
    pytest.param(
        "shared.json", "model", ("models", 0, "assumptions"), id="model-assumptions"
    ),
    pytest.param(
        "shared.json",
        "closure",
        ("closures", 0, "safety", "assumptions"),
        id="claim-assumptions",
    ),
)


def observe_repeated_reference_refusal(name, kind, slot):
    document = reference_document(name)
    # Reuse across distinct slots is legal; only within-list repetition is
    # challenged. Both controls still enter the real public constructor.
    document["constraints"] = [copy.deepcopy(document["purpose"])]
    document["decisions"] = [copy.deepcopy(document["purpose"])]
    if kind is not None:
        index = next(
            index
            for index, section in enumerate(document["architect_handoff"]["sections"])
            if section["kind"] == kind
        )
        slot = ("architect_handoff", "sections", index, "status", "payload", *slot)
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, count=1)
        journey.bind(document).admitted("unique lists with cross-slot reference reuse")
        candidate = copy.deepcopy(document)
        items = at(candidate, slot)
        repeated = copy.deepcopy(items[0])
        items.append(repeated)
        result = journey.refused(
            candidate,
            None,
            "InvalidDesignDocument",
            ["DesignListEntryRepeated"],
            replace=True,
            ids=[repeated["ref"]],
        )
        report = result.stdout + result.stderr
        assert "NameError" not in report, message(
            "repeated references reached a publisher name error",
            "list uniqueness is a constructor refusal, not a publication failure",
            "report the repeated-reference defect before binding or publication",
        )
        pointer = "/" + "/".join(map(str, slot))
        dotted = ".".join(
            str(part) if isinstance(part, str) else f"[{part}]" for part in slot
        ).replace(".[", "[")
        defect_lines = [
            line
            for line in report.splitlines()
            if re.match(
                r"^\s*(?:WHY:\s*)?(?:[-*]\s*)?DesignListEntryRepeated\b",
                line,
            )
        ]
        assert any(
            (pointer in line or dotted in line)
            and re.search(
                r"(?<![A-Za-z0-9_-])"
                + re.escape(repeated["ref"])
                + r"(?![A-Za-z0-9_-])",
                line,
            )
            for line in defect_lines
        ), message(
            f"repetition refusal omitted slot {slot} or repeated id {repeated['ref']}: {report}",
            "the operator must identify the particular list and entry without confusing it with a catalog-definition clash",
            "name the complete list slot and repeated id on its token-led defect line",
        )


@pytest.mark.parametrize("name,kind,slot", UNIQUE_REFERENCE_LISTS)
def test_repeated_references_cannot_replace_current_facts(name, kind, slot):
    """normalized_reference_restrictions; the closed thirteen-list population."""
    observe_repeated_reference_refusal(name, kind, slot)


def test_recovery_consumers_receive_the_same_single_definition_catalog():
    shared, values = load("shared.json"), [load("value-1.json")]
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, count=1).current(shared, values)
        recovered, changed = journey.recovery(shared, values[0])
        packet, _ = journey.prompt(1)
        expected = reachable_catalog(changed, values[0])
        assert recovered.get("facts") == packet.get("facts") == expected, message(
            "prompt/recovery catalog meanings differ",
            "independently consumed recovery must not duplicate or drop current authority",
            "use the same normalized catalog projection for both real consumers",
        )
        assert_packet(recovered, changed, values[0])
        assert_inherited(recovered, changed, values[0])
        counts = Counter(text for _, text in walk(recovered) if isinstance(text, str))
        for identity, text in expected.items():
            assert counts[text] == 1, message(
                f"recovery fact {identity} has {counts[text]} definitions",
                "recovery is not a second expanded prose carrier",
                "keep current facts once and project reference-only recovery authority",
            )


def test_author_consumes_only_the_current_constructor_grammar():
    """The real author prompt carries the sole admitted producer grammar."""
    with tempfile.TemporaryDirectory() as directory:
        journey = HandoffJourney(directory, count=1)
        _, prompt = journey.prompt(1, role="nw-solution-architect")
        help_output = (
            journey.invoke("design", "--help")
            .admitted("public constructor description")
            .stdout
        )
        for surface in (help_output, prompt.stdout):
            schema_lines = [
                line
                for line in surface.splitlines()
                if re.search(r"schema_version.*integer", line)
            ]
            assert schema_lines and all(
                re.search(r"integer\s+`?2`?", line) for line in schema_lines
            ), message(
                f"consumed producer schema is not exclusively current: {schema_lines}",
                "author guidance must not teach the retired optional representation",
                "regenerate the consumed schema description from the sole normalized constructor",
            )
            assert re.search(r"\bref\b", surface) and re.search(
                r"\bfacts\b", surface
            ), message(
                "consumed grammar omits catalog/reference construction",
                "the author must be able to construct the admitted normalized form",
                "include the catalog and exact FactRef field grammar in the real author surface",
            )
        instructions = prompt.stdout.split("=== [C] orchestrator ===", 1)[0].split(
            "## FROM THE ROOT", 1
        )[0]
        # Inspect actual dispatched author instructions, not caller root-context
        # and never classify catalog text by words or substrings.
        history_instructions = [
            line
            for line in instructions.splitlines()
            if re.search(
                r"histor(?:y|ical).*narrat|narrat.*histor(?:y|ical)",
                line,
                re.IGNORECASE,
            )
        ]
        assert history_instructions and any(
            re.search(r"forbid|must not|never|prohibit", line, re.IGNORECASE)
            for line in history_instructions
        ), message(
            "consumed history-narration clause is not an author prohibition",
            "a prohibition elsewhere in the prompt cannot discharge this specific owner contract",
            "state current-only author responsibility in the actual historical-narration instruction; independent review/EXAMINE judge its semantics",
        )
        assert re.search(r"review|EXAMINE", instructions), message(
            "author guidance lacks the independent semantic judgment boundary",
            "no automatic semantic classifier is claimed",
            "assign semantic narrative judgment to review and EXAMINE",
        )
        assert re.search(
            r"external.*model|model.*external", instructions, re.IGNORECASE | re.DOTALL
        ) and re.search(
            r"driven.*receipt|receipt.*driven", instructions, re.IGNORECASE | re.DOTALL
        ), message(
            "formal author guidance lacks external model/receipt ownership",
            "a consumed instruction to inline models or receipts contradicts the sole normalized form",
            "cite model.source locators and the driven receipt store in consumed specification, skills and template",
        )


def architecture_modules():
    # Future API absence is first observed as the promised public admission
    # failure, never as a collection/import error for a nonexistent symbol.
    shared, values = small_designs(
        CurrentFacts(("Architecture current fact",), (), 1, "")
    )
    with tempfile.TemporaryDirectory() as directory:
        HandoffJourney(directory, count=1).current(shared, values)
    return (
        importlib.import_module("des.domain.design_document"),
        importlib.import_module("des.ports.driven_ports.task_invocation_port"),
        importlib.import_module("des.application.architect_handoff.g10_types"),
    )


def declared_member(module, name):
    member = getattr(module, name, None)
    assert member is not None, message(
        f"declared architecture member {name} is absent",
        "public admission alone does not establish the governed type boundary",
        "implement the DESIGN-declared member without inventing an alternate API",
    )
    return member


def test_fact_catalog_is_built_only_by_its_owner():
    """Runtime construction guard, not an unsupported global Python ownership proof."""
    owner, port, _ = architecture_modules()
    catalog_type = declared_member(owner, "FactCatalog")
    refusal = declared_member(owner, "FactCatalogConstructionRefused")
    record_type = declared_member(port, "FactRecord")
    identity_type = declared_member(port, "FactId")
    builder = declared_member(owner, "build_fact_catalog")
    inputs = (record_type(id=identity_type("F-1"), text="t"),)
    for constructor in (
        catalog_type,
        # The indirect callback is a separate declared constructor-boundary stimulus.
        lambda records, **kwargs: catalog_type(records, **kwargs),  # noqa: PLW0108
    ):
        with pytest.raises(refusal) as refused:
            constructor(inputs, token=object())
        report = str(refused.value)
        for required in (
            "FactCatalog built outside design_document.py",
            "the catalog bijection is owned by its smart constructor",
            "call design_document.build_fact_catalog",
        ):
            assert required in report, message(
                "construction guard omitted its declared correction: " + report,
                "TypeError or a malformed-input refusal is not ownership enforcement",
                "raise FactCatalogConstructionRefused with the declared WHAT/WHY/HOW",
            )
    built = builder(inputs)
    assert isinstance(built, catalog_type), message(
        "owner builder refused the legal control",
        "a guard that refuses all catalogs cannot satisfy the constructor contract",
        "construct the same legal records through the owner builder",
    )


PLAIN_VALUE_FIELDS = {
    "FactRecord": ("text",),
    "DesignTarget": ("path", "decision"),
    "DesignFacts": (
        "paradigm",
        "oracle",
        "acceptance_supports",
        "verification",
        "authority_locator",
        "product_change",
        "architect_handoff",
    ),
    "PreNormalizedDesign": ("raw", "authority_locator", "design_semantic_sha256"),
    "ArchitecturalTestObligation": ("oracle",),
    "ContractTestObligation": ("contract", "producer", "consumer", "oracle"),
    "ApplicablePrefactoring": (
        "existing_oracle",
        "verification",
        "acceptance_supports",
        "applicability",
    ),
    "AgreementParty": ("contract", "role", "locator", "decision"),
    "ReuseCandidate": ("symbol", "locator", "decision"),
    "ImpactItem": ("kind", "locator", "decision"),
    "ApplicableADR": ("status", "applicability"),
    "ApplicableArchitecturalTests": ("applicability",),
    "ApplicableContractTests": ("applicability",),
    "ApplicableAgreementAnalysis": ("applicability",),
    "ApplicableImpactClosure": ("applicability",),
    "NotApplicable": ("applicability",),
    "UnassessedDesignDecision": ("applicability",),
    "BoundaryFailure": ("outcome",),
    "Constructor": ("signature",),
    "Observation": ("result_type",),
    "StateAtom": ("name", "symbol"),
    "ActionAtom": ("name", "symbol"),
    "PropertyAtom": ("name", "symbol"),
    "ConstantAtom": ("name", "symbol"),
    "Kill": ("property",),
    "Checked": ("properties",),
    "Judged": ("by",),
    "Entry": ("scope",),
    "Applicable": ("payload",),
}


def test_every_prose_slot_is_a_fact_reference():
    """Whole governed dataclass graph, with exact pairs and resolved union members."""
    _, port, typed = architecture_modules()
    roots = [
        declared_member(port, name) for name in ("DesignFacts", "PreNormalizedDesign")
    ]
    roots += [
        declared_member(typed, name)
        for name in (
            "Entry",
            "Applicable",
            "NotApplicable",
            "Laws",
            "Construction",
            "Models",
            "ClosureSet",
            "Scenarios",
        )
    ]
    allowed_newtypes = {
        declared_member(typed, name) for name in ("ID", "Locator", "Sha", "RelPath")
    }
    allowed_newtypes.add(declared_member(port, "FactId"))
    population, hints = set(), {}

    def discover(annotation):
        if isinstance(annotation, type) and dc.is_dataclass(annotation):
            if annotation in population:
                return
            population.add(annotation)
            hints[annotation] = t.get_type_hints(annotation)
            for field in dc.fields(annotation):
                discover(hints[annotation][field.name])
        else:
            for argument in t.get_args(annotation):
                discover(argument)

    for root in roots:
        discover(root)
    fact_ref = declared_member(port, "FactRef")

    def allowed(annotation):
        if (
            annotation in (int, float, bool, type(None), fact_ref)
            or annotation in allowed_newtypes
        ):
            return True
        if isinstance(annotation, type) and annotation in population:
            return True
        origin, arguments = t.get_origin(annotation), t.get_args(annotation)
        if origin is t.Literal:
            return True
        if origin in (t.Union, types.UnionType):
            return bool(arguments) and all(allowed(argument) for argument in arguments)
        if origin is tuple:
            return (
                len(arguments) == 2
                and arguments[1] is Ellipsis
                and allowed(arguments[0])
            )
        return False

    port_records = {
        "FactRecord",
        "DesignTarget",
        "DesignFacts",
        "PreNormalizedDesign",
        "ArchitecturalTestObligation",
        "ContractTestObligation",
        "ApplicablePrefactoring",
        "AgreementParty",
        "ReuseCandidate",
        "ImpactItem",
        "ApplicableADR",
        "ApplicableArchitecturalTests",
        "ApplicableContractTests",
        "ApplicableAgreementAnalysis",
        "ApplicableImpactClosure",
        "NotApplicable",
        "UnassessedDesignDecision",
        "BoundaryFailure",
    }
    allowed_pairs = {
        (getattr(port if name in port_records else typed, name, None), field)
        for name, names in PLAIN_VALUE_FIELDS.items()
        for field in names
    }
    mistakes = []
    for record in sorted(population, key=lambda item: (item.__module__, item.__name__)):
        for field in dc.fields(record):
            annotation = hints[record][field.name]
            if (record, field.name) not in allowed_pairs and not allowed(annotation):
                mistakes.append(
                    (record.__module__, record.__name__, field.name, str(annotation))
                )
    assert fact_ref in population and not mistakes, message(
        f"governed typed slots allow parallel prose: {mistakes}",
        "FactRef | str and later ungoverned fields create a second semantic carrier",
        "use only the closed resolved-type rules or the DESIGN-declared exact scalar pairs",
    )

"""Real Dune assertions establish delivery outcomes without trusting exit alone.

@contract-shape: real-io @driving_port @adapter-integration
Extends the existing native delivery journey; no second walking skeleton.
The fixture under test owns the OCaml reporter. This oracle never replaces it.
Finite completion cases are observed through real Dune and the public DES CLI.
Review and EXAMINE remain independent, later candidate attestations.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from enum import Enum
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
for package_root in (ROOT, ROOT / "src"):
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))

from tests.common.in_process_cli import run_cli_in_process
from tests.des._helpers.host_facts import design_manifest, product_manifest
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    base_repository,
    block,
    git,
    hermetic_environment,
)
from tests.des.unit.application.test_native_delivery_lifecycle import _native_project


MARKER = "DES-ORACLE-OBSERVATION: "
OBSERVATION = "the native public command reports the agreed answer of forty-two"
RECIPE = [
    ["dune", "exec", "./oracle.exe", "--", "--public"],
    ["dune", "build", "@check"],
    ["dune", "exec", "./contract.exe"],
]


class CompletionCase(Enum):
    DELIVERY = "answer-and-protocol-delivery-with-owned-drift"
    RUNTIME = "runtime-failure-is-not-assertion-red"
    ABSENT = "assertion-free-success-is-indeterminate"


def require(condition: bool, what: str, how: str) -> None:
    assert condition, (
        f"WHAT: {what}; WHY: real Dune completion must preserve assertion, "
        f"setup and missing-observation meaning; HOW: {how}"
    )


class DuneDeliveryJourney:
    """Protocol driver for one isolated, real native fixture repository."""

    def __init__(self, workspace: Path):
        workspace.mkdir(parents=True)
        home = workspace / "home"
        home.mkdir()
        native_paths = []
        for tool in ("dune", "ocamlc", "git"):
            executable = shutil.which(tool)
            if executable is None:
                raise RuntimeError(
                    f"WHAT: required {tool} is unavailable; WHY: real native "
                    "execution cannot be measured; HOW: provide the declared "
                    "Dune/OCaml/Git runtime, never skip or substitute Python"
                )
            native_paths.append(str(Path(executable).absolute().parent))
        self.environment = hermetic_environment(
            {
                "PATH": os.pathsep.join(
                    dict.fromkeys([*native_paths, "/usr/bin", "/bin"])
                ),
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(home / "config"),
                "XDG_CACHE_HOME": str(home / "cache"),
                "XDG_DATA_HOME": str(home / "data"),
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            },
            workspace / "claude",
        )
        # The fixture's own Git subprocesses receive the same declared inputs.
        with pytest.MonkeyPatch.context() as environment:
            for key in tuple(os.environ):
                environment.delenv(key)
            for key, value in self.environment.items():
                environment.setenv(key, value)
            self.root = base_repository(workspace / "subject")
            (self.root / ".gitignore").write_text("_build/\n.nwave/\n")
            _native_project(self.root)
            self.baseline = git(self.root, "rev-parse", "HEAD")

    def native(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            argv,
            cwd=self.root,
            env=self.environment | {"DUNE_ROOT": str(self.root)},
            text=True,
            capture_output=True,
            timeout=90,
        )
        print(
            f"NATIVE argv={argv!r} exit={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
            flush=True,
        )
        return result

    def compile_subject(self) -> None:
        result = self.native(
            ["dune", "build", "./oracle.exe", "./contract.exe", "@check"]
        )
        if result.returncode:
            raise RuntimeError(
                f"WHAT: native subject did not compile: {result.stderr}; "
                "WHY: a compiler/setup failure is not assertion RED; HOW: "
                "restore the declared Dune libraries and OCaml runtime"
            )

    def counts(self, stdout: str, expected: tuple[int, int, int], label: str) -> dict:
        population = [line for line in stdout.splitlines() if line.startswith(MARKER)]
        require(
            len(population) == 1 and stdout.endswith("\n"),
            f"{label}: expected one newline-terminated native completion, got {population!r}",
            "wrap the actual OCaml assertion with the fixture-owned observer and "
            "flush exactly one completion record after execution",
        )
        try:
            actual = json.loads(population[0][len(MARKER) :])
        except ValueError as error:
            raise AssertionError(
                f"WHAT: {label} emitted invalid observation JSON: {population!r}; "
                "WHY: DES cannot consume assertion completion; HOW: emit the "
                "declared version-1 integer record after execution"
            ) from error
        wanted = dict(
            zip(
                ("version", "observed", "assertions_failed", "setup_failed"),
                (1, *expected),
                strict=True,
            )
        )
        require(
            isinstance(actual, dict)
            and actual == wanted
            and all(type(value) is int for value in actual.values()),
            f"{label}: measured {actual!r}, expected {wanted!r}",
            "count the one actual assertion callback, distinguishing Assert_failure "
            "from other exceptions; do not emit premature or exit-only success",
        )
        print(f"MEASURED {label}: {actual}", flush=True)
        return actual

    def assertion(self, argv: list[str], *, failed: bool, label: str) -> None:
        result = self.native(argv)
        self.counts(result.stdout, (1, int(failed), 0), label)
        require(
            (result.returncode != 0) if failed else (result.returncode == 0),
            f"{label}: assertion completion contradicts exit={result.returncode}",
            "return normally only after a passing assertion and re-raise the "
            "original Assert_failure after recording a failed assertion",
        )

    def invoke(self, action: str, *, payload: dict | None = None, success=True):
        arguments = [action, "--repo-root", str(self.root)]
        if action in {"design", "oracle", "craft"}:
            arguments += ["--value", "1"]
        if action == "oracle":
            arguments += ["--baseline", self.baseline]
        if action == "po":
            arguments += ["--feature", "native"]
        if payload is not None:
            arguments += ["--input", "-"]
        code, out, err = run_cli_in_process(
            arguments,
            cwd=self.root,
            env=self.environment,
            stdin_text=json.dumps(payload) if payload is not None else "",
            catch_all=True,
        )
        # Nest inner terminal text so the outer script has only ONE marker line.
        print(f"DES {action} exit={code} stdout={out!r} stderr={err!r}", flush=True)
        if success:
            require(
                code == 0 and block(out, err).get("DELIVERY-OUTCOME") == "Success",
                f"public {action} did not succeed: {out}{err}",
                "restore the bound native recipe and truthful observation "
                "through the existing public DES command",
            )
        return code, out, err

    def bind(self) -> None:
        self.invoke(
            "po",
            payload=product_manifest(
                "Deliver the native public answer using the existing Dune project.",
                [OBSERVATION],
            ),
        )
        parties = [
            {
                "contract": "answer-protocol",
                "role": role,
                "locator": locator,
                "decision": "UNCHANGED_COMPATIBLE",
                "reason": "The consumer requires protocol v1.",
            }
            for role, locator in (
                ("producer", "lib/answer.ml:1"),
                ("consumer", "contract.ml:1"),
            )
        ]
        facts = {
            "targets": [{"path": "lib/answer.ml", "decision": "EXTEND"}],
            "paradigm": "functional",
            "decisions": ["Retain the real native answer and protocol consumers."],
            "oracle": "oracle.ml",
            "acceptance_supports": ["dune-project", "dune", "lib/dune"],
            "verification": RECIPE,
            "oracle_verification_index": 0,
            "architectural_tests": {
                "applicability": "applicable",
                "obligations": [
                    {
                        "obligation": "Implementation conforms to the published native interface.",
                        "oracle": "lib/answer.mli",
                        "verification_index": 1,
                    }
                ],
            },
            "agreement_analysis": {"applicability": "applicable", "parties": parties},
            "contract_tests": {
                "applicability": "applicable",
                "obligations": [
                    {
                        "obligation": "The native consumer observes the agreed protocol.",
                        "contract": "answer-protocol",
                        "producer": "lib/answer.ml:1",
                        "consumer": "contract.ml:1",
                        "observation": "The consumer accepts protocol v1.",
                        "oracle": "contract.ml",
                        "verification_index": 2,
                    }
                ],
            },
            "prefactoring": {
                "applicability": "not_applicable",
                "reason": "The existing native seam needs no preserving move.",
            },
        }
        self.invoke("design", payload=design_manifest(facts, OBSERVATION, 1))
        self.invoke(
            "distill",
            payload={
                "schema_version": 2,
                "values": [
                    {
                        "observation": OBSERVATION,
                        "acceptance_obligations": [
                            {
                                "id": "public-answer",
                                "stimulus": "Run the real native public assertion.",
                                "expected": "The public answer is forty-two.",
                            }
                        ],
                        "oracle": "oracle.ml",
                        "acceptance_supports": ["dune-project", "dune", "lib/dune"],
                        "verification": [RECIPE[0]],
                        "oracle_verification_index": 0,
                    }
                ],
            },
        )

    def measure_oracle(self, verdict: str, *, success: bool) -> dict:
        code, out, err = self.invoke(
            "oracle",
            payload={
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "Observe the actual Dune assertion completion.",
                }
            },
            success=success,
        )
        witnesses = []
        for ref in git(
            self.root, "for-each-ref", "--format=%(refname)", "refs/nwave/turns"
        ).splitlines():
            subject, _, payload = git(
                self.root, "show", "-s", "--format=%B", ref
            ).partition("\n\n")
            if subject == "nwave witness: oracle":
                witnesses.extend(json.loads(payload))
        require(
            len(witnesses) == 1,
            f"one oracle invocation retained {len(witnesses)} witnesses: {witnesses}",
            "retain exactly one witness for this isolated invocation",
        )
        witness = witnesses[0]
        require(
            all(
                witness.get(key)
                for key in ("revision", "design_sections", "acceptance_tree")
            )
            and [row["oracle"] for row in witness["oracles"]] == ["oracle.ml"],
            f"native witness is not bound to the selected oracle: {witness}",
            "retain the selected revision, DESIGN and acceptance identity",
        )
        row = witness["oracles"][0]
        require(
            row["verdict"] == verdict
            and f"verdict={verdict}" in block(out, err).get("ORACLE-RED", ""),
            f"expected {verdict} in retained evidence and terminal, got {row}: {out}{err}",
            "classify actual completion counts, never process exit status alone",
        )
        if verdict == "indeterminate":
            require(
                code != 0
                and row["axis"] == "native-observation-no-observation"
                and "OracleRedUnobservable" in out + err,
                f"missing observation was not explicitly refused: {row}: {out}{err}",
                "preserve strict no-observation refusal and its provenance",
            )
        else:
            require(
                row["axis"] == "native-observation",
                f"{verdict} has the wrong observation provenance: {row}",
                "classify the real version-1 Dune record on the native axis",
            )
        if verdict == "broken":
            require(
                code != 0 and "OracleNotRed" in out + err,
                f"runtime/setup failure was not publicly refused: {row}: {out}{err}",
                "retain setup evidence as broken and refuse it rather than "
                "admitting assertion RED or GREEN",
            )
        executions = []
        for path in (self.root / ".nwave/des/logs/native").glob("oracle-*.json"):
            executions.extend(json.loads(path.read_text()))
        require(
            len(executions) == 1 and executions[0]["argv"] == RECIPE[0],
            f"one selected native invocation retained {executions!r}",
            "retain the actual oracle argv and channels before returning its outcome",
        )
        execution = executions[0]
        require(
            execution["incomplete"] is False and execution["exit"] == row["exit"],
            f"witness lost actual native completion: {execution!r} versus {row!r}",
            "bind verdict and process capture to the same completed execution",
        )
        print(f"RETAINED-WITNESS: {row!r}", flush=True)
        return execution

    def craft(self) -> None:
        self.invoke(
            "craft",
            payload={
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "Measure the disposable subject's changed answer.",
                    "blocked_by": None,
                }
            },
        )

    def answer(self, protocol: str) -> None:
        (self.root / "lib/answer.ml").write_text(
            f'let value = 42\nlet protocol = "{protocol}"\n'
        )

    def protects_delivery(self) -> None:
        self.compile_subject()
        self.assertion(RECIPE[0], failed=True, label="answer 0 failed assertion")
        self.bind()
        red = self.measure_oracle("red", success=True)
        self.counts(red["stdout"], (1, 1, 0), "DES retained answer RED")
        self.answer("v1")
        self.assertion(RECIPE[0], failed=False, label="answer 42 passed assertion")
        self.assertion(RECIPE[2], failed=False, label="protocol v1 passed assertion")
        self.craft()
        _, out, err = self.invoke("verify")
        candidate = block(out, err).get("CANDIDATE")
        require(
            bool(candidate),
            f"verify Success omitted its candidate: {out}{err}",
            "retain a candidate-bound native verification identity",
        )
        paths = list((self.root / ".nwave/des/logs/native").glob(f"{candidate}-*.json"))
        require(
            len(paths) == 1,
            f"candidate {candidate} retained {len(paths)} native evidence files",
            "retain one complete evidence vector for this candidate",
        )
        evidence_bytes = paths[0].read_bytes()
        evidence = json.loads(evidence_bytes)
        require(
            [row["argv"] for row in evidence] == RECIPE
            and all(
                row["exit"] == 0 and row["incomplete"] is False for row in evidence
            ),
            f"candidate lost the ordered answer/interface/protocol population: {evidence!r}",
            "execute and retain all three DESIGN selections, including @check",
        )
        for index, label in ((0, "verified answer"), (2, "verified protocol v1")):
            self.counts(evidence[index]["stdout"], (1, 0, 0), label)
        human = self.root / "human-wip.txt"
        human.write_bytes(b"unrelated human bytes\n")
        before = human.read_bytes()
        self.answer("v2")
        self.assertion(RECIPE[0], failed=False, label="answer preserved during drift")
        self.assertion(RECIPE[2], failed=True, label="protocol v2 failed assertion")
        self.craft()
        code, out, err = self.invoke("verify", success=False)
        require(
            code != 0 and "VerificationFailed" in out + err,
            f"owned protocol drift did not fail verification: {out}{err}",
            "execute the real protocol assertion against the drifted candidate",
        )
        require(
            human.read_bytes() == before and paths[0].read_bytes() == evidence_bytes,
            "owned drift changed foreign human bytes or prior candidate evidence",
            "confine craft/verify to owned subject bytes and preserve prior evidence",
        )
        print("MEASURED drift: VerificationFailed; human bytes unchanged", flush=True)

    def protects_runtime_failure(self) -> None:
        self.compile_subject()
        self.assertion(RECIPE[0], failed=True, label="fixture observer reachable")
        # Exercise the DESIGN-declared callback using the GENERATED observer.
        # The control supplies the exception, never a replacement reporter.
        (self.root / "oracle.ml").write_text(
            'let () = Native_observer.run (fun () -> failwith "native runtime control")\n'
        )
        self.compile_subject()
        direct = self.native(RECIPE[0])
        self.counts(direct.stdout, (0, 0, 1), "caught runtime exception")
        require(
            direct.returncode != 0,
            f"runtime exception was swallowed: exit={direct.returncode}",
            "re-raise non-assertion exceptions after recording setup failure",
        )
        self.bind()
        captured = self.measure_oracle("broken", success=False)
        self.counts(captured["stdout"], (0, 0, 1), "DES retained runtime broken")
        require(
            captured["exit"] != 0,
            f"DES runtime control unexpectedly succeeded: {captured!r}",
            "preserve the authentic exception's nonzero process completion",
        )

    def protects_missing_observation(self) -> None:
        (self.root / "oracle.ml").write_text(
            'let () = print_endline "ASSERTION-FREE: completed"\n'
        )
        self.compile_subject()
        self.bind()
        captured = self.measure_oracle("indeterminate", success=False)
        require(
            captured["exit"] == 0
            and "ASSERTION-FREE: completed\n" in captured["stdout"]
            and not any(
                line.startswith(MARKER) for line in captured["stdout"].splitlines()
            ),
            f"assertion-free control did not complete without a record: {captured!r}",
            "retain genuine native completion without inventing assertion counts",
        )
        print("MEASURED absence: exit=0; no record; verdict=indeterminate", flush=True)

    def protects(self, case: CompletionCase) -> None:
        {
            CompletionCase.DELIVERY: self.protects_delivery,
            CompletionCase.RUNTIME: self.protects_runtime_failure,
            CompletionCase.ABSENT: self.protects_missing_observation,
        }[case]()


@pytest.mark.parametrize("case", list(CompletionCase), ids=lambda case: case.value)
def test_real_dune_completion_preserves_delivery_meaning(
    tmp_path: Path, case: CompletionCase
):
    DuneDeliveryJourney(tmp_path / case.value).protects(case)


def main() -> int:
    observed = assertions_failed = setup_failed = 0
    try:
        with tempfile.TemporaryDirectory(
            prefix="dune-delivery-observations-"
        ) as directory:
            # Stop at the first behavioral RED, so unavailable later controls
            # cannot obscure the baseline's missing native assertion record.
            for case in CompletionCase:
                print(f"EVALUATING: {case.value}", flush=True)
                journey = DuneDeliveryJourney(Path(directory) / case.value)
                try:
                    journey.protects(case)
                except AssertionError as error:
                    observed += 1
                    assertions_failed += 1
                    print(str(error), file=sys.stderr, flush=True)
                    return 1
                observed += 1
                print(f"COMPLETED: {case.value}", flush=True)
        return 0
    except Exception as error:
        setup_failed += 1
        print(
            f"WHAT: acceptance harness could not complete: {error}; WHY: setup "
            "is not behavioral RED or GREEN; HOW: restore the declared runtime "
            "and public fixture prerequisites",
            file=sys.stderr,
            flush=True,
        )
        return 2
    finally:
        print(
            MARKER
            + json.dumps(
                {
                    "version": 1,
                    "observed": observed,
                    "assertions_failed": assertions_failed,
                    "setup_failed": setup_failed,
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())

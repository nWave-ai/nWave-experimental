"""Pinned native tooling reaches every CI test shard without weakening acceptance.

@contract-shape: real-io @architectural-tests
The shipped workflow is the declared configuration port. Remote installation,
case outcomes and the complete CI conclusion remain host-owned observations.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
NATIVE_CASES_PATH = (
    REPO_ROOT
    / "tests/des/acceptance/steps_for_the_orchestrator"
    / "test_dune_delivery_observations.py"
)
PINS = {"OCAML_COMPILER_VERSION": "5.2.1", "DUNE_VERSION": "3.21.1"}


def _require(condition: bool, what: str, how: str) -> None:
    assert condition, (
        f"WHAT: {what}; WHY: every dynamically assigned CI shard must execute "
        f"unchanged acceptance with the agreed native runtime; HOW: {how}"
    )


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _jobs() -> dict:
    return _workflow()["jobs"]


def _run(step: dict) -> str:
    return "\n".join(
        line
        for line in str(step.get("run", "")).splitlines()
        if not line.lstrip().startswith("#")
    ).replace("\\\n", " ")


def _step(job: dict, purpose: str, predicate) -> dict:
    matches = [step for step in job["steps"] if predicate(step)]
    _require(
        len(matches) == 1,
        f"expected one {purpose} step, found {len(matches)}",
        f"provide one unconditional {purpose} step in the test job",
    )
    return matches[0]


def _native_steps(job: dict) -> list[dict]:
    return [
        _step(
            job,
            "cached compiler setup",
            lambda s: str(s.get("uses", "")).startswith("ocaml/setup-ocaml@"),
        ),
        _step(
            job,
            "pinned Dune installation",
            lambda s: bool(re.search(r"\bopam\s+install\b", _run(s))),
        ),
        _step(
            job,
            "switch PATH publication",
            lambda s: bool(re.search(r"\bopam\s+var\s+bin\b", _run(s))),
        ),
        _step(
            job, "native runtime verification", lambda s: "dune --version" in _run(s)
        ),
    ]


def _pytest_step(job: dict) -> dict:
    return _step(
        job,
        "acceptance execution",
        lambda s: bool(re.search(r"\buv\s+run\s+pytest\b", _run(s))),
    )


@pytest.mark.parametrize("name,version", PINS.items())
def test_workflow_env_pins_exact_ocaml_and_dune_versions(
    name: str, version: str
) -> None:
    """L_exact_pins / K_single_pin_owner: each agreed version has one owner."""
    workflow = _workflow()
    actual = workflow.get("env", {}).get(name)
    _require(
        isinstance(actual, str)
        and actual == version
        and bool(re.fullmatch(r"\d+\.\d+\.\d+", actual)),
        f"{name} expected exact string {version}, got {actual!r}",
        "declare the agreed quoted version once in workflow env",
    )
    job = workflow["jobs"]["test"]
    overrides = [
        env
        for env in [job.get("env", {}), *(s.get("env", {}) for s in job["steps"])]
        if name in env
    ]
    _require(
        not overrides,
        f"{name} is overridden below workflow env: {overrides!r}",
        "remove job and step overrides so setup, installation and verification share the workflow pin",
    )


def test_every_test_shard_provisions_before_pytest_unconditionally() -> None:
    """L_all_shards_provision: dynamic ownership never bypasses provisioning."""
    job = _jobs()["test"]
    native = _native_steps(job)
    pytest_step = _pytest_step(job)
    positions = [job["steps"].index(step) for step in [*native, pytest_step]]
    _require(
        positions == sorted(positions) and len(set(positions)) == len(positions),
        f"setup/install/publish/verify/pytest order is {positions!r}",
        "run compiler setup, Dune install, PATH publication and verification before pytest in that order",
    )
    for step in [*native, pytest_step]:
        _require(
            "if" not in step and not step.get("continue-on-error", False),
            f"required step is conditional or failure-tolerant: {step!r}",
            "remove step conditions and continue-on-error so every shard provisions and failures stop testing",
        )
    _require(
        "matrix.shard" not in str(job.get("if", ""))
        and not job.get("continue-on-error", False),
        "test job restricts shard ownership or suppresses failure",
        "retain duration-balanced matrix ownership and normal job failure propagation",
    )
    _require(
        job.get("timeout-minutes") == 45,
        f"test timeout expected 45, got {job.get('timeout-minutes')!r}",
        "preserve the existing bounded test-job timeout",
    )


def test_setup_ocaml_uses_exact_compiler_with_cache_and_without_opam_pin() -> None:
    """L_cache_bounded / L_exact_pins: cached setup installs the agreed compiler."""
    setup = _native_steps(_jobs()["test"])[0]
    _require(
        setup.get("uses") == "ocaml/setup-ocaml@v3",
        f"unexpected compiler action {setup.get('uses')!r}",
        "reuse the declared setup-ocaml v3 action",
    )
    expected = {
        "ocaml-compiler": "ocaml-base-compiler.${{ env.OCAML_COMPILER_VERSION }}",
        "cache": True,
        "opam-pin": False,
    }
    actual = setup.get("with", {})
    _require(
        all(actual.get(key) == value for key, value in expected.items()),
        f"compiler/cache/pinning inputs expected {expected!r}, got {actual!r}",
        "consume the workflow compiler pin, enable cache and disable repository package pinning",
    )


@pytest.mark.parametrize(
    "missing,wrong_versions",
    [
        pytest.param(None, (), id="agreed-runtime-is-ready"),
        pytest.param("dune", (), id="missing-dune-is-refused"),
        pytest.param("ocamlc", (), id="missing-compiler-is-refused"),
        pytest.param("git", (), id="missing-git-is-refused"),
        pytest.param(None, ("dune",), id="wrong-dune-is-refused"),
        pytest.param(None, ("ocamlc",), id="wrong-compiler-is-refused"),
        pytest.param(None, ("dune", "ocamlc"), id="both-wrong-versions-are-refused"),
    ],
)
def test_dune_install_and_verify_consume_the_same_pins(
    tmp_path: Path, missing: str | None, wrong_versions: tuple[str, ...]
) -> None:
    """L_runtime_verified / L_exact_pins: readiness and refusal are observable."""
    _, install, _, verify = _native_steps(_jobs()["test"])
    install_run = _run(install)
    _require(
        "dune.${DUNE_VERSION}" in install_run
        and bool(re.search(r"--switch\s+\"?\$GITHUB_WORKSPACE\"?", install_run))
        and "--yes" in install_run,
        f"Dune install does not use the agreed pin and local switch: {install_run!r}",
        "install dune from DUNE_VERSION noninteractively in the workspace switch",
    )
    run = verify["run"]
    _require(
        "git --version" in run,
        "verification no longer reports the Git version",
        "retain Git version reporting for the host-owned runtime log observation",
    )
    bash = shutil.which("bash")
    _require(
        bash is not None,
        "the verification test runner cannot resolve bash",
        "provide the declared Bash workflow executor to run the shipped verification",
    )
    native_bin = tmp_path / "native-bin"
    native_bin.mkdir()
    tools = {
        "dune": ("--version", PINS["DUNE_VERSION"]),
        "ocamlc": ("-version", PINS["OCAML_COMPILER_VERSION"]),
        "git": ("--version", "git version 2.47.0"),
    }
    for tool, (argument, version) in tools.items():
        if tool == missing:
            continue
        executable = native_bin / tool
        reported = "0.0.0" if tool in wrong_versions else version
        executable.write_text(
            f"#!{bash}\n"
            f'if [ "$#" -ne 1 ] || [ "$1" != "{argument}" ]; then exit 64; fi\n'
            f"printf '%s\\n' '{reported}'\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)
    result = subprocess.run(
        [bash, "--noprofile", "--norc", "-c", run],
        cwd=tmp_path,
        env={"PATH": str(native_bin), "HOME": str(tmp_path), **PINS},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    output = result.stdout + result.stderr
    ready = missing is None and not wrong_versions
    _require(
        (result.returncode == 0) == ready,
        f"runtime readiness={ready}, missing={missing!r}, drift={wrong_versions!r}, "
        f"verification exit={result.returncode}, output={output!r}",
        "accept the agreed runtime and return nonzero for each missing tool or version mismatch",
    )
    if not ready:
        _require(
            all(marker in output for marker in ("::error::", "WHAT:", "WHY:", "HOW:")),
            f"refused runtime lacks actionable observed diagnostics: {output!r}",
            "emit WHAT/WHY/HOW on the actual refusal branch, not an unreachable branch",
        )


def test_switch_bin_is_published_on_github_path() -> None:
    """R_setup_ocaml_puts_dune_on_path: later plain pytest inherits the switch."""
    run = _run(_native_steps(_jobs()["test"])[2])
    _require(
        bool(
            re.search(
                r"opam\s+var\s+bin\s+--switch\s+\"?\$GITHUB_WORKSPACE\"?\s*>>\s*\"?\$GITHUB_PATH\"?",
                run,
            )
        ),
        f"switch bin is not appended to the Actions PATH carrier: {run!r}",
        "publish the workspace switch bin through GITHUB_PATH for subsequent steps",
    )


def test_acceptance_invocation_and_cases_unchanged() -> None:
    """L_acceptance_unchanged: native acceptance remains discoverable on all shards."""
    jobs = _jobs()
    run = _run(_pytest_step(jobs["test"]))
    _require(
        bool(
            re.search(
                r"\buv\s+run\s+pytest\s+tests/\s+-m\s+[\"\x27]not e2e[\"\x27]", run
            )
        )
        and "--splits 4 --group ${{ matrix.shard }}" in run,
        f"plain duration-balanced acceptance invocation changed: {run!r}",
        "retain plain uv-run pytest of tests with the not-e2e marker and dynamic four-way shard group",
    )
    _require(
        not re.search(
            r"(?:--deselect|--ignore|--ignore-glob|(?:^|\s)-k(?:\s|=)|opam\s+exec)", run
        ),
        "acceptance execution is filtered or wrapped",
        "remove deselection, ignore, keyword filtering and opam-exec substitution",
    )
    matrices = [
        json.loads(match)
        for match in re.findall(
            r"matrix=(\{[^\n]*?\})",
            _run(
                _step(jobs["plan"], "matrix selection", lambda s: s.get("id") == "set")
            ),
        )
    ]
    _require(
        bool(matrices)
        and all(matrix.get("shard") == [1, 2, 3, 4] for matrix in matrices),
        f"declared shard populations changed: {matrices!r}",
        "preserve the four shard members in default and full matrices",
    )
    tree = ast.parse(NATIVE_CASES_PATH.read_text(encoding="utf-8"))
    cases = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "CompletionCase"
    )
    population = {
        node.value.value
        for node in cases.body
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
    }
    expected = {
        "answer-and-protocol-delivery-with-owned-drift",
        "runtime-failure-is-not-assertion-red",
        "assertion-free-success-is-indeterminate",
    }
    _require(
        population == expected,
        f"native case population expected {expected!r}, got {population!r}",
        "retain all three existing native completion outcomes unchanged",
    )
    test = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "test_real_dune_completion_preserves_delivery_meaning"
    )
    decorators = [ast.unparse(node) for node in test.decorator_list]
    _require(
        any(
            "parametrize" in decorator and "list(CompletionCase)" in decorator
            for decorator in decorators
        )
        and not any(
            re.search(r"\b(skip|skipif|xfail)\b", decorator) for decorator in decorators
        ),
        f"native case discovery is narrowed or skipped: {decorators!r}",
        "retain parametrization over every completion case with no skip or xfail",
    )

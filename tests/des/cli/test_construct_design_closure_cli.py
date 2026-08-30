"""One public acceptance oracle for ADR-SSOT-002 section 4g."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from tests.common.in_process_cli import run_cli_in_process, run_hook_in_process


_AUTHORITY_PATH = Path("docs/product/architecture/brief.md")
_OBLIGATIONS = (
    "ARCHITECTURE_BOUNDARY_CHANGE",
    "BROAD_INPUT_DOMAIN",
    "CONTESTED_LAW",
    "INVALID_STATE",
    "PRESERVATION",
    "REPRESENTATION_CHANGE",
)
_START = b"<!-- GENERATED:design-closure START -->\n"
_END = b"<!-- GENERATED:design-closure END -->\n"
_REGION = re.compile(
    rb"<!-- GENERATED:design-closure START -->\n"
    rb"```json\n(?P<body>[^\n]+)\n```\n"
    rb"<!-- GENERATED:design-closure END -->\n"
)


def _expect(condition: object, what: str, why: str, how: str) -> None:
    assert condition, f"WHAT: {what}\nWHY: {why}\nHOW: {how}"


def _boundary(label: str) -> dict[str, str]:
    return {
        "failure-behavior": f"{label} refuses without publication",
        "substrate-lie": f"{label} can claim a false success",
        "substrate-probe": f"independently observe {label}",
        "double-blind-spot": f"two {label} paths can share one defect",
    }


def _semantic_case(
    salt: int,
    count: int = 3,
    *,
    oracle_kind: str = "new",
    verification_kind: str = "commands",
) -> dict[str, Any]:
    authority = f"docs/product/architecture/brief-{salt}.md#closure-{salt}"
    oracle = f"tests/test_closure_{salt}.py"
    skill = f"nw-generated-{salt}"
    pbt_family = "nw-property-based-testing"
    dependencies = tuple(
        f"tests/support/dependency-{salt}-{index}.txt" for index in range(1 + salt % 3)
    )
    verification = (
        ".venv/bin/python",
        "-m",
        "pytest",
        f"tests/test_verification_{salt}.py",
        "-q",
    )
    verification_authority = (
        f"docs/product/architecture/verification-{salt}.md#verify-{salt}"
    )
    verification_lines = (
        f".venv/bin/python -m pytest tests/test_verification_{salt}.py -q",
    )
    shapes = (
        "pure-function",
        "bounded-change",
        "unbounded-preservation",
    )
    targets: list[dict[str, Any]] = []
    for index in range(count):
        path = f"pkg_{salt}/target_{index}.py"
        decision = "EXTEND" if index % 2 == 0 else "CREATE_NEW"
        targets.append(
            {
                "path": path,
                "purpose": f"purpose π {salt}-{index}",
                "shape": shapes[index % len(shapes)],
                "decision": decision,
                "extend": (f"existing_{salt}_{index}",) if decision == "EXTEND" else (),
                "create": ()
                if decision == "EXTEND"
                else (
                    (
                        f"legacy_{salt}/candidate_{index}.py",
                        f"legacy_{salt}_{index}",
                        f"candidate {salt}-{index} owns a different observation",
                    ),
                ),
                "imports": ("os", f"support_{salt}_{index}")
                if decision == "EXTEND"
                else (),
                "boundary": _boundary(f"boundary π {salt}-{index}"),
            }
        )
    return {
        "authority": authority,
        "authority_path": Path(authority.split("#", 1)[0]),
        "oracle": oracle,
        "oracle_kind": oracle_kind,
        "skills": (skill, pbt_family),
        "skill_contents": {
            skill: f"method π {salt}\n",
            pbt_family: f"generic property method π {salt}\n",
            "nw-pbt-python": f"Python property adapter π {salt}\n",
        },
        "dependencies": dependencies,
        "verification": verification,
        "verification_kind": verification_kind,
        "verification_authority": verification_authority,
        "verification_lines": verification_lines,
        "paradigm": "functional",
        "targets": targets,
        "obligations": _OBLIGATIONS,
        "outcome": f"seed π {salt}\nsecond line {salt}",
    }


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
    )


def _write_target_substrate(repo_root: Path, target: Mapping[str, Any]) -> None:
    if target["decision"] == "EXTEND":
        path = repo_root / target["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        imports = "import os\n" if "os" in target["imports"] else ""
        imports += "\n".join(
            f"{name} = 1" for name in target["imports"] if name != "os"
        )
        imports += "\n"
        symbols = "\n".join(
            f"def {symbol}():\n    return {symbol!r}\n" for symbol in target["extend"]
        )
        path.write_text(imports + symbols, encoding="utf-8")
    for candidate_path, symbol, _reason in target["create"]:
        path = repo_root / candidate_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"def {symbol}():\n    return {symbol!r}\n",
            encoding="utf-8",
        )


def _verification_test(case: Mapping[str, Any]) -> str:
    expected = case["outcome"].encode("utf-8")
    failure = (
        "WHAT: the compiled outcome changed\\n"
        "WHY: the composed checkpoint must preserve the semantic seed\\n"
        "HOW: preserve fill-contract outcome bytes through recompile"
    )
    return (
        "import json\n"
        "from pathlib import Path\n\n"
        "def test_composed_checkpoint():\n"
        "    contract = json.loads(Path(\n"
        "        'docs/delivery-contracts/closure-slice.json'\n"
        "    ).read_text(encoding='utf-8'))\n"
        f"    assert contract['outcome'].encode('utf-8') == {expected!r}, "
        f"{failure!r}\n"
    )


def _corrupt_valid_authority(
    authority: bytes,
    prefix: bytes,
    suffix: bytes,
    kind: str,
) -> bytes:
    region, envelope = _decode_exact_region(authority, prefix, suffix)
    if kind == "one-sided":
        corrupted = _START
    if kind == "nested":
        corrupted = _START + region + _END
    elif kind == "duplicate":
        corrupted = region + region
    elif kind == "cross-heading":
        return prefix + b"## Other\n\n" + region + suffix
    elif kind == "wrong-owner":
        wrong = _START.replace(b"START", b"START source=docgen")
        corrupted = wrong + region[len(_START) :]
    elif kind == "malformed-json":
        corrupted = _START + b"```json\n{\n```\n" + _END
    elif kind in {
        "empty-payload",
        "digest-valid-structural-payload",
        "unsupported-version",
        "wrong-digest",
        "noncanonical-json",
    }:
        changed = dict(envelope)
        if kind == "empty-payload":
            changed["payload"] = {}
            changed["design-projection-digest"] = _digest({})
        elif kind == "digest-valid-structural-payload":
            changed["payload"] = {"targets": []}
            changed["design-projection-digest"] = _digest(changed["payload"])
        elif kind == "unsupported-version":
            changed["format"] = "DesignClosureV0"
        elif kind == "wrong-digest":
            changed["design-projection-digest"] = "sha256:" + "0" * 64
        body = (
            json.dumps(changed, ensure_ascii=False).encode("utf-8") + b"\n"
            if kind == "noncanonical-json"
            else _compact_json(changed)
        )
        corrupted = _START + b"```json\n" + body + b"```\n" + _END
    elif kind != "one-sided":
        raise AssertionError(f"unknown fixture kind: {kind}")
    return prefix + corrupted + suffix


def _build_repo(
    root: Path,
    case: Mapping[str, Any],
) -> tuple[Path, bytes, bytes]:
    repo_root = root / "repo"
    repo_root.mkdir(parents=True)
    for target in case["targets"]:
        _write_target_substrate(repo_root, target)
    for dependency in case["dependencies"]:
        path = repo_root / dependency
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"dependency {dependency}\n", encoding="utf-8")
    for skill, contents in case["skill_contents"].items():
        path = repo_root / "nWave" / "skills" / skill / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\nname: {skill}\n---\n{contents}", encoding="utf-8")

    if case["oracle_kind"] == "existing":
        oracle_path = repo_root / case["oracle"]
        oracle_path.parent.mkdir(parents=True, exist_ok=True)
        oracle_path.write_text(
            "def test_existing_oracle():\n"
            "    assert True, "
            "'WHAT: fixture failed\\nWHY: existing means present\\nHOW: restore it'\n",
            encoding="utf-8",
        )

    executable = repo_root / case["verification"][0]
    executable.parent.mkdir(parents=True)
    executable.symlink_to(sys.executable)
    verification_path = repo_root / case["verification"][3]
    verification_path.parent.mkdir(parents=True, exist_ok=True)
    verification_path.write_text(_verification_test(case), encoding="utf-8")
    verification_authority_path = (
        repo_root / case["verification_authority"].split("#", 1)[0]
    )
    verification_authority_path.parent.mkdir(parents=True, exist_ok=True)
    verification_heading = case["verification_authority"].rsplit("-", 1)[1]
    verification_authority_path.write_text(
        f"# Verify {verification_heading}\n\n```bash\n"
        + "\n".join(case["verification_lines"])
        + "\n```\n",
        encoding="utf-8",
    )

    authority_path = repo_root / case["authority_path"]
    authority_path.parent.mkdir(parents=True, exist_ok=True)
    heading_number = case["authority"].rsplit("-", 1)[1]
    prefix = (
        f"# Closure {heading_number}\n\n"
        "Immutable prose before the typed projection.\n"
        "Legacy-looking decoy: `pkg_decoy/not_a_target.py:1`, "
        "**REUSE_CANDIDATE**, and `Acceptance support locator:`.\n\n"
    ).encode()
    suffix = b"## Unrelated\n\nImmutable prose after the projection.\n"
    authority_path.write_bytes(prefix + suffix)
    authority_path.chmod(0o640)
    activation = repo_root / ".nwave/config.json"
    activation.parent.mkdir(parents=True)
    activation.write_text('{"enabled":true}\n', encoding="utf-8")
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "test")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "base")
    return repo_root, prefix, suffix


def _target_args(target: Mapping[str, Any]) -> list[str]:
    args = [
        "--target",
        target["path"],
        "--purpose",
        target["purpose"],
        "--shape",
        target["shape"],
    ]
    for symbol in target["extend"]:
        args.extend(("--extend", symbol))
    for candidate_path, symbol, reason in target["create"]:
        args.extend(("--create-new", candidate_path, symbol, reason))
    for imported in target["imports"]:
        args.extend(("--import", imported))
    for option, key in (
        ("--failure-behavior", "failure-behavior"),
        ("--substrate-lie", "substrate-lie"),
        ("--substrate-probe", "substrate-probe"),
        ("--double-blind-spot", "double-blind-spot"),
    ):
        args.extend((option, target["boundary"][key]))
    return args


def _construct_args(
    repo_root: Path,
    case: Mapping[str, Any],
    *,
    target_order: Sequence[int] | None = None,
    reverse_sets: bool = False,
) -> list[str]:
    verification = case["verification"]
    args = [
        "construct-design-closure",
        "--repo-root",
        str(repo_root),
        "--authority",
        case["authority"],
        "--paradigm",
        case["paradigm"],
        "--oracle",
        case["oracle_kind"],
        case["oracle"],
    ]
    if case["verification_kind"] == "commands":
        args.extend(("--verification-executable", verification[0]))
        for token in verification[1:]:
            args.extend(("--verification-arg", token))
    else:
        args.extend(("--verification-authority", case["verification_authority"]))
    order = target_order if target_order is not None else range(len(case["targets"]))
    for index in order:
        args.extend(_target_args(case["targets"][index]))
    for obligation in (
        reversed(case["obligations"]) if reverse_sets else case["obligations"]
    ):
        args.extend(("--obligation", obligation))
    for skill in reversed(case["skills"]) if reverse_sets else case["skills"]:
        args.extend(("--skill", skill))
    dependencies = (
        reversed(case["dependencies"]) if reverse_sets else case["dependencies"]
    )
    for dependency in dependencies:
        args.extend(("--test-dependency", dependency))
    return args


def _run(
    args: Sequence[str],
    *,
    cwd: Path,
    stdin_text: str | None = None,
) -> tuple[int, str, str]:
    return run_cli_in_process(list(args), cwd=cwd, stdin_text=stdin_text)


def _compact_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _digest(payload: Mapping[str, Any]) -> str:
    payload_bytes = _compact_json(payload)
    material = (
        b"nwave-design-projection/v1\0"
        + len(payload_bytes).to_bytes(8, "big")
        + payload_bytes
    )
    return "sha256:" + hashlib.sha256(material).hexdigest()


def _decode_exact_region(
    authority: bytes,
    prefix: bytes,
    suffix: bytes,
) -> tuple[bytes, dict[str, Any]]:
    _expect(
        authority.startswith(prefix) and authority.endswith(suffix),
        "surrounding authority prose changed",
        "the producer owns only one generated region",
        "preserve the exact prefix and suffix bytes",
    )
    region = authority[len(prefix) : len(authority) - len(suffix)]
    match = _REGION.fullmatch(region)
    _expect(
        match is not None,
        "the generated region is not the exact fenced envelope",
        "the public carrier has one canonical byte grammar",
        "emit exact START, one-line compact JSON, END and terminal LFs",
    )
    body = match.group("body") if match is not None else b""
    envelope = json.loads(body)
    _expect(
        set(envelope) == {"design-projection-digest", "format", "payload"},
        "the generated envelope has missing or additional keys",
        "DesignClosureV1 owns one closed three-field wire envelope",
        "emit only format, design-projection-digest and payload",
    )
    _expect(
        envelope["format"] == "DesignClosureV1",
        "the generated envelope has the wrong format variant",
        "readback must reject every unsupported carrier version",
        "emit the exact DesignClosureV1 format tag",
    )
    expected = _START + b"```json\n" + _compact_json(envelope) + b"```\n" + _END
    _expect(
        region == expected,
        "the fenced envelope is not compact sorted-key UTF-8 JSON",
        "normalizable alternatives would create multiple byte identities",
        "render the independently decoded envelope canonically once",
    )
    _expect(
        envelope["design-projection-digest"] == _digest(envelope["payload"]),
        "the design projection digest does not bind canonical payload bytes",
        "shape-only digest checks permit cross-domain or stale payloads",
        "use the domain prefix, uint64 length and canonical payload bytes",
    )
    return region, envelope


def _decision_text(target: Mapping[str, Any]) -> str:
    return json.dumps(target["decision"], ensure_ascii=False, sort_keys=True)


def _walk_lists(value: Any) -> Iterable[list[Any]]:
    if isinstance(value, list):
        yield value
        for member in value:
            yield from _walk_lists(member)
    elif isinstance(value, dict):
        for member in value.values():
            yield from _walk_lists(member)


def _assert_payload(payload: Mapping[str, Any], case: Mapping[str, Any]) -> None:
    _expect(
        set(payload)
        == {
            "authority",
            "obligations",
            "oracle",
            "paradigm",
            "skills",
            "targets",
            "test_dependencies",
            "verification",
        },
        "the payload contains missing or prose-derived state",
        "DesignClosureV1 is the exclusive architecture compiler input",
        "emit exactly the eight typed carrier fields and no dropped-citations",
    )
    _expect(
        payload["authority"] == case["authority"],
        "authority locator changed",
        "selectors are case-sensitive typed input",
        "preserve the literal admitted locator",
    )
    _expect(
        payload["paradigm"] == case["paradigm"],
        "the closed paradigm variant changed",
        "the schema-admitted paradigm is DESIGN-selected typed input",
        "project the selected closed constructor",
    )
    _expect(
        list(payload["targets"])
        == sorted(target["path"] for target in case["targets"]),
        "target keys are missing, extra or noncanonical",
        "nonempty maps canonicalize by UTF-8 path without using the 12 H1 paths",
        "sort and preserve every arbitrary semantic target path",
    )
    expected_by_path = {target["path"]: target for target in case["targets"]}
    for path, projected in payload["targets"].items():
        expected = expected_by_path[path]
        _expect(
            projected["purpose"] == expected["purpose"],
            f"purpose changed for {path}",
            "purpose is the sole justification source",
            "preserve Unicode semantic text exactly",
        )
        _expect(
            projected["shape"] == expected["shape"],
            f"shape changed for {path}",
            "all three closed shapes have different observations",
            "preserve the selected shape without a default",
        )
        _expect(
            set(projected["declared_imports"]) == set(expected["imports"]),
            f"declared imports changed for {path}",
            "imports are grounded target evidence",
            "preserve and canonically order every import",
        )
        _expect(
            projected["boundary"] == expected["boundary"],
            f"one or more boundary facts changed for {path}",
            "each boundary member maps to a distinct contract field",
            "preserve all four complete boundary facts",
        )
        decision = _decision_text(projected).lower()
        expected_variant = expected["decision"].lower()
        _expect(
            expected_variant in decision
            or expected_variant.replace("_", "-") in decision,
            f"decision variant changed for {path}",
            "Extend and CreateNew carry different construction evidence",
            "retain the explicit tagged decision variant",
        )
        evidence = expected["extend"] or tuple(
            item for exclusion in expected["create"] for item in exclusion
        )
        for item in evidence:
            _expect(
                item in decision,
                f"decision evidence {item!r} vanished for {path}",
                "a decision without reuse or exclusion evidence is uninhabited",
                "preserve every symbol, candidate path and exclusion reason",
            )
    _expect(
        payload["obligations"] == sorted(case["obligations"]),
        "closed acceptance obligations changed or are noncanonical",
        "H1 owns exactly six executable obligations",
        "sort the six selected variants without adding REUSE_CANDIDATE",
    )
    _expect(
        payload["skills"] == sorted(case["skills"]),
        "installed skill identities changed or are noncanonical",
        "skill identity is typed input and its fixture content grounds it",
        "preserve each admitted skill name in sorted order",
    )
    _expect(
        payload["test_dependencies"] == sorted(case["dependencies"]),
        "test dependencies changed or are noncanonical",
        "private substrate identity joins the closure digest",
        "preserve each grounded dependency in UTF-8 order",
    )
    oracle_text = json.dumps(payload["oracle"], ensure_ascii=False)
    verification_text = json.dumps(payload["verification"], ensure_ascii=False)
    _expect(
        case["oracle_kind"] in oracle_text.lower() and case["oracle"] in oracle_text,
        "oracle variant or locator changed",
        "oracle identity is a closed tagged value",
        "preserve the selected variant and exact locator",
    )
    expected_verification_tokens = (
        case["verification"]
        if case["verification_kind"] == "commands"
        else (case["verification_authority"],)
    )
    for token in expected_verification_tokens:
        _expect(
            token in verification_text,
            f"verification token {token!r} vanished",
            "argv order and contents are authority",
            "preserve the executable and every ordered argument",
        )
    if case["verification_kind"] == "commands":
        nested_lists = [
            member
            for member in _walk_lists(payload["verification"])
            if all(isinstance(token, str) for token in member)
        ]
        _expect(
            list(case["verification"]) in nested_lists
            or list(case["verification"][1:]) in nested_lists,
            "verification argv order changed",
            "command execution equality is order-sensitive",
            "preserve the exact executable/argument sequence",
        )
    else:
        _expect(
            "delegat" in verification_text.lower(),
            "delegated verification lost its variant",
            "Commands and Delegated are distinct closed constructors",
            "preserve the Delegated tag and exact authority section",
        )


def _compile_args(
    repo_root: Path,
    authority: str,
    *,
    paradigm: str = "functional",
) -> list[str]:
    return [
        "compile-contract",
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "closure-slice",
        "--architecture-authority",
        f"ARCHITECTURE-COVERED: {authority}",
        "--route",
        "RED_TO_GREEN",
        "--paradigm",
        paradigm,
        "--examine",
        "false",
        "--independent-review",
        "true",
        "--budget-token-limit",
        "18000",
        "--budget-wall-clock-minutes",
        "45",
    ]


def _expected_overlap(target: Mapping[str, Any]) -> str:
    if target["decision"] == "EXTEND":
        witnesses = (f"{target['path']}::{symbol}" for symbol in target["extend"])
    else:
        witnesses = (
            f"{candidate_path}::{symbol} — {reason}"
            for candidate_path, symbol, reason in target["create"]
        )
    return "; ".join(sorted(witnesses))


def _assert_compiled_root(
    contract: Mapping[str, Any],
    case: Mapping[str, Any],
    repo_root: Path,
) -> None:
    head = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    expected = {
        "schema-version": "1.4",
        "delivery-id": "closure-slice",
        "repository": {"worktree": ".", "base-revision": f"git-sha1:{head}"},
        "paradigm": case["paradigm"],
        "delivery-route": "RED_TO_GREEN",
        "cited-skills": sorted(case["skills"]),
        "pbt-adapter": {
            "cited": "nw-property-based-testing",
            "resolved-variant": "nw-pbt-python",
            "status": "resolved",
            "reason": "target extension '.py' maps to 'nw-pbt-python'",
        },
        "applicability": {"independent-review": True, "examine": False},
        "budget": {"token-limit": 18000, "wall-clock-minutes": 45},
    }
    _expect(
        {key: contract[key] for key in expected} == expected,
        "one or more compiled root fields changed",
        "schema, identity, paradigm, skills, PBT and delivery inputs each have one source",
        "project the exact typed values without defaults or prose recovery",
    )


def _assert_compiled_targets(
    contract: Mapping[str, Any],
    case: Mapping[str, Any],
) -> None:
    _expect(
        set(contract["targets"]) == {target["path"] for target in case["targets"]},
        "compiled target map differs from DesignClosureV1",
        "free prose and defaults must not become compiler input",
        "compile exclusively from the typed target map",
    )
    for expected in case["targets"]:
        actual = contract["targets"][expected["path"]]
        _expect(
            actual["candidate"] == expected["path"],
            f"candidate/map-key identity broke for {expected['path']}",
            "candidate is derived only from the nonempty map key",
            "emit the identical path as key and candidate",
        )
        _expect(
            actual["decision"] == expected["decision"],
            f"compiled decision changed for {expected['path']}",
            "decision variants project without defaults",
            "map Extend/CreateNew to EXTEND/CREATE_NEW",
        )
        _expect(
            actual["overlap"] == _expected_overlap(expected),
            f"canonical overlap changed for {expected['path']}",
            "reuse and exclusion evidence must survive compilation exactly",
            "sort path::symbol witnesses and join them with canonical separators",
        )
        _expect(
            actual["justification"] == expected["purpose"],
            f"compiled purpose changed for {expected['path']}",
            "purpose is the sole justification source",
            "copy it losslessly",
        )
        _expect(
            actual["contract-shape"] == expected["shape"],
            f"compiled shape changed for {expected['path']}",
            "a default would recreate the removed grammar",
            "project the typed shape",
        )
        _expect(
            set(actual["declared-imports"]) == set(expected["imports"]),
            f"compiled imports changed for {expected['path']}",
            "imports are design-owned typed facts",
            "preserve each grounded import",
        )
        _expect(
            actual["boundary"] == expected["boundary"],
            f"compiled boundary changed for {expected['path']}",
            "all four fields are required construction evidence",
            "copy all boundary facts exactly",
        )


def test_construct_compile_fill_recompile_and_execute_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _semantic_case(41, count=4)
    repo_root, prefix, suffix = _build_repo(tmp_path, case)
    authority_path = repo_root / case["authority_path"]
    initial = authority_path.read_bytes()
    mode = stat.S_IMODE(authority_path.stat().st_mode)

    construct_args = _construct_args(repo_root, case)
    from des.adapters.drivers.hooks import pre_tool_use_handler

    transcript = tmp_path / "auto-root-transcript.jsonl"
    transcript.write_text(
        "\n".join(
            json.dumps({"type": "tool_use", "name": "Skill", "input": {"skill": skill}})
            for skill in ("nw-auto", "nw-mode-select")
        )
        + "\n",
        encoding="utf-8",
    )
    hook_event = json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {"command": shlex.join(["des", *construct_args])},
            "transcript_path": str(transcript),
        }
    )
    hook_env = dict(os.environ)
    hook_env["DES_PROJECT_DIR"] = str(repo_root)
    hook_code, hook_stdout, hook_stderr = run_hook_in_process(
        pre_tool_use_handler.handle_pre_tool_use,
        stdin_text=hook_event,
        cwd=repo_root,
        env=hook_env,
    )
    hook_payload = json.loads(hook_stdout) if hook_stdout.strip() else None
    _expect(
        hook_code == 0
        and not (
            isinstance(hook_payload, dict) and hook_payload.get("decision") == "block"
        ),
        "the exact construct invocation is blocked by Auto root",
        hook_stdout + hook_stderr,
        "allow this one literal semantic argv form without shell composition",
    )
    code, out, err = _run(construct_args, cwd=repo_root)
    _expect(code == 0, "construction refused", err, "implement the typed producer")
    _expect(
        out == f"DESIGN-CLOSURE-WRITTEN: {case['authority']}\n",
        "success terminal changed",
        "the public port has one observable success",
        "emit the exact locator terminal once",
    )
    authority = authority_path.read_bytes()
    region, envelope = _decode_exact_region(authority, prefix, suffix)
    _assert_payload(envelope["payload"], case)
    _expect(
        stat.S_IMODE(authority_path.stat().st_mode) == mode,
        "authority mode changed",
        "atomic replacement must preserve the destination mode",
        "copy the prior mode to the same-directory temporary",
    )
    _expect(
        not list(authority_path.parent.glob("*.tmp"))
        and not list(authority_path.parent.glob("*.bak")),
        "publication left a temporary or backup",
        "H1 admits bounded temporary mechanics and no .bak",
        "clean the sibling temporary on every terminal path",
    )

    code, _out, err = _run(
        _compile_args(repo_root, case["authority"]),
        cwd=repo_root,
    )
    _expect(code == 0, "typed compile refused", err, "consume DesignClosureV1")
    contract_path = repo_root / "docs/delivery-contracts/closure-slice.json"
    skeleton = json.loads(contract_path.read_text(encoding="utf-8"))
    _assert_compiled_root(skeleton, case, repo_root)
    _assert_compiled_targets(skeleton, case)
    _expect(
        "dropped-citations" not in skeleton
        and "pkg_decoy/not_a_target.py" not in json.dumps(skeleton),
        "free-prose decoy entered the compiled skeleton",
        "architecture input must end at DesignClosureV1",
        "remove every Markdown citation/default fallback",
    )

    fill = json.dumps([{"field": "outcome", "value": case["outcome"]}])
    code, out, err = _run(
        [
            "fill-contract",
            "--repo-root",
            str(repo_root),
            "--delivery-id",
            "closure-slice",
            "--batch",
        ],
        cwd=repo_root,
        stdin_text=fill,
    )
    _expect(code == 0, "fill-contract refused", err, "publish the atomic batch")
    _expect(
        "CONTRACT-FILL-STATUS: COMPLETE" in out,
        "fill did not report COMPLETE",
        "the composed checkpoint requires a complete contract",
        "fill the exact remaining outcome field",
    )
    filled = contract_path.read_bytes()

    code, out, err = _run(
        [
            "recompile-contract",
            "--repo-root",
            str(repo_root),
            "--delivery-id",
            "closure-slice",
            "--architecture-authority",
            f"ARCHITECTURE-COVERED: {case['authority']}",
        ],
        cwd=repo_root,
    )
    _expect(code == 0, "typed recompile refused", err, "preserve eligible fills")
    recompiled = json.loads(contract_path.read_text(encoding="utf-8"))
    _assert_compiled_root(recompiled, case, repo_root)
    _assert_compiled_targets(recompiled, case)
    _expect(
        recompiled["obligations"] == sorted(case["obligations"]),
        "compiled obligations differ from the six typed variants",
        "acceptance obligations have one architecture source",
        "preserve and sort the typed set without REUSE_CANDIDATE",
    )
    _expect(
        recompiled["acceptance-tests"]
        == {
            "locator": case["oracle"],
            "supporting-locators": sorted(case["dependencies"]),
        },
        "oracle or test dependencies changed during compile/recompile",
        "the primary identity and private substrate form one closure",
        "project the exact typed locator and sorted dependency set",
    )
    stored_command = recompiled["verification-scope"]["commands"][0]
    _expect(
        stored_command["executable"]
        == {"kind": "repository", "path": case["verification"][0]}
        and stored_command["arguments"] == list(case["verification"][1:]),
        "compiled verification argv differs from typed input",
        "execution equality is order-sensitive",
        "project the repository executable and ordered arguments exactly",
    )
    _expect(
        recompiled["outcome"].encode("utf-8") == case["outcome"].encode("utf-8"),
        "lossless seed/outcome bytes changed across recompile",
        "UTF-8 decode then encode must reproduce every admitted byte",
        "preserve the filled Unicode outcome exactly",
    )
    _expect(
        filled != b"" and "CONTRACT" in out.upper(),
        "recompile emitted no public preservation summary",
        "silent mutation cannot establish the composed checkpoint",
        "emit the existing locator/preserve-fills summary",
    )

    command = stored_command
    executable = repo_root / command["executable"]["path"]
    result = subprocess.run(
        [str(executable), *command["arguments"]],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    _expect(
        result.returncode == 0,
        "repository-local verification failed at the composed checkpoint",
        result.stdout + result.stderr,
        "execute the stored argv after fill and recompile",
    )

    code, _out, err = _run(_construct_args(repo_root, case), cwd=repo_root)
    _expect(
        code == 0,
        "idempotent reconstruction refused",
        err,
        "reread and rerender",
    )
    _expect(
        authority_path.read_bytes() == authority and region in authority,
        "idempotent construction changed canonical bytes",
        "equal typed values must render equal regions",
        "canonicalize maps and sets before publication",
    )

    def refuse_replace(_source: object, _destination: object) -> None:
        raise OSError("injected replace refusal")

    changed = dict(case)
    changed["targets"] = [dict(target) for target in case["targets"]]
    changed["targets"][0]["purpose"] = "must not leak"
    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", refuse_replace)
        code, _out, err = _run(_construct_args(repo_root, changed), cwd=repo_root)
    _expect(code != 0, "replace failure reported success", err, "propagate refusal")
    _expect(
        all(label in err for label in ("WHAT:", "WHY:", "HOW:")),
        "replace refusal lacks WHAT/WHY/HOW",
        "recovery must be observable",
        "render one typed refusal with recovery guidance",
    )
    _expect(
        authority_path.read_bytes() == authority,
        "replace refusal changed authority bytes",
        "failure before replace preserves the prior complete file",
        "publish only through one successful os.replace",
    )
    _expect(
        not list(authority_path.parent.glob("*.tmp")),
        "replace refusal leaked a temporary",
        "bounded mechanics must clean up after failure",
        "unlink only the sibling temporary",
    )
    _expect(
        initial == prefix + suffix,
        "fixture began nonempty",
        "initial publication admits zero pairs",
        "keep the valid fixture independently inhabitable",
    )


@pytest.mark.parametrize("paradigm", ("functional", "object_oriented"))
def test_construct_dispatch_and_compile_project_each_schema_paradigm(
    tmp_path: Path,
    paradigm: str,
) -> None:
    case = _semantic_case(44)
    case["paradigm"] = paradigm
    repo_root, prefix, suffix = _build_repo(tmp_path, case)

    code, _out, err = _run(_construct_args(repo_root, case), cwd=repo_root)

    _expect(
        code == 0,
        f"{paradigm} was refused by the real construct dispatcher",
        err,
        "admit every schema-declared paradigm through construction",
    )
    _region, envelope = _decode_exact_region(
        (repo_root / case["authority_path"]).read_bytes(), prefix, suffix
    )
    _assert_payload(envelope["payload"], case)

    code, _out, err = _run(
        _compile_args(repo_root, case["authority"], paradigm=paradigm),
        cwd=repo_root,
    )

    _expect(
        code == 0,
        f"{paradigm} was refused by compile-contract",
        err,
        "project the same selected constructor into the contract",
    )
    contract = json.loads(
        (repo_root / "docs/delivery-contracts/closure-slice.json").read_text(
            encoding="utf-8"
        )
    )
    _assert_compiled_root(contract, case, repo_root)


def test_construct_refuses_a_third_paradigm_without_mutating_authority(
    tmp_path: Path,
) -> None:
    case = _semantic_case(45)
    repo_root, _prefix, _suffix = _build_repo(tmp_path, case)
    authority_path = repo_root / case["authority_path"]
    before = authority_path.read_bytes()
    args = _construct_args(repo_root, case)
    args[args.index("--paradigm") + 1] = "imperative"

    code, _out, err = _run(args, cwd=repo_root)

    _expect(
        code != 0 and "paradigm" in err.lower(),
        "an undeclared third paradigm was accepted",
        err,
        "refuse every value outside the schema's two-constructor algebra",
    )
    _expect(
        authority_path.read_bytes() == before,
        "an invalid paradigm changed authority bytes",
        "an uninhabited constructor must not reach publication",
        "validate the closed variant before writing the generated region",
    )


def test_existing_oracle_and_delegated_verification_are_inhabited(
    tmp_path: Path,
) -> None:
    case = _semantic_case(
        47,
        oracle_kind="existing",
        verification_kind="delegated",
    )
    repo_root, prefix, suffix = _build_repo(tmp_path, case)

    code, _out, err = _run(_construct_args(repo_root, case), cwd=repo_root)
    _expect(
        code == 0,
        "ExistingOracle plus Delegated refused construction",
        err,
        "inhabit both alternate closed variants through the public dispatcher",
    )
    authority = (repo_root / case["authority_path"]).read_bytes()
    _region, envelope = _decode_exact_region(authority, prefix, suffix)
    _assert_payload(envelope["payload"], case)

    code, _out, err = _run(
        _compile_args(repo_root, case["authority"]),
        cwd=repo_root,
    )
    _expect(
        code == 0,
        "ExistingOracle plus Delegated refused compilation",
        err,
        "project the two variants into the existing contract fields",
    )
    contract = json.loads(
        (repo_root / "docs/delivery-contracts/closure-slice.json").read_text(
            encoding="utf-8"
        )
    )
    _assert_compiled_root(contract, case, repo_root)
    _assert_compiled_targets(contract, case)
    _expect(
        contract["acceptance-tests"]
        == {
            "locator": case["oracle"],
            "supporting-locators": sorted(case["dependencies"]),
        },
        "ExistingOracle did not preserve its exact public identity",
        "new and existing are distinct constructors with the same contract locator field",
        "project the existing locator and ordered private dependencies",
    )
    lines = list(case["verification_lines"])
    digest = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    _expect(
        contract["verification-scope"]
        == {
            "literal-script-block": {
                "locator": case["verification_authority"],
                "content-digest": f"sha256:{digest}",
                "lines": lines,
            }
        },
        "Delegated did not preserve the exact authority section",
        "delegation is by-reference and cannot become argv commands",
        "emit the locator, literal lines and their exact content digest",
    )


def test_commands_keep_red_and_base_green_argvs_ordered_through_compile(
    tmp_path: Path,
) -> None:
    case = _semantic_case(48)
    repo_root, prefix, suffix = _build_repo(tmp_path, case)
    args = _construct_args(repo_root, case)
    first_target = args.index("--target")
    base_green = ("tools/base-green", "--all", "--no-network")
    args[first_target:first_target] = [
        "--verification-executable",
        base_green[0],
        "--verification-arg",
        base_green[1],
        "--verification-arg",
        base_green[2],
    ]

    code, _out, err = _run(args, cwd=repo_root)
    _expect(code == 0, "two command closure refused", err, "preserve both argv vectors")
    authority_path = repo_root / case["authority_path"]
    first = tuple(case["verification"])
    expected = [list(first), list(base_green)]
    _region, envelope = _decode_exact_region(
        authority_path.read_bytes(), prefix, suffix
    )
    _expect(
        envelope["payload"]["verification"] == {"kind": "commands", "argvs": expected},
        "constructor did not emit canonical ordered command vectors",
        "P5 needs the red feature oracle and distinct base-green preservation argv",
        "emit one argvs list in invocation order",
    )
    constructed = authority_path.read_bytes()

    code, _out, err = _run(_compile_args(repo_root, case["authority"]), cwd=repo_root)
    _expect(
        code == 0,
        "multi-command closure refused compilation",
        err,
        "derive every command",
    )
    contract = json.loads(
        (repo_root / "docs/delivery-contracts/closure-slice.json").read_text(
            encoding="utf-8"
        )
    )
    _expect(
        contract["verification-scope"]["commands"]
        == [
            {
                "executable": {"kind": "repository", "path": argv[0]},
                "arguments": argv[1:],
            }
            for argv in expected
        ],
        "compiler lost or reordered a closure verification command",
        "command order is executable authority",
        "derive each argvs member into verification-scope.commands",
    )

    code, _out, err = _run(args, cwd=repo_root)
    _expect(
        code == 0,
        "repeat multi-command construction refused",
        err,
        "render canonically",
    )
    _expect(
        authority_path.read_bytes() == constructed,
        "equivalent multi-command input rendered different bytes",
        "closure digest binds one deterministic representation",
        "preserve canonical ordered argvs rendering",
    )


@pytest.mark.parametrize(
    ("inserted", "needle"),
    (
        (("--verification-arg", "-q"), "must follow"),
        (("--verification-executable", ""), "nonempty"),
        (("--verification-executable", "../escape"), "repository-relative"),
    ),
)
def test_commands_refuse_unbound_empty_or_escaping_argv(
    tmp_path: Path, inserted: tuple[str, str], needle: str
) -> None:
    case = _semantic_case(46)
    repo_root, _prefix, _suffix = _build_repo(tmp_path, case)
    authority_path = repo_root / case["authority_path"]
    before = authority_path.read_bytes()
    args = _construct_args(repo_root, case)
    if inserted[0] == "--verification-arg":
        args[1:1] = inserted
    else:
        args.extend(inserted)

    code, _out, err = _run(args, cwd=repo_root)

    _expect(
        code != 0 and needle in err,
        "malformed command argv was accepted",
        err,
        "refuse before publication",
    )
    _expect(
        authority_path.read_bytes() == before,
        "refused command argv changed authority bytes",
        "invalid command grammar must not publish a carrier",
        "correct the argv and retry",
    )


def test_compiler_reads_legacy_single_command_closure_carrier(tmp_path: Path) -> None:
    case = _semantic_case(44)
    repo_root, prefix, suffix = _build_repo(tmp_path, case)
    code, _out, err = _run(_construct_args(repo_root, case), cwd=repo_root)
    _expect(code == 0, "new closure setup refused", err, "construct fixture authority")
    authority_path = repo_root / case["authority_path"]
    _region, envelope = _decode_exact_region(
        authority_path.read_bytes(), prefix, suffix
    )
    legacy_argv = envelope["payload"]["verification"]["argvs"][0]
    envelope["payload"]["verification"] = {"kind": "commands", "argv": legacy_argv}
    envelope["design-projection-digest"] = _digest(envelope["payload"])
    authority_path.write_bytes(
        prefix
        + _START
        + b"```json\n"
        + _compact_json(envelope)
        + b"```\n"
        + _END
        + suffix
    )

    code, _out, err = _run(_compile_args(repo_root, case["authority"]), cwd=repo_root)

    _expect(
        code == 0,
        "legacy single argv carrier no longer compiles",
        err,
        "retain reader compatibility",
    )
    contract = json.loads(
        (repo_root / "docs/delivery-contracts/closure-slice.json").read_text(
            encoding="utf-8"
        )
    )
    _expect(
        contract["verification-scope"]["commands"]
        == [
            {
                "executable": {"kind": "repository", "path": legacy_argv[0]},
                "arguments": legacy_argv[1:],
            }
        ],
        "legacy argv did not project to its original command",
        "the carrier migration is writer-only",
        "interpret legacy argv as one ordered command",
    )


@pytest.mark.parametrize(
    "argvs",
    (
        (),
        ((),),
        (("../outside",),),
    ),
)
def test_compiler_refuses_malformed_or_escaping_command_vectors(
    tmp_path: Path, argvs: tuple[tuple[str, ...], ...]
) -> None:
    case = _semantic_case(43)
    repo_root, prefix, suffix = _build_repo(tmp_path, case)
    code, _out, err = _run(_construct_args(repo_root, case), cwd=repo_root)
    _expect(code == 0, "new closure setup refused", err, "construct fixture authority")
    authority_path = repo_root / case["authority_path"]
    _region, envelope = _decode_exact_region(
        authority_path.read_bytes(), prefix, suffix
    )
    envelope["payload"]["verification"] = {
        "kind": "commands",
        "argvs": [list(argv) for argv in argvs],
    }
    envelope["design-projection-digest"] = _digest(envelope["payload"])
    authority_path.write_bytes(
        prefix
        + _START
        + b"```json\n"
        + _compact_json(envelope)
        + b"```\n"
        + _END
        + suffix
    )

    code, _out, err = _run(_compile_args(repo_root, case["authority"]), cwd=repo_root)

    _expect(
        code != 0 and "argv" in err.lower(),
        "compiler accepted malformed command vector",
        err,
        "reject malformed or escaping executables before contract publication",
    )


def test_semantic_marker_text_is_data_and_idempotently_reconstructs(
    tmp_path: Path,
) -> None:
    case = _semantic_case(49)
    marker = "<!-- GENERATED:design-closure START -->"
    case["targets"][0]["purpose"] = f"literal semantic data: {marker}"
    repo_root, prefix, suffix = _build_repo(tmp_path, case)
    authority_path = repo_root / case["authority_path"]

    code, _out, err = _run(_construct_args(repo_root, case), cwd=repo_root)

    _expect(
        code == 0,
        "literal marker text in a semantic field was treated as carrier structure",
        err,
        "count only complete marker-delimited regions outside JSON data",
    )
    constructed = authority_path.read_bytes()
    _region, envelope = _decode_exact_region(constructed, prefix, suffix)
    _assert_payload(envelope["payload"], case)

    code, _out, err = _run(_construct_args(repo_root, case), cwd=repo_root)

    _expect(
        code == 0,
        "idempotent reconstruction with literal marker text was refused",
        err,
        "decode the carrier before judging semantic string contents",
    )
    _expect(
        authority_path.read_bytes() == constructed,
        "idempotent reconstruction changed bytes containing literal marker text",
        "semantic marker text is data, not a second generated region",
        "preserve the canonical carrier byte-for-byte on identical retry",
    )


@pytest.mark.parametrize("fault", ("duplicate", "noncanonical-json"))
def test_compile_refuses_any_marked_noncanonical_carrier_without_legacy_fallback(
    tmp_path: Path,
    fault: str,
) -> None:
    case = _semantic_case(50)
    repo_root, prefix, suffix = _build_repo(tmp_path, case)
    authority_path = repo_root / case["authority_path"]
    code, _out, err = _run(_construct_args(repo_root, case), cwd=repo_root)
    _expect(
        code == 0,
        f"valid setup for {fault} refused",
        err,
        "construct one canonical carrier before corrupting its bytes",
    )

    if fault == "duplicate":
        region, _envelope = _decode_exact_region(
            authority_path.read_bytes(), prefix, suffix
        )
        authority_path.write_bytes(prefix + region + region + suffix)
    else:
        authority_path.write_bytes(
            _corrupt_valid_authority(authority_path.read_bytes(), prefix, suffix, fault)
        )
    before_authority = authority_path.read_bytes()
    contract_path = repo_root / "docs/delivery-contracts/closure-slice.json"
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    sentinel = b"pre-existing contract destination\n"
    contract_path.write_bytes(sentinel)

    code, _out, err = _run(
        _compile_args(repo_root, case["authority"]),
        cwd=repo_root,
    )

    _expect(
        code != 0,
        f"{fault} marked carrier compiled through legacy prose fallback",
        err,
        "a cited section containing any design-closure marker must use only the canonical carrier parser",
    )
    _expect(
        all(label in err for label in ("WHAT:", "WHY:", "HOW:")),
        f"{fault} carrier refusal lacks WHAT/WHY/HOW",
        "the carrier is an observable authority boundary",
        "report the malformed marker state and its recovery",
    )
    _expect(
        "designclosure" in err.lower() or "design-closure" in err.lower(),
        f"{fault} carrier was not identified as a closure failure",
        "a marker forbids the legacy prose route",
        "name the design-closure carrier rather than reporting legacy citation gaps",
    )
    _expect(
        authority_path.read_bytes() == before_authority,
        f"{fault} compilation normalized the cited authority",
        "compile-contract is a consumer and may not repair malformed input",
        "preserve the exact cited authority bytes",
    )
    _expect(
        contract_path.read_bytes() == sentinel,
        f"{fault} compilation published over an existing destination",
        "refusal must precede all contract publication",
        "leave the destination byte-for-byte unchanged",
    )


def test_docgen_refuses_design_closure_before_any_write(tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parents[3]
    repo_root = tmp_path / "docgen-repo"
    asset = repo_root / "nWave/agents/design-closure-probe.md"
    asset.parent.mkdir(parents=True)
    (repo_root / "nWave/tasks/nw").mkdir(parents=True)
    (repo_root / "nWave/skills").mkdir(parents=True)
    asset.write_text(
        "---\nname: probe\ndescription: probe\n---\n"
        "<!-- GENERATED:design-closure START -->\n"
        "must remain byte-identical\n"
        "<!-- GENERATED:design-closure END -->\n",
        encoding="utf-8",
    )
    before = {
        path.relative_to(repo_root): path.read_bytes()
        for path in repo_root.rglob("*")
        if path.is_file()
    }

    result = subprocess.run(
        [
            sys.executable,
            str(source_root / "scripts/docgen.py"),
            "--root",
            str(repo_root),
            "--output-dir",
            str(repo_root / "generated"),
        ],
        cwd=source_root,
        capture_output=True,
        text=True,
    )

    _expect(
        result.returncode != 0 and "design-closure" in result.stderr,
        "docgen accepted the architecture-owned design-closure source",
        result.stdout + result.stderr,
        "refuse that source id through scripts/docgen.py",
    )
    after = {
        path.relative_to(repo_root): path.read_bytes()
        for path in repo_root.rglob("*")
        if path.is_file()
    }
    _expect(
        after == before,
        "docgen wrote before refusing design-closure",
        "exclusive source ownership must be decided during projection",
        "refuse before write_generated_regions or page publication",
    )


@pytest.mark.parametrize(
    "fault",
    (
        "one-sided",
        "nested",
        "duplicate",
        "cross-heading",
        "wrong-owner",
        "malformed-json",
        "noncanonical-json",
        "empty-payload",
        "digest-valid-structural-payload",
        "unsupported-version",
        "wrong-digest",
    ),
)
def test_each_malformed_region_refuses_without_mutation(
    tmp_path: Path,
    fault: str,
) -> None:
    case = _semantic_case(52)
    repo_root, prefix, suffix = _build_repo(tmp_path, case)
    authority_path = repo_root / case["authority_path"]
    code, _out, err = _run(_construct_args(repo_root, case), cwd=repo_root)
    _expect(
        code == 0,
        f"valid setup for {fault} refused",
        err,
        "construct one inhabitable carrier before corrupting one dimension",
    )
    authority_path.write_bytes(
        _corrupt_valid_authority(
            authority_path.read_bytes(),
            prefix,
            suffix,
            fault,
        )
    )
    before = authority_path.read_bytes()

    code, _out, err = _run(_construct_args(repo_root, case), cwd=repo_root)

    _expect(code != 0, f"{fault} region reported success", err, "refuse before write")
    _expect(
        all(label in err for label in ("WHAT:", "WHY:", "HOW:")),
        f"{fault} refusal lacks WHAT/WHY/HOW",
        "all finite carrier failures share one recoverable observation",
        "name the malformed state and preserve bytes",
    )
    _expect(
        authority_path.read_bytes() == before,
        f"{fault} refusal changed authority bytes",
        "malformed readback cannot be normalized",
        "leave the exact prior bytes untouched",
    )
    _expect(
        not list(authority_path.parent.glob("*.tmp")),
        f"{fault} refusal leaked a temporary",
        "validation precedes publication",
        "construct no publication temporary",
    )


def _without_target_groups(args: list[str]) -> list[str]:
    first = args.index("--target")
    return args[:first]


@pytest.mark.parametrize(
    ("kind", "needles"),
    (
        ("empty-target", ("target", "nonempty")),
        (
            "multiple-target-errors",
            ("purpose", "substrate-probe", "extend", "create-new"),
        ),
        ("conflicting-verification", ("verification", "authority")),
        ("invalid-locators", ("repository-relative", "oracle", "executable")),
        ("empty-boundary", ("substrate-probe", "empty")),
        ("malformed-target-path", ("target", "repository-relative")),
        ("space-in-target-path", ("target", "repository-relative")),
    ),
)
def test_invalid_semantic_batches_report_every_problem_and_preserve_bytes(
    tmp_path: Path,
    kind: str,
    needles: tuple[str, ...],
) -> None:
    case = _semantic_case(63)
    repo_root, _prefix, _suffix = _build_repo(tmp_path, case)
    authority_path = repo_root / case["authority_path"]
    before = authority_path.read_bytes()
    args = _construct_args(repo_root, case)
    if kind == "empty-target":
        args = _without_target_groups(args)
    elif kind == "multiple-target-errors":
        first_target = args.index("--target")
        global_tail = args.index("--obligation")
        first = case["targets"][0]
        second = case["targets"][1]
        first_group = [
            "--target",
            first["path"],
            "--shape",
            first["shape"],
            "--extend",
            first["extend"][0],
            "--failure-behavior",
            first["boundary"]["failure-behavior"],
            "--substrate-lie",
            first["boundary"]["substrate-lie"],
            "--double-blind-spot",
            first["boundary"]["double-blind-spot"],
        ]
        second_group = _target_args(second)
        second_group.extend(("--extend", "conflicting_reuse"))
        args = args[:first_target] + first_group + second_group + args[global_tail:]
    elif kind == "conflicting-verification":
        args.extend(("--verification-authority", case["authority"]))
    elif kind == "invalid-locators":
        args[args.index("--authority") + 1] = "../escape.md#bad"
        args[args.index("--oracle") + 2] = "../escape.py"
        args[args.index("--verification-executable") + 1] = "../python"
    elif kind == "empty-boundary":
        args[args.index("--substrate-probe") + 1] = ""
    elif kind == "malformed-target-path":
        args[args.index("--target") + 1] = "pkg//bad.py"
    else:
        args[args.index("--target") + 1] = "pkg/a b.py"

    code, _out, err = _run(args, cwd=repo_root)

    _expect(code != 0, f"{kind} batch reported success", err, "refuse all-at-once")
    _expect(
        all(label in err for label in ("WHAT:", "WHY:", "HOW:")),
        f"{kind} aggregate lacks WHAT/WHY/HOW",
        "every invalid semantic batch must explain failure and recovery",
        "render the complete aggregate through the shared refusal vocabulary",
    )
    for needle in needles:
        _expect(
            needle.lower() in err.lower(),
            f"{kind} omitted independently observable problem {needle!r}",
            "aggregate refusal prevents serial repair ping-pong",
            "report every detectable problem in one WHAT/WHY/HOW result",
        )
    _expect(
        authority_path.read_bytes() == before,
        f"{kind} batch changed authority bytes",
        "invalid semantic input has no constructed value",
        "validate the complete batch before publication",
    )
    _expect(
        not list(authority_path.parent.glob("*.tmp")),
        f"{kind} batch leaked a temporary",
        "invalid construction must not reach the publisher",
        "create no sibling temporary",
    )


@st.composite
def _broad_cases(draw: st.DrawFn) -> tuple[dict[str, Any], tuple[int, ...], bool]:
    salt = draw(st.integers(min_value=100, max_value=99_999))
    count = draw(st.integers(min_value=3, max_value=5))
    obligations = tuple(
        draw(
            st.sets(
                st.sampled_from(_OBLIGATIONS),
                min_size=1,
                max_size=len(_OBLIGATIONS),
            )
        )
    )
    case = _semantic_case(salt, count)
    case["obligations"] = obligations
    order = draw(st.permutations(tuple(range(count))))
    return case, order, draw(st.booleans())


@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(generated=_broad_cases())
def test_broad_typed_domain_has_one_canonical_inhabited_projection(
    tmp_path: Path,
    generated: tuple[dict[str, Any], tuple[int, ...], bool],
) -> None:
    case, order, reverse_sets = generated
    with tempfile.TemporaryDirectory(dir=tmp_path) as case_dir:
        root = Path(case_dir)
        reference_root, prefix, suffix = _build_repo(root / "reference", case)
        code, _out, err = _run(
            _construct_args(reference_root, case),
            cwd=reference_root,
        )
        _expect(
            code == 0,
            "generated reference refused",
            err,
            "inhabit the typed case",
        )
        reference_authority = (reference_root / case["authority_path"]).read_bytes()
        reference_region, reference_envelope = _decode_exact_region(
            reference_authority,
            prefix,
            suffix,
        )
        _assert_payload(reference_envelope["payload"], case)

        variant_root, prefix, suffix = _build_repo(root / "variant", case)
        code, _out, err = _run(
            _construct_args(
                variant_root,
                case,
                target_order=order,
                reverse_sets=reverse_sets,
            ),
            cwd=variant_root,
        )
        _expect(
            code == 0,
            "generated permutation refused",
            err,
            "canonicalize input order",
        )
        variant_authority = (variant_root / case["authority_path"]).read_bytes()
        variant_region, variant_envelope = _decode_exact_region(
            variant_authority,
            prefix,
            suffix,
        )
        _assert_payload(variant_envelope["payload"], case)
        _expect(
            variant_region == reference_region
            and variant_envelope == reference_envelope,
            "equal typed values produced different canonical bytes",
            "map and set input order is observationally irrelevant",
            "sort targets, obligations, skills, imports and dependencies",
        )

        code, _out, err = _run(
            _construct_args(
                variant_root,
                case,
                target_order=order,
                reverse_sets=reverse_sets,
            ),
            cwd=variant_root,
        )
        _expect(
            code == 0,
            "idempotent generated retry refused",
            err,
            "reread canonical bytes",
        )
        _expect(
            (variant_root / case["authority_path"]).read_bytes() == variant_authority,
            "generated retry changed canonical bytes",
            "canonicalization is idempotent",
            "publish the identical region for equal typed input",
        )

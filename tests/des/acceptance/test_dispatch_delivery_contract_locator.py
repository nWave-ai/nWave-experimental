"""Acceptance specs -- retarget-des-dispatch-contract (C5, ADR-SSOT-002 S4a).

Independent, uncontaminated acceptance designer (ATD) authorship -- no read of
any PO charter. Value seed: a DELIVER-test-executing `des dispatch` currently
succeeds WITHOUT an explicit repo-root-relative `DeliveryContract`, warns about
`feature-delta.md`, and cites it as a "Design reference". Per ADR-SSOT-002
S4a, the operator must instead receive one discoverable contract requirement
(a required `--repo-root <ROOT>` + `--delivery-contract <PATH>` pair,
`PATH` resolved ONLY against `ROOT`) or a WHAT/WHY/HOW refusal -- BEFORE any
prompt is rendered -- on every DELIVER-test-executing route; authoring-wave
dispatches (e.g. `--wave discuss`) remain usable with no contract at all.

CONTRACT_SHAPE: bounded-change (a finite CLI-boundary locator law) with one
BROAD_INPUT_DOMAIN leg (the unsafe-path-segment domain for `--delivery-
contract`, covered by a bounded Hypothesis property, never enumerated by
hand).

Driving surface: the public `des dispatch` CLI, in-process via
`tests.common.in_process_cli.run_cli_in_process` (repo convention, mirrors
`tests/des/unit/cli/test_des_dispatch_generator.py`) -- the SAME production
`des.cli.__main__.main(argv) -> int` edge a real subprocess invokes; never
`des.cli.dispatch` imported directly.

FAILS TODAY: `--delivery-contract` does not exist on the parser at all, so
every "valid pair" / "missing pair refuses" / "unsafe path refuses" scenario
below fails for a genuine semantic reason (a missing flag / absent refusal
text / present feature-delta text), never a collection error.

covers: retarget-des-dispatch-contract (ADR-SSOT-002 S4a)
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.common.in_process_cli import run_cli_in_process


_REPO_ROOT = Path(__file__).resolve().parents[3]
_DISPATCH_YAML_PARTS = ("nWave", "dispatch", "atdd_pure.yaml")
_VENDORS_YAML_PARTS = ("nWave", "dispatch", "vendors.yaml")


def _dispatch_argv(*args: str) -> list[str]:
    return ["dispatch", *args]


def _run(*args: str, cwd: Path | None = None) -> tuple[int, str, str]:
    """Drive the real `des dispatch` public CLI edge in-process."""
    return run_cli_in_process(_dispatch_argv(*args), cwd=cwd or _REPO_ROOT)


def _seed_ssot(root: Path) -> None:
    """Copy the real dispatch SSOT (atdd_pure.yaml + vendors.yaml) under a
    throwaway ROOT, so a DELIVER-test-executing invocation can reach prompt
    render without touching the real checkout tree -- the ROOT under test IS
    the locator's `--repo-root`, never a second, drifting fixture root."""
    for parts in (_DISPATCH_YAML_PARTS, _VENDORS_YAML_PARTS):
        src = _REPO_ROOT.joinpath(*parts)
        dst = root.joinpath(*parts)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


# The real, checked-in DeliveryContract fixture this AT proves the locator
# against -- read from disk, NEVER embedded as a dict literal in this test's
# own source. Embedding it here would make the fixture's `acceptance-tests.
# digest` field a hash of a file that contains that same hash: an
# unsatisfiable self-reference. Loading it keeps the digest cycle broken
# cleanly: the JSON fixture names this test file's digest; this test file
# never names the JSON fixture's digest back.
_DELIVERY_CONTRACT_FIXTURE = (
    _REPO_ROOT / "docs" / "delivery-contracts" / "retarget-des-dispatch-contract.json"
)


def _load_valid_contract() -> dict:
    return json.loads(_DELIVERY_CONTRACT_FIXTURE.read_text(encoding="utf-8"))


def _seed_valid_contract(
    root: Path,
    rel_path: str = "delivery-contract.json",
    *,
    delivery_route: str = "RED_TO_GREEN",
) -> Path:
    contract = _load_valid_contract()
    contract["delivery-route"] = delivery_route
    dst = root / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(contract), encoding="utf-8")
    return dst


_DELIVER_ARGS = (
    "--mode",
    "atdd_pure",
    "--project-id",
    "demo",
    "--slice",
    "slice-01",
    "--phase",
    "A_GREEN",
)


# ---------------------------------------------------------------------------
# 1. --help discoverability
# ---------------------------------------------------------------------------


def test_help_names_repo_root_and_delivery_contract_pairing() -> None:
    exit_code, out, err = _run("--help")
    text = out + err
    assert exit_code == 0
    assert "--repo-root" in text
    assert "--delivery-contract" in text, (
        "`--delivery-contract` must be a discoverable public flag -- "
        f"help text=\n{text}"
    )
    assert "relative" in text.lower(), (
        "help text must make repository-relative PATH resolution "
        f"discoverable -- text=\n{text}"
    )


# ---------------------------------------------------------------------------
# 2. Missing pair refuses before any prompt, no feature-delta suggestion
# ---------------------------------------------------------------------------


def test_missing_repo_root_refuses_before_prompt(tmp_path: Path) -> None:
    _seed_ssot(tmp_path)
    contract = _seed_valid_contract(tmp_path)
    exit_code, out, err = _run(
        *_DELIVER_ARGS, "--delivery-contract", str(contract.name)
    )
    assert exit_code != 0
    assert out == "", f"no prompt may be rendered before refusal; stdout={out!r}"
    text = err.lower()
    assert "repo-root" in text or "repo_root" in text
    assert "why" in text or "must" in text
    assert "feature-delta" not in text


def test_missing_delivery_contract_refuses_before_prompt(tmp_path: Path) -> None:
    _seed_ssot(tmp_path)
    exit_code, out, err = _run(*_DELIVER_ARGS, "--repo-root", str(tmp_path))
    assert exit_code != 0
    assert out == "", f"no prompt may be rendered before refusal; stdout={out!r}"
    text = err.lower()
    assert "delivery-contract" in text or "delivery_contract" in text
    assert "feature-delta" not in text


# ---------------------------------------------------------------------------
# 3. Valid pair succeeds, renders contract facts, never cites feature-delta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("delivery_route", ["RED_TO_GREEN", "GREEN_TO_GREEN"])
def test_valid_pair_renders_contract_facts_never_feature_delta(
    tmp_path: Path,
    delivery_route: str,
) -> None:
    _seed_ssot(tmp_path)
    contract = _seed_valid_contract(tmp_path, delivery_route=delivery_route)
    exit_code, out, err = _run(
        *_DELIVER_ARGS,
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        str(contract.name),
    )
    assert exit_code == 0, f"stdout={out!r} stderr={err!r}"
    assert "retarget-des-dispatch-contract" in out, (
        "the rendered prompt must carry a contract-derived observable fact "
        f"(delivery-id); prompt=\n{out}"
    )
    assert f"Delivery-route: {delivery_route}" in out, (
        f"route projection missing; prompt=\n{out}"
    )
    assert "feature-delta" not in out.lower()
    assert "design reference" not in out.lower()


# ---------------------------------------------------------------------------
# 4. Unsafe / invalid path domain refuses before prompt (examples + property)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "",
        "/etc/passwd",
        "../outside.json",
        "a/../../escape.json",
        "a\\b.json",
        "C:\\contract.json",
        "*.json",
        "contract.json?",
    ],
)
def test_unsafe_delivery_contract_path_refuses_before_prompt(
    tmp_path: Path, unsafe_path: str
) -> None:
    _seed_ssot(tmp_path)
    exit_code, out, err = _run(
        *_DELIVER_ARGS,
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        unsafe_path,
    )
    assert exit_code != 0, f"unsafe path {unsafe_path!r} must refuse"
    assert out == ""
    assert "feature-delta" not in err.lower()


_SAFE_ALNUM = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


@st.composite
def _unsafe_delivery_contract_paths(draw: st.DrawFn) -> str:
    """Bounded-arity strategy: an arbitrary safe alphanumeric prefix/suffix
    wrapping exactly one structurally unsafe form -- an absolute leading
    slash, a `/../` traversal segment, a backslash, or a `*`/`?` glob
    token. Every generated value is structurally unsafe by construction,
    never merely unlucky text."""
    prefix = draw(st.text(alphabet=_SAFE_ALNUM, max_size=6))
    suffix = draw(st.text(alphabet=_SAFE_ALNUM, max_size=6))
    shape = draw(st.sampled_from(["leading-slash", "traversal", "backslash", "glob"]))
    if shape == "leading-slash":
        return f"/{prefix}{suffix}"
    if shape == "traversal":
        return f"{prefix}/../{suffix}"
    if shape == "backslash":
        return f"{prefix}\\{suffix}"
    glob_token = draw(st.sampled_from(["*", "?"]))
    return f"{prefix}{glob_token}{suffix}"


@settings(
    deadline=None,
    max_examples=25,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(unsafe_path=_unsafe_delivery_contract_paths())
def test_property_unsafe_path_shapes_always_refuse(
    tmp_path_factory: pytest.TempPathFactory, unsafe_path: str
) -> None:
    """Bounded BROAD_INPUT_DOMAIN property: any safe-alnum-wrapped
    leading-slash / traversal / backslash / glob form is refused before any
    file access or prompt render -- never accepted as a resolvable PATH."""
    root = tmp_path_factory.mktemp("root")
    _seed_ssot(root)
    exit_code, out, _err = _run(
        *_DELIVER_ARGS,
        "--repo-root",
        str(root),
        "--delivery-contract",
        unsafe_path,
    )
    assert exit_code != 0
    assert out == ""


# ---------------------------------------------------------------------------
# 4b. Malformed JSON / schema-invalid / missing / non-regular refuse before
#     prompt render -- SAFE paths (pass the 4a locator check) that fail at
#     the later content/schema validation stage, a distinct code path from
#     the unsafe-path-segment domain above.
# ---------------------------------------------------------------------------


# Opaque, keyword-free relative names (never containing "json", "schema",
# "regular", "exist" or "missing") -- argparse's own error text ECHOES back
# the literal `--delivery-contract` value verbatim, so a filename that
# happens to spell a diagnostic keyword would let today's plain "unrecognized
# arguments" rejection satisfy `expected_keyword in err` for the wrong
# reason (the flag not existing yet), never the intended content/schema
# diagnostic. An opaque name closes that loophole cleanly.
def _write_malformed_json(root: Path) -> str:
    rel_path = "alpha-artifact"
    (root / rel_path).write_text("{not valid content", encoding="utf-8")
    return rel_path


def _write_schema_invalid_json(root: Path) -> str:
    rel_path = "beta-artifact"
    invalid = _load_valid_contract()
    del invalid["obligations"]  # required field, per thin-delivery-contract schema
    (root / rel_path).write_text(json.dumps(invalid), encoding="utf-8")
    return rel_path


def _write_non_regular_path(root: Path) -> str:
    rel_path = "gamma-artifact"
    (root / rel_path).mkdir(parents=True, exist_ok=True)
    return rel_path


def _write_missing_path(root: Path) -> str:
    return "delta-artifact"


@pytest.mark.parametrize(
    "setup_fn,case_name,expected_keyword",
    [
        (_write_malformed_json, "malformed-json", "json"),
        (_write_schema_invalid_json, "schema-invalid-json", "schema"),
        (_write_non_regular_path, "non-regular-file", "regular"),
        (_write_missing_path, "missing-file", "exist"),
    ],
)
def test_malformed_non_regular_or_missing_contract_refuses_before_prompt(
    tmp_path: Path,
    setup_fn: object,
    case_name: str,
    expected_keyword: str,
) -> None:
    _seed_ssot(tmp_path)
    rel_path = setup_fn(tmp_path)  # type: ignore[operator]
    exit_code, out, err = _run(
        *_DELIVER_ARGS,
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        rel_path,
    )
    assert exit_code != 0, f"{case_name} must refuse; stdout={out!r} stderr={err!r}"
    assert out == "", f"{case_name}: no prompt may be rendered before refusal"
    assert "feature-delta" not in err.lower(), (
        f"{case_name}: refusal must never suggest feature-delta"
    )
    assert expected_keyword in err.lower(), (
        f"{case_name}: refusal must name WHAT failed (expected keyword "
        f"{expected_keyword!r} in stderr); stderr={err!r}"
    )


# ---------------------------------------------------------------------------
# 5. A conflicting feature-delta beside a valid contract never influences output
# ---------------------------------------------------------------------------


def test_conflicting_feature_delta_does_not_influence_output(tmp_path: Path) -> None:
    _seed_ssot(tmp_path)
    contract = _seed_valid_contract(tmp_path)
    delta_dir = tmp_path / "docs" / "feature" / "demo"
    delta_dir.mkdir(parents=True, exist_ok=True)
    (delta_dir / "feature-delta.md").write_text(
        "## Wave: DESIGN\nConflicting legacy design reference.\n", encoding="utf-8"
    )
    exit_code, out, err = _run(
        *_DELIVER_ARGS,
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        str(contract.name),
    )
    assert exit_code == 0, f"stdout={out!r} stderr={err!r}"
    assert "retarget-des-dispatch-contract" in out
    assert "feature-delta" not in out.lower()
    assert "feature-delta" not in err.lower()
    assert "conflicting legacy design reference" not in out.lower()


# ---------------------------------------------------------------------------
# 6. Authoring-wave dispatch stays usable without any contract, no fabrication
# ---------------------------------------------------------------------------


def test_authoring_wave_dispatch_succeeds_without_contract(tmp_path: Path) -> None:
    _seed_ssot(tmp_path)
    exit_code, out, err = _run(
        "--mode",
        "atdd_pure",
        "--project-id",
        "demo",
        "--slice",
        "slice-01",
        "--wave",
        "discuss",
        "--repo-root",
        str(tmp_path),
    )
    assert exit_code == 0, f"stdout={out!r} stderr={err!r}"
    assert "retarget-des-dispatch-contract" not in out, (
        "an authoring-wave dispatch with no --delivery-contract must never "
        f"fabricate contract facts; prompt=\n{out}"
    )

"""Shared ThinDeliveryContract test fixture helpers (ADR-SSOT-002 S4a).

Every DELIVER-test-executing `des dispatch` now REQUIRES an explicit
`--repo-root <ROOT>` + `--delivery-contract <PATH>` pair, `PATH` resolved
ONLY against `ROOT` (`src/des/cli/dispatch.py::_load_delivery_contract`).
This module is the ONE place every test module reaches for that pair,
mirroring the pattern `test_des_dispatch_generator.py` established first
(commit `36f96207b`) -- never a second, drifting hand-authored contract
literal per test file.

The real, checked-in, schema-valid ThinDeliveryContract fixture
(`docs/delivery-contracts/retarget-des-dispatch-contract.json`) is reused
verbatim; this module never embeds a contract dict literal.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DELIVERY_CONTRACT_FIXTURE_REL = (
    "docs/delivery-contracts/fix-language-agnostic-contract-paths.json"
)
_DELIVERY_CONTRACT_FIXTURE = _REPO_ROOT / _DELIVERY_CONTRACT_FIXTURE_REL
_DISPATCH_YAML_PARTS = ("nWave", "dispatch", "atdd_pure.yaml")
_VENDORS_YAML_PARTS = ("nWave", "dispatch", "vendors.yaml")
_DELIVERY_CONTRACT_SCHEMA_PARTS = ("schemas", "thin-delivery-contract.schema.json")
_DELIVERY_CONTRACT_SCHEMA_FIXTURE = _REPO_ROOT.joinpath(
    "nWave", *_DELIVERY_CONTRACT_SCHEMA_PARTS
)


def load_valid_contract() -> dict:
    """Parse the real checked-in ThinDeliveryContract fixture."""
    return json.loads(_DELIVERY_CONTRACT_FIXTURE.read_text(encoding="utf-8"))


#: `des dispatch`'s oracle red-reason probe (`des.cli.
#: _oracle_red_reason_refusal`) is never switchable off (GDP-7): it always
#: executes `verification-scope.commands` for real. The real, checked-in
#: `acceptance-tests.locator` this fixture names
#: (`tests/build/test_thin_delivery_contract_schema.py`) is a genuine,
#: already-passing schema test -- correct in the real repo, but GREEN at
#: base is exactly the defect that probe refuses for a RED_TO_GREEN route.
#: `seed_referenced_oracle` therefore writes this synthetic body instead of
#: copying the real file's bytes: a plain `AssertionError` needs no
#: declared-symbol correlation and is always an acceptable RED reason,
#: regardless of route (`GREEN_TO_GREEN` does not require GREEN either --
#: this probe only refuses GREEN under `RED_TO_GREEN`). This never touches
#: the real file in the actual checkout; only the copy under a test's own
#: `tmp_path`.
_SYNTHETIC_RED_ORACLE_SOURCE = (
    "def test_it_awaits_the_missing_feature() -> None:\n"
    '    """Deliberately RED: this shared dispatch-test fixture\'s oracle\n'
    "    stays a genuine RED-for-the-right-reason under the always-on\n"
    '    oracle red-reason probe."""\n'
    '    assert False, "fixture oracle: intentionally not implemented"\n'
)


def seed_referenced_oracle(root: Path, contract: dict) -> Path:
    """Materialize a genuinely RED-for-the-right-reason oracle body at
    `contract["acceptance-tests"]["locator"]`, under `root`, so a tmp
    `--repo-root` can resolve the oracle `dispatch._resolve_oracle` reads,
    without embedding a second oracle fixture. The locator itself never
    changes with route/examine, so this is safe to call before or after
    those fields are overridden. The written bytes are synthetic
    (`_SYNTHETIC_RED_ORACLE_SOURCE`), not a copy of the real file's bytes --
    see that constant's own comment for why."""
    locator = str(contract["acceptance-tests"]["locator"])
    dst = root / locator
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(_SYNTHETIC_RED_ORACLE_SOURCE, encoding="utf-8")
    return dst


def seed_delivery_contract(
    root: Path,
    rel_path: str = "delivery-contract.json",
    *,
    route: str = "RED_TO_GREEN",
    examine: bool = False,
) -> str:
    """Write the real ThinDeliveryContract fixture under `root`, with its
    top-level `delivery-route` set explicitly to `route` and
    `applicability.examine` set explicitly to `examine`, and return its
    ROOT-relative PATH -- for a test driving an isolated `--repo-root` (a
    tmp workspace), which cannot resolve a PATH relative to the real
    checkout root. Parses and re-serializes the fixture (rather than a raw
    byte copy) so `route` and `examine` always land in the written contract
    instead of silently reusing whatever the checked-in fixture happens to
    contain. Also materializes the fixture's referenced oracle under `root`,
    since dispatch resolves `acceptance-tests.locator` against `root` too."""
    dst = root / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    contract = load_valid_contract()
    contract["delivery-route"] = route
    contract["applicability"]["examine"] = examine
    seed_referenced_oracle(root, contract)
    dst.write_text(json.dumps(contract), encoding="utf-8")
    return rel_path


def contract_args(
    root: Path, *, seed: bool = True, examine: bool = False
) -> tuple[str, str, str, str]:
    """The `--repo-root <root> --delivery-contract <PATH>` pair a test-
    running dispatch against `root` now requires. `seed=True` (the default)
    copies the fixture under `root` first, for an isolated tmp workspace;
    `seed=False` reuses the real checked-in fixture in place, for a dispatch
    driven against the real checkout root (`_REPO_ROOT`) -- never a second
    copy of a file already on disk there. `examine` (default False) sets the
    contract's `applicability.examine` axis -- passed through to seed_delivery_contract."""
    rel_path = (
        seed_delivery_contract(root, examine=examine)
        if seed
        else _DELIVERY_CONTRACT_FIXTURE_REL
    )
    return ("--repo-root", str(root), "--delivery-contract", rel_path)


def seed_delivery_contract_schema_only(installed_dispatch_assets_dir: Path) -> None:
    """Copy ONLY the thin-delivery-contract JSON-schema next to a monkeypatched
    ``_INSTALLED_DISPATCH_ASSETS_DIR`` -- for a test that must keep the
    contract-SCHEMA axis resolvable (``_load_delivery_contract`` reads it via
    ``_INSTALLED_DISPATCH_ASSETS_DIR.parent``, unconditionally, before the
    dispatch-SSOT resolution the test is actually probing) while leaving the
    dispatch SSOT itself (``atdd_pure.yaml``) genuinely absent under that same
    directory -- so a --delivery-contract load never masks the SSOT-absent
    refusal a negative-SSOT-axis test targets."""
    dst = installed_dispatch_assets_dir.parent.joinpath(
        *_DELIVERY_CONTRACT_SCHEMA_PARTS
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_DELIVERY_CONTRACT_SCHEMA_FIXTURE, dst)


def seed_dispatch_ssot(root: Path) -> None:
    """Copy the real dispatch SSOT (atdd_pure.yaml + vendors.yaml) under a
    throwaway ROOT, so a DELIVER-test-executing invocation can reach prompt
    render without touching the real checkout tree -- the ROOT under test IS
    the locator's `--repo-root`, never a second, drifting fixture root."""
    for parts in (_DISPATCH_YAML_PARTS, _VENDORS_YAML_PARTS):
        src = _REPO_ROOT.joinpath(*parts)
        dst = root.joinpath(*parts)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

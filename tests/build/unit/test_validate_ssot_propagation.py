"""Unit tests for `scripts/validation/validate_ssot_propagation.py` (R3).

Per Recommendation 3 (lean-wave doc audit, 2026-04-28). The validator
warns when a PR modifies `docs/feature/{id}/feature-delta.md` without a
paired modification under `docs/product/` (SSOT back-propagation
contract). Soft-warn during rollout — promote to hard fail via
`--strict` after one stable release.
"""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path

import pytest


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    target = repo_root / "scripts" / "validation" / "validate_ssot_propagation.py"
    spec = importlib.util.spec_from_file_location("validate_ssot_propagation", target)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def vsp():
    return _load_module()


def test_feature_delta_paired_with_ssot_no_warning(vsp) -> None:
    """A diff that touches both feature-delta.md AND docs/product/ is clean."""
    paths = [
        "docs/feature/alpha/feature-delta.md",
        "docs/product/architecture/brief.md",
    ]
    result = vsp.validate_ssot_propagation(paths)
    assert result.has_warnings is False
    assert result.feature_delta_count == 1
    assert result.ssot_modified is True


def test_feature_delta_alone_warns(vsp) -> None:
    """A diff that only modifies feature-delta.md (no SSOT) emits a warning."""
    paths = ["docs/feature/beta/feature-delta.md"]
    result = vsp.validate_ssot_propagation(paths)
    assert result.has_warnings is True
    assert len(result.warnings) == 1
    warning = result.warnings[0]
    assert warning.feature_id == "beta"
    assert warning.feature_delta_path == "docs/feature/beta/feature-delta.md"
    # Contract: the warning enumerates expected SSOT write targets.
    assert "docs/product/architecture/brief.md" in warning.expected_ssot_paths


def test_no_feature_delta_no_warning(vsp) -> None:
    """A diff with no feature-delta.md modification cannot violate the contract."""
    paths = [
        "src/des/application/orchestrator.py",
        "tests/des/unit/test_x.py",
    ]
    result = vsp.validate_ssot_propagation(paths)
    assert result.has_warnings is False
    assert result.feature_delta_count == 0


def test_main_soft_exit_zero_on_warning(vsp, monkeypatch) -> None:
    """Default (non-strict) main() exits 0 even on warnings (rollout window)."""
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO("docs/feature/gamma/feature-delta.md\n"),
    )
    rc = vsp.main([])
    assert rc == 0


def test_main_strict_exit_one_on_warning(vsp, monkeypatch) -> None:
    """`--strict` main() exits 1 when the contract is violated."""
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO("docs/feature/delta/feature-delta.md\n"),
    )
    rc = vsp.main(["--strict"])
    assert rc == 1

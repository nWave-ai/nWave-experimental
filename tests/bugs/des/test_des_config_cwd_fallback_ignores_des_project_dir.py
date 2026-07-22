"""Regression AT -- `DESConfig.__init__`'s cwd fallback ignores the per-test
`.nwave` ROOT isolation override (`DES_PROJECT_DIR` / `resolve_nwave_root()`).

Site under test (`src/des/adapters/driven/config/des_config.py:77`, inside
`DESConfig.__init__`):

    if config_path is None:
        effective_cwd = cwd or Path.cwd()
        config_path = effective_cwd / ".nwave" / "des-config.json"

Reached ONLY when BOTH constructor params (`config_path`, `cwd`) are omitted
-- exactly the shape `DESConfig()` (bare) is called with across the codebase
(e.g. inline construction sites that do not thread an explicit root). The
fallback reads bare `Path.cwd()` instead of consulting the isolation resolver
`des.domain.nwave_root.resolve_nwave_root()` (DDD-14/15), which prefers
`DES_PROJECT_DIR` when set. A test (or a real per-project isolation caller)
that sets `DES_PROJECT_DIR` to redirect config resolution away from the
shared process cwd is silently ignored by this call site -- it reads whatever
`.nwave/des-config.json` sits at the ACTUAL process cwd instead.

DISCRIMINATING ARRANGEMENT (cwd != DES_PROJECT_DIR, the only way to tell the
two reads apart): two real tmp roots, each carrying a `.nwave/des-config.json`
with a DIFFERENT `audit_logging_enabled` value (`False` at the isolated root,
`True` at the shared cwd root -- deliberately the NON-default value at the
isolated root so a read that silently falls through to the built-in default
cannot masquerade as "isolation honoured").

RED before the fix: `DESConfig()` reads the shared cwd's config
(`audit_logging_enabled=True`) via bare `Path.cwd()`. GREEN after: it reads
the isolated root's config (`audit_logging_enabled=False`) via
`resolve_nwave_root()`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.adapters.driven.config.des_config import DESConfig


def _write_des_config(root: Path, data: dict[str, object]) -> None:
    config_dir = root / ".nwave"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "des-config.json").write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.negative_at
def test_des_config_default_cwd_resolution_ignores_des_project_dir_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`DESConfig()` (both `config_path` and `cwd` omitted) must honour
    `DES_PROJECT_DIR`, not bare `Path.cwd()`.

    See the module docstring for the full discriminating arrangement.
    """
    shared_cwd_root = tmp_path / "shared_repo_cwd"
    isolated_root = tmp_path / "isolated_des_project_dir"
    shared_cwd_root.mkdir()
    isolated_root.mkdir()

    _write_des_config(isolated_root, {"audit_logging_enabled": False})
    _write_des_config(shared_cwd_root, {"audit_logging_enabled": True})

    monkeypatch.delenv("DES_AUDIT_LOGGING_ENABLED", raising=False)
    monkeypatch.setenv("DES_PROJECT_DIR", str(isolated_root))
    monkeypatch.chdir(shared_cwd_root)

    # Explicit (unused) global_config_path keeps this hermetic against the
    # real machine's ~/.nwave/global-config.json -- audit_logging_enabled
    # only ever reads the PROJECT config, so this has no bearing on the
    # assertion below, only on test isolation.
    config = DESConfig(global_config_path=isolated_root / "unused-global.json")

    assert config.audit_logging_enabled is False, (
        "DESConfig()'s default cwd resolution (des_config.py:77, "
        "`effective_cwd = cwd or Path.cwd()`) must honour DES_PROJECT_DIR via "
        "resolve_nwave_root() -- the isolated root's "
        ".nwave/des-config.json declares audit_logging_enabled=False. "
        f"Observed audit_logging_enabled={config.audit_logging_enabled!r}: the "
        "constructor read the SHARED cwd's config (audit_logging_enabled=True) "
        "via bare Path.cwd() instead of the isolated DES_PROJECT_DIR root."
    )


def test_des_config_default_cwd_resolution_reads_cwd_when_des_project_dir_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With `DES_PROJECT_DIR` explicitly UNSET, `DESConfig()` must keep
    resolving against `Path.cwd()` exactly as it does today (non-regression
    pin for the fix that wires site 1 through `resolve_nwave_root()` --
    which falls back to `Path.cwd()` on an unset override, so this behaviour
    must be unchanged before and after)."""
    project_root = tmp_path / "unset_cwd_project"
    project_root.mkdir()
    _write_des_config(project_root, {"audit_logging_enabled": False})

    monkeypatch.delenv("DES_AUDIT_LOGGING_ENABLED", raising=False)
    monkeypatch.delenv("DES_PROJECT_DIR", raising=False)
    monkeypatch.chdir(project_root)

    config = DESConfig(global_config_path=project_root / "unused-global.json")

    assert config.audit_logging_enabled is False, (
        "with DES_PROJECT_DIR unset, DESConfig() must still resolve its "
        f"config off Path.cwd(); observed audit_logging_enabled="
        f"{config.audit_logging_enabled!r}, expected False (the cwd project's "
        "declared value)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

"""Regression AT -- `AuditLogPathResolver.resolve`'s cwd fallback ignores the
per-test `.nwave` ROOT isolation override (`DES_PROJECT_DIR` /
`resolve_nwave_root()`, `src/des/domain/nwave_root.py`).

Site under test (`src/des/domain/audit_log_path_resolver.py:55`, inside
`AuditLogPathResolver.resolve`):

    effective_cwd = self._cwd or Path.cwd()

Reached ONLY on Priority-4 resolution: no explicit `log_dir` constructor
param, no `DES_AUDIT_LOG_DIR` env var, no explicit `cwd` constructor param,
and no `audit_log_dir` key in `.nwave/des-config.json` at the resolved root
(so Priority 3 -- the config-file read, which itself ALSO uses
`effective_cwd` -- falls through empty). At Priority 4 the resolver returns
`effective_cwd / ".nwave" / "des" / "logs"`, reading bare `Path.cwd()`
instead of consulting the isolation resolver. A test relying on
`DES_PROJECT_DIR` to keep its audit-log writes private is silently redirected
to the shared process cwd's `.nwave/des/logs`.

DISCRIMINATING ARRANGEMENT (cwd != DES_PROJECT_DIR, the only way to tell the
two reads apart): two real, distinct tmp roots -- neither carries a
`.nwave/des-config.json` (so Priority 3 is inert at both, isolating the
assertion to the Priority-4 fallback under test).

RED before the fix: `resolve()` returns `shared_cwd_root/.nwave/des/logs`
(bare `Path.cwd()`). GREEN after: it returns
`isolated_root/.nwave/des/logs` (`resolve_nwave_root()`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.domain.audit_log_path_resolver import AuditLogPathResolver


@pytest.mark.negative_at
def test_audit_log_path_resolver_cwd_fallback_ignores_des_project_dir_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared_cwd_root = tmp_path / "shared_repo_cwd"
    isolated_root = tmp_path / "isolated_des_project_dir"
    shared_cwd_root.mkdir()
    isolated_root.mkdir()

    monkeypatch.delenv("DES_AUDIT_LOG_DIR", raising=False)
    monkeypatch.setenv("DES_PROJECT_DIR", str(isolated_root))
    monkeypatch.chdir(shared_cwd_root)

    resolved = AuditLogPathResolver().resolve()

    expected = isolated_root / ".nwave" / "des" / "logs"
    assert resolved == expected, (
        "AuditLogPathResolver.resolve()'s Priority-4 cwd fallback "
        "(audit_log_path_resolver.py:55, `effective_cwd = self._cwd or "
        "Path.cwd()`) must honour DES_PROJECT_DIR via resolve_nwave_root() "
        f"when both log_dir and cwd are omitted. Observed {resolved}, expected "
        f"{expected} -- the resolver read bare Path.cwd() (the shared root) "
        "instead of the isolated DES_PROJECT_DIR root."
    )


def test_audit_log_path_resolver_cwd_fallback_reads_cwd_when_des_project_dir_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "unset_cwd_project"
    project_root.mkdir()

    monkeypatch.delenv("DES_AUDIT_LOG_DIR", raising=False)
    monkeypatch.delenv("DES_PROJECT_DIR", raising=False)
    monkeypatch.chdir(project_root)

    resolved = AuditLogPathResolver().resolve()

    expected = project_root / ".nwave" / "des" / "logs"
    assert resolved == expected, (
        "with DES_PROJECT_DIR unset, AuditLogPathResolver.resolve() must "
        f"still resolve off Path.cwd(); observed {resolved}, expected "
        f"{expected}."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

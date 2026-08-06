"""Regression AT -- the DISCUSS gate-IN precondition read must honour the
per-test `.nwave` isolation override (`DES_PROJECT_DIR` / `resolve_nwave_root()`),
not the shared process `Path.cwd()`.

Sibling to `test_xdist_group_real_repo_scan_swallows_the_suite.py::(b)`, which
guards the SAME isolation property for the OTHER production call site --
`PreToolUseService._read_active_wave()` (the wave-active floor read, line ~513,
wired through `resolve_nwave_root()` by commit b9d77820c). This file guards the
SECOND, residual call site that the same commit left on bare `Path.cwd()`:

    `PreToolUseService._discuss_gate_in_invoker()` reads the product-SSOT
    presence via `self._product_ssot_reader.ssot_present(Path.cwd())`
    (`src/des/application/pre_tool_use_service.py:430`).

Both call sites feed the same `real_repo_scan`-serialized floor: a test that
relies on `DES_PROJECT_DIR` per-test isolation (rather than serialization) to
keep its `.nwave` / `docs/product/` state private is silently read against the
SHARED repo checkout whenever a production reader consults `Path.cwd()` directly.
The shared checkout IS a real nWave repo with a complete `docs/product/`, so the
gate-IN would read a fabricated "SSOT present" for a project whose isolated root
has NO such state -- an order-independent false PASS. Narrowing the
serialization lane (commit b9d77820c) is only safe once EVERY production reader
of shared `.nwave`-adjacent state honours the isolation override; this test pins
the discuss gate-IN reader as one of them.

DISCRIMINATING ARRANGEMENT (cwd != DES_PROJECT_DIR, the only way to tell the two
reads apart):

  * `isolated_root`  (DES_PROJECT_DIR): a `discuss` wave floor is armed here
    (so `_read_active_wave()` -- already isolation-wired -- sources
    `markers.wave == "discuss"` and the gate-IN branch fires) AND
    `docs/product/` is INCOMPLETE (vision + backlog + glossary present, the
    `jobs.yaml` registry ABSENT) -> `DiscussGateIn.evaluate` -> MISSING_SSOT
    -> a named-LOUD VETO (block).
  * `shared_cwd_root` (Path.cwd()): `docs/product/` is COMPLETE (all four
    required docs) -> if the gate-IN read cwd instead, `DiscussGateIn.evaluate`
    -> PASS -> no objection -> the dispatch is ALLOWED.

The dispatch prompt is deliberately markerless: `markers.wave` is sourced from
the armed floor (never the prompt), so a markerless entering dispatch reaches
the gate-IN branch and, on a gate-IN PASS, falls through to the S1 allow.

RED before the fix: the gate-IN reads the COMPLETE `shared_cwd_root` SSOT via
`Path.cwd()` -> PASS -> ALLOW. GREEN after: it reads the INCOMPLETE
`isolated_root` SSOT via `resolve_nwave_root()` -> MISSING_SSOT -> BLOCK.

This test does not drive a `cwd=<real repo>` subprocess (it drives the
application service in-process and only `chdir`s), so it is not itself pinned to
the `real_repo_scan` group.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.adapters.driven.filesystem.product_ssot_filesystem_reader import (
    ProductSsotFilesystemReader,
)
from des.adapters.driven.filesystem.wave_active_filesystem_store import (
    WaveActiveFilesystemStore,
)
from des.adapters.driven.logging.null_audit_log_writer import NullAuditLogWriter
from des.adapters.driven.time.system_time import SystemTimeProvider
from des.application.pre_tool_use_service import PreToolUseService
from des.domain.des_marker_parser import DesMarkerParser
from des.domain.wave_active import WaveActiveRecord, WaveProvenance
from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput


_SSOT_MD_DOCS: tuple[str, ...] = ("vision.md", "backlog.md", "glossary.md")
_JOBS_DOC = "jobs.yaml"


def _write_product_docs(root: Path, docs: tuple[str, ...]) -> None:
    product_dir = root / "docs" / "product"
    product_dir.mkdir(parents=True, exist_ok=True)
    for doc in docs:
        (product_dir / doc).write_text(f"# {doc}\n", encoding="utf-8")


@pytest.mark.negative_at
def test_discuss_gate_in_reads_isolated_root_not_shared_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The discuss gate-IN precondition read must honour `DES_PROJECT_DIR`.

    See the module docstring for the full discriminating arrangement. If the
    gate-IN reads bare `Path.cwd()` (the shared checkout, complete SSOT) it
    ALLOWS; honouring the isolation override it reads the isolated root's
    INCOMPLETE SSOT and BLOCKS.
    """
    shared_cwd_root = tmp_path / "shared_repo_cwd"
    isolated_root = tmp_path / "isolated_des_project_dir"
    shared_cwd_root.mkdir()
    isolated_root.mkdir()

    # shared_cwd_root: a COMPLETE product SSOT (the shape the real repo checkout
    # carries). A gate-IN that reads cwd here would find no missing doc -> PASS.
    _write_product_docs(shared_cwd_root, (*_SSOT_MD_DOCS, _JOBS_DOC))
    # isolated_root: an INCOMPLETE product SSOT (jobs.yaml absent) -> MISSING_SSOT.
    _write_product_docs(isolated_root, _SSOT_MD_DOCS)

    # Arm a discuss wave floor at the ISOLATED root so `_read_active_wave()`
    # (already isolation-wired via resolve_nwave_root) sources
    # `markers.wave == "discuss"` and the gate-IN branch fires.
    WaveActiveFilesystemStore().arm(
        isolated_root,
        WaveActiveRecord(
            wave="discuss", provenance=WaveProvenance.COMMAND, entry_pending=True
        ),
    )

    monkeypatch.setenv("DES_PROJECT_DIR", str(isolated_root))
    monkeypatch.chdir(shared_cwd_root)

    service = PreToolUseService(
        marker_parser=DesMarkerParser(),
        audit_writer=NullAuditLogWriter(),
        time_provider=SystemTimeProvider(),
        wave_active_reader=WaveActiveFilesystemStore(),
        product_ssot_reader=ProductSsotFilesystemReader(),
    )
    decision = service.validate(
        PreToolUseInput(
            prompt="begin the discuss wave",
            subagent_type="child",
            wave_entering=True,
        )
    )

    assert decision.action == "block", (
        "the DISCUSS gate-IN must read the product-SSOT presence from the "
        "isolated per-test root (DES_PROJECT_DIR / resolve_nwave_root), where "
        "the SSOT is INCOMPLETE (jobs.yaml absent -> MISSING_SSOT) -> a VETO "
        f"block. Observed action={decision.action!r} reason={decision.reason!r}: "
        "the gate-IN read the COMPLETE shared-cwd SSOT instead, proving "
        "`_discuss_gate_in_invoker()` still calls bare `Path.cwd()` "
        "(pre_tool_use_service.py:430) rather than the isolation-aware resolver. "
        "Until this call site honours DES_PROJECT_DIR, narrowing the "
        "`real_repo_scan` serialization lane re-opens cross-test docs/product "
        "state bleed (see the sibling floor-read guard)."
    )
    reason = (decision.reason or "").lower()
    assert "ssot" in reason, (
        "the gate-IN block must NAME the unmet product-SSOT precondition so it "
        f"surfaces as a loud, attributable veto; got reason={decision.reason!r}"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

#!/usr/bin/env python3
"""Guarded invocation of the harness-neutral declare-done pre-push backstop.

fix-pre-push-hook-dual-installer-collision (slice-01): folds the DES
declare-done backstop into `.pre-commit-config.yaml` as a `local` hook
(`stages: [pre-push]`), replacing `DESPlugin._install_git_pre_push_backstop`'s
now-retired wrapper-chaining install. RCA:
docs/analysis/root-cause-analysis-pre-push-hook-dual-installer-collision.md

Two independent installers used to each treat themselves as sole writer of
`.git/hooks/pre-push` -- `pre-commit install` (the SSOT-intended writer) and
the DES plugin's bespoke wrapper. `pre-commit install` is now the SOLE
writer: this hook fires the SAME backstop behavior FROM INSIDE the
pre-commit-managed hook body instead of a second file-write.

Target-machine independence: `des_declare_done_pre_push.py` is deployed to
the operator's installed path (`~/.claude/scripts/des_declare_done_pre_push.py`
via the DES plugin's `DES_HOOKS` list), not part of this repo's runtime. On a
machine where it is absent (e.g. nWave not installed there, or a bare clone
of this dev repo without running the installer), this guard degrades to a
no-op (exit 0) -- never a hard push failure.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """Pre-push entry point. Returns exit code for the shell."""
    argv = sys.argv[1:] if argv is None else argv
    script = Path.home() / ".claude" / "scripts" / "des_declare_done_pre_push.py"
    if not script.is_file():
        return 0
    spec = importlib.util.spec_from_file_location("des_declare_done_pre_push", script)
    if spec is None or spec.loader is None:
        return 0
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main(argv)


if __name__ == "__main__":
    sys.exit(main())

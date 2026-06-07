"""SubagentStop hook intercept for the robustness PBT-density gate.

Slice-05 wiring (feature-fix-robustness-pbt-density-gate, AT2). Registers as
a Claude Code ``SubagentStop`` hook: after a sub-agent dispatch completes,
this hook invokes ``scripts.cli.check_robustness_density`` against a
configured DISTILL-exit declaration + AT-scope. A non-zero gate exit
mechanically blocks the dispatch outcome by emitting a JSON decision payload
with ``"decision": "block"`` and exiting 2 (Claude Code's block signal). The
gate's stdout diagnostic token (e.g. ``RobustnessCoverageMiss``) is carried
verbatim in the ``reason`` field so the operator can identify WHY the
dispatch was blocked.

B4 invariant (feature-delta § 6 lines 443-449): "slice-05 AT2 MUST exercise
the real ``SubagentStop`` hook chain end-to-end against a real sub-agent
dispatch -- never a mocked dispatch." This hook is the gate's own
composition root in the hook chain; a registration that exists but never
executes is the fixture-only-wiring defect the gate exists to prevent.

Configuration (per ADR-030 hook-only OSS design; no native ``exit_gates``
YAML key):

  NWAVE_ROBUSTNESS_GATE_DECLARATION  -- path to unbounded-domains.yaml
  NWAVE_ROBUSTNESS_GATE_AT_SCOPE     -- path to staged AT-scope directory

When either env var is unset the hook is dormant and exits 0 (the hook
chain proceeds). The intercept fires only when an operator (or the
composition-root driver in the AT2 driving port) wires both env vars at the
DISTILL-exit boundary.

Invocable as ``python -m scripts.hooks.subagent_stop_robustness_gate`` (the
Claude Code hook command form). Stdlib-only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys


_ENV_DECLARATION = "NWAVE_ROBUSTNESS_GATE_DECLARATION"
_ENV_AT_SCOPE = "NWAVE_ROBUSTNESS_GATE_AT_SCOPE"
_ENV_REPO_ROOT = "NWAVE_ROBUSTNESS_GATE_REPO_ROOT"
_GATE_MODULE = "scripts.cli.check_robustness_density"


def _invoke_gate(declaration: str, at_scope: str, repo_root: str) -> tuple[int, str]:
    """Invoke ``check_robustness_density`` as a subprocess; return (rc, stdout)."""
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            _GATE_MODULE,
            "--declaration",
            declaration,
            "--at-scope",
            at_scope,
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode, completed.stdout or ""


def main() -> int:
    """Run the SubagentStop robustness gate intercept.

    Reads + ignores the JSON SubagentStop payload from stdin (Claude Code
    hook protocol). When configured (both env vars set), invokes the gate
    CLI; on non-zero exit emits a ``{"decision": "block", "reason": ...}``
    JSON payload on stdout and returns 2 (Claude Code's block signal). On
    zero exit (or when dormant) returns 0 (the hook chain proceeds).
    """
    # Drain stdin so the parent hook protocol does not block on a
    # never-read payload. The payload is informational; the intercept
    # decision is driven by the gate CLI exit code, not by payload shape.
    try:
        sys.stdin.read()
    except OSError:
        pass

    declaration = os.environ.get(_ENV_DECLARATION)
    at_scope = os.environ.get(_ENV_AT_SCOPE)
    if not declaration or not at_scope:
        return 0

    repo_root = os.environ.get(_ENV_REPO_ROOT) or os.getcwd()
    rc, gate_stdout = _invoke_gate(declaration, at_scope, repo_root)
    if rc == 0:
        return 0

    block_payload = {
        "decision": "block",
        "reason": gate_stdout,
    }
    sys.stdout.write(json.dumps(block_payload) + "\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

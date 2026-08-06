#!/usr/bin/env python3
"""Claude Code hook adapter — thin facade for backward compatibility.

This module is the installed entry point for DES hooks:
  python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter <command>

All handler logic lives in dedicated modules:
- pre_tool_use_handler.py  — PreToolUse (Task/Agent validation)
- subagent_stop_handler.py — SubagentStop (step completion validation)
- post_tool_use_handler.py — PostToolUse (failure notification injection)
- pre_write_handler.py     — PreWrite/PreEdit (session guard)
- subagent_start_handler.py — SubagentStart (agent lifecycle)

Routing lives in hook_router.py. This facade re-exports handler functions
so that existing test imports (``from ... import adapter; adapter.handle_*``)
continue to work.

Exit Codes:
  0 = allow/continue
  1 = fail-closed error (BLOCKS execution)
  2 = block/reject (validation failed)
"""

import sys
from pathlib import Path


# Add project root to sys.path for standalone script execution
if __name__ == "__main__":
    project_root = str(Path(__file__).resolve().parent.parent.parent.parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

# Re-export handler functions for backward compatibility with tests
from des.adapters.drivers.hooks.hook_router import main
from des.adapters.drivers.hooks.post_tool_use_handler import (  # noqa: F401
    handle_post_tool_use,
)
from des.adapters.drivers.hooks.pre_tool_use_handler import (  # noqa: F401
    handle_pre_tool_use,
)
from des.adapters.drivers.hooks.pre_write_handler import (  # noqa: F401
    handle_pre_write,
)

# Re-export service factory functions for test patching
from des.adapters.drivers.hooks.service_factory import (  # noqa: F401
    create_pre_tool_use_service,
    create_subagent_stop_service,
)
from des.adapters.drivers.hooks.subagent_start_handler import (  # noqa: F401
    handle_subagent_start,
)
from des.adapters.drivers.hooks.subagent_stop_handler import (  # noqa: F401
    extract_des_context_from_transcript,
    handle_subagent_stop,
)
from des.runtime.freshness import assert_fresh_or_explain


# Runtime freshness gate (DESIGN SYS-2 / Gap A): fire at the hook process startup
# as an import-time side effect, mirroring des.cli/__init__.py — before any
# handler logic runs. DV-2: the hook hot path passes suppress_git_autoskip=True so
# the content probe REACHES the verdict even on a developer checkout (the #58
# topology the coarse .git/-adjacency autoskip would otherwise neuter).
# Degrade-loud: a stale install warns + proceeds (exit 0); it never bricks a
# session.
assert_fresh_or_explain(suppress_git_autoskip=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Claude Code hook adapter — thin facade for backward compatibility.

This module is the installed entry point for DES hooks:
  python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter <command>

All handler logic lives in dedicated modules:
- pre_tool_use_handler.py  — PreToolUse (Task/Agent validation)
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
from des.adapters.drivers.hooks.pre_tool_use_handler import (  # noqa: F401
    handle_pre_tool_use,
)
from des.adapters.drivers.hooks.pre_write_handler import (  # noqa: F401
    handle_pre_write,
)
from des.adapters.drivers.hooks.subagent_start_handler import (  # noqa: F401
    handle_subagent_start,
)


if __name__ == "__main__":
    main()

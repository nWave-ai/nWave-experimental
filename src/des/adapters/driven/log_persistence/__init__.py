"""LogPersistencePort adapters — D4 Phase 3 slice-04 RED scaffold.

Per `docs/analysis/d4-schema-spec-2026-05-26.md` § 3.3:

  JsonlLogAdapter   -- two-tier JSONL persistence with optional fanout to
                       BOTH per-feature ledger AND singleton common log.
                       Closes friction #36 structurally when fanout=True.
  StdoutLogAdapter  -- emit gate events as JSON-line on stdout/stderr (for
                       `des <gate> --emit-stdout` operator-debug mode).
  SilentLogAdapter  -- no-op adapter for tests + dry-run replays; optionally
                       captures events in-memory for test introspection.
"""

from des.adapters.driven.log_persistence.jsonl_adapter import JsonlLogAdapter
from des.adapters.driven.log_persistence.silent_adapter import SilentLogAdapter
from des.adapters.driven.log_persistence.stdout_adapter import StdoutLogAdapter


__all__ = ["JsonlLogAdapter", "SilentLogAdapter", "StdoutLogAdapter"]

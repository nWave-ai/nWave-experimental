# Technology Stack: nw-rigor

## Summary

No new technologies or dependencies. This feature is pure configuration plumbing within the existing stack.

## Stack

| Component | Technology | Version | License | Rationale |
|-----------|-----------|---------|---------|-----------|
| Config properties | Python | >= 3.10 | PSF-2.0 | Existing DES runtime language |
| Config storage | JSON | N/A | N/A | Existing des-config.json format |
| Command definitions | Markdown | N/A | N/A | Existing slash command format |
| Type checking | mypy | strict | MIT | Existing project requirement |
| Testing | pytest | existing | MIT | Existing test framework |
| Diagrams | Mermaid C4 | N/A | MIT | Existing documentation format |

## New Dependencies

None.

## Rejected Alternatives

### YAML for config storage
- Already using JSON for des-config.json
- Switching formats would break existing consumers
- No benefit for this flat config structure

### SQLite for config persistence
- Massive overkill for a single JSON file with 10 keys
- Adds a dependency where none is needed
- JSON read-modify-write is sufficient for single-writer (one user, one session)

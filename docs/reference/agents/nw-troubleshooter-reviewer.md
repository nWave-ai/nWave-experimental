# nw-troubleshooter-reviewer

Use for review and critique tasks - Risk analysis and failure mode review specialist. Runs on Haiku for cost efficiency.

**Wave:** Other
**Model:** haiku
**Max turns:** 25
**Tools:** Read, Glob, Grep, Task, Bash

## Preloaded skills

- [nw-code-analysis-port](../skills/nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) through the vendor-neutral CLI `des code-fact`, degrading LOUD through bundled adapters (AST, TextSearch). Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.
- [nw-tr-review-criteria](../skills/nw-tr-review-criteria.md) — Review dimensions and scoring for root cause analysis quality assessment

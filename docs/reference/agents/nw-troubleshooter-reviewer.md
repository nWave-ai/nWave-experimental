# nw-troubleshooter-reviewer

Use for review and critique tasks - Risk analysis and failure mode review specialist. Runs on Haiku for cost efficiency.

**Wave:** Other
**Model:** haiku
**Max turns:** 25
**Tools:** Read, Glob, Grep, Task, Bash, mcp__tsunami__callers_of, mcp__tsunami__reads_of, mcp__tsunami__never_wired, mcp__tsunami__atoms_in_file, mcp__tsunami__adr_section

## Skills

- [nw-code-analysis-port](../skills/nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) THROUGH the nWave vendor-neutral CodeFactPort, preferring graphify (Tsunami temporarily disabled), then AST, with grep as last resort and degrading LOUD. Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.
- [nw-tr-review-criteria](../skills/nw-tr-review-criteria.md) — Review dimensions and scoring for root cause analysis quality assessment

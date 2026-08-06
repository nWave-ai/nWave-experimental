# nw-troubleshooter

Use for investigating system failures, recurring issues, unexpected behaviors, or complex bugs requiring systematic root cause analysis with evidence-based investigation.

**Wave:** Other
**Model:** inherit
**Max turns:** 45
**Tools:** Read, Write, Edit, Glob, Grep, Bash, Task, WebSearch, WebFetch, mcp__tsunami__callers_of, mcp__tsunami__reads_of, mcp__tsunami__never_wired, mcp__tsunami__atoms_in_file, mcp__tsunami__adr_section

## Commands

- [`/nw-bugfix`](../commands/index.md)
- [`/nw-root-why`](../commands/index.md)

## Skills

- [nw-code-analysis-port](../skills/nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) THROUGH the nWave vendor-neutral CodeFactPort, preferring Tsunami, then AST, with grep as last resort and degrading LOUD. Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.
- [nw-five-whys-methodology](../skills/nw-five-whys-methodology.md) — Toyota 5 Whys methodology with multi-causal branching, evidence requirements, and validation techniques
- [nw-investigation-techniques](../skills/nw-investigation-techniques.md) — Evidence collection methods, problem categorization, analysis techniques, and solution design patterns
- [nw-post-mortem-framework](../skills/nw-post-mortem-framework.md) — Blameless post-mortem structure, incident timeline reconstruction, response evaluation, and organizational learning

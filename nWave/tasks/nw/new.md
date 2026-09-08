---
description: Reads where an open request stands, then routes to the earliest authority that lacks evidence.
argument-hint: '[request]'
disable-model-invocation: true
---

# NW-NEW

Read the state first. It says whether a request is already open here, and names
the canonical next step in its `NEXT` line:

```bash
des state --repo-root ROOT
```

If a request is open, invoke that step. If none is open, start one:

```bash
printf '%s' "$REQUEST" | des po --repo-root ROOT
```

A step refuses when the state does not admit it and names the missing producer
in its `HOW`. A refusal for missing authority names the durable authority it
needs: go upstream, then invoke the same step again. Do not create a feature workspace and do not infer progress from
filesystem names.

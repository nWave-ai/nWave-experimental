---
name: nw-discuss
description: Routes a product question or outcome into the DES steps.
user-invocable: true
argument-hint: '<product question or outcome>'
---
# NW-DISCUSS
Set the exact question or outcome as `$REQUEST`:
```bash
printf '%s' "$REQUEST" | des po --repo-root ROOT
```
Product clarification is the Product Owner turn inside that step; the existing product authority remains owner. Then invoke the step each block names in its `NEXT` line. `nw-auto` owns the loop. Public results are `Success`, `Refusal`, `Retry`, and `Indeterminate`.

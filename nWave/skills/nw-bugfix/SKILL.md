---
name: nw-bugfix
description: Routes an observed defect request into the DES steps that deliver the fix.
user-invocable: true
argument-hint: '<observed defect>'
---
# NW-BUGFIX
Set the observed defect as `$REQUEST`:
Interactive, one step at a time:
```bash
printf '%s' "$REQUEST" | des po --repo-root ROOT
```
Then invoke the step each block names in its `NEXT` line. A step invoked on a state that does not admit it refuses and names what is missing, so a fix reaches its oracle before its code by the same floor every Request obeys. The source-blind EXAMINE lives inside `des verify` and is never skipped: a fix no one observed working is not a fix. `nw-auto` owns the loop. Public results are `Success`, `Refusal`, `Retry`, and `Indeterminate`.

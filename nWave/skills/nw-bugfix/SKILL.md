---
name: nw-bugfix
description: Routes an observed defect request into the DES steps that deliver the fix.
user-invocable: true
argument-hint: '<observed defect>'
---
# NW-BUGFIX
Before authoring regression tests or changing code, load `nw-auto` and report
the affected project's existing test baseline to the user as required by its
visible-baseline rule. A broken setup is not the bug's intentional RED.

Give the observed defect verbatim to the native installed Product Owner. Follow
`nw-role-invocation` for its mandatory skills and exact role contract, then:
```bash
printf '%s' "$DISCUSS_MANIFEST" | des po --repo-root ROOT --feature FEATURE_ID --input -
```
The same typed constructors as a feature write durable authorities from native
role facts under configured destinations. Keep the defect verbatim in DISCUSS
and the matching observation in DISTILL. The native acceptance designer authors
the regression oracle; `des oracle --input -` measures RED. The native crafter
implements the correction; `des craft --input -` measures GREEN and records it.
DES never authors code or invokes a model; no wave is mandatory.

For this bugfix, the LLM evaluates and revises an evidence-based S/M/L assessment, decides applicable waves or an upstream authority correction, and chooses each supported operation. `NEXT` is advisory and may be ignored; DES never maps size to a route or invokes it. A command may refuse when its required input or recorded data is absent, so a fix uses its observed refusal evidence before changing code. The source-blind EXAMINE is never skipped: a fix no one observed working is not a fix. `des verify` records the candidate and its native evidence; the LLM selects and runs the reviewer and the examiner through the separate role commands. `nw-auto` owns that guidance. Public results are `Success`, `Refusal`, `Retry`, and `Indeterminate`.

Document scope must be explicit for DISCUSS, PO and DEVOPS. The examples select a feature; alternatives are `--project`, `--epic EPIC_ID`, or `--slice FEATURE_ID SLICE_ID`. Select exactly one. Later steps inherit the persisted scope.

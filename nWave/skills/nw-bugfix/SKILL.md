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

Set the observed defect as `$REQUEST`:
Interactive, one step at a time:
```bash
printf '%s' "$REQUEST" | des po --repo-root ROOT --feature FEATURE_ID
```
The durable documents a bugfix owes are constructed by the SAME typed producers a feature uses -- `des discuss`, `des design`, `des devops`, `des distill` -- reading global configuration with project overrides. There is no bugfix pipeline: `des po` records the decomposition and writes no authority, so a fix that stops there leaves no conforming document. Carry the observed defect verbatim into the DISCUSS authority, name the same observation in the DISTILL obligation the regression oracle answers, and let `des oracle` measure that oracle RED against the defect before `des craft` corrects it. No wave is mandatory and the LLM never writes a document itself.

For this bugfix, the LLM evaluates and revises an evidence-based S/M/L assessment, decides applicable waves or an upstream authority correction, and chooses each supported operation. `NEXT` is advisory and may be ignored; DES never maps size to a route or invokes it. A command may refuse when its required input or recorded data is absent, so a fix uses its observed refusal evidence before changing code. The source-blind EXAMINE is never skipped: a fix no one observed working is not a fix. `des verify` records the candidate and its native evidence; the LLM selects and runs the reviewer and the examiner through the separate role commands. `nw-auto` owns that guidance. Public results are `Success`, `Refusal`, `Retry`, and `Indeterminate`.

Document scope must be explicit for DISCUSS, PO and DEVOPS. The examples select a feature; alternatives are `--project`, `--epic EPIC_ID`, or `--slice FEATURE_ID SLICE_ID`. Select exactly one. Later steps inherit the persisted scope.

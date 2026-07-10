---
name: nw-distill-feature-delta-schema
description: "Feature-delta.md authoring schema for DISTILL — the canonical four-column inherited-commitments table format, the scaffold command, the E1+E2 validator rules, and incremental authoring. Consult while authoring or validating a feature-delta wave section's table structure."
user-invocable: false
disable-model-invocation: true
---

# DISTILL Feature-Delta Schema (KNOWLEDGE)

**Kind**: KNOWLEDGE (reference). No forced sequence — consulted on its trigger.

**Trigger**: you are authoring or validating a `feature-delta.md` wave section's TABLE FORMAT — the inherited-commitments table, the scaffold command, or whether a section passes the E1+E2 validator. Composed by `nw-distill`.

Provenance: `unified-feature-delta` US-01 (scaffold command), US-02 (E1+E2 validator rules).

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## Document shape

Every `feature-delta.md` = Markdown with `## Wave: <NAME>` sections. Canonical table format MANDATORY in every `### [REF] Inherited commitments` block.

## Scaffold command

```
nwave-ai init-scaffold --feature <feature-name>
```

Creates `docs/feature/<feature-name>/feature-delta.md` with three pre-populated wave sections (DISCUSS, DESIGN, DISTILL), each with a ready-to-fill commitments table. Scaffold passes E1+E2 validator immediately.

## Canonical table format

Every `### [REF] Inherited commitments` block MUST have exactly four columns in this order:

```markdown
## Wave: DISCUSS

### [REF] Inherited commitments

| Origin | Commitment | DDD | Impact |
|--------|------------|-----|--------|
| n/a | <commitment text> | n/a | <impact text> |
```

Column semantics:
- **Origin**: wave + row ref of upstream commitment (e.g., `DISCUSS#row1`) or `n/a` for root commitments
- **Commitment**: the commitment inherited or newly introduced in this wave
- **DDD**: Design Decision Document ref authorizing any change (e.g., `DDD-3`) or `n/a` / `(none)`
- **Impact**: substantive description (>=10 words or a consequence verb from the verb list) of effect on system

## Reuse Analysis table (separate contract — cross-reference)

The `## Reuse Analysis` section (DESIGN wave) is a DIFFERENT table with its own contract — canonical heading, 5 columns (`Existing Component | File | Overlap | Decision | Justification`). Full contract + gate SSOT: `nw-design` skill §Reuse Analysis. Reminder for authors/validators: the Decision cell is exactly `EXTEND` or `CREATE_NEW` — a read-only consumed dependency (a Protocol/interface merely called, a property cross-checked) is NOT a table row; note it in prose beneath the table instead.

## Validator rules (E1+E2)

- **E1 (SectionPresent)**: every `## Wave: <NAME>` heading matches the canonical pattern. Known wave names: DISCOVER, DISCUSS, DESIGN, DEVOPS, DISTILL, DELIVER. Near-misses get a did-you-mean suggestion.
- **E2 (ColumnsPresent)**: every `### [REF] Inherited commitments` block has a header row with the four required columns (Origin, Commitment, DDD, Impact) in any order, case-insensitive.

Validator: `src/des/cli/validate_feature_delta.py`.

## Incremental authoring

Wave sections not yet authored may be omitted entirely. The validator does not require all six. A DISCUSS-only feature-delta = valid. Missing future-wave sections are never flagged.

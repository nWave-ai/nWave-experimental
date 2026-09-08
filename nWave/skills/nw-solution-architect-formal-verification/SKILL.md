---
name: nw-solution-architect-formal-verification
description: "PROCEDURE — verify one separately selected formal DESIGN obligation and state its runtime refinement boundary."
user-invocable: false
---

# Formal DESIGN Verification

**Kind**: PROCEDURE. **Job**: verify one formal DESIGN claim with its scope.
**Trigger**: a separately selected local totality, inhabitation, canonicalization, or preservation obligation; selected state-transition safety/refinement; or
selected state-machine reachability, liveness, concurrency, or recovery.
Routine constructor/type/equality claims alone do not trigger it; artifact
absence does not disable a selected claim trigger. It composes in either parent.

## Deterministic sequence

1. **Classify** — selected local proof uses Agda; selected state/temporal proof
   uses TLA+/TLC. Run selected safety/refinement invariants; bounded execution
   makes only liveness irrelevant. Decompose mixed obligations.
2. **Probe tools** — detect the host platform, then execute `agda --version`;
   for TLA+, execute `java -version` and locate `tla2tools.jar`. Declared
   configuration is not availability evidence. Do not assume Linux paths,
   package managers or shell behavior.
3. **Run** — execute available Agda. For TLA, execute declared temporal
   properties with necessary fairness; create/reuse a `.tla` model and `.cfg`
   configuration and actually pass both files to TLC. Record literal argv, exit
   status and result. Gate: intended/future argv, missing model/configuration
   or non-executed TLC is `ARCHITECTURE-BLOCKED`.
4. **Refine** — name model atoms, runtime symbols, exclusions and refinement.
   For `RED_TO_GREEN`, a runtime implementation is not required: record the
   mapping/refinement obligation and declared limits. A verified design model
   with complete mapping may support DESIGN coverage, but never runtime
   coverage. Gate: absent mapping is unrefined model-only evidence, never
   COVERED. T5 models declared progress/liveness only; T6 names real guarantor,
   monitor and failure consequence; T7 names exact code reference and
   mechanism/protocol atomicity, or `QUESTION/NEEDS_INPUT`.
5. **Fallback** — when unavailable on a documented host-supported path, offer
   installation once with user authorization; on decline record `formal tools
   unavailable -- prose-algebra fallback` and affected proof `INDETERMINATE`.
   Unknown/unsupported paths do the same. Include equations, observations and
   vacuity checks. missing tooling never invents a proof or blocks all DESIGN.

## Composition

- `nw-algebraic-design-protocol` — observations, equality and public terms.
- `nw-certainty-by-construction` — local construction boundary.
- `nw-formal-verification-tlaplus` — TLA+/TLC modeling heuristics.

## Verification

- [ ] Tool availability was executed, not asserted.
- [ ] The selected tool and property match local or state-transition trigger.
- [ ] Probe and any installation offer match the actual host platform.
- [ ] The authority names mapping, exclusions, mapping/refinement obligation
  and declared limits; it never calls a model result runtime coverage.
- [ ] A TLA run records `.tla`, `.cfg`, literal TLC argv, exit status and
  result; an intended/future argv is BLOCKED.
- [ ] Fallback is explicit when the tool remains unavailable.

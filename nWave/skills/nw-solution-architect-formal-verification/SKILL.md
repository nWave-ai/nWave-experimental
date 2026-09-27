---
name: nw-solution-architect-formal-verification
description: "PROCEDURE — verify one separately selected formal DESIGN obligation and state its runtime refinement boundary."
user-invocable: false
---

# Formal DESIGN Verification

**Kind**: PROCEDURE. **Job**: verify one formal DESIGN claim with its scope.
**Trigger**: a separately selected local totality, inhabitation, canonicalization, or preservation obligation; selected state-transition safety/refinement; or
selected state-machine reachability, liveness, concurrency, or recovery;
or a selected non-functional requirement with a modelable observation, such as
response deadlines, bounded queues, isolation, availability or recovery time.
Routine constructor/type/equality claims alone do not trigger it; artifact
absence does not disable a selected claim trigger. It composes in either parent.

## Deterministic sequence

1. **Classify** — selected local proof uses Agda. For a new state/temporal
   model, use Quint as the standard notation because it is more readable for
   the model author; select Apalache or TLC according to the actual claim.
   Preserve useful existing TLA+ models. Use direct TLA+ for a new model only
   when Quint cannot express or verify the selected claim with available
   tooling; record that concrete reason in the DESIGN authority. Decompose
   mixed obligations; finite exploration does not make a requested liveness
   guarantee irrelevant.
2. **Probe tools** — detect the host platform, then execute `agda --version`;
   for Quint, execute `quint --version` (or its configured local binary), and
   check the selected verifier and its Java prerequisites; for direct TLA+,
   execute `java -version` and locate `tla2tools.jar`. Declared
   configuration is not availability evidence. Do not assume Linux paths,
   package managers or shell behavior.
3. **Run** — execute available Agda. For Quint, use `quint run` for exploration
   and `quint verify` with the selected backend for model checking; record the
   `.qnt` model, backend/configuration, checked properties and bounds. A passing
   simulation is not a completed formal verification. Check temporal properties
   and fairness with the selected backend's documented capabilities. For TLA,
   execute declared temporal
   properties with necessary fairness; create/reuse a `.tla` model and `.cfg`
   configuration and actually pass both files to TLC. Record literal argv, exit
   status and result. Intended commands, missing configuration or an unexecuted
   checker leave the selected proof `INDETERMINATE`; the LLM decides the route.
4. **Refine** — name model atoms, runtime symbols, exclusions and refinement.
   For `RED_TO_GREEN`, a runtime implementation is not required: record the
   mapping/refinement obligation and declared limits. A verified design model
   with complete mapping may support DESIGN coverage, but never runtime
   coverage. Gate: absent mapping is unrefined model-only evidence, never
   COVERED. T5 models declared progress/liveness only; T6 names real guarantor,
   monitor and failure consequence; T7 names exact code reference and
   mechanism/protocol atomicity, or `QUESTION/NEEDS_INPUT`.
5. **Offer installation / fallback** — when tools are unavailable, explain the
   relevant alternatives before offering a host-supported installation:
   Quint is the standard notation for new state models and uses Apalache or TLC
   for verification; direct TLA+/TLC retains existing models and its native tooling;
   Agda complements either for selected local type/proof obligations. Quint
   does not remove verifier dependencies. Include those dependencies in the
   offer: do not invoke a command that auto-downloads a missing backend before
   authorization. Offer only pertinent tools, not all three as a mandatory bundle.
   Preserve prior consent/refusal and offer installation once with user
   authorization; on decline record `formal tools
   unavailable -- prose-algebra fallback` and affected proof `INDETERMINATE`.
   Unknown/unsupported paths do the same. Include equations, observations and
   vacuity checks. missing tooling never invents a proof or blocks all DESIGN.

## Non-functional requirements and human review

Name the actor, observation, operating conditions, units and threshold before
modeling a non-functional requirement. Use explicit time, resource and fault
assumptions: state-transition count is not elapsed time. Separate real failure
from detected failure, and stated capacity from measured throughput. Model
checking can establish a property of those assumptions; actual latency,
throughput, recovery and availability still need their relevant runtime tests.
Do not claim a production percentile or service level from model exploration.

Reuse the PO's behavioral core where available, then make architectural
refinement and preservation obligations explicit. Render relevant traces into
domain-language scenarios for human review using `nw-po-scenario-exploration`;
the human need not read Quint or TLA+. Keep raw traces and model identity.

## Composition

- `nw-algebraic-design-protocol` — observations, equality and public terms.
- `nw-certainty-by-construction` — local construction boundary.
- `nw-formal-verification-tlaplus` — TLA+/TLC modeling heuristics.

## Verification

- [ ] Tool availability was executed, not asserted.
- [ ] The selected tool and property match local or state-transition trigger.
- [ ] A new state model uses Quint, or the authority records why direct TLA+ is required.
- [ ] Probe and any installation offer match the actual host platform.
- [ ] The authority names mapping, exclusions, mapping/refinement obligation
  and declared limits; it never calls a model result runtime coverage.
- [ ] A Quint verification records `.qnt`, backend/configuration, properties,
  bounds, literal argv, exit status and result; simulation is labelled separately.
- [ ] A TLA run records `.tla`, `.cfg`, literal TLC argv, exit status and result.
- [ ] Non-functional model assumptions and required runtime measurements are explicit.
- [ ] Fallback is explicit when the tool remains unavailable.

Reference: https://quint.sh/docs/quint#command-verify

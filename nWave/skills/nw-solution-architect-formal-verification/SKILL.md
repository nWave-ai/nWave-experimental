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

Completion requires an executed selected checker on the model/proof plus
property-specific falsification evidence. An available Quint installation
must be used, not replaced by a Python enumerator, even for a small finite
state space. Model authoring or syntax difficulty is not tool unavailability:
repair the model and run it, using the execution host when required by your
capabilities. If execution cannot be completed, leave the selected formal
claim `INDETERMINATE`, not PASS on substitute evidence.

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
   for Quint, execute `quint --version` (or its configured local binary) and
   `java -version`, then execute `printenv QUINT_HOME` and list `apalache-dist-*`
   in the directory it prints (`~/.quint` only when it prints nothing): Quint
   keeps its Apalache backend there, not on PATH, and `quint verify` downloads
   a missing one (see step 5). For direct TLA+,
   execute `java -version` and locate `tla2tools.jar`. Declared
   configuration is not availability evidence. Do not assume Linux paths,
   package managers or shell behavior.
3. **Run** — execute available Agda. For Quint, execute `quint run` for
   exploration (it needs no backend, so run it whenever `quint` is available)
   and `quint verify` with the selected backend for model checking;
   record the `.qnt` model text, backend/configuration, checked properties and
   bounds in the authority. A passing simulation is not a completed formal
   verification. Both `quint verify` backends first start a local Apalache
   server, and TLC itself opens a local socket; when the sandbox refuses it,
   record that failure and verify the same `.qnt` without a server:
   `quint compile --target json M.qnt > M.qnt.json` (Apalache reads Quint
   input only from a file named `*.qnt.json`), then
   `apalache-mc check --init=… --next=… --inv=… --length=…` on it with the same
   names and bound, using `apalache-mc` from
   `apalache-dist-<version>/apalache/bin` in the probed directory.
   Check temporal
   properties and fairness with the selected backend's documented capabilities.
   For TLA, execute declared temporal
   properties with necessary fairness; create/reuse a `.tla` model and `.cfg`
   configuration and actually pass both files to TLC. Record literal argv, exit
   status and result. Unless the authority retains it at a requested path, the
   model or proof file is an invocation-local disposable probe outside the
   repository. Run checkers on a copy outside the repository so their output
   (`.agdai`, `_build`, `_apalache-out`) never lands in it. Create files only
   where your capability surface grants file creation; otherwise give your host
   their exact text, path and checker argv to write and execute, and record the
   returned receipts. Label hand enumeration, scripts and prose separately;
   none replaces the selected checker. Intended commands, missing configuration
   or an unexecuted checker leave the selected proof `INDETERMINATE`.
   **Discriminate the selected obligations.** For each property claimed as
   verified, link it to the behavior/observation it names and run the same check
   on a targeted behavioral mutant, not a changed property definition or flag.
   Before reporting completion, pair each selected property with its correct
   check and its mutant violation receipt (Quint/TLA: counterexample exit;
   Agda: rejected mutant module or checked refutation). For a conjunction,
   one mutant violating one clause does not discriminate the other clauses:
   check each selected clause against a relevant mutant, reusing a mutant only
   when its counterexample actually violates that clause. Keep this check
   proportionate to the
   selected obligations, not every helper lemma. Missing mutant discrimination
   is insufficient falsification evidence: mark that claim unverified and
   investigate its observation or strengthen the model when warranted. Failure
   to find a mutant is not a mathematical proof of vacuity; establish vacuity
   from the property's semantics before calling it vacuous.
4. **Refine** — name model atoms, runtime symbols, exclusions and refinement.
   For `RED_TO_GREEN`, a runtime implementation is not required: record the
   mapping/refinement obligation and declared limits. A verified design model
   with complete mapping may support DESIGN coverage, but never runtime
   coverage. Gate: absent mapping is unrefined model-only evidence, never
   COVERED. T5 models declared progress/liveness only; T6 names real guarantor,
   monitor and failure consequence; T7 names exact code reference and
   mechanism/protocol atomicity, or `QUESTION/NEEDS_INPUT`.
5. **Offer installation / fallback** — when a selected tool is unavailable,
   explain the relevant alternatives: Quint is the standard notation for new
   state models and uses Apalache or TLC for verification; direct TLA+/TLC
   retains existing models and its native tooling; Agda complements either for
   selected local type/proof obligations. Quint does not remove verifier
   dependencies. Do not invoke a command that auto-downloads a missing backend
   before authorization. Preserve prior consent/refusal; absent one, write both
   lines below in the authority and repeat them verbatim in your final reply,
   also in subagent or auto mode where nobody answers this turn:
   - `formal tools unavailable -- prose-algebra fallback`, and the affected
     proof `INDETERMINATE` beside any substitute check that did run;
   - one line beginning `Installation offer:` naming only the pertinent tools
     and their dependencies (for Quint: Node.js, Java and the Apalache or TLC
     backend) for the probed platform. Offering is not installing; it needs no
     network.
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
- [ ] An available selected checker ran on the actual model/proof (own or host
  receipt); substitute evidence is labelled separately.
- [ ] The selected tool and property match local or state-transition trigger.
- [ ] A new state model uses Quint, or the authority records why direct TLA+ is required.
- [ ] Probe and any installation offer match the actual host platform.
- [ ] The authority names mapping, exclusions, mapping/refinement obligation
  and declared limits; it never calls a model result runtime coverage.
- [ ] A Quint verification records `.qnt`, backend/configuration, properties,
  bounds, literal argv, exit status and result; simulation is labelled separately.
- [ ] A TLA run records `.tla`, `.cfg`, literal TLC argv, exit status and result.
- [ ] Non-functional model assumptions and required runtime measurements are explicit.
- [ ] An unavailable tool leaves the fallback label, `INDETERMINATE` and one
  `Installation offer:` line in both authority and reply.

Reference: https://quint.sh/docs/quint#command-verify

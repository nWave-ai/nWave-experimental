# Delivery-convergence role-evaluation corpus

This bounded corpus fixes expected judgments before the instruction edits. It is
an evaluation input set, not product acceptance evidence, a new runner, or a
provider transcript. `cases.json` supplies public role inputs, an independently
determined outcome class and reason, plus the result that would falsify each
judgment. Its observations, identities, and declared oracle are synthetic
fixtures until an installed-role run records real public evidence.

The packet-revision and exact-restoration facts already have executable coverage
in the two tests named in `cases.json`; this corpus deliberately does not repeat
them. Its delta is instruction behavior: preserving original value in EXAMINE,
distinguishing missing evidence, no-op alignment reuse, dependency uncertainty,
unavailable Jev fallback, and the source-blind boundary.

## Run plan

The parent runs any purchased evaluation. For each case, use the actual installed
role and its declared mandatory skills; do not manufacture a provider outcome.

| Cases | Installed public role/input | Expected judgment |
| --- | --- | --- |
| `examiner-*` | Native `nw-user-examiner` with only that case's `public_input` serialized as its structured input. The installed role has empty tools apart from structured output. | `rejected` for the observed failed Confirm; `indeterminate` for the absent Confirm observation; source-blind input boundary preserved. |
| `examiner-rejects-established-confirmation-failure-despite-positive-observation` | Native `nw-user-examiner` with authenticated, candidate-bound positive and negative Confirm observations. | `rejected`; an established relevant failure contradicts the promise even when a positive observation also exists. |
| `examiner-keeps-unresolved-evidentiary-confirmation-conflict-indeterminate` | Native `nw-user-examiner` with two incompatible reports whose authenticity, candidate linkage, and same-event linkage are unresolved. | `indeterminate`; retain both reports and request an evidence discriminator. |
| `reviewer-rejects-v1-weakened-matching-oracle` | Native `nw-acceptance-designer-reviewer` with the original request, weakened visibility-only criterion, and matching declared oracle. Its installed review skills are mandatory. | Typed rejection with a design finding: successful confirmation is omitted and returns to the criteria/product owner before craft. |
| `unchanged-alignment-*` | Native `nw-acceptance-designer` for a bounded preimplementation reuse assessment, after loading its required skills including `nw-at-completeness-check`. Current and prior canonical fixture bytes carry the same independently computed SHA-256; its prior accepted record is explicitly hypothetical evaluator setup. | Typed `accepted` only confirms the bounded reuse assessment. It does not claim a real earlier acceptance role ran, product acceptance, or a compulsory new meeting/role turn. |
| `unknown-dependency-*`, `optional-jev-*` | The normal installed outer route that loads `nw-auto`; use `nw-role-invocation` when a specialist is actually needed. The `nw-typesafe-system-one` reference requires every supported, authorized semantic question to use the service when available; same-owner reuse and explicit limitations remain valid. | Do not authorize reuse under unknown dependency pertinence; continue locally if Jev is unavailable. These are pending installed outer-route probes, not simulated direct-role cases. |
| `review-round2-demonstrated-regression-blocks-integration` | The normal installed route carrying `nw-review`, with its existing reviewer and ATD routing. | A demonstrated product regression remains blocking even when introduced by the previous repair: ask ATD about oracle coverage first, then do not integrate before correction and independent review. |

For a native host, select the exact installed role, for example Codex
`spawn_agent(agent_type="nw-user-examiner", message=<serialized public input>)`.
The outer route, model selection, installed-home path, evidence output path, and
any `des prepare-role` argv remain host-owned. Do not invent DES flags: obtain
them from the installed command help at execution time.

For a directly selectable role, the executable public-port consumer is:

```bash
PYTHONPATH=src python tests/evals/delivery_convergence/run_probe.py \
  --case examiner-rejects-selected-criteria-that-lost-original-confirmation \
  --output-root /absolute/new-eval-output --model <installed-model> --provider claude
```

It writes the public input, immutable turn-record projection, and decoded typed
judgment below a fresh invocation directory and reports that exact path in its
JSON result. Claude additionally retains its raw
structured reply. Codex stdout is event transport and is never parsed or labelled
as a verdict; its existing adapter's decoded outcome/diagnostic (and review
defect when present) is authoritative.
It then prints the actual provider outcome as JSON. A process exit proves only a
completed role run. For a case that declares `expected_provider_outcomes`, the
probe returns non-zero when the typed outcome differs; it never judges
free-text diagnostics or fabricates a role decision. `nw-auto` cases return
`not-run` from this direct-role consumer because `nw-auto` is a skill of the
normal outer route, not a selectable specialist role; run those cases through
that installed outer route as the table specifies.

Pass `--provider codex` to compare the same directly selectable role through
the existing `CodexTaskAdapter`; no generic adapter is introduced. The current
CLI exposes exact final-role preparation only for a verified candidate:
`des prepare-role --repo-root ROOT --role examiner --candidate SHA --observations PATH`,
then `des invoke-role --repo-root ROOT --role examiner --candidate SHA --provider claude|codex --input INPUT`.
It exposes no direct `nw-auto` or `nw-review` command, so those cases remain
explicit pending normal installed outer-route probes.

## Repeated declared runs

The declared command may be run again with the same `--output-root`. Each run
creates `<output-root>/<case>/invocation-NNNN/`, preserving earlier prompts,
turn records, and results. A repeated run is new evaluation evidence; it does
not replace, relabel, or establish currentness of an earlier result.

`nw-user-examiner` must receive no production source, oracle source,
test-derived expectation, Jev request, or Jev result. Its preimplementation
assessment is not a final product verdict; only the two `final EXAMINE` packets
are final-outcome probes.

## Expected-result check

Compare the typed role outcome only where `expected_provider_outcomes` is
declared: the two final-EXAMINE cases and the V1 adequacy-review case. For the
unchanged-alignment control, the `accepted` result is a bounded assessment over
fixture bytes; it cannot establish historical real-role acceptance. A process
exit cannot itself claim semantic reuse. An unissued role call, unavailable
installation, missing mandatory skill, or absent recorded result is
`not-run`/`indeterminate` evaluation evidence, never a pass.

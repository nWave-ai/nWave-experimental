---
name: nw-adversarial-refutation
description: The adversarial-refutation review stance — assume the artifact is WRONG and try to PROVE it, default-to-refuted, diverse lenses, and an exhibited executable counterexample. The shared SSOT every DELIVER review (per-slice C_REVIEWER_AUDIT + per-feature F_FINAL_REVIEW) applies so the expensive final swarm is needed less.
user-invocable: false
disable-model-invocation: true
---

# Adversarial Refutation Stance

The review METHOD (the HOW), not a checklist. The dimensions (`nw-sc-review-dimensions`,
`nw-at-completeness-check`) are the WHAT to look for; this is the falsification POSTURE the
adversarial swarm runs — the one that caught the C13/C14 catalogued-not-wired false-DONE, and
on the consolidated 3-lens review the named-catch-all guard + fragile state-machine that two
homogeneous reviewers would have missed. Apply on every per-slice (C_REVIEWER_AUDIT) +
per-feature (F_FINAL_REVIEW) DELIVER review.

## Pillar 1 — confirmation → falsification

A confirmation review asks "does this look right?" and accepts the artifact's own claim. The
refutation stance INVERTS the burden:

> **Assume the artifact is WRONG. Try to PROVE it broken. You cannot prove an implementation
> correct — only fail to refute it. The burden is on the ARTIFACT to SURVIVE refutation, never
> on you to prove a bug exists.**

Popperian asymmetry — the single biggest shift from a confirmation review. Incomplete without
lens-diversity (Pillar 2).

## Pillar 1b — the SCORE is INDEPENDENT of design-agreement (the coherence-maximizer counter-force)

The subtlest way a review passes a wrong artifact: it scores how well the artifact AGREES with
the stated design/intent, not whether the artifact SURVIVES an independent attempt to break it.
An artifact that matches the design is coherent — it is not thereby correct. A reviewer rewarded
for confirming design-coherence maximizes COHERENCE, not TRUTH: it climbs the gradient toward
"reads as intended" and awards its highest score exactly where the artifact and the design tell
the same story — which is precisely where a shared blind spot hides. This gradient is the force
the whole stance exists to oppose; default-to-refuted (Pillar 2) and the exhibited counterexample
(Pillar 3) only bite if the SCORE itself is blind to design-agreement.

- **Score only survival, never agreement.** The verdict is a function of "did the constructed
  counterexample get caught?" — NOT "does this match what the design said?". Set the design aside
  as a claim to be broken, not an oracle to be confirmed against. Two artifacts that agree can
  both be wrong in the same way; agreement is evidence of nothing.
- **An empirical design-question is resolved by a TARGETED probe, not by assent.** When the design
  carries a question to settle at review/RED ("Q-1: verify X at RED", "confirm the wiring reaches
  production"), it is discharged by a probe that DISCRIMINATES the specific cause — not a coarse
  end-to-end red compatible with every cause, and never by the artifact asserting the question is
  answered. A walking-skeleton test that calls the target directly (callers in tests, ZERO in
  production) resolves nothing: it is `never_wired` wearing the name of the discipline that exists
  to prevent it. Ask the code-analysis port for the production-caller count (Tsunami → AST → grep,
  degrade-LOUD) — do not eyeball it.

## Pillar 2 — two levers, BOTH required

1. **Default-to-refuted** — uncertain = REFUTED, not "probably fine". Forces the artifact to
   EXHIBIT why it survives instead of riding the reviewer's benefit of the doubt. ALONE it
   degenerates into skepticism-noise — it becomes coverage only when paired with lens-diversity.
2. **Perspective-diversity** — each reviewer/pass attacks through ONE DISTINCT LENS
   (correctness · does-it-reproduce · security · vacuity · wiring · oracle-soundness). The power
   is the UNION of lenses, not redundant skepticism; N identical refuters catch less than N
   different ones. (Empirical: an architecture lens caught a named-catch-all a test-fragility
   lens missed, and vice-versa — homogeneous refuters miss one.)

   **Where this pillar fully lands — per-slice vs feature-end (do not over-claim).** A per-slice
   `C_REVIEWER_AUDIT` is a SINGLE reviewer: it realizes Pillars 1 + 3 in FULL (assume-wrong +
   default-to-refuted + exhibited counterexample) and can only APPROXIMATE Pillar 2 by running its
   own passes under different named lenses — a weaker substitute, since one agent shares one blind
   spot. GENUINE lens-diversity is a property of the per-feature `F_FINAL_REVIEW`, where ≥2 DISTINCT
   reviewers each carry a distinct lens. Do NOT collapse lens-diversity into a single per-slice
   prompt and call it covered — the empirical catch (the named-catch-all a homogeneous reviewer
   missed) came from N DIFFERENT reviewers, not one reviewer's N passes. (Sister Tsunami, validated
   on a real per-slice review: 9 refutations all survived in ONE reviewer = Pillars 1+3, not 2.)

## Pillar 3 — evidence discipline (for REFUTE and for CLEAR)

The executable counterexample is the witness. No prose-only verdicts.

- **To REFUTE** — EXHIBIT the failing case: the breaking input, the deleted call-site that leaves
  the test green, a real build error (trybuild/compile), an actual failing run. A refutation
  without a constructed, runnable counterexample is a suspicion, not a finding.
- **To CLEAR** — the artifact must EXHIBIT why it survives: run the counterexample, show it is
  caught. A clear without exhibited survival is a confirmation-bias pass.
- **The witness runs against the REAL artifact, not a synthetic snippet** — a doc-test or
  hand-written sample can diverge from the real impl (the H-1 fix required a real
  `trybuild E0004`, not a prose note: the synthetic test missed the named-catch-all in the real
  impls).

## Failure-mode taxonomy (the swarm's hunting checklist)

Drive each refutation pass against these refutation-specific modes — the ways an artifact looks
green while proving nothing that go BEYOND the test-quality catalog. For the vacuous / tautological /
mock-dominated / zero-assertion family, apply the **Testing-Theater Detection** catalog in
`nw-sc-review-dimensions` under this stance — it is the SSOT for those and is not re-listed here.

| Failure mode | The attack / litmus |
|---|---|
| **Catalogued-not-wired** (asserts the *declaration*, not the *behavior*) | Delete the call-site that wires the new code — does the test stay green? If yes → wrong-level / never reaches production dispatch. (Testing-Theater's "delete the production code" litmus misses this: a test calling the leaf directly stays meaningful while production dispatch never wires it.) |
| **Oracle silent today** (the "true-positive oracle" does not actually fire) | Run the positive case — does the detector/AT actually FIRE? A confirmation review accepts "the AT asserts it fires" without verifying it fires. |
| **Guard that does not guard** (the enforcement mechanism is itself bypassable) | Attack the guard: a fragile wildcard, a named catch-all `other =>`, a too-narrow regex — the guard-test passes but can false-green. |
| **Byte-identity claimed-not-proven** ("behavior-preserving" without an exact-set oracle) | Demand the exact-set oracle (the full tuple), not a count-only check that misses a reordering/swap. |
| **Scope-creep / silent-narrowing** (the slice ships more or less than declared) | Diff the delivered surface against the declared slice plan — anything extra or missing is unattested. |
| **Cross-language projection leakage** *(POLYGLOT / language-agnostic projects only)* | A language-specific sink/predicate fires on another language's file via callee name-collision. Run the projection against a SIBLING-language fixture carrying a colliding symbol (e.g. Python `exec("c"+x)` vs a TS/JS `exec` detector) — does it stay silent? If it fires on the wrong language, the projection leaks. Invisible to a single-language hermetic AT — the genericity-dual of catalogued-not-wired. |

The first five modes are UNIVERSAL (any review, any stack). **Cross-language projection leakage**
is CONDITIONAL — it applies only when the project is polyglot / language-agnostic (e.g. nWave's own
multi-language detectors); skip it for single-language work.

## Verdict shape

Each pass ends as either: a REFUTED finding carrying its exhibited executable counterexample, or
a SURVIVED verdict carrying the demonstration that the counterexample is caught. "Looks fine" is
not a verdict.

---

*Empirical source: the nWave adversarial verifier swarm (sister Tsunami) — the 15-verifier swarm
that caught the C13/C14 catalogued-not-wired false-DONE, and the consolidated multi-lens DELIVER
review. This SSOT productizes that stance into the standard per-slice + per-feature reviews so the
full swarm is the exception, not the rule. The cross-language projection-leakage mode was found by
sister Tsunami APPLYING this taxonomy's catalogued-not-wired litmus on a real polyglot slice (F1
slice-03, TS/JS detector D2) — the method generating a new mode is the stance working on itself.*

---
name: nw-distill-red-scaffolding
description: "DISTILL RED-ready scaffolding procedure (Mandate 7) — create minimal stub files so ATs are RED (assertion failure, impl missing) not BROKEN (import/infra error), with per-language scaffold recipes, then run the pre-DELIVER fail-for-the-right-reason gate that classifies each failing scenario before handoff."
user-invocable: false
disable-model-invocation: true
---

# DISTILL RED-Ready Scaffolding + Fail-for-Right-Reason Gate (PROCEDURE)

**Kind**: PROCEDURE | **One job**: make every AT RED-not-BROKEN and verify each fails for the right reason | **One trigger**: ATs are authored and import not-yet-implemented production modules, OR scenarios are about to hand off to DELIVER.

Composed by `nw-distill`. Universal principle: **raise an exception classified as assertion failure (RED), not infrastructure error (BROKEN).**

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## Deterministic step-sequence (run every time, in order)

At execution start create these as TaskCreate items and run in order:

1. **INVENTORY MODULES** — list every production module imported in step definitions that does not yet exist. Gate: module list complete.
2. **SCAFFOLD EACH MODULE** — per module create the file at the correct path; add scaffold marker `__SCAFFOLD__ = True` (or language equivalent); define class/function with the correct parameter signature; method bodies raise an assertion error with the scaffold-marker message. Gate: every imported module scaffolded.
3. **CONFIRM RED-NOT-BROKEN** — run the suite; the runner classifies each test RED (assertion failure), never BROKEN (import/infra error). Gate: zero BROKEN.
4. **CLASSIFY (pre-DELIVER fail-for-right-reason gate)** — run `pytest tests/{feature}/acceptance/`, capture per-scenario failure output, classify each (table below). Gate: every failing scenario classified.
5. **BLOCK ON WRONG-REASON** — any ❌ row → BLOCK handoff to DELIVER; fix the test before crafter starts. Gate: zero ❌ rows.
6. **EMIT CLASSIFICATION** — one-line classification per failing scenario → `docs/feature/{feature-id}/distill/red-classification.md`. Gate: file written.

## What to scaffold

| # | Action | Gate |
|---|---|---|
| 1 | Create module file at the correct path (e.g., `src/app/plugin/installer.py`) | file created |
| 2 | Add scaffold marker `__SCAFFOLD__ = True` (or language equivalent) for machine detection | marker present |
| 3 | Define class/function with the correct parameter signature | signatures match what step definitions expect |
| 4 | Method bodies MUST raise an assertion error with the scaffold marker message | all methods raise AssertionError (not NotImplementedError) |
| 5 | Confirm the test runner classifies tests RED, not BROKEN | RED confirmed |

## Language-specific scaffolding

**Python**:
```python
# src/app/plugin/installer.py
"""Plugin installer -- RED scaffold (created by DISTILL)."""
__SCAFFOLD__ = True

class PluginInstaller:
    def __init__(self, **kwargs):
        pass

    def install(self, ctx):
        raise AssertionError("Not yet implemented -- RED scaffold")
```

**Rust**:
```rust
// src/plugin/installer.rs
// SCAFFOLD: true
pub struct PluginInstaller;

impl PluginInstaller {
    pub fn install(&self) -> Result<(), Box<dyn std::error::Error>> {
        panic!("Not yet implemented -- RED scaffold")
    }
}
```

**Go**:
```go
// plugin/installer.go
// SCAFFOLD: true
package plugin

func Install() error {
    panic("not yet implemented -- RED scaffold")
}
```

**TypeScript/JavaScript**:
```typescript
// src/plugin/installer.ts
export const __SCAFFOLD__ = true;

export class PluginInstaller {
    install(): never {
        throw new Error("Not yet implemented -- RED scaffold");
    }
}
```

**Java**:
```java
// src/plugin/PluginInstaller.java
// SCAFFOLD: true
public class PluginInstaller {
    public void install() {
        throw new AssertionError("Not yet implemented -- RED scaffold");
    }
}
```

### Scaffold detection

DELIVER uses the scaffold marker to track progress: `grep -r "__SCAFFOLD__" src/` (Python, TypeScript) · `grep -r "SCAFFOLD: true" src/` (Rust, Go, Java). After all DELIVER steps complete, zero scaffold markers should remain. The scaffold is never committed to production — it exists only between DISTILL approval and DELIVER completion.

### Why assertion errors (not NotImplementedError)

The RED/GREEN gate (`src/des/cli/verify_red_green.py`) classifies failures by error type:
- `AssertionError` / `panic!` / `throw Error` — **RED** (implementation missing, test correct)
- `NotImplementedError` — **BROKEN** (infrastructure issue)
- `ImportError` / `ModuleNotFoundError` — **BROKEN** (module missing)

Only RED tests proceed to the DELIVER TDD cycle. BROKEN tests block the upstream gate.

### Negative ATs — the detection convention (author them detectably the FIRST time)

Every critical scope MUST carry ≥1 **negative AT** — an assertion that the WRONG outcome is NOT
produced (the GS-8 class: presence-only ATs go red once, then green forever while asserting almost
nothing; weak assertions die only to negative ATs). The `des verify-negative-at` gate enforces this,
but it detects a negative AT **by NAME or MARKER, not by assertion shape**:

- **pytest**: the test carries `@pytest.mark.negative_at`, OR its function name contains one of
  `_not_` / `_never_` / `_rejects_` / `_refuses_` / `_fails_`.
- **Gherkin**: the scenario carries a `@negative` tag OR its name contains one of the same stems.

Author the negative AT with a matching NAME or the `@pytest.mark.negative_at` marker from the start —
a substantively-correct negative AT with a non-matching name (e.g. `test_..._passes_with_no_...`) is
NOT detected and the gate refuses, forcing a rename round-trip. `negative_at` is a registered marker
(`pyproject.toml [tool.pytest.ini_options] markers`), so the explicit marker is always available.

### Test-evidence contract — the runner MUST emit JUnit XML

The `des verify-red-green` gate (the RED-observed seal + the RED→GREEN mechanical proof) reads
per-test outcomes from **JUnit XML** — without it there is nothing to seal. So the test runner the
slice declares MUST emit JUnit XML:
- pytest: `--junitxml=<path>` (the gate's default when no run-cmd is given);
- Rust: `cargo nextest run --message-format ...` / a JUnit reporter;
- TypeScript: `vitest --reporter=junit` (or jest-junit);
- other languages: the equivalent JUnit-reporter flag.

If a declared `--run-cmd` does NOT emit JUnit XML, `verify-red-green` degrades LOUD ("no parseable
JUnit XML produced") and cannot seal — surface the runner's JUnit flag in the slice's test-evidence
setup so the seal is producible the first time. This is the proactive (GDP-2) complement to that
reactive degrade.

## The in-process active-RED pattern (the L2 default — drive the shipped entry, never import the SUT)

The default acceptance level (L2 in-process, per `nw-test-design-mandates-composition-contract`) drives the real entry IN-PROCESS rather than scaffolding the absent SUT module and importing it. This raises a problem the scaffold approach above does not face: **an absent SUT module imported at the test module top fails at COLLECTION → BROKEN, not active-RED.** subprocess-e2e dodged this by importing the SUT inside a forked child (so the ImportError became child-stderr) — at the cost of one interpreter fork per AT. The in-process cure keeps active-RED WITHOUT the fork.

**The cure: drive a STABLE always-present entry; the absent behaviour surfaces at RUNTIME inside the call.** The AT imports ONLY the stable entry (`cli main(argv)` / an application-service method) + the fake output port — NEVER the absent dispatched-to module. The absence manifests as a caught runtime exception (or a non-zero return + an emitted error line) WITHIN the in-process call, which the `Then` asserts on as a semantic `AssertionError`.

**The 4 invariants (P1-P4) that make in-process active-RED work:**

| # | Invariant | Why |
|---|---|---|
| **P1** | Module-level imports name ONLY stable entries (`main`, the app-service, the fake output port). NEVER the absent SUT module. | A top-level `import des.cli.not_yet` → collection ImportError → BROKEN. Keep the absent name out of import scope. |
| **P2** | The driving call goes through the stable entry IN-PROCESS: `rc = main(["--repo", str(tmp), "--new-flag"], output=fake)`. | In-process = no fork; same Mandate-13 driving-port semantics. |
| **P3** | The absent behaviour is reached by the entry's OWN internal dispatch (a **lazy** import / registry lookup / argparse route to an unimplemented branch). Its failure surfaces as a RUNTIME exception value WITHIN the call. | Runtime-inside-call ≠ collection. The test BODY runs; the assertion is reachable. |
| **P4** | The `Then` asserts on a CAPTURED observable: the fake recorded an error line, OR `main` returned non-zero, OR `pytest.raises(...)` wraps the call. The failure is a semantic `AssertionError`, not an import traceback. | active-RED contract: failure-for-the-right-reason, captured at the port boundary. |

**Cross-language general form** (the rule is language-agnostic; the Python form below is illustration): drive the shipped surface through the real protocol and assert on a captured observable — the protocol-driver contract owned by Mandate 13 (`nw-test-design-mandates-composition-contract`). The active-RED-specific addition this skill owns: **NEVER import the not-yet-implemented SUT at module top** — the absent behaviour is always reached through the stable entry's own internal dispatch, so its failure is a runtime value, not a collection error.

**Collection-semantics premise (the WHY behind P1+P3).** The runner's collection phase imports the test module and traverses it to find test functions but does NOT execute function bodies. Therefore a lazy import (or any reference to the absent name) placed INSIDE a function body is never evaluated during collection — it runs only when the test executes, after collection. P1 keeps the absent name out of the collection-traversed module top; P3 places its reach in a body the collection phase provably never runs. (Per-language analogue: if a target runner cannot guarantee collection does not execute bodies, degrade-LOUD to INDETERMINATE rather than assume the premise.)

**Executable proof**: run the focused AT before handoff. It must collect, reach the project's stable public entry, and fail at the captured output boundary because behavior is missing. A repository-specific exemplar is evidence only for that repository; never copy its command or module name as a cross-project rule.

## Pre-DELIVER fail-for-the-right-reason gate

Before handing scenarios to DELIVER, run them once; verify each fails for the **right reason** — implementation missing — not setup error, fixture bug, import error, or test-infrastructure problem.

| Outcome | Classification | Verdict |
|---|---|---|
| FAIL — assertion fires, behaviour unimplemented | `MISSING_FUNCTIONALITY` | ✅ correct RED |
| FAIL — test never reaches the assertion | `IMPORT_ERROR` / `FIXTURE_BROKEN` / `SETUP_FAILURE` | ❌ wrong RED (test bug) → BLOCK |
| FAIL — assertion couples to internal struct | `WRONG_ASSERTION` / `OBSERVABLE_NOT_AT_PORT` | ❌ wrong shape (fix Universe) → BLOCK |
| SKIPPED at DISTILL→DELIVER handoff | BLOCK per ADR-GV-001 D7: "AT scaffold is skipped/pending — must be active-RED before DELIVER begins (D6/D7)." | ❌ BLOCK |

SKIPPED remediation: convert to active-RED scaffold (raises `AssertionError`), or move to a future slice (absent from disk until that slice enters). A skipped test = silent dormant seam — never reaches its assertion, invisible to all subsequent gates.

**Why this gate matters**: wrong-reason failure = false signal at GREEN — crafter "fixes" the import error, test goes green, feature never tested. Observed 2026-05-06 (`feedback_fixture_only_acceptance_hides_wiring`): a fixture-shape scenario passes against a wired-but-broken bridge, never exercising the seam. Gate output → `docs/feature/{feature-id}/distill/red-classification.md`; DELIVER reads it at PREPARE phase to confirm RED is genuine.

## Expansion `domain-language-fact-to-step-table` (soft gate)

Proposed to the user BEFORE step-method generation. One row per Given/When/Then surface. User approval = quick exchange — but renaming an established step-method is expensive, so surface the names early.

| Fact / observation | Step name (snake_case Python; PascalCase per host language) |
|---|---|
| no user is registered | `Given_no_user_is_registered` |
| user signs up with a valid email | `When_the_user_signs_up_with_a_valid_email` |
| user receives magic link | `Then_the_user_should_have_received_a_magic_link` |
| order is rejected | `Then_the_order_is_rejected` |

Use this mapping while authoring the executable oracle; do not persist a second prose copy.

## Success Criteria

- [ ] Every imported not-yet-implemented module scaffolded with `__SCAFFOLD__` + AssertionError bodies
- [ ] Suite classifies RED, never BROKEN
- [ ] Each failing scenario classified; zero ❌ wrong-reason rows
- [ ] `red-classification.md` written for DELIVER PREPARE-phase consumption

---
name: nw-at-completeness-check
description: Canonical AT completeness gate — research-anchored 7-category taxonomy (C1-C7) + 15-item mechanical checklist, PLUS Tier-2 structural-invariants gate (S-family) covering test-suite SSOT invariants (S1 step-text uniqueness, S2 driving-port-only boundary / no direct-domain testing). Paradigm-neutral. Drives acceptance-designer reviewer verdict deterministically.
user-invocable: false
disable-model-invocation: true
---

# AT Completeness Check — Canonical Taxonomy

Mechanical gate for acceptance-test completeness. Runs against any candidate AT set. Each unchecked item = potential gap. Verdict deterministic by count, not judgment.

**Provenance**: research-anchored 7-category taxonomy, paradigm-neutral. See `docs/research/at-edge-case-taxonomy-2026-05-19.md` for full literature review. Plan v3 §6 (ATDD-pure restructure) is the canonical specification.

**Anchors** [1]-[14] reference research doc bibliography.

## Two-tier gate

Reviewer runs **both** gates before issuing verdict; they are independent and additive:

1. **Tier-1 Coverage Gate** (§§1-2) — the canonical 7-category C1-C7 taxonomy + 15-item mechanical checklist. Audits **what the AT set covers** of the SUT's input/state/mode/error/env space.
2. **Tier-2 Structural Invariants Gate** (§2-bis) — the S-family (S1 step-text uniqueness, S2 driving-port-only boundary / no direct-domain testing per Mandate-13, S3 dormant-seam reconciliation per D11, future S4+). Audits **how the AT set itself is structured** — Mandate-12 + Mandate-13 SSOT/boundary invariants on the test code, plus the DESIGN driving-surface ↔ DISTILL AT-oracle reconciliation, not SUT coverage. A Tier-2 failure is independent of the Tier-1 score and BLOCKS regardless of coverage band.

The 15-item count, IDs, and verdict thresholds in Tier-1 are **unchanged** by Tier-2 additions; the S-family lives in its own namespace.

**Runtime note** (Ale 2026-05-24): nwave-dev has no sequencer / no engine — only hooks. This skill is a **contract document** loaded by acceptance-designer + reviewer agents at dispatch time. Enforcement is "the agent MUST run both gates before issuing AT verdict", not a runtime hook. Tsunami cross-language pair: structural invariants will also be enforceable by Rhai recipes (e.g. `step_text_collision.rhai`, tree-sitter `#[step]` AtomDecorator query) — see §2-bis cross-reference.

## Domain extensions

Project-specific AT-class specializations live as YAML overlays in `domain-extensions/` (sibling dir to this SKILL.md). The canonical 7-category taxonomy stays paradigm-neutral; domain overlays add `extra_checks` that the reviewer appends to the 15-item checklist for features opting in.

**When to add an extension**: project surfaces an AT-class that is a specialization of one or more canonical categories (typically C5 + C6) but not a new general category. Example: nWave IP/Privacy boundary = `public:false` mode flag (C5) + leak-in-output failure-contract (C6) — lives in `domain-extensions/nwave-installer.yaml`, NOT in canonical taxonomy.

**Overlay schema** (`domain-extensions/<kebab-case-domain-id>.yaml`):

```yaml
name: <kebab-case-domain-id>
version: <semver>
applies_to: <project / package / feature-pattern>
extends_canonical: [C5, C6]      # which canonical categories this specializes
extra_checks:
  - id: <DomainID>a
    description: <what to verify>
    maps_to_canonical: C6
    mandatory: <bool>
```

**Opt-in per feature** — in `docs/feature/{id}/distill/at-completeness-extensions.yaml`:

```yaml
extensions: [nwave-installer]
```

Reviewer adds overlay's `extra_checks` to the canonical 15-item checklist for that feature only. Verdict thresholds scale with total item count.

## AT-set scope under `atdd_pure`

The candidate AT set this gate runs against is **scoped by `workflow.mode`** (`.nwave/config.yaml`). Under `classic` mode the gate audits the feature's full acceptance-test set. Under `atdd_pure` mode (ADR-028) the unit of work is a carpaccio slice, DISTILL is invoked **per slice**, and only that slice's bounded `@slice-NN`-tagged AT group exists on disk when the slice enters DELIVER.

The completeness gate therefore runs **per-slice**: it audits the entering slice's AT group — the `≤ N` ATs tagged for that one slice — against the 7-category taxonomy, not an all-ATs-up-front contract. Each slice's AT group is gated when that slice is greened; the audit widens incrementally as later slices' ATs are authored. A per-slice AT set that scores `< 10/15` on the §2 checklist routes per §4 exactly as a classic full set would — the taxonomy, checklist, and verdict thresholds are paradigm-neutral and unchanged; only the *scope* of the candidate AT set narrows to one slice under `atdd_pure`.

---

## 1. Canonical 7-category taxonomy (paradigm-neutral)

| ID | Category | Anchor | One-line definition |
|----|----------|--------|---------------------|
| **C1** | Equivalence & Boundary | ISTQB §4.2 [1] / Beizer ch.5 [2] | Partition input domain + test at/adjacent to each boundary |
| **C2** | State & Transition | ISTQB §4.2.4 [1] / Hendrickson [3] / Hypothesis stateful [4] | Every legal transition + illegal-event-from-each-state + self-loops/terminal exits |
| **C3** | Count Cardinality (0/1/N) | Hendrickson "Count" [3] / Adzic key examples [5] | Empty / singleton / many for every collection input or output |
| **C4** | CRUD-Lifecycle & Idempotency | Hendrickson "CRUD" [3] / Hillel Wayne PBT+Contracts [6] | Repeat / replay / out-of-order ops preserve invariants; `f(f(x)) == f(x)` for idempotent ops |
| **C5** | Mode-Flag / Decision-Table | ISTQB §4.2.3 [1] / Adzic "key examples" [7] | Every materially-distinct Cartesian combination of mode flags exercised |
| **C6** | Negative & Robustness (Postel) | RFC 760 §1.2.10 [8] / FEW HICCUPPS [9] / Kaner LLST [10] / RIMGEA [11] | Hostile/degenerate input → explicit typed-error contract, never silent coercion |
| **C7** | Configuration / Environment / Interruption | Bach HTSM SFDIPOT [12] / Hendrickson "Configurations+Interruptions+Starvation" [3] / Marick Q4 [13] | Resource starvation + interruption mid-flow + concurrent actors |

### C1. Equivalence & Boundary
Partition the input domain into equivalence classes; test at least one representative per class plus values immediately on/adjacent to each partition boundary. Failures cluster at edges, not interiors. **Citation**: ISTQB Foundation v4.0 §4.2 [1]; Beizer 1990 ch.5 "Domain Testing" [2].

### C2. State & Transition
Model the SUT as states + events + guards + transitions. Cover (a) every legal transition, (b) ≥1 illegal-event-from-each-state (rejected gracefully), (c) self-loops and terminal-state exits. **Citation**: ISTQB §4.2.4 [1]; Hendrickson "State Analysis" [3]; Hypothesis `RuleBasedStateMachine` [4].

### C3. Count Cardinality (0/1/N)
For every collection-shaped input or output, exercise zero, one, and many. Zero is the canonical bug magnet (null-deref, divide-by-zero, "no items" UI). **Citation**: Hendrickson/Lyndsay/Emery cheat sheet — "Count: Zero, One, Many" [3]; Adzic [5].

### C4. CRUD-Lifecycle & Idempotency
Full Create/Read/Update/Delete lifecycle + verify repeat/replay/out-of-order operations preserve invariants. Idempotency = `f(f(x)) == f(x)`. **Citation**: Hendrickson "CRUD" [3]; Hillel Wayne PBT+Contracts [6]; ISTQB decision-table [1].

### C5. Mode-Flag / Decision-Table Coverage
When SUT exposes mode flags (`dry_run`, `force`, `verbose`, `public`), every Cartesian combination materially-different in behavior is a distinct AT. **Citation**: ISTQB §4.2.3 decision-table [1]; Adzic "Focus on key examples" [7]; Adzic SbE [5].

### C6. Negative & Robustness (Postel)
Every input channel accepts hostile/degenerate input; SUT must respond with explicit, asserted failure contract (typed error, exit code, empty-valid output) — never crash, never silently accept. **Citation**: RFC 760 §1.2.10 [8]; FEW HICCUPPS "Standards"+"Claims" [9]; Kaner/Bach/Pettichord LLST [10]; RIMGEA [11].

### C7. Configuration / Environment / Interruption
SUT runs under varying resource availability and may be interrupted mid-flow. Cover (a) resource starvation, (b) interruption mid-transaction, (c) concurrent actors. **Citation**: Bach HTSM SFDIPOT [12]; Hendrickson "Configurations"/"Interruptions"/"Starvation"/"Multi-user"/"Flood" [3]; Marick Q4 [13].

---

## 2. Mechanical 15-item application checklist

Run against any candidate AT set. Unchecked = potential completeness gap.

```
C1a — ≥1 AT exercises empty/zero/minimum-size input
C1b — ≥1 AT on each partition boundary (max-1, max, max+1)
C2a — SUT state machine documented in AT module docstring
C2b — For each state, ≥1 AT for illegal-event-from-that-state
C3  — parametrize/PBT covering n ∈ {0, 1, many} for each collection input
C4a — Each mutating op has "apply twice" AT (idempotency or correct non-idempotency)
C4b — ≥1 AT for inverse op without prerequisite (uninstall-without-install)
C5a — Each mode flag: every materially-distinct combination exercised
C5b — ≥1 AT asserting flag orthogonality (verbose toggles output only)
C6a — Each input param: ≥1 AT with malformed value (wrong type, malformed encoding)
C6b — Each declared error in contract: ≥1 AT triggers exactly that error
C6c — ≥1 AT asserts closed error set (no other error escapes)
C7a — ≥1 AT under degraded-resource condition (read-only FS / no network / low disk)
C7b — ≥1 AT for interruption mid-operation (SIGINT / timeout / partial commit)
C7c — If concurrent-safe by claim: ≥1 multi-actor AT (two parallel invocations)
```

Machine-readable form: `checklist-15-item.yaml` (alongside this file).

### Verdict thresholds (deterministic)

| Count passing | Verdict |
|---------------|---------|
| < 10 / 15 | **INCOMPLETE** — reject; route per §4 |
| 10–12 / 15 | **ACCEPTABLE_WITH_DOCUMENTED_GAPS** — pass with explicit listed gaps |
| ≥ 13 / 15 | **COMPLETE** — pass |

The reviewer agent **computes the count mechanically**, not subjectively. Items not applicable (e.g. C7c for non-concurrent SUTs) count as passing — document the rationale in verdict output.

---

## 2-bis. Tier-2 Structural Invariants Gate (S-family)

Independent gate. S-family items audit **how the AT set itself is structured** — Mandate-12 SSOT invariants on test code (S1/S2) plus the DESIGN driving-surface ↔ DISTILL AT-oracle reconciliation (S3), not coverage of SUT space. A Tier-2 failure BLOCKS regardless of the Tier-1 15-item score.

### S1. Step-Text Uniqueness Within Feature Scope

**Invariant**: every `@given(...) | @when(...) | @then(...)` decorator's literal argument string is unique across all step files in the same feature directory.

**Why**: pytest-bdd registers step bodies in a process-global registry keyed by `(step_type, literal_arg_string)`. When two step files in the same feature directory each declare `@then("the gate REFUSES the invocation with exit code 78")` with their own function bodies, the last-loaded module's body shadows the earlier one. Result: silent test inversion — one slice's scenarios start exercising another slice's production code path. The Tier-1 coverage gate cannot detect this; the contract gate catches it only after a test fails (often days later, with a misleading failure message). S1 is a Mandate-12 SSOT violation: one body per domain noun.

**Detection mechanism** (pseudo-code):

```python
def check_s1_step_text_uniqueness(feature_steps_dir: Path) -> S1Verdict:
    """Scan all .py files under feature_steps_dir, collect decorator literals,
    flag duplicates across distinct files where each declares its own body."""

    registry: dict[tuple[str, str], list[Site]] = defaultdict(list)
    # (step_type, literal_arg) -> [Site(file, lineno, qualname), ...]

    for py_file in feature_steps_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for dec in node.decorator_list:
                literal = extract_step_literal(dec)   # None if parsers.parse(...)
                if literal is None:
                    continue                          # parametrized templates skip
                step_type = extract_step_type(dec)    # "given" | "when" | "then"
                site = Site(file=py_file, lineno=dec.lineno, qualname=node.name)
                registry[(step_type, literal)].append(site)

    collisions = [
        (key, sites) for key, sites in registry.items()
        if len({s.file for s in sites}) >= 2          # two+ DIFFERENT files
    ]
    verdict = "PASS" if not collisions else "FAIL"
    return S1Verdict(verdict=verdict, collisions=collisions)
```

**Output token**: `step_text_uniqueness verdict={PASS|FAIL} collisions=<list of (step_type, literal, [file:line, ...])>`

**Tolerable variants** (NOT flagged as collision):

| Pattern | Why NOT a collision |
|---------|---------------------|
| `@then(parsers.parse("the gate responds with {phrase}"))` declared twice with different bodies | Template strings with `parsers.parse(...)` / `parsers.re(...)` — pytest-bdd binds via template+arg-extraction, not literal-string match. Different placeholder set ⇒ different registry key. |
| Same `@then("X")` in `slice_01_steps.py`, imported into `slice_02_steps.py` via `from .slice_01_steps import *` (one-source, propagated) | Single function object, single registration. No shadow possible. |
| Same `@then("X")` in `common_steps.py` (single SSOT module), referenced from multiple slice features via pytest-bdd's `features=[...]` step-set composition | Single source of truth, designed re-use. No shadow. |
| Literal `@then("X")` declared once in slice_01 file and not at all in slice_02 file | Single declaration ⇒ no collision (this is the goal state). |

**Flagged (FAIL)**:

| Pattern | Why a collision |
|---------|----------------|
| `slice_01_steps.py`: `@then("the gate REFUSES the invocation with exit code 78") def step_fn_a(...): ...` AND `slice_02_steps.py`: `@then("the gate REFUSES the invocation with exit code 78") def step_fn_b(...): ...` (each its own body, no shared import) | Two distinct function objects register against the same `(then, literal)` key. Last-loaded wins. Silent inversion. |

**Empirical anchor (2026-05-24)**: Slice-02 of Stream A (`fix-des-self-hosted-gate-sync`) double-registered `@then("the freshness gate PROCEEDS the invocation with exit code 0")` and `@then("the freshness gate REFUSES the invocation with exit code 78")` across `steps_slice_01_walking_skeleton.py` + `steps_slice_02_install_manifest.py`. pytest-bdd's global step registry shadowed slice-01's bodies. The contract gate caught it (1 AT failed) only after slice-02 had been authored — this S1 check is the FIRST line of defense and would have caught it at AT-completeness audit time, before DELIVER even started.

**Cross-language pair (Tsunami)**: the broader cross-language detector lives as a Rhai recipe `step_text_collision.rhai` (tree-sitter `#[step]` AtomDecorator query, group by qualname+body_text, emit on collision). Same invariant, two enforcement layers: S1 here is the FIRST-line within-feature Python check; Tsunami's recipe is the broader cross-language / cross-feature detector. Future readers: when porting, S1 maps 1:1 to the Rhai recipe's per-feature scope; cross-feature is Tsunami-only.

### S2. Driving-Port-Only Boundary — NO direct-domain testing in ATs (Mandate-13, 2026-05-25)

**Invariant**: NO AT step module (`composition.py`, `steps_*.py`, `slice*.py` under `tests/{path}/(?:acceptance|cli)/<feature>/`) imports production code directly from `des.domain.*`, `des.application.*`, or `des.adapters.*` for the purpose of invoking pure functions / classes / adapter instances at the function boundary. AND no NEW behavioral AT ships under `tests/des/unit/(?:domain|cli)/*` (that path is reserved for pre-existing legacy + arch tests).

**Why**: ATs must drive the SUT through a composition-root driving port at one of three layers — Layer 3 subprocess (`des <subcommand>` kebab dispatcher per F-DES-SINGLE-ENTRY-POINT-CONSOLIDATION), Layer 3 composition (`PreToolUseService(...).evaluate(...)`), or Layer 4 wiring_e2e (full stack, real hook subprocess). Direct-domain import + function-boundary invocation collapses the AT into a Layer-1 unit test, breaks hexagonal boundary discipline, and violates the atdd_pure paradigm (Layer 3 only). Ale directive 2026-05-25 verbatim: "ma perche ci sono unit test? il nuovo DES non dovrebbe farne scrivere. Inoltre il domain non dovrebbe essere testato direttamente." Empirical anchor (2 instances caught 2026-05-25 BEFORE shipping): M15 DISTILL composition.py:115-118 imported `DesMarkerParser` directly + invoked `.parse()` with comment "layer-1 (unit, pure-function)" — REMOVED; M16 D3 reviewer recommended Layer-1 parity guard at `tests/des/unit/cli/test_collect_node_ids_parity_guard.py`, crafter shipped, REMOVED.

**Detection mechanism** (pseudo-code):

```python
def check_s2_driving_port_only(feature_steps_dir: Path, new_test_files: list[Path]) -> S2Verdict:
    """Two-pass audit:
       (a) AST scan of feature step modules for forbidden direct-domain imports
       (b) Path check of NEW test files for behavioral coverage under tests/des/unit/(domain|cli)/*
    """
    DIRECT_IMPORT_RE = re.compile(r"^from des\.(?:domain|application|adapters)\.\w+ import ")
    FORBIDDEN_PATH_RE = re.compile(r"tests/des/unit/(?:domain|cli)/test_[^/]+\.py$")

    violations: list[Violation] = []

    # Pass (a) — direct import scan
    for py_file in feature_steps_dir.rglob("*.py"):
        for lineno, line in enumerate(py_file.read_text().splitlines(), 1):
            if DIRECT_IMPORT_RE.match(line.strip()):
                violations.append(Violation(
                    kind="direct_domain_import",
                    file=py_file, lineno=lineno, snippet=line.strip(),
                    remediation="restructure via driving port (Layer 3 subprocess OR Layer 3 composition root OR Layer 4 wiring_e2e); relocate to tests/des/(acceptance|cli)/<feature-name>/",
                ))

    # Pass (b) — wrong-tier path scan over NEW files only
    for new_file in new_test_files:
        if FORBIDDEN_PATH_RE.search(str(new_file)):
            violations.append(Violation(
                kind="wrong_test_tier",
                file=new_file, lineno=0, snippet="new behavioral AT under tests/des/unit/(domain|cli)/*",
                remediation="relocate to tests/des/(acceptance|cli)/<feature-name>/ and restructure via driving port",
            ))

    verdict = "PASS" if not violations else "FAIL"
    return S2Verdict(verdict=verdict, violations=violations)
```

**Output token**: `driving_port_only verdict={PASS|FAIL} violations=<list of (kind, file:line, snippet, remediation)>`

**Tolerable variants** (NOT flagged):

| Pattern | Why NOT a violation |
|---------|---------------------|
| `from des.domain.X import Y` / `from des.adapters.X import Y` inside production code under `src/des/**` | Production composition is allowed to import domain/adapters — invariant is scoped to test step modules only. |
| Pre-existing legacy test under `tests/des/unit/domain/*` not modified this run | Path constraint applies to NEW behavioral ATs; legacy tests are out of scope (retro audit is `F-DIRECT-DOMAIN-TEST-RETRO-AUDIT` HIGH). |
| Architecture/contract test under `tests/des/unit/cli/test_arch_*.py` asserting structural invariants (no behavioral execution) | Arch tests legitimately import to introspect structure, not to exercise behavior. Recognized via `test_arch_` prefix or `tests/des/architecture/*` path. |
| `from des.cli.X import main` invoked in step module via `subprocess.run([sys.executable, '-m', 'des.cli.X', ...])` | Subprocess invocation is Layer 3 subprocess (allowed). The import-statement scan only flags `from des.(domain\|application\|adapters).Y import Z` followed by direct-call use. |

**Flagged (FAIL)**:

| Pattern | Why a violation |
|---------|----------------|
| `composition.py`: `from des.domain.marker_parser import DesMarkerParser` + `DesMarkerParser().parse(text)` at step boundary | Direct-domain import + function-boundary invocation = Layer-1 unit test masquerading as AT. (M15 empirical anchor.) |
| `composition.py`: `from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger` + `AtCompletionLedger(...).append_*(...)` at step boundary | Direct-adapter import + instance-boundary invocation = composition-layer unit test masquerading as AT; adapters are infrastructure not driving surface. Restructure via subprocess f-string stub (Layer 3 subprocess) or composition-root entry (PreToolUseService / SubagentStopService). (M33 empirical anchor.) |
| New file `tests/des/unit/cli/test_collect_node_ids_parity_guard.py` shipped this feature as behavioral coverage | Wrong tier; behavioral ATs ship under acceptance/cli. (M16 empirical anchor.) |

**Remediation hint** (always emitted with finding): "relocate to tests/des/(?:acceptance|cli)/[feature-name]/ + restructure via driving port (Layer 3 subprocess / Layer 3 composition root / Layer 4 wiring_e2e)". Never recommend deletion — restructure preserves behavioral coverage at the right tier.

### S3. Dormant-Seam Reconciliation — every net-new DESIGN driving-surface seam has a witnessing AT (D11, 2026-06-07)

**Invariant**: for every net-new seam declared load-bearing in the DESIGN driving-surface for this slice — a net-new effectful parameter on an entry-point function (`clock=`), a net-new effectful call reached from the entry point (`absorb_ready_refs()`), a net-new param threaded into an existing seam — the slice's AT set names THAT exact seam as the port it drives, AND drives it through the **real entry point** while asserting an **observable effect** (state delta, emitted event, captured side effect). A declared net-new seam with no witnessing AT is a dormant-seam coverage gap.

**Why**: per-feature Driving Adapter Verification (`nw-distill` § Driving Adapter Verification) is entry-point-protocol-shaped (CLI / HTTP / hook) — satisfied by ONE nominal walking skeleton, BLIND to intra-process load-bearing seams. The DISTILL AT-oracle re-deriving its target from "what's new in the slice" silently substitutes the COMPONENT for the SEAM — an intra-author / intra-commit contradiction with the DESIGN driving-surface table. A feature then passes every per-slice gate yet ships the seam DORMANT (no production call-site, never reached from the real entry point) and does not function e2e. Empirical anchor (2026-06-07): consolidation-loops `background-loops-hybrid-c` (slices 04/05/07/08) shipped absorb/clock/drain-selector/reaper uncalled from `handle_session_start`; ALL per-slice gates green; two independent RCAs converged on this shared-asset gap. Full methodology: `nw-distill` § Dormant-Seam Reconciliation legs (b) + (c).

**Witnessing counts INDIRECT wiring (framing-attack — do NOT naive name/protocol match)**: "the seam has a witnessing AT driving it" MUST count indirect wiring — entry-point discovery, registry registration, dependency-injection — as valid coverage. A seam reached via registry / entry-point / DI is validly witnessed even with NO literal direct call-site or protocol call. Empirical anchor: `nwave.lang.adapter` entry-point discovery wires modules with no direct call-site **by design**. So "drives the declared seam" is NOT "a literal CLI / hook protocol call" nor "a bare-name function call" — a binding-resolved indirect reach (the symbol's registration value joined to its identity) counts. A naive name / protocol match reintroduces a false-positive class on every registry-dispatched symbol.

**Detection mechanism** (per-slice, against the DESIGN driving-surface declaration):

```python
def check_s3_dormant_seam_reconciliation(
    design_net_new_seams: list[Seam],   # from DESIGN driving-surface table, NOT slice diff
    slice_ats: list[AcceptanceTest],
) -> S3Verdict:
    """For each net-new DESIGN-declared seam, require a witnessing AT that drives
    it through the real entry point and asserts an observable effect. Witnessing
    counts INDIRECT wiring (registry / entry-point / DI), never naive name match."""
    gaps: list[Seam] = []
    for seam in design_net_new_seams:
        if not any(at_witnesses_seam(at, seam) for at in slice_ats):
            gaps.append(seam)   # declared load-bearing, no witnessing AT
    verdict = "PASS" if not gaps else "FAIL"
    return S3Verdict(verdict=verdict, dormant_seams=gaps)

def at_witnesses_seam(at: AcceptanceTest, seam: Seam) -> bool:
    """True iff the AT drives the seam through the real entry point AND asserts an
    observable effect. Reaching the seam via registry/entry-point/DI wiring counts
    (binding-resolved), NOT only a direct call-site or protocol call."""
    return at.drives_real_entry_point and at.reaches(seam, include_indirect_wiring=True) \
        and at.asserts_observable_effect_of(seam)
```

**Output token**: `dormant_seam_reconciliation verdict={PASS|FAIL} dormant_seams=<list of (seam, design_ref)>`

**Tolerable variants** (NOT flagged):

| Pattern | Why NOT a gap |
|---------|---------------|
| Seam reached only via entry-point discovery / registry registration / DI (no direct call-site) | Indirect wiring is valid witnessing — binding-resolved reach counts (the `nwave.lang.adapter` shape, by design). |
| A seam the DESIGN driving-surface does NOT declare net-new this slice | S3 audits the DESIGN declaration, not every symbol; pre-existing seams are out of scope. |
| Owned residue cleared by a `# dormant-ok: <F-id>` marker (mirrors the mechanical backstop escape) | Auditable, never-silent suppression — the seam is acknowledged-dormant with an owning F-id, not an undeclared gap. |

**Flagged (FAIL)**:

| Pattern | Why a gap |
|---------|----------|
| DESIGN declares `clock=` load-bearing on the entry point; the slice AT exercises the new COMPONENT directly but no AT drives `clock=` through the real entry point | Component-not-seam substitution; the seam ships dormant. (background-loops-hybrid-c empirical anchor.) |
| DESIGN declares `absorb_ready_refs()` reached from `handle_session_start`; no AT asserts its observable effect via the real entry point | Declared load-bearing, no witnessing AT — dormant seam. |

**Mechanical backstop**: the shipped OSS gate `des dormant-seam-gate` (`src/des/cli/dormant_seam_gate.py`, leg-a) is the runtime net behind S3 — it warns **INDETERMINATE (non-halting)** when a net-new effectful `src/**` public symbol has no production call-site, counting registry / entry-point / DI wiring as a call-site (binding-resolved, never a naive grep), with two never-silent escapes (a real call-site including indirect wiring, OR a `# dormant-ok: <F-id>` marker). S3 is the AT-completeness-time first line of defense; the gate is the runtime backstop. Treat an INDETERMINATE warning as an S3 finding to resolve (witness the seam, or annotate the owned residue), not as noise.

### S-family checklist

```
S1 — Step-text uniqueness within feature scope: zero literal-arg collisions across step files in same feature dir (parametrized templates and shared-import re-use excluded)
S2 — Driving-Port-Only Boundary: zero direct-domain imports in step modules (composition.py / steps_*.py); zero NEW behavioral ATs under tests/des/unit/(domain|cli)/* (legacy + arch tests excluded)
S3 — Dormant-Seam Reconciliation: every net-new DESIGN-declared driving-surface seam has a witnessing AT driving it through the real entry point + asserting an observable effect (indirect registry/entry-point/DI wiring counts; owned-residue marker excused)
```

### Tier-2 verdict

| S1 result | S2 result | S3 result | Tier-2 verdict | Action |
|-----------|-----------|-----------|----------------|--------|
| PASS | PASS | PASS | PASS | Proceed to Tier-1 verdict |
| FAIL | * | * | **BLOCK** | Reject AT set regardless of Tier-1 score. Verdict token includes collision list. Route to `AT_GAP_IN_DELIVERY_SCOPE`. |
| * | FAIL | * | **BLOCK** | Reject AT set regardless of Tier-1 score. Verdict token includes violation list (kind + file:line + remediation). Route to `AT_GAP_IN_DELIVERY_SCOPE`. |
| * | * | FAIL | **BLOCK** | Reject AT set regardless of Tier-1 score. Verdict token includes the dormant-seam list (seam + design_ref). Route to `AT_GAP_IN_DELIVERY_SCOPE` (a declared seam without a witnessing AT is a test-suite coverage defect, never an upstream specification gap — DESIGN already declared the seam). |

S-family items are MANDATORY by default; no falsifier-prune for S1/S2/S3 (S1/S2 have zero false-positive rate given the tolerable-variant filters; S3's indirect-wiring rule removes the registry/entry-point/DI false-positive class).

---

## 3. PBT / parametrize signatures per category

One-line code template per category. Crafter/acceptance-designer copy-adapt.

```python
# C1 — Equivalence & Boundary
@given(st.lists(elt, min_size=0, max_size=N+1))
@example([]) @example([single])

# C2 — State & Transition
class M(RuleBasedStateMachine):
    @rule(...)
    @invariant()
    @precondition(...)

# C3 — Count Cardinality
@pytest.mark.parametrize("n", [0, 1, 2, 100])
# or st.integers(min_value=0, max_value=...)

# C4 — CRUD-Lifecycle & Idempotency
# Property: f(f(x)) == f(x)
# Or: RuleBasedStateMachine with @rule chains over CRUD sequence

# C5 — Mode-Flag / Decision-Table
from itertools import product
@pytest.mark.parametrize("flags", list(product([True, False], repeat=k)))
# filter degenerate combinations

# C6 — Negative & Robustness
@given(st.one_of(st.text(), st.integers(), st.binary()))
# assert raises typed error from closed set:
# with pytest.raises(DeclaredError): ...

# C7 — Configuration / Environment / Interruption
class M(RuleBasedStateMachine):
    @rule(...)  # includes interruption events
# + parametrize over resource-degradation fixtures
```

Language-equivalent frameworks: Hypothesis (Python), fast-check (TS/JS), QuickCheck (Haskell), quickcheck (Rust), jqwik (Java), FsCheck (C#).

---

## 4. Reviewer output schema

Reviewer emits a typed verdict combining BOTH tiers. Two kinds of finding only.

```python
@dataclass(frozen=True)
class ATGap:
    scenario_class: str            # e.g. "C5a:dry_run-and-force-combo" | "S1:then-shadow-slice-01-vs-02"
    current_at_count: int          # 0 if missing entirely (Tier-1) | n/a for S-family
    reason: str
    kind: ATGapKind
    severity: Severity             # BLOCKER | HIGH | MEDIUM | LOW

class ATGapKind(str, Enum):
    AT_GAP_IN_DELIVERY_SCOPE = "at_gap_in_delivery_scope"
    SPECIFICATION_AMBIGUITY  = "specification_ambiguity"
```

`ARCHITECTURE_SCOPE_MISS` is NOT a reviewer-authored kind. Phase D router derives it via second-order rule (≥2 gaps sharing a scenario_class mapping to component absent from DESIGN output).

**S-family findings**: always `AT_GAP_IN_DELIVERY_SCOPE` (structural test-authoring defect), always severity `BLOCKER` (silent test inversion is a correctness hazard, not a coverage thinness). Never `SPECIFICATION_AMBIGUITY` — S-family invariants are intrinsic to the test suite, not derivable from upstream-wave artifacts.

---

## 5. Upstream-wave routing rule

Categories C2, C5, C6, C7 require upstream-wave specification. If absent → `SPECIFICATION_AMBIGUITY`, NOT `AT_GAP_IN_DELIVERY_SCOPE`. Phase D routes back to upstream wave, not back to DISTILL.

| Category | Upstream owner | Required artifact |
|----------|----------------|-------------------|
| C2 (state machine) | **DISCUSS** | State diagram in user-stories Elevator Pitch + DoD |
| C5 (mode-flag inventory) | **DESIGN** | Flag enumeration in component manifest |
| C6 (error contract) | **DESIGN** + **DISCUSS** | Typed error set + invariants per port |
| C7 (env / interruption matrix) | **DEVOPS** | Env matrix + concurrency/interruption contract |

Routing decision (mechanical):

```
if upstream artifact for category X missing
    → ATGap.kind = SPECIFICATION_AMBIGUITY → Phase D → upstream wave re-entry
else
    → ATGap.kind = AT_GAP_IN_DELIVERY_SCOPE → Phase D → loop A_GREEN_ATS
```

This closes the Mandate-12 SSOT loop: domain types in DISCUSS/DESIGN/DEVOPS drive taxonomy population.

---

## 6. Domain extensions

Canonical taxonomy is paradigm-neutral. Project-specific instantiations live in `domain-extensions/*.yaml`.

```
nWave/skills/nw-at-completeness-check/
├── SKILL.md                          # this file — canonical 7-category (GENERIC)
├── checklist-15-item.yaml            # machine-readable mechanical gate
└── domain-extensions/                # per-project overlays (kebab-case)
    ├── README.md                     # how to add a domain extension
    ├── nwave-installer.yaml          # IP/Privacy + filesystem-shape (nWave-specific) [SLOT]
    └── nwave-des.yaml                # DES marker-specific extensions [SLOT]
```

Per-feature opt-in: `docs/feature/{id}/distill/at-completeness-extensions.yaml` lists which overlays apply (e.g. `extensions: [nwave-installer]`).

**Example mapping**: IP/Privacy boundary (nWave domain) → instance of C5 (`public:false` mode flag) + C6 (leak-in-output as failure-contract assertion). Lives in `domain-extensions/nwave-installer.yaml`, NOT in canonical taxonomy.

---

## 7. Falsifier-gate (taxonomy self-pruning)

Telemetry per gate run: `(feature_id, category_id, finding_count, severity_max)` → 3-month rolling window.

| Signal | Decision |
|--------|----------|
| 3 consecutive zero-findings on category X across pilot features | **PRUNE** X from default checklist (cost ≤ benefit) |
| 1 BLOCKER found via category X | **ESCALATE** X to MANDATORY (cannot be skipped) |

This makes the taxonomy itself empirically-falsifiable. Default state: all 7 C-categories active.

**S-family exemption**: structural invariants (S1/S2/S3) are NOT subject to the falsifier-prune rule. Zero collisions / zero dormant seams across N features is the goal state, not evidence the check is wasteful. S-family stays MANDATORY unconditionally.

---

## 8. Empirical class → research category mapping (proves generality)

| Empirical class (spike-3 2026-05-19) | Research category | Notes |
|--------------------------------------|-------------------|-------|
| IP/Privacy boundary | C5 + C6 (instantiation) | Domain-specific overlay, NOT general |
| Negative paths (missing file, malformed JSON) | C6 direct | Canonical robustness/Postel |
| Idempotency (uninstall w/o install) | C4 direct | CRUD lifecycle + idempotency property |
| Mode flags (dry_run / force / verbose) | C5 direct | Decision-table coverage |
| Failure contract on degenerate state | C6 direct | FEW HICCUPPS "Claims" consistency |
| Type-domain (bool/int where str expected) | C6 direct | Type-level robustness; PBT `st.one_of` natural fit |

Empirical classes 2–6 generalize via C4+C5+C6. Class 1 (IP/Privacy) → domain extension. C1, C2, C3, C7 = categories spikes did NOT surface — predictable next adversarial-reviewer hits.

---

## References (research doc bibliography)

[1] ISTQB Foundation v4.0 §4.2 Black-Box Test Techniques (2023).
[2] Beizer, *Software Testing Techniques* 2nd ed., 1990, ch.5 Domain Testing.
[3] Hendrickson/Lyndsay/Emery, Test Heuristics Cheat Sheet, testobsessed.com / Ministry of Testing.
[4] Hypothesis stateful tests docs.
[5] Adzic, *Specification by Example*, Manning 2011.
[6] Wayne, "Property Tests + Contracts = Integration Tests", hillelwayne.com 2019.
[7] Adzic, "Focus on key examples", 2014.
[8] RFC 760 §1.2.10 Robustness Principle (Postel, IETF 1980).
[9] Bolton/Bach, "FEW HICCUPPS", DevelopSense.
[10] Kaner/Bach/Pettichord, *Lessons Learned in Software Testing*, Wiley 2001.
[11] Kaner, RIMGEA/RIMGEN bug-reporting mnemonic.
[12] Bach, Heuristic Test Strategy Model v6.3 (SFDIPOT), Satisfice.
[13] Crispin/Gregory, *Agile Testing*, Addison-Wesley 2009 (Marick quadrants synthesis).
[14] Thomson/Nottingham, "The Robustness Principle Reconsidered", CACM 2011.

Full research doc: `docs/research/at-edge-case-taxonomy-2026-05-19.md`.

# US-004 SCOPE ANALYSIS: What's Actually Needed

**Date**: 2026-01-25
**Status**: POST-CLEANUP
**Purpose**: Definire esattamente cosa serve per US-004 basandosi SOLO sulle user stories approvate

---

## USER STORIES ORIGINALI (Source of Truth)

### US-006: Turn Discipline Without max_turns

**Descrizione**: DES deve includere istruzioni di turn discipline in ogni prompt per far sì che gli agenti si autoregolino, dato che max_turns non è disponibile.

**Acceptance Criteria (SOLO questi vanno implementati)**:

| ID | AC | Implementato | Note |
|----|----|--------------| -----|
| AC-006.1 | All DES-validated prompts include TIMEOUT_INSTRUCTION section | ❓ | Da verificare |
| AC-006.2 | Turn budget (approximately 50) specified in instructions | ❓ | Da verificare |
| AC-006.3 | Progress checkpoints defined (turn ~10, ~25, ~40, ~50) | ❓ | Da verificare |
| AC-006.4 | Early exit protocol documented in prompt | ❓ | Da verificare |
| AC-006.5 | Prompt instructs agent to log turn count at each phase transition | ❓ | Da verificare |

**NON richiesto**:
- ❌ Extension API
- ❌ Possibilità di richiedere estensioni
- ❌ Approval logic per estensioni

---

## COMPONENTI IMPLEMENTATI (Audit)

### ✅ VALIDATI - In Scope

| Component | File | Purpose | User Story | Status |
|-----------|------|---------|------------|--------|
| TurnCounter | des/turn_counter.py | Track turn count per phase | US-006 (implicito) | ✅ KEEP |
| TimeoutMonitor | des/timeout_monitor.py | Elapsed time tracking | US-006 (supporto) | ✅ KEEP |
| InvocationLimitsValidator | des/invocation_limits_validator.py | Pre-invocation validation | US-006 (supporto) | ✅ KEEP |

### ❌ RIMOSSI - Out of Scope

| Component | File | Lines | Reason |
|-----------|------|-------|--------|
| ExtensionRequest | des/extension_api.py | ~152 | Non richiesto |
| ExtensionApprovalEngine | des/extension_approval.py | ~186 | Non richiesto |
| request_extension() | des/orchestrator.py | ~80 | Non richiesto |
| Extension tests | tests/* | ~800 | Non richiesto |

### ⚠️ DA VALIDARE - Boundary Case

| Component | File | Richiesto da | Necessario? |
|-----------|------|--------------|-------------|
| Wiring step 02-01 | Wire TurnCounter into orchestrator | Roadmap | ✅ SÌ - senza wiring, non funziona |
| Wiring step 04-01 | Wire TimeoutMonitor into orchestrator | Roadmap | ✅ SÌ - senza wiring, non funziona |

---

## ROADMAP CORRETTA (Solo feature richieste)

### Phase 01: Turn Limit Infrastructure ✅
- 01-01: Extend schema with turn_count ✅ COMPLETATO
- 01-02: Implement TurnCounter ✅ COMPLETATO
- 01-03: Add configurable turn limits ✅ COMPLETATO

### Phase 02: Turn Counter Wiring ✅
- 02-01: Wire TurnCounter into orchestrator ✅ COMPLETATO
- 02-02: Integrate turn limit enforcement in hook ✅ COMPLETATO

### Phase 03: Timeout Warning System ✅
- 03-01: Add timeout threshold configuration ✅ COMPLETATO
- 03-02: Implement TimeoutMonitor ✅ COMPLETATO
- 03-03: Implement timeout threshold validator ✅ COMPLETATO

### Phase 04: Timeout Wiring ✅
- 04-01: Wire TimeoutMonitor into orchestrator ✅ COMPLETATO
- 04-02: Add timeout warning to agent prompt ✅ COMPLETATO

### ~~Phase 05: Extension Request Mechanism~~ ❌ OUT OF SCOPE
- ~~05-01: Design extension request API~~ ❌ RIMOSSO
- ~~05-02: Implement extension approval logic~~ ❌ RIMOSSO
- ~~05-03: Add extension tracking~~ ❌ RIMOSSO

### ~~Phase 06: Extension API Wiring~~ ❌ OUT OF SCOPE
- ~~06-01: Add request_extension to orchestrator~~ ❌ RIMOSSO
- ~~06-02: Expose extension API to prompt~~ ❌ RIMOSSO

### Phase 07: Enforcement (NEXT STEPS)
- 07-01: Integrate timeout validation in hook ⏹️ NOT_STARTED
- 07-02: Pre-invocation validation ⏹️ NOT_STARTED

### Phase 08: E2E Wiring Tests (NEXT STEPS)
- 08-01: E2E wiring test /nw:execute ⏸️ IN_PROGRESS
- 08-02: E2E wiring test /nw:develop ⏹️ NOT_STARTED

### Phase 09: Turn Counter Validation (NEXT STEPS)
- 09-01: Validate TurnCounter logic ✅ COMPLETATO
- 09-02: Add turn counter unit tests ✅ COMPLETATO
- 09-03: Turn counter edge cases ⏹️ NOT_STARTED

### Phase 10: Timeout Validation (NEXT STEPS)
- 10-01: Validate TimeoutMonitor logic ✅ COMPLETATO
- 10-02: Add timeout monitor unit tests ⏹️ NOT_STARTED
- 10-03: Timeout monitor edge cases ⏹️ NOT_STARTED
- 10-04: Integration test timeout flow ⏹️ NOT_STARTED

### Phase 11: Documentation (NEXT STEPS)
- 11-01: Update DES design docs ✅ COMPLETATO
- 11-02: Update command templates ⏹️ NOT_STARTED
- 11-03: Create troubleshooting guide ⏹️ NOT_STARTED
- 11-04: Update evolution log ⏹️ NOT_STARTED

---

## ACCEPTANCE CRITERIA VALIDATION

### US-006 AC Check

| AC | Implementazione Richiesta | Attuale | Gap |
|----|---------------------------|---------|-----|
| AC-006.1 | TIMEOUT_INSTRUCTION in prompts | ❓ | Verificare orchestrator.render_prompt() |
| AC-006.2 | Turn budget ~50 specified | ❓ | Verificare default config |
| AC-006.3 | Checkpoints (10,25,40,50) | ❌ | NON IMPLEMENTATO |
| AC-006.4 | Early exit protocol | ❌ | NON IMPLEMENTATO |
| AC-006.5 | Log turn count at phase transition | ❓ | Verificare hook integration |

### GAP ANALYSIS

**Da implementare**:
1. ❌ Progress checkpoints nel prompt (AC-006.3)
2. ❌ Early exit protocol (AC-006.4)
3. ❓ Verifica che TIMEOUT_INSTRUCTION sia nel prompt (AC-006.1)

---

## PROSSIMI STEP (In Order)

### 1. VERIFICA AC-006.1, AC-006.2, AC-006.5
```bash
# Check se TIMEOUT_INSTRUCTION è nel prompt
grep -r "TIMEOUT_INSTRUCTION" des/
grep -r "turn.*budget.*50" des/
grep -r "turn_count" des/hooks.py
```

### 2. IMPLEMENTA AC-006.3 e AC-006.4 (se mancanti)
- Aggiungere checkpoint logic al prompt
- Aggiungere early exit protocol

### 3. COMPLETA STEP RIMANENTI
- 07-01: Timeout validation in hook
- 07-02: Pre-invocation validation
- 08-01, 08-02: E2E wiring tests
- 09-03, 10-02, 10-03, 10-04: Test completeness
- 11-02, 11-03, 11-04: Documentation

### 4. FINALIZE US-004
```bash
/nw:finalize @devop "des-us006"
```

---

## CONCLUSION

**Scope correto**: US-004 dovrebbe implementare **SOLO** turn discipline via prompt instructions e monitoring, **NON** extension request API.

**Stato attuale**: Cleanup completato, ~1300 linee di codice non richiesto rimosse.

**Prossima azione**: Verificare AC rimanenti e completare step 07-11 senza aggiungere feature non richieste.

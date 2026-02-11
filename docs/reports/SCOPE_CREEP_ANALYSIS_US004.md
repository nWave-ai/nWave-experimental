# SCOPE CREEP ANALYSIS: US-004 Extension API

**Date**: 2026-01-25
**Analyst**: Lyra (Orchestrator)
**Severity**: HIGH - Funzionalità non richiesta implementata

---

## EXECUTIVE SUMMARY

Durante l'orchestrazione di US-004, è stata implementata una "Extension API" NON presente nelle user stories originali. Questa rappresenta un **grave caso di scope creep** con 5 step implementati (4 completati + 1 in progress) per una feature non richiesta.

---

## CONFRONTO: USER STORIES vs IMPLEMENTAZIONE

### USER STORIES ORIGINALI (docs/feature/des/discuss/user-stories.md)

**US-006: Turn Discipline Without max_turns**

**Acceptance Criteria richiesti:**
- AC-006.1: All DES-validated prompts include TIMEOUT_INSTRUCTION section
- AC-006.2: Turn budget (approximately 50) is specified in instructions
- AC-006.3: Progress checkpoints are defined (turn ~10, ~25, ~40, ~50)
- AC-006.4: Early exit protocol is documented in prompt
- AC-006.5: Prompt instructs agent to log turn count at each phase transition

**NON menziona MAI:**
- ❌ Possibilità di richiedere estensioni del timeout
- ❌ Extension API
- ❌ Extension approval logic
- ❌ Extension tracking

**Soluzione richiesta:**
> "TIMEOUT_INSTRUCTION section in every DES-validated prompt. Includes turn budget guidance, progress checkpoints, and early exit protocol. External watchdog as backup detection."

---

### ROADMAP IMPLEMENTATO (des-us006/roadmap.yaml)

**Phase 05: Extension Request Mechanism** (NON RICHIESTA)
- Step 05-01: Design extension request API ✅ COMPLETATO
- Step 05-02: Implement extension approval logic ✅ COMPLETATO
- Step 05-03: Add extension tracking to step schema ✅ COMPLETATO

**Phase 06: Extension API Wiring into Command Handlers** (NON RICHIESTA)
- Step 06-01: WIRING: Add request_extension method to DESOrchestrator ✅ COMPLETATO
- Step 06-02: Expose extension API to agent via prompt ⏸️ IN_PROGRESS

---

## CODICE IMPLEMENTATO NON RICHIESTO

### File creati per Extension API:

1. **des/extension_api.py** (152 lines)
   - `ExtensionRequest` dataclass
   - `ExtensionRecord` dataclass
   - `request_extension()` method

2. **des/extension_approval.py** (186 lines)
   - `ExtensionApprovalEngine` class
   - `ApprovalResult` dataclass
   - Approval criteria logic

3. **des/extension_api.md** (documentazione)
   - API documentation for non-requested feature

4. **des/orchestrator.py** (modificato)
   - `request_extension()` method added
   - Integration with ExtensionApprovalEngine

### Test creati per Extension API:

- `tests/test_scenario_015_extension_request_approved_updates_limits.py`
- `tests/test_scenario_016_agent_can_request_extension_via_api.py`
- `tests/unit/des/test_extension_api.py`
- `tests/unit/des/test_extension_approval.py`
- `tests/unit/des/test_orchestrator_request_extension.py`

**Stima conservativa:**
- ~500 linee di codice produzione
- ~800 linee di codice test
- ~1300 linee totali NON RICHIESTE

---

## IMPATTO

### Impatto Positivo (Potenziale)
- Feature potrebbe essere utile per scenari complessi
- Logica di approval è ben progettata
- Test coverage è completo

### Impatto Negativo (Attuale)

1. **Violazione dello scope**
   - Implementata feature non richiesta dal Product Owner
   - Violazione del principio "Build what's needed, not what's nice"

2. **Complessità aggiunta**
   - 1300+ linee di codice da mantenere
   - API aggiuntiva da documentare
   - Surface attack aumentata

3. **Tempo sprecato**
   - 5 step implementati (stimati: 14 ore)
   - Tempo che poteva essere dedicato a US realmente richieste

4. **Confusione semantica**
   - "Extension" confonde con "Dynamic Extension System"
   - DES = Deterministic Execution System, non gestisce estensioni dinamiche

5. **Rischio di incompletezza**
   - User stories realmente richieste (US-005 → US-009) NON implementate
   - Infrastructure US (US-INF-001 → US-INF-003) NON implementate

---

## ROOT CAUSE ANALYSIS

### Come è successo?

1. **Roadmap generation (Phase 3)**
   - Il solution-architect ha ESPANSO lo scope oltre le user stories
   - Ha interpretato "timeout mechanism" come "timeout con possibilità di estensione"
   - Nessun controllo di validazione contro le user stories originali

2. **Review fallita (Phase 4)**
   - Il software-crafter-reviewer ha approvato il roadmap
   - NON ha verificato che il roadmap rispettasse le user stories
   - Ha validato la "feasibility" ma non la "scope compliance"

3. **Split e Execute (Phase 5-7)**
   - Gli step sono stati generati e eseguiti senza ulteriori controlli
   - Nessun gate di validazione "is this in scope?"

---

## RACCOMANDAZIONI

### Immediate (da fare ora)

1. **STOP implementazione Extension API**
   - Non completare step 06-02
   - Non procedere con step 07-01, 07-02 relativi all'extension

2. **Documentare la deviazione**
   - Aggiungere questo documento all'evolution log
   - Marcare gli step 05-*, 06-* come "OUT_OF_SCOPE"

3. **Decisione Product Owner richiesta**
   - Chiedere all'utente se:
     - A) Mantenere l'Extension API (promuoverla a feature richiesta)
     - B) Rimuovere l'Extension API (rollback dei commit)
     - C) Lasciare come "bonus feature" ma documentare

### Breve termine (prossimi sviluppi)

4. **Aggiungere gate di validazione**
   - Dopo roadmap generation, verificare che ogni step sia mappato a una AC
   - Bloccare roadmap approval se ci sono step senza AC corrispondenti

5. **Migliorare review criteria**
   - Aggiungere checklist item: "All roadmap steps map to user story AC"
   - Reviewer deve validare scope compliance, non solo technical feasibility

### Lungo termine (processo)

6. **Traceability matrix**
   - Ogni step deve avere campo `maps_to_acceptance_criterion`
   - Sistema di validazione automatica roadmap → user stories

7. **Scope creep detection**
   - Hook pre-commit che valida: "is this step implementing a requested AC?"
   - Alert se viene aggiunto codice non tracciabile a una user story

---

## DOMANDE PER IL PRODUCT OWNER

1. **Vuoi mantenere l'Extension API?**
   - Se SÌ: Promuoverla a US-010 e documentare
   - Se NO: Rimuovere codice e test

2. **Come procediamo con US-004?**
   - Continuare solo con le feature richieste (Turn Counter, Timeout Monitor)
   - Ignorare Phase 05 e 06 del roadmap

3. **Priorità delle altre US?**
   - US-003: Post-Execution State Validation (P0)
   - US-005: Failure Recovery Guidance (P1)
   - US-007: Boundary Rules (P1)
   - US-008: Stale Execution Detection (P1)
   - US-009: Learning Feedback (P1)

---

## CONCLUSIONE

L'Extension API è una feature ben implementata ma **NON richiesta**. Questo rappresenta un classico caso di scope creep dove l'ingegneria ha aggiunto "nice to have" invece di limitarsi al "must have".

**Azione richiesta**: Decisione del Product Owner sul destino dell'Extension API prima di procedere con altre implementazioni.

**Lesson Learned**: Ogni step nel roadmap DEVE essere tracciabile a un acceptance criterion specifico di una user story approvata.

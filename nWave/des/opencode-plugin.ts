// nWave DES Plugin for OpenCode
// Deterministic Execution System -- TDD phase enforcement, audit logging, state management
//
// Single-file plugin: zero external dependencies, only fs and path from Bun/Node built-ins.
// Architecture: Pure functions compose into hook handlers. Policy encoded as data, not branches.
//
// Components:
//   1. Hook Router       -- Routes OpenCode hook events to enforcement logic
//   2. State Manager     -- Loads/saves DES session from deliver-session.json (atomic rename)
//   3. Phase Enforcer    -- Validates tool calls against current phase policy matrix
//   4. File Classifier   -- Determines if a path is test or production code (pure)
//   5. Audit Writer      -- Appends JSONL audit entries to des-audit.jsonl
//   6. Phase Transition Manager -- Validates and executes phase transitions
//   7. Stale Session Detector   -- Detects stale sessions by elapsed time (pure)
//   8. Compaction Handler       -- Injects DES state into compaction context
//   9. Custom Tools             -- des_create_session, des_advance_phase

import type { Plugin } from "@opencode-ai/plugin"
import {
  readFileSync,
  writeFileSync,
  renameSync,
  existsSync,
  mkdirSync,
} from "fs"
import { join, basename } from "path"

// =============================================================================
// Domain Types
// =============================================================================

export type Phase =
  | "NOT_STARTED"
  | "PREPARE"
  | "RED_ACCEPTANCE"
  | "RED_UNIT"
  | "GREEN"
  | "COMMIT"
  | "COMPLETED"

export type ToolCategory = "writeTest" | "writeProd" | "editTest" | "editProd" | "bash" | "readOnly"

export type FileKind = "test" | "production"

export type StaleSeverity = "none" | "warning" | "error"

interface StalenessResult {
  readonly stale: boolean
  readonly severity: StaleSeverity
  readonly message: string
}

interface PhaseHistoryEntry {
  readonly phase: Phase
  readonly timestamp: string
  readonly evidence: string
}

interface DESSession {
  readonly featureId: string
  readonly stepId: string
  readonly currentPhase: Phase
  readonly turnCount: number
  readonly startedAt: string
  readonly phaseHistory: ReadonlyArray<PhaseHistoryEntry>
  readonly filesModified: ReadonlyArray<string>
  readonly testsRan: boolean
}

interface AuditEntry {
  readonly event: string
  readonly timestamp: string
  readonly [key: string]: unknown
}

interface EnforcementResult {
  readonly allowed: boolean
  readonly reason: string
}

interface TransitionResult {
  readonly success: boolean
  readonly message: string
  readonly session?: DESSession
}

// =============================================================================
// Constants
// =============================================================================

const SESSION_FILENAME = "deliver-session.json"
const SESSION_TMP_FILENAME = "deliver-session.json.tmp"
const AUDIT_FILENAME = "des-audit.jsonl"
const DES_DIR_SEGMENTS = [".nwave", "des"] as const
const AUDIT_DIR_SEGMENTS = [".nwave", "des", "logs"] as const
const READ_RETRY_DELAY_MS = 50

const FOUR_HOURS_MS = 4 * 60 * 60 * 1000
const TWENTY_FOUR_HOURS_MS = 24 * 60 * 60 * 1000

// =============================================================================
// 4. File Classifier (Pure)
// =============================================================================

const TEST_DIR_PATTERNS: ReadonlyArray<string> = ["/tests/", "/test/", "/__tests__/"]

const TEST_FILE_PATTERNS: ReadonlyArray<RegExp> = [
  /^test_/,       // test_foo.py
  /_test\./,      // foo_test.py, foo_test.ts
  /\.test\./,     // foo.test.ts, foo.test.js
  /\.spec\./,     // foo.spec.ts, foo.spec.js
]

const TEST_INFRA_PATTERNS: ReadonlyArray<string> = ["conftest"]

export const classifyFile = (filePath: string): FileKind => {
  const normalizedPath = filePath.replace(/\\/g, "/")
  const fileName = basename(normalizedPath)

  const isInTestDir = TEST_DIR_PATTERNS.some((pattern) =>
    normalizedPath.includes(pattern)
  )
  if (isInTestDir) return "test"

  const matchesTestFilePattern = TEST_FILE_PATTERNS.some((pattern) =>
    pattern.test(fileName)
  )
  if (matchesTestFilePattern) return "test"

  const isTestInfra = TEST_INFRA_PATTERNS.some((pattern) =>
    fileName.includes(pattern)
  )
  if (isTestInfra) return "test"

  return "production"
}

const isTestFile = (filePath: string): boolean =>
  classifyFile(filePath) === "test"

const isProductionFile = (filePath: string): boolean =>
  classifyFile(filePath) === "production"

// =============================================================================
// 7. Stale Session Detector (Pure)
// =============================================================================

export const detectStaleness = (startedAt: string, now: Date): StalenessResult => {
  const startTime = new Date(startedAt).getTime()
  const elapsed = now.getTime() - startTime

  if (elapsed > TWENTY_FOUR_HOURS_MS) {
    return {
      stale: true,
      severity: "error",
      message:
        `DES session started ${Math.floor(elapsed / 3_600_000)}h ago (> 24h). ` +
        `Consider resetting: call des_create_session to start a fresh session.`,
    }
  }

  if (elapsed > FOUR_HOURS_MS) {
    return {
      stale: true,
      severity: "warning",
      message:
        `DES session started ${Math.floor(elapsed / 3_600_000)}h ago (> 4h). ` +
        `Session may be stale.`,
    }
  }

  return { stale: false, severity: "none", message: "" }
}

// =============================================================================
// Phase Policy Matrix (Data, not logic)
// =============================================================================

// Policy: true = allowed, false = blocked
// Rows: phases. Columns: tool categories.
const PHASE_POLICY: Record<Phase, Record<ToolCategory, boolean>> = {
  NOT_STARTED: {
    writeTest: true,
    writeProd: true,
    editTest: true,
    editProd: true,
    bash: true,
    readOnly: true,
  },
  PREPARE: {
    writeTest: true,
    writeProd: true,
    editTest: true,
    editProd: true,
    bash: true,
    readOnly: true,
  },
  RED_ACCEPTANCE: {
    writeTest: true,
    writeProd: false,
    editTest: true,
    editProd: false,
    bash: true,
    readOnly: true,
  },
  RED_UNIT: {
    writeTest: true,
    writeProd: false,
    editTest: true,
    editProd: false,
    bash: true,
    readOnly: true,
  },
  GREEN: {
    writeTest: false,
    writeProd: true,
    editTest: false,
    editProd: true,
    bash: true,
    readOnly: true,
  },
  COMMIT: {
    writeTest: false,
    writeProd: false,
    editTest: true,
    editProd: true,
    bash: true,
    readOnly: true,
  },
  COMPLETED: {
    writeTest: true,
    writeProd: true,
    editTest: true,
    editProd: true,
    bash: true,
    readOnly: true,
  },
}

// =============================================================================
// Phase Transition Rules (Data)
// =============================================================================

const VALID_TRANSITIONS: Record<Phase, ReadonlyArray<Phase>> = {
  NOT_STARTED: ["PREPARE"],
  PREPARE: ["RED_ACCEPTANCE"],
  RED_ACCEPTANCE: ["RED_UNIT", "PREPARE"],
  RED_UNIT: ["GREEN"],
  GREEN: ["COMMIT"],
  COMMIT: ["COMPLETED"],
  COMPLETED: [],
}

// =============================================================================
// Tool Category Classification (Pure)
// =============================================================================

export const classifyToolCall = (
  toolName: string,
  filePath: string | undefined
): ToolCategory => {
  const readOnlyTools = ["read", "glob", "grep"]
  if (readOnlyTools.includes(toolName)) return "readOnly"
  if (toolName === "bash") return "bash"

  if (toolName === "write" && filePath) {
    return isTestFile(filePath) ? "writeTest" : "writeProd"
  }

  if (toolName === "edit" && filePath) {
    return isTestFile(filePath) ? "editTest" : "editProd"
  }

  // Unknown tools: treat as readOnly (fail-open)
  return "readOnly"
}

// =============================================================================
// 3. Phase Enforcer (Pure)
// =============================================================================

export const enforcePhasePolicy = (
  phase: Phase,
  toolCategory: ToolCategory,
  toolName: string,
  filePath: string | undefined
): EnforcementResult => {
  const phasePolicy = PHASE_POLICY[phase]
  if (!phasePolicy) {
    return { allowed: true, reason: "Unknown phase -- fail-open" }
  }

  const allowed = phasePolicy[toolCategory]
  if (allowed) {
    return { allowed: true, reason: "" }
  }

  // Build descriptive error messages per phase category
  const fileDescription = filePath ? ` '${filePath}'` : ""

  if (phase === "RED_ACCEPTANCE" || phase === "RED_UNIT") {
    if (toolCategory === "writeProd" || toolCategory === "editProd") {
      return {
        allowed: false,
        reason:
          `Cannot modify production file${fileDescription} during ${phase} phase. ` +
          `Only test files may be written or edited in RED phases.`,
      }
    }
  }

  if (phase === "GREEN") {
    if (toolCategory === "writeTest" || toolCategory === "editTest") {
      return {
        allowed: false,
        reason:
          `Cannot modify test file${fileDescription} during GREEN phase. ` +
          `Only production files may be written or edited in GREEN phase.`,
      }
    }
  }

  if (phase === "COMMIT") {
    if (toolCategory === "writeTest" || toolCategory === "writeProd") {
      return {
        allowed: false,
        reason:
          `Cannot create new files during COMMIT phase. ` +
          `Only edits to existing files are allowed.`,
      }
    }
  }

  return {
    allowed: false,
    reason: `Tool '${toolName}' is blocked during ${phase} phase.`,
  }
}

// =============================================================================
// 6. Phase Transition Manager (Pure logic, impure wiring)
// =============================================================================

export const validateTransition = (
  currentPhase: Phase,
  nextPhase: Phase,
  evidence: string
): TransitionResult => {
  if (!evidence || evidence.trim().length === 0) {
    return {
      success: false,
      message: "Evidence string is required for phase transitions.",
    }
  }

  const allowedNextPhases = VALID_TRANSITIONS[currentPhase]
  if (!allowedNextPhases) {
    return {
      success: false,
      message: `Unknown current phase: ${currentPhase}`,
    }
  }

  if (!allowedNextPhases.includes(nextPhase)) {
    const allowedList =
      allowedNextPhases.length > 0
        ? allowedNextPhases.join(", ")
        : "none (phase complete)"
    return {
      success: false,
      message:
        `Invalid transition: ${currentPhase} -> ${nextPhase}. ` +
        `Allowed transitions from ${currentPhase}: ${allowedList}`,
    }
  }

  return { success: true, message: `Phase advanced to ${nextPhase}` }
}

const applyTransition = (
  session: DESSession,
  nextPhase: Phase,
  evidence: string
): DESSession => ({
  ...session,
  currentPhase: nextPhase,
  phaseHistory: [
    ...session.phaseHistory,
    {
      phase: nextPhase,
      timestamp: new Date().toISOString(),
      evidence,
    },
  ],
})

// =============================================================================
// 5. Audit Writer (Side-effect boundary)
// =============================================================================

const buildAuditEntry = (
  fields: Record<string, unknown>,
  session: DESSession | null
): AuditEntry => ({
  ...fields,
  ...(session
    ? { featureId: session.featureId, stepId: session.stepId }
    : {}),
  timestamp: new Date().toISOString(),
  event: fields.event as string,
})

const writeAuditEntry = (directory: string, entry: AuditEntry): void => {
  try {
    const logDir = join(directory, ...AUDIT_DIR_SEGMENTS)
    if (!existsSync(logDir)) {
      mkdirSync(logDir, { recursive: true })
    }
    const logFile = join(logDir, AUDIT_FILENAME)
    const line = JSON.stringify(entry) + "\n"
    writeFileSync(logFile, line, { flag: "a" })
  } catch (e) {
    console.error("nWave DES: Audit write failed:", e)
  }
}

// =============================================================================
// 2. State Manager (Side-effect boundary, atomic writes)
// =============================================================================

const desDir = (directory: string): string =>
  join(directory, ...DES_DIR_SEGMENTS)

const sessionFilePath = (directory: string): string =>
  join(desDir(directory), SESSION_FILENAME)

const sessionTmpFilePath = (directory: string): string =>
  join(desDir(directory), SESSION_TMP_FILENAME)

const parseSessionJson = (raw: string): DESSession | null => {
  try {
    const parsed = JSON.parse(raw)
    // Minimal validation: must have currentPhase
    if (typeof parsed.currentPhase !== "string") return null
    return parsed as DESSession
  } catch {
    return null
  }
}

const loadSession = (directory: string): DESSession | null => {
  const filePath = sessionFilePath(directory)
  if (!existsSync(filePath)) return null

  try {
    const raw = readFileSync(filePath, "utf-8")
    const session = parseSessionJson(raw)
    if (session) return session

    // Retry once after delay (race condition recovery for mid-rename reads)
    const sleepSync = (ms: number) => {
      const end = Date.now() + ms
      while (Date.now() < end) {
        // busy-wait for sync retry
      }
    }
    sleepSync(READ_RETRY_DELAY_MS)

    const rawRetry = readFileSync(filePath, "utf-8")
    return parseSessionJson(rawRetry)
  } catch {
    return null
  }
}

const saveSession = (directory: string, session: DESSession): void => {
  try {
    const dir = desDir(directory)
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true })
    }

    const tmpPath = sessionTmpFilePath(directory)
    const targetPath = sessionFilePath(directory)
    const content = JSON.stringify(session, null, 2) + "\n"

    // Atomic write: write to temp, then rename
    writeFileSync(tmpPath, content, "utf-8")
    renameSync(tmpPath, targetPath)
  } catch (e) {
    console.error("nWave DES: State write failed:", e)
  }
}

const createSession = (
  directory: string,
  featureId: string,
  stepId: string
): DESSession => {
  const session: DESSession = {
    featureId,
    stepId,
    currentPhase: "NOT_STARTED",
    turnCount: 0,
    startedAt: new Date().toISOString(),
    phaseHistory: [],
    filesModified: [],
    testsRan: false,
  }
  saveSession(directory, session)
  return session
}

const incrementTurnCount = (session: DESSession): DESSession => ({
  ...session,
  turnCount: session.turnCount + 1,
})

const addModifiedFile = (
  session: DESSession,
  filePath: string
): DESSession => {
  if (session.filesModified.includes(filePath)) return session
  return {
    ...session,
    filesModified: [...session.filesModified, filePath],
  }
}

const markTestsRan = (session: DESSession): DESSession => ({
  ...session,
  testsRan: true,
})

// =============================================================================
// Test Run Detection (Pure)
// =============================================================================

const TEST_COMMAND_PATTERNS: ReadonlyArray<string> = [
  "pytest",
  "npm test",
  "npm run test",
  "yarn test",
  "bun test",
  "jest",
  "vitest",
  "mocha",
  "dotnet test",
  "cargo test",
  "go test",
  "mix test",
  "rspec",
]

const isTestCommand = (command: string): boolean =>
  TEST_COMMAND_PATTERNS.some((pattern) => command.includes(pattern))

// =============================================================================
// 1. Hook Router (Wiring -- plugin entry point)
// =============================================================================

const plugin: Plugin = async ({ directory }) => {
  // Helper: log audit with session context
  const logAudit = (
    fields: Record<string, unknown>,
    session: DESSession | null
  ): void => {
    const entry = buildAuditEntry(fields, session)
    writeAuditEntry(directory, entry)
  }

  return {
    // -----------------------------------------------------------------
    // tool.execute.before -- Phase Enforcement (Hook Router -> Phase Enforcer)
    // -----------------------------------------------------------------
    "tool.execute.before": async (input, output) => {
      const session = loadSession(directory)

      // Fail-open: no active session means no enforcement
      if (!session) return

      // Stale session detection
      const staleness = detectStaleness(session.startedAt, new Date())
      if (staleness.stale) {
        logAudit(
          {
            event: "stale_session_detected",
            severity: staleness.severity,
            message: staleness.message,
            phase: session.currentPhase,
          },
          session
        )

        if (staleness.severity === "error") {
          // Don't block, but log prominently -- the agent should see the audit trail
          // For error-level staleness, we log but still enforce phase rules
        }
      }

      // Increment turn count
      const updatedSession = incrementTurnCount(session)
      saveSession(directory, updatedSession)

      // Extract file path from tool arguments
      const filePath =
        (output.args as Record<string, unknown>)?.filePath as
          | string
          | undefined

      // Classify the tool call
      const toolCategory = classifyToolCall(input.tool, filePath)

      // Enforce phase policy
      const enforcement = enforcePhasePolicy(
        session.currentPhase,
        toolCategory,
        input.tool,
        filePath
      )

      if (!enforcement.allowed) {
        logAudit(
          {
            event: "tool_blocked",
            tool: input.tool,
            phase: session.currentPhase,
            file: filePath,
            reason: enforcement.reason,
          },
          session
        )
        throw new Error(`DES: ${enforcement.reason}`)
      }
    },

    // -----------------------------------------------------------------
    // tool.execute.after -- Audit Logging + File Tracking
    // -----------------------------------------------------------------
    "tool.execute.after": async (input) => {
      const session = loadSession(directory)
      if (!session) return

      let updatedSession = session

      // Track file modifications from write/edit tools
      const filePath =
        ((input as Record<string, unknown>).args as Record<string, unknown>)
          ?.filePath as string | undefined
      if (filePath && (input.tool === "write" || input.tool === "edit")) {
        updatedSession = addModifiedFile(updatedSession, filePath)
      }

      // Track test runs from bash tool
      if (input.tool === "bash") {
        const command =
          ((input as Record<string, unknown>).args as Record<string, unknown>)
            ?.command as string | undefined
        if (command && isTestCommand(command)) {
          updatedSession = markTestsRan(updatedSession)
        }
      }

      // Persist state changes if any
      if (updatedSession !== session) {
        saveSession(directory, updatedSession)
      }

      logAudit(
        {
          event: "tool_executed",
          tool: input.tool,
          phase: session.currentPhase,
        },
        session
      )
    },

    // -----------------------------------------------------------------
    // stop -- Subagent Stop Validation
    // -----------------------------------------------------------------
    stop: async (input) => {
      const session = loadSession(directory)
      if (!session) return

      // Log the stop event
      logAudit(
        {
          event: "session_stop",
          phase: session.currentPhase,
          turnCount: session.turnCount,
          filesModified: session.filesModified.length,
          testsRan: session.testsRan,
        },
        session
      )
    },

    // -----------------------------------------------------------------
    // experimental.session.compacting -- Context Preservation
    // -----------------------------------------------------------------
    "experimental.session.compacting": async (_input, output) => {
      const session = loadSession(directory)
      if (!session) return

      const desContext =
        `<des-state>\n` +
        `Feature: ${session.featureId}\n` +
        `Step: ${session.stepId}\n` +
        `Phase: ${session.currentPhase}\n` +
        `Turn: ${session.turnCount}\n` +
        `Files modified: ${session.filesModified.join(", ") || "(none)"}\n` +
        `Tests ran: ${session.testsRan}\n` +
        `Started: ${session.startedAt}\n` +
        `</des-state>`

      output.context.push(desContext)
    },

    // -----------------------------------------------------------------
    // Custom Tools -- des_create_session, des_advance_phase
    // -----------------------------------------------------------------
    tool: {
      des_create_session: {
        description:
          "Create a new DES session for TDD phase enforcement. " +
          "Call this before dispatching a subagent for a deliver step.",
        parameters: {
          type: "object",
          properties: {
            featureId: {
              type: "string",
              description: "Feature identifier (e.g., 'opencode-des')",
            },
            stepId: {
              type: "string",
              description: "Step identifier (e.g., '01-03')",
            },
          },
          required: ["featureId", "stepId"],
        },
        async execute(args: { featureId: string; stepId: string }) {
          if (!args.featureId || args.featureId.trim().length === 0) {
            return "Error: featureId is required and must be non-empty."
          }
          if (!args.stepId || args.stepId.trim().length === 0) {
            return "Error: stepId is required and must be non-empty."
          }

          const existingSession = loadSession(directory)
          if (existingSession) {
            logAudit(
              {
                event: "session_replaced",
                previousFeatureId: existingSession.featureId,
                previousStepId: existingSession.stepId,
                previousPhase: existingSession.currentPhase,
              },
              existingSession
            )
          }

          const session = createSession(
            directory,
            args.featureId.trim(),
            args.stepId.trim()
          )

          logAudit(
            {
              event: "session_created",
              featureId: session.featureId,
              stepId: session.stepId,
            },
            session
          )

          return (
            `DES session created: feature=${session.featureId}, ` +
            `step=${session.stepId}, phase=NOT_STARTED. ` +
            `Call des_advance_phase("PREPARE", "reason") to begin.`
          )
        },
      },

      des_advance_phase: {
        description:
          "Advance to the next TDD phase. " +
          "Valid transitions: NOT_STARTED->PREPARE, PREPARE->RED_ACCEPTANCE, " +
          "RED_ACCEPTANCE->RED_UNIT|PREPARE, RED_UNIT->GREEN, GREEN->COMMIT, COMMIT->COMPLETED.",
        parameters: {
          type: "object",
          properties: {
            nextPhase: {
              type: "string",
              description:
                "Target phase (PREPARE, RED_ACCEPTANCE, RED_UNIT, GREEN, COMMIT, COMPLETED)",
            },
            evidence: {
              type: "string",
              description: "Evidence that current phase requirements are met",
            },
          },
          required: ["nextPhase", "evidence"],
        },
        async execute(args: { nextPhase: string; evidence: string }) {
          const session = loadSession(directory)
          if (!session) {
            return "Error: No active DES session. Call des_create_session first."
          }

          const nextPhase = args.nextPhase as Phase
          const transitionResult = validateTransition(
            session.currentPhase,
            nextPhase,
            args.evidence
          )

          if (!transitionResult.success) {
            logAudit(
              {
                event: "transition_rejected",
                from: session.currentPhase,
                to: args.nextPhase,
                reason: transitionResult.message,
              },
              session
            )
            return `Error: ${transitionResult.message}`
          }

          const updatedSession = applyTransition(
            session,
            nextPhase,
            args.evidence
          )
          saveSession(directory, updatedSession)

          logAudit(
            {
              event: "phase_advanced",
              from: session.currentPhase,
              to: nextPhase,
              evidence: args.evidence,
            },
            updatedSession
          )

          return transitionResult.message
        },
      },
    },
  }
}

export default plugin

/**
 * Unit tests for the pure functions in the nWave DES OpenCode plugin.
 *
 * Tests cover the five pure function groups:
 *   1. classifyFile    -- file path -> test | production
 *   2. detectStaleness -- elapsed time -> none | warning | error
 *   3. enforcePhasePolicy -- phase + tool -> allowed | blocked
 *   4. validateTransition -- current phase + next phase -> success | failure
 *   5. classifyToolCall   -- tool name + file path -> tool category
 *
 * No OpenCode runtime required -- these are pure functions with no IO.
 */

import { describe, expect, test } from "bun:test"
import {
  classifyFile,
  classifyToolCall,
  detectStaleness,
  enforcePhasePolicy,
  validateTransition,
} from "./opencode-plugin"
import type { Phase, ToolCategory } from "./opencode-plugin"

// =============================================================================
// classifyFile
// =============================================================================

describe("classifyFile", () => {
  test("classifies files in /tests/ directory as test", () => {
    expect(classifyFile("/project/tests/unit/test_foo.py")).toBe("test")
    expect(classifyFile("/project/tests/integration/adapter.py")).toBe("test")
  })

  test("classifies files in /test/ directory as test", () => {
    expect(classifyFile("/project/test/helpers.ts")).toBe("test")
  })

  test("classifies files in /__tests__/ directory as test", () => {
    expect(classifyFile("/project/src/__tests__/app.test.ts")).toBe("test")
  })

  test("classifies test_ prefixed files as test", () => {
    expect(classifyFile("/project/src/test_calculator.py")).toBe("test")
  })

  test("classifies _test. suffixed files as test", () => {
    expect(classifyFile("/project/src/calculator_test.py")).toBe("test")
    expect(classifyFile("/project/src/calculator_test.ts")).toBe("test")
  })

  test("classifies .test. files as test", () => {
    expect(classifyFile("/project/src/calculator.test.ts")).toBe("test")
    expect(classifyFile("/project/src/calculator.test.js")).toBe("test")
  })

  test("classifies .spec. files as test", () => {
    expect(classifyFile("/project/src/calculator.spec.ts")).toBe("test")
    expect(classifyFile("/project/src/calculator.spec.js")).toBe("test")
  })

  test("classifies conftest files as test", () => {
    expect(classifyFile("/project/conftest.py")).toBe("test")
    expect(classifyFile("/project/tests/conftest.py")).toBe("test")
  })

  test("classifies production source files as production", () => {
    expect(classifyFile("/project/src/calculator.py")).toBe("production")
    expect(classifyFile("/project/src/domain/order.ts")).toBe("production")
    expect(classifyFile("/project/lib/utils.js")).toBe("production")
  })

  test("classifies files with 'test' in directory name but not pattern as production", () => {
    expect(classifyFile("/project/src/contest/results.py")).toBe("production")
    expect(classifyFile("/project/src/latest/data.ts")).toBe("production")
  })

  test("handles Windows-style backslash paths", () => {
    expect(classifyFile("C:\\project\\tests\\unit\\test_foo.py")).toBe("test")
    expect(classifyFile("C:\\project\\src\\calculator.py")).toBe("production")
  })

  test("handles edge case of empty-ish paths", () => {
    expect(classifyFile("test_foo.py")).toBe("test")
    expect(classifyFile("foo.py")).toBe("production")
  })
})

// =============================================================================
// detectStaleness
// =============================================================================

describe("detectStaleness", () => {
  test("returns none for sessions under 4 hours", () => {
    const now = new Date("2026-03-03T12:00:00Z")
    const startedAt = "2026-03-03T09:00:00Z" // 3 hours ago

    const result = detectStaleness(startedAt, now)

    expect(result.stale).toBe(false)
    expect(result.severity).toBe("none")
    expect(result.message).toBe("")
  })

  test("returns none for sessions exactly at the boundary (just under 4h)", () => {
    const now = new Date("2026-03-03T12:00:00Z")
    const startedAt = "2026-03-03T08:00:01Z" // 3h 59m 59s ago

    const result = detectStaleness(startedAt, now)

    expect(result.stale).toBe(false)
    expect(result.severity).toBe("none")
  })

  test("returns warning for sessions between 4 and 24 hours", () => {
    const now = new Date("2026-03-03T20:00:00Z")
    const startedAt = "2026-03-03T10:00:00Z" // 10 hours ago

    const result = detectStaleness(startedAt, now)

    expect(result.stale).toBe(true)
    expect(result.severity).toBe("warning")
    expect(result.message).toContain("stale")
  })

  test("returns error for sessions over 24 hours", () => {
    const now = new Date("2026-03-04T20:00:00Z")
    const startedAt = "2026-03-03T10:00:00Z" // 34 hours ago

    const result = detectStaleness(startedAt, now)

    expect(result.stale).toBe(true)
    expect(result.severity).toBe("error")
    expect(result.message).toContain("24h")
    expect(result.message).toContain("des_create_session")
  })

  test("returns warning right at 4 hours boundary", () => {
    const now = new Date("2026-03-03T14:00:01Z")
    const startedAt = "2026-03-03T10:00:00Z" // 4h 0m 1s ago

    const result = detectStaleness(startedAt, now)

    expect(result.stale).toBe(true)
    expect(result.severity).toBe("warning")
  })
})

// =============================================================================
// enforcePhasePolicy
// =============================================================================

describe("enforcePhasePolicy", () => {
  test("RED phases block production file writes", () => {
    const result = enforcePhasePolicy(
      "RED_UNIT",
      "writeProd",
      "write",
      "/src/app.ts"
    )

    expect(result.allowed).toBe(false)
    expect(result.reason).toContain("production file")
    expect(result.reason).toContain("RED_UNIT")
  })

  test("RED phases block production file edits", () => {
    const result = enforcePhasePolicy(
      "RED_ACCEPTANCE",
      "editProd",
      "edit",
      "/src/app.ts"
    )

    expect(result.allowed).toBe(false)
    expect(result.reason).toContain("production file")
  })

  test("RED phases allow test file writes", () => {
    const result = enforcePhasePolicy(
      "RED_UNIT",
      "writeTest",
      "write",
      "/tests/test_app.py"
    )

    expect(result.allowed).toBe(true)
  })

  test("GREEN phase blocks test file writes", () => {
    const result = enforcePhasePolicy(
      "GREEN",
      "writeTest",
      "write",
      "/tests/test_app.py"
    )

    expect(result.allowed).toBe(false)
    expect(result.reason).toContain("test file")
    expect(result.reason).toContain("GREEN")
  })

  test("GREEN phase blocks test file edits", () => {
    const result = enforcePhasePolicy(
      "GREEN",
      "editTest",
      "edit",
      "/tests/test_app.py"
    )

    expect(result.allowed).toBe(false)
    expect(result.reason).toContain("test file")
  })

  test("GREEN phase allows production file writes", () => {
    const result = enforcePhasePolicy(
      "GREEN",
      "writeProd",
      "write",
      "/src/app.ts"
    )

    expect(result.allowed).toBe(true)
  })

  test("COMMIT phase blocks new file creation", () => {
    const writeTestResult = enforcePhasePolicy(
      "COMMIT",
      "writeTest",
      "write",
      "/tests/test_new.py"
    )
    const writeProdResult = enforcePhasePolicy(
      "COMMIT",
      "writeProd",
      "write",
      "/src/new_module.py"
    )

    expect(writeTestResult.allowed).toBe(false)
    expect(writeTestResult.reason).toContain("COMMIT")
    expect(writeProdResult.allowed).toBe(false)
  })

  test("COMMIT phase allows edits to existing files", () => {
    const editTestResult = enforcePhasePolicy(
      "COMMIT",
      "editTest",
      "edit",
      "/tests/test_app.py"
    )
    const editProdResult = enforcePhasePolicy(
      "COMMIT",
      "editProd",
      "edit",
      "/src/app.ts"
    )

    expect(editTestResult.allowed).toBe(true)
    expect(editProdResult.allowed).toBe(true)
  })

  test("all phases allow bash and readOnly tools", () => {
    const phases: Phase[] = [
      "NOT_STARTED", "PREPARE", "RED_ACCEPTANCE",
      "RED_UNIT", "GREEN", "COMMIT", "COMPLETED",
    ]

    for (const phase of phases) {
      expect(enforcePhasePolicy(phase, "bash", "bash", undefined).allowed).toBe(true)
      expect(enforcePhasePolicy(phase, "readOnly", "read", undefined).allowed).toBe(true)
    }
  })

  test("NOT_STARTED and PREPARE allow all operations", () => {
    const permissivePhases: Phase[] = ["NOT_STARTED", "PREPARE"]
    const categories: ToolCategory[] = [
      "writeTest", "writeProd", "editTest", "editProd", "bash", "readOnly",
    ]

    for (const phase of permissivePhases) {
      for (const category of categories) {
        expect(enforcePhasePolicy(phase, category, "write", "/any/file").allowed).toBe(true)
      }
    }
  })
})

// =============================================================================
// validateTransition
// =============================================================================

describe("validateTransition", () => {
  test("allows valid forward transitions", () => {
    const validTransitions: Array<[Phase, Phase]> = [
      ["NOT_STARTED", "PREPARE"],
      ["PREPARE", "RED_ACCEPTANCE"],
      ["RED_ACCEPTANCE", "RED_UNIT"],
      ["RED_UNIT", "GREEN"],
      ["GREEN", "COMMIT"],
      ["COMMIT", "COMPLETED"],
    ]

    for (const [from, to] of validTransitions) {
      const result = validateTransition(from, to, "Tests pass")
      expect(result.success).toBe(true)
    }
  })

  test("allows RED_ACCEPTANCE to PREPARE (retry path)", () => {
    const result = validateTransition(
      "RED_ACCEPTANCE",
      "PREPARE",
      "Restarting from prepare"
    )

    expect(result.success).toBe(true)
  })

  test("rejects invalid transitions", () => {
    const invalidTransitions: Array<[Phase, Phase]> = [
      ["NOT_STARTED", "GREEN"],
      ["PREPARE", "GREEN"],
      ["RED_UNIT", "COMMIT"],
      ["GREEN", "RED_UNIT"],
      ["COMMIT", "GREEN"],
      ["COMPLETED", "NOT_STARTED"],
    ]

    for (const [from, to] of invalidTransitions) {
      const result = validateTransition(from, to, "Some evidence")
      expect(result.success).toBe(false)
      expect(result.message).toContain("Invalid transition")
    }
  })

  test("rejects transitions with empty evidence", () => {
    const result = validateTransition("NOT_STARTED", "PREPARE", "")

    expect(result.success).toBe(false)
    expect(result.message).toContain("Evidence")
  })

  test("rejects transitions with whitespace-only evidence", () => {
    const result = validateTransition("NOT_STARTED", "PREPARE", "   ")

    expect(result.success).toBe(false)
    expect(result.message).toContain("Evidence")
  })

  test("COMPLETED has no valid outgoing transitions", () => {
    const phases: Phase[] = [
      "NOT_STARTED", "PREPARE", "RED_ACCEPTANCE",
      "RED_UNIT", "GREEN", "COMMIT", "COMPLETED",
    ]

    for (const target of phases) {
      const result = validateTransition("COMPLETED", target, "Try to escape")
      expect(result.success).toBe(false)
    }
  })

  test("error message lists allowed transitions", () => {
    const result = validateTransition(
      "RED_ACCEPTANCE",
      "GREEN",
      "Skipping unit tests"
    )

    expect(result.success).toBe(false)
    expect(result.message).toContain("RED_UNIT")
    expect(result.message).toContain("PREPARE")
  })
})

// =============================================================================
// classifyToolCall
// =============================================================================

describe("classifyToolCall", () => {
  test("classifies read tools as readOnly", () => {
    expect(classifyToolCall("read", undefined)).toBe("readOnly")
    expect(classifyToolCall("glob", undefined)).toBe("readOnly")
    expect(classifyToolCall("grep", undefined)).toBe("readOnly")
  })

  test("classifies bash as bash", () => {
    expect(classifyToolCall("bash", undefined)).toBe("bash")
  })

  test("classifies write to test file as writeTest", () => {
    expect(classifyToolCall("write", "/project/tests/test_app.py")).toBe("writeTest")
    expect(classifyToolCall("write", "/project/src/app.test.ts")).toBe("writeTest")
  })

  test("classifies write to production file as writeProd", () => {
    expect(classifyToolCall("write", "/project/src/app.ts")).toBe("writeProd")
    expect(classifyToolCall("write", "/project/lib/utils.py")).toBe("writeProd")
  })

  test("classifies edit to test file as editTest", () => {
    expect(classifyToolCall("edit", "/project/tests/test_app.py")).toBe("editTest")
  })

  test("classifies edit to production file as editProd", () => {
    expect(classifyToolCall("edit", "/project/src/app.ts")).toBe("editProd")
  })

  test("classifies unknown tools as readOnly (fail-open)", () => {
    expect(classifyToolCall("unknown_tool", undefined)).toBe("readOnly")
    expect(classifyToolCall("custom_tool", "/some/file")).toBe("readOnly")
  })

  test("classifies write without filePath as readOnly", () => {
    expect(classifyToolCall("write", undefined)).toBe("readOnly")
  })

  test("classifies edit without filePath as readOnly", () => {
    expect(classifyToolCall("edit", undefined)).toBe("readOnly")
  })
})

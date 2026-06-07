"""Tests for OpenCode platform contract validation.

Validates that validate_des_template() correctly detects anomalies
in the DES plugin template and reports zero findings for a compliant template.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Add scripts to path for importing validation module
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from validation.validate_platform_contracts import validate_des_template  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

COMPLIANT_TEMPLATE = """\
/**
 * nWave DES Plugin for OpenCode
 */

import type { Plugin } from "@opencode-ai/plugin";

const TOOL_MAP: Record<string, { action: string; toolName: string }> = {
  task:  { action: "pre-task",  toolName: "Agent" },
  write: { action: "pre-write", toolName: "Write" },
  edit:  { action: "pre-write", toolName: "Edit"  },
};

function translateEvent(
  tool: string,
  input: Record<string, unknown>,
): { action: string; ccJson: Record<string, unknown> } | null {
  const mapping = TOOL_MAP[tool];
  if (!mapping) return null;
  return { action: mapping.action, ccJson: { tool_name: mapping.toolName, tool_input: input } };
}

async function invokeDESAdapter(
  action: string,
  ccJson: Record<string, unknown>,
): Promise<{ exitCode: number; stdout: string; stderr: string }> {
  const proc = Bun.spawn(
    ["{{PYTHON_PATH}}", "-m", "des.adapters.drivers.hooks.claude_code_hook_adapter", action],
    { stdin: new Blob([JSON.stringify(ccJson)]), stdout: "pipe", stderr: "pipe",
      env: { ...process.env, PYTHONPATH: "{{PYTHONPATH}}" } },
  );
  const exitCode = await proc.exited;
  const stdout = await new Response(proc.stdout).text();
  const stderr = await new Response(proc.stderr).text();
  return { exitCode, stdout, stderr };
}

export default function nwaveDES(_ctx: Plugin) {
  return {
    "session.created": async (_event: Record<string, unknown>) => {
      try { await invokeDESAdapter("session-start", {}); } catch (err) {
        console.error(`[nWave DES] Session start error: ${err}`);
      }
    },

    "tool.execute.before": async (input: { tool: string; args: Record<string, unknown> }, output: Record<string, unknown>) => {
      const translated = translateEvent(input.tool, output.args ?? {});
      if (!translated) return;
      try {
        const result = await invokeDESAdapter(translated.action, translated.ccJson);
        if (result.exitCode === 2) {
          let reason = "DES enforcement blocked this action";
          try { const parsed = JSON.parse(result.stdout); if (parsed.reason) reason = parsed.reason; } catch {}
          throw new Error(reason);
        }
      } catch (err) {
        if (err instanceof Error && err.message.startsWith("DES")) throw err;
        console.error(`[nWave DES] Subprocess error (fail-open): ${err}`);
      }
    },
  };
}
"""

ANOMALY_3_TEMPLATE = """\
import type { PluginContext } from "opencode";

export default function nwaveDES(_ctx: PluginContext) {
  return {
    "tool.execute.before": async (input: { tool: string }, output: { args: Record<string, unknown> }) => {},
  };
}
"""

ANOMALY_4_TEMPLATE = """\
import type { Plugin } from "@opencode-ai/plugin";

export default function nwaveDES(_ctx: Plugin) {
  return {
    "tool.execute.before": async (input: { tool: string; is_subagent?: boolean }, output: { args: Record<string, unknown> }) => {
      if (input.is_subagent) return;
    },
  };
}
"""

ANOMALY_5_TEMPLATE = """\
import type { Plugin } from "@opencode-ai/plugin";

export default function nwaveDES(_ctx: Plugin) {
  return {
    "tool.execute.before": async (event: {
      tool: string;
      input: Record<string, unknown>;
    }) => {
      const tool = event.tool;
    },
  };
}
"""


# ---------------------------------------------------------------------------
# ANOMALY-3: Import contract
# ---------------------------------------------------------------------------


class TestAnomaly3ImportContract:
    """DES template must import Plugin from '@opencode-ai/plugin'."""

    def test_detects_wrong_import(self) -> None:
        findings = validate_des_template(ANOMALY_3_TEMPLATE)
        anomaly_3 = [f for f in findings if f.anomaly_id == "ANOMALY-3"]
        assert len(anomaly_3) == 1
        assert "PluginContext" in anomaly_3[0].message

    def test_passes_correct_import(self) -> None:
        findings = validate_des_template(COMPLIANT_TEMPLATE)
        anomaly_3 = [f for f in findings if f.anomaly_id == "ANOMALY-3"]
        assert len(anomaly_3) == 0


# ---------------------------------------------------------------------------
# ANOMALY-4: No is_subagent references
# ---------------------------------------------------------------------------


class TestAnomaly4NoIsSubagent:
    """DES template must not reference is_subagent anywhere."""

    def test_detects_is_subagent_references(self) -> None:
        findings = validate_des_template(ANOMALY_4_TEMPLATE)
        anomaly_4 = [f for f in findings if f.anomaly_id == "ANOMALY-4"]
        assert len(anomaly_4) == 1
        assert "is_subagent" in anomaly_4[0].message

    def test_passes_without_is_subagent(self) -> None:
        findings = validate_des_template(COMPLIANT_TEMPLATE)
        anomaly_4 = [f for f in findings if f.anomaly_id == "ANOMALY-4"]
        assert len(anomaly_4) == 0


# ---------------------------------------------------------------------------
# ANOMALY-5: Two-parameter handler signature
# ---------------------------------------------------------------------------


class TestAnomaly5TwoParameterSignature:
    """tool.execute.before must use two-parameter (input, output) signature."""

    def test_detects_single_parameter_signature(self) -> None:
        findings = validate_des_template(ANOMALY_5_TEMPLATE)
        anomaly_5 = [f for f in findings if f.anomaly_id == "ANOMALY-5"]
        assert len(anomaly_5) == 1
        assert "single-parameter" in anomaly_5[0].message

    def test_passes_two_parameter_signature(self) -> None:
        findings = validate_des_template(COMPLIANT_TEMPLATE)
        anomaly_5 = [f for f in findings if f.anomaly_id == "ANOMALY-5"]
        assert len(anomaly_5) == 0


# ---------------------------------------------------------------------------
# Integration: compliant template passes all checks
# ---------------------------------------------------------------------------


class TestCompliantTemplate:
    """A fully compliant template should produce zero findings."""

    def test_passes_compliant_template(self) -> None:
        findings = validate_des_template(COMPLIANT_TEMPLATE)
        assert len(findings) == 0, (
            f"Expected zero findings but got: "
            f"{[f'{f.anomaly_id}: {f.message}' for f in findings]}"
        )


# ---------------------------------------------------------------------------
# Integration: current template (before fix) has findings
# ---------------------------------------------------------------------------


class TestActualTemplateCompliance:
    """The shipped template should be fully compliant (zero findings)."""

    def test_current_template_has_anomalies(self) -> None:
        template_path = (
            PROJECT_ROOT / "nWave" / "templates" / "opencode-des-plugin.ts.template"
        )
        assert template_path.is_file(), f"Template file not found: {template_path}"
        content = template_path.read_text(encoding="utf-8")
        findings = validate_des_template(content)
        # After ANOMALY-3,4,5 fixes, template should be fully compliant
        assert len(findings) == 0, (
            f"Template has {len(findings)} finding(s): "
            f"{[f'{f.anomaly_id}: {f.message}' for f in findings]}"
        )

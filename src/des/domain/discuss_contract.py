"""The one public description of the DISCUSS input contract (help, docs, tests)."""

from __future__ import annotations

import json


CURRENT_VERSION = 2
LEGACY_VERSIONS = (1,)
SECTION_NAMES = ("jtbd", "journey", "gherkin", "quint_scenarios")
DESCRIBE_FLAG = "des discuss --describe-input"
EXAMPLE_MARKER = "EXAMPLE (minimal, copyable):"

# Minimal valid input: core fields plus every section explicitly unexpanded.
MINIMAL_EXAMPLE: dict[str, object] = {
    "schema_version": CURRENT_VERSION,
    "request": "Let a user choose a widget color.",
    "outcomes": ["A user can choose a widget color."],
    "scope": {
        "in_scope": ["Widget color selection."],
        "out_of_scope": {
            "applicability": "not_applicable",
            "reason": "No exclusions are needed.",
            "items": [],
        },
    },
    "decisions": ["Open: which colors are offered."],
    "values": [
        {"observation": "A user can select a widget color.", "dependencies": []}
    ],
    "jtbd": {"status": "not_explored"},
    "journey": {"status": "not_explored"},
    "gherkin": {"status": "not_explored"},
    "quint_scenarios": {"status": "not_run"},
}

DESCRIPTION = f"""\
DISCUSS input: one JSON object, schema_version {CURRENT_VERSION} (current).
Legacy schema_version {LEGACY_VERSIONS[0]} is still accepted unchanged (its four
sections are optional and untagged); it is never migrated automatically.

Required keys: schema_version, request, outcomes, scope, decisions, values,
{", ".join(SECTION_NAMES)}. Unknown keys are refused, and nothing is written when
any part is invalid.
  request      non-empty string          outcomes/decisions  non-empty string arrays
  scope        {{"in_scope": [...], "out_of_scope": {{"applicability":
               "applicable"|"not_applicable", "reason": str, "items": [...]}}}}
               (items non-empty exactly when applicable)
  values       ordered [{{"observation": str, "dependencies": [earlier observations]}}]

Each section is ALWAYS rendered; state explicitly what you did:
  jtbd             {{"status": "not_explored"}}
                   | {{"status": "provided", "human": [JOB], "llm": [JOB]}}  (>= 1 list)
                   JOB = {{"job": str, "status": proposed|confirmed|open}}
  journey          {{"status": "not_explored"}}
                   | {{"status": "provided", "steps": [{{"step": str,
                     "human_emotion": str (optional, human only), "status": S}}]}}
  gherkin          {{"status": "not_explored"}}
                   | {{"status": "provided", "scenarios": [{{"scenario": str,
                     "steps": [one-line str, no code fence], "status": S}}]}}
  quint_scenarios  {{"status": "not_run"}}
                   | {{"status": "generated", "model": {{"path","identity"}},
                     "tool": {{"name","version","command"}}, "trace": {{"path"}},
                     "scenarios": [{{"title": str, "events": [{{"trace_index": int>=0,
                     "text": str}}]}}]}}   (only with real Quint tool output)
S = proposed | confirmed | open. Never invent emotions or Quint output. Quint is
never required. DES records the evidence; it does not run or verify Quint.
"""


def describe_input() -> str:
    """Full contract text followed by the minimal example, for ``--describe-input``."""
    return f"{DESCRIPTION}\n{EXAMPLE_MARKER}\n{json.dumps(MINIMAL_EXAMPLE, indent=2)}\n"


HELP_EPILOG = (
    f"Input: closed JSON, schema_version {CURRENT_VERSION} (legacy "
    f"{LEGACY_VERSIONS[0]} accepted). Required: schema_version request outcomes "
    f"scope decisions values {' '.join(SECTION_NAMES)}; each section is explicit "
    '({"status":"not_explored"} / "provided"; quint_scenarios "not_run" / '
    f'"generated"). Full schema and a copyable example: `{DESCRIBE_FLAG}`.'
)

HOW_TO_FIX = (
    f"run `{DESCRIBE_FLAG}` for the schema and a minimal valid example, "
    "then pipe the corrected JSON into des discuss --input -"
)

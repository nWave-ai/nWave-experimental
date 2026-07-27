"""Read-only classification and rendering for initial feature contexts."""

from __future__ import annotations

import json
from dataclasses import dataclass


_SCHEMA_VERSION = "1"
_MARKER = "<!-- des-feature-context-bootstrap: "


@dataclass(frozen=True)
class BootstrapContext:
    feature_id: str
    intent: str
    state: str
    inventory: tuple[dict[str, str], ...]


def render(context: BootstrapContext) -> str:
    """Render the sole durable bootstrap artifact deterministically."""
    metadata = json.dumps(
        {
            "feature_id": context.feature_id,
            "intent": context.intent,
            "inventory": context.inventory,
            "schema_version": _SCHEMA_VERSION,
            "state": context.state,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        f"{_MARKER}{metadata} -->\n"
        f"# Feature context: {context.feature_id}\n\n"
        f"Intent: {context.intent}\n"
    )


def classify(content: str, feature_id: str) -> BootstrapContext | None:
    """Return only an exact bootstrap artifact; ordinary deltas remain unclassified."""
    first_line, _, _ = content.partition("\n")
    if not first_line.startswith(_MARKER) or not first_line.endswith(" -->"):
        return None
    try:
        payload = json.loads(first_line[len(_MARKER) : -4])
        context = BootstrapContext(
            feature_id=payload["feature_id"],
            intent=payload["intent"],
            state=payload["state"],
            inventory=tuple(payload["inventory"]),
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    if (
        payload.get("schema_version") != _SCHEMA_VERSION
        or context.feature_id != feature_id
        or context.state not in {"OPEN", "ADOPTED_WIP"}
        or content != render(context)
    ):
        return None
    return context

"""Generic deterministic prompt generator (no model call).

Used by ``des handoff prompt``; the host invokes models, never this generator.

templates/NAME.tmpl       prompt text with {{field}}, {{field|bullets}}, {{field|csv}},
                          {{@block}} (text sourced from a DES command), {{role}}
templates/NAME.spec.json  {"role", "required": {field: "str"|"list"}, "blocks": {name: {"argv", "from"}},
                          "must_contain": [...]}

Strict by design: unknown placeholder, missing/extra/mistyped fixture field, or an empty DES
block is an error. Same template + fixture + DES contract text -> same bytes.

The optional caller-owned used_fields set records fixture fields actually substituted,
not merely required by the spec. Callers use root_input consumption to assign literal
ROOT placement; fixture values and caller text are not scanned for matching content.
"""

import json
import re
from pathlib import Path

from des.adapters.driven.task_invocation.role_instructions import (
    _PREFIXES,
    _portable_reads,
)
from des.runtime.packaged_asset import resolve_packaged_asset


PLACEHOLDER = re.compile(r"\{\{\s*(@?[A-Za-z_][A-Za-z0-9_]*)(?:\|([a-z]+))?\s*\}\}")


class PromptError(Exception):
    pass


# Template data, asset location, explicit blocks and host instruction paths are
# independently declared inputs; this boundary must not read ambient substitutes.
def render(  # noqa: PLR0913
    name,
    fixture,
    *,
    directory=None,
    blocks=None,
    root=None,
    role_id=None,
    skills_directory=None,
    used_fields=None,
):
    if directory is None:
        resolution = resolve_packaged_asset(
            "nWave/templates/architect-handoff", start=root
        )
        if not resolution.is_usable:
            raise PromptError(
                f"WHAT: prompt templates unavailable: {resolution.detail}. "
                "WHY: no unambiguous template input was supplied. "
                "HOW: pass --template-dir naming the intended shipped template directory."
            )
        directory = resolution.path
    directory = Path(directory)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        raise PromptError("template name must be a shipped basename, not a path")
    spec = json.loads((directory / f"{name}.spec.json").read_bytes().decode("utf-8"))
    tmpl = (directory / f"{name}.tmpl").read_bytes().decode("utf-8")
    if any(prefix in tmpl for prefix in _PREFIXES):
        if skills_directory is None:
            resolution = resolve_packaged_asset("nWave/skills", start=root)
            if not resolution.is_usable:
                raise PromptError(
                    f"WHAT: declared skill input unavailable: {resolution.detail}. "
                    "WHY: measured instructions need a real host skill tree. "
                    "HOW: pass --skills-dir naming that installed skill directory."
                )
            skills_directory = resolution.path
        # Rewrite instruction paths before root insertion: caller text remains
        # verbatim even when it happens to name the same historical paths.
        tmpl = _portable_reads(tmpl, Path(skills_directory))
    required = spec["required"]
    missing = sorted(set(required) - set(fixture))
    extra = sorted(set(fixture) - set(required))
    if missing or extra:
        raise PromptError(f"fixture mismatch: missing={missing} extra={extra}")
    for field, kind in required.items():
        v = fixture[field]
        ok = (
            isinstance(v, str) and v.strip()
            if kind == "str"
            else isinstance(v, list)
            and v
            and all(isinstance(i, str) and i.strip() for i in v)
        )
        if not ok:
            raise PromptError(f"field {field!r} must be a non-empty {kind}")
    blocks = blocks or {}
    if set(blocks) != set(spec.get("blocks", {})):
        raise PromptError(
            "template blocks must be supplied explicitly; no DES command is auto-run"
        )

    def sub(m):
        key, flt = m.group(1), m.group(2)
        if key == "role":
            return role_id if role_id is not None else spec["role"]
        if key.startswith("@"):
            if key[1:] not in blocks:
                raise PromptError(f"unknown block {key!r}")
            return blocks[key[1:]]
        if key not in fixture:
            raise PromptError(f"unknown placeholder {key!r}")
        v = fixture[key]
        if used_fields is not None:
            used_fields.add(key)
        if flt == "bullets":
            return "\n".join("- " + i for i in v)
        if flt == "csv":
            return ", ".join(v)
        if flt is None:
            if isinstance(v, list):
                raise PromptError(f"list field {key!r} needs a |bullets or |csv filter")
            return v
        raise PromptError(f"unknown filter {flt!r}")

    text = PLACEHOLDER.sub(sub, tmpl)
    if "{{" in PLACEHOLDER.sub("", tmpl):
        raise PromptError("unresolved placeholder left in output")
    return text, spec

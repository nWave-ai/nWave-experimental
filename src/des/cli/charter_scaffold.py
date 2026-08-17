"""Create one value-side expectation charter for a DeliveryContract.

The command owns no workflow state and reads no design or implementation
artifact.  It copies one immutable value statement into one direct member of
``docs/product/expectations/<delivery-id>/``.  A fresh product owner fills the
remaining source-blind observations before ``des dispatch`` may reuse it.
"""

from __future__ import annotations

import argparse
import re
import stat
import sys
from pathlib import Path

from des.cli._scaffold_core import (
    ACCEPTED_VERDICT,
    decide_on_exists,
    emit_scaffold_verdict,
)
from des.runtime.packaged_asset import AssetOrigin, resolve_packaged_asset


VERDICT_AMBIGUOUS_CHARTER_TEMPLATE = "ambiguous-charter-template"
VERDICT_MISSING_CHARTER_TEMPLATE = "missing-charter-template"
VERDICT_INVALID_DELIVERY_ID = "invalid-delivery-id"
VERDICT_INVALID_REPO_ROOT = "invalid-repo-root"
VERDICT_MISSING_VALUE = "missing-value"
VERDICT_UNSAFE_VALUE = "unsafe-value"

_TEMPLATE_RELATIVE_PATH = Path("nWave/templates/expectation-charter.md")
_TEMPLATE_HEADING = "## Template"
_DELIVERY_ID = re.compile(r"[a-z0-9][a-z0-9-]*\Z")
_MAX_FILENAME_LENGTH = 100
_SUFFIX = ".md"
_MAX_SLUG_LENGTH = _MAX_FILENAME_LENGTH - len(_SUFFIX)


def _kebab_slug(value: str) -> str:
    """Return one deterministic, bounded, filesystem-safe intent slug."""
    normalized = re.sub(r"[^A-Za-z0-9\s-]", "", value).strip().lower()
    slug = re.sub(r"[-\s]+", "-", normalized).strip("-")
    if not slug:
        return ""
    if len(slug) <= _MAX_SLUG_LENGTH:
        return slug
    truncated = slug[:_MAX_SLUG_LENGTH].rstrip("-")
    boundary = truncated.rfind("-")
    return truncated[:boundary] if boundary > 0 else truncated


def _extract_template_skeleton(template_content: str) -> str:
    """Extract the fenced canonical skeleton, or accept a bare fixture."""
    lines = template_content.splitlines()
    try:
        heading = lines.index(_TEMPLATE_HEADING)
    except ValueError:
        return template_content
    fence_start = next(
        (i for i in range(heading + 1, len(lines)) if lines[i].startswith("```")),
        None,
    )
    if fence_start is None:
        return template_content
    fence_end = next(
        (i for i in range(fence_start + 1, len(lines)) if lines[i].startswith("```")),
        None,
    )
    if fence_end is None:
        return template_content
    return "\n".join(lines[fence_start + 1 : fence_end]) + "\n"


def _replace_heading_and_identity(
    skeleton: str, *, delivery_id: str, value: str
) -> str:
    """Fill only producer-owned identity and immutable intent fields."""
    lines = skeleton.splitlines()
    output: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("# "):
            output.append(f"# {value}")
            index += 1
            continue
        if line.startswith("ID:"):
            output.append(f"ID: {delivery_id} · Persona: <who>")
            index += 1
            continue
        output.append(line)
        index += 1
        if line.strip() != "## Intent":
            continue
        while index < len(lines) and not lines[index].startswith("## "):
            index += 1
        output.append(value)
        output.append("")
    return "\n".join(output).rstrip() + "\n"


def _degrade(delivery_id: str, verdict: str, detail: str) -> int:
    return emit_scaffold_verdict(
        {
            "delivery_id": delivery_id,
            "created": [],
            "skipped": [],
            "verdict": verdict,
            "detail": detail,
        }
    )


def _template(repo_root: Path, delivery_id: str) -> tuple[str | None, int | None]:
    installed = Path(__file__).resolve().parents[3] / _TEMPLATE_RELATIVE_PATH
    checkout = repo_root / _TEMPLATE_RELATIVE_PATH
    resolution = resolve_packaged_asset(
        str(_TEMPLATE_RELATIVE_PATH), start=repo_root, installed=installed
    )
    if resolution.origin is AssetOrigin.AMBIGUOUS:
        return None, _degrade(
            delivery_id,
            VERDICT_AMBIGUOUS_CHARTER_TEMPLATE,
            "WHAT: installed and checkout expectation-charter templates differ. "
            "WHY: silently choosing one would create a charter the operator did "
            "not intend. HOW: reconcile the copies and rerun. "
            f"installed={resolution.installed}; checkout={resolution.repo}",
        )
    if resolution.is_usable:
        assert resolution.path is not None
        try:
            return _extract_template_skeleton(
                resolution.path.read_text(encoding="utf-8")
            ), None
        except OSError as error:
            detail = f"template cannot be read ({error})"
    else:
        detail = f"template absent at {installed} and {checkout}"
    return None, _degrade(
        delivery_id,
        VERDICT_MISSING_CHARTER_TEMPLATE,
        f"WHAT: {detail}. WHY: charter shape is unavailable. "
        "HOW: reinstall nWave or restore the canonical template.",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des charter-scaffold",
        description=(
            "Create one source-blind expectation charter from an explicit "
            "DeliveryContract identity and value statement."
        ),
    )
    parser.add_argument("--delivery-id", required=True)
    parser.add_argument("--value", required=True)
    parser.add_argument(
        "--repo-root",
        required=True,
        type=Path,
        help="Absolute physical repository root; never inferred from cwd.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    delivery_id: str = args.delivery_id
    repo_root: Path = args.repo_root
    value: str = args.value

    if not _DELIVERY_ID.fullmatch(delivery_id):
        return _degrade(
            delivery_id,
            VERDICT_INVALID_DELIVERY_ID,
            "WHAT: --delivery-id is not schema-valid. WHY: it cannot safely "
            "name the DeliveryContract namespace. HOW: use lowercase letters, "
            "digits and hyphens, starting with a letter or digit.",
        )
    try:
        root_stat = repo_root.lstat()
    except OSError as error:
        return _degrade(
            delivery_id,
            VERDICT_INVALID_REPO_ROOT,
            f"WHAT: --repo-root cannot be read ({error}). WHY: output identity "
            "would be ambiguous. HOW: pass an existing absolute repository root.",
        )
    if (
        not repo_root.is_absolute()
        or not stat.S_ISDIR(root_stat.st_mode)
        or repo_root.is_symlink()
    ):
        return _degrade(
            delivery_id,
            VERDICT_INVALID_REPO_ROOT,
            "WHAT: --repo-root is not an absolute physical directory. WHY: "
            "output identity must not depend on cwd or symlink resolution. HOW: "
            "pass the absolute physical repository root.",
        )
    if not value.strip():
        return _degrade(
            delivery_id,
            VERDICT_MISSING_VALUE,
            "WHAT: --value is blank. WHY: a charter cannot invent user value. "
            "HOW: pass the immutable value-side intent verbatim.",
        )
    slug = _kebab_slug(value)
    if not slug:
        return _degrade(
            delivery_id,
            VERDICT_UNSAFE_VALUE,
            "WHAT: --value cannot produce a safe filename. WHY: a blank or "
            "symbol-only slug is not a stable charter identity. HOW: include "
            "a short ASCII intent phrase in the value statement.",
        )

    skeleton, error = _template(repo_root, delivery_id)
    if error is not None:
        return error
    assert skeleton is not None

    relative = Path("docs/product/expectations") / delivery_id / f"{slug}{_SUFFIX}"
    target = repo_root / relative
    if decide_on_exists(target_exists=target.exists(), policy="skip") == "skip":
        created: list[str] = []
        skipped = [relative.as_posix()]
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            _replace_heading_and_identity(
                skeleton, delivery_id=delivery_id, value=value
            ),
            encoding="utf-8",
        )
        created = [relative.as_posix()]
        skipped = []
    return emit_scaffold_verdict(
        {
            "delivery_id": delivery_id,
            "created": created,
            "skipped": skipped,
            "verdict": ACCEPTED_VERDICT,
            "detail": "created" if created else "already exists; preserved",
        }
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

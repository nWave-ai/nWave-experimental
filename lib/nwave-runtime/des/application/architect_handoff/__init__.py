"""Native projection and storage of the evaluated typed architect handoff.

DES constructs these values and observes explicit caller effects. It invokes
neither models nor a delivery route. The accumulated handover remains the SSOT.
"""

from __future__ import annotations

import contextlib
import dataclasses as dc
import json
import typing as t
from typing import TYPE_CHECKING

from . import g10_codec as C
from . import g10_project as P
from . import g10_types as T
from .g10_defect import Defect, report


if TYPE_CHECKING:
    from pathlib import Path

    from des.application.handover import StoredHandover


# Published identities are translated here only. Internal views remain private
# to the migrated implementation, not compatibility aliases for public roles.
ROLE_VIEWS = {
    "nw-solution-architect": "architect",
    "nw-product-owner": "product_owner",
    "nw-acceptance-designer": "atd",
    "nw-acceptance-designer-reviewer": "atd_reviewer",
    "nw-software-crafter": "software_crafter",
    "nw-functional-software-crafter": "functional_crafter",
    "nw-software-crafter-reviewer": "reviewer",
    "nw-user-examiner": "examiner",
}


def decode(raw: object) -> T.Handoff:
    """Use the original closed constructor; never extract typed facts from prose."""
    handoff, defects = C.decode_handoff(raw)
    if handoff is None:
        raise ValueError(report(defects))
    return handoff


def wire(handoff: T.Handoff) -> dict:
    return C.to_json(handoff)


def decode_receipts(raw: object) -> tuple[T.Run, ...]:
    handoff = decode(
        {
            "sections": [
                {
                    "kind": "receipts",
                    "scope": "shared",
                    "status": {"tag": "applicable", "payload": {"runs": raw}},
                }
            ]
        }
    )
    return handoff[("receipts", "shared")].status.payload.runs


def accumulated(stored: StoredHandover) -> T.Handoff:
    """Join typed DESIGN deltas and driven receipts without dropping older facts."""
    from des.ports.driven_ports.task_invocation_port import DesignFacts

    handoff: T.Handoff = {}
    if stored.shared_design is not None:
        handoff = C.merge(handoff, stored.shared_design.design.architect_handoff or {})
    for value in stored.values:
        if isinstance(value.authority, DesignFacts):
            handoff = C.merge(handoff, value.authority.architect_handoff or {})
    if stored.architect_receipts:
        entry = handoff.get(("receipts", "shared"))
        runs = (
            entry.status.payload.runs
            if entry is not None and isinstance(entry.status, T.Applicable)
            else ()
        )
        # Receipt recording is an explicit replacement effect, not a merge of
        # conflicting semantic sections. Authored claims remain until replaced.
        by_id = C.index_by(runs, lambda run: run.id)
        by_id.update({run.id: run for run in stored.architect_receipts})
        handoff = C.replace(
            handoff,
            T.Entry(
                kind="receipts",
                scope="shared",
                status=T.Applicable(payload=T.Receipts(runs=tuple(by_id.values()))),
            ),
        )
    return handoff


def projection(
    role_id: str,
    handoff: T.Handoff,
    *,
    value: int | None = None,
    targets: tuple[str, ...] | None = None,
    base_dir: str | None = None,
) -> list[dict[str, object]]:
    """Expose exactly the original consumer views, including UNASSESSED markers."""
    role = ROLE_VIEWS[role_id.partition("#")[0]]
    return [
        {
            "kind": kind,
            "scope": scope,
            "sha256": digest,
            "view": view,
            "content": content,
        }
        for kind, scope, digest, view, content in P.project(
            handoff, role, value, targets, base_dir
        )
    ]


# Role, typed authority, scoped projection and verbatim caller inputs are separate
# design inputs; grouping them would obscure the evidence boundary.
def compose(  # noqa: PLR0913
    role_id: str,
    handoff: T.Handoff,
    template: str,
    *,
    root_context: str,
    context: dict[str, str] | None = None,
    value: int | None = None,
    targets: tuple[str, ...] | None = None,
    base_dir: str | None = None,
    prepared_projection: list[dict[str, object]] | None = None,
) -> str:
    """Retain verbatim root bytes; the prototype's optional stripping is not used."""
    role = ROLE_VIEWS[role_id.partition("#")[0]]
    rows = (
        projection(role_id, handoff, value=value, targets=targets, base_dir=base_dir)
        if prepared_projection is None
        else prepared_projection
    )
    grammar = (
        P.grammar_what(role)
        .replace("python3 g10.py", "des handoff")
        .replace("g10.py", "des handoff")
    )
    grammar = grammar.replace(
        "the rules are checked when you submit",
        "cross-section checks run only on explicit des handoff check",
    ).replace(
        "Checked when you submit (des handoff check FILE... --targets PATHS)",
        "Explicit advisory check (des handoff check --targets PATHS)",
    )
    parts = [f"=== [T] WHAT ({role}) ===\n{template}\n{grammar}"]
    for row in rows:
        parts.append(
            f"=== [H] {row['kind']}@{row['scope']} sha={row['sha256'][:12]} view={row['view']} ===\n"
            + json.dumps(
                row["content"],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
        )
    caller = "\n".join(
        f"{key}: {(context or {})[key]}" for key in sorted(context or {})
    )
    parts.append(
        "=== [C] orchestrator ===\n" + caller + ("\n" if caller else "") + root_context
    )
    return "\n".join(parts) + "\n"


class HandoverReceiptStore:
    """Snapshot-bound driven receipt writer using the native graph CAS and lock."""

    def __init__(self, root: Path, stored: StoredHandover):
        self.root = root
        self.stored = stored

    @staticmethod
    def _refuse(what: str, why: str, how: str) -> None:
        from .g10_run import RunError

        raise RunError(Defect("RUN5", ".nwave/des/handover.json", what, why, how))

    def load(self) -> tuple[T.Run, ...]:
        from des.application.handover import handover_unchanged

        failure = handover_unchanged(self.root, self.stored.raw)
        if failure is not None:
            self._refuse(failure.what, failure.why, failure.how)
        try:
            handoff = accumulated(self.stored)
        except ValueError as error:
            self._refuse(
                f"typed handoff cannot be accumulated: {error}",
                "a receipt must bind to one unambiguous graph snapshot",
                "reconcile the conflicting typed sections through des design",
            )
        return tuple(
            run
            for (kind, _), entry in handoff.items()
            if kind == "receipts" and isinstance(entry.status, T.Applicable)
            for run in entry.status.payload.runs
        )

    def append(
        self,
        run: T.Run,
        *,
        replace: bool = False,
        publication: contextlib.AbstractContextManager[None] | None = None,
    ) -> None:
        from des.application.handover import (
            Blocked,
            StoredHandover,
            acquire_delivery_lock,
            bind_architect_receipts,
            stored_handover,
        )

        from .g10_run import RunError

        lock = acquire_delivery_lock(self.root)
        if isinstance(lock, Blocked):
            self._refuse(lock.what, lock.why, lock.how)
        try:
            known = self.load()
            if any(old.id == run.id for old in known) and not replace:
                raise RunError(
                    Defect(
                        "RUN2",
                        run.id,
                        "the receipt id is already recorded",
                        "a run id names one observed or declared execution",
                        "use a new --id or explicitly pass --replace",
                    )
                )
            runs = (
                *(old for old in self.stored.architect_receipts if old.id != run.id),
                run,
            )
            # Snapshot and ID are reserved before the command's artifact is published.
            # Unwind only when a re-read proves the original graph is still visible.
            # A rename followed by fsync failure may already have published the receipt.
            uncertain = None
            with publication if publication is not None else contextlib.nullcontext():
                updated = bind_architect_receipts(self.root, self.stored, runs)
                if isinstance(updated, Blocked):
                    visible = stored_handover(self.root)
                    if (
                        isinstance(visible, StoredHandover)
                        and visible.raw == self.stored.raw
                    ):
                        self._refuse(updated.what, updated.why, updated.how)
                    uncertain = updated
                    if (
                        isinstance(visible, StoredHandover)
                        and run in visible.architect_receipts
                    ):
                        self.stored = visible
                else:
                    self.stored = updated
            if uncertain is not None:
                self._refuse(
                    uncertain.what,
                    f"{uncertain.why}; receipt publication may already be visible and "
                    "its durability is uncertain; matching evidence has been retained",
                    f"inspect the handover and receipt artifacts before retrying; {uncertain.how}",
                )
        finally:
            lock.release()


def input_schema() -> dict:
    """Project the migrated closed record grammar into the native provider schema."""

    def shape(tp, metadata=None):
        metadata = metadata or {}
        origin = t.get_origin(tp)
        if C.is_union(origin):
            return {"anyOf": [shape(arg) for arg in t.get_args(tp)]}
        if origin is t.Literal:
            return {"type": "string", "enum": list(t.get_args(tp))}
        if origin is tuple:
            item_meta = (
                {"allow_blank": True, "pattern": T.ARGV_DATA_RE}
                if metadata.get("literal_argv")
                else None
            )
            result = {"type": "array", "items": shape(t.get_args(tp)[0], item_meta)}
            if metadata.get("literal_argv"):
                result["prefixItems"] = [shape(str, {"pattern": T.ARGV_EXECUTABLE_RE})]
            if metadata.get("nonempty"):
                result["minItems"] = 1
            return result
        if isinstance(tp, t.NewType):
            return {"type": "string", "pattern": T.PATTERNS[tp.__name__]}
        if dc.is_dataclass(tp):
            hints = t.get_type_hints(tp)
            fields = dc.fields(tp)
            return {
                "type": "object",
                "properties": {
                    field.name: shape(hints[field.name], field.metadata)
                    for field in fields
                },
                "required": [
                    field.name
                    for field in fields
                    if (
                        field.default is dc.MISSING
                        and field.default_factory is dc.MISSING
                    )
                    or field.name == "tag"
                    # Strict transports must not invent null for nonnullable defaults.
                    or type(None) not in t.get_args(hints[field.name])
                ],
                "additionalProperties": False,
            }
        if tp is type(None):
            return {"type": "null"}
        if tp is str:
            return {
                "type": "string",
                **({} if metadata.get("allow_blank") else {"minLength": 1}),
                **({"pattern": metadata["pattern"]} if "pattern" in metadata else {}),
            }
        if tp is int:
            return {
                "type": "integer",
                **({"minimum": 1} if metadata.get("positive") else {}),
            }
        if tp is float:
            return {
                "type": "number",
                **({"minimum": 0} if metadata.get("nonneg") else {}),
            }
        raise TypeError(f"unsupported architect record grammar: {tp!r}")

    entries = []
    for kind, payload in T.PAYLOAD.items():
        entries.append(
            {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": [kind]},
                    "scope": {"type": "string", "pattern": f"^(?:{T.SCOPE_RE})$"},
                    "status": {
                        "anyOf": [
                            {
                                "type": "object",
                                "properties": {
                                    "tag": {"type": "string", "enum": ["applicable"]},
                                    "payload": shape(payload),
                                },
                                "required": ["tag", "payload"],
                                "additionalProperties": False,
                            },
                            shape(T.NotApplicable),
                        ]
                    },
                },
                "required": ["kind", "scope", "status"],
                "additionalProperties": False,
            }
        )
    return {
        "type": "object",
        "properties": {"sections": {"type": "array", "items": {"anyOf": entries}}},
        "required": ["sections"],
        "additionalProperties": False,
    }

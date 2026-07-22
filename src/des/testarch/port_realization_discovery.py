"""Composition root -- resolve plugins, AST-work-probe declared-covered ports (slice-02).

language-port-realization-gate, slice-02 (DELIVER, A_GREEN). Wires the real
world (``importlib.metadata`` entry-point discovery, ``inspect``/``ast``
source reading) to the slice-01 pure detector
``des.testarch.rules.registry_conformance.detect_port_realization_conformance``.

Pipeline, per plugin:

  1. Read the plugin's self-declared ``port_coverage`` mapping
     (``LanguageAdapterPlugin.port_coverage``).
  2. Call ``plugin.register_adapters(<capturing registry>)`` with a registry
     double duck-typed against ``LanguageAdapterRegistry``'s 3 new
     ``register_contract_gate`` / ``register_environmental_e2e`` /
     ``register_robustness_density`` methods (``runner_registry.py``) --
     capturing whichever facet instance each call receives, independent of
     the ``name`` (tool-token) argument the plugin passes.
  3. For every DECLARED-covered (``True``) port, AST-probe the captured
     facet's backing method(s) for that port for EVIDENCE OF REAL WORK (see
     "The criterion" below). A port is unrealized iff ANY method its Protocol
     declares lacks that evidence (or is absent from the facet entirely) --
     a partially-backed port is not a realized port.
  4. Feed the resulting ``{plugin_id: {port: declared}}`` +
     ``{plugin_id: {port: is_stub}}`` maps to
     ``detect_port_realization_conformance`` and return its verdict.

The criterion -- EVIDENCE OF REAL WORK, not a catalogue of stub spellings
(``fix-port-realization-stub-evasion``). The probe does NOT look for the
known SHAPE of a stub; it requires proof that the method does something, and
treats a body without that proof as unrealized. So an UNFAMILIAR spelling of
fake work defaults to FLAGGED, never to bypass.

Each TOP-LEVEL statement of the method body is classified INERT or EVIDENCE;
the method is realized iff AT LEAST ONE statement is EVIDENCE. INERT is the
enumerated, closed set (4 rules) -- it is enumerable because "does nothing"
has a small provable extension, while "fakes work" does not:

  I-1  ``ast.Expr`` whose value is an ``ast.Constant`` -- a docstring, a bare
       ``...``, a bare literal. POSITION-INDEPENDENT (not merely a leading
       docstring): ``...`` followed by ``raise`` is inert, and so is a
       docstring-only body.
  I-2  ``ast.Pass``.
  I-3  ``ast.Return`` whose value is absent, or is ``None`` / ``Ellipsis`` /
       the ``NotImplemented`` singleton -- the spellings that denote "no
       answer".
  I-4  ``ast.Raise`` as a TOP-LEVEL body statement, of ANY exception type --
       an unconditional raise means the method can never succeed. TOP-LEVEL
       ONLY: a raise nested in ``if``/``try`` leaves the enclosing ``If`` /
       ``Try`` statement as EVIDENCE, so guard clauses and error-wrapping
       stay clean.

EVIDENCE is everything else (assignments, control flow, imports, asserts,
``Expr`` of a call/await/yield, a ``Return`` of anything but the I-3
singletons). EVIDENCE is the DEFAULT, so an unfamiliar REAL construct is
never falsely accused.

Each unrealized method carries a REASON CODE (``REASON_*`` below) so the
CLI's refusal can say something TRUE and SPECIFIC about WHY -- the verdict is
identical across shapes, only the message distinguishes them.

ACCEPTED RESIDUALS (known limits, deliberately not closed -- documented so
they are known rather than silent):

  * A method returning a NON-``None`` constant that fakes success (e.g.
    ``return {"verdict": "PASS"}``) counts as EVIDENCE. The lie is one of
    CONTENT, not of shape, and content is not statically decidable.
  * A body that is a single ``Expr(Call)`` (e.g. only logging) counts as
    EVIDENCE. The SHIPPED
    ``PythonEnvironmentalE2EAdapter.run_against_installed`` IS exactly one
    delegating call, so any rule excluding that shape would fire on
    production code.

Effect-Isolation (Earned-Trust 3-layer): the probe is STATIC -- it reads
source only via ``inspect.getsource`` + ``ast.parse`` and NEVER invokes
``build()``/``install()``/the probed method itself, nor any
``plugin.probe()``.

Degrade-LOUD: an unresolvable (``OSError``/``TypeError`` from
``inspect.getsource``) or unparsable (``SyntaxError`` from ``ast.parse``)
method source raises ``PortRealizationProbeError`` with the plugin/port/
method context -- never a silent pass, never a raw traceback from the
underlying stdlib exception. Likewise, a declared-covered port outside this
slice's known 3-port catalog is never silently skipped nor guessed at --
it is recorded as a ``PortRealizationUnknownPortNote`` (plugin + port,
out-of-catalog/not-probed) and returned to the caller (slice-03 CLI
consumes these to visibly note them, never a silent gap and never a false
green -- Vera examine finding #2).

Imports: ``ast``, ``inspect``, ``textwrap``, ``importlib.metadata`` (stdlib)
plus the slice-01 detector (``des.testarch.rules.registry_conformance``) and
the ``LanguageAdapterPlugin`` port type -- stdlib + des only, F-D-09 clean,
no third-party.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from dataclasses import dataclass
from importlib import metadata
from typing import TYPE_CHECKING

from des.testarch.rules.registry_conformance import (
    PortRealizationVerdict,
    detect_port_realization_conformance,
)


if TYPE_CHECKING:
    from collections.abc import Iterable

    from des.ports.language_adapter_plugin import LanguageAdapterPlugin


_ENTRY_POINTS_GROUP = "nwave.lang.adapter"

RUN_CONTRACT_GATE = "run_contract_gate"
VERIFY_ENVIRONMENTAL_E2E = "verify_environmental_e2e"
CHECK_ROBUSTNESS_DENSITY = "check_robustness_density"

# The backing-method surface each port's Protocol declares (mirrors
# ContractGatePort / EnvironmentalE2EPort / RobustnessDensityPort under
# src/des/ports/driven_ports/). A port is unrealized iff ANY of these
# methods lacks evidence of real work (a partially-backed port is not a
# realized port).
_PORT_METHOD_NAMES: dict[str, tuple[str, ...]] = {
    RUN_CONTRACT_GATE: ("collect_scope", "run_suite"),
    VERIFY_ENVIRONMENTAL_E2E: ("build", "install", "run_against_installed"),
    CHECK_ROBUSTNESS_DENSITY: ("covered_domain_ids",),
}


_NOT_IMPLEMENTED_ERROR = "NotImplementedError"

REASON_RAISES_NOT_IMPLEMENTED = "RAISES_NOT_IMPLEMENTED"
"""WHY: the body's only effect is to raise ``NotImplementedError``."""

REASON_ALWAYS_RAISES = "ALWAYS_RAISES"
"""WHY: the body unconditionally raises some other type -- it can never succeed."""

REASON_NO_OBSERVABLE_EFFECT = "NO_OBSERVABLE_EFFECT"
"""WHY: the body does no work at all and would silently FAKE success."""

REASON_INHERITED_UNIMPLEMENTED = "INHERITED_UNIMPLEMENTED"
"""WHY: the method is not overridden -- it resolves to an unimplemented base body."""

REASON_ABSENT = "ABSENT"
"""WHY: the registered facet does not define the port's method at all."""


class PortRealizationProbeError(RuntimeError):
    """Raised when the AST work-probe cannot resolve a backing method's classification.

    Covers: unreadable source (``OSError``/``TypeError`` from
    ``inspect.getsource``), unparsable source (``SyntaxError`` from
    ``ast.parse``), and a declared-covered port outside this slice's known
    port catalog. Degrade-LOUD -- never a silent pass, never a bare stdlib
    traceback.
    """


class _CapturingRegistry:
    """Capturing double duck-typed against ``LanguageAdapterRegistry``.

    Exposes exactly the 3 method names a ``LanguageAdapterPlugin.register_adapters``
    call uses to wire its new-port facets (``register_contract_gate`` /
    ``register_environmental_e2e`` / ``register_robustness_density``) and
    captures whichever facet instance each call receives, independent of the
    ``name`` (tool-token) argument.
    """

    def __init__(self) -> None:
        self.captured: dict[str, object] = {}

    def register_contract_gate(self, name: str, facet: object) -> None:
        del name
        self.captured[RUN_CONTRACT_GATE] = facet

    def register_environmental_e2e(self, name: str, facet: object) -> None:
        del name
        self.captured[VERIFY_ENVIRONMENTAL_E2E] = facet

    def register_robustness_density(self, name: str, facet: object) -> None:
        del name
        self.captured[CHECK_ROBUSTNESS_DENSITY] = facet

    def register(self, name: str, run_facet: object) -> None:
        """No-op: the legacy single test-runner facet slot (out of this probe's scope).

        A plugin (e.g. ``NwaveLangRust``) may ALSO call the real registry's
        pre-existing ``register(name, run_facet)`` slot for the ``"test-runner"``
        port -- a port outside this feature's 3-port catalog (``_PORT_METHOD_NAMES``).
        Duck-typing the full real ``LanguageAdapterRegistry`` surface (not only
        the 3 new slots) keeps ``register_adapters`` calls from crashing on a
        plugin that also uses the legacy slot; the call itself is untracked (this
        probe only judges the 3 new ports).
        """
        del name, run_facet


def _denotes_no_answer(value: ast.expr | None) -> bool:
    """I-3: is this ``return`` value one of the "no answer" singletons?

    A bare ``return`` (``value is None``), ``return None``, ``return ...``,
    or ``return NotImplemented``.
    """
    if value is None:
        return True
    if isinstance(value, ast.Constant):
        return value.value is None or value.value is Ellipsis
    return isinstance(value, ast.Name) and value.id == "NotImplemented"


def _raised_exception_name(node: ast.Raise) -> str | None:
    """The exception type name a top-level ``raise`` names, when it names one."""
    exception = node.exc
    callee = exception.func if isinstance(exception, ast.Call) else exception
    if isinstance(callee, ast.Name):
        return callee.id
    if isinstance(callee, ast.Attribute):
        return callee.attr
    return None


def _is_inert_statement(statement: ast.stmt) -> bool:
    """The closed INERT set (I-1..I-4). Everything else is EVIDENCE."""
    if isinstance(statement, ast.Expr):
        return isinstance(statement.value, ast.Constant)  # I-1
    if isinstance(statement, ast.Pass):
        return True  # I-2
    if isinstance(statement, ast.Return):
        return _denotes_no_answer(statement.value)  # I-3
    return isinstance(statement, ast.Raise)  # I-4 (TOP-LEVEL only)


def _parse_method_definition(
    method: object, *, plugin_id: str, port: str, method_name: str
) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """STATIC read -- ``inspect.getsource`` + ``ast.parse``, NEVER an invocation.

    Degrade-LOUD: unreadable, unparsable, or non-function source raises
    ``PortRealizationProbeError`` naming the plugin/port/method -- never a
    silent pass, never a bare stdlib traceback.
    """
    try:
        source = inspect.getsource(method)
    except (OSError, TypeError) as exc:
        raise PortRealizationProbeError(
            f"cannot read source for {plugin_id}.{port}.{method_name}: {exc}"
        ) from exc

    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError as exc:
        raise PortRealizationProbeError(
            f"cannot parse source for {plugin_id}.{port}.{method_name}: {exc}"
        ) from exc

    func_def = tree.body[0] if tree.body else None
    if not isinstance(func_def, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise PortRealizationProbeError(
            f"source for {plugin_id}.{port}.{method_name} is not a function "
            "definition -- cannot AST-probe it for evidence of real work"
        )
    return func_def


def _lacks_evidence_of_real_work(
    method: object, *, plugin_id: str, port: str, method_name: str
) -> tuple[str, str | None] | None:
    """STATIC AST probe -- reads ``method``'s source, NEVER invokes it.

    Returns ``None`` when the body carries EVIDENCE of real work (at least
    one non-INERT top-level statement -- the method is realized). Otherwise
    returns ``(reason_code, raised_exception_name_or_None)`` describing WHY
    the body does nothing, so a refusal can say something true and specific.
    """
    func_def = _parse_method_definition(
        method, plugin_id=plugin_id, port=port, method_name=method_name
    )

    body = list(func_def.body)
    if any(not _is_inert_statement(statement) for statement in body):
        return None

    raises = [statement for statement in body if isinstance(statement, ast.Raise)]
    raised_names = [_raised_exception_name(statement) for statement in raises]
    if _NOT_IMPLEMENTED_ERROR in raised_names:
        return REASON_RAISES_NOT_IMPLEMENTED, _NOT_IMPLEMENTED_ERROR
    if raises:
        return REASON_ALWAYS_RAISES, next(
            (name for name in raised_names if name is not None), None
        )
    return REASON_NO_OBSERVABLE_EFFECT, None


def _defining_class_name(facet_type: type, method_name: str) -> str | None:
    """Qualname of the class defining ``method_name`` when it is NOT ``facet_type``.

    ``None`` means the facet overrides the method itself. A non-``None``
    answer means the facet INHERITED the body being probed -- the EVASION-C
    shape (subclass the port ``Protocol``, override nothing) reports the
    Protocol here.
    """
    for klass in type.mro(facet_type):
        if method_name in vars(klass):
            return None if klass is facet_type else klass.__qualname__
    return None


def _discover_registered_plugins() -> list[LanguageAdapterPlugin]:
    """Resolve the registered ``nwave.lang.adapter`` entry-points.

    Default resolver used only when the caller omits ``plugins``. Untested
    by this slice's AT (Slice Plan justification: the AT always supplies an
    explicit ``plugins`` iterable, bypassing entry-point discovery).
    """
    discovered: list[LanguageAdapterPlugin] = []
    for entry_point in metadata.entry_points(group=_ENTRY_POINTS_GROUP):
        plugin_cls = entry_point.load()
        discovered.append(plugin_cls())
    return discovered


@dataclass(frozen=True)
class PortRealizationUnknownPortNote:
    """A declared-covered port outside the known 3-port probe catalog (slice-03).

    Not a gap -- the port is genuinely out of this gate's scope (e.g.
    ``nwave-lang-rust``'s legacy ``"test-runner"`` port) -- but silence is
    also wrong (Vera examine finding #2, GDP-6): a maintainer reading a bare
    exit-0 must be able to tell "verified nothing to report" from "silently
    ignored a declared port".
    """

    plugin_id: str
    port: str


@dataclass(frozen=True)
class PortRealizationGapDetail:
    """Rich per-gap diagnostic (WHAT a FAIL-LOUD CLI needs, GDP-3/4, slice-03).

    Extends the plain ``(plugin_id, port)`` violation pair with the first
    unrealized method's name, its ``file:line`` location, and the REASON CODE
    for WHY it carries no evidence of real work -- read via ``inspect`` on
    the SAME already-imported class the AST probe already read (no additional
    invocation, Effect-Isolation preserved).

    ``file_path``/``line_number`` locate the OFFENDING BODY (for an inherited
    method, the base's body); ``facet_class``/``facet_file_path`` always name
    the REGISTERED facet, so the HOW routes to where the fix goes even when
    the offending body lives in a base class elsewhere. ``defining_class`` is
    set only when the method was INHERITED rather than overridden,
    ``raised_type`` only when the body unconditionally raises.

    Every field after ``line_number`` carries a DEFAULT so pre-existing
    constructions keep compiling.
    """

    plugin_id: str
    port: str
    method_name: str
    file_path: str
    line_number: int
    reason: str = REASON_RAISES_NOT_IMPLEMENTED
    facet_class: str | None = None
    facet_file_path: str | None = None
    defining_class: str | None = None
    raised_type: str | None = None


def _absent_method_detail(
    plugin_id: str, port: str, facet: object, method_name: str
) -> PortRealizationGapDetail:
    """Detail for a port method the registered facet does not define at all.

    There is no method body to locate, so the location cited is the facet
    CLASS itself -- the file the maintainer must open to add the method.
    """
    facet_type = type(facet)
    file_path = inspect.getsourcefile(facet_type) or "<unknown>"
    try:
        _, line_number = inspect.getsourcelines(facet_type)
    except (OSError, TypeError):
        line_number = 0
    return PortRealizationGapDetail(
        plugin_id=plugin_id,
        port=port,
        method_name=method_name,
        file_path=file_path,
        line_number=line_number,
        reason=REASON_ABSENT,
        facet_class=facet_type.__qualname__,
        facet_file_path=file_path,
    )


def _find_unrealized_method(
    plugin_id: str, port: str, facet: object, method_names: tuple[str, ...]
) -> PortRealizationGapDetail | None:
    """The first backing method lacking evidence of real work, or ``None``.

    ``None`` means every method its Protocol declares is genuinely
    implemented -- the port is realized. A non-``None`` answer is BOTH the
    verdict (the port is unrealized) and the diagnostic, so the classification
    is computed exactly once per method.
    """
    facet_type = type(facet)
    for method_name in method_names:
        method = getattr(facet_type, method_name, None)
        if method is None:
            return _absent_method_detail(plugin_id, port, facet, method_name)

        finding = _lacks_evidence_of_real_work(
            method, plugin_id=plugin_id, port=port, method_name=method_name
        )
        if finding is None:
            continue

        reason, raised_type = finding
        defining_class = _defining_class_name(facet_type, method_name)
        file_path = inspect.getsourcefile(method) or "<unknown>"
        _, line_number = inspect.getsourcelines(method)
        return PortRealizationGapDetail(
            plugin_id=plugin_id,
            port=port,
            method_name=method_name,
            file_path=file_path,
            line_number=line_number,
            reason=(REASON_INHERITED_UNIMPLEMENTED if defining_class else reason),
            facet_class=facet_type.__qualname__,
            facet_file_path=inspect.getsourcefile(facet_type) or "<unknown>",
            defining_class=defining_class,
            raised_type=raised_type,
        )
    return None


def resolve_and_probe_port_realization_with_detail(
    plugins: Iterable[LanguageAdapterPlugin] | None = None,
) -> tuple[
    PortRealizationVerdict,
    tuple[PortRealizationGapDetail, ...],
    tuple[PortRealizationUnknownPortNote, ...],
    int,
]:
    """Like ``resolve_and_probe_port_realization`` but also returns per-gap detail.

    Same discovery + evidence-of-real-work probe; additionally records, for
    each declared-True-but-unrealized port, the first unrealized method's
    name, file:line and REASON CODE -- the WHAT/WHY a FAIL-LOUD CLI needs
    (GDP-3/4, slice-03).

    A declared port outside this slice's known 3-port catalog
    (``_PORT_METHOD_NAMES``, e.g. the legacy ``"test-runner"`` port) is out
    of this gate's scope entirely -- never probed, never flagged, but
    recorded as a ``PortRealizationUnknownPortNote`` rather than silently
    dropped (Vera examine finding #2). The trailing ``int`` is the count of
    plugins resolved+probed (a truthful, non-fabricated count for a
    self-explaining exit-0 summary -- Vera examine finding #1, GDP-3).
    """
    resolved = list(plugins) if plugins is not None else _discover_registered_plugins()

    plugin_ports: dict[str, dict[str, bool]] = {}
    is_stub_by_plugin: dict[str, dict[str, bool]] = {}
    details: list[PortRealizationGapDetail] = []
    unknown_port_notes: list[PortRealizationUnknownPortNote] = []

    for plugin in resolved:
        plugin_id = plugin.target_language
        declared_ports = dict(plugin.port_coverage)
        plugin_ports[plugin_id] = declared_ports

        registry = _CapturingRegistry()
        plugin.register_adapters(registry)

        is_stub_map: dict[str, bool] = {}
        for port, declared in declared_ports.items():
            if not declared:
                continue
            if port not in _PORT_METHOD_NAMES:
                unknown_port_notes.append(
                    PortRealizationUnknownPortNote(plugin_id=plugin_id, port=port)
                )
                continue
            facet = registry.captured.get(port)
            if facet is None:
                # Declared covered but never registered -- fully unrealized.
                is_stub_map[port] = True
                continue
            detail = _find_unrealized_method(
                plugin_id, port, facet, _PORT_METHOD_NAMES[port]
            )
            is_stub_map[port] = detail is not None
            if detail is not None:
                details.append(detail)
        is_stub_by_plugin[plugin_id] = is_stub_map

    verdict = detect_port_realization_conformance(plugin_ports, is_stub_by_plugin)
    return verdict, tuple(details), tuple(unknown_port_notes), len(resolved)


def resolve_and_probe_port_realization(
    plugins: Iterable[LanguageAdapterPlugin] | None = None,
) -> PortRealizationVerdict:
    """Resolve plugins, evidence-probe declared-covered ports, return the verdict.

    ``plugins`` is an ``Iterable[LanguageAdapterPlugin]``; when omitted, the
    registered ``nwave.lang.adapter`` entry-points are resolved instead
    (untested by this slice's AT).

    Pure over its resolved ``plugins`` argument (a real installed
    environment's ``entry_points()`` read + each adapter's on-disk source
    are the only external reads; the probe never mutates or invokes
    anything).
    """
    verdict, _, _, _ = resolve_and_probe_port_realization_with_detail(plugins)
    return verdict


__all__ = [
    "REASON_ABSENT",
    "REASON_ALWAYS_RAISES",
    "REASON_INHERITED_UNIMPLEMENTED",
    "REASON_NO_OBSERVABLE_EFFECT",
    "REASON_RAISES_NOT_IMPLEMENTED",
    "PortRealizationGapDetail",
    "PortRealizationProbeError",
    "PortRealizationUnknownPortNote",
    "resolve_and_probe_port_realization",
    "resolve_and_probe_port_realization_with_detail",
]

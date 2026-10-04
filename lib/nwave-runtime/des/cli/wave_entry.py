"""Resolve documentation density and the expansion offer once at wave entry.

The default entry query is READ-ONLY. It opens the selected global config for
reading, resolves the existing density cascade, and prints both the frozen
density and the offer the assistant retains for the END of the wave. The
explicit ``--complete`` mode instead consumes the captured entry and successful
constructor terminals after the host attests that the whole wave completed. It
does not reread configuration and uses the packaged renderer on the actual DES
Markdown document. The entry query writes no file, creates no directory and touches neither
``.nwave/des/`` nor the config it read — accepting or ignoring the offer must
leave the accepted documents and the DES execution exactly as they were.

The carrier is split on stdout. `ask` emits a chat sentence; `smart` emits
a sentence that may be relayed only if the completed result satisfies its
condition. Other modes have no entry-time chat sentence:

- ``WAVE-END-OFFER-CHAT: <question>`` — optional offer for `ask`.
- ``WAVE-END-OFFER-CHAT-IF: <question>`` — optional offer for `smart`, only
  after the assistant confirms concrete context in the completed wave result.
  A consumer that does not recognize this marker relays nothing.
- ``WAVE-END-OFFER-INTERNAL-MODE|-ACCEPTANCE|-CONDITION|-TRIGGER|-NAMING|-EXPAND|-NOTE|-WHEN|-NOT-NOW|-ON-REQUEST|-RESOLVED-ONCE``
  — addressed to the assistant alone. They carry the resolved mode with its
  cascade provenance, the natural-language acceptance policy where one applies,
  and the unprompted expansion directive where one applies. ``-WHEN`` confines
  the utterance to the final response of a wave that really completed, and the
  six ``-NOT-NOW`` rows enumerate the situations that are not that completion —
  a lone step terminal of any outcome, an earlier turn, a wave that stopped.
  Both are absent in the silent branch, where nothing is ever said.
  ``-ON-REQUEST`` and ``-RESOLVED-ONCE`` are present in EVERY branch, silence
  included: the first owes the user an immediate substantive answer whenever the
  user asks directly — at any moment of the wave, under ``always-skip`` too — and
  confines the preference and the scope rows to proactive raising alone; the
  second states the preference lifecycle. Both are INTERNAL with no relayable
  payload, so nothing canned exists to repeat to the user. They are never shown
  to the user.

The resolved behaviour is read from ONE closed sum and printed under ONE label
family: ``WAVE-END-OFFER: none`` for silence by preference,
``WAVE-END-OFFER: unprompted`` when the explanation is delivered directly with
nothing to accept, ``WAVE-END-OFFER: conditional`` when the question is gated on
the wave having produced concrete optional context, ``WAVE-END-OFFER: named``
when that same gate applies and the assistant must write the question naming at
most two topics the wave really produced, and the CHAT row when an
unconditional question is put.
``INTERNAL-ACCEPTANCE`` appears only where a question can actually be accepted.

The wave-end explanation invokes no step and rereads no configuration: the
assistant already holds the sentence from entry. The local HTML view uses the
separate explicit ``--complete`` invocation and the captured entry preference.
DES has no whole-wave completion ledger. Calling that mode is the host's
assertion that the whole wave completed, not a conclusion drawn from a lone
successful DES step or a ``DOCUMENT`` row on an Indeterminate terminal.

The step is outside the canonical delivery order, so it is never named by any
``NEXT`` line and prints ``NEXT: no step is owed``. It is deliberately NOT
projected through ``des state`` or the shared terminal's rows: ``des state`` is
invoked after every terminal, and an offer projected there would surface after
every DES step.

Its only inputs are declared, never ambient: ``--repo-root`` (validated as a
repository top level) and ``--wave`` (a closed set), plus the global config path
resolved through the same ``NWaveLocations`` channel the rest of nWave reads
through. It never reads ``.nwave/des/handover.json``: a wave may begin before
any DES delivery exists.

Reading the config is THREE-STATE on purpose (GDP-6, never silent-wrong). The
existing readers (``DESConfig._load_json_file``, the doctor density check,
``attribution_utils.read_global_config``) all collapse an unreadable file and
malformed JSON into ``{}`` — which would print the default branch's decision for
a preference this process never actually read. Here: absent file -> the
cascade's own default; unreadable file -> LOUD ``Indeterminate`` with no offer;
malformed JSON -> LOUD ``Indeterminate`` with no offer. An illegal value in a
CLOSED legal set the release owns in full (``documentation.expansion_prompt``,
``documentation.density``) is a ``Refusal`` instead: the wave does not begin,
and the terminal names the field, the supplied value and every accepted value,
so the operator can repair it without guessing. An unknown ``rigor.profile``
stays ``Indeterminate`` — its legal set is owned upstream by the rigor system.
This value promises no rejection grammar beyond that.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from des.adapters.driven.rendering import nwave_document
from des.cli.step_terminal import (
    NOTHING_OWED,
    StepRefusal,
    refuse,
    repository_top_level,
    succeed,
)
from des.domain.delivery_disposition import Disposition
from des.domain.documentation_density import (
    Density,
    IllegalChoice,
    resolve_density_result,
)
from des.domain.nwave_locations import NWaveLocations
from des.domain.result import Failure, Result, Success
from des.domain.wave_end_offer import (
    CHAT_MARKER,
    GATED_CHAT_MARKER,
    INSTALLED_WAVES,
    CompletedWave,
    Conditional,
    Named,
    Question,
    Silent,
    Unprompted,
    WaveEndBehaviour,
    build_offer,
)


STEP = "wave-entry"
_BRAND_IDENTITY = "nwave-oss-neutral-v1"
_DOCUMENT_CONSTRUCTING_WAVES = frozenset({"discuss", "design", "devops", "distill"})


class _ViewIdentity(HTMLParser):
    """Read only the packaged page's brand and source provenance as HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.brands: list[str] = []
        self.provenance_count = 0
        self.sources: list[str] = []
        self._provenance_depth = 0
        self._source_depth = 0
        self._source_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "meta" and attributes.get("name") == "nwave-brand":
            self.brands.append(attributes.get("content") or "")
        if tag == "div" and "provenance" in (attributes.get("class") or "").split():
            self.provenance_count += 1
            self._provenance_depth = 1
            return
        if self._provenance_depth:
            self._provenance_depth += 1
            if tag == "code":
                self._source_depth += 1
                self._source_text = []

    def handle_data(self, data: str) -> None:
        if self._source_depth:
            self._source_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._provenance_depth:
            return
        if tag == "code" and self._source_depth:
            self.sources.append("".join(self._source_text))
            self._source_depth = 0
            self._source_text = []
        self._provenance_depth -= 1


def _capture(path: Path) -> dict[str, list[str]] | StepRefusal:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        return _indeterminate(
            "WaveResultUnavailable",
            f"could not read captured terminal {path}: {error}; completion is unknown",
            f"capture the real DES terminal at {path} and retry des {STEP} --complete",
        )
    rows: dict[str, list[str]] = {}
    for line in lines:
        label, separator, value = line.partition(": ")
        if separator:
            rows.setdefault(label, []).append(value)
    return rows


def _one(rows: dict[str, list[str]], label: str, capture: Path) -> str | StepRefusal:
    values = rows.get(label, [])
    if len(values) != 1:
        return StepRefusal(
            "WaveResultMalformed",
            f"{capture} has {len(values)} {label} rows; exactly one is required",
            f"capture one unmodified DES terminal with exactly one {label} row",
        )
    return values[0]


def _safe_source(root: Path, locator: str) -> tuple[Path, Path] | StepRefusal:
    relative_text, separator, heading = locator.partition("#")
    parts = relative_text.split("/")
    relative = Path(relative_text)
    if (
        not relative_text
        or relative.is_absolute()
        or relative.suffix != ".md"
        or any(part in ("", ".", "..") for part in parts)
        or "\\" in relative_text
        or "://" in relative_text
        or ":" in parts[0]
        or (separator and not heading)
    ):
        return StepRefusal(
            "WaveDocumentUnsafe",
            f"DOCUMENT locator {locator!r} is not a safe repository-relative Markdown path",
            "use the successful DES constructor's repository-relative .md DOCUMENT locator",
        )
    source = root / relative
    try:
        canonical_root = root.resolve(strict=True)
        for parent in (
            root / Path(*parts[:index]) for index in range(1, len(parts) + 1)
        ):
            if parent.is_symlink():
                raise ValueError(f"symlink at {parent}")
        canonical_source = source.resolve(strict=True)
        if not canonical_source.is_relative_to(canonical_root) or not source.is_file():
            raise ValueError("source is not a regular file under the repository root")
    except (OSError, ValueError) as error:
        return StepRefusal(
            "WaveDocumentUnsafe",
            f"DOCUMENT locator {locator!r} cannot be safely read: {error}",
            "restore the real DES Markdown under the repository root without symlinks, then retry completion",
        )
    return source, source.with_suffix(".html")


def _safe_existing_view(root: Path, source: Path, view: Path) -> StepRefusal | None:
    if view.is_symlink() or (view.exists() and not view.is_file()):
        return StepRefusal(
            "WaveViewUnsafe",
            f"HTML destination {view} is a symlink or not a regular file",
            "remove the unsafe destination or choose a valid generated-view location before retrying",
        )
    if not view.exists():
        return None
    try:
        identity = _ViewIdentity()
        identity.feed(view.read_text(encoding="utf-8"))
        identity.close()
        recorded = identity.sources[0]
        recorded_path = Path(recorded)
        recorded_source = (
            recorded_path if recorded_path.is_absolute() else root / recorded_path
        ).resolve(strict=True)
        same_source = recorded_source == source.resolve(strict=True)
        owned = (
            identity.brands == [_BRAND_IDENTITY]
            and identity.provenance_count == 1
            and len(identity.sources) == 1
            and same_source
        )
    except (OSError, UnicodeError, ValueError, IndexError) as error:
        return StepRefusal(
            "WaveViewUnrecognized",
            f"could not establish ownership of {view}: {error}",
            "preserve the existing HTML and use a destination that is a verified nWave projection of this Markdown",
        )
    if not owned:
        return StepRefusal(
            "WaveViewUnrelated",
            f"{view} is not one nWave projection of the same source {source}",
            "preserve the existing HTML; move it aside only after inspection, then retry completion",
        )
    return None


def _global_config_path(repo_root: Path) -> Result[Path, str]:
    """The ONE global config location, through the shared override channels.

    Reuses ``NWaveLocations.resolve`` — the intra-``des`` channel that already
    honours ``NWAVE_AGENTS_HOME``, ``CLAUDE_CONFIG_DIR`` and ``CODEX_HOME`` for
    ``DESConfig``. A relative override is refused there rather than silently
    joined under an ambient directory, and that refusal is surfaced here instead
    of being degraded to the operator's real home: a wave-entry preference read
    against the wrong home is exactly the silent-wrong outcome this step exists
    to avoid.
    """
    located = NWaveLocations.resolve(
        home=Path.home(),
        repo_root=repo_root,
        agents_home_override=os.environ.get("NWAVE_AGENTS_HOME"),
        claude_config_override=os.environ.get("CLAUDE_CONFIG_DIR"),
        codex_config_override=os.environ.get("CODEX_HOME"),
    )
    if isinstance(located, Failure):
        return located
    return Success(located.unwrap().agents_home / ".nwave" / "config.json")


def _indeterminate(what: str, why: str, how: str) -> StepRefusal:
    return StepRefusal(what, why, how, Disposition.Indeterminate)


def _read_global_config(path: Path) -> Result[dict[str, Any], StepRefusal]:
    """Absent -> ``{}``; unreadable -> Indeterminate; malformed -> Indeterminate."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Success({})
    except OSError as exc:
        return Failure(
            _indeterminate(
                "GlobalConfigUnreadable",
                f"could not read {path}: {exc}; the documentation preference for "
                "this wave is unknown, so no offer was built",
                f"grant read permission on {path} (for example chmod u+r {path}) "
                f"and re-run des {STEP}",
            )
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return Failure(
            _indeterminate(
                "GlobalConfigMalformed",
                f"{path} is not valid JSON ({exc}); the documentation preference "
                "for this wave is unknown, so no offer was built",
                f"repair the JSON syntax of {path} and re-run des {STEP}",
            )
        )
    if not isinstance(parsed, dict):
        return Failure(
            _indeterminate(
                "GlobalConfigMalformed",
                f"{path} holds a JSON {type(parsed).__name__}, not an object; the "
                "documentation preference for this wave is unknown, so no offer "
                "was built",
                f"make {path} a JSON object and re-run des {STEP}",
            )
        )
    return Success(parsed)


def _illegal_choice_refusal(illegal: IllegalChoice, path: Path) -> StepRefusal:
    """A choice outside a CLOSED legal set is a Refusal, not an Indeterminate.

    GDP-8: the decision is made on the decidable property -- the configured
    value lies outside a legal set this release owns in full -- and never on
    the designation "the resolver raised ValueError". Calling it Indeterminate
    claimed the preference "was never understood", which is false about facts
    the software already holds: the field, the supplied value, and every
    accepted member listed below.
    """
    return StepRefusal(
        "GlobalConfigValueIllegal",
        f"{path} sets {illegal.field} to {illegal.value!r}, which is outside "
        f"the closed set of accepted values {sorted(illegal.legal)}; the wave "
        "does not begin and no offer was built",
        f"set {illegal.field} in {path} to one of "
        f"{', '.join(sorted(illegal.legal))}, then re-run des {STEP}",
        Disposition.Refusal,
    )


def _resolve(config: dict[str, Any], path: Path) -> Result[Density, StepRefusal]:
    """Three causes, told apart as DATA: illegal choice refuses, rest stays loud.

    An illegal closed-set choice arrives as a typed ``IllegalChoice`` and is
    REFUSED. The remaining cascade causes -- an unknown ``rigor.profile``,
    validated upstream by the rigor system, and a non-object section that was
    never really read -- keep their ``ValueError`` path and stay Indeterminate.
    """
    try:
        resolved = resolve_density_result(config)
    except ValueError as exc:
        return Failure(
            _indeterminate(
                "GlobalConfigValueIllegal",
                f"{path} carries a documentation setting this release cannot "
                f"resolve ({exc}); no offer was built for a preference that was "
                "never understood",
                f"correct the reported setting in {path} and re-run des {STEP}",
            )
        )
    if isinstance(resolved, Failure):
        return Failure(_illegal_choice_refusal(resolved.error, path))
    return Success(resolved.unwrap())


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=f"des {STEP}",
        description=(
            "Resolve documentation density and the wave-end expansion offer "
            "once at wave entry; --complete renders an attested completed wave."
        ),
    )
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--wave", required=True)
    parser.add_argument(
        "--complete",
        action="store_true",
        help=(
            "host attests the whole wave completed; consume captured entry and "
            "successful constructor terminals to render a full-density local view"
        ),
    )
    parser.add_argument("--entry-result", type=Path)
    parser.add_argument("--constructor-result", type=Path, action="append", default=[])
    return parser.parse_args(argv)


def _behaviour_rows(behaviour: WaveEndBehaviour) -> list[str]:
    """Match the closed behaviour sum onto the ONE label family it decides.

    ``WAVE-END-OFFER`` stays the single label family: ``none`` for silence,
    ``unprompted`` for the direct explanation and ``named`` for the gated offer
    the assistant must write naming at most two produced topics — so the
    already-shipped consumer rule needs one added clause and no second grammar.
    Only ``Question`` and ``Conditional`` render a relayable CHAT row; ``named``
    deliberately renders none, because at entry there is no result to name and a
    consumer that does not know the label then has nothing to repeat (GDP-6).
    """
    match behaviour:
        case Question(chat_text=chat_text):
            return [f"{CHAT_MARKER}: {chat_text}"]
        case Conditional(chat_text=chat_text):
            return [
                "WAVE-END-OFFER: conditional",
                f"{GATED_CHAT_MARKER}: {chat_text}",
            ]
        case Named():
            return ["WAVE-END-OFFER: named"]
        case Unprompted():
            return ["WAVE-END-OFFER: unprompted"]
        case Silent():
            return ["WAVE-END-OFFER: none"]


def _complete_wave(
    root: Path,
    wave: CompletedWave,
    entry_result: Path | None,
    constructor_results: list[Path],
) -> int:
    """Render captured successful DES authorities after the host attests completion.

    DES has no whole-wave ledger. Calling this mode is the host's assertion that
    the whole wave completed; neither a DOCUMENT row nor a single successful
    step terminal can establish that assertion on its own.
    """
    if entry_result is None:
        return refuse(
            StepRefusal(
                "WaveEntryCaptureMissing",
                "--complete has no --entry-result capture",
                "capture the actual wave-entry Success terminal and pass --entry-result PATH",
            ),
            NOTHING_OWED,
        )
    entry = _capture(entry_result)
    if isinstance(entry, StepRefusal):
        return refuse(entry, NOTHING_OWED)
    for label, expected in (("DELIVERY-OUTCOME", "Success"), ("WAVE", wave.name)):
        actual = _one(entry, label, entry_result)
        if isinstance(actual, StepRefusal):
            return refuse(actual, NOTHING_OWED)
        if actual != expected:
            return refuse(
                StepRefusal(
                    "WaveEntryMismatch",
                    f"{entry_result} records {label}={actual!r}, expected {expected!r}",
                    "pass the real successful entry terminal for this selected wave",
                ),
                NOTHING_OWED,
            )
    density = _one(entry, "WAVE-DOCUMENTATION-DENSITY", entry_result)
    if isinstance(density, StepRefusal):
        return refuse(density, NOTHING_OWED)
    if density not in ("full", "lean"):
        return refuse(
            StepRefusal(
                "WaveDensityIllegal",
                f"{entry_result} records unknown density {density!r}",
                "pass an unmodified wave-entry terminal with full or lean density",
            ),
            NOTHING_OWED,
        )

    if wave.name in _DOCUMENT_CONSTRUCTING_WAVES and not constructor_results:
        return refuse(
            _indeterminate(
                "WaveConstructorCaptureMissing",
                f"{wave.name} completed-wave input has no captured DES constructor terminal; its document outcome is unknown",
                "capture the successful DES constructor terminal and pass it with --constructor-result PATH",
            ),
            NOTHING_OWED,
        )

    locators: list[str] = []
    for capture_path in constructor_results:
        captured = _capture(capture_path)
        if isinstance(captured, StepRefusal):
            return refuse(captured, NOTHING_OWED)
        outcome = _one(captured, "DELIVERY-OUTCOME", capture_path)
        if isinstance(outcome, StepRefusal):
            return refuse(outcome, NOTHING_OWED)
        if outcome != "Success":
            return refuse(
                StepRefusal(
                    "WaveConstructorNotSuccessful",
                    f"{capture_path} records {outcome!r}; its DOCUMENT cannot attest a completed authority",
                    "finish or repair that DES constructor, then capture its Success terminal before retrying the completed wave",
                ),
                NOTHING_OWED,
            )
        locators.extend(captured.get("DOCUMENT", []))

    if wave.name in _DOCUMENT_CONSTRUCTING_WAVES and not locators:
        return refuse(
            _indeterminate(
                "WaveDocumentEvidenceMissing",
                f"{wave.name} has no DOCUMENT row in its captured successful constructor terminals",
                "pass the actual successful DES document constructor terminal with its DOCUMENT row",
            ),
            NOTHING_OWED,
        )

    if density == "lean":
        return succeed(
            [
                f"WAVE: {wave.name}",
                "WAVE-DOCUMENTATION-DENSITY: lean",
                "LOCAL-VIEW: not requested; authoritative DES documents and handoffs remain",
            ],
            NOTHING_OWED,
        )

    planned: list[tuple[Path, Path]] = []
    seen: set[Path] = set()
    for locator in locators:
        checked = _safe_source(root, locator)
        if isinstance(checked, StepRefusal):
            return refuse(checked, NOTHING_OWED)
        source, view = checked
        if source in seen:
            continue
        seen.add(source)
        destination_issue = _safe_existing_view(root, source, view)
        if destination_issue is not None:
            return refuse(destination_issue, NOTHING_OWED)
        planned.append((source, view))

    facts = [
        f"WAVE: {wave.name}",
        "WAVE-DOCUMENTATION-DENSITY: full",
        "COMPLETION-EVIDENCE: host asserted whole-wave completion; captured DES terminals alone do not prove it",
        *(f"DOCUMENT: {locator}" for locator in locators),
    ]
    if not planned:
        facts.append("LOCAL-VIEW: no applicable DES Markdown authority")
        return succeed(facts, NOTHING_OWED)

    for source, view in planned:
        rendered_stdout = io.StringIO()
        rendered_stderr = io.StringIO()
        try:
            with (
                contextlib.redirect_stdout(rendered_stdout),
                contextlib.redirect_stderr(rendered_stderr),
            ):
                renderer_status = nwave_document.main([str(source), "--out", str(view)])
        except (
            OSError,
            UnicodeError,
            ValueError,
            nwave_document.BrandAssetError,
        ) as error:
            return refuse(
                _indeterminate(
                    "WaveViewRenderFailed",
                    f"packaged renderer failed for {source} -> {view}: {error}; an output may be partial",
                    f"inspect {view} and the authority {source}, repair the cause, then retry des {STEP} --complete",
                ),
                NOTHING_OWED,
                facts=facts,
            )
        if renderer_status != 0:
            return refuse(
                _indeterminate(
                    "WaveViewRenderFailed",
                    f"packaged renderer returned {renderer_status} for {source} -> {view}: {rendered_stderr.getvalue().strip()}",
                    f"inspect {source} and {view}, repair the reported cause, then retry des {STEP} --complete",
                ),
                NOTHING_OWED,
                facts=facts,
            )
        generated_issue = _safe_existing_view(root, source, view)
        if generated_issue is not None:
            return refuse(
                _indeterminate(
                    "WaveViewResultUnconfirmed",
                    f"renderer returned success but {view} is not a confirmed view of {source}: {generated_issue.why}",
                    f"inspect {view}, repair the renderer or destination, then retry des {STEP} --complete",
                ),
                NOTHING_OWED,
                facts=facts,
            )
        facts.append(f"HTML: {view}")
        if rendered_stderr.getvalue().strip():
            diagnostic = " | ".join(rendered_stderr.getvalue().splitlines())
            facts.append(f"RENDER-DIAGNOSTIC: {diagnostic}")
    return succeed(facts, NOTHING_OWED)


def main(argv: list[str] | None = None) -> int:
    """One read-only outcome: the offer block, or WHY none was built."""
    arguments = _parse(argv)

    root = repository_top_level(arguments.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(root, NOTHING_OWED)

    wave = CompletedWave.of(arguments.wave)
    if isinstance(wave, Failure):
        return refuse(
            StepRefusal(
                "UnknownWave",
                wave.error,
                "pass one of the installed wave names as --wave: "
                f"{', '.join(INSTALLED_WAVES)}",
            ),
            NOTHING_OWED,
        )

    if arguments.complete:
        return _complete_wave(
            root, wave.unwrap(), arguments.entry_result, arguments.constructor_result
        )
    if arguments.entry_result is not None or arguments.constructor_result:
        return refuse(
            StepRefusal(
                "WaveCompletionArgumentsWithoutComplete",
                "captured result paths were supplied without --complete",
                "use --complete after the host has established whole-wave success, or omit the result paths at entry",
            ),
            NOTHING_OWED,
        )

    config_path = _global_config_path(root)
    if isinstance(config_path, Failure):
        return refuse(
            _indeterminate(
                "GlobalConfigLocationUnresolved",
                f"{config_path.error}; the documentation preference for this wave "
                "is unknown, so no offer was built",
                "set the override to an absolute path, or unset it, and re-run "
                f"des {STEP}",
            ),
            NOTHING_OWED,
        )
    path = config_path.unwrap()

    config = _read_global_config(path)
    if isinstance(config, Failure):
        return refuse(config.error, NOTHING_OWED)

    density = _resolve(config.unwrap(), path)
    if isinstance(density, Failure):
        return refuse(density.error, NOTHING_OWED)

    selected_density = density.unwrap()
    offer = build_offer(wave.unwrap(), selected_density)
    return succeed(
        [
            f"WAVE: {offer.wave}",
            f"GLOBAL-CONFIG: {path}",
            f"WAVE-DOCUMENTATION-DENSITY: {selected_density.mode}",
            f"WAVE-DOCUMENTATION-PROVENANCE: {selected_density.provenance}",
            *_behaviour_rows(offer.behaviour),
            *offer.internal,
        ],
        NOTHING_OWED,
    )

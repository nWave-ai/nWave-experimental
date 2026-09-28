"""Resolve the documentation preference ONCE at wave entry and build its offer.

READ-ONLY. This step opens the selected global config for reading, resolves the
existing density cascade, and prints the offer the assistant retains for the END
of the wave. It writes no file, creates no directory and touches neither
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

The END of a wave invokes NO step and rereads NO configuration: the assistant
already holds the sentence from this invocation. That is why the preference is
resolved here and only here.

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
import json
import os
from pathlib import Path
from typing import Any

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
            "Resolve the documentation preference once at wave entry and emit "
            "the wave-end expansion offer block. Read-only."
        ),
    )
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--wave", required=True)
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

    offer = build_offer(wave.unwrap(), density.unwrap())
    return succeed(
        [
            f"WAVE: {offer.wave}",
            f"GLOBAL-CONFIG: {path}",
            *_behaviour_rows(offer.behaviour),
            *offer.internal,
        ],
        NOTHING_OWED,
    )

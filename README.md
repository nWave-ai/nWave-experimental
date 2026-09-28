# nWave — Experimental Channel

> Experimental software: evaluate it on non-critical work and report concrete friction or defects.

**Build:** `59c47180b` from `atdd_pure_staging` (`59c47180b9ea751fb264c272fc2a91b63c748ee9`)

## Delivery

```bash
printf '%s' "$REQUEST" | des po --repo-root ROOT
des state --repo-root ROOT
```

DES helps deliver a request one step at a time. Your assistant chooses and starts each step.
The steps define the product goal, establish design facts, and write a public oracle: an executable check of promised behavior.
They then implement the change, review the whole change, examine observed behavior without reading implementation code, and integrate the result.

Each step reports one outcome:
- `Success`: the step completed.
- `Refusal`: the step cannot proceed as requested.
- `Retry`: the operation can be tried again.
- `Indeterminate`: the result is uncertain; do not treat it as success.

The `NEXT` line suggests a following step; DES does not start it. Run `des state` to see where an open request stands.

## Writing for this channel

Use short, active sentences in guides, examples, and user-facing messages. Explain a new abbreviation or internal term before using it. Keep command names, flags, configuration keys, and required technical details exact.

## Install

Prerequisites: Python 3.10+ and either `uv` or `pipx`.
```bash
git clone https://github.com/nWave-ai/nWave-experimental.git
cd nWave-experimental
uv run python -m nwave_ai.cli install
```
Restart the host, then enable nWave with `nwave-ai project enable`. nWave sends no telemetry; share redacted feedback through the experimental issue tracker.

## Recover the previous experimental package identity

A previous experimental release used the distribution name `nwave` at version
`4.0.0+atddpure.2d5a26a`, although it exported the `nwave_ai` module and the
`nwave-ai` command. A corrected release uses the canonical distribution name
`nwave-ai`. Recover only after the corrected release receipt gives its exact
commit; set `CORRECTED_REF` to that receipt value, never to a guessed commit.

Use the complete [installation recovery guide](docs/guides/installation-guide/#recover-a-previous-experimental-package-identity): it identifies the actual manager and absolute executables, removes the verified obsolete owner before reinstalling canonical `nwave-ai`, then runs install, DES migration, and doctor.

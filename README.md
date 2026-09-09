# nWave — Experimental Channel

> Experimental software: evaluate it on non-critical work and report concrete friction or defects.

**Build:** `821610d` from `feature/atdd-pure-staging` (`821610db594df04d6518be2f1a0ee83948989ce3`)

## Delivery

```bash
printf '%s' "$REQUEST" | des po --repo-root ROOT
des state --repo-root ROOT
```

Each step resolves one thing — product decomposition, design facts, public oracle, craft, whole-diff review with source-blind examination, integration — and returns `Success`, `Refusal`, `Retry`, or `Indeterminate` with the canonical next step in its `NEXT` line. Your assistant invokes them one at a time; `des state` says where an open request stands.

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

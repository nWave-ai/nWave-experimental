# nWave — Experimental Channel

> Experimental software: evaluate it on non-critical work and report concrete friction or defects.

**Build:** `2d5a26a` from `feature/atdd-pure-staging` (`2d5a26a0e1fc7cc810581d5423ba912817c5ea0a`)

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

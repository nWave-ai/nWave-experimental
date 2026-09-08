# nWave — Experimental Channel

> Experimental software: evaluate it on non-critical work and report concrete friction or defects.

**Build:** `{sha}` from `feature/atdd-pure-staging` (`{full_sha}`)

## Delivery

```bash
printf '%s' "$REQUEST" | des po --repo-root ROOT
des state --repo-root ROOT
```

Each step resolves one thing — product decomposition, design facts, public oracle, craft, whole-diff review with source-blind examination, integration — and returns `Success`, `Refusal`, `Retry`, or `Indeterminate` with the canonical next step in its `NEXT` line. Your assistant invokes them one at a time; `des state` says where an open request stands.

## Install

Prerequisites: Python 3.10+ and either `uv` or `pipx`.
```bash
git clone https://github.com/{target_slug}.git
cd nWave-experimental
uv run python -m nwave_ai.cli install
```
Restart the host, then enable nWave with `nwave-ai project enable`. nWave sends no telemetry; share redacted feedback through the experimental issue tracker.

# nWave — atdd_pure Preview (Experimental Channel)

> **Private, access-controlled preview.** This repository is a snapshot of the
> nWave `feature/atdd-pure-staging` branch (the atdd_pure version), published for
> preview only. It is **not** the beta, RC, or prod release, and there is
> **no PyPI package** for this channel — you install **locally from this clone**.

**Build:** atdd-pure preview `@ 7c871a598` (source `feature/atdd-pure-staging` `7c871a598fe28ef64cae23f53516d5d14ee13c8c`)

## Install (local — there is no PyPI for this preview)

```bash
git clone https://github.com/nWave-ai/nWave-experimental.git
cd nWave-experimental
uv run python -m nwave_ai.cli install
```

`uv run` provisions the environment automatically. **Restart Claude Code** when
it finishes.

- No `uv`? Install it: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  (or see https://docs.astral.sh/uv/getting-started/installation/).
- **pip alternative** (Python 3.10+): `pip install -e . && nwave-ai install`
- **Windows**: use WSL (`wsl --install`).

## Update to the latest preview

```bash
cd nWave-experimental && git pull && uv run python -m nwave_ai.cli install
```

## Uninstall

```bash
uv run python -m nwave_ai.cli uninstall
```

## Notes

- **Use the local CLI install above.** The Claude plugin-marketplace path does
  **not** enable DES enforcement (upstream Claude Code limitation) — without the
  CLI install you lose phase enforcement, TDD validation, and audit logging,
  which are the core of nWave.
- This preview tracks `feature/atdd-pure-staging` and is refreshed by
  `scripts/release/publish_experimental.py`; the build SHA above identifies the
  exact source commit.
- User-facing docs are under `docs/guides/` and `docs/reference/` in this tree.

---
*Experimental channel — segregated from beta/rc/prod, no PyPI. Access is limited
to collaborators on this private repository.*

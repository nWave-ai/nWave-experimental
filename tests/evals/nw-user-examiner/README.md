# Source-blind examination of observed operations

Three synthetic observation packets test the existing examiner through the native Claude adapter. They do not certify a product, exercise Django, or prove general reviewer reliability. No source is supplied; the role keeps its empty tool declaration (provider structured output only).

Success criteria fixed before the role edit:

- Missing PUT observation with green test counts: `indeterminate`.
- POST, PUT and subsequent GET observed correctly: `accepted`.
- PUT observed returning 405: `rejected`.

The provider-enforced outcome is graded. Diagnostics are retained for independent inspection and are not parsed into a verdict. The recorder retains invocation, model usage, session ID and elapsed duration, including failures. Use a new output directory for every run.

```bash
PYTHONPATH=src python tests/evals/nw-user-examiner/run_probe.py --output-root /absolute/durable/eval-directory --model haiku
```

The model alias must resolve on the authenticated host. This command buys three bounded native provider turns. `--framework-root` can select the root containing an installed `nWave/` asset tree. It does not install or reconfigure a provider.

Measured 2026-09-16 with `claude-haiku-4-5-20251001`: original role 2/3 outcomes; clarified role 3/3. The original role already detected missing PUT but called absence a product rejection. This probe demonstrates the corrected missing/contradictory evidence distinction, not reproduction of the historical false approval.

Original: USD0.023915 and37.022s summed role elapsed. Clarified: USD0.024374 and37.483s. One observation per case/variant is not a statistical estimate or an economic improvement claim. Native records, exact original prompts and source hashes remain at `/home/alexd/.nwave/recovery/des-improvement-20260916T074447Z/n11/`; `baseline-results.json` and `clarified-results.json` index them.

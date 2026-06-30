"""``CodeFactPort`` driven adapters (OSS tier, ADR-LA-001).

The code-fact provider family behind :class:`des.ports.code_fact_port.CodeFactPort`:

* :class:`~des.adapters.driven.codefact.text_search_code_fact_adapter.TextSearchAdapter`
  — the pure-Python ``re``/``pathlib`` universal floor (``noisy`` confidence,
  always answers on any Python-only target).
* :class:`~des.adapters.driven.codefact.ast_code_fact_adapter.AstAdapter`
  — the per-language structural tier (``approx`` confidence); delegates to the
  sole testarch parser (NO second ``import ast``).
* :class:`~des.adapters.driven.codefact.tsunami_code_fact_adapter.TsunamiAdapter`
  — the paid-tier precision seam (``binding-resolved`` confidence); wired only
  when its ``probe`` passes (absence is the normal OSS case).
* :class:`~des.adapters.driven.codefact.code_fact_chain.CodeFactChain`
  — the negotiation that walks ``Tsunami -> Ast -> TextSearch`` top-down, tags the
  answer, and degrades LOUD past an absent paid tier.

slice-01 shipped the floor + a floor-backed chain (the walking-skeleton
substrate); slice-02 adds the ``AstAdapter`` / ``TsunamiAdapter`` precision tiers
and the full fallback-chain negotiation.
"""

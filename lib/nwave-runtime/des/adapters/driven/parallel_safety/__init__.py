"""`SliceBlastRadiusPort` driven adapters (measured-parallel-safety-report).

Behind :class:`des.ports.slice_blast_radius_port.SliceBlastRadiusPort`:

* :class:`~des.adapters.driven.parallel_safety.subprocess_blast_radius_adapter.SubprocessBlastRadiusAdapter`
  -- the real adapter, shells `des blast-radius` with a wall-clock timeout;
  owns ALL subprocess/git indirection (D-6).
* :class:`~des.adapters.driven.parallel_safety.in_memory_blast_radius_adapter.InMemoryBlastRadiusAdapter`
  -- the in-process test twin, returns canned measurements/unmeasured.
"""

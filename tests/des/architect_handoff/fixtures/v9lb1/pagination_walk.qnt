// Page-walk model of paginate(items, offset, limit): a caller steps offset by limit.
// Atoms: n = len(items); lim = limit (validated positive); offset = validated nonnegative offset;
// index i stands for items[i]; count.get(i) = how many times items[i] has been delivered so far
// (ghost history). Order inside a page is abstracted: pages are index sets; order is checked
// by the Python property tests, not by this model.
module pagination_walk {
  var n: int
  var lim: int
  var offset: int
  var count: int -> int

  pure val IDX = 0.to(5)

  // Python slice items[a:b] for a >= 0 over indices 0..len-1: the indices in [a, min(b, len)).
  // (Apalache needs a constant interval, so the interval is written as a filter over IDX.)
  pure def pySlice(a: int, b: int, len: int): Set[int] =
    IDX.filter(i => a <= i and i < (if (b < len) b else len))

  // Implementation under test: the fixed rule items[offset:offset+limit].
  pure def page(len: int, off: int, l: int): Set[int] = pySlice(off, off + l, len)

  // Independent oracle: the filter definition of the page, no slice arithmetic.
  pure def spec(len: int, off: int, l: int): Set[int] =
    IDX.filter(i => i < len and off <= i and i < off + l)

  action init = all {
    nondet len = 0.to(6).oneOf()
    nondet l = 1.to(3).oneOf()
    all { n' = len, lim' = l, offset' = 0, count' = IDX.mapBy(i => 0) }
  }

  // A page request inside the list: deliver the page, the caller advances by limit.
  action step = all {
    offset < n,
    count' = IDX.mapBy(i => count.get(i) + (if (page(n, offset, lim).contains(i)) 1 else 0)),
    offset' = offset + lim,
    n' = n, lim' = lim,
  }

  // A page request at or beyond the end: delivers nothing, nothing changes.
  action probeEnd = all {
    offset >= n,
    count' = IDX.mapBy(i => count.get(i) + (if (page(n, offset, lim).contains(i)) 1 else 0)),
    offset' = offset, n' = n, lim' = lim,
  }

  action move = any { step, probeEnd }

  val pageMatchesSpec = page(n, offset, lim) == spec(n, offset, lim)
  val noSkipNoRepeat = IDX.forall(i => count.get(i) == (if (i < offset and i < n) 1 else 0))
  val completeAtEnd = offset >= n implies IDX.forall(i => count.get(i) == (if (i < n) 1 else 0))
  val bounded = page(n, offset, lim).size() <= lim
  val beyondEndEmpty = offset >= n implies page(n, offset, lim) == Set()
}

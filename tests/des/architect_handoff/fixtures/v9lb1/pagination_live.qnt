// Liveness slice for TLC: only the variables the property reads (no ghost history).
module pagination_live {
  var n: int
  var lim: int
  var offset: int

  action init = all {
    nondet len = 0.to(6).oneOf()
    nondet l = 1.to(3).oneOf()
    all { n' = len, lim' = l, offset' = 0 }
  }
  action step = all { offset < n, offset' = offset + lim, n' = n, lim' = lim }
  action probeEnd = all { offset >= n, offset' = offset, n' = n, lim' = lim }
  action move = any { step, probeEnd }

  temporal fair = weakFair(step, (n, lim, offset))
  temporal reachesEnd = eventually(offset >= n)
  temporal liveUnderFairness = fair implies reachesEnd
}

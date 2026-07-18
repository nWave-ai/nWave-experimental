---- MODULE Claim_MC_EagerUnfenced ----
(* Claims ON with an EAGER lease (may lapse while the holder is alive and  *)
(* still working -- a slow holder is indistinguishable from a dead one),   *)
(* and NO fencing check at landing. Expect NoDoubleTake/NoDoubleLand to be *)
(* VIOLATED: expiry reintroduces exactly the double-take that claiming was *)
(* introduced to prevent.                                                  *)
EXTENDS Naturals, FiniteSets

Items == {"w1"}
Claimers == {"c1", "c2"}
Mortal == {}
NoItem == "NoItem"
NoOwner == "NoOwner"
ClaimEnabled == TRUE
ExpiryMode == "eager"
Fenced == FALSE

VARIABLES working, owner, landed, alive

INSTANCE Claim
====

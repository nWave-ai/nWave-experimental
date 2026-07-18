---- MODULE Claim_MC_NoClaim ----
(* No claim marker at all: in-flight work is invisible to peers, only       *)
(* landing is recorded. Nobody dies. Expect NoDoubleTake and NoDoubleLand   *)
(* to be VIOLATED -- two instances take and land the same item.             *)
EXTENDS Naturals, FiniteSets

Items == {"w1", "w2"}
Claimers == {"c1", "c2"}
Mortal == {}
NoItem == "NoItem"
NoOwner == "NoOwner"
ClaimEnabled == FALSE
ExpiryMode == "none"
Fenced == FALSE

VARIABLES working, owner, landed, alive

INSTANCE Claim
====

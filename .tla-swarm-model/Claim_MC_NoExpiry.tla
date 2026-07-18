---- MODULE Claim_MC_NoExpiry ----
(* Claims ON, but a claim is NEVER released except by landing. c1 may die  *)
(* mid-flight. Expect safety to HOLD but EventualDrain to be VIOLATED:     *)
(* the dead instance's claim wedges its item forever.                      *)
EXTENDS Naturals, FiniteSets

Items == {"w1", "w2"}
Claimers == {"c1", "c2"}
Mortal == {"c1"}
NoItem == "NoItem"
NoOwner == "NoOwner"
ClaimEnabled == TRUE
ExpiryMode == "none"
Fenced == TRUE

VARIABLES working, owner, landed, alive

INSTANCE Claim
====

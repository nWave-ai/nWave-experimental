---- MODULE Claim_MC_EagerFenced ----
(* Claims ON, EAGER lease (may lapse while the holder is alive), but WITH  *)
(* the fencing check at landing: a claimer that no longer holds the claim  *)
(* is refused and must abandon. c1 may die mid-flight.                     *)
(* Expect: safety HOLDS (fencing absorbs the over-eager expiry) AND        *)
(* EventualDrain HOLDS (expiry lets a peer recover the dead holder's item).*)
(* This is the candidate correct discipline.                               *)
EXTENDS Naturals, FiniteSets

Items == {"w1", "w2"}
Claimers == {"c1", "c2"}
Mortal == {"c1"}
NoItem == "NoItem"
NoOwner == "NoOwner"
ClaimEnabled == TRUE
ExpiryMode == "eager"
Fenced == TRUE

VARIABLES working, owner, landed, alive

INSTANCE Claim
====

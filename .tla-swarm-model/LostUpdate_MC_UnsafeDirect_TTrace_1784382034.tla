---- MODULE LostUpdate_MC_UnsafeDirect_TTrace_1784382034 ----
EXTENDS LostUpdate_MC_UnsafeDirect, Sequences, TLCExt, Toolbox, Naturals, TLC

_expression ==
    LET LostUpdate_MC_UnsafeDirect_TEExpression == INSTANCE LostUpdate_MC_UnsafeDirect_TEExpression
    IN LostUpdate_MC_UnsafeDirect_TEExpression!expression
----

_trace ==
    LET LostUpdate_MC_UnsafeDirect_TETrace == INSTANCE LostUpdate_MC_UnsafeDirect_TETrace
    IN LostUpdate_MC_UnsafeDirect_TETrace!trace
----

_inv ==
    ~(
        TLCGet("level") = Len(_TETrace)
        /\
        visible = ([f1 |-> 1, f2 |-> 0])
        /\
        mergeLock = (FALSE)
        /\
        version = ([f1 |-> 1, f2 |-> 1])
        /\
        snapshot = ([i1 |-> [f1 |-> 0, f2 |-> 1], i2 |-> [f1 |-> 0, f2 |-> 0]])
        /\
        status = ([i1 |-> "landed", i2 |-> "landed"])
    )
----

_init ==
    /\ mergeLock = _TETrace[1].mergeLock
    /\ status = _TETrace[1].status
    /\ version = _TETrace[1].version
    /\ visible = _TETrace[1].visible
    /\ snapshot = _TETrace[1].snapshot
----

_next ==
    /\ \E i,j \in DOMAIN _TETrace:
        /\ \/ /\ j = i + 1
              /\ i = TLCGet("level")
        /\ mergeLock  = _TETrace[i].mergeLock
        /\ mergeLock' = _TETrace[j].mergeLock
        /\ status  = _TETrace[i].status
        /\ status' = _TETrace[j].status
        /\ version  = _TETrace[i].version
        /\ version' = _TETrace[j].version
        /\ visible  = _TETrace[i].visible
        /\ visible' = _TETrace[j].visible
        /\ snapshot  = _TETrace[i].snapshot
        /\ snapshot' = _TETrace[j].snapshot

\* Uncomment the ASSUME below to write the states of the error trace
\* to the given file in Json format. Note that you can pass any tuple
\* to `JsonSerialize`. For example, a sub-sequence of _TETrace.
    \* ASSUME
    \*     LET J == INSTANCE Json
    \*         IN J!JsonSerialize("LostUpdate_MC_UnsafeDirect_TTrace_1784382034.json", _TETrace)

=============================================================================

 Note that you can extract this module `LostUpdate_MC_UnsafeDirect_TEExpression`
  to a dedicated file to reuse `expression` (the module in the 
  dedicated `LostUpdate_MC_UnsafeDirect_TEExpression.tla` file takes precedence 
  over the module `LostUpdate_MC_UnsafeDirect_TEExpression` below).

---- MODULE LostUpdate_MC_UnsafeDirect_TEExpression ----
EXTENDS LostUpdate_MC_UnsafeDirect, Sequences, TLCExt, Toolbox, Naturals, TLC

expression == 
    [
        \* To hide variables of the `LostUpdate_MC_UnsafeDirect` spec from the error trace,
        \* remove the variables below.  The trace will be written in the order
        \* of the fields of this record.
        mergeLock |-> mergeLock
        ,status |-> status
        ,version |-> version
        ,visible |-> visible
        ,snapshot |-> snapshot
        
        \* Put additional constant-, state-, and action-level expressions here:
        \* ,_stateNumber |-> _TEPosition
        \* ,_mergeLockUnchanged |-> mergeLock = mergeLock'
        
        \* Format the `mergeLock` variable as Json value.
        \* ,_mergeLockJson |->
        \*     LET J == INSTANCE Json
        \*     IN J!ToJson(mergeLock)
        
        \* Lastly, you may build expressions over arbitrary sets of states by
        \* leveraging the _TETrace operator.  For example, this is how to
        \* count the number of times a spec variable changed up to the current
        \* state in the trace.
        \* ,_mergeLockModCount |->
        \*     LET F[s \in DOMAIN _TETrace] ==
        \*         IF s = 1 THEN 0
        \*         ELSE IF _TETrace[s].mergeLock # _TETrace[s-1].mergeLock
        \*             THEN 1 + F[s-1] ELSE F[s-1]
        \*     IN F[_TEPosition - 1]
    ]

=============================================================================



Parsing and semantic processing can take forever if the trace below is long.
 In this case, it is advised to uncomment the module below to deserialize the
 trace from a generated binary file.

\*
\*---- MODULE LostUpdate_MC_UnsafeDirect_TETrace ----
\*EXTENDS LostUpdate_MC_UnsafeDirect, IOUtils, TLC
\*
\*trace == IODeserialize("LostUpdate_MC_UnsafeDirect_TTrace_1784382034.bin", TRUE)
\*
\*=============================================================================
\*

---- MODULE LostUpdate_MC_UnsafeDirect_TETrace ----
EXTENDS LostUpdate_MC_UnsafeDirect, TLC

trace == 
    <<
    ([visible |-> [f1 |-> 0, f2 |-> 0],mergeLock |-> FALSE,version |-> [f1 |-> 0, f2 |-> 0],snapshot |-> [i1 |-> [f1 |-> 0, f2 |-> 0], i2 |-> [f1 |-> 0, f2 |-> 0]],status |-> [i1 |-> "pending", i2 |-> "pending"]]),
    ([visible |-> [f1 |-> 0, f2 |-> 0],mergeLock |-> FALSE,version |-> [f1 |-> 0, f2 |-> 0],snapshot |-> [i1 |-> [f1 |-> 0, f2 |-> 0], i2 |-> [f1 |-> 0, f2 |-> 0]],status |-> [i1 |-> "pending", i2 |-> "running"]]),
    ([visible |-> [f1 |-> 0, f2 |-> 0],mergeLock |-> TRUE,version |-> [f1 |-> 0, f2 |-> 0],snapshot |-> [i1 |-> [f1 |-> 0, f2 |-> 0], i2 |-> [f1 |-> 0, f2 |-> 0]],status |-> [i1 |-> "pending", i2 |-> "merging"]]),
    ([visible |-> [f1 |-> 0, f2 |-> 1],mergeLock |-> FALSE,version |-> [f1 |-> 0, f2 |-> 1],snapshot |-> [i1 |-> [f1 |-> 0, f2 |-> 0], i2 |-> [f1 |-> 0, f2 |-> 0]],status |-> [i1 |-> "pending", i2 |-> "landed"]]),
    ([visible |-> [f1 |-> 0, f2 |-> 1],mergeLock |-> TRUE,version |-> [f1 |-> 0, f2 |-> 1],snapshot |-> [i1 |-> [f1 |-> 0, f2 |-> 1], i2 |-> [f1 |-> 0, f2 |-> 0]],status |-> [i1 |-> "applying", i2 |-> "landed"]]),
    ([visible |-> [f1 |-> 1, f2 |-> 0],mergeLock |-> FALSE,version |-> [f1 |-> 1, f2 |-> 1],snapshot |-> [i1 |-> [f1 |-> 0, f2 |-> 1], i2 |-> [f1 |-> 0, f2 |-> 0]],status |-> [i1 |-> "landed", i2 |-> "landed"]])
    >>
----


=============================================================================

---- CONFIG LostUpdate_MC_UnsafeDirect_TTrace_1784382034 ----

INVARIANT
    _inv

CHECK_DEADLOCK
    \* CHECK_DEADLOCK off because of PROPERTY or INVARIANT above.
    FALSE

INIT
    _init

NEXT
    _next

CONSTANT
    _TETrace <- _trace

ALIAS
    _expression
=============================================================================
\* Generated on Sat Jul 18 14:40:34 BST 2026
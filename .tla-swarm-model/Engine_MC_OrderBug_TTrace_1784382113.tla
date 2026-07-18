---- MODULE Engine_MC_OrderBug_TTrace_1784382113 ----
EXTENDS Sequences, TLCExt, Toolbox, Naturals, TLC, Engine_MC_OrderBug

_expression ==
    LET Engine_MC_OrderBug_TEExpression == INSTANCE Engine_MC_OrderBug_TEExpression
    IN Engine_MC_OrderBug_TEExpression!expression
----

_trace ==
    LET Engine_MC_OrderBug_TETrace == INSTANCE Engine_MC_OrderBug_TETrace
    IN Engine_MC_OrderBug_TETrace!trace
----

_inv ==
    ~(
        TLCGet("level") = Len(_TETrace)
        /\
        mergeLock = (FALSE)
        /\
        status = ([i1 |-> "running", i2 |-> "running"])
    )
----

_init ==
    /\ mergeLock = _TETrace[1].mergeLock
    /\ status = _TETrace[1].status
----

_next ==
    /\ \E i,j \in DOMAIN _TETrace:
        /\ \/ /\ j = i + 1
              /\ i = TLCGet("level")
        /\ mergeLock  = _TETrace[i].mergeLock
        /\ mergeLock' = _TETrace[j].mergeLock
        /\ status  = _TETrace[i].status
        /\ status' = _TETrace[j].status

\* Uncomment the ASSUME below to write the states of the error trace
\* to the given file in Json format. Note that you can pass any tuple
\* to `JsonSerialize`. For example, a sub-sequence of _TETrace.
    \* ASSUME
    \*     LET J == INSTANCE Json
    \*         IN J!JsonSerialize("Engine_MC_OrderBug_TTrace_1784382113.json", _TETrace)

=============================================================================

 Note that you can extract this module `Engine_MC_OrderBug_TEExpression`
  to a dedicated file to reuse `expression` (the module in the 
  dedicated `Engine_MC_OrderBug_TEExpression.tla` file takes precedence 
  over the module `Engine_MC_OrderBug_TEExpression` below).

---- MODULE Engine_MC_OrderBug_TEExpression ----
EXTENDS Sequences, TLCExt, Toolbox, Naturals, TLC, Engine_MC_OrderBug

expression == 
    [
        \* To hide variables of the `Engine_MC_OrderBug` spec from the error trace,
        \* remove the variables below.  The trace will be written in the order
        \* of the fields of this record.
        mergeLock |-> mergeLock
        ,status |-> status
        
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
\*---- MODULE Engine_MC_OrderBug_TETrace ----
\*EXTENDS IOUtils, TLC, Engine_MC_OrderBug
\*
\*trace == IODeserialize("Engine_MC_OrderBug_TTrace_1784382113.bin", TRUE)
\*
\*=============================================================================
\*

---- MODULE Engine_MC_OrderBug_TETrace ----
EXTENDS TLC, Engine_MC_OrderBug

trace == 
    <<
    ([mergeLock |-> FALSE,status |-> [i1 |-> "pending", i2 |-> "pending"]]),
    ([mergeLock |-> FALSE,status |-> [i1 |-> "running", i2 |-> "pending"]]),
    ([mergeLock |-> FALSE,status |-> [i1 |-> "running", i2 |-> "running"]])
    >>
----


=============================================================================

---- CONFIG Engine_MC_OrderBug_TTrace_1784382113 ----

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
\* Generated on Sat Jul 18 14:41:54 BST 2026
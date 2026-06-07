# pass: WSGI downgrade ratified by DDD entry

## Wave: DISCUSS

### [REF] Inherited commitments

| Origin | Commitment | DDD | Impact |
|--------|------------|-----|--------|
| n/a | real WSGI handler bound to /api/usage | n/a | protocol surface established |

## Wave: DESIGN

### [REF] Inherited commitments

| Origin | Commitment | DDD | Impact |
|--------|------------|-----|--------|
| DISCUSS#row1 | framework-agnostic dispatcher | DDD-1 | runtime probes confirm equivalence |

### [REF] Design Decisions

- DDD-1: WSGI handler removal authorized — switching to framework-agnostic dispatcher per portability mandate.

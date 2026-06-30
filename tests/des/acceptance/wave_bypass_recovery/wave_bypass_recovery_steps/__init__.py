"""AT package for fix-wave-bypass-recovery-truthful (JOB-019).

UNIQUE package name (``wave_bypass_recovery_steps``) per the dispatch contract --
NOT a generic ``steps`` / ``gate_steps`` -- so pytest-bdd's process-global step
registry never shadows another feature's step bodies (S1 step-text uniqueness).
"""

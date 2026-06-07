"""Substrate probe — wraps run_doctor for passive SessionStart health advisory.

Returns a one-line advisory if any install health checks fail, or an empty
string on a healthy install or any exception (fire-and-forget safety).

Design note: nwave_ai imports are intentionally deferred inside run_probe()
and guarded by try/except ImportError.  This preserves the fail-open contract
in standalone DES deployments where nwave_ai is not on sys.path.
"""

from __future__ import annotations


def run_probe(context: object = None) -> str:
    """Run install health checks and return an advisory string or empty string.

    Args:
        context: Doctor context supplying filesystem roots. Uses
            DoctorContext.from_defaults() when None.  Accepts ``object`` to
            avoid a hard type dependency on nwave_ai at import time.

    Returns:
        Empty string when all checks pass or any exception occurs.
        One-line advisory ending with newline when one or more checks fail.
    """
    try:
        # Deferred import: nwave_ai is optional in standalone DES deployments.
        # ImportError → fail-open (return "") so hooks always stay responsive.
        try:
            from nwave_ai.doctor.context import DoctorContext
            from nwave_ai.doctor.runner import run_doctor
        except ImportError:
            return ""

        resolved_context = (
            context if context is not None else DoctorContext.from_defaults()
        )
        results = run_doctor(resolved_context)
        failed_count = sum(1 for r in results if not r.passed)
        if failed_count == 0:
            return ""
        noun = "issue" if failed_count == 1 else "issues"
        return (
            f"⚠ nWave install health check: {failed_count} {noun} found"
            f" (run `nwave-ai doctor` for details).\n"
        )
    except Exception:
        return ""

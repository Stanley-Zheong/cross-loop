"""The convergence gate.

A phase is only ``done`` when its verify command succeeds (exit code 0). The
verify command is an ordinary shell command — ``npm test``, ``pytest -q``,
``ruff check .``, a custom eval script, anything that exits non-zero on failure.
If a phase declares no verify command, dispatch success (exit 0) is treated as
done.
"""

from __future__ import annotations

import subprocess
from typing import Optional, Tuple


def run_verify(
    verify_cmd: Optional[str],
    cwd: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Tuple[bool, str]:
    """Return (passed, combined_output)."""
    if not verify_cmd:
        return True, "(no verify command configured)"
    try:
        proc = subprocess.run(
            verify_cmd,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout or None,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, f"verify timed out after {timeout}s"

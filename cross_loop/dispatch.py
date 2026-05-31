"""Turn a tool adapter config + a prompt into an actual subprocess invocation.

This is the only place that knows how to translate the abstract notion of
"run this prompt on this tool with this model" into a concrete argv list. Each
phase runs as a brand-new process so it starts from a clean context window.
"""

from __future__ import annotations

import subprocess
from typing import Any, Dict, List, Optional, Tuple


def _subst(args: List[str], mapping: Dict[str, str]) -> List[str]:
    """Replace ``{placeholder}`` tokens inside each argv item."""
    out: List[str] = []
    for arg in args:
        s = arg
        for key, val in mapping.items():
            s = s.replace("{" + key + "}", val)
        out.append(s)
    return out


def build_command(
    tool_cfg: Dict[str, Any],
    prompt: str,
    model: Optional[str] = None,
    autonomous: bool = False,
    extra: Optional[List[str]] = None,
) -> List[str]:
    """Build the argv for one headless invocation.

    Order: ``command`` then model flags then autonomous flags then any extra
    flags then the prompt args. The prompt is passed as a single argv element
    (never through a shell), so arbitrary text — including slash commands like
    ``/gsd:execute-phase 1`` — is safe.
    """
    cmd: List[str] = [tool_cfg["command"]]

    if model:
        model_args = tool_cfg.get("model_args")
        if model_args:
            cmd += _subst(model_args, {"model": model})

    if autonomous:
        cmd += list(tool_cfg.get("autonomous_args", []))

    if extra:
        cmd += list(extra)

    prompt_args = tool_cfg.get("prompt_args", ["{prompt}"])
    cmd += _subst(prompt_args, {"prompt": prompt})
    return cmd


def run_command(
    cmd: List[str],
    cwd: Optional[str] = None,
    timeout: Optional[int] = None,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[int, str, str]:
    """Run argv, capturing output. Returns (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout or None,
            env=env,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError as exc:
        return 127, "", f"command not found: {cmd[0]} ({exc})"
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", f"timed out after {timeout}s"

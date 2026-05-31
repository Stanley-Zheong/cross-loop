"""Configuration loading for cross-loop.

Two kinds of config:

* the **global config** (``cross-loop.yaml``) — defaults like which tool to use,
  retry budget, timeouts;
* **per-tool adapter configs** (``config/tools/<name>.yaml``) — how to invoke a
  particular CLI: its command, how it takes a prompt and a model, its autonomous
  flags, and the models it exposes.

Everything is plain YAML so new tools can be added with no code changes.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Built-in fallbacks; a user cross-loop.yaml overrides any of these.
DEFAULT_GLOBAL_CONFIG: Dict[str, Any] = {
    "default_tool": "claude-code",
    "max_retries": 3,
    "stop_on_failure": False,
    "timeout": 0,  # 0 => no timeout
}


def _read_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping at the top level")
    return data


def load_global_config(path: Optional[str]) -> Dict[str, Any]:
    """Load the global config, layered on top of built-in defaults."""
    cfg = dict(DEFAULT_GLOBAL_CONFIG)
    candidate = path or os.environ.get("CROSS_LOOP_CONFIG")
    if not candidate:
        # opportunistically pick up ./cross-loop.yaml or ./config/cross-loop.yaml
        for guess in (Path.cwd() / "cross-loop.yaml", Path.cwd() / "config" / "cross-loop.yaml"):
            if guess.exists():
                candidate = str(guess)
                break
    if candidate:
        p = Path(candidate).expanduser()
        if not p.exists():
            raise FileNotFoundError(f"global config not found: {p}")
        cfg.update(_read_yaml(p))
    return cfg


def resolve_tools_dir(explicit: Optional[str], global_cfg: Dict[str, Any]) -> str:
    """Figure out where the per-tool adapter YAML files live."""
    candidate = explicit or os.environ.get("CROSS_LOOP_TOOLS_DIR") or global_cfg.get("tools_dir")
    if candidate:
        return str(Path(candidate).expanduser())
    # default search: ./config/tools, then the dir next to this package
    for base in (Path.cwd(), Path(__file__).resolve().parent.parent):
        guess = base / "config" / "tools"
        if guess.exists():
            return str(guess)
    return str(Path.cwd() / "config" / "tools")


def load_tool_config(tools_dir: str, name: str) -> Dict[str, Any]:
    """Load and lightly validate a single tool adapter config."""
    p = Path(tools_dir).expanduser() / f"{name}.yaml"
    if not p.exists():
        available = ", ".join(list_tools(tools_dir)) or "(none)"
        raise FileNotFoundError(f"no tool config '{name}' in {tools_dir}. Available: {available}")
    cfg = _read_yaml(p)
    cfg.setdefault("name", name)
    if "command" not in cfg:
        raise ValueError(f"tool config {p} is missing required key 'command'")
    cfg.setdefault("prompt_args", ["{prompt}"])
    cfg.setdefault("models", [])
    return cfg


def list_tools(tools_dir: str) -> List[str]:
    d = Path(tools_dir).expanduser()
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.yaml"))

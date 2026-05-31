"""Durable, file-backed state for the build loop.

The orchestrator stays (nearly) stateless on purpose — every meaningful fact
about progress is written to a JSON file after each step. That is what lets a
loop resume after a crash, and what keeps the controlling process's context
window clean: it can forget everything and re-read the state file.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

PENDING = "pending"
RUNNING = "running"
DONE = "done"
NEEDS_ATTENTION = "needs_attention"


class State:
    def __init__(self, path: str, data: Dict[str, Any] | None = None) -> None:
        self.path = Path(path)
        self.data = data or {"tasks": {}, "updated_at": None}

    @classmethod
    def load(cls, path: str) -> "State":
        p = Path(path)
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            data.setdefault("tasks", {})
        else:
            data = {"tasks": {}, "updated_at": None}
        return cls(path, data)

    def get(self, task_id: str) -> Dict[str, Any]:
        return self.data["tasks"].get(task_id, {"status": PENDING, "attempts": 0})

    def status(self, task_id: str) -> str:
        return self.get(task_id).get("status", PENDING)

    def is_done(self, task_id: str) -> bool:
        return self.status(task_id) == DONE

    def update(self, task_id: str, **fields: Any) -> None:
        task = self.data["tasks"].setdefault(task_id, {"status": PENDING, "attempts": 0})
        task.update(fields)
        self.save()

    def save(self) -> None:
        self.data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def reset(self) -> None:
        self.data = {"tasks": {}, "updated_at": None}
        self.save()

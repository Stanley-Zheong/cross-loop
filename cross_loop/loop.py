"""The build loop itself.

Walk the phases in order. For each unfinished phase, pick a tool + model,
dispatch it as a fresh process, then run the verify command. On failure, feed
the failure output back into the next attempt and retry — up to a budget. This
is the "converge until it passes" behaviour: iteration with feedback, gated by
a real test, bounded by a retry ceiling.
"""

from __future__ import annotations

import shlex
from typing import Any, Callable, Dict

from cross_loop import dispatch, verify
from cross_loop.state import DONE, NEEDS_ATTENTION, RUNNING, State

FEEDBACK_TEMPLATE = (
    "\n\n----- cross-loop: PREVIOUS ATTEMPT #{n} DID NOT PASS VERIFICATION -----\n"
    "Do not start over from scratch. Read the current code, diagnose why the\n"
    "verification step failed, and fix it. Verification output (tail):\n\n{output}\n"
    "----- end of previous failure -----\n"
)


def _tail(text: str, limit: int = 4000) -> str:
    text = text or ""
    return text[-limit:]


def _join(cmd) -> str:
    try:
        return shlex.join(cmd)
    except AttributeError:  # Python < 3.8 (shouldn't happen given requires-python)
        return " ".join(shlex.quote(c) for c in cmd)


def run_loop(
    tasks_doc: Dict[str, Any],
    state: State,
    tool_loader: Callable[[str], Dict[str, Any]],
    *,
    global_cfg: Dict[str, Any],
    overrides: Dict[str, Any],
    log: Callable[[str], None],
) -> State:
    defaults = tasks_doc.get("defaults", {})
    tasks = tasks_doc.get("tasks", [])

    cwd = overrides.get("cwd") or tasks_doc.get("cwd")
    max_retries_default = (
        overrides.get("max_retries")
        or defaults.get("max_retries")
        or global_cfg.get("max_retries", 3)
    )
    stop_on_failure = overrides.get("stop_on_failure", global_cfg.get("stop_on_failure", False))
    autonomous = overrides.get("yolo", False)
    dry_run = overrides.get("dry_run", False)
    timeout = (overrides.get("timeout") or global_cfg.get("timeout") or 0) or None

    completed = {t["id"] for t in tasks if state.is_done(t["id"])}

    for task in tasks:
        task_id = task["id"]
        if state.is_done(task_id):
            log(f"[skip] {task_id} — already done")
            continue

        unmet = [d for d in task.get("depends_on", []) if d not in completed]
        if unmet:
            log(f"[block] {task_id} — unmet dependencies {unmet}")
            state.update(task_id, status=NEEDS_ATTENTION, note=f"unmet deps: {unmet}")
            if stop_on_failure:
                break
            continue

        tool_name = (
            overrides.get("tool")
            or task.get("tool")
            or defaults.get("tool")
            or global_cfg.get("default_tool")
        )
        tool_cfg = tool_loader(tool_name)
        model = (
            overrides.get("model")
            or task.get("model")
            or defaults.get("model")
            or tool_cfg.get("default_model")
        )
        max_retries = int(task.get("max_retries", max_retries_default))
        base_prompt = task.get("prompt") or task.get("command")
        if not base_prompt:
            raise ValueError(f"task '{task_id}' has no 'prompt'")
        verify_cmd = task.get("verify")

        log(f"\n=== {task_id} | tool={tool_name} model={model} retries<={max_retries} ===")
        state.update(task_id, status=RUNNING, tool=tool_name, model=model)

        success = False
        attempt = 0
        last_out = ""
        while attempt < max_retries:
            attempt += 1
            prompt = base_prompt
            if attempt > 1:
                prompt = base_prompt + FEEDBACK_TEMPLATE.format(
                    n=attempt - 1, output=_tail(last_out)
                )
            cmd = dispatch.build_command(tool_cfg, prompt, model=model, autonomous=autonomous)
            log(f"[attempt {attempt}/{max_retries}] $ {_join(cmd)}")

            if dry_run:
                success = True
                last_out = "(dry-run: command not executed)"
                break

            rc, out, err = dispatch.run_command(cmd, cwd=cwd, timeout=timeout)
            combined = (out or "") + (err or "")
            if rc != 0:
                log(f"  dispatch exited rc={rc}")

            passed, vout = verify.run_verify(verify_cmd, cwd=cwd, timeout=timeout)
            if verify_cmd:
                success = passed
                last_out = combined + "\n--- VERIFY ---\n" + vout
            else:
                success = rc == 0
                last_out = combined

            if success:
                break

            note = "will retry" if attempt < max_retries else "out of retries"
            log(f"  verification failed — {note}")
            state.update(task_id, attempts=attempt, last_output=_tail(last_out, 2000))

        if success:
            state.update(task_id, status=DONE, attempts=attempt, last_output=_tail(last_out, 2000))
            completed.add(task_id)
            log(f"[done] {task_id} after {attempt} attempt(s)")
        else:
            state.update(
                task_id, status=NEEDS_ATTENTION, attempts=attempt, last_output=_tail(last_out, 2000)
            )
            log(f"[needs_attention] {task_id} failed after {attempt} attempt(s)")
            if stop_on_failure:
                log("stop_on_failure set — halting loop")
                break

    return state

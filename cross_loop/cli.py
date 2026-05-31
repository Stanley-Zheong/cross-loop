"""Command-line interface for cross-loop.

Subcommands:
  run     run (or resume) the build loop over a tasks file
  status  print the current progress table
  reset   clear saved progress for a tasks file
  tools   list configured tools and the models they expose
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from cross_loop import __version__
from cross_loop import config as cfgmod
from cross_loop.loop import run_loop
from cross_loop.state import State


def _load_tasks(path: str):
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"tasks file not found: {p}")
    with p.open("r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    if not isinstance(doc, dict) or "tasks" not in doc:
        raise ValueError("tasks file must be a mapping containing a 'tasks' list")
    ids = [t.get("id") for t in doc["tasks"]]
    if any(i is None for i in ids):
        raise ValueError("every task needs an 'id'")
    if len(ids) != len(set(ids)):
        raise ValueError("task ids must be unique")
    return doc, p


def _default_state_path(tasks_path: Path) -> str:
    return str(Path(tasks_path).with_suffix(".state.json"))


def _tool_loader_factory(tools_dir: str):
    cache: dict = {}

    def loader(name: str):
        if name not in cache:
            cache[name] = cfgmod.load_tool_config(tools_dir, name)
        return cache[name]

    return loader


def _print_status(doc, state) -> None:
    rows = []
    for t in doc.get("tasks", []):
        tid = t["id"]
        st = state.get(tid)
        rows.append(
            (
                tid,
                st.get("status", "pending"),
                str(st.get("attempts", 0)),
                f"{st.get('tool', '')} {st.get('model', '')}".strip(),
            )
        )
    width = max([len(r[0]) for r in rows] + [4])
    print(f"\n{'TASK':<{width}}  {'STATUS':<15} ATT  TOOL/MODEL")
    print("-" * (width + 33))
    for tid, status, attempts, toolmodel in rows:
        print(f"{tid:<{width}}  {status:<15} {attempts:<3}  {toolmodel}".rstrip())
    done = sum(1 for r in rows if r[1] == "done")
    print(f"\n{done}/{len(rows)} phases done")


def cmd_run(args) -> int:
    global_cfg = cfgmod.load_global_config(args.config)
    tools_dir = cfgmod.resolve_tools_dir(args.tools_dir, global_cfg)
    doc, tasks_path = _load_tasks(args.tasks)
    state_path = args.state or _default_state_path(tasks_path)
    state = State.load(state_path)
    loader = _tool_loader_factory(tools_dir)

    overrides = {
        "tool": args.tool,
        "model": args.model,
        "max_retries": args.max_retries,
        "yolo": args.yolo or None,
        "dry_run": args.dry_run or None,
        "stop_on_failure": args.stop_on_failure or None,
        "cwd": args.cwd,
        "timeout": args.timeout,
    }
    overrides = {k: v for k, v in overrides.items() if v is not None}

    def log(msg: str) -> None:
        print(msg, flush=True)

    log(f"cross-loop {__version__}")
    log(f"tasks={tasks_path}  state={state_path}  tools_dir={tools_dir}")
    run_loop(doc, state, loader, global_cfg=global_cfg, overrides=overrides, log=log)
    _print_status(doc, state)
    # exit non-zero if anything still needs attention
    unfinished = any(not state.is_done(t["id"]) for t in doc["tasks"])
    return 1 if unfinished else 0


def cmd_status(args) -> int:
    doc, tasks_path = _load_tasks(args.tasks)
    state_path = args.state or _default_state_path(tasks_path)
    state = State.load(state_path)
    _print_status(doc, state)
    return 0


def cmd_reset(args) -> int:
    doc, tasks_path = _load_tasks(args.tasks)
    state_path = args.state or _default_state_path(tasks_path)
    state = State.load(state_path)
    state.reset()
    print(f"cleared progress: {state_path}")
    return 0


def cmd_tools(args) -> int:
    global_cfg = cfgmod.load_global_config(args.config)
    tools_dir = cfgmod.resolve_tools_dir(args.tools_dir, global_cfg)
    names = cfgmod.list_tools(tools_dir)
    if not names:
        print(f"no tool configs found in {tools_dir}")
        return 1
    print(f"tools dir: {tools_dir}\n")
    for name in names:
        cfg = cfgmod.load_tool_config(tools_dir, name)
        models = cfg.get("models", []) or []
        default = cfg.get("default_model", "")
        marked = [f"{m}*" if m == default else m for m in models]
        print(f"  {name:<14} command={cfg.get('command')}")
        print(f"  {'':<14} models: {', '.join(marked) or '(unspecified)'}")
    print("\n(* = default model)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cross-loop",
        description="Drive multiple AI coding CLIs through a self-verifying build loop.",
    )
    parser.add_argument("--version", action="version", version=f"cross-loop {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p):
        p.add_argument("--tasks", required=True, help="path to the tasks/phases YAML file")
        p.add_argument("--state", help="path to the state file (default: alongside tasks)")
        p.add_argument("--config", help="path to global cross-loop.yaml")
        p.add_argument("--tools-dir", help="directory of per-tool adapter configs")

    p_run = sub.add_parser("run", help="run or resume the build loop")
    add_common(p_run)
    p_run.add_argument("--tool", help="override the tool for every phase")
    p_run.add_argument("--model", help="override the model for every phase")
    p_run.add_argument("--max-retries", type=int, help="convergence budget per phase")
    p_run.add_argument("--cwd", help="working directory the tools run in")
    p_run.add_argument("--timeout", type=int, help="per-attempt timeout in seconds")
    p_run.add_argument("--yolo", action="store_true", help="enable a tool's autonomous flags")
    p_run.add_argument("--stop-on-failure", action="store_true",
                       help="halt the loop if a phase exhausts retries")
    p_run.add_argument("--dry-run", action="store_true",
                       help="print the commands without executing them")
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser("status", help="show progress")
    add_common(p_status)
    p_status.set_defaults(func=cmd_status)

    p_reset = sub.add_parser("reset", help="clear saved progress")
    add_common(p_reset)
    p_reset.set_defaults(func=cmd_reset)

    p_tools = sub.add_parser("tools", help="list configured tools and models")
    p_tools.add_argument("--config", help="path to global cross-loop.yaml")
    p_tools.add_argument("--tools-dir", help="directory of per-tool adapter configs")
    p_tools.set_defaults(func=cmd_tools)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

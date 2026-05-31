"""Smoke tests that don't require any real coding CLI to be installed."""

from pathlib import Path


from cross_loop import config as cfgmod
from cross_loop.dispatch import build_command
from cross_loop.loop import run_loop
from cross_loop.state import DONE, NEEDS_ATTENTION, State

REPO = Path(__file__).resolve().parent.parent
TOOLS_DIR = str(REPO / "config" / "tools")


def test_build_command_substitution():
    tool = {
        "command": "claude",
        "prompt_args": ["-p", "{prompt}"],
        "model_args": ["--model", "{model}"],
        "autonomous_args": ["--dangerously-skip-permissions"],
    }
    cmd = build_command(tool, "/gsd:execute-phase 1", model="opus", autonomous=True)
    assert cmd == [
        "claude",
        "--model",
        "opus",
        "--dangerously-skip-permissions",
        "-p",
        "/gsd:execute-phase 1",
    ]


def test_build_command_no_model_no_yolo():
    tool = {"command": "codex", "prompt_args": ["exec", "{prompt}"]}
    assert build_command(tool, "do it") == ["codex", "exec", "do it"]


def test_shipped_tool_configs_load():
    names = cfgmod.list_tools(TOOLS_DIR)
    assert {"claude-code", "codex", "cursor", "opencode"} <= set(names)
    for name in names:
        cfg = cfgmod.load_tool_config(TOOLS_DIR, name)
        assert "command" in cfg


def test_state_roundtrip(tmp_path):
    sp = tmp_path / "x.state.json"
    st = State.load(str(sp))
    st.update("a", status=DONE, attempts=2)
    again = State.load(str(sp))
    assert again.is_done("a")
    assert again.get("a")["attempts"] == 2


def test_loop_converges_on_retry(tmp_path):
    """A mock tool that only passes verify on the 2nd attempt should converge."""
    counter = tmp_path / "count.txt"
    # mock 'tool': each call appends a line to count.txt
    mock = tmp_path / "mock.sh"
    mock.write_text("#!/usr/bin/env bash\necho run >> '%s'\n" % counter)
    mock.chmod(0o755)
    # verify passes only once count.txt has >= 2 lines
    verify = f"test $(wc -l < '{counter}') -ge 2"

    tool_loader = lambda name: {"command": str(mock), "prompt_args": ["{prompt}"]}
    doc = {"tasks": [{"id": "p1", "prompt": "do work", "verify": verify, "max_retries": 5}]}
    state = State(str(tmp_path / "t.state.json"))
    run_loop(
        doc,
        state,
        tool_loader,
        global_cfg={"max_retries": 5},
        overrides={},
        log=lambda m: None,
    )
    assert state.status("p1") == DONE
    assert state.get("p1")["attempts"] == 2


def test_loop_marks_needs_attention_when_verify_never_passes(tmp_path):
    tool_loader = lambda name: {"command": "true", "prompt_args": ["{prompt}"]}
    doc = {"tasks": [{"id": "p1", "prompt": "x", "verify": "false", "max_retries": 2}]}
    state = State(str(tmp_path / "t.state.json"))
    run_loop(doc, state, tool_loader, global_cfg={}, overrides={}, log=lambda m: None)
    assert state.status("p1") == NEEDS_ATTENTION
    assert state.get("p1")["attempts"] == 2


def test_dependencies_block(tmp_path):
    tool_loader = lambda name: {"command": "true", "prompt_args": ["{prompt}"]}
    doc = {
        "tasks": [
            {"id": "a", "prompt": "x", "verify": "false", "max_retries": 1},
            {"id": "b", "prompt": "y", "depends_on": ["a"]},
        ]
    }
    state = State(str(tmp_path / "t.state.json"))
    run_loop(doc, state, tool_loader, global_cfg={}, overrides={}, log=lambda m: None)
    assert state.status("a") == NEEDS_ATTENTION
    # b's dependency never completed, so b should be blocked
    assert state.status("b") == NEEDS_ATTENTION

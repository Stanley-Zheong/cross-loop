"""Tests for cross-run / cross-phase memory and its injection into prompts.

The headline test (`test_lesson_from_failed_phase_is_injected_into_later_phase`)
is the real signal: a lesson a *failed* phase records shows up in a *later*
phase's prompt. That is "read accumulated assets at decision time" reduced to
something a test can pin down with no real CLI installed.
"""

from cross_loop.loop import run_loop
from cross_loop.memory import Memory, memory_path_for
from cross_loop.state import DONE, NEEDS_ATTENTION, State


def test_memory_path_derivation():
    assert memory_path_for("/x/tasks.state.json") == "/x/tasks.memory.json"
    assert memory_path_for("/x/foo.json") == "/x/foo.json.memory.json"


def test_record_and_relevant_ordering(tmp_path):
    m = Memory(str(tmp_path / "m.memory.json"))
    m.record("a", "failure", "lesson A1")
    m.record("b", "failure", "lesson B1")
    m.record("a", "resolved", "lesson A2")
    texts = [e["text"] for e in m.relevant("a", limit=10)]
    # same-phase first (most recent first), then others
    assert texts[0] == "lesson A2"
    assert texts[1] == "lesson A1"
    assert "lesson B1" in texts
    # blank text is ignored, not recorded
    m.record("a", "failure", "   ")
    assert len(m.data["learnings"]) == 3


def test_render_empty_and_nonempty(tmp_path):
    m = Memory(str(tmp_path / "m.memory.json"))
    assert m.render([]) == ""
    m.record("a", "failure", "boom happened")
    block = m.render(m.relevant("z"))
    assert "boom happened" in block
    assert "MEMORY" in block


def test_persists_across_reload(tmp_path):
    p = str(tmp_path / "m.memory.json")
    Memory(p).record("a", "failure", "remember me")
    again = Memory.load(p)
    assert any("remember me" in e["text"] for e in again.data["learnings"])


def _capture_tool(tmp_path):
    """A mock 'tool' that appends the prompt it received to capture.txt."""
    cap = tmp_path / "capture.txt"
    mock = tmp_path / "mock.sh"
    mock.write_text('#!/usr/bin/env bash\nprintf "%s\\n===SEP===\\n" "$1" >> "' + str(cap) + '"\n')
    mock.chmod(0o755)
    return mock, cap


def _two_phase_doc():
    return {
        "tasks": [
            {
                "id": "a",
                "prompt": "do A",
                "verify": "echo DISTINCTIVE_LESSON_XYZ; false",
                "max_retries": 1,
            },
            {"id": "b", "prompt": "do B", "verify": "true"},
        ]
    }


def test_lesson_from_failed_phase_is_injected_into_later_phase(tmp_path):
    mock, cap = _capture_tool(tmp_path)
    tool_loader = lambda name: {"command": str(mock), "prompt_args": ["{prompt}"]}
    logs = []
    mem = Memory(str(tmp_path / "t.memory.json"))
    state = State(str(tmp_path / "t.state.json"))

    run_loop(
        _two_phase_doc(),
        state,
        tool_loader,
        global_cfg={"max_retries": 1},
        overrides={},
        log=logs.append,
        memory=mem,
    )

    assert state.status("a") == NEEDS_ATTENTION
    assert state.status("b") == DONE
    # phase a recorded a failure lesson carrying the distinctive verify output
    assert any("DISTINCTIVE_LESSON_XYZ" in e["text"] for e in mem.data["learnings"])
    # phase b's prompt (captured by the mock tool) contains phase a's lesson
    assert "DISTINCTIVE_LESSON_XYZ" in cap.read_text()
    # and the loop logged the injection — the "asset was referenced" signal
    assert any("[memory] injected" in m and "into b" in m for m in logs)


def test_no_memory_means_no_injection(tmp_path):
    mock, cap = _capture_tool(tmp_path)
    tool_loader = lambda name: {"command": str(mock), "prompt_args": ["{prompt}"]}
    state = State(str(tmp_path / "t.state.json"))

    run_loop(
        _two_phase_doc(),
        state,
        tool_loader,
        global_cfg={"max_retries": 1},
        overrides={},
        log=lambda m: None,
    )  # no memory= passed → behaviour unchanged
    assert "DISTINCTIVE_LESSON_XYZ" not in cap.read_text()

"""Direct tests for the convergence gate (``run_verify``).

The whole loop hinges on this function: a phase is ``done`` only when its verify
command exits 0. The existing smoke tests exercise it indirectly through the
loop; these pin down its contract directly — no command, pass, fail, captured
output, cwd, and timeout.
"""

from cross_loop.verify import run_verify


def test_no_command_passes():
    passed, out = run_verify(None)
    assert passed is True
    assert "no verify" in out.lower()
    # empty string is also "no command"
    assert run_verify("")[0] is True


def test_exit_zero_passes_and_captures_stdout():
    passed, out = run_verify("echo hello")
    assert passed is True
    assert "hello" in out


def test_nonzero_exit_fails_and_captures_output():
    passed, out = run_verify("echo nope; exit 3")
    assert passed is False
    assert "nope" in out


def test_stderr_is_captured():
    passed, out = run_verify("echo boom 1>&2; exit 1")
    assert passed is False
    assert "boom" in out


def test_cwd_is_honored(tmp_path):
    (tmp_path / "marker").write_text("x")
    # `test -f marker` only passes if the command runs inside tmp_path
    assert run_verify("test -f marker", cwd=str(tmp_path))[0] is True
    assert run_verify("test -f marker")[0] is False


def test_timeout_fails_gracefully():
    passed, out = run_verify("sleep 2", timeout=1)
    assert passed is False
    assert "timed out" in out

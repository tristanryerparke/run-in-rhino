"""Example test that forwards a Rhino exception to the parent server."""

from run_in_rhino.pipe import run_script
from run_in_rhino.server import server


SCRIPT = """
from run_in_rhino.rhino_env.client import SocketConnection
from run_in_rhino.rhino_env.parasite import OutputParasite


def divide_by_zero(x):
    return x / 0


connection = SocketConnection()
with OutputParasite(connection):
    divide_by_zero(1)
"""


def test_rhino_error_forwards_traceback_and_quits(rhino_instance):
    terminal_output = []

    for status, data in server():
        if status == "ready":
            run_script(script=SCRIPT, pipe_path=rhino_instance.pipe_path)
        elif status == "terminal":
            terminal_output.append(data)

    assert status == "quit"
    traceback_output = "".join(terminal_output)
    assert "Traceback (most recent call last):" in traceback_output
    assert "ZeroDivisionError: division by zero" in traceback_output

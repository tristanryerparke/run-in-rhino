import sys

import pytest

from run_in_rhino.rhino_env import client
from run_in_rhino.rhino_env.parasite import OutputParasite


class Connection:
    def __init__(self):
        self.output = []

    def send_terminal(self, output):
        self.output.append(output)


def test_debug_to_server_prints_and_sends_by_default(capsys):
    connection = Connection()

    client.debug_to_server("one", connection=connection)

    assert capsys.readouterr().out == "one\n"
    assert connection.output == ["'one'"]


def test_debug_to_server_can_send_without_printing(capsys):
    connection = Connection()

    client.debug_to_server("one", connection=connection, send_only=True)

    assert capsys.readouterr().out == ""
    assert connection.output == ["'one'"]


def test_output_parasite_sends_stdout_and_stderr(capsys):
    connection = Connection()

    with OutputParasite(connection):
        print("stdout")
        print("stderr", file=sys.stderr)

    captured = capsys.readouterr()
    assert captured.out == "stdout\n"
    assert captured.err == "stderr\n"
    assert connection.output == ["stdout\nstderr\n"]


def test_output_parasite_flush_sends_output_early():
    connection = Connection()

    with OutputParasite(connection) as output:
        print("first")
        output.flush()
        print("second")

    assert connection.output == ["first\n", "second\n"]


def test_output_parasite_can_send_done_after_output():
    events = []

    class LifecycleConnection:
        def send_terminal(self, output):
            events.append(("terminal", output))

        def send_done(self):
            events.append(("done", None))

    with OutputParasite(LifecycleConnection(), done_msg=True):
        print("finished")

    assert events == [("terminal", "finished\n"), ("done", None)]


def test_output_parasite_preserves_wrapped_exceptions():
    connection = Connection()

    with pytest.raises(ValueError, match="failed"):
        with OutputParasite(connection):
            print("before failure")
            raise ValueError("failed")

    assert connection.output == ["before failure\n"]


class UnavailableConnection:
    def send_terminal(self, output):
        raise OSError("connection refused")


def test_output_parasite_runs_without_a_connection():
    with OutputParasite() as output:
        print("captured without a connection")

    assert output.output.getvalue() == "captured without a connection\n"


def test_output_parasite_ignores_send_failures():
    with OutputParasite(UnavailableConnection()):
        print("still runs")

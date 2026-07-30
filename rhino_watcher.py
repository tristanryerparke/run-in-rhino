import sys
from contextlib import contextmanager
from contextlib import redirect_stderr
from contextlib import redirect_stdout
from io import StringIO

from client import send_message

DONE_MESSAGE = "__RHINO_DONE__"


@contextmanager
def websocket_output():
    output = StringIO()
    try:
        with redirect_stdout(output), redirect_stderr(output):
            yield
    finally:
        captured = output.getvalue()
        if captured:
            send_message(captured)


def send_done():
    return send_message(DONE_MESSAGE)



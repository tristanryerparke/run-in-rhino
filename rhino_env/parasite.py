#! python 3
# To be run in rhino

import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO


class _OutputRecorder:
    def __init__(self, stream, output):
        self.stream = stream
        self.output = output

    def write(self, text):
        result = self.stream.write(text)
        self.output.write(text)
        return result

    def flush(self):
        self.stream.flush()
        self.output.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


class OutputParasite:
    """Context manager class to optionally send terminal output from 
    within the context to a provided websocket server."""
    def __init__(self, connection=None, done_msg=False):
        self.connection = connection
        self.output = StringIO()
        self._stdout = redirect_stdout(_OutputRecorder(sys.stdout, self.output))
        self._stderr = redirect_stderr(_OutputRecorder(sys.stderr, self.output))

    def __enter__(self):
        self._stdout.__enter__()
        self._stderr.__enter__()
        return self

    def flush(self):
        """Send captured output now and clear it after a successful send."""
        output = self.output.getvalue()
        if not output or self.connection is None:
            return None
        try:
            result = self.connection.send_terminal(output)
        except Exception:
            return None
        self.output.seek(0)
        self.output.truncate(0)
        return result

    def __exit__(self, exc_type, exc_value, traceback):
        self._stderr.__exit__(exc_type, exc_value, traceback)
        self._stdout.__exit__(exc_type, exc_value, traceback)
        self.flush()
        return False

#! python 3
# To be run in rhino

import json
import traceback


class JsonlLogger:
    """Append JSON log lines to a parent-provided file.

    Pass the module-level ``RUN_IN_RHINO_LOG`` value (set by rhino-log) as the
    path. When a script runs without run-in-rhino that global is undefined, so
    ``globals().get("RUN_IN_RHINO_LOG")`` gives ``None`` and every method
    becomes a clean no-op while still printing locally.

    Use as a context manager to send ``done`` automatically on clean exit;
    an exception sends the traceback plus ``quit`` instead.
    """

    def __init__(self, path=None, echo=True):
        self.path = path
        self.echo = echo

    def log(self, data, type="terminal"):
        if self.echo and data is not None:
            print(data)
        if self.path is None:
            return None
        try:
            with open(self.path, "a", encoding="utf-8") as file:
                file.write(json.dumps({"type": type, "data": data}) + "\n")
        except OSError:
            return None

    def send_done(self):
        self.log(None, type="done")

    def send_quit(self):
        self.log(None, type="quit")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback_value):
        if exc_type is not None:
            self.log(
                "".join(
                    traceback.format_exception(exc_type, exc_value, traceback_value)
                )
            )
            self.send_quit()
        else:
            self.send_done()
        return False

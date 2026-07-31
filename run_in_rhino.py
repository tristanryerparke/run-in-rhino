import asyncio
from pathlib import Path
from threading import Event
from threading import Thread

import pipe
import server


_ROOT = Path(__file__).resolve().parent
_CLIENT_SCRIPT = _ROOT / "client.py"
_DONE_SCRIPT = _ROOT / "send_done.py"


class RhinoServer:
    def __init__(self, pipe_path=None):
        self.pipe_path = pipe_path
        self._ready = Event()
        self._done = Event()
        self._error = None
        self._thread = None
        self._warmed_up = False

    def start(self, timeout=10):
        if self._thread is not None:
            raise RuntimeError("Rhino server already started")

        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            raise TimeoutError("Timed out starting the Rhino WebSocket server")
        if self._error is not None:
            raise RuntimeError("Rhino server failed to start") from self._error
        return self

    def _run(self):
        try:
            asyncio.run(server.serve(ready=self._ready))
        except BaseException as error:
            self._error = error
            self._ready.set()
        finally:
            self._done.set()

    def run_file(self, script_path):
        """Execute a Python file inside Rhino while this server is running."""
        if self._done.is_set():
            raise RuntimeError("Rhino server is not running")
        if not self._warmed_up:
            pipe.run_rhino_script(_CLIENT_SCRIPT, pipe_path=self.pipe_path)
            self._warmed_up = True
        return pipe.run_rhino_script(script_path, pipe_path=self.pipe_path)

    def run_done_script(self):
        """Run the Rhino-side script that sends the server done message."""
        return self.run_file(_DONE_SCRIPT)

    def finish(self):
        return self.run_done_script()

    def wait(self, timeout=None):
        if not self._done.wait(timeout):
            raise TimeoutError("Timed out waiting for the Rhino server")
        if self._error is not None:
            raise RuntimeError("Rhino server failed") from self._error
        return None

    def close(self):
        if not self._done.is_set():
            self.finish()
        self.wait()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


def start_server(pipe_path=None, timeout=10):
    """Start a controllable Rhino watcher without running a file."""
    return RhinoServer(pipe_path=pipe_path).start(timeout)

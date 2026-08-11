import asyncio
from pathlib import Path
from queue import Empty
from queue import Queue
from threading import Event
from threading import Thread

import pipe
import server


_ROOT = Path(__file__).resolve().parent
_CLIENT_SCRIPT = _ROOT / "client.py"
_ENVIRONMENT_SCRIPT = _ROOT / "rhino_environment.py"
_END_SCRIPT = _ROOT / "send_end.py"
_QUIT_SCRIPT = _ROOT / "send_quit.py"


class RhinoServer:
    def __init__(self, pipe_path=None, nostop=False, environment=None):
        self.pipe_path = pipe_path
        self.nostop = nostop
        self.environment = server.normalize_environment(environment)
        self._ready = Event()
        self._done = Event()
        self._error = None
        self._thread = None
        self._warmed_up = False
        self._environment_installed = False
        self._data = Queue()

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
            asyncio.run(
                server.serve(
                    ready=self._ready,
                    data_queue=self._data,
                    stop_on_end=not self.nostop,
                    environment=self.environment,
                )
            )
        except BaseException as error:
            self._error = error
            self._ready.set()
        finally:
            self._done.set()

    def _ensure_rhino_ready(self):
        if self._done.is_set():
            raise RuntimeError("Rhino server is not running")
        if not self._warmed_up:
            pipe.run_script(_CLIENT_SCRIPT, pipe_path=self.pipe_path)
            self._warmed_up = True
        if self.environment is not None and not self._environment_installed:
            pipe.run_script(_ENVIRONMENT_SCRIPT, pipe_path=self.pipe_path)
            self._environment_installed = True

    def run_file(self, script_path):
        """Execute a Python file inside Rhino while this server is running."""
        self._ensure_rhino_ready()
        return pipe.run_script(script_path, pipe_path=self.pipe_path)

    def run_command(self, command):
        """Execute a top-level Rhino command while this server is running."""
        self._ensure_rhino_ready()
        return pipe.run_command(command, pipe_path=self.pipe_path)

    def take_data(self, timeout=0):
        data = []
        try:
            data.append(self._data.get(timeout=timeout))
        except Empty:
            return data
        while True:
            try:
                data.append(self._data.get_nowait())
            except Empty:
                return data

    def run_end_script(self):
        """Run the Rhino-side script that sends an end message."""
        return self.run_file(_END_SCRIPT)

    def run_quit_script(self):
        """Run the Rhino-side script that sends a quit message."""
        return self.run_file(_QUIT_SCRIPT)

    def finish(self):
        return self.run_end_script()

    def wait(self, timeout=None):
        if not self._done.wait(timeout):
            raise TimeoutError("Timed out waiting for the Rhino server")
        if self._error is not None:
            raise RuntimeError("Rhino server failed") from self._error
        return None

    def close(self):
        if not self._done.is_set():
            if self.nostop:
                self.run_quit_script()
            else:
                self.finish()
        self.wait()

    def __enter__(self):
        return self if self._thread is not None else self.start()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


def start_server(pipe_path=None, timeout=10, nostop=False, environment=None):
    """Start a controllable Rhino watcher without running a file.

    ``environment`` is installed in Rhino before the first ``run_file``.
    With ``nostop=True``, an end message leaves the watcher available for
    subsequent ``run_file()`` calls; the context manager closes it with quit.
    """
    return RhinoServer(
        pipe_path=pipe_path,
        nostop=nostop,
        environment=environment,
    ).start(timeout)

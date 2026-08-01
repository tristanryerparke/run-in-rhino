import asyncio
import json
import queue
import sys
import threading
import time
from contextlib import asynccontextmanager
from contextlib import contextmanager
from contextlib import redirect_stderr
from contextlib import redirect_stdout
from io import StringIO

from client import TIMING_ENABLED
from client import send_message
from client import send_message_sync

END_COMMAND = "end"
QUIT_COMMAND = "quit"
DONE_COMMAND = END_COMMAND
TIMING_PREFIX = "[RHINO-WATCH-CLIENT] "
_async_queue = None
_async_sender_task = None
_async_send_error = None
_sync_queue = None
_sync_sender_thread = None
_sync_send_error = None


class _OutputTee:
    def __init__(self, stream, capture):
        self._stream = (
            stream._stream if isinstance(stream, _OutputTee) else stream
        )
        self._capture = capture

    def write(self, text):
        self._stream.write(text)
        return self._capture.write(text)

    def flush(self):
        self._stream.flush()
        self._capture.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


@contextmanager
def _tee_output():
    output = StringIO()
    with redirect_stdout(_OutputTee(sys.stdout, output)), redirect_stderr(
        _OutputTee(sys.stderr, output)
    ):
        yield output


async def _drain_async_queue():
    global _async_send_error
    while True:
        captured = await _async_queue.get()
        try:
            await send_log(captured)
        except Exception as error:
            _async_send_error = error
        finally:
            _async_queue.task_done()


async def _send_async_capture(captured):
    global _async_queue, _async_sender_task
    if _async_queue is None:
        _async_queue = asyncio.Queue()
        _async_sender_task = asyncio.create_task(_drain_async_queue())

    started = time.perf_counter()
    _async_queue.put_nowait(captured)
    elapsed_ms = (time.perf_counter() - started) * 1000
    if TIMING_ENABLED:
        print("{}context exit async enqueue: {:.3f} ms".format(TIMING_PREFIX, elapsed_ms))


def _send_sync_capture(captured):
    started = time.perf_counter()
    send_log_sync(captured)
    elapsed_ms = (time.perf_counter() - started) * 1000
    if TIMING_ENABLED:
        print("{}context exit sync: {:.3f} ms".format(TIMING_PREFIX, elapsed_ms))


def _drain_sync_queue():
    global _sync_send_error
    while True:
        captured = _sync_queue.get()
        try:
            if captured is None:
                return
            send_log_sync(captured)
        except Exception as error:
            _sync_send_error = error
        finally:
            _sync_queue.task_done()


def _send_sync_capture_deferred(captured):
    global _sync_queue, _sync_sender_thread
    if _sync_queue is None:
        _sync_queue = queue.Queue()
        _sync_sender_thread = threading.Thread(target=_drain_sync_queue, daemon=True)
        _sync_sender_thread.start()

    started = time.perf_counter()
    _sync_queue.put_nowait(captured)
    elapsed_ms = (time.perf_counter() - started) * 1000
    if TIMING_ENABLED:
        print("{}context exit sync enqueue: {:.3f} ms".format(TIMING_PREFIX, elapsed_ms))


@asynccontextmanager
async def websocket_output():
    try:
        with _tee_output() as output:
            yield
    finally:
        captured = output.getvalue()
        if captured:
            await _send_async_capture(captured)


@contextmanager
def websocket_output_sync():
    try:
        with _tee_output() as output:
            yield
    finally:
        captured = output.getvalue()
        if captured:
            _send_sync_capture(captured)


@contextmanager
def websocket_output_deferred():
    try:
        with _tee_output() as output:
            yield
    finally:
        captured = output.getvalue()
        if captured:
            _send_sync_capture_deferred(captured)


def _message(message_type, **payload):
    return json.dumps({"type": message_type, **payload}, separators=(",", ":"))


async def send_log(message):
    return await send_message(_message("log", message=str(message)))


def send_log_sync(message):
    return send_message_sync(_message("log", message=str(message)))


async def send_data(data):
    return await send_message(_message("data", data=data))


def send_data_sync(data):
    return send_message_sync(_message("data", data=data))


async def send_command(command):
    return await send_message(_message("command", command=str(command)))


def send_command_sync(command):
    return send_message_sync(_message("command", command=str(command)))


async def _send_lifecycle_command(command):
    if _async_queue is not None:
        await _async_queue.join()
    if _async_send_error is not None:
        raise _async_send_error
    return await send_command(command)


def _send_lifecycle_command_sync_deferred(command):
    if _sync_queue is not None:
        _sync_queue.join()
        if _sync_send_error is not None:
            raise _sync_send_error
        _sync_queue.put(None)
        _sync_queue.join()
        _sync_sender_thread.join()
    return send_command_sync(command)


async def send_end():
    return await _send_lifecycle_command(END_COMMAND)


def send_end_sync():
    return send_command_sync(END_COMMAND)


def send_end_sync_deferred():
    return _send_lifecycle_command_sync_deferred(END_COMMAND)


async def send_quit():
    return await _send_lifecycle_command(QUIT_COMMAND)


def send_quit_sync():
    return send_command_sync(QUIT_COMMAND)


def send_quit_sync_deferred():
    return _send_lifecycle_command_sync_deferred(QUIT_COMMAND)


send_done = send_end
send_done_sync = send_end_sync
send_done_sync_deferred = send_end_sync_deferred


if __name__ == "__main__":
    async def main():
        async with websocket_output():
            print("Hello from Rhino")
            print("stderr from Rhino", file=sys.stderr)
        await send_end()

    asyncio.run(main())

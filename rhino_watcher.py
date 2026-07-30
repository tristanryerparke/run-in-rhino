import asyncio
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

DONE_MESSAGE = "__RHINO_DONE__"
TIMING_PREFIX = "[RHINO-WATCH-CLIENT] "
_async_queue = None
_async_sender_task = None
_async_send_error = None
_sync_queue = None
_sync_sender_thread = None
_sync_send_error = None


async def _drain_async_queue():
    global _async_send_error
    while True:
        captured = await _async_queue.get()
        try:
            await send_message(captured)
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
    send_message_sync(captured)
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
            send_message_sync(captured)
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
    output = StringIO()
    try:
        with redirect_stdout(output), redirect_stderr(output):
            yield
    finally:
        captured = output.getvalue()
        if captured:
            await _send_async_capture(captured)


@contextmanager
def websocket_output_sync():
    output = StringIO()
    try:
        with redirect_stdout(output), redirect_stderr(output):
            yield
    finally:
        captured = output.getvalue()
        if captured:
            _send_sync_capture(captured)


@contextmanager
def websocket_output_deferred():
    output = StringIO()
    try:
        with redirect_stdout(output), redirect_stderr(output):
            yield
    finally:
        captured = output.getvalue()
        if captured:
            _send_sync_capture_deferred(captured)


async def send_done():
    if _async_queue is not None:
        await _async_queue.join()
    if _async_send_error is not None:
        raise _async_send_error
    return await send_message(DONE_MESSAGE)


def send_done_sync():
    return send_message_sync(DONE_MESSAGE)


def send_done_sync_deferred():
    if _sync_queue is not None:
        _sync_queue.join()
        if _sync_send_error is not None:
            raise _sync_send_error
        _sync_queue.put(None)
        _sync_queue.join()
        _sync_sender_thread.join()
    return send_message_sync(DONE_MESSAGE)


if __name__ == "__main__":
    async def main():
        async with websocket_output():
            print("Hello from Rhino")
            print("stderr from Rhino", file=sys.stderr)
        await send_done()

    asyncio.run(main())

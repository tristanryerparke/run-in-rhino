import json
import os
import shutil
import tempfile
import time

from .pipe import run_script


def _inject_log_path(source, log_path):
    """Insert the log path assignment after any leading magic comment lines."""
    lines = source.splitlines(keepends=True)
    index = 0
    while index < len(lines) and lines[index].lstrip().startswith("#"):
        index += 1
    header = "RUN_IN_RHINO_LOG = {!r}\n\n".format(log_path)
    return "".join(lines[:index]) + header + "".join(lines[index:])


def tail_jsonl(path, poll_interval=0.05):
    """Yield parsed JSON lines appended to ``path``, polling until stopped."""
    position = 0
    remainder = ""
    while True:
        with open(path, "r", encoding="utf-8") as file:
            file.seek(position)
            chunk = file.read()
            position = file.tell()
        if chunk:
            remainder += chunk
            lines = remainder.split("\n")
            remainder = lines.pop()
            for line in lines:
                if line.strip():
                    yield json.loads(line)
        time.sleep(poll_interval)


def log_session(
    script_path=None,
    *,
    script=None,
    pipe_path=None,
    stop=True,
    poll_interval=0.05,
):
    """Submit a script to Rhino with an injected log path and stream its log.

    Yields ``(status, data)`` pairs like the websocket server: ``"terminal"``
    and ``"data"`` messages carry payloads; ``"done"`` ends the stream unless
    ``stop`` is false, and ``"quit"`` always ends it. The temp log directory
    is removed when the generator finishes.
    """
    if (script_path is None) == (script is None):
        raise ValueError("Provide exactly one of script_path or script")
    if script_path is not None:
        with open(script_path, encoding="utf-8") as file:
            script = file.read()

    directory = tempfile.mkdtemp(prefix="rhinocode_log_")
    log_path = os.path.join(directory, "log.jsonl")
    with open(log_path, "w", encoding="utf-8"):
        pass
    try:
        run_script(
            script=_inject_log_path(script, log_path),
            pipe_path=pipe_path,
        )
        for message in tail_jsonl(log_path, poll_interval=poll_interval):
            message_type = message.get("type")
            yield message_type, message.get("data")
            if message_type == "quit" or (message_type == "done" and stop):
                return
    finally:
        shutil.rmtree(directory, ignore_errors=True)

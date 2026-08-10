import glob
import json
import os
import socket
import tempfile
import time


PIPE_NAME_PREFIX = "rhinocode_remotepipe_"
SOCKET_NAME_PREFIX = "CoreFxPipe_" + PIPE_NAME_PREFIX


def _pipe_roots():
    roots = [tempfile.gettempdir()]
    tmpdir = os.environ.get("TMPDIR")
    if tmpdir and tmpdir not in roots:
        roots.append(tmpdir)
    return roots


def list_pipes():
    pipes = {}
    for root in _pipe_roots():
        for path in glob.glob(os.path.join(root, SOCKET_NAME_PREFIX + "*")):
            if os.path.exists(path):
                pipes[path] = path
    return sorted(pipes.values())


def _resolve_pipe(pipe_path=None):
    if pipe_path:
        if os.path.exists(pipe_path):
            return pipe_path
        raise FileNotFoundError("Rhino pipe not found: " + pipe_path)

    pipes = list_pipes()
    if not pipes:
        raise RuntimeError("No running RhinoCode pipe found")
    return pipes[0]


def _send_request(payload, pipe_path):
    encoded = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(pipe_path)
        client.sendall(encoded)
        chunks = []
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
            if chunk.endswith(b"\n"):
                break

    response = b"".join(chunks).decode("utf-8").strip()
    if not response:
        return None
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {"raw_response": response}


def run_script(script_path, pipe_path=None, attempts=5):
    script_path = os.path.abspath(str(script_path))
    if not os.path.isfile(script_path):
        raise FileNotFoundError("Script not found: " + script_path)

    payload = {
        "$meta": {"version": "1.0"},
        "$type": "script",
        "location": script_path,
    }
    last_error = None
    for attempt in range(attempts):
        try:
            response = _send_request(payload, _resolve_pipe(pipe_path))
            if response is not None:
                return response
            last_error = RuntimeError("Rhino returned no response")
        except (FileNotFoundError, ConnectionRefusedError, OSError, RuntimeError) as error:
            last_error = error
        if attempt < attempts - 1:
            time.sleep(0.05)
    raise last_error


def run_command(command, pipe_path=None, attempts=5):
    if not isinstance(command, str) or not command:
        raise ValueError("command must be a non-empty string")

    payload = {
        "$meta": {"version": "1.0"},
        "$type": "job",
        "endpoint": "command",
        "payload": command,
    }
    last_error = None
    for attempt in range(attempts):
        try:
            response = _send_request(payload, _resolve_pipe(pipe_path))
            if response is not None:
                return response
            last_error = RuntimeError("Rhino returned no response")
        except (FileNotFoundError, ConnectionRefusedError, OSError, RuntimeError) as error:
            last_error = error
        if attempt < attempts - 1:
            time.sleep(0.05)
    raise last_error


def run_rhino_script(script_path, pipe_path=None):
    return run_script(script_path, pipe_path=pipe_path)



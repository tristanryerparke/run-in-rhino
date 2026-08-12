import glob
import json
import os
import socket
import tempfile


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


def run_script(script_path=None, pipe_path=None, *, script=None):
    """Run a Python file or source text in Rhino via the RhinoCode pipe."""
    if (script_path is None) == (script is None):
        raise ValueError("Provide exactly one of script_path or script")

    temp_path = None
    try:
        if script is not None:
            with tempfile.NamedTemporaryFile(
                "w",
                suffix=".py",
                encoding="utf-8",
                delete=False,
            ) as file:
                file.write(script)
                temp_path = file.name
            script_path = temp_path

        script_path = os.path.abspath(str(script_path))
        if not os.path.isfile(script_path):
            raise FileNotFoundError("Script not found: " + script_path)

        payload = {
            "$meta": {"version": "1.0"},
            "$type": "script",
            "location": script_path,
        }
        response = _send_request(payload, _resolve_pipe(pipe_path))
        if response is None:
            raise RuntimeError("Rhino returned no response")
        return response
    finally:
        if temp_path is not None:
            os.unlink(temp_path)


def run_command(command, pipe_path=None):
    """Runs a rhino command in rhino via the rhinocode pipe"""
    if not isinstance(command, str) or not command:
        raise ValueError("command must be a non-empty string")

    payload = {
        "$meta": {"version": "1.0"},
        "$type": "job",
        "endpoint": "command",
        "payload": command,
    }
    response = _send_request(payload, _resolve_pipe(pipe_path))
    if response is None:
        raise RuntimeError("Rhino returned no response")
    return response


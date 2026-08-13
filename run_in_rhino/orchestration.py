import json
import uuid

from .pipe import run_script
from .server import server
from .utils import command_script


def start_rhino_command(command, pipe_path=None):
    """Submit a Rhino command and return without waiting for it to finish."""
    return run_script(script=command_script(command), pipe_path=pipe_path)


def run_rhino_command(command, callback=None, pipe_path=None):
    """Run a Rhino command and return its callback payload."""
    if callback is None:
        callback = str(uuid.uuid4())
    elif not isinstance(callback, str) or not callback:
        raise ValueError("callback must be a non-empty string")

    result = None
    terminal_output = []
    final_status = None

    for status, data in server():
        final_status = status
        if status == "ready":
            run_script(
                script=command_script(
                    command,
                    callback=callback,
                    done=True,
                ),
                pipe_path=pipe_path,
            )
        elif status == "data":
            payload = json.loads(data)
            if payload.get("callback") == callback:
                result = payload
        elif status == "terminal":
            terminal_output.append(data)

    if result is None:
        message = "Rhino exited with {!r} before command callback {!r}".format(
            final_status,
            callback,
        )
        if terminal_output:
            message += "\n" + "".join(terminal_output)
        raise RuntimeError(message)

    return result


def run_rhino_python_til_done(
    script_path=None,
    context=None,
    pipe_path=None,
    *,
    script=None,
):
    """Start the server, run a Rhino script, and wait for the server to exit."""
    if (script_path is None) == (script is None):
        raise ValueError("Provide exactly one of script_path or script")

    received_data = []
    for status, data in server(context=context):
        if status == "ready":
            run_script(script_path, pipe_path=pipe_path, script=script)
        elif status == "data":
            received_data.append(data)
    return status, received_data


if __name__ == "__main__":
    reason, data = run_rhino_python_til_done("demos/parasite_usage.py")
    print("Server stopped because:", reason)

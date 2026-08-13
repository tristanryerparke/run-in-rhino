"""Launch a dedicated Rhino instance and send a script to its exact pipe."""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from run_in_rhino.pipe import list_pipes, run_script


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RHINO_EXECUTABLE = Path("/Applications/Rhino 8.app/Contents/MacOS/Rhinoceros")
BLANK_FILE = PROJECT_ROOT / "blank_file.3dm"
STARTUP_TIMEOUT_SECONDS = 60
SCRIPT_TIMEOUT_SECONDS = 15


def wait_for_owned_pipe(process):
    """Return only the RhinoCode pipe whose suffix matches the owned PID."""
    expected_suffix = "rhinocode_remotepipe_{}".format(process.pid)
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                "Dedicated Rhino exited with code {} before its pipe appeared".format(
                    return_code
                )
            )

        matching_pipes = [
            pipe_path
            for pipe_path in list_pipes()
            if pipe_path.endswith(expected_suffix)
        ]
        if len(matching_pipes) == 1:
            return matching_pipes[0]
        if len(matching_pipes) > 1:
            raise RuntimeError(
                "Multiple RhinoCode sockets matched owned PID {}: {!r}".format(
                    process.pid,
                    matching_pipes,
                )
            )

        time.sleep(0.25)

    raise TimeoutError(
        "No RhinoCode pipe appeared for dedicated Rhino PID {} within {} seconds. "
        "Configure StartScriptServer as a Rhino startup command.".format(
            process.pid,
            STARTUP_TIMEOUT_SECONDS,
        )
    )


def wait_for_result(result_path):
    deadline = time.monotonic() + SCRIPT_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if result_path.exists():
            return json.loads(result_path.read_text(encoding="utf-8"))
        time.sleep(0.1)
    raise TimeoutError(
        "Dedicated Rhino did not write {} within {} seconds".format(
            result_path,
            SCRIPT_TIMEOUT_SECONDS,
        )
    )


def stop_owned_rhino(process, pipe_path):
    """Ask the owned Rhino to exit cleanly, then force-stop only if it hangs."""
    if process.poll() is not None:
        return

    if pipe_path is not None:
        try:
            run_script(
                script="import Rhino\nRhino.RhinoApp.Exit(False)\n",
                pipe_path=pipe_path,
            )
            process.wait(timeout=10)
            return
        except (ConnectionError, OSError, RuntimeError, subprocess.TimeoutExpired):
            pass

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def test_script_runs_in_new_rhino_instance_via_its_owned_pipe():
    assert RHINO_EXECUTABLE.is_file(), "Rhino executable not found"
    assert BLANK_FILE.is_file(), "blank_file.3dm not found"

    pipes_before_launch = set(list_pipes())
    process = subprocess.Popen(
        [str(RHINO_EXECUTABLE), str(BLANK_FILE)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    result_file = tempfile.NamedTemporaryFile(
        prefix="dedicated-rhino-result-",
        suffix=".json",
        delete=False,
    )
    result_file.close()
    result_path = Path(result_file.name)
    result_path.unlink()
    owned_pipe = None

    try:
        owned_pipe = wait_for_owned_pipe(process)
        print("Existing Rhino pipes:", sorted(pipes_before_launch))
        print("Dedicated Rhino PID:", process.pid)
        print("Dedicated Rhino pipe:", owned_pipe)

        assert owned_pipe not in pipes_before_launch
        assert owned_pipe.endswith("rhinocode_remotepipe_{}".format(process.pid))

        script = """import json
import os

import Rhino

payload = {{
    "process_id": os.getpid(),
    "document_path": Rhino.RhinoDoc.ActiveDoc.Path,
}}
with open({result_path!r}, "w", encoding="utf-8") as result_file:
    json.dump(payload, result_file)
""".format(result_path=str(result_path))

        response = run_script(script=script, pipe_path=owned_pipe)
        result = wait_for_result(result_path)
        print("RhinoCode response:", response)
        print("Dedicated Rhino result:", result)

        assert result["process_id"] == process.pid
        assert Path(result["document_path"]).resolve() == BLANK_FILE.resolve()
    finally:
        result_path.unlink(missing_ok=True)
        stop_owned_rhino(process, owned_pipe)

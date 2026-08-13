"""Launch a callback-confirmed Rhino and use only its PID-owned pipe."""

import json
import tempfile
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BLANK_FILE = PROJECT_ROOT / "blank_file.3dm"
SCRIPT_TIMEOUT_SECONDS = 15


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


def test_script_runs_in_new_rhino_instance_via_its_owned_pipe(rhino_instance):
    result_file = tempfile.NamedTemporaryFile(
        prefix="dedicated-rhino-result-",
        suffix=".json",
        delete=False,
    )
    result_file.close()
    result_path = Path(result_file.name)
    result_path.unlink()

    try:
        print("Dedicated Rhino startup callback:", rhino_instance.startup_payload)
        print("Dedicated Rhino PID:", rhino_instance.process.pid)
        print("Dedicated Rhino pipe:", rhino_instance.pipe_path)

        assert rhino_instance.pipe_path.endswith(
            "rhinocode_remotepipe_{}".format(rhino_instance.process.pid)
        )

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

        response = rhino_instance.run_script(script=script)
        result = wait_for_result(result_path)
        print("RhinoCode response:", response)
        print("Dedicated Rhino result:", result)

        assert result["process_id"] == rhino_instance.process.pid
        assert Path(result["document_path"]).resolve() == BLANK_FILE.resolve()
    finally:
        result_path.unlink(missing_ok=True)

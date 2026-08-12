from .pipe import run_script
from .server import server


def run_rhino_python_til_done(script_path=None, context=None, *, script=None):
    """Start the server, run a Rhino script, and wait for the server to exit."""
    if (script_path is None) == (script is None):
        raise ValueError("Provide exactly one of script_path or script")

    received_data = []
    for status, data in server(context=context):
        if status == "ready":
            run_script(script_path, script=script)
        elif status == "data":
            received_data.append(data)
    return status, received_data


if __name__ == "__main__":
    reason, data = run_rhino_python_til_done("demos/parasite_usage.py")
    print("Server stopped because:", reason)

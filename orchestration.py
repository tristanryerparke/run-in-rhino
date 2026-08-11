import asyncio
import os
import tempfile

from pipe import run_script
from server_2 import main


async def run_rhino_python_til_done(script_path=None, context=None, *, script=None):
    """Start the server, run a Rhino script, and wait for the server to exit."""
    if (script_path is None) == (script is None):
        raise ValueError("Provide exactly one of script_path or script")

    temp_path = None
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

    started = asyncio.get_running_loop().create_future()
    server_task = asyncio.create_task(main(context=context, started=started))

    try:
        await started
        await asyncio.to_thread(run_script, script_path)
        return await server_task
    except BaseException:
        server_task.cancel()
        await asyncio.gather(server_task, return_exceptions=True)
        raise
    finally:
        if temp_path is not None and os.path.exists(temp_path):
            os.unlink(temp_path)


if __name__ == "__main__":
    reason, data = asyncio.run(run_rhino_python_til_done("test_new.py"))
    print("Server stopped because:", reason)


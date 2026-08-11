import asyncio

from pipe import run_script
from server_2 import main


async def run_rhino_python_til_done(script_path, context=None):
    """Start the server, run a Rhino script, and wait for the server to exit."""
    started = asyncio.get_running_loop().create_future()
    server_task = asyncio.create_task(main(context=context, started=started))

    try:
        await started
        await asyncio.to_thread(
            run_script,
            script_path,
        )
        return await server_task
    except BaseException:
        server_task.cancel()
        await asyncio.gather(server_task, return_exceptions=True)
        raise


if __name__ == "__main__":
    reason, data = asyncio.run(run_rhino_python_til_done("test_new.py"))
    print("Server stopped because:", reason)


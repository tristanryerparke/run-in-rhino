# run-in-rhino

Programatically run python scripts inside an already-open Rhino instance, and optionally exchange messages over a local WebSocket. It is especially useful for tests, interactive development, and analysis of rhino's state.
The parent script can easily poll what's running in rhino and perform other tasks using the provided generator function.

## CLI

Run a watched script with `uv run rhino-watch path/to/script.py`; add `--nostop` to keep the watcher open after `done`. Run a script without a watcher using `uv run in-rhino path/to/script.py`.

## Setup

Install this project with `uv sync`. In Rhino 8, add the checkout directory to **ScriptEditor → Options → Python 3 → Paths**:

```text
/Users/tristanryerparke/projects-local/run-in-rhino
```

Rhino then adds the directory to the pipe script server's `sys.path`, allowing Rhino scripts to import `run_in_rhino`.

## Run a Rhino script and receive data

The parent starts the watcher and sends Python source to Rhino:

```python
from run_in_rhino.orchestration import run_rhino_python_til_done
from run_in_rhino.server import RunContext

reason, data = run_rhino_python_til_done(
    script=SCRIPT,
    context=RunContext(env={"box_dims": [5, 5, 5]}),
)
assert reason == "done"
```

Inside Rhino, create a `SocketConnection`. `install_sticky_environment()` requests the parent's `env` mapping and stores it in `scriptcontext.sticky`. `send_data()` sends a value back to the parent; the returned `data` list contains those values.

```python
connection = SocketConnection()
environment = install_sticky_environment(connection)
connection.send_data(json.dumps(environment["box_dims"]))
connection.send_done()
```

## Basic Client Socket Methods

- `send_terminal(string)` forwards terminal output to the parent watcher.
- `send_data(string)` sends textual data to the parent watcher.
- `send_done()` ends the watcher when `RunContext.stop` is true (the default).
- `send_quit()` ends it when `RunContext.quit` is true (the default).

## Sender Helpers

`debug_to_server(data, connection)` prints locally and forwards a representation as terminal output. Pass `send_only=True` to forward without printing locally.

- `OutputParasite(connection, done_msg=True)` forwards captured `print()` output and sends `done`. If code in the context raises, it forwards the traceback and sends `quit`.

Both of these helpers are meant to run without a connection, so you aren't forced to set it up if it can't be imported, or is turned off, etc.


## Run a Rhino command

`run_rhino_command()` starts a server, runs the command, waits for its callback, and returns the callback payload:

```python
from run_in_rhino.orchestration import run_rhino_command

result = run_rhino_command("_Circle 0,0,0 5")
assert result["succeeded"] is True
```

The callback defaults to a generated UUID. Specify it when you need a predictable value:

```python
result = run_rhino_command(
    "_Circle 0,0,0 5",
    callback="circle_done",
)
assert result["callback"] == "circle_done"
```

To submit a command without waiting for it to finish, use `start_rhino_command()`:

```python
from run_in_rhino.orchestration import start_rhino_command

response = start_rhino_command("_Circle 0,0,0 5")
job_id = response["jobId"]
# The command may still be running in Rhino here.
```

`start_rhino_command()` does not start a WebSocket server or create a callback; it returns after RhinoCode acknowledges the submitted script.

For multi-step flows on one server, `command_script()` provides the lower-level interface. It creates Python source that calls `rhinoscriptsyntax.Command()` inside Rhino. Pass that source to `run_script()` and handle its callback data:

```python
import json

from run_in_rhino.pipe import run_script
from run_in_rhino.server import server
from run_in_rhino.utils import command_script

for status, data in server():
    if status == "ready":
        run_script(
            script=command_script(
                "_Circle 0,0,0 5",
                callback="circle_done",
                done=True,
            )
        )
    elif status == "data":
        result = json.loads(data)
        if result.get("callback") == "circle_done":
            assert result["succeeded"] is True
```

The generated script sends the callback after `rhinoscriptsyntax.Command()` returns. With `done=True`, it then sends `done` so the default server exits. The callback data also contains the original `command` and its boolean `succeeded` result.

## Lifecycle and output

For longer interactions, iterate `server(...)` directly. On its `"ready"` event, use `run_script(script=...)`; handle returned `"data"` and `"terminal"` events to sequence later scripts or commands.

See `demos/example_tests/`: `test_rhino_box.py` exchanges test data, `test_rhino_end_command_move.py` drives `_SelID` and `_Move`, and `test_error_in_rhino.py` verifies error forwarding.

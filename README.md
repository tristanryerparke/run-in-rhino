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


## Lifecycle and output

For longer interactions, iterate `server(...)` directly. On its `"ready"` event, use `run_script(script=...)`; later use `run_command(...)` to drive Rhino commands while handling returned `"data"` and `"terminal"` events.

See `demos/example_tests/`: `test_rhino_box.py` exchanges test data, `test_rhino_end_command_move.py` drives `_SelID` and `_Move`, and `test_error_in_rhino.py` verifies error forwarding.

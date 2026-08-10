# Rhino environment bootstrap

`run-in-rhino` can provide environment variables to Python code running inside an
already-open Rhino process. This is useful because Rhino is not a child process
of the watcher, so changing the parent process environment would not otherwise
reach Rhino.

## Use from parent Python

Pass an `environment` mapping when starting the controllable watcher:

```python
from run_in_rhino import start_server

with start_server(
    nostop=True,
    environment={
        "TACK_DEBUG": "1",
        "TACK_MODE": "preview",
    },
) as rhino:
    rhino.run_file("commands/setup_tack.py")
```

Environment names and values must both be strings. An empty mapping is treated
as no environment.

### Execute a top-level Rhino command

Use `run_command()` when the operation must create its own Rhino command and undo record rather than run inside a Python script command:

```python
with start_server(nostop=True, environment={"debug": "true"}) as rhino:
    rhino.run_file("tests/rhino/prepare_move.py")
    rhino.run_command("_Move 0,0,0 0,10,0")
    rhino.run_file("tests/rhino/collect_move.py")
```

### Command-line debug flag

Run a watched script with `debug=true` in its Rhino environment:

```bash
uv run rhino-watch commands/setup_tack.py --debug
```

The CLI explicitly installs `debug=false` when `--debug` is absent. Rhino is a persistent process, so this clears a `debug=true` value left by an earlier debug watcher.

## Use inside Rhino

The values are available before the first target script executes:

```python
import os

if os.getenv("debug") == "true":
    print("Debug mode is enabled")
```

The complete mapping is also retained for the Rhino session in
`scriptcontext.sticky`:

```python
import scriptcontext as sc

environment = sc.sticky["run_in_rhino.environment"]
```

## How it works

When `environment` is configured, `run-in-rhino` runs a small Rhino bootstrap
script before the first target script. The bootstrap opens the existing local
WebSocket connection. The watcher includes the environment as base64 JSON in
the WebSocket upgrade response, and the bootstrap applies it with
`os.environ.update()`.

## No-environment behavior

With the default `environment=None`, or with `environment={}`:

- no environment header is sent;
- no environment WebSocket connection is opened; and
- no extra Rhino bootstrap script runs.

The normal watcher path is otherwise unchanged.

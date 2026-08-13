# Rhino decorator plan

## Goal

Add a small API that lets local Python call a function **inside a running Rhino process** using the existing `run-in-rhino` pipe + watcher backend.

Example target shape:

```python
from run_in_rhino import in_rhino, start_server

with start_server(nostop=True) as rhino:
    @in_rhino(session=rhino)
    def add_point(x, y, z):
        import scriptcontext as sc
        import Rhino
        return str(sc.doc.Objects.AddPoint(Rhino.Geometry.Point3d(x, y, z)))

    guid = add_point(1, 2, 3)
```

## Non-goals for v1

Skip all of this initially:

- closures / lambdas / notebook functions
- arbitrary object transport
- returning live RhinoCommon objects to the caller
- syncing the caller's whole local venv into Rhino
- async / concurrency features

## Constraints

- Functions must live in real `.py` files.
- Functions must be top-level importable callables.
- Args / kwargs / results should be JSON-serializable in v1.
- Rhino-specific values should come back as plain data, usually `str(guid)` or dicts/lists.

## Reuse from existing code

Existing pieces already cover the hard parts:

- `pipe.run_rhino_script(...)`
- `RhinoServer.run_file(...)`
- watcher data channel via `server.py`
- optional `environment` bootstrap

So the decorator layer only needs to:

1. generate a temporary Rhino-side wrapper script
2. call that wrapper with `run_file(...)`
3. receive one structured result message
4. return it or raise an error locally

## Proposed API

### Minimal decorator

```python
@in_rhino(session=rhino)
def func(...):
    ...
```

### Slightly more explicit helper

```python
remote_func = in_rhino(session=rhino)(func)
result = remote_func(...)
```

### Optional future convenience

```python
@in_rhino(session=rhino, project_root=ROOT)
def func(...):
    ...
```

`project_root` would be prepended to `sys.path` in Rhino before import.

## How a call should work

Parent process:

1. Inspect the function:
   - source file path
   - module name if useful
   - function name / qualname
2. Validate v1 rules:
   - top-level function
   - JSON-safe args / kwargs
3. Write a temp wrapper script.
4. `session.run_file(temp_script)`.
5. Wait for one `data` message.
6. If message is `ok`, return result.
7. If message is `error`, raise a local exception with remote traceback.

Rhino wrapper script:

1. Add source module dir to `sys.path`.
2. Optionally add project root.
3. Import the module from file path.
4. Resolve the function by name.
5. Decode args / kwargs.
6. Execute.
7. Send one envelope back over the websocket.

## Result envelope

Use a tiny stable protocol:

```json
{"type":"rhino_call_result","status":"ok","result":...}
```

```json
{"type":"rhino_call_result","status":"error","error":"...","traceback":"..."}
```

This avoids parsing terminal output.

## Import strategy

Use the simplest thing that works:

1. prepend the function file's parent directory to `sys.path`
2. optionally prepend `project_root`
3. let Rhino's normal Python paths / `.pth` / `# env:` handle the rest

Do **not** try to clone the caller's whole Python environment into Rhino.

## Serialization rules for v1

Allowed:

- `None`
- `bool`, `int`, `float`, `str`
- lists / dicts of the above

Rejected early:

- RhinoCommon objects
- custom class instances
- open file handles
- functions / modules

Later, if needed, add explicit adapters like:

- `Point3d -> [x, y, z]`
- `Guid -> str`

## Error handling

Two error classes are enough:

- local usage error: unsupported function / args
- remote execution error: exception raised inside Rhino

Remote errors should include:

- exception type
- message
- traceback

## Suggested implementation steps

### Phase 1: single call proof

- add helper that runs one named function from one module file in Rhino
- pass JSON args / kwargs
- receive JSON result

### Phase 2: decorator wrapper

- add `in_rhino(session=...)`
- validate function shape
- map call -> helper

### Phase 3: ergonomics

- add `project_root`
- better error messages
- maybe temp file cleanup helper

## File ideas

Potential additions:

- `run_in_rhino.py` or new `decorator.py` for public API
- `rpc.py` for wrapper generation + response handling
- temp wrapper script emitted at runtime, not committed

Keep it to one or two files if possible.

## Test plan

Start tiny:

1. remote function returning a number
2. remote function returning a dict
3. remote function raising an exception
4. remote function importing `Rhino` and reading `scriptcontext.doc`
5. remote function creating geometry and returning a GUID string

## Nice-to-have later

- support methods via explicit staticmethod/classmethod handling
- explicit adapters for common Rhino geometry data
- batch calls
- async API

## Recommendation

Build the smallest RPC layer on top of the current watcher.

**Do not** try to ship function bytecode, closures, or live Rhino objects across processes.

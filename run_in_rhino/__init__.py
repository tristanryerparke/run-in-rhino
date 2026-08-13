__all__ = [
    "RunContext",
    "run_rhino_python_til_done",
    "run_script",
]


def __getattr__(name):
    if name == "run_script":
        from . import pipe

        return getattr(pipe, name)
    if name == "run_rhino_python_til_done":
        from .orchestration import run_rhino_python_til_done

        return run_rhino_python_til_done
    if name == "RunContext":
        from .server import RunContext

        return RunContext
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))

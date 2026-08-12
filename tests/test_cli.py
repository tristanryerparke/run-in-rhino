from unittest.mock import patch

import run_in_rhino.cli as cli
from run_in_rhino.server import RunContext


def test_main_runs_script_with_default_context():
    calls = []

    async def run(script, context=None):
        calls.append((script, context))
        return "done", []

    with patch.object(cli, "run_rhino_python_til_done", side_effect=run):
        assert cli.rhino_watch(["model.py"]) == 0

    assert calls == [
        (
            "model.py",
            RunContext(
                stop=True,
                quit=True,
                env={"debug": "false"},
            ),
        )
    ]


def test_main_maps_watcher_options_to_run_context():
    calls = []

    async def run(script, context=None):
        calls.append((script, context))
        return "quit", []

    with patch.object(cli, "run_rhino_python_til_done", side_effect=run):
        assert cli.rhino_watch(["model.py", "--debug", "--noquit"]) == 0

    assert calls == [
        (
            "model.py",
            RunContext(
                stop=False,
                quit=False,
                env={"debug": "true"},
            ),
        )
    ]


def test_main_reports_orchestration_errors(capsys):
    async def run(script, context=None):
        raise RuntimeError("could not trigger Rhino")

    with patch.object(cli, "run_rhino_python_til_done", side_effect=run):
        assert cli.rhino_watch(["model.py"]) == 1

    assert capsys.readouterr().err == (
        "rhino-watch failed: could not trigger Rhino\n"
    )


def test_in_rhino_runs_script_through_pipe(capsys):
    with patch.object(cli, "run_script", return_value={"ok": True}) as run:
        assert cli.in_rhino(["model.py", "--pipe-path", "/tmp/rhino"]) == 0

    run.assert_called_once_with("model.py", pipe_path="/tmp/rhino")
    assert capsys.readouterr().out == '{\n  "ok": true\n}\n'


def test_in_rhino_reports_pipe_errors(capsys):
    with patch.object(
        cli,
        "run_script",
        side_effect=RuntimeError("No running RhinoCode pipe found"),
    ):
        assert cli.in_rhino(["model.py"]) == 1

    assert capsys.readouterr().err == (
        "in-rhino failed: No running RhinoCode pipe found\n"
    )

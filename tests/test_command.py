from unittest.mock import patch

import run_in_rhino.pipe as pipe


def test_run_command_sends_rhino_job_request():
    with patch.object(pipe, "_resolve_pipe", return_value="/tmp/rhino") as resolve:
        with patch.object(pipe, "_send_request", return_value={"ok": True}) as send:
            assert pipe.run_command("_Undo") == {"ok": True}

    resolve.assert_called_once_with(None)
    send.assert_called_once_with(
        {
            "$meta": {"version": "1.0"},
            "$type": "job",
            "endpoint": "command",
            "payload": "_Undo",
        },
        "/tmp/rhino",
    )


def test_run_command_requires_non_empty_text():
    for command in (None, "", 1):
        try:
            pipe.run_command(command)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError for {!r}".format(command))

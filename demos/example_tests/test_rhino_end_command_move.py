"""Example test driving Rhino commands from one server generator."""

import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from test_rhino_box import BOX_MAX, BOX_SCRIPT_PREFIX
from run_in_rhino.pipe import run_script
from run_in_rhino.server import RunContext, server
from run_in_rhino.utils import command_script


MOVE_X = 5

SETUP_EXTENSION = """import Rhino

debug_to_server("DEBUG setup extension starting", connection=connection)

def handler(sender, event):
    command_name = (
        getattr(event, "CommandEnglishName", None)
        or getattr(event, "CommandLocalName", None)
        or ""
    )
    if command_name != "Move":
        return

    Rhino.Commands.Command.EndCommand -= handler
    callback_connection = SocketConnection()
    with OutputParasite(callback_connection):
        print(
            "DEBUG EndCommand command={!r} box_id={}".format(
                command_name,
                box_id,
            )
        )
        callback_connection.send_data(
            json.dumps({
                "box_id": str(box_id),
                "max": box_maximum_point(box_id),
                "command": command_name,
            })
        )
        sc.doc.Objects.Delete(box_id, True)


Rhino.Commands.Command.EndCommand += handler
debug_to_server("DEBUG EndCommand handler subscribed", connection=connection)
connection.send_data(json.dumps({"box_id": str(box_id), "max": box_maximum_point(box_id)}))
debug_to_server("DEBUG setup payload sent", connection=connection)
"""

SETUP_SCRIPT = BOX_SCRIPT_PREFIX + """print("DEBUG Rhino setup script started")
connection = SocketConnection()
print("DEBUG Rhino setup script connected to watcher")
debug_to_server("DEBUG setup script connected", connection=connection)
environment = install_sticky_environment(connection)
print("DEBUG Rhino setup script installed sticky environment")
debug_to_server("DEBUG environment installed value={!r}".format(environment), connection=connection)
debug_to_server(
    "DEBUG sticky environment value={!r}".format(sc.sticky.get(STICKY_ENVIRONMENT_KEY)),
    connection=connection,
)

x, y, z = environment["box_dims"]
debug_to_server("DEBUG creating box with max={!r}".format((x, y, z)), connection=connection)
box_id = add_box_from_diagonal(x, y, z)
debug_to_server(
    "DEBUG box created box_id={} max={!r}".format(box_id, box_maximum_point(box_id)),
    connection=connection,
)
""" + SETUP_EXTENSION


def run_flow():
    events = server(context=RunContext(env={"box_dims": BOX_MAX}))
    setup_payload = None
    final_payload = None
    finished_commands = []

    try:
        for status, data in events:
            if status == "ready":
                print("DEBUG parent sending setup script after server started")
                run_script(script=SETUP_SCRIPT)
                continue

            print("DEBUG parent saw event", (status, data))
            if status == "data":
                payload = json.loads(data)
                callback = payload.get("callback")
                if setup_payload is None:
                    setup_payload = payload
                    assert setup_payload["max"] == BOX_MAX
                    print("DEBUG parent sending _SelID script")
                    run_script(
                        script=command_script(
                            "_SelID {} _Enter".format(setup_payload["box_id"]),
                            callback="selection_done",
                        )
                    )
                elif callback == "selection_done":
                    assert payload["succeeded"] is True
                    finished_commands.append(callback)
                    print("DEBUG parent sending _Move script")
                    run_script(
                        script=command_script(
                            "_Move 0,0,0 {},0,0".format(MOVE_X),
                            callback="move_done",
                            done=True,
                        )
                    )
                elif callback == "move_done":
                    assert payload["succeeded"] is True
                    finished_commands.append(callback)
                elif payload.get("command") == "Move":
                    final_payload = payload
    finally:
        events.close()

    assert setup_payload is not None
    assert final_payload is not None
    assert finished_commands == ["selection_done", "move_done"]
    assert final_payload["box_id"] == setup_payload["box_id"]
    assert final_payload["max"] == [BOX_MAX[0] + MOVE_X, BOX_MAX[1], BOX_MAX[2]]


def test_rhino_end_command_handler_tracks_move_with_one_server():
    run_flow()

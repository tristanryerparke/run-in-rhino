def command_script(command, callback, done=False):
    """Create a Rhino Python script that runs a command and reports completion."""
    return f"""import json

import rhinoscriptsyntax as rs

from run_in_rhino.rhino_env.client import SocketConnection
from run_in_rhino.rhino_env.parasite import OutputParasite


command = {command!r}
callback = {callback!r}
connection = SocketConnection()
completed = False
with OutputParasite(connection):
    succeeded = bool(rs.Command(command, echo=False))
    connection.send_data(json.dumps({{
        "callback": callback,
        "command": command,
        "succeeded": succeeded,
    }}))
    completed = True

if completed and {done!r}:
    connection.send_done()
"""

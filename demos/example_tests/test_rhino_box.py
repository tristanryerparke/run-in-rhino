"""Create a box in Rhino and round-trip its measured dimensions."""

import asyncio
import json
from pathlib import Path

from orchestration import run_rhino_python_til_done
from server_2 import RunContext


BOX_DIMS = [5, 5, 5]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = f"""import json
import sys

import rhinoscriptsyntax as rs
import scriptcontext as sc

sys.path.insert(0, {str(PROJECT_ROOT)!r})

from rhino_env.client import SocketConnection
from rhino_env.env import STICKY_ENVIRONMENT_KEY, install_sticky_environment

connection = SocketConnection()
install_sticky_environment(connection)

x, y, z = sc.sticky[STICKY_ENVIRONMENT_KEY]["box_dims"]
box_id = rs.AddBox([
    (0, 0, 0),
    (x, 0, 0),
    (x, y, 0),
    (0, y, 0),
    (0, 0, z),
    (x, 0, z),
    (x, y, z),
    (0, y, z),
])

bbox = rs.BoundingBox(box_id)
connection.send_data(json.dumps([
    max(point.X for point in bbox) - min(point.X for point in bbox),
    max(point.Y for point in bbox) - min(point.Y for point in bbox),
    max(point.Z for point in bbox) - min(point.Z for point in bbox),
]))
rs.DeleteObject(box_id)
connection.send_done()
"""


def test_rhino_box_reports_original_dimensions():
    reason, data = asyncio.run(
        run_rhino_python_til_done(
            script=SCRIPT,
            context=RunContext(env={"box_dims": BOX_DIMS}),
        )
    )

    assert reason == "done"
    assert len(data) == 1
    assert json.loads(data[0]) == BOX_DIMS

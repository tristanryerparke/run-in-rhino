"""Example test file for another library, showing how to send data 
to and recieve data from a script that gets run in rhino, 
and use it to run a real test"""

import json

from run_in_rhino.orchestration import run_rhino_python_til_done
from run_in_rhino.server import RunContext


BOX_MAX = [5, 5, 5]


BOX_SCRIPT_PREFIX = """import json

import Rhino
import scriptcontext as sc

from run_in_rhino.rhino_env.client import SocketConnection, debug_to_server
from run_in_rhino.rhino_env.env import STICKY_ENVIRONMENT_KEY, install_sticky_environment
from run_in_rhino.rhino_env.parasite import OutputParasite


def add_box_from_diagonal(x, y, z):
    minimum = Rhino.Geometry.Point3d(0, 0, 0)
    maximum = Rhino.Geometry.Point3d(x, y, z)
    bounding_box = Rhino.Geometry.BoundingBox(minimum, maximum)
    return sc.doc.Objects.AddBox(Rhino.Geometry.Box(bounding_box))


def box_maximum_point(box_id):
    box_object = sc.doc.Objects.Find(box_id)
    bounding_box = box_object.Geometry.GetBoundingBox(True)
    return [bounding_box.Max.X, bounding_box.Max.Y, bounding_box.Max.Z]
"""


SCRIPT = BOX_SCRIPT_PREFIX + """print("DEBUG Rhino box script started")
connection = SocketConnection()
print("DEBUG Rhino box script connected to watcher")
install_sticky_environment(connection)
print("DEBUG Rhino box script installed sticky environment")

with OutputParasite(connection, done_msg=True):
    x, y, z = sc.sticky[STICKY_ENVIRONMENT_KEY]["box_dims"]
    print("DEBUG creating box from diagonal max={!r}".format((x, y, z)))
    box_id = add_box_from_diagonal(x, y, z)
    payload = box_maximum_point(box_id)
    print("DEBUG box max point={!r}".format(payload))
    sc.doc.Objects.Delete(box_id, True)
    connection.send_data(json.dumps(payload))
"""


def test_rhino_box_reports_original_maximum_point(rhino_instance):
    reason, data = run_rhino_python_til_done(
        script=SCRIPT,
        context=RunContext(env={"box_dims": BOX_MAX}),
        pipe_path=rhino_instance.pipe_path,
    )

    assert reason == "done"
    assert len(data) == 1
    assert json.loads(data[0]) == BOX_MAX

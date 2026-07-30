import Rhino

from rhino_watcher import send_done
from rhino_watcher import websocket_output


with websocket_output():
    point = Rhino.Geometry.Point3d(1, 2, 3)
    print(f"RhinoCommon is available: {type(point)}")

    print("hi")

with websocket_output():
    point = Rhino.Geometry.Point3d(1, 2, 3)
    print(f"RhinoCommon is available: {type(point)}")

    print("hi2")

send_done()

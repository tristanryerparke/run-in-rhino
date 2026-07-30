import Rhino

from rhino_watcher import send_done_sync
from rhino_watcher import websocket_output_sync


with websocket_output_sync():
    point = Rhino.Geometry.Point3d(1, 2, 3)
    print("RhinoCommon is available: {}".format(type(point)))
    print("hi")

with websocket_output_sync():
    point = Rhino.Geometry.Point3d(1, 2, 3)
    print("RhinoCommon is available: {}".format(type(point)))
    print("hi2")

send_done_sync()

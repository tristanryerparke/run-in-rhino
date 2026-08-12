# r: websocket-client

import Rhino

try:
    from run_in_rhino.rhino_env.client import SocketConnection

    connection = SocketConnection()
except Exception:
    connection = None
from run_in_rhino.rhino_env.parasite import OutputParasite


print("outside")

with OutputParasite(connection, done_msg=True):
    print("mf100")
    point = Rhino.Geometry.Point3d(1, 2, 3)
    print("Created point: {}".format(point))

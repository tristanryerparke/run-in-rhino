# r: websocket-client

import Rhino


from rhino_env.client import SocketConnection
from rhino_env.parasite import OutputParasite


connection = SocketConnection()

try:
    print("mf100")
    with OutputParasite(connection):
        point = Rhino.Geometry.Point3d(1, 2, 3)
        print("Created point: {}".format(point))
finally:
    connection.send_done()

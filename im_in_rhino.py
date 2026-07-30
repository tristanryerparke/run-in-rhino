import asyncio

import Rhino

from rhino_watcher import send_done
from rhino_watcher import websocket_output


async def main():
    async with websocket_output():
        point = Rhino.Geometry.Point3d(1, 2, 3)
        print(f"RhinoCommon is available: {type(point)}")
        print("hi")

    async with websocket_output():
        point = Rhino.Geometry.Point3d(1, 2, 3)
        print(f"RhinoCommon is available: {type(point)}")
        print("hi2")

    await send_done()


asyncio.run(main())

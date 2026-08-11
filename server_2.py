import asyncio
import json
from dataclasses import dataclass

from websockets.asyncio.server import serve

class BadClientMessageException(RuntimeError):
    pass

class NoClientMessageTypeException(RuntimeError):
    pass

class UnknownMessageTypeException(RuntimeError):
    pass


@dataclass(frozen=True)
class RunContext:
    """Stores context for the server so it can decide what messages to exit on"""
    stop: bool = True
    quit: bool = True


async def handle_client(ws, context, stopped_by, received_data):
    """Receive Rhino lifecycle events and raise invalid client messages."""
    try:
        async for message_raw in ws:
            
            # Parse the message and raise exceptions if it is bad
            try:
                message = json.loads(message_raw)
            except json.JSONDecodeError:
                raise BadClientMessageException(message_raw) from None
            if not isinstance(message, dict):
                raise BadClientMessageException(message_raw)
            message_type = message.get("type")
            if not isinstance(message_type, str) or not message_type:
                raise NoClientMessageTypeException(message_raw)

            # Parse the message type and act
            if message_type == "terminal":
                print(message.get("data", ""))
                await ws.send("received")
            elif message_type == "data":
                received_data.append(message.get("data"))
                await ws.send("received")
            elif message_type == "done":
                await ws.send("received")
                if context.stop and not stopped_by.done():
                    stopped_by.set_result(message_type)
                    return
            elif message_type == "quit":
                await ws.send("received")
                if context.quit and not stopped_by.done():
                    stopped_by.set_result(message_type)
                    return
            else:
                raise UnknownMessageTypeException(message_raw)

    # Forward exceptions to the main loop
    except BaseException as error:
        if not stopped_by.done():
            stopped_by.set_exception(error)
        raise


async def main(address="127.0.0.1", port=8765, context=None):
    """Run until a lifecycle event or invalid client message occurs."""
    if context is None:
        context = RunContext()
    stopped_by = asyncio.get_running_loop().create_future()
    received_data = []
    async with serve(
        lambda ws: handle_client(ws, context, stopped_by, received_data),
        address,
        port,
    ) as server:
        print("Server listening on ws://{}:{}".format(address, port))
        return await stopped_by, received_data

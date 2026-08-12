import asyncio
import json
from dataclasses import dataclass, field

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
    env: dict = field(default_factory=dict)


async def handle_client(ws, context, stopped_by, received_data):
    """Receive Rhino lifecycle events and collect data messages."""
    try:
        async for message_raw in ws:
            try:
                message = json.loads(message_raw)
            except json.JSONDecodeError:
                message = None

            message_type = message.get("type") if isinstance(message, dict) else None

            if message_type == "terminal":
                print(message.get("data", ""))
                await ws.send("received")
            elif message_type == "data":
                received_data.append(message.get("data"))
                await ws.send("received")
            elif message_type == "env":
                await ws.send(json.dumps(context.env))
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
                received_data.append(message_raw)
                await ws.send("received")

    # Forward exceptions to the main loop
    except BaseException as error:
        if not stopped_by.done():
            stopped_by.set_exception(error)
        raise


async def main(address="127.0.0.1", port=8765, context=None, started=None):
    """Run until a lifecycle event occurs."""
    if context is None:
        context = RunContext()
    stopped_by = asyncio.get_running_loop().create_future()
    received_data = []
    try:
        async with serve(
            lambda ws: handle_client(ws, context, stopped_by, received_data),
            address,
            port,
            close_timeout=0,
        ) as server:
            if started is not None:
                started.set_result(None)
            print("Server listening on ws://{}:{}".format(address, port))
            return await stopped_by, received_data
    except BaseException as error:
        if started is not None and not started.done():
            started.set_exception(error)
        raise

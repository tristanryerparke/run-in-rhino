import json
from dataclasses import dataclass, field

from run_in_rhino.socket import WebSocketServer


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


def server(address="127.0.0.1", port=8765, context=None, poll_timeout=0.01):
    context = RunContext() if context is None else context

    with WebSocketServer(address, port) as websocket:
        print("Server listening on ws://{}:{}".format(address, port))
        yield "ready", None

        while True:
            message = websocket.poll(poll_timeout)
            if message is None:
                continue

            try:
                payload = json.loads(message.data)
            except json.JSONDecodeError as error:
                raise BadClientMessageException(message.data) from error
            if not isinstance(payload, dict):
                raise BadClientMessageException(message.data)
            if "type" not in payload:
                raise NoClientMessageTypeException(message.data)

            message_type = payload["type"]
            if message_type == "env":
                websocket.send(message, json.dumps(context.env))
            elif message_type == "terminal":
                data = payload.get("data", "")
                websocket.send(message, "received")
                print(data)
                yield message_type, data
            elif message_type == "data":
                websocket.send(message, "received")
                yield message_type, payload.get("data")
            elif message_type == "done":
                websocket.send(message, "received")
                if context.stop:
                    result = message_type, None
                    yield result
                    return result
            elif message_type == "quit":
                websocket.send(message, "received")
                if context.quit:
                    result = message_type, None
                    yield result
                    return result
            else:
                raise UnknownMessageTypeException(message_type)

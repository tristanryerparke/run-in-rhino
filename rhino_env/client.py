#! python 3
# To be run in rhino

import json
from io import StringIO

from websocket import create_connection

class SocketConnection:
    """Handles connection to a watcher websocket server.
    Meant for devlopment or other close observation of scripts running in rhino"""
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.ws = create_connection(f"ws://{host}:{port}")

    def _send(self, message: str):
        self.ws.send(message)
        response = self.ws.recv()
        return response
    
    def get_env(self):
        """Retrives a dict of environment variables from the server"""
        env_raw = self._send(json.dumps({"type": "env"}))
        env = json.loads(env_raw)
        return env

    def send_data(self, data: str):
        return self._send(json.dumps({"type": "data", "data": data}))

    def send_terminal(self, output: str):
        return self._send(json.dumps({"type": "terminal", "data": output}))

    def send_done(self):
        return self._send(json.dumps({"type": "done"}))

    def send_quit(self):
        return self._send(json.dumps({"type": "quit"}))


def debug_to_server(data, connection=None, send_only=False):
    """Print text locally and optionally send the same text 
    to a provided watcher server connection."""
    output = StringIO()
    if not send_only:
        print(data)
    if connection:
        connection.send_terminal(repr(data))
    


if __name__ == '__main__': 
    
    wsc = SocketConnection()
    # wsc.send("mf")
    env = wsc.get_env()
    print(env)
    wsc.send_data("mf1000")
    wsc.send_quit()
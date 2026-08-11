#! python 3
# To be run in rhino

import json
from websocket import create_connection

class SocketConnection:
    """class to handle the websocket client connection lifecycle"""
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        
        self.ws = create_connection(f"ws://{host}:{port}")

    def _send(self, message: str):
        self.ws.send(message)
        response = self.ws.recv()
        return response

    def send_data(self, data: str):
        return self._send(json.dumps({"type": "data", "data": data}))

    def send_terminal(self, output: str):
        return self._send(json.dumps({"type": "terminal", "data": output}))

    def send_done(self):
        return self._send(json.dumps({"type": "done"}))

    def send_quit(self):
        return self._send(json.dumps({"type": "quit"}))

    

if __name__ == '__main__': 
    
    wsc = SocketConnection()
    # wsc.send("mf")
    
    wsc.send_data("mf1000")
    wsc.send_quit()
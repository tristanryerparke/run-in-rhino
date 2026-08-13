import select
import socket as standard_socket
from collections import deque
from dataclasses import dataclass, field

from wsproto import WSConnection
from wsproto.connection import ConnectionType
from wsproto.events import AcceptConnection, BytesMessage, CloseConnection, Ping, Pong, Request, TextMessage


@dataclass
class _Client:
    socket: standard_socket.socket
    connection: WSConnection = field(
        default_factory=lambda: WSConnection(ConnectionType.SERVER)
    )
    text_parts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Message:
    data: str
    _client: _Client


class WebSocketServer:
    def __init__(self, address="127.0.0.1", port=8765):
        self.address = address
        self.port = port
        self._listener = None
        self._clients = {}
        self._messages = deque()

    def start(self):
        self._listener = standard_socket.socket(
            standard_socket.AF_INET,
            standard_socket.SOCK_STREAM,
        )
        self._listener.setsockopt(
            standard_socket.SOL_SOCKET,
            standard_socket.SO_REUSEADDR,
            1,
        )
        self._listener.bind((self.address, self.port))
        self._listener.listen()
        return self

    def _send(self, client, event):
        data = client.connection.send(event)
        if data:
            client.socket.sendall(data)

    def send(self, message, text):
        self._send(message._client, TextMessage(data=text))

    def _drop(self, client):
        self._clients.pop(client.socket, None)
        try:
            client.socket.close()
        except OSError:
            pass

    def _handle_event(self, client, event):
        if isinstance(event, Request):
            self._send(client, AcceptConnection())
        elif isinstance(event, Ping):
            self._send(client, event.response())
        elif isinstance(event, Pong):
            return
        elif isinstance(event, CloseConnection):
            self._send(client, event.response())
            self._drop(client)
        elif isinstance(event, BytesMessage):
            raise ValueError("binary websocket messages are not supported")
        elif isinstance(event, TextMessage):
            client.text_parts.append(event.data)
            if event.message_finished:
                self._messages.append(
                    Message("".join(client.text_parts), client)
                )
                client.text_parts.clear()

    def poll(self, timeout=0.01):
        if self._messages:
            return self._messages.popleft()

        sockets = [self._listener] + list(self._clients)
        readable, _, _ = select.select(sockets, [], [], timeout)
        for sock in readable:
            if sock is self._listener:
                client_socket, _address = self._listener.accept()
                self._clients[client_socket] = _Client(client_socket)
                continue

            client = self._clients[sock]
            data = sock.recv(4096)
            if not data:
                self._drop(client)
                continue

            client.connection.receive_data(data)
            for event in client.connection.events():
                self._handle_event(client, event)

        return self._messages.popleft() if self._messages else None

    def close(self):
        for client in list(self._clients.values()):
            try:
                self._send(client, CloseConnection(code=1001, reason=""))
            except OSError:
                pass
            self._drop(client)
        if self._listener is not None:
            self._listener.close()
            self._listener = None

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

import base64
import hashlib
import os
import socket
import struct

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8765
_MAGIC = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _recv_exact(connection, size):
    data = b""
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            raise ConnectionError("websocket connection closed")
        data += chunk
    return data


def _read_frame(connection):
    first, second = _recv_exact(connection, 2)
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", _recv_exact(connection, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recv_exact(connection, 8))[0]
    mask = second & 0x80
    mask_key = _recv_exact(connection, 4) if mask else b""
    payload = bytearray(_recv_exact(connection, length))
    if mask:
        for index in range(length):
            payload[index] ^= mask_key[index % 4]
    return first & 0x0F, bytes(payload)


def send_message(message):
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    with socket.create_connection((SERVER_HOST, SERVER_PORT)) as connection:
        connection.sendall(
            ("GET / HTTP/1.1\r\n"
             "Host: {}:{}\r\n"
             "Upgrade: websocket\r\n"
             "Connection: Upgrade\r\n"
             "Sec-WebSocket-Key: {}\r\n"
             "Sec-WebSocket-Version: 13\r\n\r\n").format(
                 SERVER_HOST, SERVER_PORT, key
             ).encode("ascii")
        )

        response = b""
        while b"\r\n\r\n" not in response:
            chunk = connection.recv(4096)
            if not chunk:
                raise ConnectionError("websocket connection closed during handshake")
            response += chunk
        expected = base64.b64encode(
            hashlib.sha1(key.encode("ascii") + _MAGIC).digest()
        ).decode("ascii")
        if not response.startswith(b"HTTP/1.1 101") or expected.encode("ascii") not in response:
            raise ConnectionError("websocket handshake failed")

        payload = message.encode("utf-8")
        length = len(payload)
        mask = os.urandom(4)
        if length < 126:
            header = bytes([0x81, 0x80 | length])
        elif length <= 0xFFFF:
            header = b"\x81\xfe" + struct.pack("!H", length)
        else:
            header = b"\x81\xff" + struct.pack("!Q", length)
        payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        connection.sendall(header + mask + payload)
        opcode, response = _read_frame(connection)
        if opcode != 1:
            raise ConnectionError("websocket server did not confirm the message")
        return response.decode("utf-8")


if __name__ == "__main__":
    print(send_message("Hello from Rhino"))

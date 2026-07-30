import base64
import hashlib
import importlib
import os
import socket
import struct
import sys


HOST = "127.0.0.1"
PORT = 8765
PRINT_WARMUP = True
IN_RHINO_PREFIX = "[RHINO-WATCH-CLIENT] "
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
    _, second = _recv_exact(connection, 2)
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", _recv_exact(connection, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recv_exact(connection, 8))[0]
    mask = _recv_exact(connection, 4) if second & 0x80 else None
    payload = bytearray(_recv_exact(connection, length))
    if mask:
        for index in range(length):
            payload[index] ^= mask[index % 4]
    return bytes(payload)


def send_message(message):
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    with socket.create_connection((HOST, PORT)) as connection:
        connection.sendall(
            ("GET / HTTP/1.1\r\n"
             "Host: {}:{}\r\n"
             "Upgrade: websocket\r\n"
             "Connection: Upgrade\r\n"
             "Sec-WebSocket-Key: {}\r\n"
             "Sec-WebSocket-Version: 13\r\n\r\n").format(
                 HOST, PORT, key
             ).encode("ascii")
        )
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = connection.recv(4096)
            if not chunk:
                raise ConnectionError("websocket connection closed during handshake")
            response += chunk

        payload = message.encode("utf-8")
        mask = os.urandom(4)
        length = len(payload)
        if length < 126:
            header = bytes([0x81, 0x80 | length])
        elif length <= 0xFFFF:
            header = b"\x81\xfe" + struct.pack("!H", length)
        else:
            header = b"\x81\xff" + struct.pack("!Q", length)
        payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        connection.sendall(header + mask + payload)
        return _read_frame(connection).decode("utf-8")


def _report(message):
    message = IN_RHINO_PREFIX + message
    print(message)
    send_message(message)


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        importlib.import_module("rhino_watcher")
    except ImportError:
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        try:
            importlib.import_module("rhino_watcher")
        except ImportError:
            if PRINT_WARMUP:
                _report("couldn't import rhino_watcher")
            raise
        else:
            if PRINT_WARMUP:
                _report(
                    "original import failed, added current dir to path "
                    "and then import succeeded"
                )
    else:
        if PRINT_WARMUP:
            _report("original import succeeded")

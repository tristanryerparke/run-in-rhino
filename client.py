import asyncio
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
TIMING_ENABLED = True
IN_RHINO_PREFIX = "[RHINO-WATCH-CLIENT] "
_MAGIC = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


async def _recv_exact(reader, size):
    return await reader.readexactly(size)


async def _read_frame(reader):
    _, second = await _recv_exact(reader, 2)
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", await _recv_exact(reader, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", await _recv_exact(reader, 8))[0]
    mask = await _recv_exact(reader, 4) if second & 0x80 else None
    payload = bytearray(await _recv_exact(reader, length))
    if mask:
        for index in range(length):
            payload[index] ^= mask[index % 4]
    return bytes(payload)


async def send_message(message):
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    reader, writer = await asyncio.open_connection(HOST, PORT)
    try:
        writer.write(
            ("GET / HTTP/1.1\r\n"
             "Host: {}:{}\r\n"
             "Upgrade: websocket\r\n"
             "Connection: Upgrade\r\n"
             "Sec-WebSocket-Key: {}\r\n"
             "Sec-WebSocket-Version: 13\r\n\r\n").format(
                 HOST, PORT, key
             ).encode("ascii")
        )
        await writer.drain()

        response = b""
        while b"\r\n\r\n" not in response:
            chunk = await reader.read(4096)
            if not chunk:
                raise ConnectionError("websocket connection closed during handshake")
            response += chunk
        expected = base64.b64encode(
            hashlib.sha1(key.encode("ascii") + _MAGIC).digest()
        ).decode("ascii")
        if not response.startswith(b"HTTP/1.1 101") or expected.encode("ascii") not in response:
            raise ConnectionError("websocket handshake failed")

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
        writer.write(header + mask + payload)
        await writer.drain()
        return (await _read_frame(reader)).decode("utf-8")
    finally:
        writer.close()
        await writer.wait_closed()


def _recv_exact_sync(connection, size):
    data = b""
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            raise ConnectionError("websocket connection closed")
        data += chunk
    return data


def _read_frame_sync(connection):
    _, second = _recv_exact_sync(connection, 2)
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", _recv_exact_sync(connection, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recv_exact_sync(connection, 8))[0]
    mask = _recv_exact_sync(connection, 4) if second & 0x80 else None
    payload = bytearray(_recv_exact_sync(connection, length))
    if mask:
        for index in range(length):
            payload[index] ^= mask[index % 4]
    return bytes(payload)


def send_message_sync(message):
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
        expected = base64.b64encode(
            hashlib.sha1(key.encode("ascii") + _MAGIC).digest()
        ).decode("ascii")
        if not response.startswith(b"HTTP/1.1 101") or expected.encode("ascii") not in response:
            raise ConnectionError("websocket handshake failed")

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
        return _read_frame_sync(connection).decode("utf-8")


def _import_rhino_watcher():
    module = importlib.import_module("rhino_watcher")
    client_module = sys.modules.get("client")
    if client_module is not None:
        importlib.reload(client_module)
    return importlib.reload(module)


async def _report(message):
    message = IN_RHINO_PREFIX + message
    if PRINT_WARMUP:
        print(message)
        await send_message(message)


async def _warmup():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        _import_rhino_watcher()
    except ImportError:
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        try:
            _import_rhino_watcher()
        except ImportError:
            await _report("couldn't import rhino_watcher")
            raise
        else:
            await _report(
                "original import failed, added current dir to path "
                "and then import succeeded"
            )
    else:
        await _report("original import succeeded")


if __name__ == "__main__":
    asyncio.run(_warmup())

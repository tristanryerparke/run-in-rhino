import argparse
import base64
import hashlib
import socket
import struct
import sys
import threading
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8765
DONE_MESSAGE = "__RHINO_DONE__"
_MAGIC = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
LOG_PREFIX = "[RHINO-WATCH] "


def _log(message, end="\n", file=None):
    if file is None:
        file = sys.stdout
    text = str(message).replace("\n", "\n" + LOG_PREFIX)
    if text.endswith(LOG_PREFIX):
        text = text[:-len(LOG_PREFIX)]
    print(LOG_PREFIX + text, end=end, file=file, flush=True)


def _recv_exact(sock, size):
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("websocket connection closed")
        data += chunk
    return data


def _read_frame(sock):
    first, second = _recv_exact(sock, 2)
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", _recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recv_exact(sock, 8))[0]

    mask = second & 0x80
    mask_key = _recv_exact(sock, 4) if mask else b""
    payload = bytearray(_recv_exact(sock, length))
    if mask:
        for index in range(length):
            payload[index] ^= mask_key[index % 4]
    return first & 0x0F, bytes(payload)


def _send_frame(sock, opcode, payload=b""):
    length = len(payload)
    header = bytes([0x80 | opcode])
    if length < 126:
        header += bytes([length])
    elif length <= 0xFFFF:
        header += b"\x7e" + struct.pack("!H", length)
    else:
        header += b"\x7f" + struct.pack("!Q", length)
    sock.sendall(header + payload)


def _handshake(sock):
    request = b""
    while b"\r\n\r\n" not in request:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("websocket connection closed during handshake")
        request += chunk

    headers = {}
    for line in request.decode("ascii").split("\r\n")[1:]:
        if ":" in line:
            name, value = line.split(":", 1)
            headers[name.lower()] = value.strip()

    accept = base64.b64encode(
        hashlib.sha1(headers["sec-websocket-key"].encode("ascii") + _MAGIC).digest()
    ).decode("ascii")
    sock.sendall(
        ("HTTP/1.1 101 Switching Protocols\r\n"
         "Upgrade: websocket\r\n"
         "Connection: Upgrade\r\n"
         "Sec-WebSocket-Accept: " + accept + "\r\n\r\n").encode("ascii")
    )


def _trigger_script(script_path, failed):
    try:
        from pipe import run_rhino_script

        run_rhino_script(Path(__file__).with_name("client.py"))
        run_rhino_script(script_path)
    except Exception as error:
        failed.append(error)
        _log("Rhino trigger failed: {}".format(error), file=sys.stderr)


def serve(script_path):
    done = threading.Event()
    trigger_error = []

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()
        server.settimeout(0.2)
        _log("WebSocket server listening on ws://{}:{}".format(HOST, PORT))

        trigger = threading.Thread(
            target=_trigger_script,
            args=(script_path, trigger_error),
            daemon=True,
        )
        trigger.start()

        while not done.is_set() and not trigger_error:
            try:
                connection, _ = server.accept()
            except socket.timeout:
                continue

            with connection:
                try:
                    _handshake(connection)
                    while True:
                        opcode, payload = _read_frame(connection)
                        if opcode == 1:
                            message = payload.decode("utf-8")
                            if message == DONE_MESSAGE:
                                done.set()
                            else:
                                print(
                                    message,
                                    end="" if message.endswith("\n") else "\n",
                                    flush=True,
                                )
                            _send_frame(
                                connection,
                                1,
                                ("received: " + message).encode("utf-8"),
                            )
                            if done.is_set():
                                break
                        elif opcode == 8:
                            _send_frame(connection, 8, payload)
                            break
                        elif opcode == 9:
                            _send_frame(connection, 10, payload)
                except (ConnectionError, OSError, KeyError, UnicodeDecodeError):
                    pass

    if done.is_set():
        _log("WebSocket server closed: End message received")

    trigger.join(timeout=1)
    if trigger_error:
        raise trigger_error[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run a script inside Rhino and watch its WebSocket output")
    parser.add_argument("script", help="Rhino Python script path")
    args = parser.parse_args(argv)
    try:
        serve(args.script)
    except Exception as error:
        _log("rhino-watch failed: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

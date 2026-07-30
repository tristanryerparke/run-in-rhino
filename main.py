import base64
import hashlib
import socket
import struct
import threading

HOST = "127.0.0.1"
PORT = 8765
_MAGIC = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_RHINO_MESSAGE = "Hello from Rhino"
_rhino_confirmed = threading.Event()
_rhino_output = None


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


def serve():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()
        server.settimeout(0.2)
        print("WebSocket server listening on ws://{}:{}".format(HOST, PORT))
        trigger = threading.Thread(target=_trigger_rhino, daemon=True)
        trigger.start()
        while not _rhino_confirmed.is_set():
            try:
                connection, address = server.accept()
            except socket.timeout:
                continue
            with connection:
                try:
                    _handshake(connection)
                    while True:
                        opcode, payload = _read_frame(connection)
                        if opcode == 1:
                            message = payload.decode("utf-8")
                            print("{}: {}".format(address, message))
                            if message == _RHINO_MESSAGE:
                                global _rhino_output
                                _rhino_output = message
                                _rhino_confirmed.set()
                            _send_frame(
                                connection,
                                1,
                                ("received: " + message).encode("utf-8"),
                            )
                            if _rhino_confirmed.is_set():
                                break
                        elif opcode == 8:
                            _send_frame(connection, 8, payload)
                            break
                        elif opcode == 9:
                            _send_frame(connection, 10, payload)
                except (ConnectionError, OSError, KeyError, UnicodeDecodeError):
                    pass
        trigger.join(timeout=1)
        print("Rhino output confirmed: {}".format(_rhino_output))


def _trigger_rhino():
    try:
        from pipe import run_rhino_wrapper

        response = run_rhino_wrapper()
        if response is None or not _rhino_confirmed.wait(10):
            raise RuntimeError("Rhino wrapper did not confirm its output")
    except Exception as error:
        print("Rhino trigger failed: {}".format(error))


def main():
    serve()


if __name__ == "__main__":
    main()

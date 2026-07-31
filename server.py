import argparse
import asyncio
import base64
import hashlib
import socket
import struct
import sys
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8765
DONE_MESSAGE = "__RHINO_DONE__"
LOG_PREFIX = "[RHINO-WATCH] "
_MAGIC = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _log(message, end="\n", file=None):
    if file is None:
        file = sys.stdout
    text = str(message).replace("\n", "\n" + LOG_PREFIX)
    if text.endswith(LOG_PREFIX):
        text = text[:-len(LOG_PREFIX)]
    print(LOG_PREFIX + text, end=end, file=file, flush=True)


async def _read_frame(reader):
    first, second = await reader.readexactly(2)
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", await reader.readexactly(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", await reader.readexactly(8))[0]

    mask = second & 0x80
    mask_key = await reader.readexactly(4) if mask else b""
    payload = bytearray(await reader.readexactly(length))
    if mask:
        for index in range(length):
            payload[index] ^= mask_key[index % 4]
    return first & 0x0F, bytes(payload)


async def _send_frame(writer, opcode, payload=b""):
    length = len(payload)
    header = bytes([0x80 | opcode])
    if length < 126:
        header += bytes([length])
    elif length <= 0xFFFF:
        header += b"\x7e" + struct.pack("!H", length)
    else:
        header += b"\x7f" + struct.pack("!Q", length)
    writer.write(header + payload)
    await writer.drain()


async def _handshake(reader, writer):
    request = await reader.readuntil(b"\r\n\r\n")
    headers = {}
    for line in request.decode("ascii").split("\r\n")[1:]:
        if ":" in line:
            name, value = line.split(":", 1)
            headers[name.lower()] = value.strip()

    accept = base64.b64encode(
        hashlib.sha1(headers["sec-websocket-key"].encode("ascii") + _MAGIC).digest()
    ).decode("ascii")
    writer.write(
        ("HTTP/1.1 101 Switching Protocols\r\n"
         "Upgrade: websocket\r\n"
         "Connection: Upgrade\r\n"
         "Sec-WebSocket-Accept: " + accept + "\r\n\r\n").encode("ascii")
    )
    await writer.drain()


async def _handle_client(reader, writer, done):
    try:
        await _handshake(reader, writer)
        while True:
            opcode, payload = await _read_frame(reader)
            if opcode == 1:
                message = payload.decode("utf-8")
                is_done = message == DONE_MESSAGE
                if not is_done:
                    print(
                        message,
                        end="" if message.endswith("\n") else "\n",
                        flush=True,
                    )
                await _send_frame(
                    writer,
                    1,
                    ("received: " + message).encode("utf-8"),
                )
                if is_done:
                    done.set()
                    break
            elif opcode == 8:
                await _send_frame(writer, 8, payload)
                break
            elif opcode == 9:
                await _send_frame(writer, 10, payload)
    except (ConnectionError, OSError, KeyError, UnicodeDecodeError,
            asyncio.IncompleteReadError):
        pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass


async def _trigger_script(script_path):
    try:
        from pipe import run_rhino_script

        await asyncio.to_thread(
            run_rhino_script,
            Path(__file__).with_name("client.py"),
        )
        await asyncio.to_thread(run_rhino_script, script_path)
    except Exception as error:
        _log("Rhino trigger failed: {}".format(error), file=sys.stderr)
        return error
    return None


async def serve(script_path=None, ready=None):
    done = asyncio.Event()
    websocket_server = await asyncio.start_server(
        lambda reader, writer: _handle_client(reader, writer, done),
        HOST,
        PORT,
    )
    _log("WebSocket server listening on ws://{}:{}".format(HOST, PORT))
    if ready is not None:
        ready.set()

    trigger_task = (
        asyncio.create_task(_trigger_script(script_path))
        if script_path is not None
        else None
    )
    done_task = asyncio.create_task(done.wait())
    try:
        tasks = {done_task}
        if trigger_task is not None:
            tasks.add(trigger_task)

        finished, _ = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if trigger_task is not None and trigger_task in finished:
            error = trigger_task.result()
            if error is not None:
                raise error
            if not done.is_set():
                await done_task
        elif trigger_task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(trigger_task), 1)
            except asyncio.TimeoutError:
                trigger_task.cancel()
    finally:
        websocket_server.close()
        await websocket_server.wait_closed()
        if not done_task.done():
            done_task.cancel()
        if trigger_task is not None and not trigger_task.done():
            trigger_task.cancel()
        tasks = [done_task]
        if trigger_task is not None:
            tasks.append(trigger_task)
        await asyncio.gather(*tasks, return_exceptions=True)

    if done.is_set():
        _log("WebSocket server closed: End message received")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run a script inside Rhino and watch its WebSocket output"
    )
    parser.add_argument("script", help="Rhino Python script path")
    args = parser.parse_args(argv)
    try:
        asyncio.run(serve(args.script))
    except Exception as error:
        _log("rhino-watch failed: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

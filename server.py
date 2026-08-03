import argparse
import asyncio
import base64
import hashlib
import json
import os
import signal
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8765
END_COMMAND = "end"
QUIT_COMMAND = "quit"
LEGACY_DONE_COMMAND = "done"
LOG_PREFIX = "[RHINO-WATCH] "
_MAGIC = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_ROOT = str(Path(__file__).resolve().parent)
_ENVIRONMENT_HEADER = "X-Run-In-Rhino-Environment"


def normalize_environment(environment):
    if environment is None:
        return None
    try:
        values = dict(environment)
    except (TypeError, ValueError) as error:
        raise TypeError("environment must be a mapping of strings") from error
    if not values:
        return None
    for name, value in values.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise TypeError("environment names and values must be strings")
        if not name or "=" in name or "\x00" in name or "\x00" in value:
            raise ValueError("environment contains an invalid name or value")
    return values


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


async def _handshake(reader, writer, environment=None):
    request = await reader.readuntil(b"\r\n\r\n")
    headers = {}
    for line in request.decode("ascii").split("\r\n")[1:]:
        if ":" in line:
            name, value = line.split(":", 1)
            headers[name.lower()] = value.strip()

    accept = base64.b64encode(
        hashlib.sha1(headers["sec-websocket-key"].encode("ascii") + _MAGIC).digest()
    ).decode("ascii")
    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Accept: " + accept + "\r\n"
    )
    if environment is not None:
        encoded_environment = base64.urlsafe_b64encode(
            json.dumps(environment, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        response += _ENVIRONMENT_HEADER + ": " + encoded_environment + "\r\n"
    writer.write((response + "\r\n").encode("ascii"))
    await writer.drain()


async def _handle_client(
    reader,
    writer,
    done,
    data_queue,
    stop_reason,
    stop_on_end,
    stop_on_quit,
    environment,
):
    try:
        await _handshake(reader, writer, environment)
        while True:
            opcode, payload = await _read_frame(reader)
            if opcode == 1:
                message = payload.decode("utf-8")
                try:
                    envelope = json.loads(message)
                except json.JSONDecodeError:
                    envelope = {"type": "log", "message": message}
                if not isinstance(envelope, dict):
                    envelope = {"type": "log", "message": message}

                message_type = envelope.get("type")
                if message_type == "log":
                    text = str(envelope.get("message", ""))
                    print(text, end="" if text.endswith("\n") else "\n", flush=True)
                elif message_type == "data":
                    data_queue.put(envelope.get("data"))
                elif message_type == "command":
                    command = envelope.get("command")
                    if command == LEGACY_DONE_COMMAND:
                        command = END_COMMAND
                    if command == END_COMMAND and stop_on_end:
                        stop_reason["command"] = END_COMMAND
                        done.set()
                    elif command == QUIT_COMMAND and stop_on_quit:
                        stop_reason["command"] = QUIT_COMMAND
                        done.set()

                await _send_frame(writer, 1, b"received")
                if done.is_set():
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


async def _trigger_script(script_path, environment=None):
    try:
        from pipe import run_rhino_script

        await asyncio.to_thread(
            run_rhino_script,
            Path(__file__).with_name("client.py"),
        )
        if environment is not None:
            await asyncio.to_thread(
                run_rhino_script,
                Path(__file__).with_name("rhino_environment.py"),
            )
        await asyncio.to_thread(run_rhino_script, script_path)
    except Exception as error:
        _log("Rhino trigger failed: {}".format(error), file=sys.stderr)
        return error
    return None


def _listener_pids():
    try:
        result = subprocess.run(
            ["lsof", "-tiTCP:{}".format(PORT), "-sTCP:LISTEN"],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return []
    return [int(pid) for pid in result.stdout.split() if pid.isdigit()]


def _is_rhino_watcher(pid):
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        capture_output=True,
        check=False,
        text=True,
    )
    command = result.stdout.strip()
    return "rhino-watch" in command or (
        _ROOT in command and "server.py" in command
    )


def _stop_existing_watcher():
    for pid in _listener_pids():
        if not _is_rhino_watcher(pid):
            raise RuntimeError(
                "port {} is in use by a process that is not rhino-watch "
                "(PID {})".format(PORT, pid)
            )
        _log("Stopping existing rhino-watch listener (PID {})".format(pid))
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if pid not in _listener_pids():
                break
            time.sleep(0.05)
        else:
            raise RuntimeError(
                "existing rhino-watch listener (PID {}) did not stop".format(pid)
            )


async def serve(
    script_path=None,
    ready=None,
    data_queue=None,
    stop_on_end=True,
    stop_on_quit=True,
    environment=None,
):
    environment = normalize_environment(environment)
    _stop_existing_watcher()
    done = asyncio.Event()
    stop_reason = {}
    if data_queue is None:
        import queue

        data_queue = queue.Queue()
    websocket_server = await asyncio.start_server(
        lambda reader, writer: _handle_client(
            reader,
            writer,
            done,
            data_queue,
            stop_reason,
            stop_on_end,
            stop_on_quit,
            environment,
        ),
        HOST,
        PORT,
    )
    _log("WebSocket server listening on ws://{}:{}".format(HOST, PORT))
    if ready is not None:
        ready.set()

    trigger_task = (
        asyncio.create_task(_trigger_script(script_path, environment))
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
        _log(
            "WebSocket server closed: {} message received".format(
                stop_reason.get("command", "stop")
            )
        )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run a script inside Rhino and watch its WebSocket output"
    )
    parser.add_argument("script", help="Rhino Python script path")
    parser.add_argument(
        "--nostop",
        action="store_true",
        help="Keep watching after an end message; quit still stops the server.",
    )
    parser.add_argument(
        "--noquit",
        action="store_true",
        help="Keep watching after both end and quit messages.",
    )
    args = parser.parse_args(argv)
    try:
        asyncio.run(
            serve(
                args.script,
                stop_on_end=not (args.nostop or args.noquit),
                stop_on_quit=not args.noquit,
            )
        )
    except Exception as error:
        _log("rhino-watch failed: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

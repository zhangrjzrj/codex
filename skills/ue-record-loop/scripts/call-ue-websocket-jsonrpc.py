import argparse
import base64
import hashlib
import json
import os
import socket
import struct
import uuid


def receive_exact(connection, size):
    data = b""
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            raise ConnectionError("WebSocket closed before a complete frame arrived")
        data += chunk
    return data


def make_frame(payload):
    encoded = payload.encode("utf-8")
    mask = os.urandom(4)
    masked = bytes(value ^ mask[index % 4] for index, value in enumerate(encoded))
    length = len(masked)
    if length < 126:
        header = struct.pack("!BB", 0x81, 0x80 | length)
    elif length <= 0xFFFF:
        header = struct.pack("!BBH", 0x81, 0x80 | 126, length)
    else:
        header = struct.pack("!BBQ", 0x81, 0x80 | 127, length)
    return header + mask + masked


def read_frame(connection):
    first, second = struct.unpack("!BB", receive_exact(connection, 2))
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", receive_exact(connection, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", receive_exact(connection, 8))[0]
    mask = receive_exact(connection, 4) if second & 0x80 else None
    data = receive_exact(connection, length)
    if mask:
        data = bytes(value ^ mask[index % 4] for index, value in enumerate(data))
    return first & 0x0F, data.decode("utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=19877)
    parser.add_argument("--code-file", required=True)
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--fire-and-forget", action="store_true")
    arguments = parser.parse_args()
    code = open(arguments.code_file, encoding="utf-8").read()
    request = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "execute_python", "params": {"code": code}}
    connection = socket.create_connection((arguments.host, arguments.port), arguments.timeout)
    connection.settimeout(arguments.timeout)
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    handshake = f"GET / HTTP/1.1\r\nHost: {arguments.host}:{arguments.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
    connection.sendall(handshake.encode("ascii"))
    response = b""
    while b"\r\n\r\n" not in response:
        response += connection.recv(4096)
    expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()).decode("ascii")
    if f"Sec-WebSocket-Accept: {expected}" not in response.decode("latin1"):
        raise ConnectionError("UE WebSocket handshake failed")
    connection.sendall(make_frame(json.dumps(request, ensure_ascii=False)))
    if arguments.fire_and_forget:
        print("UE WebSocket request sent")
        return
    opcode, content = read_frame(connection)
    if opcode != 1:
        raise RuntimeError(f"Unexpected WebSocket opcode: {opcode}")
    print(content)


if __name__ == "__main__":
    main()

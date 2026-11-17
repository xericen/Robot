"""Bounded same-origin HTTP tunnel for Viser's binary WebSocket protocol.

WIZ's HTTP routing rejects WebSocket upgrades on custom routes. The original
Viser client/renderer and binary protocol remain unchanged behind this adapter.
"""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import queue
import threading
import time
import uuid

from websockets.sync.client import connect


class Connection:
    def __init__(self, port):
        self.socket = connect("ws://127.0.0.1:" + str(port),
                              subprotocols=["viser-v1.1.1"], proxy=None, max_size=16 * 1024 * 1024)
        self.messages = queue.Queue(maxsize=128)
        self.touched = time.monotonic()
        self.closed = False
        threading.Thread(target=self.receive, daemon=True).start()

    def receive(self):
        try:
            while not self.closed and time.monotonic() - self.touched < 60:
                try:
                    message = self.socket.recv(timeout=5)
                except TimeoutError:
                    continue
                self.messages.put(base64.b64encode(message).decode(), timeout=5)
        except Exception:
            pass
        finally:
            self.closed = True
            self.socket.close()

    def close(self):
        self.closed = True
        self.socket.close()


def start_transport(viewer_port):
    connections = {}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            try:
                action, _, key = self.path.strip("/").partition("/")
                length = int(self.headers.get("Content-Length", 0))
                if length > 2 * 1024 * 1024:
                    raise ValueError("message too large")
                body = self.rfile.read(length)
                with lock:
                    stale = [k for k, c in connections.items() if c.closed or time.monotonic() - c.touched > 60]
                    for k in stale:
                        connections.pop(k).close()
                    if action == "open":
                        if len(connections) >= 4:
                            raise ValueError("too many browser clients")
                        key = uuid.uuid4().hex
                        connections[key] = Connection(viewer_port)
                        result = {"id": key}
                    else:
                        connection = connections[key]
                        connection.touched = time.monotonic()
                        result = {}
                if action == "poll":
                    messages = []
                    try:
                        messages.append(connection.messages.get(timeout=.2))
                    except queue.Empty:
                        pass
                    while not connection.messages.empty():
                        messages.append(connection.messages.get_nowait())
                    result = {"messages": messages, "closed": connection.closed}
                elif action == "send":
                    connection.socket.send(body)
                elif action == "close":
                    connection.close()
                elif action != "open":
                    raise ValueError("invalid action")
                payload = json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except (ValueError, KeyError, OSError):
                self.send_error(400)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server

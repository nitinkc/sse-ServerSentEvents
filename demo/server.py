#!/usr/bin/env python3
"""
Zero-dependency Server-Sent Events (SSE) demo server.

Deliberately written with ONLY the Python standard library so every byte of
the SSE wire protocol is visible in this file — no framework magic.

Run:   python3 server.py        (or: uv run server.py)
Then:  open http://127.0.0.1:8765
Raw:   curl -N http://127.0.0.1:8765/events
"""
from __future__ import annotations

import itertools
import json
import os
import mimetypes
import queue
import random
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8765"))  # PORT=9000 python3 server.py
STATIC_DIR = Path(__file__).resolve().parent / "static"

# The "channels" a client may subscribe to via /events?channels=clock,chat
CHANNELS = ("clock", "stocks", "chat")

# A comment line (": hb") is sent if nothing else went out for this long.
# It keeps proxies/load balancers from killing the idle connection.
HEARTBEAT_SECONDS = 15

# Tells the browser how long to wait before auto-reconnecting after a drop.
RETRY_MS = 2000


# --------------------------------------------------------------------------
# Broker: the tiniest possible fan-out hub.
# Every connected SSE client owns one queue; publish() copies each message
# into every queue so all browsers see the same events.
# --------------------------------------------------------------------------
class Broker:
    def __init__(self) -> None:
        self._clients: set[queue.Queue] = set()
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=200)
        with self._lock:
            self._clients.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            self._clients.discard(q)

    def publish(self, *, channel: str, event: str, data: dict) -> None:
        # One global, monotonically increasing id -> powers Last-Event-ID.
        msg = {
            "id": next(_ids),
            "channel": channel,
            "event": event,
            "data": data,
        }
        with self._lock:
            for q in list(self._clients):
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    pass  # slow consumer: drop rather than stall everyone


broker = Broker()
_ids = itertools.count(1)


# --------------------------------------------------------------------------
# Event generators — background threads that pretend to be "real" sources.
# --------------------------------------------------------------------------
STOCKS = {"ACME": 142.50, "NOVA": 88.10, "ORBT": 31.75, "GLOB": 210.40}


def clock_loop() -> None:
    """Emit a `tick` event once per second."""
    while True:
        broker.publish(
            channel="clock",
            event="tick",
            data={"time": datetime.now().astimezone().isoformat(timespec="seconds")},
        )
        time.sleep(1)


def stocks_loop() -> None:
    """Emit a `stock` event at random intervals with a random-walk price."""
    while True:
        time.sleep(random.uniform(0.8, 2.2))
        sym = random.choice(list(STOCKS))
        change = round(random.uniform(-0.60, 0.65), 2)
        STOCKS[sym] = max(1.0, round(STOCKS[sym] + change, 2))
        broker.publish(
            channel="stocks",
            event="stock",
            data={"symbol": sym, "price": STOCKS[sym], "change": change},
        )


# --------------------------------------------------------------------------
# The SSE wire format, in one function. An event is just lines of
# "field: value" terminated by a BLANK line.
# --------------------------------------------------------------------------
def format_sse(event: str, data: dict, event_id: int | None = None) -> bytes:
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    if event != "message":  # "message" is the default event type; browsers omit it
        lines.append(f"event: {event}")
    # Multi-line payloads are sent as repeated `data:` lines.
    payload = json.dumps(data)
    for line in payload.splitlines() or [""]:
        lines.append(f"data: {line}")
    return ("\n".join(lines) + "\n\n").encode()  # blank line = dispatch!


# --------------------------------------------------------------------------
# HTTP handler. Three kinds of traffic:
#   GET /            -> the demo page
#   GET /static/*    -> css/js assets
#   GET /events      -> the SSE stream (the whole point)
#   POST /publish    -> lets the page broadcast a chat message to everyone
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"  # keep-alive matters for SSE

    def log_message(self, fmt: str, *args) -> None:
        print(f"  {self.address_string()}  {fmt % args}")

    # -- small response helper -------------------------------------------
    def _send(self, code: int, body: bytes = b"",
              ctype: str = "text/plain; charset=utf-8", extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    # -- routing ----------------------------------------------------------
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/events":
            return self.stream_events()
        if path in ("/", "/index.html", "/clock", "/stocks", "/chat", "/connection"):
            return self._serve_static("index.html")
        if path.startswith("/static/"):
            return self._serve_static(path.removeprefix("/static/"))
        if path == "/healthz":
            return self._send(200, b"ok")
        self._send(404, b"not found")

    def _serve_static(self, name: str) -> None:
        file = (STATIC_DIR / name).resolve()
        if not str(file).startswith(str(STATIC_DIR)) or not file.is_file():
            return self._send(404, b"not found")
        ctype = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        self._send(200, file.read_bytes(), ctype)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/publish":
            return self._send(404, b"not found")
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, b'{"error":"invalid json"}', "application/json")
        text = str(payload.get("text", "")).strip()[:500]
        if not text:
            return self._send(400, b'{"error":"empty message"}', "application/json")
        name = str(payload.get("name", "anon")).strip()[:40] or "anon"
        broker.publish(
            channel="chat",
            event="chat",
            data={"name": name, "text": text,
                  "at": datetime.now().astimezone().isoformat(timespec="seconds")},
        )
        self._send(200, b'{"ok":true}', "application/json")

    # -- THE SSE endpoint --------------------------------------------------
    def stream_events(self) -> None:
        # A stream never carries a second request — don't let the keep-alive
        # loop try to read one after the client disconnects.
        self.close_connection = True

        # Clients pick channels with ?channels=clock,chat (default: all).
        params = parse_qs(urlparse(self.path).query)
        requested = set(params.get("channels", [""])[0].split(",")) - {""}
        channels = requested or set(CHANNELS)

        # These THREE headers are what make a response an SSE stream.
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")   # the magic type
        self.send_header("Cache-Control", "no-cache")           # never buffer-cache
        self.send_header("Connection", "keep-alive")            # stream stays open
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        q = broker.subscribe()
        try:
            # Notice: no Content-Length and no chunked framing visible here —
            # the response simply never ends. We flush after every write.
            last_id = self.headers.get("Last-Event-ID")
            note = f"last received ID: {last_id}; live updates only, no replay" if last_id else "new connection"
            self._write(f": {note} | channels={','.join(sorted(channels))}\n\n")
            self._write(f"retry: {RETRY_MS}\n\n")
            self._write(format_sse("welcome", {"msg": note,
                                               "channels": sorted(channels)}))

            while True:
                try:
                    msg = q.get(timeout=HEARTBEAT_SECONDS)
                except queue.Empty:
                    # Nothing to say? Say nothing — literally. A comment line
                    # keeps intermediaries from reaping the connection.
                    self._write(": hb\n\n")
                    continue
                if msg["channel"] not in channels:
                    continue
                self._write(format_sse(msg["event"], msg["data"], msg["id"]))
        except (BrokenPipeError, ConnectionResetError):
            pass  # client went away — perfectly normal
        finally:
            broker.unsubscribe(q)

    def _write(self, chunk) -> None:
        if isinstance(chunk, str):
            chunk = chunk.encode()
        self.wfile.write(chunk)
        self.wfile.flush()  # THE most important line: push it NOW, don't buffer


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address) -> None:
        # Clients vanishing mid-request — closed tab, EventSource reconnect —
        # is normal for SSE. Don't spam tracebacks for it.
        exc = sys.exc_info()[1]
        if not isinstance(exc, (ConnectionResetError, BrokenPipeError)):
            super().handle_error(request, client_address)


def main() -> None:
    for fn in (clock_loop, stocks_loop):
        threading.Thread(target=fn, daemon=True).start()
    server = Server((HOST, PORT), Handler)
    print(f"SSE demo     -> http://{HOST}:{PORT}")
    print(f"Raw stream   -> curl -N http://{HOST}:{PORT}/events")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()

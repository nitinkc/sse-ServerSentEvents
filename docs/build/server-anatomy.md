# Anatomy of the Server

`demo/server.py` is ~250 lines of *standard-library-only* Python. No framework
hides the protocol — every SSE byte is visible. Here's the tour, top to bottom.

## The four building blocks

```mermaid
flowchart TB
    T1[clock_loop thread<br/>tick every 1s] --> B[Broker<br/>fan-out: one queue per client]
    T2[stocks_loop thread<br/>random walks] --> B
    P[POST /publish<br/>chat form] --> B
    B --> E1[/events handler<br/>client 1]
    B --> E2[/events handler<br/>client 2]
    B --> E3[/events handler<br/>client N]
```

## 1. The Broker — fan-out

Each connected SSE client gets a `queue.Queue`. `publish()` copies every
message into every queue, stamped with a global monotonic `id`.

```python
class Broker:
    def subscribe(self) -> queue.Queue: ...      # one queue per client
    def unsubscribe(self, q) -> None: ...        # on disconnect
    def publish(self, *, channel, event, data):  # copy to ALL queues
        msg = {"id": next(_ids), ...}
```

Design notes:

- `maxsize=200` + `put_nowait` → a stalled client drops events instead of
  blocking every other client. Trade "slow consumers lose events" against
  "slow consumers kill the server" — the right call for a feed.
- The `id` is assigned at publish time, so **every client sees the same ids** —
  that's what makes `Last-Event-ID` meaningful.

## 2. Event generators — threads pretending to be real

```python
def clock_loop():   # publishes event="tick" every second
def stocks_loop():  # publishes event="stock" every 0.8–2.2s, random walk
```

In a real app these are your domain events: rows from a CDC stream, pub/sub
messages, job-status callbacks. The broker doesn't care where events come from.

## 3. `format_sse` — the protocol, entire

```python
def format_sse(event, data, event_id=None):
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    if event != "message":
        lines.append(f"event: {event}")
    for line in json.dumps(data).splitlines() or [""]:
        lines.append(f"data: {line}")
    return ("\n".join(lines) + "\n\n").encode()   # blank line = dispatch
```

If you understand this function you understand the SSE spec. Fields as lines,
`data:` repeated for multi-line payloads, blank line terminates.

## 4. `stream_events` — the endpoint

The request handler for `GET /events` in five acts:

**Act 1 — subscription params.** `?channels=clock,chat` selects which broker
channels this client receives:

```python
requested = set(params.get("channels", [""])[0].split(",")) - {""}
channels = requested or set(CHANNELS)
```

**Act 2 — the three headers that matter:**

```python
self.send_header("Content-Type", "text/event-stream")
self.send_header("Cache-Control", "no-cache")
self.send_header("Connection", "keep-alive")
```

Note what is *not* sent: `Content-Length`. The response has no end.

**Act 3 — greeting.** A comment identifying the connection (echoing any
`Last-Event-ID` the browser sent), then `retry:` to set reconnect delay, then
a `welcome` event.

**Act 4 — the loop**, which is the heart of SSE:

```python
while True:
    try:
        msg = q.get(timeout=HEARTBEAT_SECONDS)   # wait for next event...
    except queue.Empty:
        self._write(": hb\n\n")                  # ...or heartbeat if quiet
        continue
    if msg["channel"] not in channels:
        continue
    self._write(format_sse(msg["event"], msg["data"], msg["id"]))
```

And `_write` contains the most important line in the file:

```python
self.wfile.write(chunk)
self.wfile.flush()     # push NOW — buffering is the enemy of SSE
```

**Act 5 — cleanup.** `BrokenPipeError`/`ConnectionResetError` means the client
left; `finally: broker.unsubscribe(q)` frees the queue.

## 5. The write path — `POST /publish`

Chat shows the standard SSE write path: client POSTs JSON → handler validates
→ `broker.publish(channel="chat")` → every subscribed `/events` stream (all
tabs) gets the event. SSE is receive-only; this POST is a *separate, ordinary*
HTTP request.

## Threading model

`ThreadingHTTPServer` gives each connection a thread. The `/events` handler's
thread just blocks on `q.get()` — cheap, and fine for dozens/hundreds of
clients. It does not scale to 100k connections (threads ≈ MBs each); for that
you want `asyncio` or a dedicated push layer — see
[production](../ship/production.md). For learning and most internal tools,
threads + queues is the honest, legible choice.

## Try reading it with the stream open

Run `python3 demo/server.py`, `curl -N` the stream in one terminal, and read
`stream_events` top to bottom while events scroll past. Every line you read
maps to bytes you're watching — that's the point of this file.

Next: [demo walkthrough](walkthrough.md) — experiments to run.

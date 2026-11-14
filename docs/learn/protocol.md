# The Wire Protocol

SSE's beauty is that the *entire spec* fits in your head. A stream is a
`text/event-stream` response body made of **events**, and an event is a block
of `field: value` lines ended by a **blank line**.

```text
┌─ an event ─────────────────┐
id: 42                        │   ← optional fields, any order
event: stock                  │
data: {"symbol":"ACME",       │
data: "price":142.50}         │
                              │   ← blank line = "dispatch now"
└─────────────────────────────┘
```

## The four fields

| Field | Purpose | Repeatable? |
| --- | --- | --- |
| `data:` | The payload. Concatenated with `\n` if repeated. | ✅ yes — that's how multi-line data works |
| `event:` | Names the event type. Client listens via `addEventListener(name)`. | no |
| `id:` | Sets `lastEventId`. Sent back as `Last-Event-ID` on reconnect. | no |
| `retry:` | Milliseconds the client should wait before reconnecting. | no |

Any other field name is **ignored** — so you can send comments for debugging
or heartbeats.

## Field-by-field

### `data:` — the payload (required)

```text
data: hello

data: line one
data: line two
```

The second example delivers `"line one\nline two"` — **one** event whose data
contains a newline. JSON is the convention for structured data
(`data: {"price": 142.5}`), but the protocol doesn't care; it's all strings.

!!! warning "No leading/trailing whitespace games"
    Everything after `data: ` up to the newline is data — a single leading
    space after the colon is stripped, but the rest is literal. Just `json.dumps`
    your payload and move on.

### `event:` — naming events

```text
event: tick
data: {"time": "2026-11-13T10:02:01"}

event: chat
data: {"name": "ada", "text": "hi"}
```

On the client:

```js
es.addEventListener("tick", handler);   // gets the tick event
es.addEventListener("chat", handler);   // gets the chat event
es.onmessage = handler;                  // only events WITHOUT an event: field
```

The default type is `message`. If you never send `event:`, everything lands
on `onmessage`.

### `id:` — resumability

```text
id: 41
data: ...

id: 42
data: ...
```

The browser remembers the last id it saw. On reconnect it sends:

```text
GET /events
Last-Event-ID: 42
```

Your server can then replay missed events or resume a cursor. **Set ids on
every event** — it costs nothing and buys exactly-once-ish semantics. (See
[reliability](reliability.md).)

### `retry:` — reconnect backoff

```text
retry: 2000
```

Tells the browser "if we get disconnected, wait 2000ms before retrying."
Applies to the whole connection from then on; you can send it once at the
top of the stream. Without it, browsers pick their own (usually ~3s).

### Comments — lines starting with `:`

```text
: hb

: this is a comment, ignored by EventSource
```

Two uses:

1. **Heartbeat**: send `: hb` every N seconds so proxies, load balancers, and
   NATs don't drop your "idle" connection. Our demo uses 15s.
2. **Human debugging**: first line of our stream is a comment describing the
   connection — you see it in `curl` but never in JS.

## Putting it together — a real stream

```bash
$ curl -N http://127.0.0.1:8765/events
```

```text
: new connection | channels=chat,clock,stocks   ← comment (JS never sees this)

retry: 2000                                      ← set reconnect delay

event: welcome                                   ← named event, no id
data: {"msg": "new connection", "channels": ["chat","clock","stocks"]}

id: 1                                            ← tick event
event: tick
data: {"time": "2026-11-13T10:02:01+05:30"}

id: 2
event: stock
data: {"symbol": "NOVA", "price": 88.4, "change": 0.3}

: hb                                             ← heartbeat after 15s idle

id: 3
event: chat
data: {"name": "ada", "text": "hello", "at": "..."}
```

## The response headers that make it SSE

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream     ← REQUIRED — this is the switch
Cache-Control: no-cache             ← stop caches buffering events
Connection: keep-alive              ← the response never ends
```

Gotchas:

- **No `Content-Length`** — the length is unknowable, that's the point.
- **Flush every write.** If your framework buffers, events arrive in clumps.
- **`X-Accel-Buffering: no`** for nginx (details in
  [production](../ship/production.md)).
- `text/event-stream` must be exact — `text/plain` streams will *display* in
  curl but `EventSource` refuses them.

## Dispatch rules (the spec in 30 seconds)

A client must:

1. Buffer `field: value` lines until a **blank line**, then dispatch.
2. Strip exactly one leading space after the colon, if present.
3. Concatenate multiple `data:` fields with `\n`.
4. Ignore unknown fields and lines starting with `:`.
5. Fire `onmessage` if no `event:` field was given; otherwise fire an event
   of that type. Skip dispatch entirely if there was no `data:` at all
   (that's why `retry:` alone doesn't create an event, and comments are free).

## Check your understanding

<quiz>
What actually dispatches (delivers) an SSE event to JavaScript?
- [x] A blank line after the field lines
- [ ] A newline after each `data:` field
- [ ] A `\0` byte
- [ ] A `Content-Length` header

Fields buffer until an empty line — that's the entire framing mechanism.
</quiz>

<quiz>
Which field may appear **multiple times** in a single event?
- [ ] `id:`
- [ ] `event:`
- [x] `data:`
- [ ] `retry:`

Multiple `data:` lines are joined with `\n` — that's how multi-line payloads work.
</quiz>

<quiz>
A block contains only `event: hello` — no `data:` line. What happens?
- [ ] A `hello` event fires with empty data
- [x] Nothing — the event is discarded
- [ ] The connection resets

No `data:` = no dispatch. That's why `retry:`-only blocks and comments are free.
</quiz>

<quiz>
Which of these does JavaScript **receive** via EventSource? *(select all)*
- [x] `data:` payloads
- [x] `event:` names (via `addEventListener`)
- [x] `id:` values (via `e.lastEventId`)
- [ ] `: ` comment lines

Comments travel on the wire (visible in `curl -N`) but never dispatch — they
exist for heartbeats and humans.
</quiz>

Next: [the EventSource API](eventsource-api.md) — the browser side.

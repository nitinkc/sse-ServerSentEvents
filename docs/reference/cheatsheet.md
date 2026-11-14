# SSE Cheatsheet

## Wire format

```text
: comment — ignored by clients, keeps connections alive
retry: 2000           — ms before browser auto-reconnects
id: 42                — remembered; sent back as Last-Event-ID
event: stock          — event name; omit for default "message"
data: {"price": 1}    — payload; repeat data: lines for multi-line
                      — BLANK LINE dispatches the event
```

Rules: `field: value` lines → dispatch on blank line → one space after `:` is
stripped → unknown fields and `:` lines ignored → no `data:` = no event.

## Response headers

```http
Content-Type: text/event-stream   # required, exact
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no             # when behind nginx
```

No `Content-Length`. Flush every event.

## Client API — everything

```js
const es = new EventSource("/events?channels=a,b");
es.onopen / es.onerror            // lifecycle
es.onmessage                      // unnamed events only
es.addEventListener("name", fn)   // named events
e.data                            // string — JSON.parse yourself
e.lastEventId                     // last id: seen
es.readyState                     // CONNECTING(0) OPEN(1) CLOSED(2)
es.close()                        // you close it; reconnect is automatic
```

Gotchas: GET only · no custom headers · cookies OK · ~6 conns/origin on h1.

## Server skeleton (any language)

```python
write_headers("text/event-stream", "no-cache", "keep-alive")
write("retry: 2000\n\n")
while True:
    msg = queue.get(timeout=15)
    if msg is None:
        write(": hb\n\n")           # heartbeat
    else:
        write(f"id: {msg.id}\nevent: {msg.event}\ndata: {json(msg.data)}\n\n")
    flush()
```

## Reconnect request

```http
GET /events
Accept: text/event-stream
Last-Event-ID: 42        ← browser sends automatically
```

## Numbers to remember

| Thing | Value |
| ---| --- |
| Heartbeat interval | 10–25s |
| Browser default retry | ~3s |
| HTTP/1.1 conns per origin | ~6 (use HTTP/2) |
| Max safe event size | unbounded, but keep < ~64KB |

## curl recipes

```bash
curl -N localhost:8765/events                        # raw stream
curl -N "localhost:8765/events?channels=clock"       # filtered
curl -N -H "Last-Event-ID: 42" localhost:8765/events # simulate resume
curl -XPOST -d '{"text":"hi"}' -H 'Content-Type: application/json' \
     localhost:8765/publish                          # write path
```

## What makes a server SSE-capable

SSE is **plain HTTP** — no new protocol, no handshake, no framing. Any HTTP
server that can do these three things can serve SSE:

1. **Hold a response open** — never send `Content-Length`, never terminate
   the body. The response just doesn't end.
2. **Flush on demand** — each `write()` must reach the socket NOW. Buffered
   output is the #1 bug: if your framework buffers the response body, SSE
   silently delivers nothing (look for a `flush()` call or a
   "streaming response" API).
3. **One long-lived connection per client** — so the server must handle
   many concurrent connections: threads, async, or event loop — anything
   that doesn't block the whole server on one client.

That's it. `python3 -m http.server` can't do it (no app code), but
`http.server` + a handler that loops-and-flushes can — see
`demo/server.py` in the repo ([anatomy](../build/server-anatomy.md)).

Works over HTTP/1.1 (keep-alive) and HTTP/2+ (streams fix the ~6 conns/origin
limit). No TLS, upgrade, or special library required.

### vs. WebSocket — the bar is much higher

| | SSE | WebSocket |
| --- | --- | --- |
| Protocol | Plain HTTP/1.1+, response never ends | New protocol (`ws://`), RFC 6455 |
| Handshake | None — just GET + response headers | `101 Switching Protocols` + `Upgrade:`/`Sec-WebSocket-*` headers + SHA-1 accept key |
| Framing | UTF-8 text lines, blank line = dispatch | Binary frame protocol: opcodes, FIN bit, masking, ping/pong, close frames |
| Server needs | HTTP + `flush()` | Frame parser/serializer — realistically a library (`websockets`, `ws`, `gorilla/websocket`) |
| Proxy/LB | Passes as normal HTTP; disable buffering (`X-Accel-Buffering: no`) | Must explicitly support `Upgrade` (nginx `proxy_set_header Upgrade/Connection`) |
| Direction | Server→client only | Full duplex |
| Payload | UTF-8 text (JSON) | Text **and** binary |

Rule of thumb: **SSE = any HTTP stack. WebSocket = you need a WebSocket-aware
server/library and infrastructure that tolerates the Upgrade handshake.**

## When to use what

| Need | Tool |
| ---| --- |
| server→client feed | SSE |
| client also streams | WebSocket |
| >30s freshness OK | polling |
| binary | WebSocket |

Full details: [protocol](../learn/protocol.md) ·
[reliability](../learn/reliability.md) · [production](../ship/production.md)

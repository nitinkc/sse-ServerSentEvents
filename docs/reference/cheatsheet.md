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

## When to use what

| Need | Tool |
| ---| --- |
| server→client feed | SSE |
| client also streams | WebSocket |
| >30s freshness OK | polling |
| binary | WebSocket |

Full details: [protocol](../learn/protocol.md) ·
[reliability](../learn/reliability.md) · [production](../ship/production.md)

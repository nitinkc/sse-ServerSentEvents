# Production Checklist

The demo works because localhost is kind. Production is not. These are the
things that actually break SSE in the real world, roughly in order of "how
often they bite".

## 1. Buffering — the #1 killer

Your server flushed. Something in the middle didn't. Symptoms: events arrive
in clumps every N seconds, or only when the buffer fills.

| Layer | Fix |
| ---| --- |
| **Your app/framework** | Call `flush()` after every event. Disable any response middleware that buffers (gzip-on-the-fly in some frameworks buffers!). |
| **nginx** | `proxy_buffering off;` or send response header `X-Accel-Buffering: no` from your app. Also `proxy_read_timeout 1h;` |
| **Load balancers / CDNs** | Cloudflare: SSE works, but disable caching on the route. Some managed LBs buffer unconditionally — test. |
| **Compression** | `gzip` can hold small events hostage. Either disable compression on `/events`, or flush the compressor after each event (most frameworks' flush does this). Padding to ~2KB is the ugly fallback. |

## 2. Timeouts

Every hop has an idle timeout; the default is often 30–60s.

- Send **heartbeats every 10–25s** (`: hb`) — defeats almost all of them.
- Still set sane explicit timeouts: nginx `proxy_read_timeout`, gunicorn
  `--timeout`, LB idle timeouts — raise them for the SSE route or connections
  die on schedule.
- Browsers will reconnect anyway (that's the point of `retry:`), but churn is
  wasteful — heartbeats are cheaper than reconnects.

## 3. HTTP/1.1 connection limits

- Browsers cap ~6 HTTP/1.1 connections per origin. Each SSE stream holds one
  for its whole life — a few tabs can starve *other* requests.
- **Fix: serve over HTTP/2** (or h3). Hundreds of streams multiplexed on one
  connection, limit gone. This requires TLS in practice — which you wanted anyway.
- If you can't do h2: one stream per tab, share it across components.

## 4. Authentication

`EventSource` can't set headers. Options:

| Method | Notes |
| ---| --- |
| **Cookie session** | Just works — same-origin requests carry cookies. The default for web apps. |
| **Token in query string** | `/events?token=…`. Works, but tokens in URLs leak into logs/history — use short-lived, single-purpose tokens. |
| **`fetch-event-source`** | When you truly need `Authorization` headers — trades native auto-reconnect for full control. |

Whatever you choose, re-check auth *per connect*: a stream opened before a
logout stays open until it's closed — so **close streams on auth revocation**.

## 5. CORS

Cross-origin `EventSource` works with `Access-Control-Allow-Origin` (and
`withCredentials` + `Allow-Credentials` for cookies). Our demo sends
`Access-Control-Allow-Origin: *` so the page works even from `file://` —
tighten it in production. EventSource never sends a preflight (it's a plain
GET), but your `POST /publish`-style endpoints will.

## 6. Scaling past one process

The broker in this demo is in-memory: one process, N clients. Production
options:

- **Sticky one-process-per-tenant**: often enough for internal tools.
- **External fan-out**: Redis pub/sub, NATS, Kafka → each app node subscribes
  and forwards to its own clients. The broker interface barely changes:
  `subscribe()` yields messages from Redis instead of a local queue.
- **Dedicated push layer**: pushpin / Mercure / managed services
  (Ably, Pusher, AWS API Gateway WebSocket-adjacent) when you'd rather not run it.
- **Watch thread/async limits**: one thread per connection melts at ~10⁴
  clients. `asyncio` (or Go, Node, etc.) takes you to ~10⁵+.

## 7. Correctness details that get forgotten

- **Always send `id:`** — free `Last-Event-ID` resume support.
- **Make event consumers idempotent** — at-least-once delivery is real.
- **Handle partial writes** — `flush()` after the complete event, never mid-event.
- **UTF-8 everything** — declare it, encode explicitly, don't let the platform guess.
- **JSON payloads only as `data:`** — never interpolate user text into other
  fields (a newline in `event:` would corrupt the frame — sanitize or stick to `data:`).
- **Graceful shutdown**: on deploy, respond to SIGTERM by closing streams;
  clients reconnect to the new version automatically. Test this path!
- **Observability**: count open streams, events/sec, drops from full queues,
  reconnect rate. "It seemed fine" is how SSE outages hide.

## 8. Quick self-audit

```text
[ ] flush after every event            [ ] heartbeat ≤ 25s
[ ] X-Accel-Buffering: no behind nginx [ ] timeouts raised for /events
[ ] served over HTTP/2 (+TLS)          [ ] id: on every event
[ ] auth enforced on connect           [ ] streams closed on logout/deploy
[ ] cross-instance fan-out plan        [ ] handlers idempotent
```

If all nine are checked, your SSE is production-grade.

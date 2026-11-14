# Reconnection, Heartbeats & Reliability

SSE connections are *long-lived*. Hours-long. Anything that can interrupt a
TCP connection will, eventually: Wi-Fi roaming, proxy idle timeouts, deploys,
laptop sleep. SSE has three built-in mechanisms for surviving them — none of
which require client code.

## 1. Automatic reconnection (free)

When the connection drops, the browser waits (default ~3s, or your `retry:`
value) and re-issues the GET. Your job on the server: **treat every connect as
a new connection**. Don't assume a returning client is a new user — that's what
`Last-Event-ID` is for.

```text
retry: 2000     ← send once near the top of the stream
```

Things to know:

- `onerror` fires on each failed attempt, `readyState` stays `CONNECTING`.
- If the server responds with non-`text/event-stream` or a 4xx (other than
  401/403/407 which may retry in some browsers), the client goes `CLOSED`
  and stops retrying.
- You can't tune backoff beyond the `retry:` field. For exponential backoff,
  you'd need `fetch()`-based SSE instead.

## 2. `Last-Event-ID` (resume where you left off)

Every event the client receives updates its remembered `lastEventId`. On
reconnect:

```text
GET /events HTTP/1.1
Last-Event-ID: 42
```

Server-side, you now have options:

| Strategy | How |
| ---| --- |
| **Replay buffer** | Keep last N events (ring buffer); on reconnect, flush everything after `Last-Event-ID`. |
| **Cursor/resume** | For streams backed by a log (Kafka, DB oplog), the id *is* a cursor — resume reading there. |
| **State snapshot** | Don't replay at all: send one `snapshot` event with current state, then continue live. Simplest correct option for dashboards. |

Our demo keeps it simple: it *logs* the resume point in a comment and `welcome`
event — watch the footer `lastEventId` survive a reconnect.

!!! warning "At-least-once, not exactly-once"
    A client may receive the same event twice: the server flushed it, the
    client never got it, reconnect, replay. **Make handlers idempotent** — e.g.
    keys events by id and skip duplicates if that matters to you.

## 3. Heartbeats (keep the pipe warm)

Many intermediaries silently kill connections idle for 30–120s. If your stream
has quiet periods, you *must* say something periodically — even nothing.

```text
: hb
```

A comment line costs 5 bytes, is invisible to `EventSource` handlers, and
resets every idle timer on the path. Our server sends one whenever the broker
queue is empty for `HEARTBEAT_SECONDS` (15s).

Alternatives: a real `event: ping` (visible to JS — useful if the *client* also
wants liveness info) or padding `data:` events. Comments are cheapest.

**Recommended heartbeat intervals:** 10–25s. Under 10s wastes bytes at scale;
over 30s risks aggressive proxies.

## Disconnects you *want*

Sometimes the server should end the stream itself:

- **Deploys**: close all streams; clients reconnect to the new version. Graceful
  if your LB drains — the `retry:` field controls how fast they come back.
- **Auth expiry**: close the stream and let the client's next connect hit a 401
  → they redirect to login.
- **Server-side throttle**: if a consumer falls behind (queue full), close and
  let them resync rather than buffer forever.

Detecting a dead client from the server is easy: the next `write()` raises
`BrokenPipeError`/`ECONNRESET`. You usually won't notice until you try to
write — another reason heartbeats are useful: they double as liveness probes
that reap dead connections promptly.

```python
try:
    self.wfile.write(chunk)
    self.wfile.flush()
except (BrokenPipeError, ConnectionResetError):
    broker.unsubscribe(q)   # client gone — clean up and move on
```

## Failure modes cheat table

| Failure | Client sees | Fix |
| --- | --- | --- |
| Wi-Fi drop | `onerror`, auto-reconnect | nothing — built in |
| Proxy idle-kill | stream goes silent, then error | heartbeats ≤ 25s |
| Server restart | reconnect → possibly replay | `Last-Event-ID` handling |
| Event arrives twice | duplicate UI entries | idempotent handlers / dedupe by id |
| Non-SSE response (error page) | `CLOSED`, no retry | fix the server, never return HTML on `/events` |

## Check your understanding

<quiz>
Wi-Fi drops for 10 seconds mid-stream. What does the browser do?
- [x] Auto-reconnects after `retry:` ms, sending `Last-Event-ID`
- [ ] Fires `onerror` once and gives up
- [ ] Buffers events and delivers them when the network returns
- [ ] Silently continues when the socket heals

Your JS does nothing — `onerror` fires while retrying, `onopen` on success.
</quiz>

<quiz>
The server gets `Last-Event-ID: 42` on a reconnect. Sane responses? *(select all)*
- [x] Replay buffered events with `id > 42`
- [x] Resume a log/DB cursor at 42
- [x] Send a fresh state snapshot, then continue live
- [ ] Ignore it — resume semantics don't matter

Any of the first three is valid; the choice depends on your stream's source.
</quiz>

<quiz>
Why send `: hb` every 15s during quiet periods?
- [ ] To keep the client's `EventSource` from timing out
- [x] Because intermediaries (proxies, NATs, LBs) kill idle connections
- [ ] To advance `lastEventId`
- [ ] To measure client latency

Bonus effect: the periodic write surfaces dead clients via `BrokenPipeError`.
</quiz>

<quiz>
A client applies the same event twice. Your server is…
- [ ] Buggy — fix the replay buffer
- [x] Probably fine — SSE delivery is at-least-once
- [ ] Definitely leaking connections

"Flushed" ≠ "received" — a drop between write and read causes replay.
Make handlers **idempotent** (dedupe by `id` if needed) and move on.
</quiz>

Next: [SSE vs the alternatives](alternatives.md) — knowing when *not* to use it.

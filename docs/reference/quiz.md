# SSE 101 — Final Quiz

Everything from the course in one self-test. Answers are graded instantly
(single-choice auto-submits; multi-choice needs all correct boxes; blanks are
case-insensitive). Your score is saved in the browser — refresh to retry.

Aim for **10/10** before calling yourself SSE-fluent. 🎯

---

## Round 1 — Fundamentals

<quiz>
An SSE "event" on the wire is…
- [ ] A JSON object sent as one HTTP response
- [x] A block of `field: value` text lines ended by a blank line
- [ ] A binary frame inside an upgraded connection
- [ ] A `data:` URL in an `<iframe>`

That's the whole protocol — text lines + blank-line dispatch.
</quiz>

<quiz>
The header that makes a response an SSE stream is `Content-Type: [[text/event-stream]]`

---
Exact match required — anything else makes `EventSource` refuse the response
and stop retrying.
</quiz>

<quiz>
Which of these are valid SSE fields? *(select all)*
- [x] `data:`
- [x] `event:`
- [x] `id:`
- [x] `retry:`
- [ ] `timeout:`
- [ ] `ack:`

Unknown fields are simply ignored — so you could invent `x-foo:` for debugging.
</quiz>

<quiz>
True or false: the browser client library for SSE must be installed via npm.
- [ ] True — `npm install eventsource`
- [x] False — `EventSource` is built into every modern browser

Zero client dependencies is one of SSE's superpowers.
</quiz>

## Round 2 — The Client

<quiz>
`new EventSource("/events")` sends which request?
- [x] `GET /events` with `Accept: text/event-stream`
- [ ] `POST /events` with a WebSocket upgrade
- [ ] `GET /events` with `Upgrade: eventsource`
- [ ] `CONNECT /events`

It's an ordinary GET — no upgrade dance, no special method.
</quiz>

<quiz>
Events with `event: tick` on the wire are received with…
- [ ] `es.onmessage`
- [x] `es.addEventListener("tick", handler)`
- [ ] `es.ontick`
- [ ] `es.addEventListener("message", handler)`

`onmessage` only sees events with **no** `event:` field (default type `message`).
</quiz>

<quiz>
`es.readyState` inside `onerror` is `0`. The stream is…
- [ ] Closed forever
- [ ] Open and healthy
- [x] Reconnecting — the browser is retrying on its own

`0` = CONNECTING, `1` = OPEN, `2` = CLOSED. Only `CLOSED` means give up.
</quiz>

<quiz>
Name one way to send a credential over native EventSource despite the
"no custom headers" limit: use a [[cookie]]-based session or a token in the
query string.

---
Cookie auth works automatically same-origin. For header-level auth you need
`fetch()`-based SSE (`@microsoft/fetch-event-source`) instead.
</quiz>

## Round 3 — Reliability & Production

<quiz>
On reconnect, the browser automatically sends which header?
- [ ] `If-Modified-Since`
- [x] `Last-Event-ID`
- [ ] `ETag`
- [ ] `X-Resume-From`

Built from the last `id:` the client saw — free resume support.
</quiz>

<quiz>
Why did your events arrive in 30-second clumps behind nginx?
- [ ] The server forgot `id:` fields
- [x] Response buffering — need `X-Accel-Buffering: no` / `proxy_buffering off`
- [ ] `retry:` was set too high
- [ ] EventSource batches events by design

Buffering (nginx, gzip, framework) is the #1 real-world SSE bug. Also check
you `flush()` after every write.
</quiz>

<quiz>
Which practices keep SSE healthy in production? *(select all)*
- [x] Heartbeat comment every 10–25s
- [x] `id:` on every event
- [x] Serve over HTTP/2 (fixes the 6-connection limit)
- [x] Make event handlers idempotent
- [ ] Send `Content-Length` on the stream

A never-ending response can't declare a length — that's the point.
</quiz>

<quiz>
Your app needs the client to stream cursor positions live. SSE is…
- [ ] Perfect — that's its job
- [x] The wrong tool — use WebSocket for client→server streaming
- [ ] Possible with `es.send()`

`EventSource` has no `send()`. SSE is a broadcast medium, not a socket.
</quiz>

---

!!! tip "Scoring"
    - **10–12**: Ship it. Go read the [exercises](exercises.md) and break the
      demo on purpose.
    - **7–9**: Solid. Skim [the protocol page](../learn/protocol.md) and
      [reliability](../learn/reliability.md) for the misses.
    - **<7**: Rerun the [demo walkthrough](../build/walkthrough.md) with
      `curl -N` open — watching real bytes makes it click fast.

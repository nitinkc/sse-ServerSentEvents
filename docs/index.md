# SSE, simply

**The browser asks once. The server keeps sending updates.**

That is Server-Sent Events (SSE). It uses an ordinary HTTP response that stays
open, rather than a new request for every update.

## Start with a live clock

```bash
uv run demo/server.py
```

Open <http://127.0.0.1:8765>. The time changes because the **server** sends a
new value every second. The page does not refresh.

## Three things to remember

1. **A stream:** an HTTP response that stays open for updates.
2. **An event:** one text update, finished by a blank line.
3. **EventSource:** the browser's built-in JavaScript API for receiving those updates.

For example, the server sends:

```text
event: tick
data: {"time": "2026-11-13T10:30:00+00:00"}

```

`tick` names the update. `data` holds its contents. JSON is a convenient choice,
not a requirement of SSE.

## A short learning path

1. [Run the demo](build/quickstart.md) and watch one clock.
2. [Understand the idea](learn/what-is-sse.md) with a tiny browser example.
3. [Try three experiments](build/walkthrough.md): inspect, disconnect, reconnect.

**You can stop there.** You do not need stocks, chat, brokers, or deployment
configuration to understand the basic idea.

## When you need more

- [Event fields](learn/protocol.md): `data`, `event`, `id`, and `retry`.
- [Browser API](learn/eventsource-api.md): connection handling and listeners.
- [Reliability](learn/reliability.md): reconnects, heartbeats, and replay.
- [Server code](build/server-anatomy.md): how the optional broadcast examples work.
- [Choosing a transport](learn/alternatives.md): SSE, polling, or WebSockets.
- [Production checklist](ship/production.md): deployment concerns, not beginner prerequisites.
- [Cheatsheet](reference/cheatsheet.md), [quiz](reference/quiz.md), and [exercises](reference/exercises.md).

!!! important "Reconnect is not replay"
    EventSource normally retries a lost connection automatically. Recovering missed
    events requires the server to store and replay them. This demo sends live updates only.

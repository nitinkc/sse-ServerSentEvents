# Exercises — Break It, Then Fix It

Ordered roughly easy → hard. Each one teaches a production lesson. Solutions
aren't provided — the point is to break the demo and observe.

## 1. Heartbeat forensics

Set `HEARTBEAT_SECONDS = 3` in `server.py`, restart, and
`curl -N ".../events?channels=chat"`. Count heartbeats between events. Then set
it to `120` and imagine a proxy with a 60s idle timeout — what happens to your
clients?

*Lesson: heartbeats exist for intermediaries, not for your code.*

## 2. The buffering bug

Comment out `self.wfile.flush()` in `_write`. `curl -N` again — what do you
see now? (Nothing, until the OS buffer flushes or enough events pile up.)

*Lesson: the most common real-world SSE bug is a missing flush — at some layer
you didn't know existed.*

## 3. Make an event without `id:`

Remove `event_id` from the `tick` publishes. Connect, kill the server, restart.
What does `lastEventId` in the footer show now? Why did `Last-Event-ID` get
*stale*?

*Lesson: only `id:`-bearing events advance the resume cursor — send them on
everything or your resume point drifts.*

## 4. Write a second client language

Connect to `/events` with **Python** instead of the browser:

```python
import urllib.request
for line in urllib.request.urlopen("http://127.0.0.1:8765/events"):
    print(line, end="")   # parse field: value yourself
```

Extend it to dispatch on blank lines — that's the whole client spec.

*Lesson: SSE clients are ~30 lines in any language. It's just HTTP.*

## 5. Event injection

Send a chat message containing a newline and the text `event: admin` via
`POST /publish`. Look at the raw stream with `curl -N`. Why *doesn't* it inject
an event? Where is the newline handled?

*Lesson: the JSON encoding in `data:` saves you here — but never interpolate
user strings into `event:`/`id:` fields.*

## 6. Replay buffer (the big one)

Add a ring buffer of the last 100 events to the broker. On a new connection
with `Last-Event-ID: N`, flush all buffered events with `id > N` before
joining the live queue. Test: `curl -N`, `Ctrl-C` it, note the last id, then
`curl -N -H "Last-Event-ID: <id>"`.

*Lesson: this is what "resume" means in production SSE — the difference
between "live feed" and "durable stream".*

## 7. Per-connection channels server-side vs client-side

Move filtering: subscribe to *everything* in EventSource and drop unwanted
channels in JS. Compare with the current `?channels=` approach.

*Lesson: server-side filtering saves bandwidth; client-side filtering avoids
reconnects when the filter changes. Know why you'd pick each.*

## 8. Graceful shutdown

Add SIGTERM handling that sends an `event: goodbye` to every client, then
closes streams. Watch browser reconnect behavior.

*Lesson: deploys shouldn't look like outages — and `retry:` controls the
thundering herd.*

## 9. Slow consumer

Make `stocks_loop` publish every 10ms and subscribe one paused `curl`
(`Ctrl-Z`). Watch other clients — do they stall? Why not?

*Lesson: `put_nowait` + bounded queues = backpressure by dropping. What would
a Kafka-style consumer do instead?*

## 10. Port it

Re-implement `stream_events` + `format_sse` in another language (Node
`http`, Go `net/http`, Rust axum — pick one). Keep the wire format identical;
verify the demo page works unchanged against your new server.

*Lesson: SSE is a protocol, not a library. If the bytes match, the client
can't tell the difference.*

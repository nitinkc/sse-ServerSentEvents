# The EventSource API

The browser side of SSE is one object: `EventSource`. It has a tiny surface —
this page covers all of it.

## Create and listen

```js
const es = new EventSource("/events");

// events with no `event:` field land here
es.onmessage = (e) => console.log("message:", e.data);

// named events need addEventListener
es.addEventListener("tick", (e) => console.log("tick:", e.data));
es.addEventListener("stock", (e) => console.log("stock:", e.data));
```

The `e` in every handler is a `MessageEvent`:

| Property | Contains |
| ---| --- |
| `e.data` | The `data:` payload — **always a string**. Parse JSON yourself. |
| `e.lastEventId` | The `id:` of this event (or the last id seen, for id-less events). |
| `e.type` | The event name — `"message"`, `"tick"`, whatever `event:` said. |
| `e.origin` | Origin of the stream. |

!!! tip "Parse once, parse early"
    `e.data` is a string. `JSON.parse(e.data)` is the universal first line of
    most handlers — our demo does exactly that.

## Lifecycle: open / error / close

```js
es.onopen = () => setStatus("open");

es.onerror = () => {
  // Fires on connection failure AND on every failed reconnect attempt.
  // Check readyState to tell them apart:
  if (es.readyState === EventSource.CONNECTING) {
    setStatus("reconnecting");   // a retry is already scheduled — do nothing
  } else {
    setStatus("closed");         // CLOSED — it gave up (e.g. non-SSE response)
  }
};

// You close it; it never closes itself except on fatal errors.
es.close();
```

`readyState` values:

| Constant | Value | Meaning |
| --- | --- | --- |
| `EventSource.CONNECTING` | 0 | Connecting or reconnecting — retries in progress |
| `EventSource.OPEN` | 1 | Connected, events flowing |
| `EventSource.CLOSED` | 2 | Dead — you called `close()` or a fatal error occurred |

## What EventSource does *for* you

- ✅ Opens the connection and sets `Accept: text/event-stream`
- ✅ Parses the wire format (blank-line dispatch, multi-line data, comments)
- ✅ Reconnects automatically on drops, honoring the `retry:` field
- ✅ Sends `Last-Event-ID` on reconnects — for free
- ✅ Buffers correctly across TCP chunk boundaries (half an event never fires)

## What it does *not* do — the sharp edges

- ❌ **GET only.** No POST, no custom body.
- ❌ **No custom headers** in the browser API. `Authorization: Bearer …` is not
  possible with native `EventSource` — auth comes from cookies or a token in
  the query string (see [production](../ship/production.md)).
- ❌ **No reconnection of a half-read stream** — if the server crashes mid-event,
  that partial event is discarded.
- ❌ **No pause/backpressure API** — events queue in the browser if your
  handler is slow.
- ❌ **HTTP/1.1 connection limits**: ~6 connections per origin per browser.
  Two tabs with two streams each = 4 used. HTTP/2 removes this limit.

!!! note "Need headers or POST?"
    The community standard is `fetch()` + a manual SSE parser, or the
    [`@microsoft/fetch-event-source`](https://github.com/Azure/fetch-event-source)
    package (~2KB) — same protocol, full control. The wire format is the same;
    you just lose auto-reconnect and `Last-Event-ID` handling (reconnect logic
    becomes yours).

## Query params are your config surface

Since headers are off-limits, encode client choices in the URL:

```js
new EventSource("/events?channels=clock,chat&since=2026-11-13T10:00:00Z");
```

Our demo uses this for channel subscriptions — the checkboxes rebuild the URL
and reconnect.

## Minimal robust client — the pattern our demo uses

```js
let es;

function connect() {
  if (es) es.close();
  es = new EventSource("/events");

  es.onopen  = () => ui.status("open");
  es.onerror = () =>
    ui.status(es.readyState === EventSource.CONNECTING ? "reconnecting" : "closed");

  es.addEventListener("tick", (e) => ui.tick(JSON.parse(e.data)));
}

window.addEventListener("beforeunload", () => es?.close());  // tidy
connect();
```

## Check your understanding

<quiz>
Inside `addEventListener('stock', e => …)`, what is `e.data`?
- [x] A string — you `JSON.parse` it yourself
- [ ] A parsed object — the browser handles JSON
- [ ] An ArrayBuffer
- [ ] Depends on the `Content-Type` the server sent

SSE payloads are always UTF-8 text. JSON is a convention, not the protocol.
</quiz>

<quiz>
Where do events **without** an `event:` field land?
- [ ] `addEventListener('default', …)`
- [x] `es.onmessage`
- [ ] They throw an error

The default event type is `message`, which `onmessage` handles.
</quiz>

<quiz>
Inside `onerror`, `es.readyState === EventSource.CONNECTING` means…
- [ ] The stream is dead — call `connect()` yourself
- [x] A reconnect attempt is already scheduled — do nothing
- [ ] The server sent bad data

`CLOSED` (2) is the dead state. `CONNECTING` (0) means auto-retry is working.
</quiz>

<quiz>
Which are real limitations of the native `EventSource` API? *(select all)*
- [x] GET only — no request body
- [x] No custom headers (e.g. `Authorization`)
- [ ] No automatic reconnection
- [x] ~6 connection limit per origin over HTTP/1.1
- [ ] Requires a polyfill in modern browsers

Workarounds for headers: cookies, token in the query string, or
`@microsoft/fetch-event-source`. Reconnect is built in — it's the best part.
</quiz>

Next: [reconnection & heartbeats](reliability.md) — what happens when things
go wrong (they will).

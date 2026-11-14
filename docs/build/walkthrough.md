# Three experiments

Start the app with `uv run demo/server.py` and open <http://127.0.0.1:8765>.
Keep only the clock enabled at first.

## 1. Read an update

Watch **Events received**. A clock update looks like this:

```text
id: 42
event: tick
data: {"time": "2026-11-13T10:30:00+00:00"}

```

- `id` identifies the update; your number will differ.
- `event` names it so JavaScript can listen for `tick`.
- `data` is text containing JSON in this app.
- A blank line finishes the event.

To see the actual stream rather than the page's reconstructed view:

```bash
curl -N "http://127.0.0.1:8765/events?channels=clock"
```

**Takeaway:** SSE is a sequence of small text records in one HTTP response.

## 2. Close the stream

Click **Disconnect**. The clock freezes. Click **Connect** and it updates again.

**Takeaway:** `EventSource.close()` stops receiving and disables automatic retries
for that EventSource. Connect creates a new one.

## 3. Let the browser reconnect

Leave the page connected. Stop the server with `Ctrl-C`, then run it again.
The page moves from open to reconnecting and back to open. Select **Connection**
to read the connection log.

**Takeaway:** the browser normally retries a dropped connection automatically.
This does not mean it recovers missed updates. This demo has no replay store,
and its IDs start over when the server restarts.

## Optional: send a message to two tabs

Open the **Chat** page (`/chat`) in both browser tabs. Each page subscribes only
to chat events. Send a message in one and watch `POST /publish` in DevTools Network.
Both receive it. The browser sends through a separate HTTP POST; the server
sends the resulting chat event through each subscribed SSE stream.

The shared distributor in `server.py` is called a **broker**. It is needed for
this broadcast example, not for SSE itself.

Next: [browser API](../learn/eventsource-api.md) or [reliability](../learn/reliability.md).

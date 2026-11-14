# Run the demo

You need Python 3.9+ and a modern browser. The app uses only Python's standard library.

## 1. Start the server

From the repository directory:

```bash
uv run demo/server.py
```

Alternatively, run `python3 demo/server.py` without installing any dependencies.
Open <http://127.0.0.1:8765>.

## 2. Watch one update flow

The app starts with only the **clock** enabled.

- **Live clock:** the latest time received from the server.
- **Browser code:** how EventSource listens for a `tick` event.
- **Events received:** the event name, data, and ID exposed to JavaScript.

One request stays open. Each new clock value arrives through that same response.

## 3. Stop and start receiving

Click **Disconnect**. The displayed time freezes because the stream is closed.
Click **Connect** to open a new stream.

This is a deliberate close, not an automatic retry. To test automatic retries,
stop the server with `Ctrl-C`, leave the page open, and start the server again.
The browser reconnects without clicking Connect.

## Optional: look at the raw text

In a second terminal:

```bash
curl -N "http://127.0.0.1:8765/events?channels=clock"
```

`-N` tells curl to display data as it arrives. Use `Ctrl-C` to stop it.
Unlike the page's reconstructed event view, curl also shows comments and `retry:`.

## Optional: other examples

Follow the **Stocks** or **Chat** page link. These load new documents at `/stocks`
and `/chat`, each with its own example-specific stream. For chat, open `/chat` in
two browser tabs before sending a message. Sending uses HTTP POST; receiving uses SSE.

The **Connection** page (`/connection`) contains the log and feed checkboxes.
It starts with the clock. Changing feeds opens a new stream unless you have
clicked Disconnect. Click Connect to resume receiving.

## Watch the Network panel

1. Open DevTools → Network, select **All**, and enable **Preserve log**.
2. Click **Clock**, then **Stocks**. Each navigation requests a new HTML document
   and starts a new `/events?channels=...` request. The previous stream closes.
3. Select the stream and inspect **Headers**: the response uses
   `Content-Type: text/event-stream`. The request stays pending because it is live.
4. Open its **EventStream** view (or streaming response view in your browser).
   Clock events arrive regularly; stock events arrive at irregular intervals.
5. On **Chat**, send a message. `POST /publish` completes normally, while the
   existing SSE response delivers the chat event to each subscribed browser tab.
6. On **Connection**, stop and restart the server. Watch automatic retries and,
   after receiving an event ID, the `Last-Event-ID` request header on retry.

Clicking Disconnect deliberately stops retries. Clicking Connect creates a new
EventSource, so it does not preserve the previous object's last event ID.
Navigating also creates a fresh EventSource. This demo has no replay storage.

## Read these docs locally

```bash
uv sync
uv run mkdocs serve -a 127.0.0.1:8001
```

Open <http://127.0.0.1:8001>.

Next: [the basic idea](../learn/what-is-sse.md), or [three experiments](walkthrough.md).

# SSE — one request, many updates

Server-Sent Events (SSE) lets a server send updates through an HTTP response
that stays open. Start with one example: a live clock.

## Run the app

```bash
uv run demo/server.py
```

Open <http://127.0.0.1:8765>. Watch the clock, read the received events, then
try **Disconnect** and **Connect**. The clock is the only enabled feed at startup.

The essential steps are:

1. The browser opens a request with `new EventSource(url)`.
2. The server responds with `Content-Type: text/event-stream`.
3. The server sends text events, each ending with a blank line.
4. JavaScript receives each event and updates the page.

To see the actual stream:

```bash
curl -N "http://127.0.0.1:8765/events?channels=clock"
```

Use the **Clock**, **Stocks**, **Chat**, and **Connection** page links to explore
one concept at a time. These are real document navigations to `/clock`, `/stocks`,
`/chat`, and `/connection`, not in-page tabs. Each page opens a new SSE stream
subscribed only to its example (Connection starts with the clock).

To watch the concepts in action, open **DevTools → Network → All** and enable
**Preserve log** before navigating. Watch the new document request and the pending
`/events?channels=...` response. Select the stream's EventStream view to see updates.
On Chat, sending produces a separate `POST /publish` while the SSE response stays open.

There is no frontend build step or extra dependency. The browser automatically
retries a lost connection, but this demo does **not** replay missed events.

The demo uses only Python's standard library. You can also run it directly
with `python3 demo/server.py` (Python 3.9+), without installing the docs tools.

## Read the docs

```bash
uv sync
uv run mkdocs serve -a 127.0.0.1:8001
```

Open <http://127.0.0.1:8001>. Start with the quickstart and the basic explanation;
protocol details, exercises, quizzes, and deployment guidance are optional next steps.

Build the static docs with `uv run mkdocs build`.

## Where to look

- `demo/server.py`: HTTP server, event formatting, and optional broadcast examples.
- `demo/static/`: browser page, styles, and native EventSource client.
- `docs/`: explanations and guided experiments.
- `mkdocs.yml`: documentation navigation and theme.

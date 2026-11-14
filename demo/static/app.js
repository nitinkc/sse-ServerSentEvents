// SSE demo client — built entirely on the browser's native EventSource API.
const $ = (s) => document.querySelector(s);

let es = null;
let events = 0;
let reconnects = 0;
let disconnected = false;
const page = location.pathname.split('/')[1] || 'clock';
const currentPage = ['clock', 'stocks', 'chat', 'connection'].includes(page) ? page : 'clock';
document.title = `${currentPage[0].toUpperCase() + currentPage.slice(1)} — SSE Studio`;
document.querySelectorAll('[data-page]').forEach((link) => {
  if (link.dataset.page === currentPage) link.setAttribute('aria-current', 'page');
});
document.querySelectorAll('[data-panel]').forEach((panel) => {
  panel.hidden = panel.dataset.panel !== currentPage;
});
document.querySelectorAll('input[type="checkbox"]').forEach((feed) => {
  feed.checked = feed.value === (currentPage === 'connection' ? 'clock' : currentPage);
});
const experiments = {
  clock: 'Watch GET /events?channels=clock stay pending. Open its EventStream view: a tick arrives each second. No repeated HTTP requests are needed.',
  stocks: 'Watch GET /events?channels=stocks. Prices arrive at irregular intervals through the same response, without new requests for each update.',
  chat: 'Open /chat in two browser tabs. Send a message: POST /publish finishes, while GET /events?channels=chat stays pending and receives the broadcast in both tabs.',
  connection: 'Stop and restart the server without closing this page. Watch EventSource retry GET /events. After receiving an ID, an automatic retry sends Last-Event-ID. Clicking Disconnect stops retries; Connect creates a fresh EventSource.'
};
$('#network-experiment').textContent = experiments[currentPage];

function channels() {
  return [...document.querySelectorAll('input[type="checkbox"]:checked')]
    .map((c) => c.value)
    .join(',');
}

function setStatus(state) {
  const el = $('#status');
  el.textContent = state;
  el.className = 'pill ' + state;
}

// Timestamped lifecycle log — makes the connection story visible.
function log(msg, cls = '') {
  const li = document.createElement('li');
  li.className = cls;
  li.innerHTML = `<span class="t">${new Date().toLocaleTimeString()}</span> `;
  li.appendChild(document.createTextNode(msg));
  const list = $('#connlog');
  list.prepend(li);
  while (list.children.length > 30) list.lastChild.remove();
}

// Show every event in the inspector almost exactly as it arrives on the wire.
function inspect(e) {
  events++;
  $('#count').textContent = events;
  $('#lastid').textContent = e.lastEventId || '—';

  const block = document.createElement('div');
  block.className = 'evt';
  block.textContent =
    (e.lastEventId ? `id: ${e.lastEventId}\n` : '') +
    (e.type !== 'message' ? `event: ${e.type}\n` : '') +
    `data: ${e.data}`;

  const box = $('#inspector');
  box.prepend(block);
  while (box.children.length > 50) box.lastChild.remove();
}

function updateStock({ symbol, price, change }) {
  const tbody = $('#stocks tbody');
  let row = tbody.querySelector(`tr[data-sym="${symbol}"]`);
  if (!row) {
    row = document.createElement('tr');
    row.dataset.sym = symbol;
    row.innerHTML = '<td class="sym"></td><td class="price"></td><td class="chg"></td>';
    tbody.appendChild(row);
  }
  row.querySelector('.sym').textContent = symbol;
  row.querySelector('.price').textContent = price.toFixed(2);
  const chg = row.querySelector('.chg');
  chg.textContent = (change > 0 ? '+' : '') + change.toFixed(2);
  chg.className = 'chg ' + (change >= 0 ? 'up' : 'down');
  row.classList.remove('flash-up', 'flash-down');
  void row.offsetWidth; // restart the animation
  row.classList.add(change >= 0 ? 'flash-up' : 'flash-down');
}

function addChat({ name, text, at }) {
  const li = document.createElement('li');
  const when = new Date(at).toLocaleTimeString();
  li.innerHTML = `<span class="who"></span> <span class="what"></span> <span class="when"></span>`;
  li.querySelector('.who').textContent = name + ':';
  li.querySelector('.what').textContent = text;
  li.querySelector('.when').textContent = when;
  const list = $('#chat');
  list.appendChild(li);
  while (list.children.length > 30) list.firstChild.remove();
}

function connect() {
  if (es) es.close();
  const url = `/events?channels=${channels() || 'none'}`;
  $('#streamurl').textContent = url;
  setStatus('connecting');
  log(`connecting → ${url}`);

  // One line is the whole client: open a GET stream and get events.
  es = new EventSource(url);

  es.onopen = () => {
    setStatus('open');
    log('open — stream is flowing', 'good');
  };
  es.onerror = () => {
    // EventSource reconnects BY ITSELF — CONNECTING means a retry is scheduled.
    if (es.readyState === EventSource.CONNECTING) {
      setStatus('reconnecting');
      reconnects++;
      $('#reconnects').textContent = reconnects;
      log('connection lost — auto-reconnecting (retry: 2000)', 'warn');
    } else {
      setStatus('closed');
      log('closed — server refused the stream', 'bad');
    }
  };

  // Named events map to addEventListener(<event field value>).
  es.addEventListener('welcome', (e) => {
    inspect(e);
    const { msg } = JSON.parse(e.data);
    log(`server says: ${msg}`, 'good'); // shows Last-Event-ID resume on reconnect
  });
  es.addEventListener('tick', (e) => {
    inspect(e);
    $('#clock').textContent = new Date(JSON.parse(e.data).time).toLocaleTimeString();
  });
  es.addEventListener('stock', (e) => {
    inspect(e);
    updateStock(JSON.parse(e.data));
  });
  es.addEventListener('chat', (e) => {
    inspect(e);
    addChat(JSON.parse(e.data));
  });
}

$('#reconnect').addEventListener('click', () => {
  disconnected = false;
  connect();
});
$('#disconnect').addEventListener('click', () => {
  disconnected = true;
  if (es) es.close();
  setStatus('closed');
  log('closed — you called es.close()', 'bad');
});
document.querySelectorAll('input[type="checkbox"]').forEach((c) =>
  c.addEventListener('change', () => {
    if (!disconnected) connect();
  })
);

$('#chatform').addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = $('#chattext').value.trim();
  if (!text) return;
  const feedback = $('#chatfeedback');
  try {
    const response = await fetch('/publish', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: $('#chatname').value || 'anon', text }),
    });
    if (!response.ok) throw new Error('Message was not accepted.');
    $('#chattext').value = '';
    feedback.textContent = disconnected
      ? 'Sent. Click Connect to receive messages.'
      : 'Message sent to everyone listening.';
  } catch {
    feedback.textContent = 'Could not send. Check that the server is running and try again.';
  }
});

window.addEventListener('pagehide', () => {
  if (es) es.close();
});
window.addEventListener('pageshow', (event) => {
  if (event.persisted && !disconnected) connect();
});
connect();
